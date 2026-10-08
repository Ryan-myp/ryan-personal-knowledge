"""Prepare trusted request context and intent before an advertising Tool plan."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from agents.agent_harness import ModelTurn

from agents.agent_harness.core.interfaces import ParsedIntent, ToolContext


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedTurnInput:
    """Validated, session-bound inputs consumed by turn policy and planning."""

    request_context: dict[str, Any]
    session: Any
    safe_input: str
    platform_params: Any
    intent: Any
    model_turn: ModelTurn | None = None


class AdTurnRequestServices:
    """Own request validation, intent enrichment, and session adaptation."""

    def __init__(self, owner: Any, planner: Any) -> None:
        self.owner = owner
        self.planner = planner

    def prepare(
        self,
        request: Any,
        state: dict[str, Any],
    ) -> PreparedTurnInput:
        request_context = (
            dict(request.context) if isinstance(request.context, Mapping) else {}
        )
        session = self._session_for(request, request_context)
        state["session"] = session
        ad_context = self._tool_context(request, request_context, session)
        safe_input = self.owner._redact_for_persistence(request.user_input)
        terminal = self._validate_input(
            request.user_input,
            request_context,
            safe_input,
            session,
            state,
        )
        if terminal is not None:
            return self._prepared(
                request_context, session, safe_input, None, terminal,
            )
        return self._prepare_intent(
            request,
            state,
            request_context,
            session,
            safe_input,
            ad_context,
        )

    def _prepare_intent(
        self,
        request: Any,
        state: dict[str, Any],
        request_context: dict[str, Any],
        session: Any,
        safe_input: str,
        ad_context: ToolContext,
    ) -> PreparedTurnInput:
        intent = self.owner.intent_parser.parse(safe_input, ad_context)
        intent, terminal = self.owner.prepare_creation_template(
            intent,
            request=request,
            request_context=request_context,
            state=state,
        )
        if terminal is not None:
            return self._prepared(
                request_context, session, safe_input, intent, terminal,
            )

        platform_params = request_context.get("platform_params")
        terminal = self._merge_trusted_platform_params(
            intent,
            platform_params,
            session,
            state,
        )
        if terminal is not None:
            return self._prepared(
                request_context,
                session,
                safe_input,
                intent,
                terminal,
                platform_params,
            )
        intent = self._adopt_drafts(intent, request, request_context, safe_input)
        return self._prepared(
            request_context,
            session,
            safe_input,
            intent,
            platform_params=platform_params,
        )

    def _adopt_drafts(
        self,
        intent: Any,
        request: Any,
        request_context: Mapping[str, Any],
        safe_input: str,
    ) -> Any:
        intent = self._adopt_pending_intents(intent, request)
        return self.owner.adopt_creation_drafts(
            str(request.session_id or ""),
            intent,
            safe_input,
            has_blueprint=bool(request_context.get("creation_blueprint_id")),
        )

    @staticmethod
    def _prepared(
        request_context: dict[str, Any],
        session: Any,
        safe_input: str,
        intent: Any,
        model_turn: ModelTurn | None = None,
        platform_params: Any = None,
    ) -> PreparedTurnInput:
        if platform_params is None:
            platform_params = request_context.get("platform_params")
        return PreparedTurnInput(
            request_context,
            session,
            safe_input,
            platform_params,
            intent,
            model_turn,
        )

    def _session_for(self, request: Any, request_context: Mapping[str, Any]) -> Any:
        session_id = str(request.session_id or "")
        session = self.owner._sessions.get(session_id)
        if session is not None:
            return session
        return self.owner._ensure_session(
            session_id,
            request.user_id,
            request_context.get("account_id"),
            request_context.get("credentials"),
            tenant_id=request.tenant_id,
        )

    @staticmethod
    def _tool_context(
        request: Any,
        request_context: Mapping[str, Any],
        session: Any,
    ) -> ToolContext:
        agent_context = request_context.get("agent_context")
        skill_context = (
            agent_context.get("skill_context")
            if isinstance(agent_context, Mapping) else None
        )
        scope = {
            key: value
            for key, value in request_context.items()
            if key != "_agent_application_state"
        }
        return ToolContext(
            session_id=str(request.session_id or ""),
            user_id=str(request.user_id or "anonymous"),
            scope=scope,
            credentials=request_context.get("credentials"),
            protected_state=session.protected_state,
            metadata={
                "execution_mode": str(request.execution_mode or "dry_run"),
                "run_id": str(request.run_id or ""),
                "turn_id": str(request.turn_id or ""),
                "cancellation_event": request.cancellation_event,
                "lease_lost_event": request.lease_lost_event,
                "skill_context": (
                    dict(skill_context) if isinstance(skill_context, Mapping) else {}
                ),
            },
        )

    def _validate_input(
        self,
        raw_user_input: str,
        request_context: Mapping[str, Any],
        safe_input: str,
        session: Any,
        state: dict[str, Any],
    ) -> ModelTurn | None:
        protected = self.owner.security.validate_text_redline(raw_user_input)
        if protected:
            message = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected)
            return self._block_request(
                state,
                session,
                message,
                f"❌ 参数契约阻止本次请求：{message}",
                "input_contract",
            )
        input_error = self.owner._validate_request_limits(
            safe_input,
            request_context.get("platform_params"),
        )
        if input_error:
            return self._block_request(
                state,
                session,
                input_error,
                f"❌ {input_error}",
                "request_limits",
            )
        return None

    def _merge_trusted_platform_params(
        self,
        intent: Any,
        platform_params: Any,
        session: Any,
        state: dict[str, Any],
    ) -> ModelTurn | None:
        if not isinstance(platform_params, Mapping):
            return None
        protected = self.owner.security.validate_input_redline(platform_params)
        if protected:
            message = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected)
            return self._block_request(
                state,
                session,
                message,
                f"❌ {message}",
                "input_contract",
            )
        self.planner.merge_platform_params(intent, platform_params)
        return None

    def _adopt_pending_intents(self, intent: Any, request: Any) -> Any:
        for feature in self.owner.features:
            adopt = getattr(feature, "adopt_pending_intent", None)
            if not callable(adopt):
                continue
            try:
                result = adopt(
                    self.owner.services,
                    intent,
                    session_id=str(request.session_id or ""),
                )
            except Exception as error:
                # Feature failures must abort intent adoption; log safely and re-raise.
                logger.warning(
                    "Pending Feature intent adoption failed",
                    extra={
                        "feature": str(getattr(feature, "feature_name", "unknown")),
                        "error_type": type(error).__name__,
                    },
                )
                raise
            if result is not None:
                intent = result
        return intent

    @staticmethod
    def _block_request(
        state: dict[str, Any],
        session: Any,
        reason: str,
        reply: str,
        response_source: str,
    ) -> ModelTurn:
        state.update({
            "intent": None,
            "calls": (),
            "session": session,
            "policy_errors": [reason],
            "last_results": [],
            "last_reply": reply,
            "response_source": response_source,
            "ui": {},
        })
        return ModelTurn(content=reply, stop_reason="policy_blocked")


__all__ = ["AdTurnRequestServices", "PreparedTurnInput"]
