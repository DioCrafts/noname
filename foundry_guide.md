# Dashboard de Monitorización de Componentes Críticos en Palantir AIP Foundry Workshop

## Resumen Ejecutivo

Este documento describe cómo diseñar e implementar un **dashboard de ingeniería en Palantir Workshop** para monitorizar en tiempo real el estado de los componentes críticos de la plataforma AIP Foundry. El objetivo es proporcionar a los ingenieros una visión unificada del estado de servicios como la indexación, OSS, Highbury, builders, Cassandra y el resto de la capa de microservicios — permitiendo reacción inmediata ante cualquier incidencia.

La plataforma AIP + Foundry está compuesta por **más de 300 microservicios**, todos orquestados sobre Kubernetes mediante Apollo y Rubix. Entender qué monitorizar, dónde obtener los datos y cómo construir el dashboard en Workshop es la clave para una operación resiliente.[^1]

El documento se divide en dos partes:

- **Parte 1 — Referencia Técnica**: Arquitectura, componentes, métricas y diseño del dashboard.
- **Parte 2 — Guía Paso a Paso**: Implementación práctica clic por clic en Foundry.
- **Apéndice**: Prompt de IA para copiloto operacional en AIP Logic / Workshop.

---

# PARTE 1 — REFERENCIA TÉCNICA

## Arquitectura de la Plataforma: Qué Monitorizar

### La Tríada Central: AIP + Foundry + Apollo

El stack de Palantir se organiza en tres plataformas integradas:[^2][^3]

- **Foundry**: plataforma de operaciones de datos — gestión, pipelines, ontología, analíticas y aplicaciones.
- **AIP**: plataforma de IA generativa — conectividad a LLMs, agents, automations y evaluación de workflows.
- **Apollo**: continuous delivery platform — gestiona actualizaciones zero-downtime de cientos de servicios cada día.

Toda esta infraestructura corre sobre **Rubix**, la implementación hardened de Kubernetes de Palantir, que ofrece autoscaling dinámico, ephemerality obligatoria de nodos (máximo 48 horas) y alta disponibilidad built-in.[^4]

### Mapa de Componentes Críticos

#### 1. Capa de Ontología — Object Storage & OSS

El backend de la Ontología usa una **arquitectura de microservicios** en la que múltiples servicios trabajan juntos para indexar, almacenar, consultar y manipular objetos:[^5][^6]

| Servicio | Función | Qué Monitorizar |
|----------|---------|-----------------|
| **Object Storage V2 (OSv2)** | Almacén canónico de objetos de Ontología (next-gen) | Estado de indexación, disk space, throughput (límite 2 MB/s/object type)[^7] |
| **Object Storage V1 / Phonograph** | Backend legacy (*deprecación planificada: 30 jun 2026*)[^8] | Estado de migración a OSv2, jobs activos |
| **Object Set Service (OSS)** | Sirve todas las lecturas de la Ontología — búsqueda, filtrado, agregaciones[^6] | Query latency P95, error rate, disponibilidad |
| **Object Data Funnel ("Funnel")** | Microservicio que orquesta escrituras e indexación en la Ontología[^5] | Scroll jobs (failures consecutivos), pipeline batch/streaming status |
| **Ontology Metadata Service (OMS)** | Define todos los tipos de entidades ontológicas (object types, link types, action types)[^9] | Errores de definición, inconsistencias de schema |

> **Nota sobre "Highbury"**: El nombre "Highbury" no aparece en la documentación pública de Palantir — es muy probable que sea el nombre interno de un componente del stack de búsqueda o indexación dentro de Object Storage. En la práctica, este componente se monitoriza a través del estado del Funnel y las métricas de OSS (latencia de búsqueda, errores de index). Coordina con tu Palantir representative para confirmar el mapping exacto en tu enrollment.

#### 2. Indexación (Funnel Pipelines)

La indexación en la Ontología es gestionada por el **Object Data Funnel**. Existen dos tipos de pipelines:[^10]

- **Funnel batch pipelines**: indexación sobre datasources estáticos o actualizados por schedule.
- **Funnel streaming pipelines**: indexación de baja latencia sobre streaming datasources (Kafka, etc.).[^7]

Métricas clave a monitorizar para indexación:

- **Scroll jobs**: responsables de transmitir datos del datasource a las databases de objetos. Un fallo en scroll jobs indica que los datos de Ontología se quedan desactualizados.[^11]
- **Consecutive scroll job failures**: recomendación de Palantir — alerta LOW a 1 fallo, MEDIUM a 3, HIGH a 7.[^11]
- **Disk space de search nodes**: si no hay espacio, los jobs de indexación fallan silenciosamente.[^7]
- **Throughput**: por defecto limitado a 2 MB/s por object type; si se supera, contactar soporte.[^7]
- **Pipeline graph status**: verde = indexación completa y lista para queries desde OSv2.[^7]

#### 3. Data Connection & Agentes (Magritte)

El servicio **magritte-coordinator** es el coordinador central de todos los agentes de Data Connection. Los agentes son bootstrappers instalados on-premise (o en red del cliente) que hacen de puente entre los sistemas de datos externos y Foundry.[^12]

Métricas críticas para agentes:

- **Agent heartbeat**: alerta cuando el último heartbeat supera un umbral configurado. Un agente sin heartbeat implica pérdida de sincronización de datos.[^11]
- **Job queue depth**: recomendación de alertar cuando supere **70 jobs en cola**.[^11]
- **Consecutive schedule failures**: umbral de 1 fallo = MEDIUM, 3 fallos = HIGH.[^11]

#### 4. Pipeline Builder / Builders (Compute)

Pipeline Builder es la aplicación principal de integración de datos, usando **Spark y Flink** como motores de ejecución. El "builders" en el contexto de la plataforma se refiere tanto a los builds de pipelines como a los Code Repository builds.[^13]

| Componente | Métricas a Monitorizar |
|------------|------------------------|
| **Build schedules** | Consecutive failures, última ejecución exitosa, duración media |
| **Spark compute** | Driver/executor memory, CPU cores, número de executors, duration P95[^14] |
| **Streaming pipelines** (Flink/Kafka) | Lag de consumo, offset del topic, errores de procesamiento[^15] |
| **Incremental pipelines** | Estado de incrementalidad, errores de schema change |

#### 5. Cassandra (Fuente de Datos Externa)

En el contexto de Foundry, **Cassandra** aparece como un conector de base de datos externo gestionado a través de Data Connection. Si Cassandra es una fuente de datos crítica en tu plataforma, lo que debes monitorizar es:[^16]

- Estado del **Data Connection agent/sync** asociado al cluster Cassandra (heartbeat, job queue).
- Latencia y errores del **Funnel pipeline** que indexa los datos de Cassandra en la Ontología.
- **Health checks** sobre los datasets derivados de Cassandra (schema changes, row count anomalías, tiempo desde última actualización).

#### 6. Capa AIP

| Servicio AIP | Función | Métricas |
|--------------|---------|----------|
| **AIP Logic** | Clasificación y razonamiento con LLMs[^17] | Success/failure counts, P95 execution duration (disponible en Ontology Manager)[^18] |
| **Actions** | Aplica edits de usuarios a object databases[^6] | Throughput, error rate, latency |
| **Automations (Automate)** | Triggers event-driven sobre cambios en objetos[^19] | Execution failures, trigger delays |
| **AIP Agents** | Workflows autónomos con LLMs[^20] | Execution history, trace errors, token usage |
| **Functions** | Logic server-side para dashboards y apps[^21] | P95 latency, consecutive failures[^20] |

#### 7. Infraestructura: Apollo & Rubix

- **Apollo**: gestiona upgrades, rollbacks y deployment de cada uno de los 300+ microservicios. Monitorizar el estado de deployments activos y cualquier rollback automático.[^22]
- **Rubix** (Kubernetes): node cycling obligatorio cada 48 horas. Monitorizar pods en CrashLoopBackOff, pending nodes, autoscaling events.[^4]
- **Compute Modules**: contenedores Docker serverless deployados en la mesh. Monitorizar disponibilidad y latencia de respuesta.[^23]

#### 8. Streaming Datasets (Kafka/Streams)

Los streaming datasets son first-class citizens en Foundry. Para cada stream crítico monitorizar:[^24]

- **Metrics tab** del stream: throughput, lag, batch size (si batch size = max batch size → considerar HIGH_THROUGHPUT mode).[^24]
- **Live deployment health**: estado en Monitoring Views con scope de proyecto.[^25]
- Errores de Kafka producer/consumer, SSL auth failures.

---

## Herramientas Nativas de Observabilidad en Foundry

Antes de construir el dashboard en Workshop, es clave entender el stack de observabilidad built-in que sirve como **fuente de verdad** para los datos del dashboard:[^18]

| Herramienta | Capacidades | Uso en el Dashboard |
|-------------|-------------|---------------------|
| **Data Health** | Monitoring views + health checks, alertas a PagerDuty/Slack[^26] | Fuente de datos de estado de datasets, schedules, object types |
| **Workflow Lineage** | 7 días de historial de ejecución, logs, distributed tracing[^18] | Drill-down de incidencias desde el dashboard |
| **AIP Observability** | Metrics, execution history, distributed tracing, logs de LLM calls[^20] | Status de AIP Logic, Agents, Functions |
| **Data Lineage** | Grafo de linaje coloreado por estado de health checks[^27] | Bird's-eye view de la pipeline health |
| **Internal Dataset Export** | Datasets internos de uso de infraestructura (compute, storage)[^28] | Métricas de capacidad y optimización |
| **Streams Metrics Tab** | Métricas de health de streaming workloads[^18] | Estado de Kafka streams |

---

## Arquitectura del Dashboard en Workshop

### Principios de Diseño

El **three-panel layout** es el gold standard para dashboards operacionales en Workshop:[^29]
1. Panel izquierdo: selección/filtros (por componente, por severidad, por proyecto).
2. Panel central: lista de alertas activas o estado de recursos.
3. Panel derecho: detalle del componente seleccionado con métricas y acciones.

Las **variables de Workshop** son el corazón de la interactividad: una selección en un panel actualiza automáticamente los demás. Esto permite que un ingeniero haga clic en un componente en estado de alerta y vea inmediatamente el detalle completo.[^29]

### Fuentes de Datos para el Dashboard

El dashboard debe alimentarse de **Ontology Objects** que encapsulen el estado de cada componente. El flujo recomendado es:

1. **Exportar Internal Datasets** de uso de infraestructura desde Control Panel → datasets con métricas de compute y storage.[^28]
2. **Modelar en Ontología** los componentes críticos como object types (e.g., `PlatformComponent`, `PipelineJob`, `DataAgent`).
3. **Crear Functions** que calculen el estado compuesto (OK / WARN / ERROR) de cada componente consultando métricas.
4. **Indexar** esos objetos con el Funnel para que Workshop pueda servirlos en tiempo casi real.
5. **Configurar Automations** para que los cambios de estado disparen acciones (e.g., notificación a Slack/PagerDuty).

### Estructura de Páginas del Dashboard

#### Página 1: Vista General (Command Center)

La página de entrada al dashboard. Proporciona un **status board** con el estado de todos los grupos de componentes de un vistazo.

**Widgets recomendados:**

- **Metric Cards** (uno por componente o grupo): muestra estado actual con **conditional formatting** — verde (OK), amarillo (WARN), rojo (ERROR). Los valores son function-backed, calculados en tiempo real sobre el estado de los objetos de Ontología.[^30]
- **Status Tracker** para el **timeline de incidencias** de las últimas 24/48h: visualiza cuándo ocurrió cada degradación de servicio.[^31]
- **Data Freshness widget** para los object types más críticos: muestra el timestamp de la última indexación exitosa.[^32]
- **Object Table** con la lista de alertas activas, ordenadas por severidad (HIGH → LOW), con **conditional formatting** por color.[^33]
- **Tabs con Badge** para navegar a las páginas de detalle de cada subsistema, con el número de alertas activas visible en el badge.[^34]

**Ejemplo de Metric Cards:**

