"""Storage helpers for scoped conversation-feedback writes and aggregates."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from agents.agent_platform.evals.regression import RegressionAssertions
from .feedback_review_pages import FeedbackReviewQuery, read_feedback_review_page


def save_conversation_feedback(
    connection: Any,
    *,
    mysql: bool,
    session_id: str,
    turn_id: str,
    user_id: str,
    tenant_id: str,
    feedback: dict[str, Any],
) -> bool:
    """Atomically persist transcript feedback and its minimal analytics row."""
    rating = str(feedback.get("rating") or "")
    submitted_at = str(feedback.get("submitted_at") or "")
    if rating not in {"positive", "negative"} or not submitted_at:
        raise ValueError("feedback rating and submitted_at are required")

    safe_feedback = {
        "rating": rating,
        "reason": str(feedback.get("reason") or "")[:1000] or None,
        "submitted_at": submitted_at,
        "schema_version": 1,
    }
    if mysql:
        connection.begin()
    else:
        connection.execute("BEGIN IMMEDIATE")
    try:
        lock_suffix = " FOR UPDATE" if mysql else ""
        session = connection.execute(
            """SELECT session_id FROM sessions
               WHERE session_id = ? AND user_id = ? AND tenant_id = ?"""
            + lock_suffix,
            (str(session_id), str(user_id), str(tenant_id)),
        ).fetchone()
        if not session:
            connection.rollback()
            return False

        messages = connection.execute(
            """SELECT message_id, metadata
               FROM conversation_messages
               WHERE session_id = ? AND turn_id = ? AND role = 'assistant'""",
            (str(session_id), str(turn_id)),
        ).fetchall()
        if not messages:
            connection.rollback()
            return False

        _write_turn_metadata(connection, messages, safe_feedback)
        _upsert_feedback_aggregate(
            connection,
            session_id=session_id,
            turn_id=turn_id,
            user_id=user_id,
            tenant_id=tenant_id,
            rating=rating,
            reason=safe_feedback["reason"],
            submitted_at=submitted_at,
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise


def _write_turn_metadata(
    connection: Any,
    messages: list[Any],
    feedback: dict[str, Any],
) -> None:
    for message in messages:
        current = message["metadata"]
        if isinstance(current, str):
            try:
                current = json.loads(current or "{}")
            except (TypeError, ValueError):
                current = {}
        merged = dict(current) if isinstance(current, dict) else {}
        merged["user_feedback"] = feedback
        connection.execute(
            "UPDATE conversation_messages SET metadata = ? WHERE message_id = ?",
            (
                json.dumps(merged, ensure_ascii=False, default=str),
                str(message["message_id"]),
            ),
        )


def _upsert_feedback_aggregate(
    connection: Any,
    *,
    session_id: str,
    turn_id: str,
    user_id: str,
    tenant_id: str,
    rating: str,
    reason: str | None,
    submitted_at: str,
) -> None:
    connection.execute(
        """INSERT INTO conversation_feedback
           (feedback_id, session_id, turn_id, tenant_id, user_id, rating,
            reason, submitted_at, review_status, assertions)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', '{}')
           ON CONFLICT(session_id, turn_id) DO UPDATE SET
               tenant_id = excluded.tenant_id,
               user_id = excluded.user_id,
               rating = excluded.rating,
               reason = excluded.reason,
               submitted_at = excluded.submitted_at,
               review_status = 'pending',
               reviewer_id = NULL,
               reviewed_at = NULL,
               expected_behavior = NULL,
               assertions = '{}'""",
        (
            str(uuid.uuid4()), str(session_id), str(turn_id),
            str(tenant_id), str(user_id), rating, reason, submitted_at,
        ),
    )


def get_conversation_feedback_trend(
    connection: Any,
    *,
    days: int,
    user_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Query no more than 180 daily/rating aggregates for one principal."""
    if int(days) not in {7, 30, 90}:
        raise ValueError("days must be one of 7, 30, or 90")
    now = datetime.now(timezone.utc)
    start_date = now.date() - timedelta(days=int(days) - 1)
    start_at = datetime.combine(
        start_date, datetime.min.time(), tzinfo=timezone.utc,
    ).isoformat()
    end_at = now.isoformat()
    rows = connection.execute(
        """SELECT substr(submitted_at, 1, 10) AS feedback_day,
                  rating, COUNT(*) AS count
           FROM conversation_feedback
           WHERE tenant_id = ? AND user_id = ?
             AND submitted_at >= ? AND submitted_at <= ?
           GROUP BY substr(submitted_at, 1, 10), rating
           ORDER BY feedback_day""",
        (str(tenant_id), str(user_id), start_at, end_at),
    ).fetchall()

    daily_counts = {
        (start_date + timedelta(days=index)).isoformat(): {
            "positive": 0, "negative": 0,
        }
        for index in range(int(days))
    }
    for row in rows:
        day = str(row["feedback_day"] or "")
        rating = str(row["rating"] or "")
        if day in daily_counts and rating in {"positive", "negative"}:
            daily_counts[day][rating] = int(row["count"] or 0)

    daily = [
        {
            "date": day,
            "positive": counts["positive"],
            "negative": counts["negative"],
            "total": counts["positive"] + counts["negative"],
        }
        for day, counts in daily_counts.items()
    ]
    positive = sum(item["positive"] for item in daily)
    negative = sum(item["negative"] for item in daily)
    total = positive + negative
    return {
        "days": int(days),
        "since": start_date.isoformat(),
        "until": now.date().isoformat(),
        "total": total,
        "positive": positive,
        "negative": negative,
        "positive_rate": positive / total if total else None,
        "daily": daily,
    }


