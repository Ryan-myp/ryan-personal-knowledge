from agents.agent_platform.benchmarks.runtime_load import run_load


def test_generic_run_load_reports_measured_concurrency_and_latency():
    report = run_load(iterations=12, concurrency=3)
    assert report["scope"] == "offline_generic_run"
    assert report["iterations"] == 12
    assert report["concurrency"] == 3
    assert report["completed"] == 12
    assert report["failed"] == 0
    assert report["provider_calls"] == 0
    assert report["latency_ms"]["p95"] >= report["latency_ms"]["p50"] >= 0
    assert report["throughput_runs_per_second"] > 0
    assert report["production_capacity_attested"] is False
