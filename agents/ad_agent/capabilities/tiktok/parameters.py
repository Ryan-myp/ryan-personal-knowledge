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
TIKTOK_PLACEMENTS = ["PLACEMENT_TIKTOK", "PLACEMENT_PANGLE", "PLACEMENT_GLOBAL_APP_BUNDLE"]
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
TIKTOK_AD_FORMATS = ["SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL", "SPARK_AD"]
TIKTOK_AUDIENCE_TYPES = ["CUSTOM", "CUSTOM_AUDIENCE", "LOOKALIKE", "LOOKALIKE_AUDIENCE"]
TIKTOK_AUDIENCE_CALCULATE_TYPES = [
    "EMAIL_SHA256", "FIRST_MD5", "FIRST_SHA256", "GAID_MD5", "GAID_SHA256",
    "IDFA_MD5", "IDFA_SHA256", "MAID_MD5", "MAID_SHA256", "MULTIPLE_TYPES",
    "PHONE_SHA256",
]
TIKTOK_AUDIENCE_ACTIONS = ["REPLACE", "APPEND", "REMOVE"]
TIKTOK_AUDIENCE_SUB_TYPES = ["NORMAL", "REACH_FREQUENCY"]
TIKTOK_MEDIA_UPLOAD_TYPES = [
    "UPLOAD_BY_FILE", "UPLOAD_BY_URL", "UPLOAD_BY_FILE_ID", "UPLOAD_BY_VIDEO_ID",
]
TIKTOK_KEYWORD_LANGUAGES = [
    "fr", "id", "it", "ja", "ms", "ar", "vi", "en", "ru", "es",
    "th", "tr", "hi", "zh", "de", "ko",
]
TIKTOK_INTEREST_KEYWORD_MODES = ["FUZZ_MATCH", "SEMANTIC_RECOMMEND"]
TIKTOK_INTEREST_AUDIENCE_TYPES = ["GENERAL_INTEREST", "PURCHASE_INTENTION"]


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


def tiktok_audience_schema() -> dict[str, Any]:
    """Schema for TikTok's customer-file custom audience creation."""
    return {
        "required": ["account_id", "name", "calculate_type", "file_paths"],
        "provider_required": ["name", "calculate_type", "file_paths"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "name": _field("string", "Audience name", minLength=1),
            "calculate_type": _field(
                "string", "Encryption type matching the uploaded file",
                enum=TIKTOK_AUDIENCE_CALCULATE_TYPES,
            ),
            "file_paths": _field(
                "array", "TikTok uploaded file paths", minItems=1, maxItems=500,
                items={"type": "string", "minLength": 16, "maxLength": 16},
            ),
            "retention_in_days": _field("integer", "Retention window in days", minimum=1, maximum=365),
            "audience_sub_type": _field("string", "Audience subtype", enum=TIKTOK_AUDIENCE_SUB_TYPES),
            "audience_enhancement": _field("boolean", "Enable audience enhancement"),
        },
    }


def tiktok_audience_update_schema() -> dict[str, Any]:
    """Schema for TikTok's official custom-audience update endpoint."""
    return {
        "required": ["account_id", "audience_id", "updates"],
        "provider_required": ["updates"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "audience_id": _field("string", "TikTok custom audience ID"),
            "updates": _field(
                "object", "Audience name or encrypted file update",
                properties={
                    "custom_audience_name": _field(
                        "string", "New audience name", minLength=1, maxLength=128,
                    ),
                    "file_paths": _field(
                        "array", "TikTok uploaded file paths", minItems=1, maxItems=50,
                        items={"type": "string", "minLength": 16, "maxLength": 16},
                    ),
                    "action": _field(
                        "string", "File operation", enum=TIKTOK_AUDIENCE_ACTIONS,
                    ),
                    "audience_enhancement": _field(
                        "boolean", "Enable audience enhancement",
                    ),
                    "audience_sub_type": _field(
                        "string", "Audience subtype", enum=["REACH_FREQUENCY"],
                    ),
                    "context_info": _field(
                        "object", "TikTok request context", additionalProperties=False,
                    ),
                },
                additionalProperties=False,
            ),
        },
    }


