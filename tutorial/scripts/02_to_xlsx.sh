#!/usr/bin/env bash
# Tutorial step 2: write .json -> .xlsx for the Items workbook.
# Reads tutorial/sample_project/json/Items_*.json and rewrites
# tutorial/sample_project/xlsx/Items.xlsx with both sheets.
set -euo pipefail
project="$(cd "$(dirname "$0")/../sample_project" && pwd)"
gdt to-xlsx "$project" --file items
