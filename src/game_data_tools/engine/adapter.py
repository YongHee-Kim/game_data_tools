"""The engine-agnostic interface that the sync orchestration talks to.

Concrete adapters (`unreal_adapter.UnrealAdapter`, the test fake) implement this
Protocol. Keeping the orchestration behind it is what lets `unreal_sync` be unit
tested with no Unreal Engine present.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol

from ..config import AssetFilter

# An opaque, engine-specific asset handle (a ``unreal.Object`` in production, a
# simple stand-in object in tests). The orchestration never inspects it directly.
AssetHandle = Any


class EngineUnavailableError(RuntimeError):
    """Raised when the requested engine integration cannot be used here.

    The most common cause is running outside the engine's embedded Python, where
    the engine module (``unreal``) is not importable.
    """


class EngineAdapter(Protocol):
    """Read/write access to engine assets, in engine-neutral terms."""

    def find_assets(self, flt: AssetFilter) -> list[AssetHandle]:
        """Return every asset matching ``flt`` (an Asset Registry query)."""
        ...

    def asset_key(self, asset: AssetHandle, key_property: str) -> Any:
        """Resolve the value used to match a sheet row to ``asset``.

        ``key_property`` is either a property name or a sentinel (``__name__`` /
        ``__path__``).
        """
        ...

    def get_property(self, asset: AssetHandle, path: list[str]) -> Any:
        """Read a (possibly nested) property; ``path`` is the dotted path split."""
        ...

    def set_property(self, asset: AssetHandle, path: list[str], value: Any) -> None:
        """Write a (possibly nested) property on ``asset``."""
        ...

    def save(self, asset: AssetHandle) -> None:
        """Persist ``asset`` to disk."""
        ...

    def transaction(self, description: str) -> AbstractContextManager[None]:
        """Context manager grouping edits into one undoable transaction."""
        ...
