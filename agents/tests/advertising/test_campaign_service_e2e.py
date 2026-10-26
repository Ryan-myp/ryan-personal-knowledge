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
    assert set(config["granted_permissions"]) == {
        "ads.read",
        "knowledge.read",
        "skills.read",
        "memory.read",
    }
    assert config["allowed_accounts"] == driver.CONFIRMED_ACCOUNTS
    default_config = driver.build_service_config(driver.CONFIRMED_ACCOUNTS)
    assert default_config["execution_mode"] == "dry_run"
    assert default_config["allow_live_writes"] is False
    assert default_config["live_approved_tools"] == []
    live_config = driver.build_service_config(
        driver.CONFIRMED_ACCOUNTS, live=True
    )
    assert live_config["execution_mode"] == "live"
    assert live_config["allow_live_writes"] is True
    assert live_config["allowed_accounts"] == driver.CONFIRMED_ACCOUNTS
    assert {"skills.read", "memory.read"} <= set(live_config["granted_permissions"])
    assert "skills.write" not in live_config["granted_permissions"]
    assert "memory.write" not in live_config["granted_permissions"]
    with pytest.raises(ValueError):
        driver.build_service_config(
            driver.CONFIRMED_ACCOUNTS, read_only=True, live=True
        )
    with pytest.raises(ValueError):
        driver.build_service_config({"meta": ["unconfirmed"]}, read_only=True)


def test_e2e_service_start_validates_durable_memory_before_launch(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace
    from scripts.advertising import campaign_service_e2e as driver

    loaded_roots = []
    monkeypatch.setattr(
        driver,
        "load_live_e2e_memory",
        lambda root: loaded_roots.append(root) or {},
    )
    monkeypatch.setattr(driver, "load_default_local_env", lambda: None)
    monkeypatch.setattr(driver.subprocess, "Popen", lambda *_args, **_kwargs: (
        SimpleNamespace(pid=1234, poll=lambda: None)
    ))
    monkeypatch.setattr(
        driver.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=200),
    )

    driver.start(tmp_path, 8766)

    assert loaded_roots == [driver.ROOT]


@pytest.mark.parametrize("allow_read_tools", [True, False])
def test_conversation_query_scopes_tools_and_live_mode(
    monkeypatch, tmp_path, allow_read_tools
):
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
    driver.conversation_chat(
        tmp_path,
        "meta",
        text,
        "natural",
        "query-session",
        live=True,
        allow_read_tools=allow_read_tools,
    )
    body = calls[0]["json"]
    assert body["user_input"] == text
    assert body["account_id"] == "2806375919473667"
    assert body["session_id"] == "query-session"
    assert body["execution_mode"] == "live"
    assert "platform_params" not in body
    assert calls[0]["timeout"] == 500.0
    definitions = {
        binding.definition.name: binding.definition
        for binding in driver.create_tool_source("meta").list_bindings()
    }
    if allow_read_tools:
        assert body["tool_allowlist"]
        assert all(
            not definitions[name].is_write_tool
            for name in body["tool_allowlist"]
        )
    else:
        assert body["tool_allowlist"] == []


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


def test_selection_token_helper_preserves_scalar_field_shape(monkeypatch, tmp_path):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _directory: (
            tmp_path,
            {
                "base_url": "http://localhost",
                "accounts": driver.CONFIRMED_ACCOUNTS,
            },
            {"X-API-Key": "test-key"},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "options": [{
            "value": "24357433403",
            "selection_token": "ps1.private.signature",
        }],
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
        {"campaign_id": ["24357433403"]},
        "google-parent-lookup",
        "google-parent-session",
    )

    assert resolved == {"campaign_id": "ps1.private.signature"}
    assert len(calls) == 1
    calls.clear()

    with pytest.raises(ValueError, match="exactly one value"):
        resolve_selection_tokens(
            tmp_path,
            "google-ads",
            "google_create_asset_group",
            {"campaign_id": ["24357433403", "24357433404"]},
            "google-parent-lookup",
            "google-parent-session",
        )

    assert calls == []


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
    assert body["user_input"] == "提交 Google Campaign 创建计划"
    assert body["tool_allowlist"] == ["google_create_campaign"]
    assert body["creation_template_id"] == "builtin-template"
    assert body["session_id"] == "google-template-session"


