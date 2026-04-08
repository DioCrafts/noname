# Data Integration en Palantir Foundry — Magritte (Data Connection)

> Esta guía describe cómo entran los datos en Foundry, con foco en **Magritte** (Data Connection) y sus **Agents**.
>
> Última actualización: 2026-04-08

---

## Índice

1. [¿Qué es Magritte?](#1--qué-es-magritte)
2. [Conceptos clave](#2--conceptos-clave)
3. [Arquitectura (Control plane vs Data plane)](#3--arquitectura-control-plane-vs-data-plane)
4. [Tipos de fuentes (sources)](#4--tipos-de-fuentes-sources)
5. [Agents](#5--agents)
6. [Modos de ingesta: batch vs incremental vs streaming](#6--modos-de-ingesta-batch-vs-incremental-vs-streaming)
7. [Extracción → Staging → Dataset](#7--extracción--staging--dataset)
8. [Esquemas, tipos y evolución (schema drift)](#8--esquemas-tipos-y-evolución-schema-drift)
9. [Seguridad y red (TLS, puertos, credenciales)](#9--seguridad-y-red-tls-puertos-credenciales)
10. [Observabilidad y troubleshooting](#10--observabilidad-y-troubleshooting)
11. [Checklist de puesta en marcha](#11--checklist-de-puesta-en-marcha)
12. [Glosario](#12--glosario)

---

## 1. 🔌 ¿Qué es Magritte?

**Magritte** (también llamado **Data Connection**) es el subsistema de Foundry encargado de **conectar Foundry con sistemas externos** y traer datos hacia la plataforma.

En una frase:

> Magritte = conectores + ejecución de ingestas + agents en red del cliente + control de credenciales + scheduling de pulls.

**Objetivos típicos:**
- Importar tablas de una base de datos (Postgres, Oracle, SQL Server)
- Consumir APIs (REST/SOAP)
- Traer ficheros (SFTP, shares, buckets)
- Ingesta de SaaS (Salesforce, ServiceNow, etc.)
- Ingesta de eventos/streams (Kafka, etc.)

---

## 2. 🧩 Conceptos clave

| Concepto | Qué es | Para qué sirve |
|---|---|---|
| **Connection** | Definición de conexión a una fuente externa | Guardar host/URL, tipo de conector, auth, etc. |
| **Source** | Un origen de datos dentro de una Connection | Ej: una tabla concreta, una ruta SFTP, un endpoint API |
| **Ingest job / Sync** | Ejecución de ingesta | Traer datos (snapshot o delta) hacia Foundry |
| **Agent** | Proceso instalado en la red del cliente | Ejecutar la extracción “cerca” de la fuente cuando no hay acceso directo |
| **Staging** | Zona de aterrizaje en Foundry | Datos crudos antes de normalizarlos/curarlos |
| **Dataset** | Tabla/archivo dentro del catálogo de Foundry | Entrada al mundo de pipelines/transformaciones |

---

## 3. 🏗️ Arquitectura (Control plane vs Data plane)

Una forma útil de entenderlo:

- **Control plane**: UI/API de Foundry donde defines conexiones, credenciales, schedules, y ves logs.
- **Data plane**: ejecución real del “pull” de datos (normalmente en un **Agent**) y escritura en storage.

```
[Foundry UI / APIs]
      │  (define connection/schedule)
      ▼
[Magritte Control Plane]
      │  (instrucciones)
      ▼
[Agent en red del cliente] ── extrae datos ──▶ [Staging en Foundry] ──▶ [Dataset]
```

**Idea clave:** en entornos on-prem/segregados, el Agent suele comunicarse hacia Foundry por **salida (egress)**, evitando abrir entradas (ingress) en red.

---

## 4. 🗂️ Tipos de fuentes (sources)

### 4.1 Bases de datos (JDBC/ODBC)
- Tablas y vistas
- Queries parametrizadas
- Extracción por rango (ej: `updated_at`) para incremental

### 4.2 Ficheros
- SFTP
- Carpetas compartidas
- Buckets (S3/Azure Blob/GCS)
- CSV / JSON / Parquet / Avro

### 4.3 APIs
- REST
- SOAP
- Paginación
- Rate limits

### 4.4 SaaS
- Salesforce, ServiceNow, etc.
- Autenticación OAuth / tokens
- APIs de extracción con límites

### 4.5 Streaming (si aplica)
- Kafka / event bus
- Semántica de offsets
- Ventanas temporales

---

## 5. 🤝 Agents

Los **Agents** son el componente crítico cuando:
- La fuente está en una red que Foundry no puede acceder directamente
- Hay requerimientos de seguridad (no exponer DB a la plataforma)
- Se necesita extraer datos muy cerca del origen

### 5.1 Responsabilidades típicas
- Conectarse a la fuente (DB/API/files)
- Leer datos (snapshot o delta)
- Serializar y enviar hacia Foundry
- Reintentos y backoff
- Logging local + reporting hacia Foundry

### 5.2 Consideraciones operativas
- Alta disponibilidad (varios agents)
- Rotación de credenciales
- Certificados TLS
- Proxy corporativo

---

## 6. ⏱️ Modos de ingesta: batch vs incremental vs streaming

| Modo | Qué trae | Cuándo usar |
|---|---|---|
| **Batch / Snapshot** | Copia completa | Tablas pequeñas/medianas o ingestas iniciales |
| **Incremental / Delta** | Solo cambios | Tablas grandes, sincronizaciones frecuentes |
| **Streaming** | Eventos continuos | Datos en tiempo real (sensores, clickstream) |

### 6.1 Patrones de incremental
- **Timestamp watermark**: `updated_at > last_success`
- **ID creciente**: `id > last_id`
- **CDC** (si la fuente lo soporta): log de cambios

---

## 7. 🧱 Extracción → Staging → Dataset

Una ingesta suele producir:

1. **Staging/raw landing** (datos crudos)
2. **Dataset estructurado** (tipos correctos, schema estable)
3. **Dataset curado** (para consumo por pipelines y/o Ontología)

Recomendación práctica:
- Mantén un dataset **raw** inmutable
- A partir de ahí, transforma hacia `clean` / `conformed`

---

## 8. 🧬 Esquemas, tipos y evolución (schema drift)

Problemas comunes:
- Una columna cambia de tipo (string → int)
- Aparecen columnas nuevas
- Columnas desaparecen

Buenas prácticas:
- **Versionar** el contrato del dataset
- Validar schema antes de publicar datasets downstream
- Normalizar nombres (snake_case) y tipos

---

## 9. 🔐 Seguridad y red (TLS, puertos, credenciales)

### 9.1 Red
- Patrón típico: el Agent hace conexión **saliente** a Foundry (egress), normalmente por **443/TCP**.
- Si hay proxy corporativo, planificarlo desde el inicio.

### 9.2 TLS
- Certificados y truststore correctos en el Agent
- Evitar inspección TLS si rompe mTLS (depende del entorno)

### 9.3 Credenciales
- Principio de mínimo privilegio (solo SELECT si es DB)
- Rotación programada
- Evitar hardcode: usar el gestor de secretos/credenciales de Foundry

---

## 10. 🔎 Observabilidad y troubleshooting

Qué mirar cuando algo falla:

1. **Estado del Agent**: online/offline
2. **Logs de la sync**: errores de auth, timeouts, rate limits
3. **Conectividad**: DNS, proxy, firewall
4. **Permisos en source**: SELECT/READ
5. **Schema drift**: cambios en columnas
6. **Volumen**: timeouts por tablas enormes

### Síntomas típicos
- Sync en `PENDING`: normalmente scheduling/colas o Agent sin capacidad
- `AUTH_FAILED`: credencial expirada o permisos insuficientes
- `TLS handshake`: CA/certificados mal instalados
- `Too many requests`: rate limit en APIs

---

## 11. ✅ Checklist de puesta en marcha

- [ ] Identificar fuentes y dueños (DBA / API owner)
- [ ] Elegir modo de ingesta (snapshot vs delta vs streaming)
- [ ] Definir SLA: frecuencia, latencia, volumen
- [ ] Preparar infraestructura del Agent (VM/Pod), HA si necesario
- [ ] Configurar salida a Foundry (443, proxy, DNS)
- [ ] Configurar TLS/certificados
- [ ] Crear Connection + Sources
- [ ] Ejecutar primera ingesta (snapshot)
- [ ] Estabilizar schema (raw → clean)
- [ ] Alertas/monitorización

---

## 12. 📖 Glosario

| Término | Significado |
|---|---|
| **Data Connection / Magritte** | Subsistema de conectores e ingestas hacia Foundry |
| **Agent** | Proceso en red del cliente que ejecuta extracciones |
| **Source** | Origen concreto: tabla, endpoint, carpeta, etc. |
| **Sync / Ingest job** | Ejecución de una ingesta |
| **Staging** | Zona de aterrizaje de datos crudos |
| **Schema drift** | Cambios no controlados en el esquema de la fuente |

---

## Relación con otros apuntes

- Para la capa semántica: ver `ontologia-foundry.md`
- Para orquestación y pipelines: ver `palantir-foundry-componentes.md`