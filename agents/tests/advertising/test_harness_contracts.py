"""Harness-level invariants for the single-Agent execution boundary."""

import json
import sqlite3
from pathlib import Path
import time
import threading
from datetime import datetime, timedelta
import pytest
import threading

from agents.tools.advertising.providers.meta import create_meta_tool_source
from agents.tools.advertising.providers.google import create_google_tool_source
from agents.tools.advertising.providers.tiktok import create_tiktok_tool_source
from agents.tools.advertising.providers.dv360 import create_dv360_tool_source
from agents.agent_harness.core.interfaces import (
    ToolContext, ToolSchema, ToolDefinition, ToolEffect,
    EffectReconciler, ReconciliationObservation, ToolSourceRuntime,
    ReconciliationContext, ParsedIntent, ToolResult, Skill,
)
from agents.agent_harness.messages import ModelTurn, ToolCall
from agents.agent_platform.data.knowledge.wiki import KnowledgeDocument
from agents.agent_harness.core.intent import LLMIntentParser
from agents.agent_harness.core.tool_registry import SimpleToolRegistry, validate_tool_input
from agents.tools.advertising.wiki_query import WikiQueryTool, wiki_get_errors
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.tools.advertising.shared.domain.parameter_selection import (
    ParameterSelectionError,
    ParameterSelectionSigner,
)
from agents.tools.advertising.clients.base import RateLimiter, TemporaryError
from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from agents.tools.advertising.clients.dv360_client import DV360APIClient
from agents.agent_platform.data.persistence.store import AdAgentStore
from agents.tools.advertising.application.ad_application import AccountWhitelistValidator, AdvertisingComposition
from agents.tools.advertising.application.reconciliation import ToolReadbackReconciler


def _whitelist(**accounts):
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = accounts
    return validator


