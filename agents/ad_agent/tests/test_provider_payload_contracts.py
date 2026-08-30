"""Ensure existing provider creation schemas reach their API adapters."""

import json
import pytest

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
from agents.ad_agent.api_clients.base import APIError
from agents.ad_agent.capabilities.tiktok.campaigns import TikTokGetCampaignHandler
from agents.ad_agent.capabilities.meta.capability import _meta_update_adapter
from agents.ad_agent.capabilities.tiktok.capability import _tiktok_update_adapter
from agents.ad_agent.capabilities.google.capability import _google_update_adapter
from agents.ad_agent.capabilities.base import CampaignUpdateHandler


def test_generic_campaign_type_maps_to_google_wire_field():
    runtime = AgentRuntime(require_llm=False, )
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


def test_meta_graph_payload_normalizes_categories_and_nested_updates():
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"id": "resource-1"}
    )

    client.create_campaign("m1", {"name": "Reach", "objective": "OUTCOME_AWARENESS"})
    assert payloads[-1]["special_ad_categories"] == ["NONE"]
    assert payloads[-1]["is_adset_budget_sharing_enabled"] is False

    client.update_adset("as1", {
        "targeting": {"geo_locations": {"countries": ["US"]}},
        "daily_budget": 12,
    })
    assert json.loads(payloads[-1]["targeting"]) == {
        "geo_locations": {"countries": ["US"]}
    }
    assert payloads[-1]["daily_budget"] == "1200"


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
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"ad_group_id": "ag-1"}
    )
    client.create_adgroup("t1", "101", {
        "name": "App Group",
        "promotion_type": "APP_ANDROID",
        "billing_event": "OCPM",
        "conversion_id": 42,
        "budget_mode": "BUDGET_MODE_DAY",
        "daily_budget": 50,
    })
    assert payloads[-1]["ad_group"]["conversion_id"] == 42


def test_tiktok_lead_ad_builds_instant_form_promote_object():
    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"ad_id": "lead-ad-1"}
    )

    assert client.create_lead_ad("t1", "101", "202", {
        "name": "Lead ad", "form_id": "form-1",
        "media": [{"video_id": "video-1"}],
        "text": {"primary_text": "Get the guide"},
        "tracking_url": "https://example.test/track",
    }) == "lead-ad-1"
    method, endpoint, data = payloads[-1]
    assert (method, endpoint) == ("POST", "ad/create/")
    ad = data["ad"]
    assert ad["promotion_type"] == "LEAD_FORM"
    assert ad["form_id"] == "form-1"
    assert ad["promote_object"] == {"lead_form": {"form_id": "form-1"}}
    assert ad["media"] == [{"video_id": "video-1"}]
    assert ad["tracking_url"] == "https://example.test/track"

    with pytest.raises(ValueError, match="form_id is required"):
        client.create_lead_ad("t1", "101", "202", {"name": "Missing"})


def test_tiktok_audience_creation_builds_provider_envelope():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data)) or {"audience_id": "aud-1"}
    )

    assert client.create_audience("adv-1", {
        "name": "Purchasers 30D",
        "audience_type": "CUSTOM_AUDIENCE",
        "rule": {"event_sources": ["PIXEL_ID"]},
        "retention_in_days": 30,
    }) == "aud-1"
    assert calls == [(
        "POST", "audience/create/", {
            "advertiser_id": "adv-1",
            "name": "Purchasers 30D",
            "audience_type": "CUSTOM_AUDIENCE",
            "rule": {"event_sources": ["PIXEL_ID"]},
            "retention_in_days": 30,
        },
    )]


