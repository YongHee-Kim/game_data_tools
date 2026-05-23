# Tutorial

A hands-on walk through the `gdt` CLI: convert an Excel workbook to structured JSON, edit the JSON, and round-trip it back into the workbook.

## Prerequisites

Install the package in editable mode from the repo root:

```bash
pip install -e .
```

Confirm the CLI is on your PATH:

```bash
gdt --help
```

## What's in this folder

```
tutorial/
├── README.md
├── sample_project/
│   ├── config.json
│   ├── xlsx/
│   │   └── Items.xlsx        # source spreadsheet (Equipment + Consumable sheets)
│   └── json/                 # populated by the first `gdt convert`
└── scripts/
    ├── 01_convert.{ps1,sh}      # xlsx -> json
    ├── 02_to_xlsx.{ps1,sh}      # json -> xlsx
    └── 03_roundtrip.{ps1,sh}    # convert / snapshot / to-xlsx / convert / diff
```

`sample_project/config.json` describes one workbook (`Items.xlsx`) with two sheets:

```json
{
    "name": "TutorialProject",
    "environment": { "xlsx": "./xlsx", "out": "./json" },
    "xlsxtables": {
        "Items.xlsx": {
            "workSheets": [
                { "name": "Equipment",  "out": "Items_Equipment.json" },
                { "name": "Consumable", "out": "Items_Consumable.json" }
            ]
        }
    }
}
```

The Equipment sheet uses JSONPointer-style column headers (`/stats/hp`, `/stats/atk`) to demonstrate nested objects in the converted JSON, and a semicolon-delimited `Tags` column to demonstrate array cells.

## Step 1 — xlsx → json

Generates `sample_project/json/Items_Equipment.json` and `Items_Consumable.json`.

```powershell
# PowerShell
./tutorial/scripts/01_convert.ps1
```

```bash
# bash
./tutorial/scripts/01_convert.sh
```

Or directly:

```bash
gdt convert ./tutorial/sample_project
```

You should see something like:

```
『Items.xlsx』
  SAVE => .../tutorial/sample_project/json/Items_Equipment.json
  SAVE => .../tutorial/sample_project/json/Items_Consumable.json

DONE: 2 written, 0 unchanged, 0 failed
```

Open `Items_Equipment.json` and note that `/stats/hp` and `/stats/atk` columns landed nested under a `stats` object, and `Tags` is a JSON array.

Re-running `gdt convert` is cheap — files only get rewritten when the content actually changes.

## Step 2 — edit the json, then json → xlsx

Edit `sample_project/json/Items_Equipment.json` — change a stat, add a tag, whatever you like. Then push it back into the workbook:

```powershell
./tutorial/scripts/02_to_xlsx.ps1
```

```bash
./tutorial/scripts/02_to_xlsx.sh
```

Or directly:

```bash
gdt to-xlsx ./tutorial/sample_project --file items
```

Open `Items.xlsx` — your edits should be reflected in the Equipment sheet, and the Consumable sheet is preserved.

`--file` accepts the workbook filename (`Items.xlsx`) or just its stem (`items`).

## Step 3 — round trip sanity check

This script proves the loop is lossless on the supported feature set:

1. `gdt convert` (snapshot the json)
2. `gdt to-xlsx` (write json back into the workbook)
3. `gdt convert` again
4. diff the new json against the snapshot — should be empty

```powershell
./tutorial/scripts/03_roundtrip.ps1
```

```bash
./tutorial/scripts/03_roundtrip.sh
```

If the diff is empty, the workbook survived the trip with no data loss.

## What round-trips today

| Feature                                  | xlsx → json | json → xlsx |
| ---------------------------------------- | :---------: | :---------: |
| Row-oriented sheets                      |      ✓      |      ✓      |
| Bare column names (`Key`, `Name`)        |      ✓      |      ✓      |
| JSONPointer column names (`/stats/hp`)   |      ✓      |      ✓      |
| Array cells (`a;b;c`)                    |      ✓      |      ✓      |
| `empty_value` post-process               |      ✓      |      —      |
| `start_line` offset                      |      ✓      |      ✓      |
| Multiple sheets per workbook             |      ✓      |      ✓      |
| Other sheets preserved on partial write  |     n/a     |      ✓      |
| Column-oriented sheets (`row_oriented:false`) |    —     |      —      |
| `squeeze`, `omit_null_object`            |      —      |      —      |
| Localization (`$`-prefixed columns)      |      —      |      —      |

When a feature lands, this tutorial should pick it up without changes.

## See also

- [../README.md](../README.md) — package overview and config reference
- [../GameDataManager/README.md](../GameDataManager/README.md) — the original Julia tool whose behavior we're porting
