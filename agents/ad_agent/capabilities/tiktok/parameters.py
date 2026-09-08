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
TIKTOK_PROMOTION_TYPES = [
    "APP_ANDROID", "APP_IOS", "WEBSITE", "WEBSITE_OR_DISPLAY", "LEAD_FORM", "CATALOG",
]
TIKTOK_PLACEMENTS = ["PLACEMENT_TIKTOK", "PLACEMENT_PANGLE", "PLACEMENT_GLOBAL_APP_BUNDLE"]
TIKTOK_BID_TYPES = ["BID_TYPE_NO_BID", "BID_TYPE_CUSTOM", "BID_TYPE_MAX_CONVERSION"]
TIKTOK_BILLING_EVENTS = ["CPM", "GD", "CPV", "CPA", "OCPC", "OCPM", "CPC"]
TIKTOK_PLACEMENT_TYPES = ["PLACEMENT_TYPE_NORMAL", "PLACEMENT_TYPE_AUTOMATIC"]
TIKTOK_DEEP_BID_TYPES = ["AEO", "OCC", "ROAS"]
TIKTOK_OPTIMIZATION_GOALS = [
    "CLICK", "CONVERSION", "INSTALL", "IN_APP_EVENT", "REACH", "VIDEO_VIEW",
    "VALUE", "LEAD_GENERATION", "ENGAGEMENT", "PRODUCT_SALES", "WEB_CONVERSIONS",
    "SHOP_PURCHASES", "CATALOG_SALES",
]
TIKTOK_PACING_MODES = ["PACING_MODE_SMOOTH", "PACING_MODE_FAST"]
TIKTOK_SCHEDULE_TYPES = ["SCHEDULE_START_END", "SCHEDULE_FROM_NOW"]
TIKTOK_BRAND_SAFETY_TYPES = [
    "NO_BRAND_SAFETY", "STANDARD_INVENTORY", "LIMITED_INVENTORY", "THIRD_PARTY",
]
TIKTOK_PRODUCT_SOURCES = ["UNSET", "CATALOG", "STORE", "SHOWCASE"]
TIKTOK_SHOPPING_ADS_TYPES = ["UNSET", "VIDEO", "LIVE", "CATALOG_LISTING_ADS"]
TIKTOK_APP_PROMOTION_TYPES = ["APP_ACQUISITION", "APP_RETARGETING"]
TIKTOK_AGE_GROUPS = [
    "AGE_13_17", "AGE_18_24", "AGE_25_34", "AGE_35_44",
    "AGE_45_54", "AGE_55_64", "AGE_65+",
]
TIKTOK_GENDERS = ["GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE"]
TIKTOK_OPERATING_SYSTEMS = ["ANDROID", "IOS"]
TIKTOK_AD_FORMATS = ["SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL", "SPARK_AD"]
TIKTOK_CREATIVE_TYPES = ["SINGLE_IMAGE", "SINGLE_VIDEO", "LIVE_CONTENT"]
TIKTOK_OPERATION_STATUSES = ["ENABLE", "DISABLE"]
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
TIKTOK_IDENTITY_TYPES = ["CUSTOMIZED_USER", "AUTH_CODE", "TT_USER"]
TIKTOK_PIXEL_OBJECT_TYPES = ["WEBSITE", "APP"]

# Current v1.3 all-in-one Spark Ads surface.  This is intentionally separate
# from the legacy campaign/ad-group objective catalog: the provider exposes a
# different request shape and the Capability must not accidentally send these
# objectives through the deprecated three-step chain.
TIKTOK_ALL_IN_ONE_SPARK_OBJECTIVES = [
    "REACH", "VIDEO_VIEWS", "ENGAGEMENT",
]
TIKTOK_ALL_IN_ONE_SPARK_GOALS = [
    "REACH", "ENGAGED_VIEW", "FOLLOWERS", "PAGE_VISIT",
]

# TikTok's current Upgraded Smart+ API uses a three-resource workflow.  The
# user-facing Traffic/Sales aliases are intentionally kept in the provider
# catalog: the API represents web Traffic and Sales as WEB_CONVERSIONS with
# different ad-group destinations/optimization goals.
TIKTOK_SMART_PLUS_OBJECTIVES = [
    "APP_PROMOTION", "WEB_CONVERSIONS", "LEAD_GENERATION",
    "TRAFFIC", "SALES", "PRODUCT_SALES",
]
TIKTOK_SMART_PLUS_OPTIMIZATION_GOALS = [
    "CLICK", "INSTALL", "IN_APP_EVENT", "VALUE", "CONVERT",
    "TRAFFIC_LANDING_PAGE_VIEW", "CONVERSATION", "LEAD_GENERATION",
]


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


def _ui_when(field: str, *values: str) -> dict[str, Any]:
    """Declare a provider-field applicability rule for creation cards."""
    return {"ui_visible_when": {"field": field, "in": list(values)}}


def _ui_equals(field: str, value: str) -> dict[str, Any]:
    return {"ui_visible_when": {"field": field, "equals": value}}


def _tiktok_media_field(description: str) -> dict[str, Any]:
    """Advanced media payload with typed asset alternatives.

    The common ``video_id``/``image_ids`` fields remain the preferred UI
    controls.  This shape is for provider versions that require a media
    object and keeps its asset sources discoverable instead of presenting an
    unbounded JSON blob as the only option.
    """
    return _field(
        "array", description,
        minItems=1,
        items={
            "type": "object",
            "properties": {
                "type": _field("string", "Media type", enum=["IMAGE", "VIDEO"]),
                "image_id": _field(
                    "string", "Uploaded TikTok image ID", minLength=1,
                    lookup_tool="tiktok_list_images", lookup_result_key="images",
                    selection_value_fields=["image_id", "id"],
                    selection_label_fields=["file_name", "image_name", "name", "id"],
                ),
                "video_id": _field(
                    "string", "Uploaded TikTok video ID", minLength=1,
                    lookup_tool="tiktok_list_videos", lookup_result_key="videos",
                    selection_value_fields=["video_id", "id"],
                    selection_label_fields=["file_name", "video_name", "name", "id"],
                ),
                "image_url": _field("string", "Provider-accessible image URL", minLength=1),
                "video_url": _field("string", "Provider-accessible video URL", minLength=1),
            },
            "additionalProperties": True,
        },
        manual_entry={
            "title": "高级素材对象",
            "instructions": "优先选择 video_id/image_ids 或先上传素材；仅当 TikTok 版本要求额外 media 字段时填写此高级对象。URL 必须可被 TikTok 访问。",
            "source": "provider_media_payload",
        },
        presentation="asset_picker",
    )


def _tiktok_creatives_field(description: str) -> dict[str, Any]:
    """Advanced creative list with the stable fields used by ad/create."""
    return _field(
        "array", description,
        minItems=1,
        items={
            "type": "object",
            "properties": {
                "creative_type": _field("string", "Creative type", enum=TIKTOK_CREATIVE_TYPES),
                "ad_text": _field("string", "Primary ad text", minLength=1, maxLength=100),
                "display_name": _field("string", "Creative display name", maxLength=512),
                "call_to_action": _field("string", "Call to action"),
                "identity_id": _field(
                    "string", "TikTok identity ID", minLength=1,
                    lookup_tool="tiktok_list_identities", lookup_result_key="identities",
                    selection_value_fields=["identity_id", "id"],
                    selection_label_fields=["display_name", "name", "id"],
                ),
            },
            "additionalProperties": True,
        },
        manual_entry={
            "title": "高级 Creative 列表",
            "instructions": "优先使用页面上的素材、文案和身份选择；只有 Provider 版本需要额外 creative 字段时才编辑此列表。",
            "source": "provider_creative_payload",
        },
        presentation="object_editor",
    )


def _tiktok_text_field() -> dict[str, Any]:
    return _field(
        "object", "Ad copy payload",
        properties={
            "ad_text": _field("string", "Primary ad text", minLength=1, maxLength=100),
            "display_name": _field("string", "Creative display name", maxLength=512),
            "call_to_action": _field("string", "Call to action"),
        },
        additionalProperties=True,
        presentation="object_editor",
    )


