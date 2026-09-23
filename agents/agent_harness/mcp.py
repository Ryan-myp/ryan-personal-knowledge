"""Generic MCP Tool Source and Executor contracts.

The Harness treats MCP as one possible Tool transport. Authentication,
tenant-scoped client construction, discovery policy and persistence remain
owned by the application or platform integration layer.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .tool_sources import ToolBinding, ToolSource


class MCPClient:
    """Minimal client contract required by the generic MCP adapter."""

    def list_tools(self) -> Sequence[Mapping[str, Any]]:
        raise NotImplementedError

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError


def _tenant_from_context(ctx: Any) -> str:
    request = getattr(ctx, "request", None)
    if request is not None:
        return str(getattr(request, "tenant_id", None) or "default")
    metadata = getattr(ctx, "metadata", None)
    if isinstance(metadata, Mapping):
        return str(metadata.get("tenant_id") or "default")
    return "default"


class MCPToolExecutor:
    """Turn one remote MCP call into a normal Harness Tool executor."""

    def __init__(
        self,
        client: Any,
        remote_name: str,
        *,
        tenant_id: str = "default",
        write_effect: bool = False,
        max_output_chars: int = 32_000,
    ) -> None:
        self.client = client
        self.remote_name = str(remote_name)
        self.tenant_id = str(tenant_id or "default")
        self.write_effect = bool(write_effect)
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self.max_output_chars = int(max_output_chars)

    def execute(self, ctx: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        if _tenant_from_context(ctx) != self.tenant_id:
            return {
                "success": False,
                "error": "MCP Tool is outside the current tenant scope",
            }
        try:
            value = self.client.call_tool(self.remote_name, dict(input_data or {}))
        except Exception:
            if self.write_effect:
                return {
                    "success": False,
                    "error": "remote write result is unknown and requires reconciliation",
                    "execution_status": "unknown",
                    "effect_state": "unknown",
                    "recovery_required": True,
                }
            return {"success": False, "error": "MCP Tool call failed"}
        if not isinstance(value, Mapping):
            return {"success": False, "error": "MCP Tool returned an invalid response"}
        if value.get("isError"):
            if self.write_effect:
                return {
                    "success": False,
                    "error": "remote write result requires reconciliation",
                    "execution_status": "unknown",
                    "effect_state": "unknown",
                    "recovery_required": True,
                }
            return {"success": False, "error": "MCP Server reported Tool failure"}
        result = {
            "success": True,
            "content": value.get("content", []),
            "structured_content": value.get("structuredContent"),
        }
        try:
            encoded = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            encoded = str(result)
        if len(encoded) > self.max_output_chars:
            return {
                "success": False,
                "error": "MCP Tool output exceeded the configured limit",
                "output_truncated": True,
            }
        return result


class MCPToolSource(ToolSource):
    """Expose a discovered MCP snapshot as ordinary Harness Tool bindings."""

    def __init__(
        self,
        source_id: str,
        client: Any,
        *,
        tenant_id: str = "default",
    ) -> None:
        value = str(source_id or "").strip()
        if not value:
            raise ValueError("MCP Tool Source requires source_id")
        self._source_id = value
        self.client = client
        self.tenant_id = str(tenant_id or "default")

    @property
    def source_id(self) -> str:
        return self._source_id

    def list_bindings(self) -> Sequence[ToolBinding]:
        list_tools = getattr(self.client, "list_tools", None)
        if not callable(list_tools):
            raise TypeError("MCP client must expose list_tools()")
        bindings: list[ToolBinding] = []
        names: set[str] = set()
        for raw in list_tools() or ():
            if not isinstance(raw, Mapping):
                raise TypeError("MCP list_tools() must return mappings")
            name = str(raw.get("name") or "").strip()
            if not name:
                raise ValueError("MCP Tool requires a name")
            if name in names:
                raise ValueError(f"duplicate MCP Tool name: {name}")
            names.add(name)
            annotations = raw.get("annotations") or {}
            read_only = (
                isinstance(annotations, Mapping)
                and annotations.get("readOnlyHint") is True
                and annotations.get("destructiveHint") is not True
            )
            definition = {
                "name": name,
                "description": str(raw.get("description") or name)[:4000],
                "input_schema": dict(
                    raw.get("inputSchema") or raw.get("input_schema") or {}
                ),
                "effect_class": "read" if read_only else "external_write",
                "replay_policy": "safe" if read_only else "unsafe",
                "traits": ["external", "mcp"],
            }
            bindings.append(ToolBinding(
                definition,
                MCPToolExecutor(
                    self.client,
                    name,
                    tenant_id=self.tenant_id,
                    write_effect=not read_only,
                ),
            ))
        return bindings


__all__ = ["MCPClient", "MCPToolExecutor", "MCPToolSource"]
