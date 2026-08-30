"""Google Ads creation contracts owned by the Google Capability."""

from __future__ import annotations

from typing import Any


GOOGLE_CHANNEL_TYPES = [
    # AdvertisingChannelType values published by the Google Ads v24 API.
    # ``MAX`` and ``APP`` are intentionally not advertised here: they are
    # terminology used by older internal examples, not provider enum values.
    "SEARCH", "DISPLAY", "SHOPPING", "HOTEL", "VIDEO", "MULTI_CHANNEL",
    "LOCAL", "SMART", "DEMAND_GEN", "PERFORMANCE_MAX", "TRAVEL",
    "LOCAL_SERVICES",
]
GOOGLE_CHANNEL_INPUT_TYPES = [*GOOGLE_CHANNEL_TYPES, "MAX", "APP"]
GOOGLE_CHANNEL_TYPE_INTENT_MAP = {"MAX": "PERFORMANCE_MAX", "APP": "MULTI_CHANNEL"}
GOOGLE_CHANNEL_SUB_TYPES = ["APP_CAMPAIGN", "APP_CAMPAIGN_FOR_ENGAGEMENT"]
GOOGLE_BIDDING_STRATEGIES = [
    "MANUAL_CPC", "MAXIMIZE_CLICKS", "MAXIMIZE_CONVERSIONS", "TARGET_CPA",
    "TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE", "TARGET_IMPRESSION_SHARE",
    "MANUAL_CPM", "MANUAL_CPV", "TARGET_CPM", "TARGET_CPV",
]
GOOGLE_PORTFOLIO_BIDDING_STRATEGIES = [
    "MANUAL_CPC", "MAXIMIZE_CONVERSIONS", "MAXIMIZE_CONVERSION_VALUE",
    "TARGET_CPA", "TARGET_ROAS", "TARGET_IMPRESSION_SHARE",
]
GOOGLE_TARGET_IMPRESSION_SHARE_LOCATIONS = [
    "ANYWHERE_ON_PAGE", "TOP_OF_PAGE", "ABSOLUTE_TOP_OF_PAGE",
]
GOOGLE_ASSET_TYPES = ["TEXT", "IMAGE", "YOUTUBE_VIDEO", "MEDIA_BUNDLE"]
GOOGLE_ASSET_IMAGE_MIME_TYPES = ["IMAGE_JPEG", "IMAGE_GIF", "IMAGE_PNG"]
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
GOOGLE_VIDEO_AD_FORMATS = [
    "SKIPPABLE_IN_STREAM", "NON_SKIPPABLE_IN_STREAM", "BUMPER", "OUTSTREAM",
]
GOOGLE_VIDEO_CAMPAIGN_FORMAT_PREFERENCES = [
    "TRUE_VIEW_IN_STREAM", "NON_TRUE_VIEW_IN_STREAM", "BUMPER", "OUTSTREAM",
]
GOOGLE_TARGETING_DIMENSIONS = [
    "AUDIENCE", "AGE_RANGE", "GENDER", "INCOME_RANGE", "PARENTAL_STATUS",
    "PLACEMENT", "TOPIC", "USER_INTEREST", "CUSTOM_AFFINITY", "CUSTOM_INTENT",
    "KEYWORD", "LOCATION",
]
GOOGLE_GEO_TARGET_TYPES = ["LOCAL_OR_PRESENT", "PRESENCE"]
GOOGLE_PMAX_GOAL_TYPES = [
    "SALES_GOAL_TYPE_ECOMMERCE", "LEAD_GENERATION", "APP_INSTALL",
    "APP_ENGAGEMENT",
]
GOOGLE_CAMPAIGN_CRITERION_TYPES = [
    "LOCATION", "LANGUAGE", "DEVICE", "USER_LIST", "USER_INTEREST",
    "AGE_RANGE", "GENDER", "PARENTAL_STATUS", "INCOME_RANGE",
    "CONTENT_LABEL", "PLACEMENT", "TOPIC",
]
GOOGLE_CRITERION_STATUSES = ["ENABLED", "PAUSED", "REMOVED"]
GOOGLE_CRITERION_DEVICES = ["MOBILE", "TABLET", "DESKTOP", "CONNECTED_TV"]
GOOGLE_AGE_RANGES = [
    "AGE_RANGE_18_24", "AGE_RANGE_25_34", "AGE_RANGE_35_44",
    "AGE_RANGE_45_54", "AGE_RANGE_55_64", "AGE_RANGE_65_UP",
    "AGE_RANGE_UNDETERMINED",
]
GOOGLE_GENDERS = ["MALE", "FEMALE", "UNDETERMINED"]
GOOGLE_PARENTAL_STATUSES = ["PARENT", "NOT_A_PARENT", "UNDETERMINED"]
GOOGLE_INCOME_RANGES = [
    "INCOME_RANGE_0_50", "INCOME_RANGE_50_60", "INCOME_RANGE_60_70",
    "INCOME_RANGE_70_80", "INCOME_RANGE_80_90", "INCOME_RANGE_90_100",
    "INCOME_RANGE_UNDETERMINED",
]
GOOGLE_CONTENT_LABELS = [
    "CONTENT_LABEL_DLT", "CONTENT_LABEL_DL_G", "CONTENT_LABEL_DL_PG",
    "CONTENT_LABEL_DL_T", "CONTENT_LABEL_DL_MA", "CONTENT_LABEL_DLV",
    "CONTENT_LABEL_DNS", "CONTENT_LABEL_UNRATED",
]