def test_chat_does_not_expose_redacted_selection_token_as_missing_parameter(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({"status": "succeeded", "results": []}).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests, "post",
        lambda *_args, **kwargs: (calls.append(kwargs["json"]) or response),
    )
    driver.chat(
        tmp_path, "tiktok", "tiktok_smart_plus_create_adgroup",
        {"campaign_id": "ps1.private.signature", "location_ids": ["ps1.other.signature"]},
        "selection-token-prompt",
    )
    body = calls[0]
    assert "<redacted>" not in body["user_input"]
    assert "ps1.private.signature" not in body["user_input"]
    assert body["platform_params"]["tiktok"]["campaign_id"] == "ps1.private.signature"


def test_chat_keeps_explicit_user_intent_separate_from_e2e_safety_context(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({"status": "succeeded", "results": []}).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests, "post",
        lambda *_args, **kwargs: (calls.append(kwargs["json"]) or response),
    )
    prompt = "在已创建的 Campaign 下创建暂停的 TikTok Ad Group。"
    driver.chat(
        tmp_path, "tiktok", "tiktok_smart_plus_create_adgroup",
        {"campaign_id": "ps1.private.signature", "operation_status": "DISABLE"},
        "focused-intent", user_input=prompt,
    )
    assert calls[0]["user_input"] == prompt
    assert calls[0]["tool_allowlist"] == ["tiktok_smart_plus_create_adgroup"]


def test_chat_can_run_a_single_live_read_tool(monkeypatch, tmp_path):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver,
        "_load_state",
        lambda _directory: (
            tmp_path,
            {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS},
            {"X-API-Key": "test-key"},
        ),
    )
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "status": "succeeded",
        "results": [{
            "tool": "google_get_campaign",
            "success": True,
            "data": {"campaign": {"id": "campaign-1", "status": "PAUSED"}},
        }],
    }).encode()
    calls = []
    monkeypatch.setattr(
        driver.requests,
        "post",
        lambda *args, **kwargs: (calls.append(kwargs) or response),
    )
    monkeypatch.setattr(driver, "_json_write", lambda *_args: None)

    driver.chat(
        tmp_path,
        "google-ads",
        "google_get_campaign",
        {"campaign_id": "campaign-1"},
        "live-parent-readback",
        live=True,
    )

    assert calls[0]["json"]["execution_mode"] == "live"
    assert calls[0]["json"]["tool_allowlist"] == ["google_get_campaign"]


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
        calls.append(json.loads(json.dumps(kwargs)))
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
    assert calls[1]["json"]["user_input"] == calls[0]["json"]["user_input"]
    assert calls[1]["json"]["confirmed"] is True
    assert calls[1]["json"]["confirmation_payload"] == {
        "confirmation_token": "secret",
    }
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


def test_template_workflow_uses_normal_agent_planning_and_signed_confirmations(
    monkeypatch, tmp_path, capsys
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))
    template = {
        "template_id": "google.test.shopping", "provider": "google-ads",
        "blueprint_id": "google-ads.shopping", "blueprint_version": "1.1.0",
        "account_id": "9055507554", "status": "active",
    }

    def response(value):
        result = requests.Response()
        result.status_code = 200
        result._content = json.dumps(value).encode()
        return result

    monkeypatch.setattr(driver.requests, "get", lambda *_args, **_kwargs: response(template))
    observations = []
    monkeypatch.setattr(
        driver,
        "append_live_e2e_observation",
        lambda *args, **kwargs: observations.append(kwargs),
    )
    approval = {"confirmation_token": "test-only-confirmation", "type": "confirm_write_plan"}
    phases = iter([
        {"status": "awaiting_input", "needs_confirmation": True, "confirmation_payload": approval},
        {"status": "succeeded", "results": [{"tool": "google_create_campaign", "success": True}]},
    ])
    calls = []

    def post(*_args, **kwargs):
        calls.append(json.loads(json.dumps(kwargs["json"])))
        return response(next(phases))

    monkeypatch.setattr(driver.requests, "post", post)
    driver.template_chat(
        tmp_path, "google-ads", "google.test.shopping",
        {"campaign": {"campaign_name": "QA normal workflow", "daily_budget": 5}},
        "native-shopping", write=True, session_id="template-session",
        allow_new_hierarchy=True,
        existing_resources_reconciled=True,
    )
    assert len(calls) == 2
    assert "tool_allowlist" not in calls[0]
    assert "google_create_campaign" not in calls[0]["user_input"]
    assert calls[0]["creation_blueprint_id"] == "google-ads.shopping"
    assert calls[0]["creation_template_id"] == "google.test.shopping"
    assert calls[0]["platform_params"] == {
        "google-ads": {"campaign": {"campaign_name": "QA normal workflow", "daily_budget": 5}},
    }
    assert calls[1]["confirmed"] is True
    assert calls[1]["confirmation_payload"] == approval
    assert calls[1]["user_input"] == calls[0]["user_input"]
    evidence = json.loads((tmp_path / "cases/native-shopping.json").read_text())
    assert "test-only-confirmation" not in json.dumps(evidence)
    assert evidence["e2e_memory"]["template_key"] == "google.test.shopping"
    assert evidence["e2e_memory"]["verification_state"] == "partial_live"
    assert evidence["e2e_memory"]["recovery_plan"]["action"] == (
        "readback_and_resume_existing_hierarchy"
    )
    assert [row["event_type"] for row in observations] == [
        "attempt_started",
        "attempt_completed",
        "attempt_started",
        "attempt_completed",
    ]
    output = capsys.readouterr().out
    assert "e2e_memory_preflight" in output
    assert "readback_and_resume_existing_hierarchy" in output


