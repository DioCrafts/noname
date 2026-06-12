# Pipelines y Transformaciones en Palantir Foundry — Apuntes

> Cómo se diseñan y operan pipelines en Foundry: **Pipeline Builder**, **Code Repositories** y **Code Workbooks**; ejecución (Build), incrementales, calidad, rendimiento (Spark) y cómo esto alimenta la Ontología.
>
> **Para quién:** data engineers y cualquiera que escriba o revise transformaciones. Responde a "¿cómo paso de datos crudos a datos confiables sin que el coste y los duplicados se disparen?".
>
> Última actualización: 2026-04-08

---

## Índice

1. [Qué es un pipeline en Foundry](#1-qué-es-un-pipeline-en-foundry)
2. [Herramientas: Pipeline Builder vs Code Repos vs Code Workbooks](#2-herramientas-pipeline-builder-vs-code-repos-vs-code-workbooks)
3. [Modelo mental: DAG, dependencias y Build](#3-modelo-mental-dag-dependencias-y-build)
4. [Bronze / Silver / Gold](#4-bronze--silver--gold)
5. [Ejecución: Full vs Incremental](#5-ejecución-full-vs-incremental)
6. [Watermarks, lookback y late-arriving data](#6-watermarks-lookback-y-late-arriving-data)
7. [Idempotencia, deduplicación y claves](#7-idempotencia-deduplicación-y-claves)
8. [Particionado, formatos y layout](#8-particionado-formatos-y-layout)
9. [Calidad de datos: checks recomendados](#9-calidad-de-datos-checks-recomendados)
10. [Rendimiento en Spark (práctico)](#10-rendimiento-en-spark-práctico)
11. [Observabilidad y troubleshooting](#11-observabilidad-y-troubleshooting)
12. [Integración con Ontología: backing datasets → Funnel → objetos](#12-integración-con-ontología-backing-datasets--funnel--objetos)
13. [Ejemplo end-to-end: bronze → silver → gold → ontología](#13-ejemplo-end-to-end-bronze--silver--gold--ontología)
14. [Checklist de diseño de pipelines](#14-checklist-de-diseño-de-pipelines)

---

## 1. Qué es un pipeline en Foundry

Un **pipeline** en Foundry es una secuencia de **transformaciones** que:
- toma inputs (datasets “upstream”),
- aplica lógica (Spark / SQL / Python / Java),
- produce outputs (datasets “downstream”),
- se ejecuta bajo un **scheduler/orquestador (Build)** con un grafo de dependencias.

**Objetivo práctico:** pasar de datos crudos (raw) a datos confiables y reutilizables (curated), listos para BI, apps y Ontología.

---

## 2. Herramientas: Pipeline Builder vs Code Repos vs Code Workbooks

| Herramienta | Cuándo usar | Pros | Contras |
|---|---|---|---|
| **Pipeline Builder** | Pipelines estándar, ETL/ELT, joins, agregaciones, filtros, lógica declarativa | Rápido, visual, gobernado, fácil de mantener | Se queda corto si necesitas lógica compleja o librerías |
| **Code Repositories** | Transformaciones “de verdad” (proyecto software): librerías, tests, CI, refactors | Versionado Git, revisiones, modularidad | Curva de entrada; requiere disciplina de ingeniería |
| **Code Workbooks** | Exploración, prototipado, análisis ad hoc, validación rápida | Iteración rápida, interactivo | Riesgo de “código suelto”; si escala, hay que formalizar en repos/pipeline |

**Regla de oro:** explora en Workbooks, productiviza en Repos/Pipeline Builder.

> Pipeline Builder en profundidad (grafo visual, preview, incrementales, migración a código): [`15-pipeline-builder.md`](15-pipeline-builder.md).

---

## 3. Modelo mental: DAG, dependencias y Build

En Foundry, el pipeline real es un **DAG** (Directed Acyclic Graph):

```
          (bronze)                (silver)                   (gold)
     raw_orders_ingest  ──▶  orders_clean  ──▶  orders_fact
            │                          │              │
            └──────────────▶  customers_clean  ───────┘
```

**Build** (scheduler/orquestador) se encarga de:
- resolver dependencias,
- ejecutar solo lo necesario,
- gestionar reintentos/fallos,
- materializar outputs como datasets.

---

## 4. Bronze / Silver / Gold

### Bronze (raw)
- “lo que viene del source”
- mínima transformación
- conservar columnas originales (para trazabilidad)

### Silver (clean)
- normalización de tipos
- deduplicación
- estandarización de timezone, enums, nullability
- quality checks

### Gold (curated)
- modelo de negocio (fact/dim, entidades “listo para consumo”)
- joins definitivos
- KPIs y agregados
- datasets que alimentan Ontología o productos finales

---

## 5. Ejecución: Full vs Incremental

### Full refresh
Reprocesa todo.
- útil para tablas pequeñas o cambios de lógica que afectan a todo
- caro si la tabla crece

### Incremental
Procesa solo “lo nuevo/cambiado”.
- requiere una **estrategia de cambio** (timestamp, partición, CDC, versión)
- necesita deduplicación si hay re-ingestas / correcciones

---

## 6. Watermarks, lookback y late-arriving data

**Watermark:** marca que indica hasta dónde procesaste.

**Lookback window:** re-procesar un intervalo anterior para capturar eventos tardíos.

Ejemplo conceptual:

```
Procesamiento diario:
- watermark = max(updated_at) procesado
- cada día procesas updated_at > watermark - lookback(2 días)
- deduplicas por PK + updated_at más reciente
```

**Por qué es crítico:** en sistemas reales, llegan registros tarde, con correcciones o reintentos.

---

## 7. Idempotencia, deduplicación y claves

Un pipeline “sano” debe ser **idempotente**:
- si se ejecuta 2 veces, el resultado debe ser consistente.

Recomendaciones:
- define una **PK estable** (natural o surrogate)
- usa `updated_at`/`version` para elegir el “último” registro
- dedup explícita en Silver

**Patrón típico de dedup (conceptual):**
- particionar por PK
- ordenar por updated_at desc
- quedarte con row_number = 1

---

## 8. Particionado, formatos y layout

- **Formato recomendado:** Parquet (columnares)
- **Particionado por fecha** (`event_date`, `ingest_date`) mejora:
  - performance
  - incrementales
  - costes (leer menos)

Errores comunes:
- particionar por una columna con cardinalidad enorme (miles/millones de particiones)
- no controlar el “small files problem”

---

## 9. Calidad de datos: checks recomendados

Checks típicos en Silver/Gold:

| Check | Motivo |
|---|---|
| Not null en PK | evita duplicados/huérfanos |
| Uniqueness en PK | garantiza entidad |
| Rango válido (fechas, importes) | detecta corrupciones |
| Dominio de enums (estado ∈ {A,B,C}) | consistencia |
| Reglas de negocio (importe >= 0) | integridad |
| Freshness (dataset actualizado hoy) | SLAs |

**Consejo:** los checks deben fallar “rápido” y con mensajes claros.

---

## 10. Rendimiento en Spark (práctico)

### Joins
- evita joins gigantes sin keys bien distribuidas
- si hay skew (una key con millones de filas), considera:
  - salting
  - pre-aggregations
  - estrategias de join alternativas

### Particiones
- controla número de particiones (ni 1, ni 100k)
- revisa repartition/coalesce

### Caching
- cachea solo si se reutiliza varias veces en el job
- cachear por defecto suele empeorar memoria

### Coste
- pipelines innecesarios o demasiado frecuentes = gasto
- preferir incrementales cuando aplica

---

## 11. Observabilidad y troubleshooting

Síntomas → causas típicas:

| Síntoma | Causa probable | Qué mirar |
|---|---|---|
| Job OOM | skew, shuffle enorme, cache mal | tamaños intermedios, particiones, joins |
| Muy lento | lectura excesiva, no particionado | scans completos, filtros |
| Output vacío | filtro mal, watermark mal | lógica incremental |
| Duplicados | idempotencia rota | dedup/PK, lookback |
| Permisos | acceso a input/output | gobernanza y ownership |

---

## 12. Integración con Ontología: backing datasets → Funnel → objetos

Pipelines producen datasets **Gold** que típicamente se usan como:
- **backing dataset** de un Object Type (ver `06-ontologia-foundry.md`)

Luego ocurre:

```
Gold dataset actualizado
        │
        ▼
Funnel indexa
  ├─▶ Phonograph (objetos materializados)
  └─▶ ES8 (búsqueda)
        │
        ▼
Workshop / AIP / Object Explorer ven los cambios
```

---

## 13. Ejemplo end-to-end: bronze → silver → gold → ontología

### 13.1 Bronze: ingesta (raw)
- `raw_customers`
- `raw_orders`

### 13.2 Silver: limpieza
**customers_clean**
- parseo de fechas
- normalización de emails
- dedup por `customer_id`

**orders_clean**
- cast de importes
- eliminación de registros corruptos
- dedup por `order_id`

### 13.3 Gold: modelo de negocio
**orders_fact**
- join orders_clean + customers_clean (para claves y atributos)
- métricas derivadas (ej: total, taxes, etc.)

**customers_agg**
- agregados por customer_id: total_orders, total_spent, last_order_at

### 13.4 Ontología
- Object Type `Customer` backing dataset: `customers_clean` o `customers_agg`
- Object Type `Order` backing dataset: `orders_fact`
- Link: Customer (1:N) Orders por `customer_id`

---

## 14. Checklist de diseño de pipelines

- [ ] Definir objetivo: ¿bronze/silver/gold?
- [ ] Definir PK estable + estrategia de dedup
- [ ] Decidir full vs incremental (y watermark/lookback)
- [ ] Particionado razonable (fecha/evento)
- [ ] Checks de calidad mínimos (PK not null/unique, ranges, freshness)
- [ ] Observabilidad: logs, métricas, alertas
- [ ] Optimización Spark: joins, skew, particiones, caching
- [ ] Si alimenta Ontología: asegurar schema “contract” y claves consistentes

---

## Referencias

- Ver también: [`01-palantir-foundry-componentes.md`](01-palantir-foundry-componentes.md)
- Ver también: [`06-ontologia-foundry.md`](06-ontologia-foundry.md)
- Ver también: [`03-data-integration-magritte.md`](03-data-integration-magritte.md)
