import threading
import time

from agents.agent_harness import (
    AgentApplication,
    AgentMessage,
    AgentState,
    ModelTurn,
    ToolCall,
    ToolCallContext,
    TurnRequest,
)
from agents.agent_platform.tools.policy import ToolExecutionPolicy
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.persistence.adapters import (
    PersistenceIdempotencyStore,
)


class _TranscriptStore:
    def __init__(self):
        self.messages = {}
        self.lock = threading.RLock()

    def load(self, session_id, *, tenant_id, user_id, limit=200):
        with self.lock:
            return list(self.messages.get((tenant_id, user_id, session_id), ()))

    def append(self, session_id, messages, *, tenant_id, user_id):
        with self.lock:
            key = (tenant_id, user_id, session_id)
            self.messages.setdefault(key, []).extend(messages)

    def clear(self, session_id, *, tenant_id, user_id):
        with self.lock:
            self.messages.pop((tenant_id, user_id, session_id), None)


def test_sql_idempotency_is_cross_store_and_hash_bound(tmp_path):
    path = tmp_path / "idempotency.db"
    first = PersistenceIdempotencyStore(AdAgentStore(str(path)))
    second = PersistenceIdempotencyStore(AdAgentStore(str(path)))

    assert first.reserve("tenant:user:tool:key", request_hash="hash-a", ttl_seconds=60)
    assert not second.reserve(
        "tenant:user:tool:key", request_hash="hash-a", ttl_seconds=60,
    )
    assert not second.reserve(
        "tenant:user:tool:key", request_hash="hash-b", ttl_seconds=60,
    )
    second.release("tenant:user:tool:key", request_hash="hash-a")
    assert second.reserve("tenant:user:tool:key", request_hash="hash-b", ttl_seconds=60)
    second.mark_executed("tenant:user:tool:key", request_hash="hash-b")
    assert not first.reserve(
        "tenant:user:tool:key", request_hash="hash-b", ttl_seconds=60,
    )


def test_sql_idempotency_allows_only_one_concurrent_reservation(tmp_path):
    path = tmp_path / "concurrent-idempotency.db"
    stores = [
        PersistenceIdempotencyStore(AdAgentStore(str(path)))
        for _ in range(2)
    ]
    results = []
    barrier = threading.Barrier(2)

    def reserve(store):
        barrier.wait()
        results.append(store.reserve(
            "same-key", request_hash="same-request", ttl_seconds=60,
        ))

    threads = [threading.Thread(target=reserve, args=(store,)) for store in stores]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
    assert sorted(results) == [False, True]


def test_tool_policy_uses_durable_idempotency_across_runs(tmp_path):
    definition = {
        "name": "update_record",
        "effect_class": "write",
        "live_support": True,
        "idempotency_key_field": "request_id",
        "input_schema": {
            "type": "object",
            "required": ["request_id"],
            "properties": {"request_id": {"type": "string"}},
        },
    }
    path = tmp_path / "policy.db"
    policy = ToolExecutionPolicy(
        allow_live_writes=True,
        live_approved_tools={"update_record"},
        write_guard_configured=True,
        require_confirmation_for_writes=True,
        idempotency_store=PersistenceIdempotencyStore(AdAgentStore(str(path))),
    )

    def context(run_id, turn_id):
        from agents.agent_harness import AgentState, ToolCallContext

        return ToolCallContext(
            request=TurnRequest(
                user_input="update",
                user_id="user-1",
                tenant_id="tenant-1",
                run_id=run_id,
                turn_id=turn_id,
                execution_mode="live",
                context={
                    "confirmed": True,
                    "confirmation_payload": {"plan": "current"},
                },
            ),
            assistant_message=AgentMessage.assistant(""),
            tool_call=ToolCall("call", "update_record", {"request_id": "same"}),
            state=AgentState(),
            tool_definition=definition,
        )

    first = context("run-1", "turn-1")
    assert policy.before_tool_call(first) is None
    policy.after_tool_call(first, {"is_error": False})

    second = context("run-2", "turn-2")
    blocked = policy.before_tool_call(second)
    assert blocked is not None
    assert blocked["reason"].startswith("Duplicate")


def test_live_write_fails_closed_without_durable_idempotency_store():
    policy = ToolExecutionPolicy(
        allow_live_writes=True,
        live_approved_tools={"update_record"},
        write_guard_configured=True,
        require_confirmation_for_writes=True,
    )
    context = ToolCallContext(
        request=TurnRequest(
            user_input="update",
            execution_mode="live",
            context={
                "confirmed": True,
                "confirmation_payload": {"plan": "current"},
            },
        ),
        assistant_message=AgentMessage.assistant(""),
        tool_call=ToolCall("call-1", "update_record", {"request_id": "same"}),
        state=AgentState(),
        tool_definition={
            "name": "update_record",
            "effect_class": "write",
            "live_support": True,
            "idempotency_key_field": "request_id",
            "input_schema": {
                "type": "object",
                "required": ["request_id"],
                "properties": {"request_id": {"type": "string"}},
            },
        },
    )

    result = policy.before_tool_call(context)

    assert result is not None
    assert result["runtime_signals"]["idempotency_store_error"] is True


