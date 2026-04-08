# Seguridad y Gobernanza en Palantir Foundry — Apuntes

> Guía práctica de seguridad y gobernanza en Foundry: modelo de identidad (**Multipass**), autorización (**Gatekeeper**), permisos por recurso, markings, gobernanza de datasets, patrones para pipelines y errores comunes.
>
> Última actualización: 2026-04-08

---

## Índice

1. [Modelo de identidad y autenticación](#1-modelo-de-identidad-y-autenticación)
2. [Autorización: Gatekeeper y modelos RBAC/ABAC/PBAC](#2-autorización-gatekeeper-y-modelos-rbacabacpbac)
3. [Herencia de permisos y estructura de roles/grupos](#3-herencia-de-permisos-y-estructura-de-rolesgrupos)
4. [Permisos por tipo de recurso](#4-permisos-por-tipo-de-recurso)
5. [Markings y sensibilidad de datos](#5-markings-y-sensibilidad-de-datos)
6. [Gobernanza de datasets](#6-gobernanza-de-datasets)
7. [Patrones de seguridad para pipelines](#7-patrones-de-seguridad-para-pipelines)
8. [Errores comunes de permisos](#8-errores-comunes-de-permisos)
9. [Checklist: antes de crear un pipeline/app/ontología](#9-checklist-antes-de-crear-un-pipelineappontología)
10. [Glosario rápido](#10-glosario-rápido)

---

## 1. Modelo de identidad y autenticación

### 1.1 Multipass — el servicio de autenticación de Foundry

**Multipass** es el servicio centralizado de autenticación de Foundry. Gestiona:
- Emisión y validación de **tokens de acceso** (bearer tokens)
- Integración con proveedores de identidad externos (IdP)
- Gestión de usuarios, grupos y service accounts
- Ciclo de vida de tokens (expiración, revocación)

```
[Usuario / Service Account]
         │
         ▼
  ┌─────────────┐      SSO/SAML/OAuth
  │  IdP externo│◄──────────────────────  (LDAP / Azure AD / Okta / etc.)
  └─────────────┘
         │  assertion / id_token
         ▼
  ┌─────────────┐
  │  Multipass  │  ← emite token Foundry (bearer)
  └─────────────┘
         │  token
         ▼
  ┌──────────────────────────────────────┐
  │  Cualquier servicio de Foundry       │
  │  (Carbon UI, Gatekeeper, OSS, etc.)  │
  └──────────────────────────────────────┘
```

### 1.2 Protocolos soportados (conceptual)

| Protocolo | Descripción | Cuándo se usa en Foundry |
|---|---|---|
| **SAML 2.0** | Federación con IdP enterprise (XML assertions) | SSO corporativo (ADFS, Shibboleth, Okta SAML) |
| **OAuth 2.0** | Delegación de autorización mediante tokens | Integraciones programáticas, service accounts |
| **OIDC** | OpenID Connect (OAuth 2.0 + identidad) | SSO moderno, AIP, integraciones cloud |
| **LDAP/AD** | Directorio de usuarios y grupos | Sincronización de grupos en entornos on-prem |

### 1.3 Service accounts

Los **service accounts** son identidades no interactivas usadas por:
- Pipelines (Code Repos, Pipeline Builder)
- Agentes de integración (Magritte Agents)
- Aplicaciones externas que consumen APIs de Foundry

> ⚠️ Un service account sólo debe tener los permisos mínimos necesarios para su función. No reutilizar service accounts entre dominios o entornos.

### 1.4 Flujo completo de autenticación

```
1. Usuario abre navegador → Carbon (UI de Foundry)
2. Carbon redirige a Multipass
3. Multipass redirige al IdP corporativo (SSO)
4. IdP autentica al usuario (password + MFA si aplica)
5. IdP devuelve assertion SAML / id_token OIDC a Multipass
6. Multipass emite bearer token Foundry al usuario
7. Cada llamada a la API de Foundry lleva el bearer token en cabecera
8. El servicio receptor valida el token con Multipass
9. Gatekeeper evalúa si la identidad tiene permisos sobre el recurso solicitado
```

---

## 2. Autorización: Gatekeeper y modelos RBAC/ABAC/PBAC

### 2.1 Gatekeeper — el servicio de autorización de Foundry

**Gatekeeper** es el servicio centralizado que evalúa **si una identidad puede realizar una operación sobre un recurso**.

Cada vez que un usuario o service account intenta acceder a un dataset, ejecutar una acción, o leer un objeto de la Ontología, Gatekeeper evalúa las políticas de acceso en tiempo real.

```
[Petición de acceso]
  identidad: user@empresa.com
  recurso:   /ri.foundry.main.dataset.abc123
  operación: READ
         │
         ▼
  ┌──────────────────────┐
  │     Gatekeeper       │
  │  ┌────────────────┐  │
  │  │  Roles del     │  │
  │  │  usuario       │  │
  │  └────────────────┘  │
  │  ┌────────────────┐  │
  │  │  Markings del  │  │
  │  │  recurso       │  │
  │  └────────────────┘  │
  │  ┌────────────────┐  │
  │  │  Políticas     │  │
  │  │  PBAC          │  │
  │  └────────────────┘  │
  └──────────────────────┘
         │
    ALLOW / DENY
```

### 2.2 Modelos de control de acceso en Foundry

Foundry combina varios modelos:

| Modelo | Descripción | Cómo se aplica en Foundry |
|---|---|---|
| **RBAC** (Role-Based) | Permisos asignados a roles, roles asignados a usuarios/grupos | Roles de proyecto (Owner, Editor, Viewer) asignados a grupos Multipass |
| **ABAC** (Attribute-Based) | Decisiones basadas en atributos del usuario y del recurso | Markings combinados con atributos de usuario (clasificación, departamento) |
| **PBAC** (Policy-Based) | Políticas explícitas que combinan condiciones complejas | Gatekeeper policies para casos avanzados (hora, red, contexto) |

> En la práctica diaria, lo que más se manipula es RBAC (roles de proyecto) con soporte de markings (ABAC). PBAC aparece en configuraciones de seguridad avanzadas o multi-tenant.

### 2.3 Roles estándar de Foundry

| Rol | Permisos típicos |
|---|---|
| **Owner** | CRUD completo + gestión de permisos del recurso |
| **Editor** | Leer + escribir/modificar contenido; no gestiona permisos |
| **Viewer** | Solo lectura |
| **Discoverer** | Puede ver que el recurso existe (nombre/metadatos), pero no su contenido |
| **Builder** (en repos) | Puede ejecutar builds / transformaciones |
| **Commenter** | Solo puede añadir comentarios/anotaciones |

---

## 3. Herencia de permisos y estructura de roles/grupos

### 3.1 Jerarquía de herencia

Los permisos en Foundry se heredan de forma jerárquica:

```
[Organización / Enrollment]
         │  herencia
         ▼
   [Proyecto (Project)]
         │  herencia
         ▼
   [Carpeta (Folder)]
         │  herencia
         ▼
   [Recurso (Dataset / Repo / Workbook / ...)]
```

Un permiso asignado en un proyecto se hereda por todas las carpetas y recursos dentro de ese proyecto, salvo que se sobreescriba explícitamente en un nivel inferior.

### 3.2 Grupos vs usuarios individuales

**Siempre que sea posible, asignar permisos a grupos, no a usuarios individuales:**

| Asignación | Pro | Contra |
|---|---|---|
| **Grupos** | Escalable, mantenible, auditado en el IdP | Requiere disciplina en la gestión del IdP |
| **Usuarios individuales** | Rápido para excepciones puntuales | Difícil de auditar, riesgo de permisos olvidados |

> Los grupos pueden ser grupos de Multipass (definidos en Foundry) o grupos sincronizados desde LDAP/AD corporativo.

### 3.3 Ejemplo práctico de estructura de permisos

```
Proyecto: "Supply Chain Analytics"
├── Owners:   grupo-sc-engineers
├── Editors:  grupo-sc-analysts
└── Viewers:  grupo-sc-business-users
    │
    ├── Carpeta: "Datos Brutos (Bronze)"
    │   └── Editors adicionales: grupo-magritte-service-accounts
    │
    ├── Carpeta: "Transformaciones (Silver/Gold)"
    │   └── Editors adicionales: grupo-pipeline-service-accounts
    │
    └── Carpeta: "Ontología y Apps"
        └── (hereda permisos del proyecto)
```

---

## 4. Permisos por tipo de recurso

### 4.1 Proyectos y carpetas

| Acción | Rol mínimo requerido |
|---|---|
| Ver nombre/existencia del proyecto | Discoverer |
| Ver contenido (listar recursos) | Viewer |
| Crear/modificar recursos dentro | Editor |
| Eliminar el proyecto | Owner |
| Cambiar permisos del proyecto | Owner |

### 4.2 Datasets

| Acción | Rol mínimo requerido |
|---|---|
| Leer datos (query/preview) | Viewer |
| Ver esquema y metadatos | Viewer |
| Escribir nueva transacción | Editor |
| Cambiar permisos | Owner |
| Ver linaje (upstream/downstream) | Viewer (sobre los recursos visibles) |

> ⚠️ Un usuario puede ver que un dataset existe (Discoverer) pero no poder leer su contenido (sin Viewer). Esto es un error frecuente.

### 4.3 Code Repositories

| Acción | Rol mínimo requerido |
|---|---|
| Clonar / leer código | Viewer |
| Hacer commit / push | Editor |
| Ejecutar builds | Editor o Builder |
| Merge/approve PRs | Editor (+ políticas de branch) |
| Gestionar permisos del repo | Owner |

### 4.4 Workbooks (Code Workbooks)

| Acción | Rol mínimo requerido |
|---|---|
| Ver el workbook | Viewer |
| Ejecutar celdas | Editor |
| Editar código | Editor |
| Compartir el workbook | Owner |

### 4.5 Ontología: Object Types y Actions

| Acción | Configuración necesaria |
|---|---|
| Leer objetos de un Object Type | El usuario debe ser Viewer del backing dataset **Y** tener permiso de lectura sobre el Object Type en Gatekeeper |
| Ejecutar una Action | Permiso explícito de ejecución sobre la Action (configurado en la definición de la Action) |
| Modificar la definición de un Object Type | Editor/Owner del proyecto de la Ontología |
| Ver las propiedades de un Object Type | Permiso de Viewer sobre el Object Type |

```
[Usuario quiere leer objetos "Pedido"]
         │
         ▼
  ¿Tiene Viewer en backing dataset? ──NO──▶ 403 "Dataset not found/accessible"
         │YES
         ▼
  ¿Tiene permiso en el Object Type?  ──NO──▶ Objeto no aparece en búsquedas
         │YES
         ▼
  ¿El objeto tiene markings?          ──SÍ─▶ ¿El usuario tiene el marking? ──NO──▶ Objeto filtrado
         │NO (o sí y tiene markings)
         ▼
  Objeto visible ✓
```

### 4.6 Workshop (Apps)

| Acción | Configuración necesaria |
|---|---|
| Usar una app Workshop | El usuario debe tener Viewer sobre la app Workshop **Y** sobre los recursos que la app consume |
| Editar/diseñar la app | Editor de la app Workshop |
| Ejecutar Actions desde la app | Permiso de ejecución sobre cada Action invocada |

> Las apps Workshop **no elevan permisos**. Si el usuario no tiene acceso al dataset subyacente, la app no puede leerlo en su nombre.

### 4.7 Ontología: Actions y writeback

Para que una Action pueda escribir (writeback):
1. El **service account** de la Action debe tener permisos de **Editor** sobre el dataset de writeback.
2. El **usuario** que ejecuta la Action debe tener permiso de **ejecución** sobre esa Action.
3. Las **validaciones** de la Action deben pasar (campos obligatorios, rangos, etc.).

---

## 5. Markings y sensibilidad de datos

### 5.1 ¿Qué son los markings?

Los **markings** son etiquetas de clasificación de sensibilidad que se aplican a recursos (datasets, carpetas, Object Types). Un usuario solo puede acceder a recursos que tienen markings **que él también posee**.

```
Dataset "clientes_pii"
├── Marking: CONFIDENTIAL
└── Marking: GDPR-PII

Usuario A: tiene markings [CONFIDENTIAL, GDPR-PII]  → puede acceder ✓
Usuario B: tiene markings [CONFIDENTIAL]             → no puede acceder ✗
Usuario C: no tiene markings                          → no puede acceder ✗
```

### 5.2 Tipos de markings habituales

| Tipo | Descripción |
|---|---|
| **Clasificación de seguridad** | PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED |
| **Protección de datos** | GDPR-PII / HIPAA / datos sensibles según regulación |
| **Origen/dominio** | Por división de negocio o geografía |
| **Compartición externa** | Controla si datos pueden salir a partners/proveedores |

### 5.3 Markings en la práctica

- Los markings se configuran en el recurso (dataset, carpeta, etc.).
- Los markings se asignan a usuarios/grupos en la gestión de Multipass/Gatekeeper.
- Un recurso sin markings es accesible por cualquier usuario con Viewer o superior.
- Un recurso con markings solo es accesible a usuarios que **poseen todos** los markings requeridos.

### 5.4 Auditoría de acceso

Foundry registra todos los accesos a recursos, especialmente los que fallan por markings/permisos. Los logs de auditoría permiten:
- Detectar intentos de acceso no autorizado.
- Demostrar cumplimiento regulatorio (GDPR, SOC2, etc.).
- Investigar incidentes de seguridad.

> Los logs de auditoría se consultan normalmente desde el panel de administración de Foundry o exportándolos a un SIEM externo.

---

## 6. Gobernanza de datasets

### 6.1 Ownership

Cada dataset debe tener un **owner claro** (persona o equipo). El owner es responsable de:
- Mantener la calidad y documentación del dataset.
- Revisar solicitudes de acceso.
- Decidir la política de sharing.
- Gestionar el ciclo de vida (deprecación, archivado).

> Foundry permite asignar ownership explícito a nivel de dataset/carpeta/proyecto. Sin owner asignado, el dataset "orphan" es una fuente de deuda técnica y riesgo de seguridad.

### 6.2 Publishing y visibilidad

| Estado | Significado |
|---|---|
| **Privado** | Solo accesible a quien tiene permisos explícitos |
| **Publicado** | Visible en catálogo/búsqueda para usuarios con permisos de discovery |
| **Compartido externamente** | Accesible fuera del enrollment habitual (requiere marking especial) |

### 6.3 Lineage y metadata

El **linaje** (lineage) permite rastrear el origen de cada dato:
- ¿De qué source externo vienen los datos? (ver [`data-integration-magritte.md`](data-integration-magritte.md))
- ¿Qué transformaciones se aplicaron? (ver [`pipelines-y-transformaciones.md`](pipelines-y-transformaciones.md))
- ¿Qué datasets downstream dependen de este?

```
Source (SAP ERP)
    │
    ▼  [Magritte sync]
raw_orders  (bronze)
    │
    ▼  [Pipeline Python]
orders_clean  (silver)
    │
    ├──▶  orders_fact  (gold)
    │          │
    │          ▼  [Funnel indexing]
    │     Object Type: "Pedido"
    │
    └──▶  orders_monthly_agg  (gold, BI)
```

El linaje de Foundry **incluye** accesos, modificaciones y quién hizo qué y cuándo.

### 6.4 Principio de acceso mínimo

| Principio | Aplicación práctica en Foundry |
|---|---|
| **Need-to-know** | Solo dar acceso a quien lo necesita para su trabajo |
| **Least privilege** | Dar el rol mínimo necesario (Viewer vs Editor vs Owner) |
| **Segregación de entornos** | dev / pre / prod con permisos separados |
| **Revisión periódica** | Auditar accesos cada trimestre o cuando cambian roles |

---

## 7. Patrones de seguridad para pipelines

### 7.1 Service accounts para pipelines

**Nunca usar cuentas de usuario personal para ejecutar pipelines en producción.** Usar service accounts dedicados:

```
pipeline-sa-bronze@foundry          ← solo escribe en bronze
pipeline-sa-silver@foundry          ← lee bronze, escribe silver
pipeline-sa-gold@foundry            ← lee silver, escribe gold
magritte-sa-erp@foundry             ← solo lee source ERP
```

Cada SA tiene los permisos mínimos necesarios para su función.

### 7.2 Separación de entornos: dev / pre / prod

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DEV           │    │   PRE/STAGING   │    │   PROD          │
│                 │    │                 │    │                 │
│ Datos sintéticos│    │ Datos anonimiz. │    │ Datos reales    │
│ Acceso amplio   │    │ Acceso restrin. │    │ Acceso mínimo   │
│ (engineers)     │    │ (QA + eng)      │    │ (solo SAs + ops)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                      │                      │
        └──────── Nunca mezclar permisos entre entornos ─────────┘
```

**Prácticas recomendadas:**
- Proyectos separados por entorno (no carpetas dentro del mismo proyecto).
- Service accounts distintos por entorno (no reutilizar SA de dev en prod).
- Los ingenieros tienen Editor en dev, Viewer en prod (o sin acceso a datos reales PII).
- Las credenciales de sources de producción solo las conoce el SA de prod.

### 7.3 Secretos y credenciales en Magritte

Para las conexiones de Magritte (fuentes externas):
- Las credenciales (usuario/contraseña de BD, API keys) se guardan en la configuración de la **Connection** de Foundry, **nunca en código**.
- Los secretos en Code Repositories se gestionan mediante el mecanismo de **secrets** de Foundry (no hardcodeados en el repo Git).
- Rotación periódica de credenciales (recomendado: cada 90 días o según política).

```python
# MAL: credenciales en código
connection = connect(
    host="db.empresa.com",
    user="admin",
    password="supersecret123"  # ❌ NUNCA
)

# BIEN: usar la Connection de Magritte o las variables de entorno/secrets de Foundry
# El SA solo necesita permiso sobre la Connection configurada en Foundry
```

Ver también: [`data-integration-magritte.md`](data-integration-magritte.md) — sección 8 (Seguridad y red).

### 7.4 Seguridad en Code Repositories

| Práctica | Por qué |
|---|---|
| Revisar PRs antes de merge | Detectar código malicioso o que eluda permisos |
| No commitear credenciales | Usar secrets de Foundry o variables de entorno |
| Branch protection en `main`/`master` | Evitar escrituras directas sin revisión |
| Limitar quién puede crear repos | Evitar repos huérfanos sin owner |

---

## 8. Errores comunes de permisos

### 8.1 Build que falla por permisos

**Síntoma:** El pipeline falla con error de tipo `403 Forbidden`, `Access Denied` o `Dataset not found`.

| Causa | Diagnóstico | Solución |
|---|---|---|
| El SA del pipeline no tiene Viewer sobre el dataset de entrada | Revisar logs del build, buscar el RID del dataset | Dar Viewer al SA sobre ese dataset |
| El SA no tiene Editor sobre el dataset de salida | El build escribe un dataset nuevo/existente | Dar Editor al SA sobre el dataset destino |
| El SA no tiene acceso al repo del pipeline | Error al clonar el código | Dar Viewer al SA sobre el Code Repository |
| El dataset de entrada tiene markings que el SA no posee | El SA "no ve" el dataset | Asignar el marking correspondiente al SA |

### 8.2 Actions que no escriben (writeback fallido)

**Síntoma:** El usuario ejecuta una Action en Workshop pero los datos no se actualizan.

| Causa | Diagnóstico | Solución |
|---|---|---|
| El SA de la Action no tiene Editor sobre el writeback dataset | Revisar logs de la Action | Dar Editor al SA de la Action sobre el dataset |
| El usuario no tiene permiso de ejecución sobre la Action | La Action no aparece en Workshop o da error | Asignar permiso de ejecución al usuario/grupo |
| La validación de la Action falla silenciosamente | Revisar el resultado de la Action (status) | Revisar reglas de validación de la Action |
| El Object Type no tiene writeback dataset configurado | La acción no sabe dónde escribir | Configurar el writeback dataset en la definición del Object Type |

### 8.3 Usuarios que no ven objetos (Object Type invisible)

**Síntoma:** El usuario busca objetos en Object Explorer o Workshop pero no aparecen.

| Causa | Diagnóstico | Solución |
|---|---|---|
| No tiene Viewer sobre el backing dataset | Probar acceder al dataset directamente | Dar Viewer al usuario/grupo sobre el dataset |
| No tiene permiso sobre el Object Type | Revisar configuración del Object Type en Gatekeeper | Asignar permiso de lectura sobre el Object Type |
| El objeto tiene markings que el usuario no posee | Revisar markings del dataset/Object Type | Asignar el marking al usuario, o quitar marking si no corresponde |
| El índice de la Ontología está desactualizado | El build/funnel no ha indexado aún los objetos | Esperar a que termine el indexing, o forzar rebuild del Funnel |

### 8.4 Indexing bloqueado

**Síntoma:** Los objetos de la Ontología no se actualizan aunque el pipeline haya terminado correctamente.

| Causa | Diagnóstico | Solución |
|---|---|---|
| Funnel no tiene permiso sobre el backing dataset | Revisar logs de Funnel/Indexing | Dar Viewer al service account de Funnel/Indexing |
| El dataset de backing no tiene la columna PK esperada | El esquema cambió | Revisar definición del Object Type y el backing dataset |
| Hay un marking en el dataset que bloquea al SA de indexing | Revisar markings del dataset | Asignar marking al SA de indexing o revisar política |
| Build dependiente no ha terminado | El indexing espera al build | Revisar estado del Build graph y dependencias |

### 8.5 Tabla resumen de errores frecuentes

| Síntoma | Dónde buscar | Solución probable |
|---|---|---|
| `403 Forbidden` en build | Logs del pipeline, permisos del SA | Revisar permisos del SA de pipeline |
| Action no escribe | Logs de Action, permisos del SA de Action | Editor sobre writeback dataset |
| Objeto no visible | Gatekeeper, markings, backing dataset | Viewer + marking correcto |
| Indexing no avanza | Logs de Funnel, permisos, build graph | Permisos de Funnel, dataset schema |
| App Workshop vacía | Permisos del usuario sobre recursos de la app | Viewer sobre datasets/Object Types usados |
| "Dataset not found" | ¿Existe? ¿Permisos? ¿Marking? | Discoverer mínimo, revisar markings |

---

## 9. Checklist: antes de crear un pipeline/app/ontología

### 9.1 Para un nuevo pipeline

- [ ] Existe un **service account dedicado** para este pipeline (no usar cuenta personal)
- [ ] El SA tiene **Viewer** sobre todos los datasets de entrada
- [ ] El SA tiene **Editor** sobre todos los datasets de salida
- [ ] Las **credenciales de fuentes externas** están en la Connection de Magritte (no en código)
- [ ] El pipeline está en el **entorno correcto** (dev/pre/prod separados)
- [ ] Se ha definido el **owner** del dataset de salida
- [ ] Se han aplicado **markings** adecuados a los datasets con datos sensibles
- [ ] El pipeline tiene **tests de calidad de datos** básicos
- [ ] Se ha revisado el **linaje** (que los datos fuente tienen permisos correctos)
- [ ] El código ha sido **revisado** antes de merge a main

### 9.2 Para una nueva app Workshop

- [ ] Los **usuarios finales** tienen Viewer sobre la app y los recursos que usa
- [ ] Las **Actions** tienen configurado un SA con Editor sobre el writeback dataset
- [ ] El SA de las Actions tiene permisos solo para los **recursos necesarios** (mínimo privilegio)
- [ ] Los **Object Types** consumidos por la app son visibles para los usuarios finales
- [ ] Se ha probado la app con un usuario **sin privilegios de admin** para verificar que todo es accesible
- [ ] Los markings de los datos son **compatibles con los usuarios** que usarán la app

### 9.3 Para un nuevo Object Type / pieza de Ontología

- [ ] El **backing dataset** tiene permisos correctos (Viewer para los SA de indexing/Funnel)
- [ ] Se ha definido la **Primary Key** (estable, no nula, no reutilizable)
- [ ] El Object Type tiene **owner** asignado
- [ ] Los **markings** del Object Type son coherentes con los del backing dataset
- [ ] Las **Actions** del Object Type tienen writeback dataset configurado
- [ ] El **indexing/Funnel** tiene permisos sobre el backing dataset
- [ ] Se ha validado que el backing dataset llega correctamente al **build de Funnel**

---

## 10. Glosario rápido

| Término | Descripción |
|---|---|
| **Multipass** | Servicio de autenticación de Foundry (tokens, SSO, service accounts) |
| **Gatekeeper** | Servicio de autorización centralizado (RBAC/ABAC/PBAC) |
| **Service Account (SA)** | Identidad no interactiva para pipelines y servicios |
| **RBAC** | Role-Based Access Control: permisos por rol |
| **ABAC** | Attribute-Based Access Control: permisos por atributos del usuario/recurso |
| **PBAC** | Policy-Based Access Control: permisos por políticas complejas |
| **Marking** | Etiqueta de clasificación de sensibilidad en un recurso |
| **Owner** | Rol con control total sobre un recurso, incluido gestión de permisos |
| **Editor** | Rol con permisos de lectura y escritura, sin gestionar permisos |
| **Viewer** | Rol de solo lectura |
| **Discoverer** | Rol que permite ver la existencia de un recurso pero no su contenido |
| **Backing Dataset** | Dataset que alimenta un Object Type en la Ontología |
| **Funnel** | Servicio que indexa datasets hacia la Ontología (requiere permisos sobre el backing dataset) |
| **Writeback Dataset** | Dataset donde una Action escribe los cambios del usuario |
| **Lineage** | Trazabilidad del origen y transformaciones de un dataset |
| **Enrollment** | Instancia/organización de Foundry (nivel más alto de la jerarquía) |

---

## Referencias

- Ver también: [`palantir-foundry-componentes.md`](palantir-foundry-componentes.md) — sección 6 (Gobernanza y Metadatos)
- Ver también: [`ontologia-foundry.md`](ontologia-foundry.md) — sección 4 (Actions) y sección 8 (Writeback)
- Ver también: [`data-integration-magritte.md`](data-integration-magritte.md) — sección 8 (Seguridad y red)
- Ver también: [`pipelines-y-transformaciones.md`](pipelines-y-transformaciones.md) — sección 11 (Troubleshooting)
