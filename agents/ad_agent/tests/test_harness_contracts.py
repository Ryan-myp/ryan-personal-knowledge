"""Harness-level invariants for the single-Agent execution boundary."""

import json
import sqlite3
from pathlib import Path
import time
from datetime import datetime, timedelta
import pytest

from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.core.interfaces import (
    ToolContext, ToolSchema, ToolDefinition, ToolEffect,
    ProviderReconciler, ReconciliationObservation, CapabilityRuntime,
    ParsedIntent, ToolResult,
)
from agents.ad_agent.core.knowledge import KnowledgeDocument
from agents.ad_agent.core.intent import LLMIntentParser
from agents.ad_agent.core.tool_registry import SimpleToolRegistry, validate_tool_input
from agents.ad_agent.tools.wiki_query import WikiQueryTool, wiki_get_errors
from agents.ad_agent.core.auth import RequestPrincipal
from agents.ad_agent.core.parameter_selection import (
    ParameterSelectionError,
    ParameterSelectionSigner,
)
from agents.ad_agent.api_clients.base import RateLimiter, TemporaryError
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.api_clients.dv360_client import DV360APIClient
from agents.ad_agent.persistence.store import AdAgentStore
from agents.ad_agent.runtime.runtime import AccountWhitelistValidator, AgentRuntime


def _whitelist(**accounts):
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = accounts
    return validator


def test_runtime_registry_cannot_bypass_execution_boundary():
    runtime = AgentRuntime(require_llm=False, whitelist_validator=_whitelist(meta=["m1"]))
    runtime.register_capability(create_meta_capability())
    definition, _ = runtime.registry.get("meta_create_campaign")

    result = runtime.registry.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="m1"),
        definition.name,
        {"account_id": "m1", "name": "direct"},
    )

    assert result.success is False
    assert "AgentRuntime" in result.error

    definition, handler = runtime.registry.get("meta_create_campaign")
    direct_handler_result = handler.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="m1"),
        {"account_id": "m1", "name": "direct"},
    )
    assert direct_handler_result.success is False
    assert "AgentRuntime" in direct_handler_result.error
    assert runtime.registry.execute_authorized(
        ToolContext(session_id="s1", user_id="u1", account_id="m1"),
        definition.name,
        {"account_id": "m1", "name": "direct"},
    ).success is False


def test_batch_planner_selects_campaign_updater_from_tool_metadata():
    """Batch routing must not depend on provider Tool registration order."""
    lookup = ToolDefinition(
        name="new_network_list_campaigns",
        skill="new-network",
        platform="new-network",
        description="List campaigns",
        input_schema=ToolSchema(),
        action="list",
        resource_type="campaign",
        intent_types=["cross_channel_batch_pause"],
    )
    updater = ToolDefinition(
        name="new_network_update_campaign",
        skill="new-network",
        platform="new-network",
        description="Update a campaign",
        input_schema=ToolSchema(properties={"updates": {"type": "object"}}),
        action="update",
        resource_type="campaign",
        intent_types=["cross_channel_batch_pause"],
        effect_class=ToolEffect.WRITE,
    )

    selected = AgentRuntime._select_batch_campaign_tool(
        [lookup, updater], "cross_channel_batch_pause"
    )

    assert selected is updater


def test_batch_planner_fails_closed_for_ambiguous_campaign_updaters():
    first = ToolDefinition(
        name="new_network_update_campaign_a",
        skill="new-network",
        platform="new-network",
        description="Update a campaign variant A",
        input_schema=ToolSchema(),
        action="update",
        resource_type="campaign",
        intent_types=["cross_channel_batch_pause"],
        effect_class=ToolEffect.WRITE,
    )
    second = ToolDefinition(
        name="new_network_update_campaign_b",
        skill="new-network",
        platform="new-network",
        description="Update a campaign variant B",
        input_schema=ToolSchema(),
        action="update",
        resource_type="campaign",
        intent_types=["cross_channel_batch_pause"],
        effect_class=ToolEffect.WRITE,
    )

    assert AgentRuntime._select_batch_campaign_tool(
        [first, second], "cross_channel_batch_pause"
    ) is None


def test_batch_budget_uses_provider_schema_and_rejects_unsupported_provider():
    runtime = AgentRuntime(
        require_llm=False,
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=_whitelist(dv360=["d1"]),
    )
    runtime.register_capability(create_dv360_capability())

    result = runtime.run(
        "批量更新 DV360 campaign_ids=campaign-1 预算100元/天",
        user_id="u1",
        platform_params={"dv360": {"account_id": "d1"}},
    )

    assert result["results"][0]["success"] is False
    assert "没有唯一兼容" in result["results"][0]["error"]
    workflow = runtime._session_manager.get_workflow(result["workflow_id"])
    assert workflow["status"] == "blocked"
    assert workflow["metadata"]["planning_error_count"] == 1
    assert workflow["items"] == []


