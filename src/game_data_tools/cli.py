"""Command-line interface: ``gdt <command> <project> [...]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import Project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gdt", description="Game data tools.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_convert = sub.add_parser("convert", help="xlsx -> json/csv/tsv")
    p_convert.add_argument("project", type=Path, help="path to project directory or config.json")
    p_convert.add_argument("--file", help="workbook filename or stem; default: all")
    p_convert.add_argument("--strict", action="store_true", help="fail fast on first error")

    p_to_xlsx = sub.add_parser("to-xlsx", help="json -> xlsx (round trip)")
    p_to_xlsx.add_argument("project", type=Path)
    p_to_xlsx.add_argument("--file", required=True, help="workbook filename or stem")

    args = parser.parse_args(argv)

    if args.command == "convert":
        return _cmd_convert(args)
    if args.command == "to-xlsx":
        return _cmd_to_xlsx(args)
    parser.error(f"unknown command {args.command!r}")
    return 2


def _cmd_convert(args: argparse.Namespace) -> int:
    project = Project(args.project)
    results = project.export(args.file, strict=args.strict)

    total_written = total_skipped = total_errors = 0
    for r in results:
        print(f"[{r.workbook}]")
        for p in r.written:
            print(f"  SAVE => {p}")
        for p in r.skipped:
            print(f"   n/a => {p}")
        for sheet, exc in r.errors:
            print(f"  FAIL => {sheet}: {exc}", file=sys.stderr)
        total_written += len(r.written)
        total_skipped += len(r.skipped)
        total_errors += len(r.errors)

    print(
        f"\nDONE: {total_written} written, {total_skipped} unchanged, {total_errors} failed",
        file=sys.stderr if total_errors else sys.stdout,
    )
    return 1 if total_errors else 0


def _cmd_to_xlsx(args: argparse.Namespace) -> int:
    project = Project(args.project)
    result = project.import_json(args.file)

    print(f"[{result.workbook}]")
    for sheet in result.sheets:
        print(f"  WRITE => {result.xlsx_path}::{sheet}")
    for sheet, exc in result.errors:
        print(f"  FAIL  => {sheet}: {exc}", file=sys.stderr)

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
