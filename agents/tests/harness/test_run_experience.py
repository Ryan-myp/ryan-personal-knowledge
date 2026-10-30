from agents.agent_harness.observability import InMemoryMetrics


def test_experience_distinguishes_progress_text_and_completion(monkeypatch):
    from agents.agent_harness import run_experience
    now = [0.0]
    monkeypatch.setattr(run_experience.time, "monotonic", lambda: now[0])
    metrics = InMemoryMetrics()
    def emit(kind, **fields):
        metrics.observe({"type": kind, "run_id": "r", **fields})
    emit("agent_start")
    now[0] = 1
    emit("model_start", message_chars=1200)
    emit("model_reasoning_delta", delta="PRIVATE reasoning")
    now[0] = 2
    emit("tool_execution_start", tool_call_id="t")
    now[0] = 4
    emit("model_start", message_chars=1500)
    emit("model_delta", delta="答案")
    now[0] = 5
    emit("agent_end", status="succeeded")
    snapshot = metrics.snapshot()["experience"]
    assert snapshot["first_progress_ms"]["p95"] == 2000
    assert snapshot["first_text_ms"]["p95"] == 4000
    assert snapshot["total_ms"]["p95"] == 5000
    assert snapshot["model_attempts"]["p95"] == 2
    assert snapshot["prompt_chars_peak"]["p95"] == 1500
    assert "PRIVATE" not in str(snapshot)
    metrics.reset()
    assert metrics.snapshot()["experience"]["total_ms"]["samples"] == 0


def test_experience_no_text_is_missing_not_zero_and_state_is_bounded():
    from agents.agent_harness.run_experience import RunExperienceMetrics
    metrics = RunExperienceMetrics(capacity=2)
    for run in ("a", "b", "c"):
        metrics.observe({"type": "agent_start", "run_id": run})
    metrics.observe({"type": "agent_end", "run_id": "a", "status": "cancelled"})
    snap = metrics.snapshot()
    assert snap["dropped_runs"] == 1
    assert snap["active_runs"] == 1
    assert snap["first_text_ms"]["p95"] is None
    assert snap["total_ms"]["samples"] == 1


def test_nonstreaming_content_counts_but_empty_delta_does_not(monkeypatch):
    from agents.agent_harness.run_experience import RunExperienceMetrics
    metrics = RunExperienceMetrics()
    metrics.observe({"type": "agent_start", "run_id": "r"})
    metrics.observe({"type": "model_delta", "run_id": "r", "delta": " "})
    metrics.observe({"type": "model_end", "run_id": "r", "has_content": True})
    metrics.observe({"type": "agent_end", "run_id": "r"})
    assert metrics.snapshot()["first_text_ms"]["samples"] == 1
