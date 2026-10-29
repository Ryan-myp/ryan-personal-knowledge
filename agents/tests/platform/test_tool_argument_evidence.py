"""Parameter assertions require matching, successful invocation evidence."""

import pytest

from agents.agent_platform.evals.execution_evidence import argument_fingerprints, ToolArgumentEvidence
from agents.agent_platform.evals.regression import RegressionAssertions, evaluate_regression


def test_correct_tool_with_wrong_parameters_does_not_pass():
    assertions = RegressionAssertions(tool_arguments=[{
        "tool": "read_report", "equals": {"account_id": "test-account", "effective_status": ["PAUSED"]},
    }])
    row = {"tool": "read_report", "success": True, "state": "completed"}
    for arguments, expected in (
        ({"account_id": "wrong", "effective_status": ["PAUSED"]}, "failed"),
        ({"account_id": "test-account", "effective_status": ["PAUSED"]}, "passed"),
    ):
        result = evaluate_regression({"tool_executions": [{
            **row, "argument_fingerprints": argument_fingerprints(arguments),
        }]}, assertions)
        assert result["status"] == expected
        assert "test-account" not in str(result)


def test_missing_failed_or_split_parameter_evidence_cannot_pass():
    assertions = RegressionAssertions(tool_arguments=[{
        "tool": "read_report", "equals": {"account_id": "a", "date_preset": "yesterday"},
    }])
    rows = [{"tool": "read_report", "success": True, "state": "completed",
             "argument_fingerprints": argument_fingerprints(values)} for values in (
        {"account_id": "a"}, {"date_preset": "yesterday"},
    )]
    assert evaluate_regression({"tool_executions": rows}, assertions)["status"] == "failed"
    rows = [{"tool": "read_report", "success": False, "state": "failed",
             "argument_fingerprints": argument_fingerprints({"account_id": "a", "date_preset": "yesterday"})}]
    assert evaluate_regression({"tool_executions": rows}, assertions)["status"] == "failed"


@pytest.mark.parametrize("values", [
    {"client_secret": "PRIVATE"}, {"query": "access_token=PRIVATE"},
    {"a": "x" * 5000}, {}, {"a": float("nan")},
])
def test_unsafe_or_unbounded_parameter_assertions_are_rejected(values):
    with pytest.raises(ValueError):
        RegressionAssertions(tool_arguments=[{"tool": "read_report", "equals": values}])


def test_collector_retains_only_bounded_fingerprints_and_clears_between_turns():
    collector = ToolArgumentEvidence()
    collector({"type": "tool_execution_start", "tool_call_id": "call", "tool_name": "read",
               "arguments": {"query": "private user query", "client_secret": "PRIVATE"}})
    rows = collector.enrich([{"name": "read", "tool_call_id": "call"}])
    assert rows[0]["argument_fingerprints"] == argument_fingerprints({"query": "private user query"})
    assert "PRIVATE" not in str(rows)
    assert "private user query" not in str(rows)
    collector.clear()
    assert "argument_fingerprints" not in collector.enrich([{"name": "read", "tool_call_id": "call"}])[0]
