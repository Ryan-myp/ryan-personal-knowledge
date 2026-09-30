"""Generic MCP Tool Source and Executor contracts.

The Harness treats MCP as one possible Tool transport. Authentication,
tenant-scoped client construction, discovery policy and persistence remain
owned by the application or platform integration layer.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

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


def _execution_mode(ctx: Any) -> str:
    request = getattr(ctx, "request", None)
    value = getattr(request, "execution_mode", None)
    if isinstance(request, Mapping):
        value = value or request.get("execution_mode")
    metadata = getattr(ctx, "metadata", None)
    if not value and isinstance(metadata, Mapping):
        value = metadata.get("execution_mode")
    request_context = getattr(request, "context", None)
    if not value and isinstance(request_context, Mapping):
        value = request_context.get("execution_mode")
    return str(value or "dry_run").strip().lower()


def _tool_names(values: Iterable[str], *, field_name: str) -> frozenset[str]:
    if isinstance(values, str):
        raise TypeError(f"{field_name} must be a collection of Tool names")
    names = frozenset(str(item).strip() for item in (values or ()) if str(item).strip())
    if any(len(name) > 128 for name in names):
        raise ValueError(f"{field_name} contains an invalid Tool name")
    return names


class MCPToolExecutor:
    """Turn one remote MCP call into a normal Harness Tool executor."""

    def __init__(
        self,
        client: Any,
        remote_name: str,
        *,
        tenant_id: str = "default",
        write_effect: bool = True,
        live_write_allowed: bool = False,
        idempotency_key_field: str | None = None,
        max_output_chars: int = 32_000,
    ) -> None:
        self.client = client
        self.remote_name = str(remote_name)
        self.tenant_id = str(tenant_id or "default")
        self.write_effect = bool(write_effect)
        self.live_write_allowed = bool(live_write_allowed)
        self.idempotency_key_field = (
            str(idempotency_key_field or "").strip() or None
        )
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self.max_output_chars = int(max_output_chars)

    def execute(self, ctx: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        if _tenant_from_context(ctx) != self.tenant_id:
            return {
                "success": False,
                "error": "MCP Tool is outside the current tenant scope",
            }
        if self.write_effect:
            mode = _execution_mode(ctx)
            if mode == "dry_run":
                return {
                    "success": True,
                    "executed": False,
                    "execution_status": "dry_run_only",
                    "effect_state": "not_started",
                    "mcp_tool": self.remote_name,
                }
            if mode != "live" or not self.live_write_allowed:
                return {
                    "success": False,
                    "executed": False,
                    "execution_status": "blocked_untrusted_write",
                    "effect_state": "not_started",
                    "mcp_tool": self.remote_name,
                    "error": "MCP live write is not trusted by the host",
                }
            if (
                not self.idempotency_key_field
                or input_data.get(self.idempotency_key_field) in (None, "")
            ):
                return {
                    "success": False,
                    "executed": False,
                    "execution_status": "blocked_missing_idempotency_key",
                    "effect_state": "not_started",
                    "mcp_tool": self.remote_name,
                    "error": "MCP live write requires its declared idempotency key",
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
        trusted_read_tools: Iterable[str] = (),
        live_write_tools: Iterable[str] = (),
        idempotency_key_fields: Mapping[str, str] | None = None,
    ) -> None:
        value = str(source_id or "").strip()
        if not value:
            raise ValueError("MCP Tool Source requires source_id")
        self._source_id = value
        self.client = client
        self.tenant_id = str(tenant_id or "default")
        self.trusted_read_tools = _tool_names(
            trusted_read_tools,
            field_name="trusted_read_tools",
        )
        self.live_write_tools = _tool_names(
            live_write_tools,
            field_name="live_write_tools",
        )
        if idempotency_key_fields is not None and not isinstance(
            idempotency_key_fields, Mapping,
        ):
            raise TypeError("idempotency_key_fields must be a Tool-to-field mapping")
        self.idempotency_key_fields = {
            str(name).strip(): str(field).strip()
            for name, field in (idempotency_key_fields or {}).items()
        }
        if any(
            not name or len(name) > 128 or not field or len(field) > 128
            for name, field in self.idempotency_key_fields.items()
        ):
            raise ValueError("idempotency_key_fields contains an invalid Tool or field")
        if set(self.idempotency_key_fields) != set(self.live_write_tools):
            raise ValueError(
                "every live-write MCP Tool must have exactly one host-declared "
                "idempotency field"
            )
        overlap = self.trusted_read_tools & self.live_write_tools
        if overlap:
            raise ValueError(
                "MCP Tool cannot be both trusted read-only and live-write-enabled"
            )

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
            read_only = name in self.trusted_read_tools
            live_write_allowed = name in self.live_write_tools
            schema = dict(
                raw.get("inputSchema") or raw.get("input_schema") or {}
            )
            idempotency_key_field = self.idempotency_key_fields.get(name)
            if live_write_allowed:
                properties = schema.get("properties")
                required = schema.get("required")
                if (
                    not isinstance(properties, Mapping)
                    or idempotency_key_field not in properties
                    or not isinstance(required, list)
                    or idempotency_key_field not in required
                    or not isinstance(properties[idempotency_key_field], Mapping)
                    or properties[idempotency_key_field].get("type") != "string"
                ):
                    raise ValueError(
                        f"live-write MCP Tool '{name}' must require its "
                        "host-declared string idempotency field in inputSchema"
                    )
            definition = {
                "name": name,
                "description": str(raw.get("description") or name)[:4000],
                "input_schema": schema,
                "effect_class": "read" if read_only else "external_write",
                "replay_policy": "safe" if read_only else "unsafe",
                "risk_level": "low" if read_only else "high",
                "required_permissions": [
                    "mcp.read" if read_only else "mcp.write"
                ],
                "live_support": read_only or live_write_allowed,
                "idempotency_key_field": idempotency_key_field,
                "traits": ["external", "mcp"],
            }
            bindings.append(ToolBinding(
                definition,
                MCPToolExecutor(
                    self.client,
                    name,
                    tenant_id=self.tenant_id,
                    write_effect=not read_only,
                    live_write_allowed=live_write_allowed,
                    idempotency_key_field=idempotency_key_field,
                ),
            ))
        configured_names = (
            self.trusted_read_tools
            | self.live_write_tools
            | set(self.idempotency_key_fields)
        )
        unknown_names = sorted(configured_names - names)
        if unknown_names:
            raise ValueError(
                "MCP trust policy references undiscovered Tools: "
                + ", ".join(unknown_names)
            )
        return bindings


__all__ = ["MCPClient", "MCPToolExecutor", "MCPToolSource"]
