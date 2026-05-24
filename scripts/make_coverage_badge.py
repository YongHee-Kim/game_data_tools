#!/usr/bin/env python
"""Generate a shields.io-style coverage badge SVG from a ``coverage json`` report.

Self-contained (stdlib only) so CI needs no third-party badge tool. Reads the
total line coverage from a coverage.py JSON report and writes a flat SVG.

Usage::

    coverage json -o coverage.json
    python scripts/make_coverage_badge.py --input coverage.json --output coverage.svg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# (minimum percent, fill color) ordered high to low.
_THRESHOLDS = [
    (95, "#4c1"),       # brightgreen
    (90, "#97ca00"),    # green
    (75, "#a4a61d"),    # yellowgreen
    (60, "#dfb317"),    # yellow
    (40, "#fe7d37"),    # orange
    (0, "#e05d44"),     # red
]

_LABEL = "coverage"


def _color_for(percent: float) -> str:
    for minimum, color in _THRESHOLDS:
        if percent >= minimum:
            return color
    return _THRESHOLDS[-1][1]


def _text_width(text: str) -> int:
    """Rough pixel width of the text rendered at 11px DejaVu Sans, plus padding."""
    return round(len(text) * 6.5) + 10


def render(percent: float) -> str:
    value = f"{round(percent)}%"
    color = _color_for(percent)
    label_w = _text_width(_LABEL)
    value_w = _text_width(value)
    total_w = label_w + value_w
    # Text anchors sit at the centre of each half (x10 for the @1000 scale).
    label_x = label_w * 5
    value_x = label_w * 10 + value_w * 5
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img" aria-label="{_LABEL}: {value}">
  <title>{_LABEL}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_w}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="110" text-rendering="geometricPrecision">
    <text x="{label_x}" y="150" transform="scale(.1)" fill="#010101" fill-opacity=".3" textLength="{(label_w - 10) * 10}">{_LABEL}</text>
    <text x="{label_x}" y="140" transform="scale(.1)" textLength="{(label_w - 10) * 10}">{_LABEL}</text>
    <text x="{value_x}" y="150" transform="scale(.1)" fill="#010101" fill-opacity=".3" textLength="{(value_w - 10) * 10}">{value}</text>
    <text x="{value_x}" y="140" transform="scale(.1)" textLength="{(value_w - 10) * 10}">{value}</text>
  </g>
</svg>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("coverage.json"))
    parser.add_argument("--output", type=Path, default=Path("coverage.svg"))
    args = parser.parse_args(argv)

    if not args.input.is_file():
        parser.error(f"coverage JSON not found: {args.input} (run 'coverage json' first)")

    data = json.loads(args.input.read_text(encoding="utf-8"))
    percent = float(data["totals"]["percent_covered"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(percent), encoding="utf-8")
    print(f"wrote {args.output} ({round(percent)}% coverage)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