def tiktok_audience_file_upload_schema() -> dict[str, Any]:
    """Schema for the multipart upload step preceding audience create/update."""
    return {
        "required": ["account_id", "file_path", "calculate_type"],
        "provider_required": ["file_path", "calculate_type"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "file_path": _field(
                "string", "Local CSV/TXT file path; contents are never put in model context",
                minLength=1,
            ),
            "calculate_type": _field(
                "string", "Encryption type matching the uploaded file",
                enum=TIKTOK_AUDIENCE_CALCULATE_TYPES,
            ),
            "file_name": _field("string", "Optional upload filename", maxLength=255),
        },
    }


def tiktok_image_upload_schema() -> dict[str, Any]:
    """Schema for TikTok advertiser image Asset Library upload/binding."""
    return {
        "required": ["account_id"],
        "provider_required": [],
        "provider_exactly_one_of": [["file_path", "image_url", "file_id"]],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "file_path": _field("string", "Local image path; only used with UPLOAD_BY_FILE"),
            "image_url": _field("string", "Provider-reachable image URL; only used with UPLOAD_BY_URL"),
            "file_id": _field("string", "TikTok file repository ID; only used with UPLOAD_BY_FILE_ID"),
            "file_name": _field("string", "Optional Asset Library filename", maxLength=100),
            "upload_type": _field("string", "TikTok upload mode", enum=TIKTOK_MEDIA_UPLOAD_TYPES),
        },
    }


def tiktok_video_upload_schema() -> dict[str, Any]:
    """Schema for TikTok advertiser video Asset Library upload/binding."""
    return {
        "required": ["account_id"],
        "provider_required": [],
        "provider_exactly_one_of": [["file_path", "video_url", "video_id", "file_id"]],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "file_path": _field("string", "Local video path; only used with UPLOAD_BY_FILE"),
            "video_url": _field("string", "Provider-reachable video URL; only used with UPLOAD_BY_URL"),
            "video_id": _field("string", "Existing TikTok video ID to bind to this advertiser"),
            "file_id": _field("string", "TikTok file repository ID; only used with UPLOAD_BY_FILE_ID"),
            "file_name": _field("string", "Optional Asset Library filename", maxLength=100),
            "upload_type": _field("string", "TikTok upload mode", enum=TIKTOK_MEDIA_UPLOAD_TYPES),
            "flaw_detect": _field("boolean", "Enable video flaw detection"),
            "auto_fix_enabled": _field("boolean", "Automatically fix detected video flaws"),
            "auto_bind_enabled": _field("boolean", "Bind an automatically fixed video"),
            "is_third_party": _field("boolean", "Whether the video is a third-party asset"),
        },
    }


def _tiktok_pixel_event_properties() -> dict[str, Any]:
    """Shared event fields from TikTok v1.3 Pixel Track contracts."""
    return {
        "event": _field(
            "string", "TikTok web conversion event name", minLength=1, maxLength=100,
        ),
        "event_id": _field(
            "string", "Stable event ID used for Pixel/Events API deduplication",
            minLength=1, maxLength=200,
        ),
        "timestamp": _field(
            "string", "Event timestamp in ISO 8601 format", minLength=1, maxLength=64,
        ),
        "context": _field(
            "object", "Browser, page and user matching context",
            properties={
                "ip": _field("string", "Non-hashed public browser IP"),
                "user_agent": _field("string", "Non-hashed browser user agent"),
                "page": _field(
                    "object", "Page where the event occurred",
                    properties={
                        "url": _field("string", "Page URL"),
                        "referrer": _field("string", "Page referrer"),
                    },
                    additionalProperties=False,
                ),
                "user": _field(
                    "object", "TikTok user matching identifiers",
                    properties={
                        "email": _field("string", "SHA-256 hashed email"),
                        "phone_number": _field("string", "SHA-256 hashed phone number"),
                        "external_id": _field("string", "SHA-256 hashed advertiser user ID"),
                        "ttp": _field("string", "TikTok _ttp cookie value"),
                    },
                    additionalProperties=False,
                ),
                "ad": _field(
                    "object", "TikTok ad click context",
                    properties={"callback": _field("string", "TikTok callback value")},
                    additionalProperties=False,
                ),
            },
            additionalProperties=False,
        ),
        "properties": _field(
            "object", "Event value, currency, contents and custom properties",
            properties={
                "value": _field("number", "Order or conversion value"),
                "currency": _field("string", "ISO 4217 currency code", maxLength=3),
                "description": _field("string", "Item or page description"),
                "query": _field("string", "Search query or coupon code"),
                "contents": _field(
                    "array", "Items related to the web event",
                    items={"type": "object", "additionalProperties": True},
                    maxItems=100,
                ),
            },
            additionalProperties=True,
        ),
    }


