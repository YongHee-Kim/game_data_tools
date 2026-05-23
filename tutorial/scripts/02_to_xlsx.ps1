# Tutorial step 2: write .json -> .xlsx for the Items workbook.
# Reads tutorial/sample_project/json/Items_*.json and rewrites
# tutorial/sample_project/xlsx/Items.xlsx with both sheets.
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot '..\sample_project'
gdt to-xlsx $project --file items
