"""Generic durable Agent scheduling Tool contract and executor."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)


class _ScheduleCreateExecutor:
    def __init__(self, create_schedule: Callable[..., Mapping[str, Any]]) -> None:
        self._create_schedule = create_schedule

    @staticmethod
    def _request_context(context: Any) -> tuple[Any, str]:
        request = getattr(context, "request", None)
        if request is not None:
            return (
                getattr(request, "principal", None),
                str(getattr(request, "session_id", "") or ""),
            )
        return (
            getattr(context, "principal", None),
            str(getattr(context, "session_id", "") or ""),
        )

    def execute(
        self,
        context: Any,
        arguments: dict[str, Any],
    ) -> ToolResult:
        principal, session_id = self._request_context(context)
        if not principal or not str(getattr(principal, "user_id", "") or "").strip():
            return ToolResult.error("创建定时任务需要可信的已认证用户身份")
        try:
            schedule = self._create_schedule(
                name=str(arguments.get("name") or ""),
                prompt=str(arguments.get("prompt") or ""),
                cron_expression=str(arguments.get("cron_expression") or ""),
                timezone=str(arguments.get("timezone") or "Asia/Shanghai"),
                session_id=session_id,
                principal=principal,
            )
        except (PermissionError, RuntimeError, TypeError, ValueError) as error:
            return ToolResult.error(f"定时任务未创建：{error}")
        if not isinstance(schedule, Mapping):
            return ToolResult.error("定时任务服务返回了无效结果")
        return ToolResult.ok({
            "schedule": dict(schedule),
            "data_status": "local",
        })


def scheduling_tool_source(
    create_schedule: Callable[..., Mapping[str, Any]],
    *,
    required_permission: str,
) -> StaticToolSource:
    """Publish the generic schedule-creation Tool through a trusted callback."""
    permission = str(required_permission or "").strip()
    if not callable(create_schedule):
        raise TypeError("create_schedule must be callable")
    if not permission:
        raise ValueError("required_permission is required")

    definition = ToolDefinition(
        name="agent_schedule_create",
        skill="agent-scheduling",
        namespace="agent_platform",
        description=(
            "仅在用户明确要求创建周期性 Agent 任务时调用。创建持久化调度记录，"
            "每次到期都重新进入同一 Agent Runtime；未来运行固定使用 dry_run，"
            "不会因为创建定时任务而开启广告渠道 live 写入。cron_expression 使用"
            "标准五字段表达式；时区默认为 Asia/Shanghai。若执行内容、频率或时区"
            "不明确，先向用户澄清，不要猜测。"
        ),
        input_schema=ToolSchema(
            properties={
                "name": {
                    "type": "string",
                    "maxLength": 120,
                    "description": "定时任务名称",
                },
                "prompt": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 12_000,
                    "description": "每次触发时交给 Agent 执行的指令",
                },
                "cron_expression": {
                    "type": "string",
                    "minLength": 9,
                    "maxLength": 128,
                    "description": "标准五字段 cron 表达式",
                },
                "timezone": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100,
                    "default": "Asia/Shanghai",
                    "description": "IANA 时区",
                },
            },
            required=["prompt", "cron_expression"],
            additional_properties=False,
        ),
        action="schedule",
        resource_type="scheduled_task",
        intent_types=["schedule_create"],
        intent_aliases=[
            "创建定时任务",
            "新建定时任务",
            "周期性任务",
            "每天执行",
            "每周执行",
            "recurring agent task",
            "create schedule",
        ],
        risk_level=RiskLevel.MEDIUM,
        effect_class=ToolEffect.INTERNAL_WRITE,
        replay_policy=ReplayPolicy.UNSAFE,
        traits=["agent_schedule", "durable", "internal_control_plane"],
        live_support=False,
        timeout_seconds=10,
        max_output_bytes=32_000,
        required_permissions=[permission],
        scope_required=False,
        result_id_fields=["schedule_id"],
        contract_version="1.0.0",
    )
    binding = ToolBinding(
        definition,
        _ScheduleCreateExecutor(create_schedule),
    )
    return StaticToolSource("agent-platform:scheduling", [binding])


__all__ = ["scheduling_tool_source"]