def test_batch_items_have_global_sequences_and_keep_account_on_validation_failure():
    runtime = AgentRuntime(
        require_llm=False,
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=_whitelist(meta=["m1"], google=["g1"]),
    )
    runtime.register_capability(create_meta_capability())
    runtime.register_capability(create_google_capability())

    result = runtime.run(
        "跨渠道批量更新 Meta 和 Google campaign_ids=meta-1 预算100元/天",
        user_id="u1",
        platform_params={
            "meta": {
                "account_id": "m1",
                "campaign_ids": ["meta-1"],
                "updates": {"invalid_field": "reject-me"},
            },
            "google": {"account_id": "g1", "campaign_ids": ["google-1"]},
        },
    )

    workflow = runtime._session_manager.get_workflow(result["workflow_id"])
    assert [item["sequence"] for item in workflow["items"]] == [1, 2]
    assert [item["account_id"] for item in workflow["items"]] == ["m1", "g1"]
    assert workflow["items"][0]["status"] == "failed"
    assert workflow["items"][0]["input_data"]["campaign_id"] == "meta-1"
    assert workflow["items"][1]["status"] == "succeeded"


def test_capability_unload_clears_tools_and_derived_discovery_indexes():
    """A Capability unload must be symmetric with registration."""
    runtime = AgentRuntime(require_llm=False, enforce_account_scope=False)
    runtime.register_capability(create_meta_capability())

    assert runtime.registry.list_by_platform("meta")
    assert "meta_create_campaign" in runtime.intent_parser._intent_candidates_prompt()
    assert runtime.parameter_catalogs.list("meta")
    assert runtime.list_ad_formats("meta")

    assert runtime.unload_skill("meta") is True

    assert runtime.registry.list_by_platform("meta") == []
    assert "meta_create_campaign" not in runtime.intent_parser._intent_candidates_prompt()
    assert runtime.parameter_catalogs.list("meta") == []
    assert runtime.list_ad_formats("meta") == []
    assert runtime.skill_loader.get_by_platform("meta") == []


def test_capability_registration_rolls_back_partial_tool_registration():
    """A failed provider configure must not leave a half-loaded Capability."""

    class PartialCapability:
        platform_name = "partial-provider"

        def configure(self, context):
            context.registry.register(
                ToolDefinition(
                    name="partial_provider_first",
                    skill="partial-provider",
                    platform="partial-provider",
                    description="first tool",
                    input_schema=ToolSchema(),
                ),
                lambda _ctx, _input: ToolResult.ok({"ok": True}),
            )
            raise RuntimeError("provider configure failed")

    runtime = AgentRuntime(require_llm=False, enforce_account_scope=False)
    with pytest.raises(RuntimeError, match="provider configure failed"):
        runtime.register_capability(PartialCapability())

    assert runtime.registry.list_by_platform("partial-provider") == []
    assert runtime.parameter_catalogs.list("partial-provider") == []
    assert "partial-provider" not in runtime.get_loaded_skills()


