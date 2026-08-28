"""Meta Marketing API creation contracts owned by the Meta Capability."""

from __future__ import annotations

from typing import Any


META_OBJECTIVES = [
    "OUTCOME_SALES", "OUTCOME_LEADS", "OUTCOME_TRAFFIC", "OUTCOME_AWARENESS",
    "OUTCOME_ENGAGEMENT", "OUTCOME_APP_PROMOTION", "OUTCOME_CONVERSIONS",
    "OUTCOME_MESSAGES", "APP_INSTALLS",
    "PRODUCT_CATALOG_SALES", "CONVERSIONS", "TRAFFIC", "LINK_CLICKS",
]
META_OPTIMIZATION_GOALS = [
    "APP_INSTALLS", "OFFSITE_CONVERSIONS", "VALUE", "LINK_CLICKS",
    "LANDING_PAGE_VIEWS", "LEAD_GENERATION", "IMPRESSIONS", "REACH",
    "THRUPLAY", "POST_ENGAGEMENT", "EVENT_RESPONSES", "VIDEO_VIEWS",
    "CONVERSIONS", "LEADS", "MESSAGES", "PAGE_LIKES", "THRU_PLAY",
]
META_BILLING_EVENTS = ["IMPRESSIONS", "LINK_CLICKS", "THRUPLAY"]
META_BID_STRATEGIES = [
    "LOWEST_COST_WITHOUT_CAP", "LOWEST_COST_WITH_BID_CAP", "COST_CAP",
    "LOWEST_COST_WITH_MIN_ROAS",
]
META_SPECIAL_AD_CATEGORIES = ["NONE", "EMPLOYMENT", "HOUSING", "CREDIT"]
META_STATUS = ["ACTIVE", "PAUSED"]
META_CUSTOM_EVENT_TYPES = [
    "PURCHASE", "LEAD", "COMPLETE_REGISTRATION", "ADD_TO_CART",
    "INITIATE_CHECKOUT", "VIEW_CONTENT", "SEARCH", "SUBSCRIBE",
]


def _field(field_type: Any, description: str = "", **kwargs: Any) -> dict[str, Any]:
    value = {"type": field_type, "description": description}
    value.update(kwargs)
    return value


def _object(properties: dict[str, Any], description: str, *, additional_properties: bool = False) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": properties,
        "additionalProperties": additional_properties,
    }


def meta_targeting_schema() -> dict[str, Any]:
    """Known Meta targeting dimensions; IDs remain provider/account scoped."""
    audience_ref = _object({
        "id": _field("string", "Meta audience ID"),
        "name": _field("string", "Optional display name"),
    }, "Custom audience reference")
    return _object({
        "geo_locations": _object({
            "countries": _field("array", "ISO country codes", items={"type": "string"}),
            "regions": _field("array", "Region IDs", items=_object({"key": _field("string")}, "Region reference")),
            "cities": _field("array", "City references", items=_object({"key": _field("string")}, "City reference")),
            "location_types": _field("array", "Location semantics", items={"type": "string", "enum": ["home", "recent"]}),
        }, "Geographic targeting"),
        "age_min": _field("integer", "Minimum age", minimum=13, maximum=65),
        "age_max": _field("integer", "Maximum age", minimum=13, maximum=65),
        "genders": _field("array", "1 male, 2 female", items={"type": "integer", "enum": [1, 2]}),
        "locales": _field("array", "Locale IDs", items={"type": "integer", "minimum": 0}),
        "device_platforms": _field("array", "Device platforms", items={"type": "string", "enum": ["mobile", "desktop"]}),
        "publisher_platforms": _field("array", "Publisher platforms", items={"type": "string", "enum": ["facebook", "instagram", "audience_network", "messenger"]}),
        "facebook_positions": _field("array", "Facebook placements", items={"type": "string"}),
        "instagram_positions": _field("array", "Instagram placements", items={"type": "string"}),
        "custom_audiences": _field("array", "Included custom audiences", items=audience_ref),
        "excluded_custom_audiences": _field("array", "Excluded custom audiences", items=audience_ref),
        "flexible_spec": _field("array", "Interest/behavior groups", items={"type": "object", "additionalProperties": True}),
    }, "Meta ad set targeting")


