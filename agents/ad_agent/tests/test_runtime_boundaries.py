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


def test_runtime_kernel_assigns_stable_run_and_turn_ids():
    store = _LeaseStore()
    mode = ContextVar("test_mode_run_identity", default=None)
    observed = []
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
        ensure_session=lambda _request: None,
        execute_unlocked=lambda request: observed.append(request) or {
            "run_id": request.run_id,
            "turn_id": request.turn_id,
        },
    )

    first = kernel.run(TurnRequest(user_input="one"))
    second = kernel.run(TurnRequest(user_input="two"))

    assert first["run_id"] == observed[0].run_id
    assert first["turn_id"] == observed[0].turn_id
    assert first["run_id"] != second["run_id"]
    assert first["turn_id"] != second["turn_id"]


def test_task_outcome_is_not_inferred_from_handler_returning_normally():
    assert task_outcome_status({"needs_input": True}) == "awaiting_input"
    assert task_outcome_status({"results": [{"success": False}]}) == "failed"
    assert task_outcome_status({"results": [{"success": True}, {"success": False}]}) == "partially_failed"
    assert task_outcome_status({"effect_state": "unknown"}) == "recovery_required"
    assert task_outcome_status({"success": True}) == "succeeded"


def test_application_runtime_has_no_direct_provider_factory_imports():
    source = open("agents/ad_agent/runtime/runtime.py", encoding="utf-8").read()
    tree = ast.parse(source)
    direct_provider_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.level >= 2 and node.module.split(".", 1)[0] in {
                "api_clients", "tools.providers",
            }:
                direct_provider_imports.append(node.module)
    assert direct_provider_imports == []


def test_ad_runtime_assembly_is_the_only_application_composition_graph():
    """The facade delegates infrastructure wiring to an explicit assembly."""
    from pathlib import Path

    root = Path("agents/ad_agent/runtime")
    facade = (root / "ad_runtime.py").read_text(encoding="utf-8")
    assembly = (root / "ad_runtime_assembly.py").read_text(encoding="utf-8")

    # The facade may expose the assembly, but it must not recreate the worker
    # graph in its constructor as more application services are added.
    assert "AdRuntimeAssembly.compose" in facade
    assert "RuntimeSupervisor(" not in facade
    assert "TaskExecutor(" not in facade
    assert "OutboxConsumer(" not in facade
    assert "SchedulingService(" not in facade

    # Assembly code is application composition, not a provider dispatch
    # table. Provider discovery remains behind Tool Source factories.
    assert "api_clients" not in assembly
    assert "tools.providers" not in assembly
    assert "google" not in assembly.lower()
    assert '"meta"' not in assembly.lower()
    assert "tiktok" not in assembly.lower()
    assert "dv360" not in assembly.lower()


def test_ad_turn_has_one_pipeline_entrypoint_without_compatibility_modules():
    """New code enters directly through the application stage pipeline."""
    from pathlib import Path

    root = Path("agents/ad_agent/runtime")
    assert not (root / "ad_turn_engine.py").exists()
    assert not (root / "ad_turn_orchestrator.py").exists()
    runtime_source = (root / "ad_runtime.py").read_text(encoding="utf-8")
    stages_source = (root / "ad_turn_stages.py").read_text(encoding="utf-8")
    assert "def _run_unlocked" not in runtime_source
    assert "_run_unlocked" not in stages_source


def test_ad_turn_pipeline_is_the_application_stage_composition_root():
    from pathlib import Path

    source = Path("agents/ad_agent/runtime/ad_turn_pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "SequentialTurnPipeline" in source
    for stage_name in (
        "RequestValidationStage",
        "SessionContextStage",
        "IntentStage",
        "PlanningStage",
        "ExecutionStage",
        "ResponseStage",
    ):
        assert stage_name in source


def test_ad_turn_state_is_explicit_and_keeps_domain_data_out_of_harness():
    from pathlib import Path

    state_source = Path("agents/ad_agent/runtime/ad_turn_state.py").read_text(
        encoding="utf-8"
    )
    harness_source = Path("agents/agent_harness/turn_pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "class AdTurnState" in state_source
    for field in (
        "safe_user_input",
        "intent",
        "tool_plan",
        "execution_plan",
        "results",
        "response",
    ):
        assert field in state_source
    assert "ad_agent" not in harness_source


def test_turn_application_services_do_not_import_provider_implementations():
    """Turn stages depend on Runtime contracts, never on channel clients."""
    from pathlib import Path

    root = Path("agents/ad_agent/runtime")
    for name in (
        "ad_turn_flow.py",
        "ad_turn_stages.py",
        "ad_turn_context.py",
        "ad_turn_planning.py",
        "ad_tool_execution.py",
        "ad_turn_result.py",
        "ad_runtime_facades.py",
    ):
        source = (root / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        provider_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in {"api_clients", "tools.providers"}:
                    provider_imports.append(node.module)
        assert provider_imports == []


def test_generic_worker_modules_do_not_import_application_models_or_principal():
    """Queue/schedule infrastructure must remain reusable outside ad-agent."""
    import pathlib

    root = pathlib.Path("agents/ad_agent/runtime")
    for name in ("task_executor.py", "outbox.py", "scheduler.py", "scheduling_service.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "persistence.models" not in source
        assert "domain.ad" not in source
        assert "provider_state" not in source


def test_supervisor_receives_task_kinds_from_the_application_composition_root():
    """The generic worker lifecycle must not own an application task name."""
    source = open("agents/ad_agent/runtime/supervisor.py", encoding="utf-8").read()
    assert 'register_handler("agent.turn"' not in source
    assert "task_handlers" in source


def test_tool_source_context_has_no_skill_back_reference():
    """Tool Sources receive execution dependencies, not Skill objects."""
    from agents.ad_agent.core.interfaces import ToolSourceContext
    from agents.ad_agent.runtime.tool_source_context import ToolSourceContextWrapper

    assert "skills" not in ToolSourceContext.__dataclass_fields__
    assert not hasattr(ToolSourceContextWrapper(object()), "skills")


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