def test_transcript_store_restores_across_application_instances():
    store = _TranscriptStore()
    seen = []

    class Model:
        def complete(self, messages, _tools, _request):
            seen.append([message.content for message in messages])
            return "done"

    first = AgentApplication.create(model=Model(), transcript_store=store)
    first.prompt("first", session_id="session-1", user_id="user-1", tenant_id="tenant-1")
    first.close()

    second = AgentApplication.create(model=Model(), transcript_store=store)
    result = second.prompt(
        "second", session_id="session-1", user_id="user-1", tenant_id="tenant-1",
    )
    try:
        assert result.status.value == "succeeded"
        assert "first" in seen[-1]
        assert "second" in seen[-1]
    finally:
        second.close()


def test_transcript_store_keeps_tenant_and_user_scopes_separate():
    store = _TranscriptStore()
    seen = []

    class Model:
        def complete(self, messages, _tools, _request):
            seen.append([message.content for message in messages])
            return "done"

    app = AgentApplication.create(model=Model(), transcript_store=store)
    try:
        app.prompt("private", session_id="same", user_id="u1", tenant_id="t1")
        app.prompt("other", session_id="same", user_id="u2", tenant_id="t1")
        assert "private" not in seen[-1]
    finally:
        app.close()


def test_reset_clears_durable_transcript_when_the_store_supports_clear():
    store = _TranscriptStore()
    seen = []

    class Model:
        def complete(self, messages, _tools, _request):
            seen.append([message.content for message in messages])
            return "done"

    app = AgentApplication.create(model=Model(), transcript_store=store)
    try:
        app.prompt("old", session_id="reset-session", user_id="u1", tenant_id="t1")
        app.agent.reset(
            "reset-session",
            user_id="u1",
            tenant_id="t1",
        )
    finally:
        app.close()

    second = AgentApplication.create(model=Model(), transcript_store=store)
    try:
        second.prompt(
            "new",
            session_id="reset-session",
            user_id="u1",
            tenant_id="t1",
        )
        assert "old" not in seen[-1]
        assert "new" in seen[-1]
    finally:
        second.close()


def test_forget_session_drops_only_the_in_memory_working_window():
    store = _TranscriptStore()
    seen = []

    class Model:
        def complete(self, messages, _tools, _request):
            seen.append([message.content for message in messages])
            return "done"

    app = AgentApplication.create(model=Model(), transcript_store=store)
    try:
        app.prompt("old", session_id="forget-session", user_id="u1", tenant_id="t1")
        store.clear("forget-session", tenant_id="t1", user_id="u1")
        app.runtime.forget_session(
            "forget-session",
            user_id="u1",
            tenant_id="t1",
        )
        app.prompt("new", session_id="forget-session", user_id="u1", tenant_id="t1")
        assert "old" not in seen[-1]
        assert "new" in seen[-1]
    finally:
        app.close()


def test_streaming_emits_deltas_and_only_executes_tools_after_final_turn():
    events = []

    class StreamingModel:
        def stream(self, _messages, _tools, _request):
            yield {"delta": "hel"}
            yield {"delta": "lo"}
            yield ModelTurn(content="hello", stop_reason="stop")

    app = AgentApplication.create(model=StreamingModel(), event_callback=events.append)
    try:
        result = app.prompt("say hello", streaming=True)
        assert result.reply == "hello"
        assert [event["delta"] for event in events if event["type"] == "model_delta"] == [
            "hel", "lo",
        ]
        assert events[-1]["type"] == "agent_end"
    finally:
        app.close()


def test_model_budget_is_enforced_from_provider_usage():
    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(
                content="too much",
                usage={"input_tokens": 4, "output_tokens": 7, "total_tokens": 11},
            )

    app = AgentApplication.create(model=Model(), max_total_tokens=10)
    try:
        result = app.prompt("budget")
        assert result.status.value == "failed"
        assert result.runtime_signals["budget_exceeded"] is True
        assert result.data["usage"]["total_tokens"] == 11
    finally:
        app.close()


def test_model_timeout_and_retryable_fallback_are_explicit():
    class Slow:
        def complete(self, _messages, _tools, _request):
            time.sleep(0.05)
            return "late"

    class Fallback:
        def complete(self, _messages, _tools, _request):
            return "fallback"

    events = []
    app = AgentApplication.create(
        model=Slow(),
        model_fallbacks=(Fallback(),),
        model_timeout_seconds=0.01,
        event_callback=events.append,
    )
    try:
        result = app.prompt("fallback")
        assert result.reply == "fallback"
        assert any(event["type"] == "model_fallback" for event in events)
        assert any(event["type"] == "model_error" for event in events)
    finally:
        app.close()


