"""Smoke-test the ``gdt`` command-line entry point end to end."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from openpyxl import Workbook

from game_data_tools.cli import main


def _build_project(root: Path) -> None:
    xlsx_dir = root / "xlsx"
    out_dir = root / "json"
    xlsx_dir.mkdir()
    out_dir.mkdir()

    wb = Workbook()
    ws = wb.active
    ws.title = "Equipment"
    ws.append(["Key", "Name", "/stats/hp", "Tags"])
    ws.append(["WPN001", "Steel Sword", 10, "melee;steel"])
    wb.save(xlsx_dir / "Items.xlsx")

    (root / "config.json").write_text(
        json.dumps(
            {
                "name": "CliProject",
                "environment": {"xlsx": "./xlsx", "out": "./json"},
                "xlsxtables": {
                    "Items.xlsx": {
                        "workSheets": [{"name": "Equipment", "out": "Items_Equipment.json"}]
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_project(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_convert_writes_json_and_reports(self) -> None:
        code, out, _ = _run("convert", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("DONE", out)
        self.assertTrue((self.root / "json" / "Items_Equipment.json").is_file())

    def test_config_prints_resolved_layout(self) -> None:
        code, out, _ = _run("config", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("CliProject", out)
        self.assertIn("Items.xlsx", out)

    def test_to_xlsx_round_trips(self) -> None:
        self.assertEqual(_run("convert", str(self.root))[0], 0)
        code, out, _ = _run("to-xlsx", str(self.root), "--file", "items")
        self.assertEqual(code, 0)
        self.assertIn("WRITE", out)

    def test_convert_single_file_by_stem(self) -> None:
        code, out, _ = _run("convert", str(self.root), "--file", "items")
        self.assertEqual(code, 0)
        self.assertIn("SAVE", out)


if __name__ == "__main__":
    unittest.main()
