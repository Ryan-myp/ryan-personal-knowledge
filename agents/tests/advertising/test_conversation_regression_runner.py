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
    assert report["latency_samples"] == 0
    assert report["latency_p95_ms"] is None
    assert "private credential value" not in str(report)


def test_runner_reports_bounded_tool_names_for_flaky_model_cases():
    report = run_suite(
        [RegressionCase(
            id="ambiguous", input="create something",
            assertions={"max_tool_calls": 1},
        )],
        lambda _case: {
            "reply": "Please clarify",
            "results": [
                {"tool": "agent_request_input", "success": True},
                {"tool": "agent_request_input", "success": True},
            ],
        },
        mode="fixture_contract",
    )
    case = report["cases"][0]
    assert case["status"] == "failed"
    assert case["tool_call_count"] == 2
    assert case["tool_names"] == [
        "agent_request_input", "agent_request_input",
    ]


def test_runner_summarizes_only_numeric_phase_timings():
    report = run_suite(
        [RegressionCase(
            id="timed", input="hello", assertions={"reply_nonempty": True},
        )],
        lambda _case: {
            "reply": "done", "results": [],
            "phase_metrics": {
                "run_wall_ms": 24.5, "tool_duration_ms_sum": 5.0,
                "private": "should-not-appear",
            },
            "model_metrics": {
                "duration_ms": 10.0, "prepare_duration_ms": 2.0,
            },
        },
        mode="fixture_contract",
    )
    assert report["cases"][0]["phase_ms"] == {
        "run_wall": 24.5, "tool_duration_sum": 5.0,
        "model": 10.0, "model_prepare": 2.0,
    }
    assert report["phase_p95_ms"]["model"] == 10.0
    assert "should-not-appear" not in str(report)


def test_model_mode_loads_local_configuration_once(monkeypatch, tmp_path):
    from scripts.advertising import run_conversation_regressions as runner

    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([
        {"id": "one", "input": "hello", "assertions": {"reply_nonempty": True}},
    ]))
    calls = []
    monkeypatch.setattr(
        runner, "load_default_local_env",
        lambda: calls.append("loaded"),
        raising=False,
    )
    monkeypatch.setattr(
        runner, "configured_model_adapter",
        lambda: calls.append("configured") or object(),
        raising=False,
    )
    monkeypatch.setattr(
        runner, "_model_response",
        lambda _case, *, model_adapter: {"reply": "hello", "results": []},
    )
    monkeypatch.setattr(
        runner.sys, "argv", ["runner", "--cases", str(cases), "--model-backed"],
    )
    assert runner.main() == 0
    assert calls == ["loaded", "configured"]


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


def test_multi_turn_case_uses_isolated_runtime_history(monkeypatch, tmp_path):
    from scripts.advertising import run_conversation_regressions as runner
    from agents.evals.advertising import skill_up_engine

    sent = []
    monkeypatch.setattr(skill_up_engine, "run", lambda payload, **kwargs: (
        sent.append(payload) or {
            "metadata": {"runtime_result": {"reply": "done", "results": []}},
        }
    ))
    case = RegressionCase(
        id="multi", input="继续 Meta campaign",
        history=["Meta campaign 必须保持 paused", "我们换个话题"],
        assertions={"reply_nonempty": True},
    )
    runner._model_response(case, model_adapter=object())
    assert sent[0]["messages"] == [
        {"role": "user", "content": "Meta campaign 必须保持 paused"},
        {"role": "user", "content": "我们换个话题"},
        {"role": "user", "content": "继续 Meta campaign"},
    ]
    assert sent[0]["workspace"]


def test_holdout_contains_multi_turn_cases_and_no_case_can_set_credentials():
    root = Path(__file__).resolve().parents[3]
    cases = load_cases(root / "agents/evals/advertising/conversation_holdout_cases.json")
    assert any(case.history for case in cases)
    with pytest.raises(ValueError):
        RegressionCase(
            id="bad", input="continue",
            history=["hello"], api_key="untrusted",
        )


def test_history_is_bounded_and_cannot_override_the_current_turn():
    with pytest.raises(ValueError):
        RegressionCase(
            id="bad", input="continue", history=["x"] * 12,
        )
    with pytest.raises(ValueError):
        RegressionCase(
            id="bad", input="continue", history=["x" * 4001],
        )
