"""Durable ports used by the application-neutral Agent Harness."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from .messages import AgentMessage


class IdempotencyStore(Protocol):
    """Cross-process reservations; unresolved calls require reconciliation."""

    def reserve(
        self, key: str, *, request_hash: str, ttl_seconds: float,
    ) -> bool: ...

    def mark_executed(self, key: str, *, request_hash: str) -> None: ...

    def mark_uncertain(self, key: str, *, request_hash: str) -> None:
        """Quarantine an unknown effect; normal TTL and release cannot erase it."""
        ...

    def resolve_uncertain(
        self, key: str, *, request_hash: str, executed: bool,
    ) -> bool:
        """Trusted reconciliation only, after verifying the external outcome."""
        ...

    def release(self, key: str, *, request_hash: str) -> None: ...


class TranscriptStore(Protocol):
    """Durable, already-redacted session transcript port."""

    def load(
        self,
        session_id: str,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 200,
    ) -> Sequence[AgentMessage | dict[str, Any]]: ...

    def append(
        self,
        session_id: str,
        messages: Sequence[AgentMessage],
        *,
        tenant_id: str,
        user_id: str,
    ) -> None: ...

    def clear(
        self,
        session_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> None: ...


class UserHistoryStore(Protocol):
    """Optional, bounded user-only history lookup; never returns Tool results."""

    def load_user_history(
        self, session_id: str, *, tenant_id: str, user_id: str, limit: int,
    ) -> Sequence[AgentMessage]: ...


__all__ = ["IdempotencyStore", "TranscriptStore", "UserHistoryStore"]
