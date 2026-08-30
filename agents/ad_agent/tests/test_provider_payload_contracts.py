"""Ensure existing provider creation schemas reach their API adapters."""

import json
import hashlib
import pytest

from agents.ad_agent.capabilities.meta import create_meta_capability
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.capabilities.tiktok import create_tiktok_capability
from agents.ad_agent.capabilities.dv360 import create_dv360_capability
from agents.ad_agent.core.interfaces import ParsedIntent, ToolContext
from agents.ad_agent.core.tool_registry import validate_tool_input
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.api_clients.dv360_client import DV360APIClient
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.api_clients.base import APIError
from agents.ad_agent.capabilities.tiktok.campaigns import TikTokGetCampaignHandler
from agents.ad_agent.capabilities.google.campaigns import GoogleCreateCampaignHandler
from agents.ad_agent.capabilities.meta.capability import _meta_update_adapter
from agents.ad_agent.capabilities.tiktok.capability import _tiktok_update_adapter
from agents.ad_agent.capabilities.google.capability import _google_update_adapter
from agents.ad_agent.capabilities.base import CampaignUpdateHandler


def test_creation_tools_publish_provider_payload_requirements():
    """Provider contracts must describe payload fields beyond account scope."""
    capabilities = {
        "dv360": create_dv360_capability(),
        "google-ads": create_google_capability(),
        "meta": create_meta_capability(),
        "tiktok": create_tiktok_capability(),
    }
    definitions = {
        platform: {
            definition.name: definition
            for definition, _handler in capability.register_tools()
        }
        for platform, capability in capabilities.items()
    }

    assert definitions["dv360"]["dv360_create_creative"].input_schema.provider_required == [
        "creative"
    ]
    assert definitions["dv360"]["dv360_create_line_item_assigned_targeting_option"].input_schema.provider_required == [
        "targeting_type", "assigned_targeting_option"
    ]
    assert definitions["dv360"]["dv360_create_report"].input_schema.provider_required == [
        "report"
    ]

    assert definitions["google-ads"]["google_create_campaign_budget"].input_schema.provider_required == [
        "name", "daily_budget"
    ]
    assert definitions["google-ads"]["google_create_search_ad"].input_schema.provider_required == [
        "headlines", "descriptions", "final_url"
    ]

    assert definitions["meta"]["meta_create_ad"].input_schema.provider_any_of == [
        ["creative_id", "object_story_spec", "creative", "media", "image_url"]
    ]
    assert validate_tool_input(
        definitions["meta"]["meta_create_ad"].input_schema,
        {"adset_id": "adset-1", "name": "image ad", "media": [{"url": "https://cdn.example/image.png"}]},
        include_provider_contract=True,
    ) == []
    assert definitions["meta"]["meta_create_creative"].input_schema.provider_required == [
        "name", "page_id", "link"
    ]
    assert definitions["meta"]["meta_create_catalog"].input_schema.provider_required == [
        "business_id", "name", "vertical"
    ]
    assert definitions["meta"]["meta_create_product_set"].input_schema.provider_required == [
        "catalog_id", "name"
    ]

    assert definitions["tiktok"]["tiktok_create_pixel"].input_schema.provider_required == [
        "name", "object_type"
    ]

    # Runtime context supplies the account/customer scope; missing business
    # payload fields must still be visible as provider-contract failures.
    errors = validate_tool_input(
        definitions["google-ads"]["google_create_campaign_budget"].input_schema,
        {"customer_id": "123", "name": "budget"},
        include_provider_contract=True,
    )
    assert any("daily_budget" in error for error in errors)


def test_tiktok_image_upload_builds_official_multipart_payload(tmp_path):
    image = tmp_path / "creative.png"
    image.write_bytes(b"image-bytes")
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, files=None, **_kwargs: (
        calls.append((method, endpoint, data, files)) or {"image_id": "img-1"}
    )

    result = client.upload_image("123", file_path=str(image))

    assert result["image_id"] == "img-1"
    assert calls[0][0:2] == ("POST", "file/image/ad/upload/")
    assert calls[0][2]["advertiser_id"] == "123"
    assert calls[0][2]["upload_type"] == "UPLOAD_BY_FILE"
    assert calls[0][2]["image_signature"] == hashlib.md5(b"image-bytes").hexdigest()
    assert calls[0][3]["image_file"][0] == "creative.png"
    assert calls[0][3]["image_file"][1].closed is True


def test_tiktok_video_upload_supports_provider_url_without_local_file():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, files=None, **_kwargs: (
        calls.append((method, endpoint, data, files)) or {"video_id": "vid-1"}
    )

    result = client.upload_video("123", video_url="https://cdn.example/video.mp4")

    assert result["video_id"] == "vid-1"
    assert calls[0][0:2] == ("POST", "file/video/ad/upload/")
    assert calls[0][2] == {
        "advertiser_id": "123",
        "upload_type": "UPLOAD_BY_URL",
        "video_url": "https://cdn.example/video.mp4",
    }
    assert calls[0][3] is None


def test_tiktok_media_upload_rejects_ambiguous_sources_and_exposes_tools():
    client = TikTokAPIClient({"access_token": "test"})
    with pytest.raises(ValueError, match="exactly one"):
        client.upload_image("123", image_url="https://cdn.example/a.png", file_id="f1")

    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert {"tiktok_upload_image", "tiktok_upload_video"} <= definitions.keys()
    assert definitions["tiktok_upload_image"].input_schema.provider_exactly_one_of == [
        ["file_path", "image_url", "file_id"]
    ]
    assert definitions["tiktok_upload_video"].live_support is False
    errors = validate_tool_input(
        definitions["tiktok_upload_image"].input_schema,
        {"account_id": "123", "image_url": "https://cdn.example/a.png", "file_id": "f1"},
        include_provider_contract=True,
    )
    assert any("exactly one" in error for error in errors)


def test_tiktok_pixel_track_and_batch_build_v13_payloads_and_tools():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, **_kwargs: (
        calls.append((method, endpoint, data)) or {"result": "ok"}
    )
    event = {
        "event": "CompletePayment",
        "event_id": "order-1",
        "timestamp": "2026-08-30T12:00:00Z",
        "context": {"page": {"url": "https://example.test/checkout"}},
        "properties": {"value": 19.9, "currency": "USD"},
    }

    assert client.send_pixel_event("123", "pixel-code", event) == {"result": "ok"}
    assert calls[0] == ("POST", "pixel/track/", {**event, "pixel_code": "pixel-code"})

    assert client.send_pixel_events("123", "pixel-code", [event]) == {"result": "ok"}
    assert calls[1] == (
        "POST", "pixel/batch/",
        {"pixel_code": "pixel-code", "batch": [{**event, "type": "track"}]},
    )

    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert definitions["tiktok_send_pixel_event"].live_support is False
    assert definitions["tiktok_send_pixel_events"].input_schema.properties["events"]["maxItems"] == 50
    assert validate_tool_input(
        definitions["tiktok_send_pixel_event"].input_schema,
        {"account_id": "123", "pixel_id": "pixel-code", **event},
    ) == []
    assert validate_tool_input(
        definitions["tiktok_send_pixel_events"].input_schema,
        {"account_id": "123", "pixel_id": "pixel-code", "events": [event]},
    ) == []


def test_tiktok_pixel_lifecycle_builds_scoped_v13_payloads_and_tools():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []

    def request(method, endpoint, data=None, params=None, **_kwargs):
        calls.append((method, endpoint, data, params))
        if endpoint == "pixel/get/":
            return {"list": [{"pixel_id": "px-1", "name": "Website Pixel"}]}
        if endpoint == "pixel/create/":
            return {"pixel_id": "px-new"}
        return {"updated": True}

    client.request = request
    assert client.list_pixels("123", pixel_ids=["px-1"], page_size=10) == [
        {"pixel_id": "px-1", "name": "Website Pixel"}
    ]
    assert client.get_pixel("123", "px-1")["name"] == "Website Pixel"
    assert client.create_pixel("123", {
        "name": "App Pixel", "object_type": "APP",
    }) == "px-new"
    assert client.update_pixel("123", "px-1", {"name": "Renamed Pixel"})["success"] is True

    assert calls[0] == (
        "GET", "pixel/get/", None,
        {"advertiser_id": "123", "page_size": 10, "pixel_ids": ["px-1"]},
    )
    assert calls[2] == (
        "POST", "pixel/create/",
        {"advertiser_id": "123", "name": "App Pixel", "object_type": "APP"}, None,
    )
    assert calls[-1] == (
        "POST", "pixel/update/",
        {"advertiser_id": "123", "pixel_id": "px-1", "name": "Renamed Pixel"}, None,
    )

    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert {
        "tiktok_list_pixels", "tiktok_get_pixel",
        "tiktok_create_pixel", "tiktok_update_pixel",
    } <= definitions.keys()
    assert definitions["tiktok_get_pixel"].input_schema.properties["pixel_id"]["lookup_tool"] == (
        "tiktok_list_pixels"
    )
    assert definitions["tiktok_create_pixel"].live_support is False
    assert definitions["tiktok_update_pixel"].input_schema.properties["updates"]["additionalProperties"] is False
    assert validate_tool_input(
        definitions["tiktok_create_pixel"].input_schema,
        {"account_id": "123", "name": "Website Pixel", "object_type": "WEBSITE"},
        include_provider_contract=True,
    ) == []


def test_tiktok_catalog_queries_are_scoped_validated_and_published_as_provider_tools():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, params=None, **_kwargs: (
        calls.append((method, endpoint, params))
        or {"data": {"list": [{"id": "catalog-1"}]}}
    )

    assert client.list_catalogs(
        "123", filtering=[{"field": "CATALOG_IDS", "operator": "IN", "values": ["catalog-1"]}],
        page_size=50,
    ) == [{"id": "catalog-1"}]
    assert client.list_product_sets("123", "catalog-1", page_size=10) == [
        {"id": "catalog-1"}
    ]
    assert calls == [
        (
            "GET", "catalog/get/",
            {
                "advertiser_id": "123", "page_size": 50,
                "filtering": [{"field": "CATALOG_IDS", "operator": "IN", "values": ["catalog-1"]}],
            },
        ),
        (
            "GET", "product_set/get/",
            {"advertiser_id": "123", "page_size": 10, "catalog_id": "catalog-1"},
        ),
    ]
    with pytest.raises(ValueError, match="digits only"):
        client.list_catalogs("advertiser-123")
    with pytest.raises(ValueError, match="between 1 and 100"):
        client.list_product_sets("123", page_size=101)
    with pytest.raises(ValueError, match="filtering must be an array"):
        client.list_catalogs("123", filtering={"field": "CATALOG_IDS"})

    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert definitions["tiktok_list_catalogs"].input_schema.provider_required == ["account_id"]
    assert definitions["tiktok_list_product_sets"].input_schema.properties["limit"]["maximum"] == 100
    assert definitions["tiktok_list_catalogs"].traits == ["read", "catalog", "lookup"]


def test_tiktok_creative_portfolio_uses_official_v13_payload_and_keeps_crud_gap_explicit():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, **_kwargs: (
        calls.append((method, endpoint, data)) or {"portfolio_id": "portfolio-1"}
    )
    content = [{"call_to_action_text": "Shop now", "asset_ids": ["asset-1"]}]

    result = client.create_creative_portfolio("123", "CTA", content)

    assert result == {"portfolio_id": "portfolio-1"}
    assert calls == [(
        "POST", "creative/portfolio/create/", {
            "advertiser_id": "123",
            "creative_portfolio_type": "CTA",
            "portfolio_content": content,
        },
    )]
    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    tool = definitions["tiktok_create_creative_portfolio"]
    assert tool.live_support is False
    assert validate_tool_input(
        tool.input_schema,
        {"account_id": "123", "creative_portfolio_type": "CTA", "portfolio_content": content},
    ) == []


def test_tiktok_creative_portfolio_get_and_preview_use_scoped_verified_endpoints():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []

    def request(method, endpoint, data=None, params=None, **_kwargs):
        calls.append((method, endpoint, data, params))
        if endpoint == "creative/portfolio/get/":
            return {
                "creative_portfolio_id": "portfolio-1",
                "creative_portfolio_type": "CTA",
                "portfolio_content": [{"asset_ids": ["asset-1"]}],
            }
        return {"preview_link": "https://preview.example/portfolio-1", "iframe": "<iframe/>"}

    client.request = request
    assert client.get_creative_portfolio("123", "portfolio-1")["creative_portfolio_id"] == (
        "portfolio-1"
    )
    assert client.preview_creative_portfolio("123", "portfolio-1") == {
        "preview_link": "https://preview.example/portfolio-1",
        "iframe": "<iframe/>",
    }
    assert calls == [
        (
            "POST", "creative/portfolio/get/",
            {"advertiser_id": "123", "creative_portfolio_id": "portfolio-1"},
            None,
        ),
        (
            "POST", "creative/ads_preview/create/",
            {"advertiser_id": "123", "preview_type": "CARD", "card_id": "portfolio-1"},
            None,
        ),
    ]
    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    get_tool = definitions["tiktok_get_creative_portfolio"]
    preview_tool = definitions["tiktok_preview_creative_portfolio"]
    assert get_tool.input_schema.required == ["account_id", "creative_portfolio_id"]
    assert preview_tool.input_schema.properties["preview_type"]["enum"] == ["CARD"]
    assert preview_tool.live_support is True
    assert validate_tool_input(
        get_tool.input_schema,
        {"account_id": "123", "creative_portfolio_id": "portfolio-1"},
        include_provider_contract=True,
    ) == []
    assert validate_tool_input(
        preview_tool.input_schema,
        {"account_id": "123", "creative_portfolio_id": "portfolio-1", "preview_type": "VIDEO"},
    )


