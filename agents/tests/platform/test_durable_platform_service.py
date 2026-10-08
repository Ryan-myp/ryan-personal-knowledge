"""A non-ad application can enter the same Run through a durable worker."""

from dataclasses import dataclass
import time

import pytest

from agents.agent_harness import RunResult
from agents.agent_platform.infrastructure.durable import DurableAgentService
from agents.agent_platform.infrastructure.durable import SQLiteRunStore, SQLiteTaskQueueStore
from agents.agent_platform.infrastructure.durable.task import TaskSubmission
from agents.agent_platform.examples.ticket_support import create_ticket_support_application
from agents.agent_platform.runtime import DataLayer, PlatformDependencies


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    permissions: frozenset[str] = frozenset()


class Application:
    def __init__(self):
        self.requests = []
        self.closed = False

    def run(self, request):
        self.requests.append(request)
        return RunResult(
            run_id=request.run_id or "run-test",
            turn_id=request.turn_id or "turn-test",
            reply="ticket found",
        )

    def close(self):
        self.closed = True


def _terminal(service, task_id, principal):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        record = service.get(task_id, principal=principal)
        if record.status in {"succeeded", "failed", "recovery_required"}:
            return record
        time.sleep(0.01)
    return service.get(task_id, principal=principal)


def test_durable_non_ad_run_uses_revalidated_principal_and_one_runtime():
    store = SQLiteTaskQueueStore(":memory:")
    application = Application()
    trusted = Principal("tenant-a", "user-a")
    service = DurableAgentService(
        application=application,
        store=store,
        principal_resolver=lambda tenant, user: trusted,
        max_task_workers=1,
    )
    service.start()
    try:
        task, created = service.submit(
            "Find ticket 42", principal=trusted, session_id="support-session",
            idempotency_key="request-1",
        )
        assert created is True
        assert _terminal(service, task.task_id, trusted).status == "succeeded"
        assert service.get(
            task.task_id, principal=Principal("tenant-b", "user-a")
        ) is None
        request = application.requests[0]
        assert request.principal is trusted
        assert request.user_id == "user-a"
        assert request.tenant_id == "tenant-a"
        assert request.task_id == task.task_id
        assert request.session_id == "support-session"
        assert store.get_task(task.task_id).result["reply"] == "ticket found"
        duplicate, created = service.submit(
            "Find ticket 42", principal=trusted, session_id="support-session",
            idempotency_key="request-1",
        )
        assert created is False
        assert duplicate.task_id == task.task_id
        with pytest.raises(ValueError, match="idempotency key conflict"):
            service.submit(
                "Find ticket 99", principal=trusted, session_id="support-session",
                idempotency_key="request-1",
            )
    finally:
        service.close()
        assert application.closed is False
        store.close()


def test_durable_run_rejects_identity_mismatch_on_worker_recovery():
    store = SQLiteTaskQueueStore(":memory:")
    application = Application()
    service = DurableAgentService(
        application=application,
        store=store,
        principal_resolver=lambda _tenant, _user: Principal("other", "user-a"),
        max_task_workers=1,
    )
    service.start()
    try:
        task, _ = service.submit(
            "Find ticket 42", principal=Principal("tenant-a", "user-a"),
        )
        assert _terminal(
            service, task.task_id, Principal("tenant-a", "user-a")
        ).status == "failed"
        assert application.requests == []
    finally:
        service.close()
        assert application.closed is False
        store.close()


def test_submission_requires_trusted_principal():
    store = SQLiteTaskQueueStore(":memory:")
    service = DurableAgentService(
        application=Application(), store=store,
        principal_resolver=lambda _tenant, _user: None,
    )
    with pytest.raises(ValueError, match="principal"):
        service.submit("hello", principal=None)
    service.close()
    store.close()


def test_submission_rejects_unbounded_durable_payload_fields():
    store = SQLiteTaskQueueStore(":memory:")
    service = DurableAgentService(
        application=Application(), store=store,
        principal_resolver=lambda _tenant, _user: Principal("t", "u"),
        max_input_chars=8,
    )
    principal = Principal("t", "u")
    try:
        with pytest.raises(ValueError, match="input exceeds"):
            service.submit("x" * 9, principal=principal)
        with pytest.raises(ValueError, match="session_id exceeds"):
            service.submit("hello", principal=principal, session_id="s" * 256)
        with pytest.raises(ValueError, match="idempotency_key exceeds"):
            service.submit("hello", principal=principal, idempotency_key="k" * 256)
    finally:
        service.close()
        store.close()


def test_durable_management_is_scoped_to_principal():
    store = SQLiteTaskQueueStore(":memory:")
    trusted = Principal("tenant-a", "user-a")
    other = Principal("tenant-b", "user-a")
    service = DurableAgentService(
        application=Application(), store=store,
        principal_resolver=lambda _tenant, _user: trusted,
        max_task_workers=1,
    )
    try:
        task = store.create_task(TaskSubmission(
            task_id="managed-task", tenant_id="tenant-a", user_id="user-a",
            kind="agent.turn", status="queued",
            payload={"user_input": "Find ticket 42", "session_id": ""},
        ))
        assert [row.task_id for row in service.list(principal=trusted)] == [task.task_id]
        assert service.list(principal=other) == []
        assert service.cancel(task.task_id, principal=other) is None
        assert service.pause(task.task_id, principal=other) is None
        assert service.resume(task.task_id, principal=other) is None
        assert service.pause(task.task_id, principal=trusted).status == "paused"
        assert service.resume(task.task_id, principal=trusted).status == "queued"
        store.create_task(TaskSubmission(
            task_id="cancel-task", tenant_id="tenant-a", user_id="user-a",
            kind="agent.turn", status="queued", payload={"user_input": "cancel me"},
        ))
        assert service.cancel("cancel-task", principal=trusted).status == "cancelled"
    finally:
        service.close()
        store.close()


def test_ticket_support_tool_run_is_durable_from_task_to_run_store(tmp_path):
    store = SQLiteTaskQueueStore(":memory:")
    run_store = SQLiteRunStore(tmp_path / "ticket-runs.sqlite3")
    trusted = Principal("tenant-a", "user-a")

    class Model:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages, _tools, _request):
            self.calls += 1
            if self.calls == 1:
                return {"tool_calls": [{
                    "id": "lookup-1", "name": "lookup_ticket",
                    "arguments": {"ticket_id": "42"},
                }]}
            return "Ticket 42 is open"

    application = create_ticket_support_application(
        model=Model(),
        dependencies=PlatformDependencies(data=DataLayer(run_store=run_store)),
    )
    service = DurableAgentService(
        application=application,
        store=store,
        principal_resolver=lambda _tenant, _user: trusted,
        max_task_workers=1,
    )
    service.start()
    try:
        task, created = service.submit("Find ticket 42", principal=trusted)
        assert created is True
        final = _terminal(service, task.task_id, trusted)
        assert final.status == "succeeded"
        assert final.result["reply"] == "Ticket 42 is open"
        assert final.result["tool_results"][0]["name"] == "lookup_ticket"
        run = run_store.get_run(
            final.result["run_id"], tenant_id="tenant-a", user_id="user-a",
        )
        assert run["task_id"] == task.task_id
        assert run["status"] == "succeeded"
        events = run_store.list_run_events(
            run["run_id"], tenant_id="tenant-a", user_id="user-a",
        )
        assert events
        assert any(
            event["event"].get("type") == "tool_execution_end"
            for event in events
        )
    finally:
        service.close()
        assert application.closed is False
        application.close()
        run_store.close()
        store.close()
