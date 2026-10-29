"""Bounded legacy sidebar reads behind the persistence boundary."""

from __future__ import annotations

from typing import Any

from .models import ConversationMessagePage, ConversationMessageRecord


def list_conversation_preview_messages(
    connection: Any, session_ids: list[str], *, user_id: str, tenant_id: str,
    limit_per_session: int = 50,
) -> dict[str, ConversationMessagePage]:
    ids = list(dict.fromkeys(str(value) for value in session_ids))
    if not ids:
        return {}
    if len(ids) > 256:
        raise ValueError("conversation preview batch supports at most 256 sessions")
    limit = min(max(1, int(limit_per_session)), 64)
    placeholders = ", ".join("?" for _ in ids)
    rows = connection.execute(
        """WITH ranked_messages AS (
               SELECT messages.*,
                      ROW_NUMBER() OVER (
                          PARTITION BY messages.session_id
                          ORDER BY messages.created_at DESC, messages.message_id DESC
                      ) AS recent_rank,
                      ROW_NUMBER() OVER (
                          PARTITION BY messages.session_id
                          ORDER BY CASE WHEN messages.role = 'user' THEN 0 ELSE 1 END,
                                   messages.created_at ASC, messages.message_id ASC
                      ) AS source_rank,
                      COUNT(*) OVER (PARTITION BY messages.session_id) AS record_count
               FROM conversation_messages AS messages
               JOIN sessions ON sessions.session_id = messages.session_id
               WHERE sessions.user_id = ? AND sessions.tenant_id = ?
                 AND messages.session_id IN (""" + placeholders + """))
           SELECT * FROM ranked_messages
           WHERE recent_rank <= ? OR source_rank = 1
           ORDER BY session_id, created_at, message_id""",
        (str(user_id), str(tenant_id), *ids, limit),
    ).fetchall()
    records: dict[str, list[ConversationMessageRecord]] = {}
    counts: dict[str, int] = {}
    for row in rows:
        data = dict(row)
        session_id = str(data["session_id"])
        counts[session_id] = int(data.pop("record_count"))
        data.pop("recent_rank")
        data.pop("source_rank")
        records.setdefault(session_id, []).append(ConversationMessageRecord.from_row(data))
    return {
        session_id: ConversationMessagePage(
            records=messages, has_more=counts[session_id] > len(messages),
        )
        for session_id, messages in records.items()
    }
