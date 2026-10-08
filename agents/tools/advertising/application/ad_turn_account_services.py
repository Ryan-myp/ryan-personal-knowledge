"""Account selection and write-scope decisions for advertising turns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from agents.agent_harness import ModelTurn


@dataclass(frozen=True)
class AccountScopeDecision:
    """Read-scope context updates or a prompt that must stop the turn."""

    context_updates: Mapping[str, Any] = field(default_factory=dict)
    model_turn: ModelTurn | None = None


class AdTurnAccountServices:
    """Resolve account context and enforce principal scope before Feature hooks."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def resolve_read_account_scope(
        self,
        *,
        intent: Any,
        routed: Mapping[str, list[Any]],
        request: Any,
        request_context: Mapping[str, Any],
        session: Any,
        state: dict[str, Any],
    ) -> AccountScopeDecision:
        context = getattr(request, "context", None)
        if not isinstance(context, dict) or context.get("account_id") not in (None, ""):
            return AccountScopeDecision()

        platforms = {
            self.owner._canonical_platform(platform)
            for platform in routed
        }
        if len(platforms) != 1:
            return AccountScopeDecision()
        platform = next(iter(platforms))
        definitions = next(
            (
                tools for namespace, tools in routed.items()
                if self.owner._canonical_platform(namespace) == platform
            ),
            [],
        )
        if not definitions or any(
            bool(getattr(tool, "is_write_tool", False))
            for tool in definitions
        ):
            return AccountScopeDecision()
        if self._has_scoped_account(intent, platform, definitions, request_context):
            return AccountScopeDecision()
        namespace = str(getattr(definitions[0], "namespace", platform) or platform)
        return self._choose_read_account(
            request,
            session,
            state,
            intent,
            namespace,
        )

    def _choose_read_account(
        self,
        request: Any,
        session: Any,
        state: dict[str, Any],
        intent: Any,
        namespace: str,
    ) -> AccountScopeDecision:
        accounts = self.owner._available_accounts_for_request(
            namespace,
            getattr(getattr(request, "principal", None), "account_scope", None),
        )
        if len(accounts) == 1:
            account_id = str(accounts[0])
            request.context["account_id"] = account_id
            session.ctx.account_id = account_id
            return AccountScopeDecision(context_updates={"account_id": account_id})
        if len(accounts) > 1:
            return AccountScopeDecision(model_turn=self._ask_for_account(
                state,
                intent,
                session,
                namespace,
            ))
        return AccountScopeDecision()

    def validate_write_account_scope(
        self,
        *,
        intent: Any,
        routed: Mapping[str, list[Any]],
        request: Any,
        request_context: Mapping[str, Any],
        state: dict[str, Any],
        context_updates: Mapping[str, Any],
    ) -> ModelTurn | None:
        principal_scope = getattr(
            getattr(request, "principal", None), "account_scope", None,
        )
        if principal_scope is None:
            return None
        validated: set[tuple[str, str]] = set()
        for namespace, definitions in routed.items():
            for definition in definitions:
                if not getattr(definition, "is_write_tool", False):
                    continue
                platform = self.owner._canonical_platform(
                    str(getattr(definition, "namespace", namespace) or namespace)
                )
                account_id = self.owner.account_resolver.resolve(
                    intent,
                    platform,
                    [definition],
                    request_context.get("account_id"),
                    allow_automatic_account=False,
                )
                if account_id in (None, ""):
                    continue
                key = (platform, str(account_id))
                if key in validated:
                    continue
                validated.add(key)
                allowed, message = self.owner._validate_account_with_principal(
                    platform,
                    key[1],
                    True,
                    principal_scope,
                )
                if not allowed:
                    return self._block_write_scope(
                        state,
                        intent,
                        message,
                        context_updates,
                    )
        return None

    def _has_scoped_account(
        self,
        intent: Any,
        platform: str,
        definitions: list[Any],
        request_context: Mapping[str, Any],
    ) -> bool:
        scoped = self.owner.account_resolver.resolve(
            intent,
            platform,
            definitions,
            request_context.get("account_id"),
            allow_automatic_account=False,
        )
        return scoped not in (None, "")

    @staticmethod
    def _ask_for_account(
        state: dict[str, Any],
        intent: Any,
        session: Any,
        platform: str,
    ) -> ModelTurn:
        question = "请提供要操作的广告账户 ID。"
        payload = {
            "type": "ask_account",
            "platform": platform,
            "question": question,
        }
        state.update({
            "intent": intent,
            "calls": (),
            "session": session,
            "last_results": [{
                "success": False,
                "data": {},
                "needs_confirmation": True,
                "confirmation_payload": payload,
            }],
            "last_reply": question,
            "needs_input": True,
            "needs_confirmation": True,
            "confirmation_payload": payload,
            "response_source": "account_scope",
            "ui": {},
        })
        return ModelTurn(content=question, stop_reason="awaiting_input")

    @staticmethod
    def _block_write_scope(
        state: dict[str, Any],
        intent: Any,
        reason: str,
        context_updates: Mapping[str, Any],
    ) -> ModelTurn:
        reply = f"❌ {reason}"
        state.update({
            "intent": intent,
            "calls": (),
            "policy_errors": [reason],
            "last_results": [],
            "last_reply": reply,
            "response_source": "policy",
            "ui": {},
        })
        return ModelTurn(
            content=reply,
            stop_reason="policy_blocked",
            context_updates=dict(context_updates),
        )


__all__ = ["AccountScopeDecision", "AdTurnAccountServices"]
