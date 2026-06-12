# Palantir Foundry — Componentes y Servicios

> Guía de referencia organizada por capas arquitectónicas.
>
> **Para quién:** todo el equipo. Es el mapa de la plataforma y el punto de entrada recomendado: léelo primero y vuelve a él cuando un nombre de servicio no te suene.
>
> Última actualización: 2026-04-08

---

## 1. 🏗️ Infraestructura y Orquestación ("The Bedrock")

| Componente | Descripción |
|---|---|
| **Apollo** | Plataforma de entrega continua (CD). Instala, actualiza y gestiona todos los microservicios de Foundry en cualquier entorno (cloud, on-prem, air-gapped). Es el "cerebro operacional". |
| **Rubix** | Distribución de Kubernetes optimizada por Palantir. Gestiona la orquestación de contenedores y cargas de trabajo de datos. |
| **OpenShift** | Plataforma de contenedores (Red Hat) sobre la que puede desplegarse Foundry en entornos on-prem. Alternativa/complemento a Rubix. |
| **Skylab** | Gestión de configuraciones y feature flags para los servicios internos que Apollo despliega (los YAMLs de configuración). |

---

## 2. 💾 Almacenamiento y Estado del Sistema

| Componente | Descripción |
|---|---|
| **HDFS / Object Storage** | Capa de almacenamiento persistente. Históricamente HDFS (Hadoop), hoy evoluciona hacia S3/Azure Blob/GCS. |
| **AtlasDB** | Capa de abstracción transaccional (ACID) creada por Palantir sobre almacenes clave-valor. Garantiza consistencia en metadatos y estado. **Open source.** |
| **Cassandra** | Base de datos NoSQL distribuida usada como backend de AtlasDB para alta disponibilidad y consistencia. |
| **PostgreSQL** | Usado por muchos microservicios internos para almacenar sus propios metadatos y estados. |
| **Highbury** | Servicio que gestiona el filesystem lógico de Foundry: el árbol de carpetas, proyectos y recursos que el usuario ve en la interfaz (Carbon). |

---

## 3. 🔌 Integración de Datos (Data Connection)

| Componente | Descripción |
|---|---|
| **Magritte (Data Connection)** | Servicio de conexión con fuentes externas (SQL, SAP, Salesforce, APIs REST, ficheros, etc.) mediante **Agents** desplegados en la red del cliente. |
| **Agents** | Procesos ligeros instalados fuera de Foundry que actúan como puente seguro entre las fuentes de datos y la plataforma (comunicación saliente por puerto 443). |

---

## 4. ⚙️ Cómputo y Orquestación de Pipelines

| Componente | Descripción |
|---|---|
| **Spark** | Motor principal de procesamiento distribuido (Apache Spark). Ejecuta las transformaciones a escala. |
| **Build** | Orquestador/scheduler que decide cuándo y cómo se ejecutan los pipelines de datos (gestiona dependencias y triggers). |
| **Code Repositories** | Entorno de desarrollo basado en Git para escribir transformaciones en **Python, Java o SQL**. |
| **Code Workbooks** | Entorno interactivo tipo notebook (similar a Jupyter) para exploración de datos y prototipado rápido con Spark/SQL. |
| **Pipeline Builder** | Interfaz visual no-code/low-code para crear flujos de transformación de datos sin escribir código. |

---

## 5. 🧠 La Ontología (Capa Semántica — "El Corazón de Foundry")

> Aquí los datos dejan de ser tablas y se convierten en **Objetos** con relaciones, propiedades y acciones.

| Componente | Descripción |
|---|---|
| **OSS (Object Set Service)** | Servicio que permite buscar, filtrar y operar sobre conjuntos masivos de objetos de la Ontología en milisegundos. |
| **Phonograph** | Base de datos OLAP de alta velocidad que almacena los objetos de la Ontología para lectura y escritura en tiempo real desde aplicaciones. |
| **Funnel** | Servicio de indexación que toma datos de los datasets (Storage/Spark) y los empuja hacia la Ontología (Phonograph, Elasticsearch). El "puente" entre datos crudos y objetos. |
| **ES8 (Elasticsearch)** | Motor de búsqueda full-text usado para indexar y buscar objetos y datos dentro de la Ontología. |
| **Indexing** | Infraestructura general de indexación que coordina Funnel y ES8 para mantener la Ontología actualizada. |
| **Actions** | Framework para definir y ejecutar acciones (write-backs) sobre objetos de la Ontología desde aplicaciones. |
| **Functions** | Lógica personalizada (TypeScript) que se ejecuta sobre objetos de la Ontología para cálculos, validaciones y reglas de negocio. |

---

## 6. 🔍 Metadatos, Linaje y Gobernanza

