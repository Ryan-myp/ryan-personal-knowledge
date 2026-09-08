"""Provider-owned update payload contracts.

The Runtime owns the lifecycle and safety gates, while each provider owns the
fields that may be changed on a resource.  Keeping these contracts beside the
Capabilities makes a new Skill/Tool additive: it can publish its own schema
without teaching the shared Runtime provider-specific rules.
"""

from typing import Any


def _field(field_type: Any, description: str = "", **kwargs: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"type": field_type}
    if description:
        value["description"] = description
    value.update(kwargs)
    return value


def _object(properties: dict[str, Any], description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": properties,
        "additionalProperties": False,
    }


def _with_lifecycle_defaults(schema: dict[str, Any]) -> dict[str, Any]:
    """Publish provider-neutral intent defaults as Tool metadata.

    The wire value is still normalized by the nested status field's
    provider-owned ``intent_status_map``.  Runtime only applies this metadata
    generically and never owns pause/resume semantics.
    """
    schema["intent_defaults"] = {
        "pause_campaign": {"status": "PAUSED"},
        "resume_campaign": {"status": "ACTIVE"},
        "cross_channel_batch_pause": {"status": "PAUSED"},
        "cross_channel_batch_resume": {"status": "ACTIVE"},
    }
    return schema


def meta_updates(resource_type: str) -> dict[str, Any]:
    common = {
        "name": _field("string", "Resource name"),
        "status": _field(
            "string", "Delivery status", enum=["ACTIVE", "PAUSED"],
            intent_status_field="status",
            intent_status_map={
                "ACTIVE": "ACTIVE", "ENABLED": "ACTIVE", "PAUSED": "PAUSED",
            },
        ),
    }
    if resource_type == "campaign":
        common.update({
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "budget": _field("number", "Budget alias", minimum=0),
        })
    elif resource_type == "adset":
        common.update({
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "bid_amount": _field("number", "Bid amount", minimum=0),
            "optimization_goal": _field("string", "Optimization goal", enum=[
                "APP_INSTALLS", "OFFSITE_CONVERSIONS", "VALUE", "LINK_CLICKS",
                "LANDING_PAGE_VIEWS", "LEAD_GENERATION", "IMPRESSIONS", "REACH",
                "THRUPLAY",
            ]),
            "billing_event": _field("string", "Billing event", enum=[
                "IMPRESSIONS", "LINK_CLICKS", "THRUPLAY",
            ]),
            "bidding_strategy": _field("string", "Bidding strategy", enum=[
                "LOWEST_COST_WITHOUT_CAP", "LOWEST_COST_WITH_BID_CAP",
                "COST_CAP", "LOWEST_COST_WITH_MIN_ROAS",
            ]),
            "targeting": _field("object", "Meta targeting object"),
        })
    elif resource_type == "ad":
        common.update({
            "creative": _field("object", "Creative payload"),
            "creative_id": _field("string", "Existing creative ID"),
            "url_tags": _field("string", "URL tracking tags"),
        })
    return _with_lifecycle_defaults(
        _object(common, f"Allowed Meta {resource_type} update fields")
    )


