# Errores Comunes y Troubleshooting en Palantir Foundry — Runbook

> Guía práctica de diagnóstico: **Magritte/Agents**, **pipelines/builds**, **Spark**, **Funnel/indexing**, **permisos/markings**, y problemas típicos **on‑prem (OpenShift/Rubix)**.
>
> **Para quién:** cualquiera con algo roto delante. Empieza por el [mapa síntoma → dónde mirar](#2-mapa-rápido-síntoma--dónde-mirar) y salta a la sección que te toque.
>
> Última actualización: 2026-04-08

---

## Índice

1. [Cómo usar este runbook](#1-cómo-usar-este-runbook)
2. [Mapa rápido: síntoma → dónde mirar](#2-mapa-rápido-síntoma--dónde-mirar)
3. [Magritte / Agents](#3-magritte--agents)
4. [Pipelines / Builds](#4-pipelines--builds)
5. [Spark: OOM, skew, shuffle, lentitud](#5-spark-oom-skew-shuffle-lentitud)
6. [Funnel / Indexing / Ontología](#6-funnel--indexing--ontología)
7. [Permisos / Markings / Gobernanza](#7-permisos--markings--gobernanza)
8. [Workshop / Apps](#8-workshop--apps)
9. [AIP / LLMs](#9-aip--llms)
10. [On‑prem (OpenShift/Rubix): fallos clásicos](#10-on-prem-openshiftrubix-fallos-clásicos)
11. [Checklist de “primeros 15 minutos”](#11-checklist-de-primeros-15-minutos)

---

## 1. Cómo usar este runbook

Estrategia recomendada:
1) Identifica **síntoma** (qué falla y para quién).
2) Encuentra **etapa del flujo** (ingesta → transform → ontología → app → action).
3) Aplica pasos:
   - **diagnóstico** (confirmar causa)
   - **fix**
   - **prevención**

---

## 2. Mapa rápido: síntoma → dónde mirar

| Síntoma | Suele ser | Sección |
|---|---|---|
| Sync no corre / Agent offline | red/TLS/proxy/credenciales | [Magritte / Agents](#3-magritte--agents) |
| Build falla | datos malos / permisos / Spark | [Pipelines / Builds](#4-pipelines--builds) |
| OOM o muy lento | skew/shuffle/particiones | [Spark](#5-spark-oom-skew-shuffle-lentitud) |
| “No aparecen objetos” | indexing/Funnel | [Funnel/Indexing](#6-funnel--indexing--ontología) |
| “No veo datos” | permisos/markings/Object Set | [Permisos](#7-permisos--markings--gobernanza) |
| Action falla | validaciones/permisos writeback | [Workshop](#8-workshop--apps) |
| LLM responde vago | grounding insuficiente o permisos | [AIP](#9-aip--llms) |
| Pods Pending / ImagePullBackOff | K8s/registry/CA | [On‑prem](#10-on-prem-openshiftrubix-fallos-clásicos) |

---

## 3. Magritte / Agents

### 3.1 Síntoma: Agent desconectado / no hace sync
**Causas probables**
- TLS/CA no confiable
- proxy corporativo bloquea egress
- DNS/resolución mal
- credenciales expiradas

**Diagnóstico**
- Confirmar conectividad (egress 443, proxy)
- Revisar certificados/CA chain (si hay MITM de proxy, aún más)
- Revisar logs del Agent (errores de auth, handshake TLS)

**Fix**
- Instalar CA corporativa donde corresponda
- Ajustar proxy allowlist
- Rotar credenciales/secretos

**Prevención**
- alertas por “Agent heartbeat”
- rotación programada de certificados/secretos

### 3.2 Síntoma: Sync lenta
**Causas**
- query en source sin índices
- demasiada concurrencia
- red con poco ancho de banda
- API rate limit (si API source)

**Diagnóstico**
- medir tiempo de extracción vs transferencia
- revisar plan de ejecución en DB (si aplica)
- bajar concurrencia y comparar

**Fix**
- índices en columnas de incremental (`updated_at`, PK)
- particionar ingest
- ajustar scheduling

---

## 4. Pipelines / Builds

### 4.1 Síntoma: build falla por permisos
**Causa**
- pipeline no puede leer input o escribir output

**Diagnóstico**
- ¿falla al inicio (lectura) o al final (escritura)?
- comparar permisos entre usuario y service account (si existe)

**Fix**
- otorgar permisos mínimos necesarios al actor correcto
- revisar ownership del dataset output

### 4.2 Síntoma: build falla por datos malos
**Causa**
- schema drift, nulls inesperados, valores fuera de rango

**Diagnóstico**
- validar Bronze vs Silver (dónde se rompe)
- mirar checks de calidad

**Fix**
- endurecer Silver (casts, defaults, quarantine)
- policy de drift: bloquear vs permitir columnas nuevas

---

## 5. Spark: OOM, skew, shuffle, lentitud

### 5.1 OOM (Out Of Memory)
**Causas**
- skew extremo
- shuffle enorme por join mal
- cache innecesario
- particiones muy pocas (tareas gigantes)

**Diagnóstico**
- identificar stage del fallo
- revisar tamaño intermedio (shuffle)
- comprobar keys con cardinalidad rara

**Fix**
- broadcast join (si tabla pequeña)
- salting en join keys con skew
- repartir particiones (repartition) o reducir (coalesce) según caso
- quitar cache y usar persist solo si se reutiliza

### 5.2 Muy lento
**Causas**
- scan completo sin particionado
- join sin filtros
- demasiadas particiones (overhead) o muy pocas (stragglers)

**Fix**
- particionar por fecha/evento
- aplicar filtros lo antes posible
- pre-agregar antes de joins

---

## 6. Funnel / Indexing / Ontología

### 6.1 Síntoma: “actualicé el dataset pero no veo objetos”
**Causas**
- Funnel atrasado o bloqueado
- schema incompatible con el Object Type
- claves/IDs no consistentes

**Diagnóstico**
- verificar si el backing dataset se actualizó
- verificar estado del indexing (cola/latencia)
- comprobar que el ID del objeto no cambia (estabilidad)

**Fix**
- estabilizar claves/ID
- asegurar schema contract
- reindex (si se permite) o revisar configuración del object type

### 6.2 Síntoma: búsqueda no encuentra objetos
**Causas**
- ES8 no actualizado
- properties no indexadas / mappings

**Fix**
- revisar qué campos son “searchables”
- asegurar Funnel indexa esos campos

---

## 7. Permisos / Markings / Gobernanza

### 7.1 “Yo puedo ver, otros no”
**Causas**
- markings (sensibilidad) bloquean
- permisos heredados distintos
- Object Set aplica filtro por política

**Diagnóstico**
- probar con usuario afectado
- revisar roles/grupos
- revisar markings del objeto/dataset

**Fix**
- ajustar políticas (mínimo privilegio)
- crear vistas/objsets específicos por rol

### 7.2 Actions no escriben (writeback)
**Causas**
- permisos de Action
- permisos del writeback dataset
- validación/restricción por estado

**Fix**
- otorgar permiso explícito a ejecutar Action
- revisar quién es el actor (usuario vs service identity)
- mejorar mensajes de error al usuario final

---

## 8. Workshop / Apps

### 8.1 Tabla vacía
- revisar filtros por defecto
- revisar Object Set
- revisar permisos/markings

### 8.2 Action falla en UI
- revisar validaciones
- revisar restricciones por rol/estado
- revisar writeback dataset

---

## 9. AIP / LLMs

### 9.1 Respuestas vagas o genéricas
**Causas**
- grounding insuficiente (poco contexto)
- contexto recortado por permisos/markings
- prompt no orientado a evidencia

**Fix**
- aumentar recuperación con “mínimo necesario”
- exigir evidencia: IDs/propiedades consultadas
- diseñar prompts “con estructura” (resumen + evidencia + recomendación)

### 9.2 Riesgo: prompt injection
**Mitigaciones**
- separar claramente “instrucciones del sistema” de “datos recuperados”
- sanitizar inputs de usuario
- allowlist de tools y parámetros
- human-in-the-loop para write-backs

---

## 10. On‑prem (OpenShift/Rubix): fallos clásicos

| Síntoma | Causa típica | Fix rápido |
|---|---|---|
| `ImagePullBackOff` | registry/credenciales/CA | revisar pull secret y CA del registry |
| Pods `Pending` | falta de recursos/quotas/taints | revisar capacity + requests/limits |
| `CrashLoopBackOff` | config/secret faltante | revisar logs + config injection |
| UI no carga | ingress/routes/TLS/DNS | revisar routes/certs |
| llamadas externas fallan | proxy/egress/TLS | revisar proxy config + allowlist |

---

## 11. Checklist de “primeros 15 minutos”

- [ ] ¿Qué etapa falla? (ingesta / pipeline / ontología / app / action)
- [ ] ¿Afecta a todos o solo a un rol/usuario? (permisos/markings)
- [ ] ¿Hay datos en Bronze? (si no, es ingesta)
- [ ] ¿Silver dedup/checks ok? (si no, es calidad)
- [ ] ¿Gold actualizado? (si no, es build)
- [ ] ¿Indexing al día? (si no, Funnel)
- [ ] ¿On-prem health? (pods pending/pulls/TLS/DNS)
- [ ] ¿Acción requiere permisos/writeback? (si es write)
