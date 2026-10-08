"""Dispatch optional application hooks published by registered Features."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from agents.agent_harness import ModelTurn

from agents.agent_platform.governance.identity.principal import RequestPrincipal


@dataclass(frozen=True)
class TurnFeatureContext:
    """Turn-scoped values passed to optional application Feature hooks."""

    request: Any
    request_context: Mapping[str, Any]
    session: Any
    state: dict[str, Any]
    platform_params: Any = None
    user_input: str = ""
    context_updates: Mapping[str, Any] = field(default_factory=dict)


class AdTurnFeatureServices:
    """Keep Feature hooks at the application boundary, outside the Harness."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def handle_control_turn(
        self,
        intent: Any,
        context: TurnFeatureContext,
    ) -> ModelTurn | None:
        feature = self.owner._feature_for_intent(intent)
        handler = getattr(feature, "handle_turn", None)
        if not callable(handler):
            return None
        request = context.request
        result = handler(
            self.owner.services,
            intent,
            session_id=str(request.session_id or ""),
            user_id=str(request.user_id or "anonymous"),
            tenant_id=str(request.tenant_id or "default"),
            account_id=context.request_context.get("account_id"),
            platform_params=context.platform_params,
            principal=self._principal(request),
        )
        return self._control_result_turn(intent, feature, result, context)

    def _control_result_turn(
        self,
        intent: Any,
        feature: Any,
        result: Mapping[str, Any],
        context: TurnFeatureContext,
    ) -> ModelTurn:
        reply = str(result.get("reply") or "已处理。")
        needs_input = bool(result.get("needs_input"))
        response_type = str(
            getattr(feature, "turn_response_type", "feature") or "feature"
        )
        context.state.update({
            "intent": intent,
            "calls": (),
            "session": context.session,
            "last_results": [{
                "success": bool(result.get("success")),
                **{key: value for key, value in result.items() if key != "reply"},
            }],
            "last_reply": reply,
            "needs_input": needs_input,
            "needs_confirmation": bool(result.get("needs_confirmation")),
            "response_source": response_type,
            "workflow_id": None,
            "ui": {"type": response_type, **result},
        })
        return ModelTurn(
            content=reply,
            stop_reason="awaiting_input" if needs_input else "stop",
        )

    def _principal(self, request: Any) -> Any:
        return getattr(request, "principal", None) or RequestPrincipal(
            user_id=str(request.user_id or "anonymous"),
            tenant_id=str(request.tenant_id or "default"),
            permissions=frozenset(self.owner._granted_permissions),
            account_scope={},
        )

    def handle_routed_turn(
        self,
        intent: Any,
        routed: Mapping[str, list[Any]],
        context: TurnFeatureContext,
    ) -> ModelTurn | None:
        feature = self.owner._feature_for_intent(intent)
        handler = getattr(feature, "handle_routed_turn", None)
        if not callable(handler):
            return None
        return handler(
            services=self.owner.services,
            workflow=self.owner.workflow,
            canonicalize=self.owner._canonical_platform,
            bind_run_workflow=self.owner._bind_execution_run_workflow,
            granted_permissions=self.owner._granted_permissions,
            intent=intent,
            tool_plan=routed,
            request=context.request,
            request_context=context.request_context,
            session=context.session,
            user_input=context.user_input,
            context_updates=context.context_updates,
            state=context.state,
        )


__all__ = ["AdTurnFeatureServices", "TurnFeatureContext"]
