import pytest

from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient
from agents.tools.advertising.providers.google import create_google_tool_source


def test_template_asset_resource_name_is_accepted_by_the_lookup_contract():
    definition = next(
        item.definition for item in create_google_tool_source().list_bindings()
        if item.definition.name == "google_list_assets"
    )
    assert validate_tool_input(definition.input_schema, {
        "asset_id": "customers/9055507554/assets/194802085984",
    }) == []


def test_asset_lookup_resolves_the_resource_name_in_the_selected_customer():
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    seen = []
    client._search_all = lambda query, page_size=100: (seen.append(query) or [])
    assert client.list_assets(
        asset_id="customers/9055507554/assets/194802085984",
    ) == []
    assert "WHERE asset.id = 194802085984" in seen[0]


def test_asset_lookup_rejects_a_resource_name_from_another_customer():
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    client._search_all = lambda *_args, **_kwargs: pytest.fail("Provider must not be called")
    with pytest.raises(ValueError, match="customer"):
        client.list_assets(asset_id="customers/9999999999/assets/194802085984")


def test_asset_group_parent_picker_passes_exact_campaign_id_to_read_tool():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition

    calls = []

    class LookupClient:
        def list_campaigns(self, campaign_id=None, page_size=100):
            calls.append((campaign_id, page_size))
            return [{
                "id": str(campaign_id),
                "campaign_name": "QA PMax",
                "status": "PAUSED",
            }]

    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.whitelist_validator.allowed_accounts = {
        "google-ads": ["9055507554"],
    }
    runtime.register_tool_source(create_google_tool_source(LookupClient()))

    selection = runtime.resolve_parameter_options(
        "google-ads",
        "campaign_id",
        "google_create_asset_group",
        "9055507554",
        session_id="pmax-parent-selection",
        user_id="test-user",
        query="24357433403",
    )

    assert calls == [("24357433403", 100)]
    assert [item["value"] for item in selection["options"]] == ["24357433403"]
    assert selection["options"][0]["selection_token"]


def test_meta_template_prefill_resolves_a_valid_app_beyond_the_picker_limit():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    selected_app = "meta-app-27"
    calls = []

    class LookupClient:
        def list_apps(self, account_id, limit=25):
            calls.append((account_id, limit))
            return [
                {"id": f"meta-app-{index}", "name": f"Meta App {index}"}
                for index in range(1, 53)
            ]

    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.whitelist_validator.allowed_accounts = {"meta": ["2806375919473667"]}
    runtime.register_tool_source(create_meta_tool_source(LookupClient()))
    try:
        selection = runtime.resolve_parameter_options(
            "meta",
            "promoted_object.application_id",
            "meta_create_adset",
            account_id="2806375919473667",
            session_id="meta-app-template-prefill",
            user_id="test-user",
            account_scope={"meta": {"2806375919473667"}},
            lookup_context={
                "promoted_object": {"application_id": selected_app},
                "application_id": selected_app,
            },
        )
    finally:
        runtime.close(wait=True)

    options = selection["options"]
    assert calls == [("2806375919473667", 1000)]
    assert len(options) == 20
    assert [item["value"] for item in options].count(selected_app) == 1
    assert options[[item["value"] for item in options].index(selected_app)][
        "selection_token"
    ]


def test_meta_template_lookup_never_signs_a_prefill_missing_from_provider_results():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    class LookupClient:
        def list_apps(self, _account_id, limit=25):
            return [
                {"id": f"meta-app-{index}", "name": f"Meta App {index}"}
                for index in range(1, 53)
            ]

    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.whitelist_validator.allowed_accounts = {"meta": ["2806375919473667"]}
    runtime.register_tool_source(create_meta_tool_source(LookupClient()))
    try:
        selection = runtime.resolve_parameter_options(
            "meta",
            "promoted_object.application_id",
            "meta_create_adset",
            account_id="2806375919473667",
            session_id="meta-app-template-unverified-prefill",
            user_id="test-user",
            account_scope={"meta": {"2806375919473667"}},
            lookup_context={
                "promoted_object": {"application_id": "not-a-provider-app"},
                "application_id": "not-a-provider-app",
            },
        )
    finally:
        runtime.close(wait=True)

    assert len(selection["options"]) == 20
    assert "not-a-provider-app" not in {
        item["value"] for item in selection["options"]
    }
    assert all(item.get("selection_token") for item in selection["options"])