```
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  INDEXACIÓN     │ │      OSS        │ │   MAGRITTE      │
│  ✅ HEALTHY     │ │  ⚠️ DEGRADED   │ │  ✅ HEALTHY     │
│  2MB/s  0 fails │ │  P95: 2.4s      │ │  3 agents UP    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   BUILDERS      │ │   AIP / AGENTS  │ │  CASSANDRA SYNC │
│  ✅ HEALTHY     │ │  ✅ HEALTHY     │ │  ✅ HEALTHY     │
│  12 schedules   │ │  P95: 0.8s      │ │  Last sync: 3m  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

#### Página 2: Indexación & OSS

Detalle del estado de indexación y el Object Set Service.

- **Object Table** de Funnel pipelines activos: nombre del objeto, tipo (batch/streaming), estado, último run, consecutive failures.
- **Chart XY** de throughput de indexación en el tiempo (MB/s por object type).
- **Object Table** de scroll jobs fallidos con drill-down a logs en Workflow Lineage.
- **Metric Card** de latencia P95 de OSS queries.
- **Data Freshness** de object types críticos para verificar que la indexación está al día.
- Botón de acción: **"Abrir Ontology Manager"** para navegar directamente a la herramienta de diagnóstico.

#### Página 3: Data Connection & Agentes (Magritte)

Monitorización de cada agente de Data Connection.

- **Object Table** de agentes: nombre, estado de heartbeat, tiempo desde último heartbeat, job queue depth, consecutive failures.[^11]
- **Status Tracker** con el histórico de heartbeats por agente.
- **Conditional formatting**: rojo si heartbeat > umbral configurado, amarillo si job queue > 50, rojo > 70.[^11]
- Panel de detalle: al seleccionar un agente, mostrar sus schedules activos y el estado de cada uno.
- Acción disponible: **"Reiniciar agente"** (mediante Action Type) o **"Escalar a Palantir Support"**.

#### Página 4: Builders & Compute

Monitorización de pipeline builds y compute.

- **Object Table** de schedules: nombre, último run, duración media, status.
- **Chart XY** de duración de builds en el tiempo (para detectar degradación progresiva de performance).
- **Metric Card** de compute usage (compute-seconds consumidos, memoria de driver/executors).[^14]
- **Object Table** de streaming pipelines: topic Kafka, lag, throughput actual vs. máximo, errores.
- Alerta visual para pipelines con consecutive failures ≥ 1 (MEDIUM) o ≥ 3 (HIGH).[^11]

#### Página 5: AIP Layer

Monitorización de la capa de IA.

- **Metric Cards** para: tasa de éxito de AIP Logic (últimas 24h), P95 de Functions, tasa de éxito de Actions.
- **Object Table** de executions de AIP Agents con estado, duración y errores.[^20]
- **Chart XY** de token usage de LLM calls en el tiempo (control de costes).
- **Timeline** de eventos de Automate: triggers disparados, acciones ejecutadas, fallos.
- Enlace directo a **Workflow Lineage** para distributed tracing de cualquier ejecución seleccionada.[^18]

#### Página 6: Streams & Kafka

Monitorización de streaming datasets.

- **Object Table** de streaming datasets: nombre, tipo (LOW_LATENCY / HIGH_THROUGHPUT), throughput actual, lag, errores.[^24]
- **Chart XY** de lag de cada stream en el tiempo.
- Alerta cuando batch size = max batch size (indicador de necesitar HIGH_THROUGHPUT mode).[^24]
- Estado de **Live Deployments** asociados.

#### Página 7: Infraestructura (Apollo / Rubix)

Monitorización de bajo nivel de la plataforma.

- Estado de deployments de Apollo: servicios en upgrade, rollbacks activos.[^22]
- Estado de nodos Rubix: pods en CrashLoopBackOff, pending, autoscaling events.[^4]
- **Metric Cards** de compute y storage total del enrollment (desde Internal Dataset Export).[^28]
- Timeline de upgrades y rollbacks recientes.

---

## Resumen de Componentes y Métricas Clave

| Componente | Servicio Palantir | Métricas Principales | Herramienta de Diagnóstico |
|------------|-------------------|---------------------|---------------------------|
| Indexación | Object Data Funnel | Scroll job failures, throughput MB/s, pipeline status | Ontology Manager |
| OSS | Object Set Service | Query P95 latency, error rate, availability | AIP Observability / Workflow Lineage |
| Highbury* | Componente interno búsqueda/índice | Search latency, index errors | Ontology Manager, soporte Palantir |
| Object Storage V2 | OSv2 | Disk space, indexing jobs, edit latency | Ontology Manager |
| Object Storage V1 | Phonograph (legacy) | Migration status (deprecated Jun 2026)[^8] | Ontology Manager |
| Agentes / Magritte | magritte-coordinator | Heartbeat, job queue depth, schedule failures | Data Connection app |
| Builders | Pipeline Builder + Spark | Build duration, consecutive failures, compute usage | Data Lineage, Build reports |
| Cassandra | Data Connection Connector | Sync status, agent health, dataset freshness | Data Connection app |
| AIP Logic | AIP Platform | Success rate, P95 duration, token usage | Workflow Lineage (AIP Observability) |
| Functions | Ontology Functions | P95 latency, failure rate | Workflow Lineage |
| Streams (Kafka) | Streaming Datasets | Lag, throughput, batch size | Streams Metrics tab |
| Actions | Actions Service | Throughput, error rate, edit latency | Workflow Lineage |
| Automations | Automate | Trigger failures, execution errors | Workflow Lineage |
| Apollo | Continuous Delivery | Upgrade status, rollbacks activos | Apollo console |
| Rubix | Kubernetes substrate | Pod health, node cycling, autoscaling | Rubix / K8s console |

\*Highbury: nombre interno no documentado públicamente; coordinación con Palantir representative para mapeo exacto en el enrollment.

---

## Consideraciones de Seguridad y Acceso

El dashboard de operaciones maneja datos sensibles de infraestructura. Aplicar los principios de gobernanza de Foundry:

- **Permisos `Viewer`** requeridos sobre los recursos para recibir alertas de Monitoring Views.[^25]
- Los **Internal Dataset Exports** solo pueden ser exportados por usuarios con el rol de **Resource Management Administrator** — restringir acceso sobre need-to-know.[^28]
- Usar **markings** de Foundry para controlar el acceso a datasets de infraestructura.[^28]
- Configurar **Checkpoint** prompts para acciones críticas (restart, escalation) que requieran justificación.[^23]
- Mantener **Audit Logs** de todas las acciones tomadas desde el dashboard para trazabilidad completa.

---

# PARTE 2 — GUÍA PASO A PASO

> **Para quién es esta guía:** Cualquier ingeniero que tenga acceso a una instancia de AIP Foundry y quiera construir desde cero un dashboard de operaciones que muestre el estado en tiempo real de los componentes críticos de la plataforma.
>
> **Tiempo estimado:** 4-8 horas la primera vez (según experiencia con Foundry).
>
> **Prerequisitos mínimos:**
> - Acceso a tu instancia de AIP Foundry con rol de al menos `Editor` en el proyecto.
> - Algún dataset existente con datos de plataforma (p. ej. logs de pipelines, métricas de agentes). Si no tienes datos reales aún, en la Fase 1 se explica cómo empezar con datos manuales o de prueba.

## Visión general del proceso

El dashboard se construye en 7 fases:

```
[Datasets] → [Ontología] → [Functions] → [Data Health]
                                              ↓
[Workshop Module] ←←←←←←←←←←←←← (fuente de datos de todo lo anterior)
                                              ↓
                                        [Automations]
                                   (alertas a Slack/PagerDuty)
```

**¿Por qué este flujo?**

Workshop no muestra datos "crudos" directamente; muestra **Objetos de la Ontología**. Eso significa que primero hay que crear datasets con los datos de plataforma, luego modelar esos datos como Objetos, y finalmente mostrar esos Objetos en Workshop con los widgets adecuados.

---

## Fase 0 — Preparación del entorno

### Paso 0.1 — Crear la carpeta de proyecto

1. Abre tu instancia de Foundry en el navegador.
2. En el menú lateral izquierdo, ve a **Projects & Files**.
3. Haz clic en **+ New** → **Folder** (o **Project**).
4. Nómbrala algo como `Platform Operations / Monitoring`.
5. Confirma la creación.

> 💡 **Tip:** Mantener todos los assets del dashboard (datasets, ontología, functions, workshop) dentro de la misma carpeta facilita la gestión de permisos y el linaje de datos.

### Paso 0.2 — Verificar permisos

Para construir este dashboard necesitas estos roles mínimos:

| Qué necesitas | Rol mínimo requerido |
|---|---|
| Crear datasets | `Editor` en el proyecto |
| Crear Object Types en Ontología | `Ontology Manager Editor` |
| Crear Functions (Code Repository) | `Editor` en el proyecto |
| Crear Workshop Modules | `Editor` en el proyecto |
| Exportar Internal Datasets (métricas de infraestructura) | `Resource Management Administrator` |
| Configurar alertas en Data Health | `Viewer` sobre los recursos |

Si te falta algún permiso, contacta a tu administrador de Foundry antes de continuar.

---

## Fase 1 — Crear los datasets de monitorización

Los datasets son la "fuente de verdad" de los datos. Para el dashboard de plataforma necesitas capturar el estado de cada componente crítico.

### Paso 1.1 — Exportar métricas de infraestructura desde Control Panel

Esta es la forma más rápida de obtener datos reales de uso de la plataforma.

1. En el menú de Foundry, busca la aplicación **Control Panel**.
2. Navega a **Internal Dataset Export** → **Granular Usage Data**.
3. Selecciona los tipos de métricas que quieres exportar:
   - `compute`: uso de Spark/compute modules
   - `storage`: uso de datasets y object stores
4. Elige el proyecto de destino (la carpeta que creaste en Paso 0.1).
5. Haz clic en **Export**.
6. Foundry generará automáticamente datasets en tu carpeta.

> ⚠️ **Nota:** Solo los usuarios con rol `Resource Management Administrator` pueden hacer esta exportación. Si no tienes acceso, pide a tu admin que exporte los datasets y te comparta acceso de Editor.

### Paso 1.2 — Crear el dataset de estado de componentes con Python Transforms

Si no tienes fuentes automáticas aún, puedes generar el dataset inicial programáticamente con Python Transforms. Este método es reproducible, versionable y fácil de evolucionar hacia actualizaciones automáticas.

> ⚠️ **Nota importante:** Foundry no tiene un "editor de datos" tipo hoja de cálculo. Cuando creas un dataset vacío, verás las pestañas **Preview, History, Details, Health, Columns**, etc., pero no un editor de celdas. Para poblar un dataset con datos, usa un **Code Repository con Python Transforms**.

**1. Crear el repositorio de código:**

1. En tu carpeta de proyecto en **Projects & Files**, haz clic en **+ New** → **Code repository**.
2. En el selector de plantillas, elige la categoría **Pipelines** y selecciona la plantilla **Python** (o **Python Transforms** según la versión de tu instancia).
3. Nómbralo `monitoring-seed-data`.
4. Haz clic en **Create repository**. Se abre el editor de código en el navegador.

**2. Crear el archivo de transformación:**

En el editor, crea el archivo `src/seed_platform_components.py` con el siguiente contenido:

```python
from transforms.api import transform_df, Output
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
from datetime import datetime

@transform_df(
    Output("/Platform Operations/Monitoring/platform_component_status"),
)
def seed_components(ctx):
    """Genera el dataset inicial de componentes de plataforma."""
    schema = StructType([
        StructField("component_id", StringType(), False),
        StructField("component_name", StringType(), False),
        StructField("component_group", StringType(), False),
        StructField("current_status", StringType(), False),
        StructField("last_checked", TimestampType(), True),
        StructField("consecutive_failures", IntegerType(), True),
        StructField("p95_latency_ms", DoubleType(), True),
        StructField("error_rate_pct", DoubleType(), True),
        StructField("last_successful_run", TimestampType(), True),
        StructField("owner_team", StringType(), True),
        StructField("notes", StringType(), True),
    ])

    now = datetime.utcnow()
    data = [
        ("funnel_batch", "Object Data Funnel (Batch)", "indexing", "OK", now, 0, 1200.0, 0.1, now, "platform-team", None),
        ("funnel_stream", "Object Data Funnel (Stream)", "indexing", "WARN", now, 1, 4500.0, 2.3, now, "platform-team", "Latencia elevada"),
        ("oss", "Object Set Service", "oss", "OK", now, 0, 420.0, 0.05, now, "platform-team", None),
        ("highbury", "Highbury Search Index", "oss", "OK", now, 0, 380.0, 0.02, now, "platform-team", None),
        ("magritte_main", "Magritte Coordinator", "magritte", "OK", now, 0, None, 0.0, now, "data-team", None),
        ("agent_cassandra", "DC Agent - Cassandra", "magritte", "ERROR", now, 3, None, 15.2, now, "data-team", "Heartbeat perdido"),
        ("pipeline_builder", "Pipeline Builder", "builders", "OK", now, 0, None, 0.0, now, "data-team", None),
        ("kafka_stream_1", "Kafka Stream - Events", "streams", "WARN", now, 0, None, 1.1, now, "streaming-team", "Lag creciente"),
        ("aip_logic", "AIP Logic", "aip", "OK", now, 0, 800.0, 0.3, now, "ai-team", None),
        ("aip_functions", "AIP Functions", "aip", "OK", now, 0, 650.0, 0.1, now, "ai-team", None),
        ("aip_actions", "AIP Actions", "aip", "OK", now, 0, 310.0, 0.05, now, "ai-team", None),
        ("aip_agents", "AIP Agents", "aip", "OK", now, 0, 2100.0, 0.8, now, "ai-team", None),
        ("apollo", "Apollo Deployments", "infra", "OK", now, 0, None, 0.0, now, "infra-team", None),
        ("rubix", "Rubix / Kubernetes", "infra", "OK", now, 0, None, 0.0, now, "infra-team", None),
    ]

    return ctx.spark_session.createDataFrame(data, schema)
