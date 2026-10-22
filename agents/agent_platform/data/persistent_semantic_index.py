"""Persistence-backed adapter for the semantic index contract."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import heapq
import math
from threading import RLock
from typing import Any, Mapping, Sequence

from .semantic import validate_vector


@dataclass(frozen=True)
class _Snapshot:
    revision: tuple
    rows: tuple
    value_count: int


def _unit_vector(vector: Sequence[float]) -> tuple[float, ...]:
    normalized = validate_vector(vector)
    magnitude = math.hypot(*normalized)
    return tuple(value / magnitude for value in normalized) if magnitude else normalized


class PersistentSemanticIndex:
    """Delegate vector lifecycle to a PersistenceBackend implementation."""

    def __init__(
        self, store: Any, *, max_records: int = 100_000,
        max_cached_values: int = 2_000_000,
    ) -> None:
        if max_records <= 0 or max_cached_values <= 0:
            raise ValueError("semantic index budgets must be positive")
        self.store = store
        self.max_records = int(max_records)
        self.max_cached_values = int(max_cached_values)
        self._cache: OrderedDict[str, _Snapshot] = OrderedDict()
        self._lock = RLock()
        self._loads = 0
        self._hits = 0

    def rebuild(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        scope: str,
        fingerprint: str = "",
    ) -> None:
        if len(records) > self.max_records:
            raise ValueError("semantic index record limit exceeded")
        method = getattr(self.store, "rebuild_knowledge_semantic_index", None)
        if not callable(method):
            raise RuntimeError("persistence backend lacks semantic index support")
        method(list(records), scope=scope, fingerprint=fingerprint)
        with self._lock:
            self._cache.pop(scope, None)

    def is_current(self, *, scope: str, fingerprint: str) -> bool:
        method = getattr(self.store, "is_knowledge_semantic_index_current", None)
        return bool(
            callable(method)
            and method(scope=scope, fingerprint=fingerprint)
        )

    def search(
        self,
        vector: Sequence[float],
        *,
        scope: str,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        if limit <= 0:
            return []
        query = _unit_vector(vector)
        with self._lock:
            snapshot = self._snapshot(scope, query)
        scored = (
            {"chunk_id": chunk_id, "document_id": document_id,
             "score": math.fsum(a * b for a, b in zip(query, candidate))}
            for chunk_id, document_id, candidate in snapshot.rows
            if len(candidate) == len(query)
        )
        return heapq.nsmallest(
            min(int(limit), 100), scored,
            key=lambda item: (-item["score"], item["chunk_id"]),
        )

    def _snapshot(self, scope: str, query: tuple) -> _Snapshot:
        metadata = self.store.get_knowledge_semantic_index_metadata(scope=scope)
        revision = (
            metadata.get("fingerprint"), metadata.get("updated_at"),
            metadata.get("dimension"), metadata.get("record_count"),
        )
        cached = self._cache.get(scope)
        if cached and cached.revision == revision:
            self._cache.move_to_end(scope)
            self._hits += 1
            return cached
        self._cache.pop(scope, None)
        count = int(metadata.get("record_count") or 0)
        if count and int(metadata["dimension"]) != len(query):
            return _Snapshot(revision, (), 0)
        values = count * int(metadata.get("dimension") or 0)
        if count > self.max_records or values > self.max_cached_values:
            raise RuntimeError("semantic snapshot exceeds local index budget")
        rows = self.store.search_knowledge_semantic_index(
            query, scope=scope, limit=self.max_records,
        )
        prepared = tuple(
            (str(row["chunk_id"]), str(row["document_id"]), _unit_vector(row["vector"]))
            for row in rows
        )
        if metadata != self.store.get_knowledge_semantic_index_metadata(scope=scope):
            raise RuntimeError("semantic snapshot changed while loading; retry query")
        snapshot = _Snapshot(revision, prepared, sum(len(row[2]) for row in prepared))
        self._loads += 1
        while self._cache and (
            len(self._cache) >= 256
            or sum(item.value_count for item in self._cache.values()) + values
            > self.max_cached_values
        ):
            self._cache.popitem(last=False)
        self._cache[scope] = snapshot
        return snapshot

    def metrics(self) -> dict[str, int]:
        with self._lock:
            return {
                "cached_scopes": len(self._cache), "snapshot_loads": self._loads,
                "cache_hits": self._hits,
                "cached_values": sum(item.value_count for item in self._cache.values()),
                "max_cached_values": self.max_cached_values,
            }


__all__ = ["PersistentSemanticIndex"]