def test_google_campaign_criteria_builds_targeting_mutations():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    calls = []
    client.request_raw = lambda method, url, data=None, **kwargs: (
        calls.append((method, url, data)) or {
            "status_code": 200,
            "data": {"results": [
                {"resourceName": "customers/123/campaignCriteria/456~1"},
                {"resourceName": "customers/123/campaignCriteria/456~2"},
            ]},
        }
    )

    ids = client.create_campaign_criteria("456", [
        {"criterion_type": "LOCATION", "location_id": "geoTargetConstants/1014044"},
        {"criterion_type": "DEVICE", "device": "MOBILE", "negative": True},
    ])

    assert ids == ["1", "2"]
    assert calls[-1][0] == "POST"
    assert calls[-1][1].endswith("/customers/123/campaignCriteria:mutate")
    operations = calls[-1][2]["operations"]
    assert operations[0]["create"]["campaign"] == "customers/123/campaigns/456"
    assert operations[0]["create"]["location"] == {
        "geoTargetConstant": "geoTargetConstants/1014044"
    }
    assert operations[1]["create"]["device"] == {"type": "MOBILE"}
    assert operations[1]["create"]["negative"] is True


def test_google_campaign_criterion_update_and_delete_are_scoped():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    calls = []
    client.request_raw = lambda method, url, data=None, **kwargs: (
        calls.append((method, url, data)) or {"status_code": 200, "data": {"results": []}}
    )

    assert client.update_campaign_criterion("456", "7", {
        "status": "PAUSED", "bid_modifier": 1.25,
    })["success"] is True
    assert client.delete_campaign_criterion("456", "7")["success"] is True

    update = calls[-2][2]["operations"][0]
    assert update["update"]["resourceName"] == "customers/123/campaignCriteria/456~7"
    assert update["update"]["bidModifier"] == 1.25
    assert update["updateMask"] == {"paths": ["status", "bidModifier"]}
    remove = calls[-1][2]["operations"][0]
    assert remove["remove"] == "customers/123/campaignCriteria/456~7"


def test_google_campaign_criterion_reads_normalize_oneof_fields():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    client._search_all = lambda query, page_size=100: [{
        "campaign": {"id": "456"},
        "campaignCriterion": {
            "criterionId": "7",
            "type": "LOCATION",
            "status": "ENABLED",
            "negative": False,
            "location": {"geoTargetConstant": "geoTargetConstants/1014044"},
        },
    }]

    result = client.get_campaign_criterion("456", "7")

    assert result["criterion_id"] == "7"
    assert result["campaign_id"] == "456"
    assert result["location_id"] == "geoTargetConstants/1014044"
    assert result["type"] == "LOCATION"


def test_tiktok_app_ad_builds_app_install_promote_object_and_checks_os():
    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"ad_id": "app-ad-1"}
    )

    assert client.create_app_ad("t1", "101", "202", {
        "name": "App install", "app_id": "app-1", "promotion_type": "APP_ANDROID",
        "operating_systems": ["ANDROID"],
        "media": [{"video_id": "video-1"}],
        "deep_link": "myapp://home",
    }) == "app-ad-1"
    ad = payloads[-1][2]["ad"]
    assert ad["app_id"] == "app-1"
    assert ad["promotion_type"] == "APP_ANDROID"
    assert ad["operating_systems"] == ["ANDROID"]
    assert ad["promote_object"] == {"app_install": {"app_id": "app-1"}}
    assert ad["deep_link"] == "myapp://home"

    with pytest.raises(ValueError, match="requires operating_systems"):
        client.create_app_ad("t1", "101", "202", {
            "name": "Wrong OS", "app_id": "app-1", "promotion_type": "APP_ANDROID",
            "operating_systems": ["IOS"], "media": [{"video_id": "video-1"}],
        })


def test_tiktok_lead_and_app_tools_publish_provider_contracts():
    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    lead = definitions["tiktok_create_lead_ad"]
    assert lead.input_schema.properties["form_id"]["minLength"] == 1
    assert lead.input_schema.properties["conversion_id"]["lookup_tool"] == (
        "tiktok_list_conversions"
    )
    assert lead.parent_resource_type == "ad_group"
    app = definitions["tiktok_create_app_ad"]
    assert app.input_schema.properties["app_id"]["lookup_tool"] == "tiktok_list_apps"
    assert app.input_schema.properties["promotion_type"]["enum"] == [
        "APP_ANDROID", "APP_IOS"
    ]
    assert app.parent_resource_id_field == "adgroup_id"


