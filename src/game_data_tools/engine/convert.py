"""Pure helpers for mapping between sheet values and engine property paths.

UE-free on purpose so it is fully unit-testable. M1 ships the property-path
helpers and identity value converters; richer UE-type coercion (FName/FText,
enums, soft references, ...) lands in M2.
"""

from __future__ import annotations

from typing import Any

# Property targets that resolve to engine metadata rather than a stored property.
SENTINELS = frozenset({"__name__", "__path__"})


def is_sentinel(ue_path: str) -> bool:
    return ue_path in SENTINELS


def property_path(ue_path: str) -> list[str]:
    """Split a dotted UE property path (``Stats.Health``) into tokens."""
    return ue_path.split(".")


def to_engine(value: Any) -> Any:
    """Convert a sheet/JSON value into an engine-ready value (M1: identity)."""
    return value


def from_engine(value: Any) -> Any:
    """Convert an engine value into a JSON-friendly value (M1: identity)."""
    return value