def test_request_cancellation_stops_before_the_next_model_turn():
    cancelled = threading.Event()
    calls = []

    class Model:
        def complete(self, _messages, _tools, _request):
            calls.append("model")
            if len(calls) == 1:
                return ModelTurn(
                    content="",
                    tool_calls=(ToolCall("call-1", "cancel_after_tool", {}),),
                )
            return "should not run"

    class Tool:
        def execute(self, _context, _arguments):
            cancelled.set()
            return {"ok": True}

    from agents.agent_harness import StaticToolSource, ToolBinding

    app = AgentApplication.create(
        model=Model(),
        tool_execution="sequential",
    )
    app.register_tool_source(StaticToolSource(
        "test",
        [ToolBinding({"name": "cancel_after_tool"}, Tool())],
    ))
    try:
        result = app.prompt(
            "cancel",
            cancellation_event=cancelled,
        )
        assert result.status.value == "cancelled"
        assert calls == ["model"]
    finally:
        app.close()


def test_lease_loss_is_recovery_required_before_next_model_turn():
    lease_lost = threading.Event()
    calls = []

    class Model:
        def complete(self, _messages, _tools, _request):
            calls.append("model")
            if len(calls) == 1:
                return ModelTurn(
                    content="",
                    tool_calls=(ToolCall("call-1", "lose_lease", {}),),
                )
            return "should not run"

    class Tool:
        def execute(self, _context, _arguments):
            lease_lost.set()
            return {"ok": True}

    from agents.agent_harness import StaticToolSource, ToolBinding

    app = AgentApplication.create(model=Model(), tool_execution="sequential")
    app.register_tool_source(StaticToolSource(
        "test",
        [ToolBinding({"name": "lose_lease"}, Tool())],
    ))
    try:
        result = app.prompt(
            "lease",
            lease_lost_event=lease_lost,
        )
        assert result.status.value == "recovery_required"
        assert result.recovery_required is True
        assert result.runtime_signals["session_lease_lost"] is True
        assert calls == ["model"]
    finally:
        app.close()


def test_stream_iteration_is_bounded_by_model_timeout():
    class HangingStream:
        def stream(self, _messages, _tools, _request):
            yield {"delta": "start"}
            time.sleep(0.05)
            yield {"delta": "never observed"}

    app = AgentApplication.create(
        model=HangingStream(),
        model_timeout_seconds=0.01,
    )
    started = time.monotonic()
    try:
        result = app.prompt("stream", streaming=True)
    finally:
        app.close()
    assert time.monotonic() - started < 0.2
    assert result.status.value == "failed"
    assert result.runtime_signals["model_timeout"] is True


def test_model_budget_is_scoped_to_one_run_not_the_whole_session():
    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(
                content="ok",
                usage={"input_tokens": 3, "output_tokens": 3, "total_tokens": 6},
            )

    app = AgentApplication.create(model=Model(), max_total_tokens=6)
    try:
        first = app.prompt("one", session_id="budget-session")
        second = app.prompt("two", session_id="budget-session")
        assert first.status.value == "succeeded"
        assert second.status.value == "succeeded"
        assert second.data["usage"]["total_tokens"] == 6
    finally:
        app.close()


def test_tool_policy_hook_failure_requires_recovery():
    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(
                content="",
                tool_calls=(ToolCall("call-1", "protected_tool", {}),),
            )

    class Tool:
        def execute(self, _context, _arguments):
            raise AssertionError("policy hook should run before the Tool")

    from agents.agent_harness import StaticToolSource, ToolBinding

    app = AgentApplication.create(
        model=Model(),
        before_tool_call=lambda _context: (_ for _ in ()).throw(
            RuntimeError("policy unavailable")
        ),
    )
    app.register_tool_source(StaticToolSource(
        "test",
        [ToolBinding({"name": "protected_tool"}, Tool())],
    ))
    try:
        result = app.prompt("protected")
        assert result.status.value == "recovery_required"
        assert result.recovery_required is True
        assert result.runtime_signals["tool_policy_error"] is True
    finally:
        app.close()


def test_tool_output_is_bounded_before_it_enters_the_next_model_turn():
    seen_tool_content = []

    class Model:
        def complete(self, messages, _tools, _request):
            if any(message.role == "tool" for message in messages):
                seen_tool_content.append(
                    next(message.content for message in messages if message.role == "tool")
                )
                return "done"
            return ModelTurn(
                content="",
                tool_calls=(ToolCall("call-1", "large_tool", {}),),
            )

    class Tool:
        def execute(self, _context, _arguments):
            return "x" * 200

    from agents.agent_harness import StaticToolSource, ToolBinding

    app = AgentApplication.create(
        model=Model(),
        max_tool_result_chars=32,
    )
    app.register_tool_source(StaticToolSource(
        "test",
        [ToolBinding({"name": "large_tool"}, Tool())],
    ))
    try:
        result = app.prompt("large")
        assert result.status.value == "succeeded"
        assert len(seen_tool_content) == 1
        assert len(seen_tool_content[0]) <= 32
        assert "truncated" in seen_tool_content[0]
    finally:
        app.close()
