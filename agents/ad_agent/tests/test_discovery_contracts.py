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
from agents.ad_agent.core.creation_card import CreationCardBuilder
from agents.ad_agent.core.blueprint import BlueprintRegistry
from agents.ad_agent.core.platform import normalize_platform
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


def test_core_does_not_infer_routing_metadata_from_tool_name():
    definition = ToolDefinition(
        name="new_network_create_campaign",
        skill="new-network-skill",
        platform="new-network",
        description="An intentionally incomplete low-level fixture",
        input_schema=ToolSchema(),
    )

    assert definition.action == ""
    assert definition.resource_type == ""
    assert definition.parent_resource_type is None
    assert definition.intent_types == []
    assert definition.routing_metadata_errors() == [
        "action", "resource_type", "intent_types",
    ]


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


def test_cross_channel_tools_publish_result_relationship_metadata():
    definitions = []
    for capability in (
        create_meta_capability(), create_google_capability(),
        create_tiktok_capability(), create_dv360_capability(),
    ):
        definitions.extend(definition for definition, _ in capability.register_tools())

    by_name = {definition.name: definition for definition in definitions}
    for name in ("meta_list_campaigns", "google_list_campaigns",
                 "tiktok_list_campaigns", "dv360_list_campaigns"):
        definition = by_name[name]
        assert definition.result_items_key == "campaigns"
        assert definition.result_id_fields
    for name in ("meta_get_campaign_report", "google_get_campaign_report",
                 "tiktok_get_campaign_report"):
        definition = by_name[name]
        assert definition.related_resource_type == "campaign"
        assert definition.related_resource_id_fields


