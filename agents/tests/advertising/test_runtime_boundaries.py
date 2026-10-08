"""Regression tests for the business-neutral Runtime boundaries."""

import ast
import threading
from contextvars import ContextVar
from datetime import datetime, timedelta

from agents.agent_harness import AgentRuntimeKernel, TurnRequest
from agents.agent_platform.infrastructure.durable import task_outcome_status
from agents.agent_platform.data.persistence.models import ToolCallRecord
from agents.agent_platform.data.persistence.store import AdAgentStore


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
    source = open(
        "agents/tools/advertising/application/ad_application_assembly.py",
        encoding="utf-8",
    ).read()
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

    root = Path("agents/tools/advertising/application")
    facade = (root / "ad_application.py").read_text(encoding="utf-8")
    bootstrap = (root / "ad_application_bootstrap.py").read_text(encoding="utf-8")
    assembly = (root / "ad_application_assembly.py").read_text(encoding="utf-8")

    # The facade delegates startup to Bootstrap, which owns the application
    # assembly. Neither public entrypoint may recreate the worker graph.
    assert "AdApplicationBootstrap.initialize" in facade
    assert "AdApplicationAssembly.compose" in bootstrap
    assert not (root / "ad_runtime_bootstrap.py").exists()
    assert not (root / "ad_runtime_assembly.py").exists()
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


def test_ad_runtime_domain_policy_and_context_are_replaceable_services():
    from pathlib import Path

    root = Path("agents/tools/advertising/application")
    facade = (root / "ad_application.py").read_text(encoding="utf-8")
    application_facade = (root / "ad_application_facade.py").read_text(
        encoding="utf-8"
    )
    hooks = (root / "ad_application_hooks.py").read_text(encoding="utf-8")
    policy = (root / "ad_runtime_policy.py").read_text(encoding="utf-8")
    context = (root / "ad_runtime_context.py").read_text(encoding="utf-8")
    run_service = (root / "ad_run_service.py").read_text(encoding="utf-8")
    catalog = (root / "ad_runtime_catalog.py").read_text(encoding="utf-8")
    lifecycle = (root / "ad_runtime_lifecycle.py").read_text(encoding="utf-8")
    presentation = (root / "ad_runtime_presentation.py").read_text(
        encoding="utf-8"
    )
    controls = (root / "ad_runtime_controls.py").read_text(encoding="utf-8")
    scope = (root / "ad_runtime_scope.py").read_text(encoding="utf-8")
    reconciliation = (root / "ad_runtime_reconciliation.py").read_text(
        encoding="utf-8"
    )

    assert "class AdvertisingRuntimePolicy" in policy
    assert "class AdvertisingRuntimeContext" in context
    assert "class AdvertisingRunService" in run_service
    assert "class AdvertisingCatalogService" in catalog
    assert "class AdvertisingLifecycleService" in lifecycle
    assert "class AdvertisingPresentationService" in presentation
    assert "class AdvertisingRuntimeControls" in controls
    assert "class AdvertisingRuntimeScope" in scope
    assert "class AdvertisingRuntimeReconciliation" in reconciliation
    assert "class AdvertisingRuntimePolicy" not in facade
    assert "class AdvertisingRuntimeContext" not in facade
    assert "class AdvertisingRunService" not in facade
    assert "class AdvertisingCatalogService" not in facade
    assert "class AdvertisingLifecycleService" not in facade
    assert "class AdvertisingPresentationService" not in facade
    assert "class AdvertisingRuntimeControls" not in facade
    assert "class AdvertisingRuntimeScope" not in facade
    assert "class AdvertisingRuntimeReconciliation" not in facade
    assert "self.runtime_policy" in hooks
    assert "self.runtime_context" in hooks
    assert "self._run_service()" in application_facade
    assert "def run(" in application_facade
    assert "def register_tool_source(" in application_facade
    assert "api_clients" not in application_facade
    assert "api_clients" not in hooks
    assert "api_clients" not in policy
    assert "api_clients" not in context
    assert "api_clients" not in run_service
    assert "api_clients" not in catalog
    assert "api_clients" not in lifecycle
    assert "api_clients" not in presentation
    assert "api_clients" not in controls
    assert "api_clients" not in scope
    assert "api_clients" not in reconciliation


