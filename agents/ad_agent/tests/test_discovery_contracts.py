"""Regression tests for metadata-driven Tool discovery."""

import pytest
import os

from agents.ad_agent.core.interfaces import (
    IntentParser,
    ParsedIntent,
    Skill,
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.ad_agent.core.intent import LLMIntentParser, SimpleIntentRouter
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.runtime.runtime import AgentRuntime, AccountWhitelistValidator
from agents.ad_agent.runtime.skill import SkillContract
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


def test_existing_channel_tools_publish_wire_id_fields_for_hierarchy():
    definitions = []
    for capability in (
        create_meta_capability(), create_google_capability(),
        create_tiktok_capability(), create_dv360_capability(),
    ):
        definitions.extend(definition for definition, _ in capability.register_tools())

    by_name = {definition.name: definition for definition in definitions}
    assert by_name["meta_create_ad"].parent_resource_id_field == "adset_id"
    assert by_name["google_create_ad"].parent_resource_id_field == "ad_group_id"
    assert by_name["tiktok_create_adgroup"].resource_id_field == "adgroup_id"
    assert by_name["tiktok_create_ad"].parent_resource_id_field == "adgroup_id"
    assert by_name["dv360_create_line_item"].parent_resource_id_field == "io_id"


@pytest.mark.parametrize(
    "campaign_type, expected_tools",
    [
        (
            "SEARCH",
            ["google_create_campaign", "google_create_ad_group", "google_create_ad"],
        ),
        (
            "PERFORMANCE_MAX",
            ["google_create_campaign", "google_create_pmax_asset_group"],
        ),
        (
            "SHOPPING",
            ["google_create_campaign", "google_create_ad_group", "google_create_product_group"],
        ),
        (
            "DISPLAY",
            ["google_create_campaign", "google_create_ad_group", "google_create_responsive_display_ad"],
        ),
        (
            "VIDEO",
            ["google_create_campaign", "google_create_ad_group", "google_create_video_ad"],
        ),
    ],
)
def test_google_campaign_route_selects_type_specific_creation_chain(
    campaign_type, expected_tools,
):
    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(create_google_capability())
    routed = runtime.intent_router.route(
        ParsedIntent(
            "create_campaign", "create", ["google-ads"],
            platform_params={
                "google-ads": {"advertising_channel_type": campaign_type},
            },
        ),
        runtime.registry,
    )

    assert [definition.name for definition in routed["google-ads"]] == expected_tools


def test_google_app_campaign_route_selects_app_hierarchy_chain():
    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(create_google_capability())
    routed = runtime.intent_router.route(
        ParsedIntent(
            "create_campaign", "create", ["google-ads"],
            platform_params={
                "google-ads": {
                    "advertising_channel_type": "MULTI_CHANNEL",
                    "advertising_channel_sub_type": "APP_CAMPAIGN",
                },
            },
        ),
        runtime.registry,
    )

    assert [definition.name for definition in routed["google-ads"]] == [
        "google_create_campaign",
        "google_create_app_ad_group",
        "google_create_app_ad",
    ]
    assert "google_create_ad_group" not in {
        definition.name for definition in routed["google-ads"]
    }


def test_google_app_campaign_chain_is_dry_run_ready():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"google-ads": ["123"]}
    runtime = AgentRuntime(require_llm=False, whitelist_validator=validator)
    runtime.register_capability(create_google_capability())

    result = runtime.run(
        "创建 Google App campaign 名称=app-dry-run",
        user_id="app-chain-test",
        account_id="123",
        platform_params={
            "google-ads": {
                "customer_id": "123",
                "campaign_name": "app-dry-run",
                "advertising_channel_type": "MULTI_CHANNEL",
                "advertising_channel_sub_type": "APP_CAMPAIGN",
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "budget": 100,
                "app_campaign_setting": {
                    "app_id": "com.example.app",
                    "app_store": "GOOGLE_APP_STORE",
                    "bidding_strategy_goal_type": "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
                },
                "headlines": [{"text": "Install now"}, {"text": "Try the app"}],
                "descriptions": [{"text": "A useful app"}, {"text": "Download today"}],
            },
        },
    )

    assert [item["tool"] for item in result["results"]] == [
        "google_create_campaign", "google_create_app_ad_group", "google_create_app_ad",
    ]
    assert all(item["success"] and item["data"]["simulated"] for item in result["results"])


