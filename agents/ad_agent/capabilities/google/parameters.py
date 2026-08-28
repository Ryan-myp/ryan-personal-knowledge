"""Google Ads creation contracts owned by the Google Capability."""

from __future__ import annotations

from typing import Any


GOOGLE_CHANNEL_TYPES = ["SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "APP", "PERFORMANCE_MAX"]
GOOGLE_BIDDING_STRATEGIES = [
    "MANUAL_CPC", "MAXIMIZE_CLICKS", "MAXIMIZE_CONVERSIONS", "TARGET_CPA",
    "TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE", "TARGET_IMPRESSION_SHARE",
]
GOOGLE_STATUSES = ["ENABLED", "PAUSED", "REMOVED"]
GOOGLE_AD_GROUP_TYPES = [
    "SEARCH_STANDARD", "SEARCH_DYNAMIC_ADS", "DISPLAY_STANDARD",
    "SHOPPING_PRODUCT", "VIDEO_TRUEVIEW_IN_STREAM", "VIDEO_BUMPER",
]
GOOGLE_ASSET_GROUP_TYPES = ["PERFORMANCE_MAX"]
GOOGLE_TARGETING_NETWORKS = ["GOOGLE_SEARCH", "SEARCH_PARTNERS", "DISPLAY_NETWORK"]


def _field(field_type: Any, description: str = "", **kwargs: Any) -> dict[str, Any]:
    value = {"type": field_type, "description": description}
    value.update(kwargs)
    return value


def google_campaign_schema() -> dict[str, Any]:
    return {
        "required": ["customer_id", "campaign_name"],
        "provider_required": ["advertising_channel_type", "bidding_strategy"],
        "provider_any_of": [["daily_budget", "budget"]],
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID; MCC is not accepted here"),
            "campaign_name": _field("string", "Campaign name", maxLength=255),
            "advertising_channel_type": _field(
                "string", "Channel type", enum=GOOGLE_CHANNEL_TYPES,
                input_aliases=["campaign_type"], default="SEARCH",
            ),
            "campaign_type": _field("string", "Channel type alias", enum=GOOGLE_CHANNEL_TYPES),
            "bidding_strategy": _field(
                "string", "Bidding strategy", enum=GOOGLE_BIDDING_STRATEGIES,
                default="MAXIMIZE_CONVERSIONS",
            ),
            "daily_budget": _field("number", "Daily budget in account currency", minimum=0),
            "budget": _field("number", "Daily budget alias", minimum=0),
            "status": _field("string", "Campaign status", enum=GOOGLE_STATUSES),
            "target_cpa_micros": _field("integer", "Target CPA in micros", minimum=1),
            "target_roas": _field("number", "Target ROAS", minimum=0.01),
            "target_impression_share": _field("number", "Target impression share", minimum=0, maximum=1),
            "networks": _field("array", "Serving networks", items={"type": "string", "enum": GOOGLE_TARGETING_NETWORKS}),
            "start_date": _field("string", "YYYY-MM-DD start date"),
            "end_date": _field("string", "YYYY-MM-DD end date"),
        },
        "conditional_rules": [
            {"id": "target_cpa_dependency", "if": {"bidding_strategy": "TARGET_CPA"},
             "required": ["target_cpa_micros"], "message": "TARGET_CPA requires target_cpa_micros"},
            {"id": "target_roas_dependency", "if": {"bidding_strategy": "TARGET_ROAS"},
             "required": ["target_roas"], "message": "TARGET_ROAS requires target_roas"},
            {"id": "target_value_dependency", "if": {"bidding_strategy": "MAXIMIZE_CONVERSION_VALUE"},
             "required": ["target_roas"], "message": "MAXIMIZE_CONVERSION_VALUE requires target_roas"},
        ],
    }


def google_ad_group_schema() -> dict[str, Any]:
    return {
        "required": ["campaign_id", "name"],
        "provider_required": ["type"],
        "properties": {
            "campaign_id": _field("string", "Parent Campaign ID"),
            "name": _field("string", "Ad group name", maxLength=255),
            "type": _field("string", "Ad group type", enum=GOOGLE_AD_GROUP_TYPES),
            "cpc_bid": _field("number", "CPC bid in account currency", minimum=0),
            "cpc_bid_micros": _field("integer", "CPC bid in micros", minimum=0),
            "status": _field("string", "Ad group status", enum=GOOGLE_STATUSES),
            "targeting": _field("object", "Ad group targeting", additionalProperties=True),
        },
    }


def google_ad_schema() -> dict[str, Any]:
    return {
        "required": ["ad_group_id", "name"],
        "provider_required": ["final_url"],
        "provider_any_of": [["headlines", "responsive_search_ad"]],
        "properties": {
            "ad_group_id": _field("string", "Parent Ad Group ID"),
            "name": _field("string", "Ad name", maxLength=255),
            "ad_type": _field("string", "Ad format", enum=["RESPONSIVE_SEARCH_AD", "EXPANDED_TEXT_AD", "RESPONSIVE_DISPLAY_AD"]),
            "headlines": _field("array", "Ad headlines", minItems=3, maxItems=15, items={"type": "string", "minLength": 1, "maxLength": 30}),
            "descriptions": _field("array", "Ad descriptions", minItems=2, maxItems=4, items={"type": "string", "minLength": 1, "maxLength": 90}),
            "final_url": _field("string", "Final URL", minLength=1),
            "path1": _field("string", "Display path 1", maxLength=15),
            "path2": _field("string", "Display path 2", maxLength=15),
            "responsive_search_ad": _field("object", "Responsive Search Ad payload", additionalProperties=True),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
        "conditional_rules": [
            {"id": "rsa_headlines", "if": {"ad_type": "RESPONSIVE_SEARCH_AD"},
             "required": ["headlines", "descriptions"], "message": "RESPONSIVE_SEARCH_AD requires headlines and descriptions"},
        ],
    }


def google_asset_group_schema() -> dict[str, Any]:
    asset = _field("array", "Asset references", minItems=1, items={"type": "object", "additionalProperties": True})
    return {
        "required": ["campaign_id", "name"],
        "provider_required": ["asset_group_type"],
        "properties": {
            "campaign_id": _field("string", "Parent Performance Max Campaign ID"),
            "name": _field("string", "Asset group name", maxLength=255),
            "asset_group_type": _field("string", "Asset group type", enum=GOOGLE_ASSET_GROUP_TYPES),
            "headlines": _field("array", "Text headline assets", minItems=3, maxItems=15, items={"type": "object", "additionalProperties": True}),
            "long_headlines": _field("array", "Long headline assets", minItems=1, items={"type": "object", "additionalProperties": True}),
            "descriptions": _field("array", "Description assets", minItems=2, maxItems=5, items={"type": "object", "additionalProperties": True}),
            "images": asset,
            "videos": asset,
            "logos": asset,
            "status": _field("string", "Asset group status", enum=GOOGLE_STATUSES),
        },
    }