def test_tiktok_targeting_reference_lookups_build_official_v13_queries():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []

    def request(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return {"list": [{"id": "1"}]}

    client.request = request
    assert client.list_interest_categories(
        "123", version=2, placements=["PLACEMENT_TIKTOK"],
        special_industries=["HOUSING"], language="zh",
    ) == [{"id": "1"}]
    assert client.list_action_categories("123", ["HOUSING"]) == [{"id": "1"}]
    assert client.list_languages("123") == [{"id": "1"}]
    assert client.list_device_models("123") == [{"id": "1"}]
    assert client.recommend_interest_keywords(
        "123", "running shoes", language="en", limit=10,
        mode="SEMANTIC_RECOMMEND", audience_type="PURCHASE_INTENTION",
    ) == [{"id": "1"}]
    assert calls == [
        ("GET", "tool/interest_category/", {"params": {
            "advertiser_id": "123", "version": 2, "language": "zh",
            "placements": ["PLACEMENT_TIKTOK"], "special_industries": ["HOUSING"],
        }}),
        ("GET", "tool/action_category/", {"params": {
            "advertiser_id": "123", "special_industries": ["HOUSING"],
        }}),
        ("GET", "tool/language/", {"params": {"advertiser_id": "123"}}),
        ("GET", "tool/device_model/", {"params": {"advertiser_id": "123"}}),
        ("GET", "tool/interest_keyword/recommend/", {"params": {
            "advertiser_id": "123", "keyword": "running shoes", "language": "en",
            "limit": 10, "mode": "SEMANTIC_RECOMMEND",
            "audience_type": "PURCHASE_INTENTION",
        }}),
    ]

    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert definitions["tiktok_list_languages"].effect_class.value == "read"
    assert definitions["tiktok_list_device_models"].input_schema.required == ["account_id"]
    assert definitions["tiktok_list_interest_categories"].input_schema.required == ["account_id"]
    assert definitions["tiktok_list_action_categories"].input_schema.required == ["account_id"]
    assert definitions["tiktok_recommend_interest_keywords"].input_schema.properties["mode"]["enum"] == [
        "FUZZ_MATCH", "SEMANTIC_RECOMMEND",
    ]


def test_tiktok_identity_tools_cover_create_lookup_and_spark_video_preflight():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []

    def request(method, endpoint, data=None, **kwargs):
        calls.append((method, endpoint, data, kwargs))
        if endpoint == "identity/get/":
            return {"list": [{"identity_id": "i1"}]}
        return {"identity_id": "i1", "video_id": "v1"}

    client.request = request
    assert client.create_identity("123", "Brand identity", "image-1")["identity_id"] == "i1"
    assert client.list_identities("123", "AUTH_CODE", page=2, page_size=10) == [
        {"identity_id": "i1"}
    ]
    assert client.get_identity_video_info("123", "AUTH_CODE", "i1", "v1")["video_id"] == "v1"
    assert calls == [
        ("POST", "identity/create/", {
            "advertiser_id": "123", "display_name": "Brand identity", "image_uri": "image-1",
        }, {}),
        ("GET", "identity/get/", None, {"params": {
            "advertiser_id": "123", "page": 2, "page_size": 10, "identity_type": "AUTH_CODE",
        }}),
        ("GET", "identity/video/info/", None, {"params": {
            "advertiser_id": "123", "identity_type": "AUTH_CODE",
            "identity_id": "i1", "item_id": "v1",
        }}),
    ]

    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert definitions["tiktok_create_identity"].live_support is False
    assert definitions["tiktok_create_identity"].input_schema.properties.keys() == {
        "account_id", "display_name", "image_uri",
    }
    assert "identity_authorized_bc_id" not in definitions["tiktok_list_identities"].input_schema.properties
    assert definitions["tiktok_get_identity_video_info"].input_schema.properties["identity_type"]["enum"] == [
        "AUTH_CODE", "TT_USER",
    ]


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


def test_google_conversion_action_queries_normalize_gaql_rows():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def search(query, **kwargs):
        calls.append((query, kwargs))
        return [{
            "conversionAction": {
                "id": "42", "resourceName": "customers/123/conversionActions/42",
                "name": "Purchase", "status": "ENABLED", "type": "WEBPAGE",
                "category": "PURCHASE", "origin": "WEBSITE",
                "ownerCustomer": "customers/123", "countingType": "MANY",
                "clickThroughLookbackWindowDays": "30",
                "valueSettings": {
                    "defaultValue": 10.0, "alwaysUseDefaultValue": True,
                },
            }
        }]

    client._search_all = search
    actions = client.list_conversion_actions(page_size=25)
    assert actions[0]["name"] == "Purchase"
    assert actions[0]["resource_name"].endswith("/42")
    assert actions[0]["value_settings"] == {
        "default_value": 10.0, "always_use_default_value": True,
    }
    assert calls[0][1] == {"page_size": 25}

    client._search = lambda query: {"results": [{
        "conversionAction": {"id": "42", "name": "Purchase"}
    }]}
    assert client.get_conversion_action("42")["id"] == "42"


def test_google_conversion_action_lifecycle_builds_customer_mutations():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def mutate(resource, operation):
        calls.append((resource, operation))
        return {"results": [{
            "resourceName": "customers/123/conversionActions/42"
        }]}

    client._mutate = mutate
    action_id = client.create_conversion_action({
        "name": "Purchase",
        "type": "WEBPAGE",
        "category": "PURCHASE",
        "counting_type": "MANY_PER_CLICK",
        "value_settings": {
            "default_value": 10,
            "default_currency_code": "USD",
            "always_use_default_value": True,
        },
    })
    assert action_id == "42"
    assert calls[0][0] == "conversionActions"
    assert calls[0][1]["create"]["countingType"] == "MANY_PER_CLICK"
    assert calls[0][1]["create"]["valueSettings"]["defaultCurrencyCode"] == "USD"

    assert client.update_conversion_action("42", {
        "name": "Completed purchase",
        "value_settings": {"default_value": 12.5},
    }) == {"success": True, "conversion_action_id": "42"}
    assert calls[1][1]["update"]["resourceName"].endswith("/42")
    assert calls[1][1]["updateMask"]["paths"] == [
        "name", "valueSettings.defaultValue"
    ]

    assert client.delete_conversion_action("42") == {
        "success": True, "conversion_action_id": "42"
    }
    assert calls[2] == (
        "conversionActions",
        {"remove": "customers/123/conversionActions/42"},
    )


def test_google_conversion_action_rejects_immutable_or_invalid_fields():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    with pytest.raises(ValueError, match="type must be one"):
        client.create_conversion_action({
            "name": "Invalid", "type": "NOT_A_TYPE", "category": "PURCHASE"
        })
    with pytest.raises(ValueError, match="Unsupported Google ConversionAction"):
        client.update_conversion_action("42", {"type": "WEBPAGE"})


def test_google_bidding_strategy_queries_normalize_gaql_rows():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def search(query, **kwargs):
        calls.append((query, kwargs))
        return [{
            "biddingStrategy": {
                "id": "7", "resourceName": "customers/123/biddingStrategies/7",
                "name": "Max conversions", "status": "ENABLED", "type": "MAXIMIZE_CONVERSIONS",
            }
        }]

    client._search_all = search
    strategies = client.list_bidding_strategies(page_size=10)
    assert strategies == [{
        "id": "7", "resource_name": "customers/123/biddingStrategies/7",
        "name": "Max conversions", "status": "ENABLED", "type": "MAXIMIZE_CONVERSIONS",
    }]
    assert calls[0][1] == {"page_size": 10}

    client._search = lambda query: {"results": [{
        "biddingStrategy": {"id": "7", "name": "Max conversions"}
    }]}
    assert client.get_bidding_strategy("7")["name"] == "Max conversions"


def test_google_experiment_read_surfaces_normalize_gaql_rows_and_queries():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def search_all(query, **kwargs):
        calls.append((query, kwargs))
        if "experiment_arm" in query:
            return [{
                "experimentArm": {
                    "id": "2",
                    "resourceName": "customers/123/experimentArms/2",
                    "name": "Treatment",
                    "experiment": "customers/123/experiments/1",
                    "control": False,
                    "trafficSplit": 50,
                }
            }]
        return [{
            "experiment": {
                "id": "1",
                "resourceName": "customers/123/experiments/1",
                "name": "Budget test",
                "description": "test",
                "status": "SETUP",
                "type": "SEARCH_CUSTOM",
                "startDate": "2026-09-01",
                "endDate": "2026-09-30",
                "suffix": " treatment",
                "baseCampaign": "customers/123/campaigns/9",
                "experimentCampaign": "customers/123/campaigns/10",
            }
        }]

    client._search_all = search_all
    assert client.list_experiments(page_size=10)[0] == {
        "id": "1",
        "resource_name": "customers/123/experiments/1",
        "name": "Budget test",
        "description": "test",
        "status": "SETUP",
        "type": "SEARCH_CUSTOM",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
        "suffix": " treatment",
        "base_campaign": "customers/123/campaigns/9",
        "experiment_campaign": "customers/123/campaigns/10",
    }
    assert client.list_experiment_arms(page_size=5)[0]["traffic_split"] == 50
    assert calls[0][1] == {"page_size": 10}
    assert calls[1][1] == {"page_size": 5}
    assert "FROM experiment" in calls[0][0]
    assert "FROM experiment_arm" in calls[1][0]


def test_google_bidding_strategy_lifecycle_builds_official_scheme_payloads():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []
    client._mutate = lambda resource, operation: (
        calls.append((resource, operation))
        or {"results": [{"resourceName": "customers/123/biddingStrategies/8"}]}
    )

    assert client.create_bidding_strategy({
        "name": "Portfolio tCPA",
        "strategy_type": "TARGET_CPA",
        "target_cpa_micros": 500000,
    }) == "8"
    assert calls[0] == ("biddingStrategies", {"create": {
        "name": "Portfolio tCPA",
        "targetCpa": {"targetCpaMicros": 500000},
    }})

    client.update_bidding_strategy("8", {
        "strategy_type": "TARGET_ROAS",
        "target_roas": 4.5,
        "cpc_bid_ceiling_micros": 2_000_000,
    })
    assert calls[1] == ("biddingStrategies", {
        "update": {
            "resourceName": "customers/123/biddingStrategies/8",
            "targetRoas": {
                "targetRoas": 4.5,
                "cpcBidCeilingMicros": 2_000_000,
            },
        },
        "updateMask": {"paths": [
            "targetRoas.targetRoas", "targetRoas.cpcBidCeilingMicros",
        ]},
    })

    client.delete_bidding_strategy("8")
    assert calls[2] == ("biddingStrategies", {
        "remove": "customers/123/biddingStrategies/8",
    })


def test_google_bidding_strategy_rejects_incomplete_strategy_specific_settings():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    with pytest.raises(ValueError, match="target_cpa_micros"):
        client.create_bidding_strategy({
            "name": "Missing target",
            "strategy_type": "TARGET_CPA",
        })
    with pytest.raises(ValueError, match="target_impression_share_location"):
        client.create_bidding_strategy({
            "name": "Missing location",
            "strategy_type": "TARGET_IMPRESSION_SHARE",
            "target_impression_share": 0.5,
            "cpc_bid_ceiling_micros": 1_000_000,
        })


def test_google_user_list_queries_normalize_gaql_rows():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    client._search_all = lambda query, **kwargs: [{
        "userList": {
            "id": "9", "resourceName": "customers/123/userLists/9",
            "name": "Purchasers", "description": "Recent purchasers",
            "type": "CRM_BASED", "membershipStatus": "OPEN",
            "membershipLifeSpan": "30", "sizeForDisplay": "1000",
            "sizeForSearch": "900",
        }
    }]
    user_lists = client.list_user_lists(page_size=12)
    assert user_lists == [{
        "id": "9", "resource_name": "customers/123/userLists/9",
        "name": "Purchasers", "description": "Recent purchasers",
        "type": "CRM_BASED", "membership_status": "OPEN",
        "membership_life_span": "30", "size_for_display": "1000",
        "size_for_search": "900",
    }]

    client._search = lambda query: {"results": [{
        "userList": {"id": "9", "name": "Purchasers"}
    }]}
    assert client.get_user_list("9")["name"] == "Purchasers"


def test_google_user_list_lifecycle_builds_customer_mutate_payloads():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []
    client._mutate = lambda resource, operation: (
        calls.append((resource, operation))
        or {"results": [{"resourceName": "customers/123/userLists/77"}]}
    )

    assert client.create_user_list({
        "name": "Purchasers",
        "description": "Recent purchasers",
        "membership_life_span": 30,
        "upload_key_type": "CONTACT_INFO",
    }) == "77"
    assert calls[0] == ("userLists", {"create": {
        "name": "Purchasers",
        "description": "Recent purchasers",
        "membershipLifeSpan": 30,
        "crmBasedUserList": {
            "uploadKeyType": "CONTACT_INFO",
            "dataSourceType": "FIRST_PARTY",
        },
    }})

    client.update_user_list("77", {
        "name": "Recent purchasers",
        "membership_life_span": 45,
        "eligible_for_search": True,
    })
    assert calls[1] == ("userLists", {
        "update": {
            "resourceName": "customers/123/userLists/77",
            "name": "Recent purchasers",
            "membershipLifeSpan": 45,
            "eligibleForSearch": True,
        },
        "updateMask": {"paths": [
            "name", "membershipLifeSpan", "eligibleForSearch",
        ]},
    })

    client.delete_user_list("77")
    assert calls[2] == ("userLists", {
        "remove": "customers/123/userLists/77",
    })


def test_google_user_list_upload_uses_hashed_file_and_three_step_offline_job(tmp_path):
    digest = "a" * 64
    source = tmp_path / "customers.csv"
    source.write_text(
        "hashed_email,hashed_phone_number\n"
        f"{digest},{'b' * 64}\n",
        encoding="utf-8",
    )
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []
    responses = iter([
        {"status_code": 200, "data": {
            "resourceName": "customers/123/offlineUserDataJobs/88",
        }},
        {"status_code": 200, "data": {}},
        {"status_code": 200, "data": {"name": "operations/abc"}},
    ])
    client.request_raw = lambda method, endpoint, data=None, **_kwargs: (
        calls.append((method, endpoint, data)) or next(responses)
    )

    result = client.upload_user_list_data("77", str(source))

    assert result == {
        "success": True,
        "job_id": "88",
        "job_resource_name": "customers/123/offlineUserDataJobs/88",
        "user_list_id": "77",
        "rows_uploaded": 1,
        "status": "RUNNING",
    }
    assert [call[1] for call in calls] == [
        "https://googleads.googleapis.com/v24/customers/123/offlineUserDataJobs:create",
        "customers/123/offlineUserDataJobs/88:addOperations",
        "customers/123/offlineUserDataJobs/88:run",
    ]
    assert calls[0][2]["job"]["customerMatchUserListMetadata"]["userList"] == (
        "customers/123/userLists/77"
    )
    assert calls[1][2] == {"operations": [{"create": {"userIdentifiers": [
        {"hashedEmail": digest}, {"hashedPhoneNumber": "b" * 64},
    ]}}]}
    assert digest not in str(result)


def test_google_user_list_upload_rejects_raw_or_unknown_columns(tmp_path):
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    raw = tmp_path / "raw.csv"
    raw.write_text("email\nuser@example.com\n", encoding="utf-8")
    with pytest.raises(ValueError, match="only be hashed_email"):
        client.upload_user_list_data("77", str(raw))

    malformed = tmp_path / "malformed.csv"
    malformed.write_text("hashed_email\nnot-a-sha256\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-SHA-256"):
        client.upload_user_list_data("77", str(malformed))


def test_google_user_list_tools_expose_lifecycle_and_closed_upload_contract():
    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    assert {
        "google_create_user_list", "google_update_user_list",
        "google_delete_user_list", "google_upload_user_list_data",
        "google_create_bidding_strategy", "google_update_bidding_strategy",
        "google_delete_bidding_strategy",
    } <= definitions.keys()
    create = definitions["google_create_user_list"]
    assert create.input_schema.properties["upload_key_type"]["enum"] == [
        "CONTACT_INFO", "CRM_ID", "MOBILE_ADVERTISING_ID",
    ]
    upload = definitions["google_upload_user_list_data"]
    assert upload.input_schema.additional_properties is False
    assert upload.live_support is False
    errors = validate_tool_input(
        upload.input_schema,
        {"customer_id": "123", "user_list_id": "77", "file_path": "/tmp/x.csv", "email": "x"},
        include_provider_contract=True,
    )
    assert any("not allowed" in error for error in errors)
    bidding = definitions["google_create_bidding_strategy"]
    assert bidding.input_schema.properties["strategy_type"]["enum"] == [
        "MANUAL_CPC", "MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE",
        "TARGET_CPA", "TARGET_ROAS", "TARGET_IMPRESSION_SHARE",
    ]
    bidding_errors = validate_tool_input(
        bidding.input_schema,
        {"customer_id": "123", "name": "tCPA", "strategy_type": "TARGET_CPA"},
        include_provider_contract=True,
    )
    assert any("target_cpa_micros" in error for error in bidding_errors)


def test_google_customer_client_queries_normalize_manager_rows():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []
    client._search_all = lambda query, **kwargs: (
        calls.append((query, kwargs)) or [{
            "customerClient": {
                "id": "456", "resourceName": "customers/456",
                "clientCustomer": "customers/456", "level": "1",
                "manager": False, "descriptiveName": "Child account",
                "currencyCode": "USD", "timeZone": "America/Los_Angeles",
                "status": "ENABLED",
            }
        }]
    )
    clients = client.list_customer_clients(page_size=25)
    assert clients == [{
        "id": "456", "resource_name": "customers/456",
        "client_customer": "customers/456", "level": "1", "manager": False,
        "descriptive_name": "Child account", "currency_code": "USD",
        "time_zone": "America/Los_Angeles", "status": "ENABLED",
    }]
    assert calls[0][1] == {"page_size": 25}
    assert "FROM customer_client" in calls[0][0]


def test_google_customer_client_tool_is_read_only():
    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    tool = definitions["google_list_customer_clients"]
    assert tool.resource_type == "customer_client"
    assert tool.is_write_tool is False
    assert tool.input_schema.required == ["customer_id"]


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
        "bid_amount": 5,
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


def test_meta_core_hierarchy_delete_methods_are_scoped_and_use_graph_delete():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: (
        calls.append(("ownership", account_id, resource_type, resource_id)) or True
    )
    client.acquire_rate_limit = lambda *_args, **_kwargs: None
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data)) or {}
    )

    assert client.delete_campaign("act_123", "campaign-1")["campaign_id"] == "campaign-1"
    assert client.delete_adset("123", "adset-1")["adset_id"] == "adset-1"
    assert client.delete_ad("123", "ad-1")["ad_id"] == "ad-1"

    assert calls == [
        ("ownership", "123", "campaign", "campaign-1"),
        ("DELETE", "/campaign-1", None),
        ("ownership", "123", "ad_set", "adset-1"),
        ("DELETE", "/adset-1", None),
        ("ownership", "123", "ad", "ad-1"),
        ("DELETE", "/ad-1", None),
    ]

    client.resource_belongs_to_account = lambda *_args: False
    with pytest.raises(PermissionError, match="does not belong"):
        client.delete_ad("123", "ad-1")
    with pytest.raises(ValueError, match="simple Meta object ID"):
        client.delete_campaign("123", "campaign/1")


