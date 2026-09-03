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
GOOGLE_CAMPAIGN_ASSET_FIELD_TYPES = [
    "HEADLINE", "DESCRIPTION", "LONG_HEADLINE", "MARKETING_IMAGE",
    "MEDIA_BUNDLE", "YOUTUBE_VIDEO", "LOGO", "LANDSCAPE_LOGO",
    "BUSINESS_NAME", "CALL_TO_ACTION", "CALLOUT", "SITELINK",
    "STRUCTURED_SNIPPET", "PRICE", "PROMOTION", "MOBILE_APP",
    "CALL", "LEAD_FORM", "HOTEL_CALLOUT", "BOOK_ON_GOOGLE",
]
GOOGLE_ASSET_GROUP_ASSET_FIELD_TYPES = [
    "HEADLINE", "LONG_HEADLINE", "DESCRIPTION", "MARKETING_IMAGE",
    "SQUARE_MARKETING_IMAGE", "PORTRAIT_MARKETING_IMAGE", "LOGO",
    "LANDSCAPE_LOGO", "YOUTUBE_VIDEO", "MEDIA_BUNDLE",
    "CALL_TO_ACTION_SELECTION", "BUSINESS_NAME",
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
GOOGLE_VIDEO_AD_FORMATS = [
    "SKIPPABLE_IN_STREAM", "NON_SKIPPABLE_IN_STREAM", "BUMPER", "OUTSTREAM",
]
GOOGLE_VIDEO_CAMPAIGN_FORMAT_PREFERENCES = [
    "TRUE_VIEW_IN_STREAM", "NON_TRUE_VIEW_IN_STREAM", "BUMPER", "OUTSTREAM",
]
GOOGLE_LOCAL_LOCATION_SOURCE_TYPES = [
    "GOOGLE_MY_BUSINESS", "AFFILIATE",
]
GOOGLE_DEMAND_GEN_CHANNEL_CONFIGS = ["CHANNEL_STRATEGY", "SELECTED_CHANNELS"]
GOOGLE_DEMAND_GEN_CHANNEL_STRATEGIES = [
    "ALL_CHANNELS", "ALL_OWNED_AND_OPERATED_CHANNELS",
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
GOOGLE_EXPERIMENT_TYPES = [
    "DISPLAY_AND_VIDEO_360", "AD_VARIATION", "YOUTUBE_CUSTOM", "DISPLAY_CUSTOM",
    "SEARCH_CUSTOM", "DISPLAY_AUTOMATED_BIDDING_STRATEGY",
    "SEARCH_AUTOMATED_BIDDING_STRATEGY", "SHOPPING_AUTOMATED_BIDDING_STRATEGY",
    "SMART_MATCHING", "HOTEL_CUSTOM", "OPTIMIZE_ASSETS", "ADOPT_AI_MAX",
    "ADOPT_BROAD_MATCH_KEYWORDS", "PMAX_REPLACEMENT_SHOPPING",
]
GOOGLE_EXPERIMENT_STATUSES = [
    "ENABLED", "REMOVED", "HALTED", "PROMOTED", "SETUP", "INITIATED", "GRADUATED",
]
GOOGLE_EXPERIMENT_METRICS = [
    "CLICKS", "IMPRESSIONS", "COST", "CONVERSIONS_PER_INTERACTION_RATE",
    "COST_PER_CONVERSION", "CONVERSIONS_VALUE_PER_COST", "AVERAGE_CPC", "CTR",
    "INCREMENTAL_CONVERSIONS", "COMPLETED_VIDEO_VIEWS", "CUSTOM_ALGORITHMS",
    "CONVERSIONS", "CONVERSION_VALUE",
]
GOOGLE_EXPERIMENT_METRIC_DIRECTIONS = [
    "NO_CHANGE", "INCREASE", "DECREASE", "NO_CHANGE_OR_INCREASE",
    "NO_CHANGE_OR_DECREASE",
]
GOOGLE_VIDEO_EXPERIMENT_SUBTYPES = ["DEMAND_GEN_ASSET", "ASSET", "ASSET_UPLIFT"]
GOOGLE_OPTIMIZE_ASSETS_EXPERIMENT_SUBTYPES = [
    "ADD_ASSETS_TO_ASSETLESS_RETAIL", "ADD_VIDEO_ASSETS_TO_VIDEOLESS", "COMPARE_ASSETS",
]


def _field(field_type: Any, description: str = "", **kwargs: Any) -> dict[str, Any]:
    value = {"type": field_type, "description": description}
    value.update(kwargs)
    return value


def _ui_when(field: str, *values: str) -> dict[str, Any]:
    """Declare a provider-field applicability rule for creation cards."""
    return {"ui_visible_when": {"field": field, "in": list(values)}}


def _ui_equals(field: str, value: str) -> dict[str, Any]:
    return {"ui_visible_when": {"field": field, "equals": value}}


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


def _google_asset_ref_item(description: str) -> dict[str, Any]:
    """A reusable Asset reference that can be selected or pasted explicitly.

    Google ad payloads accept either an Asset resource name/object or, in the
    dry-run contract, a provider-shaped object.  Keeping the lookup metadata
    on the item as well as on the surrounding array is important for nested
    editors such as Demand Gen carousel cards.
    """
    return _field(
        ["string", "object"], description,
        additionalProperties=True,
        lookup_tool="google_list_assets",
        lookup_result_key="assets",
        lookup_account_required=True,
        selection_value_fields=["resource_name", "asset_id", "id"],
        selection_label_fields=["name", "text", "resource_name", "id"],
        presentation="asset_picker",
    )


def _google_asset_refs(description: str, *, min_items: int = 1) -> dict[str, Any]:
    """Build an account-scoped, multi-select Asset reference field."""
    return _field(
        "array", description, minItems=min_items,
        items=_google_asset_ref_item(description),
        lookup_tool="google_list_assets", lookup_result_key="assets",
        lookup_account_required=True,
        selection_value_fields=["resource_name", "asset_id", "id"],
        selection_label_fields=["name", "text", "resource_name", "id"],
        presentation="asset_picker",
    )


def _google_text_assets(
    description: str, *, min_items: int = 1, max_items: int | None = None,
) -> dict[str, Any]:
    """Build a text-asset list that renders as editable lines in A2UI."""
    kwargs: dict[str, Any] = {"minItems": min_items, "presentation": "text_list"}
    if max_items is not None:
        kwargs["maxItems"] = max_items
    return _field(
        "array", description,
        items={"type": ["string", "object"], "additionalProperties": True},
        **kwargs,
    )


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


def google_experiment_schema() -> dict[str, Any]:
    """Schema for Google ExperimentService create/read lifecycle Tools."""
    goal = _object({
        "metric": _field("string", "Experiment metric", enum=GOOGLE_EXPERIMENT_METRICS),
        "direction": _field(
            "string", "Desired metric direction", enum=GOOGLE_EXPERIMENT_METRIC_DIRECTIONS
        ),
    }, "Experiment success metric", required=["metric", "direction"])
    return {
        "required": ["customer_id", "name", "type"],
        "provider_required": ["name", "type"],
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID; MCC is not accepted"),
            "experiment_id": _field("string", "Experiment ID", minLength=1),
            "name": _field("string", "Experiment name", minLength=1, maxLength=1024),
            "description": _field("string", "Experiment description", minLength=1, maxLength=2048),
            "suffix": _field("string", "Suffix for generated experiment campaigns", maxLength=255),
            "type": _field("string", "Google Experiment type", enum=GOOGLE_EXPERIMENT_TYPES),
            "status": _field("string", "Advertiser-chosen experiment status", enum=GOOGLE_EXPERIMENT_STATUSES),
            "start_date": _field("string", "Start date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$"),
            "end_date": _field("string", "End date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$"),
            "goals": _field("array", "Experiment metric goals", items=goal, minItems=1),
            "sync_enabled": _field("boolean", "Sync base campaign changes to trial campaigns"),
            "video_experiment_subtype": _field("string", "YOUTUBE_CUSTOM experiment subtype", enum=GOOGLE_VIDEO_EXPERIMENT_SUBTYPES),
            "optimize_assets_experiment_subtype": _field("string", "OPTIMIZE_ASSETS experiment subtype", enum=GOOGLE_OPTIMIZE_ASSETS_EXPERIMENT_SUBTYPES),
            "limit": _field("integer", "Maximum number of experiments", minimum=1, maximum=10000),
            "query": _field("string", "Optional GAQL query for experiment reads"),
        },
        "conditional_rules": [
            {"id": "video_experiment_subtype", "if": {"type": "YOUTUBE_CUSTOM"},
             "required": ["video_experiment_subtype"],
             "message": "YOUTUBE_CUSTOM experiments require video_experiment_subtype"},
            {"id": "optimize_assets_experiment_subtype", "if": {"type": "OPTIMIZE_ASSETS"},
             "required": ["optimize_assets_experiment_subtype"],
             "message": "OPTIMIZE_ASSETS experiments require optimize_assets_experiment_subtype"},
        ],
    }


def google_experiment_update_schema() -> dict[str, Any]:
    schema = google_experiment_schema()
    properties = schema["properties"]
    return {
        "type": "object",
        "description": "Mutable Google Experiment fields; immutable type and sync settings are excluded",
        "additionalProperties": False,
        "properties": {
            key: properties[key]
            for key in ("name", "description", "suffix", "status", "start_date", "end_date", "goals")
        },
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
        "app_id": _field(
            "string", "Google Play package name or iOS App Store ID", minLength=1,
            manual_entry={
                "title": "应用标识",
                "instructions": "Google App Campaign 需要应用包名或 App Store ID；当前 Google Ads Capability 未声明通用应用列表查询 Tool，请提供已在账号中关联的应用标识。",
                "example": "com.example.app",
            },
        ),
        "app_store": _field(
            "string", "App store", enum=GOOGLE_APP_STORES,
            option_labels={"GOOGLE_APP_STORE": "Google Play", "APPLE_APP_STORE": "Apple App Store"},
        ),
        "bidding_strategy_type": _field(
            "string", "App campaign bidding strategy", enum=GOOGLE_APP_BIDDING_TYPES,
            option_labels={
                "TARGET_CPA": "目标 CPA", "TARGET_ROAS": "目标 ROAS",
                "MAXIMIZE_CONVERSIONS": "最大化转化次数",
                "MAXIMIZE_CONVERSION_VALUE": "最大化转化价值",
            },
        ),
        "bidding_strategy_goal_type": _field(
            "string", "App campaign optimization goal", enum=[
                "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
                "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST",
            ], option_labels={
                "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST": "优化安装量（目标安装成本）",
                "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST": "优化应用内转化（目标安装成本）",
            },
        ),
        "selective_optimization": _field(
            "array", "Conversion action resource names used for App Engagement",
            minItems=1, items={"type": "string", "minLength": 1},
            lookup_tool="google_list_conversion_actions",
            lookup_result_key="conversion_actions",
            selection_value_fields=["resource_name", "conversion_action_id", "id"],
            selection_label_fields=["name", "resource_name", "id"],
        ),
    }, "Google App Campaign settings", required=["app_id", "app_store"])