def test_tiktok_provider_envelope_is_decoded_for_ids_and_lookup_lists():
    client = TikTokAPIClient({"access_token": "test"})
    client._do_request = lambda method, url, **kwargs: {
        "status_code": 200,
        "data": {
            "code": 0,
            "message": "OK",
            "data": {"campaign_id": "campaign-42"},
        },
        "headers": {},
    }

    campaign_id = client.create_campaign(
        "t1",
        {
            "name": "Envelope campaign",
            "objective_type": "TRAFFIC",
            "campaign_type": "REGULAR_CAMPAIGN",
            "budget_mode": "BUDGET_MODE_INFINITE",
        },
    )

    assert campaign_id == "campaign-42"

    client._do_request = lambda method, url, **kwargs: {
        "status_code": 200,
        "data": {
            "code": 0,
            "message": "OK",
            "data": {"list": [{"location_id": "US"}]},
        },
        "headers": {},
    }
    assert client.list_locations() == [{"location_id": "US"}]


def test_tiktok_report_failure_and_missing_task_are_not_silent_successes():
    client = TikTokAPIClient({"access_token": "test"})
    client.request = lambda method, endpoint, data=None, **kwargs: {
        "task_id": "task-1"
    } if endpoint == "report/task/create/" else {
        "status": 3, "message": "invalid report"
    }
    with pytest.raises(APIError, match="report task failed"):
        client.get_campaign_report("t1", ["1"])

    client.request = lambda *args, **kwargs: {}
    with pytest.raises(APIError, match="no task_id"):
        client.get_campaign_report("t1", ["1"])


def test_meta_client_does_not_mutate_caller_query_params(monkeypatch):
    client = MetaAPIClient({"access_token": "test"})
    captured = {}

    class Response:
        status_code = 200
        content = b"{}"
        headers = {}

        @staticmethod
        def json():
            return {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = dict(params or {})
        return Response()

    monkeypatch.setattr("agents.ad_agent.api_clients.meta_client.requests.get", fake_get)
    params = {"fields": "id,name"}
    client._do_request("GET", "https://example.test", params=params)

    assert params == {"fields": "id,name"}
    assert captured["params"]["access_token"] == "test"


def test_meta_creation_dependency_lookups_cover_pages_pixels_and_lead_forms():
    client = MetaAPIClient({"access_token": "test"})
    calls = []

    def fake_pages(account_id, endpoint, params, item_key="data", max_pages=100):
        calls.append((account_id, endpoint, params))
        return [{"id": "resource-1"}]

    client._list_graph_pages = fake_pages
    assert client.list_pages("act_123")[0]["id"] == "resource-1"
    assert client.list_pixels("123")[0]["id"] == "resource-1"
    assert client.list_lead_forms("page-1")[0]["id"] == "resource-1"
    assert calls == [
        ("123", "/act_123/promoted_pages", {"limit": 25, "fields": "id,name,category"}),
        ("123", "/act_123/adspixels", {"limit": 25, "fields": "id,name,last_fired_time"}),
        ("page-1", "/page-1/leadgen_forms", {
            "limit": 25, "fields": "id,name,status,created_time,updated_time"
        }),
    ]


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


def test_meta_lead_ad_builds_instant_form_story_spec():
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"id": "ad-lead-1"}
    )

    assert client.create_lead_ad("act_1", "as_1", {
        "name": "Lead Ad", "page_id": "page-1", "form_id": "form-1",
        "message": "Get the guide", "headline": "Download now",
        "call_to_action_type": "SIGN_UP", "status": "PAUSED",
    }) == "ad-lead-1"
    method, endpoint, data = payloads[-1]
    assert (method, endpoint) == ("POST", "/act_1/ads")
    creative = json.loads(data["creative"])
    assert creative == {
        "object_story_spec": {
            "page_id": "page-1",
            "link_data": {
                "message": "Get the guide",
                "name": "Download now",
                "description": "",
                "call_to_action": {
                    "type": "SIGN_UP",
                    "value": {"lead_gen_form_id": "form-1"},
                },
            },
        }
    }

    with pytest.raises(ValueError, match="page_id and form_id"):
        client.create_lead_ad("act_1", "as_1", {"name": "Missing"})


