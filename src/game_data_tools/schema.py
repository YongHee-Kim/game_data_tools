"""JSON Schema validation against ``<jsonschema>/<out_basename>.json``.

The lookup name matches the converted file's basename (with ``.json``), so a sheet
exported to ``Items_Weapon.json`` is validated against ``<jsonschema_dir>/Items_Weapon.json``
when that schema exists. Missing schemas are silently skipped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as _SchemaError


class SchemaError(ValueError):
    pass


def schema_path(schema_dir: Path, out_basename: str) -> Path:
    """Resolve the schema file for a given output basename (with or without extension)."""
    stem = Path(out_basename).stem
    return schema_dir / f"{stem}.json"


def validate(schema_dir: Path, out_basename: str, data: Any) -> bool:
    """Validate ``data`` against the schema for ``out_basename``.

    Returns True if a schema was found and applied, False if no schema exists.
    Raises SchemaError on validation failure or malformed schema.
    """
    path = schema_path(schema_dir, out_basename)
    if not path.is_file():
        return False

    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
    except (json.JSONDecodeError, _SchemaError) as exc:
        raise SchemaError(f"invalid schema at {path}: {exc}") from exc

    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        lines = [f"{path.name} validation failed ({len(errors)} error(s)):"]
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            lines.append(f"  - {loc}: {err.message}")
        raise SchemaError("\n".join(lines))
    return True
