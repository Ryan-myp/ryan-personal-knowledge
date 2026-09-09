"""Regression tests for the business-neutral Runtime boundaries."""

import ast
import threading
from contextvars import ContextVar
from datetime import datetime, timedelta

from agents.ad_agent.core.runtime_kernel import AgentRuntimeKernel, TurnRequest
from agents.ad_agent.runtime.task_executor import task_outcome_status
from agents.ad_agent.persistence.models import ToolCallRecord
from agents.ad_agent.persistence.store import AdAgentStore


class _LeaseStore:
    def __init__(self):
        self.calls = []

    def acquire_session_lease(self, session_id, owner, seconds):
        self.calls.append(("acquire", session_id, owner))
        return True

    def heartbeat_session_lease(self, session_id, owner, seconds):
        self.calls.append(("heartbeat", session_id, owner))
        return True

    def release_session_lease(self, session_id, owner):
        self.calls.append(("release", session_id, owner))
        return True


def test_runtime_kernel_refreshes_session_only_after_acquiring_lease():
    store = _LeaseStore()
    locks = {}
    mode = ContextVar("test_mode", default=None)
    calls = []

    kernel = AgentRuntimeKernel(
        session_manager=store,
        session_locks=locks,
        session_locks_guard=threading.RLock(),
        lease_owner="worker-a",
        lease_seconds=30,
        mode_context=mode,
        validate_mode=lambda value: value,
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda *args, **kwargs: calls.append(("ensure", args, kwargs)),
        refresh_session=lambda *args, **kwargs: calls.append(("refresh", args, kwargs)),
        execute_unlocked=lambda request: {
            "session_id": request.session_id,
            "tenant_id": request.tenant_id,
            "mode": mode.get(),
        },
    )

    result = kernel.run(TurnRequest(user_input="hello", tenant_id="tenant-a"))

    assert result["tenant_id"] == "tenant-a"
    assert result["mode"] == "dry_run"
    assert [item[0] for item in calls] == ["ensure", "refresh"]
    assert store.calls[0][0] == "acquire"
    assert store.calls[-1][0] == "release"


def test_runtime_kernel_does_not_retain_idle_session_locks():
    """Unrelated new sessions get independent locks and idle locks are retired."""
    store = _LeaseStore()
    locks = {}
    mode = ContextVar("test_mode_lock_lifecycle", default=None)
    kernel = AgentRuntimeKernel(
        session_manager=store,
        session_locks=locks,
        session_locks_guard=threading.RLock(),
        lease_owner="worker-a",
        lease_seconds=30,
        mode_context=mode,
        validate_mode=lambda value: value,
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda *args, **kwargs: None,
        execute_unlocked=lambda request: {"session_id": request.session_id},
    )

    first = kernel._get_session_lock("session-a")
    second = kernel._get_session_lock("session-b")
    assert first is not second
    kernel._release_session_lock("session-a", first)
    kernel._release_session_lock("session-b", second)
    assert locks == {}


def test_runtime_kernel_treats_domain_context_as_opaque():
    """The generic shell must forward, but never interpret, domain fields."""
    store = _LeaseStore()
    mode = ContextVar("test_mode_opaque_context", default=None)
    observed = []
    domain_context = {
        "account_id": "account-a",
        "provider_parameters": {"custom_field": "value"},
    }
    kernel = AgentRuntimeKernel(
        session_manager=store,
        session_locks={},
        session_locks_guard=threading.RLock(),
        lease_owner="worker-a",
        lease_seconds=30,
        mode_context=mode,
        validate_mode=lambda value: value,
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda request: observed.append(("ensure", request)),
        refresh_session=lambda request: observed.append(("refresh", request)),
        execute_unlocked=lambda request: {
            "context": request.context,
            "session_id": request.session_id,
        },
    )

    result = kernel.run(
        TurnRequest(user_input="hello", tenant_id="tenant-a", context=domain_context)
    )

    assert result["context"] == domain_context
    assert all(item[1].context == domain_context for item in observed)
    assert not hasattr(TurnRequest, "account_id")
    assert not hasattr(TurnRequest, "credentials")


def test_task_outcome_is_not_inferred_from_handler_returning_normally():
    assert task_outcome_status({"needs_input": True}) == "awaiting_input"
    assert task_outcome_status({"results": [{"success": False}]}) == "failed"
    assert task_outcome_status({"results": [{"success": True}, {"success": False}]}) == "partially_failed"
    assert task_outcome_status({"provider_state": "unknown"}) == "recovery_required"
    assert task_outcome_status({"success": True}) == "succeeded"


def test_application_runtime_has_no_direct_provider_factory_imports():
    source = open("agents/ad_agent/runtime/runtime.py", encoding="utf-8").read()
    tree = ast.parse(source)
    direct_provider_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.level >= 2 and node.module.split(".", 1)[0] in {
                "api_clients", "capabilities",
            }:
                direct_provider_imports.append(node.module)
    assert direct_provider_imports == []


def test_monitoring_tool_counts_are_tenant_scoped_by_session_column():
    store = AdAgentStore(":memory:")
    store.create_session("session-a", "user-a", metadata={"tenant_id": "tenant-a"})
    store.create_session("session-b", "user-b", metadata={"tenant_id": "tenant-b"})
    started = (datetime.now() - timedelta(minutes=1)).isoformat()
    for session_id, tool_name in (("session-a", "visible"), ("session-b", "hidden")):
        store.record_tool_call(ToolCallRecord(
            id=tool_name, session_id=session_id, turn_id=tool_name,
            tool_name=tool_name, platform="custom", input_data={},
            output_data={}, started_at=started, ended_at=started,
        ))

    snapshot = store.get_monitoring_snapshot(tenant_id="tenant-a")

    assert snapshot["tools"]["total"] == 1
    assert snapshot["tools"]["top_tools"][0]["tool_name"] == "visible"
