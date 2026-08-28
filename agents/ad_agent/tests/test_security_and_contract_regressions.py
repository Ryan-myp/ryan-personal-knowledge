import pytest

from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.core.interfaces import (
    ExecutionMode, ParsedIntent, ReplayPolicy, ToolContext, ToolDefinition,
    ToolEffect, ToolResult,
    ToolSchema,
)
from agents.ad_agent.api_clients.base import (
    APIError,
    AuthError,
    BasePlatformClient,
    ProviderVersionAdapter,
    RateLimitError,
    RetryConfig,
    TemporaryError,
)
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.api_clients.dv360_client import DV360APIClient
from agents.ad_agent.runtime.runtime import AccountWhitelistValidator, AgentRuntime
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.skill import BaseSkill, SkillContract, SkillLoader
from agents.ad_agent.core.tool_registry import validate_tool_input
from agents.ad_agent.core.cross_channel import CampaignRef, BatchOperation
from agents.ad_agent.core.auth import normalize_account_id, normalize_platform
from agents.ad_agent.core.intent import LLMIntentParser
from agents.ad_agent.core.tool_selector import DynamicToolSelector
from agents.ad_agent.user_skills.orchestrator import AdCampaignOrchestratorHandler


def whitelist(**accounts):
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = accounts
    return validator


def test_live_write_support_is_opt_in_for_new_tools():
    definition = ToolDefinition(
        name="new_provider_update_campaign",
        skill="new-provider",
        platform="new-provider",
        description="Update a campaign",
        input_schema=ToolSchema(),
        effect_class=ToolEffect.WRITE,
    )

    assert definition.live_support is False
    assert definition.replay_policy is ReplayPolicy.UNSAFE

    with pytest.raises(ValueError, match="ReplayPolicy.UNSAFE"):
        ToolDefinition(
            name="unsafe_contract_test",
            skill="new-provider",
            platform="new-provider",
            description="invalid replay policy",
            input_schema=ToolSchema(),
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.SAFE,
        )


def test_provider_api_version_is_bound_to_every_client_endpoint_builder():
    meta = MetaAPIClient({"api_version": "v19.0"})
    google = GoogleAdsAPIClient({"api_version": "v24"})
    tiktok = TikTokAPIClient({"api_version": "open_api/v1.3"})
    dv360 = DV360APIClient({"api_version": "v4"})

    assert meta._build_url("me/accounts").startswith("https://graph.facebook.com/v19.0/")
    assert google._build_url("customers/1").startswith("https://googleads.googleapis.com/v24/")
    assert tiktok._build_url("campaign/get/").startswith("https://business-api.tiktok.com/open_api/v1.3/")
    assert dv360._build_url("advertisers/1").startswith("https://display-video.googleapis.com/v4/")

    with pytest.raises(ValueError, match="Unsupported Meta API version"):
        MetaAPIClient({"api_version": "v99.0"})


def test_builtin_write_handlers_never_report_success_without_a_provider_client():
    context = ToolContext(session_id="s1", user_id="u1", account_id="account-1")
    for capability_factory in (
        create_meta_capability,
        create_google_capability,
        create_tiktok_capability,
        create_dv360_capability,
    ):
        for definition, handler in capability_factory().register_tools():
            if not definition.is_write_tool:
                continue
            result = handler.execute(context, {})
            assert result.success is False, definition.name


def test_builtin_no_client_reads_are_explicitly_marked_offline():
    context = ToolContext(session_id="s1", user_id="u1", account_id="account-1")
    for capability_factory in (
        create_meta_capability,
        create_google_capability,
        create_tiktok_capability,
        create_dv360_capability,
    ):
        for definition, handler in capability_factory().register_tools():
            if not definition.is_read_tool:
                continue
            result = handler.execute(context, {})
            if result.success:
                assert result.data.get("data_status") == "offline_no_client", definition.name


def test_skill_contract_write_tool_defaults_to_dry_run(tmp_path):
    skill_dir = tmp_path / "channels" / "new-provider"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: new-provider\nplatform: new-provider\n---\n",
        encoding="utf-8",
    )
    (skill_dir / "contract.yaml").write_text(
        "tools:\n"
        "  new_provider_update_campaign:\n"
        "    effect: write\n"
        "    input_schema: {type: object}\n",
        encoding="utf-8",
    )

    skill = BaseSkill(SkillContract(str(skill_dir)).load())

    assert skill.get_tools()[0].live_support is False
    assert skill.get_tools()[0].replay_policy.value == "unsafe"


def test_skill_loader_ignores_business_context_files_without_malformed_errors(tmp_path):
    business_dir = tmp_path / "businesses" / "app"
    business_dir.mkdir(parents=True)
    (business_dir / "SKILL.md").write_text(
        "---\n"
        "business:\n"
        "  name: app\n"
        "  allowed_channels: [google]\n"
        "---\n\n# App policy\n",
        encoding="utf-8",
    )

    loader = SkillLoader([str(tmp_path)])
    assert loader.load_all() == {}
    assert loader.errors == {}


def test_skill_contract_preserves_harness_operational_metadata(tmp_path):
    skill_dir = tmp_path / "channels" / "metadata-provider"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: metadata-provider\nplatform: metadata-provider\n---\n",
        encoding="utf-8",
    )
    (skill_dir / "contract.yaml").write_text(
        "tools:\n"
        "  metadata_provider_read:\n"
        "    effect: read\n"
        "    timeout_seconds: 3\n"
        "    max_output_bytes: 2048\n"
        "    replay_policy: safe\n"
        "    traits: [read, metadata]\n"
        "    input_schema: {type: object}\n",
        encoding="utf-8",
    )

    definition = BaseSkill(SkillContract(str(skill_dir)).load()).get_tools()[0]

    assert definition.timeout_seconds == 3
    assert definition.max_output_bytes == 2048
    assert definition.replay_policy.value == "safe"
    assert definition.traits == ["read", "metadata"]


