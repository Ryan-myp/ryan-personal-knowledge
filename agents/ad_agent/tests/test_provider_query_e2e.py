from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.ad_agent.scripts.provider_query_e2e import (
    QUERY_TOOLS,
    ReadOnlyQueryRun,
    _build_safe_query_input,
    _ensure_query_coverage,
    _ids_for_resource,
    _run_google,
    _run_meta,
    _run_tiktok,
    classify_query_failure,
    count_result_rows,
    main,
    redact_error,
    select_test_account,
    _collect_secret_values,
    seed_created_resources_from_evidence,
)
from agents.ad_agent.core.interfaces import ToolEffect, ToolSchema


def test_select_test_account_requires_one_allowlisted_test_account():
    account = select_test_account(
        ["acct-1111", "acct-2222"],
        {"test": [{"account_id": "acct-2222", "label": "sandbox"}]},
    )

    assert account == "acct-2222"


@pytest.mark.parametrize(
    ("allowlist", "test_accounts"),
    [
        (["acct-1111"], {"test": ["acct-2222"]}),
        (["acct-1111", "acct-2222"], {"test": ["acct-1111", "acct-2222"]}),
    ],
)
def test_select_test_account_fails_closed_without_exact_match(
    allowlist, test_accounts
):
    with pytest.raises(ValueError):
        select_test_account(allowlist, test_accounts)


@pytest.mark.parametrize(
    ("payload", "result_key", "expected"),
    [
        ({"campaigns": [{"id": "1"}, {"id": "2"}]}, "campaigns", 2),
        ({"account": {"id": "1"}}, "account", 1),
        ({"report": {"data": [{"id": "1"}]}}, "report", 1),
        ({"report": {"data": []}}, "report", 0),
        ({}, "campaigns", 0),
        ({"assets": [{"asset_id": "1"}], "data_status": "live"}, "", 1),
        ({"report": {"data": []}, "data_status": "live"}, "", 0),
    ],
)
def test_count_result_rows_handles_lists_objects_and_empty_results(
    payload, result_key, expected
):
    assert count_result_rows(payload, result_key) == expected


def test_resource_id_extraction_uses_result_rows_and_resource_specific_fields():
    payload = {
        "campaigns": [
            {"campaign_id": "campaign-1", "name": "one"},
            {"id": "campaign-2", "name": "two"},
        ],
        "data_status": "live",
    }

    assert _ids_for_resource(payload, "campaigns", "campaign") == [
        "campaign-1",
        "campaign-2",
    ]


def test_resource_id_extraction_handles_single_objects_with_or_without_result_key():
    assert _ids_for_resource(
        {
            "asset_group": {"asset_group_id": "asset-group-1"},
            "data_status": "live",
        },
        "asset_group",
        "asset_group",
    ) == ["asset-group-1"]
    assert _ids_for_resource(
        {
            "ad": {"ad_id": "ad-1"},
            "data_status": "live",
        },
        "",
        "ad",
    ) == ["ad-1"]


def test_tiktok_ad_backed_creative_rows_use_ad_id_as_logical_resource_id():
    payload = {
        "creatives": [{
            "ad_id": "ad-1",
            "adgroup_id": "group-1",
        }],
        "data_status": "live",
    }

    assert count_result_rows(payload, "creatives", "creative") == 1
    assert _ids_for_resource(payload, "creatives", "creative") == ["ad-1"]