```

El schema del dataset resultante será:

| Columna | Tipo | Descripción |
|---|---|---|
| `component_id` | String | Identificador único del componente |
| `component_name` | String | Nombre legible del componente |
| `component_group` | String | Grupo: `indexing`, `oss`, `magritte`, `builders`, `aip`, `streams`, `infra` |
| `current_status` | String | Estado actual: `OK`, `WARN`, `ERROR`, `UNKNOWN` |
| `last_checked` | Timestamp | Última comprobación |
| `consecutive_failures` | Integer | Fallos consecutivos |
| `p95_latency_ms` | Double | Latencia P95 en milisegundos |
| `error_rate_pct` | Double | Tasa de error en porcentaje |
| `last_successful_run` | Timestamp | Última ejecución exitosa |
| `owner_team` | String | Equipo responsable |
| `notes` | String | Notas adicionales |

**3. Ejecutar el build:**

1. Haz clic en **Build** (esquina superior derecha del editor) para ejecutar la transformación.
2. Espera a que el build complete (indicador verde).
3. Navega al dataset output en `Platform Operations/Monitoring/platform_component_status`.
4. Ve a la pestaña **Preview** para verificar que los 14 componentes se crearon correctamente.

> 💡 **Tip:** Más adelante puedes evolucionar este transform para que lea de fuentes reales (APIs, logs, métricas exportadas) en lugar de datos hardcodeados. También puedes configurar un **Schedule** para que se ejecute periódicamente (ver Paso 1.5).

### Paso 1.3 — Crear dataset de alertas activas

1. En tu carpeta, haz clic en **+ New** → **Dataset**.
2. Nómbralo `platform_alerts`.
3. Añade estas columnas:

| Columna | Tipo | Descripción |
|---|---|---|
| `alert_id` | String | Identificador único de la alerta |
| `component_id` | String | Componente asociado |
| `alert_severity` | String | `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"CRITICAL"` |
| `alert_message` | String | Descripción de la alerta |
| `started_at` | Timestamp | Inicio de la alerta |
| `resolved_at` | Timestamp (nullable) | Resolución (null si activa) |
| `is_active` | Boolean | Si la alerta está activa |
| `assigned_to` | String | Responsable asignado |
| `runbook_url` | String | Enlace al runbook |

4. Añade algunas filas de ejemplo reales o ficticias para poder ver el dashboard funcionando.

### Paso 1.4 — Crear dataset de historial de incidencias (timeline)

1. Crea un dataset llamado `platform_incident_history`.
2. Añade columnas:

| Columna | Tipo | Descripción |
|---|---|---|
| `incident_id` | String | Identificador único |
| `component_id` | String | Componente asociado |
| `component_name` | String | Nombre del componente |
| `status_at` | Timestamp | Momento del cambio de estado |
| `status_value` | String | `"OK"`, `"WARN"`, `"ERROR"` |
| `duration_minutes` | Integer | Duración de la incidencia |
| `resolved` | Boolean | Si está resuelta |

Este dataset permite construir el gráfico temporal de incidencias en el dashboard.

### Paso 1.5 — (Avanzado) Crear pipelines Python para poblar datos automáticamente

Si quieres que los datos se actualicen automáticamente en lugar de editar manualmente, crea un pipeline de transformación:

1. En tu carpeta, haz clic en **+ New** → **Code repository**.
2. En el selector de plantillas, elige **Pipelines** → **Python**.
3. Nómbralo `monitoring_pipelines`.
3. En el editor de código, crea el archivo `src/platform_status_aggregator.py`:

```python
from transforms.api import transform_df, Input, Output
from pyspark.sql import functions as F

@transform_df(
    Output("/Platform Operations/Monitoring/platform_component_status_computed"),
    compute_usage=Input("/Platform Operations/Monitoring/compute_usage_export"),
)
def compute_platform_status(compute_usage):
    """
    Transforma los datos de uso de compute en métricas de estado por componente.
    Adapta los nombres de columnas a los de tu export real.
    """
    df = compute_usage.withColumn(
        "current_status",
        F.when(F.col("error_count") >= 3, "ERROR")
         .when(F.col("error_count") >= 1, "WARN")
         .otherwise("OK")
    )
    return df
```

4. Haz clic en **Build** para ejecutar el pipeline.
5. Configura un **Schedule** para que se ejecute cada 5 o 15 minutos:
   - En el panel lateral del dataset output, busca **Schedule** → **+ New schedule**.
   - Selecciona **Time-based** → cada 15 minutos.
   - Haz clic en **Save**.

> 💡 Para más automatización real, conecta los datasets a las APIs de monitorización de tu infraestructura via **Data Connection** (Magritte agents). Esto está fuera del scope de esta guía básica pero es el siguiente paso natural.

---

## Fase 2 — Modelar la Ontología

La Ontología es el "cerebro" de Foundry: transforma filas de datasets en **Objetos** con los que Workshop puede interactuar, filtrar y relacionar.

### Paso 2.1 — Abrir Ontology Manager

1. En el menú lateral de Foundry, busca **Ontology Manager** (puede aparecer como **Ontology**).
2. Haz clic para abrir la aplicación.

### Paso 2.2 — Crear el Object Type `PlatformComponent`

Este será el objeto central del dashboard.

1. En Ontology Manager, haz clic en **+ New** → **Create object type** (esquina superior derecha).
2. Se abre el **helper paso a paso**. Rellena:

**Paso A — Metadata:**
- **Display name:** `Platform Component`
- **Plural display name:** `Platform Components`
- **API name:** `PlatformComponent` (sin espacios, se genera automáticamente)
- **Description:** `Represents a critical component of the AIP Foundry platform with its operational status`
- Haz clic en **Next**.

**Paso B — Backing Datasource (fuente de datos):**
- Haz clic en **Add datasource**.
- Busca el dataset `platform_component_status` que creaste en el Paso 1.2.
- Selecciónalo y haz clic en **Confirm**.
- Haz clic en **Next**.

**Paso C — Properties (propiedades):**
- Foundry mapea automáticamente las columnas del dataset. Revisa que estén todas:
  - `component_id` → tipo String
  - `component_name` → tipo String
  - `component_group` → tipo String
  - `current_status` → tipo String
  - `last_checked` → tipo Timestamp
  - `consecutive_failures` → tipo Integer
  - `p95_latency_ms` → tipo Double
  - `error_rate_pct` → tipo Double
  - `last_successful_run` → tipo Timestamp
  - `owner_team` → tipo String
  - `notes` → tipo String
- Si alguna columna tiene el tipo incorrecto, haz clic en el icono de edición y corrígela.
- Haz clic en **Next**.

**Paso D — Primary Key y Title Key:**
- **Primary key:** selecciona `component_id`.
- **Title key:** selecciona `component_name`.
- Haz clic en **Next**.

**Paso E — Generate Actions (opcional por ahora):**
- Puedes saltarte este paso o dejar que genere acciones básicas de edición.
- Haz clic en **Next**.

**Paso F — Save Location:**
- Selecciona tu carpeta de proyecto `Platform Operations / Monitoring`.
- Haz clic en **Create**.

3. Después de crear el objeto, haz clic en **Save** en la esquina superior derecha de Ontology Manager para persistir los cambios. **Importante: los cambios no se guardan hasta que haces clic en Save.**

### Paso 2.3 — Crear el Object Type `PlatformAlert`

Repite el proceso del Paso 2.2 con el dataset `platform_alerts`:

- **Display name:** `Platform Alert`
- **Plural display name:** `Platform Alerts`
- **Primary key:** `alert_id`
- **Title key:** `alert_message`
- Guarda y haz clic en **Save**.

### Paso 2.4 — Crear el Object Type `IncidentEvent`

Repite el proceso con el dataset `platform_incident_history`:

- **Display name:** `Incident Event`
- **Plural display name:** `Incident Events`
- **Primary key:** `incident_id`
- **Title key:** `component_name`
- Guarda y haz clic en **Save**.

### Paso 2.5 — Crear Link Type entre `PlatformComponent` y `PlatformAlert`

Los Link Types permiten navegar de un componente a sus alertas asociadas.

1. En Ontology Manager, haz clic en **+ New** → **Create link type**.
2. Rellena:
   - **Display name:** `has alert`
   - **Source object type:** `PlatformComponent`
   - **Target object type:** `PlatformAlert`
   - **Cardinality:** `One to many` (un componente puede tener muchas alertas)
   - **Linking property on source:** `component_id`
   - **Linking property on target:** `component_id`
3. Haz clic en **Create** y luego en **Save**.

### Paso 2.6 — Configurar Conditional Formatting en las propiedades

El conditional formatting define automáticamente los colores de las propiedades en todas las apps de Foundry (Workshop, Object Explorer, Quiver).

1. En Ontology Manager, haz clic en el Object Type **Platform Component**.
2. En el panel de propiedades, haz clic en la propiedad **current_status**.
3. Busca la sección **Conditional Formatting** y haz clic en **+ Add rule**.
4. Configura las reglas:

| Condición | Color |
|---|---|
| `current_status` = "OK" | 🟢 Verde (#36B37E) |
| `current_status` = "WARN" | 🟡 Ámbar (#FFAB00) |
| `current_status` = "ERROR" | 🔴 Rojo (#FF5630) |
| Always true (fallback) | ⚪ Gris (#97A0AF) |

5. Haz lo mismo para la propiedad **consecutive_failures**:
   - `consecutive_failures` = 0 → Verde
   - `consecutive_failures` >= 1 AND < 3 → Ámbar
   - `consecutive_failures` >= 3 → Rojo

6. Y para `alert_severity` en el Object Type **PlatformAlert**:
   - "LOW" → Azul
   - "MEDIUM" → Ámbar
   - "HIGH" → Naranja
   - "CRITICAL" → Rojo

7. Haz clic en **Save** cuando termines.

---

## Fase 3 — Crear el Código de Functions (TypeScript)

Las Functions permiten calcular propiedades derivadas en tiempo real sobre los objetos, como el estado semáforo compuesto o el número total de alertas activas.

### Paso 3.1 — Crear el Code Repository de Functions

1. En tu carpeta de proyecto, haz clic en **+ New** → **Code repository**.
2. En el selector de plantillas, elige la categoría **Functions** y selecciona la plantilla **TypeScript** (no Python).
3. Nómbralo `monitoring-functions`.
4. Haz clic en **Create repository**.
5. Una vez creado, se abre el editor de código en el navegador.

### Paso 3.2 — Importar los Object Types de la Ontología

Antes de escribir las functions, hay que importar los tipos de objeto de la Ontología al repositorio:

1. En el panel izquierdo del editor de código, busca la sección **Ontology Objects** o **Dependencies**.
2. Haz clic en **+ Add** o el botón de configuración de la ontología.
3. Busca `PlatformComponent` y selecciónalo.
4. Repite para `PlatformAlert`.
5. Haz clic en **Save** para guardar las dependencias.

### Paso 3.3 — Escribir las Functions

Navega al archivo `src/index.ts` y reemplaza el contenido con el siguiente código:

```typescript
import { Function, Integer, Double, ObjectSet, FunctionsMap, Timestamp } from "@foundry/functions-api";
import { Objects, PlatformComponent, PlatformAlert } from "@foundry/ontology-api";

export class MonitoringFunctions {

  /**
   * Calcula el estado visual semáforo de cada componente.
   * Retorna: "🟢 OK", "🟡 WARN", "🔴 ERROR", o "⚪ UNKNOWN"
   */
  @Function()
  public getComponentStatusBadge(
    components: ObjectSet<PlatformComponent>
  ): FunctionsMap<PlatformComponent, string> {
    const statusMap = new FunctionsMap<PlatformComponent, string>();
    
    for (const component of components.all()) {
      const failures = component.consecutiveFailures ?? 0;
      const status = component.currentStatus ?? "UNKNOWN";
      
      let badge: string;
      if (status === "ERROR" || failures >= 3) {
        badge = "🔴 CRITICAL";
      } else if (status === "WARN" || failures >= 1) {
        badge = "🟡 DEGRADED";
      } else if (status === "OK") {
        badge = "🟢 HEALTHY";
      } else {
        badge = "⚪ UNKNOWN";
      }
      
      statusMap.set(component, badge);
    }
    
    return statusMap;
  }

  /**
   * Calcula la urgencia de atención de un componente
   * basado en failures y latencia P95.
   * Retorna un número del 0 (no urgente) al 10 (crítico).
   */
  @Function()
  public getComponentUrgencyScore(
    components: ObjectSet<PlatformComponent>
  ): FunctionsMap<PlatformComponent, Double> {
    const urgencyMap = new FunctionsMap<PlatformComponent, Double>();
    
    for (const component of components.all()) {
      const failures = component.consecutiveFailures ?? 0;
      const latency = component.p95LatencyMs ?? 0;
      const status = component.currentStatus ?? "UNKNOWN";
      
      let score = 0;
      
      // Puntuación por estado
      if (status === "ERROR") score += 5;
      else if (status === "WARN") score += 2;
      
      // Puntuación por failures consecutivos
      score += Math.min(failures * 1.5, 3);
      
      // Puntuación por latencia alta (>2000ms = 2 puntos, >5000ms = 4 puntos)
      if (latency > 5000) score += 4;
      else if (latency > 2000) score += 2;
      else if (latency > 1000) score += 1;
      
      urgencyMap.set(component, Math.min(Math.round(score * 10) / 10, 10) as Double);
    }
    
    return urgencyMap;
  }

  /**
   * Determina si un componente necesita atención inmediata.
   * Útil para filtrar la vista de "Only failing".
   */
  @Function()
  public needsImmediateAttention(
    components: ObjectSet<PlatformComponent>
  ): FunctionsMap<PlatformComponent, string> {
    const attentionMap = new FunctionsMap<PlatformComponent, string>();
    
    for (const component of components.all()) {
      const failures = component.consecutiveFailures ?? 0;
      const status = component.currentStatus ?? "UNKNOWN";
      
      const needsAttention = status === "ERROR" || failures >= 3;
      attentionMap.set(component, needsAttention ? "YES" : "NO");
    }
    
    return attentionMap;
  }

