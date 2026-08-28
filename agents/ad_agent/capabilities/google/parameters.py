"""Google Ads creation contracts owned by the Google Capability."""

from __future__ import annotations

from typing import Any


GOOGLE_CHANNEL_TYPES = [
    "SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "MULTI_CHANNEL", "PERFORMANCE_MAX",
]
GOOGLE_CHANNEL_SUB_TYPES = ["APP_CAMPAIGN", "APP_CAMPAIGN_FOR_ENGAGEMENT"]
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
GOOGLE_APP_STORES = ["GOOGLE_APP_STORE", "APPLE_APP_STORE"]
GOOGLE_APP_BIDDING_TYPES = [
    "TARGET_CPA", "TARGET_ROAS", "MAXIMIZE_CONVERSIONS",
    "MAXIMIZE_CONVERSION_VALUE",
]
GOOGLE_KEYWORD_MATCH_TYPES = ["BROAD", "PHRASE", "EXACT"]
GOOGLE_PRODUCT_GROUP_TYPES = [
    "all_products",
    "product_type_1", "product_type_2", "product_type_3", "product_type_4", "product_type_5",
    "brand", "condition",
    "custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3", "custom_label_4",
    "channel", "item_id", "bidding_category",
]
GOOGLE_PRODUCT_PARTITION_TYPES = ["UNIT", "SUBDIVISION"]
GOOGLE_PRODUCT_CONDITIONS = ["NEW", "USED", "REFURBISHED"]
GOOGLE_PRODUCT_CHANNELS = ["ONLINE", "LOCAL"]
GOOGLE_PRODUCT_LEVELS = ["LEVEL1", "LEVEL2", "LEVEL3", "LEVEL4", "LEVEL5"]


def _field(field_type: Any, description: str = "", **kwargs: Any) -> dict[str, Any]:
    value = {"type": field_type, "description": description}
    value.update(kwargs)
    return value


def _object(
    properties: dict[str, Any], description: str, *, additional_properties: bool = False
) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": properties,
        "additionalProperties": additional_properties,
    }


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
                intent_field="campaign_type",
            ),
            "campaign_type": _field("string", "Channel type alias", enum=GOOGLE_CHANNEL_TYPES),
            "advertising_channel_sub_type": _field(
                "string", "Channel subtype (App campaigns and Performance Max)",
                enum=GOOGLE_CHANNEL_SUB_TYPES,
            ),
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
            "app_campaign_setting": _object({
                "app_id": _field("string", "Google Play package name or iOS App Store ID", minLength=1),
                "app_store": _field("string", "App store", enum=GOOGLE_APP_STORES),
                "bidding_strategy_type": _field(
                    "string", "App campaign bidding strategy", enum=GOOGLE_APP_BIDDING_TYPES,
                ),
                "bidding_strategy_goal_type": _field(
                    "string", "App campaign optimization goal", enum=[
                        "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
                        "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST",
                    ],
                ),
            }, "Google App Campaign settings"),
            "shopping_setting": _object({
                "merchant_id": _field("integer", "Merchant Center ID", minimum=1),
                "sales_country": _field("string", "Shopping sales country", minLength=2),
                "marketing_language": _field("string", "Shopping marketing language", minLength=2),
                "priority": _field("integer", "Shopping campaign priority", minimum=0, maximum=100),
                "exclude_offline_store_locations": _field("boolean", "Exclude offline store locations"),
            }, "Google Shopping settings"),
            "campaign_goal_setting": _field("object", "Performance Max campaign goal setting", additionalProperties=True),
            "video_setting": _field("object", "Google Video campaign settings", additionalProperties=True),
            "targeting_setting": _field("object", "Campaign targeting settings", additionalProperties=True),
            "network_setting": _field("object", "Campaign network settings", additionalProperties=True),
            "final_url_suffix": _field("string", "Final URL suffix for tracking"),
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
            {"id": "app_campaign_dependency", "if": {"advertising_channel_type": "MULTI_CHANNEL"},
             "required": ["advertising_channel_sub_type", "app_campaign_setting"],
             "message": "MULTI_CHANNEL App campaigns require advertising_channel_sub_type and app_campaign_setting"},
            {"id": "app_campaign_channel_dependency", "if": {"advertising_channel_sub_type": "APP_CAMPAIGN"},
             "allowed": {"advertising_channel_type": ["MULTI_CHANNEL"]},
             "message": "APP_CAMPAIGN requires advertising_channel_type=MULTI_CHANNEL"},
            {"id": "app_engagement_channel_dependency", "if": {"advertising_channel_sub_type": "APP_CAMPAIGN_FOR_ENGAGEMENT"},
             "allowed": {"advertising_channel_type": ["MULTI_CHANNEL"]},
             "message": "APP_CAMPAIGN_FOR_ENGAGEMENT requires advertising_channel_type=MULTI_CHANNEL"},
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


