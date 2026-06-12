# 📚 Apuntes de Palantir Foundry

> Documentación técnica interna sobre Palantir Foundry, escrita para que **cualquier miembro del equipo** pueda entender la plataforma: qué piezas tiene, cómo fluyen los datos, cómo se construyen apps y cómo se diagnostican problemas.

---

## ¿Nuevo en Foundry? Empieza aquí

1. Lee [`01-palantir-foundry-componentes.md`](01-palantir-foundry-componentes.md) para tener el **mapa** (15 min).
2. Lee [`05-flujo-datos-end-to-end.md`](05-flujo-datos-end-to-end.md) para entender el **viaje completo de un dato** con un caso práctico (30 min).
3. Ten a mano [`02-glosario-foundry.md`](02-glosario-foundry.md) mientras lees el resto.

Con esos tres documentos ya puedes seguir cualquier conversación del equipo. Después, profundiza según tu rol (ver abajo).

---

## Documentos disponibles

| # | Documento | Qué responde |
|---|---|---|
| 01 | [Componentes y servicios](01-palantir-foundry-componentes.md) | ¿Qué piezas tiene Foundry y cómo se organizan por capas? Mapa de referencia de toda la plataforma. |
| 02 | [Glosario](02-glosario-foundry.md) | ¿Qué significa cada término? Definiciones cortas con ejemplos, agrupadas por tema. |
| 03 | [Integración de datos (Magritte)](03-data-integration-magritte.md) | ¿Cómo entran los datos desde fuentes externas? Agents, conectores, modos de sincronización, PII masking. |
| 04 | [Pipelines y transformaciones](04-pipelines-y-transformaciones.md) | ¿Cómo se limpian y modelan los datos? Bronze/Silver/Gold, incrementales, calidad, Spark. |
| 05 | [Flujo de datos end-to-end](05-flujo-datos-end-to-end.md) | ¿Cómo encaja todo? Caso práctico completo: de SQL Server a una app con write-back. |
| 06 | [La Ontología](06-ontologia-foundry.md) | ¿Qué es la capa semántica? Object Types, Links, Actions, Functions, Phonograph, OSS. |
| 07 | [Workshop: apps operativas](07-workshop-apps-operativas.md) | ¿Cómo se construyen aplicaciones? Widgets, variables, eventos, patrones, rendimiento. |
| 08 | [Seguridad y gobernanza](08-seguridad-y-gobernanza.md) | ¿Quién puede ver/hacer qué? Multipass, Gatekeeper, RBAC/ABAC, markings, ownership. |
| 09 | [Apollo e infraestructura](09-apollo-infraestructura.md) | ¿Cómo se despliega y opera? Apollo, Rubix/OpenShift/K8s, Skylab, on-prem y air-gapped. |
| 10 | [AIP: LLMs sobre la Ontología](10-aip-llms-ontologia.md) | ¿Cómo se usan LLMs con datos gobernados? Grounding, tools, permisos, human-in-the-loop. |
| 11 | [Errores comunes y troubleshooting](11-errores-comunes-y-troubleshooting.md) | ¿Por dónde empiezo cuando algo falla? Runbook: síntoma → diagnóstico → fix → prevención. |
| 12 | [Contour y Quiver: análisis exploratorio](12-contour-quiver-analisis-exploratorio.md) | ¿Cómo respondo preguntas con datos sin escribir código? Paths, pivots, series temporales y cuándo promocionar un análisis a pipeline. |
| 13 | [Functions (TypeScript)](13-functions-typescript.md) | ¿Cómo escribo lógica de negocio en vivo sobre la Ontología? API, versionado, testing, límites y Functions vs Transforms. |
| 14 | [Streaming y tiempo real](14-streaming-y-tiempo-real.md) | ¿Cuándo (no) usar streaming? Kafka, micro-batch, ventanas, small files, latencia end-to-end y monitorización. |

### Documentos relacionados (raíz del repositorio)

