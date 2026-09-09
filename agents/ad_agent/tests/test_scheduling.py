from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timezone

from agents.ad_agent.domain.ad.auth import RequestPrincipal
from agents.ad_agent.core.interfaces import (
    ParsedIntent, RiskLevel, ToolDefinition, ToolEffect, ToolHandler, ToolResult, ToolSchema,
)
from agents.ad_agent.features.scheduling import SchedulingFeature
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.persistence.models import ScheduledTaskRecord
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.runtime.scheduler import CronExpression, CronExpressionError, next_run_at


class _NoopReportHandler(ToolHandler):
    def execute(self, _ctx, _input_data):
        return ToolResult.ok({"rows": []})


def test_cron_and_timezone_are_bounded_and_deterministic():
    cron = CronExpression("*/15 9-10 * * 1-5")
    assert cron.matches(datetime(2026, 1, 5, 9, 15))
    assert not cron.matches(datetime(2026, 1, 4, 9, 15))
    assert next_run_at("0 9 * * *", "Asia/Shanghai", datetime(2026, 1, 1, tzinfo=timezone.utc)).startswith("2026-01-01T01:00:00")
    try:
        CronExpression("* * *")
    except CronExpressionError:
        pass
    else:
        raise AssertionError("invalid cron expression was accepted")


def test_schedule_time_parser_handles_weekly_monthly_and_rejects_ambiguous_cron():
    assert SchedulingFeature._expression(
        ParsedIntent("schedule_create", "每周一下午 9:30 分析 campaign", ["google"])
    ) == "30 21 * * 1"
    assert SchedulingFeature._expression(
        ParsedIntent("schedule_create", "每月 15 号晚上 8 点分析 campaign", ["google"])
    ) == "0 20 15 * *"
    assert SchedulingFeature._expression(
        ParsedIntent("schedule_create", "每天分析 campaign", ["google"])
    ) is None
    # The scheduler intentionally supports five-field cron only; accepting a
    # Quartz '?' here would create a task that the durable scheduler cannot run.
    assert SchedulingFeature._expression(
        ParsedIntent("schedule_create", "cron: 0 9 * * ? 分析 campaign", ["google"])
    ) is None


def test_account_extraction_does_not_turn_business_words_into_account_ids():
    assert SchedulingFeature._account_from_text("account performance") is None
    assert SchedulingFeature._account_from_text("account 123") == "123"
    assert SchedulingFeature._account_from_text("Meta account act_123") == "act_123"


