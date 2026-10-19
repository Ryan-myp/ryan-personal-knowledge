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
from agents.agent_harness.core.security import redact_sensitive_text


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


class _ScheduleRunNowExecutor:
    def __init__(
        self,
        run_schedule_now: Callable[..., Mapping[str, Any] | None],
    ) -> None:
        self._run_schedule_now = run_schedule_now

    def execute(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        request = getattr(context, "request", None)
        principal = (
            getattr(request, "principal", None)
            if request is not None
            else getattr(context, "principal", None)
        )
        user_id = str(getattr(principal, "user_id", "") or "").strip()
        tenant_id = str(getattr(principal, "tenant_id", "") or "").strip()
        if not user_id or not tenant_id:
            return ToolResult.error("执行定时任务需要可信的已认证用户身份")

        schedule_id = arguments.get("schedule_id")
        if not isinstance(schedule_id, str) or not schedule_id.strip():
            return ToolResult.error("必须提供要执行的定时任务 ID")
        schedule_id = schedule_id.strip()
        if len(schedule_id) > 200:
            return ToolResult.error("定时任务 ID 超过长度限制")

        try:
            result = self._run_schedule_now(
                schedule_id=schedule_id,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        except PermissionError:
            return ToolResult.error("当前身份无权执行该定时任务")
        except (RuntimeError, TypeError, ValueError) as error:
            reason = redact_sensitive_text(str(error))[:500]
            return ToolResult.error(
                f"定时任务未能提交：{reason or type(error).__name__}"
            )

        if not isinstance(result, Mapping):
            return ToolResult.error("定时任务不存在或当前身份无权访问")
        task = result.get("task")
        run = result.get("run")
        if not isinstance(task, Mapping) or not isinstance(run, Mapping):
            return ToolResult.error("定时任务服务返回了无效的运行记录")

        return ToolResult.ok({
            "schedule_id": str(run.get("schedule_id") or schedule_id),
            "schedule_run_id": str(run.get("schedule_run_id") or ""),
            "task_id": str(run.get("task_id") or task.get("task_id") or ""),
            "status": str(run.get("status") or task.get("status") or "queued"),
            "created": bool(result.get("created", False)),
            "data_status": "local",
        })


def scheduling_tool_source(
    create_schedule: Callable[..., Mapping[str, Any]],
    *,
    required_permission: str,
    run_schedule_now: Callable[..., Mapping[str, Any] | None],
) -> StaticToolSource:
    """Publish generic schedule Tools through trusted application callbacks."""
    permission = str(required_permission or "").strip()
    if not callable(create_schedule):
        raise TypeError("create_schedule must be callable")
    if not callable(run_schedule_now):
        raise TypeError("run_schedule_now must be callable")
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
    run_definition = ToolDefinition(
        name="agent_schedule_run_now",
        skill="agent-scheduling",
        namespace="agent_platform",
        description=(
            "仅在用户明确要求立即执行一个已存在的定时任务时调用。此 Tool 只把"
            "该任务提交到持久化 Agent Task 队列，然后由同一个 Agent Runtime 执行；"
            "不会在当前对话中直接重放任务指令，也不会绕过权限、幂等和审计。"
            "必须使用对话上下文中明确的 schedule_id；若无法确定目标任务，先询问用户，"
            "不要猜测 ID，也不要改为创建任务或执行别的业务操作。调用成功代表已排队，"
            "不是任务已完成。"
        ),
        input_schema=ToolSchema(
            properties={
                "schedule_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200,
                    "description": "要立即触发的现有定时任务 ID",
                },
            },
            required=["schedule_id"],
            additional_properties=False,
        ),
        action="schedule_run_now",
        resource_type="scheduled_task",
        intent_types=["schedule_run_now"],
        intent_aliases=[
            "立即执行定时任务",
            "运行定时任务",
            "执行这个定时任务",
            "现在运行这个任务",
            "run scheduled task now",
            "run schedule now",
        ],
        risk_level=RiskLevel.MEDIUM,
        effect_class=ToolEffect.INTERNAL_WRITE,
        replay_policy=ReplayPolicy.UNSAFE,
        traits=["agent_schedule", "durable", "internal_control_plane"],
        live_support=False,
        timeout_seconds=10,
        max_output_bytes=8_000,
        required_permissions=[permission],
        scope_required=False,
        result_id_fields=["schedule_run_id", "task_id"],
        contract_version="1.0.0",
    )
    run_binding = ToolBinding(
        run_definition,
        _ScheduleRunNowExecutor(run_schedule_now),
    )
    return StaticToolSource(
        "agent-platform:scheduling",
        [binding, run_binding],
    )


__all__ = ["scheduling_tool_source"]
