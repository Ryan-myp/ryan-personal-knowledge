"""Read grants must never expand the test-account mutation boundary."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import yaml

from agents.agent_harness.core.interfaces import ToolResult
from agents.agent_harness.messages import ModelTurn
from agents.agent_harness.redaction import redact_for_persistence
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.execution.account_policy import AccountWhitelistValidator
from agents.applications.advertising.execution.ad_tool_policy_factory import AdvertisingToolPolicyFactory
from agents.applications.advertising.integrations.ad_capability_catalog import AdvertisingCapabilityCatalog
from agents.applications.advertising.integrations.mcp.runtime_mcp import RuntimeMCPServers
from agents.deployments.advertising.api.security import RequestAuthorizer
from agents.tests.advertising.harness_models import call, install
from agents.tests.advertising.test_conversation_account_scope import (
    QueryClient, _chat_client, _close, _principal, _prompt, _runtime,
)
from agents.tools.advertising.providers.tiktok.provider import _account_listing_arguments


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("Permission tests must not call external services")

    monkeypatch.setattr(requests.Session, "request", blocked)


def _reader(namespace="meta"):
    return replace(
        _principal(namespace),
        provider_read_namespaces=frozenset({namespace}),
    )


def test_trusted_read_claim_roundtrips_without_expanding_write_scope():
    principal = RequestPrincipal.from_claims({
        "user_id": "service",
        "permissions": ["ads.read", "ads.plan"],
        "account_scope": {"Google Ads": ["test-account"]},
        "provider_read_namespaces": ["Google Ads", "meta"],
    })
    restored = RequestPrincipal.from_claims(principal.to_safe_dict())
    assert restored == principal
    assert restored.provider_read_namespaces == frozenset({"google-ads", "meta"})
    assert not restored.allows_account("meta", "production-account")


def test_legacy_principal_snapshot_does_not_gain_optional_grants():
    assert "provider_read_namespaces" not in _principal().to_safe_dict()


def test_read_grant_survives_persistence_redaction():
    claims = redact_for_persistence(_reader().to_safe_dict())
    assert RequestPrincipal.from_claims(claims) == _reader()


def test_scheduled_read_preserves_the_trusted_read_grant(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        principal = _reader()
        schedule = runtime.create_schedule(
            name="Read report", prompt="只查询账户报表",
            cron_expression="0 9 * * *", timezone="Asia/Shanghai",
            principal=principal,
        )
        stored = runtime.get_schedule(
            schedule["schedule_id"], user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        assert RequestPrincipal.from_claims(stored["metadata"]["principal"]) == principal
        runtime.scheduling_service.submit_task = lambda *_args, **_kwargs: (
            {"task_id": "fake-read-task", "status": "queued"}, True,
        )
        result = runtime.run_schedule_now(
            schedule["schedule_id"], user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        assert result["task"]["task_id"] == "fake-read-task"
    finally:
        _close(runtime)


@pytest.mark.parametrize("value", ["meta", True, {}, ["*"], [""], [None]])
def test_malformed_read_namespace_claim_fails_closed(value):
    with pytest.raises(ValueError):
        RequestPrincipal.from_claims({
            "user_id": "service", "provider_read_namespaces": value,
        })


def test_deployment_reads_are_opt_in_and_do_not_change_test_allowlist(tmp_path):
    path = tmp_path / "accounts.yaml"
    path.write_text(
        "allowed_accounts:\n  meta: ['test-account']\n"
        "provider_read_namespaces: [meta, 'Google Ads']\n",
        encoding="utf-8",
    )
    validator = AccountWhitelistValidator(str(path))
    assert validator.provider_read_namespaces == frozenset({"meta", "google-ads"})
    assert not validator.validate_account("meta", "production-account")[0]
    path.write_text("allowed_accounts:\n  meta: ['test-account']\n", encoding="utf-8")
    validator.reload()
    assert validator.provider_read_namespaces == frozenset()
    path.unlink()
    validator.reload()
    assert validator.allowed_accounts == {}


def test_shared_principal_gets_read_claim_but_keyed_identity_does_not():
    runtime = SimpleNamespace(
        _granted_permissions={"ads.read", "ads.plan"},
        whitelist_validator=SimpleNamespace(
            allowed_accounts={"meta": ["test-account"]},
            provider_read_namespaces=frozenset({"meta"}),
        ),
    )
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: runtime,
        api_key_getter=lambda: "service-key",
        principals_getter=lambda: {"user-key": {
            "user_id": "tenant-user", "permissions": ["ads.read"],
            "account_scope": {"meta": ["test-account"]},
        }},
        allow_unauthenticated_getter=lambda: False,
    )
    shared = authorizer.configured_service_principal()
    assert shared.provider_read_namespaces == frozenset({"meta"})
    assert authorizer.authorize("user-key").provider_read_namespaces == frozenset()


@pytest.mark.parametrize("namespace,prefix,field", [
    ("meta", "meta", "account_id"),
    ("google-ads", "google", "customer_id"),
    ("tiktok", "tiktok", "account_id"),
])
def test_non_test_account_read_reaches_exact_requested_account(
    tmp_path, namespace, prefix, field,
):
    provider = QueryClient(namespace)
    runtime = _runtime(tmp_path, namespace, provider)
    try:
        install(
            runtime,
            ModelTurn(tool_calls=(call(f"{prefix}_list_campaigns", {
                field: "production-account",
            }),)),
            ModelTurn(content="查询完成。"),
        )
        result = runtime.run(
            f"查询 {namespace} 账户 production-account 的 Campaign",
            principal=_reader(namespace),
        )
        assert result["status"] == "succeeded", result
        assert provider.calls == [("campaigns", "production-account")]
    finally:
        _close(runtime)


def test_report_read_preserves_provider_error_and_never_switches_account(tmp_path):
    class DeniedClient(QueryClient):
        def get_campaign_report(self, account_id, *args, **kwargs):
            self.calls.append(("report", account_id))
            raise PermissionError("Provider denied account access")

    provider = DeniedClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    try:
        install(
            runtime,
            ModelTurn(tool_calls=(call("meta_get_campaign_report", {
                "account_id": "production-account", "campaign_ids": ["101"],
            }),)),
            ModelTurn(content="该账户的渠道访问权限不足。"),
        )
        result = runtime.run("查询指定账户报表", principal=_reader())
        assert provider.calls == [("report", "production-account")]
        assert result["results"][0]["success"] is False
        assert "Provider denied account access" in result["results"][0]["error"]
    finally:
        _close(runtime)


@pytest.mark.parametrize("namespace,prefix,field", [
    ("meta", "meta", "account_id"),
    ("google-ads", "google", "customer_id"),
    ("tiktok", "tiktok", "account_id"),
])
def test_read_grant_does_not_authorize_non_test_writes(
    tmp_path, namespace, prefix, field,
):
    runtime = _runtime(tmp_path, namespace, QueryClient(namespace))
    try:
        tool, _ = runtime.registry.get(f"{prefix}_create_campaign")
        factory = AdvertisingToolPolicyFactory(runtime)
        request = SimpleNamespace(
            principal=_reader(namespace), context={}, execution_mode="dry_run",
        )
        denied = factory._account_scope_error(
            tool, request, {field: "production-account"}, namespace, {},
        )
        assert denied[0] == "scope_denied"
        assert factory._account_scope_error(
            tool, request, {field: "test-account"}, namespace, {},
        ) is None
    finally:
        _close(runtime)


def test_restrictive_principal_and_body_claims_cannot_inherit_shared_read_grant(tmp_path):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    runtime.whitelist_validator.provider_read_namespaces = frozenset({"meta"})
    try:
        install(
            runtime,
            ModelTurn(tool_calls=(call("meta_list_campaigns", {
                "account_id": "production-account",
            }),)),
            ModelTurn(content="请求被拒绝。"),
        )
        with _chat_client(runtime, _principal()) as client:
            response = client.post("/chat", json={
                "user_input": "查询 Meta production-account 的 Campaign",
                "provider_read_namespaces": ["meta"],
                "user_id": "ad-agent-service",
            })
        assert response.status_code in {200, 422}
        assert provider.calls == []
    finally:
        _close(runtime)


def test_account_discovery_and_catalog_honor_read_claim(tmp_path):
    runtime = _runtime(tmp_path, client=QueryClient("meta"))
    try:
        tool, _ = runtime.registry.get("meta_list_accounts")
        records = [
            {"id": "act_test-account", "name": "Test"},
            {"id": "act_production-account", "name": "Production"},
        ]
        result = runtime.security.filter_account_discovery_result(
            tool, ToolResult.ok({"accounts": records}),
            _reader().account_scope,
            provider_read_namespaces=_reader().provider_read_namespaces,
        )
        assert result.data["accounts"] == records
        restricted = runtime.security.filter_account_discovery_result(
            tool, ToolResult.ok({"accounts": records}), _principal().account_scope,
        )
        assert restricted.data["accounts"] == records[:1]
        request = SimpleNamespace(principal=_reader(), execution_mode="dry_run")
        catalog = AdvertisingCapabilityCatalog(runtime)
        assert catalog.read_account_candidates(request) == {}
        assert "credential" in catalog.build(request).lower()
    finally:
        _close(runtime)


def test_empty_write_scope_does_not_hide_read_tools_for_credential_reader(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        principal = replace(_reader(), account_scope={})
        tool, _ = runtime.registry.get("meta_get_campaign_report")
        catalog = AdvertisingCapabilityCatalog(runtime)
        assert catalog._visible_to_principal(
            tool, SimpleNamespace(principal=principal, execution_mode="dry_run"),
        )
        allowed, _ = runtime._validate_account_with_principal(
            "meta", "production-account", False, principal.account_scope,
            provider_read_namespaces=principal.provider_read_namespaces,
        )
        assert allowed
        assert not runtime._validate_account_with_principal(
            "meta", "production-account", True, principal.account_scope,
            provider_read_namespaces=principal.provider_read_namespaces,
        )[0]
    finally:
        _close(runtime)


@pytest.mark.parametrize("endpoint", ["/chat", "/chat/stream"])
def test_non_test_report_and_followup_keep_requested_account(tmp_path, endpoint):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    try:
        install(
            runtime,
            ModelTurn(tool_calls=(call("meta_get_campaign_report", {
                "account_id": "production-account", "campaign_ids": ["101"],
            }),)),
            ModelTurn(content="花费为 12.50。"),
            ModelTurn(tool_calls=(call("meta_list_campaigns", {}),)),
            ModelTurn(content="同一账户的 Campaign 列表。"),
        )
        with _chat_client(runtime, _reader()) as client:
            first = _prompt(
                client, "只分析 Meta production-account 昨天的报表",
                endpoint=endpoint,
            )
            followup = _prompt(client, "再看看这个账户的 Campaign", endpoint=endpoint)
        assert first["status"] == "succeeded", first
        assert followup["status"] == "succeeded", followup
        assert provider.calls[0][0:2] == ("report", "production-account")
        assert provider.calls[1] == ("campaigns", "production-account")
    finally:
        _close(runtime)


def test_mcp_reads_non_test_account_but_cannot_bypass_write_scope(tmp_path):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    principal = replace(_reader(), permissions=frozenset({"ads.read", "ads.plan", "ads.write"}))
    gateway = RuntimeMCPServers(lambda: runtime, lambda *_args: principal)
    try:
        result = gateway.invoke_for_principal(
            runtime, principal, "meta_list_campaigns",
            {"account_id": "production-account"}, source="test",
            account_id="production-account",
        )
        assert result["success"], result
        assert provider.calls == [("campaigns", "production-account")]
        with pytest.raises(PermissionError):
            gateway.invoke_for_principal(
                runtime, principal, "meta_create_campaign",
                {"account_id": "production-account", "name": "must-not-create",
                 "objective": "OUTCOME_TRAFFIC"},
                source="test",
            )
        assert provider.calls == [("campaigns", "production-account")]
    finally:
        _close(runtime)


def test_read_grant_keeps_known_cross_channel_and_argument_mismatch_checks(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        principal = replace(
            _reader(), account_scope={"meta": frozenset({"test-account"}),
                                      "tiktok": frozenset({"other-channel-account"})},
        )
        tool, _ = runtime.registry.get("meta_list_campaigns")
        factory = AdvertisingToolPolicyFactory(runtime)
        request = SimpleNamespace(principal=principal)
        assert factory._account_scope_error(
            tool, request, {"account_id": "other-channel-account"}, "meta", {},
        )[0] == "scope_mismatch"
        assert factory._account_scope_error(
            tool, request, {"account_id": "production-account"}, "meta",
            {"account_id": "different-account"},
        )[0] == "scope_mismatch"
    finally:
        _close(runtime)


def test_test_deployment_approves_supported_campaign_writes_only():
    from agents.tools.advertising.providers.source_factory import create_tool_source

    root = Path(__file__).resolve().parents[3]
    config = yaml.safe_load((root / "agents/ad_agent/config.test-live.yaml").read_text())
    allowed_resources = {
        "campaign", "ad_set", "ad_group", "ad", "creative", "asset_group",
        "listing_group_filter", "product_group", "creative_portfolio",
    }
    approved = set(config["live_approved_tools"])
    for namespace in ("meta", "tiktok", "google-ads"):
        for binding in create_tool_source(namespace).list_bindings():
            tool = binding.definition
            if tool.is_write_tool and tool.live_support and tool.resource_type in allowed_resources:
                assert tool.name in approved
            if tool.name in approved:
                assert tool.resource_type in allowed_resources
                assert tool.live_support


@pytest.mark.parametrize("config", [
    "provider_read_namespaces: meta\n",
    "provider_read_namespaces: ['*']\n",
    "provider_read_namespaces: [\n",
])
def test_invalid_policy_reload_revokes_old_grants(tmp_path, config):
    path = tmp_path / "policy.yaml"
    path.write_text(
        "allowed_accounts: {meta: ['test-account']}\nprovider_read_namespaces: [meta]\n",
        encoding="utf-8",
    )
    validator = AccountWhitelistValidator(str(path))
    path.write_text(config, encoding="utf-8")
    validator.reload()
    assert validator.provider_read_namespaces == frozenset()
    assert validator.allowed_accounts == {}


def test_explicit_credential_read_directory_is_not_restricted_to_selected_account():
    context = SimpleNamespace(
        account_id="test-account", metadata={"authorized_account_ids": None},
    )
    args, _ = _account_listing_arguments(
        context, {"advertiser_ids": ["production-account", "test-account"]},
    )
    assert args == (["production-account", "test-account"],)
    with pytest.raises(PermissionError):
        _account_listing_arguments(
            SimpleNamespace(account_id="test-account", metadata={}),
            {"advertiser_ids": ["production-account"]},
        )


def test_parameter_lookup_uses_the_same_read_grant_without_authorizing_writes(tmp_path):
    provider = QueryClient("meta")
    runtime = _runtime(tmp_path, client=provider)
    principal = _reader()
    try:
        selection = runtime.resolve_parameter_options(
            "meta", "campaign_id", "meta_create_adset", "production-account",
            user_id=principal.user_id, tenant_id=principal.tenant_id,
            account_scope=principal.account_scope,
            granted_permissions=principal.permissions,
            provider_read_namespaces=principal.provider_read_namespaces,
        )
        assert selection["options"][0]["value"] == "101"
        assert provider.calls == [("campaigns", "production-account")]
        with pytest.raises(PermissionError):
            runtime.resolve_parameter_options(
                "meta", "campaign_id", "meta_create_adset", "production-account",
                account_scope=principal.account_scope,
                granted_permissions=principal.permissions,
            )
        assert provider.calls == [("campaigns", "production-account")]
    finally:
        _close(runtime)
