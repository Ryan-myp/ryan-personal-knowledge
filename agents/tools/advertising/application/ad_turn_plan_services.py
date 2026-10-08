"""Translate routed advertising Tools into one Harness tool-call turn."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness import ModelTurn


class AdTurnPlanServices:
    """Build the application Tool plan and bind writes to the existing Run."""

    def __init__(self, owner: Any, planner: Any, investigator: Any) -> None:
        self.owner = owner
        self.planner = planner
        self.investigator = investigator

    def prepare_tool_turn(
        self,
        *,
        intent: Any,
        routed: Mapping[str, list[Any]],
        session: Any,
        request: Any,
        creation_ui: Mapping[str, Any],
        context_updates: Mapping[str, Any],
        state: dict[str, Any],
    ) -> ModelTurn:
        plan = self.planner.build_plan(routed, intent, session.ctx)
        calls = tuple(plan.calls)
        state.update({
            "intent": intent,
            "calls": calls,
            "session": session,
            "ui": dict(creation_ui),
            "workflow_id": None,
            "tool_plan": {
                platform: list(names)
                for platform, names in plan.tool_plan.items()
            },
            "execution_plan": {},
            "investigation_enabled": self.investigator.eligible(intent, calls),
            "investigation_steps": 0,
        })
        workflow_id = self._start_write_workflow(
            intent,
            routed,
            session,
            request,
            plan.execution_plan,
        )
        state["workflow_id"] = workflow_id
        state["execution_plan"] = plan.execution_plan.to_dict()
        if not calls:
            return self._chat_reply(request, state, context_updates)
        return ModelTurn(
            tool_calls=calls,
            stop_reason="tool_call",
            context_updates=dict(context_updates),
        )

    @staticmethod
    def record_context_selection(session: Any, state: dict[str, Any]) -> None:
        skill_context = session.ctx.metadata.get("skill_context", {})
        skill_context = skill_context if isinstance(skill_context, Mapping) else {}
        state["tool_selection"] = {
            "knowledge": list(skill_context.get("knowledge") or []),
            "tools": list(skill_context.get("selected_tools") or []),
        }
        state["memory"] = list(skill_context.get("memory") or [])
        state["memory_updates"] = list(
            session.ctx.metadata.get("memory_updates") or []
        )

    def _start_write_workflow(
        self,
        intent: Any,
        routed: Mapping[str, list[Any]],
        session: Any,
        request: Any,
        execution_plan: Any,
    ) -> str | None:
        has_write = any(
            bool(getattr(tool, "is_write_tool", False))
            for tools in routed.values()
            for tool in tools
        )
        if not has_write:
            return None
        workflow_id = self.owner.workflow.start(
            session,
            intent,
            routed,
            execution_plan=execution_plan,
        )
        self.owner._bind_execution_run_workflow(
            str(request.run_id or ""),
            workflow_id,
        )
        return workflow_id

    def _chat_reply(
        self,
        request: Any,
        state: dict[str, Any],
        context_updates: Mapping[str, Any],
    ) -> ModelTurn:
        reply = self.owner.response_renderer.render_chat(request.user_input)
        state.update({
            "last_results": [],
            "last_reply": reply,
            "ui": {},
            "response_source": "chat",
        })
        return ModelTurn(
            content=reply,
            stop_reason="stop",
            context_updates=dict(context_updates),
        )


__all__ = ["AdTurnPlanServices"]