def test_selector_only_builds_context_and_cannot_shrink_authoritative_plan():
    class Parser:
        def parse(self, _text, _ctx):
            return ParsedIntent("route_test", "route test", ["meta"])

    class Router:
        def route(self, _intent, registry):
            return {
                "meta": [registry.get("route_first")[0], registry.get("route_second")[0]]
            }

    class NarrowSelector:
        def build_context_for_input(self, *_args):
            return {}

        def optimize_for_llm(self, _text, _intent, all_tools):
            return {
                "selected_tools": list(all_tools[:1]), "tool_count": 1,
                "tool_prompt": "one tool for model context", "expert_knowledge": "",
                "context": {}, "platforms": "meta", "knowledge": [],
            }

    class Handler:
        def execute(self, _ctx, _input_data):
            return ToolResult.ok({"executed": True})

    runtime = AgentRuntime(require_llm=False,
        intent_parser=Parser(), intent_router=Router(),
        tool_selector=NarrowSelector(),
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    for name in ("route_first", "route_second"):
        runtime.registry.register(
            ToolDefinition(
                name=name, skill="route-test", platform="meta", description=name,
                input_schema=ToolSchema(properties={
                    "account_id": {"type": "string"},
                    "name": {"type": "string"},
                }),
                effect_class=ToolEffect.READ,
                required_permissions=["ads.read"],
            ), Handler()
        )

    result = runtime.run("route test", account_id="m1")
    assert result["tool_plan"] == {"meta": ["route_first", "route_second"]}
    assert [item["success"] for item in result["results"]] == [True, True]


def test_knowledge_context_is_read_only_bounded_and_source_addressable():
    class Provider:
        def __init__(self):
            self.calls = []

        def query(self, query, **kwargs):
            self.calls.append((query, kwargs))
            return [KnowledgeDocument(
                document_id="meta:campaigns.md", platform="meta", topic="campaigns",
                excerpt="Use the registered campaign schema.", source="fixture",
                version="v1", confidence=0.9, updated_at="2026-08-27",
            )]

    provider = Provider()
    runtime = AgentRuntime(require_llm=False, knowledge_provider=provider)
    result = runtime.run("查询 Meta campaign", account_id=None)

    assert provider.calls
    assert result["tool_selection"]["knowledge"][0]["source"] == "fixture"
    assert result["tool_selection"]["knowledge"][0]["confidence"] == 0.9
    assert not hasattr(provider, "add")


def test_direct_runtime_rejects_non_object_platform_params():
    result = AgentRuntime(require_llm=False, ).run("查询 Meta campaign", platform_params=[])
    assert result["policy_errors"] == ["platform_params 必须是对象"]


def test_rate_limit_wait_is_bounded_by_provider_deadline():
    limiter = RateLimiter(max_requests=1, period=60)
    limiter.acquire()
    with pytest.raises(TemporaryError, match="deadline"):
        limiter.acquire(max_wait=0.001)


def test_parameter_selection_tokens_are_signed_and_context_bound():
    signer = ParameterSelectionSigner("selection-secret-1234", ttl_seconds=10)
    token, expires_at = signer.issue(
        session_id="s1", user_id="u1", account_id="t1", platform="tiktok",
        tool_name="tiktok_create_adgroup", field="app_id",
        source_tool="tiktok_list_apps", value="app-1", now=100,
    )
    assert expires_at == 110
    assert signer.verify(
        token,
        session_id="s1", user_id="u1", account_id="t1", platform="tiktok",
        tool_name="tiktok_create_adgroup", field="app_id",
        source_tool="tiktok_list_apps", now=109,
    ) == "app-1"
    with pytest.raises(ParameterSelectionError, match="not bound to user_id"):
        signer.verify(
            token,
            session_id="s1", user_id="other", account_id="t1", platform="tiktok",
            tool_name="tiktok_create_adgroup", field="app_id",
            source_tool="tiktok_list_apps", now=109,
        )
    with pytest.raises(ParameterSelectionError, match="expired"):
        signer.verify(
            token,
            session_id="s1", user_id="u1", account_id="t1", platform="tiktok",
            tool_name="tiktok_create_adgroup", field="app_id",
            source_tool="tiktok_list_apps", now=110,
        )


def test_live_write_without_provider_client_fails_closed():
    runtime = AgentRuntime(require_llm=False,
        whitelist_validator=_whitelist(tiktok=["t1"]),
        execution_mode="live",
        allow_live_writes=True,
        live_approved_tools={"tiktok_create_adgroup"},
    )
    runtime.register_capability(create_tiktok_capability())
    definition, _handler = runtime._get_registered_tool("tiktok_create_adgroup")

    result = runtime._execute_tool(
        ToolContext(session_id="s1", user_id="u1", account_id="t1"),
        definition.name,
        {},
    )

    assert result.success is False
    assert result.data["execution_status"] == "provider_unavailable"
    assert "不会返回本地模拟结果" in result.error


def test_lookup_contract_must_reference_same_provider_read_tool():
    class BadLookupCapability:
        def configure(self, context):
            context.registry.register(
                ToolDefinition(
                    name="bad_dynamic_tool",
                    skill="bad-skill",
                    platform="tiktok",
                    description="invalid dynamic field",
                    input_schema=ToolSchema(properties={
                        "app_id": {
                            "type": "string",
                            "lookup_tool": "missing_lookup_tool",
                        },
                    }),
                ),
                lambda _ctx, _input: None,
            )
            return CapabilityRuntime()

    with pytest.raises(ValueError, match="unknown lookup tool"):
        AgentRuntime(require_llm=False, ).register_capability(BadLookupCapability())


def test_provider_specific_rate_limiters_use_request_deadline():
    for client in (TikTokAPIClient({}), DV360APIClient({})):
        client._rate_limiter = RateLimiter(max_requests=1, period=60)
        client.acquire_rate_limit(client._rate_limiter)
        client.set_request_budget(0.001)
        with pytest.raises(TemporaryError, match="deadline"):
            client.acquire_rate_limit(client._rate_limiter)


def test_async_report_polling_does_not_outlive_request_deadline():
    client = TikTokAPIClient({})
    client.set_request_budget(0.001)
    with pytest.raises(TemporaryError, match="deadline"):
        client._poll_report_result("advertiser", "task", max_wait=30)

    client = DV360APIClient({})
    client.set_request_budget(0.001)
    client.create_report = lambda _advertiser_id, _report: "report"
    with pytest.raises(TemporaryError, match="deadline"):
        client.get_line_item_report("advertiser", "line-item")


def test_closed_tool_schema_rejects_unknown_top_level_fields():
    schema = ToolSchema(
        required=["name"],
        properties={"name": {"type": "string"}},
    )
    errors = validate_tool_input(schema, {"name": "x", "future_flag": True})
    assert any("future_flag" in error for error in errors)


def test_live_confirmation_requires_payload_even_for_direct_runtime_call():
    calls = []

    class Client:
        platform = "meta"

        def update_campaign(self, campaign_id, updates):
            calls.append((campaign_id, updates))
            return {"campaign_id": campaign_id}

    runtime = AgentRuntime(require_llm=False,
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=_whitelist(meta=["m1"]),
        execution_mode="live",
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_capability(create_meta_capability(Client()))
    runtime.registry.get("meta_update_campaign")[0].live_support = True
    result = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="s1", user_id="u1", account_id="m1", confirmed=True,
    )

    assert result["results"][0]["success"] is False
    assert "confirmation_payload" in result["results"][0]["error"]
    assert calls == []


def test_live_write_without_write_guard_fails_closed():
    calls = []

    class Client:
        platform = "meta"

        def update_campaign(self, campaign_id, updates):
            calls.append((campaign_id, updates))
            return {"campaign_id": campaign_id}

    runtime = AgentRuntime(require_llm=False,
        whitelist_validator=_whitelist(meta=["m1"]),
        execution_mode="live",
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_capability(create_meta_capability(Client()))
    runtime.registry.get("meta_update_campaign")[0].live_support = True
    runtime.write_guard = None
    result = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="s-no-guard", user_id="u1", account_id="m1",
    )

    assert result["results"][0]["success"] is False
    assert "WriteGuard" in result["results"][0]["error"]
    assert calls == []


def test_parameter_catalogs_expose_static_and_dynamic_options():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_tiktok_capability())

    objective = runtime.list_parameter_options("tiktok", "objective_type")[0]
    app = runtime.list_parameter_options("tiktok", "app_id")[0]
    operating_systems = runtime.list_parameter_options("tiktok", "operating_systems")[0]
    budget_modes = runtime.list_parameter_options("tiktok", "budget_mode")

    assert objective["source"] == "tool_schema"
    assert "APP_PROMOTION" in {item["value"] for item in objective["options"]}
    assert app["source"] == "lookup"
    assert app["lookup_tool"] == "tiktok_list_apps"
    assert {item["value"] for item in operating_systems["options"]} == {"ANDROID", "IOS"}
    campaign_budget = next(
        item for item in budget_modes if item.get("tool_name") == "tiktok_create_campaign"
    )
    adgroup_budget = next(
        item for item in budget_modes if item.get("tool_name") == "tiktok_create_adgroup"
    )
    assert "BUDGET_MODE_TOTAL" in {item["value"] for item in campaign_budget["options"]}
    assert "BUDGET_MODE_TOTAL" not in {item["value"] for item in adgroup_budget["options"]}


