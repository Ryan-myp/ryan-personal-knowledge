"""Contracts and provider payload plans for Google Ads v24 specialized formats."""

from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.capabilities.google import create_google_capability
from agents.ad_agent.core.interfaces import ParsedIntent
from agents.ad_agent.core.tool_registry import validate_tool_input
from agents.ad_agent.runtime.runtime import AgentRuntime


def _definitions():
    return {
        definition.name: definition
        for definition, _handler in create_google_capability().register_tools()
    }


def test_google_specialized_creation_chains_are_metadata_driven():
    runtime = AgentRuntime(require_llm=False)
    runtime.register_capability(create_google_capability())
    expected = {
        "DEMAND_GEN": [
            "google_create_campaign", "google_create_specialized_ad_group",
            "google_create_demand_gen_carousel_ad",
            "google_create_demand_gen_multi_asset_ad",
            "google_create_demand_gen_product_ad",
            "google_create_demand_gen_video_responsive_ad",
        ],
        "HOTEL": [
            "google_create_campaign", "google_create_specialized_ad_group",
            "google_create_hotel_ad",
        ],
        "LOCAL": [
            "google_create_campaign", "google_create_specialized_ad_group",
            "google_create_local_ad",
        ],
        "SMART": [
            "google_create_campaign", "google_create_specialized_ad_group",
            "google_create_smart_campaign_ad",
        ],
        "TRAVEL": [
            "google_create_campaign", "google_create_specialized_ad_group",
            "google_create_travel_ad",
        ],
    }
    for campaign_type, tool_names in expected.items():
        routed = runtime.intent_router.route(
            ParsedIntent(
                "create_campaign", "create", ["google-ads"],
                platform_params={"google-ads": {
                    "advertising_channel_type": campaign_type,
                }},
            ),
            runtime.registry,
        )
        assert [definition.name for definition in routed["google-ads"]] == tool_names


def test_google_specialized_campaign_settings_are_closed_and_provider_ready():
    campaign = _definitions()["google_create_campaign"]
    valid = {
        "customer_id": "123", "campaign_name": "specialized", "daily_budget": 10,
        "bidding_strategy": "MAXIMIZE_CONVERSIONS",
        "advertising_channel_type": "DEMAND_GEN",
        "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        "demand_gen_campaign_settings": {"upgraded_targeting": True},
    }
    assert validate_tool_input(campaign.input_schema, valid, include_provider_contract=True) == []
    missing = dict(valid)
    missing.pop("demand_gen_campaign_settings")
    assert any("demand_gen_campaign_settings" in error for error in validate_tool_input(
        campaign.input_schema, missing, include_provider_contract=True,
    ))

    for campaign_type, setting in (
        ("HOTEL", {"hotel_center_id": "55"}),
        ("LOCAL", {"location_source_type": "GOOGLE_MY_BUSINESS"}),
        ("TRAVEL", {"travel_account_id": "77"}),
    ):
        payload = dict(valid)
        payload["advertising_channel_type"] = campaign_type
        payload.pop("demand_gen_campaign_settings")
        field = {
            "HOTEL": "hotel_setting",
            "LOCAL": "local_campaign_setting",
            "TRAVEL": "travel_campaign_settings",
        }[campaign_type]
        payload[field] = setting
        assert validate_tool_input(
            campaign.input_schema, payload, include_provider_contract=True,
        ) == []


def test_google_specialized_ad_tools_are_live_capable_and_closed():
    definitions = _definitions()
    names = {
        "google_create_specialized_ad_group",
        "google_create_demand_gen_multi_asset_ad",
        "google_create_demand_gen_carousel_ad",
        "google_create_demand_gen_video_responsive_ad",
        "google_create_demand_gen_product_ad",
        "google_create_hotel_ad", "google_create_local_ad",
        "google_create_smart_campaign_ad", "google_create_travel_ad",
    }
    assert names <= definitions.keys()
    for name in names:
        assert definitions[name].live_support is True
        assert definitions[name].input_schema.additional_properties is False


def test_google_specialized_provider_plans_use_v24_adgroup_ad_payloads():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    cases = [
        ("create_demand_gen_multi_asset_ad", (
            "10", "multi", "https://example.test", ["h1", "h2", "h3"],
            ["d1", "d2"], "Example",
        ), {"marketing_images": ["customers/123/assets/1"]}, "demandGenMultiAssetAd"),
        ("create_demand_gen_carousel_ad", (
            "10", "carousel", "https://example.test", "headline", "description",
            [{"headline": "card 1", "square_marketing_image_asset": "customers/123/assets/1"},
             {"headline": "card 2", "marketing_image_asset": "customers/123/assets/2"}],
        ), {}, "demandGenCarouselAd"),
        ("create_local_ad", (
            "10", "local", "https://example.test", ["h1", "h2", "h3"], ["d1", "d2"],
        ), {}, "localAd"),
        ("create_smart_campaign_ad", (
            "10", "smart", "https://example.test", ["h1", "h2", "h3"], ["d1", "d2"],
        ), {}, "smartCampaignAd"),
        ("create_hotel_ad", ("10", "hotel"), {}, "hotelAd"),
        ("create_travel_ad", ("10", "travel"), {}, "travelAd"),
    ]
    for method_name, args, kwargs, payload_name in cases:
        plan = getattr(client, method_name)(*args, **kwargs)
        operation = plan["operation"]["adGroupAds"]["create"]
        assert operation["ad"][payload_name] is not None
        assert plan["mode"] == "dry_run"
        assert plan["live_support"] is True


def test_google_demand_gen_ad_group_and_campaign_settings_map_to_wire_fields():
    client = GoogleAdsAPIClient({"access_token": "test", "customer_id": "123"})
    operations = []
    client._mutate = lambda resource, operation: (
        operations.append((resource, operation)) or {
            "data": {"results": [{"resourceName": f"customers/123/{resource}/1"}]}
        }
    )
    client.create_campaign(
        "Demand Gen", "DEMAND_GEN", "MAXIMIZE_CONVERSIONS", 10,
        demand_gen_campaign_settings={"upgraded_targeting": True},
        live=True,
    )
    campaign = operations[1][1]["create"]
    assert campaign["demandGenCampaignSettings"] == {"upgradedTargeting": True}

    operations.clear()
    client.create_ad_group(
        "1", "Demand Gen group", type="SEARCH_STANDARD",
        demand_gen_ad_group_settings={
            "channel_controls": {"channel_config": "SELECTED_CHANNELS"}
        },
        live=True,
    )
    ad_group = operations[0][1]["create"]
    assert ad_group["demandGenAdGroupSettings"] == {
        "channelControls": {"channelConfig": "SELECTED_CHANNELS"}
    }