def test_meta_template_parent_campaign_prefill_resolves_beyond_the_picker_limit():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.tools.advertising.providers.meta import create_meta_tool_source

    selected_campaign = "meta-campaign-27"
    calls = []

    class LookupClient:
        def list_campaigns(self, account_id, fields=None, limit=25):
            calls.append((account_id, limit))
            return [
                {"id": f"meta-campaign-{index}", "name": f"Meta Campaign {index}"}
                for index in range(1, 53)
            ]

    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.whitelist_validator.allowed_accounts = {"meta": ["2806375919473667"]}
    runtime.register_tool_source(create_meta_tool_source(LookupClient()))
    try:
        selection = runtime.resolve_parameter_options(
            "meta",
            "campaign_id",
            "meta_create_adset",
            account_id="2806375919473667",
            session_id="meta-parent-template-prefill",
            user_id="test-user",
            account_scope={"meta": {"2806375919473667"}},
            lookup_context={"campaign_id": selected_campaign},
        )
    finally:
        runtime.close(wait=True)

    options = selection["options"]
    assert calls == [("2806375919473667", 1000)]
    assert len(options) == 20
    assert [item["value"] for item in options].count(selected_campaign) == 1
    assert options[[item["value"] for item in options].index(selected_campaign)][
        "selection_token"
    ]


@pytest.mark.parametrize("identifier", ["124", "customers/9055507554/conversionActions/124"])
def test_conversion_lookup_filters_on_the_provider_before_the_result_limit(identifier):
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    seen = []
    client._search_all = lambda query, page_size=100: (seen.append(query) or [])
    assert client.list_conversion_actions(conversion_action_id=identifier) == []
    assert "WHERE conversion_action.id = 124" in seen[0]


def test_conversion_lookup_rejects_a_resource_name_from_another_customer():
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    client._search_all = lambda *_a, **_kw: pytest.fail("Provider must not be called")
    with pytest.raises(ValueError, match="customer"):
        client.list_conversion_actions(
            conversion_action_id="customers/9999999999/conversionActions/124",
        )


def test_template_conversion_lookup_finds_values_beyond_the_first_twenty_options():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition

    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    def list_actions(page_size=100, conversion_action_id=None):
        assert conversion_action_id == "customers/9055507554/conversionActions/124"
        return [{
            "id": "124",
            "resource_name": conversion_action_id,
            "name": "Action 124",
        }]

    client.list_conversion_actions = list_actions
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.whitelist_validator.allowed_accounts = {"google-ads": ["9055507554"]}
    runtime.register_tool_source(create_google_tool_source(client))
    result = runtime.resolve_parameter_options(
        "google-ads", "selective_optimization.conversion_actions", "google_create_campaign",
        account_id="9055507554", session_id="template-lookup", user_id="test-user",
        account_scope={"google-ads": {"9055507554"}},
        query="customers/9055507554/conversionActions/124",
    )
    assert [option["value"] for option in result["options"]] == [
        "customers/9055507554/conversionActions/124",
    ]
    assert result["options"][0]["selection_token"]


def test_template_conversion_lookup_without_search_is_still_bounded():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition

    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    client.list_conversion_actions = lambda page_size=100, conversion_action_id=None: [
        {
            "id": str(index),
            "resource_name": f"customers/9055507554/conversionActions/{index}",
            "name": f"Action {index}",
        }
        for index in range(30)
    ]
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    runtime.whitelist_validator.allowed_accounts = {"google-ads": ["9055507554"]}
    runtime.register_tool_source(create_google_tool_source(client))
    result = runtime.resolve_parameter_options(
        "google-ads", "selective_optimization.conversion_actions", "google_create_campaign",
        account_id="9055507554", session_id="template-lookup", user_id="test-user",
        account_scope={"google-ads": {"9055507554"}},
    )
    assert len(result["options"]) == 20


@pytest.mark.parametrize("parent_status", ["PAUSED", "ENABLED"])
def test_live_listing_filter_verifies_the_parent_is_paused(parent_status):
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    events = []
    client.get_asset_group = lambda identifier: (
        events.append(("read", identifier)) or {"id": identifier, "status": parent_status}
    )
    client._mutate = lambda *_args, **_kwargs: (
        events.append(("write", None)) or {
            "results": [{"resourceName": "customers/9055507554/assetGroupListingGroupFilters/100~200"}],
        }
    )
    if parent_status == "ENABLED":
        with pytest.raises(ValueError, match="PAUSED"):
            client.create_asset_group_listing_group_filter("100", filter_type="UNIT_INCLUDED", live=True)
        assert events == [("read", "100")]
    else:
        client.create_asset_group_listing_group_filter("100", filter_type="UNIT_INCLUDED", live=True)
        assert events == [("read", "100"), ("write", None)]
