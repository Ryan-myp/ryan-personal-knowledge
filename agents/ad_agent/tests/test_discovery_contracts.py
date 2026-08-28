"""Regression tests for metadata-driven Tool discovery."""

from agents.ad_agent.core.interfaces import (
    ParsedIntent,
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.ad_agent.core.intent import SimpleIntentRouter
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.runtime.runtime import AgentRuntime, AccountWhitelistValidator


def test_existing_channel_tools_publish_routing_metadata():
    definitions = []
    for capability in (
        create_meta_capability(), create_google_capability(),
        create_tiktok_capability(), create_dv360_capability(),
    ):
        definitions.extend(definition for definition, _ in capability.register_tools())

    assert all(definition.action for definition in definitions)
    assert all(definition.resource_type for definition in definitions)
    assert all(definition.intent_types for definition in definitions if definition.is_read_tool or definition.is_write_tool)

    by_name = {definition.name: definition for definition in definitions}
    assert by_name["meta_create_adset"].parent_resource_type == "campaign"
    assert by_name["google_create_ad"].parent_resource_type == "ad_group"
    assert by_name["dv360_create_line_item"].parent_resource_type == "io"


def test_new_standard_tool_is_discovered_without_router_configuration():
    registry = SimpleToolRegistry()

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({"discovered": True})

    registry.register(
        ToolDefinition(
            name="new_network_create_campaign",
            skill="new-network-skill",
            platform="new-network",
            description="Create a campaign on a new network",
            input_schema=ToolSchema(),
            action="create",
            resource_type="campaign",
            effect_class=ToolEffect.WRITE,
        ),
        Handler(),
    )

    routed = SimpleIntentRouter().route(
        ParsedIntent("create_campaign", "create", ["new-network"]), registry
    )
    assert [definition.name for definition in routed["new-network"]] == [
        "new_network_create_campaign"
    ]


def test_new_custom_intent_is_declared_on_tool_not_router():
    registry = SimpleToolRegistry()

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({})

    registry.register(
        ToolDefinition(
            name="new_network_estimate_reach",
            skill="new-network-skill",
            platform="new-network",
            description="Estimate reach",
            input_schema=ToolSchema(),
            action="estimate",
            resource_type="audience",
            intent_types=["estimate_reach"],
        ),
        Handler(),
    )

    routed = SimpleIntentRouter().route(
        ParsedIntent("estimate_reach", "estimate", ["new-network"]), registry
    )
    assert [definition.name for definition in routed["new-network"]] == [
        "new_network_estimate_reach"
    ]


def test_live_mode_alone_cannot_enable_provider_writes():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["m1"]}
    runtime = AgentRuntime(
        execution_mode="live",
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
        whitelist_validator=validator,
    )
    runtime.register_capability(create_meta_capability())

    result = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        user_id="u1", account_id="m1",
    )
    assert result["results"][0]["success"] is False
    assert "allow_live_writes" in result["results"][0]["error"]
