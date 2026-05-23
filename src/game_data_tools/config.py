"""Load and resolve config.json for a project."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Environment:
    xlsx: Path
    out: Path
    localize: Path | None
    jsonschema: Path | None


@dataclass(frozen=True)
class WorksheetSpec:
    name: str
    out: str
    localize: dict[str, Any] | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkbookSpec:
    filename: str
    worksheets: tuple[WorksheetSpec, ...]


@dataclass(frozen=True)
class Localization:
    base_language: str = "kr"
    target_languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    name: str
    root: Path
    environment: Environment
    localization: Localization
    workbooks: tuple[WorkbookSpec, ...]

    def workbook(self, name_or_stem: str) -> WorkbookSpec:
        """Look up a workbook by filename or stem (case-insensitive)."""
        target = name_or_stem.lower()
        for wb in self.workbooks:
            if wb.filename.lower() == target or Path(wb.filename).stem.lower() == target:
                return wb
        raise KeyError(f"no workbook matching {name_or_stem!r} in config")


def load(root: Path | str) -> Config:
    """Load `<root>/config.json` and resolve paths relative to it."""
    root = Path(root).resolve()
    config_path = root if root.is_file() else root / "config.json"
    if not config_path.is_file():
        raise ConfigError(f"config.json not found at {config_path}")

    project_root = config_path.parent
    raw = json.loads(config_path.read_text(encoding="utf-8"))

    for required in ("name", "environment", "xlsxtables"):
        if required not in raw:
            raise ConfigError(f"config.json missing required field {required!r}")

    env_raw = raw["environment"]
    for required in ("xlsx", "out"):
        if required not in env_raw:
            raise ConfigError(f"config.json environment missing required field {required!r}")

    def _resolve(p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (project_root / path).resolve()

    environment = Environment(
        xlsx=_resolve(env_raw["xlsx"]),
        out=_resolve(env_raw["out"]),
        localize=_resolve(env_raw["localize"]) if env_raw.get("localize") else None,
        jsonschema=_resolve(env_raw["jsonschema"]) if env_raw.get("jsonschema") else None,
    )

    loc_raw = raw.get("localization") or {}
    localization = Localization(
        base_language=loc_raw.get("baseLanguage", "kr"),
        target_languages=tuple(loc_raw.get("targetLanguage", ())),
    )

    workbooks = tuple(
        WorkbookSpec(
            filename=fname,
            worksheets=tuple(
                WorksheetSpec(
                    name=ws["name"],
                    out=ws["out"],
                    localize=ws.get("localize"),
                    kwargs=ws.get("kwargs", {}),
                )
                for ws in spec.get("workSheets", [])
            ),
        )
        for fname, spec in raw["xlsxtables"].items()
    )

    return Config(
        name=raw["name"],
        root=project_root,
        environment=environment,
        localization=localization,
        workbooks=workbooks,
    )
