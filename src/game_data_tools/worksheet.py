"""In-memory representation of a converted Excel worksheet, with IO methods.

A ``JSONWorksheet`` carries the columns, row objects, and source metadata for one
sheet. It can be constructed from an Excel sheet via ``JSONWorksheet.read`` or from
a converted JSON file via ``JSONWorksheet.from_json``, and written back via
``.write`` (json/csv/tsv) or ``.write_xlsx`` (xlsx round trip).

Implemented subset of XLSXasJSON behavior:
- Row-oriented sheets with a header row at ``start_line``.
- Column names that are JSONPointers nest values in the emitted object.
- Cells containing ``delim`` are split into arrays.

Column-oriented sheets, ``squeeze``, and full object-array cell syntax are not yet
implemented — they raise ``NotImplementedError`` so callers fail loudly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import pointer


DEFAULT_DELIM = ";"


@dataclass
class JSONWorksheet:
    """Converted form of a single worksheet."""

    source: Path
    sheet_name: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)

    def __iter__(self) -> Iterable[dict[str, Any]]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    # ---- read paths --------------------------------------------------------

    @classmethod
    def read(
        cls,
        xlsx_path: Path,
        sheet_name: str,
        **kwargs: Any,
    ) -> "JSONWorksheet":
        """Open ``xlsx_path`` and read one sheet. For batched multi-sheet runs,
        open a ``JSONWorkbook`` once and call ``read_sheet`` per sheet instead."""
        from .workbook import JSONWorkbook

        with JSONWorkbook.open_for_read(xlsx_path) as jwb:
            return jwb.read_sheet(sheet_name, **kwargs)

    @classmethod
    def _read_from_workbook(
        cls,
        wb: Any,
        source: Path,
        sheet_name: str,
        *,
        start_line: int = 1,
        row_oriented: bool = True,
        squeeze: bool = False,
        delim: str = DEFAULT_DELIM,
        omit_null_object: bool = False,
        empty_value: dict[str, Any] | None = None,
    ) -> "JSONWorksheet":
        """Read one sheet out of an already-open openpyxl workbook.

        These keyword arguments are exactly the per-worksheet ``kwargs`` from
        ``config.json``; see the package overview for worked examples of each.

        :param start_line: 1-based row holding the column headers; rows above it
            are skipped and data begins on the following row.
        :param row_oriented: ``True`` reads a row-per-record sheet (the only mode
            implemented). ``False`` (column-oriented) raises ``NotImplementedError``.
        :param squeeze: collapse all rows into a single object. *Planned* —
            raises ``NotImplementedError``.
        :param delim: delimiter (string or regex source) used to split a cell into
            an array; matching cells become lists of coerced scalars.
        :param omit_null_object: drop array elements whose fields are all null.
            *Planned* — raises ``NotImplementedError``.
        :param empty_value: per-column replacement for empty cells, keyed by column
            name or pointer; unlisted columns default empty cells to ``None``.
        :raises NotImplementedError: when a not-yet-supported option is requested.
        :raises KeyError: when ``sheet_name`` is absent from the workbook.
        """
        if not row_oriented:
            raise NotImplementedError("column-oriented sheets are not yet supported")
        if squeeze:
            raise NotImplementedError("squeeze is not yet supported")
        if omit_null_object:
            raise NotImplementedError("omit_null_object is not yet supported")

        if sheet_name not in wb.sheetnames:
            raise KeyError(f"worksheet {sheet_name!r} not found in {Path(source).name}")
        ws = wb[sheet_name]

        rows_iter = ws.iter_rows(values_only=True)
        for _ in range(start_line - 1):
            next(rows_iter, None)

        header_row = next(rows_iter, None)
        if header_row is None:
            return cls(source=source, sheet_name=sheet_name)

        columns = [str(c) for c in header_row if c is not None and str(c).strip()]
        delim_re = re.compile(re.escape(delim)) if isinstance(delim, str) else re.compile(delim)
        empty_value = empty_value or {}

        rows: list[dict[str, Any]] = []
        for raw_row in rows_iter:
            if raw_row is None or all(v is None for v in raw_row):
                continue
            obj: dict[str, Any] = {}
            for col, value in zip(columns, raw_row):
                converted = _convert_cell(value, delim_re)
                if converted is None and col in empty_value:
                    converted = empty_value[col]
                pointer.set_in(obj, pointer.normalize(col), converted)
            rows.append(obj)

        return cls(source=source, sheet_name=sheet_name, columns=columns, rows=rows)

    @classmethod
    def from_json(
        cls,
        json_path: Path,
        *,
        sheet_name: str | None = None,
    ) -> "JSONWorksheet":
        """Load a converted .json file back into a worksheet.

        Column order is derived by walking the rows depth-first: top-level scalar
        keys appear as bare names (``Key``), nested keys as JSONPointers
        (``/character/stats/hp``).
        """
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{json_path}: expected a JSON array of rows")
        for i, row in enumerate(data):
            if not isinstance(row, dict):
                raise ValueError(f"{json_path}: row {i} is not an object")

        columns: dict[str, None] = {}
        for row in data:
            _collect_columns(row, "", columns)

        return cls(
            source=json_path,
            sheet_name=sheet_name or json_path.stem,
            columns=list(columns.keys()),
            rows=data,
        )

    # ---- write paths -------------------------------------------------------

    def write(self, out_path: Path) -> bool:
        """Write this worksheet to ``out_path``. Returns True if the file was actually written.

        Format is chosen from ``out_path.suffix``: ``.json``, ``.csv``, ``.tsv``.
        Skips the write when the rendered payload matches existing file contents.
        """
        suffix = out_path.suffix.lower()
        if suffix == ".json":
            payload = json.dumps(self.rows, indent=2, ensure_ascii=False)
        elif suffix == ".csv":
            payload = self._delimited(",")
        elif suffix == ".tsv":
            payload = self._delimited("\t")
        else:
            raise ValueError(f"unsupported output extension {suffix!r}; use .json, .csv, or .tsv")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.is_file() and out_path.read_text(encoding="utf-8") == payload:
            return False
        out_path.write_text(payload, encoding="utf-8")
        return True

    def write_xlsx(self, xlsx_path: Path, *, start_line: int = 1) -> None:
        """Write this worksheet into an .xlsx file at sheet ``self.sheet_name``.

        Creates the workbook if it does not exist; if it does, replaces the matching
        sheet (or adds it) and preserves other sheets. Header lands on row
        ``start_line`` so callers can mirror the original sheet's layout.
        """
        from .workbook import JSONWorkbook

        if not self.sheet_name:
            raise ValueError("JSONWorksheet.sheet_name is required to write xlsx")
        xlsx_path.parent.mkdir(parents=True, exist_ok=True)

        with JSONWorkbook.open_for_write(xlsx_path) as jwb:
            jwb.write_sheet(self, start_line=start_line)
            jwb.save()

    def _write_to_workbook(self, wb: Any, *, start_line: int = 1) -> None:
        """Replace (or add) ``self.sheet_name`` inside an already-open workbook."""
        if not self.sheet_name:
            raise ValueError("JSONWorksheet.sheet_name is required to write xlsx")

        if self.sheet_name in wb.sheetnames:
            del wb[self.sheet_name]
        sheet = wb.create_sheet(self.sheet_name)

        for _ in range(start_line - 1):
            sheet.append([])
        sheet.append(self.columns)
        for row in self.rows:
            sheet.append([_encode_cell(pointer.get_at(row, c)) for c in self.columns])

    def _delimited(self, delim: str) -> str:
        lines = [delim.join(self.columns)]
        for row in self.rows:
            lines.append(delim.join(_format_cell(row.get(c)) for c in self.columns))
        return "\n".join(lines)


# ---- helpers ---------------------------------------------------------------


def _convert_cell(value: Any, delim_re: re.Pattern[str]) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if delim_re.search(stripped):
            return [_coerce_scalar(part.strip()) for part in delim_re.split(stripped)]
        return _coerce_scalar(stripped)
    return value


def _coerce_scalar(text: str) -> Any:
    if text == "":
        return None
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "none"):
        return None
    try:
        if "." in text or "e" in lowered:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "[" + ";".join(_format_cell(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ";".join(f'"{k}":{_format_cell(v)}' for k, v in value.items()) + "}"
    return str(value)


def _encode_cell(value: Any, delim: str = DEFAULT_DELIM) -> Any:
    """Encode a python value into a single xlsx cell.

    Arrays become ``a;b;c`` so the reader's ``delim`` split recovers them.
    Nested objects fall back to JSON (no current round-trip; reader does not
    parse object cells).
    """
    if value is None:
        return None
    if isinstance(value, list):
        return delim.join("" if v is None else str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def _collect_columns(obj: Any, prefix: str, out: dict[str, None]) -> None:
    """Depth-first walk of ``obj``'s keys, recording column names in first-seen order."""
    if not isinstance(obj, dict):
        return
    for k, v in obj.items():
        if isinstance(v, dict):
            _collect_columns(v, f"{prefix}/{k}", out)
        else:
            out.setdefault(k if not prefix else f"{prefix}/{k}", None)
