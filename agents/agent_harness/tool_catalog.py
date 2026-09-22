"""Application-neutral executable Tool catalog."""

from __future__ import annotations

import threading
from typing import Any, Protocol, Sequence

from .tool_sources import ToolBinding, ToolSource


class ToolCatalog(Protocol):
    """Read-only view used by the Agent loop."""

    def list_tools(self) -> list[Any]:
        ...

    def get_binding(self, name: str) -> ToolBinding:
        ...

    def source_snapshot(self) -> dict[str, list[str]]:
        ...

    def healthcheck(self) -> dict[str, Any]:
        ...


def _tool_name(definition: Any) -> str:
    if isinstance(definition, dict):
        return str(definition.get("name") or "").strip()
    return str(getattr(definition, "name", "") or "").strip()


class InMemoryToolCatalog:
    """Small thread-safe catalog for local Tools, SDK adapters and MCP Tools."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bindings: dict[str, ToolBinding] = {}
        self._sources: dict[str, list[str]] = {}

    def register_source(self, source: ToolSource) -> list[str]:
        source_id = str(getattr(source, "source_id", "") or "").strip()
        list_bindings = getattr(source, "list_bindings", None)
        if not source_id or not callable(list_bindings):
            raise TypeError("Tool source must expose source_id and list_bindings()")
        bindings = list(list_bindings())
        names: list[str] = []
        with self._lock:
            if source_id in self._sources:
                raise ValueError(f"Tool source '{source_id}' already registered")
            try:
                for binding in bindings:
                    if not isinstance(binding, ToolBinding):
                        raise TypeError("Tool source must return ToolBinding values")
                    name = _tool_name(binding.definition)
                    if not name:
                        raise ValueError("Tool definition requires a non-empty name")
                    if name in self._bindings:
                        raise ValueError(f"Tool '{name}' already registered")
                    self._bindings[name] = binding
                    names.append(name)
                self._sources[source_id] = list(names)
            except Exception:
                for name in names:
                    self._bindings.pop(name, None)
                raise
        return names

    def unregister_source(self, source_id: str) -> list[str]:
        with self._lock:
            names = list(self._sources.pop(str(source_id), []))
            for name in names:
                self._bindings.pop(name, None)
            return names

    def get_binding(self, name: str) -> ToolBinding:
        with self._lock:
            try:
                return self._bindings[str(name)]
            except KeyError as exc:
                raise KeyError(f"Tool '{name}' not found") from exc

    def list_tools(self) -> list[Any]:
        with self._lock:
            return [binding.definition for binding in self._bindings.values()]

    def list_all(self) -> list[Any]:
        return self.list_tools()

    def source_snapshot(self) -> dict[str, list[str]]:
        """Return source ownership without exposing executor internals."""
        with self._lock:
            return {
                source_id: list(names)
                for source_id, names in sorted(self._sources.items())
            }

    def healthcheck(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": "ok",
                "tools": len(self._bindings),
                "sources": len(self._sources),
                "source_snapshot": self.source_snapshot(),
            }


__all__ = ["InMemoryToolCatalog", "ToolCatalog"]
