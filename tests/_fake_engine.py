"""An in-memory `EngineAdapter` for testing the sync orchestration without UE."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from game_data_tools.config import AssetFilter


class FakeAsset:
    """A stand-in DataAsset: a name/class/package plus a nested property dict."""

    def __init__(
        self,
        name: str,
        class_path: str,
        package_path: str,
        props: dict[str, Any] | None = None,
    ):
        self.name = name
        self.class_path = class_path
        self.package_path = package_path
        self.props: dict[str, Any] = props or {}
        self.saved = False


def _get(props: dict[str, Any], path: list[str]) -> Any:
    obj: Any = props
    for token in path:
        obj = obj[token]
    return obj


def _set(props: dict[str, Any], path: list[str], value: Any) -> None:
    obj = props
    for token in path[:-1]:
        obj = obj.setdefault(token, {})
    obj[path[-1]] = value


def _matches_path(pkg: str, base: str, recursive: bool) -> bool:
    return pkg == base or (recursive and pkg.startswith(base.rstrip("/") + "/"))


class FakeEngineAdapter:
    """Implements the `EngineAdapter` Protocol over a list of `FakeAsset`."""

    def __init__(self, assets: list[FakeAsset]):
        self.assets = list(assets)
        self.transactions: list[str] = []

    def find_assets(self, flt: AssetFilter) -> list[FakeAsset]:
        out = []
        for a in self.assets:
            if flt.class_paths and a.class_path not in flt.class_paths:
                continue
            if flt.package_paths and not any(
                _matches_path(a.package_path, p, flt.recursive_paths) for p in flt.package_paths
            ):
                continue
            out.append(a)
        return out

    def asset_key(self, asset: FakeAsset, key_property: str) -> Any:
        if key_property == "__name__":
            return asset.name
        if key_property == "__path__":
            return f"{asset.package_path}/{asset.name}"
        return _get(asset.props, key_property.split("."))

    def get_property(self, asset: FakeAsset, path: list[str]) -> Any:
        return _get(asset.props, path)

    def set_property(self, asset: FakeAsset, path: list[str], value: Any) -> None:
        _set(asset.props, path, value)

    def save(self, asset: FakeAsset) -> None:
        asset.saved = True

    @contextmanager
    def transaction(self, description: str) -> Iterator[None]:
        self.transactions.append(description)
        yield
