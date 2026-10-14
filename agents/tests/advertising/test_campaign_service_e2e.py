import pytest
import json
import logging
import requests

from scripts.advertising.campaign_service_e2e import (
    ProviderRecorder,
    SafeFormatter,
    _private_directory,
    _approved_tools,
    classify_evidence,
    readback_checks,
    chat,
    _e2e_request_case,
    paused_payload,
    resolve_selection_tokens,
    safe_evidence,
    summarize_chat,
)


def test_query_service_is_read_only_and_keeps_only_confirmed_test_accounts():
    from scripts.advertising import campaign_service_e2e as driver

    config = driver.build_service_config(driver.CONFIRMED_ACCOUNTS, read_only=True)
    assert config["execution_mode"] == "read_only"
    assert config["execution_timeout_seconds"] == 500.0
    assert config["allow_live_writes"] is False
    assert config["live_approved_tools"] == []
    assert "ads.write" not in config["granted_permissions"]
    assert config["allowed_accounts"] == driver.CONFIRMED_ACCOUNTS
    with pytest.raises(ValueError):
        driver.build_service_config({"meta": ["unconfirmed"]}, read_only=True)


def test_conversation_query_uses_natural_text_and_read_only_allowlist(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from scripts.advertising import campaign_service_e2e as driver

    calls = []
    monkeypatch.setattr(driver, "_load_state", lambda _directory: (
        tmp_path,
        {"base_url": "http://127.0.0.1:8766", "accounts": driver.CONFIRMED_ACCOUNTS},
        {"X-API-Key": "local-fixture"},
    ))
    monkeypatch.setattr(driver, "_json_write", lambda *_args: None)
    payload = {"status": "succeeded", "results": [], "tool_call_count": 0}
    def post(url, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status_code=200, raise_for_status=lambda: None, json=lambda: payload,
        )
    monkeypatch.setattr(driver.requests, "post", post)
    text = "列出这个 Meta 测试账户的 Campaign。"
    driver.conversation_chat(tmp_path, "meta", text, "natural", "query-session")
    body = calls[0]["json"]
    assert body["user_input"] == text
    assert body["account_id"] == "2806375919473667"
    assert body["session_id"] == "query-session"
    assert body["execution_mode"] == "dry_run"
    assert "platform_params" not in body
    assert calls[0]["timeout"] == 500.0
    definitions = {
        binding.definition.name: binding.definition
        for binding in driver.create_tool_source("meta").list_bindings()
    }
    assert body["tool_allowlist"]
    assert all(not definitions[name].is_write_tool for name in body["tool_allowlist"])


def test_parameter_lookup_e2e_scope_requires_confirmed_provider_account():
    from types import SimpleNamespace

    request = SimpleNamespace(
        url=SimpleNamespace(path="/parameter-options/resolve"),
        headers={
            "x-e2e-case": "google-template-assets",
            "x-e2e-provider": "google-ads",
            "x-e2e-account": "9055507554",
        },
        query_params={
            "platform": "google-ads",
            "account_id": "9055507554",
            "tool_name": "google_create_asset_group",
        },
    )

    assert _e2e_request_case(request) == {
        "case_id": "google-template-assets",
        "provider": "google-ads",
        "account": "9055507554",
    }


def test_parameter_lookup_e2e_scope_rejects_unconfirmed_account():
    from types import SimpleNamespace

    request = SimpleNamespace(
        url=SimpleNamespace(path="/parameter-options/resolve"),
        headers={},
        query_params={
            "platform": "google-ads",
            "account_id": "9999999999",
            "tool_name": "google_create_asset_group",
        },
    )

    assert _e2e_request_case(request) == {}


def test_selection_token_helper_resolves_only_exact_requested_values(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _directory: (
            tmp_path,
            {
                "base_url": "http://localhost",
                "accounts": {"google-ads": ["9055507554"]},
            },
            {"X-API-Key": "test-key"},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "options": [
            {
                "value": "customers/9055507554/assets/194802085984",
                "label": "PMax image",
                "selection_token": "ps1.private.signature",
            },
            {
                "value": "customers/9055507554/assets/194802072931",
                "label": "Other image",
                "selection_token": "ps1.other.signature",
            },
        ],
    }).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests,
        "get",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or response),
    )

    resolved = resolve_selection_tokens(
        tmp_path,
        "google-ads",
        "google_create_asset_group",
        {"images": ["customers/9055507554/assets/194802085984"]},
        "google-template-assets",
        "google-template-session",
        lookup_queries={"images": ["194802085984"]},
    )

    assert resolved == {"images": ["ps1.private.signature"]}
    assert calls[0][1]["params"] == {
        "platform": "google-ads",
        "field": "images",
        "tool_name": "google_create_asset_group",
        "account_id": "9055507554",
        "session_id": "google-template-session",
        "query": "194802085984",
    }
    assert calls[0][1]["headers"]["X-E2E-Case"] == "google-template-assets"
    assert calls[0][1]["headers"]["X-E2E-Provider"] == "google-ads"
    assert calls[0][1]["headers"]["X-E2E-Account"] == "9055507554"