def test_nested_skill_frontmatter_preserves_aliases_and_triggers(tmp_path):
    skill_dir = tmp_path / "channels" / "nested-provider"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "skill:\n"
        "  name: nested-provider\n"
        "  platform: new-network\n"
        "  aliases: [network, 网络]\n"
        "  triggers:\n"
        "    - keywords: [创建网络广告]\n"
        "      patterns: [network.*create]\n"
        "---\n",
        encoding="utf-8",
    )

    contract = SkillContract(str(skill_dir)).load()

    assert contract.platform_aliases == ["network", "网络"]
    assert contract.triggers[0].keywords == ["创建网络广告"]
    assert contract.triggers[0].patterns == ["network.*create"]


def test_malformed_skill_isolated_from_other_skills(tmp_path):
    good_dir = tmp_path / "channels" / "good"
    bad_dir = tmp_path / "channels" / "bad"
    good_dir.mkdir(parents=True)
    bad_dir.mkdir(parents=True)
    (good_dir / "SKILL.md").write_text(
        "---\nname: good\nplatform: good-network\n---\n", encoding="utf-8"
    )
    (bad_dir / "SKILL.md").write_text(
        "---\nname: bad\nplatform: bad-network\ntriggers: {broken: [1]}\n---\n",
        encoding="utf-8",
    )

    skill_loader = SkillLoader(str(tmp_path))
    loader = skill_loader.load_all()

    assert set(loader) == {"good"}
    assert str(bad_dir) in skill_loader.errors


def test_skill_contract_rejects_coercible_malformed_declarations(tmp_path):
    skill_dir = tmp_path / "channels" / "strict-provider"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: strict-provider\nplatform: strict-provider\n---\n",
        encoding="utf-8",
    )
    (skill_dir / "contract.yaml").write_text(
        "tools:\n"
        "  strict_read:\n"
        "    effect: read\n"
        "    live_support: 'false'\n"
        "    input_schema:\n"
        "      type: object\n"
        "      properties: []\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="(properties must be an object|live_support must be boolean)"):
        SkillContract(str(skill_dir)).load()


def test_schema_rejects_non_object_and_non_finite_numbers():
    schema = ToolSchema(properties={
        "budget": {"type": "number"},
        "nested": {
            "type": "object",
            "properties": {"amount": {"type": "number"}},
            "additionalProperties": False,
        },
    })

    assert validate_tool_input(schema, []) == ["Input must be an object, got list"]
    assert any("budget" in error for error in validate_tool_input(
        schema, {"budget": float("nan")}
    ))
    assert any("amount" in error for error in validate_tool_input(
        schema, {"nested": {"amount": float("inf")}}
    ))
    open_schema = ToolSchema(properties={
        "targeting": {"type": "object", "additionalProperties": True},
    })
    assert any("targeting.bid" in error for error in validate_tool_input(
        open_schema, {"targeting": {"bid": float("-inf")}}
    ))


def test_cross_channel_batch_operation_exposes_scoped_campaign_ref():
    operation = BatchOperation("meta", "m1", "c1", "pause")

    assert operation.campaign_ref == CampaignRef("meta", "m1", "c1")
    assert operation.to_dict()["campaign_ref"] == {
        "platform": "meta", "account_id": "m1", "campaign_id": "c1"
    }


def test_intent_parser_accepts_new_registered_platform_without_core_edit():
    parser = LLMIntentParser()
    parser.register_platforms(["snapchat-ads"])
    parser.register_tool_schemas(
        "snapchat-ads",
        [{"properties": {"optimization_goal": {"type": "string"}}}],
    )

    intent = parser.parse(
        "查询 Snapchat Ads campaign optimization_goal=CONVERSIONS", None
    )

    assert intent.platforms == ["snapchat-ads"]
    assert intent.platform_params["snapchat-ads"]["optimization_goal"] == "CONVERSIONS"


def test_account_whitelist_normalizes_platform_and_account_ids_fail_closed():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"google": ["act_123"], "meta": "not-an-array"}

    assert validator.validate_account("google-ads", 123) == (True, "")
    assert validator.get_allowed_accounts("google ads") == ["act_123"]
    assert validator.validate_account("meta", "m1")[0] is False

    validator.allowed_accounts = {"meta": ["act_123"]}
    assert validator.validate_account("meta", "xact_123")[0] is False
    validator.allowed_accounts = {"meta": [["nested-id"]]}
    assert validator.validate_account("meta", "nested-id")[0] is False
    assert normalize_account_id("ACT_123") == "123"
    assert normalize_account_id("xact_123") == "xact_123"
    assert normalize_account_id(["123"]) == ""
    assert normalize_platform("google ads") == "google-ads"


def test_public_tool_contract_includes_operational_and_json_schema_fields():
    definition = ToolDefinition(
        name="contract_test",
        skill="test",
        platform="meta",
        description="contract test",
        input_schema=ToolSchema(additional_properties=True),
        timeout_seconds=7,
        max_output_bytes=1234,
    )

    contract = definition.to_dict()
    assert contract["timeout_seconds"] == 7
    assert contract["max_output_bytes"] == 1234
    assert contract["input_schema"]["additional_properties"] is True
    assert contract["input_schema"]["additionalProperties"] is True


