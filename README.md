# Documentación técnica — Palantir Foundry

Repositorio de documentación interna del equipo sobre **Palantir Foundry**: apuntes por temática, una guía práctica completa y un post-mortem real. Escrito en lenguaje claro para que cualquier miembro del equipo pueda entenderlo, sin asumir experiencia previa con la plataforma.

## ¿Qué hay aquí?

| Recurso | Qué es | Empieza aquí si… |
|---|---|---|
| [📚 Apuntes de Foundry](docs/foundry/README.md) | 14 documentos numerados que cubren la plataforma completa: componentes, ingesta, pipelines, Ontología, apps, análisis, Functions, streaming, seguridad, infraestructura, IA y troubleshooting. Incluye rutas de lectura por rol. | …eres nuevo o quieres profundizar en un área concreta. |
| [📊 guia-dashboard-monitorizacion.md](guia-dashboard-monitorizacion.md) | Guía completa (referencia + paso a paso) para construir un **dashboard de monitorización de la plataforma** en Workshop: datasets, Ontología, Functions, Data Health, Automations y un copiloto AIP. | …vas a montar el dashboard de monitorización o quieres un ejemplo realista de app end-to-end. |
| [🔥 post-mortem-2026-04-ontologia-highbury.md](post-mortem-2026-04-ontologia-highbury.md) | Post-mortem real (abril 2026): degradación severa de la Ontología on-prem por co-location de nodos Highbury y discos sin RAID 0. | …operas Foundry on-prem o quieres aprender de un incidente real. |
| [📝 Plantilla de post-mortem](docs/plantillas/plantilla-post-mortem.md) | Plantilla lista para copiar, con la misma estructura que el post-mortem real, para documentar el próximo incidente. | …acabas de gestionar un incidente y toca escribirlo. |

**¿Por dónde empiezo?** Lee el [índice de apuntes](docs/foundry/README.md): tiene una ruta de onboarding de ~45 minutos y rutas específicas por rol (data engineer, app builder, plataforma/SRE, seguridad, IA).

## Conversión Markdown → DOCX

El repositorio incluye scripts para convertir todos los ficheros `.md` a
formato Word (`.docx`) usando [Pandoc](https://pandoc.org/).

```bash
# Bash (Linux / macOS)
chmod +x scripts/convert_md_to_docx.sh
./scripts/convert_md_to_docx.sh

# Python (multiplataforma)
python3 scripts/convert_md_to_docx.py
```

Los ficheros `.docx` se generan en `docx_output/`, respetando la estructura de
carpetas del repositorio. Consulta [docs/DOCX_CONVERSION.md](docs/DOCX_CONVERSION.md)
para opciones avanzadas (estilos personalizados, tabla de contenidos, etc.).

### GitHub Actions (automático)

El repositorio incluye un workflow que convierte los `.md` y sube los `.docx`
como **artifact** descargable. No es necesario tener Pandoc instalado.

- Se ejecuta automáticamente al hacer push de ficheros `.md` o los scripts.
- También puede lanzarse manualmente desde la pestaña **Actions**.
- Los artifacts están disponibles durante **30 días** tras cada ejecución.

Consulta [docs/DOCX_CONVERSION.md#github-actions-workflow](docs/DOCX_CONVERSION.md#github-actions-workflow)
para más detalles.

## Convenciones para contribuir

- Los apuntes viven en `docs/foundry/` con prefijo numérico (`NN-tema.md`) que marca el orden de lectura.
- Cada documento sigue la misma plantilla: cabecera con "para quién" y fecha, índice, diagramas ASCII, tablas de errores comunes, checklist y glosario rápido.
- Al añadir un documento: registrarlo en la tabla de [docs/foundry/README.md](docs/foundry/README.md) y enlazarlo desde los documentos relacionados.
- Al renombrar un fichero: actualizar los enlaces (`grep -rn "nombre-antiguo" .`) — los demás docs lo referencian.
