"""Application turn handler injected behind the generic Agent Harness."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from agents.agent_harness import ModelTurn

from .ad_turn_account_services import AdTurnAccountServices
from .ad_turn_feature_services import (
    AdTurnFeatureServices,
    TurnFeatureContext,
)
from .ad_turn_plan_services import AdTurnPlanServices
from .ad_turn_request_services import AdTurnRequestServices
from .ad_turn_interaction_services import TurnInteractionContext


logger = logging.getLogger(__name__)


class AdvertisingTurnHandler:
    """Compose request policy, Feature hooks, interaction, and Tool planning."""

    def __init__(self, owner: Any, planner: Any, investigator: Any) -> None:
        self.owner = owner
        self.planner = planner
        self.request_services = AdTurnRequestServices(owner, planner)
        self.account_services = AdTurnAccountServices(owner)
        self.feature_services = AdTurnFeatureServices(owner)
        self.plan_services = AdTurnPlanServices(owner, planner, investigator)

    def start_turn(self, state: dict[str, Any], request: Any) -> ModelTurn:
        try:
            prepared = self.request_services.prepare(request, state)
            if prepared.model_turn is not None:
                return prepared.model_turn
            return self._route_and_prepare(request, state, prepared)
        except Exception as error:
            # Close the current generic Run with a safe failure for any handler error.
            return self._handle_preparation_error(request, state, error)

    def _route_and_prepare(
        self,
        request: Any,
        state: dict[str, Any],
        prepared: Any,
    ) -> ModelTurn:
        intent = prepared.intent
        hook_context = TurnFeatureContext(
            request=request,
            request_context=prepared.request_context,
            session=prepared.session,
            state=state,
            platform_params=prepared.platform_params,
            user_input=prepared.safe_input,
        )
        control_turn = self.feature_services.handle_control_turn(intent, hook_context)
        if control_turn is not None:
            return control_turn
        routing = self.planner.route(
            intent,
            prepared.safe_input,
            prepared.session.ctx,
        )
        intent, routed = routing.intent, dict(routing.routed)
        if routing.policy_errors:
            return self._block_routed_policy(
                intent,
                prepared.session,
                routing.policy_errors,
                state,
            )
        self._record_intent_namespaces(request, intent)
        updates, blocked = self._resolve_account_scope(
            request, state, prepared, intent, routed,
        )
        if blocked is not None:
            return blocked
        return self._prepare_routed_interactions(
            request, state, prepared, intent, routed, updates,
        )

    def _resolve_account_scope(
        self,
        request: Any,
        state: dict[str, Any],
        prepared: Any,
        intent: Any,
        routed: Mapping[str, list[Any]],
    ) -> tuple[dict[str, Any], ModelTurn | None]:
        decision = self.account_services.resolve_read_account_scope(
            intent=intent,
            routed=routed,
            request=request,
            request_context=prepared.request_context,
            session=prepared.session,
            state=state,
        )
        updates = dict(decision.context_updates)
        if decision.model_turn is not None:
            return updates, decision.model_turn
        self.plan_services.record_context_selection(prepared.session, state)
        blocked = self.account_services.validate_write_account_scope(
            intent=intent,
            routed=routed,
            request=request,
            request_context=prepared.request_context,
            state=state,
            context_updates=updates,
        )
        return updates, blocked

    def _prepare_routed_interactions(
        self,
        request: Any,
        state: dict[str, Any],
        prepared: Any,
        intent: Any,
        routed: Mapping[str, list[Any]],
        context_updates: Mapping[str, Any],
    ) -> ModelTurn:
        context = TurnFeatureContext(
            request=request,
            request_context=prepared.request_context,
            session=prepared.session,
            state=state,
            platform_params=prepared.platform_params,
            user_input=prepared.safe_input,
            context_updates=context_updates,
        )
        feature_turn = self.feature_services.handle_routed_turn(
            intent,
            routed,
            context,
        )
        if feature_turn is not None:
            return feature_turn
        interaction = TurnInteractionContext(
            request=request,
            request_context=prepared.request_context,
            session=prepared.session,
            user_input=prepared.safe_input,
            context_updates=context_updates,
            state=state,
        )
        creation = self.owner.prepare_creation_turn(intent, routed, interaction)
        if creation.model_turn is not None:
            return creation.model_turn
        clarification = self.owner.prepare_action_clarification(
            intent,
            routed,
            interaction,
        )
        if clarification is not None:
            return clarification
        return self.plan_services.prepare_tool_turn(
            intent=intent, routed=routed, session=prepared.session, request=request,
            creation_ui=creation.creation_ui, context_updates=context_updates,
            state=state,
        )

    @staticmethod
    def _record_intent_namespaces(request: Any, intent: Any) -> None:
        context = getattr(request, "context", None)
        if isinstance(context, dict):
            context["_agent_intent_namespaces"] = list(
                getattr(intent, "namespaces", []) or []
            )

    @staticmethod
    def _block_routed_policy(
        intent: Any,
        session: Any,
        errors: tuple[str, ...],
        state: dict[str, Any],
    ) -> ModelTurn:
        reply = "❌ 业务策略阻止本次请求：" + "；".join(errors)
        state.update({
            "intent": intent,
            "calls": (),
            "session": session,
            "policy_errors": list(errors),
            "last_results": [],
            "last_reply": reply,
            "response_source": "policy",
            "ui": {},
        })
        return ModelTurn(content=reply, stop_reason="policy_blocked")

    @staticmethod
    def _handle_preparation_error(
        request: Any,
        state: dict[str, Any],
        error: Exception,
    ) -> ModelTurn:
        state["intent"] = None
        state["reason"] = "turn_preparation_failed"
        state["error_type"] = type(error).__name__
        logger.error(
            "Advertising turn preparation failed",
            extra={"error_type": type(error).__name__},
        )
        callback = getattr(request, "event_callback", None)
        if callable(callback):
            callback({
                "type": "stage_status",
                "stage_id": "intent",
                "status": "failed",
                "error_type": type(error).__name__,
            })
        state["last_results"] = [{
            "success": False,
            "error": "暂时无法完成请求理解，请稍后重试。",
        }]
        return ModelTurn(
            content="暂时无法完成请求理解，请稍后重试。",
            stop_reason="error",
            usage={"error_type": type(error).__name__},
        )


__all__ = ["AdvertisingTurnHandler"]
