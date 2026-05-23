# Tutorial step 3: full round trip.
# convert -> snapshot json -> to-xlsx -> convert again -> diff.
# Useful as a sanity check that the workbook survives a json edit.
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot '..\sample_project'
$jsonDir = Join-Path $project 'json'
$snapshot = Join-Path $env:TEMP 'gdt_tutorial_snapshot'

if (Test-Path $snapshot) { Remove-Item $snapshot -Recurse -Force }

gdt convert $project
Copy-Item $jsonDir $snapshot -Recurse
gdt to-xlsx $project --file items
gdt convert $project

$diff = Compare-Object `
    (Get-ChildItem $jsonDir -File | Sort-Object Name | ForEach-Object { Get-Content $_.FullName -Raw }) `
    (Get-ChildItem $snapshot -File | Sort-Object Name | ForEach-Object { Get-Content $_.FullName -Raw })

if ($diff) {
    Write-Error 'round trip diverged'
    $diff | Format-List
    exit 1
}
Write-Host 'round trip clean'
Remove-Item $snapshot -Recurse -Force
