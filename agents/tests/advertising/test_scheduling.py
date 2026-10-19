from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

from agents.agent_harness import ModelTurn, ToolCall
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.persistence.models import ScheduledTaskRecord
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.agent_platform.infrastructure.durable import (
    CronExpression,
    CronExpressionError,
    next_run_at,
)


def test_cron_and_timezone_are_bounded_and_deterministic():
    cron = CronExpression("*/15 9-10 * * 1-5")
    assert cron.matches(datetime(2026, 1, 5, 9, 15))
    assert not cron.matches(datetime(2026, 1, 4, 9, 15))
    assert next_run_at(
        "0 9 * * *", "Asia/Shanghai",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    ).startswith("2026-01-01T01:00:00")
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
        assert store.advance_scheduled_task(
            schedule.schedule_id, schedule.next_run_at,
            "2099-01-01T00:00:00+00:00",
        )
        assert store.update_scheduled_task_run(
            occurrence.schedule_run_id, "succeeded",
            finished_at=datetime.now(timezone.utc).isoformat(),
            result={"success": True},
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


def test_schedule_control_plane_is_independent_of_agent_chat_turns():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        persistence_store=store,
        require_llm=False,
        start_background_workers=False,
    )
    principal = RequestPrincipal(
        user_id="operator-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.plan", "ads.read"}),
    )
    try:
        assert "scheduling" not in {
            feature.feature_name for feature in runtime.features
        }
        assert not hasattr(runtime, "get_schedule_draft")

        schedule = runtime.create_schedule(
            name="Daily report",
            prompt="Summarize campaign performance",
            cron_expression="0 9 * * *",
            timezone="Asia/Shanghai",
            principal=principal,
        )

        assert schedule["tenant_id"] == "tenant-1"
        assert schedule["user_id"] == "operator-1"
        assert schedule["payload"]["execution_mode"] == "dry_run"
        assert runtime.get_schedule(
            schedule["schedule_id"], user_id="operator-1", tenant_id="tenant-1"
        ) == schedule
        assert runtime.pause_schedule(
            schedule["schedule_id"], user_id="operator-1", tenant_id="tenant-1"
        )["status"] == "paused"
        assert runtime.resume_schedule(
            schedule["schedule_id"], user_id="operator-1", tenant_id="tenant-1"
        )["status"] == "active"
        assert runtime.delete_schedule(
            schedule["schedule_id"], user_id="operator-1", tenant_id="tenant-1"
        ) is True
    finally:
        runtime.close(wait=True)
        store.close()


