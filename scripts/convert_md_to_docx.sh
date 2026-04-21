#!/usr/bin/env bash
# convert_md_to_docx.sh
#
# Converts all Markdown (*.md) files in this repository to .docx format using Pandoc.
# Output files are placed in a mirror of the original folder structure under <output_dir>.
#
# Usage:
#   ./scripts/convert_md_to_docx.sh [options]
#
# Options:
#   -o <dir>   Output directory (default: docx_output)
#   -r <file>  Pandoc reference .docx for custom styles (optional)
#   -t         Add a table of contents to every output document
#   -h         Show this help message
#
# Requirements:
#   - pandoc (https://pandoc.org/installing.html)
#
# Examples:
#   ./scripts/convert_md_to_docx.sh
#   ./scripts/convert_md_to_docx.sh -o /tmp/docx_output -t
#   ./scripts/convert_md_to_docx.sh -r reference.docx

set -euo pipefail

# ---------- defaults ----------
OUTPUT_DIR="docx_output"
REFERENCE_DOC=""
ADD_TOC=false
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ---------- parse arguments ----------
while getopts "o:r:th" opt; do
  case "$opt" in
    o) OUTPUT_DIR="$OPTARG" ;;
    r) REFERENCE_DOC="$OPTARG" ;;
    t) ADD_TOC=true ;;
    h)
      sed -n '2,/^[^#]/{ /^#/{ s/^# \{0,1\}//; p } }' "$0"
      exit 0
      ;;
    *) echo "Unknown option: -$OPTARG" >&2; exit 1 ;;
  esac
done

# ---------- sanity checks ----------
if ! command -v pandoc &>/dev/null; then
  echo "ERROR: pandoc is not installed or not in PATH." >&2
  echo "Install it from https://pandoc.org/installing.html" >&2
  exit 1
fi

if [[ -n "$REFERENCE_DOC" && ! -f "$REFERENCE_DOC" ]]; then
  echo "ERROR: reference doc not found: $REFERENCE_DOC" >&2
  exit 1
fi

# ---------- build pandoc flags ----------
PANDOC_FLAGS=()
[[ "$ADD_TOC" == true ]] && PANDOC_FLAGS+=("--toc")
[[ -n "$REFERENCE_DOC" ]] && PANDOC_FLAGS+=("--reference-doc=$REFERENCE_DOC")

# ---------- discover markdown files ----------
mapfile -t MD_FILES < <(find "$REPO_ROOT" -name "*.md" -not -path "*/.git/*" | sort)

if [[ ${#MD_FILES[@]} -eq 0 ]]; then
  echo "No Markdown files found in $REPO_ROOT"
  exit 0
fi

echo "Found ${#MD_FILES[@]} Markdown file(s). Converting to DOCX…"
echo "Output directory: $OUTPUT_DIR"
echo ""

CONVERTED=0
FAILED=0

for MD_FILE in "${MD_FILES[@]}"; do
  # Compute relative path from repo root
  REL_PATH="${MD_FILE#$REPO_ROOT/}"
  # Replace .md extension with .docx
  DOCX_REL="${REL_PATH%.md}.docx"
  DOCX_FILE="$OUTPUT_DIR/$DOCX_REL"

  # Create output subdirectory if needed
  mkdir -p "$(dirname "$DOCX_FILE")"

  if pandoc "$MD_FILE" -o "$DOCX_FILE" "${PANDOC_FLAGS[@]}" 2>/dev/null; then
    echo "  [OK]  $REL_PATH  →  $DOCX_REL"
    (( CONVERTED++ )) || true
  else
    echo "  [FAIL] $REL_PATH" >&2
    (( FAILED++ )) || true
  fi
done

echo ""
echo "Done. Converted: $CONVERTED  Failed: $FAILED"
[[ $FAILED -gt 0 ]] && exit 1 || exit 0