@pytest.mark.parametrize(
    "platform, account_id, factory, platform_params, expected_tools",
    [
        (
            "meta", "m1", create_meta_capability,
            {"account_id": "m1", "name": "smoke", "objective": "OUTCOME_SALES",
             "special_ad_categories": "NONE", "budget": 100,
             "optimization_goal": "OFFSITE_CONVERSIONS", "billing_event": "IMPRESSIONS",
             "targeting": {"geo_locations": {"countries": ["US"]}},
             "promoted_object": {"pixel_id": "px1"}, "creative": {"id": "cr1"}},
            ["meta_create_campaign", "meta_create_adset", "meta_create_ad"],
        ),
        (
            "google-ads", "g1", create_google_capability,
            {"customer_id": "g1", "campaign_name": "smoke",
             "advertising_channel_type": "SEARCH", "bidding_strategy": "MAXIMIZE_CONVERSIONS",
             "budget": 100, "type": "SEARCH_STANDARD", "final_url": "https://example.com",
             "headlines": ["a", "b", "c"], "descriptions": ["a", "b"]},
            ["google_create_campaign", "google_create_ad_group", "google_create_ad"],
        ),
        (
            "tiktok", "t1", create_tiktok_capability,
            {"account_id": "t1", "name": "smoke", "objective_type": "PRODUCT_SALES",
             "budget_mode": "BUDGET_MODE_DAY", "campaign_type": "REGULAR_CAMPAIGN",
             "promotion_type": "WEBSITE", "billing_event": "OCPM", "budget": 100,
             "location_ids": ["US"], "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
             "bid_type": "BID_TYPE_NO_BID", "landing_url": "https://example.com",
             "media": {"video_id": "v1"}},
            ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_ad"],
        ),
        (
            "dv360", "d1", create_dv360_capability,
            {"advertiser_id": "d1", "name": "smoke", "campaign_type": "DISPLAY",
             "objective": "CLICKS", "start_date": "2026-08-28", "end_date": "2026-09-04",
             "budget": 100, "type": "DISPLAY_DEFAULT", "goal": {"goal_type": "CLICKS"},
             "targeting": {"geo": {"country": ["US"]}}},
            ["dv360_create_campaign", "dv360_create_io", "dv360_create_line_item"],
        ),
    ],
)
def test_four_channel_create_chains_are_dry_run_only(
    platform, account_id, factory, platform_params, expected_tools,
):
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {platform: [account_id]}
    runtime = AgentRuntime(whitelist_validator=validator)
    runtime.register_capability(factory())

    result = runtime.run(
        f"创建 {platform} campaign 名称=smoke",
        user_id="smoke-test",
        account_id=account_id,
        platform_params={platform: platform_params},
    )

    assert [item["tool"] for item in result["results"]] == expected_tools
    assert all(item["success"] for item in result["results"])
    assert all(item["data"]["simulated"] is True for item in result["results"])
    assert all(item["data"]["provider_validation"]["ready"] is True for item in result["results"])


def test_structured_google_platform_alias_params_reach_provider_tool():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"google-ads": ["g1"]}
    runtime = AgentRuntime(whitelist_validator=validator)
    runtime.register_capability(create_google_capability())

    result = runtime.run(
        "更新 Google Ads campaign campaign_id=123",
        user_id="alias-user",
        account_id="g1",
        platform_params={
            "google-ads": {
                "customer_id": "g1",
                "updates": {"status": "PAUSED"},
            }
        },
    )

    assert result["results"][0]["success"] is True
    assert result["results"][0]["data"]["input"]["updates"] == {
        "status": "PAUSED"
    }


def test_tool_selector_discovers_platform_from_registered_tools():
    definition = ToolDefinition(
        name="snapchat_create_campaign",
        skill="snapchat-ads",
        platform="snapchat-ads",
        description="create a campaign",
        input_schema=ToolSchema(),
    )
    loader = type(
        "Loader",
        (),
        {"_skills": {}, "get_skill": lambda self, _name: None},
    )()
    selector = DynamicToolSelector(skill_loader=loader)

    selection = selector.select_tools(
        "创建 Snapchat Ads campaign",
        ParsedIntent("create_campaign", "创建 Snapchat Ads campaign", []),
        [definition],
    )

    assert selection.platform == "snapchat-ads"
    assert [tool.name for tool in selection.selected_tools] == [definition.name]


def test_cross_channel_orchestrator_builds_chain_from_tool_metadata():
    tools = [
        ToolDefinition(
            name="snapchat_create_campaign", skill="snapchat", platform="snapchat-ads",
            description="create campaign", input_schema=ToolSchema(),
            action="create", resource_type="campaign", intent_types=["create_campaign"],
        ),
        ToolDefinition(
            name="snapchat_create_ad_group", skill="snapchat", platform="snapchat-ads",
            description="create ad group", input_schema=ToolSchema(),
            action="create", resource_type="ad_group", parent_resource_type="campaign",
            intent_types=["create_campaign"],
        ),
    ]
    handler = AdCampaignOrchestratorHandler(available_tools=tools)

    plan = handler._build_execution_plan(
        ParsedIntent(
            "create_campaign", "create", ["snapchat-ads"],
            objective="sales", budget=20,
            platform_params={"snapchat-ads": {"promotion_type": "APP"}},
        )
    )

    assert plan[0]["tools"] == ["snapchat_create_campaign", "snapchat_create_ad_group"]
    assert plan[0]["params"]["promotion_type"] == "APP"


def test_provider_free_detail_reads_fail_closed_for_all_channels():
    cases = [
        ("meta", "m1", create_meta_capability),
        ("google-ads", "g1", create_google_capability),
        ("tiktok", "t1", create_tiktok_capability),
        ("dv360", "d1", create_dv360_capability),
    ]
    for platform, account, factory in cases:
        runtime = AgentRuntime(
            whitelist_validator=whitelist(**{platform: [account]}),
            offline_mode=False,
        )
        runtime.register_capability(factory())
        result = runtime.run(
            f"查询 {platform} campaign 详情 campaign_id=123",
            account_id=account,
        )
        assert result["results"]
        assert result["results"][0]["success"] is False
        assert "offline_mode" in result["results"][0]["error"]


def test_read_result_without_evidence_status_is_marked_unknown():
    runtime = AgentRuntime(offline_mode=False)
    runtime.registry.register(
        ToolDefinition(
            name="statusless_read",
            skill="test",
            platform="meta",
            description="read without evidence metadata",
            input_schema=ToolSchema(),
            required_permissions=["ads.read"],
            effect_class=ToolEffect.READ,
        ),
        object(),
    )

    result = runtime._normalize_read_result_evidence(
        runtime.registry.get("statusless_read")[0], ToolResult.ok({"items": []})
    )

    assert result.success is True
    assert result.data["data_status"] == "unknown"