def google_keyword_schema() -> dict[str, Any]:
    """Create contract for Ad Group Criterion keyword mutations."""
    return {
        "required": ["ad_group_id", "keywords"],
        "provider_required": ["keywords"],
        "properties": {
            "ad_group_id": _field("string", "Parent Ad Group ID", minLength=1),
            "keywords": _field(
                "array", "Keyword criteria to create", minItems=1,
                items=_object({
                    "text": _field("string", "Keyword text", minLength=1),
                    "match_type": _field("string", "Keyword match type", enum=GOOGLE_KEYWORD_MATCH_TYPES),
                    "negative": _field("boolean", "Create as a negative keyword"),
                    "status": _field("string", "Criterion status", enum=GOOGLE_STATUSES[:2]),
                    "cpc_bid_micros": _field("integer", "Optional criterion CPC bid in micros", minimum=0),
                }, "Keyword criterion"),
            ),
        },
    }


def google_product_group_schema() -> dict[str, Any]:
    """Create contract for a Google Shopping listing-group criterion.

    Google models a product partition as ``AdGroupCriterion.listingGroup``.
    The root ``all_products`` node has no case value; every other dimension
    maps to one explicit case-value object in the provider adapter.
    """
    properties = {
        "ad_group_id": _field("string", "Parent Shopping ad group ID", minLength=1),
        "product_group_type": _field(
            "string", "Product partition dimension", enum=GOOGLE_PRODUCT_GROUP_TYPES,
        ),
        "partition_type": _field(
            "string", "UNIT creates a leaf; SUBDIVISION creates a partition node",
            enum=GOOGLE_PRODUCT_PARTITION_TYPES, default="UNIT",
        ),
        "value": _field(
            ["string", "integer"],
            "Dimension value; bidding_category accepts a numeric category ID",
            minLength=1,
        ),
        "bidding_category_level": _field(
            "string", "Google product bidding category level", enum=GOOGLE_PRODUCT_LEVELS,
            default="LEVEL1",
        ),
        "parent_criterion_id": _field(
            "string", "Optional parent criterion ID or full resource name", minLength=1,
        ),
        "cpc_bid_micros": _field(
            "integer", "Optional product partition CPC bid in micros", minimum=0,
        ),
    }
    conditional_rules = [
        {
            "id": f"{product_type}_requires_value",
            "if": {"product_group_type": product_type},
            "required": ["value"],
            "message": f"{product_type} requires value",
        }
        for product_type in GOOGLE_PRODUCT_GROUP_TYPES
        if product_type != "all_products"
    ]
    conditional_rules.extend([
        {
            "id": "condition_values",
            "if": {"product_group_type": "condition"},
            "allowed": {"value": GOOGLE_PRODUCT_CONDITIONS},
            "message": "condition value must be NEW, USED or REFURBISHED",
        },
        {
            "id": "channel_values",
            "if": {"product_group_type": "channel"},
            "allowed": {"value": GOOGLE_PRODUCT_CHANNELS},
            "message": "channel value must be ONLINE or LOCAL",
        },
    ])
    return {
        "required": ["ad_group_id", "product_group_type"],
        "provider_required": ["product_group_type"],
        "properties": properties,
        "conditional_rules": conditional_rules,
    }


