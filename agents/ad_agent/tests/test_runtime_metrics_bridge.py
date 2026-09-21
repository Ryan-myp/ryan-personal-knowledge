from agents.agent_harness import InMemoryMetrics
from agents.ad_agent import AgentRuntime


def test_ad_runtime_forwards_generic_metrics_to_the_harness_kernel():
    metrics = InMemoryMetrics()
    runtime = AgentRuntime(
        require_llm=False,
        enforce_account_scope=False,
        metrics=metrics,
        start_background_workers=False,
    )
    try:
        assert runtime._platform_application.layer_snapshot() == (
            "application_scenarios",
            "agents",
            "core",
            "data",
            "integrations",
            "infrastructure",
        )
        assert runtime._platform_application.runtime is runtime._runtime_kernel
        result = runtime.run("列出账户")
        snapshot = metrics.snapshot()
        assert result["run_id"]
        assert snapshot["counters"]["runs_started"] == 1
        assert snapshot["counters"]["runs_finished.succeeded"] == 1
        assert snapshot["in_flight"] == 0
    finally:
        runtime.close(wait=True)