def test_structured_red_line_fields_are_rejected_without_mutating_credentials():
    runtime = AgentRuntime(whitelist_validator=whitelist(meta=["m1"]))
    runtime.register_capability(create_meta_capability())
    credentials = {"meta": {"access_token": "caller-secret"}}
    result = runtime.run(
        "更新 Meta campaign campaign_id=123",
        account_id="m1",
        credentials=credentials,
        platform_params={
            "meta": {
                "account_id": "m1",
                "updates": {"status": "PAUSED", "private_key": "secret"},
            }
        },
    )
    assert result["results"] == []
    assert "private_key" in result["policy_errors"][0]
    assert credentials == {"meta": {"access_token": "caller-secret"}}


def test_generic_token_is_a_red_line_in_structured_inputs():
    runtime = AgentRuntime(whitelist_validator=whitelist(meta=["m1"]))
    runtime.register_capability(create_meta_capability())
    result = runtime.run(
        "更新 Meta campaign campaign_id=123",
        account_id="m1",
        platform_params={
            "meta": {
                "account_id": "m1",
                "updates": {"status": "PAUSED", "token": "must-not-pass"},
            }
        },
    )
    assert result["results"] == []
    assert "token" in result["policy_errors"][0]


def test_account_configuration_fields_are_only_allowed_as_top_level_selectors():
    runtime = AgentRuntime(enforce_account_scope=False)
    calls = []

    class Handler:
        def execute(self, _ctx, _input):
            calls.append(True)
            return ToolResult.ok({"ok": True})

    runtime.registry.register(
        ToolDefinition(
            name="provider_update",
            skill="provider",
            platform="provider",
            description="update",
            input_schema=ToolSchema(additional_properties=True),
            effect_class=ToolEffect.WRITE,
        ),
        Handler(),
    )

    result = runtime._execute_tool(
        ToolContext("s1", "u1", "account-1"),
        "provider_update",
        {"account_id": "account-1", "updates": {"account_id": "other-account"}},
    )

    assert result.success is False
    assert "updates.account_id" in result.error
    assert calls == []


def test_live_write_rejects_custom_handler_without_provider_client():
    runtime = AgentRuntime(
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        enforce_account_scope=False,
    )

    class Handler:
        def execute(self, _ctx, _input):
            return ToolResult.ok({"mutated": True})

    runtime.registry.register(
        ToolDefinition(
            name="custom_live_write",
            skill="custom",
            platform="custom-provider",
            description="write",
            input_schema=ToolSchema(),
            effect_class=ToolEffect.WRITE,
            live_support=True,
        ),
        Handler(),
    )

    result = runtime._execute_tool(ToolContext("s1", "u1"), "custom_live_write", {})

    assert result.success is False
    assert result.data["execution_status"] == "provider_unavailable"
    assert "未暴露受控 Provider Client" in result.error


def test_redaction_handles_json_and_python_dict_strings():
    redact = AgentRuntime._redact_for_persistence
    value = redact(
        "{'access_token': 'SECRET', \"client_secret\": \"CS\", "
        "'private_key': 'KEY', 'partnerId': 'PARTNER', 'perterId': 'TYPO_PARTNER', 'mcc': 'MCC'}"
    )
    for secret in ("SECRET", "CS", "KEY", "PARTNER", "TYPO_PARTNER", "MCC"):
        assert secret not in value
    assert "<redacted>" in value


@pytest.mark.parametrize(
    "field",
    [
        "bc_id", "partnerId", "perterId", "mcc",
        "login_customer_id", "managerCustomerId",
    ],
)
def test_configuration_redlines_are_rejected_at_top_level_platform_params(field):
    runtime = AgentRuntime()
    result = runtime.run(
        "你好",
        session_id=f"redline-{field}",
        platform_params={"meta": {field: "must-not-enter"}},
    )

    assert result["results"] == []
    assert result["policy_errors"]
    assert field in result["policy_errors"][0]
    assert "must-not-enter" not in str(result)


def test_account_selector_remains_allowed_while_configuration_fields_do_not():
    runtime = AgentRuntime()
    assert runtime._validate_tool_input_redline({"account_id": "test-account"}) == []
    assert runtime._validate_tool_input_redline({"advertiser_id": "test-advertiser"}) == []
    assert runtime._validate_tool_input_redline({"customer_id": "test-customer"}) == []
    assert runtime._validate_tool_input_redline({"bc_id": "business-center"}) == ["bc_id"]


class MinimalMetaClient:
    platform = "meta"

    def __init__(self):
        self.calls = []

    def update_campaign(self, campaign_id, updates):
        self.calls.append((campaign_id, updates))
        return {"campaign_id": campaign_id}


class TemporaryFailureMetaClient(MinimalMetaClient):
    def update_campaign(self, campaign_id, updates):
        self.calls.append((campaign_id, updates))
        raise TemporaryError("provider timeout")


def test_confirmation_payload_is_bound_to_the_exact_plan():
    client = MinimalMetaClient()
    runtime = AgentRuntime(
        whitelist_validator=whitelist(meta=["m1"]),
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_capability(create_meta_capability(client))
    runtime.registry.get("meta_update_campaign")[0].live_support = True
    planned = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="confirm-session",
        user_id="u1",
        account_id="m1",
    )
    payload = planned["results"][0]["confirmation_payload"]
    accepted = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="confirm-session",
        user_id="u1",
        account_id="m1",
        confirmed=True,
        confirmation_payload=payload,
    )
    assert accepted["results"][0]["success"] is True
    assert len(client.calls) == 1

    changed = runtime.run(
        "更新 Meta campaign campaign_id=123 status=ACTIVE",
        session_id="confirm-session",
        user_id="u1",
        account_id="m1",
        confirmed=True,
        confirmation_payload=payload,
    )
    assert changed["results"][0]["success"] is False
    assert "不匹配" in changed["results"][0]["error"]
    assert len(client.calls) == 1


