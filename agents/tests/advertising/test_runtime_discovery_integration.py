"""Replay the reported parent/child lookup through production composition offline."""

from agents.agent_harness import ModelTurn
from agents.agent_harness.core.interfaces import ToolResult
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.tests.advertising.harness_models import call, install
from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.skills.advertising.businesses.policy import BusinessSkillPolicy


def test_campaign_child_details_are_discovered_and_loaded_without_channel_io(monkeypatch):
    runtime = AdvertisingComposition(
        require_llm=False, offline_mode=True, start_background_workers=False,
        enforce_account_scope=False,
    )
    try:
        runtime.register_tool_source(create_meta_tool_source())
        original = runtime.tool_executor.execute
        business_calls = []

        def execute(context, name, arguments, clients=None):
            if name == "agent_discover_tools":
                return original(context, name, arguments, clients)
            business_calls.append((name, arguments))
            if name == "meta_get_campaign":
                return ToolResult.ok({"id": "parent-1", "adsets": [{"id": "child-1"}]})
            assert name == "meta_get_adset"
            assert arguments["adset_id"] == "child-1"
            return ToolResult.ok({"id": "child-1", "name": "test child", "status": "PAUSED"})

        monkeypatch.setattr(runtime.tool_executor, "execute", execute)
        model = install(
            runtime,
            ModelTurn(tool_calls=[call("meta_get_campaign", {"campaign_id": "parent-1"})]),
            ModelTurn(tool_calls=[call("agent_discover_tools", {
                "query": "Meta Ad Set 详情", "namespace": "meta", "resource_type": "adset",
            })]),
            ModelTurn(tool_calls=[call("meta_get_adset", {"adset_id": "child-1"})]),
            ModelTurn(content="已查到 Campaign 和 Ad Set 的详情"),
        )
        result = runtime.run(
            "看下这个meta campaign：parent-1的详情，含他的下层级的数据",
            user_id="discovery-test", account_id="test-account",
        )
        assert "meta_get_adset" not in model.tool_names[0]
        assert "meta_get_adset" in model.tool_names[2]
        assert [name for name, _ in business_calls] == ["meta_get_campaign", "meta_get_adset"]
        assert result["status"] == "succeeded", result
        assert result["reply"] == "已查到 Campaign 和 Ad Set 的详情"
    finally:
        runtime.close(wait=True)


def test_discovery_respects_business_namespace_policy():
    runtime = AdvertisingComposition(
        require_llm=False, offline_mode=True, start_background_workers=False,
        policies=[BusinessSkillPolicy.from_values(name="restricted", denied_platforms=("meta",))],
    )
    try:
        runtime.register_tool_source(create_meta_tool_source())
        model = install(
            runtime,
            ModelTurn(tool_calls=[call("agent_discover_tools", {"query": "meta_get_adset"})]),
            ModelTurn(content="当前策略未开放该渠道"),
        )
        result = runtime.run("查找 Meta 的明细查询工具", user_id="discovery-policy-test")
        discovery_result = next(m for m in model.messages[-1] if m.role == "tool")
        assert discovery_result.content["data"]["status"] == "no_matching_tool"
        assert not any(name.startswith("meta_") for name in model.tool_names[-1])
        assert result["status"] == "succeeded"
    finally:
        runtime.close(wait=True)


def test_discovery_success_does_not_mask_failed_channel_query(monkeypatch):
    runtime = AdvertisingComposition(
        require_llm=False, offline_mode=True, start_background_workers=False,
        enforce_account_scope=False,
    )
    try:
        runtime.register_tool_source(create_meta_tool_source())
        original = runtime.tool_executor.execute

        def execute(context, name, arguments, clients=None):
            if name == "agent_discover_tools":
                return original(context, name, arguments, clients)
            assert name == "meta_get_adset"
            return ToolResult.error("fixture scope denied")

        monkeypatch.setattr(runtime.tool_executor, "execute", execute)
        install(runtime,
            ModelTurn(tool_calls=[call("agent_discover_tools", {"query": "meta_get_adset"})]),
            ModelTurn(tool_calls=[call("meta_get_adset", {"adset_id": "child-1"})]),
            ModelTurn(content="查询失败：fixture scope denied"),
        )
        result = runtime.run("查询下层级详情", user_id="discovery-failure-test", account_id="test-account")
        assert result["status"] == "failed", result
        assert any(r.get("tool") == "meta_get_adset" and not r.get("success")
                   for r in result["results"])
    finally:
        runtime.close(wait=True)
