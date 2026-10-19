"""Backend-neutral SQL helpers for complete-turn conversation pagination."""

from __future__ import annotations

from typing import Any, Optional

from .models import ConversationMessagePage, ConversationMessageRecord


def _find_cursor_anchor(
    connection: Any, session_id: str, cursor: str,
) -> tuple[str, str]:
    row = connection.execute(
        """SELECT MAX(created_at) AS sort_created_at,
                  MAX(message_id) AS sort_message_id
           FROM conversation_messages
           WHERE session_id = ?
             AND COALESCE(NULLIF(turn_id, ''), message_id) = (
                 SELECT COALESCE(NULLIF(turn_id, ''), message_id)
                 FROM conversation_messages
                 WHERE session_id = ? AND message_id = ?
             )""",
        (session_id, session_id, cursor),
    ).fetchone()
    if not row or row["sort_created_at"] is None:
        raise ValueError("历史消息游标无效，请重新打开对话")
    return str(row["sort_created_at"]), str(row["sort_message_id"])


def _query_page_rows(
    connection: Any,
    session_id: str,
    page_size: int,
    before_created_at: Optional[str],
    before_message_id: Optional[str],
) -> list[Any]:
    return connection.execute(
        """WITH turn_keys AS (
               SELECT COALESCE(NULLIF(turn_id, ''), message_id) AS turn_key,
                      MAX(created_at) AS sort_created_at,
                      MAX(message_id) AS sort_message_id
               FROM conversation_messages
               WHERE session_id = ?
               GROUP BY COALESCE(NULLIF(turn_id, ''), message_id)
           ),
           candidate_turns AS (
               SELECT turn_key, sort_created_at, sort_message_id
               FROM turn_keys
               WHERE ? IS NULL OR sort_created_at < ?
                  OR (sort_created_at = ? AND sort_message_id < ?)
               ORDER BY sort_created_at DESC, sort_message_id DESC
               LIMIT ?
           ),
           page_turns AS (
               SELECT turn_key
               FROM candidate_turns
               ORDER BY sort_created_at DESC, sort_message_id DESC
               LIMIT ?
           )
           SELECT messages.*,
                  (SELECT COUNT(*) FROM candidate_turns) AS page_turn_count
           FROM conversation_messages AS messages
           JOIN page_turns
             ON COALESCE(NULLIF(messages.turn_id, ''), messages.message_id)
                = page_turns.turn_key
           WHERE messages.session_id = ?
           ORDER BY messages.created_at ASC, messages.message_id ASC""",
        (
            session_id,
            before_created_at,
            before_created_at,
            before_created_at,
            before_message_id,
            page_size + 1,
            page_size,
            session_id,
        ),
    ).fetchall()


def list_conversation_message_page(
    connection: Any,
    session_id: str,
    limit: int = 10,
    before_message_id: Optional[str] = None,
) -> ConversationMessagePage:
    """Fetch recent turns or the next older page without splitting a turn."""
    page_size = min(max(1, int(limit)), 100)
    session_key = str(session_id)
    before_created_at = None
    before_id = None
    if before_message_id:
        before_created_at, before_id = _find_cursor_anchor(
            connection, session_key, str(before_message_id).strip(),
        )
    rows = _query_page_rows(
        connection, session_key, page_size, before_created_at, before_id,
    )
    if not rows:
        return ConversationMessagePage(records=[], has_more=False)

    turn_count = int(rows[0]["page_turn_count"])
    records = []
    for row in rows:
        record_data = dict(row)
        record_data.pop("page_turn_count", None)
        records.append(ConversationMessageRecord.from_row(record_data))
    return ConversationMessagePage(
        records=records,
        has_more=turn_count > page_size,
        next_cursor=records[0].message_id if turn_count > page_size else None,
    )


__all__ = ["list_conversation_message_page"]