def test_live_cross_channel_batch_is_explicitly_unsupported():
    runtime = AgentRuntime(
        whitelist_validator=whitelist(meta=["m1"]),
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_capability(create_meta_capability())
    result = runtime.run(
        "批量暂停 Meta campaign_ids=101,102",
        account_id="m1",
    )
    assert result["results"]
    assert all(item["success"] is False for item in result["results"])
    assert all(item["data"]["execution_status"] == "unsupported" for item in result["results"])


def test_create_tools_are_not_marked_safe_to_replay():
    for factory in (create_meta_capability, create_google_capability, create_dv360_capability):
        definitions = [definition for definition, _ in factory().register_tools()]
        create_definitions = [definition for definition in definitions if "_create_" in definition.name]
        assert create_definitions
        assert all(definition.replay_policy == ReplayPolicy.UNSAFE for definition in create_definitions)


def test_skill_markdown_is_context_only_without_executable_binding(tmp_path):
    skill_dir = tmp_path / "channels" / "unbound"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: unbound\nplatform: meta\n---\n"
        "### Tool: unbound_read\n\ndescription: read\n",
        encoding="utf-8",
    )
    skill = BaseSkill(SkillContract(str(skill_dir)).load())
    assert skill.get_tools() == []
    assert skill.get_tool_handler("unbound_read") is None


def test_tiktok_creation_contract_exposes_enums_and_conditional_dependencies():
    definitions = {
        definition.name: definition
        for definition, _ in create_tiktok_capability().register_tools()
    }
    campaign = definitions["tiktok_create_campaign"].input_schema
    adgroup = definitions["tiktok_create_adgroup"].input_schema

    assert "APP_PROMOTION" in campaign.properties["objective_type"]["enum"]
    assert "APP_ANDROID" in adgroup.properties["promotion_type"]["enum"]
    assert adgroup.properties["app_id"]["lookup_tool"] == "tiktok_list_apps"
    assert adgroup.properties["location_ids"]["lookup_tool"] == "tiktok_list_locations"
    assert adgroup.conditional_rules

    valid = {
        "campaign_id": "c1",
        "name": "Android acquisition",
        "promotion_type": "APP_ANDROID",
        "billing_event": "OCPM",
        "bid_type": "BID_TYPE_NO_BID",
        "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
        "budget_mode": "BUDGET_MODE_DAY",
        "budget": 50,
        "location_ids": ["US"],
        "app_id": "app-1",
        "deep_bid_type": "AEO",
        "operating_systems": ["ANDROID"],
    }
    assert validate_tool_input(adgroup, valid) == []

    invalid_objective = dict(valid, promotion_type="NOT_A_REAL_DESTINATION")
    assert any("promotion_type" in error and "must be one of" in error
               for error in validate_tool_input(adgroup, invalid_objective))

    missing_app = {key: value for key, value in valid.items() if key != "app_id"}
    assert any("app_id" in error for error in validate_tool_input(adgroup, missing_app))

    invalid_os = dict(valid, operating_systems=["WINDOWS"])
    assert any("operating_systems[0]" in error
               for error in validate_tool_input(adgroup, invalid_os))


def test_tiktok_website_contract_requires_landing_url():
    definition = next(
        definition for definition, _ in create_tiktok_capability().register_tools()
        if definition.name == "tiktok_create_adgroup"
    )
    data = {
        "campaign_id": "c1", "name": "Website traffic",
        "promotion_type": "WEBSITE", "billing_event": "OCPM",
        "bid_type": "BID_TYPE_NO_BID", "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
        "budget_mode": "BUDGET_MODE_DAY", "budget": 50,
        "daily_budget": 50, "location_ids": ["US"],
    }
    errors = validate_tool_input(definition.input_schema, data)
    assert any("landing_url" in error for error in errors)


def test_tiktok_campaign_and_app_ios_contracts_are_explicit():
    definitions = {
        definition.name: definition
        for definition, _ in create_tiktok_capability().register_tools()
    }
    campaign = definitions["tiktok_create_campaign"].input_schema
    adgroup = definitions["tiktok_create_adgroup"].input_schema

    assert "APP_ACQUISITION" in campaign.properties["app_promotion_type"]["enum"]
    assert any(
        rule.get("id") == "app_campaign_requires_app_mode"
        for rule in campaign.conditional_rules
    )
    assert any(
        rule.get("id") == "app_ios_dependencies"
        for rule in adgroup.conditional_rules
    )

    get_definitions = {
        definition.name: definition
        for definition, _ in create_tiktok_capability().register_tools()
        if definition.name in {"tiktok_get_adgroup", "tiktok_get_ad"}
    }
    assert get_definitions["tiktok_get_adgroup"].input_schema.required == [
        "campaign_id", "adgroup_id"
    ]
    assert get_definitions["tiktok_get_ad"].input_schema.required == [
        "adgroup_id", "ad_id"
    ]

    valid_ios = {
        "campaign_id": "c1", "name": "iOS acquisition",
        "promotion_type": "APP_IOS", "billing_event": "OCPM",
        "bid_type": "BID_TYPE_NO_BID", "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
        "budget_mode": "BUDGET_MODE_DAY", "budget": 50,
        "daily_budget": 50, "location_ids": ["US"], "app_id": "app-1",
        "deep_bid_type": "AEO", "operating_systems": ["IOS"],
    }
    assert validate_tool_input(adgroup, valid_ios) == []

    missing_bid = dict(valid_ios, bid_type="BID_TYPE_CUSTOM")
    assert any("bid_amount" in error for error in validate_tool_input(adgroup, missing_bid))


def test_provider_budget_aliases_are_normalized_before_api_payload():
    meta = MetaAPIClient({})
    meta_payloads = []
    meta.request = lambda method, endpoint, data=None, **kwargs: (
        meta_payloads.append(data) or {"id": "campaign-1"}
    )
    assert meta.create_campaign("m1", {
        "name": "Meta total",
        "objective": "OUTCOME_SALES",
        "budget": 12.5,
        "special_ad_categories": "NONE",
    }) == "campaign-1"
    assert meta_payloads[-1]["daily_budget"] == "1250"
    meta.update_campaign("campaign-1", {"budget": 15.25})
    assert meta_payloads[-1]["daily_budget"] == "1525"

    tiktok = TikTokAPIClient({})
    tiktok_payloads = []
    tiktok.request = lambda method, endpoint, data=None, **kwargs: (
        tiktok_payloads.append(data) or {"campaign_id": "campaign-1"}
    )
    assert tiktok.create_campaign("t1", {
        "name": "TikTok total",
        "objective_type": "PRODUCT_SALES",
        "campaign_type": "REGULAR_CAMPAIGN",
        "budget_mode": "BUDGET_MODE_TOTAL",
        "budget": 12.5,
    }) == "campaign-1"
    assert tiktok_payloads[-1]["budget"] == 1250
    tiktok.update_campaign("t1", "123", {"budget": 15.25})
    assert tiktok_payloads[-1]["campaign"]["budget"] == 1525


