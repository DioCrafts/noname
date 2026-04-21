# Markdown → DOCX Conversion

This repository includes scripts to convert all Markdown (`*.md`) files to
Microsoft Word (`.docx`) format using [Pandoc](https://pandoc.org/).

---

## Why Pandoc (and not markitdown)?

[microsoft/markitdown](https://github.com/microsoft/markitdown) is a tool that
converts **other formats → Markdown** (PDF, Word, Excel, PowerPoint, HTML, …).
It works in the **opposite direction** from what is needed here.  
markitdown has **no Markdown → DOCX output capability**, so it is not suitable
for this task.

**Pandoc** is the industry-standard converter that handles Markdown → DOCX with
excellent fidelity: headings, tables, lists, footnotes, code blocks, images, and
YAML front-matter metadata are all preserved. It also accepts a custom
`reference.docx` file so the output matches any Word style guide.

---

## Requirements

| Tool | Install |
|------|---------|
| **Pandoc ≥ 2.x** | [pandoc.org/installing.html](https://pandoc.org/installing.html) — available via `apt`, `brew`, `winget`, or the official installer |
| **Python ≥ 3.8** | Only required for the Python script; standard library only, no extra packages |

Verify the installation:

```bash
pandoc --version
```

---

## Scripts

| Script | Language | Notes |
|--------|----------|-------|
| `scripts/convert_md_to_docx.sh` | Bash | Linux / macOS |
| `scripts/convert_md_to_docx.py` | Python 3 | Cross-platform (Linux, macOS, Windows) |

Both scripts produce identical output and accept the same options.

---

## Quick start

### Bash (Linux / macOS)

```bash
# Make the script executable (first time only)
chmod +x scripts/convert_md_to_docx.sh

# Convert all .md files → docx_output/
./scripts/convert_md_to_docx.sh
```

### Python (cross-platform)

```bash
python3 scripts/convert_md_to_docx.py
```

---

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o <dir>` / `--output-dir` | Directory where `.docx` files are written | `docx_output` |
| `-r <file>` / `--reference-doc` | Pandoc reference `.docx` for custom Word styles | _(none)_ |
| `-t` / `--toc` | Add a table of contents to every document | off |
| `-h` / `--help` | Show help | — |

---

## Examples

```bash
# Default: output to ./docx_output/
./scripts/convert_md_to_docx.sh

# Custom output directory
./scripts/convert_md_to_docx.sh -o /tmp/my_docs

# With table of contents
./scripts/convert_md_to_docx.sh -t

# With a reference .docx for custom Word styles
./scripts/convert_md_to_docx.sh -r reference.docx

# Combine options
./scripts/convert_md_to_docx.sh -o /tmp/my_docs -r reference.docx -t

# Python equivalent
python3 scripts/convert_md_to_docx.py -o /tmp/my_docs -r reference.docx --toc
```

---

## Output structure

The original folder hierarchy is mirrored inside the output directory:

```
docx_output/
├── README.docx
├── foundry_guide.docx
├── post-mortem-doc1.docx
└── docs/
    └── foundry/
        ├── README.docx
        ├── 01-palantir-foundry-componentes.docx
        ├── 02-glosario-foundry.docx
        └── …
```

---

## Custom Word styles (reference.docx)

For professional-looking output, create a `reference.docx` with the Word styles
you want (Heading 1-3, Normal, Code, Block Quote, etc.) and pass it with `-r`:

```bash
# Generate a default reference template to customise
pandoc --print-default-data-file reference.docx > reference.docx

# Then open reference.docx in Word, edit styles, save, and use it:
./scripts/convert_md_to_docx.sh -r reference.docx
```

---

## Excluding the output directory

`docx_output/` is already listed in `.gitignore` so generated `.docx` files are
not committed to the repository.
