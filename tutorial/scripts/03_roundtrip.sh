#!/usr/bin/env bash
# Tutorial step 3: full round trip.
# convert -> snapshot json -> to-xlsx -> convert again -> diff.
# Useful as a sanity check that the workbook survives a json edit.
set -euo pipefail
project="$(cd "$(dirname "$0")/../sample_project" && pwd)"
json_dir="$project/json"
snapshot="$(mktemp -d)"
trap 'rm -rf "$snapshot"' EXIT

gdt convert "$project"
cp -r "$json_dir"/. "$snapshot"/
gdt to-xlsx "$project" --file items
gdt convert "$project"

if diff -r "$json_dir" "$snapshot" >/dev/null; then
    echo "round trip clean"
else
    echo "round trip diverged:" >&2
    diff -r "$json_dir" "$snapshot" >&2 || true
    exit 1
fi
