import pytest

from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.core.interfaces import ExecutionMode, ReplayPolicy
from agents.ad_agent.api_clients.base import (
    APIError,
    AuthError,
    BasePlatformClient,
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
from agents.ad_agent.skills.registry import SkillRegistry, SkillTool
from agents.ad_agent.core.tool_registry import SimpleToolRegistry
from agents.ad_agent.core.tool_registry import validate_tool_input


def whitelist(**accounts):
    validator = AccountWhitelistValidator.__new__(AccountWhitelistValidator)
    validator.allowed_accounts = accounts
    return validator


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


def test_redaction_handles_json_and_python_dict_strings():
    redact = AgentRuntime._redact_for_persistence
    value = redact(
        "{'access_token': 'SECRET', \"client_secret\": \"CS\", "
        "'private_key': 'KEY', 'partnerId': 'PARTNER', 'perterId': 'TYPO_PARTNER', 'mcc': 'MCC'}"
    )
    for secret in ("SECRET", "CS", "KEY", "PARTNER", "TYPO_PARTNER", "MCC"):
        assert secret not in value
    assert "<redacted>" in value


class MinimalMetaClient:
    platform = "meta"

    def __init__(self):
        self.calls = []

    def update_campaign(self, campaign_id, updates):
        self.calls.append((campaign_id, updates))
        return {"campaign_id": campaign_id}


def test_confirmation_payload_is_bound_to_the_exact_plan():
    client = MinimalMetaClient()
    runtime = AgentRuntime(
        whitelist_validator=whitelist(meta=["m1"]),
        execution_mode=ExecutionMode.LIVE.value,
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    runtime.register_capability(create_meta_capability(client))
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


def test_legacy_skill_declarations_never_claim_provider_execution():
    registry = SkillRegistry(SimpleToolRegistry())
    handler = registry._create_handler(
        SkillTool(name="undeclared_tool", description="", platform="meta")
    )
    result = handler.execute(None, {})
    assert result.success is False
    assert "no executable Capability handler" in result.error


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
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    first_runtime.register_capability(create_meta_capability(first_client))
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
        live_approved_tools={"meta_update_campaign"},
        granted_permissions={"ads.read", "ads.plan", "ads.write"},
    )
    second_runtime.register_capability(create_meta_capability(second_client))
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
