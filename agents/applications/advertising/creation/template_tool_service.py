"""Authorized local template catalog and preview services for conversational Tools."""

import copy
import logging
from typing import Any, Mapping

from agents.agent_harness.core.interfaces import ParsedIntent, ToolResult
from agents.applications.advertising.persistence.errors import PersistenceError
from .templates import CreationTemplateError

logger = logging.getLogger(__name__)


def pending_template_input_tool(runtime: Any, request: Any, tools: Any) -> Any:
    """Keep incomplete template edits on the registered, read-only draft Tool."""
    context = request.context if isinstance(request.context, Mapping) else {}
    template_id = context.get("creation_template_id")
    if not template_id or context.get("confirmed"):
        return None
    principal = getattr(request, "principal", None)
    scope = getattr(principal, "account_scope", None)
    manager = runtime._creation_template_manager_for_request(scope)
    template = manager.get(
        str(request.tenant_id or "default"), str(request.user_id or "anonymous"),
        str(template_id), account_id=context.get("account_id"), account_scope=scope,
    )
    if not template:
        return None
    provider = str(template.get("provider") or "")
    required = template.get("required_input_fields") or []
    if not required:
        return None
    intent = ParsedIntent(
        "create_campaign", request.user_input, [provider],
        scoped_parameters=dict(context.get("platform_params") or {}),
    )
    applied = runtime.apply_creation_template_to_intent(
        intent, str(template_id), account_id=context.get("account_id"),
        account_scope=scope, tenant_id=str(request.tenant_id or "default"),
        user_id=str(request.user_id or "anonymous"),
    )
    values = applied.scoped_parameters.get(provider, {})
    missing = [
        path for path in required
        if runtime._creation_path_value(values, path)[1] in (None, "", [])
    ]
    if not missing:
        return None
    candidates = [
        tool for tool in tools
        if getattr(tool, "resource_type", "") == "creation_template"
        and getattr(tool, "action", "") == "get"
        and getattr(tool, "is_read_tool", False)
        and runtime._canonical_platform(tool.namespace)
        == runtime._canonical_platform(provider)
    ]
    if len(candidates) != 1:
        return None
    if isinstance(request.context, dict):
        request.context["_agent_template_input_fields"] = missing
        request.context["_agent_template_preview_tool"] = candidates[0].name
        request.context["_agent_tool_choice_required"] = True
    return candidates[0]


class CreationTemplateToolService:
    def __init__(self, runtime: Any, namespace: str) -> None:
        self.runtime = runtime
        self.namespace = namespace

    def _request(self, context: Any, arguments: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
        scope = context.metadata.get("account_scope")
        manager = self.runtime._creation_template_manager_for_request(scope)
        account = arguments.get("account_id") or getattr(context, "account_id", None)
        return manager, {
            "tenant_id": str(context.metadata.get("tenant_id") or "default"),
            "user_id": str(context.user_id),
            "account_id": str(account) if account else None,
            "account_scope": scope,
        }

    def list_templates(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            manager, request = self._request(context, arguments)
            rows = manager.list(
                **request, provider=self.namespace, status="active",
                query=arguments.get("query"), limit=arguments.get("limit", 20),
            )
        except (CreationTemplateError, PersistenceError) as error:
            logger.warning("Template catalog unavailable (%s)", type(error).__name__)
            return ToolResult.error("模板目录暂不可用，请稍后重试。")
        templates = []
        for row in rows:
            summary = {
                key: row[key] for key in (
                    "template_id", "catalog_key", "name", "description", "provider",
                    "account_id", "blueprint_id", "blueprint_version", "ad_format",
                    "source", "verification_status", "verification", "verified_scope",
                    "live_create_supported", "live_create_block_reason",
                    "required_inputs", "required_input_fields",
                ) if key in row
            }
            summary["prefilled_fields"] = list(row.get("values") or {})
            templates.append(summary)
        return ToolResult.ok({
            "templates": templates, "provider": self.namespace,
            "account_id": request["account_id"], "data_status": "local",
            "external_effects": False,
        })

    def get_template(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            return self._preview(context, arguments)
        except CreationTemplateError as error:
            return ToolResult.error(str(error))
        except PersistenceError as error:
            logger.warning("Template preview unavailable (%s)", type(error).__name__)
            return ToolResult.error("模板存储暂不可用，请稍后重试。")

    def _preview(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        manager, request = self._request(context, arguments)
        template_id = str(arguments["template_id"])
        template = manager.get(template_id=template_id, **request)
        if (
            not template or template.get("status") != "active"
            or template.get("provider") != self.namespace
        ):
            raise CreationTemplateError("模板不存在、已停用或不在当前账户授权范围内。")
        values = manager.validate_overrides(template, arguments.get("values") or {})
        account = request["account_id"] or template.get("account_id")
        draft_values = self._draft_values(context, template, values)
        intent = ParsedIntent(
            "create_campaign", "预览已选择的广告创建模板", [self.namespace],
            scoped_parameters={self.namespace: draft_values},
        )
        applied = self.runtime.apply_creation_template_to_intent(
            intent, template_id, **{**request, "account_id": account},
        )
        ui = self.runtime.build_creation_ui(
            applied, **{**request, "account_id": account},
        )
        cards = ui.get("cards") or []
        if not cards:
            raise CreationTemplateError("模板依赖的创建蓝图不可用，请重新选择模板。")
        return ToolResult(
            success=True,
            data={
                "template": template, "overrides": values, "data_status": "local",
                "external_effects": False,
            },
            needs_input=True,
            interaction={
                "type": "ad_creation_form",
                "prompt": "已加载所选模板，请确认草稿参数；尚未创建广告。",
                "payload": cards[0],
            },
        )

    def _draft_values(
        self, context: Any, template: Mapping[str, Any], overrides: Mapping[str, Any],
    ) -> dict[str, Any]:
        previous = context.metadata.get("creation_request") or {}
        params = previous.get("platform_params") or {}
        values: dict[str, Any] = {}
        if previous.get("creation_template_id") == template.get("template_id"):
            values = copy.deepcopy(params.get(self.namespace) or {})
        blueprint = self.runtime.creation_blueprints.get(
            str(template["blueprint_id"]), str(template["blueprint_version"]),
        )
        blueprint = self.runtime.creation_card_builder.expand_blueprint(blueprint)
        fields = {str(field["path"]): field for field in blueprint.fields}
        for path, value in overrides.items():
            values[path] = copy.deepcopy(value)
            self.runtime._set_creation_path(values, path, value)
            tool_name, schema_path = str(fields[path]["tool_ref"]).split(".", 1)
            target = values.setdefault(tool_name, {})
            self.runtime._set_creation_path(target, schema_path, value)
        return values