def test_meta_catalog_ad_builds_template_story_spec():
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"id": "ad-catalog-1"}
    )

    assert client.create_catalog_ad("act_1", "as_1", {
        "name": "Catalog Ad", "page_id": "page-1", "product_set_id": "set-1",
        "link": "https://example.test/shop", "message": "Shop now",
        "headline": "Summer collection", "ad_style": "CAROUSEL",
        "call_to_action_type": "SHOP_NOW", "status": "PAUSED",
    }) == "ad-catalog-1"
    method, endpoint, data = payloads[-1]
    assert (method, endpoint) == ("POST", "/act_1/ads")
    creative = json.loads(data["creative"])
    assert creative["object_story_spec"]["page_id"] == "page-1"
    assert creative["object_story_spec"]["template_data"] == {
        "product_set_id": "set-1",
        "link": "https://example.test/shop",
        "message": "Shop now",
        "name": "Summer collection",
        "description": "",
        "call_to_action": {"type": "SHOP_NOW"},
        "format_option": "CAROUSEL",
    }

    with pytest.raises(ValueError, match="page_id, product_set_id and link"):
        client.create_catalog_ad("act_1", "as_1", {"name": "Missing"})


def test_meta_catalog_tools_expose_lookup_and_format_contract():
    capability = create_meta_capability()
    definitions = {
        definition.name: definition
        for definition, _handler in capability.register_tools()
    }
    assert "meta_list_catalogs" in definitions
    assert "meta_list_product_sets" in definitions
    catalog_ad = definitions["meta_create_catalog_ad"]
    assert catalog_ad.input_schema.properties["product_set_id"]["lookup_tool"] == (
        "meta_list_product_sets"
    )
    campaign = definitions["meta_create_campaign"]
    assert campaign.input_schema.properties["catalog_id"]["lookup_tool"] == (
        "meta_list_catalogs"
    )
    adset = definitions["meta_create_adset"]
    assert adset.input_schema.properties["product_set_id"]["lookup_tool"] == (
        "meta_list_product_sets"
    )
    assert catalog_ad.input_schema.properties["ad_style"]["enum"] == [
        "CAROUSEL", "COLLAGE", "PRODUCT_SET"
    ]
    assert catalog_ad.live_support is False


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

    client.create_campaign(
        "App installs", "APP", "MAXIMIZE_CONVERSIONS", 10,
        app_campaign_setting={
            "app_id": "com.example.app",
            "app_store": "GOOGLE_APP_STORE",
            "bidding_strategy_type": "TARGET_CPA",
        },
    )
    app_campaign = operations[-1][1]["create"]
    assert app_campaign["appCampaignSetting"] == {
        "appId": "com.example.app",
        "appStore": "GOOGLE_APP_STORE",
        "biddingStrategyType": "TARGET_CPA",
    }

    client.create_campaign(
        "Value", "SEARCH", "MAXIMIZE_CONVERSION_VALUE", 10,
        target_roas=2.5,
    )
    value_campaign = operations[-1][1]["create"]
    assert value_campaign["maximizeConversionValue"] == {"targetRoas": 2.5}

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


def test_google_keyword_creation_batches_criterion_operations():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    calls = []
    client._mutate_operations = lambda resource, operations: (
        calls.append((resource, operations)) or {
            "data": {
                "results": [
                    {"resourceName": "customers/g1/adGroupCriteria/123~1"},
                    {"resourceName": "customers/g1/adGroupCriteria/123~2"},
                ]
            }
        }
    )

    result = client.create_keywords("123", [
        {"text": "running shoes", "match_type": "PHRASE"},
        {"text": "free", "match_type": "EXACT", "negative": True},
    ])

    assert result == ["123~1", "123~2"]
    assert calls[0][0] == "adGroupCriteria"
    assert len(calls[0][1]) == 2
    assert calls[0][1][0]["create"]["adGroup"] == "customers/g1/adGroups/123"
    assert calls[0][1][0]["create"]["keyword"] == {
        "text": "running shoes", "matchType": "PHRASE"
    }
    assert calls[0][1][1]["create"]["negative"] is True


