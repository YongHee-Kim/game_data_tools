"""Run the conversion against the GameDataManager test project copied into tests/fixtures.

This is the same data the Julia reference implementation tests against, so as we
implement more features (column-oriented sheets, omit_null_object, localization, etc.)
the corresponding assertions here can graduate from ``expected_errors`` to
``expected_outputs``.

Note: we work against a copy under ``tmp/`` per test so conversion writing into the
output dir does not mutate the checked-in fixture.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from game_data_tools import Project


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "project"


SHEETS_EXPECTED_TO_SUCCEED = {
    ("Items.xlsx", "Weapon"),
    ("Items.xlsx", "Armour"),
    ("Items.xlsx", "Accessory"),
    ("TestData.xlsx", "Array"),
    ("TestData.xlsx", "Object"),
    ("TestData.xlsx", "Csv"),
    ("TestData.xlsx", "Tsv"),
    ("PostProcess.xlsx", "EmptyValue"),
    ("Folder/Character.xlsx", "Data"),
}

SHEETS_EXPECTED_TO_FAIL = {
    # column-oriented reader not implemented
    ("TestData.xlsx", "ColumnOrient"),
    # omit_null_object post-process not implemented
    ("PostProcess.xlsx", "OmitNull"),
}

WORKBOOKS_EXPECTED_MISSING = {
    "NotExistFile.xlsm",
}


class FixtureProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name) / "project"
        shutil.copytree(FIXTURE_ROOT, self.project_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self) -> dict[str, "object"]:
        project = Project(self.project_root)
        results = project.export()
        by_workbook = {r.workbook: r for r in results}
        return by_workbook

    def test_supported_sheets_write_output_files(self) -> None:
        by_workbook = self._run()
        out_dir = self.project_root / "json"

        for workbook, sheet in SHEETS_EXPECTED_TO_SUCCEED:
            with self.subTest(workbook=workbook, sheet=sheet):
                result = by_workbook[workbook]
                failed_sheets = {name for name, _ in result.errors}
                self.assertNotIn(
                    sheet,
                    failed_sheets,
                    msg=f"{workbook}::{sheet} should have converted: {result.errors}",
                )

        # Spot-check that at least one expected json file exists and parses.
        weapon = out_dir / "Items_Weapon.json"
        self.assertTrue(weapon.is_file(), f"expected {weapon} to be written")
        self.assertIsInstance(json.loads(weapon.read_text(encoding="utf-8")), list)

    def test_unsupported_sheets_land_in_errors(self) -> None:
        by_workbook = self._run()
        for workbook, sheet in SHEETS_EXPECTED_TO_FAIL:
            with self.subTest(workbook=workbook, sheet=sheet):
                result = by_workbook[workbook]
                failed = dict(result.errors)
                self.assertIn(
                    sheet,
                    failed,
                    msg=f"{workbook}::{sheet} expected to fail until feature lands",
                )
                self.assertIsInstance(failed[sheet], NotImplementedError)

    def test_missing_workbook_does_not_abort_batch(self) -> None:
        by_workbook = self._run()
        for workbook in WORKBOOKS_EXPECTED_MISSING:
            with self.subTest(workbook=workbook):
                result = by_workbook[workbook]
                self.assertEqual(len(result.errors), 1)
                self.assertIsInstance(result.errors[0][1], FileNotFoundError)

    def test_strict_mode_propagates_first_failure(self) -> None:
        project = Project(self.project_root)
        with self.assertRaises((NotImplementedError, FileNotFoundError)):
            project.export(strict=True)


if __name__ == "__main__":
    unittest.main()