def list_conversation_feedback_review_queue(
    connection: Any,
    *,
    tenant_id: str,
    status: str = "pending",
    limit: int = 50,
) -> list[dict[str, Any]]:
    if status not in {"pending", "candidate", "dismissed"}:
        raise ValueError("unsupported feedback review status")
    filters = FeedbackReviewQuery(
        tenant_id=tenant_id, status=status, limit=max(1, min(int(limit), 100)),
    )
    return read_feedback_review_page(connection, filters)['items']


def review_conversation_feedback(
    connection: Any,
    *,
    feedback_id: str,
    tenant_id: str,
    reviewer_id: str,
    review_status: str,
    expected_behavior: str,
    reviewed_at: str,
    assertions: dict[str, Any] | None = None,
) -> bool:
    if review_status not in {"candidate", "dismissed"}:
        raise ValueError("review status must be candidate or dismissed")
    expected = str(expected_behavior or "").strip()
    if review_status == "candidate" and not expected:
        raise ValueError("expected behavior is required for a regression candidate")
    if len(expected) > 2000:
        raise ValueError("expected behavior exceeds 2000 characters")
    if not str(reviewer_id or "").strip() or not str(reviewed_at or "").strip():
        raise ValueError("reviewer and reviewed_at are required")
    validated_assertions = RegressionAssertions.model_validate(assertions or {})
    cursor = connection.execute(
        """UPDATE conversation_feedback
           SET review_status = ?, reviewer_id = ?, reviewed_at = ?,
               expected_behavior = ?, assertions = ?
           WHERE feedback_id = ? AND tenant_id = ? AND rating = 'negative'""",
        (
            review_status,
            str(reviewer_id),
            str(reviewed_at),
            expected or None,
            validated_assertions.model_dump_json(exclude_defaults=True),
            str(feedback_id),
            str(tenant_id),
        ),
    )
    connection.commit()
    return int(cursor.rowcount or 0) == 1


__all__ = [
    "get_conversation_feedback_trend",
    "list_conversation_feedback_review_queue",
    "review_conversation_feedback",
    "save_conversation_feedback",
]
