from types import SimpleNamespace
import json

from agents.agent_harness import AgentApplication, StaticToolSource, ToolBinding
from agents.agent_harness.messages import ModelTurn, ToolCall
from agents.applications.advertising.run.ad_run_projection import AdvertisingRunProjection


def test_long_query_has_exact_cardinality_and_bounded_model_context():
    rows = [{"id": str(index), "name": "x" * 100} for index in range(100)]

    class Model:
        turn = 0

        def complete(self, messages, _tools, _request):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=(ToolCall("query", "list_records", {}),))
            content = messages[-1].content
            summary = content["data"]["query_summary"]
            assert summary["returned_count"] == 100
            assert summary["context_count"] == len(content["data"].get("records", []))
            assert summary["context_truncated"] is True
            return ModelTurn(content="Returned 100 records; displaying a preview.")

    app = AgentApplication.create(model=Model(), max_tool_result_chars=800)
    app.register_tool_source(StaticToolSource("queries", [ToolBinding(
        {"name": "list_records", "effect_class": "read", "result_items_key": "records"},
        lambda _context, _arguments: {"success": True, "data": {"records": rows}},
    )]))
    try:
        result = app.prompt("List records.")
        assert result.status.value == "succeeded", result.to_dict()
        assert len(result.data["tool_results"][0]["data"]["records"]) == 100
    finally:
        app.close()


def test_application_projection_uses_complete_data_not_the_model_preview():
    runtime = SimpleNamespace(
        _sessions={}, registry=SimpleNamespace(get=lambda _name: (None, None)),
    )
    projection = AdvertisingRunProjection.application_state_from_run(runtime, {
        "tool_results": [{
            "name": "list_records",
            "content": {
                "success": True, "data": {"records": [{"id": "1"}]},
                "output_truncated": True, "truncated_fields": ["data.records"],
            },
            "data": {"records": [{"id": "1"}, {"id": "2"}]},
            "is_error": False,
        }],
    }, "session", "List records.")
    row = projection["last_results"][0]
    assert len(row["data"]["records"]) == 2
    assert row["model_context_truncated"] is True
    assert "output_truncated" not in row


def test_retained_query_evidence_still_obeys_the_tool_byte_limit():
    class Model:
        turn = 0

        def complete(self, *_args):
            self.turn += 1
            if self.turn == 1:
                return ModelTurn(tool_calls=(ToolCall("query", "list_records", {}),))
            return ModelTurn(content="Results are bounded.")

    app = AgentApplication.create(model=Model())
    app.register_tool_source(StaticToolSource("queries", [ToolBinding(
        {"name": "list_records", "effect_class": "read", "max_output_bytes": 512},
        lambda *_args: {"success": True, "data": {
            "records": [{"id": str(index), "name": "\u4f60" * 100} for index in range(20)],
        }},
    )]))
    try:
        result = app.prompt("List records.")
        data = result.data["tool_results"][0]["data"]
        assert data["output_truncated"] is True
        assert len(json.dumps(data, ensure_ascii=False).encode("utf-8")) <= 512
    finally:
        app.close()
