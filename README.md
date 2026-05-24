# game_data_tools

[![Tests](https://github.com/YongHee-Kim/game_data_tools/actions/workflows/tests.yml/badge.svg)](https://github.com/YongHee-Kim/game_data_tools/actions/workflows/tests.yml)
[![Coverage](https://yonghee-kim.github.io/game_data_tools/coverage.svg)](https://yonghee-kim.github.io/game_data_tools/coverage/)
[![Docs](https://github.com/YongHee-Kim/game_data_tools/actions/workflows/docs.yml/badge.svg)](https://yonghee-kim.github.io/game_data_tools/)

A Python toolkit for game designers to wrangle spreadsheet-based game data. It converts `.xlsx`/`.xlsm` workbooks to structured `.json` (and back), extracts localizable text, and validates data against JSON Schema. Eventual goal: import generated data directly into Unreal Engine assets.

This is a Python port of [GameDataManager.jl](https://github.com/YongHee-Kim/GameDataManager.jl), preserving its config format and conversion semantics so existing projects can move over without rewriting their `config.json`.

## Why

Game designers spend most of their time wrestling with data. Spreadsheets are easy to author in but painful as a single source of truth: relationships between tables, localization, schema drift, and engine import are all manual. `game_data_tools` automates the round trip between the spreadsheet designers edit and the JSON the engine consumes, with validation in the middle.

## Core features

1. **xlsx → json** — Convert `.xlsx`/`.xlsm` workbooks to `.json` (or `.csv`/`.tsv`) per a project `config.json`. Supports row-oriented sheets, nested objects via JSONPointer column names, array cells with configurable delimiters, and per-column empty-cell substitution. (Column-oriented sheets and `squeeze`/`omit_null_object` post-processes are not yet implemented.)
2. **json → xlsx** — Round-trip JSON back into a workbook, preserving column order, JSONPointer nesting, array-cell encoding, and `start_line` offsets. Other sheets in the target workbook are preserved.
3. **Localization** *(planned)* — Extract `$`-prefixed columns into a separate per-language JSON file, leaving stable lookup keys in the main data. Compatible with the Julia tool's key format (`$gamedata.<file>.<column>.<key>`).
4. **JSON Schema validation** — Validate converted JSON against schemas in the project's `jsonschema/` directory.
5. **Unreal import** *(planned)* — Emit Unreal `DataTable` JSON and/or drive an editor commandlet to import assets directly. Deferred until the json side is stable.

## Status

The core pipeline is implemented and tested: `.xlsx`/`.xlsm` → `.json`/`.csv`/`.tsv` conversion (with JSONPointer columns and array cells), `.json` → `.xlsx` round-trip, JSON Schema validation, and the `gdt` CLI. Localization extraction and Unreal export are still planned — see the [Roadmap](#roadmap). Behavior is ported from [GameDataManager.jl](https://github.com/YongHee-Kim/GameDataManager.jl).

## Install

Not yet on PyPI. From a clone:

```bash
pip install -e .
```

Python 3.10+ recommended.

## Quickstart

### 1. Project layout

```
MyProject/
  config.json
  xlsx/
    Items.xlsx
  json/             # generated
  localization/     # generated (optional)
  jsonschema/       # optional
```

### 2. `config.json`

Identical to the Julia tool's format:

```json
{
    "name": "MyGame",
    "environment": {
        "xlsx": "./xlsx",
        "out": "./json",
        "localize": "./localization",
        "jsonschema": "./jsonschema"
    },
    "localization": {
        "baseLanguage": "eng"
    },
    "xlsxtables": {
        "Items.xlsx": {
            "workSheets": [
                {
                    "name": "Equipment",
                    "out": "Items_Equipment.json",
                    "localize": { "keycolumn": "/Key" }
                },
                {
                    "name": "Consumable",
                    "out": "Items_Consumable.json",
                    "kwargs": { "start_line": 2 }
                }
            ]
        }
    }
}
```

Path fields under `environment` may be absolute or relative to `config.json`.

### 3. Convert

**CLI:**

```bash
gdt convert ./MyProject                 # export every configured workbook
gdt convert ./MyProject --file items    # export a single workbook
gdt to-xlsx ./MyProject --file items    # reverse: json → xlsx
gdt config  ./MyProject                 # print the resolved project config
gdt shell   ./MyProject                 # open a persistent REPL for the project
```

**Library:**

```python
from game_data_tools import Project

project = Project("./MyProject")
project.export()                        # all workbooks
project.export("items")                 # one workbook
project.import_json("items")            # json → xlsx
```

By default a single failing sheet does not abort the batch. Pass `strict=True` (or `--strict` on the CLI) to fail fast.

## Worksheet options (`kwargs`)

Forwarded to the workbook reader; same semantics as the Julia tool.

| key                | type        | default | meaning                                                            |
| ------------------ | ----------- | ------- | ------------------------------------------------------------------ |
| `start_line`       | int         | `1`     | Row containing column headers.                                     |
| `row_oriented`     | bool        | `true`  | `false` reads column-oriented sheets (headers in column A).        |
| `squeeze`          | bool        | `false` | Collapse all rows of a sheet into a single object.                 |
| `delim`            | str / regex | `;`     | Delimiter for splitting a single cell into an array.               |
| `omit_null_object` | bool        | `false` | Drop array elements whose every field is null.                     |
| `empty_value`      | object      | —       | Per-column replacement for empty cells, keyed by name or pointer.  |

Column names may use JSONPointer syntax (`/character/stats/hp`) to nest values inside the emitted object.

## Localization

> **Planned — not yet implemented.** `localize` specs in `config.json` are parsed, but extraction does not run yet. The design below mirrors GameDataManager's localizer and documents the intended behavior.

1. Prefix any column header with `$` to opt it into extraction:

   | Key    | $Description           |
   | ------ | ---------------------- |
   | WPN001 | A sturdy steel sword.  |

2. Configure `localize` per worksheet:

   ```json
   { "name": "Weapon", "out": "Items_Weapon.json", "localize": { "keycolumn": "/Key" } }
   ```

3. After `gdt convert`, the data file keeps the source string and adds a lookup key:

   `json/Items_Weapon.json`
   ```json
   [
     { "Key": "WPN001", "Description": "$gamedata.Items_Weapon.Description.WPN001", "$Description": "A sturdy steel sword." }
   ]
   ```

   `localization/Items_Weapon_eng.json`
   ```json
   { "$gamedata.Items_Weapon.Description.WPN001": "A sturdy steel sword." }
   ```

   Copy `Items_Weapon_eng.json` to `Items_Weapon_<lang>.json` and translate values. Duplicate keys or empty `keycolumn` cells are errors.

## json → xlsx

The reverse direction reads the JSON output and rewrites the source workbook, preserving:

- Column order from `config.json` / the first row.
- Nested structure (JSONPointer column names).
- Array and object cell encoding (`[a;b;c]`, `{"k":v;...}`).
- `$`-prefixed source text for localized columns.

Useful when JSON has been edited by a tool (script, codegen) and designers need the change reflected in the workbook they actually open.

```bash
gdt to-xlsx ./MyProject --file items
```

Files are only rewritten when content actually changes, so re-runs are cheap and VCS diffs stay clean.

## Validation

If `environment.jsonschema` is set and a schema named `<out_basename>.json` exists, the converted file is validated against it on export. Validation failures are reported per-file and (in non-strict mode) do not abort the batch.

## Roadmap

- [x] Core xlsx → json conversion with JSONPointer columns and array cells
- [x] json → xlsx round-trip (row-oriented, multi-sheet, other sheets preserved)
- [x] JSON Schema validation
- [x] CLI (`gdt convert` / `gdt to-xlsx`)
- [ ] Column-oriented sheets, `squeeze`, `omit_null_object`
- [ ] Object-cell encoding round-trip (`{"k":v;"k2":v2}`)
- [ ] Localization extraction (`$`-prefixed columns)
- [ ] Unreal DataTable JSON emitter
- [ ] Optional editor-commandlet driver for headless imports

For a walkthrough of every worksheet `kwargs` option, see the [API documentation](https://yonghee-kim.github.io/game_data_tools/) (generated from the package docstrings with [pydoctor](https://pydoctor.readthedocs.io/)).

## License

See [LICENSE](./LICENSE).
