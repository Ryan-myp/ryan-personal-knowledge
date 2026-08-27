"""TikTok creation parameter catalog.

This is deliberately a versioned, code-owned catalog rather than a guessed
API discovery layer.  The values below are the ones already captured in the
repository's TikTok knowledge base and consumed by the current client.  A
field backed by a provider lookup is marked with ``lookup_tool`` so callers
know that its values are dynamic and must not be hard-coded here.
"""

from typing import Any, Optional


TIKTOK_OBJECTIVE_TYPES = [
    "APP_PROMOTION", "PRODUCT_SALES", "TRAFFIC", "VIDEO_VIEWS",
    "CONVERSIONS", "REACH", "LEAD_GENERATION", "ENGAGEMENT",
    "CATALOG_SALES", "SHOP_PURCHASES", "WEB_CONVERSIONS", "APP_INSTALL",
]
TIKTOK_CAMPAIGN_TYPES = ["REGULAR_CAMPAIGN", "IOS14_CAMPAIGN"]
TIKTOK_AUTOMATION_TYPES = ["MANUAL", "UPGRADED_SMART_PLUS"]
TIKTOK_BUDGET_MODES = [
    "BUDGET_MODE_DAY", "BUDGET_MODE_INFINITE",
    "BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_TOTAL",
]
TIKTOK_BUDGET_RESTRICTIONS = ["NO_LIMITATION", "DAILY_BUDGET", "LIFETIME_BUDGET"]
TIKTOK_PROMOTION_TYPES = ["APP_ANDROID", "APP_IOS", "WEBSITE", "LEAD_FORM", "CONTENT"]
TIKTOK_BID_TYPES = ["BID_TYPE_NO_BID", "BID_TYPE_CUSTOM", "BID_TYPE_MAX_CONVERSION"]
TIKTOK_BILLING_EVENTS = ["CPM", "GD", "CPV", "CPA", "OCPC", "OCPM", "CPC"]
TIKTOK_PLACEMENT_TYPES = ["PLACEMENT_TYPE_NORMAL", "PLACEMENT_TYPE_AUTOMATIC"]
TIKTOK_DEEP_BID_TYPES = ["AEO", "OCC", "ROAS"]
TIKTOK_APP_PROMOTION_TYPES = ["APP_ACQUISITION", "APP_RETARGETING"]
TIKTOK_AGE_GROUPS = [
    "AGE_13_17", "AGE_18_24", "AGE_25_34", "AGE_35_44",
    "AGE_45_54", "AGE_55_64", "AGE_65+",
]
TIKTOK_GENDERS = ["GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE"]
TIKTOK_OPERATING_SYSTEMS = ["ANDROID", "IOS"]


def _field(
    field_type: str,
    description: str,
    *,
    enum: Optional[list[Any]] = None,
    minimum: Optional[float] = None,
    items: Optional[dict[str, Any]] = None,
    **metadata: Any,
) -> dict[str, Any]:
    value: dict[str, Any] = {"type": field_type, "description": description}
    if enum is not None:
        value["enum"] = enum
    if minimum is not None:
        value["minimum"] = minimum
    if items is not None:
        value["items"] = items
    value.update(metadata)
    return value


def tiktok_campaign_schema() -> dict[str, Any]:
    return {
        "required": ["account_id", "name", "objective_type", "budget_mode", "campaign_type"],
        "provider_required": ["objective_type", "budget_mode", "campaign_type"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "name": _field("string", "Campaign name; max 60 characters"),
            "objective_type": _field(
                "string", "Campaign optimization objective", enum=TIKTOK_OBJECTIVE_TYPES,
                intent_field="objective", intent_map={
                    "sales": "PRODUCT_SALES",
                    "leads": "LEAD_GENERATION",
                    "traffic": "TRAFFIC",
                    "brand": "REACH",
                },
            ),
            "campaign_type": _field("string", "Campaign type", enum=TIKTOK_CAMPAIGN_TYPES),
            "campaign_automation_type": _field("string", "Automation mode", enum=TIKTOK_AUTOMATION_TYPES),
            "budget_restriction": _field("string", "Budget restriction", enum=TIKTOK_BUDGET_RESTRICTIONS),
            "budget_mode": _field("string", "Budget mode", enum=TIKTOK_BUDGET_MODES),
            "budget": _field("number", "Daily/lifetime budget in user currency", minimum=0),
            "daily_budget": _field("number", "Daily budget in user currency", minimum=0),
            "app_promotion_type": _field(
                "string", "App promotion mode; only for app campaigns",
                enum=TIKTOK_APP_PROMOTION_TYPES,
            ),
            "status": _field("integer", "Campaign status: 1 active, 0 paused", enum=[0, 1]),
        },
        "conditional_rules": [
            {
                "id": "daily_budget_required",
                "if": {"budget_mode": "BUDGET_MODE_DAY"},
                "required": ["daily_budget"],
                "message": "budget_mode=BUDGET_MODE_DAY requires daily_budget",
            },
            {
                "id": "total_budget_required",
                "if": {"budget_mode": "BUDGET_MODE_TOTAL"},
                "required": ["budget"],
                "message": "budget_mode=BUDGET_MODE_TOTAL requires budget",
            },
            {
                "id": "app_campaign_requires_app_mode",
                "if": {"objective_type": "APP_PROMOTION"},
                "required": ["app_promotion_type"],
                "message": "objective_type=APP_PROMOTION requires app_promotion_type",
            },
        ],
    }