def test_manual_schedule_run_is_recorded_and_linked_to_the_queued_task():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        persistence_store=store,
        require_llm=False,
        start_background_workers=False,
    )
    principal = RequestPrincipal(
        user_id="operator-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.plan", "ads.read"}),
    )
    try:
        schedule = runtime.create_schedule(
            name="Daily report",
            prompt="Summarize campaign performance",
            cron_expression="0 9 * * *",
            timezone="Asia/Shanghai",
            principal=principal,
        )
        runtime.scheduling_service.submit_task = lambda *_args, **_kwargs: (
            {"task_id": "manual-task-1", "status": "queued"},
            True,
        )

        result = runtime.run_schedule_now(
            schedule["schedule_id"],
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )

        assert result["task"]["task_id"] == "manual-task-1"
        assert result["run"]["schedule_id"] == schedule["schedule_id"]
        assert result["run"]["task_id"] == "manual-task-1"
        assert result["run"]["status"] == "queued"
        runs = runtime.list_schedule_runs(
            schedule_id=schedule["schedule_id"],
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        assert len(runs) == 1
        assert runs[0]["schedule_run_id"] == result["run"]["schedule_run_id"]
    finally:
        runtime.close(wait=True)
        store.close()


def test_chat_can_create_a_durable_schedule_through_the_registered_tool():
    class Model:
        def __init__(self):
            self.calls = []

        def complete(self, messages, tools, _request):
            self.calls.append((list(messages), list(tools)))
            if any(message.role == "tool" for message in messages):
                return ModelTurn(content="已创建每天上午 9 点的定时任务。")
            return ModelTurn(tool_calls=[ToolCall(
                id="schedule-create-call",
                name="agent_schedule_create",
                arguments={
                    "name": "Daily campaign check",
                    "prompt": "Check campaign status and summarize changes",
                    "cron_expression": "0 9 * * *",
                    "timezone": "Asia/Shanghai",
                },
            )])

    store = AdAgentStore(":memory:")
    model = Model()
    runtime = AdvertisingComposition(
        persistence_store=store,
        llm_client=model,
        require_llm=True,
        start_background_workers=False,
    )
    principal = RequestPrincipal(
        user_id="operator-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.plan", "ads.read"}),
    )
    events = []
    try:
        result = runtime.run(
            "帮我创建一个定时任务，每天上午 9 点检查 campaign 状态",
            user_id="operator-1",
            tenant_id="tenant-1",
            principal=principal,
            event_callback=events.append,
        )

        schedules = runtime.list_schedules(
            user_id="operator-1",
            tenant_id="tenant-1",
        )
        assert result["status"] == "succeeded", result
        assert len(schedules) == 1
        assert schedules[0]["name"] == "Daily campaign check"
        assert schedules[0]["cron_expression"] == "0 9 * * *"
        assert schedules[0]["timezone"] == "Asia/Shanghai"
        assert schedules[0]["payload"]["execution_mode"] == "dry_run"
        schedule_definition, _handler = runtime.registry.get(
            "agent_schedule_create"
        )
        assert schedule_definition.live_support is False
        assert model.calls
        assert "agent_schedule_create" in {
            tool.name for tool in model.calls[0][1]
        }
        model_calls = [
            event for event in events if event.get("type") == "model_start"
        ]
        assert len(model_calls) == 2
        assert len({event["model_call_id"] for event in model_calls}) == 2
    finally:
        runtime.close(wait=True)
        store.close()


def test_chat_cannot_create_a_schedule_without_trusted_plan_permission():
    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(tool_calls=[ToolCall(
                id="schedule-create-call",
                name="agent_schedule_create",
                arguments={
                    "name": "Daily campaign check",
                    "prompt": "Check campaign status and summarize changes",
                    "cron_expression": "0 9 * * *",
                    "timezone": "Asia/Shanghai",
                },
            )])

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        persistence_store=store,
        llm_client=Model(),
        require_llm=True,
        start_background_workers=False,
    )
    principal = RequestPrincipal(
        user_id="operator-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.read"}),
    )
    try:
        result = runtime.run(
            "帮我创建一个定时任务，每天上午 9 点检查 campaign 状态",
            user_id="operator-1",
            tenant_id="tenant-1",
            principal=principal,
        )

        assert result["status"] == "failed"
        assert runtime.list_schedules(
            user_id="operator-1",
            tenant_id="tenant-1",
        ) == []
    finally:
        runtime.close(wait=True)
        store.close()


