"""Advertising application stages over the generic Agent Harness contract."""

from __future__ import annotations

from typing import Any

from agents.agent_harness.turn_pipeline import (
    TurnExecutionContext,
    TurnStageResult,
)

from .ad_turn_flow import execute as execute_ad_turn
from .ad_turn_state import AdTurnState


class _AdStage:
    """Small stage base that exposes stable names and shared app state."""

    name = "ad_stage"

    def _state(self, context: TurnExecutionContext) -> AdTurnState:
        state = context.state.get("ad_turn")
        if not isinstance(state, AdTurnState):
            state = AdTurnState.from_request(context.request)
            context.state["ad_turn"] = state
        return state

    def execute(self, context: TurnExecutionContext) -> TurnStageResult:
        state = self._state(context)
        state.mark_stage(self.name, status="completed")
        return TurnStageResult.continue_with(metadata={"state": self.name})


class RequestValidationStage(_AdStage):
    name = "request_validation"


class SessionContextStage(_AdStage):
    name = "session_context"


class IntentStage(_AdStage):
    name = "intent"


class PlanningStage(_AdStage):
    name = "planning"


class ExecutionStage(_AdStage):
    name = "execution"

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def execute(self, context: TurnExecutionContext) -> TurnStageResult:
        state = self._state(context)
        principal = context.request.principal
        permissions = (
            principal.permissions
            if principal is not None
            else getattr(self.runtime, "_granted_permissions", None)
        )
        account_scope = (
            principal.account_scope if principal is not None else None
        )
        if not hasattr(self.runtime, "_validate_request_limits"):
            legacy_result = self.runtime._run_unlocked(
                user_input=context.request.user_input,
                session_id=context.request.session_id,
                run_id=context.request.run_id,
                turn_id=context.request.turn_id,
                user_id=context.request.user_id,
                account_id=state.request_context.get("account_id"),
                credentials=state.request_context.get("credentials"),
                platform_params=state.request_context.get("platform_params"),
                confirmed=bool(state.request_context.get("confirmed", False)),
                confirmation_payload=state.request_context.get(
                    "confirmation_payload"
                ),
                creation_blueprint_id=state.request_context.get(
                    "creation_blueprint_id"
                ),
                creation_blueprint_version=state.request_context.get(
                    "creation_blueprint_version"
                ),
                granted_permissions=permissions,
                account_scope=account_scope,
                tenant_id=context.request.tenant_id,
                cancellation_event=context.request.cancellation_event,
                lease_lost_event=context.request.lease_lost_event,
                event_callback=context.request.event_callback,
                task_id=context.request.task_id,
            )
            state.capture_response(legacy_result)
            return TurnStageResult.continue_with()
        response = execute_ad_turn(
            self.runtime,
            user_input=context.request.user_input,
            session_id=context.request.session_id,
            run_id=context.request.run_id,
            turn_id=context.request.turn_id,
            user_id=context.request.user_id,
            account_id=state.request_context.get("account_id"),
            credentials=state.request_context.get("credentials"),
            platform_params=state.request_context.get("platform_params"),
            confirmed=bool(state.request_context.get("confirmed", False)),
            confirmation_payload=state.request_context.get("confirmation_payload"),
            creation_blueprint_id=state.request_context.get("creation_blueprint_id"),
            creation_blueprint_version=state.request_context.get(
                "creation_blueprint_version"
            ),
            granted_permissions=(
                state.request_context.get("granted_permissions")
                if state.request_context.get("granted_permissions") is not None
                else permissions
            ),
            account_scope=(
                state.request_context.get("account_scope")
                if state.request_context.get("account_scope") is not None
                else account_scope
            ),
            tenant_id=context.request.tenant_id,
            cancellation_event=context.request.cancellation_event,
            lease_lost_event=context.request.lease_lost_event,
            event_callback=context.request.event_callback,
            task_id=context.request.task_id,
        )
        state.capture_response(response)
        state.mark_stage(
            self.name,
            status="completed",
            result_count=len(state.results),
        )
        return TurnStageResult.continue_with(
            metadata={"result_count": len(state.results)}
        )


class ResponseStage(_AdStage):
    name = "response"

    def execute(self, context: TurnExecutionContext) -> TurnStageResult:
        state = self._state(context)
        state.mark_stage(
            self.name,
            status="completed",
            response_source=state.response_source,
        )
        return TurnStageResult.complete(
            state.response,
            metadata={"response_source": state.response_source},
        )


__all__ = [
    "ExecutionStage",
    "IntentStage",
    "PlanningStage",
    "RequestValidationStage",
    "ResponseStage",
    "SessionContextStage",
]
