"""Project incomplete model Tool calls into advertising input interactions."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness.core.interfaces import ParsedIntent
from agents.agent_harness.core.tool_registry import validate_tool_input


class AdvertisingToolInteractionProvider:
    """Build application-owned UI payloads without routing or executing Tools."""

    _INPUT_REASONS = frozenset({
        "input_schema", "scope_required", "confirmation_required",
        "creation_input_required",
    })

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def build(
        self,
        context: Any,
        reason: str,
        message: str,
    ) -> Mapping[str, Any] | None:
        if reason not in self._INPUT_REASONS:
            return None
        definition = getattr(context, "tool_definition", None)
        if definition is None:
            return None
        request_context = (
            context.request.context
            if isinstance(context.request.context, Mapping) else {}
        )
        if (
            reason == "confirmation_required"
            and str(context.request.execution_mode or "dry_run").lower() == "live"
        ):
            return None
        if reason == "confirmation_required" and self._account_id(
            request_context, definition, context.tool_call.arguments,
        ):
            return None
        if reason == "scope_required":
            return self._account_selection(context, definition)
        if str(getattr(definition, "action", "") or "").lower() == "create":
            return self._creation_interaction(context, definition)
        if reason in {"input_schema", "confirmation_required"}:
            return self._action_interaction(context, definition, message)
        return None

    def _account_selection(
        self,
        context: Any,
        definition: Any,
    ) -> Mapping[str, Any]:
        namespace = str(getattr(definition, "namespace", "") or "")
        principal = getattr(context.request, "principal", None)
        accounts = self.runtime._available_accounts_for_request(
            namespace,
            getattr(principal, "account_scope", None),
        )
        options = [
            {"label": f"账户 {account}", "value": str(account)}
            for account in accounts
        ]
        prompt = (
            "请选择要查询的广告账户。"
            if options else "当前身份没有可用于此渠道的授权账户。"
        )
        return {
            "type": "account_selection",
            "prompt": prompt,
            "payload": {
                "namespace": namespace,
                "tool": str(getattr(definition, "name", "") or ""),
                "account_options": options,
                "required": True,
            },
        }

    def _intent(
        self,
        context: Any,
        definition: Any,
        arguments: Mapping[str, Any],
    ) -> tuple[ParsedIntent, dict[str, list[Any]], dict[str, Any]]:
        request = context.request
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        namespace = str(getattr(definition, "namespace", "") or "")
        intent_types = getattr(definition, "intent_types", ()) or ()
        intent_type = next(
            (str(item) for item in intent_types if str(item).strip()),
            "tool_call",
        )
        metadata = {
            "creation_blueprint_id": str(
                request_context.get("creation_blueprint_id") or ""
            ),
            "creation_blueprint_version": str(
                request_context.get("creation_blueprint_version") or ""
            ),
            "creation_template_id": str(
                request_context.get("creation_template_id") or ""
            ),
        }
        values: dict[str, Any] = {}
        platform_params = request_context.get("platform_params")
        if isinstance(platform_params, Mapping):
            for raw_namespace, raw_values in platform_params.items():
                if (
                    self.runtime._canonical_platform(str(raw_namespace))
                    != self.runtime._canonical_platform(namespace)
                    or not isinstance(raw_values, Mapping)
                ):
                    continue
                values.update(raw_values)
                tool_values = raw_values.get(str(definition.name))
                if isinstance(tool_values, Mapping):
                    values.update(tool_values)
                break
        values.update(arguments)
        blueprint_id = metadata["creation_blueprint_id"]
        if blueprint_id:
            blueprint = self.runtime.creation_blueprints.get(
                blueprint_id,
                metadata["creation_blueprint_version"] or None,
            )
            if blueprint is not None and self.runtime._canonical_platform(
                blueprint.provider
            ) == self.runtime._canonical_platform(namespace):
                selector = blueprint.selector or {}
                dimension = str(selector.get("dimension") or "")
                selector_values = selector.get("values") or ()
                if dimension and dimension not in values and len(selector_values) == 1:
                    values[dimension] = selector_values[0]
        intent = ParsedIntent(
            intent_type,
            request.user_input,
            [namespace],
            scoped_parameters={namespace: values},
            metadata=metadata,
        )
        template_id = metadata["creation_template_id"]
        if template_id:
            principal = getattr(request, "principal", None)
            intent = self.runtime.apply_creation_template_to_intent(
                intent,
                template_id,
                account_id=self._account_id(request_context, definition, values),
                account_scope=getattr(principal, "account_scope", None),
                tenant_id=str(request.tenant_id or "default"),
                user_id=str(request.user_id or "anonymous"),
            )
        return intent, {namespace: [definition]}, request_context

    def _creation_interaction(
        self,
        context: Any,
        definition: Any,
    ) -> Mapping[str, Any] | None:
        request_context = context.request.context
        selected_workflow = isinstance(request_context, Mapping) and (
            request_context.get("creation_blueprint_id")
            or request_context.get("creation_template_id")
        )
        if not selected_workflow and getattr(definition, "resource_type", "") != "campaign":
            return self._action_interaction(context, definition, "请补齐工具必需参数。")
        ui = self._creation_ui(context, definition)
        cards = ui.get("cards") if isinstance(ui, Mapping) else None
        if not isinstance(cards, list) or not cards:
            return None
        return {
            "type": "ad_creation_form",
            "prompt": "请补充或确认创建参数。",
            "payload": cards[0],
        }

    def creation_input_required(self, context: Any) -> bool:
        """Gate incomplete creation calls before dry-run or live execution."""
        definition = getattr(context, "tool_definition", None)
        if str(getattr(definition, "action", "") or "").lower() != "create":
            return False
        arguments = getattr(context.tool_call, "arguments", {})
        if validate_tool_input(definition.input_schema, dict(arguments)):
            return False
        provider_required = getattr(definition.input_schema, "requires", ()) or ()
        if any(arguments.get(field) in (None, "", []) for field in provider_required):
            return True
        request_context = context.request.context
        selected_workflow = isinstance(request_context, Mapping) and (
            request_context.get("creation_blueprint_id")
            or request_context.get("creation_template_id")
        )
        if not selected_workflow:
            return False
        return bool(self._creation_ui(context, definition).get("needs_input"))

    def _creation_ui(
        self,
        context: Any,
        definition: Any,
    ) -> Mapping[str, Any]:
        arguments = context.tool_call.arguments
        intent, tool_plan, request_context = self._intent(
            context, definition, arguments,
        )
        principal = getattr(context.request, "principal", None)
        account_id = self._account_id(request_context, definition, arguments)
        ui = self.runtime.build_creation_ui(
            intent,
            tool_plan,
            account_scope=getattr(principal, "account_scope", None),
            tenant_id=str(context.request.tenant_id or "default"),
            user_id=str(context.request.user_id or "anonymous"),
            account_id=account_id,
        )
        return ui if isinstance(ui, Mapping) else {}

    def _action_interaction(
        self,
        context: Any,
        definition: Any,
        message: str,
    ) -> Mapping[str, Any] | None:
        arguments = context.tool_call.arguments
        intent, tool_plan, request_context = self._intent(
            context, definition, arguments,
        )
        session = self.runtime._sessions.get(
            str(context.request.session_id or "")
        )
        if session is None:
            return None
        namespace = str(getattr(definition, "namespace", "") or "")
        account = self._account_id(request_context, definition, arguments)
        clarification = self.runtime.action_clarification_builder.build(
            intent,
            tool_plan,
            self.runtime.input_builder,
            session.ctx,
            account_by_platform={namespace: account},
        )
        if not clarification:
            return {
                "type": "tool_input",
                "prompt": str(message or "请补充缺少的工具参数。"),
                "payload": {
                    "tool": str(getattr(definition, "name", "") or ""),
                    "values": dict(arguments),
                },
            }
        return {
            "type": str(clarification.get("kind") or "action_clarification"),
            "prompt": str(clarification.get("question") or message or "请补充参数。"),
            "payload": clarification,
        }

    @staticmethod
    def _account_id(
        request_context: Mapping[str, Any],
        definition: Any,
        arguments: Mapping[str, Any],
    ) -> str | None:
        scope_fields = getattr(definition, "scope_fields", ()) or (
            "account_id", "ad_account_id", "advertiser_id", "customer_id",
        )
        account = request_context.get("account_id")
        if account not in (None, ""):
            return str(account)
        return next(
            (
                str(arguments[field])
                for field in scope_fields
                if arguments.get(field) not in (None, "")
            ),
            None,
        )


__all__ = ["AdvertisingToolInteractionProvider"]