def test_update_contract_rejects_unknown_nested_provider_fields():
    definitions = {
        definition.name: definition
        for definition, _ in create_meta_capability().register_tools()
    }
    schema = definitions["meta_update_adset"].input_schema
    errors = validate_tool_input(schema, {
        "adset_id": "as-1",
        "updates": {"status": "PAUSED", "not_a_provider_field": "x"},
    })
    assert any("not_a_provider_field" in error for error in errors)


def test_tool_specific_unknown_creation_parameter_is_not_silently_dropped():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["m1"]}
    runtime = AgentRuntime(whitelist_validator=validator)
    runtime.register_capability(create_meta_capability())
    result = runtime.run(
        "创建 Meta campaign",
        account_id="m1",
        platform_params={
            "meta": {
                "meta_create_campaign": {
                    "name": "Contract test",
                    "objective": "OUTCOME_SALES",
                    "unsupported_future_field": "must-be-declared",
                }
            }
        },
    )
    assert result["results"][0]["success"] is False
    assert "unsupported_future_field" in result["results"][0]["error"]


def test_conditional_missing_parameter_exposes_lookup_tool():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"tiktok": ["t1"]}
    runtime = AgentRuntime(whitelist_validator=validator)
    runtime.register_capability(create_tiktok_capability())
    result = runtime.run(
        "创建 TikTok campaign",
        account_id="t1",
        platform_params={
            "tiktok": {
                "campaign_name": "Android acquisition",
                "objective_type": "APP_PROMOTION",
                "app_promotion_type": "APP_ACQUISITION",
                "campaign_type": "REGULAR_CAMPAIGN",
                "budget_mode": "BUDGET_MODE_DAY",
                "daily_budget": 50,
                "tiktok_create_adgroup": {
                    "name": "Android ad group",
                    "promotion_type": "APP_ANDROID",
                    "billing_event": "OCPM",
                    "bid_type": "BID_TYPE_NO_BID",
                    "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
                    "budget_mode": "BUDGET_MODE_DAY",
                    "budget": 50,
                    "daily_budget": 50,
                    "location_ids": ["US"],
                },
            }
        },
    )
    ask = next(
        item["confirmation_payload"]
        for item in result["results"]
        if item.get("confirmation_payload", {}).get("type") == "ask_params"
    )
    assert "app_id" in ask["missing"]
    assert ask["lookup_tools"]["app_id"] == "tiktok_list_apps"


def test_live_lookup_mints_context_bound_selection_token_for_dry_run_create():
    class LookupClient:
        platform = "tiktok"

        def list_apps(self, filtering=None, page_size=20):
            return [{"app_id": "app-1", "app_name": "Demo App"}]

    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"tiktok": ["t1"]}
    runtime = AgentRuntime(
        whitelist_validator=validator,
        selection_token_secret="selection-secret-1234",
    )
    runtime.register_capability(create_tiktok_capability(LookupClient()))

    lookup = runtime.run(
        "查询 TikTok apps",
        session_id="selection-session",
        user_id="u1",
        account_id="t1",
    )
    selection = lookup["results"][0]["data"]["parameter_selections"][0]
    option = selection["options"][0]
    assert option["value"] == "app-1"
    assert option["selection_token"] != "<redacted>"

    planned = runtime.run(
        "创建 TikTok campaign",
        session_id="selection-session",
        user_id="u1",
        account_id="t1",
        platform_params={
            "tiktok": {
                "campaign_name": "App acquisition",
                "objective_type": "APP_PROMOTION",
                "app_promotion_type": "APP_ACQUISITION",
                "campaign_type": "REGULAR_CAMPAIGN",
                "budget_mode": "BUDGET_MODE_DAY",
                "daily_budget": 50,
                "tiktok_create_adgroup": {
                    "name": "Android group",
                    "promotion_type": "APP_ANDROID",
                    "billing_event": "OCPM",
                    "bid_type": "BID_TYPE_NO_BID",
                    "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
                    "budget_mode": "BUDGET_MODE_DAY",
                    "budget": 50,
                    "daily_budget": 50,
                    "location_ids": ["US"],
                    "deep_bid_type": "AEO",
                    "operating_systems": ["ANDROID"],
                    "selection_tokens": {"app_id": option["selection_token"]},
                },
            }
        },
    )
    adgroup = next(
        item for item in planned["results"]
        if item.get("tool") == "tiktok_create_adgroup"
    )
    assert adgroup["success"] is True
    assert adgroup["data"]["input"]["app_id"] == "app-1"


def test_parameter_options_resolver_reuses_lookup_tool_boundaries():
    class LookupClient:
        platform = "tiktok"

        def list_apps(self, filtering=None, page_size=20):
            return [{"app_id": "app-2", "app_name": "Resolver App"}]

    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"tiktok": ["t1"]}
    runtime = AgentRuntime(
        whitelist_validator=validator,
        selection_token_secret="selection-secret-1234",
    )
    runtime.register_capability(create_tiktok_capability(LookupClient()))

    selection = runtime.resolve_parameter_options(
        "tiktok", "app_id", "tiktok_create_adgroup", "t1",
        session_id="resolver-session", user_id="u1", tenant_id="tenant-a",
    )

    assert selection["tool_name"] == "tiktok_create_adgroup"
    assert selection["options"][0]["value"] == "app-2"
    assert selection["options"][0]["selection_token"].startswith("ps1.")


