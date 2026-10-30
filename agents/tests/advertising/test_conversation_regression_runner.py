import json
from pathlib import Path

import pytest

from scripts.advertising.run_conversation_regressions import (
    RegressionCase, load_cases, run_suite,
)


def test_repeated_suite_keeps_every_failure_and_does_not_inflate_unique_coverage():
    from scripts.advertising.run_conversation_regressions import ReleaseGate
    responses = iter([{"reply": "ok"}, {"reply": "bad"}, {"reply": "ok"}])
    case = RegressionCase(id="repeat", input="hello", assertions={"reply_contains": ["ok"]})
    report = run_suite([case], lambda _: next(responses), mode="model_backed_offline_providers",
                       repeats=3, release_gate=ReleaseGate(min_cases=2, max_p95_ms=10000))
    assert report["passed"] == 2 and report["failed"] == 1
    assert report["unique_cases"] == 1 and report["repeats"] == 3
    assert not report["release_ready"]
    assert "insufficient_samples" in report["release_blockers"]
    assert [row["attempt"] for row in report["cases"]] == [1, 2, 3]


def test_repeat_budget_is_bounded():
    with pytest.raises(ValueError):
        run_suite([], lambda _: {}, mode="fixture_contract", repeats=1000)


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


def test_runner_retains_failure_state_without_copying_private_content():
    report = run_suite([
        RegressionCase(id="scope", input="report", assertions={"required_tools": ["read_report"]}),
    ], lambda _case: {
        "reply": "PRIVATE account selection detail", "status": "awaiting_input", "needs_input": True,
        "tool_executions": [{"tool": "read_report", "success": False, "state": "failed"}],
    }, mode="fixture_contract")
    assert report["cases"][0]["runtime_state"] == {"status": "awaiting_input", "needs_input": True}
    assert report["cases"][0]["execution_states"] == ["failed"]
    assert report["cases"][0]["tool_execution_evidence"] == [{
        "tool": "read_report", "success": False, "state": "failed",
    }]
    assert "PRIVATE" not in str(report)


def test_interrupted_suite_preserves_completed_cases_without_a_passing_report(tmp_path, capsys):
    from scripts.advertising.run_conversation_regressions import RegressionProgressWriter

    path = tmp_path / "progress.json"
    cases = [RegressionCase(
        id=name, input="private user input", assertions={"reply_nonempty": True},
    ) for name in ("first", "second")]

    def execute(case):
        if case.id == "second":
            raise KeyboardInterrupt()
        return {"reply": "done"}

    writer = RegressionProgressWriter(path, total=2, mode="fixture_contract")
    with pytest.raises(KeyboardInterrupt):
        run_suite(cases, execute, mode="fixture_contract", on_case_complete=writer.record)

    partial = json.loads(path.read_text())
    assert partial["complete"] is False
    assert partial["gate_passed"] is False
    assert partial["release_ready"] is False
    assert partial["completed_cases"] == 1
    assert [row["id"] for row in partial["cases"]] == ["first"]
    assert "private user input" not in path.read_text() + capsys.readouterr().err


def test_progress_report_replace_failure_preserves_previous_file_and_cleans_temp(tmp_path, monkeypatch):
    from scripts.advertising.run_conversation_regressions import _write_report

    target = tmp_path / "report.json"
    target.write_text("previous report")

    def unavailable(*_args):
        raise OSError("disk failure")

    monkeypatch.setattr(Path, "replace", unavailable)
    with pytest.raises(OSError):
        _write_report(target, "new report")
    assert target.read_text() == "previous report"
    assert list(tmp_path.iterdir()) == [target]


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


def test_runner_ignores_unbounded_timing_values_in_replay_evidence():
    report = run_suite(
        [RegressionCase(
            id="timed", input="hello", assertions={"reply_nonempty": True},
        )],
        lambda _case: {
            "reply": "done",
            "phase_metrics": {"run_wall_ms": 10 ** 1000},
        },
        mode="replay_assertions",
    )
    assert report["cases"][0]["phase_ms"] == {}
    assert report["cases"][0]["status"] == "passed"
    from scripts.advertising.run_conversation_regressions import ReleaseGate
    with pytest.raises(ValueError):
        ReleaseGate(min_cases=1, max_p95_ms=10 ** 1000)


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
    assert {"holdout-budget-revision", "holdout-budget-retraction"} <= {
        case.id for case in cases
    }
    with pytest.raises(ValueError):
        RegressionCase(
            id="bad", input="continue",
            history=["hello"], api_key="untrusted",
        )


def test_history_is_bounded_and_cannot_override_the_current_turn():
    with pytest.raises(ValueError):
        RegressionCase(
            id="bad", input="continue", history=["x"] * 50,
        )
    with pytest.raises(ValueError):
        RegressionCase(
            id="bad", input="continue", history=["x" * 4001],
        )


def test_release_gate_requires_model_evidence_sample_count_and_latency():
    from scripts.advertising.run_conversation_regressions import ReleaseGate

    cases = [
        RegressionCase(id=f"case-{index}", input="hello",
                       assertions={"reply_nonempty": True})
        for index in range(2)
    ]
    gate = ReleaseGate(min_cases=2, max_p95_ms=1000)
    response = lambda _case: {"reply": "ok"}
    replay = run_suite(cases, response, mode="replay_assertions",
                       release_gate=gate)
    assert replay["gate_passed"] is True
    assert replay["release_ready"] is False
    assert "model_backed_required" in replay["release_blockers"]
    model = run_suite(cases, response, mode="model_backed_offline_providers",
                      release_gate=gate)
    assert model["release_ready"] is True
    assert run_suite(cases[:1], response, mode="model_backed_offline_providers",
                     release_gate=gate)["release_ready"] is False
    assert run_suite(cases, response, mode="model_backed_offline_providers",
                     release_gate=ReleaseGate(min_cases=2, max_p95_ms=0)
                     )["release_ready"] is False


def test_release_gate_cannot_run_in_replay_mode(monkeypatch, tmp_path):
    from scripts.advertising import run_conversation_regressions as runner

    path = tmp_path / "cases.json"
    path.write_text(json.dumps([
        {"id": "one", "input": "hello", "assertions": {"reply_nonempty": True}},
    ]))
    monkeypatch.setattr(runner.sys, "argv", [
        "runner", "--cases", str(path), "--responses", str(path),
        "--release-gate", "--max-p95-ms", "1000",
    ])
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2