| Documento | Qué contiene |
|---|---|
| [`guia-dashboard-monitorizacion.md`](../../guia-dashboard-monitorizacion.md) | Guía completa (referencia + paso a paso) para construir un **dashboard de monitorización de la plataforma** en Workshop, con Ontología, Functions, Data Health y Automations. |
| [`post-mortem-2026-04-ontologia-highbury.md`](../../post-mortem-2026-04-ontologia-highbury.md) | Post-mortem real: degradación severa de la Ontología on-prem (Highbury) por co-location de nodos y discos sin RAID 0. Lectura recomendada para perfiles de plataforma. |
| [`plantilla-post-mortem.md`](../plantillas/plantilla-post-mortem.md) | Plantilla para documentar el próximo incidente con la misma estructura que el post-mortem real. |

---

## Cómo encajan los documentos entre sí

```
                       02 · Glosario  (consulta transversal)
                       11 · Troubleshooting  (consulta transversal)

01 · Componentes ──▶ visión general de la plataforma
        │
        ▼
05 · Flujo end-to-end ──▶ el hilo conductor que une todo
        │
        ├─▶ 03 · Magritte          (cómo ENTRAN los datos)
        ├─▶ 14 · Streaming         (cómo entran en tiempo real)
        ├─▶ 04 · Pipelines         (cómo se TRANSFORMAN)
        ├─▶ 06 · Ontología         (cómo se MODELAN como objetos)
        ├─▶ 13 · Functions         (lógica en vivo sobre objetos)
        ├─▶ 07 · Workshop          (cómo se USAN en apps)
        ├─▶ 12 · Contour/Quiver    (cómo se ANALIZAN sin código)
        ├─▶ 10 · AIP / LLMs        (cómo se usan con IA)
        ├─▶ 08 · Seguridad         (quién puede ver/hacer qué)
        └─▶ 09 · Apollo / Infra    (sobre qué corre todo)
```

---

## Rutas de lectura según tu rol

| Rol | Lee en este orden |
|---|---|
| **Cualquiera (onboarding)** | 01 → 05 → 02 (a mano) |
| **Data engineer** | 01 → 05 → 03 → 04 → 06 → 14 → 11 |
| **App builder** | 01 → 05 → 06 → 07 → 13 → 08 |
| **Analista / negocio** | 01 → 05 → 12 → 02 (a mano) |
| **Plataforma / SRE** | 01 → 09 → 11 → `post-mortem-2026-04-ontologia-highbury.md` → `guia-dashboard-monitorizacion.md` |
| **Seguridad / gobernanza** | 01 → 08 → 03 (PII) → 06 (Actions) |
| **IA / AIP** | 01 → 05 → 06 → 13 → 10 |

---

## Convenciones de estos apuntes

- **Numeración** (`01-…`, `02-…`): orden de lectura sugerido y referencia rápida ("mira el 08").
- Cada documento incluye: índice, diagramas ASCII, tablas de errores comunes, **checklist** y **glosario rápido**.
- Los nombres internos de servicios (Magritte, Funnel, Phonograph, Gatekeeper…) no siempre aparecen en la documentación pública de Palantir; aquí se usan porque son los que aparecen en logs y conversaciones técnicas.
- Los `.md` se convierten automáticamente a `.docx` vía GitHub Actions (ver [README raíz](../../README.md)).

---

## Ideas para próximos apuntes

- [x] `12-contour-quiver-analisis-exploratorio.md` — Contour, Quiver y análisis ad hoc
- [x] `13-functions-typescript.md` — Functions en profundidad: testing, versionado, límites
- [x] `14-streaming-y-tiempo-real.md` — Streaming datasets, Kafka y casos near-real-time
- [ ] `15-organizacion-proyectos-y-naming.md` — Estructura de proyectos/carpetas, convenciones de nombres y ciclo de vida de recursos
- [ ] `16-slate-apps-custom.md` — Slate: cuándo compensa y cómo no convertirlo en deuda
- [ ] `17-data-health-y-monitorizacion-de-datos.md` — Health checks, Monitoring Views y SLAs de datos en profundidad
