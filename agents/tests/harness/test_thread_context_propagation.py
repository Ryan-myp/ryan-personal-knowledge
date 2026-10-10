from contextvars import ContextVar

from agents.agent_harness import (
    AgentApplication,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
)


def test_model_timeout_worker_preserves_trusted_request_context():
    mode = ContextVar("test_model_mode", default="dry_run")
    app = AgentApplication.create(model=lambda *_: "done", model_timeout_seconds=2)
    token = mode.set("live")
    try:
        assert app.agent._models.invoke(mode.get) == "live"
    finally:
        mode.reset(token)
        app.close()


def test_parallel_and_timeout_tool_workers_preserve_trusted_request_context():
    mode = ContextVar("test_tool_mode", default="dry_run")
    seen = []

    class Model:
        def complete(self, messages, *_args):
            if any(message.role == "tool" for message in messages):
                return ModelTurn(content="done")
            return ModelTurn(
                tool_calls=(ToolCall("a", "read_a", {}), ToolCall("b", "read_b", {}))
            )

    app = AgentApplication.create(
        model=Model(), tool_execution="parallel", tool_timeout_seconds=2
    )
    app.register_tool_source(
        StaticToolSource(
            "tests",
            [
                ToolBinding(
                    {"name": name}, lambda *_: seen.append(mode.get()) or {"ok": True}
                )
                for name in ("read_a", "read_b")
            ],
        )
    )
    token = mode.set("live")
    try:
        assert app.prompt("read").status.value == "succeeded"
        assert seen == ["live", "live"]
    finally:
        mode.reset(token)
        app.close()
