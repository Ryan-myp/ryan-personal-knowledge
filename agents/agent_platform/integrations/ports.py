"""Integration-layer ports for Tool providers and external services."""

from __future__ import annotations

from typing import Mapping, Protocol

from agents.agent_harness import ToolExecutor, ToolSource


class ExternalIntegration(Protocol):
    """Lifecycle boundary for an SDK, HTTP or MCP-backed integration."""

    @property
    def integration_id(self) -> str:
        ...

    def healthcheck(self) -> Mapping[str, Any]:
        ...

    def close(self) -> None:
        ...


__all__ = ["ExternalIntegration", "ToolExecutor", "ToolSource"]
