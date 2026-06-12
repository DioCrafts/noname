# Contour y Quiver: Análisis Exploratorio en Palantir Foundry — Apuntes

> Cómo explorar y analizar datos **sin escribir código**: **Contour** (análisis tabular: filtros, pivots, joins, charts) y **Quiver** (series temporales y análisis sobre objetos de la Ontología). Cuándo usar cada uno, cómo convertir un análisis en algo permanente y qué límites tienen.
>
> **Para quién:** analistas y cualquier perfil de negocio que necesite responder preguntas con datos; también data engineers, para saber qué entregar a los analistas (y qué no).
>
> Última actualización: 2026-06-12

---

## Índice

1. [El hueco que cubren: análisis ad hoc](#1-el-hueco-que-cubren-análisis-ad-hoc)
2. [Contour: análisis tabular sin código](#2-contour-análisis-tabular-sin-código)
3. [El modelo mental de Contour: el path](#3-el-modelo-mental-de-contour-el-path)
4. [Operaciones típicas en Contour](#4-operaciones-típicas-en-contour)
5. [De análisis a producto: guardar, compartir y materializar](#5-de-análisis-a-producto-guardar-compartir-y-materializar)
6. [Quiver: análisis sobre la Ontología y series temporales](#6-quiver-análisis-sobre-la-ontología-y-series-temporales)
7. [Cuándo usar qué: Contour vs Quiver vs Workshop vs Code Workbooks](#7-cuándo-usar-qué-contour-vs-quiver-vs-workshop-vs-code-workbooks)
8. [Rendimiento y límites](#8-rendimiento-y-límites)
9. [Buenas prácticas para no crear deuda](#9-buenas-prácticas-para-no-crear-deuda)
10. [Errores comunes y troubleshooting](#10-errores-comunes-y-troubleshooting)
11. [Checklist antes de compartir un análisis](#11-checklist-antes-de-compartir-un-análisis)
12. [Glosario rápido](#12-glosario-rápido)

---

## 1. El hueco que cubren: análisis ad hoc

Entre "tengo una pregunta" y "construimos una app" hay un espacio enorme. Ahí viven Contour y Quiver:

```
Pregunta puntual ──▶ Análisis repetido ──▶ Producto operativo
   │                      │                      │
   ▼                      ▼                      ▼
Contour / Quiver    Contour guardado      Workshop (app)
(minutos)           + dataset             Pipeline (dato curado)
                    materializado         Report (informe)
```

**Idea clave:** Contour y Quiver son para **responder preguntas**, no para construir productos. Cuando un análisis se consulta cada semana o alimenta decisiones de otros, hay que "promocionarlo" (sección 5), no dejarlo vivir como análisis suelto.

---

## 2. Contour: análisis tabular sin código

**Contour** permite explorar datasets grandes (millones/billones de filas) con una interfaz visual: filtrar, agrupar, pivotar, hacer joins y graficar. Por debajo ejecuta Spark, así que escala — pero con la latencia de Spark (segundos, no milisegundos).

| Característica | Detalle |
|---|---|
| Entrada | Uno o varios **datasets** (no objetos de la Ontología) |
| Interfaz | Tableros ("boards") encadenados en un **path** de análisis |
| Motor | Spark (cada board es, conceptualmente, una transformación) |
| Salida | Visualizaciones, dashboards de análisis, o un **dataset materializado** |
| Código | Ninguno (existe un board de "expression" para fórmulas puntuales) |

---

## 3. El modelo mental de Contour: el path

Un análisis de Contour es una **cadena de pasos** (path), donde cada board parte del resultado del anterior:

```
Dataset: orders_fact
   │
   ├─ Board 1: Filter        → status = PENDING, último trimestre
   ├─ Board 2: Join          → + customers_clean (por customer_id)
   ├─ Board 3: Pivot         → filas: segmento · columnas: mes · valor: sum(total)
   └─ Board 4: Chart         → evolución por segmento
```

Consecuencias prácticas:

- El path **documenta tu razonamiento**: cualquiera puede ver qué filtros y joins aplicaste (a diferencia de un Excel exportado).
- Puedes **ramificar**: desde el board 2, abrir una rama para otra pregunta sin rehacer los pasos previos.
- Si el dataset de entrada se actualiza, **el análisis se recalcula** con datos frescos.

---

## 4. Operaciones típicas en Contour

| Board | Qué hace | Equivalente SQL |
|---|---|---|
| **Filter** | Quedarte con las filas que cumplen condiciones | `WHERE` |
| **Join** | Cruzar con otro dataset | `JOIN` |
| **Pivot / aggregate** | Agrupar y agregar | `GROUP BY` + funciones |
| **Expression** | Columna calculada con fórmula | `SELECT expr AS col` |
| **Union** | Apilar datasets compatibles | `UNION` |
| **Chart** | Visualizar (barras, líneas, dispersión…) | — |
| **Histogram / distribution** | Ver la forma de una columna | — |

> **Consejo:** filtra **lo antes posible** en el path. Cada board procesa lo que le llega del anterior: un filtro temprano hace todo el análisis más rápido y barato.

---

## 5. De análisis a producto: guardar, compartir y materializar

Tres niveles, de menos a más formal:

| Nivel | Qué es | Cuándo |
|---|---|---|
| **Análisis guardado** | El path queda en el proyecto, otros pueden abrirlo y seguirlo | Pregunta puntual que quizá se repita |
| **Dataset materializado** | Un board se guarda como dataset que se reconstruye con el pipeline | Otros análisis/apps necesitan ese resultado |
| **Lógica promovida a pipeline** | La lógica del path se reescribe en Pipeline Builder / Code Repositories | El resultado es parte del modelo de datos oficial |

> **Regla práctica:** si un dataset materializado desde Contour empieza a tener consumidores serios (Ontología, apps, otros equipos), **promociónalo a pipeline** ([`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md)): ganas tests, revisión de código y un owner claro. Contour es excelente para descubrir la lógica, no para mantenerla en producción.

---

## 6. Quiver: análisis sobre la Ontología y series temporales

**Quiver** es la herramienta de análisis orientada a **objetos** (no a datasets) y a **series temporales**:

| Capacidad | Ejemplo |
|---|---|
| Explorar Object Sets visualmente | distribución de Orders por estado y segmento |
| Series temporales | sensor de temperatura por hora, KPI diario, telemetría |
| Cruzar objetos + tiempo | "pedidos del cliente X superpuestos con sus incidencias" |
| Dashboards analíticos | paneles de exploración que se comparten con el equipo |

Diferencia clave con Contour:

```
Contour  → opera sobre DATASETS  (filas y columnas, vía Spark)
Quiver   → opera sobre OBJETOS   (Ontología, vía OSS) y series temporales
```

Esto importa porque Quiver **hereda los permisos de la Ontología** (markings, Gatekeeper): dos usuarios pueden ver resultados distintos en el mismo análisis, igual que en Workshop ([`08-seguridad-y-gobernanza.md`](08-seguridad-y-gobernanza.md)).

---

## 7. Cuándo usar qué: Contour vs Quiver vs Workshop vs Code Workbooks

| Necesito… | Herramienta |
|---|---|
| Responder una pregunta sobre un dataset grande, ya | **Contour** |
| Explorar objetos de la Ontología y sus relaciones | **Quiver** (u Object Explorer si es solo buscar) |
| Analizar series temporales | **Quiver** |
| Una app donde el equipo **actúe** (aprobar, asignar…) | **Workshop** ([doc 07](07-workshop-apps-operativas.md)) |
| Lógica compleja, librerías Python, modelos | **Code Workbooks** ([doc 04](04-pipelines-y-transformaciones.md)) |
| Un informe narrativo con datos en vivo | **Reports** |

**Regla rápida:** ¿la pregunta es sobre *tablas*? → Contour. ¿Sobre *objetos o tiempo*? → Quiver. ¿La respuesta requiere *actuar*? → Workshop. ¿Necesitas *código*? → Code Workbooks.

---

## 8. Rendimiento y límites

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| Dataset enorme sin filtrar | Cada board lanza Spark sobre todo | Filtrar primero; usar datasets particionados por fecha |
| Joins de tablas grandes en Contour | Lento y caro (shuffle de Spark) | Si el join es recurrente, materializarlo en el pipeline (Gold) |
| Path con decenas de boards | Recalcular se vuelve pesado | Materializar un punto intermedio como dataset |
| Quiver sobre Object Set gigante sin filtros | Consulta masiva a OSS | Partir de un Object Set ya filtrado |
| "Los datos no cuadran con la app" | Contour lee el dataset; la app lee la Ontología (indexing puede ir atrasado) | Comparar versión del dataset vs estado de indexing ([doc 11](11-errores-comunes-y-troubleshooting.md)) |

---

## 9. Buenas prácticas para no crear deuda

- **Nombra los análisis** como preguntas ("¿Pedidos atascados por segmento — Q2?"), no "Untitled (7)".
- Guarda los análisis **dentro del proyecto** al que pertenecen, no en tu carpeta personal: si te vas de vacaciones, el análisis sigue accesible y con permisos correctos.
- Borra o archiva los paths muertos: decenas de análisis huérfanos hacen ilegible el proyecto.
- Si copias un número de Contour a una presentación, **enlaza el análisis**: el número caducará; el path no.
- Un dataset materializado desde Contour debe tener **owner** y descripción, como cualquier dataset ([`08-seguridad-y-gobernanza.md`](08-seguridad-y-gobernanza.md), sección 6).

---

## 10. Errores comunes y troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| "No veo el dataset para analizarlo" | Permisos: tienes Discoverer pero no Viewer | Pedir Viewer sobre el dataset ([doc 08](08-seguridad-y-gobernanza.md)) |
| El análisis va lentísimo | Sin filtros tempranos; joins grandes; dataset sin particionar | Filtrar primero; materializar pasos intermedios |
| Números distintos que en la app Workshop | La app lee Ontología (indexing), Contour lee el dataset | Verificar latencia de indexing; comparar versiones |
| El análisis "se rompió" de un día para otro | Schema drift: el dataset de entrada cambió columnas | Revisar el contrato de esquema con el equipo de pipeline |
| Quiver no muestra objetos que "deberían estar" | Markings/permisos del Object Type, o filtros heredados | Probar con el usuario afectado; revisar markings |
| Dataset materializado desactualizado | El schedule del build no incluye ese dataset | Revisar la configuración de build/schedule |

---

## 11. Checklist antes de compartir un análisis

- [ ] El path tiene nombre descriptivo y está en el proyecto correcto
- [ ] Los filtros aplicados están claros (cualquiera puede auditar el razonamiento)
- [ ] Las cifras clave se validaron contra una fuente conocida (sanity check)
- [ ] Si se comparte con otro equipo: tienen permisos sobre los datasets de entrada
- [ ] Si el resultado se va a reutilizar: dataset materializado con owner y descripción
- [ ] Si se va a consultar cada semana: evaluada la promoción a pipeline/Report

---

## 12. Glosario rápido

| Término | Definición |
|---|---|
| **Contour** | Herramienta de análisis tabular visual sobre datasets (motor Spark) |
| **Path** | Cadena de boards que documenta un análisis en Contour |
| **Board** | Paso individual del análisis (filtro, join, pivot, chart…) |
| **Materializar** | Guardar el resultado de un board como dataset reutilizable |
| **Quiver** | Herramienta de análisis sobre objetos de la Ontología y series temporales |
| **Object Explorer** | Buscador de objetos (navegación, no análisis) |
| **Reports** | Documentos narrativos con datos en vivo de Foundry |
| **Promocionar** | Reescribir la lógica de un análisis como pipeline gobernado |

---

## Referencias

- [Palantir Foundry Documentation — Contour](https://www.palantir.com/docs/foundry/contour/)
- [Palantir Foundry Documentation — Quiver](https://www.palantir.com/docs/foundry/quiver/)
- Ver también: [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md) — a dónde promocionar análisis recurrentes
- Ver también: [`06-ontologia-foundry.md`](06-ontologia-foundry.md) — los objetos que explora Quiver
- Ver también: [`07-workshop-apps-operativas.md`](07-workshop-apps-operativas.md) — cuándo el análisis debe ser una app
