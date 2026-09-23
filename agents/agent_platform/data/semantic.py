"""Provider-neutral semantic retrieval ports and a bounded local index.

The Agent platform does not require a particular embedding vendor or vector
database.  Knowledge sources can opt into these ports when they have a
trusted embedding provider.  The in-memory implementation is intentionally
small and deterministic so contract tests do not need a network service.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


class EmbeddingProvider(Protocol):
    """Bounded text-to-vector adapter owned by an integration boundary."""

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        ...


class SemanticIndex(Protocol):
    """Vector index port with an explicit scope for tenant isolation."""

    def rebuild(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        scope: str,
    ) -> None:
        ...

    def search(
        self,
        vector: Sequence[float],
        *,
        scope: str,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        ...


def validate_vector(
    value: Sequence[float],
    *,
    expected_dimension: int | None = None,
) -> tuple[float, ...]:
    """Normalize finite, bounded vectors before they reach an index."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("embedding must be a numeric sequence")
    vector = tuple(float(item) for item in value)
    if not vector:
        raise ValueError("embedding must not be empty")
    if expected_dimension is not None and len(vector) != expected_dimension:
        raise ValueError("embedding dimension mismatch")
    if any(not math.isfinite(item) for item in vector):
        raise ValueError("embedding must contain finite values")
    return vector


def cosine_similarity(
    left: Sequence[float],
    right: Sequence[float],
) -> float:
    left_vector = validate_vector(left)
    right_vector = validate_vector(right, expected_dimension=len(left_vector))
    denominator = math.sqrt(sum(item * item for item in left_vector)) * math.sqrt(
        sum(item * item for item in right_vector)
    )
    if denominator == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left_vector, right_vector)) / denominator


@dataclass(frozen=True)
class SemanticHit:
    """Stable index result that keeps the source chunk addressable."""

    chunk_id: str
    score: float
    scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": round(float(self.score), 6),
            "scope": self.scope,
        }


class InMemorySemanticIndex:
    """Thread-safe, bounded cosine index for local development and tests."""

    def __init__(self, *, max_records: int = 100_000) -> None:
        if max_records <= 0:
            raise ValueError("max_records must be positive")
        self.max_records = int(max_records)
        self._records: dict[tuple[str, str], tuple[float, ...]] = {}
        self._lock = threading.RLock()

    def rebuild(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        scope: str,
    ) -> None:
        normalized_scope = str(scope or "default").strip() or "default"
        staged: dict[tuple[str, str], tuple[float, ...]] = {}
        for record in records:
            if not isinstance(record, Mapping):
                raise ValueError("semantic record must be an object")
            chunk_id = str(record.get("chunk_id") or "").strip()
            if not chunk_id:
                raise ValueError("semantic record requires chunk_id")
            staged[(normalized_scope, chunk_id)] = validate_vector(
                record.get("vector") or ()
            )
        if len(staged) > self.max_records:
            raise ValueError("semantic index record limit exceeded")
        with self._lock:
            self._records = {
                key: value
                for key, value in self._records.items()
                if key[0] != normalized_scope
            }
            self._records.update(staged)

    def search(
        self,
        vector: Sequence[float],
        *,
        scope: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        normalized_scope = str(scope or "default").strip() or "default"
        query = validate_vector(vector)
        with self._lock:
            candidates = [
                (chunk_id, stored)
                for (record_scope, chunk_id), stored in self._records.items()
                if record_scope == normalized_scope
            ]
        hits: list[SemanticHit] = []
        for chunk_id, stored in candidates:
            if len(stored) != len(query):
                continue
            hits.append(SemanticHit(
                chunk_id=chunk_id,
                score=cosine_similarity(query, stored),
                scope=normalized_scope,
            ))
        hits.sort(key=lambda item: (-item.score, item.chunk_id))
        return [item.to_dict() for item in hits[: min(int(limit), 100)]]


class HashEmbeddingProvider:
    """Deterministic local embedding adapter for offline contract checks."""

    _TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9_]+")

    def __init__(self, *, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = int(dimensions)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            tokens = self._TOKEN_RE.findall(str(text or "").lower())
            for token in tokens:
                digest = hashlib.blake2b(
                    token.encode("utf-8"),
                    digest_size=8,
                ).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] % 2 else -1.0
                vector[index] += sign
            result.append(vector)
        return result


__all__ = [
    "EmbeddingProvider",
    "HashEmbeddingProvider",
    "InMemorySemanticIndex",
    "SemanticHit",
    "SemanticIndex",
    "cosine_similarity",
    "validate_vector",
]