def google_updates(resource_type: str) -> dict[str, Any]:
    common = {
        "name": _field("string", "Resource name"),
        "status": _field(
            "string", "Resource status", enum=["ENABLED", "PAUSED", "REMOVED"],
            intent_status_field="status",
            intent_status_map={
                "ACTIVE": "ENABLED", "ENABLED": "ENABLED", "PAUSED": "PAUSED",
            },
        ),
    }
    if resource_type == "campaign":
        common.update({
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "budget": _field("number", "Budget alias", minimum=0),
        })
    elif resource_type == "ad_group":
        common.update({
            "cpc_bid": _field("number", "CPC bid", minimum=0),
            "type": _field("string", "Ad group type", enum=[
                "SEARCH_STANDARD", "SEARCH_DYNAMIC_ADS", "DISPLAY_STANDARD",
            ]),
        })
    elif resource_type == "ad":
        common.update({
            "headlines": _field("array", "Headlines", items={"type": "string"}),
            "descriptions": _field("array", "Descriptions", items={"type": "string"}),
            "final_url": _field("string", "Final URL"),
            "path1": _field("string", "Display path 1"),
            "path2": _field("string", "Display path 2"),
        })
    elif resource_type == "asset_group":
        common.update({
            "headlines": _field("array", "Headlines", items={"type": "string"}),
            "descriptions": _field("array", "Descriptions", items={"type": "string"}),
            "images": _field("array", "Image assets"),
            "videos": _field("array", "Video assets"),
        })
    return _with_lifecycle_defaults(
        _object(common, f"Allowed Google Ads {resource_type} update fields")
    )


def tiktok_updates(resource_type: str) -> dict[str, Any]:
    status_field = {
        "campaign": "campaign_group_status",
        "adgroup": "ad_group_status",
        "ad": "status",
    }.get(resource_type, "status")
    common = {
        "name": _field("string", "Resource name"),
        "status": _field(
            "integer", "Compatibility status", enum=[0, 1],
            intent_status_field=status_field,
            intent_status_map={"ACTIVE": 1, "ENABLED": 1, "PAUSED": 0},
        ),
    }
    if resource_type == "campaign":
        common.update({
            "campaign_group_status": _field("integer", "Campaign status", enum=[0, 1]),
            "objective_type": _field("string", "Optimization objective", enum=[
                "APP_PROMOTION", "PRODUCT_SALES", "TRAFFIC", "VIDEO_VIEWS",
                "CONVERSIONS", "REACH", "LEAD_GENERATION", "ENGAGEMENT",
                "CATALOG_SALES", "SHOP_PURCHASES", "WEB_CONVERSIONS", "APP_INSTALL",
            ]),
            "budget_mode": _field("string", "Budget mode", enum=[
                "BUDGET_MODE_DAY", "BUDGET_MODE_INFINITE",
                "BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_TOTAL",
            ]),
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "budget": _field("number", "Budget alias", minimum=0),
        })
    elif resource_type == "adgroup":
        common.update({
            "ad_group_status": _field("integer", "Ad group status", enum=[0, 1]),
            "promotion_type": _field("string", "Promotion destination", enum=[
                "APP_ANDROID", "APP_IOS", "WEBSITE", "LEAD_FORM", "CONTENT",
            ]),
            "billing_event": _field("string", "Billing event", enum=[
                "CPM", "GD", "CPV", "CPA", "OCPC", "OCPM", "CPC",
            ]),
            "bid_type": _field("string", "Bid mode", enum=[
                "BID_TYPE_NO_BID", "BID_TYPE_CUSTOM", "BID_TYPE_MAX_CONVERSION",
            ]),
            "bid_amount": _field("number", "Bid amount", minimum=0),
            "placement_type": _field("string", "Placement mode", enum=[
                "PLACEMENT_TYPE_NORMAL", "PLACEMENT_TYPE_AUTOMATIC",
            ]),
            "deep_bid_type": _field("string", "Deep optimization goal", enum=["AEO", "OCC", "ROAS"]),
            "budget_mode": _field("string", "Budget mode", enum=[
                "BUDGET_MODE_DAY", "BUDGET_MODE_INFINITE",
                "BUDGET_MODE_DYNAMIC_DAILY_BUDGET",
            ]),
            "budget": _field("number", "Budget", minimum=0),
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "app_id": _field("string", "Selected App ID"),
            "landing_url": _field("string", "Website landing URL"),
            "location_ids": _field("array", "Selected location IDs", items={"type": "string"}),
            "operating_systems": _field("array", "Operating systems", items={"type": "string", "enum": ["ANDROID", "IOS"]}),
            "age_groups": _field("array", "Age groups", items={"type": "string"}),
            "gender": _field("string", "Gender", enum=["GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE"]),
            "auto_targeting_enabled": _field("boolean", "Automatic targeting"),
        })
    elif resource_type == "ad":
        common.update({
            "landing_page_url": _field("string", "Landing page URL"),
            "text": _field("object", "Ad text payload"),
            "status": _field("integer", "Ad status", enum=[0, 1]),
        })
    return _with_lifecycle_defaults(
        _object(common, f"Allowed TikTok {resource_type} update fields")
    )


