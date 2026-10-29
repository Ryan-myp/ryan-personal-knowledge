"""Scoped, optimistic-concurrency storage for optimization review records."""

import json
from datetime import datetime, timezone

OPTIMIZATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS optimization_reviews (
    review_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_optimization_reviews_owner
    ON optimization_reviews(tenant_id, user_id, updated_at);
"""


class OptimizationReviewRepository:
    def __init__(self, connection_provider, lock):
        self._get_conn, self._lock = connection_provider, lock

    def get(self, review_id, tenant_id, user_id):
        with self._lock:
            row = (
                self._get_conn()
                .execute(
                    "SELECT payload FROM optimization_reviews "
                    "WHERE review_id = ? AND tenant_id = ? AND user_id = ?",
                    (review_id, tenant_id, user_id),
                )
                .fetchone()
            )
            return json.loads(row[0]) if row else None

    def list(self, tenant_id, user_id, limit=20, offset=0):
        with self._lock:
            rows = (
                self._get_conn()
                .execute(
                    "SELECT payload FROM optimization_reviews WHERE tenant_id = ? AND user_id = ? "
                    "ORDER BY updated_at DESC, review_id LIMIT ? OFFSET ?",
                    (
                        tenant_id,
                        user_id,
                        max(1, min(int(limit), 50)),
                        max(0, min(int(offset), 10000)),
                    ),
                )
                .fetchall()
            )
            return [json.loads(row[0]) for row in rows]

    def save(self, review_id, tenant_id, user_id, payload, *, expected_version):
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError("invalid review version")
        encoded = json.dumps(
            {**payload, "version": expected_version + 1}, ensure_ascii=False, allow_nan=False
        )
        if len(encoded) > 64000:
            raise ValueError("optimization record exceeds storage limit")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            if expected_version == 0:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO optimization_reviews "
                    "(review_id, tenant_id, user_id, version, payload, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (review_id, tenant_id, user_id, 1, encoded, now),
                )
            else:
                cursor = conn.execute(
                    "UPDATE optimization_reviews SET version = ?, payload = ?, updated_at = ? "
                    "WHERE review_id = ? AND tenant_id = ? AND user_id = ? AND version = ?",
                    (
                        expected_version + 1,
                        encoded,
                        now,
                        review_id,
                        tenant_id,
                        user_id,
                        expected_version,
                    ),
                )
            conn.commit()
            return cursor.rowcount == 1