def test_ad_application_root_only_declares_composition_and_constructor():
    from pathlib import Path

    root = Path("agents/tools/advertising/application")
    source = (root / "ad_application.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and node.name == "AdvertisingComposition"
    ]
    assert len(classes) == 1
    methods = [
        node.name
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert methods == ["__init__"]
    assert "class AdApplicationFacadeMixin" not in source
    assert "class AdApplicationHooksMixin" not in source


def test_ad_runtime_has_one_platform_entrypoint_without_compatibility_fallback():
    """New code enters directly through the platform application."""
    from pathlib import Path

    root = Path("agents/tools/advertising/application")
    assert not (root / "ad_turn_engine.py").exists()
    assert not (root / "ad_turn_orchestrator.py").exists()
    runtime_source = (root / "ad_application.py").read_text(encoding="utf-8")
    assert not (root / "ad_runtime.py").exists()
    assert "def _run_unlocked" not in runtime_source
    assert "getattr(self, \"_platform_application\"" not in runtime_source


def test_ad_runtime_has_no_ad_turn_pipeline_or_stage_modules():
    from pathlib import Path

    root = Path("agents/tools/advertising/application")
    assert not (root / "ad_turn_pipeline.py").exists()
    assert not (root / "ad_turn_stages.py").exists()
    assert not (root / "ad_turn_state.py").exists()


def test_turn_adapter_delegates_creation_and_clarification_interaction():
    from pathlib import Path

    root = Path("agents/tools/advertising/application")
    integration = ast.parse(
        (root / "integration.py").read_text(encoding="utf-8")
    )
    adapter = next(
        node for node in integration.body
        if isinstance(node, ast.ClassDef)
        and node.name == "AdvertisingModelAdapter"
    )
    start_turn = next(
        node for node in adapter.body
        if isinstance(node, ast.FunctionDef) and node.name == "_start_turn"
    )
    direct_owner_accesses = {
        node.attr
        for node in ast.walk(start_turn)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "self"
        and node.value.attr == "owner"
    }
    assert not direct_owner_accesses.intersection({
        "build_creation_ui",
        "creation_card_builder",
        "_creation_contract_preflight",
        "_creation_contract_reply",
        "set_creation_draft",
        "action_clarification_builder",
        "action_clarification_reply",
        "set_action_draft",
    })
    assert "run_batch_plan" not in direct_owner_accesses
    assert "is_batch_intent" not in direct_owner_accesses

    interaction_services = (root / "ad_turn_interaction_services.py").read_text(
        encoding="utf-8"
    )
    assert "class AdTurnInteractionServicesMixin" in interaction_services
    assert "def prepare_creation_turn" in interaction_services
    assert "def prepare_action_clarification" in interaction_services

    cross_channel = (root / ".." / "shared" / "features" / "cross_channel.py").read_text(
        encoding="utf-8"
    )
    assert "def handle_routed_turn" in cross_channel


def test_model_adapter_delegates_application_turn_orchestration():
    from pathlib import Path

    integration = ast.parse(
        Path("agents/tools/advertising/application/integration.py").read_text(encoding="utf-8")
    )
    adapter = next(
        node for node in integration.body
        if isinstance(node, ast.ClassDef)
        and node.name == "AdvertisingModelAdapter"
    )
    start_turn = next(
        node for node in adapter.body
        if isinstance(node, ast.FunctionDef) and node.name == "_start_turn"
    )
    calls = [
        node for node in ast.walk(start_turn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "self"
        and node.func.value.attr == "_turn_handler"
        and node.func.attr == "start_turn"
    ]
    assert len(calls) == 1
    assert len(start_turn.body) == 1

    handler = Path("agents/tools/advertising/application/integration_turn_handler.py")
    assert handler.exists()


def test_turn_account_services_keep_multi_platform_scope_isolated():
    from types import SimpleNamespace

    from agents.tools.advertising.application.ad_turn_account_services import (
        AdTurnAccountServices,
    )

    validated = []
    resolved = {
        "meta": "meta-test-account",
        "tiktok": "tiktok-test-account",
    }

    def validate(platform, account, is_write, scope):
        validated.append((platform, account, is_write, scope))
        return (account in scope.get(platform, []), "account outside principal scope")

    owner = SimpleNamespace(
        account_resolver=SimpleNamespace(
            resolve=lambda _intent, platform, _tools, _fallback, **_kwargs:
                resolved[platform]
        ),
        _canonical_platform=lambda platform: platform,
        _validate_account_with_principal=validate,
    )
    request = SimpleNamespace(
        principal=SimpleNamespace(account_scope={"meta": ["meta-test-account"]}),
        context={"account_id": "must-not-cross-platform"},
    )
    routed = {
        "meta": [SimpleNamespace(namespace="meta", is_write_tool=True)],
        "tiktok": [SimpleNamespace(namespace="tiktok", is_write_tool=True)],
    }

    result = AdTurnAccountServices(owner).validate_write_account_scope(
        intent=SimpleNamespace(namespaces=["meta", "tiktok"]),
        routed=routed,
        request=request,
        request_context=request.context,
        state={},
        context_updates={},
    )

    assert result is not None
    assert result.stop_reason == "policy_blocked"
    assert [(item[0], item[1]) for item in validated] == [
        ("meta", "meta-test-account"),
        ("tiktok", "tiktok-test-account"),
    ]


def test_turn_account_services_asks_when_read_scope_is_ambiguous():
    from types import SimpleNamespace

    from agents.tools.advertising.application.ad_turn_account_services import (
        AdTurnAccountServices,
    )

    owner = SimpleNamespace(
        account_resolver=SimpleNamespace(resolve=lambda *_args, **_kwargs: None),
        _canonical_platform=lambda platform: platform,
        _available_accounts_for_request=lambda _platform, _scope: ["test-1", "test-2"],
    )
    request = SimpleNamespace(
        principal=SimpleNamespace(account_scope={"meta": ["test-1", "test-2"]}),
        context={},
    )
    session = SimpleNamespace(ctx=SimpleNamespace(account_id=None))
    state = {}

    result = AdTurnAccountServices(owner).resolve_read_account_scope(
        intent=SimpleNamespace(namespaces=["meta"]),
        routed={"meta": [SimpleNamespace(namespace="meta", is_write_tool=False)]},
        request=request,
        request_context=request.context,
        session=session,
        state=state,
    )

    assert result.model_turn is not None
    assert result.model_turn.stop_reason == "awaiting_input"
    assert state["confirmation_payload"]["type"] == "ask_account"
    assert request.context == {}
    assert session.ctx.account_id is None


def test_turn_application_services_do_not_import_provider_implementations():
    """Turn stages depend on Runtime contracts, never on channel clients."""
    from pathlib import Path

    root = Path("agents/tools/advertising/application")
    for name in (
        "ad_turn_context.py",
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

    root = pathlib.Path("agents/agent_platform/infrastructure/durable")
    for name in ("task_executor.py", "outbox.py", "scheduler.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "persistence.models" not in source
        assert "domain.ad" not in source
        assert "provider_state" not in source


def test_supervisor_receives_task_kinds_from_the_application_composition_root():
    """The generic worker lifecycle must not own an application task name."""
    source = open(
        "agents/agent_platform/infrastructure/durable/supervisor.py",
        encoding="utf-8",
    ).read()
    assert 'register_handler("agent.turn"' not in source
    assert "task_handlers" in source


def test_tool_source_context_has_no_skill_back_reference():
    """Tool Sources receive execution dependencies, not Skill objects."""
    from agents.agent_harness.core.interfaces import ToolSourceContext
    from agents.tools.advertising.application.tool_source_context import ToolSourceContextWrapper

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