def tiktok_smart_plus_updates(resource_type: str) -> dict[str, Any]:
    """Closed update contract for TikTok's current Upgraded Smart+ API."""
    common = {
        "name": _field("string", "Resource name"),
        "status": _field("string", "Compatibility status; normalized to operation_status", enum=["ACTIVE", "ENABLED", "PAUSED", "DISABLE", "ENABLE"]),
        "operation_status": _field(
            "string", "Smart+ delivery status", enum=["DISABLE", "ENABLE"],
        ),
    }
    if resource_type == "campaign":
        common.update({
            "budget_mode": _field("string", "Campaign budget mode"),
            "budget": _field("number", "Campaign budget", minimum=0),
            "budget_auto_adjust_strategy": _field("string", "Automatic budget adjustment"),
        })
    elif resource_type == "adgroup":
        common.update({
            "promotion_type": _field("string", "Optimization location"),
            "optimization_goal": _field("string", "Optimization goal"),
            "bid_type": _field("string", "Bid mode"),
            "bid_price": _field("number", "Bid price", minimum=0),
            "conversion_bid_price": _field("number", "Conversion bid price", minimum=0),
            "billing_event": _field("string", "Billing event"),
            "budget_mode": _field("string", "Ad group budget mode"),
            "budget": _field("number", "Ad group budget", minimum=0),
            "schedule_start_time": _field("string", "Schedule start time"),
            "schedule_end_time": _field("string", "Schedule end time"),
            "location_ids": _field("array", "Target locations", items={"type": "string"}),
            "saved_audience_id": _field("string", "Saved audience ID"),
        })
    elif resource_type == "ad":
        common.update({
            "ad_text": _field("string", "Primary ad text"),
            "landing_page_url": _field("string", "Landing page URL"),
            "call_to_action_id": _field("string", "Call to action ID"),
            "dark_post_status": _field("string", "Dark post status"),
        })
    else:
        raise ValueError(f"Unsupported Smart+ update resource: {resource_type}")
    return _object(common, f"Allowed TikTok Smart+ {resource_type} update fields")


def dv360_updates(resource_type: str) -> dict[str, Any]:
    # DV360 write adapters are intentionally dry-run only.  Keep the shape
    # bounded for obvious metadata fields, while allowing provider payload
    # objects where the current client has no verified field-level contract.
    common = {
        "name": _field("string", "Resource name"),
        "status": _field(
            "string", "Resource status", enum=["DRAFT", "ACTIVE", "PAUSED"],
            intent_status_field="status",
            intent_status_map={"ACTIVE": "ACTIVE", "PAUSED": "PAUSED", "ENABLED": "ACTIVE"},
        ),
        "start_date": _field("string", "Start date"),
        "end_date": _field("string", "End date"),
    }
    if resource_type == "line_item":
        common.update({
            "type": _field("string", "Line item type"),
            "goal": _field("object", "DV360 goal object"),
            "targeting": _field("object", "DV360 targeting object"),
            "budget": _field("number", "Budget", minimum=0),
        })
    elif resource_type == "io":
        common.update({
            "budget": _field("number", "Budget", minimum=0),
            "spend_cap_micros": _field("integer", "Spend cap in micros", minimum=0),
        })
    return _with_lifecycle_defaults(
        _object(common, f"Allowed DV360 {resource_type} update fields")
    )
