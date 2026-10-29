"""Persist feedback for authenticated conversation turns."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from agents.applications.advertising.persistence.feedback_review_pages import FeedbackReviewQuery


class AdConversationFeedbackServices:
    """Own scoped feedback validation and durable transcript updates."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def submit_conversation_feedback(
        self,
        *,
        session_id: str,
        turn_id: str,
        rating: str,
        reason: Optional[str],
        user_id: str,
        tenant_id: str,
    ) -> bool:
        """Attach bounded, redacted feedback to an owned assistant turn."""
        if rating not in {"positive", "negative"}:
            raise ValueError("feedback rating must be positive or negative")
        manager = self.runtime._session_manager
        if manager is None:
            raise RuntimeError("conversation storage is unavailable")

        safe_reason = self.runtime._redact_for_persistence(
            str(reason or "")
        ).strip()
        feedback = {
            "rating": str(rating),
            "reason": safe_reason[:1000] or None,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": 1,
        }
        saver = getattr(manager, "save_conversation_feedback", None)
        if not callable(saver):
            raise RuntimeError("conversation feedback storage is unavailable")
        return bool(saver(
            str(session_id),
            str(turn_id),
            user_id=str(user_id),
            tenant_id=str(tenant_id),
            feedback=feedback,
        ))

    def get_conversation_feedback_trend(
        self, *, days: int, user_id: str, tenant_id: str,
    ) -> dict[str, Any]:
        """Expose only scoped aggregates, never transcript content or reasons."""
        if int(days) not in {7, 30, 90}:
            raise ValueError("days must be one of 7, 30, or 90")
        manager = self.runtime._session_manager
        if manager is None:
            raise RuntimeError("conversation storage is unavailable")
        getter = getattr(manager, "get_conversation_feedback_trend", None)
        if not callable(getter):
            raise RuntimeError("conversation feedback analytics are unavailable")
        return getter(
            days=int(days),
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )

    def page_conversation_feedback_review_queue(self, filters: FeedbackReviewQuery) -> dict[str, Any]:
        manager = self.runtime._session_manager
        getter = getattr(manager, 'page_conversation_feedback_review_queue', None)
        if not callable(getter):
            raise RuntimeError('conversation feedback review is unavailable')
        return self.runtime._redact_for_persistence(getter(filters))

    def list_conversation_feedback_review_queue(
        self, *, tenant_id: str, status: str, limit: int,
    ) -> list[dict[str, Any]]:
        if status not in {"pending", "candidate", "dismissed"}:
            raise ValueError("unsupported feedback review status")
        manager = self.runtime._session_manager
        if manager is None:
            raise RuntimeError("conversation storage is unavailable")
        getter = getattr(manager, "list_conversation_feedback_review_queue", None)
        if not callable(getter):
            raise RuntimeError("conversation feedback review is unavailable")
        return getter(
            tenant_id=str(tenant_id),
            status=status,
            limit=max(1, min(int(limit), 100)),
        )

    def review_conversation_feedback(
        self,
        *,
        feedback_id: str,
        tenant_id: str,
        reviewer_id: str,
        review_status: str,
        expected_behavior: str,
        assertions: dict[str, Any] | None = None,
    ) -> bool:
        if review_status not in {"candidate", "dismissed"}:
            raise ValueError("review status must be candidate or dismissed")
        safe_expected = self.runtime._redact_for_persistence(
            str(expected_behavior or "")
        ).strip()
        if review_status == "candidate" and not safe_expected:
            raise ValueError("expected behavior is required for a regression candidate")
        if len(safe_expected) > 2000:
            raise ValueError("expected behavior exceeds 2000 characters")
        manager = self.runtime._session_manager
        if manager is None:
            raise RuntimeError("conversation storage is unavailable")
        reviewer = getattr(manager, "review_conversation_feedback", None)
        if not callable(reviewer):
            raise RuntimeError("conversation feedback review is unavailable")
        return bool(reviewer(
            str(feedback_id),
            tenant_id=str(tenant_id),
            reviewer_id=str(reviewer_id),
            review_status=review_status,
            expected_behavior=safe_expected,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
            assertions=self.runtime._redact_for_persistence(assertions or {}),
        ))
