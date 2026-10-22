import json
from pathlib import Path

import pytest

from scripts.advertising.run_conversation_regressions import (
    RegressionCase, load_cases, run_suite,
)


def test_manual_expectations_are_not_automatically_marked_as_passed():
    called = []
    cases = [
        RegressionCase(id="manual", input="hello", expected_behavior="Be helpful"),
        RegressionCase(id="checked", input="hello", assertions={"max_tool_calls": 0}),
    ]
    report = run_suite(
        cases, lambda case: called.append(case.id) or {"reply": "hello"},
        mode="fixture_contract",
    )
    assert called == ["checked"]
    assert report["ungraded"] == 1
    assert report["passed"] == 1
    assert report["gate_passed"] is False
    assert report["provider_e2e"] is False
    assert report["latency_samples"] == 1
    assert report["latency_p95_ms"] >= 0


def test_runner_reports_errors_without_echoing_private_exception_message():
    def execute(_case):
        raise RuntimeError("private credential value")

    report = run_suite(
        [RegressionCase(id="case", input="hello", assertions={"max_tool_calls": 0})],
        execute, mode="fixture_contract",
    )
    assert report["error"] == 1
    assert "private credential value" not in str(report)


def test_dataset_rejects_duplicate_ids_and_executable_fields(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([
        {"id": "same", "input": "one"}, {"id": "same", "input": "two"},
    ]))
    with pytest.raises(ValueError, match="unique"):
        load_cases(path)
    path.write_text(json.dumps([{"id": "one", "input": "one", "command": "bad"}]))
    with pytest.raises(ValueError):
        load_cases(path)


def test_checked_in_conversation_benchmark_has_executable_conditions():
    root = Path(__file__).resolve().parents[3]
    cases = load_cases(root / "agents/evals/advertising/conversation_regression_cases.json")
    assert len(cases) >= 8
    assert all(case.assertions.executable for case in cases)
