from agents.agent_platform.evals.phase_metrics import PhaseMetrics
from concurrent.futures import ThreadPoolExecutor


def test_phase_metrics_are_numeric_and_do_not_keep_tool_data():
    metrics = PhaseMetrics()
    metrics({"type": "agent_start", "run_id": "run"})
    metrics({"type": "tool_execution_start", "run_id": "run",
             "tool_call_id": "call", "input": "private"})
    metrics({"type": "tool_execution_end", "run_id": "run",
             "tool_call_id": "call", "result": "private"})
    metrics({"type": "agent_end", "run_id": "run"})
    snapshot = metrics.snapshot()
    assert snapshot["runs"] == 1
    assert snapshot["tool_calls"] == 1
    assert snapshot["run_wall_ms"] >= snapshot["tool_duration_ms_sum"] >= 0
    assert "private" not in str(snapshot)


def test_phase_metrics_bound_pending_calls_and_allow_failed_run():
    metrics = PhaseMetrics(max_calls=1)
    metrics({"type": "agent_start", "run_id": "run"})
    metrics({"type": "tool_execution_start", "run_id": "run", "tool_call_id": "1"})
    metrics({"type": "tool_execution_start", "run_id": "run", "tool_call_id": "2"})
    metrics({"type": "agent_end", "run_id": "run", "status": "failed"})
    assert metrics.snapshot()["truncated"] is True
    assert metrics.snapshot()["incomplete_tool_calls"] == 1


def test_phase_metrics_handle_parallel_calls_and_concurrent_snapshots():
    metrics = PhaseMetrics(max_calls=128)
    metrics({"type": "agent_start", "run_id": "run"})

    def record_call(index):
        call = str(index)
        metrics({"type": "tool_execution_start", "run_id": "run",
                 "tool_call_id": call})
        metrics.snapshot()
        metrics({"type": "tool_execution_end", "run_id": "run",
                 "tool_call_id": call})

    with ThreadPoolExecutor(max_workers=16) as workers:
        list(workers.map(record_call, range(100)))
    metrics({"type": "agent_end", "run_id": "run"})
    result = metrics.snapshot()
    assert result["runs"] == 1
    assert result["tool_calls"] == 100
    assert result["incomplete_tool_calls"] == 0
    assert result["truncated"] is False
