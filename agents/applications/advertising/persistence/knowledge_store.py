"""Domain-owned knowledge store operations behind the persistence facade."""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from .models import KnowledgeDocumentRecord, RawKnowledgeSourceRecord
from .errors import PersistenceConflictError


class KnowledgeRepository:
    def __init__(self, connection_provider, lock):
        self._get_conn = connection_provider
        self._lock = lock

    @staticmethod
    def _knowledge_row(row: Any) -> Optional[KnowledgeDocumentRecord]:
        return KnowledgeDocumentRecord.from_row(dict(row)) if row else None

    def create_knowledge_document(self, record: KnowledgeDocumentRecord) -> KnowledgeDocumentRecord:
        data = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO knowledge_documents
                       (document_id, tenant_id, title, content, platform, layer,
                        knowledge_type, source, source_ref, version, confidence,
                        tags, status, created_by, created_at, updated_at, published_at,
                        wiki_type, derived_from, raw_sha256, wikilinks)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["document_id"], data["tenant_id"], data["title"],
                        data["content"], data["platform"], data["layer"],
                        data["knowledge_type"], data["source"], data["source_ref"],
                        data["version"], data["confidence"],
                        json.dumps(data["tags"], ensure_ascii=False), data["status"],
                        data["created_by"], data["created_at"], data["updated_at"],
                        data["published_at"], data["wiki_type"], data["derived_from"],
                        data["raw_sha256"], json.dumps(data["wikilinks"], ensure_ascii=False),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError(
                    "knowledge document violates a persistence constraint"
                ) from exc
            conn.commit()
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (data["document_id"],),
                ).fetchone()
            ) or record

    def update_knowledge_document(
        self, document_id: str, *, tenant_id: str, data: dict[str, Any],
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE knowledge_documents
                   SET title = ?, content = ?, platform = ?, layer = ?,
                       knowledge_type = ?, source = ?, source_ref = ?,
                       version = ?, confidence = ?, tags = ?, updated_at = ?,
                       wiki_type = ?, derived_from = ?, raw_sha256 = ?, wikilinks = ?
                   WHERE document_id = ? AND tenant_id = ? AND status = 'draft'""",
                (
                    data["title"], data["content"], data["platform"], data["layer"],
                    data["knowledge_type"], data["source"], data["source_ref"],
                    data["version"], data["confidence"],
                    json.dumps(data["tags"], ensure_ascii=False), now,
                    data["wiki_type"], data["derived_from"], data["raw_sha256"],
                    json.dumps(data["wikilinks"], ensure_ascii=False),
                    str(document_id), str(tenant_id),
                ),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone()
            )

    def delete_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            existing = self._knowledge_row(conn.execute(
                "SELECT * FROM knowledge_documents WHERE document_id = ? AND tenant_id = ?",
                (str(document_id), str(tenant_id)),
            ).fetchone())
            if not existing:
                return None
            if existing.status == "published":
                conn.execute(
                    """UPDATE knowledge_documents
                       SET status = 'deprecated', updated_at = ?
                       WHERE document_id = ? AND tenant_id = ?""",
                    (now, str(document_id), str(tenant_id)),
                )
                conn.commit()
                return self._knowledge_row(conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone())
            conn.execute(
                "DELETE FROM knowledge_documents WHERE document_id = ? AND tenant_id = ?",
                (str(document_id), str(tenant_id)),
            )
            conn.commit()
            return existing

    def get_knowledge_document(
        self, document_id: str, *, tenant_id: Optional[str] = None,
    ) -> Optional[KnowledgeDocumentRecord]:
        query = "SELECT * FROM knowledge_documents WHERE document_id = ?"
        params: list[Any] = [str(document_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        with self._lock:
            return self._knowledge_row(self._get_conn().execute(query, params).fetchone())

    def list_knowledge_documents(
        self, tenant_id: str, status: Optional[str] = None, limit: int = 100,
    ) -> list[KnowledgeDocumentRecord]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM knowledge_documents WHERE tenant_id = ?"
        params: list[Any] = [str(tenant_id)]
        if status:
            query += " AND status = ?"
            params.append(str(status))
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
            return [self._knowledge_row(row) for row in rows if row]

    def publish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE knowledge_documents SET status = 'draft', updated_at = ?
                   WHERE tenant_id = ? AND title = (
                       SELECT title FROM knowledge_documents WHERE document_id = ?
                   ) AND status = 'published' AND document_id != ?""",
                (now, str(tenant_id), str(document_id), str(document_id)),
            )
            cursor = conn.execute(
                """UPDATE knowledge_documents
                   SET status = 'published', published_at = ?, updated_at = ?
                   WHERE document_id = ? AND tenant_id = ? AND status != 'deprecated'""",
                (now, now, str(document_id), str(tenant_id)),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone()
            )

    def unpublish_knowledge_document(
        self, document_id: str, *, tenant_id: str,
    ) -> Optional[KnowledgeDocumentRecord]:
        now = datetime.now().isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE knowledge_documents
                   SET status = 'draft', updated_at = ?
                   WHERE document_id = ? AND tenant_id = ? AND status = 'published'""",
                (now, str(document_id), str(tenant_id)),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._knowledge_row(
                conn.execute(
                    "SELECT * FROM knowledge_documents WHERE document_id = ?",
                    (str(document_id),),
                ).fetchone()
            )

    @staticmethod
    def _raw_knowledge_row(row: Any) -> Optional[RawKnowledgeSourceRecord]:
        return RawKnowledgeSourceRecord.from_row(dict(row)) if row else None

    def create_raw_knowledge_source(
        self, record: RawKnowledgeSourceRecord,
    ) -> RawKnowledgeSourceRecord:
        data = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO raw_knowledge_sources
                       (source_id, tenant_id, filename, media_type, content, sha256,
                       source_ref, status, created_by, created_at, updated_at,
                        ingest_task_id, ingest_error, ingest_attempts,
                        ingest_started_at, ingest_finished_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["source_id"], data["tenant_id"], data["filename"],
                        data["media_type"], data["content"], data["sha256"],
                        data["source_ref"], data["status"], data["created_by"],
                        data["created_at"], data["updated_at"],
                        data["ingest_task_id"], data["ingest_error"],
                        data["ingest_attempts"], data["ingest_started_at"],
                        data["ingest_finished_at"],
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError(
                    "raw knowledge source violates a persistence constraint"
                ) from exc
            conn.commit()
            return self._raw_knowledge_row(
                conn.execute(
                    "SELECT * FROM raw_knowledge_sources WHERE source_id = ?",
                    (data["source_id"],),
                ).fetchone()
            ) or record

    def get_raw_knowledge_source(
        self, source_id: str, *, tenant_id: Optional[str] = None,
    ) -> Optional[RawKnowledgeSourceRecord]:
        query = "SELECT * FROM raw_knowledge_sources WHERE source_id = ?"
        params: list[Any] = [str(source_id)]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(str(tenant_id))
        with self._lock:
            return self._raw_knowledge_row(
                self._get_conn().execute(query, params).fetchone()
            )

    def find_raw_knowledge_source_by_hash(
        self, tenant_id: str, sha256: str,
    ) -> Optional[RawKnowledgeSourceRecord]:
        with self._lock:
            return self._raw_knowledge_row(self._get_conn().execute(
                """SELECT * FROM raw_knowledge_sources
                   WHERE tenant_id = ? AND sha256 = ?""",
                (str(tenant_id), str(sha256)),
            ).fetchone())

    def update_raw_knowledge_source(
        self, source_id: str, *, tenant_id: str, data: dict[str, Any],
    ) -> Optional[RawKnowledgeSourceRecord]:
        allowed = {
            "status", "updated_at", "ingest_task_id", "ingest_error",
            "ingest_started_at", "ingest_finished_at",
        }
        if set(data) - allowed:
            raise ValueError("raw knowledge source content is immutable")
        assignments = ", ".join(f"{key} = ?" for key in data)
        if not assignments:
            return self.get_raw_knowledge_source(source_id, tenant_id=tenant_id)
        values = [data[key] for key in data] + [str(source_id), str(tenant_id)]
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE raw_knowledge_sources SET " + assignments +
                " WHERE source_id = ? AND tenant_id = ?",
                values,
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._raw_knowledge_row(conn.execute(
                "SELECT * FROM raw_knowledge_sources WHERE source_id = ?",
                (str(source_id),),
            ).fetchone())

    def claim_raw_knowledge_source(
        self,
        source_id: str,
        *,
        tenant_id: str,
        task_id: Optional[str],
        started_at: str,
    ) -> Optional[RawKnowledgeSourceRecord]:
        """Atomically move a retryable raw source into ``ingesting``."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE raw_knowledge_sources
                   SET status = 'ingesting',
                       updated_at = ?,
                       ingest_task_id = ?,
                       ingest_error = NULL,
                       ingest_attempts = ingest_attempts + 1,
                       ingest_started_at = ?,
                       ingest_finished_at = NULL
                   WHERE source_id = ? AND tenant_id = ?
                     AND status IN ('received', 'failed')""",
                (
                    str(started_at), task_id, str(started_at),
                    str(source_id), str(tenant_id),
                ),
            )
            conn.commit()
            if not cursor.rowcount:
                return None
            return self._raw_knowledge_row(
                conn.execute(
                    "SELECT * FROM raw_knowledge_sources WHERE source_id = ?",
                    (str(source_id),),
                ).fetchone()
            )

    def recover_stale_raw_knowledge_sources(
        self,
        *,
        tenant_id: str,
        stale_after_seconds: float = 900.0,
        recovered_at: Optional[str] = None,
    ) -> int:
        """Release raw sources whose ingest worker stopped heartbeating."""
        if recovered_at:
            current = datetime.fromisoformat(str(recovered_at))
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
        else:
            current = datetime.now(timezone.utc)
        cutoff = (
            current - timedelta(seconds=max(1.0, float(stale_after_seconds)))
        ).isoformat()
        finished_at = current.isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE raw_knowledge_sources
                   SET status = 'failed',
                       updated_at = ?,
                       ingest_finished_at = ?,
                       ingest_error = 'worker lease expired; retry required'
                   WHERE tenant_id = ?
                     AND status = 'ingesting'
                     AND ingest_started_at IS NOT NULL
                     AND ingest_started_at < ?""",
                (finished_at, finished_at, str(tenant_id), cutoff),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def list_raw_knowledge_sources(
        self, tenant_id: str, status: Optional[str] = None,
        limit: int = 100,
    ) -> list[RawKnowledgeSourceRecord]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM raw_knowledge_sources WHERE tenant_id = ?"
        params: list[Any] = [str(tenant_id)]
        if status:
            query += " AND status = ?"
            params.append(str(status))
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._get_conn().execute(query, params).fetchall()
            return [self._raw_knowledge_row(row) for row in rows if row]

    def _ensure_knowledge_search_index(self, conn: Any) -> bool:
        if not isinstance(conn, sqlite3.Connection):
            return False
        try:
            existing = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'knowledge_search_fts'"
            ).fetchone()
            if existing:
                columns = {
                    str(row[1])
                    for row in conn.execute("PRAGMA table_info(knowledge_search_fts)").fetchall()
                }
                if not {"category", "subcategory"}.issubset(columns):
                    conn.execute("DROP TABLE knowledge_search_fts")
            conn.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search_fts
                   USING fts5(
                       scope UNINDEXED,
                       chunk_id UNINDEXED,
                       document_id UNINDEXED,
                       title,
                       heading_path,
                       tags,
                       category,
                       subcategory,
                       content,
                       platform UNINDEXED,
                       knowledge_type UNINDEXED,
                       status UNINDEXED,
                       confidence UNINDEXED
                   )"""
            )
        except sqlite3.OperationalError:
            return False
        return True

    def rebuild_knowledge_search_index(
        self, chunks: list[dict[str, Any]], *, scope: str,
    ) -> bool:
        normalized_scope = str(scope or "").strip()
        if not normalized_scope:
            return False
        with self._lock:
            conn = self._get_conn()
            if not self._ensure_knowledge_search_index(conn):
                return False
            conn.execute(
                "DELETE FROM knowledge_search_fts WHERE scope = ?",
                (normalized_scope,),
            )
            rows = []
            for chunk in chunks or []:
                if not isinstance(chunk, dict):
                    continue
                rows.append(
                    (
                        normalized_scope,
                        str(chunk.get("chunk_id") or ""),
                        str(chunk.get("document_id") or ""),
                        str(chunk.get("title") or ""),
                        str(chunk.get("heading_path") or ""),
                        str(chunk.get("tags") or ""),
                        str(chunk.get("category") or ""),
                        str(chunk.get("subcategory") or ""),
                        str(chunk.get("content") or ""),
                        str(chunk.get("platform") or "all"),
                        str(chunk.get("knowledge_type") or "general"),
                        str(chunk.get("status") or "published"),
                        float(chunk.get("confidence") or 0.0),
                    )
                )
            if rows:
                conn.executemany(
                    """INSERT INTO knowledge_search_fts
                       (scope, chunk_id, document_id, title, heading_path,
                        tags, category, subcategory, content, platform,
                        knowledge_type, status, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
            conn.commit()
        return True

    def search_knowledge_search_index(
        self, query: str, *, scopes: list[str], limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_query = str(query or "").strip()
        normalized_scopes = [str(scope).strip() for scope in scopes if str(scope).strip()]
        if not safe_query or not normalized_scopes or limit <= 0:
            return []
        with self._lock:
            conn = self._get_conn()
            if not self._ensure_knowledge_search_index(conn):
                return []
            placeholders = ",".join("?" for _ in normalized_scopes)
            rows = conn.execute(
                f"""SELECT scope, chunk_id, document_id,
                           bm25(knowledge_search_fts, 8.0, 5.0, 3.0, 3.0, 3.0, 1.0) AS rank
                    FROM knowledge_search_fts
                    WHERE knowledge_search_fts MATCH ?
                      AND scope IN ({placeholders})
                      AND status = 'published'
                    ORDER BY rank ASC
                    LIMIT ?""",
                [safe_query, *normalized_scopes, max(1, min(int(limit), 500))],
            ).fetchall()
        return [dict(row) for row in rows]