def test_provider_owned_ad_format_catalog_reports_real_coverage():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())
    runtime.register_capability(create_meta_capability())
    runtime.register_capability(create_tiktok_capability())

    google = runtime.list_ad_formats("google-ads")
    meta = runtime.list_ad_formats("meta")
    tiktok = runtime.list_ad_formats("tiktok")

    assert {item["format_id"] for item in google} >= {
        "search", "performance_max", "shopping", "video", "display", "app",
    }
    assert {item["format_id"] for item in meta} >= {
        "traffic", "conversion", "lead", "engagement", "catalog", "messaging",
    }
    assert {item["format_id"] for item in tiktok} >= {
        "product_sales", "spark", "lead", "app", "brand",
    }
    assert all(
        item["payload_adapter"]
        for item in [*google, *meta, *tiktok]
        if item["coverage"] == "supported_dry_run"
    )
    registered = {definition.name for definition in runtime.registry.list_all()}
    assert all(
        tool_name in registered
        for item in [*google, *meta, *tiktok]
        for tool_name in item["tool_names"]
    )
    assert runtime.list_ad_formats("dv360") == []


def test_hierarchy_guide_formats_keep_provider_enum_and_execution_boundaries():
    runtime = AgentRuntime(require_llm=False, offline_mode=True)
    runtime.register_capability(create_google_capability())

    campaign_tool, _handler = runtime.registry.get("google_create_campaign")
    channel_types = campaign_tool.input_schema.properties["advertising_channel_type"]["enum"]
    app_stores = campaign_tool.input_schema.properties["app_campaign_setting"]["properties"]["app_store"]["enum"]

    assert "PERFORMANCE_MAX" in channel_types
    assert "MAX" not in channel_types
    assert app_stores == ["GOOGLE_APP_STORE", "APPLE_APP_STORE"]

    formats = runtime.list_ad_formats("google-ads")
    by_id = {item["format_id"]: item for item in formats}
    assert by_id["performance_max"]["source_document"] == "docs/ad-platform-hierarchy-guide-v5.md"
    assert by_id["video.skippable_in_stream"]["tool_names"] == ["google_create_video_ad"]
    assert by_id["display.responsive_display_ad"]["coverage"] == "supported_dry_run"
    assert by_id["video.skippable_in_stream"]["coverage"] == "supported_dry_run"
    assert "google_create_video_ad" in by_id["video"]["tool_names"]
    product_group = next(
        definition for definition in runtime.registry.list_all()
        if definition.name == "google_create_product_group"
    )
    assert product_group.parent_resource_type == "ad_group"
    assert "product_type_1" in product_group.input_schema.properties["product_group_type"]["enum"]
    assert validate_tool_input(
        product_group.input_schema,
        {"ad_group_id": "123", "product_group_type": "brand", "value": "Acme"},
        include_provider_contract=True,
    ) == []
    assert validate_tool_input(
        product_group.input_schema,
        {"ad_group_id": "123", "product_group_type": "brand"},
        include_provider_contract=True,
    )
    runtime.register_capability(create_meta_capability())
    meta_formats = {item["format_id"]: item for item in runtime.list_ad_formats("meta")}
    assert meta_formats["lead.instant_form"]["coverage"] == "supported_dry_run"
    assert meta_formats["lead.instant_form"]["tool_names"] == ["meta_create_lead_ad"]