def google_shopping_setting_schema() -> dict[str, Any]:
    """Closed contract for Merchant Center-backed Shopping campaigns."""
    return _object({
        "merchant_id": _field(
            "integer", "Merchant Center ID", minimum=1,
            manual_entry={
                "title": "Merchant Center ID",
                "instructions": "请输入已关联到 Google Ads 账号的 Merchant Center ID；当前 Capability 没有 Merchant Center 列表接口。",
            },
        ),
        "sales_country": _field(
            "string", "Shopping sales country", minLength=2, maxLength=3,
            manual_entry={
                "title": "销售国家/地区",
                "instructions": "请输入 Merchant Center feed 中配置的国家/地区代码，例如 US、GB。",
            },
        ),
        "marketing_language": _field(
            "string", "Shopping marketing language", minLength=2, maxLength=5,
            manual_entry={
                "title": "营销语言",
                "instructions": "请输入 Merchant Center feed 支持的语言代码，例如 en、zh。",
            },
        ),
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


def google_demand_gen_campaign_setting_schema() -> dict[str, Any]:
    """Campaign-level Demand Gen settings from Google Ads v24."""
    return _object({
        "upgraded_targeting": _field(
            "boolean", "Enable Demand Gen upgraded targeting",
        ),
    }, "Google Demand Gen campaign settings")


def google_hotel_setting_schema() -> dict[str, Any]:
    """Hotel Center linkage required by Hotel campaigns."""
    return _object({
        "hotel_center_id": _field(
            "string", "Hotel Center account ID", minLength=1,
            manual_entry={
                "title": "Hotel Center 账号 ID",
                "instructions": "请输入已关联到 Google Ads 的 Hotel Center 账号 ID；当前 Capability 没有 Hotel Center 列表接口。",
            },
        ),
        "disable_hotel_setting": _field(
            "boolean", "Disable Hotel Center settings for this campaign",
        ),
    }, "Google Hotel campaign settings", required=["hotel_center_id"])


def google_local_campaign_setting_schema() -> dict[str, Any]:
    """Business profile source for Local campaigns."""
    return _object({
        "location_source_type": _field(
            "string", "Source of business locations",
            enum=GOOGLE_LOCAL_LOCATION_SOURCE_TYPES,
        ),
    }, "Google Local campaign settings", required=["location_source_type"])


def google_travel_campaign_setting_schema() -> dict[str, Any]:
    """Travel account linkage required by Travel campaigns."""
    return _object({
        "travel_account_id": _field(
            "string", "Travel account ID", minLength=1,
            manual_entry={
                "title": "Travel 账号 ID",
                "instructions": "请输入已关联到 Google Ads 的 Travel 账号 ID；当前 Capability 没有 Travel 账号列表接口。",
            },
        ),
    }, "Google Travel campaign settings", required=["travel_account_id"])


def google_local_services_campaign_setting_schema() -> dict[str, Any]:
    """Declared contract for Local Services category bids.

    Local Services uses additional Local Services resources and operations;
    this schema is intentionally descriptive until that API is integrated.
    """
    return _object({
        "category_bids": _field(
            "array", "Local Services category bids",
            items={"type": "object", "additionalProperties": False},
        ),
    }, "Google Local Services campaign settings")


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
            # Compatibility input alias for intent/planner payloads.  The
            # creation card exposes the canonical advertising_channel_type;
            # App's selector may still reference this field explicitly.
            "campaign_type": _field(
                "string", "Channel type input alias", enum=GOOGLE_CHANNEL_INPUT_TYPES,
                ui_hidden=True,
            ),
            "advertising_channel_sub_type": _field(
                "string", "Channel subtype (App campaigns and Performance Max)",
                enum=GOOGLE_CHANNEL_SUB_TYPES,
                **_ui_when("advertising_channel_type", "MULTI_CHANNEL"),
            ),
            "bidding_strategy": _field(
                "string", "Bidding strategy", enum=GOOGLE_BIDDING_STRATEGIES,
                default="MAXIMIZE_CONVERSIONS",
            ),
            "daily_budget": _field("number", "Daily budget in account currency", minimum=0),
            "budget": _field(
                "number", "Daily budget alias", minimum=0, ui_hidden=True,
            ),
            "status": _field("string", "Campaign status", enum=GOOGLE_STATUSES),
            "target_cpa_micros": _field(
                "integer", "Target CPA in micros", minimum=1,
                **_ui_equals("bidding_strategy", "TARGET_CPA"),
            ),
            "target_roas": _field(
                "number", "Target ROAS", minimum=0.01,
                **_ui_equals("bidding_strategy", "TARGET_ROAS"),
            ),
            "target_impression_share": _field(
                "number", "Target impression share", minimum=0, maximum=1,
                **_ui_equals("bidding_strategy", "TARGET_IMPRESSION_SHARE"),
            ),
            "networks": _field(
                "array", "Serving networks", items={"type": "string", "enum": GOOGLE_TARGETING_NETWORKS},
                **_ui_when("advertising_channel_type", "SEARCH", "DISPLAY"),
            ),
            "app_campaign_setting": {
                **google_app_campaign_setting_schema(),
                **_ui_when("advertising_channel_type", "MULTI_CHANNEL"),
            },
            "shopping_setting": {
                **google_shopping_setting_schema(),
                **_ui_equals("advertising_channel_type", "SHOPPING"),
            },
            "campaign_goal_setting": {
                **google_campaign_goal_setting_schema(),
                **_ui_equals("advertising_channel_type", "PERFORMANCE_MAX"),
            },
            "video_setting": {
                **google_video_setting_schema(),
                **_ui_equals("advertising_channel_type", "VIDEO"),
            },
            "demand_gen_campaign_settings": {
                **google_demand_gen_campaign_setting_schema(),
                **_ui_equals("advertising_channel_type", "DEMAND_GEN"),
            },
            "hotel_setting": {
                **google_hotel_setting_schema(),
                **_ui_equals("advertising_channel_type", "HOTEL"),
            },
            "local_campaign_setting": {
                **google_local_campaign_setting_schema(),
                **_ui_equals("advertising_channel_type", "LOCAL"),
            },
            "travel_campaign_settings": {
                **google_travel_campaign_setting_schema(),
                **_ui_equals("advertising_channel_type", "TRAVEL"),
            },
            "local_services_campaign_settings": {
                **google_local_services_campaign_setting_schema(),
                **_ui_equals("advertising_channel_type", "LOCAL_SERVICES"),
            },
            "targeting_setting": google_targeting_setting_schema(),
            "network_setting": {
                **google_network_setting_schema(),
                **_ui_when("advertising_channel_type", "SEARCH", "DISPLAY"),
            },
            "final_url_suffix": _field("string", "Final URL suffix for tracking"),
            "start_date": _field("string", "YYYY-MM-DD start date"),
            "end_date": _field("string", "YYYY-MM-DD end date"),
            "target_impression_share_location": _field(
                "string", "Target search result location",
                enum=GOOGLE_TARGET_IMPRESSION_SHARE_LOCATIONS,
                **_ui_equals("bidding_strategy", "TARGET_IMPRESSION_SHARE"),
            ),
            "cpc_bid_ceiling_micros": _field(
                "integer", "Maximum CPC bid for Target Impression Share", minimum=1,
                **_ui_equals("bidding_strategy", "TARGET_IMPRESSION_SHARE"),
            ),
            "target_cpm_micros": _field(
                "integer", "Target CPM in account micros", minimum=1,
                **_ui_equals("bidding_strategy", "TARGET_CPM"),
            ),
            "target_cpv_micros": _field(
                "integer", "Target CPV in account micros", minimum=1,
                **_ui_when("bidding_strategy", "MANUAL_CPV", "TARGET_CPV"),
            ),
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
            {"id": "demand_gen_setting_dependency", "if": {"advertising_channel_type": "DEMAND_GEN"},
             "required": ["demand_gen_campaign_settings"],
             "message": "DEMAND_GEN requires demand_gen_campaign_settings"},
            {"id": "hotel_setting_dependency", "if": {"advertising_channel_type": "HOTEL"},
             "required": ["hotel_setting"],
             "message": "HOTEL requires hotel_setting with hotel_center_id"},
            {"id": "local_setting_dependency", "if": {"advertising_channel_type": "LOCAL"},
             "required": ["local_campaign_setting"],
             "message": "LOCAL requires local_campaign_setting"},
            {"id": "travel_setting_dependency", "if": {"advertising_channel_type": "TRAVEL"},
             "required": ["travel_campaign_settings"],
             "message": "TRAVEL requires travel_campaign_settings"},
            {"id": "local_services_setting_dependency", "if": {"advertising_channel_type": "LOCAL_SERVICES"},
             "required": ["local_services_campaign_settings"],
             "message": "LOCAL_SERVICES requires local_services_campaign_settings"},
        ],
    }