def test_meta_core_hierarchy_delete_tools_are_dry_run_and_scoped():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    expected = {
        "meta_delete_campaign": ("campaign_id", "campaign"),
        "meta_delete_adset": ("adset_id", "ad_set"),
        "meta_delete_ad": ("ad_id", "ad"),
    }
    for name, (resource_id, resource_type) in expected.items():
        definition = definitions[name]
        assert definition.is_write_tool
        assert definition.live_support is False
        assert definition.action == "delete"
        assert definition.resource_type == resource_type
        assert definition.input_schema.required == ["account_id", resource_id]
        assert definition.input_schema.provider_required == ["account_id", resource_id]


def test_meta_pixel_get_checks_account_ownership_and_forwards_fields():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: (
        calls.append(("ownership", account_id, resource_type, resource_id)) or True
    )
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, kwargs.get("extra_params")))
        or {"id": "px-1", "name": "Web Pixel"}
    )

    pixel = client.get_pixel("act-123", "px-1", fields=["id", "name"])
    assert pixel == {"id": "px-1", "name": "Web Pixel"}
    assert calls == [
        ("ownership", "act-123", "pixel", "px-1"),
        ("GET", "/px-1", {"fields": "id,name"}),
    ]


def test_meta_custom_conversion_create_validates_pixel_scope_and_builds_payload():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: (
        calls.append(("ownership", account_id, resource_type, resource_id)) or True
    )
    client.acquire_rate_limit = lambda *_args, **_kwargs: None
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data, kwargs.get("extra_params")))
        or {"id": "cc-1", "is_custom_event_type_predicted": "0"}
    )

    conversion_id = client.create_custom_conversion("act_123", {
        "pixel_id": "px-1",
        "name": "Paid Purchase",
        "rule": "event.source_url contains 'checkout'",
        "custom_event_type": "PURCHASE",
        "action_source_type": "website",
        "default_conversion_value": 19.9,
    })
    assert conversion_id == "cc-1"
    assert calls == [
        ("ownership", "123", "pixel", "px-1"),
        ("POST", "/act_123/customconversions",
        {
            "event_source_id": "px-1",
            "name": "Paid Purchase",
            "rule": "event.source_url contains 'checkout'",
            "custom_event_type": "PURCHASE",
            "action_source_type": "website",
            "default_conversion_value": 19.9,
        },
        None,
        ),
    ]

    with pytest.raises(ValueError, match="unsupported"):
        client.create_custom_conversion("act_123", {
            "pixel_id": "px-1", "name": "bad", "rule": "x", "access_token": "bad",
        })
    with pytest.raises(PermissionError):
        client.resource_belongs_to_account = lambda *_args: False
        client.create_custom_conversion("act_123", {
            "pixel_id": "px-1", "name": "bad", "rule": "x",
        })


def test_meta_custom_conversion_lifecycle_builds_scoped_graph_requests():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.acquire_rate_limit = lambda *_args, **_kwargs: None
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: (
        calls.append(("ownership", account_id, resource_type, resource_id)) or True
    )

    def request(method, endpoint, data=None, **kwargs):
        calls.append((method, endpoint, data, kwargs.get("extra_params")))
        if method == "GET" and endpoint.startswith("/act_"):
            return {"data": [{"id": "cc-1", "name": "Paid Purchase"}]}
        return {"id": "cc-1", "success": True}

    client.request = request

    assert client.list_custom_conversions("act_123", fields=["id", "name"], limit=10) == [
        {"id": "cc-1", "name": "Paid Purchase"}
    ]
    assert client.get_custom_conversion("act_123", "cc-1", fields=["id"]) == {
        "id": "cc-1", "success": True
    }
    assert client.update_custom_conversion("act_123", "cc-1", {
        "name": "Paid Purchase v2", "default_conversion_value": 19.9,
    }) == {
        "success": True, "custom_conversion_id": "cc-1",
        "result": {"id": "cc-1", "success": True},
    }
    assert client.delete_custom_conversion("act_123", "cc-1") == {
        "success": True, "custom_conversion_id": "cc-1",
    }

    assert calls == [
        ("GET", "/act_123/customconversions", None, {
            "limit": 10, "fields": "id,name",
        }),
        ("ownership", "123", "custom_conversion", "cc-1"),
        ("GET", "/cc-1", None, {"fields": "id"}),
        ("ownership", "123", "custom_conversion", "cc-1"),
        ("POST", "/cc-1", {
            "name": "Paid Purchase v2", "default_conversion_value": 19.9,
        }, None),
        ("ownership", "123", "custom_conversion", "cc-1"),
        ("DELETE", "/cc-1", None, None),
    ]

    with pytest.raises(ValueError, match="Unsupported Meta Custom Conversion"):
        client.update_custom_conversion("123", "cc-1", {"rule": "not mutable"})


def test_meta_custom_conversion_management_tools_publish_closed_lifecycle_contracts():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    assert {
        "meta_list_custom_conversions", "meta_get_custom_conversion",
        "meta_update_custom_conversion", "meta_delete_custom_conversion",
    } <= definitions.keys()
    assert definitions["meta_list_custom_conversions"].input_schema.required == [
        "account_id"
    ]
    assert definitions["meta_update_custom_conversion"].input_schema.required == [
        "account_id", "custom_conversion_id", "updates"
    ]
    assert definitions["meta_update_custom_conversion"].input_schema.properties[
        "updates"
    ]["additionalProperties"] is False
    assert definitions["meta_update_custom_conversion"].live_support is False
    assert validate_tool_input(
        definitions["meta_update_custom_conversion"].input_schema,
        {
            "account_id": "act_1", "custom_conversion_id": "cc_1",
            "updates": {"name": "Renamed"},
        },
    ) == []


