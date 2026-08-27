"""Harness-level invariants for the single-Agent execution boundary."""

import json
from pathlib import Path

from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.core.interfaces import ToolContext, ToolSchema
from agents.ad_agent.core.intent import LLMIntentParser
from agents.ad_agent.core.tool_registry import SimpleToolRegistry, validate_tool_input
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
    )
    runtime.register_capability(create_meta_capability(Client()))
    result = runtime.run(
        "更新 Meta campaign campaign_id=123 status=PAUSED",
        session_id="s1", user_id="u1", account_id="m1", confirmed=True,
    )

    assert result["results"][0]["success"] is False
    assert "confirmation_payload" in result["results"][0]["error"]
    assert calls == []


def test_parameter_catalogs_expose_static_and_dynamic_options():
    runtime = AgentRuntime(offline_mode=True)
    runtime.register_capability(create_tiktok_capability())

    objective = runtime.list_parameter_options("tiktok", "objective_type")[0]
    app = runtime.list_parameter_options("tiktok", "app_id")[0]
    operating_systems = runtime.list_parameter_options("tiktok", "operating_systems")[0]

    assert objective["source"] == "tool_schema"
    assert "APP_PROMOTION" in {item["value"] for item in objective["options"]}
    assert app["source"] == "lookup"
    assert app["lookup_tool"] == "tiktok_list_apps"
    assert {item["value"] for item in operating_systems["options"]} == {"ANDROID", "IOS"}


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