def test_workflow_state_machine_and_cancel_are_durable():
    store = AdAgentStore(":memory:")
    store.create_session("s1", "u1", "m1")
    store.create_workflow("w1", "s1", "create_campaign", "dry_run", "running")

    assert store.update_workflow("w1", "planned") is True
    assert store.update_workflow("w1", "succeeded") is False

    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    store.update_workflow("w1", "running")
    assert runtime.cancel_workflow("w1", "u1") is True
    assert runtime.get_workflow("w1", "u1")["status"] == "cancelled"


def test_workflow_write_items_are_checkpointed_before_execution():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    runtime.register_capability(create_meta_capability())
    result = runtime.run(
        "创建 Meta campaign 名称=checkpointed",
        session_id="checkpoint-session", user_id="u1", account_id="m1",
    )

    workflow = store.get_workflow(result["workflow_id"])
    assert workflow["items"]
    assert all(item["status"] == "succeeded" for item in workflow["items"])
    assert all(item["account_id"] == "m1" for item in workflow["items"])
    assert workflow["items"][1]["parent_resource_type"] == "campaign"
    assert workflow["items"][1]["parent_resource_id"]
    assert len(workflow["items"]) == 3


def test_workflow_resume_plan_preserves_account_scope():
    store = AdAgentStore(":memory:")
    store.create_session("resume-account-session", "u1", "m1")
    store.create_workflow(
        "resume-account-workflow", "resume-account-session", "create_campaign", "live",
        status="failed",
    )
    store.add_workflow_item(
        "resume-account-workflow:1", "resume-account-workflow", 1, "meta",
        "meta_create_campaign", "failed", {"campaign_id": "c1"},
        account_id="m1",
    )
    runtime = AgentRuntime(require_llm=False, persistence_store=store)

    plan = runtime.get_workflow_resume_plan("resume-account-workflow", user_id="u1")

    assert plan["items"][0]["account_id"] == "m1"
    assert plan["items"][0]["resource_type"] == "campaign"


def test_legacy_workflow_resume_plan_recovers_account_from_session():
    store = AdAgentStore(":memory:")
    store.create_session("legacy-resume-session", "u1", "m1")
    store.create_workflow(
        "legacy-resume-workflow", "legacy-resume-session", "create_campaign", "live",
        status="failed",
    )
    store.add_workflow_item(
        "legacy-resume-workflow:1", "legacy-resume-workflow", 1, "meta",
        "meta_create_campaign", "failed", {"campaign_id": "c1"},
    )
    runtime = AgentRuntime(require_llm=False, persistence_store=store)

    plan = runtime.get_workflow_resume_plan("legacy-resume-workflow", user_id="u1")

    assert plan["items"][0]["account_id"] == "m1"