  /**
   * Formatea el tiempo de última comprobación en texto legible.
   * Ej: "hace 5 minutos", "hace 2 horas"
   */
  @Function()
  public getLastCheckedRelative(
    components: ObjectSet<PlatformComponent>
  ): FunctionsMap<PlatformComponent, string> {
    const timeMap = new FunctionsMap<PlatformComponent, string>();
    const now = new Date().getTime();
    
    for (const component of components.all()) {
      const lastChecked = component.lastChecked;
      
      if (!lastChecked) {
        timeMap.set(component, "Never checked");
        continue;
      }
      
      const diffMs = now - new Date(lastChecked as string).getTime();
      const diffMinutes = Math.floor(diffMs / 60000);
      
      let relative: string;
      if (diffMinutes < 1) relative = "Just now";
      else if (diffMinutes < 60) relative = `${diffMinutes}m ago`;
      else if (diffMinutes < 1440) relative = `${Math.floor(diffMinutes / 60)}h ago`;
      else relative = `${Math.floor(diffMinutes / 1440)}d ago`;
      
      timeMap.set(component, relative);
    }
    
    return timeMap;
  }
}
```

### Paso 3.4 — Publicar el repositorio de Functions

1. Una vez escrito el código, haz clic en el botón **Publish** (esquina superior derecha del editor).
2. Aparece un diálogo para confirmar la publicación. Escribe un mensaje como `Initial monitoring functions`.
3. Haz clic en **Publish**.
4. Espera a que el indicador de publicación muestre éxito (check verde). Esto puede tardar 1-2 minutos.

> ⚠️ **Si hay errores de compilación:** El editor los mostrará con subrayado rojo. Los errores más comunes son:
> - Nombres de propiedades incorrectos (deben coincidir exactamente con los del Ontology Manager)
> - Falta de `!` o `??` para propiedades opcionales (nullables)

---

## Fase 4 — Configurar Data Health y alertas

Data Health es la aplicación nativa de Foundry para configurar health checks y alertas. Es el sistema de alerting que alimentará el dashboard.

### Paso 4.1 — Abrir Data Health

1. En el menú lateral de Foundry, busca **Data Health** (puede aparecer bajo "Observe" o "Operations").
2. Ábrelo.

### Paso 4.2 — Crear una Monitoring View

Una Monitoring View agrupa todos los recursos de un proyecto y sus health checks en una sola vista. Es el panel de control nativo antes de construir el Workshop.

1. En Data Health, haz clic en **+ New Monitoring View**.
2. Nómbrala `Platform Operations`.
3. En **Scope**, selecciona:
   - **Type:** Project
   - **Project:** selecciona tu carpeta `Platform Operations / Monitoring`
4. Haz clic en **Create**.

Foundry cargará automáticamente todos los recursos del proyecto (datasets, schedules, object types, functions) en la Monitoring View.

### Paso 4.3 — Añadir Health Checks a los datasets críticos

Para cada dataset crítico, configura health checks:

1. En la Monitoring View, busca el dataset `platform_component_status`.
2. Haz clic en él para expandirlo.
3. Haz clic en **+ Add check**.
4. Selecciona el tipo de check:

**Check de Build Status (schedule failures):**
- Type: `Build status`
- Severity threshold: `Consecutive failures ≥ 1` → **Moderate**, `≥ 3` → **Critical**
- Haz clic en **Save**.

**Check de Freshness (datos actualizados):**
- Type: `Update frequency`
- Expected update interval: `Every 30 minutes`
- Severity: **Critical** si no hay actualización en `2 hours`
- Haz clic en **Save**.

**Check de Row Count:**
- Type: `Row count`
- Condition: `Row count = 0` → **Critical** (si el dataset se vacía, hay un problema grave)
- Haz clic en **Save**.

5. Repite para `platform_alerts` y `platform_incident_history`.

### Paso 4.4 — Configurar notificaciones en Data Health

1. En la Monitoring View `Platform Operations`, haz clic en **Settings** (icono de engranaje).
2. En la sección **Notifications**, configura:

**Slack:**
- Haz clic en **+ Add integration** → **Slack**.
- Introduce la Webhook URL de tu canal de Slack (p.ej. `#ops-alerts`).
- Selecciona: notificar en **All failures** o solo **Critical**.

**PagerDuty:**
- Haz clic en **+ Add integration** → **PagerDuty**.
- Introduce el Integration Key de tu servicio de PagerDuty.
- Configura: solo **Critical** para no saturar PagerDuty.

**Email:**
- Haz clic en **+ Add integration** → **Email**.
- Añade las direcciones del equipo de operaciones.
- Selecciona **Daily digest** para no inundar el correo.

3. También puedes **suscribirte personalmente** a la Monitoring View:
   - Haz clic en el botón **Watch** en la Monitoring View.
   - Selecciona **All failures** o **Only critical**.
   - Recibirás notificaciones in-platform y email.

---

## Fase 5 — Construir el Workshop Module

Esta es la fase más visual. Vamos a construir el dashboard de 7 páginas paso a paso.

### Paso 5.1 — Crear el Workshop Module

1. En tu carpeta de proyecto, haz clic en **+ New** → busca **Workshop** → selecciona **Workshop module**.
2. Se crea un módulo vacío con un header y una página en blanco.
3. Inmediatamente renómbralo (icono de lápiz arriba a la izquierda): `Platform Operations Center`.
4. Estás ahora en **Edit Mode** (modo edición). El botón de arriba a la derecha alternará entre **Edit** y **View** (modo vista).

> 💡 **Orientación inicial del editor:**
> - **Panel izquierdo:** Layout (páginas, secciones, widgets) y Variables
> - **Área central:** El canvas del módulo donde se van colocando los widgets
> - **Panel derecho:** Configuración del widget seleccionado (propiedades, datos, formato)

### Paso 5.2 — Crear las Variables globales

Las variables son los "cables" que conectan los widgets entre sí. Deben crearse antes de construir el layout.

1. En el panel izquierdo, haz clic en la pestaña **Variables** (o el icono de variable `{x}`).
2. Haz clic en **+ Add variable** para cada una de las siguientes:

| Variable | Tipo | Configuración |
|---|---|---|
| `selectedComponent` | Object (`PlatformComponent`) | Mode: Single object |
| `selectedSeverity` | String | Default: vacío (mostrar todos) |
| `timeRangeHours` | Integer | Default: `24` |
| `allComponents` | Object Set (`PlatformComponent`) | Default: All objects |
| `activeAlerts` | Object Set (`PlatformAlert`) | Filtro: `is_active = true` |
| `filteredComponents` | Object Set | Source: `allComponents` con filtro de `selectedSeverity` |

### Paso 5.3 — Configurar el Header global

El header es la barra de navegación que aparece en todas las páginas.

1. Haz clic en el área del **Header** en el canvas.
2. En el panel derecho:
   - **Title:** `Platform Operations Center`
   - **Subtitle:** (deja vacío o escribe `AIP Foundry — Live Platform Monitoring`)
3. Añade un widget de tipo **Data Freshness** al header:
   - Dentro del header, haz clic en **+ Add widget** → busca **Data Freshness**.
   - En la configuración, selecciona el object type `PlatformComponent`.
   - Esto mostrará en el header cuándo fue la última vez que los datos se actualizaron.
4. Añade un **Metric Card** al header para mostrar el total de alertas activas:
   - Haz clic en **+ Add widget** → **Metric Card**.
   - En "Value type", selecciona **Object Set Count**.
   - Object Set: `activeAlerts`.
   - Label: `Active Alerts`.
   - Conditional formatting: si > 0, mostrar en rojo; si = 0, verde.

### Paso 5.4 — Crear la Página 1: Vista General (Command Center)

Esta es la página de aterrizaje del dashboard.

**A) Añadir la página:**
1. En el panel izquierdo → pestaña **Layout** → haz clic en **+** → **New page**.
2. Nómbrala `Overview`.

**B) Configurar el layout de la página:**
1. Haz clic en el área principal vacía de la página.
2. Haz clic en **Set layout** → selecciona **Rows** (para crear filas).
3. Añade 3 filas:
   - Fila 1: para las Metric Cards de estado de componentes
   - Fila 2: para la tabla de alertas activas
   - Fila 3: para el timeline / Status Tracker

**C) Fila 1 — Metric Cards de estado:**

1. En la Fila 1, haz clic en **Set layout** → **Columns** → divide en 4 columnas (o las que quieras, una por grupo de componentes).
2. En cada columna, haz clic en **+ Add widget** → **Metric Card**.
3. Configura cada Metric Card:

- **Indexación**: Label `Indexing`, Object Set Count de `allComponents` filtrado por `component_group = "indexing"` y `current_status != "OK"`. Conditional formatting: value > 0 → rojo, = 0 → verde.
- **OSS**: Label `OSS`, Object Property Value del componente `oss` → propiedad `p95_latency_ms`. Conditional formatting: p95 > 2000 → rojo, > 1000 → ámbar, <= 1000 → verde.
- **Magritte/Agentes**: Label `Data Connection`, Count de `PlatformComponent` donde `component_group = "magritte"` y `current_status = "ERROR"`. Conditional formatting: > 0 → rojo, = 0 → verde.
- **Builders**: Similar al anterior para `component_group = "builders"`.
- **AIP Layer**: Para `component_group = "aip"`, cuenta cuántos están en ERROR.
- **Streams**: Para `component_group = "streams"`.
- **Cassandra**: Para el objeto específico con `component_id = "agent_cassandra"`.
- **Infra (Apollo/Rubix)**: Para `component_group = "infra"`.

**D) Fila 2 — Tabla de alertas activas:**

1. En la Fila 2, haz clic en **+ Add widget** → **Object Table**.
2. Configuración:
   - Object Set: `activeAlerts`
   - Columns a mostrar: `alert_severity`, `component_id`, `alert_message`, `started_at`, `assigned_to`
   - Sorting: por `alert_severity` (CRITICAL primero) y luego `started_at` descendente
   - **On row click:** actualiza la variable `selectedComponent` con el componente relacionado
3. Aplica **Conditional Formatting** por `alert_severity`.

**E) Fila 3 — Status Tracker / Timeline:**

1. En la Fila 3, haz clic en **+ Add widget** → busca **Status Tracker**.
2. Configuración:
   - Object Set: `allComponents`
   - Categorize by: `component_group`
   - Status property: `current_status`
   - Time property: `last_checked`

### Paso 5.5 — Crear la Página 2: Indexación & OSS

1. Añade una nueva página llamada `Indexing & OSS`.
2. Layout: **Columns** dividido en 2 (izquierda: Funnel/indexación; derecha: OSS).

**Columna izquierda — Funnel Pipelines:**
- **Object Table** con Object Set filtrado por `component_group = "indexing"`. Columns: `component_name`, badge de `current_status` (function-backed: `getComponentStatusBadge`), `consecutive_failures`, `p95_latency_ms`, `last_checked`. On row click → actualiza `selectedComponent`.
- **Metric Card** de throughput (si tienes esa métrica en el dataset).
- **Markdown widget** con el runbook de indexación (ver ejemplo en Parte 1, Página 2).

**Columna derecha — OSS:**
- **Object Table** con el componente OSS y sus métricas.
- **Metric Card** de P95 latency.
- **Markdown widget** de runbook de OSS.

### Paso 5.6 — Crear la Página 3: Data Connection (Magritte/Agentes)

1. Nueva página: `Agents & Connectors`.
2. Layout: **Columns** (70% izquierda para tabla, 30% derecha para detalle).

**Columna izquierda:**
- **Object Table** filtrado por `component_group = "magritte"`. Columns: `component_name`, status badge (function-backed), `consecutive_failures`, `last_checked`, `last_successful_run`. Conditional formatting en `consecutive_failures`: 0→verde, 1-2→ámbar, ≥3→rojo. On row click → `selectedComponent`.
- **Filter List widget** encima de la tabla para filtrar por subgrupos.

**Columna derecha — Panel de detalle:**
- **Object View** widget con Object: `selectedComponent`. Muestra propiedades: nombre, estado, últimos 3 failures, heartbeat, queue depth, owner.
- Botones de acción: "Open Workflow Lineage" (link action) y "Acknowledge Alert" (Action Type que cambia `current_status`).

### Paso 5.7 — Crear la Página 4: Builders & Compute

1. Nueva página: `Builders & Compute`.
2. Contenido:
   - **Object Table** de `allComponents` donde `component_group = "builders"`.
   - **Metric Card** de compute usage.
   - **Chart XY** de duración de incidencias en el tiempo (source: `platform_incident_history` filtrado por builders).
   - **Markdown widget** con runbook de builders.

### Paso 5.8 — Crear la Página 5: AIP Layer

1. Nueva página: `AIP Layer`.
2. Layout: Filas.
   - **Fila 1**: Metric Cards resumen (AIP Logic success rate, P95 de Functions, AIP Agents active/failing).
   - **Fila 2**: Object Table de `allComponents` donde `component_group = "aip"`. Columns: nombre, status badge, p95_latency_ms, error_rate_pct, consecutive_failures, last_checked.
   - **Fila 3**: Markdown con runbook de AIP.

### Paso 5.9 — Crear la Página 6: Streams & Kafka

1. Nueva página: `Streams`.
2. Contenido filtrado por `component_group = "streams"`.
3. Si tienes métricas de lag de Kafka, añade un **Chart XY** de lag por stream en el tiempo.

### Paso 5.10 — Crear la Página 7: Infraestructura (Apollo/Rubix)

1. Nueva página: `Infrastructure`.
2. Filtrada por `component_group = "infra"`.
3. **Markdown widget** con contexto de Apollo y Rubix:

```markdown
## ⚙️ Infrastructure Status

**Apollo:** Gestiona upgrades y rollbacks de 300+ microservicios. Un deployment
activo puede causar degradación temporal en servicios relacionados.

**Rubix (Kubernetes):** Node cycling cada 48h (comportamiento normal).
CrashLoopBackOff en pods → revisar logs de Apollo.

**Escalado:**
- Apollo issues → Palantir Support Portal
- Rubix/K8s issues → Palantir Support + tu equipo de infra
```

