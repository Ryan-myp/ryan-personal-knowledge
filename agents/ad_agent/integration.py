"""Adapters that let advertising Skills/Tools plug into any Agent Harness."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness import (
    MarkdownSkillDirectorySource,
    StaticToolSource,
    ToolBinding,
)
from .core.interfaces import ToolContext


def capability_tool_source(
    capability: Any, *, source_id: str | None = None,
) -> StaticToolSource:
    """Expose an ad Capability's Tool definitions as a generic Tool Source."""
    register_tools = getattr(capability, "register_tools", None)
    if not callable(register_tools):
        raise TypeError("capability must expose register_tools()")
    bindings = []
    for definition, executor in register_tools():
        bindings.append(ToolBinding(
            definition,
            _GenericContextExecutor(executor),
        ))
    platform = str(getattr(capability, "platform_name", "ad") or "ad").strip()
    return StaticToolSource(source_id or f"ad-capability:{platform}", bindings)


def advertising_skill_source(*, source_id: str = "ad-skills") -> MarkdownSkillDirectorySource:
    """Expose the ad Skill Markdown tree to any generic Agent."""
    from pathlib import Path

    return MarkdownSkillDirectorySource(
        Path(__file__).resolve().parent / "skills",
        source_id=source_id,
    )


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
            scope=dict(request_context),
            credentials=request_context.get("credentials"),
            metadata={
                "execution_mode": str(request.execution_mode or "dry_run"),
                "run_id": str(request.run_id or ""),
                "turn_id": str(request.turn_id or ""),
            },
        )
        execute = getattr(self.executor, "execute", None)
        if callable(execute):
            return execute(ad_context, input_data)
        if callable(self.executor):
            return self.executor(ad_context, input_data)
        raise TypeError("advertising Tool executor is not callable")


__all__ = ["advertising_skill_source", "capability_tool_source"]