def test_template_workflow_submits_ready_creation_card_like_the_page(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))
    template = {
        "template_id": "google.test.shopping", "provider": "google-ads",
        "blueprint_id": "google-ads.shopping", "blueprint_version": "1.1.0",
        "account_id": "9055507554", "status": "active",
    }

    def response(value):
        result = requests.Response()
        result.status_code = 200
        result._content = json.dumps(value).encode()
        return result

    monkeypatch.setattr(driver.requests, "get", lambda *_args, **_kwargs: response(template))
    phases = iter([
        {
            "status": "awaiting_input", "needs_input": True, "ui": {"cards": [{
                "type": "ad_creation_form", "title": "Shopping 广告", "ready": True,
                "provider": "google-ads", "account_id": "9055507554",
                "template_id": "google.test.shopping",
                "blueprint_id": "google-ads.shopping",
                "actions": [{"id": "submit_create"}],
                "fields": [
                    {"path": "campaign.name", "provider_field": "name",
                     "tool": "google_create_campaign", "value": "QA Shopping", "visible": True},
                    {"path": "campaign.status", "provider_field": "status",
                     "tool": "google_create_campaign", "value": "PAUSED", "visible": True},
                    {"path": "ad_group.targeting", "provider_field": "targeting.geo",
                     "tool": "google_create_ad_group", "value": "SG", "visible": True},
                    {"path": "ad_group.hidden", "provider_field": "hidden",
                     "tool": "google_create_ad_group", "value": "secret", "visible": False},
                ],
                "selection_tokens": {"campaign_id": "selection-proof"},
                "selection_token_tools": {"campaign_id": "google_create_ad_group"},
            }]},
        },
        {"status": "succeeded", "results": [{
            "tool": "google_create_campaign", "success": True,
        }]},
    ])
    calls = []

    def post(*_args, **kwargs):
        calls.append(json.loads(json.dumps(kwargs["json"])))
        return response(next(phases))

    monkeypatch.setattr(driver.requests, "post", post)
    driver.template_chat(
        tmp_path, "google-ads", "google.test.shopping",
        {"campaign.name": "QA Shopping"}, "submit-ready-card",
    )
    assert len(calls) == 2
    assert calls[1]["user_input"] == "提交“Shopping 广告”创建计划"
    assert calls[1]["platform_params"]["google-ads"] == {
        "name": "QA Shopping", "status": "PAUSED",
        "targeting": {"geo": "SG"},
        "google_create_campaign": {"name": "QA Shopping", "status": "PAUSED"},
        "google_create_ad_group": {
            "targeting": {"geo": "SG"},
            "selection_tokens": {"campaign_id": "selection-proof"},
        },
    }
    evidence = json.loads((tmp_path / "cases/submit-ready-card.json").read_text())
    assert "selection-proof" not in json.dumps(evidence)