def test_meta_capi_events_validate_pixel_ownership_and_build_provider_envelope():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: (
        calls.append(("ownership", account_id, resource_type, resource_id)) or True
    )
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data))
        or {"events_received": 1, "fbtrace_id": "trace-1"}
    )
    result = client.send_conversion_events("act_123", "px-1", [{
        "event_name": "Purchase", "event_time": 1720000000,
        "action_source": "website", "user_data": {"em": ["a" * 64]},
        "custom_data": {"value": 12.5, "currency": "USD"},
        "event_id": "order-1",
    }], test_event_code="TEST123")
    assert result["events_received"] == 1
    assert calls[0] == ("ownership", "123", "pixel", "px-1")
    assert calls[1][0:2] == ("POST", "/px-1/events")
    assert calls[1][2] == {
        "data": [{
            "event_name": "Purchase", "event_time": 1720000000,
            "action_source": "website", "user_data": {"em": ["a" * 64]},
            "custom_data": {"value": 12.5, "currency": "USD"},
            "event_id": "order-1",
        }],
        "test_event_code": "TEST123",
    }

    with pytest.raises(ValueError, match="missing required fields"):
        client.send_conversion_events("123", "px-1", [{
            "event_name": "Purchase", "event_time": 1720000000,
            "action_source": "website",
        }])


def test_meta_capi_tool_exposes_pixel_lookup_and_is_dry_run_only():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    tool = definitions["meta_send_conversion_events"]
    assert tool.input_schema.properties["pixel_id"]["lookup_tool"] == "meta_list_pixels"
    assert tool.input_schema.properties["events"]["items"]["required"] == [
        "event_name", "event_time", "action_source", "user_data"
    ]
    assert tool.live_support is False


def test_meta_custom_conversion_tool_exposes_pixel_lookup_and_dry_run():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    tool = definitions["meta_create_custom_conversion"]
    assert tool.live_support is False
    assert tool.input_schema.properties["pixel_id"]["lookup_tool"] == "meta_list_pixels"
    assert validate_tool_input(
        tool.input_schema,
        {
            "account_id": "act_1",
            "pixel_id": "px_1",
            "name": "Paid Purchase",
            "rule": "event_name == 'Purchase'",
        },
    ) == []


def test_meta_test_capi_tool_requires_test_code_and_uses_test_endpoint_contract():
    calls = []

    class Client:
        def send_conversion_events(self, account_id, pixel_id, events, test_event_code=None):
            calls.append((account_id, pixel_id, events, test_event_code))
            return {"events_received": 1}

    definitions = {
        definition.name: (definition, handler)
        for definition, handler in create_meta_capability(Client()).register_tools()
    }
    tool, handler = definitions["meta_test_conversion_events"]
    event = {
        "event_name": "Purchase",
        "event_time": 1720000000,
        "action_source": "website",
        "user_data": {"em": ["a" * 64]},
    }

    assert tool.action == "test"
    assert tool.resource_type == "pixel_event"
    assert tool.live_support is False
    assert "test_event_code" in tool.input_schema.required
    assert validate_tool_input(
        tool.input_schema,
        {"account_id": "act_1", "pixel_id": "px_1", "events": [event]},
    )
    result = handler.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="act_1"),
        {
            "account_id": "act_1", "pixel_id": "px_1", "events": [event],
            "test_event_code": "TEST123",
        },
    )

    assert result.success is True
    assert calls == [("act_1", "px_1", [event], "TEST123")]


def test_meta_resource_ownership_accepts_graph_ids_and_ad_set_alias():
    client = MetaAPIClient({"access_token": "test"})
    client.list_pixels = lambda account_id, limit=25: [{"id": "px-1"}]
    assert client.resource_belongs_to_account("123", "pixel", "px-1") is True

    client.list_adsets = lambda account_id, campaign_id=None, limit=25: [{"id": "as-1"}]
    assert client.resource_belongs_to_account("123", "ad_set", "as-1") is True


def test_meta_lead_form_get_checks_page_ownership_and_forwards_fields():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.list_lead_forms = lambda page_id, limit=25: [{"id": "form-1"}]
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, kwargs.get("extra_params")))
        or {"id": "form-1", "status": "ACTIVE"}
    )

    form = client.get_lead_form("page-1", "form-1", fields=["id", "status"])
    assert form == {"id": "form-1", "status": "ACTIVE"}
    assert calls == [("GET", "/form-1", {"fields": "id,status"})]


def test_meta_lead_form_create_serializes_structured_graph_fields():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.acquire_rate_limit = lambda *_args, **_kwargs: None
    client.request = lambda method, endpoint, data=None, **_kwargs: (
        calls.append((method, endpoint, data)) or {"id": "form-new"}
    )
    form_id = client.create_lead_form("page-1", {
        "name": "Demo lead form",
        "questions": [
            {"type": "FULL_NAME"},
            {"type": "CUSTOM", "key": "company", "label": "Company"},
        ],
        "privacy_policy": {
            "url": "https://example.test/privacy",
            "link_text": "Privacy Policy",
        },
        "context_card": {"title": "Tell us about you"},
        "locale": "en_US",
    })
    assert form_id == "form-new"
    assert calls[0][:2] == ("POST", "/page-1/leadgen_forms")
    assert calls[0][2]["name"] == "Demo lead form"
    assert json.loads(calls[0][2]["questions"])[1]["key"] == "company"
    assert json.loads(calls[0][2]["privacy_policy"])["link_text"] == "Privacy Policy"
    assert json.loads(calls[0][2]["context_card"])["title"] == "Tell us about you"


def test_meta_lead_form_update_verifies_page_ownership_before_mutation():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.get_lead_form = lambda page_id, form_id, fields=None: {
        "id": form_id, "page": {"id": page_id}
    }
    client.acquire_rate_limit = lambda *_args, **_kwargs: None
    client.request = lambda method, endpoint, data=None, **_kwargs: (
        calls.append((method, endpoint, data)) or {"id": "form-1", "name": data["name"]}
    )
    result = client.update_lead_form("page-1", "form-1", {"name": "Renamed form"})
    assert result == {"id": "form-1", "name": "Renamed form"}
    assert calls == [("POST", "/form-1", {"name": "Renamed form"})]


def test_meta_lead_form_tools_expose_closed_create_and_update_contracts():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    create_tool = definitions["meta_create_lead_form"]
    update_tool = definitions["meta_update_lead_form"]
    assert create_tool.live_support is False
    assert create_tool.input_schema.properties["page_id"]["lookup_tool"] == "meta_list_pages"
    assert create_tool.input_schema.properties["questions"]["items"]["additionalProperties"] is False
    assert update_tool.input_schema.properties["updates"]["additionalProperties"] is False
    assert update_tool.input_schema.required == ["account_id", "page_id", "form_id", "updates"]


def test_google_asset_reads_are_customer_scoped_and_normalized():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "111"})
    captured = []

    def fake_search_all(query, page_size=100):
        captured.append((query, page_size, client.customer_id))
        return [{
            "asset": {
                "id": "7",
                "resourceName": "customers/222/assets/7",
                "name": "Headline asset",
                "type": "TEXT",
                "textAsset": {"text": "Sale today"},
                "finalUrls": ["https://example.test"],
            }
        }]

    client._search_all = fake_search_all
    assets = client.list_assets("222", page_size=25)
    assert assets == [{
        "id": "7",
        "resource_name": "customers/222/assets/7",
        "name": "Headline asset",
        "type": "TEXT",
        "text": "Sale today",
        "image_url": None,
        "youtube_video_id": None,
        "final_urls": ["https://example.test"],
        "final_mobile_urls": [],
    }]
    assert captured[0][1:] == (25, "111")
    assert client.customer_id == "111"


def test_google_get_asset_uses_numeric_id_and_customer_scope():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "111"})
    captured = []
    client._search = lambda query: (
        captured.append((query, client.customer_id))
        or {"data": {"results": [{"asset": {"id": "7", "type": "IMAGE"}}]}}
    )
    asset = client.get_asset("7", "222")
    assert asset["id"] == "7"
    assert asset["type"] == "IMAGE"
    assert "WHERE asset.id = 7" in captured[0][0]
    assert captured[0][1] == "111"


def test_google_asset_creation_builds_text_and_binary_asset_payloads(tmp_path):
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []
    client._mutate = lambda resource, operation: (
        calls.append((resource, operation))
        or {"results": [{"resourceName": "customers/123/assets/9"}]}
    )

    assert client.create_asset({
        "asset_type": "TEXT", "name": "Headline", "text": "Sale today",
        "final_urls": ["https://example.test"],
    }) == "9"
    assert calls[0] == ("assets", {"create": {
        "name": "Headline",
        "finalUrls": ["https://example.test"],
        "textAsset": {"text": "Sale today"},
    }})

    image = tmp_path / "creative.png"
    image.write_bytes(b"png-bytes")
    assert client.create_asset({
        "asset_type": "IMAGE", "file_path": str(image), "mime_type": "IMAGE_PNG",
    }) == "9"
    image_payload = calls[1][1]["create"]["imageAsset"]
    assert image_payload == {
        "data": "cG5nLWJ5dGVz", "fileSize": 9, "mimeType": "IMAGE_PNG",
    }


def test_google_asset_creation_rejects_wrong_payload_variants_and_exposes_tool():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    with pytest.raises(ValueError, match="text is required"):
        client.create_asset({"asset_type": "TEXT"})
    with pytest.raises(ValueError, match="11-character"):
        client.create_asset({
            "asset_type": "YOUTUBE_VIDEO", "youtube_video_id": "bad",
            "youtube_video_title": "Video",
        })

    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    create_tool = definitions["google_create_asset"]
    assert create_tool.live_support is False
    assert create_tool.input_schema.properties["asset_type"]["enum"] == [
        "TEXT", "IMAGE", "YOUTUBE_VIDEO", "MEDIA_BUNDLE",
    ]


def test_google_asset_delete_uses_customer_scoped_asset_remove():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="111")
    calls = []
    client._mutate = lambda resource, operation: calls.append((resource, operation)) or {}

    assert client.delete_asset("7", "222") == {"success": True, "asset_id": "7"}
    assert calls == [("assets", {
        "remove": "customers/222/assets/7",
    })]

    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    delete_tool = definitions["google_delete_asset"]
    assert delete_tool.live_support is False
    assert delete_tool.input_schema.required == ["customer_id", "asset_id"]


def test_google_asset_tools_publish_read_contracts():
    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    assert definitions["google_list_assets"].input_schema.required == ["customer_id"]
    assert definitions["google_get_asset"].input_schema.required == ["customer_id", "asset_id"]


def test_google_pmax_asset_group_builds_bounded_multistep_dry_run_plan():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    plan = client.create_pmax_asset_group(
        "42", "Summer PMax", [
            {"text": "Headline one"}, {"text": "Headline two"},
            {"text": "Headline three"},
        ],
        descriptions=[{"text": "Description one"}, {"text": "Description two"}],
        long_headlines=[{"text": "A longer headline"}],
        images=[{"asset_id": "88"}],
        videos=[{"resource_name": "customers/123/assets/99"}],
        final_urls=["https://example.test/landing"],
    )

    assert plan["mode"] == "dry_run"
    assert plan["execution_status"] == "planned"
    assert plan["live_support"] is False
    assert plan["requires_verified_live_adapter"] is True
    assert plan["asset_group_resource_name"] == "customers/123/assetGroups/-1"
    group = plan["operations"][0]["operation"]["create"]
    assert group == {
        "resourceName": "customers/123/assetGroups/-1",
        "campaign": "customers/123/campaigns/42",
        "name": "Summer PMax",
        "assetGroupType": "PERFORMANCE_MAX",
        "status": "PAUSED",
        "finalUrls": ["https://example.test/landing"],
    }
    assert any(
        operation["resource"] == "assets"
        and operation["operation"]["create"]["textAsset"] == {"text": "Headline one"}
        for operation in plan["operations"]
    )
    links = [
        operation["operation"]["create"]
        for operation in plan["operations"]
        if operation["resource"] == "assetGroupAssets"
    ]
    assert {link["fieldType"] for link in links} == {
        "HEADLINE", "LONG_HEADLINE", "DESCRIPTION", "MARKETING_IMAGE", "YOUTUBE_VIDEO",
    }
    assert {link["asset"] for link in links if link["fieldType"] == "MARKETING_IMAGE"} == {
        "customers/123/assets/88"
    }

    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    for name in ("google_create_pmax_asset_group", "google_create_asset_group"):
        assert definitions[name].live_support is False
        assert definitions[name].input_schema.required == [
            "campaign_id", "name", "asset_group_type", "final_urls",
            "headlines", "long_headlines", "descriptions",
        ]


