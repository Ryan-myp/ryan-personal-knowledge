"""Vendor-neutral data contracts used by every platform application.

The data layer is intentionally scoped. A store that cannot express tenant,
user and session ownership is not safe to inject into a multi-tenant Agent
Runtime, even when the current deployment happens to use SQLite.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from agents.agent_harness import RunStore


class KnowledgeStore(Protocol):
    """Published knowledge and raw-source boundary."""

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str | None = None,
        limit: int = 8,
    ) -> Sequence[Mapping[str, Any]]:
        ...


class MemoryStore(Protocol):
    """Long-term memory boundary, isolated from permissions and Tools."""

    def recall(
        self,
        query: str,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str | None = None,
        limit: int = 8,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def save(
        self,
        record: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
        session_id: str | None = None,
    ) -> Any:
        ...


class SessionStore(Protocol):
    """Durable session state boundary with explicit ownership scope."""

    def get(
        self,
        session_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> Mapping[str, Any] | None:
        ...

    def save(
        self,
        session_id: str,
        value: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
    ) -> Any:
        ...

    def delete(
        self,
        session_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> Any:
        ...


class TaskStore(Protocol):
    """Durable background task boundary."""

    def submit(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
        idempotency_key: str | None = None,
    ) -> Any:
        ...

    def cancel(
        self,
        task_id: str,
        *,
        tenant_id: str,
        user_id: str,
    ) -> Any:
        ...


__all__ = [
    "KnowledgeStore",
    "MemoryStore",
    "RunStore",
    "SessionStore",
    "TaskStore",
]