def test_live_dynamic_parameter_rejects_unattested_raw_value():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"tiktok": ["t1"]}
    runtime = AgentRuntime(
        whitelist_validator=validator,
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        selection_token_secret="selection-secret-1234",
    )
    runtime.register_capability(create_tiktok_capability())
    definition = next(
        definition for definition, _ in create_tiktok_capability().register_tools()
        if definition.name == "tiktok_create_adgroup"
    )
    errors = runtime._apply_selection_tokens(
        definition,
        {"app_id": "app-1"},
        {"app_id": "app-1"},
        ToolContext(session_id="s1", user_id="u1", account_id="t1"),
    )
    assert any("selection_token" in error for error in errors)


def test_provider_status_is_normalized_before_dry_run_update_plan():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"tiktok": ["t1"], "google-ads": ["g1"]}
    runtime = AgentRuntime(whitelist_validator=validator)
    runtime.register_capability(create_tiktok_capability())
    runtime.register_capability(create_google_capability())

    tiktok = runtime.run(
        "更新 TikTok campaign campaign_id=123 status=PAUSED",
        account_id="t1",
    )
    tiktok_updates = tiktok["results"][0]["data"]["input"]["updates"]
    assert tiktok_updates == {"campaign_group_status": 0}

    google = runtime.run(
        "更新 Google campaign campaign_id=456 status=ACTIVE",
        account_id="g1",
    )
    google_updates = google["results"][0]["data"]["input"]["updates"]
    assert google_updates == {"status": "ENABLED"}


def test_common_business_objective_uses_skill_owned_provider_mapping():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["m1"], "tiktok": ["t1"]}
    runtime = AgentRuntime(whitelist_validator=validator)
    runtime.register_capability(create_meta_capability())
    runtime.register_capability(create_tiktok_capability())

    meta = runtime.run("创建 Meta 销售 campaign 名称=Sales", account_id="m1")
    meta_input = meta["results"][0]["data"]["input"]
    assert meta_input["objective"] == "OUTCOME_SALES"

    tiktok = runtime.run(
        "创建 TikTok 销售 campaign 名称=Sales",
        account_id="t1",
        platform_params={
            "tiktok": {
                "campaign_name": "Sales",
                "campaign_type": "REGULAR_CAMPAIGN",
                "budget_mode": "BUDGET_MODE_DAY",
                "daily_budget": 50,
            }
        },
    )
    tiktok_input = tiktok["results"][0]["data"]["input"]
    assert tiktok_input["objective_type"] == "PRODUCT_SALES"


def test_dry_run_reports_provider_fields_still_pending_without_calling_api():
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = {"meta": ["m1"]}
    runtime = AgentRuntime(whitelist_validator=validator)
    runtime.register_capability(create_meta_capability())
    result = runtime.run(
        "创建 Meta campaign 名称=Pending provider fields",
        account_id="m1",
        platform_params={
            "meta": {
                "objective": "OUTCOME_SALES",
                "special_ad_categories": "NONE",
                "budget": 100,
            }
        },
    )
    campaign = result["results"][0]["data"]
    assert campaign["simulated"] is True
    assert campaign["provider_validation"]["ready"] is True

    adset = next(item for item in result["results"] if item["tool"] == "meta_create_adset")
    validation = adset["data"]["provider_validation"]
    assert validation["ready"] is False
    assert any("optimization_goal" in error for error in validation["errors"])


class RetryProbeClient(BasePlatformClient):
    def __init__(self, responses, refreshable=False):
        super().__init__({}, "probe", RetryConfig(max_retries=0, jitter=False))
        self.responses = list(responses)
        self.calls = []
        self.refreshable = refreshable
        self.reset_count = 0

    def _do_request(self, method, url, **kwargs):
        self.calls.append(method)
        return self.responses.pop(0)

    def _extract_data(self, response):
        return response.get("data", {})

    def _handle_error(self, response, status_code):
        return AuthError("expired") if status_code == 401 else None

    def _reset_auth(self):
        self.reset_count += 1
        return self.refreshable


class VersionProbeAdapter(ProviderVersionAdapter):
    def adapt_request(self, method, endpoint, kwargs):
        kwargs["adapter_pass"] = kwargs.get("adapter_pass", 0) + 1
        return f"/v1{endpoint}", kwargs

    def adapt_response(self, method, endpoint, response):
        response = dict(response)
        response.setdefault("data", {})["adapted"] = True
        return response


class VersionProbeClient(BasePlatformClient):
    API_VERSION = "v2"
    SUPPORTED_API_VERSIONS = ("v2", "v1")
    VERSION_ADAPTERS = {"v1": VersionProbeAdapter}

    def __init__(self, responses):
        super().__init__("", "version-probe", RetryConfig(max_retries=1, base_delay=0, jitter=False))
        self.api_version = "v2"
        self.responses = list(responses)
        self.calls = []

    def _do_request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def _extract_data(self, response):
        return response.get("data", {})

    def _handle_error(self, response, status_code):
        return TemporaryError("retry") if status_code >= 500 else None


def test_provider_version_adapter_is_invocation_scoped_and_retry_safe():
    client = VersionProbeClient(
        [
            {"status_code": 500, "data": {}, "headers": {}},
            {"status_code": 200, "data": {}, "headers": {}},
        ]
    )
    client.requested_tool_api_version = "v1"

    result = client.request_raw("GET", "/resource")

    assert result["data"]["adapted"] is True
    assert len(client.calls) == 2
    assert [call[1] for call in client.calls] == ["/v1/resource", "/v1/resource"]
    assert all(call[2]["adapter_pass"] == 1 for call in client.calls)
    assert client.supports_tool_api_version("v1") is True
    assert client.supports_tool_api_version("v0") is False


