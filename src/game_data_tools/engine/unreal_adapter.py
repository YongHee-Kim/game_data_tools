"""`EngineAdapter` backed by Unreal Engine's embedded Python (``unreal``).

This is the only module that touches ``unreal``, and it does so lazily so that it
can be imported (and `UnrealAdapter` referenced) on a machine without the engine —
construction is what fails, with a clear `EngineUnavailableError`.

The methods that call into ``unreal`` are marked ``# pragma: no cover`` because
they can only run inside the editor; they are exercised by hand / on CI runners
that have UE, not by the unit suite. The import-failure path *is* covered.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

from ..config import AssetFilter, Config
from .adapter import EngineUnavailableError

if TYPE_CHECKING:
    from .adapter import AssetHandle


def _require_unreal() -> Any:
    """Import and return the ``unreal`` module, or raise `EngineUnavailableError`."""
    try:
        import unreal
    except ImportError as exc:
        raise EngineUnavailableError(
            "Unreal integration must run inside Unreal Engine's embedded Python "
            "(the 'unreal' module is provided by the UE Python plugin)."
        ) from exc
    return unreal  # pragma: no cover - only reachable inside the editor


class UnrealAdapter:
    """Talks to the Asset Registry and editor property system via ``unreal``."""

    def __init__(self, config: Config):
        self._config = config
        self._unreal = _require_unreal()
        self._registry = (  # pragma: no cover - UE only
            self._unreal.AssetRegistryHelpers.get_asset_registry()
        )

    def find_assets(self, flt: AssetFilter) -> list[AssetHandle]:  # pragma: no cover - UE only
        ue = self._unreal
        ar_filter = ue.ARFilter(
            class_paths=[self._top_level_path(cp) for cp in flt.class_paths],
            package_paths=[ue.Name(p) for p in flt.package_paths],
            package_names=[ue.Name(p) for p in flt.package_names],
            recursive_paths=flt.recursive_paths,
            recursive_classes=flt.recursive_classes,
        )
        return [ad.get_asset() for ad in self._registry.get_assets(ar_filter)]

    def asset_key(self, asset: AssetHandle, key_property: str) -> Any:  # pragma: no cover - UE only
        if key_property == "__name__":
            return str(asset.get_name())
        if key_property == "__path__":
            return str(asset.get_path_name())
        return asset.get_editor_property(key_property)

    def get_property(self, asset: AssetHandle, path: list[str]) -> Any:  # pragma: no cover - UE only
        obj = asset
        for token in path:
            obj = obj.get_editor_property(token)
        return obj

    def set_property(  # pragma: no cover - UE only
        self, asset: AssetHandle, path: list[str], value: Any
    ) -> None:
        if len(path) == 1:
            asset.set_editor_property(path[0], value)
            return
        # Nested struct: UE hands out struct values by copy, so walk down,
        # set the leaf, then write each (possibly mutated) struct back up.
        chain = [asset]
        for token in path[:-1]:
            chain.append(chain[-1].get_editor_property(token))
        chain[-1].set_editor_property(path[-1], value)
        for i in range(len(chain) - 2, -1, -1):
            chain[i].set_editor_property(path[i], chain[i + 1])

    def save(self, asset: AssetHandle) -> None:  # pragma: no cover - UE only
        self._unreal.EditorAssetLibrary.save_loaded_asset(asset)

    @contextmanager
    def transaction(self, description: str) -> Iterator[None]:  # pragma: no cover - UE only
        with self._unreal.ScopedEditorTransaction(description):
            yield

    def _top_level_path(self, class_path: str) -> Any:  # pragma: no cover - UE only
        """Convert ``/Script/Module.Class`` into a ``unreal.TopLevelAssetPath``."""
        package, _, asset = class_path.rpartition(".")
        return self._unreal.TopLevelAssetPath(package or class_path, asset)
