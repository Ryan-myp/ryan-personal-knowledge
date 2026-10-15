"""Browser confirmation transport must preserve the server-approved request."""

import shutil
import subprocess
from pathlib import Path

import pytest

from agents.agent_harness.core.tool_registry import validate_tool_input
from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient
from agents.tools.advertising.providers.google import create_google_tool_source
from agents.applications.advertising.creation.templates import load_builtin_template_definitions


def test_confirmation_frontend_regressions():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser confirmation regressions")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).parent / "static/test_confirmation_flow.js")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("channel", ["SHOPPING", "SEARCH", "MULTI_CHANNEL"])
def test_non_pmax_brand_guidelines_are_rejected_before_any_budget_write(channel):
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    client._mutate = lambda *_a, **_kw: pytest.fail("Invalid campaign must not create a budget")
    with pytest.raises(ValueError, match="PERFORMANCE_MAX"):
        client.create_campaign(
            "Paused QA", channel, "MAXIMIZE_CLICKS", 20,
            brand_guidelines_enabled=False, status="PAUSED", live=True,
        )


def test_shopping_tool_schema_rejects_a_hidden_pmax_only_parameter():
    definition = next(
        item.definition for item in create_google_tool_source().list_bindings()
        if item.definition.name == "google_create_campaign"
    )
    errors = validate_tool_input(definition.input_schema, {
        "campaign_name": "Paused QA", "advertising_channel_type": "SHOPPING",
        "bidding_strategy": "MAXIMIZE_CLICKS", "daily_budget": 20,
        "brand_guidelines_enabled": False,
    })
    assert any("brand_guidelines_enabled" in error for error in errors)


def test_shopping_template_keeps_parent_settings_and_leaf_fields_consistent():
    template = next(row for row in load_builtin_template_definitions() if row["key"] == "google.test.shopping")
    values = template["values"]
    assert values["campaign.shopping_setting"] == {
        "merchant_id": values["campaign.shopping_setting.merchant_id"],
        "campaign_priority": values["campaign.shopping_setting.campaign_priority"],
        "enable_local": values["campaign.shopping_setting.enable_local"],
    }


@pytest.mark.parametrize("group_status,campaign_status", [
    ("ENABLED", "PAUSED"), ("PAUSED", "ENABLED"), ("PAUSED", None),
])
def test_product_group_creation_rejects_unpaused_or_unverified_parents(group_status, campaign_status):
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    client.get_ad_group = lambda _identifier: {
        "id": "201", "status": group_status, "campaign_status": campaign_status,
    }
    client._mutate_operations = lambda *_a, **_kw: pytest.fail("Do not create under active parents")
    with pytest.raises(ValueError, match="PAUSED"):
        client.create_product_group("201", "all_products", cpc_bid_micros=500000, live=True)


def test_product_group_creation_accepts_only_verified_paused_parents():
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    calls = []
    client.get_ad_group = lambda identifier: (
        calls.append(("read", identifier)) or {
            "id": identifier, "status": "PAUSED", "campaign_status": "PAUSED",
        }
    )
    client._mutate_operations = lambda resource, operations: (
        calls.append(("write", resource)) or {
            "results": [{"resourceName": "customers/9055507554/adGroupCriteria/201~301"}],
        }
    )
    assert client.create_product_group(
        "201", "all_products", cpc_bid_micros=500000, live=True,
    ) == "301"
    assert calls == [("read", "201"), ("write", "adGroupCriteria")]


@pytest.mark.parametrize("micros,amount", [("500000", 0.5), (None, None)])
@pytest.mark.parametrize("resource", ["ad_group", "ad_groups", "product_group"])
def test_google_cpc_readbacks_provide_a_converted_amount_and_explicit_unit(resource, micros, amount):
    client = GoogleAdsAPIClient({"customer_id": "9055507554"})
    row = {
        "adGroup": {"id": "201", "cpcBidMicros": micros},
        "adGroupCriterion": {
            "criterionId": "301", "cpcBidMicros": micros,
            "listingGroup": {"type": "UNIT"},
        },
    }
    client._search = lambda _query: {"results": [row]}
    client._search_all = lambda _query, page_size=100: [row]
    if resource == "ad_group":
        result = client.get_ad_group("201")
    elif resource == "ad_groups":
        result = client.list_ad_groups("101")[0]
    else:
        result = client._normalize_product_group(row)
    assert result["cpc_bid_micros"] == micros
    assert result["cpc_bid_amount"] == amount
    assert result["cpc_bid_unit"] == "account_currency"