def test_runtime_rejects_tool_version_not_supported_by_provider_client():
    client = VersionProbeClient([])
    calls = []

    class Handler:
        def __init__(self):
            self.client = client

        def execute(self, _ctx, _input):
            calls.append(True)
            return ToolResult.ok({"unexpected": True})

    runtime = AgentRuntime(enforce_account_scope=False)
    runtime.registry.register(
        ToolDefinition(
            name="versioned_read",
            skill="provider",
            platform="version-probe",
            description="read",
            input_schema=ToolSchema(),
            provider_api_version="v0",
        ),
        Handler(),
    )

    result = runtime._execute_tool(ToolContext("s1", "u1"), "versioned_read", {})

    assert result.success is False
    assert "要求 Provider API v0" in result.error
    assert calls == []


def test_401_recovery_retries_safe_reads_but_not_writes():
    read_client = RetryProbeClient(
        [{"status_code": 401, "data": {}}, {"status_code": 200, "data": {"ok": True}}],
        refreshable=True,
    )
    assert read_client.request("GET", "https://example.test/resource") == {"ok": True}
    assert read_client.calls == ["GET", "GET"]
    assert read_client.reset_count == 1

    write_client = RetryProbeClient(
        [{"status_code": 401, "data": {}}, {"status_code": 200, "data": {"ok": True}}],
        refreshable=True,
    )
    with pytest.raises(AuthError):
        write_client.request("POST", "https://example.test/resource", data={"x": 1})
    assert write_client.calls == ["POST"]
    assert write_client.reset_count == 0


def _provider_clients(retry_config=None):
    retry_config = retry_config or RetryConfig(max_retries=0, jitter=False)
    return [
        MetaAPIClient({"access_token": "caller-token"}, retry_config=retry_config),
        GoogleAdsAPIClient({"access_token": "caller-token", "customer_id": "g1"}, retry_config=retry_config),
        TikTokAPIClient({"access_token": "caller-token"}, retry_config=retry_config),
        DV360APIClient({"access_token": "caller-token"}, retry_config=retry_config),
    ]


@pytest.mark.parametrize(
    "status_code,error_type",
    [
        (400, APIError),
        (401, AuthError),
        (403, AuthError),
        (429, RateLimitError),
        (500, TemporaryError),
        (503, TemporaryError),
    ],
)
def test_all_provider_clients_have_consistent_http_error_contract(status_code, error_type):
    for client in _provider_clients():
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append(method)
            return {"status_code": status_code, "data": {}, "headers": {}}

        client._do_request = fake_request
        with pytest.raises(error_type):
            client.request_raw("GET", "/contract")
        assert calls == ["GET"]


class FakeHTTPResponse:
    def __init__(self, content):
        self.status_code = 200
        self.content = content
        self.headers = {}

    def json(self):
        raise ValueError("not JSON")


@pytest.mark.parametrize("content", [b"", b"<html>gateway error</html>"])
def test_all_provider_transports_normalize_empty_or_non_json_success_body(monkeypatch, content):
    response = FakeHTTPResponse(content)
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: response)
    for client in _provider_clients():
        envelope = client._do_request("GET", "https://example.test/contract")
        assert envelope["status_code"] == 200
        assert envelope["data"] == {}


def test_write_reservation_survives_runtime_restart():
    store = AdAgentStore(":memory:")
    first_client = MinimalMetaClient()
    first_runtime = AgentRuntime(
        persistence_store=store,
        whitelist_validator=whitelist(meta=["m1"]),
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    first_runtime.register_capability(create_meta_capability(first_client))
    first_runtime.registry.get("meta_update_campaign")[0].live_support = True
    planned = first_runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="persistent-confirm",
        user_id="u1",
        account_id="m1",
    )
    payload = planned["results"][0]["confirmation_payload"]
    executed = first_runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="persistent-confirm",
        user_id="u1",
        account_id="m1",
        confirmed=True,
        confirmation_payload=payload,
    )
    assert executed["results"][0]["success"] is True

    second_client = MinimalMetaClient()
    second_runtime = AgentRuntime(
        persistence_store=store,
        whitelist_validator=whitelist(meta=["m1"]),
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    second_runtime.register_capability(create_meta_capability(second_client))
    second_runtime.registry.get("meta_update_campaign")[0].live_support = True
    duplicate = second_runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="persistent-confirm",
        user_id="u1",
        account_id="m1",
        confirmed=True,
        confirmation_payload=payload,
    )
    assert duplicate["results"][0]["success"] is False
    assert (
        "approval has already been consumed" in duplicate["results"][0]["error"]
        or "Duplicate write detected" in duplicate["results"][0]["error"]
    )
    assert second_client.calls == []


def test_uncertain_live_write_keeps_reservation_for_recovery():
    store = AdAgentStore(":memory:")
    first_client = TemporaryFailureMetaClient()
    first_runtime = AgentRuntime(
        persistence_store=store,
        whitelist_validator=whitelist(meta=["m1"]),
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    first_runtime.register_capability(create_meta_capability(first_client))
    first_runtime.registry.get("meta_update_campaign")[0].live_support = True

    planned = first_runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="uncertain-write",
        user_id="u1",
        account_id="m1",
    )
    payload = planned["results"][0]["confirmation_payload"]
    uncertain = first_runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="uncertain-write",
        user_id="u1",
        account_id="m1",
        confirmed=True,
        confirmation_payload=payload,
    )

    assert uncertain["results"][0]["success"] is False
    assert uncertain["results"][0]["data"]["execution_status"] == "unknown"
    assert store.get_workflow(uncertain["workflow_id"])["status"] == "recovery_required"
    reservation = store._get_conn().execute(
        "SELECT status FROM write_reservations"
    ).fetchone()
    assert reservation["status"] == "pending"

    second_client = TemporaryFailureMetaClient()
    second_runtime = AgentRuntime(
        persistence_store=store,
        whitelist_validator=whitelist(meta=["m1"]),
        execution_mode=ExecutionMode.LIVE.value,
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    second_runtime.register_capability(create_meta_capability(second_client))
    second_runtime.registry.get("meta_update_campaign")[0].live_support = True
    retry = second_runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="uncertain-write",
        user_id="u1",
        account_id="m1",
        confirmed=True,
        confirmation_payload=payload,
    )

    assert retry["results"][0]["success"] is False
    assert "Duplicate write detected" in retry["results"][0]["error"]
    assert second_client.calls == []