def test_google_product_group_creation_builds_listing_group_criterion():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    calls = []
    client._mutate_operations = lambda resource, operations: (
        calls.append((resource, operations)) or {
            "data": {"results": [{"resourceName": "customers/g1/adGroupCriteria/123~456"}]}
        }
    )

    assert client.create_product_group(
        "123", "product_type_1", "Shoes", partition_type="SUBDIVISION",
        parent_criterion_id="123~111", cpc_bid_micros=250000,
    ) == "123~456"
    resource, operations = calls[-1]
    assert resource == "adGroupCriteria"
    criterion = operations[0]["create"]
    assert criterion["adGroup"] == "customers/g1/adGroups/123"
    assert criterion["cpcBidMicros"] == 250000
    assert criterion["listingGroup"] == {
        "type": "SUBDIVISION",
        "parentAdGroupCriterion": "customers/g1/adGroupCriteria/123~111",
        "caseValue": {"productType": {"level": "LEVEL1", "value": "Shoes"}},
    }

    client.create_product_group("123", "all_products")
    assert calls[-1][1][0]["create"]["listingGroup"] == {"type": "UNIT"}

    client.create_product_group(
        "123", "brand", "Acme",
        parent_criterion_id="customers/g1/adGroupCriteria/123~111",
    )
    assert calls[-1][1][0]["create"]["listingGroup"]["parentAdGroupCriterion"] == (
        "customers/g1/adGroupCriteria/123~111"
    )

    client.create_product_group(
        "123", "bidding_category", "1234", bidding_category_level="LEVEL3"
    )
    assert calls[-1][1][0]["create"]["listingGroup"]["caseValue"] == {
        "productBiddingCategory": {"level": "LEVEL3", "id": 1234}
    }

    with pytest.raises(ValueError, match="another customer|belong"):
        client.create_product_group("123", "brand", "Acme", parent_criterion_id="999~1")


def test_google_responsive_display_ad_builds_dedicated_ad_payload():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    operations = []
    client._mutate = lambda resource, operation: (
        operations.append((resource, operation)) or {
            "data": {"results": [{"resourceName": "customers/g1/adGroupAds/123~456"}]}
        }
    )

    result = client.create_responsive_display_ad(
        "123", "Summer Display", "https://example.test",
        ["Sale", "Shop now", "Free shipping"],
        "Summer sale up to 50% off",
        ["Limited time", "Order today"],
        "Example Store",
        marketing_images=["customers/g1/assets/11"],
        logos=[{"asset": "customers/g1/assets/12"}],
        call_to_action_text="SHOP_NOW",
        allow_flexible_color=False,
    )

    assert result == "123~456"
    resource, operation = operations[-1]
    assert resource == "adGroupAds"
    ad = operation["create"]["ad"]
    assert ad["responsiveDisplayAd"]["headlines"] == [
        {"text": "Sale"}, {"text": "Shop now"}, {"text": "Free shipping"}
    ]
    assert ad["responsiveDisplayAd"]["longHeadline"] == {
        "text": "Summer sale up to 50% off"
    }
    assert ad["responsiveDisplayAd"]["marketingImages"] == [
        {"asset": "customers/g1/assets/11"}
    ]
    assert ad["responsiveDisplayAd"]["logoImages"] == [
        {"asset": "customers/g1/assets/12"}
    ]
    assert ad["responsiveDisplayAd"]["allowFlexibleColor"] is False


