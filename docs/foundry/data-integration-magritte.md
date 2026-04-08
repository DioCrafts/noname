# Palantir Foundry — Integración de Datos con Magritte (Data Connection)

> Guía de referencia sobre el servicio de integración de fuentes externas en Foundry.
> Última actualización: 2026-04-08

---

## Índice

1. [¿Qué es Magritte / Data Connection?](#1--qué-es-magritte--data-connection)
2. [Arquitectura General](#2-️-arquitectura-general)
3. [Agents: El Puente hacia las Fuentes](#3--agents-el-puente-hacia-las-fuentes)
4. [Tipos de Conectores](#4--tipos-de-conectores)
5. [Modos de Sincronización](#5--modos-de-sincronización)
6. [Configuración de una Conexión](#6-️-configuración-de-una-conexión)
7. [Transformaciones y PII Masking](#7--transformaciones-y-pii-masking)
8. [Seguridad y Red](#8--seguridad-y-red)
9. [Flujo Completo: De la Fuente al Dataset](#9--flujo-completo-de-la-fuente-al-dataset)
10. [Errores Comunes y Troubleshooting](#10--errores-comunes-y-troubleshooting)
11. [Checklist de Configuración](#11--checklist-de-configuración)
12. [Glosario Rápido](#12--glosario-rápido)

---

## 1. 🔌 ¿Qué es Magritte / Data Connection?

**Magritte** es el servicio de **Data Connection** de Palantir Foundry. Su función es conectar la plataforma con **fuentes de datos externas** (bases de datos, APIs, ficheros, etc.) y traer esos datos de forma controlada, segura y repetible hacia el entorno de Foundry.

> El nombre viene del pintor belga René Magritte (*"Ceci n'est pas une pipe"*), una referencia irónica a la idea de que los datos que entran son transformados y ya no son exactamente lo que parecían en la fuente original.

### ¿Por qué es necesario?

```
SIN Magritte                         CON Magritte
┌─────────────────────┐              ┌──────────────────────────┐
│ Foundry             │              │ Foundry                  │
│  (red cerrada)      │   ✗ No hay   │  ┌─────────────────────┐ │
│                     │◄─ conexión ──┤  │  Control Plane      │ │
│                     │   directa   │  │  (Magritte Service) │ │
└─────────────────────┘              │  └────────┬────────────┘ │
                                     └───────────│──────────────┘
┌─────────────────────┐                          │ TLS/443
│ Red Corporativa     │              ┌────────────▼────────────┐
│  - SAP ERP          │◄─────────── │  Agent (en red cliente) │
│  - SQL Server       │             └─────────────────────────┘
│  - Ficheros locales │
└─────────────────────┘
```

**Idea clave:** Los datos de la empresa no se exponen directamente a Foundry. En cambio, un **Agent** ligero en la red del cliente extrae los datos y los envía de forma segura (salida por puerto 443) al Control Plane de Magritte en Foundry.

---

## 2. 🏗️ Arquitectura General

```
┌─────────────────────────────────────────────────────────────┐
│                    PALANTIR FOUNDRY                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Magritte Control Plane                  │   │
│  │  - Gestión de conexiones y credenciales              │   │
│  │  - Programación de sincronizaciones (schedules)      │   │
│  │  - Monitorización de estado de Agents                │   │
│  │  - Gestión de versiones de esquema                   │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │                  Storage Layer                        │   │
│  │     (HDFS / S3 / Azure Blob — Datasets crudos)       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         ▲
                    TLS (puerto 443)
                    Solo saliente
                         │
┌────────────────────────┴────────────────────────────────────┐
│                    RED DEL CLIENTE                           │
│                                                              │
│  ┌────────────────┐    ┌────────────────┐                   │
│  │   Agent 1      │    │   Agent 2      │  ...              │
│  │  (producción)  │    │  (pre-prod)    │                   │
│  └───────┬────────┘    └───────┬────────┘                   │
│          │                     │                             │
│  ┌───────▼────────┐    ┌───────▼────────┐                   │
│  │  SQL Server    │    │  SAP / Oracle  │                   │
│  │  PostgreSQL    │    │  Salesforce    │                   │
│  │  Ficheros CSV  │    │  APIs REST     │                   │
│  └────────────────┘    └────────────────┘                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Componentes principales

| Componente | Dónde vive | Función |
|---|---|---|
| **Magritte Control Plane** | En Foundry | Orquesta las conexiones, schedules y credenciales |
| **Agent** | En la red del cliente | Extrae datos de las fuentes y los envía a Foundry |
| **Connector** | Configurado en el Agent | Plugin específico para cada tipo de fuente (JDBC, REST, S3, etc.) |
| **Source** | Configurado en Foundry | Definición lógica de una fuente de datos (qué tablas, qué frecuencia) |
| **Dataset** | En Foundry Storage | Destino final de los datos extraídos, listo para pipelines |

---

## 3. 🤖 Agents: El Puente hacia las Fuentes

El **Agent** es un proceso Java ligero que se instala en la infraestructura del cliente (on-prem o cloud). Es el único componente de Magritte que vive fuera de Foundry.

### Características del Agent

- **Sin puerto entrante:** Solo abre conexiones *salientes* hacia Foundry (puerto 443 / HTTPS). No requiere abrir puertos en el firewall hacia el Agent.
- **Autenticación mutua (mTLS):** La comunicación está cifrada y autenticada en ambos extremos.
- **Autoactualizado:** Apollo gestiona las actualizaciones del Agent automáticamente.
- **Aislado:** Cada Agent puede conectar con múltiples fuentes, pero los datos nunca se mezclan.

### Ciclo de vida de un Agent

```
1. Instalación          2. Registro            3. Operación
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│ Descarga JAR │──────▶│ Token de     │──────▶│ Pull de      │
│ o paquete    │       │ registro en  │       │ configuración│
│ de Apollo    │       │ Foundry UI   │       │ cada X min   │
└──────────────┘       └──────────────┘       └──────┬───────┘
                                                      │
                                              ┌───────▼───────┐
                                              │ Ejecución de  │
                                              │ sincronización│
                                              │ según schedule│
                                              └───────────────┘
```

### Estados del Agent

| Estado | Descripción |
|---|---|
| `CONNECTED` | El Agent está activo y en comunicación con Foundry |
| `DISCONNECTED` | Sin comunicación — verificar red/firewall/certificados |
| `DEGRADED` | Conectado pero con errores en algún conector |
| `UPDATING` | Apollo está aplicando una actualización |

---

## 4. 🗂️ Tipos de Conectores

Los conectores son plugins que el Agent usa para comunicarse con cada tipo de fuente.

### Conectores de Base de Datos (JDBC)

| Conector | Casos de uso típicos |
|---|---|
| **SQL Server** | ERP Microsoft, Dynamics |
| **PostgreSQL** | Aplicaciones internas, microservicios |
| **Oracle** | Sistemas legados, financiero |
| **MySQL / MariaDB** | Aplicaciones web, e-commerce |
| **Snowflake** | Data warehouse cloud |
| **BigQuery** | Google Cloud analytics |
| **Redshift** | AWS analytics |
| **Databricks** | Delta Lake, lakehouse |

### Conectores de Ficheros

| Conector | Fuente |
|---|---|
| **S3** | Amazon S3, MinIO compatible |
| **Azure Blob / ADLS** | Microsoft Azure Storage |
| **GCS** | Google Cloud Storage |
| **SFTP** | Transferencias de ficheros seguras |
| **NFS / SMB** | Carpetas compartidas de red |

### Conectores de Aplicaciones y APIs

| Conector | Fuente |
|---|---|
| **SAP** | SAP ERP, SAP S/4HANA |
| **Salesforce** | CRM, datos de ventas |
| **ServiceNow** | ITSM, tickets |
| **REST (genérico)** | Cualquier API REST con autenticación |
| **Kafka** | Streaming de eventos |

---

## 5. 🔄 Modos de Sincronización

### 5.1 Batch (Completo vs Incremental)

| Modo | Comportamiento | Cuándo usarlo |
|---|---|---|
| **Full Snapshot** | Extrae *todos* los datos en cada ejecución. Reemplaza el dataset completo. | Tablas pequeñas o cuando no hay columna de timestamp |
| **Incremental** | Solo extrae registros nuevos o modificados desde la última sincronización. | Tablas grandes con columna `updated_at` o `id` autoincremental |
| **Change Data Capture (CDC)** | Captura cambios a nivel de logs de la BD (insert/update/delete). | Alta frecuencia, mínimo impacto en la fuente |

### 5.2 Streaming

Para fuentes en tiempo real (Kafka, eventos):

```
Fuente Kafka ──▶ Agent (consumer) ──▶ Magritte ──▶ Dataset (append)
                    └── micro-batch cada N segundos ──┘
```

### 5.3 Comparativa de Modos

```
                    LATENCIA
        Baja ◄──────────────────────► Alta
         │                               │
   Streaming                        Full Snapshot
  (segundos)                         (horas)
         │                               │
         │         Incremental           │
         │         (minutos)             │
         └───────────────────────────────┘

                    COMPLEJIDAD DE CONFIGURACIÓN
        Baja ◄──────────────────────► Alta
    Full Snapshot    Incremental    CDC / Streaming
```

---

## 6. ⚙️ Configuración de una Conexión

### Pasos para crear una nueva Source en Foundry

```
1. Acceder a Data Connection en Foundry UI
   └─▶ Seleccionar "New Source"

2. Elegir el tipo de conector
   └─▶ Ej: PostgreSQL, SQL Server, S3...

3. Seleccionar el Agent
   └─▶ El Agent que tiene acceso a esa fuente

4. Configurar credenciales
   └─▶ Usuario/contraseña (almacenados cifrados en Foundry)
   └─▶ Connection string / host / puerto

5. Probar la conexión
   └─▶ "Test connection" — verifica conectividad desde el Agent

6. Seleccionar tablas/datasets a importar
   └─▶ Browse schema → seleccionar tablas o queries SQL

7. Configurar el schedule
   └─▶ Cron expression o frecuencia predefinida

8. Mapear al dataset destino
   └─▶ Ruta en Foundry donde se escribirán los datos

9. Activar la sincronización
   └─▶ Primera ejecución manual recomendada para validar
```

### Opciones de configuración del schedule

| Opción | Ejemplo | Uso |
|---|---|---|
| **Bajo demanda** | Manual / API trigger | Cargas puntuales |
| **Cron** | `0 2 * * *` (diario a las 2AM) | Cargas programadas |
| **Continuo** | Sin intervalo fijo | Streaming / CDC |
| **Trigger por evento** | Al completar otro pipeline | Dependencias encadenadas |

---

## 7. 🔒 Transformaciones y PII Masking

Magritte no solo ingesta datos: también puede aplicar transformaciones **en el momento de la extracción**, antes de que los datos lleguen a Foundry.

### Tipos de transformaciones disponibles

| Transformación | Descripción | Ejemplo |
|---|---|---|
| **Column renaming** | Renombrar columnas al vuelo | `cust_id` → `customer_id` |
| **Type casting** | Cambiar tipos de datos | `VARCHAR(20)` → `DATE` |
| **Column filtering** | Excluir columnas sensibles | Eliminar columna `password_hash` |
| **Row filtering** | Filtrar filas en origen | Solo registros `active = true` |
| **PII Masking** | Ofuscar datos personales | Email → `***@dominio.com` |
| **Tokenization** | Sustituir valores por tokens | NIF → token reversible |
| **Null replacement** | Sustituir nulos | `NULL` → `"N/A"` |

### Flujo con PII Masking

```
Base de datos        Agent              Magritte              Dataset Foundry
┌──────────┐        ┌────────┐         ┌─────────────┐       ┌──────────────┐
│ nombre   │        │        │  PII     │             │       │ nombre       │
│ Juan     │──────▶ │Extrae  │─Masking─▶│ Transforma  │──────▶│ J***         │
│ email    │        │datos   │          │ en tránsito │       │ email        │
│ juan@... │        │        │          │             │       │ ***@corp.com │
│ dni      │        │        │          │             │       │ dni          │
│ 12345678A│        │        │          │             │       │ [REDACTED]   │
└──────────┘        └────────┘         └─────────────┘       └──────────────┘
```

> **Importante:** El PII Masking en Magritte es irreversible por diseño. Los datos nunca llegan en claro a Foundry. Para reversibilidad, usar Tokenization con gestión de claves separada.

---

## 8. 🔐 Seguridad y Red

### Modelo de seguridad

```
┌────────────────────────────────────────────────────────┐
│ FOUNDRY (Control Plane)                                │
│  - Almacena credenciales cifradas (no el Agent)        │
│  - Autentica el Agent con certificados mTLS            │
│  - Audita todas las sincronizaciones                   │
└────────────────────────┬───────────────────────────────┘
                         │
                    TLS 1.2/1.3
                    Puerto 443
                    Solo SALIENTE
                         │
┌────────────────────────▼───────────────────────────────┐
│ AGENT (Red del cliente)                                │
│  - Nunca abre puertos entrantes                        │
│  - Las credenciales se envían cifradas desde Foundry   │
│  - Logs de auditoría locales                           │
└────────────────────────────────────────────────────────┘
```

### Requisitos de red para el Agent

| Requisito | Detalle |
|---|---|
| **Salida a internet** | Puerto 443 (HTTPS) hacia el endpoint de Foundry |
| **Acceso a las fuentes** | Puertos nativos de cada BD (1433 SQL Server, 5432 PostgreSQL, etc.) |
| **Sin entrada** | No requiere abrir ningún puerto *hacia* el Agent |
| **Proxy HTTP** | Soportado con configuración de proxy en el Agent |
| **Certificados TLS** | Certificados corporativos deben añadirse al truststore del Agent si hay inspección SSL |

### Almacenamiento de credenciales

- Las credenciales **nunca se almacenan en el Agent**. El Control Plane las envía cifradas justo antes de cada sincronización.
- Se puede integrar con **gestores de secretos externos** (HashiCorp Vault, AWS Secrets Manager).
- Permisos en Foundry: solo usuarios con rol `Data Connection Admin` pueden ver/editar fuentes.

---

## 9. 📊 Flujo Completo: De la Fuente al Dataset

```
FASE 1: EXTRACCIÓN
┌──────────────┐    Query/Pull    ┌──────────────┐
│  Fuente      │◄────────────────│    Agent     │
│  (SQL/SAP/   │─────────────────▶│              │
│   fichero)   │   Datos crudos  │              │
└──────────────┘                 └──────┬───────┘
                                        │
                                   TLS/443
                                        │
FASE 2: TRANSMISIÓN Y TRANSFORMACIÓN    │
                                 ┌──────▼───────┐
                                 │   Magritte   │
                                 │   Control    │
                                 │   Plane      │
                                 │  - PII mask  │
                                 │  - Validar   │
                                 │  - Schema    │
                                 └──────┬───────┘
                                        │
FASE 3: ESCRITURA AL DATASET            │
                                 ┌──────▼───────┐
                                 │   Foundry    │
                                 │   Storage    │
                                 │  (Dataset)   │
                                 └──────┬───────┘
                                        │
FASE 4: PIPELINE / ONTOLOGÍA            │
                                 ┌──────▼───────────────────────┐
                                 │  Spark / Build               │
                                 │  └─▶ Transformaciones        │
                                 │  └─▶ Funnel / Ontología      │
                                 │  └─▶ Aplicaciones (Workshop) │
                                 └──────────────────────────────┘
```

### Linaje de datos

Foundry registra automáticamente el linaje completo: desde la fuente original hasta cualquier dataset derivado o objeto de la Ontología. Esto permite responder siempre a la pregunta: *"¿De dónde viene este dato?"*

---

## 10. 🐛 Errores Comunes y Troubleshooting

| Error | Causa habitual | Solución |
|---|---|---|
| `Agent DISCONNECTED` | Firewall bloqueando puerto 443 saliente | Verificar reglas de firewall; abrir salida a `*.palantirfoundry.com:443` |
| `Connection timeout` | El Agent no llega a la BD | Comprobar que el Agent tiene acceso de red a la BD (host/puerto) |
| `SSL handshake failed` | Certificado corporativo no reconocido | Añadir certificado raíz corporativo al truststore del Agent (`cacerts`) |
| `Authentication failed` | Credenciales incorrectas o expiradas | Actualizar credenciales en la Source dentro de Foundry UI |
| `Schema mismatch` | La BD cambió una columna o tipo | Actualizar el esquema en la definición de la Source; revisar pipelines downstream |
| `Sync job failed: OOM` | Tabla demasiado grande para Full Snapshot | Cambiar a modo Incremental; aumentar heap del Agent (`-Xmx`) |
| `PII rule not applied` | Regla de masking mal configurada | Verificar que la columna afectada tiene el tipo correcto y la regla está activa |
| `Dataset locked` | Otra sincronización en curso | Esperar a que termine; revisar schedule para evitar solapamientos |

---

## 11. ✅ Checklist de Configuración

Usa esta lista antes de poner una nueva fuente en producción:

### Infraestructura y red
- [ ] El Agent está instalado en un servidor con acceso a la fuente de datos
- [ ] El Agent puede alcanzar `*.palantirfoundry.com` por puerto 443 (saliente)
- [ ] El servidor del Agent tiene acceso al puerto nativo de la BD (ej: 1433, 5432)
- [ ] Los certificados TLS corporativos están añadidos al truststore del Agent
- [ ] Proxy configurado si la red del cliente lo requiere

### Credenciales y seguridad
- [ ] Se ha creado una cuenta de servicio (service account) en la BD fuente con permisos de solo lectura
- [ ] Las credenciales están configuradas en Foundry (no hardcodeadas en el Agent)
- [ ] Se han definido reglas de PII Masking para columnas sensibles
- [ ] Los permisos de la Source en Foundry están restringidos al equipo responsable

### Configuración de la Source
- [ ] La conexión de prueba ("Test connection") devuelve OK
- [ ] Se han seleccionado solo las tablas necesarias (principio de mínimo privilegio)
- [ ] El modo de sincronización es el adecuado (Full / Incremental / CDC)
- [ ] El schedule está configurado y no solapa con cargas pesadas en la BD fuente
- [ ] El dataset destino en Foundry tiene la ruta y permisos correctos

### Validación post-puesta en producción
- [ ] Primera sincronización manual ejecutada y validada (filas, tipos, nulos)
- [ ] El linaje en Foundry muestra correctamente el origen del dataset
- [ ] Se ha configurado una alerta o notificación si la sincronización falla
- [ ] Los pipelines downstream (Spark/Build) se han ejecutado con los nuevos datos

---

## 12. 📖 Glosario Rápido

| Término | Definición |
|---|---|
| **Magritte** | Nombre interno del servicio Data Connection de Foundry |
| **Agent** | Proceso ligero instalado en la red del cliente para extraer datos |
| **Control Plane** | Componente de Foundry que orquesta y configura los Agents |
| **Source** | Definición lógica de una fuente de datos en Foundry UI |
| **Connector** | Plugin específico para un tipo de fuente (JDBC, S3, REST...) |
| **Full Snapshot** | Modo de sincronización que extrae todos los datos en cada ejecución |
| **Incremental** | Modo que solo extrae registros nuevos/modificados |
| **CDC** | Change Data Capture — captura cambios a nivel de log de BD |
| **PII Masking** | Ofuscación irreversible de datos personales en la extracción |
| **Tokenization** | Sustitución reversible de valores sensibles por tokens |
| **Schedule** | Configuración de cuándo y con qué frecuencia se sincroniza |
| **mTLS** | Mutual TLS — autenticación cifrada en ambos extremos del canal |
| **Dataset** | Destino en Foundry donde se escriben los datos extraídos |
| **Linaje** | Trazabilidad completa del origen y transformaciones de un dato |

---

## Referencias

- [Palantir Foundry Documentation — Data Connection](https://www.palantir.com/docs/foundry/data-connection/)
- Componentes relacionados: ver [`palantir-foundry-componentes.md`](palantir-foundry-componentes.md)
- Ontología y uso de datos integrados: ver [`ontologia-foundry.md`](ontologia-foundry.md)