| Componente | Descripción |
|---|---|
| **Metadata** | Sistema que rastrea el linaje completo de cada dato (de dónde viene, cómo se transformó, quién lo modificó), definiciones y permisos. |
| **Compass** | Catálogo de datos y servicio de descubrimiento. Complementa Metadata ofreciendo navegación y búsqueda de recursos. |
| **Gatekeeper** | Servicio centralizado de autorización y control de acceso basado en políticas (PBAC/ABAC). Aplica permisos en cada nivel de la pila. |
| **Multipass** | Servicio de autenticación y gestión de tokens (SSO, SAML, OAuth). |

---

## 7. 🖥️ Capa de Aplicaciones y Análisis (User-Facing Tools)

| Componente | Descripción |
|---|---|
| **Carbon (Workspace)** | La interfaz principal unificada de Foundry. Es el "escritorio" donde el usuario ve carpetas, proyectos, archivos y navega la plataforma. |
| **Workshop** | Herramienta principal para crear aplicaciones operativas complejas sobre la Ontología (low-code). |
| **Contour** | Herramienta de análisis visual para explorar, pivotar y filtrar grandes volúmenes de datos tabulares sin código. |
| **Quiver** | Herramienta para análisis de series temporales, visualización de grafos y exploración de relaciones. |
| **Slate** | Framework para crear dashboards y aplicaciones totalmente personalizadas con HTML/CSS/JS. |
| **Object Explorer** | Buscador estilo "Google" para navegar objetos de la Ontología. |
| **Reports** | Herramienta para crear informes y documentos que combinan texto narrativo con datos en vivo de Foundry. |

---

## 8. 🤖 Inteligencia Artificial (AIP)

| Componente | Descripción |
|---|---|
| **AIP (AI Platform)** | Capa de IA (2023–2026) que integra LLMs directamente sobre la Ontología. Permite automatizar decisiones, generar análisis y crear agentes con acceso controlado a datos reales. |
| **AIP Logic** | Motor de razonamiento que conecta los modelos de lenguaje con Actions y Functions de la Ontología. |

---

## 9. 🔧 Observabilidad y Operaciones

| Componente | Descripción |
|---|---|
| **Monocle** | Servicio de monitorización y observabilidad interna de los microservicios de Foundry. |

---

## 10. 🌐 Ecosistema Palantir (Fuera de Foundry)

| Plataforma | Descripción |
|---|---|
| **Gotham** | Plataforma hermana orientada a inteligencia y defensa. Comparte servicios de infraestructura con Foundry (Apollo, AtlasDB, etc.). |
| **Apollo (standalone)** | También se comercializa de forma independiente como plataforma de CD para gestionar software en entornos complejos. |

---

## Diagrama Simplificado de Capas

```
┌─────────────────────────────────────────────────────────┐
│         APLICACIONES (Carbon / Workspace)                │
│  Workshop │ Contour │ Quiver │ Slate │ Object Explorer   │
│  Reports  │ AIP                                          │
├─────────────────────────────────────────────────────────┤
│         ONTOLOGÍA (Capa Semántica)                       │
│  OSS │ Phonograph │ Funnel │ ES8 │ Actions │ Functions   │
├─────────────────────────────────────────────────────────┤
│         GOBERNANZA Y METADATOS                           │
│  Metadata │ Compass │ Gatekeeper │ Multipass             │
├─────────────────────────────────────────────────────────┤
│         CÓMPUTO Y PIPELINES                              │
│  Spark │ Build │ Code Repos │ Code Workbooks │ Pipeline  │
│  Magritte (Data Connection) + Agents                     │
├─────────────────────────────────────────────────────────┤
│         ALMACENAMIENTO Y ESTADO                          │
│  HDFS/S3 │ AtlasDB │ Cassandra │ PostgreSQL │ Highbury   │
├─────────────────────────────────────────────────────────┤
│         INFRAESTRUCTURA Y ORQUESTACIÓN                   │
│  Apollo │ Rubix │ OpenShift │ Skylab │ Monocle           │
└─────────────────────────────────────────────────────────┘
```

---

## Flujo Típico de Datos

```
Magritte (Agents) → Storage (HDFS/S3) → Spark/Build → Funnel → Ontología (Phonograph/ES8) → Aplicaciones (Workshop/Contour/AIP)
```

---

## Notas

- Muchos de estos nombres son **internos** y no aparecen en la documentación pública oficial.
- La arquitectura es **SOA (Service-Oriented Architecture)** masiva: cada componente es un microservicio independiente orquestado por Apollo.
- AtlasDB es **open source** ([github.com/palantir/atlasdb](https://github.com/palantir/atlasdb)).
- El flujo típico de datos es: **Magritte → Storage → Spark/Build → Funnel → Ontología (Phonograph/ES8) → Aplicaciones**.
