import pytest

from agents.agent_platform.evals.regression import (
    RegressionAssertions, evaluate_regression,
)


def test_regression_without_executable_assertions_is_ungraded_not_passing():
    result = evaluate_regression({"reply": "answer"}, RegressionAssertions())
    assert result["status"] == "ungraded"


def test_tool_assertions_use_actual_calls_not_the_plan():
    expectation = RegressionAssertions(required_tools=["search_knowledge"], max_tool_calls=1)
    planned = {
        "reply": "answer", "tool_plan": {"local": ["search_knowledge"]},
        "results": [],
    }
    assert evaluate_regression(planned, expectation)["status"] == "failed"
    actual = {
        **planned,
        "results": [{"tool": "search_knowledge", "success": True}],
    }
    assert evaluate_regression(actual, expectation)["status"] == "passed"
    actual["results"].append({"tool": "search_knowledge", "success": True})
    assert evaluate_regression(actual, expectation)["status"] == "failed"


def test_regression_assertions_are_closed_bounded_and_non_executable():
    for fields in (
        {"command": "any command"},
        {"reply_regex": "arbitrary regex"},
        {"max_tool_calls": -1},
        {"required_tools": ["x"] * 65},
    ):
        with pytest.raises(ValueError):
            RegressionAssertions.model_validate(fields)


def test_response_assertions_report_failures_without_copying_the_response():
    expectation = RegressionAssertions(
        reply_contains=["source"], reply_not_contains=["internal"],
        needs_confirmation=True,
    )
    result = evaluate_regression(
        {"reply": "private internal response", "needs_confirmation": False},
        expectation,
    )
    assert result["status"] == "failed"
    assert len(result["failures"]) == 3
    assert "private internal response" not in str(result)


@pytest.mark.parametrize("response", [
    {"results": "bad"}, {"results": {}},
    {"results": ["not an envelope"]}, {"reply": {}}, {"reply": {"bad": "text"}},
])
def test_malformed_replay_evidence_cannot_pass(response):
    with pytest.raises(ValueError):
        evaluate_regression(response, RegressionAssertions(max_tool_calls=0))


def test_empty_reply_cannot_pass_a_conversation_nonempty_assertion():
    expectation = RegressionAssertions(reply_nonempty=True, max_tool_calls=0)
    assert evaluate_regression({"reply": " \n"}, expectation)["status"] == "failed"
    assert evaluate_regression({"reply": "hello"}, expectation)["status"] == "passed"


@pytest.mark.parametrize("field", ["needs_input", "needs_confirmation"])
@pytest.mark.parametrize("value", ["false", "true", 0, 1, None, [], {}])
def test_response_boolean_fields_reject_type_coercion(field, value):
    expectation = RegressionAssertions.model_validate({field: True})
    with pytest.raises(ValueError):
        evaluate_regression({field: value}, expectation)


@pytest.mark.parametrize("field", ["needs_input", "needs_confirmation"])
def test_missing_boolean_evidence_cannot_prove_false(field):
    expectation = RegressionAssertions.model_validate({field: False})
    assert evaluate_regression({"reply": "answer"}, expectation)["status"] == "failed"
    assert evaluate_regression({field: False}, expectation)["status"] == "passed"