@pytest.mark.parametrize(
    "campaign_type, expected_tools",
    [
        (
            "SEARCH",
            ["google_create_campaign", "google_create_ad_group", "google_create_ad"],
        ),
        (
            "PERFORMANCE_MAX",
            [
                "google_create_campaign",
                "google_create_pmax_asset_group",
                "google_create_asset_group_listing_group_filter",
            ],
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


def test_google_app_campaign_requires_declared_parameters_before_execution():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"google-ads": ["123"]}
    runtime = AgentRuntime(require_llm=False, whitelist_validator=validator)
    runtime.register_capability(create_google_capability())

    result = runtime.run(
        "创建 Google App 广告 名称=app-dry-run",
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

    assert result["intent"]["intent_type"] == "create_campaign"
    assert result["results"] == []
    assert result["workflow_id"] is None
    assert result["needs_input"] is True
    assert result["ui"]["cards"]
    assert result["tool_plan"] == {}
    assert result["ui"]["cards"][0]["ready"] is False
    assert result["ui"]["cards"][0]["missing_fields"]


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
            ["tiktok_smart_plus_create_campaign", "tiktok_smart_plus_create_adgroup", "tiktok_smart_plus_create_ad"],
        ),
        (
            "tiktok",
            {"objective_type": "TRAFFIC"},
            ["tiktok_smart_plus_create_campaign", "tiktok_smart_plus_create_adgroup", "tiktok_smart_plus_create_ad"],
        ),
        (
            "tiktok",
            {"objective_type": "SALES"},
            ["tiktok_smart_plus_create_campaign", "tiktok_smart_plus_create_adgroup", "tiktok_smart_plus_create_ad"],
        ),
        (
            "tiktok",
            {"objective_type": "WEB_CONVERSIONS"},
            ["tiktok_smart_plus_create_campaign", "tiktok_smart_plus_create_adgroup", "tiktok_smart_plus_create_ad"],
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
                    "tiktok_smart_plus_create_campaign",
                    "tiktok_smart_plus_create_adgroup",
                    "tiktok_smart_plus_create_ad",
                ],
        ),
        (
            "tiktok",
            {"objective_type": "REACH"},
            ["tiktok_create_all_in_one_spark_ad"],
        ),
        (
            "tiktok",
            {"objective_type": "VIDEO_VIEWS", "ad_format": "SINGLE_VIDEO"},
            ["tiktok_create_all_in_one_spark_ad"],
        ),
        (
            "tiktok",
            {"objective_type": "ENGAGEMENT", "spark_post_id": "post-1"},
            ["tiktok_create_all_in_one_spark_ad"],
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


def test_tiktok_legacy_app_and_product_tools_are_explicit_only():
    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(create_tiktok_capability())

    app_route = runtime.intent_router.route(
        ParsedIntent("create_app_ad", "create app ad", ["tiktok"]),
        runtime.registry,
    )
    assert [definition.name for definition in app_route["tiktok"]] == [
        "tiktok_create_app_ad",
    ]

    product_route = runtime.intent_router.route(
        ParsedIntent("create_product_sales_ad", "create product sales ad", ["tiktok"]),
        runtime.registry,
    )
    assert [definition.name for definition in product_route["tiktok"]] == [
        "tiktok_create_product_sales_ad",
    ]


@pytest.mark.parametrize(
    "intent_type, expected_tool",
    [
        ("create_adgroup", "tiktok_smart_plus_create_adgroup"),
        ("create_ad", "tiktok_smart_plus_create_ad"),
    ],
)
def test_tiktok_smart_plus_objective_narrows_generic_child_routes(
    intent_type, expected_tool,
):
    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(create_tiktok_capability())
    routed = runtime.intent_router.route(
        ParsedIntent(
            intent_type,
            "create TikTok Traffic child resource",
            ["tiktok"],
            platform_params={"tiktok": {"objective_type": "TRAFFIC"}},
        ),
        runtime.registry,
    )
    assert [definition.name for definition in routed["tiktok"]] == [expected_tool]


def test_meta_campaign_only_route_does_not_expand_hierarchy():
    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(create_meta_capability())
    routed = runtime.intent_router.route(
        ParsedIntent(
            "create_campaign_only", "create campaign only", ["meta"],
            platform_params={"meta": {
                "objective": "OUTCOME_SALES",
                "special_ad_categories": ["NONE"],
                "daily_budget": 10,
                "status": "PAUSED",
                "name": "campaign-only",
            }},
        ),
        runtime.registry,
    )

    assert [definition.name for definition in routed["meta"]] == [
        "meta_create_campaign",
    ]


def test_campaign_only_routes_are_provider_declared_and_do_not_expand_hierarchy():
    cases = [
        ("meta", create_meta_capability(), "meta_create_campaign"),
        ("google-ads", create_google_capability(), "google_create_campaign"),
        ("tiktok", create_tiktok_capability(), "tiktok_smart_plus_create_campaign"),
    ]
    for platform, capability, expected_tool in cases:
        runtime = AgentRuntime(require_llm=False)
        runtime.register_capability(capability)
        params = {
            "name": "campaign-only",
            "objective": "OUTCOME_TRAFFIC" if platform == "meta" else "TRAFFIC",
            "objective_type": "TRAFFIC",
            "special_ad_categories": ["NONE"],
            "status": "PAUSED",
        }
        intent = ParsedIntent(
            "create_campaign_only", "create campaign only", [platform],
            platform_params={platform: params},
        )
        routed = runtime.intent_router.route(intent, runtime.registry)
        assert [definition.name for definition in routed[platform]] == [expected_tool]
        assert runtime._is_campaign_only_plan(routed, intent)


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
            intent_types=["create_campaign"],
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


def test_activation_narrowing_uses_candidate_ambiguity_not_intent_names():
    """An opaque custom intent gets the same conditional routing semantics."""
    registry = SimpleToolRegistry()

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({})

    common = dict(
        skill="new-network-skill",
        platform="new-network",
        description="Create an asset",
        input_schema=ToolSchema(
            properties={"mode": {"type": "string"}},
        ),
        action="create",
        resource_type="asset",
        intent_types=["opaque_operation"],
    )
    registry.register(ToolDefinition(name="new_create_asset", **common), Handler())
    registry.register(
        ToolDefinition(
            name="new_create_special_asset",
            **common,
            activation_rules=[{"field": "mode", "in": ["special"]}],
        ),
        Handler(),
    )

    router = SimpleIntentRouter()
    ordinary = router.route(
        ParsedIntent(
            "opaque_operation", "ordinary", ["new-network"],
            platform_params={"new-network": {"mode": "ordinary"}},
        ),
        registry,
    )
    special = router.route(
        ParsedIntent(
            "opaque_operation", "special", ["new-network"],
            platform_params={"new-network": {"mode": "special"}},
        ),
        registry,
    )

    assert [tool.name for tool in ordinary["new-network"]] == [
        "new_create_asset"
    ]
    assert [tool.name for tool in special["new-network"]] == [
        "new_create_asset", "new_create_special_asset"
    ]


def test_creation_surface_uses_tool_action_not_intent_name_prefix():
    registry = SimpleToolRegistry()

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({})

    registry.register(
        ToolDefinition(
            name="new_launch_asset",
            skill="new-network-skill",
            platform="new-network",
            description="Create an asset",
            input_schema=ToolSchema(),
            action="create",
            resource_type="asset",
            intent_types=["launch_asset"],
        ),
        Handler(),
    )
    builder = CreationCardBuilder(BlueprintRegistry(), registry)

    assert builder.is_creation_intent(
        ParsedIntent("launch_asset", "launch", ["new-network"])
    ) is True


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


def test_platform_identity_is_published_by_the_active_skill():
    """Core normalizes identifiers; aliases are published by the active Skill."""
    assert normalize_platform("google ads") == "google-ads"
    parser = LLMIntentParser()
    parser.register_platform_aliases("new-network", ["新网络"])
    assert parser._detect_platforms("查询新网络数据") == ["new-network"]


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

    assert runtime.auto_load_skills(
        str(skill_root), allow_executable_plugins=True,
    ) == 1
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

    assert runtime.auto_load_skills(
        str(skill_root), allow_executable_plugins=True,
    ) == 1
    assert [tool.name for tool in runtime.registry.list_all()] == [
        "new_network_plan"
    ]
    loaded = runtime.skill_loader.get("campaign-planning")
    assert loaded is not None
    assert loaded.reference_documents["references/rules.md"] == "Planning guidance"


def test_untrusted_skill_root_is_advisory_only_by_default(tmp_path):
    """User-managed directories must not import code or discover capabilities."""
    skill_root = tmp_path / "managed-skills"
    skill_dir = skill_root / "meta-guidance"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: meta-guidance\nplatform: meta\n---\n\nGuidance only.\n",
        encoding="utf-8",
    )
    marker = tmp_path / "imported"
    (skill_dir / "tools.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n",
        encoding="utf-8",
    )

    runtime = AgentRuntime(require_llm=False, enforce_account_scope=False)
    assert runtime.auto_load_skills(str(skill_root)) == 0
    assert not marker.exists()
    assert runtime.registry.list_all() == []


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
        resource_id_field="campaign_id",
        intent_types=["create_campaign"],
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


def test_runtime_input_compatibility_comes_from_schema_or_generic_semantics():
    """Core must not carry a provider resource-alias table."""
    definition = ToolDefinition(
        name="new_network_create_resource",
        skill="new-network",
        platform="new-network",
        description="Create a resource",
        input_schema=ToolSchema(properties={
            "name": {"type": "string"},
            "ad_set_id": {"type": "string"},
            "source_id": {
                "type": "string",
                "input_aliases": ["origin_id"],
            },
        }),
        action="create",
        resource_type="resource",
        intent_types=["create_resource"],
        effect_class=ToolEffect.WRITE,
    )
    runtime = AgentRuntime(require_llm=False, enforce_account_scope=False)
    intent = ParsedIntent(
        intent_type="create_resource",
        raw_input="create resource",
        platforms=["new-network"],
        platform_params={"new-network": {
            "campaign_name": "demo",
            "adset_id": "set-1",
            "origin_id": "source-1",
        }},
    )

    tool_input = runtime.input_builder.build(
        definition,
        intent,
        "new-network",
        ToolContext(session_id="s1", user_id="u1", account_id="account-1"),
    )

    assert tool_input["name"] == "demo"
    assert tool_input["ad_set_id"] == "set-1"
    assert tool_input["source_id"] == "source-1"


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


def test_tiktok_all_in_one_spark_contract_is_the_only_brand_objective_chain():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    definition = runtime.registry.get("tiktok_create_all_in_one_spark_ad")[0]

    assert definition.input_schema.required[:2] == ["account_id", "campaign_name"]
    assert definition.input_schema.properties["tiktok_item_id"]["manual_entry"]["source"] == (
        "external_provider_identifier"
    )
    assert "不会根据名称猜测" in definition.input_schema.properties["tiktok_item_id"]["manual_entry"]["instructions"]
    assert definition.input_schema.properties["call_to_action"]["manual_entry"]
    assert definition.input_schema.properties["optimization_goal"]["enum"] == [
        "REACH", "ENGAGED_VIEW", "FOLLOWERS", "PAGE_VISIT"
    ]

    for objective in ("REACH", "VIDEO_VIEWS", "ENGAGEMENT"):
        routed = runtime.intent_router.route(
            ParsedIntent(
                "create_campaign", "create", ["tiktok"],
                platform_params={"tiktok": {"objective_type": objective}},
            ),
            runtime.registry,
        )
        assert [item.name for item in routed["tiktok"]] == [
            "tiktok_create_all_in_one_spark_ad"
        ]


def test_tiktok_smart_plus_product_fields_publish_lookup_contracts():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())
    definition = runtime.registry.get("tiktok_smart_plus_create_adgroup")[0]
    properties = definition.input_schema.properties

    assert properties["app_id"]["lookup_tool"] == "tiktok_list_apps"
    assert properties["catalog_id"]["lookup_tool"] == "tiktok_list_catalogs"
    assert properties["product_set_id"]["lookup_tool"] == "tiktok_list_product_sets"
    assert properties["product_set_id"]["lookup_dependencies"][0]["input_field"] == "catalog_id"
    assert properties["optimization_event"]["lookup_tool"] == "tiktok_list_conversions"
