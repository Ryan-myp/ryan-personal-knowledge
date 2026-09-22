"""Adapters from the advertising persistence backend to generic Harness ports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence

from agents.agent_harness import AgentMessage

from .models import ConversationMessageRecord


class PersistenceIdempotencyStore:
    """Expose the backend's SQL reservation table through the generic port."""

    def __init__(self, backend: Any) -> None:
        self.backend = backend

    def reserve(
        self, key: str, *, request_hash: str, ttl_seconds: float,
    ) -> bool:
        reserve = getattr(self.backend, "reserve_write", None)
        if not callable(reserve):
            raise TypeError("persistence backend lacks SQL write reservations")
        return bool(reserve(
            str(key),
            ttl_seconds=max(1, int(ttl_seconds)),
            request_hash=str(request_hash),
        ))

    def mark_executed(self, key: str, *, request_hash: str) -> None:
        mark = getattr(self.backend, "mark_write_executed", None)
        if not callable(mark):
            raise TypeError("persistence backend lacks SQL write reservations")
        mark(str(key), request_hash=str(request_hash))

    def release(self, key: str, *, request_hash: str) -> None:
        release = getattr(self.backend, "release_write", None)
        if not callable(release):
            raise TypeError("persistence backend lacks SQL write reservations")
        release(str(key), request_hash=str(request_hash))


class PersistenceTranscriptStore:
    """Persist Harness messages through the existing session-scoped SQL table."""

    def __init__(self, backend: Any) -> None:
        self.backend = backend

    def _assert_scope(self, session_id: str, tenant_id: str, user_id: str) -> None:
        get_session = getattr(self.backend, "get_session", None)
        if not callable(get_session):
            raise TypeError("persistence backend lacks session lookup")
        session = get_session(
            str(session_id), user_id=str(user_id), tenant_id=str(tenant_id),
        )
        if session is None:
            raise PermissionError("transcript session is outside the requested scope")

    def load(
        self,
        session_id: str,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 200,
    ) -> list[AgentMessage]:
        self._assert_scope(session_id, tenant_id, user_id)
        records = self.backend.list_conversation_messages(
            str(session_id), limit=max(1, int(limit)),
        )
        result: list[AgentMessage] = []
        for record in records:
            metadata = getattr(record, "metadata", {}) or {}
            content = record.content
            if isinstance(content, str):
                try:
                    legacy = json.loads(content)
                except (TypeError, ValueError):
                    legacy = None
                if isinstance(legacy, dict) and "content" in legacy:
                    content = legacy.get("content", "")
                    metadata = legacy.get("metadata") or metadata
            result.append(AgentMessage(
                role=str(record.role),
                content=content,
                message_id=str(record.message_id),
                run_id=str(getattr(record, "run_id", "") or ""),
                turn_id=str(record.turn_id),
                tool_call_id=getattr(record, "tool_call_id", None),
                name=getattr(record, "name", None),
                metadata=metadata if isinstance(metadata, dict) else {},
                timestamp=float(getattr(record, "timestamp", 0.0) or 0.0)
                or datetime.now(timezone.utc).timestamp(),
            ))
        return result

    def append(
        self,
        session_id: str,
        messages: Sequence[AgentMessage],
        *,
        tenant_id: str,
        user_id: str,
    ) -> None:
        self._assert_scope(session_id, tenant_id, user_id)
        for message in messages:
            payload = message.to_dict()
            self.backend.record_conversation_message(ConversationMessageRecord(
                message_id=str(payload["message_id"]),
                session_id=str(session_id),
                turn_id=str(payload.get("turn_id") or ""),
                role=str(payload["role"]),
                content=(
                    payload.get("content", "")
                    if isinstance(payload.get("content", ""), str)
                    else json.dumps(
                        payload.get("content", ""),
                        ensure_ascii=False,
                        default=str,
                    )
                ),
                created_at=datetime.fromtimestamp(
                    float(payload.get("timestamp") or 0),
                    tz=timezone.utc,
                ).isoformat(),
                tool_call_id=payload.get("tool_call_id"),
                name=payload.get("name"),
                metadata=payload.get("metadata") or {},
            ))


__all__ = ["PersistenceIdempotencyStore", "PersistenceTranscriptStore"]
