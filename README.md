# noname

## Documentación

- [📚 Apuntes de Palantir Foundry](docs/foundry/README.md)

## Conversión Markdown → DOCX

Este repositorio incluye scripts para convertir todos los ficheros `.md` a
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