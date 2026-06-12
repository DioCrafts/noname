# Flujo de Datos End-to-End en Palantir Foundry — Apuntes

> Caso completo (práctico) de extremo a extremo: **Fuente externa → Magritte (Agents) → Bronze/Silver/Gold → Ontología (Funnel/Phonograph/ES8) → Workshop/AIP → Actions (write-back)**, con consideraciones **on‑prem (OpenShift/Rubix)**.
>
> **Para quién:** cualquier miembro del equipo que quiera entender cómo viaja un dato por Foundry de principio a fin. Si solo lees un documento de esta carpeta, que sea este.
>
> Última actualización: 2026-06-12

---

## Índice

1. [Vista general del flujo](#1-vista-general-del-flujo)
2. [Caso de ejemplo: Pedidos/Clientes](#2-caso-de-ejemplo-pedidosclientes)
3. [Ingesta (Magritte + Agents) → Bronze](#3-ingesta-magritte--agents--bronze)
4. [Transformaciones → Silver](#4-transformaciones--silver)
5. [Curación → Gold](#5-curación--gold)
6. [Incrementales: watermarks, lookback e idempotencia](#6-incrementales-watermarks-lookback-e-idempotencia)
7. [Calidad de datos y contratos de esquema](#7-calidad-de-datos-y-contratos-de-esquema)
8. [Publicación a Ontología (backing datasets)](#8-publicación-a-ontología-backing-datasets)
9. [Indexing: Funnel → Phonograph/ES8 → OSS](#9-indexing-funnel--phonographes8--oss)
10. [Consumo: Workshop](#10-consumo-workshop)
11. [Consumo: AIP/LLMs (grounding + Actions)](#11-consumo-aipllms-grounding--actions)
12. [Write-back: Actions y datasets de escritura](#12-write-back-actions-y-datasets-de-escritura)
13. [On‑prem (OpenShift/Rubix): red, TLS, proxies y air‑gapped](#13-on-prem-openshiftrubix-red-tls-proxies-y-air-gapped)
14. [Observabilidad y troubleshooting](#14-observabilidad-y-troubleshooting)
15. [Checklist end-to-end (antes de producción)](#15-checklist-end-to-end-antes-de-producción)
16. [Referencias internas del repo](#16-referencias-internas-del-repo)

---

## 1. Vista general del flujo

Diagrama "de manual":

```
FUERA DE FOUNDRY                 DENTRO DE FOUNDRY
┌──────────────┐
│ Fuente       │   1. Ingesta   ┌─────────┐  2. Pipelines  ┌──────────────────┐
│ (SQL Server, │───────────────▶│ Bronze  │───────────────▶│ Silver → Gold    │
│  SAP, API…)  │  Agent+Magritte│ (raw)   │  Spark / Build │ (clean/curated)  │
└──────────────┘                └─────────┘                └────────┬─────────┘
                                                                    │ 3. Indexing
                                                                    ▼ (Funnel)
                              ┌───────────────────────────────────────────────┐
                              │ ONTOLOGÍA                                     │
                              │ Phonograph (objetos) + ES8 (búsqueda) + OSS   │
                              └────────┬────────────────────────────┬─────────┘
                                       │ 4. Consumo                 │
                              ┌────────▼────────┐          ┌────────▼────────┐
                              │ Workshop (apps) │          │ AIP (LLMs)      │
                              └────────┬────────┘          └────────┬────────┘
                                       │ 5. Write-back (Actions)    │
                                       └──────────────┬─────────────┘
                                                      ▼
                                       ┌──────────────────────────┐
                                       │ Writeback dataset        │
                                       │ (vuelve a pipelines)     │
                                       └──────────────────────────┘
```

En palabras simples, son **5 etapas**:

| Etapa | Qué pasa | Quién lo hace |
|---|---|---|
| 1. Ingesta | Los datos salen del sistema origen y entran a Foundry como dataset crudo | Magritte + Agent |
| 2. Pipelines | Se limpian, deduplican y modelan (Bronze → Silver → Gold) | Spark, orquestado por Build |
| 3. Indexing | El dataset Gold se convierte en objetos navegables y buscables | Funnel → Phonograph/ES8 |
| 4. Consumo | Personas (Workshop) o LLMs (AIP) leen y operan sobre los objetos | Workshop / AIP, vía OSS |
| 5. Write-back | Las decisiones del usuario se escriben de vuelta, auditadas | Actions → writeback dataset |

> **Idea clave:** en Foundry los datos no "terminan" en un dashboard. Terminan en **objetos sobre los que se actúa** (aprobar, asignar, cerrar…), y esas acciones vuelven a entrar al ciclo como datos.

---

## 2. Caso de ejemplo: Pedidos/Clientes

Usaremos este caso durante todo el documento:

- **Negocio:** una empresa recibe pedidos en un ERP con base de datos **SQL Server** (on-prem).
- **Objetivo:** una app donde el equipo de operaciones vea pedidos pendientes, detecte bloqueos y pueda **aprobar/rechazar** pedidos desde Foundry.
- **Tablas origen:** `dbo.customers` y `dbo.orders` (con columna `updated_at`).

Lo que construiremos:

```
SQL Server                      Foundry
┌────────────┐    ┌─────────────────────────────────────────────────┐
│ customers  │──▶ │ raw_customers → customers_clean → customers_agg │
│ orders     │──▶ │ raw_orders    → orders_clean    → orders_fact   │
└────────────┘    └───────────────────────┬─────────────────────────┘
                                          ▼
                       Object Types: Customer, Order (+ link 1:N)
                                          ▼
                       App Workshop "Gestión de Pedidos" + Action "Aprobar pedido"
```

---

## 3. Ingesta (Magritte + Agents) → Bronze

> Detalle completo en [`03-data-integration-magritte.md`](03-data-integration-magritte.md).

### Qué se configura

1. **Agent** instalado en un servidor de la red corporativa con acceso a SQL Server (puerto 1433) y salida HTTPS (443) hacia Foundry. No se abre ningún puerto entrante.
2. **Source** en Data Connection: conector JDBC SQL Server, credenciales de una cuenta de servicio **de solo lectura**, guardadas cifradas en Foundry (nunca en el Agent).
3. **Syncs**: una por tabla, en modo **incremental** usando `updated_at`:
   - `raw_customers` ← `SELECT * FROM dbo.customers WHERE updated_at > ?`
   - `raw_orders` ← `SELECT * FROM dbo.orders WHERE updated_at > ?`
4. **Schedule**: cada 15 minutos (o lo que tolere la fuente sin degradarla).

### Resultado: datasets Bronze

- `raw_customers` y `raw_orders` aparecen en Foundry como datasets **versionados** y con **linaje** desde la fuente.
- Regla de oro de Bronze: **no transformar** (o lo mínimo). Conservar columnas originales para poder auditar y reconstruir.

### Errores típicos en esta etapa

| Síntoma | Causa habitual |
|---|---|
| Agent `DISCONNECTED` | Firewall/proxy bloquea la salida 443, o certificado corporativo sin instalar |
| `Authentication failed` | Credenciales rotadas en la BD pero no actualizadas en la Source |
| Sync lenta | Falta índice sobre `updated_at` en la tabla origen |

---

## 4. Transformaciones → Silver

> Detalle completo en [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md).

Silver = datos **limpios y estandarizados**, todavía cerca del modelo origen.

**`customers_clean`** (desde `raw_customers`):
- cast de tipos (fechas a `date`, importes a `decimal`),
- normalización de emails (lowercase, trim),
- deduplicación por `customer_id` quedándose con el registro de `updated_at` más reciente,
- checks: `customer_id` not null y único.

**`orders_clean`** (desde `raw_orders`):
- cast de importes y fechas,
- descarte (o cuarentena) de filas corruptas,
- normalización del enum `status` ∈ {`PENDING`, `APPROVED`, `REJECTED`, `SHIPPED`},
- deduplicación por `order_id`.

> **Por qué dedup aquí:** la ingesta incremental con lookback (sección 6) **reimporta** filas a propósito. Silver es donde se garantiza "una fila por entidad".

---

## 5. Curación → Gold

Gold = modelo **pensado para el consumo** (apps, Ontología, BI), no para reflejar el origen.

**`orders_fact`**:
- join de `orders_clean` + `customers_clean` (trae nombre del cliente, segmento…),
- métricas derivadas: `total_amount`, `days_pending` (hoy − fecha de pedido),
- particionado por `order_date`.

**`customers_agg`**:
- agregados por cliente: `total_orders`, `total_spent`, `last_order_at`.

> **Contrato de esquema:** a partir de Gold, el esquema se considera **estable**. Workshop, la Ontología y otros equipos dependen de él; cambiar una columna aquí es un cambio de API, no un detalle interno.

---

## 6. Incrementales: watermarks, lookback e idempotencia

Los tres conceptos que hacen que el pipeline sea barato **y** correcto:

| Concepto | Qué es | En nuestro ejemplo |
|---|---|---|
| **Watermark** | "Hasta aquí ya procesé" | `max(updated_at)` de la última ejecución |
| **Lookback** | Reprocesar un margen hacia atrás para capturar datos que llegan tarde | reprocesar siempre los últimos 2 días |
| **Idempotencia** | Ejecutar dos veces no duplica ni corrompe | dedup por PK + `updated_at` más reciente |

Flujo de cada ejecución:

```
1. Leer watermark anterior (ej: 2026-06-10 14:00)
2. Pedir a la fuente: updated_at > watermark − lookback(2 días)
3. Unir con lo existente y deduplicar por PK (order_id / customer_id)
4. Escribir output y guardar nuevo watermark
```

> **Por qué importa:** sin lookback pierdes correcciones tardías; sin dedup el lookback crea duplicados; sin watermark cada ejecución reprocesa todo (caro y lento).

---

## 7. Calidad de datos y contratos de esquema

Checks mínimos recomendados para este caso (se ejecutan dentro del build; si fallan, el build falla **antes** de contaminar downstream):

| Check | Dataset | Regla |
|---|---|---|
| PK not null + única | `*_clean` | `order_id`, `customer_id` |
| Dominio de enum | `orders_clean` | `status` dentro de la lista válida |
| Rango | `orders_clean` | `total_amount >= 0`, fechas no futuras |
| Integridad referencial | `orders_fact` | todo `customer_id` existe en `customers_clean` |
| Freshness | `orders_fact` | actualizado en las últimas 2 horas |

**Schema drift** (el origen añade/cambia columnas): decidir la política por dataset —
- *bloquear* (el build falla y alguien revisa): más seguro para Gold,
- *permitir columnas nuevas*: aceptable en Bronze.

---

## 8. Publicación a Ontología (backing datasets)

> Detalle completo en [`06-ontologia-foundry.md`](06-ontologia-foundry.md).

En **Ontology Manager** se definen:

| Object Type | Backing dataset | Primary key | Propiedades destacadas |
|---|---|---|---|
| `Customer` | `customers_agg` | `customer_id` | name, segment, total_spent, last_order_at |
| `Order` | `orders_fact` | `order_id` | status, total_amount, order_date, days_pending |

Y un **Link Type**: `Customer 1:N Order` (vía `customer_id`).

Reglas prácticas:
- El backing dataset debe ser **Gold** (o Silver muy estable). Nunca Bronze.
- La **primary key no puede cambiar** entre ejecuciones: si el ID de un objeto cambia, para la Ontología es un objeto nuevo (y el viejo "desaparece").
- Marcar como *searchable* solo las propiedades que de verdad se buscarán (name, status…): indexar todo encarece y ralentiza.

---

## 9. Indexing: Funnel → Phonograph/ES8 → OSS

Cuando `orders_fact` se actualiza, ocurre automáticamente:

```
orders_fact (nueva versión del dataset)
      │
      ▼
Funnel detecta el cambio e indexa
      ├─▶ Phonograph  → almacena los objetos Order (lectura/escritura rápida para apps)
      └─▶ ES8         → indexa propiedades buscables (búsqueda full-text y filtros)
      ▼
OSS (Object Set Service) resuelve consultas sobre esos objetos a escala
```

**Implicación práctica:** hay una **latencia de indexing** entre "el build terminó" y "veo el cambio en la app". Suele ser de segundos a minutos. Si alguien dice *"actualicé el dataset pero no veo los objetos"*, casi siempre es:
1. el build de Gold aún no corrió,
2. Funnel va atrasado o está bloqueado,
3. la PK cambió y los objetos se reemplazaron en lugar de actualizarse.

> Diagnóstico paso a paso en [`11-errores-comunes-y-troubleshooting.md`](11-errores-comunes-y-troubleshooting.md), sección 6.

---

## 10. Consumo: Workshop

> Detalle completo en [`07-workshop-apps-operativas.md`](07-workshop-apps-operativas.md).

La app "Gestión de Pedidos" usa el patrón **search–filter–detail**:

```
┌─────────────────────────────────────────────────────┐
│ Filtros: [status = PENDING] [segmento] [fecha]      │
├──────────────────────────┬──────────────────────────┤
│ Tabla de Orders          │ Detalle del Order        │
│ (Object Set filtrado)    │ + datos del Customer     │
│                          │ (vía link)               │
│                          │ [Aprobar]  [Rechazar]    │
└──────────────────────────┴──────────────────────────┘
```

- La tabla se alimenta de un **Object Set**: "Orders con status = PENDING", ordenado por `days_pending` desc.
- El panel de detalle navega el **link** Order → Customer sin escribir ningún join: la relación ya vive en la Ontología.
- Los botones ejecutan **Actions** (sección 12).

**Seguridad:** Workshop **no eleva permisos**. Cada usuario ve solo los objetos que Gatekeeper le permite ver (roles, markings). Dos usuarios pueden abrir la misma app y ver listas distintas — eso es lo esperado.

---

## 11. Consumo: AIP/LLMs (grounding + Actions)

> Detalle completo en [`10-aip-llms-ontologia.md`](10-aip-llms-ontologia.md).

Sobre la misma Ontología se puede montar un asistente AIP: *"¿Qué pedidos llevan más de 7 días pendientes y de qué clientes son?"*

Cómo funciona bien (y con seguridad):

1. **Grounding:** el LLM no responde "de memoria"; primero recupera objetos reales (Object Sets de `Order`/`Customer`) y responde **citando esos datos**.
2. **Permisos:** la recuperación pasa por OSS/Gatekeeper → el LLM solo ve lo que el **usuario que pregunta** puede ver.
3. **Tools/Actions:** si el asistente puede actuar ("aprueba el pedido 123"), lo hace ejecutando la **misma Action** que usaría un humano, con sus mismas validaciones.
4. **Human-in-the-loop:** para write-backs, pedir confirmación humana antes de ejecutar.

> **Anti-patrón:** darle al LLM un service account con más permisos que el usuario. Rompe todo el modelo de gobernanza.

---

## 12. Write-back: Actions y datasets de escritura

La Action **"Aprobar pedido"**:

| Elemento | Valor |
|---|---|
| Objeto afectado | `Order` |
| Cambio | `status: PENDING → APPROVED`, set `approved_by`, `approved_at` |
| Validaciones | el pedido está en `PENDING`; el usuario tiene rol `ops-approver`; `total_amount` < límite del rol |
| Auditoría | quién, cuándo, valor anterior y nuevo |

Qué pasa al pulsar el botón:

```
Usuario pulsa [Aprobar]
      │
      ▼
Action valida (reglas + permisos vía Gatekeeper)
      │ ok
      ▼
Phonograph actualiza el objeto  ──▶  la app lo refleja al instante
      │
      ▼
Writeback dataset registra el cambio (fila auditada)
      │
      ▼
(opcional) pipelines consumen el writeback dataset
           → sincronizar de vuelta al ERP, métricas de aprobación, etc.
```

> **Cierre del ciclo:** el writeback dataset es un dataset más, con linaje. Las decisiones humanas se convierten en datos analizables — esta es la diferencia entre Foundry y un stack de BI clásico.

---

## 13. On‑prem (OpenShift/Rubix): red, TLS, proxies y air‑gapped

> Detalle completo en [`09-apollo-infraestructura.md`](09-apollo-infraestructura.md).

Cuando todo esto corre on-prem, los fallos "de plataforma" suelen estar aquí:

| Tema | Qué revisar |
|---|---|
| **Red / egress** | El Agent y los servicios necesitan salida 443. Con proxy corporativo: configurar proxy + allowlist de dominios de Foundry/Apollo. |
| **TLS / CA** | Si el proxy hace inspección SSL (MITM), la CA corporativa debe estar en el truststore del Agent y de los servicios. Síntoma clásico: `SSL handshake failed`. |
| **Registry de imágenes** | En air-gapped, las imágenes se sirven desde un registry interno (Harbor/Nexus). Síntoma clásico: `ImagePullBackOff`. |
| **Capacidad** | Pods `Pending` = faltan recursos/quotas. Los workloads de Spark son a ráfagas: dimensionar para el pico, no la media. |
| **Co-location** | No colocar varios nodos de un mismo servicio intensivo en I/O en el mismo host físico — ver el [post-mortem real de este repo](../../post-mortem-doc1.md). |

---

## 14. Observabilidad y troubleshooting

Pregunta guía: **¿en qué etapa de las 5 se rompió?** Recorrer el flujo de izquierda a derecha:

| # | Pregunta | Si falla, el problema es… |
|---|---|---|
| 1 | ¿Hay datos nuevos en Bronze? | Ingesta (Agent/Magritte) |
| 2 | ¿Silver/Gold se reconstruyeron sin errores? | Pipelines (Build/Spark/calidad) |
| 3 | ¿Los objetos reflejan el Gold actual? | Indexing (Funnel/Phonograph/ES8) |
| 4 | ¿La app muestra lo que OSS devuelve? | App (filtros, Object Sets, permisos) |
| 5 | ¿Las Actions escriben y queda registro? | Write-back (validaciones, permisos) |

Y la segunda pregunta clave: **¿falla para todos o solo para algunos usuarios?** Si es "solo algunos", casi siempre son **permisos o markings**, no datos.

> Runbook completo con diagnóstico/fix/prevención por síntoma: [`11-errores-comunes-y-troubleshooting.md`](11-errores-comunes-y-troubleshooting.md).

---

## 15. Checklist end-to-end (antes de producción)

### Ingesta
- [ ] Cuenta de servicio de solo lectura en la fuente; credenciales solo en Foundry
- [ ] Sync incremental con columna fiable (`updated_at`) e índice en la fuente
- [ ] Alerta configurada si el Agent se desconecta o la sync falla

### Pipelines
- [ ] PK estable y dedup explícita en Silver
- [ ] Watermark + lookback definidos y documentados
- [ ] Checks de calidad que rompen el build (PK, enums, rangos, freshness)
- [ ] Particionado por fecha en datasets grandes

### Ontología
- [ ] Backing datasets son Gold; PKs nunca cambian entre ejecuciones
- [ ] Solo las propiedades necesarias marcadas como searchables
- [ ] Latencia de indexing conocida y aceptada por el negocio

### App y write-back
- [ ] La app probada con un usuario de cada rol (no solo con el admin que la construyó)
- [ ] Actions con validaciones y mensajes de error claros
- [ ] Writeback dataset con owner y consumidores identificados

### Plataforma (on-prem)
- [ ] Egress/proxy/CA verificados desde los hosts reales
- [ ] Capacidad para el pico de Spark, no la media
- [ ] Dueño claro de la monitorización de plataforma (ver [`foundry_guide.md`](../../foundry_guide.md))

---

## 16. Referencias internas del repo

| Documento | Qué amplía |
|---|---|
| [`01-palantir-foundry-componentes.md`](01-palantir-foundry-componentes.md) | Mapa de todos los componentes citados aquí |
| [`02-glosario-foundry.md`](02-glosario-foundry.md) | Definiciones cortas de todos los términos |
| [`03-data-integration-magritte.md`](03-data-integration-magritte.md) | Etapa 1: ingesta |
| [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md) | Etapa 2: pipelines |
| [`06-ontologia-foundry.md`](06-ontologia-foundry.md) | Etapas 3 y 5: Ontología y Actions |
| [`07-workshop-apps-operativas.md`](07-workshop-apps-operativas.md) | Etapa 4: apps Workshop |
| [`08-seguridad-y-gobernanza.md`](08-seguridad-y-gobernanza.md) | Permisos y markings en todas las etapas |
| [`09-apollo-infraestructura.md`](09-apollo-infraestructura.md) | Plataforma on-prem |
| [`10-aip-llms-ontologia.md`](10-aip-llms-ontologia.md) | Etapa 4 con LLMs |
| [`11-errores-comunes-y-troubleshooting.md`](11-errores-comunes-y-troubleshooting.md) | Runbook de diagnóstico |
