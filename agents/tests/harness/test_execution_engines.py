"""A replacement reasoning loop must use the same host lifecycle and gates."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.agent_harness import AgentApplication, ModelTurn, ToolCall, StaticToolSource, ToolBinding
from agents.agent_harness.core.plugins import PluginManifest
from agents.agent_platform.tools.policy import ToolExecutionPolicy
from agents.tests.harness.test_runtime_tool_discovery import definition


def manifest(**overrides):
    return PluginManifest(**dict({
        "plugin_id": "test.execution-engine", "version": "1.0.0", "kinds": ("engine",),
        "source": "trusted", "trusted": True, "executable": True,
    }, **overrides))


class ScriptEngine:
    def __init__(self, script):
        self.manifest = manifest()
        self.script = script

    def run(self, session):
        self.script(session)


def application(script, **options):
    invoked, events = [], []
    policy = options.pop("tool_policy", ToolExecutionPolicy())
    app = AgentApplication.create(
        model=lambda *_: pytest.fail("replacement engine called native model loop"),
        engine=ScriptEngine(script), tool_policy=policy, event_callback=events.append,
        **options,
    )
    app.register_tool_source(StaticToolSource("fixture", [ToolBinding(
        definition("lookup", "record"),
        lambda context, args: invoked.append((context.request, args)) or {"id": args["id"]},
    )]))
    return app, invoked, events


def run(app, **kwargs):
    return app.prompt("请查询", session_id="session", principal=SimpleNamespace(
        user_id="alice", tenant_id="tenant-a", permissions=("read",),
    ), **kwargs)


def test_replacement_loop_uses_host_tools_transcript_and_one_run():
    seen = []
    def script(session):
        seen.append(session.snapshot())
        outcomes = session.call_tools([ToolCall("r1", "lookup", {"id": "42"})])
        assert outcomes[0]["content"] == {"id": "42"}
        session.emit_text("已查到")
        session.finish("已查到 42")

    app, invoked, events = application(script)
    try:
        result = run(app, user_id="spoof", tenant_id="spoof")
        assert result.status.value == "succeeded", result.to_dict()
        assert result.reply == "已查到 42"
        assert len(invoked) == 1
        request = invoked[0][0]
        assert (request.user_id, request.tenant_id) == ("alice", "tenant-a")
        assert request.run_id == result.run_id
        assert len([e for e in events if e["type"] == "agent_start"]) == 1
        assert len([e for e in events if e["type"] == "agent_end"]) == 1
        assert any(e["type"] == "model_delta" for e in events)
        assert [m["role"] for m in result.data["messages"]] == ["user", "assistant", "tool", "assistant"]
        assert seen[0].tools[0]["name"] == "lookup"
        assert not hasattr(seen[0], "principal")
        assert app.healthcheck()["engine"]["plugin_id"] == "test.execution-engine"
    finally:
        app.close()


@pytest.mark.parametrize("arguments", [{}, {"id": "42", "extra": 1}])
def test_replacement_tools_still_validate_closed_schema(arguments):
    def script(session):
        rows = session.call_tools([ToolCall("r", "lookup", arguments)])
        assert rows[0]["is_error"]
        session.finish("参数无效")
    app, invoked, _ = application(script)
    try:
        run(app)
        assert invoked == []
    finally:
        app.close()


def test_engine_cannot_expand_explicit_allowlist_or_change_identity():
    def script(session):
        assert session.snapshot().tools == ()
        session.call_tools([ToolCall("r", "lookup", {"id": "42"})])
        pytest.fail("host must stop denied tool plan")
    app, invoked, _ = application(script)
    try:
        result = run(app, tool_allowlist=())
        assert result.status.value == "failed"
        assert result.runtime_signals["tool_allowlist_violation"]
        assert invoked == []
    finally:
        app.close()


def test_checkpoint_failure_revokes_engine_before_next_action():
    captured = []
    def script(session):
        captured.append(session)
        session.call_tools([ToolCall("r", "lookup", {"id": "42"})])
        pytest.fail("checkpoint failure must stop engine")
    app, invoked, _ = application(script, checkpoint_store=SimpleNamespace(save_checkpoint=lambda *_: False))
    try:
        result = run(app)
        assert result.status.value == "recovery_required"
        assert len(invoked) == 1
        with pytest.raises(RuntimeError):
            captured[0].call_tools([ToolCall("late", "lookup", {"id": "other"})])
        assert len(invoked) == 1
    finally:
        app.close()


def test_incomplete_or_failed_engine_never_falls_back_and_preserves_tools():
    def script(session):
        session.call_tools([ToolCall("r", "lookup", {"id": "42"})])
        raise RuntimeError("access_token=private-engine-diagnostic")
    app, invoked, _ = application(script)
    try:
        result = run(app)
        assert result.status.value == "failed"
        assert len(result.data["tool_results"]) == len(invoked) == 1
        assert "private-engine-diagnostic" not in str(result.to_dict())
    finally:
        app.close()


def test_engine_requires_reviewed_plugin_and_tool_policy():
    engine = ScriptEngine(lambda s: s.finish("ok"))
    with pytest.raises(ValueError, match="policy"):
        AgentApplication.create(model=None, engine=engine)
    engine.manifest = manifest(trusted=False, executable=False)
    with pytest.raises(ValueError, match="trusted"):
        AgentApplication.create(model=None, engine=engine, tool_policy=ToolExecutionPolicy())


def test_native_engine_remains_default():
    app = AgentApplication.create(model=lambda *_: ModelTurn(content="原生回复"))
    try:
        assert run(app).reply == "原生回复"
        assert app.healthcheck()["engine"]["plugin_id"] == "harness.native-engine"
    finally:
        app.close()


def test_dynamic_discovery_works_from_sdk_callback_thread():
    from concurrent.futures import ThreadPoolExecutor
    from agents.agent_platform.tools.discovery import tool_discovery_source
    seen = []
    def script(session):
        assert "lookup" not in [t["name"] for t in session.snapshot().tools]
        with ThreadPoolExecutor(max_workers=1) as pool:
            found = pool.submit(session.call_tools, [ToolCall("discover", "agent_discover_tools", {
                "query": "lookup", "resource_type": "record",
            })]).result(timeout=3)
        assert found[0]["content"]["data"]["status"] == "loaded"
        seen.extend(t["name"] for t in session.snapshot().tools)
        session.call_tools([ToolCall("r", "lookup", {"id": "42"})])
        session.finish("已查询")
    app, invoked, _ = application(script, tool_selector=lambda *_: [])
    app.register_tool_source(tool_discovery_source(required_permission="read"))
    try:
        assert run(app).status.value == "succeeded"
        assert "lookup" in seen
        assert len(invoked) == 1
    finally:
        app.close()


def test_engine_timeout_revokes_late_tool_callback_and_retains_capacity():
    import threading
    released, finished = threading.Event(), threading.Event()
    late = []
    def script(session):
        released.wait(3)
        try:
            session.call_tools([ToolCall("late", "lookup", {"id": "42"})])
        except RuntimeError:
            late.append("revoked")
        finally:
            finished.set()
    app, invoked, _ = application(script, engine_timeout_seconds=0.05, max_inflight_model_invocations=1)
    try:
        result = run(app)
        assert result.runtime_signals["model_timeout"]
        assert app.agent._state_for("session", "alice", "tenant-a").is_running is False
        assert run(app).status.value == "failed"  # timed-out worker still occupies its slot
        released.set()
        assert finished.wait(3)
        assert late == ["revoked"]
        assert invoked == []
    finally:
        released.set()
        app.close()


def test_cancel_sdk_wait_releases_run_and_is_scoped_to_principal():
    import threading
    from concurrent.futures import ThreadPoolExecutor
    started, release = threading.Event(), threading.Event()
    def script(session):
        started.set()
        release.wait(3)
    app, invoked, _ = application(script)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(run, app)
            assert started.wait(2)
            assert not app.runtime.cancel_run("session", user_id="mallory", tenant_id="tenant-a")
            assert app.runtime.cancel_run("session", user_id="alice", tenant_id="tenant-a")
            result = running.result(timeout=2)
            assert result.status.value == "cancelled"
        assert invoked == []
    finally:
        release.set()
        app.close()


def test_write_uses_same_live_confirmation_and_audit_gate():
    from agents.agent_harness import RunStatus
    audited, writes = [], []
    def script(session):
        session.call_tools([ToolCall("write", "update_record", {"id": "42"})])
        session.finish("已处理")
    app, _, _ = application(script, tool_policy=ToolExecutionPolicy(
        allow_live_writes=False, audit_sink=audited.append,
    ))
    app.register_tool_source(StaticToolSource("writes", [ToolBinding(
        definition("update_record", "record", effect="write"),
        lambda *_: writes.append("actual effect") or {"success": True},
    )]))
    try:
        result = run(app, execution_mode="live")
        assert result.status != RunStatus.SUCCEEDED
        assert writes == []
        assert audited
    finally:
        app.close()


def test_context_and_transcript_are_bounded_copies_and_tenant_scoped():
    seen = []
    provider = SimpleNamespace(build_context=lambda request, _: {"prompt": f"tenant context: {request.tenant_id}"})
    def script(session):
        snapshot = session.snapshot()
        assert any("tenant context: tenant-a" in str(m["content"]) for m in snapshot.messages)
        seen.append([m["content"] for m in snapshot.messages])
        snapshot.messages[-1]["content"] = "tampered"
        snapshot.tools[0]["input_schema"]["required"] = []
        assert session.snapshot().messages[-1]["content"] != "tampered"
        assert session.snapshot().tools[0]["input_schema"]["required"] == ["id"]
        session.finish("保留历史")
    app, _, _ = application(script, context_provider=provider)
    try:
        assert run(app).status.value == "succeeded"
        assert run(app).status.value == "succeeded"
        assert "保留历史" in seen[-1]
        other = app.prompt("不同租户", session_id="session", principal=SimpleNamespace(
            user_id="alice", tenant_id="tenant-b", permissions=("read",),
        ))
        # The test engine's tenant-a assertion fails; previous tenant history is not exposed.
        assert other.status.value == "failed"
        assert "保留历史" not in str(other.data["messages"])
    finally:
        app.close()


@pytest.mark.parametrize("script,options,signal", [
    (lambda s: s.finish("x" * 2048), {"max_model_output_chars": 1024}, "model_output_limit_exceeded"),
    (lambda s: s.finish("ok", usage={"total_tokens": 20}), {"max_total_tokens": 10}, "budget_exceeded"),
])
def test_engine_output_and_usage_limits(script, options, signal):
    app, _, _ = application(script, **options)
    try:
        result = run(app)
        assert result.status.value == "failed"
        assert result.runtime_signals[signal]
    finally:
        app.close()


def test_engine_return_without_finish_is_failure():
    app, _, _ = application(lambda _: None)
    try:
        assert run(app).status.value == "failed"
    finally:
        app.close()


def test_model_switch_is_explicitly_rejected_for_an_external_engine():
    app, _, _ = application(lambda s: s.finish("ok"))
    try:
        with pytest.raises(ValueError, match="engine"):
            app.configure_model(lambda *_: "different")
    finally:
        app.close()


def test_engine_plugin_lifecycle_closes_once_and_refuses_live_replacement():
    from agents.agent_harness.core.plugins import PluginRegistry, PluginState
    registry, closed = PluginRegistry(), []
    engine = ScriptEngine(lambda s: s.finish("ok"))
    engine.close = lambda: closed.append(True)
    app = AgentApplication.create(model=None, engine=engine, engine_plugins=registry,
                                  tool_policy=ToolExecutionPolicy())
    assert registry.get(engine.manifest.plugin_id).state == PluginState.ACTIVE
    assert app.prompt("hi").status.value == "succeeded"
    with pytest.raises(AttributeError):
        app.agent.engine = ScriptEngine(lambda s: s.finish("different"))
    app.close()
    app.close()
    assert closed == [True]
    assert registry.list(kind="engine") == []


def test_checkpoint_resume_is_host_owned_and_checks_tenant_before_engine():
    called = []
    checkpoint = {
        "tenant_id": "tenant-a", "user_id": "alice", "session_id": "session",
        "messages": [{"role": "user", "content": "需要延续的目标"}], "usage": {},
    }
    def script(session):
        called.append(session.snapshot())
        assert any(m["content"] == "需要延续的目标" for m in called[-1].messages)
        session.finish("已延续")
    app, _, _ = application(script, checkpoint_store=SimpleNamespace(
        load_checkpoint=lambda _: checkpoint,
    ))
    context = {"resume_from_checkpoint": True, "resume_run_id": "prior-run"}
    try:
        result = run(app, context=context)
        assert result.status.value == "succeeded"
        assert len(called) == 1
        checkpoint["tenant_id"] = "different"
        result = run(app, context=context)
        assert result.status.value == "failed"
        assert result.data["error"] == "PermissionError"
        assert len(called) == 1
    finally:
        app.close()


def test_engine_can_not_execute_permission_restricted_tool_or_mutate_its_schema():
    def script(session):
        session.call_tools([ToolCall("secret", "private_lookup", {"id": "42"})])
    app, invoked, _ = application(script)
    app.register_tool_source(StaticToolSource("restricted", [ToolBinding(
        definition("private_lookup", "private", permission="admin"),
        lambda *_: invoked.append("not permitted"),
    )]))
    try:
        result = run(app)
        assert result.status.value == "failed"
        assert invoked == []
        assert "admin" in str(result.data["tool_results"])
    finally:
        app.close()


def test_engine_permission_failure_preserves_interaction_payload():
    interaction = {"kind": "confirmation", "title": "确认写入", "fields": []}
    def script(session):
        session.call_tools([ToolCall("r", "lookup", {"id": "42"})])
    policy = SimpleNamespace(
        before_tool_call=lambda _: {
            "block": True, "reason": "请确认", "terminate": True,
            "needs_confirmation": True, "interaction": interaction,
        },
        after_tool_call=lambda *_: None,
    )
    app, invoked, _ = application(script, tool_policy=policy)
    try:
        result = run(app)
        assert result.status.value == "awaiting_input"
        assert result.needs_input
        assert result.interactions[0]["title"] == "确认写入"
        assert invoked == []
    finally:
        app.close()


def test_external_media_support_is_declared_and_never_silently_dropped():
    from agents.agent_harness import InputMedia
    app, invoked, _ = application(lambda s: s.finish("did not inspect image"))
    try:
        result = run(app, input_media=(InputMedia("img", "photo.png", "image/png", b"test bytes"),))
        assert result.status.value == "failed"
        assert invoked == []
    finally:
        app.close()


@pytest.mark.parametrize("script", [
    lambda s: s.finish(None),
    lambda s: s.call_tools([]),
    lambda s: s.emit_text(None),
    lambda s: s.emit_text("x" * 2000),
])
def test_malformed_or_excess_engine_output_fails_closed(script):
    app, invoked, _ = application(script, max_model_output_chars=1024)
    try:
        assert run(app).status.value == "failed"
        assert invoked == []
    finally:
        app.close()


def test_tool_budget_applies_to_replacement_engine_batches():
    def script(session):
        session.call_tools([ToolCall("1", "lookup", {"id": "1"}), ToolCall("2", "lookup", {"id": "2"})])
    app, invoked, _ = application(script, max_tool_calls_per_run=1)
    try:
        result = run(app)
        assert result.status.value == "failed"
        assert result.data["tool_call_budget_exceeded"]
        assert invoked == []
    finally:
        app.close()
