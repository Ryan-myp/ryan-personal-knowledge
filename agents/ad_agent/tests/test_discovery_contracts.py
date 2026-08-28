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
from agents.ad_agent.capabilities.factory import create_capability, discover_capability_factory
from agents.ad_agent.api_clients.factory import create_platform_client


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


def test_new_channel_capability_is_discovered_by_package_convention(monkeypatch):
    """Adding a channel factory must not require editing a central map."""
    import sys
    import types

    package_name = "agents.ad_agent.capabilities.new_network"
    module_name = f"{package_name}.capability"
    package = types.ModuleType(package_name)
    package.__path__ = []
    module = types.ModuleType(module_name)

    sentinel = object()
    module.create_new_network_capability = lambda client=None: sentinel
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, module_name, module)

    factory = discover_capability_factory("new-network")
    assert callable(factory)
    assert create_capability("new-network") is sentinel


def test_new_channel_client_is_discovered_by_package_convention(monkeypatch):
    import sys
    import types

    module_name = "agents.ad_agent.api_clients.new_network_client"
    module = types.ModuleType(module_name)
    sentinel = object()
    module.create_new_network_client = lambda credentials=None: sentinel
    monkeypatch.setitem(sys.modules, module_name, module)

    assert create_platform_client("new-network", {"access_token": "secret"}) is sentinel


def test_skill_can_own_optional_workflow_without_becoming_tool_registry(tmp_path):
    from agents.ad_agent.runtime.skill import BaseSkill, SkillContract

    skill_dir = tmp_path / "channels" / "workflow-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: workflow-skill\nplatform: new-network\n---\n"
        "# Provider SOP\nUse the provider's campaign creation sequence.\n",
        encoding="utf-8",
    )
    (skill_dir / "workflow.yaml").write_text(
        "workflows:\n"
        "  create_with_validation:\n"
        "    steps:\n"
        "      - id: validate\n"
        "        tool: new_validate_campaign\n"
        "      - id: create\n"
        "        tool: new_create_campaign\n"
        "        depends_on: [validate]\n",
        encoding="utf-8",
    )

    skill = BaseSkill(SkillContract(str(skill_dir)).load())
    assert skill.get_tools() == []
    assert skill.get_workflow_mappings() == {
        "create_with_validation": {
            "new-network": ["new_validate_campaign", "new_create_campaign"]
        }
    }


def test_runtime_resource_outputs_use_tool_metadata_not_tool_name():
    definition = ToolDefinition(
        name="provider_operation",
        skill="provider-skill",
        platform="new-network",
        description="Create a campaign",
        input_schema=ToolSchema(properties={"name": {"type": "string"}}),
        action="create",
        resource_type="campaign",
        effect_class=ToolEffect.WRITE,
    )
    runtime = AgentRuntime.__new__(AgentRuntime)
    runtime.registry = SimpleToolRegistry()
    simulated = runtime._simulate_write(definition, {"name": "demo"}, "new-network")
    assert simulated.data["campaign_id"].startswith("dry_new-network_")

    assert AgentRuntime._build_resource_results([{
        "tool": "provider_operation",
        "platform": "new-network",
        "success": True,
        "data": {"campaign_id": "c1"},
    }]) == []


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
