"""End-to-end smoke test: build a tiny project on disk, convert, assert JSON output.

Run with: ``python -m unittest discover -s tests``
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from game_data_tools import Project


def _build_sample_project(root: Path) -> None:
    xlsx_dir = root / "xlsx"
    out_dir = root / "json"
    xlsx_dir.mkdir()
    out_dir.mkdir()

    wb = Workbook()
    ws = wb.active
    ws.title = "Equipment"
    ws.append(["Key", "Name", "/stats/hp", "Tags"])
    ws.append(["WPN001", "Steel Sword", 10, "melee;steel"])
    ws.append(["WPN002", "Silver Bow", 8, "ranged;silver"])
    wb.save(xlsx_dir / "Items.xlsx")

    (root / "config.json").write_text(
        json.dumps(
            {
                "name": "SampleProject",
                "environment": {"xlsx": "./xlsx", "out": "./json"},
                "xlsxtables": {
                    "Items.xlsx": {
                        "workSheets": [
                            {"name": "Equipment", "out": "Items_Equipment.json"},
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )


class ConvertTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_sample_project(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_convert_writes_expected_json(self) -> None:
        project = Project(self.root)
        results = project.export()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].errors, [])

        out = self.root / "json" / "Items_Equipment.json"
        data = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(
            data,
            [
                {
                    "Key": "WPN001",
                    "Name": "Steel Sword",
                    "stats": {"hp": 10},
                    "Tags": ["melee", "steel"],
                },
                {
                    "Key": "WPN002",
                    "Name": "Silver Bow",
                    "stats": {"hp": 8},
                    "Tags": ["ranged", "silver"],
                },
            ],
        )

    def test_second_run_skips_unchanged(self) -> None:
        project = Project(self.root)
        first = project.export()
        second = project.export()

        self.assertTrue(first[0].written)
        self.assertFalse(first[0].skipped)
        self.assertFalse(second[0].written)
        self.assertTrue(second[0].skipped)


if __name__ == "__main__":
    unittest.main()