def google_ad_schema() -> dict[str, Any]:
    return {
        "required": ["ad_group_id", "name"],
        "provider_required": ["final_url"],
        "provider_any_of": [["headlines", "responsive_search_ad"]],
        "properties": {
            "ad_group_id": _field("string", "Parent Ad Group ID"),
            "name": _field("string", "Ad name", maxLength=255),
            "ad_type": _field("string", "Ad format", enum=["RESPONSIVE_SEARCH_AD", "EXPANDED_TEXT_AD", "RESPONSIVE_DISPLAY_AD", "VIDEO"]),
            "headlines": _field("array", "Ad headlines", minItems=3, maxItems=15, items={"type": "string", "minLength": 1, "maxLength": 30}),
            "descriptions": _field("array", "Ad descriptions", minItems=2, maxItems=4, items={"type": "string", "minLength": 1, "maxLength": 90}),
            "final_url": _field("string", "Final URL", minLength=1),
            "path1": _field("string", "Display path 1", maxLength=15),
            "path2": _field("string", "Display path 2", maxLength=15),
            "responsive_search_ad": _field("object", "Responsive Search Ad payload", additionalProperties=True),
            "responsive_display_ad": _field("object", "Responsive Display Ad payload", additionalProperties=True),
            "video": _field("object", "Video ad payload", additionalProperties=True),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
        "conditional_rules": [
            {"id": "rsa_headlines", "if": {"ad_type": "RESPONSIVE_SEARCH_AD"},
             "required": ["headlines", "descriptions"], "message": "RESPONSIVE_SEARCH_AD requires headlines and descriptions"},
        ],
    }


def google_responsive_display_ad_schema() -> dict[str, Any]:
    """Create contract for a Google Responsive Display Ad payload."""
    text_asset = {
        "type": ["string", "object"],
        "description": "Text or provider asset object",
        "additionalProperties": True,
    }
    image_asset = _field(
        "array", "Provider image asset references", minItems=1,
        items={"type": "object", "additionalProperties": True},
    )
    return {
        "required": ["ad_group_id", "name", "final_url", "headlines", "long_headline", "descriptions", "business_name"],
        "provider_required": ["headlines", "long_headline", "descriptions", "business_name"],
        "properties": {
            "ad_group_id": _field("string", "Parent Display ad group ID"),
            "name": _field("string", "Ad name", maxLength=255),
            "ad_type": _field("string", "Ad format", enum=["RESPONSIVE_DISPLAY_AD"], default="RESPONSIVE_DISPLAY_AD"),
            "headlines": _field("array", "Short headline assets", minItems=3, maxItems=5, items=text_asset),
            "long_headline": text_asset,
            "descriptions": _field("array", "Description assets", minItems=1, maxItems=5, items=text_asset),
            "business_name": _field("string", "Advertiser business name", minLength=1, maxLength=25),
            "marketing_images": image_asset,
            "square_marketing_images": image_asset,
            "logos": image_asset,
            "landscape_logos": image_asset,
            "videos": _field(
                "array", "YouTube video asset references", items={"type": ["string", "object"], "additionalProperties": True},
            ),
            "call_to_action_text": _field("string", "Optional call to action"),
            "main_color": _field("string", "Optional main color"),
            "accent_color": _field("string", "Optional accent color"),
            "allow_flexible_color": _field("boolean", "Whether Google may adjust colors"),
            "final_url": _field("string", "Final URL", minLength=1),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_ad_format_catalog() -> list[dict[str, Any]]:
    """Advertised Google formats, grounded in the hierarchy guide.

    ``supported_dry_run`` is reserved for a format with a dedicated payload
    builder.  The remaining entries deliberately expose the gap instead of
    treating a broad campaign enum or an open object as full support.
    """
    source_document = "docs/ad-platform-hierarchy-guide-v5.md"
    return [
        {
            "format_id": "search",
            "category": "search",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_ad_group", "google_create_keywords", "google_create_search_ad"],
            "dependencies": ["keywords", "network_setting", "ad_group"],
            "supported_fields": ["advertising_channel_type", "bidding_strategy", "networks"],
            "gaps": ["negative keyword-specific validation", "extensions"],
            "source_document": source_document,
        },
        {
            "format_id": "search.responsive_search_ad",
            "category": "search",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_search_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_search_ad",
            "dependencies": ["ad_group", "headlines", "descriptions", "final_url"],
            "supported_fields": ["headlines", "descriptions", "path1", "path2", "final_url"],
            "gaps": ["live mutation approval", "ad extensions"],
            "source_document": source_document,
        },
        {
            "format_id": "search.expanded_text_ad",
            "category": "search",
            "resource_type": "ad",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["ad_group", "final_url"],
            "gaps": ["dedicated Expanded Text Ad payload Tool and payload builder"],
            "source_document": source_document,
        },
        {
            "format_id": "performance_max",
            "category": "performance_max",
            "resource_type": "asset_group",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_pmax_asset_group"],
            "dependencies": ["asset_group", "assets", "audience_signals", "product_feed"],
            "supported_fields": ["campaign_goal_setting", "headlines", "descriptions", "images", "videos", "logos"],
            "gaps": ["verified AssetService adapter", "audience signals", "listing groups/product targets"],
            "source_document": source_document,
        },
        {
            "format_id": "performance_max.asset_group",
            "category": "performance_max",
            "resource_type": "asset_group",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_pmax_asset_group"],
            "dependencies": ["asset_group", "assets", "audience_signals", "listing_group"],
            "supported_fields": ["headlines", "descriptions", "images", "videos"],
            "gaps": ["verified AssetService adapter", "audience signal and listing group Tools"],
            "source_document": source_document,
        },
        {
            "format_id": "shopping",
            "category": "shopping",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_ad_group"],
            "dependencies": ["shopping_setting", "merchant_center", "product_groups"],
            "supported_fields": ["shopping_setting", "bidding_strategy"],
            "gaps": ["product group create/update tool", "Merchant Center validation"],
            "source_document": source_document,
        },
        {
            "format_id": "shopping.product_group",
            "category": "shopping",
            "resource_type": "product_group",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_product_group"],
            "payload_adapter": "GoogleAdsAPIClient.create_product_group",
            "dependencies": ["ad_group", "listing_group", "merchant_center"],
            "supported_fields": ["all_products", "product_type_1..5", "custom_label_0..4", "brand", "condition", "channel", "item_id", "bidding_category"],
            "gaps": ["Merchant Center validation", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "video",
            "category": "video",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": ["google_create_campaign", "google_create_ad_group"],
            "dependencies": ["YouTube video", "video_setting", "audiences"],
            "gaps": ["dedicated Video Ad payload builder", "video format validation"],
            "source_document": source_document,
        },
        {
            "format_id": "video.skippable_in_stream",
            "category": "video",
            "resource_type": "ad",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["YouTube video", "final_url", "video_setting"],
            "gaps": ["dedicated Video Ad Tool and format-specific validation"],
            "source_document": source_document,
        },
        {
            "format_id": "video.non_skippable_in_stream",
            "category": "video",
            "resource_type": "ad",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["YouTube video", "final_url", "video_setting"],
            "gaps": ["dedicated Video Ad Tool and format-specific validation"],
            "source_document": source_document,
        },
        {
            "format_id": "video.bumper",
            "category": "video",
            "resource_type": "ad",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["YouTube video", "final_url", "video_setting"],
            "gaps": ["dedicated Video Ad Tool and format-specific validation"],
            "source_document": source_document,
        },
        {
            "format_id": "display",
            "category": "display",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_ad_group"],
            "dependencies": ["responsive_display_assets", "audiences", "placements"],
            "supported_fields": ["advertising_channel_type", "bidding_strategy", "targeting_setting", "network_setting"],
            "gaps": ["display targeting tools", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "display.responsive_display_ad",
            "category": "display",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_responsive_display_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_responsive_display_ad",
            "dependencies": ["headlines", "long_headlines", "descriptions", "images", "logos"],
            "supported_fields": ["headlines", "long_headline", "descriptions", "business_name", "marketing_images", "square_marketing_images", "logos", "videos", "final_url"],
            "gaps": ["asset upload/resource-name validation", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "app",
            "category": "app",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign"],
            "dependencies": ["MULTI_CHANNEL", "advertising_channel_sub_type", "app_campaign_setting", "app assets"],
            "supported_fields": ["app_campaign_setting", "bidding_strategy"],
            "gaps": ["App campaign asset/ad tool", "engagement selective optimization"],
            "source_document": source_document,
        },
        {
            "format_id": "app.install",
            "category": "app",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign"],
            "dependencies": ["MULTI_CHANNEL", "APP_CAMPAIGN", "app_campaign_setting", "app assets"],
            "supported_fields": ["app_id", "app_store", "bidding_strategy_type", "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST"],
            "gaps": ["App campaign asset/ad Tool", "live provider verification"],
            "source_document": source_document,
        },
        {
            "format_id": "app.engagement",
            "category": "app",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign"],
            "dependencies": ["MULTI_CHANNEL", "APP_CAMPAIGN_FOR_ENGAGEMENT", "app_campaign_setting", "app assets"],
            "supported_fields": ["app_id", "app_store", "bidding_strategy_type", "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST"],
            "gaps": ["App campaign asset/ad Tool", "live provider verification"],
            "source_document": source_document,
        },
    ]


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
