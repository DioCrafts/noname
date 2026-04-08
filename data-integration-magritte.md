# Data Integration en Palantir Foundry (Magritte) — Apuntes

> Esta nota resume cómo entran los datos a Foundry: conectores, **Magritte Data Connection**, Agents, modos de sincronización, y patrones de ingesta.
>
> Última actualización: 2026-04-08

---

## Índice

1. [Qué es Data Connection (Magritte)](#1-qué-es-data-connection-magritte)
2. [Conceptos clave](#2-conceptos-clave)
3. [Arquitectura: Control Plane vs Data Plane](#3-arquitectura-control-plane-vs-data-plane)
4. [Agents](#4-agents)
5. [Tipos de conectores y fuentes](#5-tipos-de-conectores-y-fuentes)
6. [Batch vs Incremental vs Streaming](#6-batch-vs-incremental-vs-streaming)
7. [Esquemas, particionado y formatos](#7-esquemas-particionado-y-formatos)
8. [Seguridad y red (on-prem)](#8-seguridad-y-red-on-prem)
9. [Observabilidad y troubleshooting](#9-observabilidad-y-troubleshooting)
10. [Patrones recomendados](#10-patrones-recomendados)
11. [Checklist de puesta en marcha](#11-checklist-de-puesta-en-marcha)

---

## 1. Qué es Data Connection (Magritte)

**Magritte (Data Connection)** es el subsistema de Foundry encargado de:
- Conectar con **fuentes externas** (DBs, ERP, APIs, ficheros, cloud buckets, etc.)
- Extraer datos de forma **segura** (normalmente a través de Agents)
- Escribir esos datos en Foundry como **datasets** (raw/bronze)
- Programar y gobernar sincronizaciones (incluyendo incrementales)

Piensa en Magritte como el “puerto de entrada” al lago de datos de Foundry.

---

## 2. Conceptos clave

| Término | Qué significa en Foundry |
|---|---|
| **Source** | Sistema externo (ej: SAP, Postgres, S3, API REST) |
| **Connector** | Adaptador lógico para hablar con un tipo de source |
| **Connection** | Configuración concreta de acceso a un source (credenciales + endpoint + opciones) |
| **Sync / Ingest** | Ejecución que copia datos hacia Foundry |
| **Dataset raw** | Primer dataset resultante (bronze), con mínima transformación |
| **Schema drift** | Cambios en el schema de origen (columnas nuevas, tipos cambiados) |
| **CDC** | Change Data Capture (captura de cambios) para incrementales |

---

## 3. Arquitectura: Control Plane vs Data Plane

En entornos enterprise/on-prem es útil separar mentalmente:

- **Control Plane (Foundry)**: UI + APIs + scheduler + gestión de credenciales, definiciones de sync, auditoría.
- **Data Plane (Agents + source)**: donde realmente ocurre la extracción (cerca de la red del source).

```
[Foundry Control Plane]
  Carbon/UI  ── define sync ──▶  Magritte
                               │
                               ▼
                      [Agent (Data Plane)]
                          │   (pull/push)
                          ▼
                     [Source externo]
                          │
                          ▼
                 Datos → Foundry Storage → Dataset raw
```

**Idea práctica:** Foundry intenta evitar que sistemas internos “entren” a la red del cliente; suele preferirse comunicación saliente desde el Agent.

---

## 4. Agents

### 4.1 Qué es un Agent

Un **Agent** es un proceso ligero (normalmente container/VM/servicio) desplegado en la red del cliente que:
- Se conecta a los **sources internos** (DBs, file shares, SAP, etc.)
- Se comunica con Foundry a través de TLS
- Ejecuta tareas de extracción sin exponer la red interna

### 4.2 Responsabilidades del Agent

- Autenticación hacia Foundry (certificados / tokens según despliegue)
- Gestión de conectividad (DNS, proxies, firewalls)
- Ejecución de jobs de ingesta
- Retries y buffering básico (dependiendo del conector)

### 4.3 Buenas prácticas de Agents

- Instalar Agents **cerca del source** (misma subred/VPC cuando sea posible)
- Aislar por dominios: 1 pool para ERP, otro para IoT, etc.
- Dimensionar por:
  - ancho de banda
  - concurrencia
  - tamaño de tabla/volumen diario
  - latencias de la DB

---

## 5. Tipos de conectores y fuentes

> Foundry suele proveer conectores “managed” y también permite integraciones vía APIs.

### 5.1 Bases de datos

- Postgres / MySQL
- SQL Server
- Oracle
- DB2
- Snowflake / BigQuery / Redshift (cuando el source es cloud)

**Patrones típicos:**
- Full extract de tablas pequeñas
- Incremental por `updated_at` o por PK monotónica
- CDC si el conector lo soporta

### 5.2 ERP / Sistemas enterprise

- SAP (típico en industria)
- Salesforce / Dynamics (depende del stack del cliente)

### 5.3 Ficheros

- S3 / Azure Blob / GCS
- SFTP
- Network shares (SMB/NFS) — según despliegue

### 5.4 APIs

- REST/GraphQL
- Webhooks como fuente de eventos (si se usa un collector intermedio)

### 5.5 Streaming (si aplica)

- Kafka / Event Hubs / Kinesis

**Nota:** muchas veces el streaming entra primero en un “landing dataset” o un store intermedio y luego se normaliza con pipelines.

---

## 6. Batch vs Incremental vs Streaming

### 6.1 Batch (full refresh)

- Copia todo el dataset cada vez.
- Pros: simple, robusto.
- Contras: caro, lento, duplica carga en el source.

### 6.2 Incremental (delta)

- Copia solo cambios desde la última sync.
- Técnicas:
  - columna `updated_at`
  - partición por fecha
  - CDC (log-based) si está disponible

### 6.3 Streaming

- Consumo continuo de eventos.
- Requiere diseño aguas abajo: deduplicación, ventanas, idempotencia.

---

## 7. Esquemas, particionado y formatos

### 7.1 Schema management

- Definir qué hacer con **schema drift**:
  - bloquear y alertar
  - permitir columnas nuevas
  - mapear a un schema “contract”

### 7.2 Particionado

- Particionar por fecha (`event_date`, `ingest_date`) para:
  - acelerar queries
  - facilitar incrementales
  - controlar costes

### 7.3 Formatos

- Parquet suele ser el formato objetivo para analítica.
- JSON/CSV se usa a veces en landing pero se recomienda normalizar.

---

## 8. Seguridad y red (on-prem)

### 8.1 Reglas de red típicas

- Preferencia por **salida** desde Agent hacia Foundry (HTTPS/TLS, puerto 443).
- Evitar inbound hacia la red interna del cliente.

### 8.2 Credenciales

- Principio de mínimo privilegio: el usuario de DB solo lectura.
- Rotación de secretos.
- Segregar credenciales por entorno (dev/pre/prod).

### 8.3 Gobernanza

- El dataset resultante hereda permisos/ownership según configuración.
- Gatekeeper / Multipass aplican controles de acceso.

---

## 9. Observabilidad y troubleshooting

### Señales típicas

| Síntoma | Causa probable |
|---|---|
| Sync lenta | falta de índices en source, red lenta, query mala, demasiada concurrencia |
| Timeouts | firewall/proxy, latencia DB, límites de API |
| Duplicados | incremental mal definido, no hay PK estable, dedup faltante |
| Cambios no aparecen | watermark mal calculado, timezone, CDC no activo |
| Schema mismatch | drift en origen, tipos incompatibles |

### Diagnóstico

- Revisar logs del Agent
- Validar query/where de incremental
- Validar límites de API (rate limits)
- Validar permisos del usuario de conexión

---

## 10. Patrones recomendados

### 10.1 Bronze/Silver/Gold

1. **Bronze (raw)**: ingesta casi sin cambios.
2. **Silver (clean)**: normalización, tipos, deduplicación, quality checks.
3. **Gold (curated)**: modelo listo para negocio/ontología.

### 10.2 Idempotencia

- Diseñar ingestas para que re-ejecutar no genere inconsistencias.
- Usar claves determinísticas.

### 10.3 Watermarks

- Para incrementales, manejar watermark (último timestamp/offset procesado).
- Cuidado con late-arriving data: usar “lookback window”.

---

## 11. Checklist de puesta en marcha

- [ ] Identificar sources y owners
- [ ] Definir modo de sync (batch/incremental/streaming)
- [ ] Definir claves (PK) y estrategia de deduplicación
- [ ] Preparar Agent (red, TLS, proxy, DNS)
- [ ] Crear connection con credenciales mínimas
- [ ] Probar sync pequeña (smoke test)
- [ ] Medir carga en el source
- [ ] Implementar observabilidad (alertas, logs)
- [ ] Formalizar schema contract / manejo de drift
- [ ] Crear pipelines silver/gold

---

## Referencias

- Ver también: `palantir-foundry-componentes.md`
- Ver también: `ontologia-foundry.md`