def test_google_video_ad_builds_format_specific_payload():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    operations = []
    client._mutate = lambda resource, operation: (
        operations.append((resource, operation)) or {
            "data": {"results": [{"resourceName": "customers/g1/adGroupAds/123~789"}]}
        }
    )

    result = client.create_video_ad(
        "123", "YouTube bumper", "BUMPER", "dQw4w9WgXcQ",
        "https://example.test", action_button_label="SHOP_NOW",
        action_headline="Summer sale",
    )

    assert result == "123~789"
    resource, operation = operations[-1]
    assert resource == "adGroupAds"
    video_ad = operation["create"]["ad"]["videoAd"]
    assert video_ad["videoId"] == "dQw4w9WgXcQ"
    assert video_ad["bumper"] == {}
    assert video_ad["actionButtonLabel"] == "SHOP_NOW"
    assert video_ad["actionHeadline"] == "Summer sale"

    with pytest.raises(ValueError, match="video_ad_format"):
        client.create_video_ad(
            "123", "Invalid", "UNKNOWN", "video", "https://example.test"
        )


def test_google_reads_accept_raw_and_extracted_search_payloads():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    row = {"campaign": {"id": "42", "name": "Sales", "status": "PAUSED"}}
    client._search = lambda query: {"results": [row]}
    assert client.get_campaign("42")["name"] == "Sales"

    client._search = lambda query: {"data": {"results": [row]}}
    assert client.get_campaign("42")["id"] == "42"


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


def test_dv360_creative_targeting_and_delete_methods_use_verified_endpoints():
    client = DV360APIClient({"access_token": "test", "partner_id": "p1"})
    calls = []

    def request_raw(method, endpoint, data=None, **kwargs):
        calls.append((method, endpoint, data, kwargs))
        if method == "POST" and endpoint.endswith("/creatives"):
            return {"data": {"name": "advertisers/a/creatives/cr1"}}
        if method == "POST" and endpoint.endswith("/assignedTargetingOptions"):
            return {"data": {"name": "advertisers/a/lineItems/li1/targetingTypes/4/assignedTargetingOptions/to1"}}
        if method == "GET" and endpoint.endswith("/creatives"):
            return {"data": {"creatives": [{"creativeId": "cr1"}]}}
        if method == "GET" and "/creatives/" in endpoint:
            return {"data": {"creativeId": "cr1", "displayName": "Creative"}}
        if method == "GET" and "targetingOptions" in endpoint:
            return {"data": {"targetingOptions": [{"targetingOptionId": "to1"}]}}
        if method == "GET" and "assignedTargetingOptions" in endpoint:
            return {"data": {"assignedTargetingOptions": [{"assignedTargetingOptionId": "to1"}]}}
        return {"data": {}}

    client.request_raw = request_raw

    assert client.list_creatives("a1", filter="active", page_size=10)[0]["creativeId"] == "cr1"
    assert client.get_creative("a1", "cr1")["creativeId"] == "cr1"
    assert client.create_creative("a1", {"name": "Creative"}) == "cr1"
    assert client.update_creative("a1", "cr1", {"displayName": "Updated"})["success"] is True
    assert client.delete_creative("a1", "cr1")["creative_id"] == "cr1"
    assert client.list_targeting_options("4")[0]["targetingOptionId"] == "to1"
    assert client.list_line_item_assigned_targeting_options("a1", "li1", "4")[0]["assignedTargetingOptionId"] == "to1"
    assert client.create_line_item_assigned_targeting_option("a1", "li1", "4", {"targetingOptionId": "to1"}) == "to1"
    assert client.delete_line_item_assigned_targeting_option("a1", "li1", "4", "to1")["success"] is True
    assert client.delete_campaign("a1", "c1")["campaign_id"] == "c1"
    assert client.delete_io("a1", "io1")["io_id"] == "io1"
    assert client.delete_line_item("a1", "io1", "li1")["line_item_id"] == "li1"

    assert ("DELETE", "/campaigns/c1") in [
        (method, endpoint[endpoint.find("/campaigns"):])
        for method, endpoint, _data, _kwargs in calls
        if "/campaigns/" in endpoint
    ]


