"""Sync DataAssets to/from spreadsheets through an `EngineAdapter`.

``xlsx_to_unreal`` pushes sheet rows onto matching assets collected via the
worksheet's ARFilter; ``unreal_to_xlsx`` pulls asset properties back into the
workbook. Both reuse the existing `JSONWorkbook`/`JSONWorksheet`/`pointer`
machinery and stay engine-agnostic by talking only to the adapter — so they are
unit-testable with a fake and never import ``unreal`` themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import pointer
from .config import WorkbookSpec, WorksheetSpec
from .engine import EngineAdapter, convert, get_adapter
from .project import Project
from .workbook import JSONWorkbook
from .worksheet import JSONWorksheet


@dataclass
class UnrealImportResult:
    """Outcome of pushing a workbook's rows onto Unreal assets."""

    workbook: str
    updated: list[str]
    missing: list[Any]
    errors: list[tuple[str, Exception]]


@dataclass
class UnrealExportResult:
    """Outcome of pulling Unreal assets into a workbook."""

    workbook: str
    written: list[Path]
    sheets: list[str]
    errors: list[tuple[str, Exception]]


def _unreal_worksheets(wb: WorkbookSpec) -> list[WorksheetSpec]:
    return [ws for ws in wb.worksheets if ws.unreal is not None]


def xlsx_to_unreal(
    project: Project,
    file: str,
    *,
    adapter: EngineAdapter | None = None,
    strict: bool = False,
) -> UnrealImportResult:
    """Read ``file``'s sheets and set properties on the assets each row matches.

    Rows whose key has no matching asset are collected in ``missing`` (v1 never
    creates or deletes assets). Per-sheet failures are collected unless ``strict``.
    """
    wb = project.config.workbook(file)
    adapter = adapter or get_adapter(project.config)
    xlsx_path = project.config.environment.xlsx / wb.filename

    updated: list[str] = []
    missing: list[Any] = []
    errors: list[tuple[str, Exception]] = []

    with JSONWorkbook.open_for_read(xlsx_path) as jwb:
        for ws_spec in _unreal_worksheets(wb):
            spec = ws_spec.unreal
            assert spec is not None  # guaranteed by _unreal_worksheets
            try:
                ws = jwb.read_sheet(ws_spec.name, **ws_spec.kwargs)
                index = {
                    adapter.asset_key(a, spec.key_property): a
                    for a in adapter.find_assets(spec.asset_filter)
                }
                with adapter.transaction(f"xlsx_to_unreal: {ws_spec.name}"):
                    for row in ws.rows:
                        key = pointer.get_at(row, pointer.normalize(spec.key_column))
                        asset = index.get(key)
                        if asset is None:
                            missing.append(key)
                            continue
                        _apply_row(adapter, asset, row, spec.properties)
                        if spec.save:
                            adapter.save(asset)
                        updated.append(str(key))
            except Exception as exc:
                if strict:
                    raise
                errors.append((ws_spec.name, exc))

    return UnrealImportResult(wb.filename, updated, missing, errors)


def unreal_to_xlsx(
    project: Project,
    file: str,
    *,
    adapter: EngineAdapter | None = None,
    strict: bool = False,
) -> UnrealExportResult:
    """Collect each unreal-mapped sheet's assets and write them into the workbook."""
    wb = project.config.workbook(file)
    adapter = adapter or get_adapter(project.config)
    xlsx_path = project.config.environment.xlsx / wb.filename
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    sheets: list[str] = []
    errors: list[tuple[str, Exception]] = []

    with JSONWorkbook.open_for_write(xlsx_path) as jwb:
        for ws_spec in _unreal_worksheets(wb):
            try:
                ws = _collect_worksheet(adapter, ws_spec, xlsx_path)
                jwb.write_sheet(ws, start_line=int(ws_spec.kwargs.get("start_line", 1)))
                sheets.append(ws_spec.name)
            except Exception as exc:
                if strict:
                    raise
                errors.append((ws_spec.name, exc))
        if sheets:
            jwb.save()
            written.append(xlsx_path)

    return UnrealExportResult(wb.filename, written, sheets, errors)


def _apply_row(
    adapter: EngineAdapter,
    asset: Any,
    row: dict[str, Any],
    properties: dict[str, str],
) -> None:
    for column, ue_path in properties.items():
        if convert.is_sentinel(ue_path):
            continue  # identity columns (asset name/path) are read-only on import
        value = pointer.get_at(row, pointer.normalize(column))
        adapter.set_property(asset, convert.property_path(ue_path), convert.to_engine(value))


def _collect_worksheet(
    adapter: EngineAdapter,
    ws_spec: WorksheetSpec,
    source: Path,
) -> JSONWorksheet:
    spec = ws_spec.unreal
    assert spec is not None
    columns = list(spec.properties.keys())
    rows: list[dict[str, Any]] = []
    for asset in adapter.find_assets(spec.asset_filter):
        row: dict[str, Any] = {}
        for column, ue_path in spec.properties.items():
            if convert.is_sentinel(ue_path):
                value = adapter.asset_key(asset, ue_path)
            else:
                value = convert.from_engine(
                    adapter.get_property(asset, convert.property_path(ue_path))
                )
            pointer.set_in(row, pointer.normalize(column), value)
        rows.append(row)
    return JSONWorksheet(source=source, sheet_name=ws_spec.name, columns=columns, rows=rows)