def google_ad_group_schema() -> dict[str, Any]:
    return {
        "required": ["campaign_id", "name"],
        "provider_required": ["type"],
        "properties": {
            "campaign_id": _field("string", "Parent Campaign ID"),
            "campaign_type": _field(
                "string", "Parent campaign type used to select the provider ad-group default",
                enum=GOOGLE_CHANNEL_INPUT_TYPES, ui_hidden=True,
            ),
            "name": _field("string", "Ad group name", maxLength=255),
            "type": _field("string", "Ad group type", enum=[
                *GOOGLE_AD_GROUP_TYPES,
                "HOTEL_ADS", "PROMOTED_HOTEL_ADS", "VIDEO_NON_SKIPPABLE_IN_STREAM",
                "VIDEO_TRUE_VIEW_IN_DISPLAY", "VIDEO_RESPONSIVE", "SMART_CAMPAIGN_ADS",
                "TRAVEL_ADS", "YOUTUBE_AUDIO",
            ], default="SEARCH_STANDARD"),
            "cpc_bid": _field(
                "number", "CPC bid in account currency", minimum=0,
                **_ui_when("campaign_type", "SEARCH", "DISPLAY", "SHOPPING"),
            ),
            "cpc_bid_micros": _field(
                "integer", "CPC bid in micros", minimum=0,
                **_ui_when("campaign_type", "SEARCH", "DISPLAY", "SHOPPING"),
            ),
            "status": _field("string", "Ad group status", enum=GOOGLE_STATUSES),
            "targeting": _field("object", "Ad group targeting", additionalProperties=True),
            "demand_gen_ad_group_settings": {
                **_object({
                "channel_controls": _object({
                    "channel_config": _field(
                        "string", "Demand Gen channel configuration",
                        enum=GOOGLE_DEMAND_GEN_CHANNEL_CONFIGS,
                    ),
                    "channel_strategy": _field(
                        "string", "Demand Gen channel strategy",
                        enum=GOOGLE_DEMAND_GEN_CHANNEL_STRATEGIES,
                    ),
                    "selected_channels": _object({
                        key: _field("boolean", f"Enable Demand Gen {key}")
                        for key in (
                            "youtube_shorts", "youtube_in_feed", "youtube_in_stream",
                            "gmail", "maps", "discover", "display",
                        )
                    }, "Selected Demand Gen channels"),
                }, "Demand Gen channel controls"),
                }, "Demand Gen ad group settings"),
                **_ui_equals("campaign_type", "DEMAND_GEN"),
            },
        },
        "conditional_rules": [
            {"id": "demand_gen_ad_group_setting_dependency",
             "if": {"campaign_type": "DEMAND_GEN"},
             "required": ["demand_gen_ad_group_settings"],
             "message": "DEMAND_GEN ad groups require demand_gen_ad_group_settings"},
        ],
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
    asset = _google_asset_refs("Existing Google Asset references")
    return {
        "required": ["ad_group_id", "name", "headlines", "descriptions"],
        "provider_required": ["headlines", "descriptions"],
        "properties": {
            "ad_group_id": _field("string", "Parent App campaign Ad Group ID", minLength=1),
            "name": _field("string", "App ad name", maxLength=255),
            "headlines": _field(
                "array", "App ad headline text assets", minItems=2, maxItems=5,
                items={"type": ["string", "object"], "additionalProperties": True},
                presentation="text_list",
            ),
            "descriptions": _field(
                "array", "App ad description text assets", minItems=2, maxItems=5,
                items={"type": ["string", "object"], "additionalProperties": True},
                presentation="text_list",
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


def google_keyword_update_schema() -> dict[str, Any]:
    """Closed mutable-field contract for one keyword criterion update."""
    return _object({
        "status": _field(
            "string", "Keyword criterion status", enum=GOOGLE_STATUSES[:2]
        ),
        "cpc_bid_micros": _field(
            "integer", "Criterion CPC bid in micros", minimum=0
        ),
    }, "Mutable Google AdGroupCriterion keyword fields")


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
            manual_entry={
                "title": "地理位置常量 ID",
                "instructions": "请从 Google Ads 地理位置目标列表或 Google Ads UI 复制常量 ID/资源名；当前没有本 Capability 的地理位置目录 Tool。",
                "source": "provider_geo_target",
            },
        ),
        "language_id": _field(
            "string", "Google language constant ID or resource name", minLength=1,
            manual_entry={
                "title": "语言常量 ID",
                "instructions": "请从 Google Ads 语言目标列表或 UI 复制常量 ID/资源名；当前没有本 Capability 的语言目录 Tool。",
                "source": "provider_language_target",
            },
        ),
        "user_list_id": _field(
            "string", "Google UserList ID or resource name", minLength=1,
            lookup_tool="google_list_user_lists", lookup_result_key="user_lists",
            selection_value_fields=["resource_name", "user_list_id", "id"],
            selection_label_fields=["name", "resource_name", "id"],
        ),
        "user_interest_id": _field(
            "string", "Google UserInterest ID or resource name", minLength=1,
            manual_entry={
                "title": "用户兴趣 ID",
                "instructions": "请从 Google Ads 用户兴趣目标列表或 UI 复制 ID/资源名；当前没有本 Capability 的用户兴趣目录 Tool。",
                "source": "provider_user_interest",
            },
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
            manual_entry={
                "title": "主题目标 ID",
                "instructions": "请从 Google Ads 主题目标列表或 UI 复制主题常量 ID/资源名；当前没有本 Capability 的主题目录 Tool。",
                "source": "provider_topic_target",
            },
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


def google_product_group_update_schema() -> dict[str, Any]:
    """Mutable fields for a Standard Shopping listing-group criterion."""
    return _object({
        "status": _field(
            "string", "Listing-group status", enum=GOOGLE_STATUSES,
        ),
        "cpc_bid_micros": _field(
            "integer", "Product partition CPC bid in micros", minimum=0,
        ),
        "cpc_bid": _field(
            "number", "Product partition CPC bid in account currency", minimum=0,
        ),
    }, "Allowed Product Group update fields", additional_properties=False)


def google_product_group_read_schema() -> dict[str, Any]:
    """Common identity/selection fields for Product Group read Tools."""
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "ad_group_id": _field("string", "Parent Shopping ad group ID", minLength=1),
            "product_group_id": _field(
                "string", "AdGroupCriterion listing-group criterion ID", minLength=1,
            ),
            "limit": _field(
                "integer", "Maximum number of product groups", minimum=1, maximum=10_000,
            ),
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
            "ad_type": _field("string", "Ad format", enum=["RESPONSIVE_SEARCH_AD", "EXPANDED_TEXT_AD", "RESPONSIVE_DISPLAY_AD", "VIDEO"]),
            "headlines": _field(
                "array", "Ad headlines", minItems=3, maxItems=15,
                items={"type": "string", "minLength": 1, "maxLength": 30},
                **_ui_equals("ad_type", "RESPONSIVE_SEARCH_AD"),
            ),
            "descriptions": _field(
                "array", "Ad descriptions", minItems=2, maxItems=4,
                items={"type": "string", "minLength": 1, "maxLength": 90},
                **_ui_equals("ad_type", "RESPONSIVE_SEARCH_AD"),
            ),
            "final_url": _field("string", "Final URL", minLength=1),
            "path1": _field(
                "string", "Display path 1", maxLength=15,
                **_ui_when("ad_type", "RESPONSIVE_SEARCH_AD", "EXPANDED_TEXT_AD"),
            ),
            "path2": _field(
                "string", "Display path 2", maxLength=15,
                **_ui_when("ad_type", "RESPONSIVE_SEARCH_AD", "EXPANDED_TEXT_AD"),
            ),
            "responsive_search_ad": {
                **_field("object", "Responsive Search Ad payload", additionalProperties=True),
                **_ui_equals("ad_type", "RESPONSIVE_SEARCH_AD"),
            },
            "responsive_display_ad": {
                **_field("object", "Responsive Display Ad payload", additionalProperties=True),
                **_ui_equals("ad_type", "RESPONSIVE_DISPLAY_AD"),
            },
            "video": {
                **_field("object", "Video ad payload", additionalProperties=True),
                **_ui_equals("ad_type", "VIDEO"),
            },
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
    image_asset = _google_asset_refs("Provider image asset references")
    return {
        "required": ["ad_group_id", "name", "final_url", "headlines", "long_headline", "descriptions", "business_name"],
        "provider_required": ["headlines", "long_headline", "descriptions", "business_name"],
        "properties": {
            "ad_group_id": _field("string", "Parent Display ad group ID"),
            "name": _field("string", "Ad name", maxLength=255),
            "ad_type": _field("string", "Ad format", enum=["RESPONSIVE_DISPLAY_AD"], default="RESPONSIVE_DISPLAY_AD"),
            "headlines": _field(
                "array", "Short headline assets", minItems=3, maxItems=5,
                items=text_asset, presentation="text_list",
            ),
            "long_headline": text_asset,
            "descriptions": _field(
                "array", "Description assets", minItems=1, maxItems=5,
                items=text_asset, presentation="text_list",
            ),
            "business_name": _field("string", "Advertiser business name", minLength=1, maxLength=25),
            "marketing_images": image_asset,
            "square_marketing_images": image_asset,
            "logos": image_asset,
            "landscape_logos": image_asset,
            "videos": _field(
                "array", "YouTube video asset references",
                items=_google_asset_ref_item("YouTube video asset reference"),
                lookup_tool="google_list_assets", lookup_result_key="assets",
                lookup_account_required=True,
                selection_value_fields=["resource_name", "asset_id", "id"],
                selection_label_fields=["name", "text", "resource_name", "id"],
                presentation="asset_picker",
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
            "video_id": _field(
                "string", "YouTube video ID", minLength=1,
                manual_entry={
                    "title": "YouTube 视频 ID",
                    "instructions": "Google Ads 当前没有可直接用于此字段的 YouTube 视频目录查询；请粘贴 YouTube URL 中的 11 位视频 ID。",
                    "example": "dQw4w9WgXcQ",
                    "source": "external_youtube_identifier",
                },
            ),
            "final_url": _field("string", "Final URL", minLength=1),
            "display_url": _field("string", "Optional display URL"),
            "action_button_label": _field("string", "Optional CTA button label"),
            "action_headline": _field("string", "Optional CTA headline"),
            "companion_banner": _field("object", "Optional companion banner", additionalProperties=True),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def _google_ad_text_assets(description: str, *, min_items: int = 1, max_items: int | None = None) -> dict[str, Any]:
    return _google_text_assets(description, min_items=min_items, max_items=max_items)


def _google_ad_asset_refs(description: str, *, min_items: int = 1) -> dict[str, Any]:
    return _google_asset_refs(description, min_items=min_items)


def google_demand_gen_multi_asset_ad_schema() -> dict[str, Any]:
    """Demand Gen multi-asset ad contract backed by ``Ad.demandGenMultiAssetAd``."""
    return {
        "required": ["ad_group_id", "name", "final_url", "headlines", "descriptions", "business_name"],
        "provider_required": ["headlines", "descriptions", "business_name"],
        "properties": {
            "ad_group_id": _field("string", "Parent Demand Gen ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
            "final_url": _field("string", "Final URL", minLength=1),
            "headlines": _google_ad_text_assets("Demand Gen headlines", min_items=3, max_items=5),
            "descriptions": _google_ad_text_assets("Demand Gen descriptions", min_items=2, max_items=5),
            "business_name": _field("string", "Advertiser business name", minLength=1, maxLength=25),
            "marketing_images": _google_ad_asset_refs("Landscape marketing image assets"),
            "square_marketing_images": _google_ad_asset_refs("Square marketing image assets"),
            "portrait_marketing_images": _google_ad_asset_refs("Portrait marketing image assets"),
            "tall_portrait_marketing_images": _google_ad_asset_refs("Tall portrait marketing image assets"),
            "classic_display_images": _google_ad_asset_refs("Classic display image assets"),
            "logo_images": _google_ad_asset_refs("Logo image assets"),
            "call_to_action_text": _field("string", "Call to action text"),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_demand_gen_carousel_ad_schema() -> dict[str, Any]:
    """Demand Gen carousel ad contract backed by ``Ad.demandGenCarouselAd``."""
    carousel_asset = _google_asset_ref_item(
        "Carousel card image Asset resource name or reference"
    )
    return {
        "required": ["ad_group_id", "name", "final_url", "headline", "description", "carousel_cards"],
        "provider_required": ["headline", "description", "carousel_cards"],
        "properties": {
            "ad_group_id": _field("string", "Parent Demand Gen ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
            "final_url": _field("string", "Final URL", minLength=1),
            "headline": _field("string", "Carousel headline", minLength=1),
            "description": _field("string", "Carousel description", minLength=1),
            "business_name": _field("string", "Advertiser business name", minLength=1, maxLength=25),
            "logo_image": _google_asset_ref_item("Logo image asset reference"),
            "call_to_action_text": _field("string", "Call to action text"),
            "carousel_cards": _field(
                "array", "Demand Gen carousel cards", minItems=2, maxItems=10,
                presentation="object_editor",
                items=_object({
                    "headline": _field("string", "Card headline", minLength=1),
                    "marketing_image_asset": carousel_asset,
                    "square_marketing_image_asset": _google_asset_ref_item(
                        "1:1 image Asset resource name or reference"
                    ),
                    "portrait_marketing_image_asset": _google_asset_ref_item(
                        "4:5 image Asset resource name or reference"
                    ),
                    "call_to_action_text": _field(
                        "string", "Card call to action", enum=[
                            "AUTOMATED", "BOOK_NOW", "CONTACT_US", "DOWNLOAD",
                            "GET_OFFER", "GET_QUOTE", "LEARN_MORE", "SHOP_NOW",
                            "SIGN_UP", "SUBSCRIBE", "WATCH_MORE",
                        ],
                    ),
                }, "Demand Gen carousel card", additional_properties=False,
                   required=["headline"]),
            ),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_demand_gen_video_responsive_ad_schema() -> dict[str, Any]:
    """Demand Gen video responsive ad contract."""
    return {
        "required": ["ad_group_id", "name", "business_name", "videos", "headlines", "descriptions"],
        "provider_required": ["business_name", "videos", "headlines", "descriptions"],
        "properties": {
            "ad_group_id": _field("string", "Parent Demand Gen ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
            "final_url": _field("string", "Final URL", minLength=1),
            "business_name": _field("string", "Advertiser business name", minLength=1, maxLength=25),
            "videos": _google_ad_asset_refs("YouTube video assets"),
            "headlines": _google_ad_text_assets("Demand Gen headlines", min_items=3, max_items=5),
            "long_headlines": _google_ad_text_assets("Demand Gen long headlines", min_items=1, max_items=5),
            "descriptions": _google_ad_text_assets("Demand Gen descriptions", min_items=2, max_items=5),
            "logo_images": _google_ad_asset_refs("Logo image assets"),
            "companion_banners": _google_ad_asset_refs("Companion banner assets"),
            "call_to_actions": _google_ad_asset_refs("Call-to-action assets"),
            "breadcrumb1": _field("string", "Display breadcrumb 1"),
            "breadcrumb2": _field("string", "Display breadcrumb 2"),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_demand_gen_product_ad_schema() -> dict[str, Any]:
    """Demand Gen product ad contract backed by Merchant Center products."""
    return {
        "required": ["ad_group_id", "name"],
        "provider_required": ["headline", "description", "business_name", "logo_image", "call_to_action"],
        "properties": {
            "ad_group_id": _field("string", "Parent Demand Gen ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
            "final_url": _field("string", "Optional final URL override", minLength=1),
            "headline": _field(
                ["string", "object"], "Product ad headline asset",
                additionalProperties=True,
            ),
            "description": _field(
                ["string", "object"], "Product ad description asset",
                additionalProperties=True,
            ),
            "business_name": _field(
                ["string", "object"], "Business name text asset",
                additionalProperties=True,
            ),
            "logo_image": _google_asset_ref_item("Logo image asset"),
            "call_to_action": _google_asset_ref_item("Call-to-action asset"),
            "breadcrumb1": _field("string", "Display breadcrumb 1"),
            "breadcrumb2": _field("string", "Display breadcrumb 2"),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_hotel_ad_schema() -> dict[str, Any]:
    """Hotel ads are feed-backed; the v24 ``HotelAdInfo`` payload is empty."""
    return {
        "required": ["ad_group_id", "name"],
        "provider_required": [],
        "properties": {
            "ad_group_id": _field("string", "Parent Hotel ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_local_ad_schema() -> dict[str, Any]:
    """Local campaign ad contract backed by ``Ad.localAd``."""
    return {
        "required": ["ad_group_id", "name", "final_url", "headlines", "descriptions"],
        "provider_required": ["headlines", "descriptions"],
        "properties": {
            "ad_group_id": _field("string", "Parent Local ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
            "final_url": _field("string", "Final URL", minLength=1),
            "headlines": _google_ad_text_assets("Local ad headlines", min_items=3, max_items=15),
            "descriptions": _google_ad_text_assets("Local ad descriptions", min_items=2, max_items=5),
            "path1": _field("string", "Display path 1", maxLength=15),
            "path2": _field("string", "Display path 2", maxLength=15),
            "logo_images": _google_ad_asset_refs("Logo image assets"),
            "videos": _google_ad_asset_refs("Video assets"),
            "marketing_images": _google_ad_asset_refs("Marketing image assets"),
            "call_to_actions": _google_ad_asset_refs("Call-to-action assets"),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_smart_campaign_ad_schema() -> dict[str, Any]:
    """Smart campaign ad contract backed by ``Ad.smartCampaignAd``."""
    return {
        "required": ["ad_group_id", "name", "final_url", "headlines", "descriptions"],
        "provider_required": ["headlines", "descriptions"],
        "properties": {
            "ad_group_id": _field("string", "Parent Smart campaign ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
            "final_url": _field("string", "Final URL", minLength=1),
            "headlines": _google_ad_text_assets("Smart campaign headlines", min_items=3, max_items=3),
            "descriptions": _google_ad_text_assets("Smart campaign descriptions", min_items=2, max_items=2),
            "status": _field("string", "Ad status", enum=GOOGLE_STATUSES),
        },
    }


def google_travel_ad_schema() -> dict[str, Any]:
    """Travel ads are feed-backed; the v24 ``TravelAdInfo`` payload is empty."""
    return {
        "required": ["ad_group_id", "name"],
        "provider_required": [],
        "properties": {
            "ad_group_id": _field("string", "Parent Travel ad group ID", minLength=1),
            "name": _field("string", "Ad name", minLength=1, maxLength=255),
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
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_specialized_ad_group"],
            "dependencies": ["demand_gen_ad", "audiences", "assets"],
            "supported_fields": ["demand_gen_campaign_settings", "demand_gen_ad_group_settings"],
            "gaps": ["live mutation approval", "Demand Gen audience/asset reference validation"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "hotel",
            "category": "hotel",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_specialized_ad_group", "google_create_hotel_ad"],
            "dependencies": ["hotel_ad_group", "hotel_feed"],
            "supported_fields": ["hotel_setting", "hotel_ad"],
            "gaps": ["Hotel Center feed/property validation", "live mutation approval"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "local",
            "category": "local",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_specialized_ad_group", "google_create_local_ad"],
            "dependencies": ["business_profile", "local_ad"],
            "supported_fields": ["local_campaign_setting", "headlines", "descriptions", "assets"],
            "gaps": ["Business Profile/location validation", "live mutation approval"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "smart",
            "category": "smart",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_specialized_ad_group", "google_create_smart_campaign_ad"],
            "dependencies": ["smart_campaign_ad"],
            "supported_fields": ["headlines", "descriptions", "final_url"],
            "gaps": ["SmartCampaignSetting lifecycle validation", "live mutation approval"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "travel",
            "category": "travel",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["google_create_campaign", "google_create_specialized_ad_group", "google_create_travel_ad"],
            "dependencies": ["travel_ad", "travel_feed"],
            "supported_fields": ["travel_campaign_settings", "travel_ad"],
            "gaps": ["Travel feed/account validation", "live mutation approval"],
            "source_document": "Google Ads API v24 AdvertisingChannelType",
        },
        {
            "format_id": "demand_gen.multi_asset_ad",
            "category": "demand_gen",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_demand_gen_multi_asset_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_demand_gen_multi_asset_ad",
            "dependencies": ["ad_group", "assets", "final_url"],
            "supported_fields": ["headlines", "descriptions", "business_name", "marketing_images", "logo_images"],
            "gaps": ["live mutation approval"],
            "source_document": "Google Ads API v24 Ad.demandGenMultiAssetAd",
        },
        {
            "format_id": "demand_gen.carousel_ad",
            "category": "demand_gen",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_demand_gen_carousel_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_demand_gen_carousel_ad",
            "dependencies": ["ad_group", "carousel_cards"],
            "supported_fields": ["headline", "description", "carousel_cards", "logo_image"],
            "gaps": ["live mutation approval"],
            "source_document": "Google Ads API v24 Ad.demandGenCarouselAd",
        },
        {
            "format_id": "demand_gen.video_responsive_ad",
            "category": "demand_gen",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_demand_gen_video_responsive_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_demand_gen_video_responsive_ad",
            "dependencies": ["ad_group", "videos", "assets"],
            "supported_fields": ["business_name", "videos", "headlines", "long_headlines", "descriptions"],
            "gaps": ["live mutation approval"],
            "source_document": "Google Ads API v24 Ad.demandGenVideoResponsiveAd",
        },
        {
            "format_id": "demand_gen.product_ad",
            "category": "demand_gen",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_demand_gen_product_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_demand_gen_product_ad",
            "dependencies": ["ad_group", "merchant_center", "product_feed"],
            "supported_fields": ["headline", "description", "business_name", "logo_image", "call_to_action"],
            "gaps": ["Merchant Center product validation", "live mutation approval"],
            "source_document": "Google Ads API v24 Ad.demandGenProductAd",
        },
        {
            "format_id": "hotel.ad",
            "category": "hotel",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_hotel_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_hotel_ad",
            "dependencies": ["hotel_ad_group", "hotel_feed"],
            "supported_fields": ["name", "status"],
            "gaps": ["Hotel Center feed/property validation", "live mutation approval"],
            "source_document": "Google Ads API v24 Ad.hotelAd",
        },
        {
            "format_id": "local.ad",
            "category": "local",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_local_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_local_ad",
            "dependencies": ["local_ad_group", "business_profile", "assets"],
            "supported_fields": ["headlines", "descriptions", "marketing_images", "logo_images", "videos"],
            "gaps": ["Business Profile/location validation", "live mutation approval"],
            "source_document": "Google Ads API v24 Ad.localAd",
        },
        {
            "format_id": "smart.ad",
            "category": "smart",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_smart_campaign_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_smart_campaign_ad",
            "dependencies": ["smart_ad_group", "headlines", "descriptions", "final_url"],
            "supported_fields": ["headlines", "descriptions", "final_url"],
            "gaps": ["SmartCampaignSetting lifecycle validation", "live mutation approval"],
            "source_document": "Google Ads API v24 Ad.smartCampaignAd",
        },
        {
            "format_id": "travel.ad",
            "category": "travel",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["google_create_travel_ad"],
            "payload_adapter": "GoogleAdsAPIClient.create_travel_ad",
            "dependencies": ["travel_ad_group", "travel_feed"],
            "supported_fields": ["name", "status"],
            "gaps": ["Travel feed/account validation", "live mutation approval"],
            "source_document": "Google Ads API v24 Ad.travelAd",
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


def google_campaign_asset_schema() -> dict[str, Any]:
    """Schema for Campaign-to-Asset association reads and mutations."""
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "campaign_id": _field("string", "Parent Campaign ID", minLength=1),
            "asset_id": _field(
                "string", "Reusable Google Asset ID", minLength=1,
                lookup_tool="google_list_assets", lookup_result_key="assets",
                selection_value_fields=["resource_name", "asset_id", "id"],
                selection_label_fields=["name", "text", "resource_name", "id"],
            ),
            "field_type": _field(
                "string", "Campaign asset field type",
                enum=GOOGLE_CAMPAIGN_ASSET_FIELD_TYPES,
            ),
            "limit": _field(
                "integer", "Maximum number of CampaignAsset rows",
                minimum=1, maximum=10000,
            ),
        },
    }


def google_asset_group_asset_schema() -> dict[str, Any]:
    """Schema for PMax AssetGroup-to-Asset association reads and mutations."""
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "asset_group_id": _field(
                "string", "Parent Performance Max Asset Group ID", minLength=1
            ),
            "asset_id": _field(
                "string", "Reusable Google Asset ID", minLength=1,
                lookup_tool="google_list_assets", lookup_result_key="assets",
                selection_value_fields=["resource_name", "asset_id", "id"],
                selection_label_fields=["name", "text", "resource_name", "id"],
            ),
            "field_type": _field(
                "string", "Asset group asset field type",
                enum=GOOGLE_ASSET_GROUP_ASSET_FIELD_TYPES,
            ),
            "limit": _field(
                "integer", "Maximum number of AssetGroupAsset rows",
                minimum=1, maximum=10000,
            ),
        },
    }


def google_asset_group_schema() -> dict[str, Any]:
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
            "headlines": _google_text_assets("Text headline assets or existing Asset references", min_items=3, max_items=15),
            "long_headlines": _google_text_assets("Long headline assets or existing Asset references", min_items=1, max_items=5),
            "descriptions": _google_text_assets("Description assets", min_items=2, max_items=5),
            "images": _google_asset_refs("Performance Max image assets"),
            "videos": _google_asset_refs("Performance Max video assets"),
            "logos": _google_asset_refs("Performance Max logo assets"),
            "status": _field("string", "Asset group status", enum=GOOGLE_STATUSES),
        },
    }


def google_feed_schema() -> dict[str, Any]:
    """Schema for Google Ads Feed and FeedItem management."""
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "feed_id": _field("string", "Google Feed ID", minLength=1),
            "name": _field("string", "Feed name", minLength=1, maxLength=255),
            "origin": _field(
                "string", "Feed origin",
                enum=["UNKNOWN", "USER", "GOOGLE"],
            ),
            "attributes": _field(
                "array", "Feed attribute definitions",
                items={"type": "object", "additionalProperties": True},
            ),
            "feed_item_resource_name": _field(
                "string", "FeedItem resource name",
                minLength=1,
            ),
            "attribute_values": _field(
                "array", "FeedItem attribute values",
                items={"type": "object", "additionalProperties": True},
            ),
            "limit": _field(
                "integer", "Maximum number of rows",
                minimum=1, maximum=10000,
            ),
        },
    }


def google_conversion_goal_schema() -> dict[str, Any]:
    """Schema for Customer/Campaign ConversionGoal read and update Tools."""
    goal_updates = _object({
        "biddable": _field("boolean", "Whether this goal is biddable"),
        "value_settings": _field(
            "object", "Conversion value settings",
            additionalProperties=True,
        ),
    }, "Allowed Google conversion goal update fields")
    return {
        "properties": {
            "customer_id": _field("string", "Google Ads customer ID"),
            "campaign_id": _field("string", "Campaign ID", minLength=1),
            "category": _field("string", "Conversion goal category", minLength=1),
            "origin": _field("string", "Conversion goal origin", minLength=1),
            "updates": goal_updates,
            "limit": _field(
                "integer", "Maximum number of goals",
                minimum=1, maximum=10000,
            ),
        },
    }