def tiktok_pixel_event_schema() -> dict[str, Any]:
    """Schema for TikTok's v1.3 single Pixel Track endpoint."""
    return {
        "required": ["account_id", "pixel_id", "event"],
        "provider_required": ["pixel_id", "event"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "pixel_id": _field("string", "TikTok Pixel code", minLength=1, maxLength=128),
            **_tiktok_pixel_event_properties(),
        },
    }


def tiktok_pixel_batch_schema() -> dict[str, Any]:
    """Schema for TikTok's v1.3 batch Pixel Track endpoint."""
    event_properties = _tiktok_pixel_event_properties()
    return {
        "required": ["account_id", "pixel_id", "events"],
        "provider_required": ["pixel_id", "events"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "pixel_id": _field("string", "TikTok Pixel code", minLength=1, maxLength=128),
            "events": _field(
                "array", "One or more TikTok web conversion events (max 50)",
                items={
                    "type": "object",
                    "required": ["event"],
                    "properties": event_properties,
                    "additionalProperties": False,
                },
                minItems=1, maxItems=50,
            ),
        },
    }


def tiktok_creative_portfolio_schema() -> dict[str, Any]:
    """Schema for TikTok v1.3 Creative Portfolio creation."""
    return {
        "required": ["account_id"],
        "provider_required": ["account_id"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "creative_portfolio_type": _field(
                "string", "Portfolio type",
                enum=["CTA", "CARD", "PREMIUM_BADGE", "STICKER", "DOWNLOAD_CARD", "PRODUCT_CARD"],
            ),
            "portfolio_content": _field(
                "array", "Portfolio content records",
                items={"type": "object", "additionalProperties": True},
                minItems=1, maxItems=100,
            ),
        },
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
            "optimization_goal": _field(
                "string", "Ad group optimization goal", enum=TIKTOK_DEEP_BID_TYPES,
            ),
            "conversion_id": _field(
                "integer", "Conversion event ID returned by TikTok lookup",
                minimum=0, lookup_tool="tiktok_list_conversions",
                lookup_result_key="conversions",
                selection_value_fields=["conversion_id", "id"],
                selection_label_fields=["conversion_name", "name", "event_name"],
            ),
            "optimization_event": _field(
                "string", "Provider conversion event used for optimization",
            ),
            "pixel_id": _field(
                "string", "TikTok Pixel ID for landing-page tracking",
            ),
            "placement_type": _field("string", "Placement mode", enum=TIKTOK_PLACEMENT_TYPES),
            "placements": _field(
                "array", "Apps where the ad is delivered",
                items={"type": "string", "enum": TIKTOK_PLACEMENTS},
            ),
            "promotion_website_type": _field(
                "string", "TikTok native Instant Page type",
                enum=["TIKTOK_NATIVE_PAGE"],
            ),
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
            "tracking_url": _field("string", "Tracking URL"),
            "status": _field("integer", "Ad group status: 1 active, 0 paused", enum=[0, 1]),
            "catalog_id": _field("string", "TikTok catalog ID"),
            "product_set_id": _field("string", "TikTok product set ID"),
            "audience_ids": _field("array", "Included audience IDs", items={"type": "string"}),
            "excluded_audience_ids": _field("array", "Excluded audience IDs", items={"type": "string"}),
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
            {
                "id": "normal_placement_requires_apps",
                "if": {"placement_type": "PLACEMENT_TYPE_NORMAL"},
                "required": ["placements"],
                "message": "placement_type=PLACEMENT_TYPE_NORMAL requires placements",
            },
        ],
    }


def tiktok_targeting_update_schema() -> dict[str, Any]:
    """Schema for independent, lookup-aware TikTok Ad Group targeting updates."""
    return {
        "required": ["account_id", "campaign_id", "adgroup_id", "updates"],
        "provider_required": ["campaign_id", "adgroup_id", "updates"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "campaign_id": _field("string", "Parent campaign ID"),
            "adgroup_id": _field("string", "Target Ad Group ID"),
            "updates": _field(
                "object", "Structured Ad Group targeting fields",
                properties=tiktok_targeting_fields(), additionalProperties=False,
            ),
        },
    }


