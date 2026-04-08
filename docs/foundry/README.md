# 📚 Apuntes de Palantir Foundry

> Colección de documentación técnica sobre Palantir Foundry, organizada por temática.

---

## Documentos disponibles

| Documento | Descripción |
|---|---|
| [palantir-foundry-componentes.md](palantir-foundry-componentes.md) | Mapa completo de todos los componentes y servicios de Foundry, organizados por capas arquitectónicas. Punto de entrada recomendado. |
| [ontologia-foundry.md](ontologia-foundry.md) | Guía completa de la Ontología: Object Types, Link Types, Actions, Functions, Phonograph, OSS y el flujo semántico de datos. |
| [data-integration-magritte.md](data-integration-magritte.md) | Integración de fuentes externas con Magritte (Data Connection): Agents, conectores, modos de sincronización, PII masking y troubleshooting. |
| [pipelines-y-transformaciones.md](pipelines-y-transformaciones.md) | Diseño y operación de pipelines: Pipeline Builder, Code Repositories, Code Workbooks, ejecución incremental, calidad, Spark y alimentación de la Ontología. |
| [seguridad-y-gobernanza.md](seguridad-y-gobernanza.md) | Modelo de identidad (Multipass/SSO), autorización (Gatekeeper, RBAC/ABAC/PBAC), permisos por recurso, markings, gobernanza de datasets y patrones de seguridad para pipelines. |
| [apollo-infraestructura.md](apollo-infraestructura.md) | Apollo (CD/orquestación), relación con Rubix/OpenShift/Kubernetes, ciclo de vida de despliegues, Skylab (config/feature flags), consideraciones on-prem (TLS, proxies, air-gapped) y operaciones con Monocle. |

---

## Orden de estudio recomendado

```
1. palantir-foundry-componentes.md   ← Empieza aquí (visión general)
         │
         ▼
2. ontologia-foundry.md              ← El concepto más diferenciador
         │
         ▼
3. data-integration-magritte.md      ← Cómo entran los datos
         │
         ▼
4. pipelines-y-transformaciones.md   ← Cómo se transforman los datos
         │
         ▼
5. seguridad-y-gobernanza.md         ← Cómo se protegen y gobiernan
         │
         ▼
6. apollo-infraestructura.md         ← Cómo se despliega y opera
```

---

## Próximos apuntes previstos

- [x] `pipelines-y-transformaciones.md` — Code Repositories, Spark, Build, Pipeline Builder
- [x] `seguridad-y-gobernanza.md` — Gatekeeper, Multipass, markings, permisos
- [x] `apollo-infraestructura.md` — Apollo, Rubix, Skylab y despliegue on-prem
- [ ] `workshop-apps-operativas.md` — Construcción de aplicaciones con Workshop
- [ ] `aip-llms-ontologia.md` — Integración de LLMs con AIP sobre la Ontología
- [ ] `flujo-datos-end-to-end.md` — Caso práctico completo de extremo a extremo