def test_old_workflow_items_schema_is_migrated_with_account_scope(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE workflow_items (
            item_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            platform TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            input_data TEXT NOT NULL,
            output_data TEXT,
            error TEXT,
            compensation_required INTEGER NOT NULL DEFAULT 0,
            resource_type TEXT,
            parent_sequence INTEGER,
            parent_resource_id TEXT,
            provider_resource_id TEXT,
            logical_resource_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    store = AdAgentStore(str(db_path))

    columns = {
        row[1] for row in store._get_conn().execute("PRAGMA table_info(workflow_items)")
    }
    assert "account_id" in columns
    assert "parent_resource_type" in columns


def test_fresh_running_workflow_is_not_resumable_or_claimed():
    store = AdAgentStore(":memory:")
    store.create_session("fresh-session", "u1", "m1")
    store.create_workflow(
        "fresh-workflow", "fresh-session", "create_campaign", "live",
        status="running",
    )
    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        workflow_stale_after_seconds=300,
    )

    plan = runtime.get_workflow_resume_plan("fresh-workflow", user_id="u1")
    assert plan["status"] == "running"
    assert plan["resumable"] is False
    assert runtime.list_resumable_workflows(user_id="u1") == []


def test_workflow_heartbeat_refreshes_lease_and_preserves_running_state():
    store = AdAgentStore(":memory:")
    store.create_session("heartbeat-session", "u1", "m1")
    store.create_workflow(
        "heartbeat-workflow", "heartbeat-session", "create_campaign", "live",
        status="running",
    )
    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        workflow_stale_after_seconds=300,
    )

    assert runtime._heartbeat_workflow("heartbeat-workflow") is True
    workflow = store.get_workflow("heartbeat-workflow")
    assert workflow["status"] == "running"
    assert workflow["lease_owner"] == runtime._workflow_lease_owner
    assert workflow["lease_expires_at"]
    assert runtime.get_workflow_resume_plan("heartbeat-workflow", user_id="u1")["resumable"] is False


def test_stale_running_workflow_enters_recovery_required():
    store = AdAgentStore(":memory:")
    store.create_session("stale-session", "u1", "m1")
    store.create_workflow(
        "stale-workflow", "stale-session", "create_campaign", "live",
        status="running",
    )
    store.add_workflow_item(
        "stale-workflow:1", "stale-workflow", 1, "meta",
        "meta_create_campaign", "running", {"account_id": "m1", "campaign_id": "c1"},
    )
    old_timestamp = (datetime.now() - timedelta(seconds=600)).isoformat()
    with store._lock:
        store._get_conn().execute(
            "UPDATE workflows SET updated_at = ? WHERE workflow_id = ?",
            (old_timestamp, "stale-workflow"),
        )
        store._get_conn().commit()

    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        workflow_stale_after_seconds=300,
    )
    listed = runtime.list_resumable_workflows(user_id="u1")
    assert [item["workflow_id"] for item in listed] == ["stale-workflow"]
    assert listed[0]["status"] == "running"

    plan = runtime.get_workflow_resume_plan("stale-workflow", user_id="u1")
    assert plan["status"] == "recovery_required"
    assert plan["resumable"] is True
    assert store.get_workflow("stale-workflow")["status"] == "recovery_required"


def test_workflow_recovery_claim_is_atomic_and_exclusive():
    store = AdAgentStore(":memory:")
    store.create_session("claim-session", "u1", "m1")
    store.create_workflow(
        "claim-workflow", "claim-session", "create_campaign", "live",
        status="failed",
    )

    assert store.claim_workflow_recovery("claim-workflow", "worker-a") is True
    assert store.claim_workflow_recovery("claim-workflow", "worker-b") is False
    claimed = store.get_workflow("claim-workflow")
    assert claimed["status"] == "recovery_required"
    assert claimed["lease_owner"] == "worker-a"
    assert store.release_workflow_lease("claim-workflow", "worker-b") is False
    assert store.release_workflow_lease("claim-workflow", "worker-a") is True


def test_resumable_workflows_keep_user_and_tenant_boundaries():
    store = AdAgentStore(":memory:")
    old_timestamp = (datetime.now() - timedelta(seconds=600)).isoformat()
    for workflow_id, session_id, user_id, tenant_id in (
        ("tenant-a-workflow", "tenant-a-session", "same-user", "tenant-a"),
        ("tenant-b-workflow", "tenant-b-session", "same-user", "tenant-b"),
        ("other-user-workflow", "other-user-session", "other-user", "tenant-a"),
    ):
        store.create_session(
            session_id, user_id, "m1", metadata={"tenant_id": tenant_id}
        )
        store.create_workflow(
            workflow_id, session_id, "create_campaign", "live", status="running"
        )
        with store._lock:
            store._get_conn().execute(
                "UPDATE workflows SET updated_at = ? WHERE workflow_id = ?",
                (old_timestamp, workflow_id),
            )
            store._get_conn().commit()

    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        workflow_stale_after_seconds=300,
    )
    same_user = runtime.list_resumable_workflows(user_id="same-user")
    assert {item["workflow_id"] for item in same_user} == {
        "tenant-a-workflow", "tenant-b-workflow"
    }
    tenant_a = runtime.list_resumable_workflows(
        user_id="same-user", tenant_id="tenant-a"
    )
    assert [item["workflow_id"] for item in tenant_a] == ["tenant-a-workflow"]

    with pytest.raises(PermissionError, match="different tenant"):
        runtime.get_workflow("tenant-b-workflow", tenant_id="tenant-a")

    with pytest.raises(PermissionError, match="different user"):
        runtime.get_workflow("other-user-workflow", user_id="same-user")