def test_read_query_seeding_uses_created_resources_from_exact_evidence_branch():
    definitions = {
        "google_get_ad_group": SimpleNamespace(
            resource_type="ad_group",
            parent_resource_type="campaign",
        ),
        "google_get_ad": SimpleNamespace(
            resource_type="ad",
            parent_resource_type="ad_group",
        ),
    }

    class FakeRuntime:
        @staticmethod
        def _get_registered_tool(name):
            return (
                definitions.get(
                    name,
                    SimpleNamespace(
                        resource_type="",
                        parent_resource_type=None,
                    ),
                ),
                object(),
            )

    suite = SimpleNamespace(
        accounts={"google-ads": "acct-1234"},
        runtime=FakeRuntime(),
        resource_pools={"google-ads": {}},
        resource_relationships={"google-ads": {}},
    )
    evidence = {
        "schema_version": "1.0",
        "generated_at": "2026-09-30",
        "scope": "provider_e2e",
        "safety": {
            "test_accounts_only": True,
            "new_resources_paused": True,
            "deleted": False,
            "credentials_included": False,
            "raw_provider_responses_included": False,
        },
        "runs": [
            {
                "provider": "google-ads",
                "test_account": "acct-1234",
                "campaign_type": "PMax",
                "status": "provider_limited",
                "resources": {
                    "APP": {
                        "campaign": {
                            "id": "campaign-paused",
                            "status": "PAUSED",
                            "create": "passed",
                        },
                        "ad_group": {
                            "id": "ad-group-paused",
                            "status": "PAUSED",
                            "create": "passed",
                        },
                        "ad": {
                            "id": "ad-enabled",
                            "status": "ENABLED",
                            "create": "passed",
                        },
                    },
                    "SHOPPING": {
                        "ad": {
                            "id": "unrelated-ad",
                            "status": "ENABLED",
                            "create": "passed",
                        },
                    },
                },
            },
            {
                "provider": "google-ads",
                "test_account": "other-account",
                "campaign_type": "PMax",
                "status": "provider_limited",
                "resources": {
                    "campaign": {
                        "id": "other-campaign",
                        "status": "PAUSED",
                        "create": "passed",
                    },
                },
            },
        ],
    }

    seeded_count = seed_created_resources_from_evidence(suite, evidence)

    assert seeded_count == 4
    assert suite.resource_pools["google-ads"] == {
        "campaign": ["campaign-paused"],
        "ad_group": ["ad-group-paused"],
        "ad": ["ad-enabled", "unrelated-ad"],
    }
    assert suite.resource_relationships["google-ads"]["ad_group"] == [{
        "resource_id": "ad-group-paused",
        "parent_resource_type": "campaign",
        "parent_resource_id": "campaign-paused",
    }]
    assert suite.resource_relationships["google-ads"]["ad"] == [{
        "resource_id": "ad-enabled",
        "parent_resource_type": "ad_group",
        "parent_resource_id": "ad-group-paused",
    }]

    assert seed_created_resources_from_evidence(suite, evidence) == 0


def test_read_query_seeding_requires_runtime_parent_contract():
    suite = SimpleNamespace(
        accounts={"google-ads": "acct-1234"},
        runtime=SimpleNamespace(
            _get_registered_tool=lambda _name: (
                SimpleNamespace(
                    resource_type="",
                    parent_resource_type=None,
                ),
                object(),
            )
        ),
        resource_pools={"google-ads": {}},
        resource_relationships={"google-ads": {}},
    )
    evidence = {
        "schema_version": "1.0",
        "generated_at": "2026-09-30",
        "scope": "provider_e2e",
        "safety": {
            "test_accounts_only": True,
            "new_resources_paused": True,
            "deleted": False,
            "credentials_included": False,
            "raw_provider_responses_included": False,
        },
        "runs": [{
            "provider": "google-ads",
            "test_account": "acct-1234",
            "campaign_type": "APP",
            "status": "provider_limited",
            "resources": {
                "campaign": {
                    "id": "campaign-1",
                    "status": "PAUSED",
                    "create": "passed",
                },
                "ad_group": {
                    "id": "ad-group-1",
                    "status": "PAUSED",
                    "create": "passed",
                },
            },
        }],
    }

    seed_created_resources_from_evidence(suite, evidence)

    assert suite.resource_pools["google-ads"] == {
        "campaign": ["campaign-1"],
        "ad_group": ["ad-group-1"],
    }
    assert suite.resource_relationships["google-ads"] == {}


def test_resource_seeding_rejects_invalid_safety_evidence():
    suite = SimpleNamespace(
        accounts={"google-ads": "acct-1234"},
        resource_pools={"google-ads": {}},
    )
    evidence = {
        "schema_version": "1.0",
        "generated_at": "2026-09-30",
        "scope": "provider_e2e",
        "safety": {
            "test_accounts_only": True,
            "new_resources_paused": False,
            "deleted": False,
            "credentials_included": False,
            "raw_provider_responses_included": False,
        },
        "runs": [{
            "provider": "google-ads",
            "test_account": "acct-1234",
            "campaign_type": "PMax",
            "status": "provider_limited",
            "resources": {
                "campaign": {
                    "id": "campaign-1",
                    "status": "PAUSED",
                    "create": "passed",
                },
            },
        }],
    }

    with pytest.raises(ValueError, match="invalid provider evidence"):
        seed_created_resources_from_evidence(suite, evidence)

    assert suite.resource_pools["google-ads"] == {}


