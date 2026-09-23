"""Core ports.

These protocols keep the middle platform independent from storage vendors,
provider SDKs and transport frameworks.  Implementations are injected by a
product or deployment assembly.
"""

from __future__ import annotations

from typing import Any, Protocol

from agents.agent_harness import (
    MetricsSink,
    ModelAdapter,
    RunStore,
    SkillSource,
    ToolSource,
    TurnPipeline,
)
from agents.agent_platform.data.ports import KnowledgeStore, MemoryStore


KnowledgePort = KnowledgeStore
MemoryPort = MemoryStore


class TaskPort(Protocol):
    def submit(self, kind: str, payload: Mapping[str, Any]) -> Any:
        ...

    def cancel(self, task_id: str) -> Any:
        ...


class SecurityPort(Protocol):
    def authorize(self, principal: Any, action: str, resource: Any = None) -> bool:
        ...


__all__ = [
    "KnowledgePort",
    "MemoryPort",
    "MetricsSink",
    "ModelAdapter",
    "RunStore",
    "SecurityPort",
    "SkillSource",
    "TaskPort",
    "ToolSource",
    "TurnPipeline",
]