def test_template_workflow_never_resubmits_card_after_partial_live_creation(
    monkeypatch, tmp_path,
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))

    def response(value):
        result = requests.Response()
        result.status_code = 200
        result._content = json.dumps(value).encode()
        return result

    monkeypatch.setattr(driver.requests, "get", lambda *_args, **_kwargs: response({
        "template_id": "meta.test.app-promotion",
        "catalog_key": "meta.test.app-promotion",
        "provider": "meta",
        "blueprint_id": "meta.app_promotion",
        "blueprint_version": "1.0.0",
        "account_id": "2806375919473667",
        "status": "active",
    }))
    monkeypatch.setattr(driver, "append_live_e2e_observation", lambda *_a, **_k: None)
    calls = []
    phases = iter([
        {"status": "awaiting_input", "needs_confirmation": True,
         "confirmation_payload": {"type": "confirm_write_plan"}},
        {"status": "awaiting_input", "needs_input": True, "results": [{
            "tool": "meta_create_campaign", "success": True,
            "data": {
                "campaign_id": "120252062235750251",
                "data_status": "live",
                "execution_mode": "live",
            },
        }], "ui": {"cards": [{
            "type": "ad_creation_form", "title": "App Promotion",
            "ready": True, "provider": "meta",
            "account_id": "2806375919473667",
            "template_id": "meta.test.app-promotion",
            "blueprint_id": "meta.app_promotion",
            "actions": [{"id": "submit_create"}], "fields": [],
        }]}},
    ])

    def post(*_args, **kwargs):
        calls.append(kwargs["json"])
        return response(next(phases))

    monkeypatch.setattr(driver.requests, "post", post)
    driver.template_chat(
        tmp_path, "meta", "meta.test.app-promotion", {}, "partial-meta-app",
        write=True, allow_new_hierarchy=True, existing_resources_reconciled=True,
    )
    assert len(calls) == 2
    evidence = json.loads((tmp_path / "cases/partial-meta-app.json").read_text())
    assert evidence["partial_hierarchy_stop"] == [
        {"resource_type": "campaign", "id": "120252062235750251"}
    ]


def test_template_workflow_rejects_a_different_account_before_chat(monkeypatch, tmp_path):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "provider": "google-ads", "account_id": "outside-test-account", "status": "active",
    }).encode()
    monkeypatch.setattr(driver.requests, "get", lambda *_args, **_kwargs: response)
    with pytest.raises(ValueError, match="account"):
        driver.template_chat(tmp_path, "google-ads", "wrong-account", {}, "blocked", write=True)


def test_template_workflow_uses_catalog_key_for_memory_and_builtin_id_for_chat(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))
    template = {
        "template_id": "builtin_traffic",
        "catalog_key": "tiktok.test.traffic",
        "provider": "tiktok",
        "account_id": "7397068114548195329",
        "blueprint_id": "tiktok.traffic_video",
        "blueprint_version": "3.3.0",
        "status": "active",
    }
    get_response = requests.Response()
    get_response.status_code = 200
    get_response._content = json.dumps(template).encode()
    monkeypatch.setattr(driver.requests, "get", lambda *_args, **_kwargs: get_response)
    calls = []
    post_response = requests.Response()
    post_response.status_code = 200
    post_response._content = json.dumps({"status": "succeeded", "results": []}).encode()
    monkeypatch.setattr(
        driver.requests, "post",
        lambda *_args, **kwargs: (calls.append(kwargs["json"]) or post_response),
    )

    driver.template_chat(
        tmp_path, "tiktok", "builtin_traffic", {},
        "builtin-traffic-dry", write=False,
    )

    assert calls[0]["creation_template_id"] == "builtin_traffic"
    evidence = json.loads((tmp_path / "cases/builtin-traffic-dry.json").read_text())
    assert evidence["e2e_memory"]["template_key"] == "tiktok.test.traffic"


def test_template_workflow_does_not_duplicate_a_recorded_live_hierarchy(
    monkeypatch, tmp_path
):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path,
        {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS},
        {},
    ))
    template = {
        "provider": "tiktok",
        "blueprint_id": "tiktok.traffic_video",
        "blueprint_version": "3.3.0",
        "account_id": "7397068114548195329",
        "status": "active",
    }
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(template).encode()
    monkeypatch.setattr(
        driver.requests,
        "get",
        lambda *_args, **_kwargs: response,
    )
    monkeypatch.setattr(
        driver,
        "resolve_template_memory",
        lambda *_args, **_kwargs: {
            "template_key": "tiktok.test.traffic",
            "blueprint_version": "3.3.0",
            "template_values_sha256": "locked",
            "verification_state": "live_verified",
            "known_findings": [],
            "hierarchy_reuse": {
                "prior_live_write_observed": True,
                "requires_reconciliation": True,
                "resource_ids": {"campaign": "existing-campaign"},
                "unresolved_attempt_ids": [],
                "known_hierarchies": [],
            },
            "recovery_plan": {
                "action": "readback_and_resume_existing_hierarchy",
                "instruction": "Use existing resources.",
            },
            "latest_live_test_resources": {
                "campaign_id": "existing-campaign",
                "ad_group_id": "existing-adgroup",
                "ad_id": "existing-ad",
            },
        },
    )
    posts = []
    monkeypatch.setattr(
        driver.requests,
        "post",
        lambda *args, **kwargs: posts.append((args, kwargs)),
    )

    with pytest.raises(ValueError, match="prior live writes"):
        driver.template_chat(
            tmp_path,
            "tiktok",
            "tiktok.test.traffic",
            {"campaign": {"campaign_name": "duplicate"}},
            "duplicate-template",
            write=True,
        )

    assert posts == []


