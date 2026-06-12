# Functions (TypeScript) en Palantir Foundry — Apuntes

> Qué son las **Functions**, cuándo usarlas frente a Transforms o AIP Logic, cómo se escriben (API de Ontología en TypeScript), cómo se publican y versionan, qué límites tienen y cómo se depuran.
>
> **Para quién:** quien vaya a escribir lógica de negocio sobre la Ontología (cálculos en vivo, validaciones, datos para widgets) y quien revise ese código. Requiere entender antes la Ontología ([doc 06](06-ontologia-foundry.md)).
>
> Última actualización: 2026-06-12

---

## Índice

1. [Qué es una Function (y qué no es)](#1-qué-es-una-function-y-qué-no-es)
2. [Functions vs Transforms vs AIP Logic](#2-functions-vs-transforms-vs-aip-logic)
3. [Dónde viven: el repositorio de Functions](#3-dónde-viven-el-repositorio-de-functions)
4. [Anatomía de una Function](#4-anatomía-de-una-function)
5. [La API de Ontología en TypeScript](#5-la-api-de-ontología-en-typescript)
6. [Tipos de uso habituales](#6-tipos-de-uso-habituales)
7. [Publicación y versionado](#7-publicación-y-versionado)
8. [Testing](#8-testing)
9. [Límites y rendimiento](#9-límites-y-rendimiento)
10. [Patrones y anti-patrones](#10-patrones-y-anti-patrones)
11. [Errores comunes y troubleshooting](#11-errores-comunes-y-troubleshooting)
12. [Checklist antes de publicar una Function](#12-checklist-antes-de-publicar-una-function)
13. [Glosario rápido](#13-glosario-rápido)

---

## 1. Qué es una Function (y qué no es)

Una **Function** es código TypeScript que se ejecuta **bajo demanda** sobre objetos de la Ontología: cuando un widget la necesita, cuando una Action la invoca o cuando un agente AIP la usa como herramienta.

```
                 ┌──────────────────────────────┐
   Workshop ────▶│                              │
   Action   ────▶│   Function (TypeScript)      │────▶ resultado
   AIP tool ────▶│   lee objetos, calcula,      │      (valor, lista,
                 │   valida, agrega             │       validación…)
                 └──────────────────────────────┘
                            │ lee vía
                            ▼
                     Ontología (OSS/Phonograph)
```

**Qué NO es una Function:**

- ❌ No es un **transform**: no produce datasets ni corre en builds programados.
- ❌ No es un proceso de larga duración: tiene timeout corto (segundos).
- ❌ No escribe directamente en datasets: si necesita escribir, lo hace a través de una **Action**.

---

## 2. Functions vs Transforms vs AIP Logic

La decisión más importante de este documento:

| Criterio | Function | Transform (pipeline) | AIP Logic |
|---|---|---|---|
| Cuándo se ejecuta | Bajo demanda (en vivo) | En builds programados | Bajo demanda, con LLM |
| Sobre qué opera | Objetos de la Ontología | Datasets | Objetos + prompts |
| Latencia esperada | Milisegundos–segundos | Minutos–horas | Segundos |
| Volumen razonable | Decenas–miles de objetos | Cualquiera (Spark) | El contexto de un prompt |
| Resultado | Valor calculado en vivo | Dataset materializado | Texto/JSON/Action |
| Ejemplo | "riesgo actual de este pedido" | "tabla de riesgos diaria" | "resume las incidencias del cliente" |

**Regla rápida:** si el cálculo debe reflejar **el estado de ahora mismo** y opera sobre pocos objetos → Function. Si recorre millones de filas o puede pre-calcularse → Transform. Si necesita lenguaje natural → AIP Logic ([doc 10](10-aip-llms-ontologia.md)).

> **Anti-patrón clásico:** usar una Function para agregar millones de objetos en cada carga de un widget. Eso es un Transform disfrazado: pre-calcula en el pipeline y deja la Function para lo que cambia en vivo.

---

## 3. Dónde viven: el repositorio de Functions

Las Functions se desarrollan en un **Code Repository** de tipo Functions:

1. Crear repositorio (tipo *Functions*) en el proyecto.
2. **Importar los Object Types** que la Function va a usar (genera tipos TypeScript automáticamente: autocompletado y comprobación de tipos).
3. Escribir las Functions en `src/`.
4. Commit → CI del repositorio compila y ejecuta tests.
5. **Publicar** una versión (tag semántico) para que Workshop/Actions/AIP puedan usarla.

> Ejemplo completo de este flujo, con código real, en la [guía del dashboard](../../guia-dashboard-monitorizacion.md), Fase 3.

---

## 4. Anatomía de una Function

```typescript
import { Function, OntologyObject } from "@foundry/functions-api";
import { Objects, Order, Customer } from "@foundry/ontology-api";

export class OrderFunctions {

    /**
     * Riesgo de un pedido: combina antigüedad y de importe.
     * Usada por: widget "detalle de pedido" y Action "aprobar".
     */
    @Function()
    public orderRiskScore(order: Order): Double {
        const daysPending = this.daysSince(order.orderDate);
        const amountFactor = order.totalAmount > 10_000 ? 2 : 1;
        return daysPending * amountFactor;
    }

    @Function()
    public pendingOrdersFor(customer: Customer): Order[] {
        return customer.orders.all()
            .filter(o => o.status === "PENDING");
    }
}
```

Piezas clave:

| Pieza | Qué hace |
|---|---|
| `@Function()` | Marca el método como invocable desde fuera (Workshop, Actions, AIP) |
| Tipos generados (`Order`, `Customer`) | Vienen de los Object Types importados; si el modelo cambia, el código deja de compilar (bien: error visible en CI, no en producción) |
| `customer.orders` | Navegación por **Link Types** — sin joins manuales |
| Tipos de retorno | Escalares, objetos, listas de objetos, estructuras serializables |

---

## 5. La API de Ontología en TypeScript

Operaciones habituales:

| Operación | Ejemplo |
|---|---|
| Buscar objetos | `Objects.search().order().filter(o => o.status.exactMatch("PENDING")).all()` |
| Obtener por PK | `Objects.search().order().filter(o => o.orderId.exactMatch(id)).all()[0]` |
| Navegar links | `order.customer.get()` · `customer.orders.all()` |
| Agregar | `.count()`, `.sum(o => o.totalAmount)` (delegado a OSS cuando es posible) |
| Limitar | `.take(100)` — nunca traigas "todo" sin límite |

Notas importantes:

- Las búsquedas pasan por **OSS**, así que aplican **permisos y markings del usuario que ejecuta** — una Function no eleva privilegios.
- Filtra **en la query**, no en memoria: `filter` sobre la búsqueda lo resuelve el índice; un `.all()` seguido de `Array.filter` trae todo y luego descarta (lento y propenso a timeouts).

---

## 6. Tipos de uso habituales

| Uso | Descripción | Ejemplo |
|---|---|---|
| **Cálculo en vivo** (derived/computed) | Valor calculado al mostrar un objeto | score de riesgo, días pendiente |
| **Lógica de Action** | Validar o calcular dentro de un write-back | "no aprobar si el cliente tiene impagos" |
| **Backing de widgets** | Alimentar una tabla/chart con lógica a medida | "los 10 pedidos más urgentes según regla X" |
| **Herramienta de AIP** | Operación que un agente LLM puede invocar | `getCustomerSummary(customer)` ([doc 10](10-aip-llms-ontologia.md)) |
| **Reglas reutilizables** | Una sola fuente de verdad para una regla de negocio | "¿está el pedido bloqueado?" usada por 3 apps |

---

## 7. Publicación y versionado

- Las Functions se consumen por **versión publicada** (semver): los widgets y Actions apuntan a una versión concreta, no al último commit.
- Cambios **compatibles** (nueva Function, parámetro opcional) → versión minor.
- Cambios **incompatibles** (renombrar, cambiar firma o tipo de retorno) → versión major, y migrar los consumidores de forma coordinada.
- Antes de borrar o renombrar una Function publicada, localiza a sus consumidores (Workshop, Actions, AIP): el error aparecería en *sus* pantallas, no en tu repositorio.

> **El peligro silencioso:** cambios en la Ontología (renombrar una property) rompen la compilación del repo de Functions — eso es visible. Pero un widget apuntando a una versión vieja de la Function seguirá funcionando con lógica desactualizada — eso no se ve. Coordina los cambios de modelo con re-publicación y actualización de consumidores.

---

## 8. Testing

- El repositorio admite **tests unitarios** (Jest o equivalente) que corren en CI en cada commit.
- Estructura recomendada: separar la **lógica pura** (cálculos sobre datos ya cargados) de la **carga de objetos** — la lógica pura se testea sin Ontología.

```typescript
// Lógica pura, testeable sin Ontología:
export function riskScore(daysPending: number, amount: number): number {
    return daysPending * (amount > 10_000 ? 2 : 1);
}

// La Function solo carga datos y delega:
@Function()
public orderRiskScore(order: Order): Double {
    return riskScore(this.daysSince(order.orderDate), order.totalAmount);
}
```

- Casos mínimos a cubrir: valores nulos/ausentes en properties, listas vacías al navegar links, y los límites de las reglas de negocio (¿10 000 incluido o no?).

---

## 9. Límites y rendimiento

| Límite | Implicación |
|---|---|
| **Timeout** (segundos) | Si la Function recorre demasiados objetos, falla. Síntoma de que debería ser un Transform. |
| **Memoria acotada** | No cargar Object Sets enormes con `.all()` sin filtros ni `take`. |
| **Sin estado** | Cada invocación parte de cero; no hay caché entre llamadas garantizada. |
| **Solo lectura** | La escritura va por Actions, que aplican validaciones y auditoría. |
| **Llamadas desde widgets** | Una tabla con una Function por fila = N invocaciones. Preferir una Function que reciba el conjunto y devuelva los resultados de una vez. |

---

## 10. Patrones y anti-patrones

**Patrones sanos ✅**

- Una regla de negocio = **una** Function reutilizada por todas las apps (no copias por app).
- Lógica pura separada de la carga de objetos (testeable).
- Nombres que describen la pregunta que responden: `isOrderBlocked`, `customerLifetimeValue`.
- Documentar en el JSDoc **quién consume** la Function.

**Anti-patrones ❌**

- Agregar millones de objetos en vivo → eso es un Transform ([doc 04](04-pipelines-y-transformaciones.md)).
- Replicar en una Function lógica que ya existe en el pipeline (dos fuentes de verdad que divergirán).
- `all()` sin filtro + filtrado en memoria.
- Functions "Dios" de 500 líneas que calculan diez cosas: una Function, una responsabilidad.

---

## 11. Errores comunes y troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| Timeout al ejecutar | Recorre demasiados objetos / filtra en memoria | Filtrar en la query, `take()`, o mover a Transform |
| "Function not found" en Workshop | El widget apunta a una versión no publicada o retirada | Re-publicar y actualizar la referencia del widget |
| Deja de compilar tras cambio de Ontología | Property/link renombrado o borrado | Re-importar Object Types y adaptar el código (es el comportamiento deseado) |
| Resultados distintos según el usuario | Permisos/markings: la Function ve lo que ve el usuario | Comportamiento correcto; si no lo es, revisar el diseño ([doc 08](08-seguridad-y-gobernanza.md)) |
| Resultado nulo inesperado | Properties opcionales sin manejar | Tratar nulos explícitamente; test para ese caso |
| Widget lento | Una invocación por fila | Function por lote (recibe lista, devuelve mapa) |

---

## 12. Checklist antes de publicar una Function

- [ ] ¿Debería ser una Function? (en vivo + pocos objetos; si no, Transform)
- [ ] Filtros resueltos en la query, no en memoria; límites (`take`) donde aplique
- [ ] Nulos y listas vacías manejados explícitamente
- [ ] Lógica pura separada y con tests (incluidos casos límite)
- [ ] Nombre y JSDoc claros, con consumidores documentados
- [ ] Versionado correcto (major si rompe firma) y consumidores avisados
- [ ] Probada con un usuario sin privilegios de admin

---

## 13. Glosario rápido

| Término | Definición |
|---|---|
| **Function** | Código TypeScript ejecutado bajo demanda sobre objetos de la Ontología |
| **Repositorio de Functions** | Code Repository tipo Functions: código, CI, tests y publicación |
| **Importar Object Types** | Generar los tipos TS desde el modelo de Ontología |
| **Publicar** | Crear una versión consumible (semver) de las Functions del repo |
| **OSS** | Object Set Service: resuelve las búsquedas que hace la Function |
| **Transform** | Lógica de pipeline que materializa datasets (lo contrario de "en vivo") |
| **Computed value** | Valor calculado por una Function al mostrarse un objeto |
| **Function por lote** | Patrón: recibir un conjunto y devolver todos los resultados en una llamada |

---

## Referencias

- [Palantir Foundry Documentation — Functions](https://www.palantir.com/docs/foundry/functions/)
- Ver también: [`06-ontologia-foundry.md`](06-ontologia-foundry.md) — sección 5 (Functions) y Actions
- Ver también: [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md) — cuándo usar un Transform en su lugar
- Ver también: [`10-aip-llms-ontologia.md`](10-aip-llms-ontologia.md) — Functions como herramientas de agentes
- Ejemplo con código completo: [guía del dashboard](../../guia-dashboard-monitorizacion.md), Fase 3
