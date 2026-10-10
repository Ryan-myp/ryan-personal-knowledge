import pytest
import json
import logging
import requests

from scripts.advertising.campaign_service_e2e import (
    ProviderRecorder,
    SafeFormatter,
    _private_directory,
    classify_evidence,
    readback_checks,
    chat,
    paused_payload,
    safe_evidence,
    summarize_chat,
)


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

    recorder._capture_google_ad_group_statuses(
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
