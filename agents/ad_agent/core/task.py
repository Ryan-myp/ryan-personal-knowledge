"""Business-neutral durable task submission value."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class TaskSubmission:
    """Minimal durable task record accepted by a persistence adapter."""

    task_id: str
    tenant_id: str
    user_id: str
    kind: str
    status: str
    payload: dict[str, Any]
    idempotency_key: Optional[str] = None
    workflow_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["TaskSubmission"]
