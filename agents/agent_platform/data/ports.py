"""Vendor-neutral data-layer ports."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


class KnowledgeStore(Protocol):
    """Published knowledge and raw-source boundary."""

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
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
        limit: int = 8,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def save(
        self,
        record: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
    ) -> Any:
        ...


class SessionStore(Protocol):
    """Conversation and session state boundary."""

    def get(self, session_id: str) -> Mapping[str, Any] | None:
        ...

    def save(self, session_id: str, value: Mapping[str, Any]) -> Any:
        ...


__all__ = ["KnowledgeStore", "MemoryStore", "SessionStore"]
