from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timezone

from agents.ad_agent.core.auth import RequestPrincipal
from agents.ad_agent.persistence.models import ScheduledTaskRecord
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.runtime.scheduler import CronExpression, CronExpressionError, next_run_at


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


def test_chat_schedule_feature_creates_dry_run_task_and_runtime_starts_scheduler():
    path = tempfile.mktemp(suffix=".db")
    store = AdAgentStore(path)
    runtime = AgentRuntime(
        persistence_store=store, require_llm=False, offline_mode=True,
        enforce_account_scope=False,
    )
    try:
        result = runtime.run(
            "帮我创建一个定时任务，每天 09:00 分析 account 123 下 campaign performance",
            user_id="user-1", tenant_id="tenant-1",
        )
        assert result["intent"]["intent_type"] == "schedule_create"
        schedules = runtime.list_schedules(user_id="user-1", tenant_id="tenant-1")
        assert len(schedules) == 1
        assert schedules[0]["payload"]["execution_mode"] == "dry_run"
        assert runtime.scheduler is not None
    finally:
        runtime.close(wait=True)
        store.close()
        if os.path.exists(path):
            os.unlink(path)
