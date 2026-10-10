from agents.agent_harness import (
    AgentApplication,
    ModelTurn,
    StaticToolSource,
    ToolBinding,
    ToolCall,
)


def test_model_failure_after_tool_execution_preserves_completed_result():
    class RateLimitError(RuntimeError):
        pass

    class Model:
        def complete(self, messages, *_args):
            if any(message.role == "tool" for message in messages):
                raise RateLimitError("model unavailable after execution")
            return ModelTurn(tool_calls=(ToolCall("created", "read_example", {}),))

    app = AgentApplication.create(model=Model())
    app.register_tool_source(
        StaticToolSource(
            "tests",
            [
                ToolBinding(
                    {"name": "read_example"},
                    lambda *_: {"success": True, "data": {"id": "verified-result"}},
                ),
            ],
        )
    )
    try:
        result = app.prompt("run")
        assert result.status.value == "failed"
        assert result.data["tool_results"][0]["data"]["id"] == "verified-result"
    finally:
        app.close()