def test_google_app_ad_builds_dry_run_asset_payload_without_provider_io():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    plan = client.create_app_ad(
        "42", "App install ad",
        headlines=[{"text": "Install the app"}, {"text": "Shop anywhere"}],
        descriptions=[{"text": "Fast mobile shopping"}, {"text": "Download today"}],
        images=[{"resource_name": "customers/123/assets/88"}],
        videos=[{"asset_id": "99"}],
    )

    assert plan["mode"] == "dry_run"
    assert plan["execution_status"] == "planned"
    assert plan["live_support"] is False
    create = plan["operation"]["adGroupAds"]["create"]
    assert create["resourceName"] == "customers/123/ads/-1"
    assert create["adGroup"] == "customers/123/adGroups/42"
    assert create["status"] == "PAUSED"
    assert create["ad"]["appAd"]["headlines"] == [
        {"text": "Install the app"}, {"text": "Shop anywhere"}
    ]
    assert create["ad"]["appAd"]["images"] == [
        {"resourceName": "customers/123/assets/88"}
    ]
    assert create["ad"]["appAd"]["youtubeVideos"] == [
        {"assetId": "99"}
    ]

    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    app_group = definitions["google_create_app_ad_group"]
    app_ad = definitions["google_create_app_ad"]
    assert app_group.live_support is False
    assert app_group.input_schema.properties["type"]["default"] == "SEARCH_STANDARD"
    assert app_ad.live_support is False
    assert app_ad.input_schema.required == [
        "ad_group_id", "name", "headlines", "descriptions"
    ]


def test_meta_audience_crud_builds_custom_and_lookalike_payloads():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data)) or {"id": "aud-1"}
    )
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: True

    assert client.create_audience("act-123", {
        "name": "Purchasers 30D", "subtype": "CUSTOM",
        "rule": {"event": {"eq": "purchase"}}, "retention_days": 30,
        "customer_file_source": "USER_PROVIDED_ONLY",
    }) == "aud-1"
    custom = calls[-1]
    assert custom[:2] == ("POST", "/act_act-123/customaudiences")
    assert json.loads(custom[2]["rule"]) == {"event": {"eq": "purchase"}}
    assert custom[2]["retention_days"] == 30

    assert client.create_audience("123", {
        "name": "US Lookalike", "subtype": "LOOKALIKE",
        "origin_audience_id": "aud-1", "country": "us", "ratio": 0.05,
    }) == "aud-1"
    lookalike = calls[-1][2]
    assert lookalike["origin_audience_id"] == "aud-1"
    assert json.loads(lookalike["lookalike_spec"]) == {
        "country": "US", "ratio": 0.05, "type": "similarity",
    }
    assert client.update_audience("123", "aud-1", {
        "name": "Updated", "rule": {"event": "lead"},
    })["success"] is True
    assert json.loads(calls[-1][2]["rule"]) == {"event": "lead"}
    assert client.delete_audience("123", "aud-1")["success"] is True
    assert calls[-1][:2] == ("DELETE", "/aud-1")


def test_meta_lookalike_tool_exposes_source_lookup_and_fixed_subtype():
    calls = []

    class Client:
        def create_audience(self, account_id, audience):
            calls.append((account_id, audience))
            return "lal-1"

    definitions = {
        definition.name: (definition, handler)
        for definition, handler in create_meta_capability(Client()).register_tools()
    }
    tool, handler = definitions["meta_create_lookalike_audience"]

    assert tool.resource_type == "lookalike_audience"
    assert tool.input_schema.required == [
        "account_id", "name", "origin_audience_id", "country"
    ]
    source = tool.input_schema.properties["origin_audience_id"]
    assert source["lookup_tool"] == "meta_list_audiences"
    assert source["lookup_result_key"] == "audiences"
    assert validate_tool_input(
        tool.input_schema,
        {
            "account_id": "act_1",
            "name": "US Purchasers",
            "origin_audience_id": "aud-1",
            "country": "US",
        },
    ) == []

    result = handler.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="act_1"),
        {
            "account_id": "act_1",
            "name": "US Purchasers",
            "origin_audience_id": "aud-1",
            "country": "US",
            "ratio": 0.05,
        },
    )

    assert result.success is True
    assert calls == [("act_1", {
        "name": "US Purchasers",
        "subtype": "LOOKALIKE",
        "origin_audience_id": "aud-1",
        "country": "US",
        "ratio": 0.05,
    })]


def test_meta_audience_source_upload_accepts_only_sha256_rows():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: True
    client.acquire_rate_limit = lambda *_args, **_kwargs: None
    client.request = lambda method, endpoint, data=None, **_kwargs: (
        calls.append((method, endpoint, data)) or {"audience_id": "aud-1", "num_received": 2}
    )
    result = client.upload_audience_users(
        "act-123", "aud-1", ["EMAIL", "PHONE"],
        [["A" * 64, "b" * 64], ["c" * 64, "D" * 64]],
    )
    assert result["num_received"] == 2
    assert calls == [("POST", "/aud-1/users", {
        "payload": json.dumps({
            "schema": ["EMAIL", "PHONE"],
            "data": [["a" * 64, "b" * 64], ["c" * 64, "d" * 64]],
        }, separators=(",", ":")),
    })]

    with pytest.raises(ValueError, match="SHA-256"):
        client.upload_audience_users(
            "123", "aud-1", ["EMAIL"], [["raw-email@example.test"]]
        )


def test_meta_audience_upload_tool_is_dry_run_and_closed():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    tool = definitions["meta_upload_audience_users"]
    assert tool.live_support is False
    assert tool.input_schema.properties["upload_schema"]["items"]["enum"]
    assert tool.input_schema.properties["upload_data"]["items"]["items"]["maxLength"] == 64


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
        "placement_type": "PLACEMENT_TYPE_NORMAL",
        "placements": ["PLACEMENT_TIKTOK"],
        "promotion_website_type": "TIKTOK_NATIVE_PAGE",
        "optimization_event": "LEAD_GENERATION",
        "pixel_id": "pixel-1",
    })
    assert payloads[-1]["ad_group"]["conversion_id"] == 42
    assert payloads[-1]["ad_group"]["placements"] == ["PLACEMENT_TIKTOK"]
    assert payloads[-1]["ad_group"]["promotion_website_type"] == "TIKTOK_NATIVE_PAGE"
    assert payloads[-1]["ad_group"]["optimization_event"] == "LEAD_GENERATION"
    assert payloads[-1]["ad_group"]["pixel_id"] == "pixel-1"


def test_tiktok_catalog_adgroup_contract_requires_and_forwards_product_selection():
    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    schema = definitions["tiktok_create_adgroup"].input_schema
    assert "CATALOG" in schema.properties["promotion_type"]["enum"]
    assert schema.properties["catalog_id"]["lookup_tool"] == "tiktok_list_catalogs"
    assert schema.properties["product_set_id"]["lookup_tool"] == "tiktok_list_product_sets"

    base = {
        "campaign_id": "101", "name": "Catalog group",
        "promotion_type": "CATALOG", "billing_event": "OCPM",
        "bid_type": "BID_TYPE_NO_BID", "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
        "budget_mode": "BUDGET_MODE_DAY", "budget": 50, "location_ids": ["US"],
    }
    errors = validate_tool_input(schema, base, include_provider_contract=True)
    assert any("catalog_id" in error and "product_set_id" in error for error in errors)

    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"ad_group_id": "ag-1"}
    )
    result = client.create_adgroup("t1", "101", {
        **base, "catalog_id": "catalog-1", "product_set_id": "set-1",
    })
    assert result == "ag-1"
    assert payloads[-1]["ad_group"]["catalog_id"] == "catalog-1"
    assert payloads[-1]["ad_group"]["product_set_id"] == "set-1"
    with pytest.raises(ValueError, match="CATALOG promotion requires catalog_id"):
        client.create_adgroup("t1", "101", {**base, "product_set_id": "set-1"})


def test_tiktok_product_sales_tools_cover_catalog_and_shop_destinations():
    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    adgroup = definitions["tiktok_create_product_sales_adgroup"]
    ad = definitions["tiktok_create_product_sales_ad"]

    assert adgroup.input_schema.properties["product_source"]["enum"] == [
        "CATALOG", "STORE", "SHOWCASE",
    ]
    assert "product_sales_catalog_source_requires_product_selection" in {
        rule["id"] for rule in adgroup.input_schema.conditional_rules
    }
    assert ad.input_schema.provider_any_of == [[
        "media", "creatives", "video_id", "image_ids",
        "sku_ids", "item_group_ids", "product_set_id",
    ]]

    base = {
        "campaign_id": "101", "name": "Shop sales group",
        "promotion_type": "CATALOG", "product_source": "STORE",
        "catalog_id": "catalog-1", "product_set_id": "set-1",
        "billing_event": "OCPM", "bid_type": "BID_TYPE_NO_BID",
        "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
        "budget_mode": "BUDGET_MODE_DAY", "budget": 50,
        "location_ids": ["US"],
    }
    errors = validate_tool_input(
        adgroup.input_schema, base, include_provider_contract=True,
    )
    assert any("store_id" in error for error in errors)
    base["store_id"] = "shop-1"
    assert validate_tool_input(
        adgroup.input_schema, base, include_provider_contract=True,
    ) == []

    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"ad_group_id": "ag-1"}
    )
    assert client.create_product_sales_adgroup("t1", "101", base) == "ag-1"
    assert payloads[-1][1] == "adgroup/create/"
    assert payloads[-1][2]["ad_group"]["product_source"] == "STORE"
    assert payloads[-1][2]["ad_group"]["store_id"] == "shop-1"

    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"ad_id": "ad-1"}
    )
    assert client.create_product_sales_ad("t1", "101", "202", {
        "name": "Shop video", "product_source": "STORE", "store_id": "shop-1",
        "ad_format": "SINGLE_VIDEO", "video_id": "video-1",
    }) == "ad-1"
    assert payloads[-1][1] == "ad/create/"
    assert payloads[-1][2]["ad"]["video_id"] == "video-1"


def test_tiktok_product_selection_validation_uses_product_set_lookup():
    client = TikTokAPIClient({"access_token": "test"})
    client.list_product_sets = lambda advertiser_id, catalog_id=None: [
        {"product_set_id": "set-1", "name": "Approved products"},
    ]

    valid = client.validate_product_selection("123", "catalog-1", "set-1")
    invalid = client.validate_product_selection("123", "catalog-1", "set-2")
    assert valid["valid"] is True
    assert invalid["valid"] is False
    assert valid["checked_via"] == "product_set/get"


def test_tiktok_adgroup_contract_exposes_optimization_targeting_and_schedule_fields():
    definition = next(
        definition for definition, _handler in create_tiktok_capability().register_tools()
        if definition.name == "tiktok_create_adgroup"
    )
    schema = definition.input_schema
    assert "VALUE" in schema.properties["optimization_goal"]["enum"]
    assert schema.properties["interest_category_ids"]["lookup_tool"] == (
        "tiktok_list_interest_categories"
    )
    assert schema.properties["device_model_ids"]["lookup_tool"] == (
        "tiktok_list_device_models"
    )
    assert any(
        rule["id"] == "ocpm_custom_bid_requires_conversion_bid_price"
        for rule in schema.conditional_rules
    )

    base = {
        "campaign_id": "101", "name": "Conversion group",
        "promotion_type": "WEBSITE", "billing_event": "OCPM",
        "bid_type": "BID_TYPE_CUSTOM", "bid_amount": 5,
        "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
        "budget_mode": "BUDGET_MODE_DAY", "budget": 50,
        "location_ids": ["US"], "landing_url": "https://example.test",
    }
    errors = validate_tool_input(schema, base, include_provider_contract=True)
    assert any("conversion_bid_price" in error for error in errors)
    base["conversion_bid_price"] = 4
    assert validate_tool_input(schema, base, include_provider_contract=True) == []


def test_tiktok_ad_contract_exposes_lookup_backed_assets_and_provider_creative_fields():
    definition = next(
        definition for definition, _handler in create_tiktok_capability().register_tools()
        if definition.name == "tiktok_create_ad"
    )
    schema = definition.input_schema
    assert schema.properties["video_id"]["lookup_tool"] == "tiktok_list_videos"
    assert schema.properties["image_ids"]["lookup_tool"] == "tiktok_list_images"
    assert schema.properties["catalog_id"]["lookup_tool"] == "tiktok_list_catalogs"
    assert schema.properties["identity_id"]["lookup_tool"] == "tiktok_list_identities"
    assert "SINGLE_VIDEO" in schema.properties["creative_type"]["enum"]
    assert "tiktok_item_id" in schema.properties

    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"ad_id": "ad-1"}
    )
    client.create_ad("t1", "101", "202", {
        "name": "Video creative", "video_id": "video-1",
        "creative_type": "SINGLE_VIDEO", "ad_text": "Try it",
        "call_to_action_id": "cta-1", "identity_id": "identity-1",
        "deeplink": "myapp://home", "operation_status": "ENABLE",
    })
    ad = payloads[-1]["ad"]
    assert ad["creative_type"] == "SINGLE_VIDEO"
    assert ad["ad_text"] == "Try it"
    assert ad["call_to_action_id"] == "cta-1"
    assert ad["deeplink"] == "myapp://home"