def test_selection_resolution_forwards_declared_parent_lookup_context(monkeypatch, tmp_path):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(driver, "_load_state", lambda _: (
        tmp_path, {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS}, {},
    ))
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        "options": [{"value": "product-set", "selection_token": "signed-test-option"}],
    }).encode()
    calls = []
    monkeypatch.setattr(driver.requests, "get", lambda *_args, **kwargs: (
        calls.append(kwargs) or response
    ))
    result = driver.resolve_selection_tokens(
        tmp_path, "meta", "meta_create_catalog_ad", {"product_set_id": ["product-set"]},
        "catalog-lookup", "catalog-session", lookup_context={"catalog_id": "test-catalog"},
    )
    assert result == {"product_set_id": "signed-test-option"}
    assert json.loads(calls[0]["params"]["lookup_context"]) == {"catalog_id": "test-catalog"}


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


def test_chat_rejects_selection_token_as_resource_value(monkeypatch, tmp_path):
    from scripts.advertising import campaign_service_e2e as driver

    monkeypatch.setattr(
        driver, "_load_state",
        lambda _: (
            tmp_path,
            {"base_url": "http://localhost", "accounts": driver.CONFIRMED_ACCOUNTS},
            {},
        ),
    )
    with pytest.raises(ValueError, match="selection token used as a resource value"):
        driver.chat(
            tmp_path, "tiktok", "tiktok_smart_plus_create_adgroup",
            {"campaign_id": "ps1.private.signature", "operation_status": "DISABLE"},
            "invalid-selection-input", write=True,
        )


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


def test_tiktok_ad_create_accepts_explicitly_disabled_creatives(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "tiktok-ad-status",
        "provider": "tiktok",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://business-api.tiktok.com/open_api/v1.3/ad/create/",
        json={
            "advertiser_id": "123",
            "adgroup_id": "456",
            "creatives": [
                {"ad_name": "paused app ad", "operation_status": "DISABLE"},
            ],
        },
    ).prepare()

    recorder._guard(request, "tiktok", json.loads(request.body))


def test_tiktok_smart_plus_ad_create_accepts_disabled_ad_status(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "tiktok-smart-plus-ad-status",
        "provider": "tiktok",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://business-api.tiktok.com/open_api/v1.3/smart_plus/ad/create/",
        json={
            "advertiser_id": "123",
            "campaign_id": "456",
            "adgroup_id": "789",
            "operation_status": "DISABLE",
            "creative_list": [{
                "creative_info": {
                    "ad_format": "SINGLE_VIDEO",
                    "video_info": {"video_id": "video-1"},
                },
            }],
        },
    ).prepare()

    recorder._guard(request, "tiktok", json.loads(request.body))


@pytest.mark.parametrize("operation_status", ["ENABLE", ""])
def test_tiktok_smart_plus_ad_create_rejects_enabled_or_missing_status(
    tmp_path, operation_status
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "tiktok-smart-plus-ad-status",
        "provider": "tiktok",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://business-api.tiktok.com/open_api/v1.3/smart_plus/ad/create/",
        json={
            "advertiser_id": "123",
            "campaign_id": "456",
            "adgroup_id": "789",
            "operation_status": operation_status,
            "creative_list": [{
                "creative_info": {
                    "ad_format": "SINGLE_VIDEO",
                    "video_info": {"video_id": "video-1"},
                },
            }],
        },
    ).prepare()

    with pytest.raises(PermissionError, match="DISABLE"):
        recorder._guard(request, "tiktok", json.loads(request.body))


