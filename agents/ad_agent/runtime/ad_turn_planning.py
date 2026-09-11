"""Application planning for one advertising turn.

This module owns the transition from a parsed intent to an authoritative Tool
plan. It may ask the active parser to repair a route against the registered
catalog and may replace the route with an explicitly selected Blueprint plan.
It never executes a Tool, creates a workflow, or renders UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class AdTurnRoutingResult:
    """Authoritative plan and any policy/Blueprint error discovered in planning."""

    intent: Any
    tool_plan: dict[str, list[Any]]
    policy_errors: list[str]
    blueprint_error: Optional[str] = None


class AdTurnPlanningService:
    """Resolve executable plans from current registry and declarative metadata."""

    @staticmethod
    def route_tools(runtime: Any, intent: Any) -> dict[str, list[Any]]:
        """Route only through the current registry; no provider map is kept here."""
        return runtime.intent_router.route(intent, runtime.registry)

    def route(
        self,
        *,
        runtime: Any,
        intent: Any,
        safe_user_input: str,
        session: Any,
        creation_blueprint_id: Optional[str],
        creation_blueprint_version: Optional[str],
    ) -> AdTurnRoutingResult:
        """Build the plan after optional parser repair and Blueprint selection."""
        tool_plan = self.route_tools(runtime, intent)
        routed_platforms = {
            runtime._canonical_platform(platform) for platform in tool_plan
        }
        requested_platforms = {
            runtime._canonical_platform(platform)
            for platform in (getattr(intent, "namespaces", []) or [])
        }
        route_is_incomplete = bool(
            requested_platforms and routed_platforms != requested_platforms
        )
        should_repair_route = bool(
            tool_plan
            or route_is_incomplete
            or str(getattr(intent, "intent_type", "") or "") != "chat"
            or bool(getattr(intent, "namespaces", []) or [])
        )
        if should_repair_route and (not tool_plan or route_is_incomplete):
            repair = getattr(runtime.intent_parser, "repair_for_routing", None)
            repaired_intent = (
                repair(safe_user_input, session.ctx, intent)
                if callable(repair)
                else None
            )
            if repaired_intent is not None:
                intent = repaired_intent
                runtime._load_required_skills(intent.namespaces)
                policy_errors = runtime._validate_policies(intent)
                if not policy_errors:
                    tool_plan = self.route_tools(runtime, intent)
                else:
                    return AdTurnRoutingResult(
                        intent=intent,
                        tool_plan={},
                        policy_errors=policy_errors,
                    )

        if creation_blueprint_id:
            blueprint_tool_plan, blueprint_error = runtime._creation_blueprint_tool_plan(
                creation_blueprint_id,
                creation_blueprint_version,
                intent,
            )
            if blueprint_error:
                return AdTurnRoutingResult(
                    intent=intent,
                    tool_plan={},
                    policy_errors=[],
                    blueprint_error=blueprint_error,
                )
            # Blueprint submission is an explicit structured continuation. The
            # Blueprint's declared Tool composition is authoritative; the
            # original intent name remains provider/application-owned metadata.
            intent.namespaces = [next(iter(blueprint_tool_plan))]
            tool_plan = blueprint_tool_plan or {}

        return AdTurnRoutingResult(
            intent=intent,
            tool_plan=tool_plan,
            policy_errors=[],
        )


__all__ = ["AdTurnPlanningService", "AdTurnRoutingResult"]
