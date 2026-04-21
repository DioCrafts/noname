#!/usr/bin/env python3
"""
convert_md_to_docx.py
=====================
Cross-platform script that converts all Markdown (*.md) files in this
repository to .docx format using Pandoc.

Output files mirror the original folder structure under <output_dir>.

Usage
-----
    python3 scripts/convert_md_to_docx.py [options]

Options
-------
    -o, --output-dir <dir>    Output directory (default: docx_output)
    -r, --reference-doc <file> Pandoc reference .docx for custom styles
    -t, --toc                  Add a table of contents to every output document
    -h, --help                 Show this help message

Requirements
------------
    Pandoc must be installed: https://pandoc.org/installing.html

Examples
--------
    python3 scripts/convert_md_to_docx.py
    python3 scripts/convert_md_to_docx.py -o /tmp/docx -t
    python3 scripts/convert_md_to_docx.py -r reference.docx
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert all Markdown files in the repository to DOCX using Pandoc.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="docx_output",
        help="Directory where .docx files will be written (default: docx_output)",
    )
    parser.add_argument(
        "-r", "--reference-doc",
        default=None,
        help="Path to a Pandoc reference .docx file for custom Word styles",
    )
    parser.add_argument(
        "-t", "--toc",
        action="store_true",
        help="Insert a table of contents in every output document",
    )
    return parser.parse_args()


def check_pandoc() -> None:
    if shutil.which("pandoc") is None:
        print(
            "ERROR: pandoc is not installed or not in PATH.\n"
            "Install it from https://pandoc.org/installing.html",
            file=sys.stderr,
        )
        sys.exit(1)


def find_md_files(repo_root: Path) -> list[Path]:
    return sorted(
        p for p in repo_root.rglob("*.md") if ".git" not in p.parts
    )


def convert(
    md_file: Path,
    repo_root: Path,
    output_dir: Path,
    reference_doc: Path | None,
    add_toc: bool,
) -> bool:
    rel_path = md_file.relative_to(repo_root)
    docx_rel = rel_path.with_suffix(".docx")
    docx_file = output_dir / docx_rel

    docx_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["pandoc", str(md_file), "-o", str(docx_file)]
    if add_toc:
        cmd.append("--toc")
    if reference_doc:
        cmd.append(f"--reference-doc={reference_doc}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [OK]   {rel_path}  →  {docx_rel}")
        return True
    else:
        print(f"  [FAIL] {rel_path}: {result.stderr.strip()}", file=sys.stderr)
        return False


def main() -> None:
    args = parse_args()
    check_pandoc()

    repo_root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output_dir).resolve()
    reference_doc = Path(args.reference_doc).resolve() if args.reference_doc else None

    if reference_doc and not reference_doc.is_file():
        print(f"ERROR: reference doc not found: {reference_doc}", file=sys.stderr)
        sys.exit(1)

    md_files = find_md_files(repo_root)
    if not md_files:
        print(f"No Markdown files found in {repo_root}")
        sys.exit(0)

    print(f"Found {len(md_files)} Markdown file(s). Converting to DOCX…")
    print(f"Output directory: {output_dir}\n")

    converted = 0
    failed = 0
    for md_file in md_files:
        if convert(md_file, repo_root, output_dir, reference_doc, args.toc):
            converted += 1
        else:
            failed += 1

    print(f"\nDone. Converted: {converted}  Failed: {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