@pytest.mark.parametrize(
    "platform, params, expected_tools",
    [
        (
            "meta",
            {"objective": "OUTCOME_LEADS"},
            ["meta_create_campaign", "meta_create_adset", "meta_create_lead_ad"],
        ),
        (
            "meta",
            {"catalog_id": "catalog-1"},
            ["meta_create_campaign", "meta_create_adset", "meta_create_catalog_ad"],
        ),
        (
            "tiktok",
            {"objective_type": "LEAD_GENERATION"},
            ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_lead_ad"],
        ),
        (
            "tiktok",
            {"objective_type": "APP_PROMOTION"},
            ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_app_ad"],
        ),
        (
            "tiktok",
            {"ad_format": "SINGLE_VIDEO"},
            ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_single_video_ad"],
        ),
        (
            "tiktok",
            {"spark_post_id": "post-1"},
            ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_spark_ads_create"],
        ),
        (
            "tiktok",
            {"objective_type": "PRODUCT_SALES"},
            [
                "tiktok_create_campaign",
                "tiktok_create_product_sales_adgroup",
                "tiktok_create_product_sales_ad",
            ],
        ),
    ],
)
def test_meta_and_tiktok_campaign_routes_select_specialized_ad_chain(
    platform, params, expected_tools,
):
    runtime = AgentRuntime(require_llm=False)
    factory = create_meta_capability if platform == "meta" else create_tiktok_capability
    runtime.register_capability(factory())
    routed = runtime.intent_router.route(
        ParsedIntent(
            "create_campaign", "create", [platform], platform_params={platform: params},
        ),
        runtime.registry,
    )

    assert [definition.name for definition in routed[platform]] == expected_tools


def test_resource_results_follow_declared_parent_fields_across_channels():
    cases = [
        ("meta", "meta_create_campaign", "meta_create_adset", "campaign_id", "c-meta", "adset_id", "s-meta"),
        ("google-ads", "google_create_campaign", "google_create_ad_group", "campaign_id", "c-google", "ad_group_id", "g-google"),
        ("tiktok", "tiktok_create_campaign", "tiktok_create_adgroup", "campaign_id", "c-tiktok", "adgroup_id", "g-tiktok"),
    ]
    definitions = {}
    for capability in (
        create_meta_capability(), create_google_capability(),
        create_tiktok_capability(), create_dv360_capability(),
    ):
        definitions.update({definition.name: definition for definition, _ in capability.register_tools()})

    normalized = []
    for platform, parent_name, child_name, parent_id_field, parent_id, child_id_field, child_id in cases:
        parent = definitions[parent_name]
        child = definitions[child_name]
        normalized.extend([
            {
                "tool": parent.name,
                "platform": platform,
                "account_id": f"{platform}-account",
                "resource_type": parent.resource_type,
                "resource_id_field": parent.resource_id_field or parent_id_field,
                "success": True,
                "data": {
                    "simulated": True,
                    parent.resource_id_field or parent_id_field: parent_id,
                    "input": {},
                },
            },
            {
                "tool": child.name,
                "platform": platform,
                "account_id": f"{platform}-account",
                "resource_type": child.resource_type,
                "resource_id_field": child.resource_id_field or child_id_field,
                "parent_resource_type": child.parent_resource_type,
                "parent_resource_id_field": child.parent_resource_id_field,
                "parent_resource_id": parent_id,
                "success": True,
                "data": {
                    "simulated": True,
                    child.resource_id_field or child_id_field: child_id,
                    "input": {child.parent_resource_id_field: parent_id},
                },
            },
        ])

    results = AgentRuntime._build_resource_results(normalized)
    assert len(results) == 6
    for index in (1, 3, 5):
        assert results[index]["parent_sequence"] == results[index - 1]["sequence"]
        assert results[index]["parent_resource_id"] == results[index - 1]["logical_resource_id"]
        assert results[index]["resource_ref"]["platform"] == results[index]["platform"]
        assert results[index]["parent_ref"]["resource_id"] == results[index]["parent_resource_id"]


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


