# Apollo e Infraestructura en Palantir Foundry — Apuntes

> Guía práctica sobre **Apollo** (sistema de despliegue continuo de Foundry), su relación con **Rubix**, **OpenShift** y **Kubernetes**, el ciclo de vida de despliegues, **Skylab** (configuración y feature flags), consideraciones on-prem y operaciones con **Monocle**.
>
> **Para quién:** perfiles de plataforma/SRE y quien opere Foundry on-prem. Complemento recomendado: el [post-mortem real del repo](../../post-mortem-2026-04-ontologia-highbury.md).
>
> Última actualización: 2026-04-08

---

## Índice

1. [Qué es Apollo y qué problema resuelve](#1-qué-es-apollo-y-qué-problema-resuelve)
2. [Relación con Rubix, OpenShift y Kubernetes](#2-relación-con-rubix-openshift-y-kubernetes)
3. [Ciclo de vida de despliegues](#3-ciclo-de-vida-de-despliegues)
4. [Health checks y config injection](#4-health-checks-y-config-injection)
5. [Skylab: configuración y feature flags](#5-skylab-configuración-y-feature-flags)
6. [Consideraciones on-prem](#6-consideraciones-on-prem)
7. [Operaciones: observabilidad con Monocle](#7-operaciones-observabilidad-con-monocle)
8. [Diagnósticos comunes](#8-diagnósticos-comunes)
9. [Checklist de operación](#9-checklist-de-operación)
10. [Glosario rápido](#10-glosario-rápido)

---

## 1. Qué es Apollo y qué problema resuelve

**Apollo** es el sistema de **despliegue continuo (CD)** y **orquestación de releases** de Palantir Foundry. Gestiona el ciclo de vida completo de todos los servicios que componen la plataforma: instala, actualiza, revierte y supervisa el estado de salud de cada componente.

### 1.1 Problema que resuelve

En una instalación de Foundry existen decenas (o cientos) de microservicios con sus propias versiones, dependencias entre ellas y requisitos de configuración. Hacer esto a mano sería:

- Propenso a errores humanos (versiones incompatibles, config olvidada).
- Lento (coordinar upgrades entre equipos de ops y Palantir).
- Difícil de auditar (¿quién desplegó qué y cuándo?).

Apollo resuelve esto con un modelo **declarativo**: tú defines el estado deseado del clúster; Apollo se encarga de converger la realidad hacia ese estado.

```
┌─────────────────────────────────────────────────────────┐
│                   Apollo Control Plane                  │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│  │ Release Mgr  │   │  Scheduler   │   │  Auditor   │  │
│  │ (versiones)  │   │ (orden deps) │   │ (historial)│  │
│  └──────────────┘   └──────────────┘   └────────────┘  │
│           │                 │                 │         │
│           └─────────────────┼─────────────────┘         │
│                             ▼                           │
│              ┌──────────────────────────┐               │
│              │   Producto "deseado"     │               │
│              │   (manifest declarativo) │               │
│              └──────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
             ┌────────────────────────────────┐
             │   Rubix / OpenShift / K8s       │
             │   (plataforma de ejecución)     │
             └────────────────────────────────┘
```

### 1.2 Capacidades principales

| Capacidad | Descripción |
|---|---|
| **Gestión de versiones** | Catálogo de releases por servicio; compatibilidad garantizada entre versiones |
| **Despliegue continuo** | Instala y actualiza servicios de forma automatizada y ordenada |
| **Rollback** | Revierte a una versión anterior si se detectan fallos |
| **Orquestación de dependencias** | Respeta el orden de inicio/actualización según dependencias entre servicios |
| **Estado deseado vs real** | Modelo de reconciliación continua (similar a operadores de K8s) |
| **Auditoría** | Historial completo de cambios: quién, qué versión, cuándo, resultado |

---

## 2. Relación con Rubix, OpenShift y Kubernetes

Apollo es la **capa de gestión de aplicaciones** de Foundry, pero no ejecuta los contenedores directamente. Para eso delega en una plataforma de orquestación de contenedores subyacente.

### 2.1 Rubix

**Rubix** es la plataforma de orquestación de contenedores **propia de Palantir**, desarrollada antes de que Kubernetes se popularizara. Actúa como la capa de ejecución de contenedores en instalaciones Foundry clásicas (especialmente on-prem legacy).

- Gestiona pods, scheduling y recursos del clúster.
- Apollo le envía las instrucciones de despliegue a través de su API.
- En instalaciones modernas se tiende a sustituir por Kubernetes o a usar Kubernetes vía OpenShift.

### 2.2 OpenShift

**OpenShift** (Red Hat) es una distribución enterprise de Kubernetes con capa de seguridad adicional (SCCs, OAuth, registry propia). Es la opción habitual en entornos corporativos on-prem que ya tienen OpenShift como estándar.

- Apollo puede orquestar sobre OpenShift del mismo modo que sobre Kubernetes nativo.
- Requiere configuración adicional para SCCs (Security Context Constraints) y para el registry privado.

### 2.3 Kubernetes (K8s nativo)

Apollo también puede operar directamente sobre un clúster Kubernetes estándar (EKS, AKS, GKE, RKE2, etc.).

### 2.4 Mapa de capas

```
┌───────────────────────────────────────────────────────────┐
│                    Foundry (servicios)                    │
│  Magritte · Phonograph · OSS · Funnel · Carbon · AIP …   │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │ instala / actualiza
                            │
┌───────────────────────────────────────────────────────────┐
│                      Apollo (CD)                          │
│   gestión de versiones · orquestación · rollback          │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │ crea pods / deployments
                            │
┌───────────────────────────────────────────────────────────┐
│         Plataforma de contenedores (una de estas)         │
│                                                           │
│   ┌──────────┐   ┌────────────┐   ┌────────────────────┐  │
│   │  Rubix   │   │ OpenShift  │   │   Kubernetes (K8s) │  │
│   │ (legacy) │   │ (on-prem)  │   │  (cloud / on-prem) │  │
│   └──────────┘   └────────────┘   └────────────────────┘  │
└───────────────────────────────────────────────────────────┘
                            ▲
                            │
┌───────────────────────────────────────────────────────────┐
│                    Infraestructura                        │
│          Nodos (VMs / bare metal) · Storage · Red         │
└───────────────────────────────────────────────────────────┘
```

| Plataforma | Caso típico | Notas clave |
|---|---|---|
| **Rubix** | On-prem legacy, instalaciones antiguas | Apollo nativo; menos funcionalidades K8s |
| **OpenShift** | On-prem enterprise con estándar Red Hat | SCCs, registry, OAuth; Apollo sobre OCP |
| **Kubernetes** | Cloud (EKS/AKS/GKE) o on-prem moderno | Máxima flexibilidad; Apollo usa CRDs/operators |

---

## 3. Ciclo de vida de despliegues

### 3.1 Flujo general

```
Palantir publica release
         │
         ▼
Apollo descarga el artefacto (imágenes de contenedor + manifests)
         │
         ▼
Apollo valida compatibilidad de versiones (matriz de dependencias)
         │
         ▼
Apollo planifica el orden de despliegue (grafo de dependencias)
         │
         ▼
Apollo despliega servicio a servicio, esperando health checks entre pasos
         │
         ▼
Estado "real" == Estado "deseado"  ✅
```

### 3.2 Install (primera instalación)

1. Apollo recibe el **product manifest** con la lista de servicios y versiones.
2. Crea los namespaces/proyectos necesarios en K8s/OpenShift/Rubix.
3. Inyecta los secrets y ConfigMaps (vía Skylab, ver sección 5).
4. Despliega los servicios base (dependencias de infraestructura) primero.
5. Despliega los servicios de aplicación en el orden definido.
6. Verifica health checks de cada servicio antes de continuar al siguiente.

### 3.3 Upgrade

1. Apollo recibe la nueva versión del producto.
2. Calcula el **diff** entre estado actual y deseado.
3. Actualiza solo los servicios cuya versión cambia (o cuya config cambió).
4. Respeta el orden de dependencias: primero los servicios de los que dependen los demás.
5. Hace rolling update o recreate según la estrategia del servicio.
6. Verifica health checks; si alguno falla, inicia rollback automático del servicio afectado.

```
Estado actual                    Estado deseado
─────────────                    ──────────────
service-A: v1.2.0                service-A: v1.3.0  ← upgrade
service-B: v2.0.1                service-B: v2.0.1  ← sin cambio
service-C: v0.9.5                service-C: v1.0.0  ← upgrade
service-D: v3.1.2                service-D: v3.1.2  ← sin cambio
```

### 3.4 Rollback

Si un despliegue falla (health check negativo, crashloop, error de arranque):

1. Apollo detecta el fallo (timeout en health check o errores continuos).
2. Revierte el servicio afectado a la versión anterior.
3. Re-ejecuta los health checks con la versión anterior.
4. Notifica el fallo con logs y estado detallado.

> ⚠️ El rollback de Apollo es **por servicio**, no del producto completo. Si un upgrade de 10 servicios falla en el servicio 7, revierte el 7 y los que ya se actualizaron pueden quedar en la nueva versión (si son compatibles).

### 3.5 Estrategias de despliegue por servicio

| Estrategia | Comportamiento | Cuándo se usa |
|---|---|---|
| **Rolling update** | Va reemplazando pods gradualmente | Servicios stateless con múltiples réplicas |
| **Recreate** | Para todos los pods y levanta la nueva versión | Servicios stateful o que no toleran dos versiones en paralelo |
| **Canary** | Pequeño porcentaje de tráfico a la nueva versión | Validación progresiva de cambios críticos |

---

## 4. Health checks y config injection

### 4.1 Health checks

Apollo utiliza **dos tipos de health checks** para determinar si un servicio está listo:

| Tipo | Qué verifica | Frecuencia |
|---|---|---|
| **Liveness probe** | El proceso sigue vivo (si falla, K8s/Rubix reinicia el pod) | Continua durante toda la vida del pod |
| **Readiness probe** | El servicio está listo para recibir tráfico (si falla, se saca del balanceo) | Continua; determina si Apollo puede continuar el upgrade |

En el contexto de Apollo, la **readiness probe** es la clave: Apollo espera a que todos los pods de un servicio estén "ready" antes de pasar al siguiente servicio en la cadena de despliegue.

```
Apollo deploys service-A v1.3.0
         │
         ▼
K8s crea nuevos pods
         │
         ▼
Apollo espera readiness (timeout configurable, default ~10 min)
         │
    ┌────┴────┐
    │  Ready? │
    └────┬────┘
         │ Sí                       No (timeout / crashloop)
         ▼                          ▼
Apollo continúa con          Apollo hace rollback
siguiente servicio           y reporta error
```

### 4.2 Config injection

Apollo inyecta configuración en los pods de dos formas:

**1. Variables de entorno** (para config simple):
```
ENV: FOUNDRY_HOST=foundry.empresa.com
ENV: SERVICE_PORT=8080
ENV: LOG_LEVEL=INFO
```

**2. Archivos de configuración montados como volúmenes** (para config compleja):
```
/etc/foundry/config.yml       ← configuración del servicio
/etc/foundry/certs/tls.crt    ← certificados TLS
/etc/ssl/certs/ca-bundle.crt  ← CA bundle corporativo
```

La fuente de esta configuración es **Skylab** (ver sección 5), que actúa como almacén centralizado de config.

---

## 5. Skylab: configuración y feature flags

### 5.1 Qué es Skylab

**Skylab** es el servicio centralizado de **configuración** y **feature flags** de Foundry. Es el punto único desde donde Apollo, los servicios de Foundry y los operadores gestionan toda la configuración del sistema.

### 5.2 Tipos de configuración en Skylab

| Tipo | Ejemplos | Sensibilidad |
|---|---|---|
| **Config de plataforma** | URLs internas, puertos, nombres de namespaces | Baja |
| **Config de integración** | Endpoints de LDAP, URLs de IdP, proxy settings | Media |
| **Secrets / credentials** | Contraseñas de BD, API keys, tokens de servicio | Alta (cifrados) |
| **Certificados** | Certificado TLS del servidor, CA bundle | Alta |
| **Feature flags** | Activar/desactivar funcionalidades en tiempo de ejecución | Variable |

### 5.3 Cómo encaja Skylab con Apollo

```
Operador / Palantir Support
         │
         │ configura valores en
         ▼
┌─────────────────┐
│     Skylab      │  ← almacén central de config (cifrado en reposo)
└─────────────────┘
         │
         │ Apollo lee config al desplegar
         ▼
┌─────────────────┐
│     Apollo      │
└─────────────────┘
         │
         │ inyecta config como
         ├─▶ ConfigMaps
         ├─▶ Secrets (K8s Secrets)
         └─▶ Variables de entorno
                  │
                  ▼
         ┌─────────────────┐
         │  Pod del servicio│
         └─────────────────┘
```

### 5.4 Feature flags en Skylab

Los **feature flags** permiten activar o desactivar funcionalidades sin redesplegar. Casos de uso típicos:

- Habilitar una feature beta solo para ciertos usuarios o tenants.
- Activar modo de mantenimiento en un servicio.
- Cambiar el comportamiento de un servicio sin rollout completo.
- A/B testing de funcionalidades.

```
Feature flag: ENABLE_NEW_FUNNEL_INDEXER = false   ← desactivado por defecto
                                                  ← Skylab actualiza el flag
Feature flag: ENABLE_NEW_FUNNEL_INDEXER = true    ← activado sin redeploy
```

> ⚠️ Skylab persiste la configuración en la base de datos interna de Foundry. En entornos on-prem, es crítico hacer backup de Skylab antes de upgrades de plataforma.

---

## 6. Consideraciones on-prem

### 6.1 Certificados y TLS

En entornos on-prem, la gestión de certificados es uno de los puntos más críticos y más fuente de problemas.

**Certificados necesarios:**

| Certificado | Propósito | Quién lo gestiona |
|---|---|---|
| **TLS del servidor** (wildcard o SAN) | HTTPS para la URL de Foundry | PKI corporativa / Let's Encrypt |
| **CA bundle corporativo** | Validar certificados internos | PKI corporativa |
| **Certificado del registry privado** | Tirar imágenes del registry interno | PKI corporativa |
| **Certificados entre servicios (mTLS)** | Comunicación interna segura entre pods | Apollo / Foundry gestiona internamente |

```
Navegador usuario
       │  HTTPS
       ▼
Load Balancer / Ingress  ◄── Certificado wildcard *.empresa.com
       │
       ▼
Carbon (UI de Foundry)
       │  mTLS interno
       ▼
Otros servicios de Foundry
```

**Problemas típicos con certificados:**

- CA corporativa no está en el trust store de los pods → conexiones a LDAP/SMTP/APIs internas fallan.
- Certificado del servidor expirado → usuarios no pueden acceder.
- Certificado del registry privado no confiado → image pull errors.

**Solución recomendada:** añadir la CA corporativa como `ca-bundle` en la configuración de Skylab para que Apollo la inyecte en todos los pods.

### 6.2 Proxies

En redes corporativas con proxy HTTP/HTTPS de salida:

- Foundry necesita llegar a internet para licencias y actualizaciones (si no es air-gapped).
- El proxy debe estar configurado en Skylab como variable de entorno global.
- Asegurarse de que `NO_PROXY` incluye todos los rangos de red internos (para que el tráfico interno no pase por el proxy).

```yaml
# Ejemplo de configuración de proxy en Skylab
http_proxy: http://proxy.empresa.com:3128
https_proxy: http://proxy.empresa.com:3128
no_proxy: .empresa.com,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
```

### 6.3 Redes y firewalls

Puertos mínimos que deben estar abiertos:

| Origen | Destino | Puerto | Propósito |
|---|---|---|---|
| Nodos K8s | Registry privado | 443/TCP | Pull de imágenes |
| Nodos K8s | LDAP/AD | 389/636 TCP | Autenticación (Multipass) |
| Nodos K8s | NTP | 123/UDP | Sincronización de tiempo |
| Usuarios | Load Balancer | 443/TCP | Acceso a Foundry UI/API |
| Apollo | Rubix/K8s API | 6443/TCP | Control de despliegues |
| Pods Foundry | Palantir Update Server | 443/TCP | Actualizaciones (no air-gapped) |

> ⚠️ Problemas de NTP (sincronización de tiempo) pueden hacer que los tokens de autenticación sean rechazados (drift de reloj).

### 6.4 Entornos air-gapped

Un entorno **air-gapped** es aquel completamente desconectado de internet. Requisitos especiales:

**Registry privado de imágenes:**
- Todas las imágenes de contenedor de Foundry deben ser pre-descargadas y cargadas en el registry privado.
- Apollo apunta al registry interno en lugar del registry de Palantir.

**Servidor de actualizaciones local:**
- Palantir proporciona un "mirror" de actualizaciones para entornos air-gapped.
- Apollo se configura para apuntar a este mirror local.

**Licencias offline:**
- El token de licencia debe renovarse periódicamente contactando a Palantir (por canal seguro, no automáticamente).

```
Entorno air-gapped
──────────────────────────────────────────────────────
                    ┌──────────────────────┐
                    │  Registry privado    │  ← imágenes pre-cargadas
                    │  (Harbor / Nexus)    │
                    └──────────────────────┘
                              ▲
                              │ pull
                    ┌──────────────────────┐
                    │     Apollo           │
                    └──────────────────────┘
                              ▲
                              │
                    ┌──────────────────────┐
                    │  Mirror local de     │  ← releases pre-descargadas
                    │  actualizaciones     │     (por Palantir Support)
                    └──────────────────────┘
──────────────────────────────────────────────────────
          🚫 Sin acceso a internet
```

---

## 7. Operaciones: observabilidad con Monocle

### 7.1 Qué es Monocle

**Monocle** es el sistema de **observabilidad** de Palantir Foundry. Proporciona métricas, trazas y dashboards para monitorizar el estado de los servicios de la plataforma.

### 7.2 Capas de observabilidad

```
┌─────────────────────────────────────────────────────────┐
│                    Monocle                              │
│                                                         │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│   │   Métricas  │  │    Trazas    │  │  Dashboards  │  │
│   │ (series tmp)│  │ (distributed)│  │   (alertas)  │  │
│   └─────────────┘  └──────────────┘  └──────────────┘  │
│            ▲               ▲                ▲           │
│            └───────────────┼────────────────┘           │
└────────────────────────────┼────────────────────────────┘
                             │ scrape / push
              ┌──────────────┴───────────────┐
              │     Servicios de Foundry      │
              │  (exponen métricas /metrics)  │
              └──────────────────────────────┘
```

### 7.3 Métricas clave a monitorizar

| Métrica | Descripción | Umbral de alerta típico |
|---|---|---|
| **Pod restarts** | Número de reinicios de pods | > 3 en 5 min |
| **CPU / Memory usage** | Uso de recursos por pod/namespace | > 80% del límite |
| **API latency** | Latencia de endpoints principales | > 2s (p95) |
| **Pipeline build duration** | Tiempo de ejecución de builds | Desviación > 2σ de la media |
| **Dataset freshness** | Tiempo desde la última actualización de datasets críticos | > SLA configurado |
| **Auth failures** | Fallos de autenticación en Multipass | > umbral por IP/usuario |

### 7.4 Acceso a logs

Los logs de los pods se pueden consultar de tres formas:

**1. Desde la UI de Apollo/Monocle:**
- Navegar al servicio → Pods → seleccionar pod → "View logs"

**2. Desde kubectl (si tienes acceso al clúster):**
```bash
# Ver logs de un pod
kubectl logs -n foundry <pod-name>

# Ver logs con follow
kubectl logs -n foundry <pod-name> -f

# Ver logs de un contenedor específico (pods multi-container)
kubectl logs -n foundry <pod-name> -c <container-name>

# Ver logs de un pod reiniciado (contenedor anterior)
kubectl logs -n foundry <pod-name> --previous
```

**3. Desde el sistema de log agregado** (si está configurado):
- Elasticsearch + Kibana / Grafana Loki / Splunk según lo que tenga el cliente.

---

## 8. Diagnósticos comunes

### 8.1 Pods en estado Pending

**Síntoma:** Pod lleva tiempo en estado `Pending` (no llega a `Running`).

**Causas y diagnóstico:**

| Causa | Cómo verificar | Solución |
|---|---|---|
| **Insuficiente CPU/memoria** en nodos | `kubectl describe pod <pod>` → Events: "Insufficient cpu/memory" | Escalar nodos o ajustar resource requests |
| **Node selector / affinity** sin nodo que coincida | `kubectl describe pod <pod>` → Events: "no nodes match" | Revisar labels de nodos, ajustar affinity rules |
| **PersistentVolumeClaim no bound** | `kubectl get pvc -n foundry` → STATUS != Bound | Verificar StorageClass, provisioner, quotas |
| **Taints en nodos** sin tolerations en el pod | `kubectl describe pod` → "had untolerated taint" | Añadir toleration o eliminar taint del nodo |

```bash
# Diagnóstico rápido de un pod Pending
kubectl describe pod -n foundry <pod-name>
kubectl get events -n foundry --sort-by='.lastTimestamp'
```

### 8.2 Image Pull Errors

**Síntoma:** Pod en estado `ImagePullBackOff` o `ErrImagePull`.

**Causas y diagnóstico:**

| Causa | Cómo verificar | Solución |
|---|---|---|
| **Registry no accesible** | `curl -v https://<registry>/v2/` desde nodo | Verificar red/firewall, certificado del registry |
| **Credenciales incorrectas** | `kubectl describe pod` → "unauthorized" | Actualizar imagePullSecret en Skylab/Apollo |
| **Imagen no existe** en el registry | `docker pull <image>` desde nodo | Asegurarse de que la imagen fue cargada al registry privado |
| **Certificado del registry no confiado** | Error TLS en describe pod | Añadir CA del registry al trust store de los nodos |

```bash
# Verificar imagePullSecrets
kubectl get secret -n foundry | grep registry

# Probar pull manual desde un nodo
crictl pull <image>:<tag>
```

### 8.3 Config errors / crashloop

**Síntoma:** Pod en `CrashLoopBackOff` o que arranca y muere inmediatamente.

**Diagnóstico:**

```bash
# Ver logs del pod que falla (incluyendo intentos anteriores)
kubectl logs -n foundry <pod-name> --previous

# Ver eventos del pod
kubectl describe pod -n foundry <pod-name>

# Ver variables de entorno inyectadas
kubectl exec -n foundry <pod-name> -- env | grep -i foundry
```

**Causas típicas:**

| Causa | Señal en logs | Solución |
|---|---|---|
| **Variable de entorno faltante** | "env variable X not set" / NullPointerException | Revisar config en Skylab; hacer redeploy |
| **Certificado inválido/expirado** | "certificate verify failed" / "x509" | Renovar y reinyectar certificado vía Skylab |
| **Puerto ya en uso** | "address already in use" | Verificar que no hay pods duplicados; revisar servicios con ese puerto |
| **DB no accesible** | "connection refused" / "timeout" | Verificar que la BD está corriendo y accesible desde la red de pods |
| **Config de Skylab inválida** | Error de parsing en arranque | Validar YAML/JSON de config en Skylab |

### 8.4 Upgrade atascado

**Síntoma:** Apollo lleva mucho tiempo en un paso del upgrade sin avanzar.

**Diagnóstico:**

```bash
# Ver el estado del upgrade en la UI de Apollo
# (Deployments → en curso → ver paso actual)

# Ver pods del servicio afectado
kubectl get pods -n foundry -l app=<service-name>

# Ver events recientes
kubectl get events -n foundry --sort-by='.lastTimestamp' | tail -20
```

**Causas:**
- Health check no pasa → revisar logs del pod nuevo.
- Pod en Pending → ver diagnóstico 8.1.
- Rolling update con PodDisruptionBudget muy restrictivo → PDB no permite actualizar (espera disponibilidad).
- Timeout de Apollo demasiado corto para servicios lentos en arrancar → contactar Palantir Support para ajustar.

---

## 9. Checklist de operación

### Antes de un upgrade de Foundry

- [ ] Revisar las **release notes** de la nueva versión (breaking changes, deprecations)
- [ ] Hacer **backup de Skylab** (configuración y secrets)
- [ ] Hacer **backup de la base de datos** de Foundry (Postgres interno / externo)
- [ ] Verificar que hay **suficiente espacio en disco** en nodos y PVs
- [ ] Verificar que el **registry privado** tiene las nuevas imágenes (en air-gapped)
- [ ] Notificar a usuarios del **mantenimiento programado**
- [ ] Tener un **plan de rollback** documentado (versión anterior, procedimiento)
- [ ] Verificar que **Monocle** y el sistema de alertas están funcionando

### Durante el upgrade

- [ ] Monitorizar el **progreso en la UI de Apollo**
- [ ] Observar **Monocle** en tiempo real (métricas, pod restarts)
- [ ] Tener terminal con `kubectl` listo para diagnósticos rápidos
- [ ] No realizar otros cambios de infraestructura en paralelo

### Después del upgrade

- [ ] Verificar **health checks** de todos los servicios en Apollo
- [ ] Ejecutar **smoke tests** básicos (login, cargar un dataset, ejecutar un pipeline)
- [ ] Verificar que los **schedulers de pipelines** siguen funcionando
- [ ] Verificar que la **autenticación SSO** sigue funcionando
- [ ] Revisar Monocle por **anomalías** (latencia, errores)
- [ ] Notificar a usuarios que el sistema está disponible
- [ ] Documentar el upgrade (versión, fecha, incidencias, lecciones aprendidas)

### Operación diaria

- [ ] Revisar **alertas activas** en Monocle
- [ ] Verificar **freshness de datasets** críticos
- [ ] Revisar **pods en estado no-Running** (`kubectl get pods -A | grep -v Running`)
- [ ] Verificar **espacio en disco** de nodos y PVs
- [ ] Revisar **certificados próximos a expirar** (alerta 30 días antes)

---

## 10. Glosario rápido

| Término | Descripción |
|---|---|
| **Apollo** | Sistema de CD y gestión de releases de Foundry |
| **Rubix** | Orquestador de contenedores propio de Palantir (legacy) |
| **Skylab** | Servicio centralizado de configuración y feature flags |
| **Monocle** | Sistema de observabilidad y métricas de Foundry |
| **Air-gapped** | Entorno sin acceso a internet |
| **Readiness probe** | Check que indica si un pod está listo para recibir tráfico |
| **Liveness probe** | Check que indica si un pod sigue vivo |
| **Rolling update** | Estrategia de actualización gradual (pod a pod) |
| **Recreate** | Estrategia de actualización que para todos los pods antes de crear los nuevos |
| **PDB** | PodDisruptionBudget: define el mínimo de pods disponibles durante operaciones |
| **SCC** | SecurityContextConstraints: restricciones de seguridad en OpenShift |
| **Registry privado** | Repositorio interno de imágenes de contenedor (Harbor, Nexus, etc.) |
| **mTLS** | Mutual TLS: autenticación mutua con certificados en ambos extremos |

---

## Referencias

- Ver también: [`01-palantir-foundry-componentes.md`](01-palantir-foundry-componentes.md)
- Ver también: [`08-seguridad-y-gobernanza.md`](08-seguridad-y-gobernanza.md)
- Ver también: [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md)
