# AIP, LLMs y Ontología en Palantir Foundry — Apuntes

> **AIP (Artificial Intelligence Platform)** es la capa de Foundry que integra modelos de lenguaje (LLMs) con la **Ontología**: permite que los agentes de IA lean objetos, naveguen relaciones y ejecuten **Actions** de forma segura y auditable.
>
> **Para quién:** quien diseñe o evalúe casos de uso con IA sobre Foundry. Requiere entender antes la Ontología ([doc 06](06-ontologia-foundry.md)).
>
> Última actualización: 2026-04-08

---

## Índice

1. [Qué es AIP y por qué importa](#1-qué-es-aip-y-por-qué-importa)
2. [Arquitectura: LLM + Ontología + Actions](#2-arquitectura-llm--ontología--actions)
3. [AIP Logic: prompts, pipelines y orquestación](#3-aip-logic-prompts-pipelines-y-orquestación)
4. [AIP Agents: agentes sobre Ontología](#4-aip-agents-agentes-sobre-ontología)
5. [Acceso a datos: qué ve el LLM y qué no](#5-acceso-a-datos-qué-ve-el-llm-y-qué-no)
6. [Actions con LLMs: write-backs seguros](#6-actions-con-llms-write-backs-seguros)
7. [Modelos: proveedores, on-prem y air-gapped](#7-modelos-proveedores-on-prem-y-air-gapped)
8. [Seguridad, markings y gobernanza](#8-seguridad-markings-y-gobernanza)
9. [Patrones de uso habituales](#9-patrones-de-uso-habituales)
10. [Troubleshooting y errores frecuentes](#10-troubleshooting-y-errores-frecuentes)
11. [Checklist para desplegar una solución AIP](#11-checklist-para-desplegar-una-solución-aip)
12. [Glosario rápido](#12-glosario-rápido)

---

## 1. Qué es AIP y por qué importa

**AIP** añade capacidades de IA a Foundry de forma que los modelos de lenguaje no operan sobre texto libre ni sobre bases de datos crudas, sino directamente sobre la **Ontología**: objetos con semántica de negocio, relaciones tipadas y acciones auditables.

Comparativa rápida:

| Enfoque tradicional | Enfoque AIP + Ontología |
|---|---|
| LLM consulta SQL/APIs genéricas | LLM consulta Object Sets tipados |
| Sin control de permisos por contexto | Permisos + markings aplicados siempre |
| Write-back libre o nulo | Write-back solo por Actions validadas |
| Sin trazabilidad | Auditoría de cada acción del agente |
| Alucinaciones difíciles de detectar | Contexto estructurado reduce alucinaciones |

**Idea clave:** AIP no es "ChatGPT conectado a una base de datos". Es IA que entiende el modelo de negocio (Ontología) y solo puede actuar dentro de los límites definidos (Actions + permisos).

---

## 2. Arquitectura: LLM + Ontología + Actions

Visión general del stack:

```
┌──────────────────────────────────────────────────────────┐
│                    Usuario / App                          │
│            (Workshop, AIP Assistant, API)                 │
└────────────────────────┬─────────────────────────────────┘
                         │ prompt / consulta
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    AIP Logic / Agent                      │
│   - orquestación de pasos (plan → act → observe)         │
│   - llamadas al LLM con contexto enriquecido             │
│   - selección de herramientas / funciones disponibles    │
└──────┬────────────────────────────────┬───────────────────┘
       │ lee                            │ ejecuta
       ▼                                ▼
┌─────────────┐                ┌────────────────────┐
│  Ontología  │                │      Actions        │
│ Object Sets │                │ (write-backs)       │
│ Link Types  │                │ validadas + auditadas│
│ Properties  │                └────────────────────┘
└─────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│     Datasets / Phonograph / Fuentes de datos            │
└─────────────────────────────────────────────────────────┘
```

El LLM nunca accede directamente a la capa de almacenamiento: siempre pasa por la Ontología y sus controles.

---

## 3. AIP Logic: prompts, pipelines y orquestación

**AIP Logic** es el entorno para construir pipelines de IA: encadenar pasos de procesamiento que pueden incluir llamadas a LLMs, transformaciones y acceso a la Ontología.

### 3.1 Conceptos clave de AIP Logic

| Concepto | Descripción |
|---|---|
| **Prompt template** | Plantilla parametrizada que inyecta contexto de objetos |
| **Pipeline step** | Unidad de trabajo: llamada LLM, extracción, transformación |
| **Input** | Objeto Ontología, texto, parámetro del usuario |
| **Output** | Texto generado, datos estructurados, trigger de Action |
| **Function** | Función Foundry invocada desde el pipeline |

### 3.2 Flujo típico de AIP Logic

```
Input (Objeto Ontología)
        │
        ▼
Enriquecimiento de contexto
  - propiedades del objeto
  - objetos relacionados (links)
  - documentos asociados
        │
        ▼
Llamada al LLM (prompt template)
        │
        ▼
Post-procesamiento / extracción estructurada
        │
        ▼
Output: texto, JSON, trigger de Action
```

### 3.3 Buenas prácticas de prompts

- Inyectar solo el contexto necesario (ventana de contexto limitada).
- Evitar datos sensibles en el prompt si el modelo es externo.
- Usar plantillas versionadas y revisadas.
- Validar el output del LLM antes de ejecutar una Action.

---

## 4. AIP Agents: agentes sobre Ontología

**AIP Agents** son agentes autónomos (tipo ReAct o similar) que pueden razonar en múltiples pasos, usar herramientas y ejecutar acciones sobre la Ontología.

### 4.1 Arquitectura de un agente

```
Usuario envía objetivo
        │
        ▼
┌─────────────────────────────┐
│           Agente            │
│  Plan → Actúa → Observa     │  (loop hasta completar)
└──────┬──────────────────────┘
       │ usa herramientas
       ├─▶ Buscar objetos (Object Set query)
       ├─▶ Leer propiedades / links
       ├─▶ Ejecutar Function (cálculo/lógica)
       └─▶ Ejecutar Action (write-back)
```

### 4.2 Herramientas disponibles para el agente

| Herramienta | Qué permite |
|---|---|
| `searchObjects` | Filtrar/buscar Object Sets por propiedades |
| `getObject` | Obtener propiedades de un objeto concreto |
| `getLinkedObjects` | Navegar relaciones (Link Types) |
| `callFunction` | Ejecutar Function de Ontología |
| `executeAction` | Ejecutar Action validada (write-back) |
| `searchDocuments` | Búsqueda semántica sobre documentos (si configurado) |

### 4.3 Límites del agente (intencionales)

- Solo puede ejecutar herramientas definidas explícitamente.
- Las Actions están sujetas a validaciones y permisos.
- No puede acceder a datasets fuera de la Ontología.
- El número de pasos puede estar limitado (loop guard).

---

## 5. Acceso a datos: qué ve el LLM y qué no

Este es uno de los puntos más críticos en entornos on-prem y regulados.

```
┌─────────────────────────────────────────────────────┐
│                  Qué ve el LLM                      │
│                                                     │
│  ✅ Propiedades del objeto (según permisos)         │
│  ✅ Objetos relacionados (según permisos + links)   │
│  ✅ Resultados de Functions (calculados)            │
│  ✅ Fragmentos de documentos (si RAG configurado)   │
│                                                     │
│  ❌ Datasets crudos (sin pasar por Ontología)       │
│  ❌ Datos con markings que el usuario no tiene      │
│  ❌ Propiedades excluidas por configuración         │
└─────────────────────────────────────────────────────┘
```

**Regla de oro:** el LLM recibe exactamente lo que el usuario autenticado tiene permiso de ver. Los markings y permisos de la Ontología se aplican siempre, antes de que los datos lleguen al modelo.

---

## 6. Actions con LLMs: write-backs seguros

Uno de los patrones más potentes (y delicados) es permitir que el LLM proponga o ejecute **Actions** sobre la Ontología.

### 6.1 Modos de uso

| Modo | Descripción | Riesgo |
|---|---|---|
| **Propuesta** | El LLM sugiere la acción; el humano confirma | Bajo |
| **Asistido** | El LLM rellena parámetros; humano aprueba | Medio |
| **Autónomo** | El agente ejecuta directamente (dentro de límites) | Alto (requiere diseño cuidadoso) |

### 6.2 Salvaguardas imprescindibles

- Validaciones en la Action (reglas de negocio, restricciones de estado).
- Permisos: solo usuarios/roles autorizados pueden ejecutar la Action vía agente.
- Human-in-the-loop para acciones irreversibles.
- Auditoría: registrar quién ejecutó, qué argumentos, resultado.
- Límite de intentos/reintentos (evitar bucles destructivos).

### 6.3 Flujo recomendado (modo asistido)

```
Agente propone: "Voy a ejecutar AprobarPedido(id=123)"
        │
        ▼
UI muestra confirmación al usuario
        │
        ▼
Usuario confirma (o modifica / rechaza)
        │
        ▼
Action ejecutada con permisos del usuario real
        │
        ▼
Auditoría: usuario X aprobó pedido 123 a las HH:MM
```

---

## 7. Modelos: proveedores, on-prem y air-gapped

### 7.1 Opciones de modelo en AIP

| Tipo | Ejemplos | Consideración principal |
|---|---|---|
| **Cloud (API)** | OpenAI GPT-4, Anthropic Claude | Datos salen del perímetro (revisar markings) |
| **On-prem / self-hosted** | Llama 3, Mistral, modelos fine-tuned | Datos no salen; requiere GPU/infra |
| **Foundry-managed** | Modelos gestionados por Palantir | Depende del contrato/instancia |

### 7.2 Consideraciones para on-prem (OpenShift/Rubix)

```
┌─────────────────────────────────────────────────────────┐
│                   Entorno on-prem                       │
│                                                         │
│  [Foundry AIP]  ──▶  [Model Serving endpoint]          │
│                         (interno, sin egress)           │
│                              │                          │
│                              ▼                          │
│                     [GPU nodes en K8s]                  │
│                     (tolerations, resource limits)      │
└─────────────────────────────────────────────────────────┘
```

Checklist para modelos on-prem:
- GPU nodes con `tolerations`/`nodeSelector` correctos.
- Registry privado con imagen del modelo (sin ImagePullBackOff).
- Endpoint del modelo accesible desde AIP (red interna).
- Sin egress externo para inferencia (air-gapped compliant).
- Monitorizar VRAM/latencia (modelo demasiado grande → OOM).

### 7.3 Air-gapped: lo que más falla

- Modelo descargado y en registry privado (no pull desde Hugging Face).
- Certificados TLS del endpoint del modelo (CA interna confiable).
- Sin proxy externo para llamadas al modelo.

---

## 8. Seguridad, markings y gobernanza

### 8.1 Principios de seguridad AIP

1. **Contexto = permisos del usuario**: el LLM nunca ve más de lo que el usuario puede ver.
2. **Actions = únicos puntos de escritura**: no hay write-back libre.
3. **Auditoría completa**: cada llamada al LLM, cada Action ejecutada.
4. **Data minimization**: no inyectar más datos de los necesarios en el prompt.

### 8.2 Markings y AIP

| Escenario | Comportamiento esperado |
|---|---|
| Objeto con marking `CONFIDENTIAL` | No incluido en contexto si usuario no tiene el marking |
| Propiedad con restricción | No expuesta en el prompt |
| Action restringida por rol | Agente no puede proponer ni ejecutar la Action |
| Modelo externo (cloud) | Solo datos sin markings restrictivos (según política) |

### 8.3 Gobernanza de prompts

- Versionar plantillas de prompts como código (Code Repository).
- Revisar qué datos se inyectan en cada template.
- Auditar cambios en templates (quién, cuándo, qué cambió).
- Tener proceso de aprobación para prompts que acceden a datos sensibles.

---

## 9. Patrones de uso habituales

### 9.1 Resumen automático de objetos

```
Trigger: usuario abre detalle de Pedido
        │
        ▼
AIP Logic: inyecta propiedades + historial del pedido
        │
        ▼
LLM genera: "Resumen: Pedido #123 de Cliente X, importe 5.000€,
             pendiente de aprobación desde hace 3 días por
             falta de documentación."
        │
        ▼
Workshop muestra el resumen en el panel de detalle
```

### 9.2 Clasificación/enriquecimiento masivo

```
Pipeline Foundry (dataset gold)
        │
        ▼
AIP Logic batch: para cada objeto, llamar LLM
  → clasificar categoría
  → extraer entidades
  → generar embedding
        │
        ▼
Escribir resultado en dataset / propiedad calculada
```

### 9.3 Agente de soporte / copilot operativo

```
Usuario describe problema en lenguaje natural
        │
        ▼
Agente busca objetos relacionados (incidencias, pedidos, clientes)
        │
        ▼
Agente sugiere acción o ejecuta Action (si autorizado)
        │
        ▼
Respuesta explicada al usuario + auditoría
```

### 9.4 RAG (Retrieval-Augmented Generation) sobre documentos

```
Corpus de documentos indexados (PDFs, notas, contratos)
        │  búsqueda semántica (embeddings)
        ▼
Fragmentos relevantes recuperados
        │
        ▼
Prompt = contexto del objeto + fragmentos del documento
        │
        ▼
LLM responde con base en datos reales (menos alucinaciones)
```

---

## 10. Troubleshooting y errores frecuentes

| Síntoma | Causa probable | Qué revisar |
|---|---|---|
| Agente no ve datos del objeto | Permisos / markings | Permisos del usuario, markings del Object Type |
| Respuesta vacía o "no tengo datos" | Object Set vacío o filtros incorrectos | Query del Object Set, propiedades indexadas |
| Action falla al ejecutar vía agente | Restricciones de la Action, permisos | Validaciones de la Action, rol del usuario |
| Latencia muy alta | Modelo demasiado grande, contexto enorme | Tamaño del prompt, GPU disponible, modelo on-prem |
| `ImagePullBackOff` en model server | Registry privado sin credenciales o imagen no disponible | Pull secrets, registry mirror, CA |
| Alucinaciones frecuentes | Contexto insuficiente o mal estructurado | Template del prompt, propiedades incluidas |
| Bucle infinito del agente | Loop guard ausente, herramientas mal definidas | Límite de pasos, definición de herramientas |
| Datos sensibles en logs de modelo externo | Markings no respetados o config incorrecta | Política de markings, proveedor del modelo |

---

## 11. Checklist para desplegar una solución AIP

- [ ] Ontología lista: Object Types + Links + Object Sets + Actions + Functions necesarias
- [ ] Permisos y markings revisados (qué datos puede ver el LLM)
- [ ] Modelo seleccionado y accesible (on-prem: endpoint, GPU, registry)
- [ ] Plantillas de prompt versionadas y revisadas
- [ ] Actions con validaciones y auditoría
- [ ] Human-in-the-loop definido para acciones críticas
- [ ] Límite de pasos/reintentos configurado en el agente
- [ ] Tests con datos representativos (incluyendo casos borde)
- [ ] Observabilidad: logs de llamadas al LLM + métricas de latencia
- [ ] Proceso de aprobación para cambios en prompts con datos sensibles

---

## 12. Glosario rápido

| Término | Significado |
|---|---|
| **AIP** | Artificial Intelligence Platform (capa IA de Foundry) |
| **AIP Logic** | Entorno para construir pipelines de IA con LLMs |
| **AIP Agent** | Agente autónomo que razona y actúa sobre la Ontología |
| **LLM** | Large Language Model (modelo de lenguaje grande) |
| **RAG** | Retrieval-Augmented Generation (generación con recuperación) |
| **Prompt template** | Plantilla de prompt con variables inyectadas desde la Ontología |
| **Action** | Operación de write-back validada y auditable en la Ontología |
| **Marking** | Etiqueta de sensibilidad que restringe visibilidad de datos |
| **Object Set** | Colección filtrada de objetos de la Ontología |
| **Function** | Lógica de negocio ejecutable desde la Ontología |
| **Human-in-the-loop** | Patrón donde un humano confirma antes de que el agente actúe |
| **Air-gapped** | Entorno sin acceso a internet externo |

---

## Referencias internas del repo

- Ver también: [`06-ontologia-foundry.md`](06-ontologia-foundry.md)
- Ver también: [`07-workshop-apps-operativas.md`](07-workshop-apps-operativas.md)
- Ver también: [`08-seguridad-y-gobernanza.md`](08-seguridad-y-gobernanza.md)
- Ver también: [`09-apollo-infraestructura.md`](09-apollo-infraestructura.md)
- Ver también: [`04-pipelines-y-transformaciones.md`](04-pipelines-y-transformaciones.md)