GOOGLE_BUDGET_DELIVERY_METHODS = ["STANDARD"]
GOOGLE_CONVERSION_ACTION_TYPES = [
    "AD_CALL", "CLICK_TO_CALL", "GOOGLE_PLAY_DOWNLOAD",
    "GOOGLE_PLAY_IN_APP_PURCHASE", "UPLOAD_CALLS", "UPLOAD_CLICKS", "WEBPAGE",
    "WEBSITE_CALL", "STORE_SALES_DIRECT_UPLOAD", "STORE_SALES",
    "FIREBASE_ANDROID_FIRST_OPEN", "FIREBASE_ANDROID_IN_APP_PURCHASE",
    "FIREBASE_ANDROID_CUSTOM", "FIREBASE_IOS_FIRST_OPEN",
    "FIREBASE_IOS_IN_APP_PURCHASE", "FIREBASE_IOS_CUSTOM",
    "THIRD_PARTY_APP_ANALYTICS_ANDROID_FIRST_OPEN",
    "THIRD_PARTY_APP_ANALYTICS_ANDROID_IN_APP_PURCHASE",
    "THIRD_PARTY_APP_ANALYTICS_ANDROID_CUSTOM",
    "THIRD_PARTY_APP_ANALYTICS_IOS_FIRST_OPEN",
    "THIRD_PARTY_APP_ANALYTICS_IOS_IN_APP_PURCHASE",
    "THIRD_PARTY_APP_ANALYTICS_IOS_CUSTOM", "ANDROID_APP_PRE_REGISTRATION",
    "ANDROID_INSTALLS_ALL_OTHER_APPS", "FLOODLIGHT_ACTION",
    "FLOODLIGHT_TRANSACTION", "GOOGLE_HOSTED", "LEAD_FORM_SUBMIT",
    "SEARCH_ADS_360", "SMART_CAMPAIGN_AD_CLICKS_TO_CALL",
    "SMART_CAMPAIGN_MAP_CLICKS_TO_CALL", "SMART_CAMPAIGN_MAP_DIRECTIONS",
    "SMART_CAMPAIGN_TRACKED_CALLS", "STORE_VISITS", "WEBPAGE_CODELESS",
    "UNIVERSAL_ANALYTICS_GOAL", "UNIVERSAL_ANALYTICS_TRANSACTION",
    "GOOGLE_ANALYTICS_4_CUSTOM", "GOOGLE_ANALYTICS_4_PURCHASE",
]
GOOGLE_CONVERSION_ACTION_CATEGORIES = [
    "DEFAULT", "PAGE_VIEW", "PURCHASE", "SIGNUP", "DOWNLOAD", "ADD_TO_CART",
    "BEGIN_CHECKOUT", "SUBSCRIBE_PAID", "PHONE_CALL_LEAD", "IMPORTED_LEAD",
    "SUBMIT_LEAD_FORM", "BOOK_APPOINTMENT", "REQUEST_QUOTE", "GET_DIRECTIONS",
    "OUTBOUND_CLICK", "CONTACT", "ENGAGEMENT", "STORE_VISIT", "STORE_SALE",
    "QUALIFIED_LEAD", "CONVERTED_LEAD",
]
GOOGLE_CONVERSION_ACTION_STATUSES = ["ENABLED", "REMOVED", "HIDDEN"]
GOOGLE_CONVERSION_ACTION_COUNTING_TYPES = ["ONE_PER_CLICK", "MANY_PER_CLICK"]
GOOGLE_USER_LIST_UPLOAD_KEY_TYPES = [
    "CONTACT_INFO", "CRM_ID", "MOBILE_ADVERTISING_ID",
]
GOOGLE_USER_LIST_DATA_SOURCE_TYPES = [
    "FIRST_PARTY", "THIRD_PARTY_CREDIT_BUREAU", "THIRD_PARTY_VOTER_FILE",
    "THIRD_PARTY_PARTNER_DATA",
]


def _field(field_type: Any, description: str = "", **kwargs: Any) -> dict[str, Any]:
    value = {"type": field_type, "description": description}
    value.update(kwargs)
    return value


def _object(
    properties: dict[str, Any], description: str, *,
    additional_properties: bool = False, required: list[str] | None = None,
) -> dict[str, Any]:
    schema = {
        "type": "object",
        "description": description,
        "properties": properties,
        "additionalProperties": additional_properties,
    }
    if required:
        schema["required"] = list(required)
    return schema


def google_campaign_budget_schema() -> dict[str, Any]:
    """Schema for the standalone CampaignBudget management Tools."""
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "budget_id": _field("string", "CampaignBudget ID"),
            "name": _field("string", "Budget name", minLength=1, maxLength=255),
            "daily_budget": _field("number", "Daily budget in account currency", minimum=0.01),
            "limit": _field("integer", "Maximum number of budgets", minimum=1, maximum=10000),
            "delivery_method": _field("string", "Budget delivery method", enum=GOOGLE_BUDGET_DELIVERY_METHODS),
            "explicitly_shared": _field("boolean", "Whether the budget is shared"),
        },
        "conditional_rules": [],
    }


