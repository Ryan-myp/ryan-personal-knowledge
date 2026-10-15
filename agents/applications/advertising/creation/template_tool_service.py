"""Authorized local template catalog and preview services for conversational Tools."""

import logging
from typing import Any, Mapping

from agents.agent_harness.core.interfaces import ParsedIntent, ToolResult
from agents.applications.advertising.persistence.errors import PersistenceError
from .templates import CreationTemplateError

logger = logging.getLogger(__name__)


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
                    "source", "verification_status", "verified_scope",
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
        intent = ParsedIntent(
            "create_campaign", "预览已选择的广告创建模板", [self.namespace],
            scoped_parameters={self.namespace: values},
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
