"""Schema validation integration: a passing schema, a failing schema, no schema."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from game_data_tools import Project
from game_data_tools.schema import SchemaError, validate


def _build_project(root: Path, schema: dict | None) -> None:
    xlsx_dir = root / "xlsx"
    out_dir = root / "json"
    schema_dir = root / "jsonschema"
    xlsx_dir.mkdir()
    out_dir.mkdir()
    schema_dir.mkdir()

    wb = Workbook()
    ws = wb.active
    ws.title = "Weapon"
    ws.append(["Key", "Damage"])
    ws.append(["WPN001", 10])
    wb.save(xlsx_dir / "Items.xlsx")

    if schema is not None:
        (schema_dir / "Items_Weapon.json").write_text(
            json.dumps(schema), encoding="utf-8"
        )

    (root / "config.json").write_text(
        json.dumps(
            {
                "name": "P",
                "environment": {
                    "xlsx": "./xlsx",
                    "out": "./json",
                    "jsonschema": "./jsonschema",
                },
                "xlsxtables": {
                    "Items.xlsx": {
                        "workSheets": [{"name": "Weapon", "out": "Items_Weapon.json"}]
                    }
                },
            }
        ),
        encoding="utf-8",
    )


class SchemaValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_passing_schema_exports_normally(self) -> None:
        _build_project(
            self.root,
            schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "Key": {"type": "string"},
                        "Damage": {"type": "integer"},
                    },
                    "required": ["Key", "Damage"],
                },
            },
        )
        results = Project(self.root).export()
        self.assertEqual(results[0].errors, [])
        self.assertEqual(len(results[0].written), 1)

    def test_failing_schema_records_error_and_skips_write(self) -> None:
        _build_project(
            self.root,
            schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"Damage": {"type": "string"}},
                },
            },
        )
        results = Project(self.root).export()

        self.assertEqual(len(results[0].errors), 1)
        sheet, exc = results[0].errors[0]
        self.assertEqual(sheet, "Weapon")
        self.assertIsInstance(exc, SchemaError)
        self.assertFalse((self.root / "json" / "Items_Weapon.json").exists())

    def test_missing_schema_is_silently_skipped(self) -> None:
        _build_project(self.root, schema=None)
        results = Project(self.root).export()
        self.assertEqual(results[0].errors, [])

    def test_validate_returns_false_when_no_schema(self) -> None:
        _build_project(self.root, schema=None)
        self.assertFalse(
            validate(self.root / "jsonschema", "Items_Weapon.json", [{"Key": "X"}])
        )


if __name__ == "__main__":
    unittest.main()