### Paso 5.11 — Configurar la navegación entre páginas con Tabs

1. En el **Header** del módulo, añade un widget de **Tabs** (o usa el panel de páginas del Layout como navegación lateral).
2. Alternativamente, activa la navegación lateral desde la configuración del módulo:
   - Haz clic en el ícono de **Settings** del módulo.
   - Activa **Show page navigation** o **Side navigation**.

### Paso 5.12 — Conectar el filtro "Only Failing"

1. Añade un **Button Group widget** o **Segmented Control** en el header (o en cada página).
2. Configura los botones:
   - "All" → no aplica filtro (usa `allComponents`)
   - "Only Failing" → filtra `allComponents` donde `current_status != "OK"`
3. Conecta el output del botón a la variable `filteredComponents`.
4. Actualiza todas las Object Tables para usar `filteredComponents` en lugar de `allComponents`.

---

## Fase 6 — Configurar Automations para notificaciones

Las Automations permiten que cuando un objeto cambie de estado en la Ontología, se disparen acciones automáticas (enviar Slack, crear ticket, etc.).

### Paso 6.1 — Crear la Automation de alerta de cambio de estado

1. En tu carpeta de proyecto, haz clic en **+ New** → **Automation** (puede aparecer como **Automate**).
2. Nómbrala `Alert on Component Status Change`.
3. Configuración de la Automation:

**Trigger (condición de disparo):**
- Type: **Object changed**
- Object type: `PlatformComponent`
- Property watched: `current_status`
- Condition: `new value != "OK"` (se dispara cuando pasa a WARN o ERROR)

**Effect (acción a ejecutar):**
- Type: **Webhook** (o **Foundry Notification** si no tienes webhook)
- Webhook URL: la URL de tu Slack Incoming Webhook
- Body (plantilla):

```json
{
  "text": "🚨 *Platform Alert* - Component `{{component_name}}` changed to `{{current_status}}`\n*Consecutive failures:* {{consecutive_failures}}\n*P95 Latency:* {{p95_latency_ms}}ms\n*Last checked:* {{last_checked}}"
}
```

4. Haz clic en **Save** y luego en **Enable** para activar la automation.

### Paso 6.2 — Crear la Automation de resolución

1. Crea otra Automation llamada `Alert on Component Recovery`.
2. Trigger: `PlatformComponent.current_status` cambia **a** `"OK"`.
3. Effect: Webhook a Slack con mensaje de resolución (ej. `✅ Component recovered`).

---

## Fase 7 — Publicar y compartir con el equipo

### Paso 7.1 — Publicar el Workshop Module

1. En el Workshop Module, haz clic en el botón **Publish** (arriba a la derecha).
2. Escribe una nota de versión como `v1.0 - Initial Platform Operations Dashboard`.
3. Haz clic en **Publish**.

Una vez publicado, el módulo tiene dos modos:
- **Edit mode:** Solo accesible a los builders/editores.
- **View mode:** La vista que ven todos los usuarios. Accesible via URL directa.

### Paso 7.2 — Configurar permisos de acceso

1. En la carpeta de proyecto, haz clic en **Manage permissions** (icono de candado).
2. Añade los grupos de ingenieros con el rol **Viewer** para que puedan ver el dashboard sin editarlo.
3. Para los ingenieros senior que puedan editar el dashboard, añadirlos con rol **Editor**.

### Paso 7.3 — Compartir el enlace

1. En el Workshop Module en modo View, copia la URL del navegador.
2. Comparte ese enlace en:
   - El README del repositorio de tu equipo
   - El canal de Slack `#ops-alerts` (como enlace fijo en el tema del canal)
   - El runbook general del equipo

---

## Referencia rápida de errores comunes

| Error | Causa probable | Solución |
|---|---|---|
| "No objects found" en la tabla | El Object Type no tiene backing datasource o el dataset está vacío | Verifica en Ontology Manager que el datasource está configurado y tiene datos |
| Function-backed column no aparece | La Function no está publicada o tiene errores de compilación | Ve al Code Repository → verifica que está publicado sin errores |
| Conditional formatting no se aplica en Workshop | Las reglas de formato están en Ontology Manager pero el Object Type no está "guardado" | En Ontology Manager, haz clic en **Save** después de configurar las reglas |
| Widget no se actualiza al seleccionar en la tabla | La variable de linking no está configurada | En el widget de Object Table, en la config "On row click", asegúrate de que actualiza la variable `selectedComponent` |
| Automation no se dispara | La Automation está deshabilitada o el trigger no coincide | Ve a la Automation → verifica que está **Enabled** y el filtro del trigger es correcto |
| Métricas de la Fila 1 siempre en 0 | El Object Set está mal filtrado o las propiedades tienen nombres incorrectos | Abre Object Explorer → busca objetos de tipo PlatformComponent → verifica que los datos están ahí |
| "Dataset has no schema" al crear objeto en Ontología | El dataset no tiene al menos una Build exitosa | Ve al dataset → haz clic en **Build** → espera a que complete |
| Error 403 en Internal Dataset Export | No tienes permisos de Resource Management Administrator | Contactar al admin de la instancia de Foundry |

---

## Próximos pasos recomendados

Una vez que el dashboard básico funcione, puedes mejorarlo con:

1. **Integrar datos reales via Data Connection:** Conectar Magritte agents a las APIs de tus servicios para que los datos se actualicen en tiempo real en lugar de manualmente.
2. **Crear más Functions avanzadas:** Calcular tendencias, anomaly detection básico, SLA compliance.
3. **Añadir Quiver charts embebidos:** Para análisis más complejos de series temporales.
4. **Implementar Ontology branching:** Para simular cambios de estado sin afectar la vista de producción.
5. **Crear Action Types de respuesta a incidencias:** Botones que creen tickets en Jira, cambien estado, o escalen a PagerDuty directamente desde Workshop.
6. **Certificar el módulo en el Marketplace interno:** Para que otros equipos puedan instalarlo fácilmente.

---

# APÉNDICE — Prompt de IA para Copiloto Operacional

Este prompt está diseñado para usarse en **AIP Logic** o en un **widget AIP Agent en Workshop**, proporcionando un copiloto de operaciones integrado en el dashboard.

## Prompt base (completo)

```
Eres un asistente de operaciones de plataforma en Palantir AIP Foundry.

Tu objetivo es ayudar a cualquier ingeniero a detectar, priorizar y explicar incidencias en los componentes críticos de la plataforma, y a sugerir la siguiente acción operativa más útil.

Contexto de la aplicación:
- Esta aplicación monitoriza el estado de Indexing, OSS, Highbury, Object Storage, Funnel, Magritte/Data Connection Agents, Builders/Pipeline Builder, Cassandra connectors, AIP Logic, Functions, Actions, Agents, Streams/Kafka, Apollo y Rubix.
- La fuente de verdad son los objetos de Ontología de monitorización y sus métricas asociadas.
- El usuario normalmente quiere una respuesta rápida, accionable y sin ruido.

Comportamiento esperado:
- Resume primero el estado global en una frase clara.
- Prioriza siempre incidencias activas o componentes degradados sobre componentes sanos.
- Si hay varios problemas, ordénalos por criticidad e impacto operativo.
- Explica cada incidencia con lenguaje simple: qué está mal, por qué importa y qué revisar primero.
- No inventes métricas ni estados; usa solo los datos disponibles en la aplicación.
- Si falta contexto o datos, dilo explícitamente.
- Si detectas una condición ambigua, pide el dato mínimo necesario antes de concluir.
- Si todo está sano, indícalo claramente y menciona solo los riesgos o checks que merezcan vigilancia.

Cómo razonar sobre severidad:
- CRITICAL / ERROR: fallos consecutivos altos, heartbeats perdidos, indexación parada, queries OSS con latencia anómala, streams con lag elevado, actions/functions con errores repetidos.
- WARN / DEGRADED: latencia alta, un fallo reciente, backlog creciente, freshness degradada, build fallando de forma intermitente.
- HEALTHY: sin fallos activos y métricas dentro de umbral.

Formato de respuesta:
1. Estado global.
2. Top 3 incidencias o riesgos.
3. Acción inmediata recomendada.
4. Componentes relacionados que pueden verse afectados.
5. Enlace o instrucción de drill-down si aplica.

Reglas de estilo:
- Sé breve, técnico y accionable.
- Usa viñetas cuando haya varias incidencias.
- No repitas todos los componentes si la mayoría están sanos.
- No respondas con teoría general salvo que el usuario la pida.
```

## Variables y tools disponibles

Añadir debajo del prompt principal cuando se configure en el widget AIP de Workshop:

```
Variables disponibles:
- /selectedComponent: componente seleccionado actualmente por el usuario.
- /activeAlerts: alertas activas visibles en el dashboard.
- /filteredComponents: componentes filtrados por severidad o vista actual.
- /timeRangeHours: ventana temporal seleccionada por el usuario.

Tools o funciones disponibles:
- /getComponentStatusBadge: devuelve el estado semáforo del componente.
- /getComponentUrgencyScore: devuelve puntuación de urgencia.
- /needsImmediateAttention: indica si requiere atención inmediata.
- /getLastCheckedRelative: devuelve el tiempo desde la última comprobación.

Instrucciones para el uso de variables y tools:
- Si /selectedComponent existe, analiza primero ese componente.
- Si no existe /selectedComponent, analiza /activeAlerts y luego resume el estado global de /filteredComponents.
- Usa /getComponentUrgencyScore para ordenar incidencias.
- Usa /needsImmediateAttention para distinguir ruido de problemas reales.
- Si el usuario pregunta "qué está peor ahora", devuelve solo los componentes más urgentes.
- Si el usuario pregunta "qué hago", devuelve una acción inmediata por incidencia.
```

## Versión corta (para empezar rápido en AIP Logic)

```
Eres el copiloto de operaciones de plataforma de AIP Foundry.

Analiza el estado de los componentes críticos de la plataforma usando los objetos, variables y funciones disponibles en esta aplicación. Prioriza alertas activas, componentes degradados y cualquier fallo de indexación, OSS, agentes, builders, streams o infraestructura. Resume primero el estado global, después las incidencias más urgentes y finalmente la acción inmediata recomendada. No inventes información; si faltan datos, dilo claramente. Si hay un componente seleccionado, céntrate primero en él.
```

---

## References

