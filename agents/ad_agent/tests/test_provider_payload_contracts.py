"""Ensure existing provider creation schemas reach their API adapters."""

import json

from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.core.interfaces import ParsedIntent, ToolContext
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.api_clients.dv360_client import DV360APIClient
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.capabilities.tiktok.campaigns import TikTokGetCampaignHandler


def test_generic_campaign_type_maps_to_google_wire_field():
    runtime = AgentRuntime()
    definition = next(
        definition
        for definition, _handler in create_google_capability().register_tools()
        if definition.name == "google_create_campaign"
    )
    intent = ParsedIntent(
        intent_type="create_campaign",
        raw_input="create DISPLAY campaign",
        platforms=["google-ads"],
        campaign_type="DISPLAY",
        platform_params={"google-ads": {}},
    )

    tool_input = runtime._build_tool_input(
        definition,
        intent,
        "google-ads",
        ToolContext(session_id="s1", user_id="u1", account_id="customer-1"),
    )

    assert tool_input["advertising_channel_type"] == "DISPLAY"


def test_existing_creation_contracts_keep_provider_specific_fixes():
    meta_definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    assert "creative" in meta_definitions["meta_create_ad"].input_schema.provider_any_of[0]
    assert not meta_definitions["meta_create_campaign"].input_schema.conditional_rules[1:]

    tiktok_definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert tiktok_definitions["tiktok_create_ad"].input_schema.provider_required == [
        "campaign_id"
    ]

    dv360_definitions = {
        definition.name: definition
        for definition, _handler in create_dv360_capability().register_tools()
    }
    assert dv360_definitions["dv360_get_line_item_report"].live_support is True


def test_meta_creation_options_are_forwarded_to_provider_payloads():
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"id": "resource-1"}
    )

    client.create_campaign("m1", {
        "name": "Sales",
        "objective": "OUTCOME_SALES",
        "special_ad_categories": "NONE",
        "buying_type": "AUCTION",
        "spend_cap": 25,
        "status": "PAUSED",
        "start_time": "2026-08-28T00:00:00+0000",
        "end_time": "2026-09-04T00:00:00+0000",
    })
    assert payloads[-1]["buying_type"] == "AUCTION"
    assert payloads[-1]["spend_cap"] == "2500"
    assert payloads[-1]["start_time"].startswith("2026-08-28")

    client.create_adset("m1", "c1", {
        "name": "Ad Set",
        "bid_strategy": "COST_CAP",
        "targeting": {"geo_locations": {"countries": ["US"]}},
        "promoted_object": {"pixel_id": "px1", "custom_event_type": "PURCHASE"},
        "start_time": "2026-08-28T00:00:00+0000",
        "end_time": "2026-09-04T00:00:00+0000",
    })
    assert payloads[-1]["bidding_strategy"] == "COST_CAP"
    assert payloads[-1]["targeting"]
    assert json.loads(payloads[-1]["promoted_object"]) == {
        "pixel_id": "px1", "custom_event_type": "PURCHASE"
    }
    assert payloads[-1]["start_time"].startswith("2026-08-28")

    client.create_ad("m1", "as1", {
        "name": "Ad",
        "creative": {"creative_id": "cr1"},
    })
    assert json.loads(payloads[-1]["creative"]) == {"creative_id": "cr1"}


def test_tiktok_ad_creation_preserves_existing_schema_fields():
    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"ad_id": "ad-1"}
    )

    client.create_ad("t1", "101", "202", {
        "name": "App Ad",
        "landing_page_url": "https://example.test",
        "conversion_id": 42,
        "ad_format": "SINGLE_VIDEO",
        "creatives": [{"video_id": "video-1"}],
        "media": [{"video_id": "video-1"}],
        "text": {"primary_text": "Install now"},
        "status": 0,
    })

    ad = payloads[-1]["ad"]
    assert ad["ad_format"] == "SINGLE_VIDEO"
    assert ad["creatives"] == [{"video_id": "video-1"}]
    assert ad["status"] == 0
    assert ad["landing_page_url"] == "https://example.test"
    client.create_adgroup("t1", "101", {
        "name": "App Group",
        "promotion_type": "APP_ANDROID",
        "billing_event": "OCPM",
        "conversion_id": 42,
        "budget_mode": "BUDGET_MODE_DAY",
        "daily_budget": 50,
    })
    assert payloads[-1]["ad_group"]["conversion_id"] == 42


def test_tiktok_campaign_lookup_by_name_uses_list_result():
    class Client:
        def list_campaigns(self, advertiser_id, page_size=20):
            assert advertiser_id == "t1"
            assert page_size == 20
            return [{"campaign_id": "101", "campaign_name": "Sales App"}]

        def get_campaign(self, advertiser_id, campaign_id):
            return {
                "campaign_id": campaign_id,
                "campaign_name": "Sales App",
                "advertiser_id": advertiser_id,
            }

    result = TikTokGetCampaignHandler(Client()).execute(
        ToolContext(session_id="s1", user_id="u1", account_id="t1"),
        {"campaign_name": "Sales App"},
    )

    assert result.success is True
    assert result.data["campaign"]["campaign_id"] == "101"


