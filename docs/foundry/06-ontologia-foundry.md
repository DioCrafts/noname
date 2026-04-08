# La Ontología de Palantir Foundry — Guía Completa

> La Ontología es **el corazón de Foundry**. Es lo que transforma un data lake genérico en una plataforma operativa.
> Sin entenderla, el resto de Foundry no tiene sentido.
>
> Última actualización: 2026-04-08

---

## Índice

1. [¿Qué es la Ontología?](#1--qué-es-la-ontología)
2. [Conceptos Fundamentales](#2--conceptos-fundamentales)
3. [Infraestructura Interna](#3-️-infraestructura-interna-los-servicios-detrás)
4. [Actions (Acciones)](#4--actions-acciones)
5. [Functions (Funciones)](#5--functions-funciones)
6. [Interface Types](#6--interface-types)
7. [Object Views](#7--object-views)
8. [Writeback Datasets y Ontology Sync](#8--writeback-datasets-y-ontology-sync)
9. [Flujo Completo: De Dataset a Aplicación](#9--flujo-completo-de-dataset-a-aplicación)
10. [Ejemplo Práctico](#10--ejemplo-práctico)
11. [Errores Comunes](#11--errores-comunes)
12. [Glosario Rápido](#12--glosario-rápido)

---

## 1. 🧠 ¿Qué es la Ontología?

La Ontología es una **capa semántica** que se sitúa por encima de los datasets (tablas de datos) y los transforma en **Objetos del mundo real** con relaciones, propiedades y comportamientos.

### Sin Ontología vs Con Ontología

```
SIN ONTOLOGÍA (Data Lake tradicional)
┌──────────────────────────────┐
│  tabla_clientes              │
│  tabla_pedidos               │   → El usuario ve TABLAS
│  tabla_productos             │   → Necesita saber SQL
│  tabla_envios                │   → Sin contexto de negocio
└──────────────────────────────┘

CON ONTOLOGÍA (Foundry)
┌──────────────────────────────┐
│  🧑 Cliente                  │
│    ├── realizó → 📦 Pedido   │   → El usuario ve OBJETOS
│    ├── compró → 🏷️ Producto  │   → Navega relaciones
│    └── recibió → 🚚 Envío   │   → Ejecuta acciones
└──────────────────────────────┘
```

**Idea clave:** Los datos siguen viviendo en datasets (tablas), pero la Ontología les da **significado, estructura y comportamiento**.

---

## 2. 📦 Conceptos Fundamentales

### 2.1 Object Types (Tipos de Objeto)

Un Object Type representa una **entidad del mundo real** en tu dominio de negocio.

| Propiedad del Object Type | Descripción |
|---|---|
| **Nombre** | Nombre legible del tipo (ej: `Cliente`, `Pedido`, `Máquina`) |
| **Primary Key** | Propiedad que identifica de forma única cada instancia (ej: `clienteId`) |
| **Backing Dataset** | El dataset (tabla) de donde se leen los datos |
| **Properties** | Las columnas del dataset mapeadas a propiedades del objeto |

```
Object Type: "Cliente"
├── Primary Key: cliente_id
├── Backing Dataset: /proyecto/datos/clientes_clean
└── Properties:
    ├── nombre       (string)
    ├── email        (string)
    ├── fecha_alta   (date)
    ├── segmento     (string)
    └── revenue_total (double)
```

### 2.2 Properties (Propiedades)

Las propiedades son los **atributos** de un Object Type. Cada propiedad se mapea a una columna del backing dataset.

**Tipos de datos soportados:**
- `string`, `integer`, `long`, `double`, `boolean`
- `date`, `timestamp`
- `geopoint`, `geoshape` (para datos geoespaciales)
- `array<string>`, `array<integer>` (propiedades multivalor)
- `attachment` (ficheros adjuntos)
- `timeseries` (series temporales)

### 2.3 Link Types (Tipos de Enlace)

Los Link Types definen **relaciones entre Object Types**. Son el "grafo" de tu modelo de datos.

| Tipo de Link | Cardinalidad | Ejemplo |
|---|---|---|
| **One-to-Many** | 1:N | Un `Cliente` tiene muchos `Pedidos` |
| **Many-to-Many** | M:N | Un `Producto` aparece en muchos `Pedidos` y viceversa |
| **One-to-One** | 1:1 | Un `Empleado` tiene un `Contrato` |

**Cómo se definen:**
- Se basan en una **foreign key** compartida entre los backing datasets de ambos Object Types.
- Ejemplo: `pedidos.cliente_id` → `clientes.cliente_id`

```
   Cliente ──(1:N)──→ Pedido ──(M:N)──→ Producto
      │                   │
      └──(1:N)──→ Envío ←─┘
```

### 2.4 Object Sets (Conjuntos de Objetos)

Un Object Set es un **subconjunto filtrado** de instancias de un Object Type.

- Son **dinámicos**: se recalculan automáticamente cuando cambian los datos.
- Se definen con filtros sobre propiedades.
- Se usan en Workshop, Contour, AIP y Functions.

**Ejemplos:**
- `Clientes activos`: donde `estado = "activo"`
- `Pedidos pendientes últimos 7 días`: donde `estado = "pendiente" AND fecha > hoy - 7d`
- `Máquinas con alerta crítica`: donde `nivel_alerta = "crítico"`

---

## 3. ⚙️ Infraestructura Interna (Los servicios detrás)

La Ontología no es solo un modelo conceptual — tiene una **infraestructura real** que la hace funcionar a escala:

```
┌─────────────────────────────────────────────────────┐
│                    APLICACIONES                      │
│         Workshop / Contour / AIP / Slate             │
├─────────────────────────────────────────────────────┤
│                                                      │
│   ┌──────────┐   ┌──────────┐   ┌──────────────┐   │
│   │   OSS    │   │Phonograph│   │     ES8      │   │
│   │ (Object  │←──│  Store)  │←──│(Elasticsearch│   │
│   │  Set     │   │          │   │   Search)    │   │
│   └──────────┘   └────▲─────┘   └──────▲───────┘   │
│                       │                │             │
│                  ┌────┴────────────────┴───┐         │
│                  │        FUNNEL           │         │
│                  │   (Indexing Pipeline)   │         │
│                  └────────────▲────────────┘         │
│                               │                      │
├───────────────────────────────┼──────────────────────┤
│                               │                      │
│                    ┌──────────┴──────────┐           │
│                    │  BACKING DATASETS   │           │
│                    │  (Storage/HDFS/S3)  │           │
│                    └─────────────────────┘           │
└─────────────────────────────────────────────────────┘
```

| Servicio | Rol en la Ontología |
|---|---|
| **Backing Dataset** | La tabla de datos "cruda" que alimenta un Object Type. Vive en Storage (HDFS/S3). |
| **Funnel** | Pipeline de indexación que lee el backing dataset y empuja los datos hacia Phonograph y Elasticsearch. Sin Funnel, los objetos no se actualizan. |
| **Phonograph** | Almacén OLAP de alta velocidad que contiene los objetos materializados. Permite lectura y **escritura** en tiempo real (write-backs). |
| **ES8 (Elasticsearch)** | Motor de búsqueda full-text. Permite buscar objetos por texto libre y filtros complejos. |
| **OSS (Object Set Service)** | Servicio que resuelve las consultas de Object Sets: "dame todos los Clientes donde segmento = Premium". Opera sobre Phonograph y ES8. |

### ¿Cuándo se actualizan los objetos?

1. Un **Build** ejecuta una transformación → se actualiza el **backing dataset**
2. **Funnel** detecta la nueva transacción → re-indexa los datos cambiados
3. Los datos fluyen a **Phonograph** (para lectura/escritura rápida) y **ES8** (para búsqueda)
4. Las aplicaciones (Workshop, etc.) ven los objetos actualizados automáticamente

---

## 4. ⚡ Actions (Acciones)

Las Actions son **operaciones que modifican objetos** de la Ontología. Son el mecanismo de **write-back** — permiten que las aplicaciones no solo lean datos, sino que también los cambien.

### Tipos de Actions

| Tipo | Descripción | Ejemplo |
|---|---|---|
| **Create Object** | Crea una nueva instancia de un Object Type | Crear un nuevo `Ticket de soporte` |
| **Modify Object** | Modifica propiedades de un objeto existente | Cambiar `estado` de un `Pedido` a "enviado" |
| **Delete Object** | Elimina una instancia | Eliminar un `Borrador` |
| **Create Link** | Crea una relación entre dos objetos | Asignar un `Técnico` a una `Incidencia` |
| **Delete Link** | Elimina una relación | Desasignar un `Técnico` |

### Tipos por Ejecución

| Tipo | Descripción |
|---|---|
| **Manual** | El usuario la ejecuta desde la UI (botón en Workshop) |
| **Automatizada** | Se dispara por un trigger/regla (ej: cuando un sensor supera un umbral) |
| **Notification** | Envía notificaciones (email, Slack) al ejecutarse |
| **Webhook** | Llama a una API/sistema externo al ejecutarse |
| **Function-backed** | Ejecuta lógica personalizada escrita en TypeScript antes de aplicar los cambios |

### Validaciones y Restricciones

Las Actions pueden tener:
- **Validaciones**: reglas que verifican que los datos sean correctos antes de aplicar la acción (ej: "el campo email no puede estar vacío")
- **Restricciones (Restrictions)**: quién puede ejecutar la acción (por rol, grupo o propiedad del objeto)
- **Rules**: lógica condicional que determina si la acción está disponible (ej: "solo se puede aprobar si el estado es 'pendiente'")

### ¿Dónde van los cambios?

```
Usuario ejecuta Action en Workshop
        │
        ▼
  ┌─────────────┐
  │ Phonograph  │ ← Escritura inmediata (tiempo real)
  └──────┬──────┘
         │
         ▼
  ┌─────────────────┐
  │ Writeback Dataset│ ← Los cambios se persisten en un dataset
  └─────────────────┘
```

---

## 5. 🔧 Functions (Funciones)

Las Functions son **lógica personalizada escrita en TypeScript** que opera sobre objetos de la Ontología.

### ¿Para qué sirven?

- **Cálculos derivados**: KPIs, métricas, scores que no están en el dataset original
- **Lógica de negocio**: reglas complejas, validaciones
- **Agregaciones**: sumar, contar, promediar sobre Object Sets
- **Formateo y transformación**: preparar datos para la UI

### Ejemplo de Function

```typescript
// Calcular el revenue total de un cliente sumando sus pedidos
@Function()
public getRevenueTotal(cliente: Cliente): Double {
    const pedidos = cliente.pedidos.all();  // Navega el Link Type
    return pedidos
        .map(p => p.importe ?? 0)
        .reduce((a, b) => a + b, 0);
}
```

### Diferencia entre Functions y Transforms

| | Functions | Transforms (Pipelines) |
|---|---|---|
| **Lenguaje** | TypeScript | Python / SQL / Java |
| **Ejecución** | En tiempo real (on-demand) | Batch (programada) |
| **Datos** | Opera sobre Objetos de la Ontología | Opera sobre Datasets (tablas) |
| **Resultado** | Valor devuelto a la aplicación | Nuevo dataset persistido |
| **Uso** | Workshop, AIP, APIs | Pipelines de datos |

---

## 6. 🔗 Interface Types

Los Interface Types son **abstracciones reutilizables** — como las interfaces en programación orientada a objetos.

### ¿Para qué sirven?

Permiten definir un **contrato común** de propiedades que múltiples Object Types pueden implementar.

### Ejemplo

```
Interface Type: "Auditable"
├── created_at    (timestamp)
├── updated_at    (timestamp)
├── created_by    (string)
└── updated_by    (string)

Object Type: "Cliente"  → implementa "Auditable"
Object Type: "Pedido"   → implementa "Auditable"
Object Type: "Producto" → implementa "Auditable"
```

**Ventaja**: En Workshop o Functions, puedes escribir lógica genérica que funcione con **cualquier objeto que implemente la interfaz**, sin importar si es un Cliente, Pedido o Producto.

---

## 7. 👁️ Object Views

Los Object Views son **vistas personalizadas** de un Object Type.

- Muestran solo un **subconjunto de propiedades** relevantes para un caso de uso
- Pueden incluir **propiedades derivadas** (de Functions)
- Permiten **personalizar la presentación** según el rol del usuario

### Ejemplo

```
Object Type: "Empleado" (20 propiedades)

Object View: "Vista RRHH"          Object View: "Vista Manager"
├── nombre                          ├── nombre
├── departamento                    ├── departamento
├── fecha_contratacion              ├── equipo
├── salario          ← solo RRHH   ├── proyectos_activos
├── evaluacion                      └── rendimiento_trimestral
└── tipo_contrato
```

---

## 8. 🔄 Writeback Datasets y Ontology Sync

### Writeback Datasets

Cuando un usuario ejecuta una **Action** que modifica un objeto, los cambios se escriben en un **Writeback Dataset** — un dataset especial habilitado para escritura.

```
Flujo de escritura:
Action → Phonograph (tiempo real) → Writeback Dataset (persistencia) → Puede re-entrar al pipeline
```

- Los writeback datasets pueden ser **consumidos por pipelines** posteriores (retroalimentación)
- Permiten **auditoría completa**: cada cambio queda registrado con quién, cuándo y qué

### Ontology Sync

Es el mecanismo que mantiene **sincronizados** todos los componentes cuando hay cambios en el modelo:

- Añadir una nueva propiedad a un Object Type
- Cambiar el backing dataset
- Modificar un Link Type

Ontology Sync **propaga los cambios** a:
- Funnel (re-indexación)
- Phonograph (actualización del esquema)
- Elasticsearch (re-mapping)
- Aplicaciones (Workshop, Contour se actualizan automáticamente)

---

## 9. 🔀 Flujo Completo: De Dataset a Aplicación

```
1. INGESTA                    2. TRANSFORMACIÓN              3. ONTOLOGÍA
┌──────────────┐           ┌──────────────────┐          ┌──────────────────┐
│  Magritte    │           │  Code Repos /    │          │  Definir:        │
│  (Data       │──────────▶│  Pipeline Builder│─────────▶│  • Object Types  │
│  Connection) │  raw data │  / Spark         │  clean   │  • Link Types    │
└──────────────┘           └──────────────────┘  dataset │  • Properties    │
                                                         └────────┬─────────┘
                                                                  │
                                                                  ▼
4. INDEXACIÓN                 5. APLICACIÓN                 6. ACCIÓN
┌──────────────────┐       ┌──────────────────┐          ┌──────────────────┐
│  Funnel indexa   │       │  Workshop /      │          │  Actions         │
│  hacia:          │──────▶│  Contour / AIP   │─────────▶│  modifican       │
│  • Phonograph    │       │  muestran        │  usuario │  objetos →       │
│  • Elasticsearch │       │  objetos         │  decide  │  Writeback       │
└──────────────────┘       └──────────────────┘          └──────────────────┘
```

---

## 10. 🏭 Ejemplo Práctico

### Caso: Gestión de Flotas de Vehículos

**Object Types:**

| Object Type | Primary Key | Propiedades principales |
|---|---|---|
| `Vehículo` | `vehiculo_id` | matrícula, modelo, km_actual, estado, ubicación_gps |
| `Conductor` | `conductor_id` | nombre, licencia, antigüedad, evaluación |
| `Ruta` | `ruta_id` | origen, destino, km_total, tiempo_estimado |
| `Mantenimiento` | `mant_id` | tipo, fecha, coste, taller, estado |

**Link Types:**
- `Conductor` ──(asignado a)──▶ `Vehículo` (1:1)
- `Vehículo` ──(realiza)──▶ `Ruta` (1:N)
- `Vehículo` ──(tiene)──▶ `Mantenimiento` (1:N)

**Actions:**
- `Asignar conductor a vehículo` (Create Link)
- `Registrar mantenimiento` (Create Object)
- `Marcar vehículo como fuera de servicio` (Modify Object)

**Functions:**
- `getKmHastaProximoMantenimiento(vehiculo)` → calcula km restantes
- `getCosteMantAnual(vehiculo)` → suma costes del año
- `getRendimientoConductor(conductor)` → score basado en rutas y evaluaciones

**Object Sets:**
- `Vehículos que necesitan mantenimiento` → donde `km_hasta_mant < 500`
- `Conductores sin asignar` → donde no tienen link a ningún Vehículo

---

## 11. ⚠️ Errores Comunes

| Error | Causa | Solución |
|---|---|---|
| Objetos no se actualizan | Funnel no ha re-indexado tras un Build | Verificar que el pipeline de indexación está activo y sin errores |
| "Object type has no backing dataset" | Se definió el Object Type pero no se asignó un dataset | Asignar un backing dataset en la configuración del Object Type |
| Actions fallan silenciosamente | Falta de permisos en el writeback dataset | Verificar que el usuario/grupo tiene permisos de escritura |
| Búsqueda no encuentra objetos | Elasticsearch no ha indexado aún | Esperar a que Funnel complete la indexación o forzar re-index |
| Properties aparecen como `null` | El mapeo columna→propiedad no coincide (nombres o tipos) | Revisar el mapping en la configuración del Object Type |
| Link Type no muestra relaciones | La foreign key no existe o tiene valores nulos en el dataset | Verificar la integridad referencial entre los backing datasets |
| Functions timeout | Lógica demasiado pesada sobre Object Sets grandes | Optimizar la Function o pre-calcular en un pipeline batch |

---

## 12. 📖 Glosario Rápido

| Término | Definición |
|---|---|
| **Object Type** | Definición de una entidad del mundo real (como una "clase") |
| **Object** | Una instancia concreta de un Object Type (como un "objeto/instancia") |
| **Property** | Atributo de un Object Type (como un "campo" o "columna") |
| **Link Type** | Relación entre dos Object Types (como una "foreign key" semántica) |
| **Object Set** | Subconjunto filtrado y dinámico de objetos |
| **Action** | Operación que crea, modifica o elimina objetos/links |
| **Function** | Lógica TypeScript que calcula valores sobre objetos en tiempo real |
| **Interface Type** | Contrato reutilizable de propiedades (como una "interfaz" en OOP) |
| **Backing Dataset** | El dataset físico (tabla) que alimenta un Object Type |
| **Writeback Dataset** | Dataset especial donde se persisten los cambios de Actions |
| **Funnel** | Pipeline que indexa datos del backing dataset hacia Phonograph y ES8 |
| **Phonograph** | Almacén OLAP de objetos materializados (lectura + escritura rápida) |
| **OSS** | Object Set Service — resuelve consultas sobre conjuntos de objetos |
| **Ontology Sync** | Mecanismo de propagación de cambios en el modelo ontológico |

---

## Referencias

- [Palantir Foundry Documentation](https://www.palantir.com/docs/foundry/)
- [AtlasDB (Open Source)](https://github.com/palantir/atlasdb)
- Componentes relacionados: ver [`palantir-foundry-componentes.md`](palantir-foundry-componentes.md)
- Integración de datos: ver [`data-integration-magritte.md`](data-integration-magritte.md)
