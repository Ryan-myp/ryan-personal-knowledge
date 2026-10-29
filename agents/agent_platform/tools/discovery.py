"""Trusted local Tool discovery; discovery grants no execution authority."""

from functools import partial

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ToolDefinition, ToolEffect, ToolResult, ToolSchema, RiskLevel, ReplayPolicy,
)
from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.agent_harness.tool_discovery import DISCOVERY_TRAIT, active_tool_discovery
from .policy import required_tool_permissions


def _execute_discovery(definition, configured_permissions, is_available, _context, arguments):
    errors = validate_tool_input(definition.input_schema, arguments)
    if errors:
        return ToolResult.error("；".join(errors))
    if not arguments["query"].strip():
        return ToolResult.error("工具查找内容不能为空")
    state = active_tool_discovery.get()
    if state is None:
        return ToolResult.error("工具发现需要当前 Run 上下文")
    request = state.request
    principal_permissions = getattr(request.principal, "permissions", ()) or ()
    if isinstance(principal_permissions, str):
        principal_permissions = (principal_permissions,)
    granted = (
        frozenset(principal_permissions)
        if request.principal is not None else configured_permissions
    )
    if not set(definition.required_permissions) <= granted:
        return ToolResult.error("缺少工具发现权限")

    def permitted(tool):
        return (
            required_tool_permissions(tool, request.execution_mode or "dry_run") <= granted
            and (is_available is None or is_available(request, tool))
        )

    return ToolResult.ok(state.search(
        arguments["query"].strip(), namespace=arguments.get("namespace", ""),
        resource_type=arguments.get("resource_type", ""), effect=arguments.get("effect", "read"),
        limit=arguments.get("limit", 4), permitted=permitted,
    ))


def tool_discovery_source(
    *, required_permission: str, granted_permissions=(), is_available=None,
) -> StaticToolSource:
    if not required_permission.strip():
        raise ValueError("discovery requires an explicit permission")
    configured_permissions = frozenset(granted_permissions)
    definition = ToolDefinition(
        name="agent_discover_tools", namespace="agent_platform", skill="tool-discovery",
        description=(
            "查找并加载当前未附带的已注册 Tool；用于下一步缺少查询、分析或操作工具时。"
            "按动作和资源描述搜索，可用 namespace/resource_type 缩小范围；"
            "默认只查只读工具，写工具需显式 effect=write。仅检索本地能力目录，不搜索网页、"
            "不调用渠道 API、不执行找到的操作。成功后下次请求将附带对应 schema，继续原任务。"
        ),
        input_schema=ToolSchema(properties={
            "query": {"type": "string", "minLength": 1, "maxLength": 500},
            "namespace": {"type": "string", "maxLength": 100},
            "resource_type": {"type": "string", "maxLength": 100},
            "effect": {"type": "string", "enum": ["read", "write"], "default": "read"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 4, "default": 4},
        }, required=["query"], additional_properties=False),
        action="search", resource_type="tool_catalog", intent_types=["discover_tools"],
        # This local control action changes the Run's schema window. Cached
        # results cannot reproduce that effect after an earlier schema is evicted.
        risk_level=RiskLevel.LOW, effect_class=ToolEffect.READ, replay_policy=ReplayPolicy.UNSAFE,
        required_permissions=[required_permission], scope_required=False,
        traits=[DISCOVERY_TRAIT, "local", "catalog", "bounded_output"],
        timeout_seconds=5, max_output_bytes=16000, contract_version="1.1.0",
    )

    execute = partial(_execute_discovery, definition, configured_permissions, is_available)
    return StaticToolSource("agent-platform:tool-discovery", [ToolBinding(definition, execute)])