def test_tiktok_typed_ad_tools_validate_assets_and_fix_format_payloads():
    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"ad_id": "ad-1"}
    )

    client.create_single_video_ad("t1", "101", "202", {"name": "Video", "video_id": "v1"})
    client.create_single_image_ad("t1", "101", "202", {"name": "Image", "image_ids": ["i1"]})
    client.create_carousel_ad(
        "t1", "101", "202", {"name": "Carousel", "image_ids": ["i1", "i2"]}
    )
    assert [payload[2]["ad"]["ad_format"] for payload in payloads] == [
        "SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL",
    ]
    with pytest.raises(ValueError, match="at least 2"):
        client.create_carousel_ad("t1", "101", "202", {"name": "Carousel", "image_ids": ["i1"]})
    with pytest.raises(ValueError, match="requires one of"):
        client.create_single_video_ad("t1", "101", "202", {"name": "Video"})

    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    assert definitions["tiktok_create_single_video_ad"].input_schema.properties["ad_format"]["enum"] == [
        "SINGLE_VIDEO",
    ]
    assert definitions["tiktok_create_carousel_ad"].input_schema.properties["image_ids"]["minItems"] == 2
    assert definitions["tiktok_create_single_image_ad"].live_support is False


def test_tiktok_targeting_update_validates_dimensions_and_builds_scoped_payload():
    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"code": 0, "data": {}}
    )

    result = client.update_adgroup_targeting("t1", "101", "202", {
        "location_ids": ["US"],
        "operating_systems": ["ANDROID"],
        "age_groups": ["AGE_18_24"],
        "gender": "GENDER_UNLIMITED",
        "interest_category_ids": ["cat-1"],
    })
    assert result["code"] == 0
    assert payloads[-1] == (
        "POST", "adgroup/update/", {
            "advertiser_id": "t1", "campaign_id": 101, "ad_group_id": 202,
            "ad_group": {
                "location_ids": ["US"],
                "operating_systems": ["ANDROID"],
                "age_groups": ["AGE_18_24"],
                "gender": "GENDER_UNLIMITED",
                "interest_category_ids": ["cat-1"],
            },
        },
    )
    with pytest.raises(ValueError, match="Unsupported TikTok targeting fields"):
        client.update_adgroup_targeting("t1", "101", "202", {"unknown": ["x"]})
    with pytest.raises(ValueError, match="operating_systems"):
        client.update_adgroup_targeting("t1", "101", "202", {
            "operating_systems": ["WINDOWS"],
        })


def test_tiktok_audience_delete_tool_calls_provider_method():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data)) or {"code": 0, "data": {}}
    )

    definitions = {
        definition.name: (definition, handler)
        for definition, handler in create_tiktok_capability(client).register_tools()
    }
    definition, handler = definitions["tiktok_delete_audience"]
    result = handler.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="123"),
        {"account_id": "123", "audience_id": "456"},
    )

    assert result.success is True
    assert definition.action == "delete"
    assert definition.resource_type == "audience"
    assert calls[-1] == (
        "POST", "dmp/custom_audience/delete/",
        {"advertiser_id": "123", "custom_audience_ids": ["456"]},
    )


def test_tiktok_lead_ad_builds_instant_page_payload():
    client = TikTokAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"ad_id": "lead-ad-1"}
    )

    assert client.create_lead_ad("t1", "101", "202", {
        "name": "Lead ad", "page_id": "9001",
        "media": [{"video_id": "video-1"}],
        "text": {"primary_text": "Get the guide"},
        "tracking_url": "https://example.test/track",
    }) == "lead-ad-1"
    method, endpoint, data = payloads[-1]
    assert (method, endpoint) == ("POST", "ad/create/")
    ad = data["ad"]
    assert ad["page_id"] == 9001
    assert "form_id" not in ad
    assert "promote_object" not in ad
    assert ad["media"] == [{"video_id": "video-1"}]
    assert ad["tracking_url"] == "https://example.test/track"

    with pytest.raises(ValueError, match="page_id is required"):
        client.create_lead_ad("t1", "101", "202", {"name": "Missing"})


def test_tiktok_audience_creation_builds_provider_envelope():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data)) or {"audience_id": "aud-1"}
    )

    assert client.create_audience("123", {
        "name": "Purchasers 30D",
        "calculate_type": "EMAIL_SHA256",
        "file_paths": ["abcdefghijklmnop"],
        "retention_in_days": 30,
    }) == "aud-1"
    assert calls == [(
        "POST", "dmp/custom_audience/create/", {
            "advertiser_id": "123",
            "custom_audience_name": "Purchasers 30D",
            "calculate_type": "8",
            "file_paths": ["abcdefghijklmnop"],
            "retention_in_days": 30,
        },
    )]


def test_tiktok_audience_reads_use_official_dmp_endpoints():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []

    def request_raw(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        return {
            "status_code": 200,
            "data": {
                "code": 0,
                "data": [{"audience_id": "456", "name": "Purchasers"}],
                "page_info": {"total_page": 1},
            },
        }

    client.request_raw = request_raw
    assert client.list_audiences("123", page_size=100) == [
        {"audience_id": "456", "name": "Purchasers"}
    ]
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/dmp/custom_audience/list/")

    detail_calls = []
    client.request = lambda method, endpoint, params=None, **kwargs: (
        detail_calls.append((method, endpoint, params))
        or [{"audience_details": [{"audience_id": "456", "status": "READY"}]}]
    )
    assert client.get_audience("123", "456") == {
        "audience_id": "456", "status": "READY"
    }
    assert detail_calls == [(
        "GET", "dmp/custom_audience/get/",
        {"advertiser_id": "123", "custom_audience_ids": ["456"]},
    )]


def test_tiktok_audience_update_builds_official_file_operation_payload():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data)) or {"updated": True}
    )

    result = client.update_audience("123", "456", {
        "file_paths": ["abcdefghijklmnop"],
        "action": "APPEND",
    })

    assert result == {"updated": True}
    assert calls == [(
        "POST", "dmp/custom_audience/update/", {
            "advertiser_id": "123",
            "custom_audience_id": "456",
            "file_paths": ["abcdefghijklmnop"],
            "action": "APPEND",
        },
    )]
    with pytest.raises(ValueError, match="custom_audience_name or file_paths"):
        client.update_audience("123", "456", {"action": "REPLACE"})


def test_tiktok_audience_file_upload_hashes_file_and_uses_multipart_contract(tmp_path):
    client = TikTokAPIClient({"access_token": "test"})
    source = tmp_path / "audience.csv"
    source.write_bytes(b"email\n" + b"a" * 64 + b"\n")
    calls = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data, kwargs)) or {"file_path": "abcdefghijklmnop"}
    )

    result = client.upload_audience_file("123", str(source), "EMAIL_SHA256")

    assert result == {"file_path": "abcdefghijklmnop"}
    method, endpoint, data, kwargs = calls[0]
    assert (method, endpoint) == (
        "POST", "dmp/custom_audience/file/upload/"
    )
    assert data["advertiser_id"] == "123"
    assert data["calculate_type"] == "8"
    assert data["file_signature"] == "1ca580e2a89424daff7196518f934ffa"
    assert kwargs["files"]["file"][0] == "audience.csv"
    assert kwargs["files"]["file"][1].closed is True

    with pytest.raises(ValueError, match=".csv or .txt"):
        bad = tmp_path / "audience.json"
        bad.write_text("{}", encoding="utf-8")
        client.upload_audience_file("123", str(bad), "EMAIL_SHA256")


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
    assert lead.input_schema.properties["page_id"]["minLength"] == 1
    assert lead.input_schema.properties["conversion_id"]["lookup_tool"] == (
        "tiktok_list_conversions"
    )
    assert lead.parent_resource_type == "ad_group"
    assert "form_id" not in lead.input_schema.properties
    app = definitions["tiktok_create_app_ad"]
    assert app.input_schema.properties["app_id"]["lookup_tool"] == "tiktok_list_apps"
    assert app.input_schema.properties["promotion_type"]["enum"] == [
        "APP_ANDROID", "APP_IOS"
    ]
    assert app.parent_resource_id_field == "adgroup_id"


def test_tiktok_targeting_tool_exposes_lookup_backed_schema_and_is_dry_run_only():
    definitions = {
        definition.name: definition
        for definition, _handler in create_tiktok_capability().register_tools()
    }
    targeting = definitions["tiktok_update_adgroup_targeting"]
    assert targeting.input_schema.required == [
        "account_id", "campaign_id", "adgroup_id", "updates"
    ]
    nested = targeting.input_schema.properties["updates"]
    assert nested["additionalProperties"] is False
    assert nested["properties"]["location_ids"]["lookup_tool"] == (
        "tiktok_list_locations"
    )
    assert nested["properties"]["interest_category_ids"]["lookup_tool"] == (
        "tiktok_list_interest_categories"
    )
    assert targeting.parent_resource_type == "campaign"
    assert targeting.parent_resource_id_field == "campaign_id"
    assert targeting.live_support is False
    generic_updates = definitions["tiktok_update_adgroup"].input_schema.properties["updates"]
    assert "targeting" not in generic_updates["properties"]


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


def test_tiktok_tool_region_uses_contextual_official_endpoint():
    client = TikTokAPIClient({"access_token": "test"})
    calls = []
    client.request = lambda method, endpoint, params=None, **kwargs: (
        calls.append((method, endpoint, params)) or {
            "code": 0, "message": "OK", "data": {"list": [{"location_id": "US"}]}
        }
    )

    assert client.list_regions(
        "123", ["PLACEMENT_TIKTOK"], "LEAD_GENERATION",
        promotion_target_type="INSTANT_PAGE", level_range="TO_COUNTRY",
    ) == [{"location_id": "US"}]
    assert calls == [("GET", "tool/region/", {
        "advertiser_id": "123",
        "placements": ["PLACEMENT_TIKTOK"],
        "objective_type": "LEAD_GENERATION",
        "promotion_target_type": "INSTANT_PAGE",
        "level_range": "TO_COUNTRY",
    })]


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


def test_meta_messaging_ad_builds_click_to_message_story_spec():
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"id": "ad-message-1"}
    )

    assert client.create_messaging_ad("act_1", "as_1", {
        "name": "WhatsApp Ad", "page_id": "page-1", "messaging_app": "WHATSAPP",
        "call_to_action_type": "WHATSAPP", "message": "Chat with us",
        "headline": "Talk to sales", "link": "https://example.test/contact",
        "status": "PAUSED",
    }) == "ad-message-1"
    method, endpoint, data = payloads[-1]
    assert (method, endpoint) == ("POST", "/act_1/ads")
    creative = json.loads(data["creative"])
    assert creative == {
        "object_story_spec": {
            "page_id": "page-1",
            "link_data": {
                "link": "https://example.test/contact",
                "message": "Chat with us",
                "name": "Talk to sales",
                "description": "",
                "call_to_action": {"type": "WHATSAPP"},
            },
        }
    }

    with pytest.raises(ValueError, match="requires SEND_MESSAGE CTA"):
        client.create_messaging_ad("act_1", "as_1", {
            "page_id": "page-1", "messaging_app": "MESSENGER",
            "call_to_action_type": "WHATSAPP",
        })


def test_meta_messaging_tool_publishes_destination_contract_and_route():
    capability = create_meta_capability()
    definitions = {
        definition.name: definition
        for definition, _handler in capability.register_tools()
    }
    messaging = definitions["meta_create_messaging_ad"]
    assert messaging.input_schema.properties["messaging_app"]["enum"] == [
        "MESSENGER", "WHATSAPP", "INSTAGRAM_DIRECT"
    ]
    assert messaging.input_schema.properties["call_to_action_type"]["enum"] == [
        "SEND_MESSAGE", "WHATSAPP"
    ]
    assert validate_tool_input(
        messaging.input_schema,
        {
            "adset_id": "as-1", "name": "Message Ad", "page_id": "page-1",
            "messaging_app": "MESSENGER", "call_to_action_type": "SEND_MESSAGE",
        },
        include_provider_contract=True,
    ) == []
    assert validate_tool_input(
        messaging.input_schema,
        {
            "adset_id": "as-1", "name": "Message Ad", "page_id": "page-1",
            "messaging_app": "WHATSAPP", "call_to_action_type": "SEND_MESSAGE",
        },
        include_provider_contract=True,
    )

    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(capability)
    routed = runtime.intent_router.route(
        ParsedIntent(
            "create_campaign", "create", ["meta"],
            platform_params={"meta": {
                "objective": "OUTCOME_MESSAGES",
                "optimization_goal": "MESSAGES",
                "messaging_app": "MESSENGER",
            }},
        ),
        runtime.registry,
    )
    assert [definition.name for definition in routed["meta"]] == [
        "meta_create_campaign", "meta_create_adset", "meta_create_messaging_ad",
    ]


