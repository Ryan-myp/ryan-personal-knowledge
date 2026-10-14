"""A final model reply must not hide earlier Tool failures in the same Run."""

import pytest

from agents.agent_harness import AgentApplication, StaticToolSource, ToolBinding, TurnRequest
from agents.agent_harness.messages import ModelTurn, ToolCall
from agents.agent_harness.results import RunResult


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    (([False], "failed"), ([True, False], "partially_failed"), ([True], "succeeded")),
)
def test_final_reply_preserves_outcome_of_all_executed_tools(outcomes, expected):
    class Model:
        def __init__(self):
            self.turn = 0

        def complete(self, _messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=tuple(
                    ToolCall(str(index), f"read_{index}", {})
                    for index in range(len(outcomes))
                ))
            return ModelTurn(content="Completed the query.")

    app = AgentApplication.create(model=Model(), tool_max_retries=0)
    app.register_tool_source(StaticToolSource("queries", [
        ToolBinding(
            {"name": f"read_{index}", "effect_class": "read"},
            lambda _ctx, _args, success=success: {
                "success": success,
                **({"data": {"items": [1]}} if success else {"error": "Provider unavailable"}),
            },
        )
        for index, success in enumerate(outcomes)
    ]))
    try:
        result = app.runtime.run(TurnRequest(user_input="Read records."))
        assert result.status.value == expected
        assert len(result.data["tool_results"]) == len(outcomes)
    finally:
        app.close()


def test_payload_success_status_cannot_override_failed_tool_evidence():
    result = RunResult.from_payload({
        "status": "succeeded",
        "results": [{"success": False, "error": "Provider timed out"}],
    })
    assert result.status.value == "failed"
