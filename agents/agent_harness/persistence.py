"""Durable ports used by the application-neutral Agent Harness."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from .messages import AgentMessage


class IdempotencyStore(Protocol):
    """Cross-process reservation store for externally effectful Tool calls."""

    def reserve(
        self, key: str, *, request_hash: str, ttl_seconds: float,
    ) -> bool: ...

    def mark_executed(self, key: str, *, request_hash: str) -> None: ...

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


__all__ = ["IdempotencyStore", "TranscriptStore"]