def test_query_relationship_index_stores_only_resource_ids():
    suite = ReadOnlyQueryRun(
        SimpleNamespace(),
        {"tiktok": "test-advertiser"},
        {"ads.read"},
        [],
    )
    definition = SimpleNamespace(
        name="tiktok_list_ads",
        resource_type="ad",
        action="list",
        parent_resource_type="ad_group",
    )
    payload = {
        "ads": [{
            "ad_id": "ad-123",
            "adgroup_id": "group-456",
            "ad_name": "Private test creative",
            "ad_text": "Do not retain this response field",
        }],
        "data_status": "live",
    }

    suite._record_success("tiktok", definition, payload, "ads")

    assert suite.resource_relationships["tiktok"]["ad"] == [{
        "resource_id": "ad-123",
        "parent_resource_type": "ad_group",
        "parent_resource_id": "group-456",
    }]
    assert suite.resource_pools["tiktok"]["ad"] == ["ad-123"]


def test_query_relationship_uses_exact_parent_filter_when_response_omits_it():
    suite = ReadOnlyQueryRun(
        SimpleNamespace(),
        {"google-ads": "test-account"},
        {"ads.read"},
        [],
    )
    definition = SimpleNamespace(
        name="google_list_asset_groups",
        resource_type="asset_group",
        action="list",
        parent_resource_type="campaign",
        parent_resource_id_field="campaign_id",
    )

    suite._record_success(
        "google-ads",
        definition,
        {
            "asset_groups": [{"asset_group_id": "asset-group-1"}],
            "data_status": "live",
        },
        "asset_groups",
        {"campaign_id": "campaign-1"},
    )

    assert suite.resource_relationships["google-ads"]["asset_group"] == [{
        "resource_id": "asset-group-1",
        "parent_resource_type": "campaign",
        "parent_resource_id": "campaign-1",
    }]


@pytest.mark.parametrize(
    "input_data",
    [
        {"campaign_id": ["campaign-1", "campaign-2"]},
        {"campaign_id": ""},
    ],
)
def test_query_relationship_does_not_infer_from_ambiguous_parent_filter(input_data):
    suite = ReadOnlyQueryRun(
        SimpleNamespace(),
        {"google-ads": "test-account"},
        {"ads.read"},
        [],
    )
    definition = SimpleNamespace(
        name="google_list_asset_groups",
        resource_type="asset_group",
        action="list",
        parent_resource_type="campaign",
        parent_resource_id_field="campaign_id",
    )

    suite._record_success(
        "google-ads",
        definition,
        {
            "asset_groups": [{"asset_group_id": "asset-group-1"}],
            "data_status": "live",
        },
        "asset_groups",
        input_data,
    )

    assert suite.resource_relationships["google-ads"]["asset_group"] == []


def test_query_relationship_rejects_response_parent_conflicting_with_filter():
    suite = ReadOnlyQueryRun(
        SimpleNamespace(),
        {"google-ads": "test-account"},
        {"ads.read"},
        [],
    )
    definition = SimpleNamespace(
        name="google_list_asset_groups",
        resource_type="asset_group",
        action="list",
        parent_resource_type="campaign",
        parent_resource_id_field="campaign_id",
    )

    suite._record_success(
        "google-ads",
        definition,
        {
            "asset_groups": [{
                "asset_group_id": "asset-group-1",
                "campaign_id": "different-campaign",
            }],
            "data_status": "live",
        },
        "asset_groups",
        {"campaign_id": "filtered-campaign"},
    )

    assert suite.resource_relationships["google-ads"]["asset_group"] == []