def test_chat_can_run_an_existing_schedule_through_the_registered_tool():
    class Model:
        def __init__(self, schedule_id):
            self.schedule_id = schedule_id
            self.calls = []

        def complete(self, messages, tools, _request):
            self.calls.append((list(messages), list(tools)))
            if any(message.role == "tool" for message in messages):
                return ModelTurn(content="已提交立即执行，任务正在排队。")
            return ModelTurn(tool_calls=[ToolCall(
                id="schedule-run-call",
                name="agent_schedule_run_now",
                arguments={"schedule_id": self.schedule_id},
            )])

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        persistence_store=store,
        require_llm=False,
        start_background_workers=False,
    )
    principal = RequestPrincipal(
        user_id="operator-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.plan", "ads.read"}),
    )
    try:
        schedule = runtime.create_schedule(
            name="Daily report",
            prompt="Summarize campaign performance",
            cron_expression="0 9 * * *",
            timezone="Asia/Shanghai",
            principal=principal,
        )
        runtime.scheduling_service.submit_task = lambda *_args, **_kwargs: (
            {"task_id": "manual-task-1", "status": "queued"},
            True,
        )
        model = Model(schedule["schedule_id"])
        runtime.inject_llm(model)

        result = runtime.run(
            "直接执行一下这个任务",
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            principal=principal,
        )

        assert result["status"] == "succeeded", result
        runs = runtime.list_schedule_runs(
            schedule_id=schedule["schedule_id"],
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        assert len(runs) == 1
        assert runs[0]["task_id"] == "manual-task-1"
        assert runs[0]["status"] == "queued"
        definition, _handler = runtime.registry.get("agent_schedule_run_now")
        assert definition.live_support is False
        assert "ads.plan" in definition.required_permissions
        assert "agent_schedule_run_now" in {
            tool.name for tool in model.calls[0][1]
        }
    finally:
        runtime.close(wait=True)
        store.close()


def test_chat_cannot_run_a_schedule_without_trusted_plan_permission():
    class Model:
        def __init__(self, schedule_id):
            self.schedule_id = schedule_id

        def complete(self, messages, _tools, _request):
            if any(message.role == "tool" for message in messages):
                return ModelTurn(content="未能确认该定时任务。")
            return ModelTurn(tool_calls=[ToolCall(
                id="schedule-run-call",
                name="agent_schedule_run_now",
                arguments={"schedule_id": self.schedule_id},
            )])

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        persistence_store=store,
        require_llm=False,
        start_background_workers=False,
    )
    owner = RequestPrincipal(
        user_id="operator-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.plan", "ads.read"}),
    )
    caller = RequestPrincipal(
        user_id="operator-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.read"}),
    )
    try:
        schedule = runtime.create_schedule(
            name="Daily report",
            prompt="Summarize campaign performance",
            cron_expression="0 9 * * *",
            timezone="Asia/Shanghai",
            principal=owner,
        )
        runtime.inject_llm(Model(schedule["schedule_id"]))

        result = runtime.run(
            "直接执行这个定时任务",
            user_id=caller.user_id,
            tenant_id=caller.tenant_id,
            principal=caller,
        )

        assert result["status"] == "failed"
        assert runtime.list_schedule_runs(
            schedule_id=schedule["schedule_id"],
            user_id=owner.user_id,
            tenant_id=owner.tenant_id,
        ) == []
    finally:
        runtime.close(wait=True)
        store.close()


def test_chat_cannot_run_another_users_schedule():
    class Model:
        def __init__(self, schedule_id):
            self.schedule_id = schedule_id

        def complete(self, messages, _tools, _request):
            if any(message.role == "tool" for message in messages):
                return ModelTurn(content="未能确认该定时任务。")
            return ModelTurn(tool_calls=[ToolCall(
                id="schedule-run-call",
                name="agent_schedule_run_now",
                arguments={"schedule_id": self.schedule_id},
            )])

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        persistence_store=store,
        require_llm=False,
        start_background_workers=False,
    )
    owner = RequestPrincipal(
        user_id="owner-1",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.plan", "ads.read"}),
    )
    caller = RequestPrincipal(
        user_id="other-user",
        tenant_id="tenant-1",
        permissions=frozenset({"ads.plan", "ads.read"}),
    )
    try:
        schedule = runtime.create_schedule(
            name="Private report",
            prompt="Summarize campaign performance",
            cron_expression="0 9 * * *",
            timezone="Asia/Shanghai",
            principal=owner,
        )
        runtime.inject_llm(Model(schedule["schedule_id"]))

        result = runtime.run(
            "执行这个定时任务",
            user_id=caller.user_id,
            tenant_id=caller.tenant_id,
            principal=caller,
        )

        assert result["status"] in {"failed", "recovery_required"}
        assert runtime.list_schedule_runs(
            schedule_id=schedule["schedule_id"],
            user_id=owner.user_id,
            tenant_id=owner.tenant_id,
        ) == []
    finally:
        runtime.close(wait=True)
        store.close()
