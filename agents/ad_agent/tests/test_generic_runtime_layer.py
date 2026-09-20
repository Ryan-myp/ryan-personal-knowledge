from contextvars import ContextVar
import threading

from agents.agent_harness.agent_runtime import AgentRuntime
from agents.ad_agent.core.interfaces import (
    ExecutionMode,
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from agents.ad_agent.core.policy_engine import PolicyEngine, PolicyRequest
from agents.ad_agent.core.runtime_kernel import TurnRequest
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.core.tool_selection import PromptRenderer, ToolSelector
from agents.ad_agent.core.tool_sources import StaticToolSource, ToolBinding
from agents.ad_agent.core.turn_pipeline import (
    SequentialTurnPipeline,
    TurnStageResult,
)


def _tool(name="search_docs", *, intent_types=None, namespace="docs", **overrides):
    values = {
        "name": name,
        "skill": "docs",
        "namespace": namespace,
        "description": f"{name} description",
        "input_schema": ToolSchema(properties={"query": {"type": "string"}}),
        "intent_types": list(intent_types or ["search"]),
    }
    values.update(overrides)
    return ToolDefinition(**values)


def test_tool_selector_and_prompt_renderer_are_domain_neutral():
    selector = ToolSelector()
    tools = [_tool("search_docs"), _tool("write_docs", intent_types=["update"])]

    selection = selector.select(
        user_input="search docs",
        intent=type("Intent", (), {"intent_type": "search", "namespaces": ["docs"]})(),
        available_tools=tools,
    )

    assert [tool.name for tool in selection.selected_tools] == ["search_docs"]
    prompt = PromptRenderer().render(selection)
    assert "search_docs" in prompt
    assert "write_docs" not in prompt


def test_generic_runtime_delegates_turns_through_kernel_contract():
    mode_context = ContextVar("test_generic_runtime_mode", default=None)
    calls = []
    pipeline = SequentialTurnPipeline([
        lambda context: calls.append(context.request) or {
            "session_id": context.request.session_id,
            "tenant_id": context.request.tenant_id,
            "value": context.request.context["value"],
        },
    ])

    runtime = AgentRuntime(
        session_manager=None,
        session_locks={},
        session_locks_guard=threading.RLock(),
        lease_owner="test",
        lease_seconds=30,
        mode_context=mode_context,
        validate_mode=lambda value: value or "dry_run",
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda request: request.session_id,
        pipeline=pipeline,
    )

    result = runtime.run(
        TurnRequest(
            user_input="hello",
            context={"value": "ok"},
            tenant_id="tenant-a",
        )
    )

    assert result["tenant_id"] == "tenant-a"
    assert result["value"] == "ok"
    assert len(calls) == 1
    assert calls[0].session_id == result["session_id"]


def test_generic_runtime_close_is_best_effort_and_idempotent():
    closed = []

    class Executor:
        def execute(self, _context):
            return {}

        def close(self):
            closed.append(True)

    runtime = AgentRuntime(
        session_manager=None,
        session_locks={},
        session_locks_guard=threading.RLock(),
        lease_owner="test",
        lease_seconds=30,
        mode_context=ContextVar("test_generic_runtime_close", default=None),
        validate_mode=lambda value: value or "dry_run",
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda _request: None,
        pipeline=Executor(),
    )

    runtime.close()
    runtime.close()
    assert closed == [True]


def test_generic_runtime_runs_a_domain_neutral_turn_pipeline():
    events = []

    class ParseStage:
        def execute(self, context):
            events.append("parse")
            context.state["intent"] = "search"

    class CompleteStage:
        def execute(self, context):
            events.append("complete")
            return TurnStageResult.complete({
                "intent": context.state["intent"],
                "events": list(events),
            })

    class MustNotRun:
        def execute(self, _context):
            raise AssertionError("terminal pipeline result must stop later stages")

    pipeline = SequentialTurnPipeline(
        [ParseStage(), CompleteStage(), MustNotRun()]
    )
    runtime = AgentRuntime(
        session_manager=None,
        session_locks={},
        session_locks_guard=threading.RLock(),
        lease_owner="test",
        lease_seconds=30,
        mode_context=ContextVar("test_generic_runtime_pipeline", default=None),
        validate_mode=lambda value: value or "dry_run",
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda _request: None,
        pipeline=pipeline,
    )

    result = runtime.run(TurnRequest(user_input="search"))

    assert result["intent"] == "search"
    assert result["events"] == ["parse", "complete"]
    assert result["run_id"]
    assert result["turn_id"]


def test_turn_pipeline_can_return_a_stage_error_without_leaking_exception():
    class BrokenStage:
        def execute(self, _context):
            raise ValueError("bad input")

    pipeline = SequentialTurnPipeline(
        [BrokenStage()],
        on_error=lambda _context, error: {
            "error_type": type(error).__name__,
            "status": "failed",
        },
    )

    assert pipeline.execute(TurnRequest(user_input="bad")) == {
        "error_type": "ValueError",
        "status": "failed",
    }


def test_turn_pipeline_exposes_stage_metadata_to_completion_hook():
    completed = []

    class ParseStage:
        name = "parse"

        def execute(self, context):
            return TurnStageResult.continue_with(
                "parsed",
                metadata={"intent_type": "search"},
            )

    pipeline = SequentialTurnPipeline(
        [ParseStage()],
        on_complete=lambda context: completed.append(context) or context.result,
    )

    assert pipeline.execute(TurnRequest(user_input="search")) == "parsed"
    assert completed[0].state["stage_metadata"] == {
        "parse": {"intent_type": "search"},
    }
    assert completed[0].state["stage_results"][0]["stage"] == "parse"


def test_generic_runtime_registers_tool_without_capability():
    calls = []

    class Executor:
        def execute(self, _ctx, input_data):
            calls.append(input_data)
            return {"ok": True}

    registry = SimpleToolRegistry()
    runtime = AgentRuntime(
        session_manager=None,
        session_locks={},
        session_locks_guard=threading.RLock(),
        lease_owner="test",
        lease_seconds=30,
        mode_context=ContextVar("test_generic_runtime_tools", default=None),
        validate_mode=lambda value: value or "dry_run",
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda _request: None,
        pipeline=SequentialTurnPipeline([lambda _context: {}]),
        tool_registry=registry,
    )
    tool = _tool(name="local_search")

    runtime.register_tool(tool, Executor(), source_id="local")

    definition, handler = registry.get("local_search")
    assert definition is tool
    assert handler.execute(None, {"query": "hello"}) == {"ok": True}
    assert calls == [{"query": "hello"}]


def test_generic_runtime_registers_source_atomically_and_tracks_owner():
    registry = SimpleToolRegistry()
    runtime = AgentRuntime(
        session_manager=None,
        session_locks={},
        session_locks_guard=threading.RLock(),
        lease_owner="test",
        lease_seconds=30,
        mode_context=ContextVar("test_generic_runtime_source", default=None),
        validate_mode=lambda value: value or "dry_run",
        resolve_mode=lambda _tenant, _user, _requested: "dry_run",
        assert_ready=lambda: None,
        ensure_session=lambda _request: None,
        pipeline=SequentialTurnPipeline([lambda _context: {}]),
        tool_registry=registry,
    )
    source = StaticToolSource(
        "remote:mcp:test",
        [
            ToolBinding(_tool(name="remote_one"), lambda _ctx, _data: {"one": True}),
            object(),
        ],
    )

    try:
        runtime.register_tool_source(source)
    except TypeError as exc:
        assert "ToolBinding" in str(exc)
    else:
        raise AssertionError("invalid source binding must be rejected")

    assert registry.list_all() == []

    valid_source = StaticToolSource(
        "remote:mcp:test",
        [ToolBinding(_tool(name="remote_one"), lambda _ctx, _data: {"one": True})],
    )
    runtime.register_tool_source(valid_source)
    assert [tool.name for tool in registry.list_all()] == ["remote_one"]
    runtime.unregister_tool_source("remote:mcp:test")
    assert registry.list_all() == []


def test_policy_engine_keeps_dry_run_planning_separate_from_live_execution():
    engine = PolicyEngine()
    tool = _tool(
        name="publish_docs",
        intent_types=["publish"],
        effect_class=ToolEffect.WRITE,
        required_permissions=["docs.plan"],
        live_permission="docs.publish",
        live_support=True,
    )

    dry_run = engine.evaluate(
        PolicyRequest(
            tool=tool,
            execution_mode=ExecutionMode.DRY_RUN.value,
            granted_permissions={"docs.plan"},
            allow_live_writes=False,
            live_approved_tools=set(),
            write_guard_configured=False,
        )
    )
    assert dry_run.allowed is True
    assert dry_run.requires_confirmation is False

    live = engine.evaluate(
        PolicyRequest(
            tool=tool,
            execution_mode=ExecutionMode.LIVE.value,
            granted_permissions={"docs.plan", "docs.publish"},
            allow_live_writes=True,
            live_approved_tools={"publish_docs"},
            write_guard_configured=True,
            confirmed=False,
        )
    )
    assert live.allowed is False
    assert live.requires_confirmation is True
    assert live.errors == ()


def test_policy_engine_fails_closed_for_permission_and_scope():
    engine = PolicyEngine()
    tool = _tool(
        scope_type="workspace",
        scope_required=True,
        required_permissions=["docs.write"],
    )

    decision = engine.evaluate(
        PolicyRequest(
            tool=tool,
            granted_permissions=set(),
            scope=None,
        )
    )

    assert decision.allowed is False
    assert decision.requires_confirmation is False
    assert "docs.write" in decision.errors[0]
    assert any("scope" in error for error in decision.errors)
