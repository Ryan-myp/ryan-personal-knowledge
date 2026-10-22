"""Storage operations for the versioned semantic knowledge index."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from agents.agent_platform.data.semantic import validate_vector


MAX_SEMANTIC_RECORDS = 100_000
MAX_SEMANTIC_DIMENSIONS = 8_192


def rebuild_knowledge_semantic_index(
    connection: Any,
    *,
    mysql: bool,
    records: Sequence[Mapping[str, Any]],
    scope: str,
    fingerprint: str,
) -> bool:
    normalized_scope = str(scope or "").strip()
    normalized_fingerprint = str(fingerprint or "").strip()
    if not normalized_scope or not normalized_fingerprint:
        raise ValueError("semantic index scope and fingerprint are required")
    if len(records) > MAX_SEMANTIC_RECORDS:
        raise ValueError("semantic index record limit exceeded")
    rows = _normalize_records(records, normalized_scope)
    dimension = rows[0][4] if rows else 0
    if mysql:
        connection.begin()
    else:
        connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "DELETE FROM knowledge_semantic_vectors WHERE scope = ?",
            (normalized_scope,),
        )
        if rows:
            connection.executemany(
                """INSERT INTO knowledge_semantic_vectors
                   (scope, chunk_id, document_id, vector, dimension)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (
                        row[0], row[1], row[2],
                        json.dumps(row[3], allow_nan=False, separators=(",", ":")),
                        row[4],
                    )
                    for row in rows
                ],
            )
        metadata = (
            normalized_scope,
            normalized_fingerprint,
            dimension,
            len(rows),
            datetime.now(timezone.utc).isoformat(),
        )
        statement = (
            """INSERT INTO knowledge_semantic_index_meta
               (scope, fingerprint, dimension, record_count, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE fingerprint = VALUES(fingerprint),
                 dimension = VALUES(dimension), record_count = VALUES(record_count),
                 updated_at = VALUES(updated_at)"""
            if mysql
            else
            """INSERT INTO knowledge_semantic_index_meta
               (scope, fingerprint, dimension, record_count, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(scope) DO UPDATE SET
                 fingerprint = excluded.fingerprint,
                 dimension = excluded.dimension,
                 record_count = excluded.record_count,
                 updated_at = excluded.updated_at"""
        )
        connection.execute(statement, metadata)
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise


def search_knowledge_semantic_index(
    connection: Any,
    *,
    query_vector: Sequence[float],
    scope: str,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_scope = str(scope or "").strip()
    if not normalized_scope or limit <= 0:
        return []
    query = validate_vector(query_vector)
    rows = connection.execute(
        """SELECT chunk_id, document_id, vector
           FROM knowledge_semantic_vectors
           WHERE scope = ? AND dimension = ?
           LIMIT ?""",
        (
            normalized_scope,
            len(query),
            MAX_SEMANTIC_RECORDS,
        ),
    ).fetchall()
    return [
        {
            "chunk_id": str(row["chunk_id"]),
            "document_id": str(row["document_id"]),
            "vector": _decode_vector(row["vector"]),
        }
        for row in rows
    ]


def is_knowledge_semantic_index_current(
    connection: Any,
    *,
    scope: str,
    fingerprint: str,
) -> bool:
    row = connection.execute(
        """SELECT fingerprint FROM knowledge_semantic_index_meta
           WHERE scope = ?""",
        (str(scope or "").strip(),),
    ).fetchone()
    return bool(row and str(row["fingerprint"] or "") == str(fingerprint or ""))


def _normalize_records(
    records: Sequence[Mapping[str, Any]],
    scope: str,
) -> list[tuple[str, str, str, tuple[float, ...], int]]:
    result: list[tuple[str, str, str, tuple[float, ...], int]] = []
    seen: set[str] = set()
    dimension = None
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("semantic index record must be an object")
        chunk_id = str(record.get("chunk_id") or "").strip()
        document_id = str(record.get("document_id") or "").strip()
        if not chunk_id or not document_id or chunk_id in seen:
            raise ValueError("semantic index records require unique chunk and document IDs")
        vector = validate_vector(record.get("vector") or (), expected_dimension=dimension)
        if len(vector) > MAX_SEMANTIC_DIMENSIONS:
            raise ValueError("semantic index vector dimension limit exceeded")
        if any(not math.isfinite(value) for value in vector):
            raise ValueError("semantic index vectors must be finite")
        dimension = len(vector)
        seen.add(chunk_id)
        result.append((scope, chunk_id, document_id, vector, dimension))
    return result


def _decode_vector(value: Any) -> list[float]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return list(validate_vector(parsed or ()))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


__all__ = [
    "is_knowledge_semantic_index_current",
    "rebuild_knowledge_semantic_index",
    "search_knowledge_semantic_index",
]
