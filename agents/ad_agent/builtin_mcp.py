"""FastMCP adapter for the already registered channel Tools.

This is an integration adapter, not a second Agent or channel router.  Tool
metadata and handlers always come from the Runtime Registry.  The optional
HTTP surface is disabled by default and, when enabled, is protected by the
same service authentication used by the FastAPI control plane.
"""

from __future__ import annotations

import contextvars
import logging
import os
import threading
import uuid
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
    "ad_agent_builtin_mcp_principal", default=None
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
        "risk_level": definition.risk_level.value,
        "effect_class": definition.effect_class.value,
        "replay_policy": definition.replay_policy.value,
        "live_support": bool(definition.live_support),
        "required_permissions": list(definition.required_permissions),
        "input_schema": schema,
    }


class BuiltinChannelMCP:
    """Expose Registry tools through FastMCP and provide safe UI invocation."""

    def __init__(self, runtime_provider: Callable[[], Any], authorize: Callable[..., Any]):
        self._runtime_provider = runtime_provider
        self._authorize = authorize
        self._mcp = FastMCP(
            "ad-agent-channel-tools",
            instructions=(
                "Channel tools published by the ad-agent Runtime Registry. "
                "Writes remain dry-run unless the host Runtime explicitly "
                "enables its existing live safety gates."
            ),
            version="1.0.0",
            strict_input_validation=True,
        )
        self._registered_names: set[str] = set()
        self._lock = threading.RLock()

    @property
    def enabled(self) -> bool:
        return os.environ.get("AD_AGENT_MCP_CHANNELS_ENABLED", "0") == "1"

    def refresh(self, runtime: Any) -> int:
        """Synchronize FastMCP tools from the single Runtime Registry."""
        with self._lock:
            definitions = list(runtime.registry.list_all())
            for name in list(self._registered_names):
                self._mcp.remove_tool(name)
            self._registered_names.clear()
            for definition in definitions:
                self._mcp.add_tool(self._build_function_tool(runtime, definition))
                self._registered_names.add(str(definition.name))
            return len(definitions)

    def _build_function_tool(self, runtime: Any, definition: Any) -> FunctionTool:
        tool_name = str(definition.name)

        def invoke(**kwargs: Any) -> dict[str, Any]:
            return self.invoke_for_principal(
                runtime, _current_principal.get(), tool_name, kwargs,
                source="builtin_mcp",
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
        if definition.is_write_tool and not runtime.is_dry_run:
            raise PermissionError("渠道写 Tool 测试只允许在 dry-run 模式执行")
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
            "mode": "dry_run" if runtime.is_dry_run else "live",
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
        child = self._mcp.http_app(
            transport="streamable-http", stateless_http=True,
        )
        gateway = self

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
                return child.lifespan

            async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
                if scope.get("type") != "http":
                    await child(scope, receive, send)
                    return
                if not gateway.enabled:
                    await JSONResponse({"detail": "内置渠道 MCP 未启用"}, status_code=404)(scope, receive, send)
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
                    await child(scope, receive, send)
                finally:
                    _current_principal.reset(token)

        return AuthenticatedApp()


__all__ = ["BuiltinChannelMCP"]
