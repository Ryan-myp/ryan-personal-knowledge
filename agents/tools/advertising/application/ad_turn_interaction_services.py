"""User-facing clarification and creation interactions for one advertising turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from agents.agent_harness import ModelTurn

from agents.agent_harness.core.interfaces import ParsedIntent
from agents.tools.advertising.shared.creation_templates import CreationTemplateError


@dataclass(frozen=True)
class TurnInteractionResult:
    """Creation UI prepared for a Tool plan, or a terminal prompt for the user."""

    creation_ui: Mapping[str, Any] = field(default_factory=dict)
    model_turn: ModelTurn | None = None


@dataclass(frozen=True)
class TurnInteractionContext:
    """Request values shared by the creation and clarification decisions."""

    request: Any
    request_context: Mapping[str, Any]
    session: Any
    user_input: str
    context_updates: Mapping[str, Any]
    state: dict[str, Any]


class AdTurnInteractionServicesMixin:
    """Own clarification and creation interaction policy, not Run execution."""

    def prepare_creation_template(
        self, intent: Any, *, request: Any, request_context: dict[str, Any],
        state: dict[str, Any],
    ) -> tuple[Any, ModelTurn | None]:
        template_id = str(request_context.get("creation_template_id") or "").strip()
        if template_id:
            intent, blocked = self._apply_selected_template(
                intent, template_id, request, request_context, state,
            )
            if blocked is not None:
                return intent, blocked
        if (
            request_context.get("creation_blueprint_id")
            and getattr(intent, "intent_type", "") == "chat"
        ):
            intent = self._blueprint_creation_intent(intent)
        return intent, None

    def _apply_selected_template(
        self, intent: Any, template_id: str, request: Any,
        request_context: dict[str, Any], state: dict[str, Any],
    ) -> tuple[Any, ModelTurn | None]:
        try:
            intent = self.apply_creation_template_to_intent(
                intent, template_id,
                account_id=request_context.get("account_id"),
                account_scope=getattr(
                    getattr(request, "principal", None), "account_scope", None,
                ),
                tenant_id=str(request.tenant_id or "default"),
                user_id=str(request.user_id or "anonymous"),
            )
        except CreationTemplateError as error:
            turn = self._block_creation_turn(
                state, intent, "creation_template_invalid",
                "无法应用所选创建模板，请重新选择模板后重试。",
                error_type=type(error).__name__,
            )
            return intent, turn
        metadata = getattr(intent, "metadata", {}) or {}
        blueprint_id = str(metadata.get("creation_blueprint_id") or "").strip()
        requested_id = str(request_context.get("creation_blueprint_id") or "").strip()
        if requested_id and blueprint_id and requested_id != blueprint_id:
            turn = self._block_creation_turn(
                state, intent, "creation_template_blueprint_mismatch",
                "创建模板与当前广告类型不一致，请重新选择模板。",
            )
            return intent, turn
        if blueprint_id:
            request_context["creation_blueprint_id"] = blueprint_id
            request_context["creation_blueprint_version"] = str(
                metadata.get("creation_blueprint_version") or ""
            ) or None
        if not request_context.get("account_id"):
            account_id = str(
                metadata.get("creation_template_account_id") or ""
            ).strip()
            if account_id:
                request_context["account_id"] = account_id
        return intent, None

    @staticmethod
    def _blueprint_creation_intent(intent: Any) -> ParsedIntent:
        return ParsedIntent(
            "create_campaign",
            intent.raw_input,
            list(getattr(intent, "namespaces", []) or []),
            attributes=dict(getattr(intent, "attributes", {}) or {}),
            parameters=dict(getattr(intent, "parameters", {}) or {}),
            scoped_parameters=dict(getattr(intent, "scoped_parameters", {}) or {}),
            metadata=dict(getattr(intent, "metadata", {}) or {}),
        )

    def adopt_creation_drafts(
        self,
        session_id: str,
        intent: Any,
        user_input: str,
        *,
        has_blueprint: bool,
    ) -> Any:
        if has_blueprint:
            return intent
        intent = self._adopt_creation_draft(session_id, intent, user_input)
        return self._adopt_action_draft(session_id, intent, user_input)

    def prepare_creation_turn(
        self, intent: Any, routed: Mapping[str, list[Any]],
        context: TurnInteractionContext,
    ) -> TurnInteractionResult:
        if not self.creation_card_builder.is_creation_intent(intent):
            return TurnInteractionResult()
        context.state["session"] = context.session
        creation_ui = self._creation_ui(intent, routed, context)
        if not context.request_context.get("creation_blueprint_id"):
            return self._prepare_unselected_creation(intent, context)
        return self._prepare_blueprint_creation(
            intent, routed, creation_ui, context,
        )

    def _creation_ui(
        self, intent: Any, routed: Mapping[str, list[Any]],
        context: TurnInteractionContext,
    ) -> Mapping[str, Any]:
        request = context.request
        return self.build_creation_ui(
            intent, tool_plan=routed,
            account_scope=getattr(
                getattr(request, "principal", None), "account_scope", None,
            ),
            tenant_id=str(request.tenant_id or "default"),
            user_id=str(request.user_id or "anonymous"),
            account_id=context.request_context.get("account_id"),
        ) or {}

    def _prepare_unselected_creation(
        self, intent: Any, context: TurnInteractionContext,
    ) -> TurnInteractionResult:
        creation_ui = self.build_creation_ui(
            intent,
            account_scope=getattr(
                getattr(context.request, "principal", None), "account_scope", None,
            ),
            tenant_id=str(context.request.tenant_id or "default"),
            user_id=str(context.request.user_id or "anonymous"),
            account_id=context.request_context.get("account_id"),
        ) or {}
        cards = self._cards(creation_ui)
        if self._selector_needs_choice(cards):
            ui = {
                "schema_version": "1.0", "needs_input": True,
                "cards": [],
                "clarification": self.creation_card_builder.build_clarification(intent),
            }
            return self._request_creation_input(
                intent, ui, self.creation_ui_reply(ui, context.user_input),
                "creation_selector_required", "creation_clarification", context,
            )
        if self._creation_ui_incomplete(creation_ui, cards):
            ui = {**creation_ui, "clarification": (cards or [creation_ui])[0]}
            return self._request_creation_input(
                intent, ui, self.creation_ui_reply(creation_ui, context.user_input),
                "creation_parameters_required", "creation_card", context,
            )
        return TurnInteractionResult(creation_ui=creation_ui)

    @staticmethod
    def _selector_needs_choice(cards: list[Mapping[str, Any]]) -> bool:
        selectors = [
            card for card in cards
            if card.get("type") == "ad_creation_selector"
        ]
        return bool(selectors) and not any(
            card.get("account_options") or card.get("template_options")
            for card in selectors
        )

    @staticmethod
    def _creation_ui_incomplete(
        creation_ui: Mapping[str, Any], cards: list[Mapping[str, Any]],
    ) -> bool:
        return bool(creation_ui.get("needs_input")) or any(
            card.get("ready") is False
            or (
                card.get("account_required")
                and not str(card.get("account_id") or "").strip()
            )
            for card in cards
        )

    def _prepare_blueprint_creation(
        self, intent: Any, routed: Mapping[str, list[Any]],
        creation_ui: Mapping[str, Any], context: TurnInteractionContext,
    ) -> TurnInteractionResult:
        cards = self._cards(creation_ui)
        if not cards:
            return TurnInteractionResult(creation_ui=creation_ui)
        if creation_ui.get("needs_input"):
            ui = {**creation_ui, "clarification": (cards or [creation_ui])[0]}
            return self._request_creation_input(
                intent, ui, self.creation_ui_reply(creation_ui, context.user_input),
                "creation_parameters_required", "creation_card", context,
            )
        account_id = (
            context.request_context.get("account_id")
            or getattr(context.session.ctx, "account_id", "")
            or ""
        )
        issues = self._creation_contract_preflight(
            intent, routed, context.session, str(account_id),
        )
        if issues:
            return self._block_creation_contract(intent, creation_ui, issues, context)
        return TurnInteractionResult(creation_ui=creation_ui)

    def _request_creation_input(
        self, intent: Any, ui: Mapping[str, Any], reply: str, reason: str,
        source: str, context: TurnInteractionContext,
    ) -> TurnInteractionResult:
        self.set_creation_draft(
            str(context.request.session_id or ""),
            {"intent": intent.to_dict(), "reason": reason},
        )
        return self._await_creation_input(intent, ui, reply, source, context)

    def _block_creation_contract(
        self, intent: Any, creation_ui: Mapping[str, Any], issues: list[Any],
        context: TurnInteractionContext,
    ) -> TurnInteractionResult:
        ui = {
            **creation_ui, "needs_input": True,
            "creation_validation": {"status": "blocked", "issues": issues},
        }
        reply = self._creation_contract_reply(ui, issues)
        context.state.update({
            "intent": intent, "calls": (), "session": context.session,
            "last_results": [], "tool_plan": {}, "execution_plan": {},
            "tool_selection": None, "response_source": "creation_validation",
            "needs_input": True, "ui": ui,
            "creation_validation": {"status": "blocked", "issues": issues},
            "workflow_id": None, "last_reply": reply,
        })
        self.set_creation_draft(
            str(context.request.session_id or ""),
            {"intent": intent.to_dict(), "reason": "creation_validation"},
        )
        return TurnInteractionResult(
            creation_ui=creation_ui,
            model_turn=ModelTurn(
                content=reply, stop_reason="awaiting_input",
                context_updates=dict(context.context_updates),
            ),
        )
    def prepare_action_clarification(
        self, intent: Any, routed: Mapping[str, list[Any]],
        context: TurnInteractionContext,
    ) -> ModelTurn | None:
        if (
            not routed
            or self.creation_card_builder.is_creation_intent(intent)
            or context.request_context.get("creation_blueprint_id")
        ):
            return None
        account_by_platform = self._resolve_action_accounts(
            intent, routed, context.request_context,
        )
        clarification = self.action_clarification_builder.build(
            intent, routed, self.input_builder, context.session.ctx,
            account_by_platform=account_by_platform,
        )
        if not clarification:
            return None
        return self._await_action_clarification(
            intent, routed, clarification, context,
        )

    def _resolve_action_accounts(
        self, intent: Any, routed: Mapping[str, list[Any]],
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        accounts = {}
        for platform, definitions in routed.items():
            has_write = any(
                getattr(definition, "is_write_tool", False)
                for definition in definitions
            )
            accounts[self._canonical_platform(platform)] = self.account_resolver.resolve(
                intent, platform, list(definitions),
                request_context.get("account_id"),
                allow_automatic_account=not has_write,
            )
        return accounts

    def _await_action_clarification(
        self, intent: Any, routed: Mapping[str, list[Any]],
        clarification: Mapping[str, Any], context: TurnInteractionContext,
    ) -> ModelTurn:
        ui = {
            "schema_version": "1.0", "needs_input": True,
            "cards": [], "clarification": clarification,
        }
        reply = self.action_clarification_reply(ui, context.user_input)
        payload, results = self._account_prompt(clarification, routed)
        if payload is not None:
            reply = payload["question"]
        self.set_action_draft(
            str(context.request.session_id or ""),
            {"intent": intent.to_dict(), "clarification": clarification},
        )
        context.state.update({
            "intent": intent, "calls": (), "session": context.session,
            "last_results": results, "tool_plan": {}, "execution_plan": {},
            "tool_selection": None, "ui": ui, "workflow_id": None,
            "response_source": "action_clarification", "needs_input": True,
            "needs_confirmation": bool(payload),
            "confirmation_payload": payload, "last_reply": reply,
        })
        return ModelTurn(
            content=reply, stop_reason="awaiting_input",
            context_updates=dict(context.context_updates),
        )

    @staticmethod
    def _account_prompt(
        clarification: Mapping[str, Any], routed: Mapping[str, list[Any]],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        fields = clarification.get("fields") or []
        account_fields = [
            item for item in fields
            if isinstance(item, Mapping)
            and str(item.get("path") or "") in {
                "account_id", "advertiser_id", "customer_id",
            }
        ]
        if not account_fields or len(account_fields) != len(fields):
            return None, []
        field = account_fields[0]
        platform = str(field.get("platform") or next(iter(routed), "target"))
        payload = {
            "type": "ask_account", "platform": platform,
            "question": f"请提供要操作的 {platform} 广告账户 ID。",
        }
        return payload, [{
            "tool": str(field.get("tool") or "account_scope"),
            "platform": platform, "success": False, "data": {},
            "error": "缺少账户ID", "needs_confirmation": True,
            "confirmation_payload": payload,
        }]
    @staticmethod
    def _cards(ui: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        cards = ui.get("cards")
        if not isinstance(cards, list):
            return []
        return [item for item in cards if isinstance(item, Mapping)]

    def _await_creation_input(
        self,
        intent: Any,
        ui: Mapping[str, Any],
        reply: str,
        source: str,
        context: TurnInteractionContext,
    ) -> TurnInteractionResult:
        context.state.update({
            "intent": intent,
            "calls": (),
            "session": context.session,
            "last_results": [],
            "tool_plan": {},
            "execution_plan": {},
            "tool_selection": None,
            "ui": dict(ui),
            "workflow_id": None,
            "response_source": source,
            "needs_input": True,
            "last_reply": reply,
        })
        return TurnInteractionResult(
            creation_ui=ui,
            model_turn=ModelTurn(
                content=reply,
                stop_reason="awaiting_input",
                context_updates=dict(context.context_updates),
            ),
        )

    @staticmethod
    def _block_creation_turn(
        state: dict[str, Any],
        intent: Any,
        reason: str,
        reply: str,
        *,
        error_type: str | None = None,
    ) -> ModelTurn:
        state.update({
            "intent": intent,
            "calls": (),
            "policy_errors": [reason],
            "last_results": [],
            "last_reply": f"❌ {reply}",
            "response_source": "policy",
            "ui": {},
        })
        if error_type:
            state["error_type"] = error_type
        return ModelTurn(content=state["last_reply"], stop_reason="policy_blocked")


__all__ = [
    "AdTurnInteractionServicesMixin",
    "TurnInteractionContext",
    "TurnInteractionResult",
]