@pytest.mark.parametrize(
    "media_type, extra, expected_key",
    [
        ("IMAGE", {"image_hash": "img-hash-1"}, "link_data"),
        ("VIDEO", {"video_id": "video-1"}, "video_data"),
    ],
)
def test_meta_link_ad_builds_object_story_spec(media_type, extra, expected_key):
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"id": "ad-link-1"}
    )

    assert client.create_link_ad("act_1", "as_1", {
        "name": "Link Ad", "page_id": "page-1", "link": "https://example.test/landing",
        "media_type": media_type, "message": "Learn more", "headline": "Offer",
        "call_to_action_type": "LEARN_MORE", **extra,
    }) == "ad-link-1"
    creative = json.loads(payloads[-1][2]["creative"])
    story = creative["object_story_spec"]
    assert story["page_id"] == "page-1"
    assert expected_key in story
    if media_type == "IMAGE":
        assert story[expected_key]["link"] == "https://example.test/landing"
        assert story[expected_key]["image_hash"] == "img-hash-1"
    else:
        assert story[expected_key]["video_id"] == "video-1"
        assert story[expected_key]["call_to_action"]["value"] == {
            "link": "https://example.test/landing"
        }

    with pytest.raises(ValueError, match="VIDEO link creatives require video_id"):
        client.create_link_ad("act_1", "as_1", {
            "page_id": "page-1", "link": "https://example.test/landing",
            "media_type": "VIDEO",
        })


def test_meta_traffic_and_conversion_tools_route_link_creatives():
    capability = create_meta_capability()
    definitions = {
        definition.name: definition
        for definition, _handler in capability.register_tools()
    }
    for name in ("meta_create_traffic_ad", "meta_create_conversion_ad"):
        assert definitions[name].input_schema.properties["link"]["minLength"] == 1
        assert definitions[name].input_schema.properties["media_type"]["enum"] == [
            "IMAGE", "VIDEO"
        ]

    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(capability)
    cases = [
        (
            "OUTCOME_TRAFFIC", "LINK_CLICKS", "meta_create_traffic_ad",
        ),
        (
            "OUTCOME_CONVERSIONS", "CONVERSIONS", "meta_create_conversion_ad",
        ),
    ]
    for objective, optimization_goal, expected in cases:
        routed = runtime.intent_router.route(
            ParsedIntent(
                "create_campaign", "create", ["meta"],
                platform_params={"meta": {
                    "objective": objective,
                    "optimization_goal": optimization_goal,
                    "page_id": "page-1",
                    "link": "https://example.test/landing",
                }},
            ),
            runtime.registry,
        )
        assert [definition.name for definition in routed["meta"]] == [
            "meta_create_campaign", "meta_create_adset", expected,
        ]


@pytest.mark.parametrize(
    "engagement_type, source_field, source_value, expected_story",
    [
        (
            "POST_ENGAGEMENT", "post_id", "post-1",
            {"page_id": "page-1", "post_id": "post-1"},
        ),
        (
            "VIDEO_VIEWS", "video_id", "video-1",
            {
                "page_id": "page-1",
                "video_data": {
                    "video_id": "video-1", "message": "Watch this",
                    "title": "New video",
                    "call_to_action": {"type": "WATCH_VIDEO"},
                },
            },
        ),
    ],
)
def test_meta_engagement_ad_builds_post_or_video_story_spec(
    engagement_type, source_field, source_value, expected_story,
):
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append((method, endpoint, data)) or {"id": "ad-engagement-1"}
    )

    input_data = {
        "name": "Engagement Ad", "page_id": "page-1",
        "engagement_type": engagement_type, source_field: source_value,
        "message": "Watch this", "headline": "New video",
        "call_to_action_type": "WATCH_VIDEO",
    }
    assert client.create_engagement_ad("act_1", "as_1", input_data) == "ad-engagement-1"
    creative = json.loads(payloads[-1][2]["creative"])
    assert creative["object_story_spec"] == expected_story

    missing = dict(input_data)
    missing.pop(source_field)
    with pytest.raises(ValueError, match=f"{engagement_type} creatives require"):
        client.create_engagement_ad("act_1", "as_1", missing)


def test_meta_engagement_tool_routes_post_and_video_objectives():
    capability = create_meta_capability()
    definitions = {
        definition.name: definition
        for definition, _handler in capability.register_tools()
    }
    engagement = definitions["meta_create_engagement_ad"]
    assert engagement.input_schema.properties["engagement_type"]["enum"] == [
        "POST_ENGAGEMENT", "VIDEO_VIEWS"
    ]
    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(capability)
    cases = [
        ("POST_ENGAGEMENT", {"post_id": "post-1"}),
        ("VIDEO_VIEWS", {"video_id": "video-1"}),
    ]
    for optimization_goal, source in cases:
        routed = runtime.intent_router.route(
            ParsedIntent(
                "create_campaign", "create", ["meta"],
                platform_params={"meta": {
                    "objective": "OUTCOME_ENGAGEMENT",
                    "optimization_goal": optimization_goal,
                    "page_id": "page-1", **source,
                }},
            ),
            runtime.registry,
        )
        assert [definition.name for definition in routed["meta"]] == [
            "meta_create_campaign", "meta_create_adset", "meta_create_engagement_ad",
        ]


def test_meta_creative_crud_uses_account_scoped_graph_edges():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: (
        calls.append(("ownership", account_id, resource_type, resource_id)) or True
    )
    client._list_graph_pages = lambda account_id, endpoint, params, **kwargs: (
        calls.append(("list", account_id, endpoint, params)) or [{"id": "cr-1", "name": "Old"}]
    )
    client.request = lambda method, endpoint, data=None, **kwargs: (
        calls.append((method, endpoint, data, kwargs.get("extra_params")))
        or ({"id": "cr-1", "name": "New"} if method == "GET" else {"success": True})
    )

    assert client.list_creatives("act_123", limit=10)[0]["id"] == "cr-1"
    assert client.get_creative("act_123", "cr-1", fields=["id", "name"])["id"] == "cr-1"
    assert client.update_creative("act_123", "cr-1", {"name": "New"})["success"] is True
    assert client.delete_creative("act_123", "cr-1")["creative_id"] == "cr-1"
    assert calls[0][0:3] == ("list", "123", "/act_123/adcreatives")
    assert calls[1] == ("ownership", "123", "creative", "cr-1")
    assert calls[2] == ("GET", "/cr-1", None, {"fields": "id,name"})
    assert calls[3] == ("ownership", "123", "creative", "cr-1")
    assert calls[4][0:3] == ("POST", "/cr-1", {"name": "New"})
    assert calls[5] == ("ownership", "123", "creative", "cr-1")
    assert calls[6][0:2] == ("DELETE", "/cr-1")


def test_meta_creative_tools_publish_crud_and_narrow_update_contract():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    assert {
        "meta_list_creatives", "meta_get_creative", "meta_create_creative",
        "meta_update_creative", "meta_delete_creative",
    } <= set(definitions)
    updates = definitions["meta_update_creative"].input_schema.properties["updates"]
    assert updates["properties"] == {
        "name": updates["properties"]["name"]
    }
    assert updates["additionalProperties"] is False


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


def test_meta_catalog_and_product_set_tools_cover_scoped_crud():
    client = MetaAPIClient({"access_token": "test"})
    calls = []

    client.resource_belongs_to_account = lambda account_id, resource_type, resource_id: (
        calls.append(("ownership", account_id, resource_type, resource_id)) or True
    )
    client._list_graph_pages = lambda account_id, endpoint, params, **kwargs: (
        calls.append(("list", account_id, endpoint, params)) or [{"id": "ps1"}]
    )

    def request(method, endpoint, data=None, **kwargs):
        calls.append((method, endpoint, data, kwargs.get("extra_params")))
        if method == "GET" and endpoint == "/cat1":
            return {"id": "cat1", "name": "Catalog"}
        if method == "GET" and endpoint == "/ps1":
            return {"id": "ps1", "name": "Set"}
        if method == "POST" and endpoint == "/biz1/owned_product_catalogs":
            return {"id": "cat2"}
        if method == "POST" and endpoint == "/cat1/product_sets":
            return {"id": "ps2"}
        return {"success": True}

    client.request = request

    assert client.get_catalog("act_1", "cat1")["id"] == "cat1"
    assert client.create_catalog("biz1", {
        "name": "Catalog", "vertical": "commerce", "is_checkout": False,
    }) == "cat2"
    assert client.update_catalog("1", "cat1", {"name": "Updated"})["success"]
    assert client.delete_catalog("1", "cat1")["catalog_id"] == "cat1"
    assert client.list_product_sets("1", "cat1")[0]["id"] == "ps1"
    assert client.get_product_set("1", "cat1", "ps1")["id"] == "ps1"
    assert client.create_product_set("1", "cat1", {
        "name": "Set", "filter": {"brand": {"eq": "Acme"}},
    }) == "ps2"
    assert client.update_product_set("1", "cat1", "ps1", {
        "filter": {"availability": {"eq": "in stock"}},
    })["success"]
    assert client.delete_product_set("1", "cat1", "ps1")["product_set_id"] == "ps1"

    create_catalog_call = next(
        item for item in calls
        if item[:2] == ("POST", "/biz1/owned_product_catalogs")
    )
    assert create_catalog_call[2] == {
        "name": "Catalog", "vertical": "commerce", "is_checkout": False,
    }
    create_set_call = next(
        item for item in calls
        if item[:2] == ("POST", "/cat1/product_sets")
    )
    assert json.loads(create_set_call[2]["filter"]) == {"brand": {"eq": "Acme"}}


def test_meta_catalog_tools_require_scope_and_keep_writes_dry_run():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    expected = {
        "meta_get_catalog", "meta_create_catalog", "meta_update_catalog", "meta_delete_catalog",
        "meta_list_product_sets", "meta_get_product_set", "meta_create_product_set",
        "meta_update_product_set", "meta_delete_product_set",
    }
    assert expected <= set(definitions)
    assert definitions["meta_list_product_sets"].input_schema.required == [
        "account_id", "catalog_id"
    ]
    assert definitions["meta_create_catalog"].input_schema.required == [
        "business_id", "name", "vertical"
    ]
    assert all(
        definitions[name].is_write_tool and definitions[name].live_support is False
        for name in expected
        if definitions[name].is_write_tool
    )


def test_meta_targeting_search_is_scoped_read_only_and_published():
    client = MetaAPIClient({"access_token": "test"})
    calls = []
    client._list_graph_pages = lambda account_id, endpoint, params, **kwargs: (
        calls.append((account_id, endpoint, params, kwargs))
        or [{"id": "interest-1", "name": "Marketing"}]
    )

    assert client.search_targeting(
        "act_123", "marketing", search_type="adinterest", limit=10,
    ) == [{"id": "interest-1", "name": "Marketing"}]
    assert calls == [(
        "123", "/act_123/targetingsearch",
        {"q": "marketing", "type": "adinterest", "limit": 10}, {},
    )]
    with pytest.raises(ValueError, match="non-empty"):
        client.search_targeting("123", "")
    with pytest.raises(ValueError, match="between 1 and 100"):
        client.search_targeting("123", "marketing", limit=101)

    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    targeting = definitions["meta_search_targeting_options"]
    assert targeting.is_write_tool is False
    assert targeting.input_schema.required == ["account_id", "query"]
    assert "adinterest" in targeting.input_schema.properties["type"]["enum"]


def test_meta_campaign_special_categories_are_validated_before_graph_request():
    client = MetaAPIClient({"access_token": "test"})
    client.request = lambda *args, **kwargs: {"id": "campaign-1"}
    with pytest.raises(ValueError, match="cannot be combined"):
        client.create_campaign("123", {
            "name": "Restricted", "objective": "OUTCOME_SALES",
            "special_ad_categories": ["NONE", "HOUSING"],
        })
    with pytest.raises(ValueError, match="Unsupported Meta"):
        client.create_campaign("123", {
            "name": "Invalid", "objective": "OUTCOME_SALES",
            "special_ad_categories": ["UNKNOWN"],
        })


