"""Convenient application-neutral Agent assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .agent import Agent
from .agent_runtime import AgentRuntime
from .context import ContextProvider
from .observability import MetricsSink
from .run_store import RunStore
from .skills import InMemorySkillCatalog, SkillCatalog, SkillSource
from .tool_catalog import InMemoryToolCatalog, ToolCatalog
from .tool_sources import ToolSource


@dataclass
class AgentApplication:
    """A reusable Skills + Tools application with one generic Runtime."""

    runtime: AgentRuntime
    agent: Agent
    skills: InMemorySkillCatalog
    tools: InMemoryToolCatalog

    @classmethod
    def create(
        cls,
        *,
        model: Any,
        system_prompt: str = "",
        max_turns: int = 12,
        tool_execution: str = "parallel",
        run_store: Optional[RunStore] = None,
        metrics: Optional[MetricsSink] = None,
        event_callback: Any = None,
        before_tool_call: Any = None,
        after_tool_call: Any = None,
        max_parallel_tools: int = 8,
        tool_policy: Any = None,
        tool_catalog: Optional[ToolCatalog] = None,
        skill_catalog: Optional[SkillCatalog] = None,
        ports: Any = None,
        context_provider: Optional[ContextProvider] = None,
        input_sanitizer: Any = None,
    ) -> "AgentApplication":
        if tool_policy is not None:
            if before_tool_call is not None or after_tool_call is not None:
                raise ValueError(
                    "provide tool_policy or explicit Tool hooks, not both"
                )
            before_tool_call = getattr(tool_policy, "before_tool_call", None)
            after_tool_call = getattr(tool_policy, "after_tool_call", None)
        skills = skill_catalog or InMemorySkillCatalog()
        tools = tool_catalog or InMemoryToolCatalog()
        agent = Agent(
            model=model,
            tool_catalog=tools,
            skill_catalog=skills,
            system_prompt=system_prompt,
            max_turns=max_turns,
            tool_execution=tool_execution,
            max_parallel_tools=max_parallel_tools,
            before_tool_call=before_tool_call,
            after_tool_call=after_tool_call,
            event_callback=event_callback,
            context_provider=context_provider,
            input_sanitizer=input_sanitizer,
        )
        runtime = AgentRuntime(
            agent=agent,
            tool_registry=tools,
            skill_catalog=skills,
            run_store=run_store,
            metrics=metrics,
            ports=ports,
        )
        return cls(runtime=runtime, agent=agent, skills=skills, tools=tools)

    def register_skill_source(self, source: SkillSource) -> list[str]:
        return self.skills.register_source(source)

    def register_tool_source(self, source: ToolSource) -> list[str]:
        return self.runtime.register_tool_source(source)

    def prompt(self, user_input: str, **kwargs: Any) -> Any:
        from .runtime_kernel import TurnRequest

        return self.runtime.run(TurnRequest(
            user_input=str(user_input),
            **kwargs,
        ))

    def close(self) -> None:
        self.runtime.close()


__all__ = ["AgentApplication"]
