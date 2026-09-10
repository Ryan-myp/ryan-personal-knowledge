"""FastMCP adapter for the already registered Runtime capabilities.

This is an integration adapter, not a second Agent or channel router.  Tool
metadata and handlers always come from the Runtime Registry.  The optional
HTTP surface is disabled by default and, when enabled, is protected by the
same service authentication used by the FastAPI control plane.
"""

from __future__ import annotations

import contextvars
import logging
import os
import re
import threading
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from fastmcp import FastMCP
from fastmcp.tools.function_tool import FunctionTool
from starlette.requests import Request
from starlette.responses import JSONResponse

from .core.interfaces import ToolContext, ToolResult
from .core.tool_registry import validate_tool_input
from .persistence.models import ToolCallRecord


logger = logging.getLogger(__name__)
_current_principal: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "ad_agent_runtime_mcp_principal", default=None
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_metadata(definition: Any) -> dict[str, Any]:
    schema = definition.input_schema.to_dict() if definition.input_schema else {
        "type": "object", "properties": {}, "required": [],
    }
    return {
        "name": str(definition.name),
        "namespace": str(definition.namespace),
        "skill": str(definition.skill),
        "description": str(definition.description),
        "action": str(definition.action),
        "resource_type": str(definition.resource_type),
        "intent_types": list(getattr(definition, "intent_types", []) or []),
        "intent_aliases": list(getattr(definition, "intent_aliases", []) or []),
        "skill_refs": list(getattr(definition, "skill_refs", []) or []),
        "resource_id_field": getattr(definition, "resource_id_field", None),
        "readback_tool": getattr(definition, "readback_tool", None),
        "idempotency_key_field": getattr(definition, "idempotency_key_field", None),
        "risk_level": definition.risk_level.value,
        "effect_class": definition.effect_class.value,
        "replay_policy": definition.replay_policy.value,
        "live_support": bool(definition.live_support),
        "required_permissions": list(definition.required_permissions),
        "input_schema": schema,
    }


def _execution_mode_for_principal(runtime: Any, principal: Any = None) -> str:
    """Resolve the same tenant/user mode used by the HTTP chat path."""
    getter = getattr(runtime, "get_execution_mode", None)
    if callable(getter) and principal is not None:
        return str(getter(principal.tenant_id, principal.user_id))
    return str(getattr(runtime, "execution_mode", "dry_run"))


