"""Portable advertising Tool Source adaptation for any standard Agent Harness."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import ToolContext


def advertising_tool_source(
    provider_tools: Any,
    *,
    source_id: str | None = None,
) -> StaticToolSource:
    """Expose advertising Tools as a generic Tool Source.

    Standard providers publish ``list_bindings()`` directly. Small local
    publishers may expose ``register_tools()`` contract/executor pairs. The
    consuming Harness sees only standard Tool bindings and owns its policy.
    """
    publish = getattr(provider_tools, "list_bindings", None)
    if callable(publish):
        bindings = list(publish())
        platform = str(getattr(provider_tools, "platform_name", "advertising"))
        return StaticToolSource(source_id or f"advertising:{platform}", bindings)
    register_tools = getattr(provider_tools, "register_tools", None)
    if not callable(register_tools):
        raise TypeError("provider_tools must expose register_tools()")
    bindings = []
    for definition, executor in register_tools():
        bindings.append(
            ToolBinding(
                definition,
                _GenericContextExecutor(executor),
            )
        )
    platform = str(
        getattr(provider_tools, "platform_name", "advertising") or "advertising"
    ).strip()
    return StaticToolSource(source_id or f"advertising:{platform}", bindings)


class _GenericContextExecutor:
    """Bridge generic ToolCallContext into the ad ToolContext contract."""

    def __init__(self, executor: Any) -> None:
        self.executor = executor

    def execute(self, context: Any, input_data: dict[str, Any]) -> Any:
        request = context.request
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        ad_context = ToolContext(
            session_id=str(request.session_id or ""),
            user_id=str(request.user_id or "anonymous"),
            scope={
                key: value
                for key, value in request_context.items()
                if not key.startswith("_agent_")
            },
            credentials=request_context.get("credentials"),
            metadata={
                "execution_mode": str(request.execution_mode or "dry_run"),
                "run_id": str(request.run_id or ""),
                "turn_id": str(request.turn_id or ""),
                "cancellation_event": request.cancellation_event,
                "lease_lost_event": request.lease_lost_event,
            },
        )
        execute = getattr(self.executor, "execute", None)
        if callable(execute):
            return execute(ad_context, input_data)
        if callable(self.executor):
            return self.executor(ad_context, input_data)
        raise TypeError("advertising Tool executor is not callable")


def portable_binding(definition: Any, executor: Any) -> ToolBinding:
    """Adapt one fixed Provider handler to the standard ToolCallContext."""
    return ToolBinding(definition, _GenericContextExecutor(executor))