def test_meta_boost_client_builds_timestamped_request():
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"id": "boost-1"}
    )

    result = client.boost_post("m1", "page-1", "post-1", 10, 1)

    assert result == "boost-1"
    assert payloads[-1][0:2] == ("POST", "/m1/promoted_objects")
    assert payloads[-1][2]["scheduled_publish_time"] > 0


def test_google_creation_options_are_mapped_to_rest_resources():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    operations = []

    def fake_mutate(resource, operation):
        operations.append((resource, operation))
        return {
            "data": {
                "results": [{
                    "resourceName": f"customers/g1/{resource}/resource-1"
                }]
            }
        }

    client._mutate = fake_mutate
    client.create_campaign(
        "Sales", "SEARCH", "TARGET_ROAS", 10,
        target_roas=3.5,
        networks=["GOOGLE_SEARCH", "SEARCH_PARTNERS"],
        start_date="2026-08-28", end_date="2026-09-04",
    )
    campaign = operations[1][1]["create"]
    assert campaign["startDate"] == "2026-08-28"
    assert campaign["endDate"] == "2026-09-04"
    assert campaign["networkSettings"]["targetGoogleSearch"] is True
    assert campaign["networkSettings"]["targetSearchNetwork"] is True
    assert campaign["targetRoas"] == {"targetRoas": 3.5}

    operations.clear()
    client.create_campaign(
        "Clicks", "SEARCH", "TARGET_IMPRESSION_SHARE", 10,
        target_impression_share=0.7,
    )
    impression_share_campaign = operations[1][1]["create"]
    assert impression_share_campaign["targetImpressionShare"] == {
        "location": "ANYWHERE_ON_PAGE",
        "locationFractionMicros": 700000,
    }

    client.create_ad_group(
        "c1", "Group", cpc_bid_micros=123456,
        type="SEARCH_STANDARD", targeting={"target_restrictions": []},
    )
    ad_group = operations[-1][1]["create"]
    assert ad_group["cpcBidMicros"] == 123456
    assert ad_group["type"] == "SEARCH_STANDARD"
    assert ad_group["targetingSetting"] == {"targetRestrictions": []}

    client.create_search_ad(
        "ag1", ["Headline 1", "Headline 2"], ["Description 1", "Description 2"],
        "https://example.test", path1="buy", path2="now",
    )
    ad = operations[-1][1]["create"]["ad"]
    assert ad["responsiveSearchAd"]["path1"] == "buy"
    assert ad["responsiveSearchAd"]["path2"] == "now"


def test_dv360_io_and_line_item_options_are_not_replaced_by_defaults():
    client = DV360APIClient({"access_token": "test", "partner_id": "p1"})
    payloads = []
    client.request_raw = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"data": {"name": "advertisers/a/insertionOrders/resource-1"}}
    )

    client.create_io("a1", {
        "name": "IO",
        "budget": 12,
        "spend_cap_micros": 3450000,
        "start_date": "2026-08-28",
        "end_date": "2026-09-04",
        "status": "PAUSED",
        "pacing_type": "ASAP",
        "frequency_cap": {"time_unit": "DAY", "max_impressions": 3},
    })
    io = payloads[-1]
    assert io["spendCapMicros"] == 3450000
    assert io["startDateSeconds"] != 0
    assert io["status"] == "PAUSED"
    assert io["pacing"] == {"pacingType": "ASAP"}
    assert io["frequencyCap"]["max_impressions"] == 3

    payloads.clear()
    client.request_raw = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"data": {"name": "advertisers/a/insertionOrders/io1/lineItems/li1"}}
    )
    client.create_line_item("a1", "io1", {
        "name": "LI",
        "type": "VIDEO_DEFAULT",
        "goal": {"goal_type": "CONVERSIONS"},
        "targeting": {"geo": {"country": "US"}},
        "budget": 20,
        "start_date": "2026-08-28",
        "end_date": "2026-09-04",
        "status": "PAUSED",
        "bid_strategy": "TARGET_CPA",
        "bid_amount": 2.5,
    })
    line_item = payloads[-1]
    assert line_item["lineItemType"] == "VIDEO_DEFAULT"
    assert line_item["goal"] == {"goalType": "CONVERSIONS"}
    assert line_item["budget"] == 20
    assert line_item["startDate"] == "2026-08-28"
    assert line_item["status"] == "PAUSED"
    assert line_item["bidStrategy"] == "TARGET_CPA"
    assert line_item["bidAmount"] == 2.5
