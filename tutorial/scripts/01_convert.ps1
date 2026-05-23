# Tutorial step 1: convert .xlsx -> .json.
# Reads tutorial/sample_project/xlsx/Items.xlsx and writes per-sheet JSON
# files to tutorial/sample_project/json/.
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot '..\sample_project'
gdt convert $project