def tiktok_adgroup_schema() -> dict[str, Any]:
    return {
        "required": [
            "campaign_id", "name", "promotion_type", "billing_event", "budget_mode",
            "budget", "location_ids", "placement_type", "bid_type",
        ],
        "provider_required": [
            "promotion_type", "billing_event", "budget_mode", "budget", "location_ids",
        ],
        "properties": {
            "campaign_id": _field("string", "Parent campaign ID"),
            "name": _field("string", "Ad group name; max 60 characters"),
            "promotion_type": _field("string", "Promotion destination", enum=TIKTOK_PROMOTION_TYPES),
            "app_id": _field(
                "string", "App ID returned by TikTok app lookup",
                lookup_tool="tiktok_list_apps", lookup_result_key="apps",
                selection_value_fields=["app_id", "id"],
                selection_label_fields=["app_name", "name", "display_name"],
            ),
            "landing_url": _field("string", "Website landing URL"),
            "billing_event": _field("string", "Billing event", enum=TIKTOK_BILLING_EVENTS),
            "bid_type": _field("string", "Bid mode", enum=TIKTOK_BID_TYPES),
            "bid_amount": _field("number", "Manual bid amount", minimum=0),
            "deep_bid_type": _field("string", "Deep optimization goal", enum=TIKTOK_DEEP_BID_TYPES),
            "placement_type": _field("string", "Placement mode", enum=TIKTOK_PLACEMENT_TYPES),
            "budget_mode": _field("string", "Ad group budget mode", enum=TIKTOK_BUDGET_MODES[:3]),
            "budget": _field("number", "Budget in user currency; current knowledge base minimum is 50 USD", minimum=50),
            "daily_budget": _field("number", "Daily budget in user currency", minimum=50),
            "location_ids": _field(
                "array", "Country/region IDs", items={"type": "string"},
                lookup_tool="tiktok_list_locations", lookup_result_key="locations",
                selection_value_fields=["location_id", "id", "country_code", "code"],
                selection_label_fields=["location_name", "name", "country_name", "country_code"],
            ),
            "operating_systems": _field(
                "array", "Operating systems", enum=None,
                items={"type": "string", "enum": TIKTOK_OPERATING_SYSTEMS},
            ),
            "age_groups": _field(
                "array", "Age targeting groups", items={"type": "string", "enum": TIKTOK_AGE_GROUPS},
            ),
            "gender": _field("string", "Gender targeting", enum=TIKTOK_GENDERS),
            "auto_targeting_enabled": _field("boolean", "Enable automatic targeting"),
            "targeting": _field(
                "object", "Provider targeting object; use structured fields above for known dimensions",
            ),
            # Kept for compatibility with the current client; symbolic fields
            # above are the preferred contract for new callers.
            "promote_object_type": _field("integer", "Legacy promotion type: 0 app, 1 website", enum=[0, 1]),
            "tracking_url": _field("string", "Tracking URL"),
            "status": _field("integer", "Ad group status: 1 active, 0 paused", enum=[0, 1]),
        },
        "conditional_rules": [
            {
                "id": "app_android_dependencies",
                "if": {"promotion_type": "APP_ANDROID"},
                "required": ["app_id", "deep_bid_type", "operating_systems"],
                "allowed": {"billing_event": ["OCPM"]},
                "message": "APP_ANDROID requires app_id, deep_bid_type, operating_systems and billing_event=OCPM",
            },
            {
                "id": "app_ios_dependencies",
                "if": {"promotion_type": "APP_IOS"},
                "required": ["app_id", "deep_bid_type", "operating_systems"],
                "allowed": {"billing_event": ["OCPM"]},
                "message": "APP_IOS requires app_id, deep_bid_type, operating_systems and billing_event=OCPM",
            },
            {
                "id": "website_dependencies",
                "if": {"promotion_type": "WEBSITE"},
                "required": ["landing_url"],
                "message": "WEBSITE requires landing_url",
            },
            {
                "id": "custom_bid_requires_amount",
                "if": {"bid_type": "BID_TYPE_CUSTOM"},
                "required": ["bid_amount"],
                "message": "bid_type=BID_TYPE_CUSTOM requires bid_amount",
            },
        ],
    }


def tiktok_ad_schema() -> dict[str, Any]:
    return {
        "required": ["adgroup_id", "name"],
        "provider_any_of": [["media", "creatives"]],
        "properties": {
            "adgroup_id": _field("string", "Parent ad group ID"),
            "campaign_id": _field("string", "Parent campaign ID"),
            "name": _field("string", "Ad name"),
            "landing_page_url": _field("string", "Landing page URL"),
            "conversion_id": _field("integer", "Conversion event ID", minimum=0),
            "media": _field("object", "TikTok media asset payload"),
            "creatives": _field("array", "Creative list", items={"type": "object"}),
            "text": _field("object", "Ad copy payload"),
            "status": _field("integer", "Ad status: 1 active, 0 paused", enum=[0, 1]),
        },
    }
