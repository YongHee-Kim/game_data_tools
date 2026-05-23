"""Helpers for column-name-driven nesting via JSONPointer.

A column named ``/character/stats/hp`` should produce ``{"character": {"stats": {"hp": ...}}}``.
A bare name like ``Description`` is treated as ``/Description``.
"""

from __future__ import annotations

from typing import Any

from jsonpointer import JsonPointer


def normalize(token: str) -> str:
    return token if token.startswith("/") else "/" + token


def set_in(obj: dict[str, Any], pointer: str, value: Any) -> None:
    """Set a value at `pointer`, creating intermediate dicts as needed.

    ``jsonpointer.JsonPointer.set`` does not auto-create parents, so we walk the
    tokens ourselves and delegate parsing/unescaping to the library.
    """
    tokens = list(JsonPointer(normalize(pointer)).parts)
    if not tokens:
        raise ValueError("cannot set root with empty pointer")
    cursor: Any = obj
    for tok in tokens[:-1]:
        nxt = cursor.get(tok)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[tok] = nxt
        cursor = nxt
    cursor[tokens[-1]] = value


def get_at(obj: Any, pointer: str, default: Any = None) -> Any:
    """Resolve `pointer` against `obj`, returning `default` for missing paths."""
    return JsonPointer(normalize(pointer)).resolve(obj, default=default)
