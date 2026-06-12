# Pipeline Builder en Palantir Foundry — Apuntes

> Cómo construir pipelines **visuales, sin código** con Pipeline Builder: anatomía de un pipeline, catálogo de transformaciones, incrementales, despliegue y builds, cuándo es la herramienta correcta y cuándo (y cómo) migrar a Code Repositories.
>
> **Para quién:** quien vaya a construir o mantener pipelines sin escribir código (o decidir si le basta con eso), y data engineers que revisen pipelines hechos por otros. Complementa al [doc 04](04-pipelines-y-transformaciones.md), que cubre los conceptos comunes a todos los pipelines.
>
> Última actualización: 2026-06-12

---

## Índice

1. [Qué es Pipeline Builder](#1-qué-es-pipeline-builder)
2. [Cuándo usarlo (y cuándo no)](#2-cuándo-usarlo-y-cuándo-no)
3. [Anatomía de un pipeline visual](#3-anatomía-de-un-pipeline-visual)
4. [Catálogo de transformaciones](#4-catálogo-de-transformaciones)
5. [Preview: ver los datos en cada paso](#5-preview-ver-los-datos-en-cada-paso)
6. [Esquemas: la ventaja silenciosa](#6-esquemas-la-ventaja-silenciosa)
7. [Incrementales en Pipeline Builder](#7-incrementales-en-pipeline-builder)
8. [Despliegue, builds y schedules](#8-despliegue-builds-y-schedules)
9. [Cambios seguros: ramas y propuestas](#9-cambios-seguros-ramas-y-propuestas)
10. [Señales de que te quedaste pequeño (y cómo migrar)](#10-señales-de-que-te-quedaste-pequeño-y-cómo-migrar)
11. [Errores comunes y troubleshooting](#11-errores-comunes-y-troubleshooting)
12. [Checklist antes de desplegar a producción](#12-checklist-antes-de-desplegar-a-producción)
13. [Glosario rápido](#13-glosario-rápido)

---

## 1. Qué es Pipeline Builder

**Pipeline Builder** es la herramienta visual de Foundry para construir pipelines de datos sin escribir código: defines un grafo de transformaciones con la interfaz, y Foundry lo compila y ejecuta como un pipeline normal (Spark + Build, con linaje, permisos y versionado).

```
        Lo que tú ves                      Lo que ejecuta Foundry
┌────────────────────────────┐       ┌──────────────────────────────┐
│  [raw_orders]              │       │                              │
│      │                     │       │  Pipeline Spark compilado    │
│   (clean: casts, dedup)    │ ────▶ │  + Build (schedule, DAG)     │
│      │                     │       │  + linaje y permisos         │
│   (join customers)         │       │  + datasets versionados      │
│      │                     │       │                              │
│  [orders_fact]             │       │                              │
└────────────────────────────┘       └──────────────────────────────┘
```

**Idea clave:** un pipeline de Pipeline Builder es un pipeline de primera clase, no un juguete. Produce los mismos datasets, aparece en el mismo linaje y se orquesta con el mismo Build que un pipeline de Code Repositories. Lo que cambia es **cómo se define** (visual vs código) y **qué tan lejos puede llegar la lógica**.

---

## 2. Cuándo usarlo (y cuándo no)

Ampliación de la tabla del [doc 04, sección 2](04-pipelines-y-transformaciones.md):

| Situación | ¿Pipeline Builder? |
|---|---|
| ETL estándar: casts, filtros, joins, agregaciones, unions | ✅ Sí — es su terreno |
| El equipo que lo mantendrá no programa | ✅ Sí — esa es su razón de ser |
| Limpieza y modelado Bronze → Silver → Gold típicos | ✅ Sí |
| Lógica con muchas reglas de negocio anidadas | ⚠️ Posible, pero evalúa código: 40 nodos visuales son más ilegibles que 40 líneas |
| Necesitas librerías (ML, parsing exótico, APIs) | ❌ Code Repositories |
| Necesitas tests unitarios de la lógica | ❌ Code Repositories |
| UDFs / algoritmos a medida | ❌ Code Repositories |

**Regla práctica:** elige la herramienta según **quién lo mantendrá**, no según quién lo construye hoy. Un pipeline visual que solo entiende la persona que se va de vacaciones es deuda; uno en código que el equipo de negocio no puede tocar, también.

---

## 3. Anatomía de un pipeline visual

| Pieza | Qué es | Ejemplo |
|---|---|---|
| **Input** | Dataset de entrada (de Magritte u otro pipeline) | `raw_orders` |
| **Transform / nodo** | Paso de transformación encadenable | "filtrar status válidos" |
| **Path** | Cadena de nodos desde un input hasta un output | raw → clean → join → fact |
| **Output** | Dataset que el pipeline materializa | `orders_fact` |
| **Deploy** | Publicar la definición para que Build la ejecute | versión desplegada |

Un pipeline típico Bronze → Silver → Gold del [caso Pedidos/Clientes](05-flujo-datos-end-to-end.md):

```
[raw_orders]──(cast tipos)──(dedup por order_id)──────────────┐
                                                              ├──(join por customer_id)──(métricas)──▶ [orders_fact]
[raw_customers]──(cast)──(normalizar email)──(dedup)──▶ [customers_clean]
```

> **Consejo de legibilidad:** nombra cada nodo por su **intención** ("eliminar pedidos de prueba"), no por su mecánica ("filter 3"). El grafo es la documentación; aprovéchalo.

---

## 4. Catálogo de transformaciones

Las operaciones disponibles cubren el 90% del ETL habitual:

| Categoría | Transformaciones | Equivalente |
|---|---|---|
| **Limpieza** | cast de tipos, renombrar columnas, valores por defecto, trim/lowercase | `SELECT CAST(...)` |
| **Filtrado** | filtros por condición, eliminación de nulos/duplicados | `WHERE`, `DISTINCT` |
| **Columnas derivadas** | expresiones (aritmética, fechas, strings, condicionales) | `CASE WHEN`, funciones |
| **Combinación** | joins (inner/left/right/full), unions | `JOIN`, `UNION` |
| **Agregación** | group by + count/sum/avg/min/max, ventanas | `GROUP BY`, window functions |
| **Reestructura** | pivot/unpivot, explode de arrays | — |

Notas prácticas:

- Las **expresiones** tienen un mini-lenguaje de fórmulas (tipo hoja de cálculo). Si una expresión ocupa media pantalla, es señal de que esa lógica quiere vivir en código.
- La **deduplicación por clave + más reciente** (el patrón de Silver del [doc 04, sección 7](04-pipelines-y-transformaciones.md)) se hace con agrupación/ventana: déjala como un nodo propio y visible, no escondida dentro de otro paso.

---

## 5. Preview: ver los datos en cada paso

La función más valiosa de Pipeline Builder: seleccionar cualquier nodo y **ver una muestra del resultado en ese punto**, antes de desplegar nada.

Úsalo sistemáticamente:

1. Tras cada join: ¿se disparó el número de filas? (join con duplicados) ¿se vació? (claves que no cruzan).
2. Tras cada filtro: ¿cuántas filas cayeron? ¿son las esperadas?
3. Sobre el output final: ¿el esquema y una muestra tienen sentido?

> El preview trabaja sobre una **muestra**, no el dataset completo: es perfecto para validar lógica, pero no sustituye los checks de calidad sobre el build real (sección 8).

---

## 6. Esquemas: la ventaja silenciosa

Pipeline Builder conoce el esquema en **cada punto del grafo** y lo propaga automáticamente:

- Si un input cambia de esquema (schema drift), los nodos afectados se marcan en error **al editar**, no en producción a las 3 AM.
- Renombrar una columna actualiza las referencias aguas abajo dentro del pipeline.
- El output declara un esquema explícito: es tu **contrato** con los consumidores (Ontología, otros pipelines — ver [doc 05, sección 7](05-flujo-datos-end-to-end.md)).

> Esta validación temprana es la gran ventaja frente a un script SQL suelto: la mitad de los errores de pipeline clásicos (columna renombrada, tipo cambiado) se ven en el editor antes de romper nada.

---

## 7. Incrementales en Pipeline Builder

Los conceptos del [doc 04, secciones 5–7](04-pipelines-y-transformaciones.md) (full vs incremental, watermarks, idempotencia) aplican igual; Pipeline Builder permite configurar el output como **incremental** para procesar solo lo nuevo.

Lo que hay que verificar al activarlo:

- [ ] El input se actualiza de forma **append** o con marcador fiable (si el origen reescribe todo, el incremental no tiene de dónde agarrar).
- [ ] Todas las transformaciones del path son compatibles con ejecución incremental — las **agregaciones globales** y algunos joins requieren ver el histórico completo y fuerzan recomputación.
- [ ] La deduplicación sigue garantizando idempotencia aunque lleguen reprocesos.

> **Síntoma clásico:** activaste incremental y el output acumula duplicados o pierde correcciones tardías. No es un bug de la herramienta: falta el patrón dedup/lookback, igual que en código.

---

## 8. Despliegue, builds y schedules

El ciclo de vida:

```
Editar (borrador) ──▶ Preview ──▶ Deploy (publicar versión) ──▶ Build (Spark ejecuta)
                                                                    │
                                              schedule / trigger ◀──┘
```

- **Editar no afecta a producción**: hasta el deploy, los builds siguen usando la última versión desplegada.
- El **schedule** se configura como en cualquier pipeline: por horario, o por evento ("cuando se actualice el input") — lo segundo encadena bien con las syncs de Magritte ([doc 03](03-data-integration-magritte.md)).
- Añade **checks de calidad** sobre los outputs (PK única, rangos, freshness — [doc 04, sección 9](04-pipelines-y-transformaciones.md)): el preview valida lógica, los checks vigilan producción.

---

## 9. Cambios seguros: ramas y propuestas

Para cambiar un pipeline en producción sin sustos:

1. Trabaja el cambio en una **rama/borrador**, no directamente sobre lo desplegado.
2. Usa el preview para comparar el output nuevo contra el actual (¿mismas filas? ¿columnas esperadas?).
3. Despliega en horario controlado y **vigila el primer build** completo.
4. Si el output alimenta la Ontología o a otros equipos, avisa antes de cambiar el esquema: es un cambio de contrato, no un detalle interno.

> Pipeline Builder versiona las definiciones: se puede volver a una versión anterior. Aun así, el dato ya materializado con la lógica mala no se "des-materializa" solo — puede requerir un rebuild.

---

## 10. Señales de que te quedaste pequeño (y cómo migrar)

Señales de que el pipeline pide Code Repositories:

- Expresiones kilométricas o lógica duplicada en varios nodos (querías una función).
- Necesitas tests unitarios porque los errores de lógica llegan a producción.
- El grafo ya no cabe en una pantalla y nadie lo entiende completo.
- Necesitas una librería, una UDF o un algoritmo que la herramienta no trae.

Cómo migrar sin drama:

1. **No migres todo**: identifica el tramo conflictivo (ej. el join con reglas raras) y muévelo a un transform en código; Pipeline Builder puede seguir haciendo la limpieza previa. Los pipelines visuales y de código **se encadenan** por datasets sin problema.
2. Congela el esquema del output (contrato) y replica la lógica en código contra ese contrato.
3. Ejecuta ambos en paralelo unos días comparando outputs, luego apaga el tramo visual.

---

## 11. Errores comunes y troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| El build falla pero el preview iba bien | El preview usa muestra: datos raros (nulls, skew) solo aparecen a escala completa | Mirar el error del build; añadir manejo de nulos; ver [doc 11, sección 5](11-errores-comunes-y-troubleshooting.md) si es OOM/skew |
| El output no se actualiza | Editaste pero no desplegaste, o el schedule no corre | Verificar versión desplegada y configuración del schedule |
| Filas disparadas tras un join | Duplicados en la clave de join | Dedup antes del join; validar con preview el conteo |
| Output vacío | Filtro demasiado agresivo o claves que no cruzan | Preview nodo a nodo para ver dónde se vacía |
| Nodos en error tras actualizarse el input | Schema drift en el origen | Revisar el cambio con el dueño de la fuente; ajustar casts/renombres |
| Duplicados tras activar incremental | Falta patrón dedup/lookback | Sección 7; mismo patrón que en [doc 04](04-pipelines-y-transformaciones.md) |
| "No puedo editar el pipeline" | Permisos del recurso (rol Editor) | Pedir rol al owner ([doc 08](08-seguridad-y-gobernanza.md)) |

---

## 12. Checklist antes de desplegar a producción

- [ ] Nodos nombrados por intención (el grafo se entiende sin explicación oral)
- [ ] Preview validado tras cada join y filtro (conteos con sentido)
- [ ] Esquema del output revisado y comunicado a los consumidores
- [ ] Dedup/PK garantizados si el output alimenta Ontología u otros equipos
- [ ] Incremental: compatibilidad de transforms verificada + dedup/lookback en su sitio
- [ ] Checks de calidad configurados sobre el output (PK, rangos, freshness)
- [ ] Schedule definido (horario o por actualización del input) y primer build vigilado
- [ ] Owner del pipeline asignado y decisión "visual vs código" registrada

---

## 13. Glosario rápido

| Término | Definición |
|---|---|
| **Pipeline Builder** | Herramienta visual de Foundry para definir pipelines sin código |
| **Nodo / transform** | Paso individual de transformación en el grafo |
| **Path** | Cadena de nodos de un input a un output |
| **Preview** | Muestra del resultado en cualquier punto del grafo, antes de desplegar |
| **Deploy** | Publicación de la definición; hasta entonces los cambios no afectan a producción |
| **Schema drift** | Cambio de esquema en el origen; Pipeline Builder lo señala al editar |
| **Output incremental** | Output que solo procesa datos nuevos/cambiados en cada build |
| **Contrato de esquema** | Esquema estable del output, del que dependen los consumidores |

---

## Referencias

- [Palantir Foundry Documentation — Pipeline Builder](https://www.palantir.com/docs/foundry/pipeline-builder/)
- Ver también: [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md) — conceptos comunes: DAG, Bronze/Silver/Gold, incrementales, calidad
- Ver también: [`03-data-integration-magritte.md`](03-data-integration-magritte.md) — los inputs llegan de aquí
- Ver también: [`05-flujo-datos-end-to-end.md`](05-flujo-datos-end-to-end.md) — dónde encaja el pipeline en el flujo completo
- Ver también: [`11-errores-comunes-y-troubleshooting.md`](11-errores-comunes-y-troubleshooting.md) — diagnóstico de builds y Spark
