"""Persistence-backed adapter for the semantic index contract."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .semantic import cosine_similarity, validate_vector


class PersistentSemanticIndex:
    """Delegate vector lifecycle to a PersistenceBackend implementation."""

    def __init__(self, store: Any, *, max_records: int = 100_000) -> None:
        if max_records <= 0:
            raise ValueError("max_records must be positive")
        self.store = store
        self.max_records = int(max_records)

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
        query = validate_vector(vector)
        method = getattr(self.store, "search_knowledge_semantic_index", None)
        if not callable(method):
            raise RuntimeError("persistence backend lacks semantic index support")
        rows = method(query, scope=scope, limit=self.max_records)
        scored = []
        for row in rows:
            try:
                candidate = validate_vector(
                    row.get("vector") or (),
                    expected_dimension=len(query),
                )
                score = cosine_similarity(query, candidate)
            except (TypeError, ValueError):
                continue
            scored.append({
                "chunk_id": str(row.get("chunk_id") or ""),
                "document_id": str(row.get("document_id") or ""),
                "score": score,
            })
        scored.sort(key=lambda item: (-item["score"], item["chunk_id"]))
        return scored[: min(int(limit), 100)]


__all__ = ["PersistentSemanticIndex"]