def test_router_orders_custom_resource_hierarchy_without_core_resource_table():
    registry = SimpleToolRegistry()

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({})

    # Register the child first and use resource names unknown to the built-in
    # channels. The parent metadata, not a central order map, must determine
    # the route order.
    registry.register(
        ToolDefinition(
            name="new_create_leaf",
            skill="new-network",
            platform="new-network",
            description="Create a leaf",
            input_schema=ToolSchema(),
            action="create",
            resource_type="leaf",
            parent_resource_type="container",
            intent_types=["create_campaign"],
        ),
        Handler(),
    )
    registry.register(
        ToolDefinition(
            name="new_create_container",
            skill="new-network",
            platform="new-network",
            description="Create a container",
            input_schema=ToolSchema(),
            action="create",
            resource_type="container",
            intent_types=["create_campaign"],
        ),
        Handler(),
    )

    routed = SimpleIntentRouter().route(
        ParsedIntent("create_campaign", "create", ["new-network"]), registry
    )

    assert [definition.name for definition in routed["new-network"]] == [
        "new_create_container", "new_create_leaf"
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


def test_new_tool_publishes_dynamic_intent_context_without_parser_edit():
    definition = ToolDefinition(
        name="new_network_estimate_reach",
        skill="new-network-skill",
        platform="new-network",
        description="Estimate audience reach",
        input_schema=ToolSchema(),
        action="estimate",
        resource_type="audience",
        intent_types=["estimate_reach"],
    )
    parser = LLMIntentParser()
    parser.register_platform_aliases("new-network", ["新网络"])
    parser.register_tool_definitions([definition])
    assert "estimate_reach" in parser._intent_candidates_prompt()
    assert "Estimate audience reach" in parser._intent_candidates_prompt()


def test_standard_skill_ignores_workflow_yaml_as_package_data(tmp_path):
    """A Skill package's workflow.yaml is not an execution entry point."""
    skill_dir = tmp_path / "standard-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: standard-skill\n"
        "description: Natural-language guidance\n"
        "platform: meta\n"
        "---\n\n"
        "Use the registered tools according to this guidance.\n",
        encoding="utf-8",
    )
    # This deliberately contains a workflow-shaped declaration. Loading a
    # standard Skill must not parse it or turn it into executable steps.
    (skill_dir / "workflow.yaml").write_text(
        "steps:\n"
        "  - name: hidden-provider-call\n"
        "    tool: unregistered_tool\n"
        "    depends_on: []\n",
        encoding="utf-8",
    )

    contract = SkillContract(str(skill_dir)).load()

    assert contract.name == "standard-skill"
    assert contract.capabilities == {}
    assert not hasattr(contract, "workflows")


def test_llm_prompt_uses_registered_intent_catalog():
    class FakeLLM:
        def __init__(self):
            self.calls = []

        def call(self, messages):
            self.calls.append(messages)
            return '{"intent_type":"estimate_reach","platforms":["new-network"]}'

    definition = ToolDefinition(
        name="new_network_estimate_reach",
        skill="new-network-skill",
        platform="new-network",
        description="Estimate audience reach",
        input_schema=ToolSchema(),
        action="estimate",
        resource_type="audience",
        intent_types=["estimate_reach"],
    )
    llm = FakeLLM()
    parser = LLMIntentParser(llm)
    parser.register_tool_definitions([definition])
    parser.parse("estimate reach", ToolContext("s1", "u1"))

    prompt_text = "\n".join(message["content"] for message in llm.calls[0])
    assert "estimate_reach" in prompt_text
    assert "Estimate audience reach" in prompt_text


def test_production_llm_parser_does_not_fallback_when_model_is_unavailable():
    parser = LLMIntentParser(allow_rule_fallback=False)

    with pytest.raises(RuntimeError, match="LLM client is required"):
        parser.parse("查询 Meta campaign", None)


def test_runtime_can_require_model_backed_intent_parsing():
    runtime = AgentRuntime(require_llm=True)

    with pytest.raises(RuntimeError, match="LLM client is required"):
        runtime.run("查询 Meta campaign")


def test_runtime_requires_llm_by_default():
    runtime = AgentRuntime()

    with pytest.raises(RuntimeError, match="LLM client is required"):
        runtime.run("查询 Meta campaign")


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


