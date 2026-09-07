from agents.ad_agent.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolHandler,
    ToolResult,
    ToolSchema,
)
from agents.ad_agent.core.provider_preflight import build_provider_preflight
from agents.ad_agent.runtime.account_policy import AccountWhitelistValidator
from agents.ad_agent.runtime.runtime import AgentRuntime


class _Noop(ToolHandler):
    def execute(self, context, input_data):
        return ToolResult.success_result({})


def _tool(name, *, action="list", resource="campaign", effect=ToolEffect.READ,
          readback=None):
    is_write = effect != ToolEffect.READ
    return ToolDefinition(
        name=name,
        skill="test",
        platform="meta",
        description=name,
        input_schema=ToolSchema(properties={"account_id": {"type": "string"}}, required=["account_id"]),
        intent_types=[action],
        action=action,
        resource_type=resource,
        risk_level=RiskLevel.MEDIUM if is_write else RiskLevel.LOW,
        effect_class=effect,
        replay_policy=ReplayPolicy.UNSAFE if is_write else ReplayPolicy.SAFE,
        required_permissions=["ads.plan" if is_write else "ads.read"],
        live_support=is_write,
        resource_id_field="campaign_id" if action != "list" else None,
        readback_tool=readback,
    )


def _runtime(*tools):
    validator = AccountWhitelistValidator("/path/does/not/exist")
    validator.allowed_accounts = {"meta": ["m-test"]}
    runtime = AgentRuntime(
        require_llm=False,
        offline_mode=True,
        enforce_account_scope=True,
        whitelist_validator=validator,
    )
    for tool in tools:
        runtime.registry.register(tool, _Noop())
    return runtime


def test_read_preflight_is_no_network_and_redacts_account_preview():
    runtime = _runtime(_tool("meta_list_campaigns"))
    try:
        report = build_provider_preflight(
            runtime,
            platform="meta",
            tool_names=["meta_list_campaigns"],
            account_id="m-test",
            credential_configured=True,
        )
    finally:
        runtime.close(wait=True)
    assert report["status"] == "ready_for_controlled_api_test"
    assert report["provider_calls"] == 0
    assert report["network_called"] is False
    assert report["configured_account_preview"] == ["…test"]


def test_preflight_blocks_unknown_account_and_missing_tool():
    runtime = _runtime(_tool("meta_list_campaigns"))
    try:
        report = build_provider_preflight(
            runtime,
            platform="meta",
            tool_names=["meta_list_campaigns", "meta_missing"],
            account_id="production-account",
            credential_configured=True,
        )
    finally:
        runtime.close(wait=True)
    assert report["status"] == "blocked"
    assert any("不在" in item for item in report["issues"])
    assert any("未注册" in item for item in report["issues"])


def test_live_write_preflight_requires_explicit_compatible_readback():
    write = _tool("meta_create_campaign", action="create", effect=ToolEffect.WRITE, readback=None)
    runtime = _runtime(write)
    try:
        report = build_provider_preflight(
            runtime,
            platform="meta",
            tool_names=[write.name],
            account_id="m-test",
            credential_configured=True,
            live_requested=True,
            live_environment_enabled=True,
        )
    finally:
        runtime.close(wait=True)
    assert report["status"] == "blocked"
    assert any("回查" in item for item in report["issues"])