def test_query_execution_uses_resource_type_to_count_and_index_detail_objects():
    class FakeRuntime:
        whitelist_validator = SimpleNamespace(
            validate_account=lambda *_args: (True, "")
        )
        tool_executor = SimpleNamespace(
            execute=lambda *_args: SimpleNamespace(
                success=True,
                data={
                    "ad": {"ad_id": "ad-1"},
                    "data_status": "live",
                },
                simulated=False,
                error=None,
                error_detail=None,
            )
        )

        @staticmethod
        def _get_registered_tool(_name):
            return (
                SimpleNamespace(
                    name="tiktok_get_ad",
                    effect_class=ToolEffect.READ,
                    is_write_tool=False,
                    required_permissions=[],
                    resource_type="ad",
                    action="get",
                    parent_resource_type="ad_group",
                    resource_id_field="ad_id",
                    parent_resource_id_field="adgroup_id",
                    input_schema=ToolSchema(
                        required=["ad_id", "adgroup_id"],
                        properties={
                            "ad_id": {"type": "string"},
                            "adgroup_id": {"type": "string"},
                        },
                    ),
                ),
                SimpleNamespace(client=object()),
            )

    suite = ReadOnlyQueryRun(
        FakeRuntime(),
        {"tiktok": "test-advertiser"},
        {"ads.read"},
        [],
    )
    result = suite.execute(
        "tiktok",
        "tiktok_get_ad",
        {"ad_id": "ad-1", "adgroup_id": "group-1"},
        "",
    )

    assert result["ok"] is True
    assert suite.queries["tiktok"][-1]["row_count"] == 1
    assert suite.resource_relationships["tiktok"]["ad"] == [{
        "resource_id": "ad-1",
        "parent_resource_type": "ad_group",
        "parent_resource_id": "group-1",
    }]


def test_safe_query_input_scopes_tiktok_account_list_to_current_advertiser():
    suite = SimpleNamespace(
        accounts={"tiktok": "test-advertiser-1"},
        resource_pools={"tiktok": {}},
    )
    definition = SimpleNamespace(
        input_schema=SimpleNamespace(to_dict=lambda: {
            "required": ["advertiser_ids"],
            "properties": {
                "advertiser_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 1,
                },
            },
        }),
    )

    values, reason = _build_safe_query_input(
        suite,
        "tiktok",
        "tiktok_list_accounts",
        definition,
    )

    assert reason is None
    assert values == {"advertiser_ids": ["test-advertiser-1"]}


def test_safe_query_input_uses_only_test_account_and_returned_parent_ids():
    suite = SimpleNamespace(
        accounts={"meta": "test-account"},
        resource_pools={"meta": {"campaign": ["returned-campaign"]}},
    )
    definition = SimpleNamespace(input_schema=SimpleNamespace(to_dict=lambda: {
        "required": ["account_id", "campaign_id"],
        "properties": {
            "account_id": {"type": "string"},
            "campaign_id": {"type": "string"},
            "limit": {"type": "integer", "maximum": 100},
        },
    }))

    values, reason = _build_safe_query_input(
        suite,
        "meta",
        "meta_list_ad_sets",
        definition,
    )

    assert reason is None
    assert values == {
        "account_id": "test-account",
        "campaign_id": "returned-campaign",
        "limit": 10,
    }


def test_safe_query_input_never_pairs_unrelated_resource_and_parent_ids():
    suite = SimpleNamespace(
        accounts={"tiktok": "test-advertiser"},
        resource_pools={
            "tiktok": {
                "ad_group": ["older-group"],
                "ad": ["ad-from-another-group"],
            },
        },
        resource_relationships={
            "tiktok": {
                "ad": [{
                    "resource_id": "returned-ad",
                    "parent_resource_type": "ad_group",
                    "parent_resource_id": "returned-group",
                }],
            },
        },
    )
    definition = SimpleNamespace(
        resource_type="ad",
        parent_resource_type="ad_group",
        resource_id_field="ad_id",
        parent_resource_id_field="adgroup_id",
        input_schema=SimpleNamespace(to_dict=lambda: {
            "required": ["account_id", "adgroup_id", "ad_id"],
            "properties": {
                "account_id": {"type": "string"},
                "adgroup_id": {"type": "string"},
                "ad_id": {"type": "string"},
            },
        }),
    )

    values, reason = _build_safe_query_input(
        suite,
        "tiktok",
        "tiktok_get_ad",
        definition,
    )

    assert reason is None
    assert values == {
        "account_id": "test-advertiser",
        "adgroup_id": "returned-group",
        "ad_id": "returned-ad",
    }