def google_conversion_action_schema() -> dict[str, Any]:
    """Schema for customer-scoped ConversionAction creation."""
    return {
        "required": ["customer_id", "name", "type", "category"],
        "provider_required": ["name", "type", "category"],
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID; MCC is not accepted"),
            "name": _field("string", "Conversion action name", minLength=1, maxLength=255),
            "type": _field("string", "Immutable conversion action type", enum=GOOGLE_CONVERSION_ACTION_TYPES),
            "category": _field("string", "Conversion category", enum=GOOGLE_CONVERSION_ACTION_CATEGORIES),
            "status": _field("string", "Accrual status", enum=GOOGLE_CONVERSION_ACTION_STATUSES, default="ENABLED"),
            "counting_type": _field("string", "How conversions are counted", enum=GOOGLE_CONVERSION_ACTION_COUNTING_TYPES, default="MANY_PER_CLICK"),
            "primary_for_goal": _field("boolean", "Whether this action is primary for goals"),
            "include_in_conversions_metric": _field("boolean", "Include in conversions metric"),
            "click_through_lookback_window_days": _field("integer", "Click-through lookback window", minimum=1),
            "view_through_lookback_window_days": _field("integer", "View-through lookback window", minimum=1),
            "value_settings": _object({
                "default_value": _field("number", "Fallback conversion value"),
                "default_currency_code": _field("string", "Fallback currency code", minLength=3, maxLength=3),
                "always_use_default_value": _field("boolean", "Always use fallback value"),
            }, "Conversion value settings"),
        },
    }


def google_conversion_action_update_schema() -> dict[str, Any]:
    """Closed mutable-field contract for ConversionAction updates."""
    return _object({
        "name": _field("string", "Conversion action name", minLength=1, maxLength=255),
        "status": _field("string", "Accrual status", enum=GOOGLE_CONVERSION_ACTION_STATUSES),
        "category": _field("string", "Conversion category", enum=GOOGLE_CONVERSION_ACTION_CATEGORIES),
        "counting_type": _field("string", "How conversions are counted", enum=GOOGLE_CONVERSION_ACTION_COUNTING_TYPES),
        "primary_for_goal": _field("boolean", "Whether this action is primary for goals"),
        "include_in_conversions_metric": _field("boolean", "Include in conversions metric"),
        "click_through_lookback_window_days": _field("integer", "Click-through lookback window", minimum=1),
        "view_through_lookback_window_days": _field("integer", "View-through lookback window", minimum=1),
        "value_settings": _object({
            "default_value": _field("number", "Fallback conversion value"),
            "default_currency_code": _field("string", "Fallback currency code", minLength=3, maxLength=3),
            "always_use_default_value": _field("boolean", "Always use fallback value"),
        }, "Conversion value settings"),
    }, "Allowed ConversionAction update fields")


def google_user_list_schema() -> dict[str, Any]:
    """Schemas for first-party CRM UserList lifecycle and upload Tools."""
    return {
        "required": ["customer_id", "name"],
        "provider_required": ["name"],
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID; MCC is not accepted"),
            "user_list_id": _field("string", "Google UserList numeric ID", minLength=1),
            "name": _field("string", "UserList name", minLength=1, maxLength=255),
            "description": _field("string", "UserList description", maxLength=1000),
            "membership_life_span": _field(
                "integer", "Membership duration in days", minimum=0, maximum=540,
                default=540,
            ),
            "integration_code": _field("string", "Advertiser integration correlation code"),
            "eligible_for_search": _field("boolean", "Whether the list may be used for Search"),
            "upload_key_type": _field(
                "string", "Customer Match matching key type",
                enum=GOOGLE_USER_LIST_UPLOAD_KEY_TYPES, default="CONTACT_INFO",
            ),
            "data_source_type": _field(
                "string", "CRM data source", enum=GOOGLE_USER_LIST_DATA_SOURCE_TYPES,
                default="FIRST_PARTY",
            ),
            "app_id": _field("string", "App ID required for mobile advertising ID lists"),
            "file_path": _field(
                "string", "Local .csv/.tsv file containing only SHA-256 identifiers",
                minLength=1,
            ),
            "updates": _object({
                "name": _field("string", "UserList name", minLength=1, maxLength=255),
                "description": _field("string", "UserList description", maxLength=1000),
                "membership_life_span": _field(
                    "integer", "Membership duration in days", minimum=0, maximum=540,
                ),
                "integration_code": _field("string", "Advertiser integration correlation code"),
                "eligible_for_search": _field("boolean", "Whether the list may be used for Search"),
            }, "Allowed UserList update fields", additional_properties=False),
        },
        "conditional_rules": [
            {
                "id": "mobile_user_list_app_dependency",
                "if": {"upload_key_type": "MOBILE_ADVERTISING_ID"},
                "required": ["app_id"],
                "message": "MOBILE_ADVERTISING_ID requires app_id",
            },
        ],
    }


def google_user_list_update_schema() -> dict[str, Any]:
    return google_user_list_schema()["properties"]["updates"]