def test_provider_reconciler_uses_only_runtime_read_callback():
    class Client:
        platform = "meta"

        def get_campaign(self, campaign_id):
            return {"id": campaign_id, "name": "provider-campaign", "status": "ACTIVE"}

    class Reconciler(ProviderReconciler):
        def reconcile(self, context):
            result = context.execute_read(
                "meta_get_campaign", {"campaign_id": "c1"}
            )
            assert result.success is True
            return ReconciliationObservation(
                sequence=int(context.item["sequence"]),
                status="succeeded",
                verified=True,
                source="test-provider-readback",
                observed_at="2026-01-01T00:00:00+00:00",
                output_data=result.data,
                provider_resource_id="c1",
            )

    store = AdAgentStore(":memory:")
    store.create_session("reconcile-session", "u1", "m1")
    store.create_workflow(
        "reconcile-workflow", "reconcile-session", "create_campaign", "live",
        status="failed",
    )
    store.add_workflow_item(
        "reconcile-workflow:1", "reconcile-workflow", 1, "meta",
        "meta_create_campaign", "failed", {"account_id": "m1", "campaign_id": "c1"},
        error="provider timeout",
    )
    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1"]),
        provider_reconcilers={"meta": Reconciler()},
    )
    runtime.register_capability(create_meta_capability(Client()))
    principal = RequestPrincipal(
        user_id="u1", tenant_id="default",
        permissions=frozenset({"ads.read", "ads.reconcile"}),
        account_scope={"meta": {"m1"}},
    )

    workflow = runtime.reconcile_workflow_from_provider(
        "reconcile-workflow", principal=principal
    )
    assert workflow["status"] == "succeeded"
    assert workflow["items"][0]["output_data"]["_reconciliation"]["source"] == "test-provider-readback"


