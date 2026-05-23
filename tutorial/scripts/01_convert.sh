#!/usr/bin/env bash
# Tutorial step 1: convert .xlsx -> .json.
# Reads tutorial/sample_project/xlsx/Items.xlsx and writes per-sheet JSON
# files to tutorial/sample_project/json/.
set -euo pipefail
project="$(cd "$(dirname "$0")/../sample_project" && pwd)"
gdt convert "$project"