def test_meta_adset_bid_strategy_and_inline_creative_contracts_are_explicit():
    definitions = {
        definition.name: definition
        for definition, _handler in create_meta_capability().register_tools()
    }
    adset_schema = definitions["meta_create_adset"].input_schema
    base = {
        "campaign_id": "campaign-1", "name": "Sales ad set",
        "targeting": {"geo_locations": {"countries": ["US"]}},
        "optimization_goal": "OFFSITE_CONVERSIONS",
        "billing_event": "IMPRESSIONS", "daily_budget": 20,
        "promoted_object": {"pixel_id": "pixel-1", "custom_event_type": "PURCHASE"},
        "bid_strategy": "COST_CAP",
    }
    assert any("bid_amount" in error for error in validate_tool_input(
        adset_schema, base, include_provider_contract=True,
    ))
    base["bid_amount"] = 5
    assert validate_tool_input(adset_schema, base, include_provider_contract=True) == []

    min_roas = {**base, "bid_strategy": "LOWEST_COST_WITH_MIN_ROAS"}
    assert any("roas_average_floor" in error for error in validate_tool_input(
        adset_schema, min_roas, include_provider_contract=True,
    ))
    min_roas["roas_average_floor"] = 1.25
    assert validate_tool_input(adset_schema, min_roas, include_provider_contract=True) == []

    ad_schema = definitions["meta_create_ad"].input_schema
    cta_schema = ad_schema.properties["object_story_spec"]["properties"]["link_data"]["properties"]["call_to_action"]
    assert "SEND_MESSAGE" in cta_schema["properties"]["type"]["enum"]
    assert "CAROUSEL" in ad_schema.properties["ad_format"]["enum"]


def test_meta_adset_client_rejects_missing_cap_limits_and_forwards_roas_floor():
    client = MetaAPIClient({"access_token": "test"})
    payloads = []
    client.request = lambda method, endpoint, data=None, **kwargs: (
        payloads.append(data) or {"id": "adset-1"}
    )
    with pytest.raises(ValueError, match="COST_CAP requires bid_amount"):
        client.create_adset("123", "campaign-1", {
            "name": "Cost cap", "bid_strategy": "COST_CAP",
        })

    assert client.create_adset("123", "campaign-1", {
        "name": "Min ROAS", "bid_strategy": "LOWEST_COST_WITH_MIN_ROAS",
        "roas_average_floor": 1.4,
    }) == "adset-1"
    assert payloads[-1]["bidding_strategy"] == "LOWEST_COST_WITH_MIN_ROAS"
    assert payloads[-1]["roas_average_floor"] == "1.4"


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


def test_google_campaign_handler_forwards_all_optimization_parameters():
    """The Tool schema and live handler must expose the same optimizer contract."""
    captured = {}

    class FakeGoogleClient:
        def create_campaign(self, **kwargs):
            captured.update(kwargs)
            return "campaign-1"

    handler = GoogleCreateCampaignHandler(FakeGoogleClient())
    result = handler.execute(
        ToolContext(session_id="s1", user_id="u1", account_id="customer-1"),
        {
            "campaign_name": "Video optimization",
            "advertising_channel_type": "VIDEO",
            "bidding_strategy": "TARGET_CPM",
            "daily_budget": 25,
            "target_impression_share_location": "TOP_OF_PAGE",
            "cpc_bid_ceiling_micros": 1_500_000,
            "target_cpm_micros": 2_500_000,
            "target_cpv_micros": 3_500_000,
        },
    )

    assert result.success is True
    assert captured["target_impression_share_location"] == "TOP_OF_PAGE"
    assert captured["cpc_bid_ceiling_micros"] == 1_500_000
    assert captured["target_cpm_micros"] == 2_500_000
    assert captured["target_cpv_micros"] == 3_500_000


def test_google_core_hierarchy_delete_methods_use_customer_mutate_remove():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    operations = []
    client._mutate = lambda resource, operation: operations.append((resource, operation)) or {}

    assert client.delete_campaign("10")["campaign_id"] == "10"
    assert client.delete_ad_group("20")["ad_group_id"] == "20"
    assert client.delete_ad("20", "30")["ad_id"] == "30"

    assert operations == [
        ("campaigns", {"remove": "customers/123/campaigns/10"}),
        ("adGroups", {"remove": "customers/123/adGroups/20"}),
        ("adGroupAds", {"remove": "customers/123/adGroupAds/20~30"}),
    ]
    with pytest.raises(ValueError, match="digits only"):
        client.delete_ad("20", "ad-30")


def test_google_core_hierarchy_delete_tools_are_dry_run_and_traced():
    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    expected = {
        "google_delete_campaign": ["campaign_id"],
        "google_delete_ad_group": ["ad_group_id"],
        "google_delete_ad": ["ad_group_id", "ad_id"],
    }
    for name, required in expected.items():
        definition = definitions[name]
        assert definition.is_write_tool
        assert definition.live_support is False
        assert definition.input_schema.provider_required == required


def test_google_campaign_contract_covers_channel_specific_parameters():
    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    schema = definitions["google_create_campaign"].input_schema

    # Nested settings are closed contracts, not arbitrary dictionaries.
    assert schema.properties["shopping_setting"]["additionalProperties"] is False
    assert schema.properties["network_setting"]["properties"].keys() >= {
        "target_google_search", "target_search_partners", "target_content_network",
    }
    assert "TARGET_CPM" in schema.properties["bidding_strategy"]["enum"]
    assert "DEMAND_GEN" in schema.properties["advertising_channel_type"]["enum"]

    valid_video = {
        "customer_id": "123", "campaign_name": "Video", "daily_budget": 10,
        "advertising_channel_type": "VIDEO", "bidding_strategy": "TARGET_CPM",
        "target_cpm_micros": 2500000,
        "video_setting": {"smart_performance": False},
    }
    assert validate_tool_input(schema, valid_video, include_provider_contract=True) == []

    missing_video_setting = {key: value for key, value in valid_video.items() if key != "video_setting"}
    assert any("video_setting" in error for error in validate_tool_input(
        schema, missing_video_setting, include_provider_contract=True,
    ))

    engagement = {
        "customer_id": "123", "campaign_name": "App engagement", "daily_budget": 10,
        "advertising_channel_type": "MULTI_CHANNEL",
        "advertising_channel_sub_type": "APP_CAMPAIGN_FOR_ENGAGEMENT",
        "app_campaign_setting": {
            "app_id": "com.example.app", "app_store": "GOOGLE_APP_STORE",
        },
        "bidding_strategy": "MAXIMIZE_CONVERSIONS",
    }
    assert any("selective_optimization" in error for error in validate_tool_input(
        schema, engagement, include_provider_contract=True,
    ))
    engagement["app_campaign_setting"]["selective_optimization"] = [
        "customers/123/conversionActions/9"
    ]
    assert validate_tool_input(schema, engagement, include_provider_contract=True) == []

    shopping = {
        "customer_id": "123", "campaign_name": "Shopping", "daily_budget": 10,
        "advertising_channel_type": "SHOPPING", "bidding_strategy": "MANUAL_CPC",
    }
    assert any("shopping_setting" in error for error in validate_tool_input(
        schema, shopping, include_provider_contract=True,
    ))


def test_google_campaign_client_normalizes_channel_alias_and_video_bidding():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    operations = []
    client._mutate = lambda resource, operation: (
        operations.append((resource, operation)) or {
            "data": {"results": [{"resourceName": f"customers/g1/{resource}/resource-1"}]}
        }
    )

    client.create_campaign(
        "PMax", "MAX", "MAXIMIZE_CONVERSIONS", 10,
    )
    campaign = operations[1][1]["create"]
    assert campaign["advertisingChannelType"] == "PERFORMANCE_MAX"

    operations.clear()
    client.create_campaign(
        "Video", "VIDEO", "TARGET_CPM", 10, target_cpm_micros=2500000,
        network_setting={"target_content_network": True},
    )
    campaign = operations[1][1]["create"]
    assert campaign["targetCpm"] == {"targetCpmMicros": 2500000}
    assert campaign["networkSettings"] == {"targetContentNetwork": True}


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


def test_google_keyword_update_and_delete_use_composite_criterion_resource():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "g1"})
    calls = []
    client._mutate = lambda resource, operation: (
        calls.append((resource, operation)) or {}
    )

    assert client.update_keyword(
        "123", "456", {"status": "PAUSED", "cpc_bid_micros": 250000}
    ) == {"success": True, "ad_group_id": "123", "keyword_id": "456"}
    resource, operation = calls[0]
    assert resource == "adGroupCriteria"
    assert operation["update"]["resourceName"] == (
        "customers/g1/adGroupCriteria/123~456"
    )
    assert operation["update"]["status"] == "PAUSED"
    assert operation["update"]["cpcBidMicros"] == 250000
    assert operation["updateMask"]["paths"] == ["status", "cpcBidMicros"]

    assert client.delete_keyword("123", "456") == {
        "success": True, "ad_group_id": "123", "keyword_id": "456"
    }
    assert calls[1] == (
        "adGroupCriteria",
        {"remove": "customers/g1/adGroupCriteria/123~456"},
    )

    with pytest.raises(ValueError, match="Unsupported Google keyword"):
        client.update_keyword("123", "456", {"text": "immutable"})


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
    ) == "456"
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


def test_google_product_group_queries_normalize_listing_group_rows():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []

    def search(query, **kwargs):
        calls.append((query, kwargs))
        return [{
            "adGroup": {"id": "456"},
            "adGroupCriterion": {
                "criterionId": "789",
                "resourceName": "customers/123/adGroupCriteria/456~789",
                "status": "ENABLED",
                "cpcBidMicros": "250000",
                "listingGroup": {
                    "type": "SUBDIVISION",
                    "parentAdGroupCriterion": "customers/123/adGroupCriteria/456~700",
                    "caseValue": {
                        "productType": {"level": "LEVEL2", "value": "Shoes"}
                    },
                },
            },
        }]

    client._search_all = search
    groups = client.list_product_groups("456", page_size=25)
    assert groups == [{
        "id": "789",
        "product_group_id": "789",
        "ad_group_id": "456",
        "resource_name": "customers/123/adGroupCriteria/456~789",
        "status": "ENABLED",
        "cpc_bid_micros": "250000",
        "partition_type": "SUBDIVISION",
        "product_group_type": "product_type_2",
        "value": "Shoes",
        "parent_criterion_id": "customers/123/adGroupCriteria/456~700",
    }]
    assert calls[0][1] == {"page_size": 25}
    assert "ad_group_criterion.type = LISTING_GROUP" in calls[0][0]
    assert "ad_group.id = 456" in calls[0][0]

    client._search_all = lambda query, **kwargs: [{
        "ad_group": {"id": "456"},
        "ad_group_criterion": {
            "criterion_id": "790",
            "listing_group": {
                "type": "UNIT",
                "case_value": {"product_custom_label": {
                    "index": "INDEX3", "value": "clearance"
                }},
            },
        },
    }]
    assert client.get_product_group("456", "790")["product_group_type"] == "custom_label_3"


def test_google_product_group_update_and_delete_use_composite_criterion_resource():
    client = GoogleAdsAPIClient({"access_token": "test"}, customer_id="123")
    calls = []
    client._mutate = lambda resource, operation: (
        calls.append((resource, operation)) or {}
    )

    assert client.update_product_group(
        "456", "789", {"status": "PAUSED", "cpc_bid": 0.25}
    ) == {
        "success": True, "ad_group_id": "456", "product_group_id": "789",
    }
    assert calls[0] == (
        "adGroupCriteria",
        {
            "update": {
                "resourceName": "customers/123/adGroupCriteria/456~789",
                "status": "PAUSED",
                "cpcBidMicros": 250000,
            },
            "updateMask": {"paths": ["status", "cpcBidMicros"]},
        },
    )

    assert client.delete_product_group("456", "789") == {
        "success": True, "ad_group_id": "456", "product_group_id": "789",
    }
    assert calls[1] == (
        "adGroupCriteria",
        {"remove": "customers/123/adGroupCriteria/456~789"},
    )

    with pytest.raises(ValueError, match="Unsupported Google product group"):
        client.update_product_group("456", "789", {"product_group_type": "brand"})


def test_google_product_group_lifecycle_tools_are_scoped_and_dry_run_only():
    definitions = {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }
    expected = {
        "google_create_product_group", "google_list_product_groups",
        "google_get_product_group", "google_update_product_group",
        "google_delete_product_group",
    }
    assert expected <= definitions.keys()
    assert definitions["google_list_product_groups"].input_schema.required == ["ad_group_id"]
    assert definitions["google_get_product_group"].input_schema.required == [
        "ad_group_id", "product_group_id",
    ]
    assert definitions["google_update_product_group"].input_schema.required == [
        "ad_group_id", "product_group_id", "updates",
    ]
    assert definitions["google_update_product_group"].input_schema.properties["updates"][
        "additionalProperties"
    ] is False
    assert all(
        definitions[name].is_write_tool and definitions[name].live_support is False
        for name in expected
        if definitions[name].is_write_tool
    )


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
