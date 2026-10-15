"""Local, read-only creation-template Tools with application-supplied services."""

from typing import Any, Callable

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy, RiskLevel, ToolDefinition, ToolEffect, ToolSchema,
)


class _TemplateHandler:
    def __init__(self, operation: Callable[..., Any]) -> None:
        self.operation = operation

    def execute(self, context: Any, arguments: dict[str, Any]) -> Any:
        return self.operation(context, arguments)


def creation_template_tool_source(
    namespace: str,
    list_templates: Callable[..., Any],
    get_template: Callable[..., Any],
) -> StaticToolSource:
    """Publish a channel-scoped local catalog without requiring a Provider client."""
    prefix = namespace.replace("-", "_")
    account = {
        "type": "string", "minLength": 1, "maxLength": 200,
        "description": "Optional selected account; current authorization still applies.",
    }
    specs = (
        (
            "list_creation_templates", list_templates,
            "查询当前账户可用的内置/个人广告创建模板（本地模板库，不是已建 Campaign 列表）。"
            "创建广告时先查询这些模板；用户问“有模板吗”应使用本工具，不能改查 Campaign 或预算。"
            "返回模板 ID、已预填字段和剩余输入；没有外部广告写入。",
            {
                "account_id": account,
                "query": {"type": "string", "maxLength": 120, "description": "Optional template name or ad type, e.g. Shopping, App, PMax."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            [], ["有模板吗", "有没有模板", "查询模板", "可用模板", "内置模板", "广告模板"],
        ),
        (
            "get_creation_template", get_template,
            "读取已选择的广告创建模板并返回预填参数草稿卡片；不创建广告。"
            "用户选择某个模板时调用，template_id 必须来自模板查询结果。"
            "将对话中已确认的名称、日期、预算按模板的 required_input_fields 放入 values，"
            "不要重复索要已预填的 Merchant ID、App、素材等字段。values 仅允许蓝图声明的字段。",
            {
                "account_id": account,
                "template_id": {"type": "string", "minLength": 1, "maxLength": 240},
                "values": {
                    "type": "object", "additionalProperties": True,
                    "description": "Data-only overrides keyed by declared blueprint paths. Unknown or executable fields are rejected.",
                },
            },
            ["template_id"], ["使用模板", "选择模板", "查看模板", "模板详情", "预览模板"],
        ),
    )
    bindings = []
    for intent, operation, description, properties, required, aliases in specs:
        definition = ToolDefinition(
            name=f"{prefix}_{intent}", namespace=namespace, skill="campaign-management",
            description=description,
            input_schema=ToolSchema(properties=properties, required=required),
            action="list" if intent.startswith("list_") else "get",
            resource_type="creation_template", intent_types=[intent], intent_aliases=aliases,
            risk_level=RiskLevel.LOW, effect_class=ToolEffect.READ, replay_policy=ReplayPolicy.SAFE,
            traits=["read", "local", "creation_template", "catalog"],
            required_permissions=["ads.read"], scope_type="account",
            scope_fields=["account_id"], scope_required=False,
            max_output_bytes=128_000, contract_version="1.0.0",
            result_items_key="templates" if intent.startswith("list_") else "template",
            result_id_fields=["template_id"],
        )
        bindings.append(ToolBinding(definition, _TemplateHandler(operation)))
    return StaticToolSource(f"creation-templates:{namespace}", bindings)