class RuntimeMCPServers:
    """Publish Registry capabilities as one independently addressable MCP Server per namespace."""

    def __init__(self, runtime_provider: Callable[[], Any], authorize: Callable[..., Any]):
        self._runtime_provider = runtime_provider
        self._authorize = authorize
        self._mcps: dict[str, FastMCP] = {}
        self._mcp_apps: dict[str, Any] = {}
        self._lock = threading.RLock()

    @property
    def enabled(self) -> bool:
        return os.environ.get("AD_AGENT_MCP_CHANNELS_ENABLED", "0") == "1"

    def refresh(self, runtime: Any) -> int:
        """Synchronize one FastMCP server per Runtime namespace."""
        with self._lock:
            definitions_by_server: dict[str, list[Any]] = {}
            for definition in runtime.registry.list_all():
                definitions_by_server.setdefault(self._server_key(definition.namespace), []).append(definition)
            self._mcps.clear()
            self._mcp_apps.clear()
            for server_key, definitions in sorted(definitions_by_server.items()):
                mcp = FastMCP(
                    f"ad-agent-{server_key}-tools",
                    instructions=(
                        f"Tools published by the {self._display_name(server_key)} Runtime namespace. "
                        "Writes remain dry-run unless the host Runtime explicitly enables its existing live gates."
                    ),
                    version="1.0.0", strict_input_validation=True,
                )
                names: set[str] = set()
                for definition in definitions:
                    mcp.add_tool(self._build_function_tool(runtime, definition))
                    names.add(str(definition.name))
                self._mcps[server_key] = mcp
                self._mcp_apps[server_key] = mcp.http_app(
                    transport="streamable-http", stateless_http=True,
                )
            return sum(len(items) for items in definitions_by_server.values())

    def _build_function_tool(self, runtime: Any, definition: Any) -> FunctionTool:
        tool_name = str(definition.name)

        def invoke(**kwargs: Any) -> dict[str, Any]:
            return self.invoke_for_principal(
                runtime, _current_principal.get(), tool_name, kwargs,
                source="runtime_mcp_server",
            )

        return FunctionTool(
            name=tool_name,
            title=tool_name,
            description=str(definition.description),
            parameters=definition.input_schema.to_dict() if definition.input_schema else {
                "type": "object", "properties": {}, "required": [],
            },
            annotations={
                "readOnlyHint": bool(definition.is_read_tool),
                "destructiveHint": bool(definition.is_write_tool),
                "idempotentHint": False if definition.is_write_tool else True,
                "openWorldHint": True,
            },
            timeout=float(definition.timeout_seconds),
            fn=invoke,
            run_in_thread=True,
        )

    def list_tools(self, runtime: Any) -> list[dict[str, Any]]:
        return [_tool_metadata(item) for item in runtime.registry.list_all()]

    @staticmethod
    def _server_key(namespace: Any) -> str:
        value = re.sub(r"[^a-z0-9]+", "_", str(namespace or "channel").strip().lower()).strip("_")
        return value or "channel"

    @staticmethod
    def _display_name(server_key: str) -> str:
        labels = {
            "google_ads": "Google Ads",
            "meta": "Meta",
            "tiktok": "TikTok",
            "dv360": "DV360",
        }
        return labels.get(server_key, server_key.replace("_", " ").title())

    def list_servers(self, runtime: Any, principal: Any = None) -> list[dict[str, Any]]:
        """Return channel MCP servers using the same shape as managed servers."""
        execution_mode = _execution_mode_for_principal(runtime, principal)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self.list_tools(runtime):
            grouped.setdefault(self._server_key(item["namespace"]), []).append(item)
        return [{
            "server_id": f"channel-{server_key}",
            "name": f"{self._display_name(server_key)} MCP",
            "description": f"{self._display_name(server_key)} 渠道能力，由当前 Runtime Registry 提供。",
            "endpoint": f"/mcp/channels/{server_key}/mcp",
            "transport": "streamable_http",
            "auth_type": "service",
            # Registry-backed servers are always available to this Agent
            # process.  HTTP exposure is a separate deployment concern.
            "status": "active",
            "enabled": True,
            "http_enabled": self.enabled,
            "source": "runtime_registry",
            "managed": True,
            "execution_mode": execution_mode,
            "tools": [self._public_channel_tool(item) for item in items],
        } for server_key, items in sorted(grouped.items())]

    def get_server(self, server_id: str, runtime: Any, principal: Any = None) -> Optional[dict[str, Any]]:
        return next(
            (server for server in self.list_servers(runtime, principal)
             if str(server["server_id"]) == str(server_id)),
            None,
        )

    def test_tool(
        self, server_id: str, tool_id: str, runtime: Any, principal: Any,
        input_data: Mapping[str, Any], *, account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run a Registry tool through the same safe management-console path."""
        server = self.get_server(server_id, runtime, principal)
        if not server:
            raise KeyError(server_id)
        tool = next(
            (item for item in server.get("tools", [])
             if str(item.get("tool_id")) == str(tool_id)),
            None,
        )
        if not tool:
            raise KeyError(tool_id)
        return self.invoke_for_principal(
            runtime, principal, str(tool["remote_name"]), input_data,
            source="ui_test", account_id=account_id,
        )

    @staticmethod
    def _public_channel_tool(item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "tool_id": item["name"],
            "remote_name": item["name"],
            "title": item["name"],
            "description": item["description"],
            "input_schema": item["input_schema"],
            "intent_types": item.get("intent_types", []),
            "intent_aliases": item.get("intent_aliases", []),
            "skill_refs": item.get("skill_refs", []),
            "action": item.get("action", "invoke"),
            "resource_type": item.get("resource_type", "mcp_invocation"),
            "annotations": {
                "readOnlyHint": item["effect_class"] == "read",
                "destructiveHint": item["effect_class"] != "read",
            },
            "enabled": True,
            "validation_status": "passed",
        }

    def invoke_for_principal(
        self, runtime: Any, principal: Any, tool_name: str,
        input_data: Mapping[str, Any], *, source: str,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if principal is None:
            raise PermissionError("MCP caller 未通过服务身份认证")
        definition, _handler = runtime._get_registered_tool(str(tool_name))
        missing = sorted(
            set(definition.required_permissions or ()) - set(principal.permissions or ())
        )
        if missing and "admin" not in set(principal.permissions or ()):
            raise PermissionError("Tool 所需权限未授予：" + ", ".join(missing))
        execution_mode = _execution_mode_for_principal(runtime, principal)
        if definition.is_write_tool and execution_mode != "dry_run":
            raise PermissionError(
                "当前为 live 模式；渠道写 Tool 不能在 MCP 管理台直接测试，"
                "请通过 Agent 的确认、幂等和 live 执行链路调用"
            )
        if account_id:
            validator = getattr(runtime, "_validate_account_with_principal", None)
            if callable(validator):
                valid, reason = validator(
                    str(definition.namespace), str(account_id),
                    bool(definition.is_write_tool), principal.account_scope,
                )
                if not valid:
                    raise PermissionError(reason)
        data = dict(input_data or {})
        schema_errors = validate_tool_input(definition.input_schema, data)
        if schema_errors:
            raise ValueError("Input validation failed: " + "; ".join(schema_errors))
        session_id = f"mcp-test-{uuid.uuid4().hex}"
        turn_id = f"mcp-test-turn-{uuid.uuid4().hex}"
        ctx = ToolContext(
            session_id=session_id,
            user_id=str(principal.user_id),
            scope={"account_id": account_id or ""},
            metadata={
                "tenant_id": str(principal.tenant_id),
                "mcp_source": source,
                "mcp_tool_test": True,
                "execution_mode": execution_mode,
            },
        )
        started_at = _now()
        if definition.is_write_tool:
            result = runtime._simulate_write(
                definition, data, str(definition.namespace),
            )
        else:
            result = runtime.tool_executor.execute(ctx, str(tool_name), data)
        ended_at = _now()
        self._persist_audit(
            runtime, ctx, turn_id, definition, data, result,
            started_at, ended_at,
        )
        return {
            "success": bool(result.success),
            "tool": str(tool_name),
            "mode": execution_mode,
            "data": result.data,
            "error": result.error,
        }

    @staticmethod
    def _persist_audit(
        runtime: Any, ctx: ToolContext, turn_id: str, definition: Any,
        input_data: dict[str, Any], result: ToolResult,
        started_at: str, ended_at: str,
    ) -> None:
        persistence = getattr(runtime, "persistence_services", None)
        ensure_session = getattr(runtime, "_ensure_session", None)
        if not callable(persistence) or not callable(ensure_session):
            return
        try:
            session = ensure_session(
                ctx.session_id, ctx.user_id, ctx.scope.get("account_id"), {},
                tenant_id=ctx.metadata.get("tenant_id", "default"),
            )
            persistence.persist_tool_result(
                session, turn_id, definition, str(definition.namespace),
                input_data, result, started_at=started_at, ended_at=ended_at,
            )
        except Exception:
            logger.warning("MCP Tool test audit persistence failed", exc_info=True)

    def asgi_app(self) -> Any:
        gateway = self

        @asynccontextmanager
        async def mcp_lifespan(app: Any):
            async with AsyncExitStack() as stack:
                for child in list(gateway._mcp_apps.values()):
                    await stack.enter_async_context(child.lifespan(app))
                yield

        self._mcp_lifespan = mcp_lifespan

        class AuthenticatedApp:
            # Starlette Mount does not automatically run a mounted app's
            # lifespan.  api_server.lifespan composes this context explicitly,
            # so keep the FastMCP lifecycle visible through the auth wrapper.
            # Without this, FastMCPStreamableHTTPSessionManager is never
            # started and every MCP request fails with an uninitialized task
            # group error.
            @property
            def lifespan(self) -> Any:
                # A property is intentional: assigning the function directly
                # on this class would make Python bind it as a method and add
                # an unexpected ``self`` argument.
                return gateway._mcp_lifespan

            async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
                if scope.get("type") != "http":
                    await JSONResponse({"detail": "MCP 仅支持 HTTP transport"}, status_code=404)(scope, receive, send)
                    return
                if not gateway.enabled:
                    await JSONResponse({"detail": "Runtime MCP Server HTTP 暴露未启用"}, status_code=404)(scope, receive, send)
                    return
                path_parts = [part for part in str(scope.get("path") or "").split("/") if part]
                # Depending on whether the adapter is mounted at the app
                # root or at /mcp/channels, Starlette may preserve the mount
                # prefix in scope["path"].  The endpoint contract is always
                # /{server_key}/mcp, so resolve the final two segments.
                if len(path_parts) < 2 or path_parts[-1] != "mcp":
                    await JSONResponse({"detail": "MCP Server endpoint 不存在"}, status_code=404)(scope, receive, send)
                    return
                child = gateway._mcp_apps.get(path_parts[-2])
                if child is None:
                    await JSONResponse({"detail": "MCP Server endpoint 不存在"}, status_code=404)(scope, receive, send)
                    return
                request = Request(scope, receive)
                key = request.headers.get("x-api-key")
                try:
                    principal = gateway._authorize(key, request)
                except Exception as exc:
                    status = int(getattr(exc, "status_code", 401))
                    detail = str(getattr(exc, "detail", "MCP caller 未通过认证"))
                    await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
                    return
                token = _current_principal.set(principal)
                try:
                    child_scope = dict(scope)
                    child_scope["path"] = "/mcp"
                    child_scope["raw_path"] = b"/mcp"
                    await child(child_scope, receive, send)
                finally:
                    _current_principal.reset(token)

        return AuthenticatedApp()


__all__ = ["RuntimeMCPServers"]