def test_selection_token_helper_fails_closed_for_wrong_account_or_missing_value(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    state = {
        "base_url": "http://localhost",
        "accounts": {"google-ads": ["9999999999"]},
    }
    monkeypatch.setattr(
        driver, "_load_state", lambda _directory: (tmp_path, state, {})
    )
    calls = []
    monkeypatch.setattr(
        driver.requests,
        "get",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(ValueError, match="confirmed test account"):
        resolve_selection_tokens(
            tmp_path,
            "google-ads",
            "google_create_asset_group",
            {"images": ["customers/9055507554/assets/194802085984"]},
            "google-template-assets",
            "google-template-session",
        )

    assert calls == []

def test_chat_text_is_not_provider_execution_evidence():
    assert (
        summarize_chat(
            {"reply": "created", "status": "succeeded"}, "google_create_campaign"
        )["passed"]
        is False
    )


def test_only_matching_successful_tool_result_counts_as_execution():
    result = {
        "results": [
            {
                "tool_name": "google_create_campaign",
                "success": True,
                "data": {"campaign_id": "test-id"},
            }
        ]
    }
    assert summarize_chat(result, "google_create_campaign")["passed"] is True
    assert summarize_chat(result, "meta_create_campaign")["passed"] is False


def test_chat_can_submit_a_creation_card_without_widening_tool_scope(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _directory: (
            tmp_path,
            {
                "base_url": "http://localhost",
                "accounts": {"google-ads": ["9055507554"]},
            },
            {"X-API-Key": "test-key"},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "status": "awaiting_input",
        "reply": "submit the form",
        "results": [],
    }).encode()
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr(driver.requests, "post", post)
    driver.chat(
        tmp_path,
        "google-ads",
        "google_create_campaign",
        {"campaign_name": "QA Google Template"},
        "google-template-submit",
        template_id="builtin-template",
        session_id="google-template-session",
        user_input="提交 Google Campaign 创建计划",
    )

    body = calls[0][1]["json"]
    assert "提交 Google Campaign 创建计划" in body["user_input"]
    assert body["tool_allowlist"] == ["google_create_campaign"]
    assert body["creation_template_id"] == "builtin-template"
    assert body["session_id"] == "google-template-session"


def test_coalesced_duplicate_tool_calls_count_as_one_effective_execution():
    result = {
        "tool_call_count": 2,
        "results": [
            {
                "tool": "meta_list_catalogs",
                "success": True,
                "data": {"data_status": "live", "catalogs": []},
            }
        ],
        "tool_results": [
            {"name": "meta_list_catalogs", "success": True},
            {
                "name": "meta_list_catalogs",
                "success": True,
                "runtime_signals": {"duplicate_read_coalesced": True},
            },
        ],
    }

    summary = summarize_chat(result, "meta_list_catalogs")

    assert summary["passed"] is True
    assert summary["model_tool_call_count"] == 2
    assert summary["coalesced_call_count"] == 1
    assert summary["effective_execution_count"] == 1


@pytest.mark.parametrize(
    "rows",
    [
        [
            {"tool": "meta_list_apps", "success": True, "data": {"apps": []}},
            {"tool": "meta_list_apps", "success": True, "data": {"apps": []}},
        ],
        [
            {"tool": "meta_list_apps", "success": True, "data": {"apps": []}},
            {"tool": "meta_list_businesses", "success": True, "data": {"businesses": []}},
        ],
    ],
)
def test_duplicate_or_unrequested_tool_calls_fail_single_tool_evidence(rows):
    assert summarize_chat(
        {"results": rows},
        "meta_list_apps",
    )["passed"] is False


def test_dry_run_plan_disguised_as_a_resource_id_is_not_a_real_write():
    result = {
        "results": [
            {
                "tool": "google_create_campaign",
                "success": True,
                "data": {
                    "campaign_id": {"mode": "dry_run", "execution_status": "planned"}
                },
            }
        ]
    }
    assert summarize_chat(result, "google_create_campaign")["passed"] is False


def test_simulated_query_results_are_not_real_provider_evidence():
    result = {
        "results": [
            {
                "tool": "meta_list_campaigns",
                "success": True,
                "data": {
                    "data_status": "offline_no_client",
                    "simulated": True,
                    "campaigns": [],
                },
            }
        ]
    }
    assert summarize_chat(result, "meta_list_campaigns")["passed"] is False


@pytest.mark.parametrize(
    "provider,expected",
    [("google-ads", "PAUSED"), ("meta", "PAUSED"), ("tiktok", "DISABLE")],
)
def test_all_creation_and_update_fixtures_are_paused(provider, expected):
    data = paused_payload(
        provider, {"name": "QA_test", "updates": {"name": "QA_update"}}
    )
    assert data["updates"]["status"] == expected
    assert data["status"] == expected


def test_evidence_never_retains_confirmation_or_selection_tokens():
    safe = safe_evidence(
        {
            "selection_token": "ps1.private.signature",
            "confirmation_payload": {"confirmation_token": "private"},
            "reply": "choice ps1.private.signature",
        }
    )
    assert "ps1.private.signature" not in str(safe)
    assert safe["selection_token"] == "<redacted>"


def test_evidence_redacts_credential_fields_regardless_of_scalar_type():
    safe = safe_evidence(
        {
            "identity_authorized_bc_id": 123456789,
            "client_id": "private-client",
            "password": "private-password",
            "refresh_token": "private-token",
        }
    )
    assert set(safe.values()) == {"<redacted>"}


def test_evidence_redacts_signed_media_urls():
    signed_url = (
        "https://cdn.example.test/image.jpg?"
        "x-expires=1799999999&x-signature=private-signature"
    )

    safe = safe_evidence(
        {
            "preview_url": signed_url,
            "image_web_uris": [signed_url],
        }
    )

    assert safe["preview_url"] == "<redacted>"
    assert safe["image_web_uris"] == ["<redacted>"]
    assert "private-signature" not in json.dumps(safe)


def test_transport_timeout_is_recorded_without_credential_url(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "timeout", "provider": "meta", "account": "123"}
    request = requests.Request(
        "GET", "https://graph.facebook.com/v25.0/act_123/campaigns?access_token=secret"
    ).prepare()

    def timeout(*args, **kwargs):
        raise requests.ReadTimeout("unsafe URL access_token=secret")

    recorder.original = timeout
    with pytest.raises(requests.ReadTimeout):
        recorder.send(None, request)
    evidence = (tmp_path / "provider-http.jsonl").read_text()
    assert "ReadTimeout" in evidence
    assert "secret" not in evidence
    assert json.loads(evidence)["case_id"] == "timeout"


def test_confirmation_response_is_saved_even_if_second_request_times_out(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _: (
            tmp_path,
            {"base_url": "http://localhost", "accounts": {"meta": ["123"]}},
            {},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(
        {
            "needs_confirmation": True,
            "confirmation_payload": {"confirmation_token": "secret"},
        }
    ).encode()
    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return response
        raise requests.ReadTimeout("private request")

    monkeypatch.setattr(driver.requests, "post", post)
    with pytest.raises(requests.ReadTimeout):
        chat(
            tmp_path,
            "meta",
            "meta_create_campaign",
            {"_e2e_blueprint_id": "meta.traffic_link"},
            "confirmation-timeout",
            write=True,
        )
    evidence = json.loads((tmp_path / "cases/confirmation-timeout.json").read_text())
    assert len(calls) == 2
    assert calls[0]["json"]["tool_allowlist"] == ["meta_create_campaign"]
    assert calls[0]["json"]["creation_blueprint_id"] == "meta.traffic_link"
    assert evidence["phases"][0]["response"]["needs_confirmation"] is True
    assert evidence["phases"][1]["transport_error"] == "ReadTimeout"
    assert "secret" not in json.dumps(evidence)


def test_chat_forwards_template_without_selecting_the_full_blueprint(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _: (
            tmp_path,
            {"base_url": "http://localhost", "accounts": {"meta": ["123"]}},
            {},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "status": "succeeded",
        "results": [{
            "tool_name": "meta_create_adset",
            "success": True,
            "data": {"adset_id": "test-adset"},
        }],
    }).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests,
        "post",
        lambda *args, **kwargs: (calls.append(kwargs) or response),
    )

    chat(
        tmp_path,
        "meta",
        "meta_create_adset",
        {"meta_create_adset": {"campaign_id": "test-campaign"}},
        "template-child",
        write=True,
        template_id="builtin-meta-traffic",
    )

    body = calls[0]["json"]
    assert body["creation_template_id"] == "builtin-meta-traffic"
    assert "creation_blueprint_id" not in body
    evidence = json.loads((tmp_path / "cases/template-child.json").read_text())
    assert evidence["template_id"] == "builtin-meta-traffic"


def test_chat_can_continue_an_existing_template_session(monkeypatch, tmp_path):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _: (
            tmp_path,
            {"base_url": "http://localhost", "accounts": {"meta": ["123"]}},
            {},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({"status": "succeeded"}).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests,
        "post",
        lambda *args, **kwargs: (calls.append(kwargs) or response),
    )

    chat(
        tmp_path,
        "meta",
        "meta_list_catalogs",
        {"limit": 10},
        "template-session-follow-up",
        session_id="template-session-1",
        template_id="builtin-meta-catalog-sales",
    )

    assert calls[0]["json"]["session_id"] == "template-session-1"
    assert calls[0]["json"]["creation_template_id"] == (
        "builtin-meta-catalog-sales"
    )


def test_chat_keeps_selection_tokens_structured_and_redacts_prompt(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _: (
            tmp_path,
            {"base_url": "http://localhost", "accounts": {"meta": ["123"]}},
            {},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({"status": "succeeded"}).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests,
        "post",
        lambda *args, **kwargs: (calls.append(kwargs) or response),
    )
    token = "ps1.private.signature"

    chat(
        tmp_path,
        "meta",
        "meta_create_campaign",
        {
            "meta_create_campaign": {
                "catalog_id": "catalog-1",
                "selection_tokens": {"catalog_id": token},
            }
        },
        "selection-token-prompt",
        write=True,
    )

    body = calls[0]["json"]
    assert token not in body["user_input"]
    assert body["platform_params"]["meta"]["meta_create_campaign"][
        "selection_tokens"
    ]["catalog_id"] == token
    evidence = json.loads(
        (tmp_path / "cases/selection-token-prompt.json").read_text()
    )
    assert token not in json.dumps(evidence)


def test_chat_keeps_blueprint_metadata_out_of_tool_arguments(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _: (
            tmp_path,
            {"base_url": "http://localhost", "accounts": {"meta": ["123"]}},
            {},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({"status": "succeeded"}).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests,
        "post",
        lambda *args, **kwargs: (calls.append(kwargs) or response),
    )

    chat(
        tmp_path,
        "meta",
        "meta_create_campaign",
        {
            "_e2e_blueprint_id": "meta.traffic_link",
            "_e2e_blueprint_version": "1.2.0",
            "name": "QA_TEMPLATE_CAMPAIGN",
        },
        "template-blueprint-metadata",
        template_id="builtin-meta-traffic",
    )

    body = calls[0]["json"]
    assert body["creation_blueprint_id"] == "meta.traffic_link"
    assert body["creation_blueprint_version"] == "1.2.0"
    assert body["platform_params"]["meta"] == {"name": "QA_TEMPLATE_CAMPAIGN"}
    assert "_e2e_blueprint_id" not in body["user_input"]
    assert "_e2e_blueprint_version" not in body["user_input"]


def test_test_deployment_blocks_other_meta_account_paths(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "cross-account", "provider": "meta", "account": "123"}
    request = requests.Request(
        "GET", "https://graph.facebook.com/v25.0/act_999/campaigns"
    ).prepare()
    with pytest.raises(PermissionError, match="test account"):
        recorder._guard(request, "meta", {})


@pytest.mark.parametrize(
    "operation_status",
    ["ENABLE", "ACTIVE", ""],
)
def test_tiktok_creation_requires_explicit_disabled_status(
    tmp_path, operation_status
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "tiktok-status",
        "provider": "tiktok",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://business-api.tiktok.com/open_api/v1.3/smart_plus/campaign/create/",
        json={
            "advertiser_id": "123",
            "operation_status": operation_status,
        },
    ).prepare()

    with pytest.raises(PermissionError, match="DISABLE"):
        recorder._guard(request, "tiktok", json.loads(request.body))


def test_google_customer_mutate_requires_paused_campaign_operations(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "google-status",
        "provider": "google-ads",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://googleads.googleapis.com/v24/customers/123/googleAds:mutate",
        json={"mutateOperations": [{
            "campaignOperation": {
                "create": {"campaignName": "test", "status": "ENABLED"}
            }
        }]},
    ).prepare()

    with pytest.raises(PermissionError, match="PAUSED"):
        recorder._guard(request, "google-ads", json.loads(request.body))


def test_google_product_group_is_approved_for_template_e2e():
    assert "google_create_product_group" in _approved_tools()


def test_google_pmax_listing_filter_is_approved_for_template_e2e():
    assert "google_create_asset_group_listing_group_filter" in _approved_tools()


def test_google_pmax_listing_filter_requires_verified_paused_asset_group(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    request_data = {
        "operations": [{
            "create": {
                "assetGroup": "customers/9055507554/assetGroups/77",
                "type": "UNIT_INCLUDED",
                "listingSource": "SHOPPING",
            }
        }]
    }
    path = (
        "/v24/customers/9055507554/"
        "assetGroupListingGroupFilters:mutate"
    )

    with pytest.raises(PermissionError, match="verified PAUSED Asset Group"):
        recorder._guard_google(request_data, path)

    recorder._capture_google_paused_resources(
        {"results": [{"assetGroup": {"id": "77", "status": "PAUSED"}}]}
    )
    assert recorder.paused_asset_groups == {"77"}
    recorder._guard_google(request_data, path)


@pytest.mark.parametrize("status", [None, "ENABLED"])
def test_google_product_group_creation_requires_explicit_paused_status(
    tmp_path, status
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "google-product-group-status",
        "provider": "google-ads",
        "account": "123",
    }
    create = {
        "adGroup": "customers/123/adGroups/456",
        "listingGroup": {"type": "SUBDIVISION"},
    }
    if status is not None:
        create["status"] = status
    request = requests.Request(
        "POST",
        "https://googleads.googleapis.com/v24/customers/123/adGroupCriteria:mutate",
        json={"operations": [{"create": create}]},
    ).prepare()

    with pytest.raises(PermissionError, match="Product Group.*PAUSED"):
        recorder._guard(request, "google-ads", json.loads(request.body))


def test_google_product_group_creation_accepts_explicit_paused_status(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "google-product-group-status",
        "provider": "google-ads",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://googleads.googleapis.com/v24/customers/123/adGroupCriteria:mutate",
        json={
            "operations": [{
                "create": {
                    "adGroup": "customers/123/adGroups/456",
                    "status": "PAUSED",
                    "listingGroup": {"type": "SUBDIVISION"},
                }
            }]
        },
    ).prepare()

    recorder._guard(request, "google-ads", json.loads(request.body))


def test_google_app_ad_requires_a_previously_read_paused_parent(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    data = {"mutateOperations": [{
        "adGroupAdOperation": {
            "create": {
                "adGroup": "customers/123/adGroups/77",
                "status": "ENABLED",
                "ad": {"appAd": {"headlines": [{"text": "Install"}]}},
            }
        }
    }]}

    with pytest.raises(PermissionError, match="verified PAUSED parent"):
        recorder._guard_google(
            data,
            "/v24/customers/123/googleAds:mutate",
        )

    recorder._capture_google_paused_resources(
        {"results": [{"adGroup": {"id": "77", "status": "PAUSED"}}]}
    )
    assert recorder.paused_ad_groups == {"77"}
    recorder._guard_google(
        data,
        "/v24/customers/123/googleAds:mutate",
    )


def test_service_restart_reuses_private_persistence_directory(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    (tmp_path / "state.json").write_text(
        json.dumps({"private_auth_file": str(private / "key")})
    )
    assert _private_directory(tmp_path) == private


def test_write_success_requires_real_mutation_transport_evidence():
    case = {
        "tool": "meta_update_campaign",
        "response": {
            "results": [
                {
                    "tool": "meta_update_campaign",
                    "success": True,
                    "data": {"resource_id": "123"},
                }
            ]
        },
    }
    reads = [{"method": "GET", "path": "/v25.0/123", "http_status": 200}]
    assert classify_evidence(case, reads, write=True) == "no_provider_evidence"
    assert (
        classify_evidence(
            case,
            [{"method": "POST", "path": "/v25.0/123", "http_status": 200}],
            write=True,
        )
        == "verified"
    )


def test_tiktok_http_200_with_business_error_is_not_a_verified_write():
    case = {
        "tool": "tiktok_create_campaign",
        "response": {
            "results": [
                {
                    "tool": "tiktok_create_campaign",
                    "success": True,
                    "data": {"campaign_id": "123"},
                }
            ]
        },
    }
    assert (
        classify_evidence(
            case,
            [
                {
                    "method": "POST",
                    "path": "/campaign/create/",
                    "http_status": 200,
                    "provider_code": 40001,
                }
            ],
            write=True,
        )
        == "no_provider_evidence"
    )


def test_test_service_logs_redact_api_keys_even_when_printed_as_plain_text(monkeypatch):
    monkeypatch.setenv("AD_AGENT_API_KEY", "fixture-private-api-value")
    record = logging.LogRecord(
        "test", logging.ERROR, "", 0, "unsafe fixture-private-api-value", (), None
    )
    assert "fixture-private-api-value" not in SafeFormatter().format(record)


def test_business_error_ids_are_not_added_to_owned_resource_allowlist(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "business-error",
        "provider": "tiktok",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://business-api.tiktok.com/open_api/v1.3/campaign/create/",
        json={"advertiser_id": "123", "operation_status": "DISABLE"},
    ).prepare()
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(
        {"code": 40002, "data": {"campaign_id": "456"}}
    ).encode()
    recorder.original = lambda *_args, **_kwargs: response
    recorder.send(None, request)
    assert recorder.created == set()


def test_successful_transport_does_not_hide_an_unchanged_requested_name():
    read = {
        "tool": "tiktok_get_campaign",
        "provider": "tiktok",
        "response": {
            "results": [
                {
                    "tool": "tiktok_get_campaign",
                    "success": True,
                    "data": {
                        "campaign": {
                            "campaign_id": "123",
                            "campaign_name": "old",
                            "operation_status": "DISABLE",
                        }
                    },
                }
            ]
        },
    }
    checks = readback_checks(read, "123", {"name": "new", "status": 0})
    assert checks["name"]["passed"] is False
    assert checks["status"]["passed"] is True


def test_report_ignores_non_case_json_artifacts(tmp_path, capsys):
    from scripts.advertising.campaign_service_e2e import report

    cases = tmp_path / "cases"
    cases.mkdir()
    (tmp_path / "provider-http.jsonl").write_text("", encoding="utf-8")
    (cases / "created-resource-ids.json").write_text(
        json.dumps({"resources": ["campaign-1"]}), encoding="utf-8"
    )
    (cases / "valid-case.json").write_text(
        json.dumps({
            "provider": "meta",
            "tool": "meta_list_campaigns",
            "params": {},
            "response": {
                "results": [{
                    "tool": "meta_list_campaigns",
                    "success": True,
                    "data": {"campaigns": []},
                }],
            },
        }),
        encoding="utf-8",
    )

    report(tmp_path)

    document = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert [case["case_id"] for case in document["cases"]] == ["valid-case"]
    assert "1" in capsys.readouterr().out


def test_ad_readback_checks_the_real_creative_reference():
    read = {"tool": "meta_get_ad", "provider": "meta", "response": {"results": [{
        "tool": "meta_get_ad", "success": True,
        "data": {"ad": {"id": "123", "creative": {"id": "456"}}},
    }]}}
    assert readback_checks(read, "123", {"creative_id": "456"})["creative_id"]["passed"] is True


@pytest.mark.parametrize(
    "tool,record",
    [
        (
            "tiktok_get_adgroup",
            {
                "adgroup_id": "123",
                "adgroup_name": "updated-resource",
                "campaign_id": "456",
                "campaign_name": "parent-campaign",
            },
        ),
        (
            "tiktok_get_ad",
            {
                "ad_id": "123",
                "ad_name": "updated-resource",
                "adgroup_id": "456",
                "adgroup_name": "parent-group",
                "campaign_id": "789",
                "campaign_name": "parent-campaign",
            },
        ),
    ],
)
def test_name_readback_does_not_use_parent_resource_names(tool, record):
    read = {
        "tool": tool,
        "provider": "tiktok",
        "response": {
            "results": [
                {"tool": tool, "success": True, "data": {"resource": record}}
            ]
        },
    }
    checks = readback_checks(read, "123", {"name": "updated-resource"})
    assert checks["name"]["passed"] is True
    assert checks["name"]["observed"] == "updated-resource"
