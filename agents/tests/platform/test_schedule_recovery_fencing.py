"""In-memory schedule recovery never resubmits a linked occurrence."""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from agents.agent_platform.infrastructure.durable.scheduler import SchedulerService
from agents.applications.advertising.persistence.models import ScheduledTaskRecord, TaskRecord
from agents.applications.advertising.persistence.store import AdAgentStore


class Clock(datetime):
    value = datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.value.astimezone(tz) if tz else cls.value.replace(tzinfo=None)


@pytest.fixture
def store(monkeypatch):
    Clock.value = datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("agents.agent_platform.infrastructure.durable.scheduler.datetime", Clock)
    monkeypatch.setattr("agents.applications.advertising.persistence.store.datetime", Clock)
    backend = AdAgentStore(":memory:")
    backend.create_scheduled_task(ScheduledTaskRecord(
        schedule_id="schedule", tenant_id="tenant", user_id="user",
        name="offline", prompt="offline", cron_expression="* * * * *",
        timezone="UTC", next_run_at="2026-01-01T00:00:00+00:00",
    ))
    yield backend
    backend.close()


def create_task(store, status="succeeded", tenant="tenant"):
    store.create_task(TaskRecord(
        task_id="task", tenant_id=tenant, user_id="user",
        kind="local", status=status,
    ))
    return store.get_task("task")


@pytest.mark.parametrize("status", ["running", "succeeded", "failed", "cancelled"])
def test_advance_failure_retries_without_submitting_again(store, monkeypatch, status):
    submit = Mock(side_effect=lambda *_: create_task(store, status))
    scheduler = SchedulerService(store, submit)
    with monkeypatch.context() as fault:
        fault.setattr(store, "advance_scheduled_task", Mock(
            side_effect=sqlite3.OperationalError("offline"),
        ))
        assert scheduler.scan_once() == 1
    Clock.value += timedelta(seconds=61)
    assert scheduler.scan_once() == 1
    assert store.get_scheduled_task("schedule").next_run_at == "2026-01-01T00:01:00+00:00"
    assert submit.call_count == 1
    assert len(store.list_tasks()) == 1


@pytest.mark.parametrize("task_tenant", [None, "other-tenant"])
def test_missing_or_unowned_linked_task_is_not_resubmitted(store, task_tenant):
    if task_tenant:
        create_task(store, tenant=task_tenant)
    schedule, occurrence = store.claim_due_scheduled_tasks(Clock.value.isoformat(), "old")[0]
    assert store.attach_scheduled_task_run(occurrence.schedule_run_id, "task", lease_owner="old")
    Clock.value += timedelta(seconds=61)
    submit = Mock(side_effect=AssertionError("must not enqueue"))
    SchedulerService(store, submit).scan_once()
    submit.assert_not_called()
    assert store.get_scheduled_task("schedule").next_run_at == schedule.next_run_at


def test_reconcile_previous_occurrence_preserves_next_occurrence_owner(store):
    schedule, previous = store.claim_due_scheduled_tasks(Clock.value.isoformat(), "old")[0]
    create_task(store)
    store.attach_scheduled_task_run(previous.schedule_run_id, "task", lease_owner="old")
    store.advance_scheduled_task(schedule.schedule_id, schedule.next_run_at,
                                 "2026-01-01T00:01:00+00:00", lease_owner="old")
    Clock.value += timedelta(seconds=61)
    store.claim_due_scheduled_tasks(Clock.value.isoformat(), "new")
    SchedulerService(store, Mock()).reconcile_once()
    assert store.get_scheduled_task("schedule").lease_owner == "new"


def test_old_scheduler_cannot_advance_or_rewrite_after_takeover(store):
    schedule, occurrence = store.claim_due_scheduled_tasks(Clock.value.isoformat(), "old")[0]
    Clock.value += timedelta(seconds=61)
    store.claim_due_scheduled_tasks(Clock.value.isoformat(), "new")
    assert not store.advance_scheduled_task(schedule.schedule_id, schedule.next_run_at,
                                           "2026-01-01T00:01:00+00:00", lease_owner="old")
    assert not store.attach_scheduled_task_run(
        occurrence.schedule_run_id, "stale", lease_owner="old",
    )
    assert not store.update_scheduled_task_run(
        occurrence.schedule_run_id, "failed", lease_owner="old",
    )
    assert store.get_scheduled_task("schedule").lease_owner == "new"
