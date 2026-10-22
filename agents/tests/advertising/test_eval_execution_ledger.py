import pytest

from agents.agent_platform.evals.regression import RegressionAssertions, evaluate_regression
from agents.evals.advertising.skill_up_engine import _structured_evidence


def test_interaction_tool_is_present_in_eval_calls_even_when_ui_projection_hides_it():
    evidence = _structured_evidence({
        "results": [], "needs_input": True,
        "tool_results": [{
            "tool_call_id": "clarify", "name": "agent_request_input", "is_error": False,
            "content": {"success": True}, "needs_input": True,
            "interaction": {"type": "action_clarification"},
        }],
    })
    assert len(evidence["tool_executions"]) == 1
    assert evidence["tool_executions"][0]["tool"] == "agent_request_input"
    assert evaluate_regression(evidence, RegressionAssertions(
        max_tool_calls=0,
    ))["status"] == "failed"
    assert evaluate_regression(evidence, RegressionAssertions(
        required_tools=["agent_request_input"],
    ))["status"] == "passed"


@pytest.mark.parametrize("signal", [
    "tool_execution_deferred", "duplicate_read_coalesced", "duplicate_write_coalesced",
])
def test_deferred_or_coalesced_rows_cannot_prove_successful_execution(signal):
    evidence = _structured_evidence({
        "results": [{"tool": "write", "success": True}],
        "tool_results": [{
            "name": "write", "tool_call_id": "one", "is_error": False,
            "content": {"success": True}, "runtime_signals": {signal: True},
        }],
    })
    assert evaluate_regression(evidence, RegressionAssertions(
        required_tools=["write"],
    ))["status"] == "failed"

@pytest.mark.parametrize("field", ["needs_input", "needs_confirmation"])
@pytest.mark.parametrize("value", ["false", 0, 1, None, [], {}])
def test_adapter_never_coerces_response_flags_into_boolean_evidence(field, value):
    with pytest.raises(ValueError):
        _structured_evidence({field: value, "results": []})


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_adapter_rejects_non_boolean_tool_success(value):
    with pytest.raises(ValueError):
        _structured_evidence({"results": [{"tool": "search", "success": value}]})


def test_missing_runtime_flag_cannot_be_converted_into_false_evidence():
    evidence = _structured_evidence({"results": []})
    assert evaluate_regression(evidence, RegressionAssertions(
        needs_input=False,
    ))["status"] == "failed"


def test_ledger_never_copies_arguments_results_or_interaction_payloads():
    evidence = _structured_evidence({"tool_results": [{
        "name": "search", "is_error": False,
        "arguments": {"private": "PRIVATE"}, "data": {"private": "PRIVATE"},
        "content": {"success": True, "private": "PRIVATE"},
        "interaction": {"payload": {"private": "PRIVATE"}},
    }]})
    assert evidence["tool_executions"] == [{
        "tool": "search", "success": True, "state": "completed",
    }]
    assert "PRIVATE" not in str(evidence)


@pytest.mark.parametrize("rows", [
    "invalid", [{}], [None],
    [{"name": "valid", "is_error": "false"}],
    [{"name": "valid", "is_error": False, "runtime_signals": "invalid"}],
    [{"name": "valid", "is_error": False}] * 65,
])
def test_malformed_execution_ledgers_fail_closed(rows):
    with pytest.raises((ValueError, KeyError)):
        _structured_evidence({"tool_results": rows})


@pytest.mark.parametrize("row", [
    {"tool": "x", "success": True, "state": "deferred"},
    {"tool": "x", "success": "false", "state": "failed"},
    {"tool": "x", "success": True, "state": "invented"},
])
def test_conflicting_ledger_states_cannot_pass_a_replay_assertion(row):
    with pytest.raises(ValueError):
        evaluate_regression(
            {"tool_executions": [row]}, RegressionAssertions(max_tool_calls=1),
        )


def test_runtime_failure_status_survives_the_eval_adapter():
    evidence = _structured_evidence({
        "status": "failed", "reply": "Model request failed.", "results": [],
    })
    assert evidence["status"] == "failed"
    assert evaluate_regression(
        evidence, RegressionAssertions(reply_nonempty=True),
    )["status"] == "failed"


def test_eval_transcripts_and_artifacts_never_copy_raw_credentials(tmp_path):
    import json
    from agents.evals.advertising.skill_up_engine import _session_result

    result = _session_result(
        session_input={"case_id": "redaction"},
        messages=[{"role": "user", "content": "api_key=PRIVATE_CASE_KEY"}],
        runtime_result={
            "reply": "ready", "results": [],
            "debug_metadata": {"client_secret": "PRIVATE_RUNTIME_SECRET"},
        },
        duration_ms=1, workspace=tmp_path, model_name="fixture",
    )
    artifact = (tmp_path / "outputs/ad-agent-runtime-result.json").read_text(encoding="utf-8")
    assert "PRIVATE_" not in json.dumps(result)
    assert "PRIVATE_" not in artifact