def tiktok_targeting_fields() -> dict[str, Any]:
    """Nested targeting properties shared by the targeting Tool contract."""
    audience_ref = {
        "type": "array", "items": {"type": "string"},
        "lookup_tool": "tiktok_list_audiences", "lookup_result_key": "audiences",
        "selection_value_fields": ["audience_id", "id"],
        "selection_label_fields": ["name", "audience_id", "id"],
    }
    return {
        "location_ids": _field(
            "array", "Selected location IDs",
            items={"type": "string"}, lookup_tool="tiktok_list_locations",
            lookup_result_key="locations",
            selection_value_fields=["location_id", "id", "country_code", "code"],
            selection_label_fields=["location_name", "name", "country_name", "country_code"],
        ),
        "operating_systems": _field(
            "array", "Operating systems",
            items={"type": "string", "enum": TIKTOK_OPERATING_SYSTEMS},
        ),
        "age_groups": _field(
            "array", "Age targeting groups",
            items={"type": "string", "enum": TIKTOK_AGE_GROUPS},
        ),
        "gender": _field("string", "Gender targeting", enum=TIKTOK_GENDERS),
        "auto_targeting_enabled": _field("boolean", "Enable automatic targeting"),
        "audience_ids": audience_ref,
        "excluded_audience_ids": audience_ref,
        "interest_category_ids": _field(
            "array", "Interest category IDs",
            items={"type": "string"}, lookup_tool="tiktok_list_interest_categories",
            lookup_result_key="interest_categories",
            selection_value_fields=["interest_category_id", "category_id", "id"],
            selection_label_fields=["interest_category_name", "category_name", "name", "id"],
        ),
        "device_ids": _field(
            "array", "Device IDs",
            items={"type": "string"}, lookup_tool="tiktok_list_devices",
            lookup_result_key="devices",
            selection_value_fields=["device_id", "id"],
            selection_label_fields=["device_name", "name", "id"],
        ),
        "carrier_ids": _field(
            "array", "Carrier IDs",
            items={"type": "string"}, lookup_tool="tiktok_list_carriers",
            lookup_result_key="carriers",
            selection_value_fields=["carrier_id", "id"],
            selection_label_fields=["carrier_name", "name", "id"],
        ),
        "browser_ids": _field(
            "array", "Browser IDs",
            items={"type": "string"}, lookup_tool="tiktok_list_browsers",
            lookup_result_key="browsers",
            selection_value_fields=["browser_id", "id"],
            selection_label_fields=["browser_name", "name", "id"],
        ),
    }


def tiktok_ad_schema() -> dict[str, Any]:
    return {
        "required": ["adgroup_id", "name"],
        "provider_required": ["campaign_id"],
        "provider_any_of": [["media", "creatives"]],
        "properties": {
            "adgroup_id": _field("string", "Parent ad group ID"),
            "campaign_id": _field("string", "Parent campaign ID"),
            "name": _field("string", "Ad name"),
            "landing_page_url": _field("string", "Landing page URL"),
            "conversion_id": _field(
                "integer", "Conversion event ID", minimum=0,
                lookup_tool="tiktok_list_conversions", lookup_result_key="conversions",
                selection_value_fields=["conversion_id", "id"],
                selection_label_fields=["conversion_name", "name", "event_name"],
            ),
            "ad_format": _field("string", "Ad format", enum=TIKTOK_AD_FORMATS),
            # TikTok accepts a single media object in some versions and a
            # list of assets in others; keep both shapes explicit so a
            # provider field is not silently discarded by closed validation.
            "media": _field(["array", "object"], "TikTok media asset payload", items={"type": "object"}),
            "creatives": _field("array", "Creative list", items={"type": "object"}),
            "text": _field("object", "Ad copy payload", additionalProperties=True),
            "video_id": _field("string", "Video asset ID"),
            "image_ids": _field("array", "Image asset IDs", items={"type": "string"}),
            "spark_post_id": _field("string", "Spark post ID"),
            "page_id": _field("string", "TikTok Instant Page or Instant Form page ID", minLength=1),
            "catalog_id": _field("string", "TikTok catalog ID"),
            "product_set_id": _field("string", "TikTok product set ID"),
            "call_to_action": _field("string", "Call to action"),
            "identity_id": _field("string", "TikTok identity ID"),
            "status": _field("integer", "Ad status: 1 active, 0 paused", enum=[0, 1]),
        },
    }


