"""Ports for private creative-asset persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class StoredCreativeAsset(Protocol):
    """Verified asset metadata and an optional private file reference."""

    metadata: Mapping[str, Any]
    content: bytes | None
    path: Path | None


@runtime_checkable
class CreativeAssetStore(Protocol):
    """Identity-scoped storage required by creative media Tools."""

    def put(
        self,
        content: bytes,
        *,
        filename: str,
        media_type: str,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    def create_pending(
        self,
        *,
        filename: str,
        media_type: str,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    def get(
        self,
        asset_id: str,
        *,
        tenant_id: str,
        user_id: str,
        include_content: bool = True,
    ) -> StoredCreativeAsset: ...

    def list(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
    ) -> list[Mapping[str, Any]]: ...

    def update(
        self,
        asset_id: str,
        *,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    def complete(
        self,
        asset_id: str,
        content: bytes,
        *,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


__all__ = ["CreativeAssetStore", "StoredCreativeAsset"]
