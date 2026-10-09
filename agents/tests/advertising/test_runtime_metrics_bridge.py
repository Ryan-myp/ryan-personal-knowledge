from agents.agent_harness import InMemoryMetrics
from agents.agent_harness.messages import ModelTurn
from agents.tools.advertising.application.composition.ad_application import AdvertisingComposition


def test_ad_runtime_forwards_generic_metrics_to_the_harness_kernel():
    class Model:
        def complete(self, _messages, _tools, _request):
            return ModelTurn(content="Request completed.")

    metrics = InMemoryMetrics()
    runtime = AdvertisingComposition(
        require_llm=False,
        llm_client=Model(),
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
