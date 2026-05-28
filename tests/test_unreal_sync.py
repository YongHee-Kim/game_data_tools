"""xlsx <-> Unreal sync orchestration, driven by an in-memory fake adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from game_data_tools import JSONWorksheet, Project
from game_data_tools.config import load
from game_data_tools.engine import EngineUnavailableError, get_adapter
from game_data_tools.unreal_sync import unreal_to_xlsx, xlsx_to_unreal

from _fake_engine import FakeAsset, FakeEngineAdapter

CLASS_PATH = "/Script/MyGame.WeaponDataAsset"
PACKAGE = "/Game/Data/Weapons"

_CONFIG = {
    "name": "MyGame",
    "gameEngine": {"type": "unreal", "contentRoot": "/Game"},
    "environment": {"xlsx": "./xlsx", "out": "./json"},
    "xlsxtables": {
        "Weapons.xlsx": {
            "workSheets": [
                {
                    "name": "Weapon",
                    "out": "Weapon.json",
                    "unreal": {
                        "assetFilter": {
                            "classPaths": [CLASS_PATH],
                            "packagePaths": [PACKAGE],
                            "recursivePaths": True,
                        },
                        "keyColumn": "/Key",
                        "properties": {
                            "/Key": "__name__",
                            "Name": "DisplayName",
                            "/stats/hp": "Stats.Health",
                            "Tags": "GameplayTags",
                        },
                    },
                }
            ]
        }
    },
}


def _build_project(root: Path) -> None:
    xlsx_dir = root / "xlsx"
    xlsx_dir.mkdir()
    (root / "json").mkdir()

    wb = Workbook()
    ws = wb.active
    ws.title = "Weapon"
    ws.append(["/Key", "Name", "/stats/hp", "Tags"])
    ws.append(["WPN001", "Steel Sword", 10, "melee;steel"])
    ws.append(["WPN002", "Silver Bow", 8, "ranged;silver"])
    wb.save(xlsx_dir / "Weapons.xlsx")

    (root / "config.json").write_text(json.dumps(_CONFIG), encoding="utf-8")


class _BrokenAdapter(FakeEngineAdapter):
    """Adapter whose asset lookup always fails, to exercise error handling."""

    def find_assets(self, flt):
        raise RuntimeError("boom")


class XlsxToUnrealTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_project(self.root)
        self.project = Project(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sets_properties_on_matching_asset(self) -> None:
        asset = FakeAsset("WPN001", CLASS_PATH, PACKAGE)
        adapter = FakeEngineAdapter([asset])

        result = xlsx_to_unreal(self.project, "weapons", adapter=adapter)

        self.assertEqual(result.updated, ["WPN001"])
        self.assertEqual(result.missing, ["WPN002"])  # no asset for the second row
        self.assertEqual(result.errors, [])
        self.assertTrue(asset.saved)
        self.assertEqual(
            asset.props,
            {
                "DisplayName": "Steel Sword",
                "Stats": {"Health": 10},
                "GameplayTags": ["melee", "steel"],
            },
        )

    def test_runs_inside_one_transaction(self) -> None:
        adapter = FakeEngineAdapter([FakeAsset("WPN001", CLASS_PATH, PACKAGE)])
        xlsx_to_unreal(self.project, "weapons", adapter=adapter)
        self.assertEqual(adapter.transactions, ["xlsx_to_unreal: Weapon"])

    def test_save_false_skips_persist(self) -> None:
        cfg = json.loads(json.dumps(_CONFIG))
        cfg["xlsxtables"]["Weapons.xlsx"]["workSheets"][0]["unreal"]["save"] = False
        (self.root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        project = Project(self.root)

        asset = FakeAsset("WPN001", CLASS_PATH, PACKAGE)
        xlsx_to_unreal(project, "weapons", adapter=FakeEngineAdapter([asset]))
        self.assertFalse(asset.saved)

    def test_collects_sheet_errors_without_aborting(self) -> None:
        result = xlsx_to_unreal(self.project, "weapons", adapter=_BrokenAdapter([]))
        self.assertEqual(result.updated, [])
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0][0], "Weapon")
        self.assertIsInstance(result.errors[0][1], RuntimeError)

    def test_strict_reraises_first_error(self) -> None:
        with self.assertRaises(RuntimeError):
            xlsx_to_unreal(self.project, "weapons", adapter=_BrokenAdapter([]), strict=True)


class UnrealToXlsxTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_project(self.root)
        self.project = Project(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_collects_assets_into_workbook(self) -> None:
        adapter = FakeEngineAdapter(
            [
                FakeAsset(
                    "WPN001",
                    CLASS_PATH,
                    PACKAGE,
                    {
                        "DisplayName": "Steel Sword",
                        "Stats": {"Health": 10},
                        "GameplayTags": ["melee", "steel"],
                    },
                ),
                FakeAsset(
                    "WPN002",
                    CLASS_PATH,
                    PACKAGE,
                    {
                        "DisplayName": "Silver Bow",
                        "Stats": {"Health": 8},
                        "GameplayTags": ["ranged", "silver"],
                    },
                ),
            ]
        )

        result = unreal_to_xlsx(self.project, "weapons", adapter=adapter)
        self.assertEqual(result.sheets, ["Weapon"])
        self.assertEqual(result.errors, [])

        xlsx_path = self.root / "xlsx" / "Weapons.xlsx"
        rows = JSONWorksheet.read(xlsx_path, "Weapon").rows
        self.assertEqual(
            rows,
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

    def test_collects_errors_and_skips_save_when_all_fail(self) -> None:
        result = unreal_to_xlsx(self.project, "weapons", adapter=_BrokenAdapter([]))
        self.assertEqual(result.sheets, [])
        self.assertEqual(result.written, [])  # nothing written -> no save
        self.assertEqual(len(result.errors), 1)

    def test_strict_reraises_first_error(self) -> None:
        with self.assertRaises(RuntimeError):
            unreal_to_xlsx(self.project, "weapons", adapter=_BrokenAdapter([]), strict=True)


class AdapterGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _load(self, body: dict):
        (self.root / "config.json").write_text(json.dumps(body), encoding="utf-8")
        return load(self.root)

    def test_no_engine_configured_raises(self) -> None:
        config = self._load(
            {
                "name": "Plain",
                "environment": {"xlsx": "./xlsx", "out": "./json"},
                "xlsxtables": {},
            }
        )
        with self.assertRaises(EngineUnavailableError):
            get_adapter(config)

    def test_unknown_engine_type_raises(self) -> None:
        config = self._load(
            {
                "name": "Other",
                "gameEngine": {"type": "godot"},
                "environment": {"xlsx": "./xlsx", "out": "./json"},
                "xlsxtables": {},
            }
        )
        with self.assertRaises(EngineUnavailableError):
            get_adapter(config)

    def test_unreal_without_engine_runtime_raises(self) -> None:
        # 'unreal' is not importable in CI, so constructing the adapter must fail
        # with a clear EngineUnavailableError rather than a raw ImportError.
        config = self._load(
            {
                "name": "MyGame",
                "gameEngine": {"type": "unreal"},
                "environment": {"xlsx": "./xlsx", "out": "./json"},
                "xlsxtables": {},
            }
        )
        with self.assertRaises(EngineUnavailableError):
            get_adapter(config)


if __name__ == "__main__":
    unittest.main()
