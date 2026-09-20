"""Application-neutral Tool sources for the Agent Harness.

A Tool source publishes executable bindings.  It does not get a shortcut
around the Runtime policy path: the binding is only catalogued here, while
application runtimes remain responsible for authorization and execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from .interfaces import ToolDefinition, ToolResult


class ToolExecutor(Protocol):
    """Small executor contract shared by local, SDK/HTTP and MCP adapters."""

    def execute(self, ctx: Any, input_data: dict[str, Any]) -> ToolResult:
        """Execute one already-validated Tool input."""
        ...


@dataclass(frozen=True)
class ToolBinding:
    """One Tool contract paired with its trusted execution adapter."""

    definition: ToolDefinition
    executor: ToolExecutor

    def __post_init__(self) -> None:
        if not isinstance(self.definition, ToolDefinition):
            raise TypeError("ToolBinding.definition must be a ToolDefinition")
        execute = getattr(self.executor, "execute", None)
        if not callable(execute) and not callable(self.executor):
            raise TypeError(
                f"Tool '{self.definition.name}' executor must be executable"
            )


class ToolSource(Protocol):
    """Source of Tools for a generic harness."""

    @property
    def source_id(self) -> str:
        """Stable owner ID used for lifecycle and audit bookkeeping."""
        ...

    def list_bindings(self) -> Sequence[ToolBinding]:
        """Return the complete source snapshot for one registration."""
        ...


class StaticToolSource:
    """Small adapter for application-owned local or remote Tool snapshots."""

    def __init__(self, source_id: str, bindings: Sequence[ToolBinding]):
        value = str(source_id or "").strip()
        if not value:
            raise ValueError("Tool source requires a non-empty source_id")
        self._source_id = value
        self._bindings = tuple(bindings)

    @property
    def source_id(self) -> str:
        return self._source_id

    def list_bindings(self) -> tuple[ToolBinding, ...]:
        return self._bindings


__all__ = ["ToolExecutor", "ToolBinding", "ToolSource", "StaticToolSource"]