def google_bidding_strategy_schema() -> dict[str, Any]:
    """Schema for portfolio BiddingStrategy lifecycle Tools."""
    return {
        "required": ["customer_id", "name", "strategy_type"],
        "provider_required": ["name", "strategy_type"],
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID; MCC is not accepted"),
            "bidding_strategy_id": _field("string", "BiddingStrategy numeric ID", minLength=1),
            "name": _field("string", "Portfolio bidding strategy name", minLength=1, maxLength=255),
            "strategy_type": _field(
                "string", "Portfolio bidding strategy scheme",
                enum=GOOGLE_PORTFOLIO_BIDDING_STRATEGIES,
            ),
            "target_cpa_micros": _field("integer", "Target CPA in account micros", minimum=1),
            "target_roas": _field("number", "Target ROAS", exclusiveMinimum=0, maximum=1000),
            "target_impression_share": _field(
                "number", "Target impression share as a fraction",
                exclusiveMinimum=0, maximum=1,
            ),
            "target_impression_share_location": _field(
                "string", "Target search result location",
                enum=GOOGLE_TARGET_IMPRESSION_SHARE_LOCATIONS,
            ),
            "cpc_bid_ceiling_micros": _field("integer", "Maximum CPC bid in micros", minimum=1),
            "cpc_bid_floor_micros": _field("integer", "Minimum CPC bid in micros", minimum=0),
            "enhanced_cpc_enabled": _field("boolean", "Enable enhanced CPC for Manual CPC"),
            "updates": _object({
                "name": _field("string", "Portfolio bidding strategy name", minLength=1, maxLength=255),
                "strategy_type": _field(
                    "string", "Existing strategy scheme; required for bid-setting updates",
                    enum=GOOGLE_PORTFOLIO_BIDDING_STRATEGIES,
                ),
                "target_cpa_micros": _field("integer", "Target CPA in account micros", minimum=1),
                "target_roas": _field("number", "Target ROAS", exclusiveMinimum=0, maximum=1000),
                "target_impression_share": _field(
                    "number", "Target impression share as a fraction",
                    exclusiveMinimum=0, maximum=1,
                ),
                "target_impression_share_location": _field(
                    "string", "Target search result location",
                    enum=GOOGLE_TARGET_IMPRESSION_SHARE_LOCATIONS,
                ),
                "cpc_bid_ceiling_micros": _field("integer", "Maximum CPC bid in micros", minimum=1),
                "cpc_bid_floor_micros": _field("integer", "Minimum CPC bid in micros", minimum=0),
                "enhanced_cpc_enabled": _field("boolean", "Enable enhanced CPC for Manual CPC"),
            }, "Allowed BiddingStrategy update fields", additional_properties=False),
        },
        "conditional_rules": [
            {
                "id": "target_cpa_dependency",
                "if": {"strategy_type": "TARGET_CPA"},
                "required": ["target_cpa_micros"],
                "message": "TARGET_CPA requires target_cpa_micros",
            },
            {
                "id": "target_roas_dependency",
                "if": {"strategy_type": "TARGET_ROAS"},
                "required": ["target_roas"],
                "message": "TARGET_ROAS requires target_roas",
            },
            {
                "id": "target_impression_share_dependency",
                "if": {"strategy_type": "TARGET_IMPRESSION_SHARE"},
                "required": [
                    "target_impression_share",
                    "target_impression_share_location",
                    "cpc_bid_ceiling_micros",
                ],
                "message": "TARGET_IMPRESSION_SHARE requires location, share and cpc_bid_ceiling_micros",
            },
        ],
    }


def google_bidding_strategy_update_schema() -> dict[str, Any]:
    return google_bidding_strategy_schema()["properties"]["updates"]


def google_campaign_budget_update_schema() -> dict[str, Any]:
    return _object({
        "name": _field("string", "Budget name", minLength=1, maxLength=255),
        "daily_budget": _field("number", "Daily budget in account currency", minimum=0.01),
        "budget": _field("number", "Daily budget alias", minimum=0.01),
        "delivery_method": _field("string", "Budget delivery method", enum=GOOGLE_BUDGET_DELIVERY_METHODS),
        "explicitly_shared": _field("boolean", "Whether the budget is shared"),
    }, "Allowed CampaignBudget update fields")


def google_app_campaign_setting_schema() -> dict[str, Any]:
    """Closed contract for the settings specific to App campaigns."""
    return _object({
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
        "selective_optimization": _field(
            "array", "Conversion action resource names used for App Engagement",
            minItems=1, items={"type": "string", "minLength": 1},
        ),
    }, "Google App Campaign settings", required=["app_id", "app_store"])


def google_shopping_setting_schema() -> dict[str, Any]:
    """Closed contract for Merchant Center-backed Shopping campaigns."""
    return _object({
        "merchant_id": _field("integer", "Merchant Center ID", minimum=1),
        "sales_country": _field("string", "Shopping sales country", minLength=2, maxLength=3),
        "marketing_language": _field("string", "Shopping marketing language", minLength=2, maxLength=5),
        "priority": _field("integer", "Shopping campaign priority", minimum=0, maximum=100),
        "exclude_offline_store_locations": _field("boolean", "Exclude offline store locations"),
    }, "Google Shopping settings", required=["merchant_id", "sales_country", "marketing_language"])


def google_video_setting_schema() -> dict[str, Any]:
    """Video campaign controls exposed by the hierarchy guide."""
    return _object({
        "smart_performance": _field("boolean", "Enable Smart performance optimization"),
        "video_ad_format_preference": _field(
            "array", "Preferred video ad formats", minItems=1,
            items={"type": "string", "enum": GOOGLE_VIDEO_CAMPAIGN_FORMAT_PREFERENCES},
        ),
    }, "Google Video campaign settings")


