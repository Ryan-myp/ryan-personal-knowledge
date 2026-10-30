"""Project incomplete model Tool calls into advertising input interactions."""

from __future__ import annotations

from typing import Any, Mapping

from agents.agent_harness.core.interfaces import ParsedIntent
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.agent_harness.tool_execution import ToolExecutionCoordinator
from agents.agent_platform.tools.policy import ToolArgumentValidationError


class AdvertisingToolInteractionProvider:
    """Build application-owned UI payloads without routing or executing Tools."""

    _INPUT_REASONS = frozenset({
        "input_schema", "scope_required", "confirmation_required",
        "creation_input_required", "argument_resolution_failed",
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
            interaction = self._creation_interaction(context, definition)
            if reason == "argument_resolution_failed" and interaction is not None:
                interaction = dict(interaction)
                interaction["prompt"] = message
                card = dict(interaction["payload"])
                card["validation_error"] = message
                interaction["payload"] = card
            return interaction
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
        accounts = self.runtime._read_accounts_for_request(namespace, principal)
        options = [
            {"label": f"账户 {account}", "value": str(account)}
            for account in (accounts or ())
        ]
        prompt = (
            "请选择要查询的广告账户。"
            if options else "当前身份没有可用于此渠道的授权账户。"
        )
        if accounts is None:
            prompt = (
                "请提供要查询的账户 ID，或先查询渠道账户列表。"
                "查询范围由当前渠道凭证决定；不会自动切换为测试账户。"
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
        blueprint_id = metadata["creation_blueprint_id"]
        template_id = metadata["creation_template_id"]
        if not template_id:
            values.update(arguments)
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
        request_context = context.request.context
        selected_workflow = isinstance(request_context, Mapping) and (
            request_context.get("creation_blueprint_id")
            or request_context.get("creation_template_id")
        )
        platform_params = request_context.get("platform_params") if isinstance(request_context, Mapping) else None
        singleton_input = (
            not request_context.get("creation_template_id")
            and tuple(getattr(context.request, "tool_allowlist", None) or ()) == (definition.name,)
            and isinstance(platform_params, Mapping)
            and isinstance(platform_params.get(definition.namespace), Mapping)
            and isinstance(platform_params[definition.namespace].get(definition.name), Mapping)
        )
        if selected_workflow and singleton_input:
            return bool(validate_tool_input(
                definition.input_schema, dict(arguments),
                include_tool_requirements=True,
            ))
        if validate_tool_input(definition.input_schema, dict(arguments)):
            return False
        if not selected_workflow:
            provider_required = getattr(definition.input_schema, "requires", ()) or ()
            if any(arguments.get(field) in (None, "", []) for field in provider_required):
                return True
            return False
        return bool(self._creation_ui(context, definition).get("needs_input"))

    def resolve_tool_arguments(self, context: Any) -> Mapping[str, Any]:
        """Materialize trusted template/form values before the Harness policy gate."""
        definition = getattr(context, "tool_definition", None)
        original = dict(getattr(context.tool_call, "arguments", {}) or {})
        request = context.request
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        selected_workflow = bool(
            request_context.get("creation_blueprint_id")
            or request_context.get("creation_template_id")
        )
        platform_params = request_context.get("platform_params")
        explicit_tool_input = False
        if (
            not selected_workflow
            and tuple(getattr(request, "tool_allowlist", None) or ())
            == (definition.name,)
            and isinstance(platform_params, Mapping)
        ):
            namespace = self.runtime._canonical_platform(str(definition.namespace))
            explicit_tool_input = any(
                self.runtime._canonical_platform(str(key)) == namespace
                and isinstance(values, Mapping)
                and isinstance(values.get(definition.name), Mapping)
                for key, values in platform_params.items()
            )
        if not selected_workflow and not explicit_tool_input:
            return original
        if (
            str(getattr(definition, "action", "") or "").lower() != "create"
            and not explicit_tool_input
        ):
            return original

        intent, _tool_plan, _request_context = self._intent(
            context, definition, {} if explicit_tool_input else original,
        )
        input_builder = getattr(self.runtime, "input_builder", None)
        build = getattr(input_builder, "build", None)
        if not callable(build):
            return original
        namespace = str(getattr(definition, "namespace", "") or "")
        session = self.runtime._sessions.get(
            str(getattr(request, "session_id", "") or "")
        )
        session_context = getattr(session, "ctx", None)
        resolved = build(
            definition,
            intent,
            namespace,
            session_context,
        )
        validation_errors = [
            str(error)
            for key in ("_selection_errors", "_unknown_params")
            for error in (resolved or {}).get(key, ())
        ]
        if validation_errors:
            raise ToolArgumentValidationError(
                "创建参数校验失败：" + "；".join(validation_errors[:10])
            )
        properties = getattr(
            getattr(definition, "input_schema", None), "properties", {},
        ) or {}
        effective = {
            str(name): value
            for name, value in (resolved or {}).items()
            if name in properties and value is not None and value != ""
        }
        parent_field = str(
            getattr(definition, "parent_resource_id_field", "") or ""
        )
        if not parent_field:
            resolver = getattr(
                self.runtime, "_parent_resource_id_field_for_tool", None,
            )
            if callable(resolver):
                parent_field = str(resolver(definition) or "")
        reference_fields = [parent_field, *(
            getattr(definition, "related_resource_id_fields", ()) or ()
        )]
        bind_parent = bool(
            parent_field
            and request_context.get("creation_template_id")
            and str(getattr(request, "execution_mode", "")) == "live"
            and getattr(request, "run_id", "")
            and getattr(context, "state", None) is not None
            and request_context.get("account_id")
        )
        if bind_parent and parent_field in properties and parent_field not in effective:
            parent_id = self._created_parent_id(context, definition)
            if parent_id is not None:
                effective[parent_field] = parent_id
        for field in reference_fields:
            if not explicit_tool_input and field in properties and field in original:
                effective.setdefault(field, original[field])
        return effective

    def _created_parent_id(self, context: Any, definition: Any) -> Any:
        parent_type = str(getattr(definition, "parent_resource_type", "") or "")
        namespace = self.runtime._canonical_platform(definition.namespace)
        ids = {}
        for message in list(getattr(context.state, "messages", ()))[-128:]:
            if (
                getattr(message, "role", "") != "tool"
                or getattr(message, "run_id", "") != context.request.run_id
            ):
                continue
            payload = getattr(message, "content", None)
            if not isinstance(payload, Mapping) or payload.get("success") is not True:
                continue
            if payload.get("simulated"):
                continue
            try:
                producer, _handler = self.runtime.registry.get(message.name)
            except KeyError:
                continue
            if (
                producer.action != "create"
                or producer.resource_type != parent_type
                or self.runtime._canonical_platform(producer.namespace) != namespace
            ):
                continue
            identifier = ToolExecutionCoordinator._resource_id_from_output(
                payload.get("data"), producer.resource_id_field,
            )
            if identifier is not None:
                ids[str(identifier)] = identifier
        if len(ids) > 1:
            raise ValueError("创建父级结果不唯一，请明确选择正确父级")
        return next(iter(ids.values())) if ids else None

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