def tiktok_campaign_schema() -> dict[str, Any]:
    return {
        "required": ["account_id", "name", "objective_type", "budget_mode", "campaign_type"],
        "provider_required": ["objective_type", "budget_mode", "campaign_type"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "name": _field("string", "Campaign name; max 60 characters"),
            "objective_type": _field(
                "string", "Campaign optimization objective", enum=TIKTOK_OBJECTIVE_TYPES,
                option_aliases={
                    "APP_PROMOTION": ["app promotion", "app conversion", "app install", "App 转化", "App 广告", "应用推广", "应用转化", "应用安装"],
                    "PRODUCT_SALES": ["product sales", "product ad", "商品销售", "商品广告"],
                    "TRAFFIC": ["traffic campaign", "website traffic", "流量广告", "网站流量"],
                    "VIDEO_VIEWS": ["video views", "video view", "视频观看", "视频播放"],
                    "REACH": ["reach campaign", "brand awareness", "覆盖", "品牌曝光"],
                    "LEAD_GENERATION": ["lead generation", "lead gen", "潜在客户", "线索获客", "表单获客"],
                    "ENGAGEMENT": ["engagement campaign", "互动广告"],
                    "APP_INSTALL": ["app install campaign", "应用安装广告"],
                },
                intent_field="objective", intent_map={
                    "sales": "PRODUCT_SALES",
                    "leads": "LEAD_GENERATION",
                    "traffic": "TRAFFIC",
                    "brand": "REACH",
                },
            ),
            "campaign_type": _field(
                "string", "Campaign type", enum=TIKTOK_CAMPAIGN_TYPES,
                option_aliases={
                    "REGULAR_CAMPAIGN": ["regular campaign", "standard campaign", "常规广告系列", "普通广告系列"],
                    "IOS14_CAMPAIGN": ["ios14 campaign", "ios 14 campaign", "iOS14 广告系列"],
                },
            ),
            "campaign_automation_type": _field("string", "Automation mode", enum=TIKTOK_AUTOMATION_TYPES),
            "budget_restriction": _field("string", "Budget restriction", enum=TIKTOK_BUDGET_RESTRICTIONS),
            "budget_mode": _field(
                "string", "Budget mode", enum=TIKTOK_BUDGET_MODES,
                option_aliases={
                    "BUDGET_MODE_DAY": ["daily budget", "day budget", "日预算", "每天预算"],
                    "BUDGET_MODE_TOTAL": ["lifetime budget", "total budget", "总预算", "生命周期预算"],
                },
            ),
            "budget": _field(
                "number", "Daily/lifetime budget in user currency", minimum=0,
                **_ui_equals("budget_mode", "BUDGET_MODE_TOTAL"),
            ),
            "daily_budget": _field(
                "number", "Daily budget in user currency", minimum=0,
                # The common ParsedIntent carries a generic budget value;
                # this provider field is the wire-level daily-budget variant.
                intent_aliases=["budget"],
                **_ui_equals("budget_mode", "BUDGET_MODE_DAY"),
            ),
            "app_promotion_type": _field(
                "string", "App promotion mode; only for app campaigns",
                enum=TIKTOK_APP_PROMOTION_TYPES,
                option_aliases={
                    "APP_ACQUISITION": ["app acquisition", "app user acquisition", "应用获客", "应用拉新"],
                    "APP_RETARGETING": ["app retargeting", "应用再营销", "应用召回"],
                },
                **_ui_equals("objective_type", "APP_PROMOTION"),
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


def tiktok_pixel_schema() -> dict[str, Any]:
    """Schema for TikTok Pixel list/get/create/update operations."""
    pixel_id = _field(
        "string", "TikTok Pixel ID/code", minLength=1, maxLength=128,
        lookup_tool="tiktok_list_pixels", lookup_result_key="pixels",
        selection_value_fields=["pixel_id", "id", "code"],
        selection_label_fields=["name", "pixel_id", "id"],
    )
    return {
        "create_required": ["account_id", "name", "object_type"],
        "update_required": ["account_id", "pixel_id", "updates"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "pixel_id": pixel_id,
            "pixel_ids": _field(
                "array", "Optional Pixel IDs to retrieve", minItems=1, maxItems=100,
                items={"type": "string", "minLength": 1, "maxLength": 128},
            ),
            "limit": _field("integer", "Maximum number of Pixels", minimum=1),
            "name": _field("string", "Pixel name", minLength=1, maxLength=128),
            "object_type": _field(
                "string", "Pixel source type", enum=TIKTOK_PIXEL_OBJECT_TYPES,
            ),
            "tracking_url": _field("string", "Website URL associated with the Pixel", maxLength=2048),
            "updates": {
                "type": "object",
                "description": "Supported TikTok Pixel update fields",
                "properties": {
                    "name": _field("string", "Pixel name", minLength=1, maxLength=128),
                },
                "additionalProperties": False,
            },
        },
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
                presentation="advanced_json",
                manual_entry={
                    "title": "Creative Portfolio 内容",
                    "instructions": "内容字段由 creative_portfolio_type 决定（如 CTA、CARD、PRODUCT_CARD），请按 TikTok 当前版本返回的对象结构填写；未知字段不会被系统猜测。",
                    "source": "tiktok_creative_portfolio_payload",
                },
            ),
        },
    }


def tiktok_creative_portfolio_get_schema() -> dict[str, Any]:
    """Schema for reading one TikTok Creative Portfolio."""
    return {
        "required": ["account_id", "creative_portfolio_id"],
        "provider_required": ["creative_portfolio_id"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "creative_portfolio_id": _field(
                "string", "TikTok Creative Portfolio ID", minLength=1, maxLength=128,
            ),
        },
    }


def tiktok_creative_portfolio_preview_schema() -> dict[str, Any]:
    """Schema for creating a TikTok Creative Portfolio preview."""
    return {
        "required": ["account_id", "creative_portfolio_id"],
        "provider_required": ["creative_portfolio_id"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "creative_portfolio_id": _field(
                "string", "TikTok Creative Portfolio ID", minLength=1, maxLength=128,
            ),
            "preview_type": _field(
                "string", "Preview type supported by TikTok", enum=["CARD"],
            ),
        },
    }


def tiktok_identity_create_schema() -> dict[str, Any]:
    """Schema for TikTok v1.3 customized identity creation."""
    return {
        "required": ["account_id", "display_name", "image_uri"],
        "provider_required": ["account_id", "display_name", "image_uri"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "display_name": _field("string", "Customized identity display name", minLength=1, maxLength=100),
            "image_uri": _field("string", "Uploaded TikTok avatar image ID", minLength=1, maxLength=128),
        },
    }


def tiktok_identity_list_schema() -> dict[str, Any]:
    """Schema for TikTok v1.3 advertiser identity lookup."""
    return {
        "required": ["account_id"],
        "provider_required": ["account_id"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "identity_id": _field("string", "TikTok identity ID", minLength=1, maxLength=128),
            "identity_type": _field("string", "Identity type filter", enum=TIKTOK_IDENTITY_TYPES),
            "page": _field("integer", "Page number", minimum=1),
            "limit": _field("integer", "Page size", minimum=1, maximum=100),
        },
    }


def tiktok_identity_video_info_schema() -> dict[str, Any]:
    """Schema for TikTok owned-post information lookup by identity."""
    return {
        "required": ["account_id", "identity_type", "identity_id", "item_id"],
        "provider_required": ["account_id", "identity_type", "identity_id", "item_id"],
        "properties": {
            "account_id": _field("string", "TikTok advertiser ID"),
            "identity_type": _field("string", "Identity type", enum=["AUTH_CODE", "TT_USER"]),
            "identity_id": _field("string", "TikTok identity ID", minLength=1, maxLength=128),
            "item_id": _field("string", "TikTok post ID", minLength=1, maxLength=128),
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
            "schedule_type", "schedule_start_time",
        ],
        "properties": {
            "campaign_id": _field("string", "Parent campaign ID"),
            "name": _field("string", "Ad group name; max 60 characters"),
            "promotion_type": _field(
                "string", "Promotion destination", enum=TIKTOK_PROMOTION_TYPES,
                option_aliases={
                    "APP_ANDROID": ["android", "android app", "android application", "安卓", "安卓应用"],
                    "APP_IOS": ["ios", "ios app", "ios application", "苹果", "苹果应用"],
                    "WEBSITE": ["website", "网站"],
                    "WEBSITE_OR_DISPLAY": ["website or display", "网站或展示"],
                    "LEAD_FORM": ["lead form", "表单"],
                    "CATALOG": ["catalog", "商品目录"],
                },
            ),
            "app_id": _field(
                "string", "App ID returned by TikTok app lookup",
                lookup_tool="tiktok_list_apps", lookup_result_key="apps",
                selection_value_fields=["app_id", "id"],
                selection_label_fields=["app_name", "name", "display_name"],
                **_ui_when("promotion_type", "APP_ANDROID", "APP_IOS"),
            ),
            "landing_url": _field(
                "string", "Website landing URL",
                **_ui_equals("promotion_type", "WEBSITE"),
            ),
            "billing_event": _field("string", "Billing event", enum=TIKTOK_BILLING_EVENTS),
            "bid_type": _field("string", "Bid mode", enum=TIKTOK_BID_TYPES),
            "bid_amount": _field(
                "number", "Manual bid amount", minimum=0,
                **_ui_equals("bid_type", "BID_TYPE_CUSTOM"),
            ),
            "bid_price": _field(
                "number", "Provider bid price; required for custom bid strategies", minimum=0,
                **_ui_equals("bid_type", "BID_TYPE_CUSTOM"),
            ),
            "conversion_bid_price": _field(
                "number", "Target cost per conversion for OCPM custom bidding", minimum=0,
                **{"ui_visible_when": {"all": [
                    {"field": "bid_type", "equals": "BID_TYPE_CUSTOM"},
                    {"field": "billing_event", "equals": "OCPM"},
                ]}},
            ),
            "deep_cpa_bid": _field(
                "number", "Deep CPA bid", minimum=0,
                **_ui_when("deep_bid_type", "AEO", "OCC"),
            ),
            "roas_bid": _field(
                "number", "ROAS target for value optimization", minimum=0,
                **_ui_equals("deep_bid_type", "ROAS"),
            ),
            "deep_bid_type": _field(
                "string", "Deep optimization goal", enum=TIKTOK_DEEP_BID_TYPES,
                **_ui_when("promotion_type", "APP_ANDROID", "APP_IOS"),
            ),
            "optimization_goal": _field(
                "string", "Ad group optimization goal", enum=TIKTOK_OPTIMIZATION_GOALS,
                option_aliases={
                    "INSTALL": ["install", "app installs", "应用安装", "安装量", "优化安装"],
                    "IN_APP_EVENT": ["in app event", "in-app event", "应用内事件"],
                    "CONVERSION": ["conversion", "conversions", "转化"],
                    "CLICK": ["click", "clicks", "点击"],
                    "REACH": ["reach", "覆盖"],
                    "VIDEO_VIEW": ["video view", "video views", "视频观看"],
                    "LEAD_GENERATION": ["lead generation", "潜在客户", "线索"],
                },
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
                manual_entry={
                    "title": "优化事件",
                    "instructions": "请填写 TikTok Pixel/Events API 中已配置的事件名称；如账号支持事件查询，请先从转化列表确认。",
                    "source": "provider_conversion_event",
                },
            ),
            "pixel_id": _field(
                "string", "TikTok Pixel ID for landing-page tracking",
                lookup_tool="tiktok_list_pixels", lookup_result_key="pixels",
                selection_value_fields=["pixel_id", "id", "code"],
                selection_label_fields=["pixel_name", "name", "display_name", "id"],
                **_ui_when("promotion_type", "WEBSITE", "CATALOG"),
            ),
            "placement_type": _field("string", "Placement mode", enum=TIKTOK_PLACEMENT_TYPES),
            "placements": _field(
                "array", "Apps where the ad is delivered",
                items={"type": "string", "enum": TIKTOK_PLACEMENTS},
            ),
            "promotion_website_type": _field(
                "string", "TikTok native Instant Page type",
                enum=["TIKTOK_NATIVE_PAGE"],
                **_ui_equals("promotion_type", "WEBSITE"),
            ),
            "budget_mode": _field("string", "Ad group budget mode", enum=TIKTOK_BUDGET_MODES[:3]),
            "budget_optmize_on": _field("boolean", "Enable Campaign Budget Optimization"),
            "budget": _field(
                "number",
                "Budget in user currency; current knowledge base minimum is 50 USD",
                minimum=50,
                # TikTok's ad-group endpoint calls the wire field ``budget``
                # even when the business request supplies a daily budget.
                # Keep this semantic alias provider-owned so Core/Runtime do
                # not grow a TikTok-specific budget branch.
                input_aliases=["daily_budget"],
            ),
            "daily_budget": _field(
                "number", "Daily budget in user currency", minimum=50,
                # The common ParsedIntent carries a generic budget value;
                # this provider field is the wire-level daily-budget variant.
                intent_aliases=["budget"],
                ui_hidden=True,
            ),
            "location_ids": _field(
                "array", "Country/region IDs", items={"type": "string"},
                # TikTok's supported v1.3 source is the contextual
                # ``tool/region`` API. It must be queried after the campaign
                # objective and placements are known; Runtime passes those
                # dependencies through lookup_context.
                lookup_tool="tiktok_list_regions", lookup_result_key="regions",
                lookup_dependencies=[
                    {"input_field": "placements", "value_path": "placements", "label": "投放版位"},
                    {"input_field": "objective_type", "value_path": "objective_type", "label": "推广目标"},
                ],
                lookup_defaults={
                    "placements": ["PLACEMENT_TIKTOK"],
                    "level_range": "TO_COUNTRY",
                },
                selection_value_fields=["location_id", "id", "country_code", "code"],
                selection_label_fields=["location_name", "name", "country_name", "country_code"],
            ),
            "operating_systems": _field(
                "array", "Operating systems", enum=None,
                option_aliases={
                    "ANDROID": ["android", "安卓"],
                    "IOS": ["ios", "iOS", "苹果"],
                },
                items={"type": "string", "enum": TIKTOK_OPERATING_SYSTEMS},
            ),
            "age_groups": _field(
                "array", "Age targeting groups", items={"type": "string", "enum": TIKTOK_AGE_GROUPS},
            ),
            "gender": _field("string", "Gender targeting", enum=TIKTOK_GENDERS),
            "auto_targeting_enabled": _field("boolean", "Enable automatic targeting"),
            "targeting": _field(
                "object",
                "Provider targeting object; select known dimensions below or use an advanced provider field",
                properties=tiktok_targeting_fields(), additionalProperties=True,
            ),
            "tracking_url": _field("string", "Tracking URL"),
            "status": _field("integer", "Ad group status: 1 active, 0 paused", enum=[0, 1]),
            "catalog_id": _field(
                "string", "TikTok catalog ID",
                lookup_tool="tiktok_list_catalogs", lookup_result_key="catalogs",
                selection_value_fields=["catalog_id", "id"],
                selection_label_fields=["catalog_name", "name", "id"],
                **_ui_equals("promotion_type", "CATALOG"),
            ),
            "product_set_id": _field(
                "string", "TikTok product set ID",
                lookup_tool="tiktok_list_product_sets", lookup_result_key="product_sets",
                selection_value_fields=["product_set_id", "id"],
                selection_label_fields=["product_set_name", "name", "id"],
                **_ui_equals("promotion_type", "CATALOG"),
            ),
            "brand_safety_type": _field(
                "string", "TikTok brand safety type",
                lookup_tool="tiktok_list_brand_safety", lookup_result_key="brand_safety",
            ),
            "brand_safety_partner": _field(
                "string", "Brand safety verification partner",
                enum=["IAS", "OPEN_SLATE"],
            ),
            "audience_ids": _field(
                "array", "Included audience IDs",
                items={"type": "string", "minLength": 1},
                lookup_tool="tiktok_list_audiences", lookup_result_key="audiences",
                selection_value_fields=["audience_id", "id"],
                selection_label_fields=["audience_name", "name", "id"],
            ),
            "excluded_audience_ids": _field(
                "array", "Excluded audience IDs",
                items={"type": "string", "minLength": 1},
                lookup_tool="tiktok_list_audiences", lookup_result_key="audiences",
                selection_value_fields=["audience_id", "id"],
                selection_label_fields=["audience_name", "name", "id"],
            ),
            "interest_category_ids": _field(
                "array", "Interest category IDs", items={"type": "string"},
                lookup_tool="tiktok_list_interest_categories", lookup_result_key="interest_categories",
                selection_value_fields=["interest_category_id", "category_id", "id"],
                selection_label_fields=["interest_category_name", "category_name", "name", "id"],
            ),
            "interest_keyword_ids": _field(
                "array", "Interest keyword IDs; values depend on the account and market",
                items={"type": "string", "minLength": 1},
                manual_entry={
                    "title": "兴趣关键词 ID",
                    "instructions": "当前没有独立的关键词目录接口；请从 TikTok Ads Manager 或 Provider 返回结果复制关键词 ID。",
                    "source": "provider_targeting_identifier",
                },
            ),
            "interest_keywords": _field(
                "array", "Interest keyword values",
                items={"type": "string", "minLength": 1},
                manual_entry={
                    "title": "兴趣关键词",
                    "instructions": "请输入要匹配的关键词；关键词是否可用由 TikTok 账号、地区和语言限制决定。",
                    "source": "provider_targeting_keyword",
                },
            ),
            "purchase_intention_keyword_ids": _field(
                "array", "Purchase intention keyword IDs",
                items={"type": "string", "minLength": 1},
                manual_entry={
                    "title": "购买意向关键词 ID",
                    "instructions": "当前没有独立的购买意向关键词目录接口；请复制 TikTok 返回或 Ads Manager 中的 ID。",
                    "source": "provider_targeting_identifier",
                },
            ),
            "device_model_ids": _field(
                "array", "Device model IDs", items={"type": "string"},
                lookup_tool="tiktok_list_device_models", lookup_result_key="device_models",
                selection_value_fields=["device_id", "device_model_id", "id"],
                selection_label_fields=["device_name", "device_model_name", "name", "id"],
            ),
            "languages": _field(
                "array", "Language targeting values", items={"type": "string"},
                lookup_tool="tiktok_list_languages", lookup_result_key="languages",
            ),
            "network_types": _field(
                "array", "Network types; values depend on the TikTok account and market",
                items={"type": "string", "minLength": 1},
                manual_entry={
                    "title": "网络类型",
                    "instructions": "TikTok 当前没有稳定的通用网络类型目录接口；请从账户可用定向选项中选择或复制值。",
                    "source": "provider_targeting_option",
                },
            ),
            "min_android_version": _field("string", "Minimum Android version"),
            "min_ios_version": _field("string", "Minimum iOS version"),
            "ios14_targeting": _field(
                "string", "iOS 14 targeting mode",
                enum=["UNSET", "IOS14_MINUS", "IOS14_PLUS"],
            ),
            "device_price_ranges": _field(
                "array", "Device price range values", items={"type": "integer"},
                manual_entry={
                    "title": "设备价格区间",
                    "instructions": "设备价格区间由 TikTok 市场和账户配置决定；当前没有独立目录接口，请按 Provider 支持的数值填写。",
                    "source": "provider_targeting_option",
                },
            ),
            "contextual_tag_ids": _field(
                "array", "Contextual targeting tag IDs", items={"type": "string", "minLength": 1},
                manual_entry={
                    "title": "上下文标签 ID",
                    "instructions": "当前没有独立的上下文标签目录接口；请从 TikTok 可用定向选项复制标签 ID。",
                    "source": "provider_targeting_identifier",
                },
            ),
            "targeting_expansion": _field(
                "object", "Targeting expansion advanced settings",
                additionalProperties=True, presentation="advanced_json",
                manual_entry={
                    "title": "TikTok 定向扩展高级配置",
                    "instructions": "定向扩展字段会随 TikTok objective、市场和 API 版本变化；优先使用上方已声明的定向字段，仅在拿到当前版本 Provider payload 时粘贴对象。",
                    "source": "tiktok_targeting_expansion_payload",
                },
            ),
            "household_income": _field("string", "Household income targeting value"),
            "spending_power": _field("string", "Spending power targeting value"),
            "blocked_pangle_app_ids": _field("array", "Blocked Pangle app IDs", items={"type": "string"}),
            "pacing": _field("string", "Budget pacing mode", enum=TIKTOK_PACING_MODES),
            "schedule_type": _field("string", "Ad group schedule mode", enum=TIKTOK_SCHEDULE_TYPES),
            "schedule_start_time": _field("string", "Scheduled start time"),
            "schedule_end_time": _field("string", "Scheduled end time"),
            "dayparting": _field("string", "Dayparting schedule"),
            "frequency": _field("integer", "Frequency cap", minimum=1),
            "frequency_schedule": _field("integer", "Frequency cap schedule", minimum=1),
            "product_source": _field(
                "string", "Shopping product source", enum=TIKTOK_PRODUCT_SOURCES,
                **_ui_equals("promotion_type", "CATALOG"),
            ),
            "shopping_ads_type": _field(
                "string", "Shopping ads type", enum=TIKTOK_SHOPPING_ADS_TYPES,
                **_ui_equals("promotion_type", "CATALOG"),
            ),
            "shopping_ads_retargeting_type": _field(
                "string", "Shopping ads retargeting type",
                manual_entry={
                    "title": "商品再营销类型",
                    "instructions": "可选值受 TikTok 商品广告版本和账号配置影响；请从 Provider 可用选项中选择或复制。",
                    "source": "provider_shopping_option",
                },
                **_ui_equals("promotion_type", "CATALOG"),
            ),
            "shopping_ads_retargeting_actions_days": _field(
                "integer", "Shopping ads retargeting lookback days", minimum=0,
                **_ui_equals("promotion_type", "CATALOG"),
            ),
            "store_id": _field(
                "string", "TikTok Shop or Storefront ID", minLength=1,
                manual_entry={
                    "title": "TikTok Shop / Storefront ID",
                    "instructions": "当前没有通用 Shop 列表接口；请从 TikTok Shop/Business Center 复制店铺 ID。",
                    "source": "provider_store_identifier",
                },
                **_ui_equals("product_source", "STORE"),
            ),
            "is_hfss": _field("boolean", "Whether the product is high fat, salt or sugar"),
        },
        "conditional_rules": [
            {
                "id": "app_android_dependencies",
                "if": {"promotion_type": "APP_ANDROID"},
                "required": ["app_id", "deep_bid_type", "operating_systems"],
                "allowed": {
                    "billing_event": ["OCPM"],
                    "optimization_goal": ["INSTALL", "IN_APP_EVENT", "CONVERSION"],
                    "operating_systems": ["ANDROID"],
                },
                "message": "APP_ANDROID requires app_id, deep_bid_type, operating_systems and billing_event=OCPM",
            },
            {
                "id": "app_ios_dependencies",
                "if": {"promotion_type": "APP_IOS"},
                "required": ["app_id", "deep_bid_type", "operating_systems"],
                "allowed": {
                    "billing_event": ["OCPM"],
                    "optimization_goal": ["INSTALL", "IN_APP_EVENT", "CONVERSION"],
                    "operating_systems": ["IOS"],
                },
                "message": "APP_IOS requires app_id, deep_bid_type, operating_systems and billing_event=OCPM",
            },
            {
                "id": "lead_form_dependencies",
                "if": {"promotion_type": "LEAD_FORM"},
                "allowed": {
                    "optimization_goal": ["LEAD_GENERATION"],
                    "billing_event": ["OCPM", "CPM"],
                },
                "message": "LEAD_FORM requires optimization_goal=LEAD_GENERATION and billing_event=OCPM or CPM",
            },
            {
                "id": "website_dependencies",
                "if": {"promotion_type": {"in": ["WEBSITE", "WEBSITE_OR_DISPLAY"]}},
                "required": ["landing_url"],
                "message": "WEBSITE requires landing_url",
            },
            {
                "id": "schedule_end_time_required",
                "if": {"schedule_type": "SCHEDULE_START_END"},
                "required": ["schedule_end_time"],
                "message": "schedule_type=SCHEDULE_START_END requires schedule_end_time",
            },
            {
                "id": "reach_frequency_cap_required",
                "if": {"optimization_goal": "REACH"},
                "required": ["frequency", "frequency_schedule"],
                "allowed": {"pacing": ["PACING_MODE_SMOOTH"]},
                "message": "REACH requires frequency, frequency_schedule and smooth pacing",
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
            {
                "id": "catalog_promotion_requires_product_selection",
                "if": {"promotion_type": "CATALOG"},
                "required": ["catalog_id", "product_set_id"],
                "message": "promotion_type=CATALOG requires catalog_id and product_set_id",
            },
            {
                "id": "ocpm_custom_bid_requires_conversion_bid_price",
                "if": {"bid_type": "BID_TYPE_CUSTOM", "billing_event": "OCPM"},
                "required": ["conversion_bid_price"],
                "message": "OCPM with BID_TYPE_CUSTOM requires conversion_bid_price",
            },
            {
                "id": "third_party_brand_safety_requires_partner",
                "if": {"brand_safety_type": "THIRD_PARTY"},
                "required": ["brand_safety_partner"],
                "message": "brand_safety_type=THIRD_PARTY requires brand_safety_partner",
            },
            {
                "id": "ios14_targeting_requires_min_ios_version",
                "if": {"ios14_targeting": "IOS14_PLUS"},
                "required": ["min_ios_version"],
                "message": "ios14_targeting=IOS14_PLUS requires min_ios_version",
            },
            {
                "id": "click_optimization_billing",
                "if": {"optimization_goal": "CLICK"},
                "allowed": {"billing_event": ["CPC"]},
                "message": "CLICK optimization requires billing_event=CPC",
            },
            {
                "id": "conversion_optimization_billing",
                "if": {"optimization_goal": {"in": [
                    "INSTALL", "IN_APP_EVENT", "CONVERSION", "WEB_CONVERSIONS",
                ]}},
                "allowed": {"billing_event": ["OCPM"]},
                "message": "Conversion optimization requires billing_event=OCPM",
            },
            {
                "id": "lead_optimization_billing",
                "if": {"optimization_goal": "LEAD_GENERATION"},
                "allowed": {"billing_event": ["OCPM", "CPM"]},
                "message": "LEAD_GENERATION supports billing_event=OCPM or CPM",
            },
            {
                "id": "commerce_optimization_billing",
                "if": {"optimization_goal": {"in": [
                    "VALUE", "PRODUCT_SALES", "SHOP_PURCHASES", "CATALOG_SALES",
                ]}},
                "allowed": {"billing_event": ["OCPM", "CPC"]},
                "message": "Commerce optimization supports billing_event=OCPM or CPC",
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
            items={"type": "string"}, lookup_tool="tiktok_list_regions",
            lookup_result_key="regions",
            lookup_dependencies=[
                {"input_field": "placements", "value_path": "placements", "label": "投放版位"},
                {"input_field": "objective_type", "value_path": "objective_type", "label": "推广目标"},
            ],
            lookup_defaults={
                "placements": ["PLACEMENT_TIKTOK"],
                "level_range": "TO_COUNTRY",
            },
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
        # TikTok validates identity inside creatives for regular Ad creates;
        # keep it provider-required so the Runtime asks for a real identity
        # selection before reaching the write endpoint.
        "provider_required": ["campaign_id", "identity_id"],
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
            "media": _tiktok_media_field("TikTok media asset payload"),
            "creatives": _tiktok_creatives_field("Creative list"),
            "text": _tiktok_text_field(),
            "video_id": _field(
                "string", "Video asset ID", minLength=1,
                lookup_tool="tiktok_list_videos", lookup_result_key="videos",
                selection_value_fields=["video_id", "id"],
                selection_label_fields=["file_name", "video_name", "name", "id"],
                **_ui_equals("ad_format", "SINGLE_VIDEO"),
            ),
            "image_ids": _field(
                "array", "Image asset IDs", items={"type": "string", "minLength": 1},
                lookup_tool="tiktok_list_images", lookup_result_key="images",
                selection_value_fields=["image_id", "id"],
                selection_label_fields=["file_name", "image_name", "name", "id"],
                **_ui_when("ad_format", "SINGLE_IMAGE", "CAROUSEL"),
            ),
            "spark_post_id": _field(
                "string", "Spark post ID",
                manual_entry={
                    "title": "Spark 帖子 ID",
                    "instructions": "请提供已授权可推广的 TikTok 帖子 ID；当前没有通用帖子列表接口。",
                    "source": "provider_spark_post",
                },
                **_ui_equals("ad_format", "SPARK_AD"),
            ),
            "page_id": _field(
                "string", "TikTok Instant Page or Instant Form page ID", minLength=1,
                manual_entry={
                    "title": "TikTok 页面/表单 ID",
                    "instructions": "请从 TikTok Ads Manager 复制对应 Instant Page 或 Instant Form ID。",
                    "source": "provider_page_identifier",
                },
                **_ui_equals("ad_format", "LEAD_FORM"),
            ),
            "catalog_id": _field(
                "string", "TikTok catalog ID", minLength=1,
                lookup_tool="tiktok_list_catalogs", lookup_result_key="catalogs",
                selection_value_fields=["catalog_id", "id"],
                selection_label_fields=["catalog_name", "name", "id"],
            ),
            "product_set_id": _field(
                "string", "TikTok product set ID", minLength=1,
                lookup_tool="tiktok_list_product_sets", lookup_result_key="product_sets",
                selection_value_fields=["product_set_id", "id"],
                selection_label_fields=["product_set_name", "name", "id"],
            ),
            "call_to_action": _field(
                "string", "Call to action",
                manual_entry={
                    "title": "行动号召",
                    "instructions": "可用行动号召由 TikTok 广告目标、地区和素材格式决定；请从卡片中的可用值或 Ads Manager 选择。",
                    "source": "provider_cta_option",
                },
            ),
            "call_to_action_id": _field(
                "string", "Provider call-to-action ID",
                manual_entry={
                    "title": "行动号召 ID",
                    "instructions": "当前没有独立的 CTA 目录接口；请从 TikTok 返回或 Ads Manager 复制 CTA ID。",
                    "source": "provider_cta_identifier",
                },
            ),
            "creative_type": _field("string", "Provider creative type", enum=TIKTOK_CREATIVE_TYPES),
            "ad_text": _field("string", "Provider ad text"),
            "identity_id": _field(
                "string", "TikTok identity ID", minLength=1,
                lookup_tool="tiktok_list_identities", lookup_result_key="identities",
                selection_value_fields=["identity_id", "id"],
                selection_label_fields=["display_name", "name", "id"],
                **_ui_equals("ad_format", "SPARK_AD"),
            ),
            "identity_type": _field(
                "string", "TikTok identity type", enum=TIKTOK_IDENTITY_TYPES,
                **_ui_equals("ad_format", "SPARK_AD"),
            ),
            "tiktok_item_id": _field(
                "string", "Owned TikTok post ID for Spark creative",
                manual_entry={
                    "title": "TikTok 帖子 ID",
                    "instructions": "请提供该身份下已授权的有机帖子 ID；当前没有通用帖子列表接口。",
                    "source": "provider_spark_post",
                },
                **_ui_equals("ad_format", "SPARK_AD"),
            ),
            "deeplink": _field("string", "App deep link"),
            "deeplink_type": _field("string", "Deep link behavior"),
            "click_tracking_url": _field("string", "Click tracking URL"),
            "impression_tracking_url": _field("string", "Impression tracking URL"),
            "video_view_tracking_url": _field("string", "Video view tracking URL"),
            "operation_status": _field("string", "Provider ad status", enum=TIKTOK_OPERATION_STATUSES),
            "dynamic_destination": _field("string", "Dynamic landing page destination"),
            "dynamic_format": _field("string", "Dynamic creative format"),
            "product_specific_type": _field("string", "Shopping product selection mode"),
            "sku_ids": _field(
                "array", "Shopping SKU IDs", items={"type": "string", "minLength": 1},
                manual_entry={
                    "title": "商品 SKU ID",
                    "instructions": "当前没有通用 SKU 列表接口；请从 TikTok 商品库或商品集查询结果复制 SKU ID。",
                    "source": "provider_product_identifier",
                },
                **_ui_when("ad_format", "SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL"),
            ),
            "item_group_ids": _field(
                "array", "Shopping item group IDs", items={"type": "string", "minLength": 1},
                manual_entry={
                    "title": "商品组 ID",
                    "instructions": "当前没有通用商品组列表接口；请从 TikTok 商品库或商品集查询结果复制商品组 ID。",
                    "source": "provider_product_identifier",
                },
                **_ui_when("ad_format", "SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL"),
            ),
            "shopping_ads_deeplink_type": _field("string", "Shopping ads deep link behavior"),
            "shopping_ads_fallback_type": _field("string", "Shopping ads fallback behavior"),
            "shopping_ads_video_package_id": _field("string", "Shopping ads video package ID"),
            "shopping_ads_word_set": _field("array", "Shopping ads word set IDs", items={"type": "integer"}),
            "promotional_music_disabled": _field(
                "boolean", "Disable promotional music for Spark creative",
                **_ui_equals("ad_format", "SPARK_AD"),
            ),
            "item_duet_status": _field(
                "string", "Spark duet status", enum=TIKTOK_OPERATION_STATUSES,
                **_ui_equals("ad_format", "SPARK_AD"),
            ),
            "item_stitch_status": _field(
                "string", "Spark stitch status", enum=TIKTOK_OPERATION_STATUSES,
                **_ui_equals("ad_format", "SPARK_AD"),
            ),
            "instant_product_page_used": _field("boolean", "Use TikTok instant product page"),
            "playable_url": _field("string", "Playable ad URL"),
            "status": _field("integer", "Ad status: 1 active, 0 paused", enum=[0, 1]),
        },
    }


def tiktok_creative_schema() -> dict[str, Any]:
    """Schema for TikTok's logical Creative lifecycle.

    TikTok v1.3 models an ad's creative payload inside ``ad/create`` rather
    than exposing a standalone Creative create endpoint.  Reuse the complete
    provider-owned ad creative field catalog, but make the hierarchy explicit
    for a Creative Tool so the UI/LLM asks for the Campaign and Ad Group that
    will own the resulting ad-backed creative.
    """
    base = tiktok_ad_schema()
    return {
        "required": ["campaign_id", "adgroup_id", "name"],
        "provider_required": ["campaign_id", "adgroup_id", "identity_id"],
        "provider_any_of": list(base.get("provider_any_of", [])),
        "properties": dict(base["properties"]),
        "conditional_rules": list(base.get("conditional_rules", [])),
    }


def tiktok_product_sales_adgroup_schema() -> dict[str, Any]:
    """Schema for the Product Sales ad-group composition path.

    TikTok exposes Product Sales through the regular campaign/ad-group
    endpoints, but its product destination has provider-specific references.
    Keep those references in a dedicated contract so a Skill can compose a
    sales flow without teaching Core about Catalog or Shop semantics.
    """
    base = tiktok_adgroup_schema()
    properties = dict(base["properties"])
    properties["promotion_type"] = {
        **properties["promotion_type"],
        "enum": ["WEBSITE", "CATALOG"],
    }
    properties["product_source"] = {
        **properties["product_source"],
        "enum": ["CATALOG", "STORE", "SHOWCASE"],
    }
    properties["store_id"] = {
        **properties["store_id"],
        "minLength": 1,
    }
    return {
        "required": list(base["required"]),
        "provider_required": list(base["provider_required"]),
        "properties": properties,
        "conditional_rules": [
            *base["conditional_rules"],
            {
                "id": "product_sales_catalog_source_requires_product_selection",
                "if": {"product_source": "CATALOG"},
                "required": ["catalog_id", "product_set_id"],
                "message": "product_source=CATALOG requires catalog_id and product_set_id",
            },
            {
                "id": "product_sales_shop_source_requires_store",
                "if": {"product_source": "STORE"},
                "required": ["store_id"],
                "message": "product_source=STORE requires store_id",
            },
        ],
    }


def tiktok_product_sales_ad_schema() -> dict[str, Any]:
    """Schema for Product Sales ads, including Catalog and Shop references."""
    base = tiktok_ad_schema()
    properties = dict(base["properties"])
    properties["product_source"] = _field(
        "string", "Product Sales destination source",
        enum=["CATALOG", "STORE", "SHOWCASE"],
    )
    properties["store_id"] = {
        "type": "string",
        "description": "TikTok Shop or Storefront ID",
        "minLength": 1,
        "manual_entry": {
            "title": "TikTok Shop / Storefront ID",
            "instructions": "当前没有通用 Shop 列表接口；请从 TikTok Shop/Business Center 复制店铺 ID。",
            "source": "provider_store_identifier",
        },
    }
    return {
        "required": list(base["required"]),
        "provider_required": list(base["provider_required"]),
        "provider_any_of": [[
            "media", "creatives", "video_id", "image_ids",
            "sku_ids", "item_group_ids", "product_set_id",
        ]],
        "properties": properties,
        "conditional_rules": [
            {
                "id": "product_sales_ad_catalog_source_requires_product_selection",
                "if": {"product_source": "CATALOG"},
                "required": ["catalog_id", "product_set_id"],
                "message": "product_source=CATALOG requires catalog_id and product_set_id",
            },
            {
                "id": "product_sales_ad_shop_source_requires_store",
                "if": {"product_source": "STORE"},
                "required": ["store_id"],
                "message": "product_source=STORE requires store_id",
            },
            {
                "id": "product_sales_ad_catalog_promotion_requires_product_selection",
                "if": {"promotion_type": "CATALOG"},
                "required": ["catalog_id", "product_set_id"],
                "message": "promotion_type=CATALOG requires catalog_id and product_set_id",
            },
        ],
    }


def _tiktok_format_ad_schema(
    format_name: str,
    description: str,
    asset_properties: dict[str, Any],
) -> dict[str, Any]:
    """Build a format-specific view over TikTok's ad-create contract."""
    base = tiktok_ad_schema()
    properties = dict(base["properties"])
    properties["ad_format"] = _field(
        "string", "Fixed TikTok ad format for this Tool", enum=[format_name]
    )
    for field_name, field_schema in asset_properties.items():
        # Keep applicability/lookup metadata from the shared contract when a
        # format-specific view tightens the asset shape (for example the
        # single-video Tool replacing the generic media field).
        base_schema = properties.get(field_name)
        properties[field_name] = {
            **(base_schema if isinstance(base_schema, dict) else {}),
            **field_schema,
        }
    return {
        "required": ["adgroup_id", "name"],
        "provider_required": ["campaign_id"],
        "provider_any_of": [[*asset_properties.keys()]],
        "properties": properties,
        "description": description,
    }


def tiktok_single_video_ad_schema() -> dict[str, Any]:
    return _tiktok_format_ad_schema(
        "SINGLE_VIDEO", "TikTok single-video ad", {
            "video_id": _field("string", "Uploaded TikTok video asset ID", minLength=1),
            "tiktok_item_id": _field(
                "string", "Authorized TikTok post/item ID used as the video source",
                minLength=1,
                manual_entry={
                    "title": "已授权 TikTok 帖子/视频 ID",
                    "instructions": "当 Identity 类型为 AUTH_CODE 或 TT_USER 时，填写该身份已授权的帖子/视频 ID；不会根据名称猜测。",
                    "source": "provider_authorized_item",
                },
            ),
            "media": _tiktok_media_field("Single-video media payload"),
            "creatives": _tiktok_creatives_field("Single-video creative payload"),
        },
    )


def tiktok_single_image_ad_schema() -> dict[str, Any]:
    return _tiktok_format_ad_schema(
        "SINGLE_IMAGE", "TikTok single-image ad", {
            "image_ids": _field(
                "array", "Uploaded TikTok image asset IDs", items={"type": "string"}, minItems=1,
            ),
            "media": _tiktok_media_field("Single-image media payload"),
            "creatives": _tiktok_creatives_field("Single-image creative payload"),
        },
    )


def tiktok_carousel_ad_schema() -> dict[str, Any]:
    return _tiktok_format_ad_schema(
        "CAROUSEL", "TikTok carousel ad", {
            "image_ids": _field(
                "array", "Carousel image asset IDs (at least two)",
                items={"type": "string"}, minItems=2,
            ),
            "media": _tiktok_media_field("Carousel media/card payload"),
            "creatives": _tiktok_creatives_field("Carousel creative/card payload"),
        },
    )


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
            "page_id": _field(
                "string", "TikTok Instant Page / Instant Form page ID", minLength=1,
                manual_entry={
                    "title": "TikTok Instant Page / Form ID",
                    "instructions": "请从 TikTok Ads Manager 或 Instant Page Editor 复制已发布的页面/表单 ID；当前 Capability 没有稳定的页面列表接口。",
                    "source": "provider_instant_page",
                },
            ),
            "landing_page_url": _field("string", "Optional fallback landing URL"),
            "tracking_url": _field("string", "Tracking URL"),
            "conversion_id": _field(
                "integer", "Conversion event ID", minimum=0,
                lookup_tool="tiktok_list_conversions", lookup_result_key="conversions",
                selection_value_fields=["conversion_id", "id"],
                selection_label_fields=["conversion_name", "name", "event_name"],
            ),
            "media": _tiktok_media_field("Lead ad media assets"),
            "creatives": _tiktok_creatives_field("Lead ad creative list"),
            "text": _tiktok_text_field(),
            "call_to_action": _field("string", "Lead form call to action"),
            "status": _field("integer", "Ad status: 1 active, 0 paused", enum=[0, 1]),
            "operation_status": _field(
                "string", "Provider creation status", enum=["ENABLE", "DISABLE"],
            ),
            "tracking_pixel_id": _field(
                "integer", "TikTok tracking Pixel ID", minimum=0,
                lookup_tool="tiktok_list_pixels", lookup_result_key="pixels",
                selection_value_fields=["pixel_id", "id", "code"],
                selection_label_fields=["pixel_name", "name", "display_name", "id"],
            ),
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
            "media": _tiktok_media_field("App ad media assets"),
            "creatives": _tiktok_creatives_field("App ad creative list"),
            "text": _tiktok_text_field(),
            "call_to_action": _field("string", "App ad call to action"),
            "identity_id": _field(
                "string", "TikTok identity ID", minLength=1,
                lookup_tool="tiktok_list_identities", lookup_result_key="identities",
                selection_value_fields=["identity_id", "id"],
                selection_label_fields=["display_name", "name", "id"],
            ),
            "status": _field("integer", "Ad status: 1 active, 0 paused", enum=[0, 1]),
        },
    }


def tiktok_all_in_one_spark_ad_schema() -> dict[str, Any]:
    """Contract for TikTok's current one-step Spark Ads creation endpoint.

    The provider creates campaign, ad group and Spark Ad atomically from the
    caller's perspective.  Keep the fields flat because that is the official
    wire shape; Blueprints can still present them under campaign/ad-group/ad
    sections without making Runtime understand TikTok hierarchy details.
    """
    return {
        "required": [
            "campaign_name", "objective_type", "adgroup_name", "budget_mode",
            "budget", "schedule_type", "schedule_start_time",
            "optimization_goal", "bid_type", "ad_name", "identity_type",
            "identity_id", "tiktok_item_id",
        ],
        "provider_required": [
            "campaign_name", "objective_type", "adgroup_name", "budget_mode",
            "budget", "schedule_type", "schedule_start_time",
            "optimization_goal", "bid_type", "ad_name", "identity_type",
            "identity_id", "tiktok_item_id",
        ],
        "provider_any_of": [["location_ids", "saved_audience_id"]],
        "conditional_rules": [
            {
                "if": {"objective_type": "REACH"},
                "required": ["frequency", "frequency_schedule"],
            },
            {
                "if": {"optimization_goal": "PAGE_VISIT"},
                "required": ["call_to_action", "landing_page_url"],
            },
            {
                "if": {"bid_type": "BID_TYPE_CUSTOM"},
                "required": ["bid_price"],
            },
            {
                "if": {
                    "all": [
                        {"field": "optimization_goal", "equals": "FOLLOWERS"},
                        {"field": "bid_type", "equals": "BID_TYPE_CUSTOM"},
                    ]
                },
                "required": ["conversion_bid_price"],
            },
            {
                "if": {"call_to_action": {"exists": True}},
                "required": ["landing_page_url"],
            },
            {
                "if": {"identity_type": "BC_AUTH_TT"},
                "required": ["identity_authorized_bc_id"],
            },
            {
                "if": {"objective_type": "REACH"},
                "allowed": {"optimization_goal": ["REACH"]},
            },
            {
                "if": {"objective_type": "VIDEO_VIEWS"},
                "allowed": {"optimization_goal": ["ENGAGED_VIEW"]},
            },
            {
                "if": {"objective_type": "ENGAGEMENT"},
                "allowed": {"optimization_goal": ["FOLLOWERS", "PAGE_VISIT"]},
            },
        ],
        "properties": {
            "campaign_name": _field(
                "string", "Campaign name; TikTok limit is 512 characters",
                minLength=1, maxLength=512,
            ),
            "objective_type": _field(
                "string", "Advertising objective",
                enum=TIKTOK_ALL_IN_ONE_SPARK_OBJECTIVES,
                option_labels={
                    "REACH": "覆盖",
                    "VIDEO_VIEWS": "视频观看",
                    "ENGAGEMENT": "社区互动",
                },
                option_aliases={
                    "REACH": ["reach", "覆盖", "触达"],
                    "VIDEO_VIEWS": ["video views", "视频观看", "播放量"],
                    "ENGAGEMENT": ["engagement", "community interaction", "社区互动"],
                },
            ),
            "adgroup_name": _field(
                "string", "Ad group name; TikTok limit is 512 characters",
                minLength=1, maxLength=512,
            ),
            "saved_audience_id": _field(
                "string", "Saved Audience ID returned by TikTok",
                minLength=1, lookup_tool="tiktok_list_audiences", lookup_result_key="audiences",
            ),
            "location_ids": _field(
                "array", "TikTok location IDs; choose from the provider lookup",
                minItems=1, items={"type": "string"},
                lookup_tool="tiktok_list_regions", lookup_result_key="regions",
                selection_value_fields=["location_id", "id", "country_code", "code"],
                selection_label_fields=["location_name", "name", "country_name", "country_code"],
            ),
            "gender": _field("string", "Gender targeting", enum=TIKTOK_GENDERS),
            "age_groups": _field(
                "array", "Age groups to target",
                items={"type": "string", "enum": TIKTOK_AGE_GROUPS},
            ),
            "budget_mode": _field(
                "string", "Ad group budget mode",
                enum=["BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"],
            ),
            "budget": _field("number", "Ad group budget in account currency", minimum=0),
            "schedule_type": _field(
                "string", "Schedule type",
                enum=["SCHEDULE_START_END", "SCHEDULE_FROM_NOW"],
            ),
            "schedule_start_time": _field(
                "string", "UTC start time: YYYY-MM-DD HH:MM:SS",
            ),
            "schedule_end_time": _field(
                "string", "UTC end time when using SCHEDULE_START_END",
            ),
            "optimization_goal": _field(
                "string", "Optimization goal; options depend on objective",
                enum=TIKTOK_ALL_IN_ONE_SPARK_GOALS,
                option_labels={
                    "REACH": "覆盖",
                    "CLICK": "点击",
                    "TRAFFIC_LANDING_PAGE_VIEW": "落地页浏览",
                    "ENGAGED_VIEW": "有效观看",
                    "FOLLOWERS": "关注",
                    "PAGE_VISIT": "主页访问",
                },
            ),
            "frequency": _field(
                "number", "Maximum impressions per frequency window",
                minimum=1,
            ),
            "frequency_schedule": _field(
                "number", "Frequency window in days",
                minimum=1,
            ),
            "bid_type": _field(
                "string", "Bidding strategy",
                enum=["BID_TYPE_NO_BID", "BID_TYPE_CUSTOM"],
            ),
            "bid_price": _field(
                "number", "Cost cap for reach, click or engaged view",
                minimum=0,
            ),
            "conversion_bid_price": _field(
                "number", "Target conversion cost for LPV or followers",
                minimum=0,
            ),
            "ad_name": _field(
                "string", "Spark Ad name; TikTok limit is 512 characters",
                minLength=1, maxLength=512,
            ),
            "identity_type": _field(
                "string", "TikTok identity type",
                enum=["AUTH_CODE", "TT_USER", "BC_AUTH_TT"],
            ),
            "identity_id": _field(
                "string", "Identity ID returned by the identity lookup",
                minLength=1, lookup_tool="tiktok_list_identities",
                lookup_result_key="identities",
                selection_value_fields=["identity_id", "id"],
                selection_label_fields=["display_name", "name", "id"],
            ),
            "identity_authorized_bc_id": _field(
                "string", "Authorized Business Center selected from the identity lookup",
                minLength=1, lookup_tool="tiktok_list_identities", lookup_result_key="identities",
                selection_value_fields=["authorized_bc_id", "bc_id", "id"],
                selection_label_fields=["business_center_name", "display_name", "name", "authorized_bc_id"],
            ),
            "tiktok_item_id": _field(
                "string", "Authorized TikTok post ID used by Spark Ads",
                minLength=1,
                manual_entry={
                    "title": "已授权 TikTok 帖子 ID",
                    "instructions": "请从 TikTok Ads Manager 或已授权身份的帖子信息中复制帖子 ID；当前没有稳定的帖子目录接口，系统不会根据名称猜测。",
                    "source": "provider_authorized_item",
                },
            ),
            "call_to_action": _field(
                "string", "TikTok call-to-action enum value",
                manual_entry={
                    "title": "行动号召值",
                    "instructions": "请填写 TikTok 当前账户和推广目标允许的 CTA 值；当前没有独立且稳定的 CTA 列表接口，系统不会根据中文文案猜测。",
                    "source": "provider_enum_manual",
                },
            ),
            "landing_page_url": _field(
                "string", "Landing page URL",
            ),
        },
    }


def tiktok_smart_plus_campaign_schema() -> dict[str, Any]:
    """Closed contract for ``smart_plus/campaign/create``.

    Traffic and Sales are conversational aliases.  The client maps them to
    TikTok's documented ``WEB_CONVERSIONS`` campaign objective and validates
    the destination/optimization cascade at the provider boundary.
    """
    return {
        "required": ["campaign_name", "objective_type"],
        "provider_required": ["campaign_name", "objective_type"],
        "conditional_rules": [
            {"if": {"objective_type": "APP_PROMOTION"}, "required": ["app_promotion_type"]},
            {"if": {"objective_type": "WEB_CONVERSIONS"}, "required": ["sales_destination"]},
            {"if": {"objective_type": "SALES"}, "required": ["sales_destination"]},
            {"if": {"objective_type": "PRODUCT_SALES"}, "required": ["sales_destination"]},
            {"if": {"objective_type": "APP_PROMOTION"}, "required": ["app_id"], "message": "APP_PROMOTION requires app_id"},
        ],
        "properties": {
            "request_id": _field("string", "System-generated idempotency key", minLength=1, ui_hidden=True),
            "campaign_name": _field("string", "Campaign name", minLength=1, maxLength=512),
            "objective_type": _field(
                "string", "Business objective or Smart+ API objective",
                enum=TIKTOK_SMART_PLUS_OBJECTIVES,
                option_labels={
                    "APP_PROMOTION": "App promotion",
                    "WEB_CONVERSIONS": "Web conversions",
                    "LEAD_GENERATION": "Lead generation",
                    "TRAFFIC": "Traffic",
                    "SALES": "Sales",
                    "PRODUCT_SALES": "Product sales",
                },
            ),
            "operation_status": _field("string", "Create status", enum=["DISABLE", "ENABLE"], default="DISABLE"),
            "app_promotion_type": _field("string", "App promotion type", enum=["APP_INSTALL", "APP_RETARGETING", "MINIS"]),
            "sales_destination": _field("string", "Sales destination", enum=["WEBSITE", "APP", "WEB_AND_APP", "TIKTOK_SHOP"]),
            "is_search_campaign": _field("boolean", "Create a Search Ads campaign"),
            "catalog_enabled": _field("boolean", "Use a product catalog"),
            "catalog_type": _field("string", "Catalog type", enum=["ECOMMERCE", "TRAVEL_ENTERTAINMENT", "MINI_SERIES", "GENERIC", "ONLINE_TO_OFFLINE"]),
            "campaign_type": _field("string", "Campaign type", enum=["REGULAR_CAMPAIGN", "IOS14_CAMPAIGN"]),
            "app_id": _field(
                "string", "App ID returned by tiktok_list_apps", minLength=1,
                lookup_tool="tiktok_list_apps", lookup_result_key="apps",
                selection_value_fields=["app_id", "id"],
                selection_label_fields=["app_name", "name", "display_name", "id"],
            ),
            "special_industries": _field("array", "Restricted industry categories", items={"type": "string", "enum": ["HOUSING", "EMPLOYMENT", "CREDIT"]}),
            "budget_optimize_on": _field("boolean", "Campaign Budget Optimization"),
            "budget_mode": _field("string", "Campaign budget mode", enum=["BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_TOTAL", "BUDGET_MODE_INFINITE", "BUDGET_MODE_DAY"]),
            "budget": _field("number", "Campaign budget", minimum=0),
            "budget_auto_adjust_strategy": _field("string", "Automatic budget adjustment", enum=["AUTO_BUDGET_INCREASE", "UNSET"]),
            "smart_plus_adgroup_mode": _field("string", "Smart+ ad group mode", enum=["SINGLE", "MULTIPLE"]),
        },
    }


def tiktok_smart_plus_adgroup_schema() -> dict[str, Any]:
    """Closed contract for ``smart_plus/adgroup/create``."""
    return {
        "required": [
            "campaign_id", "adgroup_name", "promotion_type",
            "optimization_goal", "bid_type", "billing_event",
            "schedule_type", "schedule_start_time",
        ],
        "provider_required": [
            "campaign_id", "adgroup_name", "promotion_type",
            "optimization_goal", "bid_type", "billing_event",
            "schedule_type", "schedule_start_time",
        ],
        "provider_any_of": [["location_ids", "saved_audience_id"]],
        "properties": {
            "request_id": _field("string", "System-generated idempotency key", minLength=1, ui_hidden=True),
            "campaign_id": _field("string", "Parent Smart+ campaign ID", minLength=1),
            "adgroup_name": _field("string", "Ad group name", minLength=1, maxLength=512),
            "operation_status": _field("string", "Create status", enum=["DISABLE", "ENABLE"], default="DISABLE"),
            "promotion_type": _field("string", "Optimization location", enum=["APP_ANDROID", "APP_IOS", "WEBSITE", "CATALOG", "TIKTOK_SHOP", "MINI_APP", "MINI_GAME", "NATIVE_SERIES", "LEAD_GENERATION", "LEAD_GEN_CLICK_TO_TT_DIRECT_MESSAGE", "LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE"]),
            "promotion_target_type": _field("string", "Lead optimization location", enum=["INSTANT_PAGE", "EXTERNAL_WEBSITE"]),
            "optimization_goal": _field("string", "Optimization goal", enum=TIKTOK_SMART_PLUS_OPTIMIZATION_GOALS),
            "optimization_event": _field(
                "string", "Pixel or app optimization event",
                lookup_tool="tiktok_list_conversions", lookup_result_key="conversions",
                selection_value_fields=["conversion_id", "event_id", "id", "event_name"],
                selection_label_fields=["conversion_name", "event_name", "name", "id"],
            ),
            "app_attribution_source": _field("string", "App attribution source", enum=["MMP", "SAN"]),
            "app_data_source": _field("string", "App data source"),
            "app_id": _field(
                "string", "App ID returned by tiktok_list_apps", minLength=1,
                lookup_tool="tiktok_list_apps", lookup_result_key="apps",
                selection_value_fields=["app_id", "id"],
                selection_label_fields=["app_name", "name", "display_name", "id"],
            ),
            "catalog_id": _field("string", "Catalog ID returned by tiktok_list_catalogs", minLength=1, lookup_tool="tiktok_list_catalogs", lookup_result_key="catalogs"),
            "product_set_id": _field(
                "string", "Product set ID returned by tiktok_list_product_sets", minLength=1,
                lookup_tool="tiktok_list_product_sets", lookup_result_key="product_sets",
                lookup_dependencies=[{
                    "input_field": "catalog_id", "value_path": "catalog_id",
                    "label": "所属商品目录", "required": True,
                }],
                selection_value_fields=["product_set_id", "id"],
                selection_label_fields=["product_set_name", "name", "id"],
            ),
            "location_ids": _field("array", "TikTok location IDs", minItems=1, items={"type": "string"}, lookup_tool="tiktok_list_regions", lookup_result_key="regions", selection_value_fields=["location_id", "id", "country_code", "code"], selection_label_fields=["location_name", "name", "country_name", "country_code"]),
            "saved_audience_id": _field("string", "Saved Audience ID", minLength=1, lookup_tool="tiktok_list_audiences", lookup_result_key="audiences"),
            "gender": _field("string", "Gender", enum=TIKTOK_GENDERS),
            "age_groups": _field("array", "Age groups", items={"type": "string", "enum": TIKTOK_AGE_GROUPS}),
            "operating_systems": _field("array", "Operating systems", items={"type": "string", "enum": TIKTOK_OPERATING_SYSTEMS}),
            "placement_type": _field("string", "Placement mode", enum=TIKTOK_PLACEMENT_TYPES),
            "placements": _field("array", "Placements", items={"type": "string", "enum": TIKTOK_PLACEMENTS}),
            "targeting_optimization_mode": _field("string", "Targeting optimization mode", enum=["AUTOMATIC", "MANUAL"]),
            "bid_type": _field("string", "Bid type", enum=["BID_TYPE_NO_BID", "BID_TYPE_CUSTOM"]),
            "bid_price": _field("number", "Bid price", minimum=0),
            "conversion_bid_price": _field("number", "Conversion bid price", minimum=0),
            "deep_bid_type": _field("string", "Deep bid type", enum=["AEO", "OCC", "ROAS", "VO_HIGHEST_VALUE", "VO_MIN_ROAS"]),
            "roas_bid": _field("number", "ROAS bid", minimum=0),
            "billing_event": _field("string", "Billing event", enum=["CPM", "CPC", "OCPM", "CPV"]),
            "budget_mode": _field("string", "Ad group budget mode", enum=["BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_TOTAL", "BUDGET_MODE_INFINITE", "BUDGET_MODE_DAY"]),
            "budget": _field("number", "Ad group budget", minimum=0),
            "schedule_type": _field("string", "Schedule type", enum=TIKTOK_SCHEDULE_TYPES),
            "schedule_start_time": _field("string", "UTC start time"),
            "schedule_end_time": _field("string", "UTC end time"),
            "frequency": _field("number", "Frequency cap", minimum=1),
            "frequency_schedule": _field("number", "Frequency window in days", minimum=1),
            "identity_type": _field("string", "Identity type", enum=["CUSTOMIZED_USER", "AUTH_CODE", "TT_USER", "BC_AUTH_TT"]),
            "identity_id": _field("string", "Identity ID", minLength=1, lookup_tool="tiktok_list_identities", lookup_result_key="identities"),
            "identity_authorized_bc_id": _field("string", "Authorized Business Center selected from the identity lookup", minLength=1, lookup_tool="tiktok_list_identities", lookup_result_key="identities", selection_value_fields=["authorized_bc_id", "bc_id", "id"], selection_label_fields=["business_center_name", "display_name", "name", "authorized_bc_id"]),
            "pixel_id": _field("string", "Pixel ID", minLength=1, lookup_tool="tiktok_list_pixels", lookup_result_key="pixels"),
            "tracking_pixel_id": _field("string", "Tracking Pixel ID", minLength=1, lookup_tool="tiktok_list_pixels", lookup_result_key="pixels"),
        },
    }


def tiktok_smart_plus_ad_schema() -> dict[str, Any]:
    """Closed contract for ``smart_plus/ad/create``."""
    return {
        "required": ["campaign_id", "adgroup_id", "ad_name"],
        "provider_required": ["campaign_id", "adgroup_id", "ad_name"],
        "provider_any_of": [["tiktok_item_id", "video_id", "image_ids"]],
        "properties": {
            "request_id": _field("string", "System-generated idempotency key", minLength=1, ui_hidden=True),
            "campaign_id": _field("string", "Parent Smart+ campaign ID", minLength=1),
            "adgroup_id": _field("string", "Parent Smart+ ad group ID", minLength=1),
            "ad_name": _field("string", "Ad name", minLength=1, maxLength=512),
            "operation_status": _field("string", "Create status", enum=["DISABLE", "ENABLE"], default="DISABLE"),
            "ad_format": _field("string", "Ad format", enum=["SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL_ADS"]),
            "tiktok_item_id": _field("string", "Authorized TikTok post ID", minLength=1),
            "video_id": _field("string", "Uploaded TikTok video ID", minLength=1, lookup_tool="tiktok_list_videos", lookup_result_key="videos"),
            "image_ids": _field("array", "Uploaded TikTok image IDs", items={"type": "string"}, lookup_tool="tiktok_list_images", lookup_result_key="images"),
            "ad_text": _field("string", "Primary ad text", minLength=1, maxLength=100),
            "identity_type": _field("string", "Identity type", enum=["CUSTOMIZED_USER", "AUTH_CODE", "TT_USER", "BC_AUTH_TT"]),
            "identity_id": _field("string", "Identity ID", minLength=1, lookup_tool="tiktok_list_identities", lookup_result_key="identities"),
            "identity_authorized_bc_id": _field("string", "Authorized Business Center selected from the identity lookup", minLength=1, lookup_tool="tiktok_list_identities", lookup_result_key="identities", selection_value_fields=["authorized_bc_id", "bc_id", "id"], selection_label_fields=["business_center_name", "display_name", "name", "authorized_bc_id"]),
            "call_to_action_id": _field("string", "CTA ID"),
            "landing_page_url": _field("string", "Landing page URL"),
            "deeplink": _field("string", "App deep link"),
            "dark_post_status": _field("string", "Ads-only mode", enum=["ON", "OFF"]),
        },
    }


def tiktok_ad_format_catalog() -> list[dict[str, Any]]:
    """Advertised TikTok formats and their current contract depth."""
    source_document = "docs/ad-platform-hierarchy-guide-v5.md"
    smart_plus_chain = [
        "tiktok_smart_plus_create_campaign",
        "tiktok_smart_plus_create_adgroup",
        "tiktok_smart_plus_create_ad",
    ]
    all_in_one_spark = ["tiktok_create_all_in_one_spark_ad"]
    return [
        {
            "format_id": "product_sales",
            "category": "product_sales",
            "resource_type": "campaign",
            "coverage": "supported_dry_run",
            "tool_names": smart_plus_chain,
            "payload_adapter": "TikTokAPIClient.create_smart_plus_campaign/create_smart_plus_adgroup/create_smart_plus_ad",
            "dependencies": ["PRODUCT_SALES", "sales_destination", "optimization_goal", "product selection"],
            "supported_fields": ["objective_type", "sales_destination", "catalog_enabled", "catalog_type", "promotion_type", "catalog_id", "product_set_id", "optimization_goal", "optimization_event", "location_ids", "age_groups", "video_id", "image_ids", "ad_text"],
            "gaps": ["live mutation approval", "catalog feed health diagnostics"],
            "source_document": source_document,
        },
        {
            "format_id": "product_sales.shop",
            "category": "product_sales",
            "resource_type": "ad_group",
            "coverage": "supported_dry_run",
            "tool_names": smart_plus_chain + ["tiktok_list_catalogs", "tiktok_validate_product_selection"],
            "payload_adapter": "TikTokAPIClient.create_smart_plus_campaign/create_smart_plus_adgroup/create_smart_plus_ad",
            "dependencies": ["PRODUCT_SALES", "catalog_id", "product_set_id", "tiktok_validate_product_selection"],
            "supported_fields": ["catalog_id", "product_set_id", "promotion_type", "optimization_goal", "optimization_event", "location_ids", "video_id", "image_ids"],
            "gaps": ["live mutation approval", "catalog feed health diagnostics", "Shop/store identifier lookup"],
            "source_document": source_document,
        },
        {
            "format_id": "spark",
            "category": "spark",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": all_in_one_spark,
            "payload_adapter": "TikTokAPIClient.create_all_in_one_spark_ad",
            "dependencies": ["REACH|VIDEO_VIEWS|ENGAGEMENT", "spark_post_id", "creator authorization"],
            "supported_fields": ["objective_type", "optimization_goal", "location_ids", "frequency", "spark_post_id"],
            "gaps": ["live mutation approval", "authorization lookup", "CTA catalog lookup"],
            "source_document": source_document,
        },
        {
            "format_id": "traffic",
            "category": "traffic",
            "resource_type": "campaign",
            "coverage": "supported_dry_run",
            "tool_names": smart_plus_chain,
            "payload_adapter": "TikTokAPIClient.create_smart_plus_campaign/create_smart_plus_adgroup/create_smart_plus_ad",
            "dependencies": ["TRAFFIC", "sales_destination=WEBSITE", "CLICK|TRAFFIC_LANDING_PAGE_VIEW"],
            "supported_fields": ["objective_type", "sales_destination", "optimization_goal", "landing_page_url", "call_to_action_id"],
            "gaps": ["live mutation approval", "CTA catalog lookup"],
            "source_document": source_document,
        },
        {
            "format_id": "sales",
            "category": "sales",
            "resource_type": "campaign",
            "coverage": "supported_dry_run",
            "tool_names": smart_plus_chain,
            "payload_adapter": "TikTokAPIClient.create_smart_plus_campaign/create_smart_plus_adgroup/create_smart_plus_ad",
            "dependencies": ["SALES|PRODUCT_SALES", "sales_destination", "CONVERT|VALUE"],
            "supported_fields": ["objective_type", "sales_destination", "catalog_enabled", "optimization_goal", "optimization_event"],
            "gaps": ["live mutation approval", "catalog/product-set validation for every destination"],
            "source_document": source_document,
        },
        {
            "format_id": "single_video",
            "category": "product_sales",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["tiktok_create_single_video_ad"],
            "payload_adapter": "TikTokAPIClient.create_single_video_ad",
            "dependencies": ["ad_group", "video_id_or_media", "text"],
            "supported_fields": ["ad_format", "video_id", "media", "text"],
            "gaps": ["dedicated video payload validation"],
            "source_document": source_document,
        },
        {
            "format_id": "single_image",
            "category": "product_sales",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["tiktok_create_single_image_ad"],
            "payload_adapter": "TikTokAPIClient.create_single_image_ad",
            "dependencies": ["ad_group", "image_ids_or_media", "text"],
            "supported_fields": ["ad_format", "image_ids", "media", "text"],
            "gaps": ["dedicated image payload validation"],
            "source_document": source_document,
        },
        {
            "format_id": "carousel",
            "category": "product_sales",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["tiktok_create_carousel_ad"],
            "payload_adapter": "TikTokAPIClient.create_carousel_ad",
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
            "tool_names": smart_plus_chain,
            "payload_adapter": "TikTokAPIClient.create_smart_plus_campaign/create_smart_plus_adgroup/create_smart_plus_ad",
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
            "tool_names": smart_plus_chain,
            "payload_adapter": "TikTokAPIClient.create_smart_plus_campaign/create_smart_plus_adgroup/create_smart_plus_ad",
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
            "tool_names": all_in_one_spark,
            "payload_adapter": "TikTokAPIClient.create_all_in_one_spark_ad",
            "dependencies": ["REACH|VIDEO_VIEWS|ENGAGEMENT", "brand creative", "placement"],
            "supported_fields": ["objective_type", "optimization_goal", "frequency", "tiktok_item_id", "targeting"],
            "gaps": ["live mutation approval", "brand takeover/TopView-specific contract", "CTA catalog lookup"],
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
