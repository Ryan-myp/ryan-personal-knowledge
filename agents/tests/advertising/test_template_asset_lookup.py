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