def tiktok_lead_ad_schema() -> dict[str, Any]:
    """Create contract for a TikTok Lead Generation Instant Form ad.

    TikTok represents an Instant Form as an Instant Page in the ad-create
    contract. The page itself is managed by the Instant Page Editor SDK.
    """
    return {
        "required": ["campaign_id", "adgroup_id", "name", "page_id"],
        "provider_required": ["campaign_id", "page_id"],
        "provider_any_of": [["media", "creatives"]],
        "properties": {
            "campaign_id": _field("string", "Parent campaign ID"),
            "adgroup_id": _field("string", "Parent ad group ID"),
            "name": _field("string", "Ad name"),
            "page_id": _field("string", "TikTok Instant Page / Instant Form page ID", minLength=1),
            "landing_page_url": _field("string", "Optional fallback landing URL"),
            "tracking_url": _field("string", "Tracking URL"),
            "conversion_id": _field(
                "integer", "Conversion event ID", minimum=0,
                lookup_tool="tiktok_list_conversions", lookup_result_key="conversions",
                selection_value_fields=["conversion_id", "id"],
                selection_label_fields=["conversion_name", "name", "event_name"],
            ),
            "media": _field("array", "Lead ad media assets", items={"type": "object"}),
            "creatives": _field("array", "Lead ad creative list", items={"type": "object"}),
            "text": _field("object", "Ad copy payload", additionalProperties=True),
            "call_to_action": _field("string", "Lead form call to action"),
            "status": _field("integer", "Ad status: 1 active, 0 paused", enum=[0, 1]),
            "operation_status": _field(
                "string", "Provider creation status", enum=["ENABLE", "DISABLE"],
            ),
            "tracking_pixel_id": _field("integer", "TikTok tracking Pixel ID", minimum=0),
        },
    }


def tiktok_app_ad_schema() -> dict[str, Any]:
    """Create contract for a TikTok App Promotion install/event ad."""
    return {
        "required": [
            "campaign_id", "adgroup_id", "name", "app_id", "promotion_type",
            "operating_systems",
        ],
        "provider_required": ["campaign_id", "app_id", "promotion_type"],
        "provider_any_of": [["media", "creatives"]],
        "properties": {
            "campaign_id": _field("string", "Parent campaign ID"),
            "adgroup_id": _field("string", "Parent ad group ID"),
            "name": _field("string", "Ad name"),
            "app_id": _field(
                "string", "App ID returned by TikTok app lookup", minLength=1,
                lookup_tool="tiktok_list_apps", lookup_result_key="apps",
                selection_value_fields=["app_id", "id"],
                selection_label_fields=["app_name", "name", "display_name"],
            ),
            "promotion_type": _field(
                "string", "App platform promotion type", enum=["APP_ANDROID", "APP_IOS"],
            ),
            "operating_systems": _field(
                "array", "Target operating systems",
                items={"type": "string", "enum": TIKTOK_OPERATING_SYSTEMS},
            ),
            "app_promotion_type": _field(
                "string", "App acquisition or retargeting mode",
                enum=TIKTOK_APP_PROMOTION_TYPES,
            ),
            "deep_link": _field("string", "Optional in-app deep link"),
            "landing_page_url": _field("string", "Optional app store fallback URL"),
            "tracking_url": _field("string", "Tracking URL"),
            "conversion_id": _field(
                "integer", "In-app conversion event ID", minimum=0,
                lookup_tool="tiktok_list_conversions", lookup_result_key="conversions",
                selection_value_fields=["conversion_id", "id"],
                selection_label_fields=["conversion_name", "name", "event_name"],
            ),
            "media": _field("array", "App ad media assets", items={"type": "object"}),
            "creatives": _field("array", "App ad creative list", items={"type": "object"}),
            "text": _field("object", "Ad copy payload", additionalProperties=True),
            "call_to_action": _field("string", "App ad call to action"),
            "identity_id": _field("string", "TikTok identity ID"),
            "status": _field("integer", "Ad status: 1 active, 0 paused", enum=[0, 1]),
        },
    }