class _ScriptedHarnessModel:
    """Return explicit model ToolCalls for deterministic Run-boundary tests."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.messages = []

    def complete(self, messages, _tools, _request):
        self.messages.append(list(messages))
        if not self.turns:
            raise AssertionError("Harness requested an unexpected model turn")
        return self.turns.pop(0)


def test_runtime_registry_cannot_bypass_execution_boundary():
    runtime = AdvertisingComposition(require_llm=False, whitelist_validator=_whitelist(meta=["m1"]))
    runtime.register_tool_source(create_meta_tool_source())
    definition, _ = runtime.registry.get("meta_create_campaign")

    result = runtime.registry.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="m1"),
        definition.name,
        {"account_id": "m1", "name": "direct"},
    )

    assert result.success is False
    assert "owning Runtime" in result.error

    definition, handler = runtime.registry.get("meta_create_campaign")
    direct_handler_result = handler.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="m1"),
        {"account_id": "m1", "name": "direct"},
    )
    assert direct_handler_result.success is False
    assert "owning Runtime" in direct_handler_result.error
    assert runtime.registry.execute_authorized(
        ToolContext(session_id="s1", user_id="u1", account_id="m1"),
        definition.name,
        {"account_id": "m1", "name": "direct"},
    ).success is False


def test_account_scoped_child_read_does_not_require_parent_input_mapping():
    read_tool = ToolDefinition(
        name="account_scoped_creative_get",
        skill="test",
        namespace="tiktok",
        description="Read a creative by account and creative ID",
        input_schema=ToolSchema(
            required=["account_id", "creative_id"],
            properties={
                "account_id": {"type": "string"},
                "creative_id": {"type": "string"},
            },
        ),
        action="get",
        resource_type="creative",
        resource_id_field="creative_id",
        parent_resource_type="ad_group",
        intent_types=["get_creative"],
        effect_class=ToolEffect.READ,
    )

    assert read_tool.routing_metadata_errors() == []

    write_tool = ToolDefinition(
        name="parent_scoped_creative_create",
        skill="test",
        namespace="tiktok",
        description="Create a creative under an ad group",
        input_schema=ToolSchema(
            required=["account_id", "creative_id"],
            properties={
                "account_id": {"type": "string"},
                "creative_id": {"type": "string"},
            },
        ),
        action="create",
        resource_type="creative",
        resource_id_field="creative_id",
        parent_resource_type="ad_group",
        intent_types=["create_creative"],
        effect_class=ToolEffect.WRITE,
    )

    assert "parent_resource_id_field" in write_tool.routing_metadata_errors()


def test_skill_unload_rolls_back_when_catalog_refresh_fails_once():
    class Handler:
        def execute(self, _ctx, _input_data):
            return ToolResult.ok({"value": "kept"})

    class CustomSkill(Skill):
        name = "atomic-unload"
        namespace = "meta"
        description = "Atomic unload test Skill"

        def __init__(self):
            self.definition = ToolDefinition(
                name="atomic_unload_read",
                skill=self.name,
                namespace=self.namespace,
                description="read a local resource",
                input_schema=ToolSchema(),
                action="read",
                resource_type="insight",
                intent_types=["atomic_unload_read"],
            )

        def get_tools(self):
            return [self.definition]

        def get_tool_handler(self, tool_name):
            return Handler() if tool_name == self.definition.name else None

    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    skill = CustomSkill()
    assert runtime.register_skill(skill, "meta") is True
    original_refresh = runtime._refresh_tool_catalog
    failed = {"value": False}

    def fail_once():
        if not failed["value"]:
            failed["value"] = True
            raise RuntimeError("forced catalog refresh failure")
        return original_refresh()

    runtime._refresh_tool_catalog = fail_once
    assert runtime.unload_skill("meta") is False
    assert [tool.name for tool in runtime.registry.list_all()] == [
        "atomic_unload_read"
    ]
    assert runtime.get_loaded_skills()["atomic-unload"] is skill
    assert runtime.plugin_registry.get("skill:atomic-unload").state.value == "active"

    runtime._refresh_tool_catalog = original_refresh
    assert runtime.unload_skill("meta") is True
    assert runtime.registry.list_all() == []


def test_skill_lifecycle_serializes_register_and_unload():
    class Handler:
        def execute(self, _ctx, _input_data):
            return ToolResult.ok({"value": "kept"})

    class SlowSkill(Skill):
        name = "serialized-lifecycle"
        namespace = "meta"
        description = "Lifecycle serialization test"

        def __init__(self):
            self.definition = ToolDefinition(
                name="serialized_lifecycle_read",
                skill=self.name,
                namespace=self.namespace,
                description="read a local resource",
                input_schema=ToolSchema(),
                action="read",
                resource_type="insight",
                intent_types=["serialized_lifecycle_read"],
            )

        def get_tools(self):
            return [self.definition]

        def get_tool_handler(self, tool_name):
            return Handler() if tool_name == self.definition.name else None

    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    entered_refresh = threading.Event()
    release_refresh = threading.Event()
    original_refresh = runtime._refresh_tool_catalog

    def blocked_refresh():
        entered_refresh.set()
        assert release_refresh.wait(timeout=2)
        return original_refresh()

    runtime._refresh_tool_catalog = blocked_refresh
    register_result = []
    unregister_result = []
    register_thread = threading.Thread(
        target=lambda: register_result.append(
            runtime.register_skill(SlowSkill(), "meta")
        )
    )
    register_thread.start()
    assert entered_refresh.wait(timeout=2)

    unload_thread = threading.Thread(
        target=lambda: unregister_result.append(runtime.unload_skill("meta"))
    )
    unload_thread.start()
    assert not unregister_result

    release_refresh.set()
    register_thread.join(timeout=2)
    unload_thread.join(timeout=2)
    assert register_result == [True]
    assert unregister_result == [True]
    assert runtime.registry.list_all() == []


def test_provider_tools_own_cross_channel_campaign_actions():
    """Cross-channel actions use regular Provider Tools and schemas."""
    sources = {
        "meta": create_meta_tool_source(),
        "google-ads": create_google_tool_source(),
        "tiktok": create_tiktok_tool_source(),
        "dv360": create_dv360_tool_source(),
    }

    for namespace, source in sources.items():
        campaign_updates = [
            definition
            for definition, _executor in source.register_tools()
            if definition.action == "update"
            and definition.resource_type == "campaign"
            and "cross_channel_batch_pause" in definition.intent_types
        ]
        assert campaign_updates, namespace
        for tool in campaign_updates:
            assert {"cross_channel_batch_pause", "cross_channel_batch_resume"} <= set(
                tool.intent_types
            )
            assert tool.effect_class == ToolEffect.WRITE
            assert tool.resource_id_field in tool.input_schema.properties
            assert "updates" in tool.input_schema.properties


def test_tool_source_unload_clears_tools_and_derived_discovery_indexes():
    """A Tool Source unload must be symmetric with registration."""
    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    runtime.register_tool_source(create_meta_tool_source())

    assert runtime.registry.list_by_namespace("meta")
    assert "meta_create_campaign" in {
        definition.name for definition in runtime.registry.list_all()
    }
    assert runtime.parameter_catalogs.list("meta")
    assert runtime.list_ad_formats("meta")

    assert runtime.unload_skill("meta") is True

    assert runtime.registry.list_by_namespace("meta") == []
    assert runtime.parameter_catalogs.list("meta") == []
    assert runtime.list_ad_formats("meta") == []
    assert runtime.skill_loader.get_by_namespace("meta") == []


def test_tool_source_registration_rolls_back_partial_tool_registration():
    """A failed provider configure must not leave a half-loaded Tool Source."""

    class PartialToolSource:
        platform_name = "partial-provider"

        def configure(self, context):
            context.registry.register(
                ToolDefinition(
                    name="partial_provider_first",
                    skill="partial-provider",
                    namespace="partial-provider",
                    description="first tool",
                    input_schema=ToolSchema(),
                ),
                lambda _ctx, _input: ToolResult.ok({"ok": True}),
            )
            raise RuntimeError("provider configure failed")

    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    with pytest.raises(RuntimeError, match="provider configure failed"):
        runtime.register_tool_source(PartialToolSource())

    assert runtime.registry.list_by_namespace("partial-provider") == []
    assert runtime.parameter_catalogs.list("partial-provider") == []
    assert "partial-provider" not in runtime.get_loaded_skills()


def test_harness_executes_model_requested_tools_from_registered_catalog():
    class Handler:
        def execute(self, _ctx, _input_data):
            return ToolResult.ok({"executed": True})

    model = _ScriptedHarnessModel(ModelTurn(tool_calls=(
        ToolCall("call-first", "route_first", {}),
        ToolCall("call-second", "route_second", {}),
    )), ModelTurn(content="两个读取已完成。"))
    runtime = AdvertisingComposition(
        require_llm=False,
        llm_client=model,
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    for name in ("route_first", "route_second"):
        runtime.registry.register(
            ToolDefinition(
                name=name, skill="route-test", namespace="meta", description=name,
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
    model = _ScriptedHarnessModel(ModelTurn(content="查到了相关资料。"))
    runtime = AdvertisingComposition(
        require_llm=False,
        llm_client=model,
        knowledge_provider=provider,
    )
    result = runtime.run("查询 Meta campaign", account_id=None)

    assert provider.calls
    prompt = "\n".join(
        str(message.content)
        for turn in model.messages
        for message in turn
        if message.role == "system"
    )
    assert "meta:campaigns.md" in prompt
    assert "fixture" in prompt
    assert "0.9" in prompt
    assert result["tool_selection"]["tools"] == []
    assert not hasattr(provider, "add")


def test_direct_runtime_rejects_non_object_platform_params():
    result = AdvertisingComposition(require_llm=False, ).run("查询 Meta campaign", platform_params=[])
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
    runtime = AdvertisingComposition(require_llm=False,
        whitelist_validator=_whitelist(tiktok=["t1"]),
        execution_mode="live",
        allow_live_writes=True,
        live_approved_tools={"tiktok_create_adgroup"},
    )
    runtime.register_tool_source(create_tiktok_tool_source())
    definition, _handler = runtime._get_registered_tool("tiktok_create_adgroup")

    result = runtime.tool_executor.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="t1"),
        definition.name,
        {},
    )

    assert result.success is False
    assert result.data["execution_status"] == "provider_unavailable"
    assert "不会返回本地模拟结果" in result.error


def test_lookup_contract_must_reference_same_provider_read_tool():
    class BadLookupToolSource:
        def configure(self, context):
            context.registry.register(
                ToolDefinition(
                    name="bad_dynamic_tool",
                    skill="bad-skill",
                    namespace="tiktok",
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
            return ToolSourceRuntime()

    with pytest.raises(ValueError, match="unknown lookup tool"):
        AdvertisingComposition(require_llm=False, ).register_tool_source(BadLookupToolSource())


def test_provider_specific_rate_limiters_use_request_deadline():
    for client in (TikTokAPIClient({}), DV360APIClient({})):
        client._rate_limiter = RateLimiter(max_requests=1, period=60)
        client.acquire_rate_limit(client._rate_limiter)
        client.set_request_budget(0.001)
        with pytest.raises(TemporaryError, match="deadline"):
            client.acquire_rate_limit(client._rate_limiter)


def test_report_requests_do_not_outlive_request_deadline():
    client = TikTokAPIClient({})
    client.set_request_budget(1e-9)
    with pytest.raises(TemporaryError, match="deadline"):
        client.get_report("123", date_preset="LAST_7_DAYS")

    client = DV360APIClient({})
    client.set_request_budget(1e-9)
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

    runtime = AdvertisingComposition(require_llm=False,
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=_whitelist(meta=["m1"]),
        execution_mode="live",
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_tool_source(create_meta_tool_source(Client()))
    runtime.registry.get("meta_update_campaign")[0].live_support = True
    runtime.inject_llm(_ScriptedHarnessModel(ModelTurn(tool_calls=(
        ToolCall(
            "update-call", "meta_update_campaign",
            {"campaign_id": "123", "updates": {"status": "PAUSED"}},
        ),
    )), ModelTurn(content="写入已被确认门禁拦截。")))
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

    runtime = AdvertisingComposition(require_llm=False,
        whitelist_validator=_whitelist(meta=["m1"]),
        execution_mode="live",
        allow_live_writes=True,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_tool_source(create_meta_tool_source(Client()))
    runtime.registry.get("meta_update_campaign")[0].live_support = True
    runtime.write_guard = None
    runtime.inject_llm(_ScriptedHarnessModel(ModelTurn(tool_calls=(
        ToolCall(
            "update-call", "meta_update_campaign",
            {"campaign_id": "123", "updates": {"status": "PAUSED"}},
        ),
    )), ModelTurn(content="写入已被 WriteGuard 门禁拦截。")))
    result = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="s-no-guard", user_id="u1", account_id="m1",
    )

    assert result["results"][0]["success"] is False
    assert "WriteGuard" in result["results"][0]["error"]
    assert calls == []


def test_parameter_catalogs_expose_static_and_dynamic_options():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_tiktok_tool_source())

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
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())
    runtime.register_tool_source(create_meta_tool_source())
    runtime.register_tool_source(create_tiktok_tool_source())

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
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.register_tool_source(create_google_tool_source())

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
        {
            "ad_group_id": "123", "product_group_type": "brand", "value": "Acme",
            "cpc_bid_micros": 250000,
        },
        include_tool_requirements=True,
    ) == []
    assert validate_tool_input(
        product_group.input_schema,
        {"ad_group_id": "123", "product_group_type": "brand"},
        include_tool_requirements=True,
    )
    runtime.register_tool_source(create_meta_tool_source())
    meta_formats = {item["format_id"]: item for item in runtime.list_ad_formats("meta")}
    assert meta_formats["lead.instant_form"]["coverage"] == "supported_dry_run"
    assert meta_formats["lead.instant_form"]["tool_names"] == ["meta_create_lead_ad"]


def test_workflow_state_machine_and_cancel_are_durable():
    store = AdAgentStore(":memory:")
    store.create_session("s1", "u1", "m1")
    store.create_workflow("w1", "s1", "create_campaign", "dry_run", "running")

    assert store.update_workflow("w1", "planned") is True
    assert store.update_workflow("w1", "succeeded") is False

    runtime = AdvertisingComposition(require_llm=False,
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    store.update_workflow("w1", "running")
    assert runtime.cancel_workflow("w1", "u1") is True
    assert runtime.get_workflow("w1", "u1")["status"] == "cancelled"


def test_harness_schema_gate_prevents_invalid_create_from_becoming_workflow():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(require_llm=False,
        llm_client=_ScriptedHarnessModel(
            ModelTurn(tool_calls=(ToolCall("create-call", "meta_create_campaign", {}),)),
            ModelTurn(content="需要更多创建参数。"),
        ),
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    runtime.register_tool_source(create_meta_tool_source())
    result = runtime.run(
        "创建 Meta campaign 名称=checkpointed",
        session_id="checkpoint-session", user_id="u1", account_id="m1",
    )

    # The Harness enforces the Tool schema; the application does not create a
    # separate workflow or clarification state machine.
    assert result["workflow_id"] is None
    assert result["results"] == []
    assert result["needs_input"] is True
    assert result["tool_results"][0]["is_error"] is True


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
        resource_type="campaign",
    )
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store)

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
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store)

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
    runtime = AdvertisingComposition(require_llm=False,
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
    runtime = AdvertisingComposition(require_llm=False,
        persistence_store=store,
        workflow_stale_after_seconds=300,
    )

    assert runtime.workflow.heartbeat("heartbeat-workflow") is True
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

    runtime = AdvertisingComposition(require_llm=False,
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

    runtime = AdvertisingComposition(require_llm=False,
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

    class Reconciler(EffectReconciler):
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
                external_resource_id="c1",
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
    runtime = AdvertisingComposition(require_llm=False,
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1"]),
        effect_reconcilers={"meta": Reconciler()},
    )
    runtime.register_tool_source(create_meta_tool_source(Client()))
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
    calls = []

    class Handler:
        def execute(self, _ctx, _input):
            calls.append(True)
            return ToolResult.ok({"read": True})

    model = _ScriptedHarnessModel(
        ModelTurn(tool_calls=(ToolCall("first-call", "budget_read", {}),)),
        ModelTurn(tool_calls=(ToolCall("second-call", "budget_read", {}),)),
    )
    runtime = AdvertisingComposition(require_llm=False,
        llm_client=model,
        max_tool_calls=1,
        enforce_account_scope=False,
    )
    runtime.register_tool(
        ToolDefinition(
            name="budget_read", skill="budget", namespace="records",
            description="Read a budget test record",
            input_schema=ToolSchema(), action="get", resource_type="record",
            intent_types=["budget_read"], effect_class=ToolEffect.READ,
        ),
        Handler(),
    )

    result = runtime.run("read budget test record")

    assert result["status"] == "failed"
    assert result["runtime_signals"]["tool_call_budget_exceeded"] is True
    assert result["tool_call_count"] == 1
    assert [item["success"] for item in result["results"]] == [True, False]
    assert calls == [True]
    assert len(model.messages) == 2


def test_missing_tool_permission_fails_closed_before_handler_execution():
    calls = []

    class Handler:
        def execute(self, _ctx, _input):
            calls.append(True)
            return type("Result", (), {"success": True, "data": {}})()

    runtime = AdvertisingComposition(require_llm=False,
        llm_client=_ScriptedHarnessModel(
            ModelTurn(tool_calls=(ToolCall("read-call", "permissioned_read", {}),)),
            ModelTurn(content="读取已被权限门禁拦截。"),
        ),
        whitelist_validator=_whitelist(meta=["m1"]),
        granted_permissions=set(),
    )
    runtime.registry.register(
        ToolDefinition(
            name="permissioned_read",
            skill="test",
            namespace="meta",
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
    runtime = AdvertisingComposition(require_llm=False, whitelist_validator=_whitelist(meta=["m1"]))
    runtime.register_tool_source(create_meta_tool_source())
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
    runtime = AdvertisingComposition(require_llm=False,
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1", "m2"]),
    )
    runtime.register_tool_source(create_meta_tool_source())
    runtime.inject_llm(_ScriptedHarnessModel(ModelTurn(tool_calls=(
        ToolCall("list-call", "meta_list_campaigns", {"account_id": "m2"}),
    )), ModelTurn(tool_calls=(
            ToolCall("list-call-allowed", "meta_list_campaigns", {"account_id": "m1"}),
        )),
        ModelTurn(content="读取已按可信身份执行。"),
    ))
    principal = RequestPrincipal(
        user_id="trusted-user",
        tenant_id="tenant-a",
        permissions=frozenset({"ads.read", "ads.plan"}),
        account_scope={"meta": {"m1"}},
    )

    denied = runtime.run(
        "查询 Meta campaign",
        user_id="forged-user",
        account_id="m2",
        principal=principal,
    )
    assert denied["results"]
    assert denied["results"][0]["success"] is False
    assert "授权范围" in denied["results"][0]["error"]

    allowed = runtime.run(
        "查询 Meta campaign",
        user_id="forged-user",
        account_id="m1",
        principal=principal,
    )
    assert allowed["results"], allowed
    assert "授权范围" not in allowed["results"][0].get("error", "")
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
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store)

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
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store)

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

    verified, reason = AdvertisingComposition._verify_skill_plugin(skill_dir, plugin)
    assert verified is False
    assert "hash mismatch" in reason


def test_tool_timeout_returns_explicit_timed_out_result_and_signals_handler():
    observed = {}

    class SlowHandler:
        def execute(self, ctx, _input):
            observed["event"] = ctx.metadata["cancel_event"]
            time.sleep(0.01)
            return type("Result", (), {"success": True, "data": {}})()

    runtime = AdvertisingComposition(require_llm=False, )
    definition = ToolDefinition(
        name="slow_read",
        skill="test",
        namespace="meta",
        description="timeout test",
        input_schema=ToolSchema(),
        effect_class=ToolEffect.READ,
        timeout_seconds=0.001,
    )
    runtime.registry.register(definition, SlowHandler())
    result = runtime.tool_executor.execute(
        ToolContext("timeout-session", "u1"), "slow_read", {}
    )

    assert result.success is False
    assert result.data["execution_status"] == "timed_out"
    assert observed["event"].is_set() is True


def test_run_cancellation_is_visible_to_provider_handler():
    observed = {}
    cancellation = threading.Event()
    handler_started = threading.Event()

    class CancellableHandler:
        def execute(self, ctx, _input):
            observed["event"] = ctx.metadata["cancel_event"]
            handler_started.set()
            cancellation.wait(2)
            return ToolResult.ok({"finished": True})

    runtime = AdvertisingComposition(require_llm=False)
    definition = ToolDefinition(
        name="cancellable_read",
        skill="test",
        namespace="meta",
        description="cancellation propagation test",
        input_schema=ToolSchema(),
        effect_class=ToolEffect.READ,
        timeout_seconds=1,
    )
    runtime.registry.register(definition, CancellableHandler())
    context = ToolContext(
        "cancellable-session",
        "u1",
        metadata={"cancellation_event": cancellation},
    )
    result_holder = {}
    worker = threading.Thread(
        target=lambda: result_holder.setdefault(
            "result",
            runtime.tool_executor.execute(
                context, "cancellable_read", {}
            ),
        ),
    )
    worker.start()
    assert handler_started.wait(1)
    cancellation.set()
    worker.join(2)

    assert observed["event"].is_set() is True
    assert result_holder["result"].success is True


def test_write_tool_timeout_is_unknown_and_requires_reconciliation():
    class SlowWriteHandler:
        def execute(self, _ctx, _input):
            time.sleep(0.01)
            return ToolResult.ok({"provider_id": "should-not-be-trusted"})

    runtime = AdvertisingComposition(require_llm=False)
    definition = ToolDefinition(
        name="slow_write",
        skill="test",
        namespace="meta",
        description="timeout test",
        input_schema=ToolSchema(),
        effect_class=ToolEffect.EXTERNAL_WRITE,
        timeout_seconds=0.001,
    )
    runtime.registry.register(definition, SlowWriteHandler())
    result = runtime.tool_executor.execute(
        ToolContext("timeout-write-session", "u1"), "slow_write", {}
    )

    assert result.success is False
    assert result.data["execution_status"] == "unknown"
    assert result.data["requires_reconciliation"] is True
    assert "不能直接重试" in result.error


def test_tool_timeout_capacity_stays_reserved_until_handler_exits():
    from agents.tools.advertising.application.tool_executor import ToolExecutor

    finished = threading.Event()

    class SlowHandler:
        def execute(self, _ctx, _input):
            finished.wait(2)
            return ToolResult.ok({"late": True})

    runtime = AdvertisingComposition(require_llm=False)
    definition = ToolDefinition(
        name="bounded_slow_read",
        skill="test",
        namespace="meta",
        description="bounded timeout test",
        input_schema=ToolSchema(),
        effect_class=ToolEffect.READ,
        timeout_seconds=0.001,
    )
    runtime.registry.register(definition, SlowHandler())
    runtime.tool_executor = ToolExecutor(runtime.services)
    runtime.tool_executor._in_flight_capacity = threading.BoundedSemaphore(1)

    first = runtime.tool_executor.execute(
        ToolContext("bounded-timeout-session", "u1"), "bounded_slow_read", {}
    )
    second = runtime.tool_executor.execute(
        ToolContext("bounded-timeout-session", "u1"), "bounded_slow_read", {}
    )
    finished.set()

    assert first.data["execution_status"] == "timed_out"
    assert second.data["execution_status"] == "capacity_exceeded"


def test_execution_mode_overrides_are_isolated_by_principal():
    runtime = AdvertisingComposition(require_llm=False, execution_mode="dry_run")
    try:
        runtime.set_execution_mode("live", tenant_id="tenant-a", user_id="operator-a")

        assert runtime.get_execution_mode("tenant-a", "operator-a") == "live"
        assert runtime.get_execution_mode("tenant-a", "operator-b") == "dry_run"
        assert runtime.get_execution_mode("tenant-b", "operator-a") == "dry_run"
        assert runtime.execution_mode == "dry_run"
    finally:
        if runtime.task_executor:
            runtime.task_executor.shutdown(wait=True)


def test_execution_mode_preference_survives_runtime_restart(tmp_path):
    db_path = tmp_path / "execution-mode.db"
    store = AdAgentStore(str(db_path))
    first = AdvertisingComposition(
        require_llm=False, execution_mode="dry_run", persistence_store=store,
    )
    first.set_execution_mode("live", tenant_id="tenant-a", user_id="operator-a")
    assert store.get_execution_mode("tenant-a", "operator-a") == "live"
    first.task_executor.shutdown(wait=True)
    store.close()

    restarted_store = AdAgentStore(str(db_path))
    second = AdvertisingComposition(
        require_llm=False, execution_mode="dry_run", persistence_store=restarted_store,
    )
    try:
        assert second.get_execution_mode("tenant-a", "operator-a") == "live"
        assert second.get_execution_mode("tenant-a", "operator-b") == "dry_run"
        assert second.get_execution_mode("tenant-b", "operator-a") == "dry_run"
    finally:
        second.task_executor.shutdown(wait=True)
        restarted_store.close()


def test_invalid_persisted_execution_mode_fails_back_to_deployment_default():
    store = AdAgentStore(":memory:")
    store.set_execution_mode("tenant-a", "operator-a", "not-a-mode")
    runtime = AdvertisingComposition(
        require_llm=False, execution_mode="dry_run", persistence_store=store,
    )
    try:
        assert runtime.get_execution_mode("tenant-a", "operator-a") == "dry_run"
    finally:
        runtime.task_executor.shutdown(wait=True)
        store.close()


def test_execution_mode_cache_is_bounded_and_expires(monkeypatch):
    import agents.tools.advertising.application.ad_runtime_controls as controls_module

    runtime = AdvertisingComposition(require_llm=False, execution_mode="dry_run")
    try:
        for index in range(controls_module._EXECUTION_MODE_CACHE_MAX_ENTRIES + 25):
            runtime.set_execution_mode(
                "dry_run", tenant_id="tenant-a", user_id=f"operator-{index}"
            )
        assert len(runtime._execution_mode_cache) == controls_module._EXECUTION_MODE_CACHE_MAX_ENTRIES
        assert ("tenant-a", "operator-0") not in runtime._execution_mode_cache

        runtime.set_execution_mode("live", tenant_id="tenant-a", user_id="operator-expiring")
        monkeypatch.setattr(controls_module.time, "monotonic", lambda: 10_000_000)
        assert runtime.get_execution_mode("tenant-a", "operator-expiring") == "dry_run"
    finally:
        if runtime.task_executor:
            runtime.task_executor.shutdown(wait=True)


def test_store_records_explicit_schema_migrations():
    store = AdAgentStore(":memory:")
    rows = store._get_conn().execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert [int(row[0]) for row in rows] == list(
        range(1, store.SCHEMA_VERSION + 1)
    )


def test_golden_intent_cases_remain_deterministic():
    cases = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "evals"
            / "advertising"
            / "golden_cases.json"
        ).read_text(
            encoding="utf-8"
        )
    )
    parser = LLMIntentParser()
    definitions = []
    for factory in (
        create_meta_tool_source,
        create_google_tool_source,
        create_tiktok_tool_source,
        create_dv360_tool_source,
    ):
        definitions.extend(definition for definition, _ in factory().register_tools())
    parser.refresh_tool_catalog(definitions)
    parser.register_namespace_aliases("google-ads", ["google", "google ads"])
    parser.register_namespace_aliases("meta", ["meta"])
    parser.register_namespace_aliases("tiktok", ["tiktok"])
    parser.register_namespace_aliases("dv360", ["dv360"])
    from agents.tools.advertising.shared.features.factory import discover_features
    for feature in discover_features():
        parser.register_intent_descriptors(feature.intent_descriptors())
    for case in cases:
        intent = parser.parse(case["input"], ToolContext("golden", "eval"))
        assert intent.intent_type == case["intent_type"], case["id"]
        assert intent.namespaces == case["platforms"], case["id"]


def test_wiki_error_lookup_honors_limit_without_runtime_name_error():
    tool = WikiQueryTool()
    solutions = tool.get_error_solutions(
        "RESOURCE_EXHAUSTED", platform="google", limit=1
    )

    assert len(solutions) == 1
    assert "重试" in solutions[0]
    assert len(wiki_get_errors("RESOURCE_EXHAUSTED", platform="google", limit=1)) == 1


def test_readback_resolution_uses_explicit_metadata_not_tool_name_conventions():
    runtime = AdvertisingComposition(require_llm=False, enforce_account_scope=False)
    write = ToolDefinition(
        name="vendor_mutate_widget_v2",
        skill="vendor",
        namespace="vendor",
        description="Mutate a widget",
        input_schema=ToolSchema(properties={"widget_key": {"type": "string"}}),
        action="update",
        resource_type="widget",
        resource_id_field="widget_key",
        intent_types=["update_widget"],
        effect_class=ToolEffect.WRITE,
    )
    read = ToolDefinition(
        name="vendor_fetch_widget_by_key",
        skill="vendor",
        namespace="vendor",
        description="Fetch a widget",
        input_schema=ToolSchema(
            required=["widget_key"],
            properties={"widget_key": {"type": "string"}},
        ),
        action="get",
        resource_type="widget",
        resource_id_field="widget_key",
        intent_types=["get_widget"],
        effect_class=ToolEffect.READ,
    )
    runtime.registry.register(write, lambda _ctx, _input: ToolResult.ok({}))
    runtime.registry.register(read, lambda _ctx, _input: ToolResult.ok({}))

    assert runtime._resolve_readback_definition(write.name) is read

    ambiguous = ToolDefinition(
        name="vendor_fetch_widget_by_alias",
        skill="vendor",
        namespace="vendor",
        description="Fetch a widget by alias",
        input_schema=read.input_schema,
        action="get",
        resource_type="widget",
        resource_id_field="widget_key",
        intent_types=["get_widget_by_alias"],
        effect_class=ToolEffect.READ,
    )
    runtime.registry.register(ambiguous, lambda _ctx, _input: ToolResult.ok({}))
    assert runtime._resolve_readback_definition(write.name) is None

    write.readback_tool = read.name
    assert runtime._resolve_readback_definition(write.name) is read


def test_generic_readback_uses_tool_declared_identity_for_arbitrary_resource():
    read = ToolDefinition(
        name="vendor_fetch_widget",
        skill="vendor",
        namespace="vendor",
        description="Fetch a widget",
        input_schema=ToolSchema(
            required=["widget_key"],
            properties={"widget_key": {"type": "string"}},
        ),
        action="get",
        resource_type="widget",
        resource_id_field="widget_key",
        intent_types=["get_widget"],
        effect_class=ToolEffect.READ,
    )
    calls = []

    observation = ToolReadbackReconciler("vendor").reconcile(
        ReconciliationContext(
            workflow={},
            item={
                "sequence": 7,
                "tool_name": "vendor_mutate_widget",
                "account_id": "acct-1",
                "input_data": {"widget_key": "w-1"},
            },
            tool_context=ToolContext("session-1", "user-1", account_id="acct-1"),
            execute_read=lambda name, payload: (
                calls.append((name, payload))
                or ToolResult.ok({"payload": {"widget_key": "w-1", "state": "active"}})
            ),
            resolve_read_tool=lambda _write_name: read,
        )
    )

    assert observation.status == "succeeded"
    assert observation.external_resource_id == "w-1"
    assert calls == [(read.name, {"widget_key": "w-1"})]
