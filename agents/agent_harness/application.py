"""Convenient application-neutral Agent assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .agent import Agent
from .agent_runtime import AgentRuntime
from .run_store import RunStore
from .skills import InMemorySkillCatalog, SkillSource
from .tool_catalog import InMemoryToolCatalog
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
        event_callback: Any = None,
    ) -> "AgentApplication":
        skills = InMemorySkillCatalog()
        tools = InMemoryToolCatalog()
        agent = Agent(
            model=model,
            tool_catalog=tools,
            skill_catalog=skills,
            system_prompt=system_prompt,
            max_turns=max_turns,
            tool_execution=tool_execution,
            event_callback=event_callback,
        )
        runtime = AgentRuntime(
            agent=agent,
            tool_registry=tools,
            skill_catalog=skills,
            run_store=run_store,
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