def test_dv360_extended_methods_are_published_as_tools():
    definitions = {
        definition.name: definition
        for definition, _handler in create_dv360_capability().register_tools()
    }
    expected = {
        "dv360_delete_campaign", "dv360_delete_io", "dv360_delete_line_item",
        "dv360_list_creatives", "dv360_get_creative", "dv360_create_creative",
        "dv360_update_creative", "dv360_delete_creative", "dv360_list_targeting_options",
        "dv360_list_line_item_assigned_targeting_options",
        "dv360_create_line_item_assigned_targeting_option",
        "dv360_delete_line_item_assigned_targeting_option",
    }
    assert expected <= definitions.keys()
    assert all(definitions[name].is_write_tool and not definitions[name].live_support
               for name in expected if "delete" in name or "create" in name or "update" in name)
    assert definitions["dv360_create_line_item_assigned_targeting_option"].parent_resource_id_field == "line_item_id"


def test_existing_update_tools_dispatch_to_normalized_resource_adapters():
    class MetaClient:
        def update_adset(self, resource_id, updates):
            return {"resource_id": resource_id, "updates": updates}

    meta_result = _meta_update_adapter(
        MetaClient(), ToolContext(session_id="s1", user_id="u1", account_id="m1"),
        "ad_set", "as1", "c1", {"status": "PAUSED"},
    )
    assert meta_result["resource_id"] == "as1"

    class TikTokClient:
        def update_adgroup(self, advertiser_id, campaign_id, adgroup_id, updates):
            return (advertiser_id, campaign_id, adgroup_id, updates)

        def update_ad(self, advertiser_id, adgroup_id, ad_id, updates):
            return (advertiser_id, adgroup_id, ad_id, updates)

    context = ToolContext(session_id="s1", user_id="u1", account_id="t1")
    client = TikTokClient()
    assert _tiktok_update_adapter(
        client, context, "ad_group", "ag1", "c1", {"ad_group_status": 0}
    )[1:3] == ("c1", "ag1")
    assert _tiktok_update_adapter(
        client, context, "ad", "ad1", "ag1", {"status": 0}
    )[1:3] == ("ag1", "ad1")

    class GoogleClient:
        def update_ad_group(self, resource_id, updates):
            return (resource_id, updates)

        def update_ad(self, resource_id, updates):
            return (resource_id, updates)

        def update_asset_group(self, resource_id, updates):
            return (resource_id, updates)

    google = GoogleClient()
    for resource_type, method_result in (
        ("ad_group", google.update_ad_group("ag1", {"status": "PAUSED"})),
        ("ad", google.update_ad("ad1", {"status": "PAUSED"})),
        ("asset_group", google.update_asset_group("asset1", {"status": "PAUSED"})),
    ):
        assert _google_update_adapter(
            google, context, resource_type, method_result[0], None, method_result[1]
        ) == method_result


def test_provider_create_and_detail_contracts_reject_empty_success_payloads():
    clients = [
        (MetaAPIClient({"access_token": "test"}), "create_campaign", ("m1", {"name": "x"})),
        (TikTokAPIClient({"access_token": "test"}), "create_campaign", ("t1", {"name": "x"})),
    ]
    for client, method_name, args in clients:
        client.request = lambda *args, **kwargs: {}
        with pytest.raises(APIError, match="resource ID"):
            getattr(client, method_name)(*args)

    meta = MetaAPIClient({"access_token": "test"})
    meta.request = lambda *args, **kwargs: {}
    with pytest.raises(APIError, match="resource"):
        meta.get_campaign("c1")

    google = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    google._search = lambda query: {"results": []}
    with pytest.raises(APIError, match="(resource|not found)"):
        google.get_campaign("1")