def test_safe_query_input_skips_paired_lookup_without_same_row_relationship():
    suite = SimpleNamespace(
        accounts={"tiktok": "test-advertiser"},
        resource_pools={
            "tiktok": {
                "ad_group": ["older-group"],
                "ad": ["unrelated-ad"],
            },
        },
        resource_relationships={"tiktok": {"ad": []}},
    )
    definition = SimpleNamespace(
        resource_type="ad",
        parent_resource_type="ad_group",
        resource_id_field="ad_id",
        parent_resource_id_field="adgroup_id",
        input_schema=SimpleNamespace(to_dict=lambda: {
            "required": ["account_id", "adgroup_id", "ad_id"],
            "properties": {
                "account_id": {"type": "string"},
                "adgroup_id": {"type": "string"},
                "ad_id": {"type": "string"},
            },
        }),
    )

    values, reason = _build_safe_query_input(
        suite,
        "tiktok",
        "tiktok_get_ad",
        definition,
    )

    assert values is None
    assert reason == "missing_parent_resource"


def test_tiktok_creative_detail_query_uses_account_scoped_resource_id():
    from agents.ad_agent.tools.providers.source_factory import create_tool_source

    source = create_tool_source("tiktok")
    definition = next(
        definition
        for definition, _handler in source.register_tools()
        if definition.name == "tiktok_get_creative"
    )
    suite = SimpleNamespace(
        accounts={"tiktok": "test-advertiser"},
        resource_pools={"tiktok": {"creative": ["creative-from-list"]}},
        resource_relationships={"tiktok": {"creative": []}},
    )

    values, reason = _build_safe_query_input(
        suite,
        "tiktok",
        "tiktok_get_creative",
        definition,
    )

    assert reason is None
    assert values == {
        "account_id": "test-advertiser",
        "creative_id": "creative-from-list",
    }


def test_tiktok_creative_detail_can_use_the_ad_id_from_the_ad_list():
    from agents.ad_agent.tools.providers.source_factory import create_tool_source

    source = create_tool_source("tiktok")
    definition = next(
        definition
        for definition, _handler in source.register_tools()
        if definition.name == "tiktok_get_creative"
    )
    suite = SimpleNamespace(
        accounts={"tiktok": "test-advertiser"},
        resource_pools={"tiktok": {"ad": ["ad-from-list"]}},
        resource_relationships={"tiktok": {"creative": []}},
    )

    values, reason = _build_safe_query_input(
        suite,
        "tiktok",
        "tiktok_get_creative",
        definition,
    )

    assert reason is None
    assert values == {
        "account_id": "test-advertiser",
        "creative_id": "ad-from-list",
    }


def test_safe_query_input_skips_resource_detail_without_a_returned_id():
    suite = SimpleNamespace(
        accounts={"meta": "test-account"},
        resource_pools={"meta": {"campaign": []}},
    )
    definition = SimpleNamespace(
        resource_id_field="campaign_id",
        input_schema=SimpleNamespace(to_dict=lambda: {
            "required": [],
            "properties": {
                "campaign_id": {"type": "string"},
                "campaign_name": {"type": "string"},
            },
        }),
    )

    values, reason = _build_safe_query_input(
        suite,
        "meta",
        "meta_get_campaign",
        definition,
    )

    assert values is None
    assert reason == "missing_parent_resource"


def test_coverage_finalizer_records_each_fixed_tool_once_without_api_calls():
    class FakeRuntime:
        @staticmethod
        def _get_registered_tool(name):
            return (
                SimpleNamespace(
                    name=name,
                    resource_type="resource",
                    action="read",
                ),
                object(),
            )

    suite = ReadOnlyQueryRun(
        FakeRuntime(),
        {"google-ads": "test", "meta": "test", "tiktok": "test"},
        {"ads.read"},
        [],
    )
    _ensure_query_coverage(suite)

    for provider, tools in QUERY_TOOLS.items():
        recorded = [query["tool"] for query in suite.queries[provider]]
        assert len(recorded) == len(tools)
        assert set(recorded) == set(tools)
        assert all(query["outcome"] == "skipped" for query in suite.queries[provider])