def tiktok_ad_format_catalog() -> list[dict[str, Any]]:
    """Advertised TikTok formats and their current contract depth."""
    source_document = "docs/ad-platform-hierarchy-guide-v5.md"
    return [
        {
            "format_id": "product_sales",
            "category": "product_sales",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_ad"],
            "dependencies": ["PRODUCT_SALES", "ad_group", "product_or_landing_destination"],
            "supported_fields": ["objective_type", "budget_mode", "promotion_type", "targeting", "media"],
            "gaps": ["Shop/product-specific resource builders", "product feed validation"],
            "source_document": source_document,
        },
        {
            "format_id": "product_sales.shop",
            "category": "product_sales",
            "resource_type": "ad_group",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_campaign", "tiktok_create_adgroup"],
            "dependencies": ["PRODUCT_SALES", "catalog_id", "product_set_id"],
            "supported_fields": ["catalog_id", "product_set_id", "promotion_type"],
            "gaps": ["Shop/product-specific resource builders", "product feed validation"],
            "source_document": source_document,
        },
        {
            "format_id": "spark",
            "category": "spark",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["tiktok_spark_ads_create"],
            "payload_adapter": "TikTokAPIClient.create_spark_ad",
            "dependencies": ["campaign", "ad_group", "spark_post_id", "creator authorization"],
            "supported_fields": ["spark_post_id"],
            "gaps": ["live mutation approval", "authorization lookup"],
            "source_document": source_document,
        },
        {
            "format_id": "single_video",
            "category": "product_sales",
            "resource_type": "ad",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_ad"],
            "dependencies": ["ad_group", "video_id_or_media", "text"],
            "supported_fields": ["ad_format", "video_id", "media", "text"],
            "gaps": ["dedicated video payload validation"],
            "source_document": source_document,
        },
        {
            "format_id": "single_image",
            "category": "product_sales",
            "resource_type": "ad",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_ad"],
            "dependencies": ["ad_group", "image_ids_or_media", "text"],
            "supported_fields": ["ad_format", "image_ids", "media", "text"],
            "gaps": ["dedicated image payload validation"],
            "source_document": source_document,
        },
        {
            "format_id": "carousel",
            "category": "product_sales",
            "resource_type": "ad",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_ad"],
            "dependencies": ["ad_group", "image_ids_or_media", "carousel card rules"],
            "supported_fields": ["ad_format", "image_ids", "media", "text"],
            "gaps": ["carousel card schema and validation"],
            "source_document": source_document,
        },
        {
            "format_id": "lead",
            "category": "lead",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_lead_ad"],
            "payload_adapter": "TikTokAPIClient.create_lead_ad",
            "dependencies": ["LEAD_GENERATION", "TIKTOK_NATIVE_PAGE", "page_id"],
            "supported_fields": ["objective_type", "page_id", "media"],
            "gaps": ["Instant Page Editor SDK integration", "page lookup/validation", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "lead.instant_form",
            "category": "lead",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["tiktok_create_adgroup", "tiktok_create_lead_ad"],
            "payload_adapter": "TikTokAPIClient.create_lead_ad",
            "dependencies": ["LEAD_GENERATION", "TIKTOK_NATIVE_PAGE", "page_id"],
            "supported_fields": ["page_id"],
            "gaps": ["Instant Page Editor SDK integration", "page lookup/validation", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "app",
            "category": "app",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_app_ad"],
            "payload_adapter": "TikTokAPIClient.create_app_ad",
            "dependencies": ["APP_PROMOTION", "app_id", "operating_systems", "deep_bid_type"],
            "supported_fields": ["objective_type", "app_promotion_type", "app_id", "operating_systems"],
            "gaps": ["app event/deep link validation", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "app.install",
            "category": "app",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["tiktok_create_adgroup", "tiktok_create_app_ad"],
            "payload_adapter": "TikTokAPIClient.create_app_ad",
            "dependencies": ["APP_PROMOTION", "APP_ANDROID_or_APP_IOS", "app_id"],
            "supported_fields": ["promotion_type", "app_id", "operating_systems"],
            "gaps": ["app event/deep link validation", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "brand",
            "category": "brand",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_ad"],
            "dependencies": ["REACH_or_VIDEO_VIEWS", "brand creative", "placement"],
            "supported_fields": ["objective_type", "budget_mode", "media", "targeting"],
            "gaps": ["brand takeover/TopView-specific contract", "CPM/CPV compatibility validation"],
            "source_document": source_document,
        },
        {
            "format_id": "brand.topview",
            "category": "brand",
            "resource_type": "ad_group",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["BRAND_AWARENESS", "TOPVIEW", "video"],
            "gaps": ["TopView-specific Tool and provider contract"],
            "source_document": source_document,
        },
        {
            "format_id": "brand.takeover",
            "category": "brand",
            "resource_type": "ad_group",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["BRAND_AWARENESS", "BRAND_TAKEOVER", "video_or_image"],
            "gaps": ["Brand Takeover-specific Tool and provider contract"],
            "source_document": source_document,
        },
    ]
