"""Deployment and execution infrastructure ports."""

from __future__ import annotations

from typing import Any, Mapping, Protocol


class TaskDispatcher(Protocol):
    def submit(self, kind: str, payload: Mapping[str, Any]) -> str:
        ...

    def cancel(self, task_id: str) -> bool:
        ...


class ProtocolEndpoint(Protocol):
    """HTTP, WebSocket, gRPC or message-queue ingress/egress boundary."""

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...


class ResourceHealth(Protocol):
    def check(self) -> Mapping[str, Any]:
        ...


__all__ = ["ProtocolEndpoint", "ResourceHealth", "TaskDispatcher"]
