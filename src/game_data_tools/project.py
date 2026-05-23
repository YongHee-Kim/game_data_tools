"""Project — entry point that ties config, conversion, and IO together."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import config as _config
from . import schema
from .config import Config, WorkbookSpec
from .worksheet import JSONWorksheet


@dataclass
class ExportResult:
    """Outcome of converting one workbook from xlsx to its `out` files."""

    workbook: str
    written: list[Path]
    skipped: list[Path]
    errors: list[tuple[str, Exception]]


@dataclass
class ImportResult:
    """Outcome of rewriting one workbook from its converted .json files."""

    workbook: str
    xlsx_path: Path
    sheets: list[str]
    errors: list[tuple[str, Exception]]


class Project:
    """Loads a project from a directory containing ``config.json``."""

    def __init__(self, root: Path | str):
        self.config: Config = _config.load(root)

    @property
    def root(self) -> Path:
        return self.config.root

    def export(self, name: str | None = None, *, strict: bool = False) -> list[ExportResult]:
        """Export one or every configured workbook from xlsx to its `out` files."""
        workbooks: Iterable[WorkbookSpec]
        if name is None:
            workbooks = self.config.workbooks
        else:
            workbooks = [self.config.workbook(name)]

        results: list[ExportResult] = []
        for wb in workbooks:
            try:
                results.append(self._export_workbook(wb, strict=strict))
            except Exception as exc:
                if strict:
                    raise
                results.append(
                    ExportResult(
                        workbook=wb.filename,
                        written=[],
                        skipped=[],
                        errors=[(wb.filename, exc)],
                    )
                )
        return results

    def import_json(self, name: str, *, strict: bool = False) -> ImportResult:
        """Rewrite one workbook's .xlsx from the converted .json files on disk."""
        wb_spec = self.config.workbook(name)
        xlsx_path = self.config.environment.xlsx / wb_spec.filename

        written_sheets: list[str] = []
        errors: list[tuple[str, Exception]] = []

        for ws_spec in wb_spec.worksheets:
            json_path = self.config.environment.out / ws_spec.out
            try:
                if json_path.suffix.lower() != ".json":
                    raise ValueError(
                        f"json -> xlsx only supports .json sources; got {json_path.name}"
                    )
                ws = JSONWorksheet.from_json(json_path, sheet_name=ws_spec.name)
                start_line = int(ws_spec.kwargs.get("start_line", 1))
                ws.write_xlsx(xlsx_path, start_line=start_line)
                written_sheets.append(ws_spec.name)
            except Exception as exc:
                if strict:
                    raise
                errors.append((ws_spec.name, exc))

        return ImportResult(
            workbook=wb_spec.filename,
            xlsx_path=xlsx_path,
            sheets=written_sheets,
            errors=errors,
        )

    def _export_workbook(self, wb: WorkbookSpec, *, strict: bool) -> ExportResult:
        xlsx_path = self.config.environment.xlsx / wb.filename
        if not xlsx_path.is_file():
            raise FileNotFoundError(f"workbook not found: {xlsx_path}")

        written: list[Path] = []
        skipped: list[Path] = []
        errors: list[tuple[str, Exception]] = []

        for ws_spec in wb.worksheets:
            out_path = self.config.environment.out / ws_spec.out
            try:
                ws = JSONWorksheet.read(xlsx_path, ws_spec.name, **ws_spec.kwargs)
                if self.config.environment.jsonschema is not None:
                    schema.validate(
                        self.config.environment.jsonschema, ws_spec.out, ws.rows
                    )
                changed = ws.write(out_path)
                (written if changed else skipped).append(out_path)
            except Exception as exc:
                if strict:
                    raise
                errors.append((ws_spec.name, exc))

        return ExportResult(
            workbook=wb.filename,
            written=written,
            skipped=skipped,
            errors=errors,
        )
