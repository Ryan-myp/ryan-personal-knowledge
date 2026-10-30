from datetime import datetime, timezone

from scripts.advertising.run_conversation_regressions import RegressionCase


def test_task_release_requires_complete_repeated_current_evidence():
    from agents.agent_platform.evals.task_release import dataset_digest, verify_task_report
    cases = [RegressionCase(id="a", input="x", assertions={"reply_nonempty": True})]
    now = datetime.now(timezone.utc)
    report = {"mode": "model_backed_offline_providers", "complete": True, "release_ready": True,
              "repeats": 3, "cases": [{"id": "a", "attempt": n, "status": "passed", "checks": 1}
                                        for n in range(1, 4)],
              "identity": {"source_sha256": "digest", "dataset_sha256": dataset_digest(cases),
                           "recorded_at": now.isoformat(), "source_unchanged": True}}
    def verify(value):
        return verify_task_report(value, cases, source_sha256="digest", now=now)
    assert verify(report)["status"] == "passed"
    for change in ({"complete": False}, {"mode": "fixture_contract"}, {"repeats": 1},
                   {"cases": report["cases"][:2]}, {"release_ready": False},
                   {"identity": {**report["identity"], "source_sha256": "old"}},
                   {"identity": {**report["identity"], "recorded_at": "2026-01-01T00:00:00+00:00"}},
                   {"identity": {**report["identity"], "source_unchanged": False}}):
        assert verify({**report, **change})["status"] != "passed"


def test_missing_task_report_is_not_a_pass():
    from agents.agent_platform.evals.task_release import verify_task_report
    assert verify_task_report(None, [], source_sha256="digest")["status"] == "not_verified"


def test_long_cases_have_real_checkpoints_and_bounded_inputs():
    from pathlib import Path
    from scripts.advertising.run_conversation_regressions import load_cases
    cases = load_cases(Path("agents/evals/advertising/conversation_holdout_cases.json"))
    long = [case for case in cases if len(case.history) >= 29]
    assert {len(case.history) + 1 for case in long} >= {30, 40, 50}
    assert all(len(case.checkpoints) >= 3 and case.task_forbidden_tools for case in long)
