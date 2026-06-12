# Glosario de Palantir Foundry — Apuntes

> Glosario práctico de términos recurrentes en Foundry (datasets, pipelines, Ontología, apps, seguridad, infraestructura y AIP).
>
> **Para quién:** todo el equipo. No se lee de principio a fin: tenlo abierto en otra pestaña mientras lees los demás documentos.
>
> Última actualización: 2026-04-08

---

## Índice

1. [Cómo usar este glosario](#1-cómo-usar-este-glosario)
2. [Datos y datasets](#2-datos-y-datasets)
3. [Pipelines, transforms y Build](#3-pipelines-transforms-y-build)
4. [Ontología](#4-ontología)
5. [Indexing y búsqueda](#5-indexing-y-búsqueda)
6. [Apps y herramientas (Workshop/Contour/...)](#6-apps-y-herramientas-workshopcontour)
7. [Seguridad y gobernanza](#7-seguridad-y-gobernanza)
8. [Infraestructura on-prem (Apollo/Rubix/OpenShift)](#8-infraestructura-on-prem-apollorubixopenshift)
9. [AIP / LLMs](#9-aip--llms)

---

## 1. Cómo usar este glosario

- **Definición corta**: para recordar rápido.
- **Ejemplo/nota**: para ubicarlo en un flujo real.
- Si un término aparece en varios docs, este archivo sirve como “ancla” común.

---

## 2. Datos y datasets

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| Dataset | Unidad de datos versionada en Foundry | Puede ser una tabla (Parquet), archivos, etc. |
| Bronze (raw) | Datos crudos recién ingeridos | “lo que viene del source”, mínimo procesamiento |
| Silver (clean) | Datos limpiados y estandarizados | dedup, tipos, reglas básicas |
| Gold (curated) | Datos listos para consumo negocio/ontología | facts/dims, agregados, modelo estable |
| Lineage | Linaje de datos: de dónde viene y cómo se transformó | clave para auditoría y debugging |
| Schema drift | Cambio de schema en origen | columnas nuevas, tipos cambiados |
| Contract / schema contract | Acuerdo del schema esperado aguas abajo | se “fija” normalmente en Silver/Gold |
| Particionado | Organización física por claves (típico fecha) | reduce lecturas y coste |
| Small files problem | Muchos ficheros pequeños degradan performance | típico en streaming/malas particiones |

---

## 3. Pipelines, transforms y Build

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| Transform | Paso que convierte inputs en un output dataset | SQL/PySpark/Java o visual (Pipeline Builder) |
| Pipeline | Conjunto de transforms conectados por dependencias | DAG de datasets |
| DAG | Grafo acíclico dirigido de dependencias | upstream → downstream |
| Build | Orquestación/scheduler de ejecuciones | decide cuándo recalcular outputs |
| Full refresh | Reprocesa todo el dataset | simple pero caro |
| Incremental | Procesa solo cambios | requiere watermark/lookback + dedup |
| Watermark | “hasta aquí he procesado” | max(updated_at) o offset |
| Lookback | Reprocesar un intervalo anterior | captura late-arriving data |
| Idempotencia | Re-ejecutar no cambia el resultado final | evita duplicados e inconsistencias |
| Skew | Desbalance en claves (una key enorme) | rompe joins/shuffles en Spark |

---

## 4. Ontología

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| Ontología | Capa semántica: datos como objetos/relaciones/acciones | diferencia principal de Foundry |
| Object Type | “Clase” de objeto (Customer, Order) | define propiedades y backing dataset |
| Property | Campo de un objeto | `status`, `total_amount` |
| Link Type | Relación entre object types | Customer 1:N Order |
| Object Set | Conjunto filtrable/buscable de objetos | “Pedidos pendientes” |
| Backing dataset | Dataset que alimenta un object type | normalmente Gold/Silver |
| Action | Operación de escritura sobre objetos | aprobar, asignar, cerrar |
| Function | Lógica reutilizable sobre objetos | cálculo o validación (conceptual) |
| Write-back | Escritura resultante de acciones | queda auditada/persistida |

---

## 5. Indexing y búsqueda

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| Funnel | Indexa datasets hacia Ontología | puente dataset → objeto/búsqueda |
| Indexing | Proceso de mantener Ontología actualizada | latencia aquí = “no veo cambios” |
| ES8 (Elasticsearch) | Índice de búsqueda | búsqueda textual y filtrado rápido |
| Phonograph | Almacén de objetos para read/write | soporte de apps operativas |
| OSS (Object Set Service) | Servicio para operar Object Sets a escala | filtrar billones de objetos |

---

## 6. Apps y herramientas (Workshop/Contour/...)

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| Carbon | Workspace / UI principal | donde navegas carpetas/proyectos |
| Workshop | Apps operativas sobre Ontología | listados + detalle + actions |
| Contour | Análisis visual tabular | pivot, filtros, exploración sin código |
| Slate | Dashboards/apps custom web | más “frontend” y flexible |
| Object Explorer | Buscador de objetos | navegar Ontología estilo “Google” |

---

## 7. Seguridad y gobernanza

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| Multipass | Identidad/autenticación (conceptual) | integra SSO, tokens |
| Gatekeeper | Autorización por políticas (PBAC/ABAC) | controla qué puede leer/hacer cada uno |
| RBAC | Control por roles | “role=admin” |
| ABAC/PBAC | Control por atributos/políticas | “puede ver si region=X y clearance=Y” |
| Markings | Etiquetas de sensibilidad/clasificación | PII, Confidencial, etc. |
| Ownership | Responsabilidad de un recurso | quién aprueba accesos/cambios |
| Least privilege | mínimo privilegio | lo esencial para operar, nada más |

---

## 8. Infraestructura on-prem (Apollo/Rubix/OpenShift)

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| Apollo | CD/operación de despliegues de Foundry | upgrades/rollbacks/config |
| Rubix | Plataforma K8s optimizada por Palantir | workloads de datos |
| OpenShift | Distribución enterprise de K8s | routes/operators/RBAC |
| Skylab | Config/feature flags para servicios | config injection a runtime |
| ImagePullBackOff | error al bajar imagen | registry/credenciales/CA |

---

## 9. AIP / LLMs

| Término | Definición corta | Ejemplo / nota |
|---|---|---|
| AIP | Plataforma para usar LLMs con datos gobernados | grounding + permisos + auditoría |
| Grounding | Recuperar contexto real (Ontología) | evita alucinaciones |
| Tool/Skill | Operación ejecutable por el agente | buscar objetos, ejecutar action |
| Prompt injection | datos “maliciosos” que intentan manipular el LLM | mitigación: separar instrucciones/datos |
| Human-in-the-loop | confirmación humana antes de actuar | clave para write-backs |
