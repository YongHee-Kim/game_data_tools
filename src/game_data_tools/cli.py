"""Command-line interface: ``gdt <command> <project> [...]``."""

from __future__ import annotations

import argparse
import cmd
import shlex
import sys
from pathlib import Path

from .project import ExportResult, ImportResult, Project


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

    p_shell = sub.add_parser("shell", help="open a persistent REPL for a project")
    p_shell.add_argument("project", type=Path, help="path to project directory or config.json")

    p_config = sub.add_parser("config", help="show resolved project config")
    p_config.add_argument("project", type=Path, help="path to project directory or config.json")
    p_config.add_argument("--file", help="workbook filename or stem; default: all")

    args = parser.parse_args(argv)

    if args.command == "convert":
        project = Project(args.project)
        return _run_convert(project, file=args.file, strict=args.strict)
    if args.command == "to-xlsx":
        project = Project(args.project)
        return _run_to_xlsx(project, file=args.file)
    if args.command == "shell":
        return _run_shell(args.project)
    if args.command == "config":
        project = Project(args.project)
        return _run_config(project, file=args.file)
    parser.error(f"unknown command {args.command!r}")
    return 2


def _run_convert(project: Project, *, file: str | None, strict: bool) -> int:
    results = project.export(file, strict=strict)

    total_written = total_skipped = total_errors = 0
    for r in results:
        _print_export_result(r)
        total_written += len(r.written)
        total_skipped += len(r.skipped)
        total_errors += len(r.errors)

    print(
        f"\nDONE: {total_written} written, {total_skipped} unchanged, {total_errors} failed",
        file=sys.stderr if total_errors else sys.stdout,
    )
    return 1 if total_errors else 0


def _run_to_xlsx(project: Project, *, file: str) -> int:
    result = project.import_json(file)
    _print_import_result(result)
    return 1 if result.errors else 0


def _run_config(project: Project, *, file: str | None = None) -> int:
    cfg = project.config
    print(f"name        : {cfg.name}")
    print(f"root        : {cfg.root}")
    print("environment :")
    for label, path in (
        ("xlsx", cfg.environment.xlsx),
        ("out", cfg.environment.out),
        ("localize", cfg.environment.localize),
        ("jsonschema", cfg.environment.jsonschema),
    ):
        if path is None:
            print(f"  {label:<10} = (none)")
        else:
            mark = "ok" if path.exists() else "MISSING"
            print(f"  {label:<10} = {path}  [{mark}]")

    loc = cfg.localization
    targets = ", ".join(loc.target_languages) or "(none)"
    print(f"localization: base={loc.base_language}  targets={targets}")

    if file is None:
        workbooks = cfg.workbooks
    else:
        try:
            workbooks = (cfg.workbook(file),)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    print(f"workbooks   : {len(workbooks)}")
    for wb in workbooks:
        xlsx_path = cfg.environment.xlsx / wb.filename
        mark = "ok" if xlsx_path.is_file() else "MISSING"
        print(f"  - {wb.filename}  [{mark}]  ({len(wb.worksheets)} sheets)")
        for ws in wb.worksheets:
            extras = f"  kwargs={ws.kwargs}" if ws.kwargs else ""
            loc_mark = "  loc" if ws.localize else ""
            print(f"      {ws.name:<24} -> {ws.out}{extras}{loc_mark}")
    return 0


def _print_export_result(r: ExportResult) -> None:
    print(f"[{r.workbook}]")
    for p in r.written:
        print(f"  SAVE => {p}")
    for p in r.skipped:
        print(f"   n/a => {p}")
    for sheet, exc in r.errors:
        print(f"  FAIL => {sheet}: {exc}", file=sys.stderr)


def _print_import_result(result: ImportResult) -> None:
    print(f"[{result.workbook}]")
    for sheet in result.sheets:
        print(f"  WRITE => {result.xlsx_path}::{sheet}")
    for sheet, exc in result.errors:
        print(f"  FAIL  => {sheet}: {exc}", file=sys.stderr)


def _run_shell(project_path: Path) -> int:
    try:
        project = Project(project_path)
    except Exception as exc:
        print(f"failed to load project: {exc}", file=sys.stderr)
        return 2
    GdtShell(project, project_path).cmdloop()
    return 0


class GdtShell(cmd.Cmd):
    intro = "gdt shell — type 'help' for commands, 'quit' to exit."
    prompt = "gdt> "

    def __init__(self, project: Project, project_path: Path):
        super().__init__()
        self.project = project
        self.project_path = project_path

    def do_convert(self, arg: str) -> None:
        """convert [--file NAME] [--strict] — xlsx -> json/csv/tsv."""
        parser = argparse.ArgumentParser(prog="convert", add_help=False)
        parser.add_argument("--file")
        parser.add_argument("--strict", action="store_true")
        ns = _safe_parse(parser, arg)
        if ns is None:
            return
        try:
            _run_convert(self.project, file=ns.file, strict=ns.strict)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)

    def do_to_xlsx(self, arg: str) -> None:
        """to_xlsx --file NAME — json -> xlsx (round trip)."""
        parser = argparse.ArgumentParser(prog="to-xlsx", add_help=False)
        parser.add_argument("--file", required=True)
        ns = _safe_parse(parser, arg)
        if ns is None:
            return
        try:
            _run_to_xlsx(self.project, file=ns.file)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)

    def do_config(self, arg: str) -> None:
        """config [--file NAME] — show the resolved project config."""
        parser = argparse.ArgumentParser(prog="config", add_help=False)
        parser.add_argument("--file")
        ns = _safe_parse(parser, arg)
        if ns is None:
            return
        try:
            _run_config(self.project, file=ns.file)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)

    def do_reload(self, arg: str) -> None:
        """reload — re-read config.json from disk."""
        try:
            self.project = Project(self.project_path)
            print(f"reloaded: {self.project_path}")
        except Exception as exc:
            print(f"failed to reload: {exc}", file=sys.stderr)

    def do_quit(self, arg: str) -> bool:
        """quit — exit the shell."""
        return True

    do_exit = do_quit
    do_EOF = do_quit

    def precmd(self, line: str) -> str:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("?") or stripped.startswith("!"):
            return line
        head, _, rest = stripped.partition(" ")
        return f"{head.replace('-', '_')} {rest}" if "-" in head else line

    def emptyline(self) -> None:
        pass

    def default(self, line: str) -> None:
        print(f"unknown command: {line.split()[0]!r} (try 'help')", file=sys.stderr)


def _safe_parse(parser: argparse.ArgumentParser, arg: str) -> argparse.Namespace | None:
    try:
        return parser.parse_args(shlex.split(arg))
    except SystemExit:
        return None
    except ValueError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    sys.exit(main())
