"""Application-neutral Tool Source and executor contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


class ToolExecutor(Protocol):
    """Executor shared by local, SDK/HTTP and MCP adapters."""

    def execute(self, ctx: Any, input_data: dict[str, Any]) -> Any:
        """Execute one already-validated Tool input."""
        ...


@dataclass(frozen=True)
class ToolBinding:
    """One opaque Tool contract paired with its trusted executor."""

    definition: Any
    executor: ToolExecutor

    def __post_init__(self) -> None:
        if self.definition is None:
            raise TypeError("ToolBinding.definition is required")
        execute = getattr(self.executor, "execute", None)
        if not callable(execute) and not callable(self.executor):
            raise TypeError("ToolBinding.executor must be executable")


class ToolSource(Protocol):
    """Source of a complete Tool snapshot for one lifecycle registration."""

    @property
    def source_id(self) -> str:
        ...

    def list_bindings(self) -> Sequence[ToolBinding]:
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
