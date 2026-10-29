"""Offline report scope acceptance without relaxing principal authorization."""

import pytest

from agents.agent_harness import ModelTurn, ToolCall
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.execution.account_policy import AccountWhitelistValidator
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.tools.advertising.providers.source_factory import create_tool_source


def test_meta_report_declares_its_account_input():
    definition = next(
        binding.definition for binding in create_tool_source("meta").list_bindings()
        if binding.definition.name == "meta_get_campaign_report"
    )
    assert definition.input_schema.properties["account_id"]["type"] == "string"
    assert definition.is_read_tool
    assert "ads.read" in definition.required_permissions


@pytest.mark.parametrize("allowed", [True, False])
def test_meta_report_explicit_account_remains_subject_to_principal_scope(allowed):
    class Model:
        def complete(self, messages, tools, request):
            if messages[-1].role == "tool":
                return ModelTurn(content="已返回离线测试报表。")
            return ModelTurn(tool_calls=(ToolCall(
                id="report", name="meta_get_campaign_report",
                arguments={"account_id": "act_123", "date_preset": "yesterday"},
            ),))

    store = AdAgentStore(":memory:")
    whitelist = AccountWhitelistValidator()
    whitelist.allowed_accounts = {"meta": ["act_123", "act_456"]}
    runtime = AdvertisingComposition(
        persistence_store=store, llm_client=Model(), require_llm=True,
        offline_mode=True, enforce_account_scope=True, start_background_workers=False,
        whitelist_validator=whitelist,
    )
    runtime.register_tool_source(create_tool_source("meta"))
    principal = RequestPrincipal(
        user_id="report-user", tenant_id="report-test", permissions=frozenset({"ads.read"}),
        account_scope={"meta": frozenset({"act_123" if allowed else "act_456"})},
    )
    try:
        result = runtime.run(
            "查询 Meta 昨天的 Campaign 报表，account_id=act_123",
            user_id=principal.user_id, tenant_id=principal.tenant_id,
            session_id="explicit-report-account", principal=principal,
        )
        successful = [row for row in result.get("results", []) if row.get("success")]
        assert bool(successful) is allowed, result
        if allowed:
            assert result["status"] == "succeeded", result
            assert not result.get("needs_input"), result
    finally:
        runtime.close(wait=True)
        store.close()
