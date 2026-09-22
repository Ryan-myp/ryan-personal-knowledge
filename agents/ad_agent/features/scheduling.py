"""Generic scheduling control feature.

This feature owns only the schedule control plane.  It keeps an auditable,
durable conversational draft until the request has a concrete cadence, scope,
an instruction that maps to the current Tool Registry, and an explicit user
confirmation.  The scheduled instruction is later handed back to
AdvertisingComposition; this feature never calls a Provider.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from ..core.interfaces import ParsedIntent
from ..runtime.scheduler import CronExpression, next_run_at, validate_timezone


class SchedulingFeature:
    feature_name = "scheduling"
    INTENTS = frozenset({
        "schedule_create", "schedule_list", "schedule_pause",
        "schedule_resume", "schedule_delete", "schedule_run_now",
    })
    _CANCEL_RE = re.compile(r"^(?:取消|算了|不用了|不创建了|放弃|cancel|never mind)\s*[。.!！]*$", re.I)
    _CONFIRM_RE = re.compile(r"^(?:确认|确认创建|创建吧|就这样|可以创建|好的|确定|confirm|yes|ok)\s*[。.!！]*$", re.I)
    _ACTION_MARKERS = (
        "查询", "查看", "分析", "统计", "报表", "performance", "report", "insight",
        "拉取", "同步", "导出", "创建", "新建", "更新", "修改", "暂停", "恢复",
        "删除", "检查", "诊断", "获取", "list", "get", "create", "update", "pause",
        "resume", "delete", "fetch", "sync", "export", "analy",
    )
    _CRON_CAPTURE_RE = re.compile(
        r"(?:cron|表达式)\s*[:：=]?\s*(?P<expression>"
        r"[0-9*/,-]+(?:\s+[0-9*/,-]+){4})",
        re.I,
    )

    _INTENT_DESCRIPTORS = {
        "schedule_create": {
            "description": "创建并管理一个按周期重新交给 Agent 执行的任务",
            "priority": 200,
            "aliases": ["定时任务", "定时执行", "定期执行", "scheduled task", "schedule"],
        },
        "schedule_list": {
            "description": "查看当前租户可见的定时任务列表",
            "priority": 200,
            "aliases": ["定时任务列表", "查看定时任务", "list schedules"],
        },
        "schedule_pause": {
            "description": "暂停一个已存在的定时任务",
            "priority": 200,
            "aliases": ["暂停定时任务", "停用定时任务", "pause schedule"],
        },
        "schedule_resume": {
            "description": "恢复一个已暂停的定时任务",
            "priority": 200,
            "aliases": ["恢复定时任务", "启用定时任务", "resume schedule"],
        },
        "schedule_delete": {
            "description": "删除一个已存在的定时任务",
            "priority": 200,
            "aliases": ["删除定时任务", "移除定时任务", "delete schedule"],
        },
        "schedule_run_now": {
            "description": "立即触发一个已存在的定时任务",
            "priority": 200,
            "aliases": ["立即执行定时任务", "现在执行定时任务", "run schedule now"],
        },
    }

    def intent_descriptors(self) -> dict[str, dict[str, Any]]:
        return {
            intent: {**descriptor, "aliases": list(descriptor.get("aliases", []))}
            for intent, descriptor in self._INTENT_DESCRIPTORS.items()
        }

    def can_handle(self, intent: Any) -> bool:
        return str(getattr(intent, "intent_type", "") or "") in self.INTENTS

    def is_control_intent(self, intent: Any) -> bool:
        """Expose control-plane ownership without leaking intent names upward."""
        return self.can_handle(intent)

    def is_batch_intent(self, _intent: Any) -> bool:
        return False

    def handles_creation_preflight(self, _intent: Any) -> bool:
        return False

    @staticmethod
    def _schedule_id(intent: ParsedIntent) -> Optional[str]:
        if getattr(intent, "schedule_id", None):
            return str(intent.schedule_id)
        match = re.search(
            r"(?:任务|schedule)[_ -]?(?:id|编号)?\s*[:：=]?\s*([a-zA-Z0-9_-]{8,})",
            intent.raw_input, re.I,
        )
        return match.group(1) if match else None

    @classmethod
    def _has_explicit_schedule_time(cls, raw_input: str) -> bool:
        text = str(raw_input or "").lower()
        if cls._CRON_CAPTURE_RE.search(text):
            return True
        if re.search(r"(?:每小时|hourly|every hour)", text, re.I):
            return True
        if re.search(
            r"(?:每天|每日|daily)\s*(?:上午|下午|晚上)?\s*\d{1,2}\s*(?:(?::|点|时)\s*\d{1,2}|点半)?",
            text, re.I,
        ):
            return True
        if re.search(
            r"(?:每周|weekly)\s*[一二三四五六日天1-7]\s*(?:上午|下午|晚上)?\s*\d{1,2}",
            text, re.I,
        ):
            return True
        if re.search(
            r"(?:每月|monthly)\s*\d{1,2}(?:号|日)?\s*(?:上午|下午|晚上)?\s*\d{1,2}",
            text, re.I,
        ):
            return True
        return False

    @classmethod
    def _expression(cls, intent: ParsedIntent) -> Optional[str]:
        raw = str(getattr(intent, "raw_input", "") or "")
        if not cls._has_explicit_schedule_time(raw):
            # A model must not silently turn “每天” into a guessed 09:00.
            return None
        expression = getattr(intent, "schedule_expression", None)
        if expression:
            try:
                CronExpression(str(expression))
                return " ".join(str(expression).strip().split())
            except ValueError:
                pass
        match = re.search(
            cls._CRON_CAPTURE_RE,
            raw,
        )
        if match:
            return match.group("expression")
        text = raw.lower()
        if re.search(r"(?:每小时|hourly|every hour)", text, re.I):
            return "0 * * * *"
        daily = re.search(
            r"(?:每天|每日|daily)\s*(?:(上午|下午|晚上)\s*)?(\d{1,2})\s*"
            r"(?:(?::|点|时)\s*(\d{1,2})|点半)?",
            text, re.I,
        )
        if daily:
            hour, minute = cls._hour_minute(
                daily.group(2), daily.group(3), daily.group(1)
                or ("点半" if "点半" in daily.group(0) else None),
            )
            if hour is None or minute is None:
                return None
            return f"{minute} {hour} * * *"
        weekly = re.search(
            r"(?:每周|weekly)\s*([一二三四五六日天1-7])\s*"
            r"(?:(上午|下午|晚上)\s*)?(\d{1,2})\s*"
            r"(?:(?::|点|时)\s*(\d{1,2}))?",
            text, re.I,
        )
        if weekly:
            weekday_map = {"日": 0, "天": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
            weekday_token = weekly.group(1)
            weekday = weekday_map.get(weekday_token)
            if weekday is None:
                weekday = int(weekday_token) % 7
            hour, minute = cls._hour_minute(
                weekly.group(3), weekly.group(4), weekly.group(2)
            )
            if hour is None or minute is None:
                return None
            return f"{minute} {hour} * * {weekday}"
        monthly = re.search(
            r"(?:每月|monthly)\s*(\d{1,2})(?:\s*(?:号|日)|\s+)\s*"
            r"(?:(上午|下午|晚上)\s*)?(\d{1,2})\s*"
            r"(?:(?::|点|时)\s*(\d{1,2}))?",
            text, re.I,
        )
        if monthly:
            day = int(monthly.group(1))
            hour, minute = cls._hour_minute(
                monthly.group(3), monthly.group(4), monthly.group(2)
            )
            if day < 1 or day > 31 or hour is None or minute is None:
                return None
            return f"{minute} {hour} {day} * *"
        return None

    @staticmethod
    def _hour_minute(
        raw_hour: Optional[str], raw_minute: Optional[str], marker: Optional[str],
    ) -> tuple[Optional[int], Optional[int]]:
        """Convert an explicit user time without guessing missing schedules."""
        if raw_hour is None:
            return None, None
        hour = int(raw_hour)
        minute = 30 if marker == "点半" else int(raw_minute or 0)
        if minute > 59:
            return None, None
        if marker in {"下午", "晚上"}:
            if hour < 1 or hour > 12:
                return None, None
            if hour < 12:
                hour += 12
        elif marker == "上午":
            if hour < 1 or hour > 12:
                return None, None
            if hour == 12:
                hour = 0
        elif hour > 23:
            return None, None
        return hour, minute

    @staticmethod
    def _timezone(intent: ParsedIntent) -> tuple[str, bool]:
        value = str(getattr(intent, "schedule_timezone", None) or "").strip()
        if value:
            return validate_timezone(value), True
        raw = str(getattr(intent, "raw_input", "") or "")
        match = re.search(r"\b(?:timezone|tz|时区)\s*[:：=]?\s*([A-Za-z_+/.-]+)", raw, re.I)
        if match:
            return validate_timezone(match.group(1)), True
        if "北京时间" in raw or "中国时间" in raw:
            return "Asia/Shanghai", True
        return "Asia/Shanghai", False

    @classmethod
    def _prompt(cls, intent: ParsedIntent) -> str:
        explicit = str(getattr(intent, "schedule_prompt", None) or "").strip()
        if explicit and cls._is_meaningful_prompt(explicit):
            return explicit
        text = str(getattr(intent, "raw_input", "") or "").strip()
        text = re.sub(r"^(?:帮我|请|请帮我)\s*", "", text, flags=re.I)
        text = re.sub(
            r"^(?:创建|新增|设置|安排)(?:一个)?\s*定时任务\s*[，,：:]?\s*",
            "", text, flags=re.I,
        )
        text = re.sub(
            r"^(?:cron|表达式)\s*[:：=]?\s*[0-9*/,-]+(?:\s+[0-9*/,-]+){4}\s*[，,：:]?\s*",
            "", text, flags=re.I,
        )
        text = re.sub(
            r"^(?:每小时|hourly|每天|每日|daily)\s*(?:(?:上午|下午|晚上)?\s*\d{1,2}\s*(?:(?::|点|时)\s*\d{1,2}|点半)?\s*)?(?:定时)?(?:的)?\s*|^(?:每周[^，,。；;]*|每月[^，,。；;]*)\s*(?:定时)?(?:的)?\s*",
            "", text, flags=re.I,
        )
        text = re.sub(r"^[，,：:、\s]+", "", text)
        return text.strip() if cls._is_meaningful_prompt(text) else ""

    @classmethod
    def _is_meaningful_prompt(cls, prompt: str) -> bool:
        text = str(prompt or "").strip().lower()
        if len(text) < 4 or cls._CANCEL_RE.match(text) or cls._CONFIRM_RE.match(text):
            return False
        return any(marker in text for marker in cls._ACTION_MARKERS)

    @staticmethod
    def _merge_params(*values: Optional[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for value in values:
            if not isinstance(value, Mapping):
                continue
            for platform, params in value.items():
                if not isinstance(params, Mapping):
                    continue
                current = dict(merged.get(str(platform), {}) or {})
                current.update(dict(params))
                merged[str(platform)] = current
        return merged

    @staticmethod
    def _account_from_params(params: Mapping[str, Any]) -> Optional[str]:
        for values in params.values() if isinstance(params, Mapping) else ():
            if not isinstance(values, Mapping):
                continue
            for key in ("account_id", "advertiser_id", "customer_id"):
                if values.get(key) not in (None, ""):
                    return str(values[key])
        return None

    @staticmethod
    def _account_from_text(text: str) -> Optional[str]:
        match = re.search(
            r"(?:account|ad[_ -]?account|广告账户|账户)"
            r"(?:\s*(?:id|编号))?\s*[:：=]?\s*"
            r"((?:act[_-]?\d+|(?:customer|customers)[/_-]?\d+|\d+(?:-\d+)*))\b",
            str(text or ""), re.I,
        )
        if not match:
            return None
        return str(match.group(1))

    def adopt_pending_intent(self, services: Any, intent: ParsedIntent, *, session_id: str) -> ParsedIntent:
        """Treat concise follow-ups as answers to the durable schedule draft."""
        draft = services.scheduling.get_draft(session_id)
        if draft and str(getattr(intent, "intent_type", "") or "") not in self.INTENTS:
            intent.intent_type = "schedule_create"
        return intent

    def _summary(self, draft: Mapping[str, Any]) -> str:
        tool_source = draft.get("preflight") or {}
        tools = ", ".join(tool_source.get("tool_names") or []) or "待能力预检"
        platforms = ", ".join(draft.get("platforms") or []) or "待补充"
        account = str(draft.get("account_id") or "待补充")
        timezone_name = str(draft.get("timezone") or "Asia/Shanghai")
        cadence = str(draft.get("cron_expression") or "待补充")
        prompt = str(draft.get("prompt") or "待补充")
        return (
            "请确认定时任务：\n"
            f"- 指令：{prompt}\n"
            f"- 周期：{cadence}\n"
            f"- 时区：{timezone_name}\n"
            f"- 渠道：{platforms}\n"
            f"- 账户：{account}\n"
            f"- 匹配 Tool：{tools}\n"
            f"- 执行模式：dry-run（写操作到期只生成计划，仍需重新确认）\n"
            "回复“确认创建”才会保存为活跃定时任务；需要修改就直接补充信息。"
        )

    def _build_draft(
        self, services: Any, intent: ParsedIntent, *, existing: Optional[Mapping[str, Any]],
        session_id: str, account_id: Optional[str], platform_params: Optional[dict], principal: Any,
    ) -> dict[str, Any]:
        previous = dict(existing or {})
        expression = self._expression(intent) or previous.get("cron_expression")
        prompt = self._prompt(intent) or str(previous.get("prompt") or "").strip()
        timezone_invalid = False
        try:
            timezone_name, timezone_explicit = self._timezone(intent)
        except ValueError:
            timezone_name, timezone_explicit = "Asia/Shanghai", False
            timezone_invalid = True
        if not timezone_explicit:
            timezone_name = str(previous.get("timezone") or timezone_name)
        current_platforms = [str(item).strip() for item in (getattr(intent, "namespaces", []) or []) if str(item).strip()]
        platforms = list(dict.fromkeys(current_platforms or previous.get("platforms") or []))
        params = self._merge_params(previous.get("platform_params"), getattr(intent, "scoped_parameters", {}), platform_params)
        selected_account = str(
            account_id or previous.get("account_id")
            or self._account_from_params(params)
            or self._account_from_text(getattr(intent, "raw_input", ""))
            or ""
        ) or None
        try:
            normalized_timezone = validate_timezone(timezone_name)
        except ValueError:
            normalized_timezone = "Asia/Shanghai"
            timezone_invalid = True
        draft: dict[str, Any] = {
            "version": 1,
            "status": "awaiting_input",
            "name": str(getattr(intent, "schedule_name", None) or previous.get("name") or prompt[:40] or "Scheduled Agent task")[:120],
            "prompt": prompt,
            "cron_expression": expression,
            "timezone": normalized_timezone,
            "timezone_explicit": timezone_explicit or bool(previous.get("timezone_explicit")),
            "platforms": platforms,
            "platform_params": params,
            "account_id": selected_account,
            "session_id": session_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        missing: list[str] = []
        if not expression:
            missing.append("schedule_time")
        else:
            try:
                CronExpression(str(expression))
            except ValueError:
                draft["cron_expression"] = None
                missing.append("schedule_time")
        if timezone_invalid:
            missing.append("timezone")
        if not prompt:
            missing.append("instruction")
        if not platforms:
            missing.append("platform")
        if not missing:
            preflight = services.preflight_scheduled_prompt(
                prompt, session_id=session_id, platforms=platforms,
                account_id=selected_account, platform_params=params,
                permissions=getattr(principal, "permissions", None),
                account_scope=getattr(principal, "account_scope", None) or None,
            )
            draft["preflight"] = preflight
            if preflight.get("status") != "ready":
                missing.extend(str(item) for item in (preflight.get("missing") or []))
                draft["status"] = (
                    "unsupported"
                    if preflight.get("status") == "unsupported"
                    else "awaiting_input"
                )
            else:
                draft["status"] = "awaiting_confirmation"
        draft["missing"] = list(dict.fromkeys(missing))
        return draft

    def handle_turn(
        self, services: Any, intent: ParsedIntent, *, session_id: str,
        user_id: str, tenant_id: str, account_id: Optional[str],
        platform_params: Optional[dict], principal: Any,
    ) -> dict[str, Any]:
        intent_type = str(intent.intent_type)
        if intent_type == "schedule_list":
            schedules = services.scheduling.list(user_id=user_id, tenant_id=tenant_id, limit=100)
            return {"success": True, "schedules": schedules, "reply": f"当前共有 {len(schedules)} 个定时任务。"}
        schedule_id = self._schedule_id(intent)
        if intent_type in {"schedule_pause", "schedule_resume", "schedule_delete", "schedule_run_now"} and not schedule_id:
            return {"success": False, "needs_input": True, "reply": "请提供要操作的定时任务 ID。"}
        if intent_type == "schedule_pause":
            schedule = services.scheduling.pause(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": bool(schedule), "schedule": schedule, "reply": "定时任务已暂停。" if schedule else "未找到该定时任务。"}
        if intent_type == "schedule_resume":
            schedule = services.scheduling.resume(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": bool(schedule), "schedule": schedule, "reply": "定时任务已恢复。" if schedule else "未找到该定时任务。"}
        if intent_type == "schedule_delete":
            deleted = services.scheduling.delete(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": deleted, "reply": "定时任务已删除。" if deleted else "未找到该定时任务。"}
        if intent_type == "schedule_run_now":
            result = services.scheduling.run_now(schedule_id, user_id=user_id, tenant_id=tenant_id)
            return {"success": bool(result), "task": result, "reply": "已提交立即执行。" if result else "未找到该定时任务。"}

        existing = services.scheduling.get_draft(session_id)
        raw = str(getattr(intent, "raw_input", "") or "").strip()
        if existing and self._CANCEL_RE.match(raw):
            services.scheduling.set_draft(session_id, None)
            return {"success": True, "reply": "已取消本次定时任务创建，草稿已清除。", "draft_cleared": True}
        if existing and existing.get("status") == "awaiting_confirmation" and self._CONFIRM_RE.match(raw):
            if (existing.get("preflight") or {}).get("status") != "ready" or existing.get("missing"):
                return {"success": False, "needs_input": True, "reply": "当前草稿尚未通过能力预检，请先补充缺失信息。", "draft": existing}
            try:
                schedule = services.scheduling.create(
                    name=str(existing.get("name") or existing.get("prompt") or "Scheduled Agent task"),
                    prompt=str(existing["prompt"]), cron_expression=str(existing["cron_expression"]),
                    timezone=str(existing.get("timezone") or "Asia/Shanghai"),
                    payload=services.redact({
                        "user_input": str(existing["prompt"]),
                        "session_id": session_id,
                        "account_id": existing.get("account_id") or account_id,
                        "platform_params": existing.get("platform_params") or platform_params or {},
                        "execution_mode": "dry_run",
                        "confirmed": False,
                        "confirmation_payload": None,
                    }),
                    metadata=services.redact({
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "principal": (
                            principal.to_safe_dict()
                            if principal is not None else None
                        ),
                        "account_id_present": bool(
                            existing.get("account_id") or account_id
                        ),
                        "execution_mode": "dry_run",
                        "created_via": "runtime",
                    }),
                )
            except Exception:
                # Keep the draft for a retry; Runtime will redact the error.
                raise
            services.scheduling.set_draft(session_id, None)
            return {
                "success": True, "schedule": schedule, "draft_cleared": True,
                "reply": f"定时任务已创建，将于 {schedule.get('next_run_at')} 首次执行。",
            }

        draft = self._build_draft(
            services, intent, existing=existing, session_id=session_id,
            account_id=account_id, platform_params=platform_params, principal=principal,
        )
        services.scheduling.set_draft(session_id, draft)
        if draft.get("status") == "awaiting_confirmation":
            return {
                "success": False, "needs_input": True, "confirmation_required": True,
                "reply": self._summary(draft), "draft": draft,
            }
        missing_labels = {
            "schedule_time": "明确执行时间（例如每天 09:00）",
            "timezone": "合法的 IANA 时区（例如 Asia/Shanghai）",
            "instruction": "到期后要执行的具体业务指令",
            "platform": "执行渠道",
            "account": "广告账户",
            "action": "具体业务动作",
        }
        missing = []
        for item in draft.get("missing", []):
            if str(item).startswith("parameter:"):
                missing.append("补充参数 " + str(item).split(":", 1)[1])
            else:
                missing.append(missing_labels.get(item, item))
        preflight = draft.get("preflight") or {}
        reason = str(preflight.get("reason") or "")
        reply = "请补充以下信息：" + "、".join(missing or ["定时任务信息"])
        if reason:
            reply += f"\n能力预检：{reason}"
        return {"success": False, "needs_input": True, "reply": reply, "draft": draft}


__all__ = ["SchedulingFeature"]