def test_plugin_only_channel_auto_discovers_without_capability_or_central_config(tmp_path):
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "channels" / "new-network"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "skill:\n"
        "  name: new-network-skill\n"
        "  platform: new-network\n"
        "  aliases: [新网络]\n"
        "---\n",
        encoding="utf-8",
    )
    (skill_dir / "tools.py").write_text(
        "from agents.ad_agent.core.interfaces import Skill, ToolDefinition, ToolSchema, ToolResult\n"
        "class NewNetworkSkill(Skill):\n"
        "    name = 'new-network-skill'\n"
        "    platform = 'new-network'\n"
        "    description = 'new network'\n"
        "    platform_aliases = ['新网络']\n"
        "    def get_tools(self):\n"
        "        return [ToolDefinition(name='new_network_list_campaigns', skill=self.name, platform=self.platform, description='list', input_schema=ToolSchema(), action='list', resource_type='campaign', intent_types=['list_campaigns'])]\n"
        "    def get_tool_handler(self, name):\n"
        "        return lambda _ctx, _input: ToolResult.ok({'source': 'plugin'})\n"
        "def create_skill(api_client=None):\n"
        "    return NewNetworkSkill()\n",
        encoding="utf-8",
    )

    runtime = AgentRuntime(require_llm=False, enforce_account_scope=False)

    assert runtime.auto_load_skills(str(skill_root)) == 1
    assert [tool.name for tool in runtime.registry.list_all()] == [
        "new_network_list_campaigns"
    ]
    assert runtime.skill_loader.get("new-network-skill").platform_aliases == ["新网络"]


def test_standard_skill_discovery_does_not_require_category_directories(tmp_path):
    """A standard Skill may be mounted at root or under arbitrary nesting."""
    skill_root = tmp_path / "mounted-skills"
    skill_dir = skill_root / "vendor" / "campaign-planning"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: campaign-planning\n"
        "platform: new-network\n"
        "description: planning extension\n"
        "---\n\n"
        "Use the registered planning tool.\n",
        encoding="utf-8",
    )
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "rules.md").write_text(
        "Planning guidance", encoding="utf-8"
    )
    (skill_dir / "tools.py").write_text(
        "from agents.ad_agent.core.interfaces import Skill, ToolDefinition, ToolSchema, ToolResult\n"
        "class PlanningSkill(Skill):\n"
        "    name = 'campaign-planning'\n"
        "    platform = 'new-network'\n"
        "    description = 'planning extension'\n"
        "    def get_tools(self):\n"
        "        return [ToolDefinition(name='new_network_plan', skill=self.name, platform=self.platform, description='plan', input_schema=ToolSchema(), action='estimate', resource_type='plan', intent_types=['plan_campaign'])]\n"
        "    def get_tool_handler(self, name):\n"
        "        return lambda _ctx, _input: ToolResult.ok({'planned': True})\n"
        "def create_skill(api_client=None):\n"
        "    return PlanningSkill()\n",
        encoding="utf-8",
    )

    runtime = AgentRuntime(require_llm=False, enforce_account_scope=False)

    assert runtime.auto_load_skills(str(skill_root)) == 1
    assert [tool.name for tool in runtime.registry.list_all()] == [
        "new_network_plan"
    ]
    loaded = runtime.skill_loader.get("campaign-planning")
    assert loaded is not None
    assert loaded.reference_documents["references/rules.md"] == "Planning guidance"


def test_skill_loader_normalizes_root_paths_for_idempotent_reload(tmp_path):
    from agents.ad_agent.runtime.skill import SkillLoader

    skill_dir = tmp_path / "skills" / "reloadable"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: reloadable\nplatform: new-network\n"
        "description: reloadable skill\n---\n\nGuidance.\n",
        encoding="utf-8",
    )

    loader = SkillLoader(str(skill_dir.parent))
    loader.add_root(os.path.relpath(skill_dir.parent, os.getcwd()))
    loaded = loader.load_all()

    assert loader.errors == {}
    assert list(loaded) == ["reloadable"]
    assert loaded["reloadable"].skill_dir == str(skill_dir.resolve())


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
    runtime = AgentRuntime(require_llm=False,
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