def test_turn_tool_budget_stops_long_create_chain():
    runtime = AgentRuntime(require_llm=False,
        max_tool_calls=1,
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    runtime.register_capability(create_meta_capability())
    result = runtime.run(
        "创建 Meta campaign 名称=budget-test",
        account_id="m1",
    )

    assert result["results"][0]["success"] is True
    assert any(item.get("data", {}).get("execution_status") == "budget_exceeded"
               for item in result["results"])


def test_missing_tool_permission_fails_closed_before_handler_execution():
    calls = []

    class Handler:
        def execute(self, _ctx, _input):
            calls.append(True)
            return type("Result", (), {"success": True, "data": {}})()

    from agents.ad_agent.core.interfaces import ParsedIntent

    class Parser:
        def parse(self, _text, _ctx):
            return ParsedIntent(
                intent_type="permission_test", raw_input="test", platforms=["meta"]
            )

    class Router:
        def route(self, _intent, registry):
            definition, _ = registry.get("permissioned_read")
            return {"meta": [definition]}

    runtime = AgentRuntime(require_llm=False,
        intent_parser=Parser(),
        intent_router=Router(),
        whitelist_validator=_whitelist(meta=["m1"]),
        granted_permissions=set(),
    )
    runtime.registry.register(
        ToolDefinition(
            name="permissioned_read",
            skill="test",
            platform="meta",
            description="permission test",
            input_schema=ToolSchema(properties={"account_id": {"type": "string"}}),
            effect_class=ToolEffect.READ,
            required_permissions=["ads.read"],
        ),
        Handler(),
    )
    result = runtime.run("test", account_id="m1")
    assert result["results"][0]["success"] is False
    assert "ads.read" in result["results"][0]["error"]
    assert calls == []


def test_builtin_tools_declare_read_or_plan_permissions():
    runtime = AgentRuntime(require_llm=False, whitelist_validator=_whitelist(meta=["m1"]))
    runtime.register_capability(create_meta_capability())
    tools = runtime.registry.list_all()

    assert tools
    assert all(tool.required_permissions for tool in tools)
    assert all(
        set(tool.required_permissions)
        == ({"ads.plan"} if tool.is_write_tool else {"ads.read"})
        for tool in tools
    )


def test_trusted_principal_overrides_user_id_and_restricts_accounts():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(require_llm=False,
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1", "m2"]),
    )
    runtime.register_capability(create_meta_capability())
    principal = RequestPrincipal(
        user_id="trusted-user",
        tenant_id="tenant-a",
        permissions=frozenset({"ads.read", "ads.plan"}),
        account_scope={"meta": {"m1"}},
    )

    denied = runtime.run(
        "创建 Meta campaign 名称=Denied",
        user_id="forged-user",
        account_id="m2",
        principal=principal,
    )
    assert denied["results"]
    assert "授权范围" in denied["results"][0]["error"]

    allowed = runtime.run(
        "创建 Meta campaign 名称=Allowed",
        user_id="forged-user",
        account_id="m1",
        principal=principal,
    )
    assert allowed["results"]
    assert store.get_session(allowed["session_id"])["user_id"] == "trusted-user"


def test_workflow_recovery_requires_verified_observations():
    store = AdAgentStore(":memory:")
    store.create_session("recovery-session", "u1", "m1")
    store.create_workflow(
        "recovery-workflow", "recovery-session", "create_campaign", "live",
        status="failed", metadata={"replay_policy": "explicit_operator_confirmation"},
    )
    store.add_workflow_item(
        "recovery-workflow:1", "recovery-workflow", 1, "meta",
        "meta_create_campaign", "failed", {"campaign_id": "c1"},
        error="provider timeout",
    )
    runtime = AgentRuntime(require_llm=False, persistence_store=store)

    plan = runtime.get_workflow_resume_plan("recovery-workflow", user_id="u1")
    assert plan["resumable"] is True
    assert plan["requires_fresh_confirmation"] is True
    assert plan["items"][0]["sequence"] == 1

    with pytest.raises(ValueError, match="verified=true"):
        runtime.reconcile_workflow(
            "recovery-workflow", [{"sequence": 1, "status": "succeeded"}], user_id="u1"
        )

    unknown = runtime.reconcile_workflow(
        "recovery-workflow",
        [{"sequence": 1, "status": "unknown", "verified": True}],
        user_id="u1",
    )
    assert unknown["status"] == "recovery_required"

    succeeded = runtime.reconcile_workflow(
        "recovery-workflow",
        [{"sequence": 1, "status": "succeeded", "verified": True}],
        user_id="u1",
    )
    assert succeeded["status"] == "succeeded"

    with pytest.raises(ValueError, match="does not belong"):
        runtime.reconcile_workflow(
            "recovery-workflow",
            [{"sequence": 99, "status": "succeeded", "verified": True}],
            user_id="u1",
        )
    with pytest.raises(ValueError, match="cannot reconcile"):
        runtime.reconcile_workflow(
            "recovery-workflow",
            [{"sequence": 1, "status": "failed", "verified": True}],
            user_id="u1",
        )


def test_workflow_access_isolated_by_tenant_even_when_user_id_matches():
    store = AdAgentStore(":memory:")
    store.create_session("tenant-session", "same-user", metadata={"tenant_id": "tenant-a"})
    store.create_workflow(
        "tenant-workflow", "tenant-session", "create_campaign", "dry_run", status="failed"
    )
    runtime = AgentRuntime(require_llm=False, persistence_store=store)

    with pytest.raises(PermissionError, match="different tenant"):
        runtime.get_workflow(
            "tenant-workflow", user_id="same-user", tenant_id="tenant-b"
        )


def test_skill_plugin_manifest_mismatch_is_rejected(tmp_path):
    skill_dir = tmp_path / "trusted-skill"
    skill_dir.mkdir()
    plugin = skill_dir / "tools.py"
    plugin.write_text("# local plugin\n", encoding="utf-8")
    (skill_dir / "skill.manifest.json").write_text(
        json.dumps({"skill": "trusted-skill", "files": {"tools.py": "0"}}),
        encoding="utf-8",
    )

    verified, reason = AgentRuntime._verify_skill_plugin(skill_dir, plugin)
    assert verified is False
    assert "hash mismatch" in reason


def test_tool_timeout_returns_explicit_timed_out_result_and_signals_handler():
    observed = {}

    class SlowHandler:
        def execute(self, ctx, _input):
            observed["event"] = ctx.metadata["cancel_event"]
            time.sleep(0.01)
            return type("Result", (), {"success": True, "data": {}})()

    runtime = AgentRuntime(require_llm=False, )
    definition = ToolDefinition(
        name="slow_read",
        skill="test",
        platform="meta",
        description="timeout test",
        input_schema=ToolSchema(),
        effect_class=ToolEffect.READ,
        timeout_seconds=0.001,
    )
    runtime.registry.register(definition, SlowHandler())
    result = runtime._execute_tool(
        ToolContext("timeout-session", "u1"), "slow_read", {}
    )

    assert result.success is False
    assert result.data["execution_status"] == "timed_out"
    assert observed["event"].is_set() is True


def test_golden_intent_cases_remain_deterministic():
    cases = json.loads(
        (Path(__file__).parents[1] / "evals" / "golden_cases.json").read_text(
            encoding="utf-8"
        )
    )
    parser = LLMIntentParser()
    for case in cases:
        intent = parser.parse(case["input"], ToolContext("golden", "eval"))
        assert intent.intent_type == case["intent_type"], case["id"]
        assert intent.platforms == case["platforms"], case["id"]


def test_wiki_error_lookup_honors_limit_without_runtime_name_error():
    tool = WikiQueryTool()
    solutions = tool.get_error_solutions(
        "RESOURCE_EXHAUSTED", platform="google", limit=1
    )

    assert len(solutions) == 1
    assert "重试" in solutions[0]
    assert len(wiki_get_errors("RESOURCE_EXHAUSTED", platform="google", limit=1)) == 1
