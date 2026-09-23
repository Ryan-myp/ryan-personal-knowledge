"""Convenient application-neutral Agent assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .agent import Agent
from .agent_runtime import AgentRuntime
from .context import ContextProvider
from .observability import AlertSink, MetricsSink, TraceSink
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
        trace: Optional[TraceSink] = None,
        alerts: Optional[AlertSink] = None,
        event_callback: Any = None,
        before_tool_call: Any = None,
        after_tool_call: Any = None,
        max_parallel_tools: int = 8,
        max_tools: int = 128,
        tool_selector: Any = None,
        tool_policy: Any = None,
        tool_catalog: Optional[ToolCatalog] = None,
        skill_catalog: Optional[SkillCatalog] = None,
        ports: Any = None,
        context_provider: Optional[ContextProvider] = None,
        input_sanitizer: Any = None,
        default_execution_mode: str = "dry_run",
        model_max_retries: int = 0,
        model_retry_delay_seconds: float = 0.0,
        max_transcript_messages: int = 200,
        max_transcript_chars: int = 100_000,
        transcript_store: Any = None,
        idempotency_store: Any = None,
        model_timeout_seconds: float | None = None,
        model_fallbacks: Any = (),
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        max_total_tokens: int | None = None,
        max_tool_result_chars: int = 32_000,
        session_ttl_seconds: float = 3600.0,
        max_sessions: int = 1000,
    ) -> "AgentApplication":
        if tool_policy is not None:
            if before_tool_call is not None or after_tool_call is not None:
                raise ValueError(
                    "provide tool_policy or explicit Tool hooks, not both"
                )
            before_tool_call = getattr(tool_policy, "before_tool_call", None)
            after_tool_call = getattr(tool_policy, "after_tool_call", None)
            if (
                idempotency_store is not None
                and getattr(tool_policy, "idempotency_store", None) is None
            ):
                tool_policy.idempotency_store = idempotency_store
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
            max_tools=max_tools,
            tool_selector=tool_selector,
            before_tool_call=before_tool_call,
            after_tool_call=after_tool_call,
            event_callback=event_callback,
            context_provider=context_provider,
            input_sanitizer=input_sanitizer,
            model_max_retries=model_max_retries,
            model_retry_delay_seconds=model_retry_delay_seconds,
            max_transcript_messages=max_transcript_messages,
            max_transcript_chars=max_transcript_chars,
            transcript_store=transcript_store,
            model_timeout_seconds=model_timeout_seconds,
            model_fallbacks=model_fallbacks,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
            max_total_tokens=max_total_tokens,
            max_tool_result_chars=max_tool_result_chars,
            session_ttl_seconds=session_ttl_seconds,
            max_sessions=max_sessions,
        )
        runtime = AgentRuntime(
            agent=agent,
            tool_registry=tools,
            skill_catalog=skills,
            run_store=run_store,
            metrics=metrics,
            trace=trace,
            alerts=alerts,
            ports=ports,
            default_execution_mode=default_execution_mode,
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

    def healthcheck(self) -> dict[str, Any]:
        check = getattr(self.runtime, "healthcheck", None)
        if callable(check):
            return dict(check())
        return {"status": "ok", "closed": self.runtime.closed}

    def readiness(self) -> dict[str, Any]:
        check = getattr(self.runtime, "readiness", None)
        if callable(check):
            return dict(check())
        health = self.healthcheck()
        ready = health.get("status") == "ok"
        return {
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "reason": None if ready else health.get("status"),
            "health": health,
        }

    def close(self) -> None:
        self.runtime.close()


__all__ = ["AgentApplication"]
