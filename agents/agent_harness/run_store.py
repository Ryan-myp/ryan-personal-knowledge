"""Durable Run lifecycle ports for the generic Agent Harness."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol

from .runtime_kernel import TurnRequest


class RunStore(Protocol):
    """Minimal durable lifecycle port with no application models."""

    def start_run(self, **payload: Any) -> Any:
        ...

    def append_event(self, run_id: str, event: Mapping[str, Any]) -> Any:
        ...

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        ...


def run_start_payload(request: TurnRequest) -> dict[str, Any]:
    """Build a sanitized, application-neutral start payload."""
    return {
        "run_id": str(request.run_id or ""),
        "turn_id": str(request.turn_id or ""),
        "session_id": str(request.session_id or ""),
        "user_id": str(request.user_id or "anonymous"),
        "tenant_id": str(request.tenant_id or "default"),
        "task_id": str(request.task_id) if request.task_id else None,
        "execution_mode": request.execution_mode,
    }


__all__ = ["RunStore", "run_start_payload"]
