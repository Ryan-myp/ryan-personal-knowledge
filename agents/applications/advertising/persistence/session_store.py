"""Domain-owned session store operations behind the persistence facade."""

from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, List
from .models import ConversationMessagePage, ConversationMessageRecord
from .conversation_pagination import list_conversation_message_page as query_conversation_message_page


class SessionRepository:
    def __init__(self, connection_provider, lock):
        self._get_conn = connection_provider
        self._lock = lock

    def create_session(self, session_id: str, user_id: str, account_id: str = None,
                       metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            # Session creation is intentionally insert-once. Replacing a row
            # would clear a cross-instance lease while another turn is using
            # the session; metadata updates have their own method.
            session_metadata = metadata or {}
            tenant_id = str(session_metadata.get("tenant_id") or "default")
            sql = """INSERT OR IGNORE INTO sessions
                     (session_id, user_id, tenant_id, account_id, created_at, updated_at, metadata)
                     VALUES (?, ?, ?, ?, ?, ?, ?)"""
            conn.execute(sql, (session_id, user_id, tenant_id, account_id, now, now,
                               json.dumps(session_metadata)))
            conn.commit()

    def update_session(self, session_id: str, metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            sql = "UPDATE sessions SET updated_at = ?, metadata = ? WHERE session_id = ?"
            conn.execute(sql, (datetime.now().isoformat(), json.dumps(metadata or {}), session_id))
            conn.commit()

    def get_session(
        self, session_id: str, user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            query = "SELECT * FROM sessions WHERE session_id = ?"
            params: list[Any] = [session_id]
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(str(user_id))
            if tenant_id is not None:
                query += " AND tenant_id = ?"
                params.append(str(tenant_id))
            row = conn.execute(query, params).fetchone()
            if row:
                return dict(row)
            return None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session; SQLite foreign keys remove its local history."""
        with self._lock:
            conn = self._get_conn()
            # Keep durable run/event replay data within the same privacy
            # boundary even for databases created before the FK was added.
            conn.execute(
                "DELETE FROM execution_runs WHERE session_id = ?",
                (str(session_id),),
            )
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (str(session_id),)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(
        self, user_id: str = None, limit: int = 50,
        tenant_id: Optional[str] = None,
        before_updated_at: Optional[str] = None,
        before_session_id: Optional[str] = None,
    ) -> List[dict]:
        if (before_updated_at is None) != (before_session_id is None):
            raise ValueError("session cursor requires updated_at and session_id")
        with self._lock:
            conn = self._get_conn()
            clauses: list[str] = []
            params: list[Any] = []
            if user_id:
                clauses.append("user_id = ?")
                params.append(str(user_id))
            if tenant_id is not None:
                clauses.append("tenant_id = ?")
                params.append(str(tenant_id))
            if before_updated_at is not None:
                clauses.append(
                    "(updated_at < ? OR (updated_at = ? AND session_id < ?))"
                )
                params.extend((
                    str(before_updated_at),
                    str(before_updated_at),
                    str(before_session_id),
                ))
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            params.append(limit)
            rows = conn.execute(
                "SELECT * FROM sessions" + where
                + " ORDER BY updated_at DESC, session_id DESC LIMIT ?", params
            ).fetchall()
            return [dict(r) for r in rows]

    def acquire_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        """Atomically reserve a session across Runtime instances."""
        if not session_id or not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now(timezone.utc)
        now_text = now.isoformat()
        expires_text = (now + timedelta(seconds=float(lease_seconds))).isoformat()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE sessions
                   SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
                   WHERE session_id = ?
                     AND (lease_owner IS NULL OR lease_owner = ?
                          OR lease_expires_at IS NULL OR lease_expires_at <= ?)""",
                (
                    str(lease_owner), expires_text, now_text, str(session_id),
                    str(lease_owner), now_text,
                ),
            )
            conn.commit()
            return cursor.rowcount == 1

    def heartbeat_session_lease(
        self, session_id: str, lease_owner: str, lease_seconds: float = 300.0,
    ) -> bool:
        if not session_id or not lease_owner or float(lease_seconds) <= 0:
            return False
        now = datetime.now(timezone.utc)
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE sessions SET lease_expires_at = ?, updated_at = ?
                   WHERE session_id = ? AND lease_owner = ?""",
                (
                    (now + timedelta(seconds=float(lease_seconds))).isoformat(),
                    now.isoformat(), str(session_id), str(lease_owner),
                ),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def release_session_lease(self, session_id: str, lease_owner: str) -> bool:
        if not session_id or not lease_owner:
            return False
        with self._lock:
            cursor = self._get_conn().execute(
                """UPDATE sessions SET lease_owner = NULL, lease_expires_at = NULL
                   WHERE session_id = ? AND lease_owner = ?""",
                (str(session_id), str(lease_owner)),
            )
            self._get_conn().commit()
            return cursor.rowcount == 1

    def record_conversation_message(self, record: ConversationMessageRecord) -> None:
        data = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO conversation_messages
                   (message_id, session_id, turn_id, role, content, created_at,
                    tool_call_id, name, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["message_id"], data["session_id"], data["turn_id"],
                    data["role"], data["content"], data["created_at"],
                    data.get("tool_call_id"), data.get("name"),
                    json.dumps(data.get("metadata") or {}, ensure_ascii=False),
                ),
            )
            conn.commit()

    def list_conversation_messages(
        self, session_id: str, limit: int = 200,
    ) -> List[ConversationMessageRecord]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT * FROM conversation_messages
                   WHERE session_id = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
            return [
                ConversationMessageRecord.from_row(dict(row))
                for row in reversed(rows)
            ]

    def list_recent_user_messages(
        self, session_id: str, limit: int = 128,
    ) -> list[dict[str, str]]:
        with self._lock:
            rows = self._get_conn().execute(
                """SELECT message_id, turn_id, SUBSTR(content, 1, 1200) AS content
                   FROM conversation_messages
                   WHERE session_id = ? AND role = 'user'
                   ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (str(session_id), min(max(1, int(limit)), 128)),
            ).fetchall()
            return [dict(row) for row in reversed(rows)]

    def list_conversation_message_page(
        self,
        session_id: str,
        limit: int = 10,
        before_message_id: Optional[str] = None,
    ) -> ConversationMessagePage:
        with self._lock:
            return query_conversation_message_page(
                self._get_conn(),
                session_id,
                limit=limit,
                before_message_id=before_message_id,
            )

    def update_conversation_message_metadata(
        self,
        session_id: str,
        turn_id: str,
        role: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Merge metadata into matching transcript rows without changing content."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT message_id, metadata
                   FROM conversation_messages
                   WHERE session_id = ? AND turn_id = ? AND role = ?""",
                (str(session_id), str(turn_id), str(role)),
            ).fetchall()
            if not rows:
                return 0
            updates = []
            for row in rows:
                current = row["metadata"]
                if isinstance(current, str):
                    try:
                        current = json.loads(current or "{}")
                    except (TypeError, ValueError):
                        current = {}
                merged = dict(current) if isinstance(current, dict) else {}
                merged.update(dict(metadata or {}))
                updates.append((
                    json.dumps(merged, ensure_ascii=False, default=str),
                    str(row["message_id"]),
                ))
            conn.executemany(
                "UPDATE conversation_messages SET metadata = ? WHERE message_id = ?",
                updates,
            )
            conn.commit()
            return len(updates)