def meta_promoted_object_schema() -> dict[str, Any]:
    return _object({
        "pixel_id": _field("string", "Meta Pixel ID"),
        "application_id": _field("string", "Meta application ID"),
        "object_store_url": _field("string", "App store URL"),
        "product_set_id": _field("string", "Catalog product set ID"),
        "page_id": _field("string", "Facebook Page ID"),
        "custom_event_type": _field("string", "Conversion event", enum=META_CUSTOM_EVENT_TYPES),
        "custom_event_str": _field("string", "Provider custom event name"),
    }, "Meta promoted object")


def meta_campaign_schema() -> dict[str, Any]:
    return {
        "required": ["account_id", "name"],
        "provider_required": ["objective", "special_ad_categories"],
        "provider_any_of": [["daily_budget", "lifetime_budget", "budget"]],
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "name": _field("string", "Campaign name", maxLength=400),
            "objective": _field(
                "string", "Campaign objective", enum=META_OBJECTIVES,
                intent_field="objective", intent_map={
                    "sales": "OUTCOME_SALES", "leads": "OUTCOME_LEADS",
                    "traffic": "OUTCOME_TRAFFIC", "brand": "OUTCOME_AWARENESS",
                },
            ),
            "buying_type": _field("string", "Buying type", enum=["AUCTION", "RESERVED"]),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
            "special_ad_categories": _field(
                ["array", "string"], "Special ad category; use NONE when not applicable",
                items={"type": "string", "enum": META_SPECIAL_AD_CATEGORIES},
            ),
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "lifetime_budget": _field("number", "Lifetime budget", minimum=0),
            "budget": _field("number", "User-facing daily budget alias", minimum=0),
            "spend_cap": _field("number", "Campaign spend cap", minimum=0),
            "start_time": _field("string", "ISO-8601 start time"),
            "end_time": _field("string", "ISO-8601 end time"),
            "catalog_id": _field("string", "Meta product catalog ID"),
            "conversion_specs": _field("array", "Conversion event specifications", items={"type": "object", "additionalProperties": True}),
            "messaging_apps": _field(
                "array", "Messaging destinations", items={"type": "string", "enum": ["MESSENGER", "WHATSAPP", "INSTAGRAM_DIRECT"]}
            ),
        },
        "conditional_rules": [
            {
                "id": "reserved_requires_lifetime_budget",
                "if": {"buying_type": "RESERVED"},
                "required": ["lifetime_budget"],
                "message": "buying_type=RESERVED requires lifetime_budget",
            },
        ],
    }


def meta_adset_schema() -> dict[str, Any]:
    return {
        "required": ["campaign_id", "name"],
        "provider_required": ["optimization_goal", "billing_event", "targeting"],
        "provider_any_of": [["daily_budget", "lifetime_budget", "budget"]],
        "properties": {
            "campaign_id": _field("string", "Parent Campaign ID"),
            "name": _field("string", "Ad Set name", maxLength=400),
            "targeting": meta_targeting_schema(),
            "optimization_goal": _field("string", "Optimization goal", enum=META_OPTIMIZATION_GOALS),
            "billing_event": _field("string", "Billing event", enum=META_BILLING_EVENTS),
            "bid_strategy": _field("string", "Bid strategy", enum=META_BID_STRATEGIES),
            "bidding_strategy": _field("string", "Bid strategy alias", enum=META_BID_STRATEGIES),
            "promoted_object": meta_promoted_object_schema(),
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "lifetime_budget": _field("number", "Lifetime budget", minimum=0),
            "budget": _field("number", "User-facing daily budget alias", minimum=0),
            "bid_amount": _field("number", "Bid amount", minimum=0),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
            "start_time": _field("string", "ISO-8601 start time"),
            "end_time": _field("string", "ISO-8601 end time"),
            "lead_gen_config": _field("object", "Instant Form configuration", additionalProperties=True),
            "product_set_id": _field("string", "Catalog product set ID"),
            "messaging_apps": _field(
                "array", "Messaging destinations", items={"type": "string", "enum": ["MESSENGER", "WHATSAPP", "INSTAGRAM_DIRECT"]}
            ),
        },
        "conditional_rules": [
            {
                "id": "conversion_goal_requires_promoted_object",
                "if": {"optimization_goal": "OFFSITE_CONVERSIONS"},
                "required": ["promoted_object"],
                "message": "OFFSITE_CONVERSIONS requires promoted_object",
            },
            {
                "id": "value_goal_requires_promoted_object",
                "if": {"optimization_goal": "VALUE"},
                "required": ["promoted_object"],
                "message": "VALUE requires promoted_object",
            },
            {
                "id": "app_goal_requires_promoted_object",
                "if": {"optimization_goal": "APP_INSTALLS"},
                "required": ["promoted_object"],
                "message": "APP_INSTALLS requires promoted_object",
            },
        ],
    }


