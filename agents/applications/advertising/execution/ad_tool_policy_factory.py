"""Compose advertising-specific account and write policy for generic Tools."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from agents.agent_harness import ToolCall, ToolCallContext
from agents.applications.advertising.creation.templates import CreationTemplateError
from agents.applications.advertising.persistence.errors import PersistenceError
from agents.applications.advertising.persistence.adapters import PersistenceIdempotencyStore
from agents.agent_platform.tools.policy import ToolExecutionPolicy
from .ad_tool_interaction import AdvertisingToolInteractionProvider

logger = logging.getLogger(__name__)


class AdvertisingToolPolicyFactory:
    """Bind advertising account rules to the shared Tool policy contract."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.interactions = AdvertisingToolInteractionProvider(runtime)

    def build(self, store: Any = None) -> ToolExecutionPolicy:
        runtime = self.runtime
        return ToolExecutionPolicy(
            permissions=frozenset(runtime._granted_permissions),
            allow_live_writes=bool(runtime.allow_live_writes),
            live_approved_tools=runtime._live_approved_tools,
            write_guard_configured=True,
            require_confirmation_for_writes=True,
            before_check=self.check_scope_and_confirmation,
            argument_resolver=self.interactions.resolve_tool_arguments,
            scope_resolver=self.resolve_scope,
            confirmation_builder=self.build_confirmation,
            interaction_builder=self.interactions.build,
            live_approved_tools_provider=lambda: runtime._live_approved_tools,
            require_audit=True,
            idempotency_store=(
                PersistenceIdempotencyStore(store) if store is not None else None
            ),
        )

    def resolve_scope(self, tool: Any, request: Any, arguments: Mapping[str, Any]) -> Any:
        request_context = request.context if isinstance(request.context, Mapping) else {}
        platform = self.runtime._canonical_platform(str(getattr(tool, "namespace", "") or ""))
        request_account, argument_account = self._accounts_for_call(
            tool, platform, arguments, request_context,
        )
        account = request_account or argument_account
        return {"namespace": platform, "account_id": str(account)} if account else None

    def check_scope_and_confirmation(
        self,
        tool: Any,
        request: Any,
        arguments: Mapping[str, Any],
    ) -> Optional[tuple[str, str]]:
        runtime = self.runtime
        protected = runtime.security.validate_input_redline(arguments)
        if protected:
            return (
                "protected_input",
                "请求包含禁止传入的凭证/账户配置字段："
                + ", ".join(protected),
            )
        platform = runtime._canonical_platform(
            str(getattr(tool, "namespace", "") or "")
        )
        is_live_write = (
            str(getattr(request, "execution_mode", "") or "").lower() == "live"
            and bool(getattr(tool, "is_write_tool", False))
        )
        if is_live_write and runtime.write_guard is None:
            return (
                "write_guard_missing",
                "live 写操作必须配置 WriteGuard；已拒绝执行",
            )
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        scope_error = self._account_scope_error(
            tool, request, arguments, platform, request_context,
        )
        if scope_error:
            return scope_error
        if str(getattr(tool, "action", "") or "").lower() == "create":
            blueprint_error = self._creation_blueprint_argument_error(
                tool, request, arguments, request_context, platform,
            )
            if blueprint_error:
                return blueprint_error
            input_error = self._creation_input_error(tool, request, arguments)
            if input_error:
                return input_error
        if is_live_write and request_context.get("confirmed"):
            return self._confirmed_write_error(
                tool, request, arguments, request_context,
            )
        return None

    def _account_scope_error(
        self,
        tool: Any,
        request: Any,
        arguments: Mapping[str, Any],
        platform: str,
        request_context: Mapping[str, Any],
    ) -> Optional[tuple[str, str]]:
        request_account, argument_account = self._accounts_for_call(
            tool, platform, arguments, request_context,
        )
        if (
            request_account not in (None, "")
            and argument_account not in (None, "")
            and str(request_account).strip() != str(argument_account).strip()
        ):
            return (
                "scope_mismatch",
                "Tool 参数账户与当前请求的可信账户范围不一致",
            )
        account = request_account or argument_account
        is_write = bool(getattr(tool, "is_write_tool", False))
        runtime = self.runtime
        scope_required = getattr(tool, "scope_required", None)
        requires_account = (
            is_write
            or scope_required is True
            or (runtime.enforce_account_scope and scope_required is None)
        )
        if not account and requires_account:
            if is_write:
                return (
                    "confirmation_required",
                    "请求缺少受控账户范围，请先提供账户并确认",
                )
            return "scope_required", "请求缺少受控账户范围"
        return self._account_authorization_error(
            request, platform, account, is_write,
        )

    def _accounts_for_call(
        self,
        tool: Any,
        platform: str,
        arguments: Mapping[str, Any],
        request_context: Mapping[str, Any],
    ) -> tuple[Any, Any]:
        runtime = self.runtime
        scoped_account = self._scoped_account(tool, platform, request_context)
        platform_params = request_context.get("platform_params")
        namespaces = (
            list(platform_params) if isinstance(platform_params, Mapping) and platform_params
            else request_context.get("_agent_tool_namespaces", ())
        )
        multiple_namespaces = len({
            runtime._canonical_platform(namespace)
            for namespace in (namespaces or ())
        }) > 1
        request_account = scoped_account or (
            None if multiple_namespaces else request_context.get("account_id")
        )
        fields = tuple(
            getattr(tool, "scope_fields", ()) or (
                "account_id", "ad_account_id", "advertiser_id", "customer_id",
            )
        )
        argument_account = next((
            arguments.get(field) for field in fields
            if arguments.get(field) not in (None, "")
        ), None)
        return request_account, argument_account

    def _account_authorization_error(
        self,
        request: Any,
        platform: str,
        account: Any,
        is_write: bool,
    ) -> Optional[tuple[str, str]]:
        if account in (None, ""):
            return None
        principal = getattr(request, "principal", None)
        account_scope = getattr(principal, "account_scope", None)
        runtime = self.runtime
        if account_scope is not None:
            allowed, message = runtime._validate_account_with_principal(
                platform, str(account), is_write, account_scope,
            )
        elif is_write or runtime.enforce_account_scope:
            allowed, message = runtime._validate_account_for_tool(
                platform, str(account), is_write,
            )
        else:
            return None
        return None if allowed else ("scope_denied", str(message))

    def _creation_blueprint_argument_error(
        self,
        tool: Any,
        request: Any,
        arguments: Mapping[str, Any],
        request_context: Mapping[str, Any],
        platform: str,
    ) -> Optional[tuple[str, str]]:
        blueprint_id, blueprint_version, error = self._creation_blueprint_reference(
            tool, request, arguments, request_context, platform,
        )
        if error:
            return "creation_input_required", error
        if not blueprint_id:
            return None

        blueprint = self.runtime.creation_blueprints.get(
            blueprint_id, blueprint_version or None,
        )
        card_builder = getattr(self.runtime, "creation_card_builder", None)
        expand_blueprint = getattr(card_builder, "expand_blueprint", None)
        if blueprint is not None and callable(expand_blueprint):
            # The creation card exposes safe Tool-schema fields in addition
            # to hand-authored fields; enforce ownership against that same set.
            blueprint = expand_blueprint(blueprint)
        blueprint_error = self._creation_blueprint_tool_error(
            blueprint, tool, platform,
        )
        if blueprint_error:
            return "creation_input_required", blueprint_error
        return self._unowned_creation_argument_error(
            blueprint, tool, arguments,
        )

    def _creation_blueprint_tool_error(
        self, blueprint: Any, tool: Any, platform: str,
    ) -> Optional[str]:
        if blueprint is None:
            return "所选广告模板引用的创建蓝图不可用，已拒绝执行"
        if (
            self.runtime._canonical_platform(blueprint.provider) != platform
            or str(getattr(tool, "name", "") or "") not in blueprint.tools
        ):
            return "当前工具不属于所选广告模板，已拒绝执行"
        if not self._blueprint_paths_for_tool(blueprint, tool):
            return "所选广告模板没有声明当前工具的可写字段，已拒绝执行"
        return None

    def _unowned_creation_argument_error(
        self,
        blueprint: Any,
        tool: Any,
        arguments: Mapping[str, Any],
    ) -> Optional[tuple[str, str]]:
        allowed_paths = self._blueprint_paths_for_tool(blueprint, tool)
        safe_fields = self._creation_safe_fields(tool)
        unowned = sorted({
            path
            for field, value in arguments.items()
            if field not in safe_fields
            for path in self._unowned_argument_paths(
                str(field), value, allowed_paths,
            )
        })
        if not unowned:
            return None
        detail = ", ".join(unowned[:8])
        return (
            "creation_input_required",
            f"所选广告模板未声明当前工具的字段，已拒绝执行：{detail}",
        )

    def _creation_safe_fields(self, tool: Any) -> set[str]:
        properties = getattr(
            getattr(tool, "input_schema", None), "properties", {},
        ) or {}
        fields = set(getattr(tool, "scope_fields", ()) or (
            "account_id", "ad_account_id", "advertiser_id", "customer_id",
        ))
        parent_field_resolver = getattr(
            self.runtime, "_parent_resource_id_field_for_tool", None,
        )
        parent_field = (
            parent_field_resolver(tool) if callable(parent_field_resolver) else None
        )
        if parent_field:
            fields.add(str(parent_field))
        fields.update(
            name for name in ("status", "operation_status")
            if name in properties
        )
        return fields

    def _creation_blueprint_reference(
        self,
        tool: Any,
        request: Any,
        arguments: Mapping[str, Any],
        request_context: Mapping[str, Any],
        platform: str,
    ) -> tuple[str, str, Optional[str]]:
        blueprint_id = str(
            request_context.get("creation_blueprint_id") or ""
        ).strip()
        blueprint_version = str(
            request_context.get("creation_blueprint_version") or ""
        ).strip()
        template_id = str(
            request_context.get("creation_template_id") or ""
        ).strip()
        if not blueprint_id and not template_id:
            return "", "", None

        if not template_id:
            return blueprint_id, blueprint_version, None
        return self._template_blueprint_reference(
            tool, request, arguments, request_context, platform,
        )

    def _template_blueprint_reference(
        self,
        tool: Any,
        request: Any,
        arguments: Mapping[str, Any],
        request_context: Mapping[str, Any],
        platform: str,
    ) -> tuple[str, str, Optional[str]]:
        template_id = str(
            request_context.get("creation_template_id") or ""
        ).strip()
        blueprint_id = str(
            request_context.get("creation_blueprint_id") or ""
        ).strip()
        blueprint_version = str(
            request_context.get("creation_blueprint_version") or ""
        ).strip()
        account = self._confirmation_account(tool, arguments, request_context)
        if not account:
            return "", "", "选择账户模板时必须先确认受控账户范围"
        template, error = self._active_creation_template(
            request, template_id, str(account),
        )
        if error:
            return "", "", error
        if not self._template_matches_request(
            template, platform, blueprint_id, blueprint_version,
        ):
            return "", "", "模板与当前创建蓝图或广告渠道不一致"
        return (
            str(template.get("blueprint_id") or "").strip(),
            str(template.get("blueprint_version") or "").strip(),
            None,
        )

    def _active_creation_template(
        self, request: Any, template_id: str, account_id: str,
    ) -> tuple[Optional[Mapping[str, Any]], Optional[str]]:
        principal = getattr(request, "principal", None)
        account_scope = getattr(principal, "account_scope", None)
        try:
            manager = self.runtime._creation_template_manager_for_request(
                account_scope,
            )
            template = manager.get(
                str(getattr(request, "tenant_id", "") or "default"),
                str(getattr(request, "user_id", "") or "anonymous"),
                template_id,
                account_id=account_id,
                account_scope=account_scope,
            )
        except CreationTemplateError:
            template = None
        except PersistenceError as exc:
            logger.warning(
                "Template policy lookup failed (%s)",
                type(exc).__name__,
            )
            return None, "模板存储暂不可用，已拒绝执行"
        if not template or template.get("status") != "active":
            return None, "模板不存在、已停用或不在当前账户授权范围内"
        return template, None

    def _template_matches_request(
        self,
        template: Mapping[str, Any],
        platform: str,
        blueprint_id: str,
        blueprint_version: str,
    ) -> bool:
        template_blueprint_id = str(
            template.get("blueprint_id") or ""
        ).strip()
        template_blueprint_version = str(
            template.get("blueprint_version") or ""
        ).strip()
        return not (
            self.runtime._canonical_platform(
                str(template.get("provider") or "")
            ) != platform
            or (blueprint_id and blueprint_id != template_blueprint_id)
            or (
                blueprint_version
                and blueprint_version != template_blueprint_version
            )
        )

    @staticmethod
    def _blueprint_paths_for_tool(
        blueprint: Any,
        tool: Any,
    ) -> set[tuple[str, ...]]:
        tool_name = str(getattr(tool, "name", "") or "")
        paths: set[tuple[str, ...]] = set()
        properties = getattr(
            getattr(tool, "input_schema", None), "properties", {},
        ) or {}
        for field in blueprint.fields:
            reference = str(field.get("tool_ref") or "")
            referenced_tool, separator, schema_path = reference.partition(".")
            if not separator or referenced_tool != tool_name:
                continue
            parts = tuple(part for part in schema_path.split(".") if part)
            if not parts:
                continue
            paths.add(parts)
            schema: Any = properties
            for part in parts:
                if not isinstance(schema, Mapping):
                    schema = {}
                    break
                schema = schema.get(part, {})
                if isinstance(schema, Mapping):
                    schema = schema.get("properties", schema)
            aliases = (
                schema.get("input_aliases", ())
                if isinstance(schema, Mapping) else ()
            )
            if isinstance(aliases, (list, tuple, set, frozenset)):
                for alias in aliases:
                    alias_name = str(alias).strip()
                    if alias_name:
                        paths.add((*parts[:-1], alias_name))
        return paths

    @staticmethod
    def _unowned_argument_paths(
        field: str,
        value: Any,
        allowed_paths: set[tuple[str, ...]],
    ) -> list[str]:
        def inspect(path: tuple[str, ...], item: Any) -> list[str]:
            matching = [
                allowed for allowed in allowed_paths
                if allowed[:len(path)] == path
            ]
            if not matching:
                return [".".join(path)]
            if path in allowed_paths:
                return []
            if not isinstance(item, Mapping):
                return [".".join(path)]
            return [
                invalid
                for key, child in item.items()
                for invalid in inspect((*path, str(key)), child)
            ]

        return inspect((field,), value)

    def _creation_input_error(
        self,
        tool: Any,
        request: Any,
        arguments: Mapping[str, Any],
    ) -> Optional[tuple[str, str]]:
        context = ToolCallContext(
            request=request,
            assistant_message=None,
            tool_call=ToolCall(
                id="creation-input-check",
                name=str(getattr(tool, "name", "") or ""),
                arguments=dict(arguments),
            ),
            state=None,
            tool_definition=tool,
        )
        if self.interactions.creation_input_required(context):
            return (
                "creation_input_required",
                "广告创建蓝图仍缺少必填字段，请先补充创建表单",
            )
        return None

    def _confirmed_write_error(
        self,
        tool: Any,
        request: Any,
        arguments: Mapping[str, Any],
        request_context: Mapping[str, Any],
    ) -> Optional[tuple[str, str]]:
        provided = request_context.get("confirmation_payload")
        if not isinstance(provided, Mapping):
            return (
                "confirmation_required",
                "confirmed=true 必须携带当前计划的 confirmation_payload",
            )
        context = ToolCallContext(
            request=request,
            assistant_message=None,
            tool_call=ToolCall(
                id="policy-confirmation",
                name=str(getattr(tool, "name", "") or ""),
                arguments=dict(arguments),
            ),
            state=None,
            tool_definition=tool,
        )
        runtime = self.runtime
        expected = self.build_confirmation(context, tool, arguments)
        if not runtime.security.confirmation_matches(provided, expected or {}):
            return (
                "confirmation_mismatch",
                "确认信息与当前写入计划不匹配，已拒绝执行",
            )
        valid, message = runtime.security.validate_confirmation_record(
            expected, provided,
        )
        return None if valid else ("confirmation_invalid", f"确认记录无效：{message}")

    def build_confirmation(
        self,
        context: Any,
        tool: Any,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        request = context.request
        request_context = (
            request.context if isinstance(request.context, Mapping) else {}
        )
        account = self._confirmation_account(tool, arguments, request_context)
        if account in (None, ""):
            return {
                "type": "ask_account",
                "platform": str(getattr(tool, "namespace", "") or ""),
                "question": "请提供要操作的广告账户 ID。",
            }
        related_tools = self._related_write_tools(tool)
        if self._is_chain_creation(tool, related_tools):
            return self._build_chain_confirmation(
                request, request_context, tool, arguments, account, related_tools,
            )
        return self._build_single_confirmation(
            request, request_context, tool, arguments, account,
        )

    def _confirmation_account(
        self,
        tool: Any,
        arguments: Mapping[str, Any],
        request_context: Mapping[str, Any],
    ) -> Any:
        runtime = self.runtime
        namespaces = request_context.get("_agent_intent_namespaces", ())
        if not namespaces:
            platform_params = request_context.get("platform_params")
            namespaces = (
                list(platform_params) if isinstance(platform_params, Mapping) else []
            )
        multiple_namespaces = len({
            runtime._canonical_platform(namespace)
            for namespace in (namespaces or ())
        }) > 1
        if not multiple_namespaces:
            account = request_context.get("account_id")
            if account not in (None, ""):
                return account
        fields = tuple(
            getattr(tool, "scope_fields", ()) or (
                "account_id", "ad_account_id", "advertiser_id", "customer_id",
            )
        )
        return next((
            arguments.get(field) for field in fields
            if arguments.get(field) not in (None, "")
        ), None)

    def _related_write_tools(self, tool: Any) -> list[Any]:
        runtime = self.runtime
        namespace = runtime._canonical_platform(
            str(getattr(tool, "namespace", "") or "")
        )
        intent_types = set(getattr(tool, "intent_types", ()) or ())
        return [
            candidate for candidate in runtime.registry.list_all()
            if (
                getattr(candidate, "is_write_tool", False)
                and runtime._canonical_platform(
                    str(getattr(candidate, "namespace", "") or "")
                ) == namespace
                and set(getattr(candidate, "intent_types", ()) or ()) & intent_types
            )
        ]

    @staticmethod
    def _is_chain_creation(tool: Any, related_tools: list[Any]) -> bool:
        return (
            getattr(tool, "action", "") == "create"
            and any(
                getattr(candidate, "parent_resource_type", None)
                for candidate in related_tools
            )
        )

    def _build_chain_confirmation(
        self,
        request: Any,
        request_context: Mapping[str, Any],
        tool: Any,
        arguments: Mapping[str, Any],
        account: Any,
        related_tools: list[Any],
    ) -> Mapping[str, Any]:
        incoming = request_context.get("confirmation_payload")
        if (
            request_context.get("confirmed")
            and isinstance(incoming, Mapping)
            and incoming.get("type") == "confirm_write_plan"
        ):
            return dict(incoming)
        runtime = self.runtime
        expected = runtime.security.confirmation_chain_plan(
            str(request.session_id or ""),
            str(request.user_id or "anonymous"),
            str(account),
            str(getattr(tool, "namespace", "") or ""),
            related_tools,
            dict(arguments),
            preview={"tools": [candidate.name for candidate in related_tools]},
        )
        return runtime.security.prepare_confirmation(
            expected,
            create=not bool(request_context.get("confirmed")),
        )

    def _build_single_confirmation(
        self,
        request: Any,
        request_context: Mapping[str, Any],
        tool: Any,
        arguments: Mapping[str, Any],
        account: Any,
    ) -> Mapping[str, Any]:
        runtime = self.runtime
        expected = runtime.security.confirmation_plan(
            str(request.session_id or ""),
            str(request.user_id or "anonymous"),
            str(account),
            tool,
            dict(arguments),
            preview={
                "tool": str(getattr(tool, "name", "") or ""),
                "input": dict(arguments),
            },
        )
        expected["type"] = "confirm_write"
        return runtime.security.prepare_confirmation(
            expected,
            create=not bool(request_context.get("confirmed")),
        )

    def _scoped_account(
        self,
        tool: Any,
        platform: str,
        request_context: Mapping[str, Any],
    ) -> Any:
        platform_params = request_context.get("platform_params")
        if not isinstance(platform_params, Mapping):
            return None
        for key, values in platform_params.items():
            if (
                self.runtime._resolve_platform_identifier(str(key))
                != self.runtime._resolve_platform_identifier(platform)
                or not isinstance(values, Mapping)
            ):
                continue
            for field in getattr(tool, "scope_fields", ()) or (
                "account_id", "ad_account_id", "advertiser_id", "customer_id",
            ):
                if values.get(field) not in (None, ""):
                    return values[field]
        return None



__all__ = ["AdvertisingToolPolicyFactory"]
