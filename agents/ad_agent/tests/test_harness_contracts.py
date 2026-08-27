"""Harness-level invariants for the single-Agent execution boundary."""

import json
from pathlib import Path
import time
from datetime import datetime, timedelta
import pytest

from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.core.interfaces import (
    ToolContext, ToolSchema, ToolDefinition, ToolEffect,
    ProviderReconciler, ReconciliationObservation, CapabilityRuntime,
)
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
    runtime = AgentRuntime(whitelist_validator=_whitelist(meta=["m1"]))
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


def test_direct_runtime_rejects_non_object_platform_params():
    result = AgentRuntime().run("查询 Meta campaign", platform_params=[])
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
    runtime = AgentRuntime(
        whitelist_validator=_whitelist(tiktok=["t1"]),
        execution_mode="live",
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
        AgentRuntime().register_capability(BadLookupCapability())


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

    runtime = AgentRuntime(
        persistence_store=AdAgentStore(":memory:"),
        whitelist_validator=_whitelist(meta=["m1"]),
        execution_mode="live",
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_capability(create_meta_capability(Client()))
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

    runtime = AgentRuntime(
        whitelist_validator=_whitelist(meta=["m1"]),
        execution_mode="live",
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_capability(create_meta_capability(Client()))
    runtime.write_guard = None
    result = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="s-no-guard", user_id="u1", account_id="m1",
    )

    assert result["results"][0]["success"] is False
    assert "WriteGuard" in result["results"][0]["error"]
    assert calls == []


def test_parameter_catalogs_expose_static_and_dynamic_options():
    runtime = AgentRuntime(offline_mode=True)
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


def test_workflow_state_machine_and_cancel_are_durable():
    store = AdAgentStore(":memory:")
    store.create_session("s1", "u1", "m1")
    store.create_workflow("w1", "s1", "create_campaign", "dry_run", "running")

    assert store.update_workflow("w1", "planned") is True
    assert store.update_workflow("w1", "succeeded") is False

    runtime = AgentRuntime(
        persistence_store=store,
        whitelist_validator=_whitelist(meta=["m1"]),
    )
    store.update_workflow("w1", "running")
    assert runtime.cancel_workflow("w1", "u1") is True
    assert runtime.get_workflow("w1", "u1")["status"] == "cancelled"


def test_workflow_write_items_are_checkpointed_before_execution():
    store = AdAgentStore(":memory:")
    runtime = AgentRuntime(
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
    assert len(workflow["items"]) == 3


def test_fresh_running_workflow_is_not_resumable_or_claimed():
    store = AdAgentStore(":memory:")
    store.create_session("fresh-session", "u1", "m1")
    store.create_workflow(
        "fresh-workflow", "fresh-session", "create_campaign", "live",
        status="running",
    )
    runtime = AgentRuntime(
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
    runtime = AgentRuntime(
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

    runtime = AgentRuntime(
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

    runtime = AgentRuntime(
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
    runtime = AgentRuntime(
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
    runtime = AgentRuntime(
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

    runtime = AgentRuntime(
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
    runtime = AgentRuntime(whitelist_validator=_whitelist(meta=["m1"]))
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
    runtime = AgentRuntime(
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
    runtime = AgentRuntime(persistence_store=store)

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
    runtime = AgentRuntime(persistence_store=store)

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

    runtime = AgentRuntime()
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
