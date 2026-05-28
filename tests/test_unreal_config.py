"""Parsing of the gameEngine and per-worksheet unreal config blocks."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from game_data_tools import config as cfg


def _write_config(root: Path, body: dict) -> Path:
    (root / "config.json").write_text(json.dumps(body), encoding="utf-8")
    return root


_UNREAL_CONFIG = {
    "name": "MyGame",
    "gameEngine": {"type": "unreal", "projectPath": "./MyGame.uproject", "contentRoot": "/Game"},
    "environment": {"xlsx": "./xlsx", "out": "./json"},
    "xlsxtables": {
        "Weapons.xlsx": {
            "workSheets": [
                {
                    "name": "Weapon",
                    "out": "Weapon.json",
                    "unreal": {
                        "assetFilter": {
                            "classPaths": ["/Script/MyGame.WeaponDataAsset"],
                            "packagePaths": ["/Game/Data/Weapons"],
                            "recursivePaths": True,
                        },
                        "keyColumn": "/Key",
                        "properties": {"/Key": "__name__", "/stats/hp": "Stats.Health"},
                    },
                }
            ]
        }
    },
}


class UnrealConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_game_engine_parsed_and_path_resolved(self) -> None:
        config = cfg.load(_write_config(self.root, _UNREAL_CONFIG))
        self.assertIsNotNone(config.game_engine)
        self.assertEqual(config.game_engine.type, "unreal")
        self.assertEqual(config.game_engine.content_root, "/Game")
        self.assertTrue(config.game_engine.project_path.is_absolute())

    def test_unreal_spec_and_filter_parsed(self) -> None:
        config = cfg.load(_write_config(self.root, _UNREAL_CONFIG))
        ws = config.workbook("weapons").worksheets[0]
        self.assertIsNotNone(ws.unreal)
        self.assertEqual(ws.unreal.key_column, "/Key")
        self.assertEqual(ws.unreal.key_property, "__name__")  # default
        self.assertTrue(ws.unreal.save)  # default
        self.assertEqual(ws.unreal.properties["/stats/hp"], "Stats.Health")

        flt = ws.unreal.asset_filter
        self.assertEqual(flt.class_paths, ("/Script/MyGame.WeaponDataAsset",))
        self.assertEqual(flt.package_paths, ("/Game/Data/Weapons",))
        self.assertTrue(flt.recursive_paths)
        self.assertFalse(flt.recursive_classes)  # default

    def test_config_without_engine_is_unchanged(self) -> None:
        body = {
            "name": "Plain",
            "environment": {"xlsx": "./xlsx", "out": "./json"},
            "xlsxtables": {"Items.xlsx": {"workSheets": [{"name": "S", "out": "S.json"}]}},
        }
        config = cfg.load(_write_config(self.root, body))
        self.assertIsNone(config.game_engine)
        self.assertIsNone(config.workbook("items").worksheets[0].unreal)


if __name__ == "__main__":
    unittest.main()