def test_google_and_dv360_existing_update_adapters_build_provider_mutations():
    google = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    operations = []
    google._mutate = lambda resource, operation: (
        operations.append((resource, operation)) or {"results": [{}]}
    )
    assert google.update_ad_group("42", {"cpc_bid": 1.25})["success"] is True
    resource, operation = operations[-1]
    assert resource == "adGroups"
    assert operation["update"]["resourceName"] == "customers/123/adGroups/42"
    assert operation["update"]["cpcBidMicros"] == 1_250_000
    assert operation["updateMask"] == {"paths": ["cpcBidMicros"]}

    assert google.update_ad("43", {"status": "PAUSED"})["success"] is True
    assert operations[-1][0] == "adGroupAds"
    assert google.update_asset_group("44", {"name": "Assets"})["success"] is True
    assert operations[-1][0] == "assetGroups"

    dv = DV360APIClient({"access_token": "test"})
    requests = []
    dv.request_raw = lambda method, endpoint, **kwargs: (
        requests.append((method, endpoint, kwargs)) or {"data": {}}
    )
    result = dv.update_resource(
        "line_item", "adv1", "li1", "io1",
        {"budget": 20, "status": "PAUSED", "targeting": {"country": "US"}},
    )
    assert result == {"success": True, "resource_id": "li1"}
    method, endpoint, kwargs = requests[-1]
    assert method == "PATCH"
    assert endpoint.endswith("/advertisers/adv1/insertionOrders/io1/lineItems/li1")
    assert kwargs["data"] == {
        "budget": 20, "status": "PAUSED", "targeting": {"country": "US"}
    }
    assert kwargs["params"]["updateMask"] == "budget,status,targeting"


def test_google_campaign_budget_tools_cover_gaql_and_mutations():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    client._search_all = lambda query, page_size=100: [{
        "campaignBudget": {
            "id": "7", "resourceName": "customers/123/campaignBudgets/7",
            "name": "Daily", "amountMicros": "2500000",
            "deliveryMethod": "STANDARD", "explicitlyShared": False,
        }
    }]
    budgets = client.list_campaign_budgets()
    assert budgets[0]["id"] == "7"
    assert budgets[0]["amount_micros"] == "2500000"

    client._search = lambda query: {"data": {"results": [{
        "campaignBudget": {"id": "7", "name": "Daily", "amountMicros": 2500000}
    }]}}
    assert client.get_campaign_budget("7")["name"] == "Daily"

    operations = []
    client._mutate = lambda resource, operation: (
        operations.append((resource, operation)) or {
            "data": {"results": [{
                "resourceName": "customers/123/campaignBudgets/8"
            }]}
        }
    )
    assert client.create_campaign_budget("New", 3.5) == "8"
    assert operations[-1][1]["create"] == {
        "name": "New", "amountMicros": 3500000,
        "deliveryMethod": "STANDARD", "explicitlyShared": False,
    }
    assert client.update_campaign_budget("8", {"daily_budget": 4, "name": "Updated"})["success"]
    assert operations[-1][1]["update"] == {
        "resourceName": "customers/123/campaignBudgets/8",
        "amountMicros": 4000000, "name": "Updated",
    }
    assert operations[-1][1]["updateMask"] == {"paths": ["amountMicros", "name"]}
    assert client.delete_campaign_budget("8")["success"]
    assert operations[-1][1] == {
        "remove": "customers/123/campaignBudgets/8"
    }


def test_google_extended_provider_tools_resolve_customer_scoped_client():
    seen = []

    class TrackingGoogleClient(GoogleAdsAPIClient):
        def for_customer(self, customer_id):
            scoped = super().for_customer(customer_id)
            scoped.get_campaign_budget = lambda budget_id: (
                seen.append((scoped.customer_id, budget_id)) or {"id": budget_id}
            )
            return scoped

    client = TrackingGoogleClient({"access_token": "test", "customer_id": "base"})
    capability = create_google_capability(client)
    definitions = {
        definition.name: handler
        for definition, handler in capability.register_tools()
    }
    handler = definitions["google_get_campaign_budget"]
    result = handler.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="customer-2"),
        {"budget_id": "7"},
    )
    assert result.ok
    assert seen == [("customer-2", "7")]