def google_targeting_setting_schema() -> dict[str, Any]:
    """Campaign-level audience restriction contract.

    Granular locations, audiences and demographics remain separate
    CampaignCriterion tools.  This object only describes Google's
    ``targetRestrictions`` switch and therefore cannot silently accept an
    arbitrary provider payload.
    """
    return _object({
        "geo_target_type": _field(
            "string", "Geographic targeting behavior", enum=GOOGLE_GEO_TARGET_TYPES,
        ),
        "target_restrictions": _field(
            "array", "Targeting dimensions that should be restricted",
            items=_object({
                "targeting_dimension": _field(
                    "string", "Google targeting dimension", enum=GOOGLE_TARGETING_DIMENSIONS,
                ),
                "bid_only": _field("boolean", "Bid only instead of restricting reach"),
            }, "Target restriction", required=["targeting_dimension"]),
        ),
    }, "Google Campaign targeting settings")


def google_network_setting_schema() -> dict[str, Any]:
    """Serving network switches for Search/Display campaigns."""
    return _object({
        "target_google_search": _field("boolean", "Serve on Google Search"),
        "target_search_partners": _field("boolean", "Serve on Search partners"),
        "target_content_network": _field("boolean", "Serve on the Display/content network"),
    }, "Google Campaign network settings")