@pytest.mark.parametrize(
    ("message", "status_code", "expected"),
    [
        ("invalid access token", 401, "credential_error"),
        (
            "This method must be called with a Page Access Token",
            400,
            "credential_error",
        ),
        ("permission denied", 403, "provider_permission"),
        ("resource not found", 404, "provider_not_found"),
        ("TikTok error 50000: plugin not found", None, "provider_error"),
        ("too many requests", 429, "provider_rate_limit"),
        ("request timed out", None, "provider_timeout"),
        ("invalid field value", 400, "provider_validation"),
        ("unexpected response", 502, "provider_unavailable"),
    ],
)
def test_classify_query_failure_uses_stable_categories(
    message, status_code, expected
):
    assert classify_query_failure(message, status_code) == expected


def test_redact_error_removes_credentials_account_ids_and_resource_ids():
    error = redact_error(
        "request failed for account 1234567890 using secret-value and campaign 9876543210",
        secret_values=["secret-value"],
        resource_ids=["1234567890"],
    )

    assert "secret-value" not in error
    assert "1234567890" not in error
    assert "9876543210" not in error
    assert "<redacted>" in error


def test_secret_collection_finds_page_tokens_nested_by_page_id():
    secrets = _collect_secret_values({
        "meta": {
            "access_token": "user-token-secret",
            "page_access_tokens": {
                "12345": "page-token-secret",
            },
        },
    })

    assert "user-token-secret" in secrets
    assert "page-token-secret" in secrets


def test_query_suite_contains_only_fixed_provider_read_tools():
    all_tools = [tool for provider_tools in QUERY_TOOLS.values() for tool in provider_tools]
    assert {
        provider: len(tools)
        for provider, tools in QUERY_TOOLS.items()
    } == {"google-ads": 35, "meta": 35, "tiktok": 43}
    assert len(all_tools) == 113
    assert len(set(all_tools)) == len(all_tools)
    assert all(not any(word in tool for word in ("create", "update", "delete")) for tool in all_tools)


def test_runner_requires_explicit_confirmation_before_any_io(capsys):
    assert main([]) == 2
    assert "confirm-read-only-provider-calls" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("provider", "run_suite", "expected_tools", "parent_inputs"),
    [
        (
            "google-ads",
            _run_google,
            [
                "google_list_campaigns",
                "google_list_ad_groups",
                "google_list_ads",
                "google_get_campaign_report",
            ],
            [
                ("google_list_ad_groups", "campaign_id", "returned-campaign"),
            ],
        ),
        (
            "meta",
            _run_meta,
            [
                "meta_get_account",
                "meta_list_campaigns",
                "meta_list_creatives",
                "meta_list_ad_sets",
                "meta_list_ads",
                "meta_get_campaign_report",
            ],
            [
                ("meta_list_ad_sets", "campaign_id", "returned-campaign"),
                ("meta_list_ads", "adset_id", "returned-child"),
            ],
        ),
        (
            "tiktok",
            _run_tiktok,
            [
                "tiktok_get_account",
                "tiktok_list_campaigns",
                "tiktok_list_adgroups",
                "tiktok_list_ads",
                "tiktok_get_campaign_report",
            ],
            [
                ("tiktok_list_adgroups", "campaign_id", "returned-campaign"),
                ("tiktok_list_ads", "adgroup_id", "returned-child"),
            ],
        ),
    ],
)
def test_query_suite_uses_returned_parent_ids_without_external_calls(
    provider, run_suite, expected_tools, parent_inputs
):
    class StubSuite:
        accounts = {provider: "test-account"}

        def __init__(self):
            self.calls = []

        def execute(self, called_provider, tool, input_data, result_key):
            self.calls.append((tool, input_data))
            if result_key in {"campaigns"}:
                result = [{"id": "returned-campaign"}]
            elif result_key in {"ad_groups", "ad_sets", "adgroups"}:
                result = [{"id": "returned-child"}]
            elif result_key == "account":
                result = {"id": "account"}
            else:
                result = []
            return {"ok": True, "data": {result_key: result}}

        def record_skip(self, called_provider, tool):
            self.calls.append((tool, {}))

    suite = StubSuite()
    run_suite(suite)

    called = {tool: inputs for tool, inputs in suite.calls}
    assert all(tool in called for tool in expected_tools)
    for tool, field, expected in parent_inputs:
        assert called[tool][field] == expected
    if provider == "google-ads":
        assert called["google_list_ads"] == {"limit": 10}
