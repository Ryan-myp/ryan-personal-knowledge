from agents.ad_agent.scripts.performance_benchmark import bounded_iterations, run_benchmark


def test_offline_benchmark_is_bounded_and_never_calls_provider():
    report = run_benchmark(2)
    assert report["iterations"] == 2
    assert report["failed_iterations"] == 0
    assert report["provider_calls"] == 0
    assert report["network_called"] is False
    assert report["max_observed_tool_calls"] <= report["configured_tool_call_limit"]


def test_offline_benchmark_clamps_unbounded_iteration_request():
    assert bounded_iterations(10000) == 100
    assert bounded_iterations(0) == 1
