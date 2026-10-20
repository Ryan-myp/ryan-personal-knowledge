"""Persist feedback for authenticated conversation turns."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


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