def google_campaign_goal_setting_schema() -> dict[str, Any]:
    """PMax goal metadata from the campaign creation contract."""
    return _object({
        "goal_type": _field("string", "Performance Max campaign goal", enum=GOOGLE_PMAX_GOAL_TYPES),
        "ecommerce_checkout_progress": _field(
            "number", "E-commerce checkout progress", minimum=0, maximum=1,
        ),
    }, "Performance Max campaign goal settings", required=["goal_type"])


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
                intent_map=GOOGLE_CHANNEL_TYPE_INTENT_MAP,
            ),
            "campaign_type": _field("string", "Channel type input alias", enum=GOOGLE_CHANNEL_INPUT_TYPES),
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
            "app_campaign_setting": google_app_campaign_setting_schema(),
            "shopping_setting": google_shopping_setting_schema(),
            "campaign_goal_setting": google_campaign_goal_setting_schema(),
            "video_setting": google_video_setting_schema(),
            "targeting_setting": google_targeting_setting_schema(),
            "network_setting": google_network_setting_schema(),
            "final_url_suffix": _field("string", "Final URL suffix for tracking"),
            "start_date": _field("string", "YYYY-MM-DD start date"),
            "end_date": _field("string", "YYYY-MM-DD end date"),
            "target_impression_share_location": _field(
                "string", "Target search result location",
                enum=GOOGLE_TARGET_IMPRESSION_SHARE_LOCATIONS,
            ),
            "cpc_bid_ceiling_micros": _field(
                "integer", "Maximum CPC bid for Target Impression Share", minimum=1,
            ),
            "target_cpm_micros": _field("integer", "Target CPM in account micros", minimum=1),
            "target_cpv_micros": _field("integer", "Target CPV in account micros", minimum=1),
        },
        "conditional_rules": [
            {"id": "target_cpa_dependency", "if": {"bidding_strategy": "TARGET_CPA"},
             "required": ["target_cpa_micros"], "message": "TARGET_CPA requires target_cpa_micros"},
            {"id": "target_roas_dependency", "if": {"bidding_strategy": "TARGET_ROAS"},
             "required": ["target_roas"], "message": "TARGET_ROAS requires target_roas"},
            {"id": "target_impression_share_dependency", "if": {"bidding_strategy": "TARGET_IMPRESSION_SHARE"},
             "required": ["target_impression_share", "target_impression_share_location", "cpc_bid_ceiling_micros"],
             "message": "TARGET_IMPRESSION_SHARE requires share, location and cpc_bid_ceiling_micros"},
            {"id": "target_cpm_dependency", "if": {"bidding_strategy": "TARGET_CPM"},
             "required": ["target_cpm_micros"], "message": "TARGET_CPM requires target_cpm_micros"},
            {"id": "target_cpv_dependency", "if": {"bidding_strategy": "TARGET_CPV"},
             "required": ["target_cpv_micros"], "message": "TARGET_CPV requires target_cpv_micros"},
            {"id": "app_campaign_dependency", "if": {"advertising_channel_type": "MULTI_CHANNEL"},
             "required": ["advertising_channel_sub_type", "app_campaign_setting"],
             "message": "MULTI_CHANNEL App campaigns require advertising_channel_sub_type and app_campaign_setting"},
            {"id": "app_campaign_channel_dependency", "if": {"advertising_channel_sub_type": "APP_CAMPAIGN"},
             "allowed": {"advertising_channel_type": ["MULTI_CHANNEL"]},
             "message": "APP_CAMPAIGN requires advertising_channel_type=MULTI_CHANNEL"},
            {"id": "app_engagement_channel_dependency", "if": {"advertising_channel_sub_type": "APP_CAMPAIGN_FOR_ENGAGEMENT"},
             "allowed": {"advertising_channel_type": ["MULTI_CHANNEL"]},
             "message": "APP_CAMPAIGN_FOR_ENGAGEMENT requires advertising_channel_type=MULTI_CHANNEL"},
            {"id": "app_engagement_selective_optimization", "if": {"advertising_channel_sub_type": "APP_CAMPAIGN_FOR_ENGAGEMENT"},
             "required": ["app_campaign_setting.selective_optimization"],
             "message": "APP_CAMPAIGN_FOR_ENGAGEMENT requires app_campaign_setting.selective_optimization"},
            {"id": "shopping_setting_dependency", "if": {"advertising_channel_type": "SHOPPING"},
             "required": ["shopping_setting"],
             "message": "SHOPPING requires shopping_setting with Merchant Center fields"},
            {"id": "video_setting_dependency", "if": {"advertising_channel_type": "VIDEO"},
             "required": ["video_setting"],
             "message": "VIDEO requires video_setting"},
            {"id": "pmax_goal_setting_dependency", "if": {"advertising_channel_type": "PERFORMANCE_MAX"},
             "required": ["campaign_goal_setting"],
             "message": "PERFORMANCE_MAX requires campaign_goal_setting"},
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


def google_app_ad_group_schema() -> dict[str, Any]:
    """Contract for the Ad Group used by Google App campaigns.

    App campaigns use ``MULTI_CHANNEL`` at Campaign level but still create an
    Ad Group before attaching AppAd assets.  Keep this contract separate from
    Search/Display/Shopping Ad Groups so their provider defaults and required
    fields cannot leak into App campaign planning.
    """
    return {
        "required": ["campaign_id", "name"],
        "provider_required": ["type"],
        "properties": {
            "campaign_id": _field("string", "Parent App Campaign ID", minLength=1),
            "name": _field("string", "App campaign ad group name", maxLength=255),
            "type": _field(
                "string", "Google App campaign ad group type",
                enum=["SEARCH_STANDARD"], default="SEARCH_STANDARD",
            ),
            "status": _field("string", "Ad group status", enum=GOOGLE_STATUSES),
        },
    }


def google_app_ad_schema() -> dict[str, Any]:
    """Dry-run contract for the Google ``Ad.appAd`` asset payload."""
    asset = _field(
        "array", "Existing Google Asset references", minItems=1,
        items={"type": "object", "additionalProperties": True},
    )
    return {
        "required": ["ad_group_id", "name", "headlines", "descriptions"],
        "provider_required": ["headlines", "descriptions"],
        "properties": {
            "ad_group_id": _field("string", "Parent App campaign Ad Group ID", minLength=1),
            "name": _field("string", "App ad name", maxLength=255),
            "headlines": _field(
                "array", "App ad headline text assets", minItems=2, maxItems=5,
                items={"type": "object", "additionalProperties": True},
            ),
            "descriptions": _field(
                "array", "App ad description text assets", minItems=2, maxItems=5,
                items={"type": "object", "additionalProperties": True},
            ),
            "images": asset,
            "videos": asset,
            "html5_media_bundles": asset,
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
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


def google_campaign_criterion_item_schema() -> dict[str, Any]:
    """Schema for one provider-neutral CampaignCriterion specification.

    Google stores location, language, device, audience and demographic
    targeting as one-of fields on CampaignCriterion.  The discriminator and
    explicit value fields keep the Tool contract renderable by a UI while the
    Client performs the type-specific required-field validation before a
    provider mutation.
    """
    return _object({
        "criterion_type": _field(
            "string", "Campaign criterion kind", enum=GOOGLE_CAMPAIGN_CRITERION_TYPES,
        ),
        "status": _field("string", "Criterion status", enum=GOOGLE_CRITERION_STATUSES[:2]),
        "negative": _field("boolean", "Exclude instead of include this criterion"),
        "bid_modifier": _field("number", "Optional bid modifier", minimum=0),
        "location_id": _field(
            "string", "Google geo target constant ID or resource name", minLength=1,
        ),
        "language_id": _field(
            "string", "Google language constant ID or resource name", minLength=1,
        ),
        "user_list_id": _field(
            "string", "Google UserList ID or resource name", minLength=1,
        ),
        "user_interest_id": _field(
            "string", "Google UserInterest ID or resource name", minLength=1,
        ),
        "age_range": _field("string", "Age range", enum=GOOGLE_AGE_RANGES),
        "gender": _field("string", "Gender", enum=GOOGLE_GENDERS),
        "parental_status": _field(
            "string", "Parental status", enum=GOOGLE_PARENTAL_STATUSES,
        ),
        "income_range": _field(
            "string", "Household income range", enum=GOOGLE_INCOME_RANGES,
        ),
        "device": _field("string", "Device type", enum=GOOGLE_CRITERION_DEVICES),
        "content_label": _field(
            "string", "Content label", enum=GOOGLE_CONTENT_LABELS,
        ),
        "placement_url": _field("string", "Placement URL", minLength=1),
        "topic_id": _field(
            "string", "Google topic constant ID or resource name", minLength=1,
        ),
    }, "CampaignCriterion specification", additional_properties=False) | {
        "required": ["criterion_type"],
    }


def google_campaign_criterion_schema() -> dict[str, Any]:
    """Schemas for CampaignCriterion list/get/create/update/delete Tools."""
    item = google_campaign_criterion_item_schema()
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "campaign_id": _field("string", "Parent Campaign ID", minLength=1),
            "criterion_id": _field("string", "Campaign criterion ID", minLength=1),
            "limit": _field("integer", "Maximum number of criteria", minimum=1, maximum=10_000),
            "criteria": _field("array", "Campaign criteria to create", minItems=1, maxItems=1000, items=item),
            "updates": _object({
                "status": _field("string", "Criterion status", enum=GOOGLE_CRITERION_STATUSES),
                "negative": _field("boolean", "Exclude instead of include this criterion"),
                "bid_modifier": _field("number", "Bid modifier", minimum=0),
            }, "Allowed CampaignCriterion update fields", additional_properties=False),
        },
        "conditional_rules": [],
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


def google_video_ad_schema() -> dict[str, Any]:
    """Create contract for the core Google Video Ad formats."""
    return {
        "required": ["ad_group_id", "name", "video_ad_format", "video_id", "final_url"],
        "provider_required": ["video_ad_format", "video_id", "final_url"],
        "properties": {
            "ad_group_id": _field("string", "Parent Video ad group ID", minLength=1),
            "name": _field("string", "Ad name", maxLength=255),
            "ad_type": _field("string", "Ad format family", enum=["VIDEO"], default="VIDEO"),
            "video_ad_format": _field(
                "string", "Video format", enum=GOOGLE_VIDEO_AD_FORMATS,
            ),
            "video_id": _field("string", "YouTube video ID", minLength=1),
            "final_url": _field("string", "Final URL", minLength=1),
            "display_url": _field("string", "Optional display URL"),
            "action_button_label": _field("string", "Optional CTA button label"),
            "action_headline": _field("string", "Optional CTA headline"),
            "companion_banner": _field("object", "Optional companion banner", additionalProperties=True),
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
            "gaps": ["live AssetService mutation approval", "audience signals", "listing groups/product targets"],
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
            "gaps": ["live AssetService mutation approval", "audience signal and listing group Tools"],
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
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_ad_group", "google_create_video_ad"],
            "dependencies": ["YouTube video", "video_setting", "audiences"],
            "supported_fields": ["video_setting", "video_ad_format", "video_id", "final_url"],
            "gaps": ["verified live Video Ad mutation", "video audience/placement Tools"],
            "source_document": source_document,
        },
        {
            "format_id": "video.skippable_in_stream",
            "category": "video",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_video_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_video_ad",
            "dependencies": ["YouTube video", "final_url", "video_setting"],
            "supported_fields": ["video_ad_format", "video_id", "final_url", "action_button_label", "action_headline"],
            "gaps": ["verified live Video Ad mutation"],
            "source_document": source_document,
        },
        {
            "format_id": "video.non_skippable_in_stream",
            "category": "video",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_video_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_video_ad",
            "dependencies": ["YouTube video", "final_url", "video_setting"],
            "supported_fields": ["video_ad_format", "video_id", "final_url"],
            "gaps": ["verified live Video Ad mutation"],
            "source_document": source_document,
        },
        {
            "format_id": "video.bumper",
            "category": "video",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_video_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_video_ad",
            "dependencies": ["YouTube video", "final_url", "video_setting"],
            "supported_fields": ["video_ad_format", "video_id", "final_url"],
            "gaps": ["verified live Video Ad mutation"],
            "source_document": source_document,
        },
        {
            "format_id": "video.outstream",
            "category": "video",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_video_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_video_ad",
            "dependencies": ["YouTube video", "final_url", "video_setting"],
            "supported_fields": ["video_ad_format", "video_id", "final_url"],
            "gaps": ["verified live Video Ad mutation"],
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
            "tool_names": ["google_create_campaign", "google_create_app_ad_group", "google_create_app_ad"],
            "dependencies": ["MULTI_CHANNEL", "advertising_channel_sub_type", "app_campaign_setting", "app assets"],
            "supported_fields": ["app_campaign_setting", "bidding_strategy", "headlines", "descriptions", "images", "videos"],
            "gaps": ["Asset upload/reference validation", "engagement selective optimization", "live provider verification"],
            "source_document": source_document,
        },
        {
            "format_id": "app.install",
            "category": "app",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_app_ad_group", "google_create_app_ad"],
            "dependencies": ["MULTI_CHANNEL", "APP_CAMPAIGN", "app_campaign_setting", "app assets"],
            "supported_fields": ["app_id", "app_store", "bidding_strategy_type", "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST", "headlines", "descriptions"],
            "gaps": ["Asset upload/reference validation", "live provider verification"],
            "source_document": source_document,
        },
        {
            "format_id": "app.engagement",
            "category": "app",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_app_ad_group", "google_create_app_ad"],
            "dependencies": ["MULTI_CHANNEL", "APP_CAMPAIGN_FOR_ENGAGEMENT", "app_campaign_setting", "app assets"],
            "supported_fields": ["app_id", "app_store", "bidding_strategy_type", "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST", "selective_optimization", "headlines", "descriptions"],
            "gaps": ["Asset upload/reference validation", "live provider verification"],
            "source_document": source_document,
        },
        {
            "format_id": "app.ad",
            "category": "app",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_app_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_app_ad",
            "dependencies": ["app_ad_group", "headlines", "descriptions", "images_or_videos"],
            "supported_fields": ["headlines", "descriptions", "images", "videos", "html5_media_bundles"],
            "gaps": ["Asset upload/reference validation", "live provider verification"],
            "source_document": source_document,
        },
        # v24 exposes additional campaign channel types beyond the six
        # formats covered by the current hierarchy guide.  Publish them as
        # explicit gaps so a caller can distinguish an accepted enum from a
        # complete campaign workflow.
        {
            "format_id": "demand_gen",
            "category": "demand_gen",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["demand_gen_ad", "audiences", "assets"],
            "gaps": ["dedicated Demand Gen campaign/ad payload Tools"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "hotel",
            "category": "hotel",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["hotel_ad_group", "hotel_feed"],
            "gaps": ["dedicated Hotel campaign/ad payload Tools"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "local",
            "category": "local",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["business_profile", "local_ad"],
            "gaps": ["dedicated Local campaign/ad payload Tools"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "smart",
            "category": "smart",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["smart_campaign_ad"],
            "gaps": ["dedicated Smart campaign/ad payload Tools"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "travel",
            "category": "travel",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["travel_ad", "travel_feed"],
            "gaps": ["dedicated Travel campaign/ad payload Tools"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "local_services",
            "category": "local_services",
            "resource_type": "campaign",
            "coverage": "declared_only",
            "tool_names": [],
            "dependencies": ["local_services_lead"],
            "gaps": ["dedicated Local Services API integration"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
    ]


def google_asset_schema() -> dict[str, Any]:
    """Schema for customer-level reusable Google Asset reads."""
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "asset_id": _field("string", "Google Asset ID", minLength=1),
            "limit": _field("integer", "Maximum number of assets", minimum=1, maximum=10000),
        },
    }


def google_asset_create_schema() -> dict[str, Any]:
    """Schema for reusable text, image, video and HTML5 assets."""
    return {
        "required": ["customer_id", "asset_type"],
        "provider_required": ["asset_type"],
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "asset_type": _field("string", "Asset payload type", enum=GOOGLE_ASSET_TYPES),
            "name": _field("string", "Optional asset name", minLength=1, maxLength=255),
            "text": _field("string", "Text asset content", minLength=1),
            "file_path": _field("string", "Local image or HTML5 ZIP file path", minLength=1),
            "mime_type": _field("string", "Image MIME enum", enum=GOOGLE_ASSET_IMAGE_MIME_TYPES),
            "youtube_video_id": _field("string", "11-character YouTube video ID", minLength=11, maxLength=11),
            "youtube_video_title": _field("string", "YouTube video title", minLength=1),
            "final_urls": _field("array", "Optional final URLs", items={"type": "string"}),
            "final_mobile_urls": _field("array", "Optional final mobile URLs", items={"type": "string"}),
            "tracking_url_template": _field("string", "Optional tracking URL template"),
            "final_url_suffix": _field("string", "Optional final URL suffix"),
        },
        "conditional_rules": [
            {"id": "text_asset_dependency", "if": {"asset_type": "TEXT"},
             "required": ["text"], "message": "TEXT assets require text"},
            {"id": "image_asset_dependency", "if": {"asset_type": "IMAGE"},
             "required": ["file_path", "mime_type"], "message": "IMAGE assets require file_path and mime_type"},
            {"id": "youtube_asset_dependency", "if": {"asset_type": "YOUTUBE_VIDEO"},
             "required": ["youtube_video_id", "youtube_video_title"],
             "message": "YOUTUBE_VIDEO assets require youtube_video_id and youtube_video_title"},
            {"id": "media_bundle_dependency", "if": {"asset_type": "MEDIA_BUNDLE"},
             "required": ["file_path"], "message": "MEDIA_BUNDLE assets require file_path"},
        ],
    }


def google_asset_group_schema() -> dict[str, Any]:
    asset = _field("array", "Asset references", minItems=1, items={"type": "object", "additionalProperties": True})
    return {
        "required": [
            "campaign_id", "name", "asset_group_type", "final_urls",
            "headlines", "long_headlines", "descriptions",
        ],
        "provider_required": [
            "asset_group_type", "final_urls", "headlines",
            "long_headlines", "descriptions",
        ],
        "properties": {
            "campaign_id": _field("string", "Parent Performance Max Campaign ID"),
            "name": _field("string", "Asset group name", maxLength=255),
            "asset_group_type": _field("string", "Asset group type", enum=GOOGLE_ASSET_GROUP_TYPES),
            "final_urls": _field("array", "Asset group landing page URLs", minItems=1, maxItems=20, items={"type": "string", "minLength": 1}),
            "final_mobile_urls": _field("array", "Optional mobile landing page URLs", maxItems=20, items={"type": "string", "minLength": 1}),
            "headlines": _field("array", "Text headline assets or existing Asset references", minItems=3, maxItems=15, items={"type": "object", "additionalProperties": True}),
            "long_headlines": _field("array", "Long headline assets or existing Asset references", minItems=1, maxItems=5, items={"type": "object", "additionalProperties": True}),
            "descriptions": _field("array", "Description assets", minItems=2, maxItems=5, items={"type": "object", "additionalProperties": True}),
            "images": asset,
            "videos": asset,
            "logos": asset,
            "status": _field("string", "Asset group status", enum=GOOGLE_STATUSES),
        },
    }