def meta_ad_schema() -> dict[str, Any]:
    return {
        "required": ["adset_id", "name"],
        "provider_any_of": [["creative_id", "object_story_spec", "creative"]],
        "properties": {
            "adset_id": _field("string", "Parent Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "creative_id": _field("string", "Existing Creative ID"),
            "object_story_spec": _object({
                "page_id": _field("string", "Page ID"),
                "link_data": _object({
                    "link": _field("string", "Destination URL"),
                    "message": _field("string", "Primary text"),
                    "name": _field("string", "Headline"),
                    "description": _field("string", "Description"),
                    "image_hash": _field("string", "Uploaded image hash"),
                    "call_to_action": _object({
                        "type": _field("string", "Call to action type"),
                        "value": _field("object", "Call to action destination", additionalProperties=True),
                    }, "Link ad call to action"),
                }, "Link ad story"),
                "video_data": _object({
                    "video_id": _field("string", "Video ID"),
                    "message": _field("string", "Primary text"),
                    "title": _field("string", "Video title"),
                    "call_to_action": _object({
                        "type": _field("string", "Call to action type"),
                        "value": _field("object", "Call to action destination", additionalProperties=True),
                    }, "Video ad call to action"),
                }, "Video ad story"),
                "carousel_data": _field("object", "Carousel ad story", additionalProperties=True),
                "lead_gen": _field("object", "Lead generation creative", additionalProperties=True),
            }, "Meta object story specification"),
            "creative": _object({}, "Creative reference or inline payload", additional_properties=True),
            "body": _field("string", "Primary text"),
            "title": _field("string", "Headline"),
            "description": _field("string", "Description"),
            "url_tags": _field("string", "URL tracking tags"),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
        },
    }


def meta_lead_ad_schema() -> dict[str, Any]:
    """Create contract for a Meta Lead Ads Instant Form creative."""
    return {
        "required": ["adset_id", "name", "page_id", "form_id"],
        "provider_required": ["page_id", "form_id"],
        "properties": {
            "adset_id": _field("string", "Parent Meta Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "page_id": _field("string", "Facebook Page ID", minLength=1),
            "form_id": _field("string", "Published Instant Form ID", minLength=1),
            "link": _field("string", "Optional destination URL"),
            "message": _field("string", "Primary text"),
            "headline": _field("string", "Headline"),
            "description": _field("string", "Description"),
            "call_to_action_type": _field(
                "string", "Lead form CTA", enum=["SIGN_UP", "LEARN_MORE", "CONTACT_US"],
                default="SIGN_UP",
            ),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
        },
    }


def meta_ad_format_catalog() -> list[dict[str, Any]]:
    """Advertised Meta objectives/formats and their current contract depth."""
    source_document = "docs/ad-platform-hierarchy-guide-v5.md"
    return [
        {
            "format_id": "traffic",
            "category": "traffic",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_ad"],
            "dependencies": ["targeting", "optimization_goal", "link_data"],
            "supported_fields": ["OUTCOME_TRAFFIC", "LINK_CLICKS", "targeting", "object_story_spec.link_data"],
            "gaps": ["objective-specific CTA validation", "placement compatibility validation"],
            "source_document": source_document,
        },
        {
            "format_id": "conversion",
            "category": "conversion",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_ad"],
            "dependencies": ["promoted_object", "conversion_specs", "pixel_or_capi"],
            "supported_fields": ["OUTCOME_CONVERSIONS", "OFFSITE_CONVERSIONS", "CONVERSIONS", "promoted_object"],
            "gaps": ["conversion event lookup/validation", "objective-specific creative contract"],
            "source_document": source_document,
        },
        {
            "format_id": "lead",
            "category": "lead",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_ad"],
            "dependencies": ["lead_gen_config", "form_id", "page_id"],
            "supported_fields": ["OUTCOME_LEADS", "LEADS", "lead_gen_config", "lead_gen"],
            "gaps": ["Instant Form lookup/validation"],
            "source_document": source_document,
        },
        {
            "format_id": "lead.instant_form",
            "category": "lead",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["meta_create_lead_ad"],
            "payload_adapter": "MetaAPIClient.create_lead_ad",
            "dependencies": ["ad_set", "page_id", "form_id"],
            "supported_fields": ["page_id", "form_id", "link", "message", "headline", "description", "call_to_action_type"],
            "gaps": ["Instant Form lookup/validation", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "engagement",
            "category": "engagement",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_ad"],
            "dependencies": ["post_id_or_story", "targeting", "optimization_goal"],
            "supported_fields": ["OUTCOME_ENGAGEMENT", "POST_ENGAGEMENT", "VIDEO_VIEWS"],
            "gaps": ["Page Likes/Video Views specialized creative validation"],
            "source_document": source_document,
        },
        {
            "format_id": "link_image",
            "category": "traffic",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["meta_create_ad"],
            "payload_adapter": "MetaAPIClient.create_ad",
            "dependencies": ["adset", "page_id", "link_data"],
            "supported_fields": ["link", "message", "name", "description", "image_hash", "call_to_action"],
            "gaps": ["live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "link_video",
            "category": "engagement",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["meta_create_ad"],
            "payload_adapter": "MetaAPIClient.create_ad",
            "dependencies": ["adset", "page_id", "video_data"],
            "supported_fields": ["video_id", "message", "title", "call_to_action"],
            "gaps": ["live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "catalog",
            "category": "catalog",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_ad"],
            "dependencies": ["catalog_id", "product_set_id", "catalog creative"],
            "gaps": ["catalog/product set lookup", "dedicated catalog creative builder", "dynamic product rules"],
            "source_document": source_document,
        },
        {
            "format_id": "catalog.dynamic_product",
            "category": "catalog",
            "resource_type": "ad_set",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["catalog_id", "product_set_id", "dynamic product rules"],
            "gaps": ["catalog/product set lookup", "dedicated catalog creative Tool"],
            "source_document": source_document,
        },
        {
            "format_id": "messaging",
            "category": "messaging",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_ad"],
            "dependencies": ["messaging_apps", "SEND_MESSAGE CTA", "page_or_business_messaging_identity"],
            "supported_fields": ["OUTCOME_MESSAGES", "MESSAGES", "messaging_apps", "call_to_action"],
            "gaps": ["messaging destination validation", "dedicated messaging creative builder"],
            "source_document": source_document,
        },
        {
            "format_id": "messaging.click_to_message",
            "category": "messaging",
            "resource_type": "ad",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_ad"],
            "dependencies": ["page_id", "messaging_apps", "SEND_MESSAGE CTA"],
            "supported_fields": ["object_story_spec.link_data", "messaging_apps"],
            "gaps": ["messaging destination validation", "dedicated messaging creative builder"],
            "source_document": source_document,
        },
    ]
