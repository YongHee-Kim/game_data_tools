"""Game-engine integration layer.

This subpackage deliberately does **not** ``import unreal`` at module load time —
the dependency is provided only by Unreal Engine's embedded Python. The single
place that imports it is `unreal_adapter.UnrealAdapter`, reached lazily through
`get_adapter`, so importing ``game_data_tools`` (or running the xlsx⇄json
pipeline) never requires Unreal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .adapter import EngineAdapter, EngineUnavailableError

if TYPE_CHECKING:
    from ..config import Config

__all__ = ["EngineAdapter", "EngineUnavailableError", "get_adapter"]


def get_adapter(config: "Config") -> EngineAdapter:
    """Return the `EngineAdapter` for the project's configured engine.

    :raises EngineUnavailableError: when no engine is configured, the engine type
        is unknown, or the engine runtime (e.g. the ``unreal`` module) is absent.
    """
    engine = config.game_engine
    if engine is None or not engine.type:
        raise EngineUnavailableError("config.json has no 'gameEngine.type' set")
    if engine.type == "unreal":
        from .unreal_adapter import UnrealAdapter

        return UnrealAdapter(config)
    raise EngineUnavailableError(f"unsupported game engine type: {engine.type!r}")
