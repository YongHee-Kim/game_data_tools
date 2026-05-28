# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`game_data_tools` converts spreadsheet-based game data between `.xlsx`/`.xlsm` and `.json`/`.csv`/`.tsv`, with localization extraction and JSON Schema validation. It is a Python port of [GameDataManager.jl](https://github.com/YongHee-Kim/GameDataManager.jl) and **intentionally preserves that tool's `config.json` format and conversion semantics** so existing Julia projects move over without rewriting config. When in doubt about a config key or conversion behavior, the Julia tool is the reference.

## Commands

The package uses a **src layout**, so `import game_data_tools` only resolves after an editable install:

```bash
pip install -e ".[dev]"          # installs openpyxl/jsonschema/jsonpointer + ruff
```

```bash
python -m unittest discover -s tests          # all tests
python -m unittest tests.test_smoke           # one test module
python -m unittest tests.test_roundtrip.RoundTripTests.test_json_to_xlsx_preserves_data_through_full_loop  # one test
ruff check .                                  # lint
ruff format .                                 # format
gdt convert ./project                         # run the CLI (entry point: game_data_tools.cli:main)
```

Tests use the stdlib `unittest` framework (not pytest) and build throwaway projects in `tempfile` dirs. Use `openpyxl` for both reading and writing xlsx.

## Architecture

Data flows config → orchestration → batched workbook I/O → per-sheet conversion. The layers:

- **`config.py`** — Parses `config.json` into frozen dataclasses (`Config` → `WorkbookSpec` → `WorksheetSpec`). Resolves `environment` paths relative to the config file. Note the Julia-derived JSON key names: top-level `xlsxtables` (a map of *filename* → spec), `workSheets`, per-sheet `kwargs`/`localize`, and `localization.baseLanguage`/`targetLanguage`. **Do not rename these keys** — compatibility is the point.
- **`project.py`** — `Project` is the public entry point and orchestrator. `export()` does xlsx→out files; `import_json()` does json→xlsx. Both return result dataclasses (`ExportResult`/`ImportResult`) that **collect per-sheet errors rather than raising** — a single bad sheet does not abort the batch. Pass `strict=True` to fail fast on the first error instead.
- **`workbook.py`** — `JSONWorkbook` is a context-managed wrapper over an openpyxl `Workbook`. It exists to enforce a **batched-I/O invariant: an N-sheet workbook is opened once and (for writes) saved once**, not N times. `open_for_read` uses `read_only=True, data_only=True`; `open_for_write` creates a fresh workbook if the file is absent. The context manager only closes — callers must call `save()` explicitly. `import_json` deliberately skips `save()` entirely when every sheet fails, leaving the xlsx byte-identical. Tests in `test_batched_open.py` assert these open/save counts, so preserve them.
- **`worksheet.py`** — `JSONWorksheet` is the in-memory form of one sheet (columns + row dicts). Reads via `_read_from_workbook`, writes via `.write()` (format chosen by suffix) / `_write_to_workbook`. `from_json` reconstructs column order by depth-first walking row keys. `.write()` **diffs against existing file content and skips unchanged writes** (returns a `bool`) to keep VCS diffs clean — keep this behavior.
- **`pointer.py`** — Column names are JSONPointers. `/character/stats/hp` nests into `{"character":{"stats":{"hp":...}}}`; a bare `Name` is top-level. Used on both read (nest) and write (resolve).
- **`schema.py`** — If `environment.jsonschema` is set, a converted file `Foo.json` is validated against `<jsonschema>/Foo.json` (matched by basename). Missing schemas are silently skipped; failures raise `SchemaError`.

### Unimplemented features fail loudly — on purpose

Several Julia-tool features are not yet ported and **deliberately raise `NotImplementedError`** rather than silently misbehaving: column-oriented sheets (`row_oriented: false`), `squeeze`, `omit_null_object`, and object-cell round-trip. `tests/test_fixture_project.py` runs the real GameDataManager fixture project (`tests/fixtures/project/`) and partitions sheets into `SHEETS_EXPECTED_TO_SUCCEED` / `SHEETS_EXPECTED_TO_FAIL`. When you implement one of these features, **graduate the sheet from the "fail" set to the "succeed" set** in that test.

## CLI

`gdt <command> <project>` with commands `convert` (xlsx→out), `to-xlsx` (json→xlsx), `config` (print resolved config), and `shell` (a `cmd`-based REPL). The shell maps hyphenated names to underscores (`to-xlsx` → `do_to_xlsx`) in `precmd`. A project argument may point at a directory or directly at its `config.json`.
