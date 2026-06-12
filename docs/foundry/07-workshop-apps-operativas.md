# Workshop: Aplicaciones Operativas en Palantir Foundry — Apuntes

> Cómo construir **aplicaciones operativas** con Workshop sobre la Ontología: módulos, widgets, variables, eventos, Object Sets, Actions/write-backs, patrones de diseño (search-filter-detail, work queue, approvals), seguridad, rendimiento y troubleshooting.
>
> **Para quién:** quien vaya a construir o mantener una app en Foundry, o quiera entender por qué "la app no muestra datos" suele no ser culpa de la app.
>
> Última actualización: 2026-06-12

---

## Índice

1. [Qué es Workshop y cuándo usarlo](#1-qué-es-workshop-y-cuándo-usarlo)
2. [Modelo mental: la app es una vista sobre la Ontología](#2-modelo-mental-la-app-es-una-vista-sobre-la-ontología)
3. [Anatomía de un módulo Workshop](#3-anatomía-de-un-módulo-workshop)
4. [Widgets principales](#4-widgets-principales)
5. [Variables: el estado de la app](#5-variables-el-estado-de-la-app)
6. [Eventos: conectar widgets entre sí](#6-eventos-conectar-widgets-entre-sí)
7. [Object Sets en la práctica](#7-object-sets-en-la-práctica)
8. [Actions y write-back desde la app](#8-actions-y-write-back-desde-la-app)
9. [Patrones de diseño probados](#9-patrones-de-diseño-probados)
10. [Seguridad: qué ve cada usuario](#10-seguridad-qué-ve-cada-usuario)
11. [Rendimiento](#11-rendimiento)
12. [Publicación y ciclo de vida](#12-publicación-y-ciclo-de-vida)
13. [Errores comunes y troubleshooting](#13-errores-comunes-y-troubleshooting)
14. [Checklist antes de publicar](#14-checklist-antes-de-publicar)
15. [Glosario rápido](#15-glosario-rápido)

---

## 1. Qué es Workshop y cuándo usarlo

**Workshop** es la herramienta low-code de Foundry para construir **aplicaciones operativas**: interfaces donde un equipo de negocio ve datos vivos (objetos de la Ontología) y **actúa** sobre ellos (Actions).

### Workshop vs otras herramientas de Foundry

| Herramienta | Úsala cuando… | No la uses cuando… |
|---|---|---|
| **Workshop** | El usuario necesita *operar*: listas de trabajo, aprobaciones, gestión de casos | Solo necesitas explorar datos ad hoc |
| **Contour** | Análisis exploratorio tabular (pivot, filtros) sin código | Necesitas botones que cambien datos |
| **Quiver** | Series temporales y grafos | App transaccional |
| **Slate** | Necesitas control total del frontend (HTML/CSS/JS) | Workshop ya cubre el caso (Slate cuesta mucho más de mantener) |
| **Object Explorer** | Buscar/navegar objetos sin construir nada | Quieres una experiencia guiada para el usuario |

**Regla práctica:** empieza siempre por Workshop. Pasa a Slate solo si chocas con un límite real de UI.

---

## 2. Modelo mental: la app es una vista sobre la Ontología

Una app Workshop **no tiene base de datos propia**. Todo lo que muestra y todo lo que escribe pasa por la Ontología:

```
        LECTURA                                ESCRITURA
Workshop ──▶ Object Sets ──▶ OSS ──▶          Workshop ──▶ Action ──▶ validaciones
             Phonograph / ES8                              │
                  ▲                                        ▼
                  │ indexing (Funnel)              Phonograph (objeto actualizado)
                  │                                        +
             Gold datasets                         writeback dataset (auditoría)
```

Consecuencias prácticas:

- Si el dato no está en la Ontología, la app **no puede mostrarlo** → primero pipeline + Object Type ([`05-flujo-datos-end-to-end.md`](05-flujo-datos-end-to-end.md)).
- Si la Action no existe en la Ontología, la app **no puede escribirlo** → las reglas de negocio viven en la Action, no en la app.
- La frescura de los datos depende del **pipeline + indexing**, no de la app.

---

## 3. Anatomía de un módulo Workshop

| Pieza | Qué es | Ejemplo |
|---|---|---|
| **Module** | La app completa (unidad que se publica y comparte) | "Gestión de Pedidos" |
| **Page** | Pantalla dentro del módulo | "Pendientes", "Histórico" |
| **Layout** | Organización de la página (columnas, tabs, secciones) | tabla a la izquierda, detalle a la derecha |
| **Widget** | Componente individual | tabla, filtro, botón, métrica |
| **Variable** | Estado compartido entre widgets | "pedido seleccionado" |
| **Event** | Reacción a una interacción | al seleccionar fila → actualizar variable |

Estructura típica:

```
Module "Gestión de Pedidos"
├── Variables: selectedOrder, statusFilter, dateRange
├── Page 1: "Cola de trabajo"
│   ├── Filter widgets (status, fecha, segmento)
│   ├── Object table (Orders filtrados)
│   └── Detail section (selectedOrder + Customer vía link)
│       └── Buttons: [Aprobar] [Rechazar]  ← Actions
└── Page 2: "Métricas"
    └── Charts (aprobaciones/día, tiempo medio)
```

---

## 4. Widgets principales

| Widget | Para qué | Notas |
|---|---|---|
| **Object table** | Listar objetos de un Object Set | el caballo de batalla; soporta orden, selección, columnas calculadas |
| **Object list / card list** | Listas más visuales | mejor para pocos elementos con foto/estado |
| **Filter list** | Filtros interactivos sobre un Object Set | encadenables; alimentan variables |
| **Property / detail** | Mostrar propiedades del objeto seleccionado | combinar con links para mostrar objetos relacionados |
| **Metric card** | KPI único (count, sum, avg de un Object Set) | "Pedidos pendientes: 42" |
| **Chart (bar/line/pie)** | Agregaciones visuales | agregación la hace OSS, no el navegador |
| **Button group** | Disparar Actions o eventos | deshabilitar según estado/permisos |
| **Action form** | Formulario generado desde la definición de la Action | hereda validaciones de la Ontología |
| **Tabs / sections / container** | Organización y navegación | mantener jerarquía visual simple |
| **Markdown / text** | Instrucciones para el usuario | subestimado: úsalo |

---

## 5. Variables: el estado de la app

Las **variables** conectan widgets sin que se conozcan entre sí. Tipos habituales:

| Tipo | Ejemplo | Quién la escribe | Quién la lee |
|---|---|---|---|
| Objeto único | `selectedOrder` | la tabla (al seleccionar fila) | panel de detalle, botones |
| Object Set | `filteredOrders` | los filtros | tabla, metric cards |
| Valor simple (string/number/date) | `statusFilter`, `dateRange` | filter widgets | definición del Object Set |
| Booleano | `showResolved` | un toggle | filtros de la tabla |

Buenas prácticas:
- **Pocas variables y con nombre claro.** Si necesitas un diagrama para entender tu propio módulo, simplifica.
- Define el **valor por defecto** pensando en el primer uso ("status = PENDING" mejor que "sin filtro" si la app es una cola de trabajo).
- Evita cadenas largas de variables derivadas unas de otras: son el equivalente Workshop del "código espagueti".

---

## 6. Eventos: conectar widgets entre sí

Un **evento** = "cuando pasa X en este widget, haz Y". Los más usados:

| Cuando… | Hacer… |
|---|---|
| El usuario selecciona una fila de la tabla | set `selectedOrder` |
| El usuario cambia un filtro | set `statusFilter` → el Object Set se recalcula |
| La Action termina con éxito | limpiar selección, mostrar notificación, refrescar tabla |
| El usuario pulsa un botón de navegación | cambiar de página llevando la selección |

> **Consejo:** los eventos post-Action son los que más se olvidan. Si tras aprobar un pedido la fila sigue apareciendo como pendiente, el usuario pensará que falló — refresca el Object Set o filtra el objeto al completar la Action.

---

## 7. Object Sets en la práctica

Un **Object Set** es una consulta viva: "los Orders con status = PENDING de los últimos 30 días". No es una copia de los datos.

- Se definen partiendo de un Object Type + filtros (estáticos o ligados a variables).
- Se pueden **encadenar**: partir de un set y navegarlo por links (los Orders → sus Customers).
- Las agregaciones (count, sum, group by) las resuelve **OSS en el servidor** — por eso una metric card sobre millones de objetos es instantánea.

Errores conceptuales frecuentes:
- Pensar que el Object Set "se queda viejo": se reevalúa solo; lo que puede ir atrasado es el **indexing** del backing dataset.
- Construir filtros complejos en la app que en realidad pertenecen al **pipeline** (ej: excluir datos corruptos — eso es trabajo de Silver, no de la app).

---

## 8. Actions y write-back desde la app

La app solo **invoca** Actions; la lógica vive en la Ontología ([`06-ontologia-foundry.md`](06-ontologia-foundry.md), sección 4):

```
[Botón Aprobar] ──▶ Action "approve-order"
                      ├── validaciones (estado, permisos, límites)
                      ├── actualiza el objeto en Phonograph
                      └── registra en el writeback dataset (auditoría)
```

Buenas prácticas en el lado de la app:

- Usa **Action forms** generados desde la definición: heredan validaciones y tipos.
- **Deshabilita** el botón cuando la Action no aplica (pedido ya aprobado) en lugar de dejar que falle.
- Muestra el **mensaje de error de la validación** al usuario, no un genérico "algo salió mal".
- Para acciones masivas (aprobar 50 pedidos), verifica que la Action soporta ejecución en lote y comunica el progreso.

---

## 9. Patrones de diseño probados

### 9.1 Search–filter–detail (el 80% de las apps)

```
┌──────────────────────────────────────────────┐
│ [Buscador]  [Filtro status] [Filtro fecha]   │
├───────────────────────┬──────────────────────┤
│ Tabla (Object Set)    │ Detalle de la fila   │
│                       │ + objetos linkados   │
│                       │ + botones de Action  │
└───────────────────────┴──────────────────────┘
```
Para: exploración + acción puntual sobre un objeto.

### 9.2 Work queue (cola de trabajo)

Igual que el anterior pero **opinionado**: el Object Set ya viene filtrado y ordenado por prioridad (`days_pending` desc), el usuario procesa de arriba abajo y cada Action saca el elemento de la cola.

Claves: criterio de orden explícito, el elemento desaparece al procesarse, metric card con el tamaño de la cola.

### 9.3 Approvals (aprobaciones con estados)

Work queue + **máquina de estados** en la Ontología:

```
PENDING ──[approve]──▶ APPROVED ──[ship]──▶ SHIPPED
   └─────[reject]───▶ REJECTED
```

Claves: las transiciones válidas se validan en la **Action** (no en la app); cada estado puede tener su página/tab; el writeback dataset es el log de auditoría.

### 9.4 Command center / dashboard operativo

Página de metric cards + charts con drill-down hacia las vistas de detalle. Ejemplo completo y paso a paso en [`guia-dashboard-monitorizacion.md`](../../guia-dashboard-monitorizacion.md) (dashboard de monitorización de la propia plataforma).

---

## 10. Seguridad: qué ve cada usuario

> Detalle completo en [`08-seguridad-y-gobernanza.md`](08-seguridad-y-gobernanza.md).

La regla de oro: **Workshop no eleva permisos**. La app se ejecuta "como el usuario":

| Capa | Quién decide | Efecto en la app |
|---|---|---|
| Acceso al módulo | permisos del recurso Workshop | puede abrir la app o no |
| Visibilidad de objetos | Gatekeeper + markings sobre el Object Type / backing dataset | la tabla muestra solo lo permitido |
| Ejecución de Actions | permisos de la Action | el botón falla (o se oculta) sin permiso |

Consecuencias:

- **Dos usuarios ven listas distintas** en la misma app: comportamiento correcto, no bug.
- Dar acceso a la app **no** da acceso a los datos: hay que dar ambos (típico error de despliegue).
- Prueba la app con un **usuario real de cada rol** antes de publicar. Lo que el builder ve no es lo que verá el usuario.

---

## 11. Rendimiento

| Síntoma | Causa típica | Mejora |
|---|---|---|
| Tabla tarda en cargar | demasiadas columnas/propiedades cargadas | mostrar lo esencial; detalle bajo demanda |
| Filtros lentos | propiedades no indexadas como searchables | marcar como searchable en el Object Type |
| Charts lentos | agregar en cliente lo que debería agregar OSS | usar agregaciones de Object Set |
| Toda la app lenta | módulo gigante con decenas de widgets por página | dividir en páginas; cargar secciones bajo demanda |
| Datos "viejos" | confundir rendimiento con latencia de indexing | revisar pipeline + Funnel, no la app |

**Principio general:** empuja el trabajo hacia abajo. Lo que pueda resolver el pipeline (Gold), que no lo haga la Ontología; lo que pueda resolver OSS, que no lo haga el navegador.

---

## 12. Publicación y ciclo de vida

1. **Desarrollo** en modo edición (solo builders).
2. **Preview** con usuarios piloto de cada rol.
3. **Publicación** de una versión del módulo (los usuarios consumen la versión publicada, no el borrador).
4. **Iteración**: los cambios en edición no afectan a lo publicado hasta re-publicar.

Recomendaciones:
- Trata el módulo como un **producto**: owner claro, changelog corto al publicar, canal de feedback.
- Cambios en el Object Type (renombrar/borrar propiedades) pueden **romper widgets** silenciosamente: coordina con el equipo de Ontología y revisa el módulo tras cada cambio de modelo.

---

## 13. Errores comunes y troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| Tabla vacía para un usuario (a otros les funciona) | permisos/markings sobre Object Type o backing dataset | revisar con el usuario afectado; ver [`08`](08-seguridad-y-gobernanza.md) |
| Tabla vacía para todos | filtros por defecto demasiado agresivos, u Object Set mal definido | revisar valores por defecto de variables |
| "No aparecen los cambios de hoy" | pipeline o indexing atrasado, no la app | seguir el flujo: ¿Gold actualizado? ¿Funnel al día? ([`11`](11-errores-comunes-y-troubleshooting.md)) |
| La Action falla en UI | validación que no se cumple, o falta permiso de Action/writeback | leer el mensaje de validación; probar la Action fuera de la app |
| Tras la Action, la lista no cambia | falta evento post-Action de refresco | añadir evento al completar la Action |
| Widget roto tras cambio de Ontología | propiedad renombrada/borrada | re-mapear el widget; pactar contrato con el equipo de modelo |

---

## 14. Checklist antes de publicar

- [ ] La app cubre un **flujo de trabajo concreto** (no "mostrar todos los datos")
- [ ] Variables con nombres claros y valores por defecto pensados para el primer uso
- [ ] Eventos post-Action: la UI refleja el cambio sin recargar a mano
- [ ] Botones deshabilitados cuando la Action no aplica, con mensajes de error útiles
- [ ] Probada con un usuario real de **cada rol** (visibilidad y Actions)
- [ ] Propiedades buscadas/filtradas marcadas como searchables en el Object Type
- [ ] Owner del módulo asignado y proceso de feedback definido
- [ ] Latencia de datos (pipeline + indexing) comunicada a los usuarios ("datos cada 15 min")

---

## 15. Glosario rápido

| Término | Definición |
|---|---|
| **Module** | La aplicación Workshop completa; unidad de publicación |
| **Page** | Pantalla dentro de un módulo |
| **Widget** | Componente de UI (tabla, filtro, botón, métrica…) |
| **Variable** | Estado compartido entre widgets (selección, filtros…) |
| **Event** | Reacción configurada a una interacción del usuario |
| **Object Set** | Consulta viva sobre objetos de la Ontología; alimenta los widgets |
| **Action form** | Formulario autogenerado desde la definición de una Action |
| **Write-back** | Escritura auditada producida por una Action |
| **Work queue** | Patrón de app: cola priorizada que el usuario procesa elemento a elemento |
| **Search–filter–detail** | Patrón de app: buscador + lista + panel de detalle con acciones |

---

## Referencias

- [Palantir Foundry Documentation — Workshop](https://www.palantir.com/docs/foundry/workshop/)
- Ver también: [`06-ontologia-foundry.md`](06-ontologia-foundry.md) — Object Sets, Actions, Functions
- Ver también: [`08-seguridad-y-gobernanza.md`](08-seguridad-y-gobernanza.md) — permisos y markings
- Ver también: [`05-flujo-datos-end-to-end.md`](05-flujo-datos-end-to-end.md) — dónde encaja la app en el flujo completo
- Ejemplo paso a paso de un dashboard real: [`guia-dashboard-monitorizacion.md`](../../guia-dashboard-monitorizacion.md)
