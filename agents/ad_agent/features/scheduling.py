"""Generic scheduling control feature.

This feature owns only schedule lifecycle requests. The scheduled prompt is
later handed back to AgentRuntime, so Skills, Tools and provider Capabilities
remain the sole source of business execution.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from ..core.interfaces import ParsedIntent
from ..runtime.scheduler import CronExpression, CronExpressionError, next_run_at, validate_timezone


class SchedulingFeature:
    feature_name = "scheduling"
    INTENTS = frozenset({
        "schedule_create", "schedule_list", "schedule_pause",
        "schedule_resume", "schedule_delete", "schedule_run_now",
    })

    def can_handle(self, intent: Any) -> bool:
        return str(getattr(intent, "intent_type", "") or "") in self.INTENTS

    def is_batch_intent(self, _intent: Any) -> bool:
        return False

    def handles_creation_preflight(self, _intent: Any) -> bool:
        return False

    @staticmethod
    def _schedule_id(intent: ParsedIntent) -> Optional[str]:
        if getattr(intent, "schedule_id", None):
            return str(intent.schedule_id)
        match = re.search(r"(?:任务|schedule)[_ -]?(?:id|编号)?\s*[:：=]?\s*([a-zA-Z0-9_-]{8,})", intent.raw_input, re.I)
        return match.group(1) if match else None

    @staticmethod
    def _expression(intent: ParsedIntent) -> Optional[str]:
        expression = getattr(intent, "schedule_expression", None)
        if expression:
            return str(expression)
        match = re.search(r"(?:cron|表达式)\s*[:：=]?\s*([\d*/?,\-]+(?:\s+[\d*/?,\-]+){4})", intent.raw_input, re.I)
        if match:
            return match.group(1)
        text = intent.raw_input.lower()
        time_match = re.search(r"(?:每天|每日|daily)\s*(?:上午|下午|晚上)?\s*(\d{1,2})(?::|点)?(\d{2})?\s*(?:点|时)?", text, re.I)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            if any(marker in text for marker in ("下午", "晚上")) and hour < 12:
                hour += 12
            if minute > 59 or hour > 23:
                return None
            return f"{minute} {hour} * * *"
        if any(marker in text for marker in ("每小时", "hourly", "every hour")):
            return "0 * * * *"
        if any(marker in text for marker in ("每天", "每日", "daily")):
            return "0 9 * * *"
        return None

    @staticmethod
    def _prompt(intent: ParsedIntent) -> str:
        explicit = getattr(intent, "schedule_prompt", None)
        if explicit:
            return str(explicit).strip()
        text = intent.raw_input.strip()
        # Remove only the scheduling wrapper. The remaining natural language
        # is intentionally preserved for the next Agent turn.
        text = re.sub(r"^(帮我|请|请帮我|创建一个|新增一个)?\s*定时任务[，,：: ]*", "", text, flags=re.I)
        text = re.sub(r"^(每天|每日|每小时|每周|每月)[^，,。；;]*[，,：: ]*", "", text, flags=re.I)
        return text.strip() or intent.raw_input.strip()

    def handle_turn(
        self, runtime: Any, intent: ParsedIntent, *, session_id: str,
        user_id: str, tenant_id: str, account_id: Optional[str],
        platform_params: Optional[dict], principal: Any,
    ) -> dict[str, Any]:
        intent_type = str(intent.intent_type)
        if intent_type == "schedule_list":
            schedules = runtime.list_schedules(user_id=user_id, tenant_id=tenant_id, limit=100)
            return {
                "success": True, "schedules": schedules,
                "reply": f"当前共有 {len(schedules)} 个定时任务。",
            }
        schedule_id = self._schedule_id(intent)
        if intent_type in {"schedule_pause", "schedule_resume", "schedule_delete", "schedule_run_now"} and not schedule_id:
            return {"success": False, "reply": "请提供要操作的定时任务 ID。"}
        if intent_type == "schedule_pause":
            schedule = runtime.pause_schedule(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": bool(schedule), "schedule": schedule, "reply": "定时任务已暂停。" if schedule else "未找到该定时任务。"}
        if intent_type == "schedule_resume":
            schedule = runtime.resume_schedule(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": bool(schedule), "schedule": schedule, "reply": "定时任务已恢复。" if schedule else "未找到该定时任务。"}
        if intent_type == "schedule_delete":
            deleted = runtime.delete_schedule(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": deleted, "reply": "定时任务已删除。" if deleted else "未找到该定时任务。"}
        if intent_type == "schedule_run_now":
            result = runtime.run_schedule_now(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": bool(result), "task": result, "reply": "已提交立即执行。" if result else "未找到该定时任务。"}

        expression = self._expression(intent)
        if not expression:
            return {"success": False, "needs_input": True, "reply": "请补充执行时间，例如“每天 09:00”或五段 cron 表达式。"}
        timezone_name = validate_timezone(getattr(intent, "schedule_timezone", None) or "Asia/Shanghai")
        prompt = self._prompt(intent)
        if not prompt:
            return {"success": False, "needs_input": True, "reply": "请补充定时任务到期后要执行的具体指令。"}
        name = getattr(intent, "schedule_name", None) or prompt[:40]
        schedule = runtime.create_schedule(
            name=str(name), prompt=prompt, cron_expression=expression,
            timezone=timezone_name, session_id=session_id, account_id=account_id,
            platform_params=platform_params, principal=principal,
        )
        return {
            "success": True, "schedule": schedule,
            "reply": f"定时任务已创建，将于 {schedule.get('next_run_at')} 首次执行。",
        }


__all__ = ["SchedulingFeature"]
