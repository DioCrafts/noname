# Streaming y Tiempo Real en Palantir Foundry — Apuntes

> Cómo manejar datos en (casi) tiempo real: **streaming datasets**, ingesta desde **Kafka**, micro-batching, ventanas y deduplicación, llegada a la Ontología con baja latencia, y — sobre todo — **cuándo NO usar streaming**.
>
> **Para quién:** data engineers que evalúen o mantengan flujos en tiempo real, y quien deba responder a "¿por qué esto no puede ser instantáneo?".
>
> Última actualización: 2026-06-12

---

## Índice

1. [Primero: ¿de verdad necesitas streaming?](#1-primero-de-verdad-necesitas-streaming)
2. [Conceptos: streaming dataset, micro-batch y latencia](#2-conceptos-streaming-dataset-micro-batch-y-latencia)
3. [Ingesta: Kafka y fuentes de eventos vía Magritte](#3-ingesta-kafka-y-fuentes-de-eventos-vía-magritte)
4. [Arquitectura típica: stream + batch conviviendo](#4-arquitectura-típica-stream--batch-conviviendo)
5. [Procesamiento: ventanas, orden y deduplicación](#5-procesamiento-ventanas-orden-y-deduplicación)
6. [El small files problem (y cómo evitarlo)](#6-el-small-files-problem-y-cómo-evitarlo)
7. [Streaming hacia la Ontología](#7-streaming-hacia-la-ontología)
8. [Presupuesto de latencia end-to-end](#8-presupuesto-de-latencia-end-to-end)
9. [Monitorización de flujos en tiempo real](#9-monitorización-de-flujos-en-tiempo-real)
10. [Errores comunes y troubleshooting](#10-errores-comunes-y-troubleshooting)
11. [Checklist antes de poner streaming en producción](#11-checklist-antes-de-poner-streaming-en-producción)
12. [Glosario rápido](#12-glosario-rápido)

---

## 1. Primero: ¿de verdad necesitas streaming?

El streaming es **caro de operar**: más piezas, más modos de fallo, más vigilancia. Antes de pedirlo, pregunta al negocio qué decisión cambia con la latencia:

| El usuario necesita… | Solución adecuada |
|---|---|
| Datos del día anterior | Batch diario (lo normal) |
| Datos de hace ~15 min | **Incremental frecuente** (doc [03](03-data-integration-magritte.md)/[04](04-pipelines-y-transformaciones.md)) — sin streaming |
| Datos de hace ~1 min | Streaming con micro-batch |
| Reaccionar en segundos (alarmas, telemetría) | Streaming real + Automations |

> **Regla práctica:** "quiero verlo en tiempo real" casi siempre significa "no quiero esperar a mañana". Un incremental cada 5–15 minutos resuelve la mayoría de los casos por una fracción del coste. Reserva el streaming para cuando **una decisión automática o humana ocurre en segundos/minutos**.

---

## 2. Conceptos: streaming dataset, micro-batch y latencia

| Concepto | Qué es |
|---|---|
| **Streaming dataset** | Dataset de Foundry que recibe **appends continuos** de eventos (no se reescribe completo) |
| **Micro-batch** | Los eventos se acumulan N segundos y se escriben en bloque: "casi tiempo real" con la mecánica de batch |
| **Evento** | Registro individual con timestamp: una transacción, una lectura de sensor, un cambio de estado |
| **Event time vs processing time** | Cuándo ocurrió el evento vs cuándo lo procesamos — pueden diferir (red, reintentos) |
| **Backpressure** | Los eventos llegan más rápido de lo que se procesan: la cola crece |

```
Batch clásico:      ████________████________████      (cada N horas)
Incremental:        ██__██__██__██__██__██__██__      (cada N minutos)
Micro-batch stream: █_█_█_█_█_█_█_█_█_█_█_█_█_█_      (cada N segundos)
Streaming puro:     ▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏▏      (evento a evento)
```

---

## 3. Ingesta: Kafka y fuentes de eventos vía Magritte

La ingesta de streams entra por **Magritte** ([doc 03](03-data-integration-magritte.md)), igual que el batch, pero con el conector de streaming:

```
Kafka (topic: orders-events)
      │  el Agent actúa como consumer del topic
      ▼
Agent (consumer group propio de Foundry)
      │  micro-batch cada N segundos · TLS 443 saliente
      ▼
Magritte ──▶ streaming dataset (append continuo)
```

Puntos de configuración que importan:

| Punto | Detalle |
|---|---|
| **Consumer group** | Foundry mantiene su offset en el topic: si la sync se para, al volver retoma donde quedó |
| **Offset inicial** | ¿Empezar por lo más antiguo (`earliest`) o solo lo nuevo (`latest`)? Decisión explícita en la primera activación |
| **Esquema de eventos** | JSON/Avro: fijar el contrato; el schema drift en streaming duele más que en batch |
| **Retención del topic** | Si Foundry se desconecta más tiempo que la retención de Kafka, **se pierden eventos** — alarma obligatoria |
| **Throughput** | Dimensionar el Agent para el pico de eventos, no la media |

---

## 4. Arquitectura típica: stream + batch conviviendo

Lo habitual no es "todo streaming", sino un flujo caliente sobre una base batch:

```
                      CAMINO CALIENTE (segundos–minutos)
Kafka ──▶ streaming dataset ──▶ transform ligero ──▶ Ontología (eventos/estado actual)
                 │                                        ▲
                 │ compactación periódica                 │ backing datasets
                 ▼                                        │
            CAMINO FRÍO (batch, horas)                    │
            Bronze ──▶ Silver ──▶ Gold ──────────────────┘
            (histórico completo, calidad, agregados)
```

- El **camino caliente** responde "¿qué está pasando ahora?": último estado, eventos recientes.
- El **camino frío** responde todo lo demás: histórico, métricas, joins pesados, calidad estricta.
- La **compactación** vuelca periódicamente el stream al camino frío y mantiene el dataset caliente pequeño.

> **Anti-patrón:** intentar que el camino caliente lo haga todo (joins complejos, dedup exhaustiva, histórico). El stream debe ser **fino**: cuanto menos haga, menos falla.

---

## 5. Procesamiento: ventanas, orden y deduplicación

Tres realidades incómodas de los eventos:

1. **Llegan tarde** (red, reintentos del productor) → procesar por *event time* con una ventana de tolerancia (ej.: aceptar eventos hasta 10 min tarde).
2. **Llegan desordenados** → no asumir que el último recibido es el último ocurrido: ordenar por `event_time` dentro de la ventana.
3. **Llegan repetidos** (reintentos = entrega *at-least-once*) → deduplicar por **ID de evento** dentro de la ventana.

```
Patrón estándar por ventana (ej. 5 minutos):
- agrupar eventos por clave (order_id)
- deduplicar por event_id
- quedarse con el estado de event_time más reciente
- emitir/escribir el resultado
```

Esto es el equivalente streaming del patrón watermark + lookback + dedup del batch ([doc 04](04-pipelines-y-transformaciones.md), secciones 6–7): mismos principios, ventanas más cortas.

---

## 6. El small files problem (y cómo evitarlo)

El fallo operativo **número 1** del streaming en plataformas tipo lake:

```
Escribir cada 5 segundos = ~17 000 ficheros/día por dataset
        │
        ▼
lecturas lentas (abrir miles de ficheros) · metadata hinchada · builds downstream que se arrastran
```

Mitigaciones:

| Medida | Efecto |
|---|---|
| Micro-batches más largos (30–60 s si la latencia lo tolera) | Menos ficheros, más grandes |
| **Compactación programada** (job batch que reescribe el stream en ficheros grandes) | Mantiene sano el dataset |
| Retención corta en el dataset caliente (lo viejo vive en el camino frío) | Dataset caliente pequeño y rápido |
| Particionado por fecha/hora razonable | Evita multiplicar carpetas |

> Si las lecturas del streaming dataset se degradan semana a semana, la causa casi segura es compactación ausente o rota.

---

## 7. Streaming hacia la Ontología

Para que el "tiempo real" llegue al usuario, los objetos deben actualizarse rápido:

```
streaming dataset ──▶ backing dataset (camino caliente) ──▶ Funnel ──▶ Phonograph/ES8 ──▶ app
```

Consideraciones:

- **Funnel marca el ritmo**: la frecuencia de indexing acota la frescura en la app. De nada sirve ingestar cada 5 s si se indexa cada 10 min — mide la cadena completa (sección 8).
- Modela **eventos** y **estado** como cosas distintas: un Object Type `OrderEvent` (inmutable, append) y el `Order` (estado actual, se actualiza). Las apps operativas casi siempre quieren el estado; los eventos son para auditoría y análisis.
- Las **Automations** (reglas que disparan notificaciones o Actions al cambiar objetos) son el complemento natural: streaming sin nadie mirando es solo coste. Ejemplo real en la [guía del dashboard](../../guia-dashboard-monitorizacion.md), Fase 6.

---

## 8. Presupuesto de latencia end-to-end

La pregunta "¿cuánto tarda en verse?" se responde **sumando etapas**:

| Etapa | Latencia típica |
|---|---|
| Productor → Kafka | < 1 s |
| Kafka → streaming dataset (micro-batch del Agent) | 5–60 s |
| Transform ligero del camino caliente | segundos–minutos |
| Funnel → Phonograph/ES8 (indexing) | segundos–minutos |
| App (refresco del widget) | segundos |
| **Total realista** | **~1–5 minutos** |

> Comunica este número al negocio **antes** de construir. "Tiempo real" en una plataforma gobernada significa minutos, no milisegundos; si el caso exige < 1 s (trading, control industrial), Foundry no es la capa de reacción — es la capa de análisis y decisión.

---

## 9. Monitorización de flujos en tiempo real

Un flujo streaming sin monitorizar **fallará en silencio**: los datos simplemente dejarán de ser frescos.

| Métrica | Alarma cuando… |
|---|---|
| **Freshness** del dataset caliente (ahora − último evento) | supera el SLA (ej.: > 5 min) |
| **Consumer lag** (eventos pendientes en Kafka) | crece de forma sostenida (backpressure) |
| Estado del Agent / sync | desconexión o errores repetidos |
| Latencia de indexing (Funnel) | cola creciente |
| Nº de ficheros del dataset | crece sin que la compactación lo reduzca |

La freshness es la métrica reina: cubre todo el camino de un vistazo. El dashboard de la [guía de monitorización](../../guia-dashboard-monitorizacion.md) incluye una página específica de Streams & Kafka.

---

## 10. Errores comunes y troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| Los datos dejaron de avanzar (freshness creciendo) | Agent caído, sync parada, o productor que dejó de emitir | Revisar Agent/sync; confirmar con el equipo productor que el topic recibe eventos |
| Lag de Kafka creciendo sin parar | Backpressure: el consumo no da abasto | Aumentar paralelismo/recursos del consumer; revisar transform caliente demasiado pesado |
| Huecos de datos tras una caída | Desconexión más larga que la retención del topic | Re-ingestar desde la fuente si es posible; subir retención; alarma de desconexión |
| Duplicados en la app | Entrega at-least-once sin dedup por event_id | Añadir dedup por ventana (sección 5) |
| Lecturas cada vez más lentas | Small files problem | Compactación programada; micro-batch más largo |
| "Ingestamos cada 5 s pero la app va 10 min atrás" | El cuello es el indexing (Funnel), no la ingesta | Medir el presupuesto de latencia por etapa (sección 8) |
| Eventos con orden imposible (updates antes que creates) | Procesando por processing time | Ordenar por event time dentro de la ventana |

---

## 11. Checklist antes de poner streaming en producción

- [ ] Justificación real de latencia (¿qué decisión cambia? ¿bastaría incremental de 15 min?)
- [ ] Contrato de esquema de eventos acordado con el productor (con `event_id` y `event_time`)
- [ ] Offset inicial decidido y retención del topic ≥ peor ventana de desconexión asumible
- [ ] Dedup por `event_id` y manejo de eventos tardíos/desordenados
- [ ] Camino frío definido (histórico/calidad) + compactación programada
- [ ] Presupuesto de latencia medido y comunicado al negocio
- [ ] Alarmas: freshness, consumer lag, Agent, indexing y nº de ficheros
- [ ] Plan de re-ingesta documentado para huecos de datos

---

## 12. Glosario rápido

| Término | Definición |
|---|---|
| **Streaming dataset** | Dataset que recibe appends continuos de eventos |
| **Micro-batch** | Acumular eventos N segundos y escribirlos en bloque |
| **Event time / processing time** | Cuándo ocurrió el evento vs cuándo lo procesamos |
| **Consumer group / offset** | Posición de lectura de Foundry en un topic de Kafka |
| **Consumer lag** | Eventos pendientes de consumir (síntoma de backpressure) |
| **Backpressure** | Los eventos llegan más rápido de lo que se procesan |
| **Ventana (window)** | Intervalo de tiempo en el que se agrupa/deduplica |
| **Compactación** | Reescritura periódica de muchos ficheros pequeños en pocos grandes |
| **Small files problem** | Degradación por exceso de ficheros pequeños |
| **Freshness** | Edad del dato más reciente; métrica reina del streaming |
| **Camino caliente / frío** | Flujo de baja latencia (estado actual) vs batch (histórico y calidad) |

---

## Referencias

- [Palantir Foundry Documentation — Streaming](https://www.palantir.com/docs/foundry/data-integration/streams/)
- Ver también: [`03-data-integration-magritte.md`](03-data-integration-magritte.md) — ingesta y conector Kafka
- Ver también: [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md) — watermarks, dedup y small files en batch
- Ver también: [`06-ontologia-foundry.md`](06-ontologia-foundry.md) — indexing hacia objetos
- Página de Streams & Kafka del dashboard: [guía de monitorización](../../guia-dashboard-monitorizacion.md)