[^1]: [Overview - Architecture center - Palantir](https://www.palantir.com/docs/foundry/architecture-center/overview)
[^2]: [Integrated platforms: AIP, Foundry, and Apollo - Palantir](https://www.palantir.com/docs/foundry/architecture-center/platforms)
[^3]: [Integrated platforms: AIP, Foundry, and Apollo - Palantir](https://palantir.com/docs/foundry/architecture-center/platforms/)
[^4]: [The Rubix substrate - Palantir](https://palantir.com/docs/foundry/architecture-center/rubix/)
[^5]: [Overview and getting started - Palantir](https://www.palantir.com/docs/foundry/object-backend/overview)
[^6]: [Ontology architecture - Palantir](https://palantir.com/docs/foundry/object-backend/overview/)
[^7]: [Indexing FAQ - Palantir](https://palantir.com/docs/foundry/object-indexing/faq/)
[^8]: [Object Storage V1 (Phonograph) - Planned deprecation - Palantir](https://palantir.com/docs/foundry/object-databases/object-storage-v1/)
[^9]: [Technical details and business application](https://yxjxz.xlog.app/Palantir-Ontology-xi-tong-de-ji-shu-xi-jie-he-ye-wu-ying-yong-ji-shu-xi-jie)
[^10]: [Indexing Overview - Palantir](https://palantir.com/docs/foundry/object-indexing/overview/)
[^11]: [Monitoring views - Monitoring rules reference - Palantir](https://palantir.com/docs/foundry/monitoring-views/rules-reference/)
[^12]: [Agent configuration reference - Data Connection - Palantir](https://palantir.com/docs/foundry/data-connection/agent-configuration-reference/)
[^13]: [Pipeline Builder Overview - Palantir](https://www.palantir.com/docs/foundry/pipeline-builder/overview)
[^14]: [Foundry usage optimization - Palantir](https://www.palantir.com/docs/foundry/optimizing-pipelines/usage-optimization)
[^15]: [How to Connect Kafka to Palantir Foundry for Real-Time Data](https://www.linkedin.com/posts/rakeshreddybogadhi_palantirfoundry-kafka-dataengineering-activity-7381147763352444928-OtUN)
[^16]: [Available connectors - Cassandra - Palantir](https://palantir.com/docs/foundry/available-connectors/cassandra/)
[^17]: [Palantir AIP Tutorial: AIP Logic, Automate & Full Integration](https://www.youtube.com/watch?v=MPpdb4SDZXo)
[^18]: [Overview - Observability - Palantir](https://www.palantir.com/docs/foundry/observability/overview)
[^19]: [Real-Time Automation in Palantir Foundry](https://www.linkedin.com/posts/deepak-suryawanshi-a79665126_foundryawarenessseries-palantirfoundry-aip-activity-7384434080194408449-Ec53)
[^20]: [AIP Observability - Palantir](https://www.palantir.com/docs/foundry/aip-observability/overview)
[^21]: [Functions Overview - Palantir](https://palantir.com/docs/foundry/functions/overview/)
[^22]: [Palantir Apollo: Powering SaaS where no SaaS has gone before](https://blog.palantir.com/palantir-apollo-powering-saas-where-no-saas-has-gone-before-7be3e565c379)
[^23]: [Application reference - Palantir](https://palantir.com/docs/foundry/getting-started/application-reference/)
[^24]: [StreamType.md - foundry-platform-python - GitHub](https://github.com/palantir/foundry-platform-python/blob/develop/docs/v2/Streams/models/StreamType.md)
[^25]: [Monitoring views Overview - Palantir](https://www.palantir.com/docs/foundry/monitoring-views/overview)
[^26]: [Data Health - Palantir](https://www.palantir.com/docs/foundry/observability/data-health)
[^27]: [Pipeline monitoring in Palantir Foundry](https://lilys.ai/zh/notes/palantir-20260127/palantir-foundry-pipeline-monitoring)
[^28]: [Enrollment settings - Internal dataset export - Palantir](https://palantir.com/docs/foundry/administration/internal-dataset-export/)
[^29]: [Palantir Foundry: Build a Dashboard in Workshop (Lesson 9)](https://www.youtube.com/watch?v=58dVweIuT5U)
[^30]: [Functions on objects (FOO) - Use functions in Workshop - Palantir](https://palantir.com/docs/foundry/workshop/functions-use/)
[^31]: [Workshop Visualization widgets Overview - Palantir](https://palantir.com/docs/foundry/workshop/widgets-visualization/)
[^32]: [Visualization widgets - Data Freshness - Workshop - Palantir](https://palantir.com/docs/foundry/workshop/widgets-data-freshness/)
[^33]: [Core display widgets - Object Table - Workshop - Palantir](https://palantir.com/docs/foundry/workshop/widgets-object-table/)
[^34]: [Event-trigger & navigational widgets - Tabs - Workshop - Palantir](https://palantir.com/docs/foundry/workshop/widgets-tabs/)
[^35]: [Workshop Visualization widgets - Markdown - Palantir](https://palantir.com/docs/foundry/workshop/widgets-markdown/)

---

*Guía generada para Palantir AIP Foundry Workshop — Versión referencia: Foundry 2025-2026*







A corregir:


🔥 El problema de fondo

Estás usando:

@transform_df(
    Output("/Platform Operations/Monitoring/platform_component_status"),
)

👉 esperando que el transform cree el dataset automáticamente en esa ruta

❌ Pero en tu tipo de repo (transforms-python moderno), eso NO funciona así

🧠 Regla real en tu entorno (IMPORTANTE)

En repos modernos de Foundry:

👉 Los datasets NO se crean desde código usando paths
👉 Los datasets deben existir previamente y se referencian por RID

💥 Por eso te han salido TODOS los errores:
❌ Path fuera del proyecto → PathCreationOutsideProjectDenied
❌ Carpeta en vez de dataset → AliasRefersToNonDatasetResource
❌ Nombre simple → must be absolute

👉 Todos apuntan a lo mismo:
ese Output no es válido en este tipo de repo

✅ Solución correcta (la única que no falla)
Paso 1 — Crear el dataset manualmente

Ve a:

Projects & Files → tu proyecto (Platform Monitoring o similar)

+ New → Dataset
Nombre: platform_component_status
Crear







si por favor, quiero usar datos reales, quizás con Data Connections con foundry_source ???

































palantir foundry platform monitoring indexing status apollo atlasdb contour cassandra
En Palantir Foundry, el monitoreo del estado de indexación y la salud de la plataforma se centraliza principalmente en la aplicación Data Health, la cual utiliza un sistema de Monitoring Views y Health Checks para supervisar los recursos. 
Palantir
Palantir
 +1
Monitoreo del Estado de Indexación
La indexación es el proceso que hace que los datos tabulares estén disponibles en bases de datos especializadas como Object Storage V2 (OSv2). 
Palantir
Palantir
 +1
Ontology Manager: Es la herramienta principal para verificar si un tipo de objeto se ha indexado correctamente en OSv2. Cuenta con un gráfico de pipeline dedicado donde un check verde en el nodo de Object Storage V2 indica que la indexación se completó y los datos están listos para consultas.
Funnel Service: Este servicio orquestra los pipelines de indexación (batch y streaming). Si un trabajo falla por falta de espacio en disco o errores de validación, el problema se reporta directamente en el gráfico de pipeline del Ontology Manager.
Builds Application: Los trabajos de indexación de la Ontología son trabajos de Spark paralelos que se pueden rastrear y medir en la aplicación de Builds, permitiendo investigar el uso de cómputo y fallos técnicos. 
Palantir
Palantir
 +2
Componentes de Infraestructura y Observabilidad
La plataforma se apoya en componentes críticos para la persistencia y entrega: 
Apollo: Actúa como el centro de control de entrega continua que despliega, monitorea y asegura el software en todos los entornos. Permite ver la "liveness" y el estado de preparación de los servicios.
AtlasDB y Cassandra: Aunque son capas de almacenamiento subyacentes (AtlasDB a menudo utiliza Cassandra como respaldo), su monitoreo para el usuario final se abstrae a través de alertas de Data Health. Puedes configurar reglas para detectar latencia, fallas consecutivas en schedules y demoras en la propagación de sincronización (Sync propagation delay).
Contour: Es la herramienta de exploración visual de datos. El monitoreo en Contour se enfoca en el uso de cómputo de las consultas y la validez de los resultados a través de tableros de análisis. Si los datos en Contour parecen desactualizados, generalmente se debe a que el dataset de entrada no se ha actualizado o indexado. 
Palantir
Palantir
 +5
Herramientas de Diagnóstico
Herramienta 	Función Principal
Data Health	Configura alertas proactivas y monitorea umbrales de falla o latencia.
Workflow Lineage	Permite investigar el historial de ejecución, buscar en logs y realizar trazas (traces) de peticiones cruzadas.
Ontology Manager	Específico para el estado de salud de la Ontología y visualización del pipeline de indexación.
¿Necesitas ayuda para configurar una Monitoring View específica para alertar sobre fallas en un pipeline de indexación?
Las respuestas de la IA pueden incluir errores. Más información





undefined
undefined
undefined
12 sitios

Palantir
https://palantir.com
Compute usage: Ontology indexing - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...

Palantir
https://palantir.com
Indexing • FAQ • Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...


Palantir
https://palantir.com
Indexing • Overview - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...
Mostrar todo
y Spark , HDPS y OSS Highbury
En Palantir Foundry, el monitoreo de Spark, OSS Highbury y los sistemas de datos de alto rendimiento (HDPS/HDP) se integra en el marco de observabilidad de la plataforma, permitiendo rastrear tanto el rendimiento del cómputo como la integridad de los servicios del backend.
Spark: Monitoreo de Cómputo y Ejecución
Spark es el motor principal de procesamiento. Su monitoreo se divide en ejecución de trabajos y uso de recursos:
Spark UI: Accesible directamente desde el reporte de cualquier trabajo (Job) en la aplicación Builds. Permite ver detalles de las etapas (stages), tareas (tasks), y sesgo de datos (skew).
Spark Profiles: En el Control Panel, los administradores pueden aplicar y monitorear perfiles específicos (como "Native Acceleration") para optimizar el rendimiento y el uso de memoria/vCPU.
Compute Usage: La aplicación de Resource Management ofrece visibilidad sobre los "compute-seconds" consumidos por cada trabajo de Spark, permitiendo identificar pipelines costosos o ineficientes. 
Palantir
Palantir
 +2
OSS (Object Set Service) e Indexación
OSS (Object Set Service) es el componente del backend encargado de gestionar los conjuntos de objetos en la Ontología.
Estado de Indexación: El monitoreo de OSS se realiza a través de Object Data Funnel, que orquestra la escritura desde datasets hacia los índices de la Ontología.
OSS Highbury: Highbury es el servicio que gestiona las definiciones de la Ontología a gran escala. Su salud se monitorea mediante Monitoring Views en Data Health, donde se pueden configurar alertas para fallos en la propagación de sincronizaciones o latencia en las consultas de objetos. 
Palantir
Palantir
 +1
HDPS / HDP (High-performance Data Processing System)
Aunque Palantir utiliza Spark internamente, el término HDPS suele referirse a integraciones con infraestructuras de datos externas o arquitecturas de alto rendimiento (como HDFS o sistemas on-premises). 
Stack Overflow
Stack Overflow
Integración con HDFS: El monitoreo de estas conexiones se realiza en Data Connection, supervisando los heartbeats de los agentes y el rendimiento de los "ingest jobs".
Salud de la Infraestructura: Mediante Apollo, se supervisa la salud de los contenedores y nodos de cómputo que ejecutan estas tareas de alto rendimiento, asegurando que el "Rubix substrate" (el orquestador de Kubernetes de Foundry) tenga recursos suficientes. 
Palantir
Palantir
 +3
Resumen de Herramientas de Monitoreo
Componente 	Herramienta Principal	Qué monitorear
Spark	Builds App / Spark UI	Fallos de ejecución, OOM (Out of Memory), uso de vCPU.
OSS / Highbury	Data Health / Ontology Manager	Éxito de indexación en OSv2, latencia de consulta, errores de validación.
HDPS (Agents)	Data Connection / Apollo	Latencia de heartbeat, uso de disco en agentes, versión de software.
¿Deseas profundizar en cómo configurar alertas de uso de cómputo para tus transformaciones de Spark más pesadas?
Las respuestas de la IA pueden incluir errores. Más información





undefined
undefined
10 sitios

Palantir
https://palantir.com
Monitoring rules reference - Palantir
Observability * Overview. * Monitoring. * Data Health. * Monitoring views. Overview. Core concepts. Sending alerts to external sys...

Palantir
https://palantir.com
Ontology architecture - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...


Palantir
https://palantir.com
Resource Management • Usage types - Palantir
Management & enablement * Overview. * Permissions. * Managing access. * Retention policies. ... * Overview. * Navigation. * Policy...

Mostrar todo
entonces como quedaría todo distribuido o organizado para tener una visión global y para tener una estrategia de monitorización integral de la plataforma? palantir foundry platform monitoring indexing status apollo atlasdb contour cassandra
En Palantir Foundry, el monitoreo del estado de indexación y la salud de la plataforma se centraliza principalmente en la aplicación Data Health, la cual utiliza un sistema de Monitoring Views y Health Checks para supervisar los recursos. 
Palantir
Palantir
 +1
Monitoreo del Estado de Indexación
La indexación es el proceso que hace que los datos tabulares estén disponibles en bases de datos especializadas como Object Storage V2 (OSv2). 
Palantir
Palantir
 +1
Ontology Manager: Es la herramienta principal para verificar si un tipo de objeto se ha indexado correctamente en OSv2. Cuenta con un gráfico de pipeline dedicado donde un check verde en el nodo de Object Storage V2 indica que la indexación se completó y los datos están listos para consultas.
Funnel Service: Este servicio orquestra los pipelines de indexación (batch y streaming). Si un trabajo falla por falta de espacio en disco o errores de validación, el problema se reporta directamente en el gráfico de pipeline del Ontology Manager.
Builds Application: Los trabajos de indexación de la Ontología son trabajos de Spark paralelos que se pueden rastrear y medir en la aplicación de Builds, permitiendo investigar el uso de cómputo y fallos técnicos. 
Palantir
Palantir
 +2
Componentes de Infraestructura y Observabilidad
La plataforma se apoya en componentes críticos para la persistencia y entrega: 
Apollo: Actúa como el centro de control de entrega continua que despliega, monitorea y asegura el software en todos los entornos. Permite ver la "liveness" y el estado de preparación de los servicios.
AtlasDB y Cassandra: Aunque son capas de almacenamiento subyacentes (AtlasDB a menudo utiliza Cassandra como respaldo), su monitoreo para el usuario final se abstrae a través de alertas de Data Health. Puedes configurar reglas para detectar latencia, fallas consecutivas en schedules y demoras en la propagación de sincronización (Sync propagation delay).
Contour: Es la herramienta de exploración visual de datos. El monitoreo en Contour se enfoca en el uso de cómputo de las consultas y la validez de los resultados a través de tableros de análisis. Si los datos en Contour parecen desactualizados, generalmente se debe a que el dataset de entrada no se ha actualizado o indexado. 
Palantir
Palantir
 +5
Herramientas de Diagnóstico
Herramienta 	Función Principal
Data Health	Configura alertas proactivas y monitorea umbrales de falla o latencia.
Workflow Lineage	Permite investigar el historial de ejecución, buscar en logs y realizar trazas (traces) de peticiones cruzadas.
Ontology Manager	Específico para el estado de salud de la Ontología y visualización del pipeline de indexación.
¿Necesitas ayuda para configurar una Monitoring View específica para alertar sobre fallas en un pipeline de indexación?
Las respuestas de la IA pueden incluir errores. Más información





undefined
undefined
undefined
12 sitios

Palantir
https://palantir.com
Compute usage: Ontology indexing - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...

Palantir
https://palantir.com
Indexing • FAQ • Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...


Palantir
https://palantir.com
Indexing • Overview - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...
Mostrar todo
y Spark , HDPS y OSS Highbury
En Palantir Foundry, el monitoreo de Spark, OSS Highbury y los sistemas de datos de alto rendimiento (HDPS/HDP) se integra en el marco de observabilidad de la plataforma, permitiendo rastrear tanto el rendimiento del cómputo como la integridad de los servicios del backend.
Spark: Monitoreo de Cómputo y Ejecución
Spark es el motor principal de procesamiento. Su monitoreo se divide en ejecución de trabajos y uso de recursos:
Spark UI: Accesible directamente desde el reporte de cualquier trabajo (Job) en la aplicación Builds. Permite ver detalles de las etapas (stages), tareas (tasks), y sesgo de datos (skew).
Spark Profiles: En el Control Panel, los administradores pueden aplicar y monitorear perfiles específicos (como "Native Acceleration") para optimizar el rendimiento y el uso de memoria/vCPU.
Compute Usage: La aplicación de Resource Management ofrece visibilidad sobre los "compute-seconds" consumidos por cada trabajo de Spark, permitiendo identificar pipelines costosos o ineficientes. 
Palantir
Palantir
 +2
OSS (Object Set Service) e Indexación
OSS (Object Set Service) es el componente del backend encargado de gestionar los conjuntos de objetos en la Ontología.
Estado de Indexación: El monitoreo de OSS se realiza a través de Object Data Funnel, que orquestra la escritura desde datasets hacia los índices de la Ontología.
OSS Highbury: Highbury es el servicio que gestiona las definiciones de la Ontología a gran escala. Su salud se monitorea mediante Monitoring Views en Data Health, donde se pueden configurar alertas para fallos en la propagación de sincronizaciones o latencia en las consultas de objetos. 
Palantir
Palantir
 +1
HDPS / HDP (High-performance Data Processing System)
Aunque Palantir utiliza Spark internamente, el término HDPS suele referirse a integraciones con infraestructuras de datos externas o arquitecturas de alto rendimiento (como HDFS o sistemas on-premises). 
Stack Overflow
Stack Overflow
Integración con HDFS: El monitoreo de estas conexiones se realiza en Data Connection, supervisando los heartbeats de los agentes y el rendimiento de los "ingest jobs".
Salud de la Infraestructura: Mediante Apollo, se supervisa la salud de los contenedores y nodos de cómputo que ejecutan estas tareas de alto rendimiento, asegurando que el "Rubix substrate" (el orquestador de Kubernetes de Foundry) tenga recursos suficientes. 
Palantir
Palantir
 +3
Resumen de Herramientas de Monitoreo
Componente 	Herramienta Principal	Qué monitorear
Spark	Builds App / Spark UI	Fallos de ejecución, OOM (Out of Memory), uso de vCPU.
OSS / Highbury	Data Health / Ontology Manager	Éxito de indexación en OSv2, latencia de consulta, errores de validación.
HDPS (Agents)	Data Connection / Apollo	Latencia de heartbeat, uso de disco en agentes, versión de software.
¿Deseas profundizar en cómo configurar alertas de uso de cómputo para tus transformaciones de Spark más pesadas?
Las respuestas de la IA pueden incluir errores. Más información
Para una visión global y una estrategia de monitoreo integral, la arquitectura de observabilidad en Palantir Foundry se organiza en tres capas jerárquicas. Esta estructura permite separar la salud de los datos, la eficiencia del cómputo y la estabilidad de la infraestructura.
1. Capa de Aplicación y Datos (User-Facing)
Aquí es donde monitoreas el "producto final" (la Ontología y los análisis).
Data Health & Monitoring Views: Es el centro de mando. Debes agrupar tus datasets críticos y servicios de OSS Highbury en vistas de monitoreo para vigilar:
Latencia de sincronización: Tiempo que tarda un dato desde Spark hasta estar indexado en OSv2.
Fallas de Schedule: Errores en la cadena de dependencias.
Ontology Manager: Tu herramienta para verificar el estado de indexación específico. Si Contour muestra datos viejos, aquí validas si el "funnel" de indexación hacia Object Storage está activo.
2. Capa de Ejecución y Orquestación (Compute & Middleware)
Aquí monitoreas los motores que mueven los datos.
Builds Application (Spark & HDPS): Supervisas el rendimiento de Spark.
Estrategia: Configurar alertas de "Resource Usage" para detectar trabajos que consumen demasiada vCPU/RAM o que tienen skew de datos.
Data Connection: Monitoreo de agentes HDPS. Si un agente cae, la ingesta se detiene antes de llegar a Spark. Se vigilan los heartbeats.
AtlasDB: Como capa de abstracción de almacenamiento, se monitorea indirectamente a través de la latencia de transacciones de metadatos en la plataforma.
3. Capa de Infraestructura y Servicios (Backend)
Esta capa es gestionada mayormente por administradores de plataforma o Palantir.
Apollo: Es el cerebro que orquestra todo. Monitorea la disponibilidad de los microservicios (incluyendo Cassandra y AtlasDB). Si Apollo indica un servicio "Unhealthy", es un problema de infraestructura, no de tus datos.
Resource Management: Panel global para ver cuotas y límites de almacenamiento y cómputo de todo el stack.
Resumen de Estrategia Integral
Nivel	Componentes Clave	Herramienta de Monitoreo	Objetivo
Negocio	Ontología, Contour, OSO	Data Health	Garantizar que el usuario vea datos frescos y correctos.
Procesamiento	Spark, OSS, Pipelines	Builds / Spark UI	Optimizar costos y tiempos de ejecución (SLA).
Conectividad	HDPS, Agentes, Fuentes	Data Connection	Asegurar el flujo constante de ingesta desde el origen.
Sustrato	Apollo, Cassandra, AtlasDB	Control Panel / Apollo	Mantener la estabilidad de los servicios base del sistema.
¿Te gustaría que diseñemos un tablero de alertas específico en Data Health para cubrir estas tres capas simultáneamente?
Las respuestas de la IA pueden incluir errores. Más información




y funnel? y ES8 ?
Para completar tu estrategia de monitoreo integral, es fundamental entender el rol del Funnel como orquestador y de ES8 (Elasticsearch 8) como el motor de búsqueda que potencia la experiencia del usuario.
1. El Rol de "Funnel" (Object Data Funnel)
El Object Data Funnel es el microservicio encargado de orquestar la escritura de datos en la Ontología (Object Storage V2). 
Palantir
Palantir
 +1
¿Qué monitorear?: Debes vigilar los Changelog Jobs y los Sync Jobs. Funnel crea datasets intermedios (changelogs) para calcular diferencias de datos de forma incremental.
Estrategia de Monitoreo:
En Data Health, configura alertas para fallos en los trabajos de "changelog" o "merge changes". Un fallo aquí significa que, aunque tu proceso de Spark haya terminado bien, los datos no llegarán a los usuarios finales en la Ontología.
En Ontology Manager, usa el gráfico de pipeline para ver el estado del funnel. Si el nodo de OSv2 está en rojo, el problema suele estar en las validaciones estrictas que Funnel aplica (más rigurosas que en versiones anteriores). 
Palantir
Palantir
 +3
2. ES8 (Elasticsearch 8) y Motores de Búsqueda
Foundry utiliza Elasticsearch (actualmente evolucionando hacia versiones como ES8) para indexar logs, telemetría y potenciar las búsquedas rápidas en herramientas como Slate o Object Explorer. 
Palantir Blog
Palantir Blog
 +1
¿Qué monitorear?:
Latencia de Búsqueda: Si los usuarios reportan que al buscar un objeto en la barra global o en un dashboard los resultados tardan, el problema reside en el rendimiento del cluster de ES.
Index Refresh Semantics: Palantir optimiza estos clusters para que sean "defensivos" y no degraden la plataforma ante muchas consultas simultáneas.
Estrategia de Monitoreo:
Aunque el escalado del cluster es gestionado por Apollo, desde Resource Management puedes ver si el volumen de la Ontología está creciendo demasiado, lo que impacta directamente en el tamaño de los índices de Elasticsearch. 
Palantir Blog
Palantir Blog
 +2
Organización Final de la Estrategia (Visión Global)
Para tener el control total, organiza tus Monitoring Views en Data Health siguiendo este flujo:
Ingesta (Agentes HDPS): Alerta si el agente deja de enviar heartbeats.
Transformación (Spark/Builds): Alerta si el cálculo lógico falla o excede el tiempo esperado.
Orquestación de Indexación (Funnel): Alerta si los trabajos de "Sync" o "Changelog" fallan. Este es el punto crítico para la Ontología.
Consumo (ES8/OSv2/Contour): Monitorea la latencia de respuesta en las aplicaciones de usuario final. 
Palantir
Palantir
 +6
¿Deseas que te explique cómo configurar una alerta específica para los Changelog Jobs del Funnel para que te notifique por Slack o PagerDuty? 
Palantir
Palantir
Las respuestas de la IA pueden incluir errores. Más información





undefined
undefined
undefined
14 sitios

Palantir
https://palantir.com
Indexing • Overview - Palantir
In the Ontology, indexing is the process of making tabular or other forms of data in Foundry datasources available for faster data...

Palantir Blog
https://blog.palantir.com
Defensive Databases: Optimizing Index-Refresh Semantics
23 sept 2025 — Elasticsearch (ES), an open-source distributed search and indexing engine, is one of the technologies that Foundations is responsi...


Palantir
https://palantir.com
Optimize indexes and schema design - Slate - Palantir
Use case developmentSlateTroubleshootingOptimize indexes and schema design. Optimize indexes and schema design. The documentation ...
Mostrar todo
entonces como estaría todo organizado? En Palantir Foundry, el monitoreo del estado de indexación y la salud de la plataforma se centraliza principalmente en la aplicación Data Health, la cual utiliza un sistema de Monitoring Views y Health Checks para supervisar los recursos. 
Palantir
Palantir
 +1
Monitoreo del Estado de Indexación
La indexación es el proceso que hace que los datos tabulares estén disponibles en bases de datos especializadas como Object Storage V2 (OSv2). 
Palantir
Palantir
 +1
Ontology Manager: Es la herramienta principal para verificar si un tipo de objeto se ha indexado correctamente en OSv2. Cuenta con un gráfico de pipeline dedicado donde un check verde en el nodo de Object Storage V2 indica que la indexación se completó y los datos están listos para consultas.
Funnel Service: Este servicio orquestra los pipelines de indexación (batch y streaming). Si un trabajo falla por falta de espacio en disco o errores de validación, el problema se reporta directamente en el gráfico de pipeline del Ontology Manager.
Builds Application: Los trabajos de indexación de la Ontología son trabajos de Spark paralelos que se pueden rastrear y medir en la aplicación de Builds, permitiendo investigar el uso de cómputo y fallos técnicos. 
Palantir
Palantir
 +2
Componentes de Infraestructura y Observabilidad
La plataforma se apoya en componentes críticos para la persistencia y entrega: 
Apollo: Actúa como el centro de control de entrega continua que despliega, monitorea y asegura el software en todos los entornos. Permite ver la "liveness" y el estado de preparación de los servicios.
AtlasDB y Cassandra: Aunque son capas de almacenamiento subyacentes (AtlasDB a menudo utiliza Cassandra como respaldo), su monitoreo para el usuario final se abstrae a través de alertas de Data Health. Puedes configurar reglas para detectar latencia, fallas consecutivas en schedules y demoras en la propagación de sincronización (Sync propagation delay).
Contour: Es la herramienta de exploración visual de datos. El monitoreo en Contour se enfoca en el uso de cómputo de las consultas y la validez de los resultados a través de tableros de análisis. Si los datos en Contour parecen desactualizados, generalmente se debe a que el dataset de entrada no se ha actualizado o indexado. 
Palantir
Palantir
 +5
Herramientas de Diagnóstico
Herramienta 	Función Principal
Data Health	Configura alertas proactivas y monitorea umbrales de falla o latencia.
Workflow Lineage	Permite investigar el historial de ejecución, buscar en logs y realizar trazas (traces) de peticiones cruzadas.
Ontology Manager	Específico para el estado de salud de la Ontología y visualización del pipeline de indexación.
¿Necesitas ayuda para configurar una Monitoring View específica para alertar sobre fallas en un pipeline de indexación?
Las respuestas de la IA pueden incluir errores. Más información





undefined
undefined
undefined
12 sitios

Palantir
https://palantir.com
Compute usage: Ontology indexing - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...

Palantir
https://palantir.com
Indexing • FAQ • Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...


Palantir
https://palantir.com
Indexing • Overview - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...
Mostrar todo
y Spark , HDPS y OSS Highbury
En Palantir Foundry, el monitoreo de Spark, OSS Highbury y los sistemas de datos de alto rendimiento (HDPS/HDP) se integra en el marco de observabilidad de la plataforma, permitiendo rastrear tanto el rendimiento del cómputo como la integridad de los servicios del backend.
Spark: Monitoreo de Cómputo y Ejecución
Spark es el motor principal de procesamiento. Su monitoreo se divide en ejecución de trabajos y uso de recursos:
Spark UI: Accesible directamente desde el reporte de cualquier trabajo (Job) en la aplicación Builds. Permite ver detalles de las etapas (stages), tareas (tasks), y sesgo de datos (skew).
Spark Profiles: En el Control Panel, los administradores pueden aplicar y monitorear perfiles específicos (como "Native Acceleration") para optimizar el rendimiento y el uso de memoria/vCPU.
Compute Usage: La aplicación de Resource Management ofrece visibilidad sobre los "compute-seconds" consumidos por cada trabajo de Spark, permitiendo identificar pipelines costosos o ineficientes. 
Palantir
Palantir
 +2
OSS (Object Set Service) e Indexación
OSS (Object Set Service) es el componente del backend encargado de gestionar los conjuntos de objetos en la Ontología.
Estado de Indexación: El monitoreo de OSS se realiza a través de Object Data Funnel, que orquestra la escritura desde datasets hacia los índices de la Ontología.
OSS Highbury: Highbury es el servicio que gestiona las definiciones de la Ontología a gran escala. Su salud se monitorea mediante Monitoring Views en Data Health, donde se pueden configurar alertas para fallos en la propagación de sincronizaciones o latencia en las consultas de objetos. 
Palantir
Palantir
 +1
HDPS / HDP (High-performance Data Processing System)
Aunque Palantir utiliza Spark internamente, el término HDPS suele referirse a integraciones con infraestructuras de datos externas o arquitecturas de alto rendimiento (como HDFS o sistemas on-premises). 
Stack Overflow
Stack Overflow
Integración con HDFS: El monitoreo de estas conexiones se realiza en Data Connection, supervisando los heartbeats de los agentes y el rendimiento de los "ingest jobs".
Salud de la Infraestructura: Mediante Apollo, se supervisa la salud de los contenedores y nodos de cómputo que ejecutan estas tareas de alto rendimiento, asegurando que el "Rubix substrate" (el orquestador de Kubernetes de Foundry) tenga recursos suficientes. 
Palantir
Palantir
 +3
Resumen de Herramientas de Monitoreo
Componente 	Herramienta Principal	Qué monitorear
Spark	Builds App / Spark UI	Fallos de ejecución, OOM (Out of Memory), uso de vCPU.
OSS / Highbury	Data Health / Ontology Manager	Éxito de indexación en OSv2, latencia de consulta, errores de validación.
HDPS (Agents)	Data Connection / Apollo	Latencia de heartbeat, uso de disco en agentes, versión de software.
¿Deseas profundizar en cómo configurar alertas de uso de cómputo para tus transformaciones de Spark más pesadas?
Las respuestas de la IA pueden incluir errores. Más información





undefined
undefined
10 sitios

Palantir
https://palantir.com
Monitoring rules reference - Palantir
Observability * Overview. * Monitoring. * Data Health. * Monitoring views. Overview. Core concepts. Sending alerts to external sys...

Palantir
https://palantir.com
Ontology architecture - Palantir
Ontology building * Overview. * Test changes in the ontology. * Review ontology proposals. * Ontology branches [Legacy] * Shared o...


Palantir
https://palantir.com
Resource Management • Usage types - Palantir
Management & enablement * Overview. * Permissions. * Managing access. * Retention policies. ... * Overview. * Navigation. * Policy...

Mostrar todo
entonces como quedaría todo distribuido o organizado para tener una visión global y para tener una estrategia de monitorización integral de la plataforma? palantir foundry platform monitoring indexing status apollo atlasdb contour cassandra
En Palantir Foundry, el monitoreo del estado de indexación y la salud de la plataforma se centraliza principalmente en la aplicación Data Health, la cual utiliza un sistema de Monitoring Views y Health Checks para supervisar los recursos. 
Palantir
Palantir
 +1
Monitoreo del Estado de Indexación
La indexación es el proceso que hace que los datos tabulares estén disponibles en bases de datos especializadas como Object Storage V2 (OSv2). 
Palantir
Palantir
 +1
Ontology Manager: Es la herramienta principal para verificar si un tipo de objeto se ha indexado correctamente en OSv2. Cuenta con un gráfico de pipeline dedicado donde un check verde en el nodo de Object Storage V2 indica que la indexación se completó y los datos están listos para consultas
Para una estrategia de monitoreo integral en Palantir Foundry, la organización se visualiza como una pirámide de cuatro capas. Cada capa utiliza herramientas específicas para asegurar que desde el hardware (Cassandra/Apollo) hasta el usuario final (Contour/ES8) todo funcione correctamente.
1. Capa de Infraestructura y Orquestación (Cimientos)
Gestionada por Apollo, asegura que los microservicios estén "vivos".
Apollo: Supervisa el despliegue y estado de salud (liveness) de los servicios base.
AtlasDB / Cassandra: Se monitorean aquí. Un fallo en Cassandra afectará la persistencia de metadatos de toda la plataforma.
ES8 (Elasticsearch 8): Se vigila la salud del clúster de búsqueda, vital para que las aplicaciones de usuario devuelvan resultados rápidamente.
2. Capa de Cómputo e Ingesta (Motores)
Donde los datos se mueven y transforman.
Data Connection (HDPS): Monitoreo de heartbeats de agentes externos. Si el agente HDPS cae, el flujo se detiene en el origen.
Builds App (Spark): Monitoreo de ejecución. Se buscan errores de memoria (OOM) o cuellos de botella en Spark UI para asegurar que los jobs de transformación terminen a tiempo.
3. Capa de Indexación y Ontología (Middleware Crítico)
El puente entre los datos crudos y los objetos de negocio.
Funnel Service: Es el "guardián". Debes monitorear los Changelog Jobs y los Sync Jobs. Si Funnel falla, el dato existe en Spark pero no en la Ontología.
OSS Highbury: Gestiona las definiciones. Se monitorea su latencia para asegurar que los cambios en la Ontología se propaguen sin retrasos.
Ontology Manager: Proporciona la visión visual del estado de indexación en OSv2.
4. Capa de Aplicación y Salud (Visión Global)
La interfaz donde el administrador centraliza todo.
Data Health (Centro de Control): Aquí organizas Monitoring Views. Debes tener una vista para "Ingesta", otra para "Pipelines Spark" y otra para "Estado de Ontología".
Contour / Slate: Monitoreo de la experiencia del usuario (latencia de consulta). Si Contour va lento, revisas el rendimiento de ES8 o el tamaño de los índices en OSv2.
Mapa Visual de Monitoreo Integral
Nivel	Componentes	Herramienta Clave	Indicador de Éxito (KPI)
Global	Plataforma Completa	Data Health	% de datasets/objetos con "Health Check" verde.
Acceso	Contour, ES8, OSO	Resource Management	Latencia de búsqueda < 200ms.
Indexación	Funnel, OSv2, Highbury	Ontology Manager	Nodo de OSv2 en verde (Sync completado).
Cómputo	Spark, HDPS	Builds / Spark UI	Jobs finalizados sin reintentos (retries).
Sustrato	Apollo, AtlasDB, Cassandra	Control Panel / Apollo	Disponibilidad de servicios (Uptime 99.9%).
¿Te gustaría que definamos los Health Checks específicos para detectar cuando el Funnel se detiene antes de que los usuarios noten la falta de datos?
Las respuestas de la IA pueden incluir errores. Más información




hay otros componentes que se me han olvidado mencionar ? quizás skylab ?
¡Buen ojo! Sí, mencionaste un componente clave. Skylab es una pieza fundamental, pero actúa tras bambalinas. Aquí te detallo su rol y otros "olvidados" que completan el mapa técnico de la plataforma: 
1. Skylab (El Control Plane de Servicios)
Skylab es el sistema encargado del ciclo de vida de las aplicaciones dentro de una instalación de Foundry. 
Palantir Blog
Palantir Blog
Qué hace: Gestiona la instalación, configuración, arranque, parada y actualización de los cientos de microservicios que componen la plataforma.
En tu estrategia: Skylab es donde los administradores configuran el "runtime" de los servicios. Si un servicio no levanta tras una actualización, Skylab es la primera herramienta de diagnóstico antes de mirar los logs de la aplicación. 
Palantir Blog
Palantir Blog
2. Rubix (El Sustrato de Kubernetes)
Si Spark es el motor, Rubix es el chasis sobre el que corre. Es la implementación de Kubernetes propia de Palantir. 
Palantir Blog
Palantir Blog
 +1
Monitoreo: Rubix garantiza que los trabajos de Spark tengan un rendimiento predecible y aislamiento de recursos (multi-tenancy). Si ves fallas sistémicas en múltiples "Builds", el problema suele estar en la salud de los nodos de Rubix gestionados por Apollo. 
Palantir
Palantir
 +2
3. Magritte (El Motor de Ingesta)
Aunque mencionamos HDPS y Data Connection, el servicio interno que realmente ejecuta la ingesta se llama Magritte.
Importancia: Es el componente que interactúa con los agentes para traer datos de fuentes externas (como SAP, SQL o S3). Si los datos no aparecen en el "Landing Area", el monitoreo de los logs de Magritte es esencial.
4. Gatekeeper (Seguridad y Gobernanza)
Es el servicio que aplica las Markings y políticas de acceso a nivel de API.
Visión Global: Si un usuario no puede ver datos que ya están indexados en la Ontología, no es un fallo de Funnel o ES8, sino posiblemente una denegación de Gatekeeper. Monitorear sus logs es vital para auditorías de seguridad y resolución de problemas de acceso. 
Palantir
Palantir
5. OSO (Object Storage Optimizer)
Es un componente más moderno que trabaja junto a OSv2.
Función: Optimiza cómo se almacenan y consultan los objetos para mantener la latencia baja conforme crece la Ontología. 
Resumen de la Estructura Ampliada
Componente 	Capa	Rol en el Monitoreo
Skylab	Infraestructura	Ciclo de vida y configuración de servicios.
Rubix	Infraestructura	Salud del clúster de Kubernetes y nodos de cómputo.
Magritte	Ingesta	Ejecución técnica de conectores y pipelines de entrada.
Gatekeeper	Seguridad	Aplicación de permisos y logs de auditoría.
¿Quieres que veamos cómo se conectan los logs de Skylab y Apollo para diagnosticar fallas cuando un servicio entra en estado "Unhealthy"?
Las respuestas de la IA pueden incluir errores. Más información





undefined
undefined
undefined
8 sitios

Palantir Blog
https://blog.palantir.com
A Sky Full of Clouds - by Robert Fink - Palantir Blog
27 abr 2020 — Skylab: Managing individual environments. To meet the requirements and expectations of our customers, we had to invest in deployme...


01Cloud
https://engineering.01cloud.com
Rubix: Palantir's Move to Kubernetes - Engineering Blog
15 feb 2024 — Palantir Foundry, a data management platform, facilitates data integration through authoring and executing transformation code and...


Palantir Blog
https://blog.palantir.com
Introducing Rubix: Kubernetes at Palantir
16 may 2019 — Background. Palantir Foundry is a data management platform that — among other things — enables users to integrate data by authorin...

Mostrar todo
serías capaz de dibujarme un mockup de como estaría todo organizado ?
¡Claro! Imagina este mockup como un Dashboard Maestro de Observabilidad diseñado para un Administrador de Plataforma. Está organizado de abajo hacia arriba, siguiendo el flujo lógico desde el hardware hasta el usuario.
text
__________________________________________________________________________________

| [FOUNDRY GLOBAL MONITORING]          | Status: OPERATIONAL | Alerts: 2 Minor   |
|______________________________________|_____________________|___________________|
|                                                                                |
|  CAPA 4: EXPERIENCIA DEL USUARIO (CONSUMO)                                     |
|  [ Contour ] [ Object Explorer ] [ Slate ] --> Status: OK (Latencia <200ms)    |
|  [ ES8 Cluster ] [██████████░░] 82% Heap Usage | [ ES8 Latency ] 45ms          |
|________________________________________________________________________________|
|                                                                                |
|  CAPA 3: CORAZÓN DE LA ONTOLOGÍA (INDEXACIÓN)                                  |
|  [ OSS Highbury ] Propagación: 1.2s | [ OSO ] Optimization: Active              |
|  [ Object Data Funnel ]                                                        |
|    - Changelog Jobs: [ OK ]                                                    |
|    - OSv2 Syncs: [ 2 In Progress ] [ 1 Failed! ] <--- [VER DETALLE]            |
|________________________________________________________________________________|
|                                                                                |
|  CAPA 2: MOTOR DE PROCESAMIENTO (CÓMPUTO)                                      |
|  [ Spark / Builds ]                                                            |
|    - Active Slots: 45/100 | Queued: 0 | Resource Usage: [████░░░░░░] 40%        |
|  [ Data Connection / Magritte ]                                                |
|    - Agent HDPS-01: [ Connected ] | Ingest Rate: 1.2 GB/s                       |
|________________________________________________________________________________|
|                                                                                |
|  CAPA 1: SUSTRATO E INFRAESTRUCTURA (BASE)                                     |
|  [ Apollo Control Plane ]                                                      |
|    - Rubix (K8s) Nodes: 12 Online / 0 Error                                    |
|    - Skylab Service Status: [ Healthy ]                                        |
|  [ Persistence Layer ]                                                         |
|    - AtlasDB / Cassandra: [ OK ] | Disk Space: [██████░░░░] 65%                |
|________________________________________________________________________________|
|  LOGS RECIENTES (Gatekeeper):                                                  |
|  14:02:01 - User 'X' - Permission Denied - Dataset 'Y'                         |
|  14:05:45 - Funnel - Validation Error - Field 'Age' expects Integer            |
|________________________________________________________________________________|
Usa el código con precaución.

Cómo leer este Mockup para tu estrategia:
Visión de "Cascada": Si la Capa 1 (Apollo/Skylab) tiene un error, no pierdas tiempo mirando Spark; la base del sistema está fallando.
El "Punto Ciego" (Funnel): He incluido el fallo en OSv2 Syncs. Esto es lo que suele pasar: Spark termina bien (Capa 2), pero el Funnel falla (Capa 3). El usuario ve el tablero "viejo".
Salud de Búsqueda (ES8): Si el Heap Usage de Elasticsearch está en rojo, las búsquedas en la Ontología se congelarán, aunque los datos estén bien indexados.
Seguridad (Gatekeeper): La sección de logs al final te dice si los "errores de datos" son en realidad problemas de permisos.
¿Te gustaría que profundicemos en los parámetros específicos que deberías configurar en las alertas de la Capa 3 (Funnel/OSv2)?