@pytest.mark.parametrize(
    "creatives",
    [
        [],
        [{}],
        [{"operation_status": "ENABLE"}],
        [
            {"operation_status": "DISABLE"},
            {"operation_status": "ENABLE"},
        ],
    ],
)
def test_tiktok_ad_create_rejects_missing_or_enabled_creative_status(
    tmp_path, creatives
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "tiktok-ad-status",
        "provider": "tiktok",
        "account": "123",
    }
    request = requests.Request(
        "POST",
        "https://business-api.tiktok.com/open_api/v1.3/ad/create/",
        json={
            "advertiser_id": "123",
            "adgroup_id": "456",
            "creatives": creatives,
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


@pytest.mark.parametrize(
    ("provider", "url", "resource_id", "payload"),
    [
        (
            "google-ads",
            "https://googleads.googleapis.com/v24/customers/123/campaigns:mutate",
            "customers/123/campaigns/456",
            {
                "operations": [{
                    "update": {
                        "resourceName": "customers/123/campaigns/456",
                        "status": "ENABLED",
                    },
                    "updateMask": "status",
                }]
            },
        ),
        (
            "meta",
            "https://graph.facebook.com/v25.0/456",
            "456",
            {"status": "ACTIVE"},
        ),
        (
            "tiktok",
            "https://business-api.tiktok.com/open_api/v1.3/campaign/update/",
            "456",
            {"campaign_id": "456", "operation_status": "ENABLE"},
        ),
    ],
)
def test_live_update_guard_rejects_reenabling_test_resources(
    tmp_path, provider, url, resource_id, payload
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "update-status-guard",
        "provider": provider,
        "account": "123",
    }
    recorder.created.add(resource_id)
    if provider in {"meta", "tiktok"}:
        recorder.created_typed.add((provider, "123", "campaign", resource_id))
    request = requests.Request("POST", url, json=payload).prepare()

    with pytest.raises(PermissionError, match="paused"):
        recorder._guard(request, provider, json.loads(request.body))


@pytest.mark.parametrize(
    ("provider", "url", "resource_id", "payload"),
    [
        (
            "google-ads",
            "https://googleads.googleapis.com/v24/customers/123/campaigns:mutate",
            "customers/123/campaigns/456",
            {
                "operations": [{
                    "update": {
                        "resourceName": "customers/123/campaigns/456",
                        "status": "PAUSED",
                    },
                    "updateMask": "status",
                }]
            },
        ),
        (
            "meta",
            "https://graph.facebook.com/v25.0/456",
            "456",
            {"status": "PAUSED"},
        ),
        (
            "tiktok",
            "https://business-api.tiktok.com/open_api/v1.3/campaign/update/",
            "456",
            {"campaign_id": "456", "operation_status": "DISABLE"},
        ),
    ],
)
def test_live_update_guard_accepts_paused_test_resources(
    tmp_path, provider, url, resource_id, payload
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {
        "case_id": "update-status-guard",
        "provider": provider,
        "account": "123",
    }
    recorder.created.add(resource_id)
    if provider in {"meta", "tiktok"}:
        recorder.created_typed.add((provider, "123", "campaign", resource_id))
    request = requests.Request("POST", url, json=payload).prepare()

    recorder._guard(request, provider, json.loads(request.body))


def test_google_product_group_is_approved_for_template_e2e():
    assert "google_create_product_group" in _approved_tools()


def test_google_pmax_listing_filter_is_approved_for_template_e2e():
    assert "google_create_asset_group_listing_group_filter" in _approved_tools()


def test_live_e2e_write_scope_excludes_non_hierarchy_resources():
    from scripts.advertising import campaign_service_e2e as driver

    approved = set(_approved_tools())
    assert "google_delete_campaign" not in approved
    assert "meta_delete_ad" not in approved
    assert "tiktok_delete_campaign" not in approved
    assert "google_delete_campaign_budget" not in approved
    assert "google_delete_campaign_asset" not in approved
    assert not any("creative" in name for name in approved)
    assert all(
        binding.definition.resource_type in {
            "campaign", "ad_group", "ad_set", "ad", "asset_group",
            "listing_group_filter", "product_group",
        }
        for provider in ("google-ads", "meta", "tiktok")
        for binding in driver.create_tool_source(provider).list_bindings()
        if binding.definition.name in approved
    )


@pytest.mark.parametrize(
    "provider,url,payload",
    [
        ("meta", "https://graph.facebook.com/v19.0/77", {}),
        (
            "tiktok",
            "https://business-api.tiktok.com/open_api/v1.3/campaign/delete/",
            {"advertiser_id": "123", "campaign_ids": [77]},
        ),
        (
            "google-ads",
            "https://googleads.googleapis.com/v24/customers/123/campaigns:mutate",
            {"operations": [{"remove": "customers/123/campaigns/77"}]},
        ),
    ],
)
def test_delete_requires_resource_created_by_same_e2e_run(
    tmp_path, provider, url, payload
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "delete", "provider": provider, "account": "123"}
    method = "DELETE" if provider == "meta" else "POST"
    request = requests.Request(method, url, json=payload).prepare()
    with pytest.raises(PermissionError, match="(created by this test|typed ownership)"):
        recorder._guard(request, provider, payload)
    recorder.created.add("77")
    if provider == "google-ads":
        recorder.created.add("customers/123/campaigns/77")
    else:
        recorder.created_typed.add((provider, "123", "campaign", "77"))
    recorder._guard(request, provider, payload)


def test_provider_recorder_rejects_unrelated_mutations(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "scope", "provider": "meta", "account": "123"}
    request = requests.Request(
        "POST", "https://graph.facebook.com/v19.0/act_123/adcreatives",
        json={"name": "unrelated"},
    ).prepare()
    with pytest.raises(PermissionError, match="outside campaign hierarchy"):
        recorder._guard(request, "meta", {"name": "unrelated"})


@pytest.mark.parametrize(
    "url,payload",
    [
        (
            "https://business-api.tiktok.com/open_api/v1.3/pixel/track/",
            {"advertiser_id": "123", "pixel_code": "77"},
        ),
        (
            "https://business-api.tiktok.com/open_api/v1.3/creative/ads_preview/create/",
            {"advertiser_id": "123", "card_id": "77"},
        ),
        (
            "https://business-api.tiktok.com/open_api/v1.3/file/video/ad/upload/",
            {"advertiser_id": "123"},
        ),
    ],
)
def test_tiktok_rejects_every_non_hierarchy_post(tmp_path, url, payload):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "scope", "provider": "tiktok", "account": "123"}
    request = requests.Request("POST", url, json=payload).prepare()
    with pytest.raises(PermissionError, match="outside campaign hierarchy"):
        recorder._guard(request, "tiktok", payload)


def test_meta_owned_identifier_is_not_enough_to_authorize_untyped_update(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "scope", "provider": "meta", "account": "123"}
    recorder.created.add("77")
    request = requests.Request(
        "POST", "https://graph.facebook.com/v19.0/77",
        json={"name": "changed"},
    ).prepare()
    with pytest.raises(PermissionError, match="typed ownership"):
        recorder._guard(request, "meta", {"name": "changed"})


def test_meta_update_requires_same_account_hierarchy_creation(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "create", "provider": "meta", "account": "123"}
    recorder._capture_ids(
        {"id": "77"}, provider="meta", account="123", resource="campaign"
    )
    restored = ProviderRecorder(tmp_path)
    restored.case = {"case_id": "update", "provider": "meta", "account": "123"}
    request = requests.Request(
        "POST", "https://graph.facebook.com/v19.0/77",
        json={"name": "changed"},
    ).prepare()
    restored._guard(request, "meta", {"name": "changed"})
    restored.case = {"case_id": "update", "provider": "meta", "account": "456"}
    with pytest.raises(PermissionError, match="typed ownership"):
        restored._guard(request, "meta", {"name": "changed"})


def test_tiktok_update_requires_matching_resource_type(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "update", "provider": "tiktok", "account": "123"}
    recorder._capture_ids(
        {"data": {"campaign_id": "77"}},
        provider="tiktok", account="123", resource="campaign",
    )
    payload = {"advertiser_id": "123", "adgroup_id": "77"}
    request = requests.Request(
        "POST", "https://business-api.tiktok.com/open_api/v1.3/adgroup/update/",
        json=payload,
    ).prepare()
    with pytest.raises(PermissionError, match="typed ownership"):
        recorder._guard(request, "tiktok", payload)
    payload = {"advertiser_id": "123", "campaign_id": "77"}
    request = requests.Request(
        "POST", "https://business-api.tiktok.com/open_api/v1.3/campaign/update/",
        json=payload,
    ).prepare()
    recorder._guard(request, "tiktok", payload)


def test_google_gaql_post_is_read_only_for_test_account(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "query", "provider": "google-ads", "account": "123"}
    request = requests.Request(
        "POST",
        "https://googleads.googleapis.com/v24/customers/123/googleAds:search",
        json={"query": "SELECT campaign.id FROM campaign LIMIT 1"},
    ).prepare()
    recorder._guard(
        request, "google-ads",
        {"query": "SELECT campaign.id FROM campaign LIMIT 1"},
    )


def test_google_gaql_rejects_non_query_payload(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "query", "provider": "google-ads", "account": "123"}
    payload = {"query": "SELECT campaign.id FROM campaign", "operations": [{"remove": "x"}]}
    request = requests.Request(
        "POST", "https://googleads.googleapis.com/v24/customers/123/googleAds:search",
        json=payload,
    ).prepare()
    with pytest.raises(PermissionError, match="outside campaign hierarchy"):
        recorder._guard(request, "google-ads", payload)


@pytest.mark.parametrize(
    "resource_name",
    [
        "",
        "customers/999/campaigns/77",
        "customers/123/campaignBudgets/77",
    ],
)
def test_google_update_rejects_missing_cross_account_or_wrong_resource(
    tmp_path, resource_name
):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "update", "provider": "google-ads", "account": "123"}
    payload = {
        "operations": [{
            "update": {"resourceName": resource_name, "status": "PAUSED"},
            "updateMask": "status",
        }]
    }
    request = requests.Request(
        "POST", "https://googleads.googleapis.com/v24/customers/123/campaigns:mutate",
        json=payload,
    ).prepare()
    recorder.created.add(resource_name)
    with pytest.raises(PermissionError, match="test account or hierarchy"):
        recorder._guard(request, "google-ads", payload)


def test_google_ad_content_update_requires_owned_ad_under_test_customer(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    recorder.case = {"case_id": "update", "provider": "google-ads", "account": "123"}
    payload = {
        "operations": [{
            "update": {
                "resourceName": "customers/123/ads/99",
                "responsiveSearchAd": {"headlines": []},
            },
            "updateMask": "responsive_search_ad.headlines",
        }]
    }
    request = requests.Request(
        "POST", "https://googleads.googleapis.com/v24/customers/123/ads:mutate",
        json=payload,
    ).prepare()
    with pytest.raises(PermissionError, match="created by this test"):
        recorder._guard(request, "google-ads", payload)
    recorder.created.add("customers/123/adGroupAds/77~99")
    recorder._guard(request, "google-ads", payload)


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


def test_google_pmax_asset_group_requires_its_created_paused_campaign(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    request_data = {
        "mutateOperations": [{
            "assetGroupOperation": {
                "create": {
                    "campaign": "customers/9055507554/campaigns/77",
                    "status": "PAUSED",
                },
            },
        }],
    }
    path = "/v24/customers/9055507554/googleAds:mutate"

    with pytest.raises(PermissionError, match="created PAUSED Campaign"):
        recorder._guard_google(request_data, path)

    recorder.created.add("77")
    recorder._capture_google_paused_resources(
        {"results": [{"campaign": {"id": "77", "status": "PAUSED"}}]}
    )
    recorder._guard_google(request_data, path)

    recorder.created.clear()
    with pytest.raises(PermissionError, match="created PAUSED Campaign"):
        recorder._guard_google(request_data, path)


def test_provider_recorder_restores_google_resource_ids_after_restart(tmp_path):
    (tmp_path / "created-resource-ids.json").write_text(
        json.dumps(["customers/9055507554/campaigns/24357433403"]),
        encoding="utf-8",
    )

    recorder = ProviderRecorder(tmp_path)

    assert "24357433403" in recorder.created


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


def test_google_app_ad_requires_enabled_status_and_both_verified_paused_parents(tmp_path):
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

    with pytest.raises(PermissionError, match="verified PAUSED"):
        recorder._guard_google(
            data,
            "/v24/customers/123/googleAds:mutate",
        )

    recorder._capture_google_paused_resources(
        {"results": [{
            "adGroup": {
                "id": "77", "status": "PAUSED", "campaign": "customers/123/campaigns/99",
            },
            "campaign": {"id": "99", "status": "ENABLED"},
        }]}
    )
    assert recorder.paused_ad_groups == {"77"}
    with pytest.raises(PermissionError, match="verified PAUSED"):
        recorder._guard_google(data, "/v24/customers/123/googleAds:mutate")
    recorder._capture_google_paused_resources(
        {"results": [{"campaign": {"id": "99", "status": "PAUSED"}}]}
    )
    recorder._guard_google(
        data,
        "/v24/customers/123/googleAds:mutate",
    )
    recorder._capture_google_paused_resources(
        {"results": [{"campaign": {"id": "99", "status": "ENABLED"}}]}
    )
    with pytest.raises(PermissionError, match="verified PAUSED"):
        recorder._guard_google(data, "/v24/customers/123/googleAds:mutate")
    recorder._capture_google_paused_resources(
        {"results": [{"campaign": {"id": "99", "status": "PAUSED"}}]}
    )
    data["mutateOperations"][0]["adGroupAdOperation"]["create"]["status"] = "PAUSED"
    with pytest.raises(PermissionError, match="explicitly be ENABLED"):
        recorder._guard_google(data, "/v24/customers/123/googleAds:mutate")


def test_enabled_exception_does_not_apply_to_other_google_ad_types(tmp_path):
    recorder = ProviderRecorder(tmp_path)
    data = {"operations": [{"create": {
        "adGroup": "customers/123/adGroups/77",
        "status": "ENABLED",
        "ad": {"responsiveSearchAd": {"headlines": [{"text": "Search"}]}},
    }}]}
    with pytest.raises(PermissionError, match="PAUSED"):
        recorder._guard_google(data, "/v24/customers/123/adGroupAds:mutate")


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