def test_schedule_occurrence_is_unique_and_aggregates_terminal_result():
    path = tempfile.mktemp(suffix=".db")
    store = AdAgentStore(path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        record = ScheduledTaskRecord(
            schedule_id="schedule-1", tenant_id="tenant-1", user_id="user-1",
            name="daily report", prompt="analyze campaign", cron_expression="* * * * *",
            next_run_at="2000-01-01T00:00:00+00:00", created_at=now, updated_at=now,
        )
        store.create_scheduled_task(record)
        first = store.claim_due_scheduled_tasks(now, "worker-a")
        assert len(first) == 1
        assert store.claim_due_scheduled_tasks(now, "worker-b") == []
        schedule, occurrence = first[0]
        assert store.attach_scheduled_task_run(occurrence.schedule_run_id, "task-1")
        assert store.advance_scheduled_task(schedule.schedule_id, schedule.next_run_at, "2099-01-01T00:00:00+00:00")
        assert store.update_scheduled_task_run(
            occurrence.schedule_run_id, "succeeded",
            finished_at=datetime.now(timezone.utc).isoformat(), result={"success": True},
        )
        snapshot = store.get_scheduled_task_metrics("tenant-1", "user-1")
        assert snapshot["tasks_by_status"] == {"active": 1}
        assert snapshot["runs_by_status"] == {"succeeded": 1}
        task = store.get_scheduled_task("schedule-1", "tenant-1", "user-1")
        assert task.success_count == 1 and task.run_count == 1
    finally:
        store.close()
        if os.path.exists(path):
            os.unlink(path)


def test_schedule_requires_capability_and_explicit_confirmation_before_persisting():
    path = tempfile.mktemp(suffix=".db")
    store = AdAgentStore(path)
    registry = SimpleToolRegistry()
    registry.register(
        ToolDefinition(
            name="google_campaign_report",
            skill="google-ads",
            namespace="google-ads",
            description="Read campaign performance report",
            input_schema=ToolSchema(
                required=["account_id"],
                properties={"account_id": {"type": "string"}},
            ),
            action="read",
            resource_type="report",
            intent_types=["download_report"],
            intent_aliases=["分析 campaign performance", "Google Ads 分析"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            required_permissions=["ads.read"],
        ),
        _NoopReportHandler(),
    )
    runtime = AgentRuntime(
        registry=registry, persistence_store=store, require_llm=False, offline_mode=True,
        enforce_account_scope=False,
    )
    try:
        runtime._refresh_parser_catalog()
        result = runtime.run(
            "帮我创建一个定时任务，每天 09:00 用 Google Ads 分析 account 123 下 campaign performance",
            user_id="user-1", tenant_id="tenant-1",
        )
        assert result["intent"]["intent_type"] == "schedule_create"
        assert result["needs_input"] is True
        assert result["results"][0]["needs_input"] is True
        assert result["results"][0]["draft"]["status"] == "awaiting_confirmation"
        assert "google_campaign_report" in result["results"][0]["draft"]["preflight"]["tool_names"]
        schedules = runtime.list_schedules(user_id="user-1", tenant_id="tenant-1")
        assert schedules == []

        confirmed = runtime.run(
            "确认创建", session_id=result["session_id"],
            user_id="user-1", tenant_id="tenant-1",
        )
        assert confirmed["success"] if "success" in confirmed else True
        schedules = runtime.list_schedules(user_id="user-1", tenant_id="tenant-1")
        assert len(schedules) == 1
        assert schedules[0]["payload"]["execution_mode"] == "dry_run"
        assert runtime.scheduler is not None
    finally:
        runtime.close(wait=True)
        store.close()
        if os.path.exists(path):
            os.unlink(path)


def test_schedule_does_not_guess_daily_time_or_create_without_a_provider():
    path = tempfile.mktemp(suffix=".db")
    store = AdAgentStore(path)
    runtime = AgentRuntime(
        persistence_store=store, require_llm=False, offline_mode=True,
        enforce_account_scope=False,
    )
    try:
        result = runtime.run(
            "帮我创建一个定时任务，每天分析 campaign performance",
            user_id="user-1", tenant_id="tenant-1",
        )
        assert result["needs_input"] is True
        draft = runtime.get_schedule_draft(result["session_id"])
        assert draft["cron_expression"] is None
        assert "schedule_time" in draft["missing"]
        assert runtime.list_schedules(user_id="user-1", tenant_id="tenant-1") == []
    finally:
        runtime.close(wait=True)
        store.close()
        if os.path.exists(path):
            os.unlink(path)


def test_schedule_preflight_checks_tool_required_parameters_before_confirmation():
    path = tempfile.mktemp(suffix=".db")
    store = AdAgentStore(path)
    registry = SimpleToolRegistry()
    registry.register(
        ToolDefinition(
            name="google_campaign_report_with_id",
            skill="google-ads",
            namespace="google-ads",
            description="Read one campaign performance report",
            input_schema=ToolSchema(
                required=["account_id", "campaign_id"],
                properties={
                    "account_id": {"type": "string"},
                    "campaign_id": {"type": "string"},
                },
            ),
            action="read",
            resource_type="report",
            intent_types=["download_report"],
            intent_aliases=["分析 campaign performance", "Google Ads 分析"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            required_permissions=["ads.read"],
        ),
        _NoopReportHandler(),
    )
    runtime = AgentRuntime(
        registry=registry, persistence_store=store, require_llm=False,
        offline_mode=True, enforce_account_scope=False,
    )
    try:
        runtime._refresh_parser_catalog()
        result = runtime.run(
            "帮我创建一个定时任务，每天 09:00 用 Google Ads 分析 account 123 下 campaign performance",
            user_id="user-1", tenant_id="tenant-1",
        )
        draft = runtime.get_schedule_draft(result["session_id"])
        assert draft["status"] == "awaiting_input"
        assert "parameter:campaign_id" in draft["missing"]
        assert "campaign_id" in draft["preflight"]["reason"]
        assert runtime.list_schedules(user_id="user-1", tenant_id="tenant-1") == []
    finally:
        runtime.close(wait=True)
        store.close()
        if os.path.exists(path):
            os.unlink(path)


def test_schedule_draft_is_restored_after_runtime_restart_and_skill_is_injected():
    path = tempfile.mktemp(suffix=".db")
    store = AdAgentStore(path)
    runtime = AgentRuntime(
        persistence_store=store, require_llm=False, offline_mode=True,
        enforce_account_scope=False,
    )
    try:
        first = runtime.run(
            "帮我创建一个定时任务，每天分析 campaign performance",
            user_id="user-1", tenant_id="tenant-1",
        )
        session_id = first["session_id"]
        assert "[skill guidance: scheduled-agent-task]" in runtime.tool_selector.build_context_for_input(
            "每天分析 campaign", runtime.registry.list_all()
        )["expert_knowledge"]
        runtime.close(wait=True)

        restarted = AgentRuntime(
            persistence_store=store, require_llm=False, offline_mode=True,
            enforce_account_scope=False,
        )
        try:
            follow_up = restarted.run(
                "Google Ads account 123", session_id=session_id,
                user_id="user-1", tenant_id="tenant-1",
            )
            draft = restarted.get_schedule_draft(session_id)
            assert follow_up["needs_input"] is True
            assert draft["prompt"] == "分析 campaign performance"
            assert draft["platforms"] == ["google-ads"]
            assert draft["account_id"] == "123"
            assert draft["cron_expression"] is None
        finally:
            restarted.close(wait=True)
    finally:
        store.close()
        if os.path.exists(path):
            os.unlink(path)
