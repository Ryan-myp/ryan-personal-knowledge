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
META_CTA_TYPES = [
    "LEARN_MORE", "SHOP_NOW", "SIGN_UP", "CONTACT_US", "LIKE_PAGE",
    "WATCH_VIDEO", "SEND_MESSAGE", "WHATSAPP", "GET_QUOTE", "BOOK_TRAVEL",
    "INSTALL_MOBILE_APP", "DOWNLOAD", "PLAY_GAME", "USE_APP",
]
META_AD_FORMATS = ["LINK", "VIDEO", "CAROUSEL", "LEAD", "CATALOG"]
META_MESSAGING_APPS = ["MESSENGER", "WHATSAPP", "INSTAGRAM_DIRECT"]
META_SPECIAL_AD_CATEGORIES = ["NONE", "EMPLOYMENT", "HOUSING", "CREDIT"]
META_STATUS = ["ACTIVE", "PAUSED"]
META_DEVICE_PLATFORMS = ["mobile", "desktop"]
META_PUBLISHER_PLATFORMS = ["facebook", "instagram", "audience_network", "messenger"]
META_FACEBOOK_POSITIONS = [
    "feed", "right_hand_column", "marketplace", "video_feeds", "story",
    "search", "instream_video", "facebook_reels", "facebook_reels_overlay",
    "profile_feed",
]
META_INSTAGRAM_POSITIONS = [
    "stream", "story", "explore", "explore_home", "profile_feed", "reels",
    "ig_search", "reels_overlay",
]
META_CUSTOM_EVENT_TYPES = [
    "PURCHASE", "LEAD", "COMPLETE_REGISTRATION", "ADD_TO_CART",
    "INITIATE_CHECKOUT", "VIEW_CONTENT", "SEARCH", "SUBSCRIBE",
]
META_AUDIENCE_SUBTYPES = ["CUSTOM", "LOOKALIKE"]
META_CUSTOMER_FILE_SOURCES = [
    "USER_PROVIDED_ONLY", "PARTNER_PROVIDED_ONLY", "BOTH_USER_AND_PARTNER_PROVIDED",
]
META_AUDIENCE_UPLOAD_SCHEMAS = [
    "EMAIL", "PHONE", "FN", "LN", "ZIP", "CT", "ST", "COUNTRY", "DOB",
    "DOBY", "DOBM", "DOBD", "GEN", "MADID", "EXTERN_ID",
]
META_LOOKALIKE_TYPES = ["similarity", "reach"]
META_CAPI_EVENT_NAMES = [
    "AddPaymentInfo", "AddToCart", "AddToWishlist", "CompleteRegistration",
    "Contact", "CustomizeProduct", "Donate", "FindLocation", "InitiateCheckout",
    "Lead", "Purchase", "Schedule", "Search", "StartTrial", "SubmitApplication",
    "Subscribe", "ViewContent",
]
META_CAPI_ACTION_SOURCES = [
    "website", "app", "physical_store", "phone_call", "chat", "email", "other",
]
META_CUSTOM_CONVERSION_EVENT_TYPES = [
    "ADD_PAYMENT_INFO", "ADD_TO_CART", "ADD_TO_WISHLIST", "COMPLETE_REGISTRATION",
    "CONTENT_VIEW", "INITIATED_CHECKOUT", "LEAD", "PURCHASE", "SEARCH", "CONTACT",
    "CUSTOMIZE_PRODUCT", "DONATE", "FIND_LOCATION", "SCHEDULE", "START_TRIAL",
    "SUBMIT_APPLICATION", "SUBSCRIBE", "LISTING_INTERACTION", "FACEBOOK_SELECTED", "OTHER",
]
META_CUSTOM_CONVERSION_ACTION_SOURCES = [
    "app", "chat", "email", "other", "phone_call", "physical_store",
    "system_generated", "website", "business_messaging",
]
META_CATALOG_VERTICALS = [
    "commerce", "destination_items", "flights", "home_listings", "hotels", "vehicles",
]
META_LEAD_FORM_QUESTION_TYPES = [
    "EMAIL", "FULL_NAME", "FIRST_NAME", "LAST_NAME", "PHONE", "CITY", "STATE",
    "ZIP", "COUNTRY", "JOB_TITLE", "COMPANY_NAME", "WORK_EMAIL", "WORK_PHONE",
    "DATE_OF_BIRTH", "GENDER", "MARITAL_STATUS", "RELATIONSHIP_STATUS",
    "MILITARY_STATUS", "STREET_ADDRESS", "POSTAL_CODE", "CUSTOM",
]
META_TARGETING_SEARCH_TYPES = [
    "adinterest", "adgeolocation", "adlocale", "adzipcode",
    "adworkposition", "adworkemployer", "adtargetingcategory",
]

# Meta's ``targeting.geo_locations.countries`` accepts ISO 3166-1 alpha-2
# codes.  This is a static provider enum, not a targeting-search result:
# ``targetingsearch?type=adgeolocation`` returns Meta location objects whose
# IDs are valid for regions/cities, but are not valid country values.
META_COUNTRY_CODES = [
    'AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS', 'AT', 'AU', 'AW', 'AX', 'AZ',
    'BA', 'BB', 'BD', 'BE', 'BF', 'BG', 'BH', 'BI', 'BJ', 'BL', 'BM', 'BN', 'BO', 'BQ', 'BR', 'BS',
    'BT', 'BV', 'BW', 'BY', 'BZ', 'CA', 'CC', 'CD', 'CF', 'CG', 'CH', 'CI', 'CK', 'CL', 'CM', 'CN',
    'CO', 'CR', 'CU', 'CV', 'CW', 'CX', 'CY', 'CZ', 'DE', 'DJ', 'DK', 'DM', 'DO', 'DZ', 'EC', 'EE',
    'EG', 'EH', 'ER', 'ES', 'ET', 'FI', 'FJ', 'FK', 'FM', 'FO', 'FR', 'GA', 'GB', 'GD', 'GE', 'GF',
    'GG', 'GH', 'GI', 'GL', 'GM', 'GN', 'GP', 'GQ', 'GR', 'GS', 'GT', 'GU', 'GW', 'GY', 'HK', 'HM',
    'HN', 'HR', 'HT', 'HU', 'ID', 'IE', 'IL', 'IM', 'IN', 'IO', 'IQ', 'IR', 'IS', 'IT', 'JE', 'JM',
    'JO', 'JP', 'KE', 'KG', 'KH', 'KI', 'KM', 'KN', 'KP', 'KR', 'KW', 'KY', 'KZ', 'LA', 'LB', 'LC',
    'LI', 'LK', 'LR', 'LS', 'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME', 'MF', 'MG', 'MH', 'MK',
    'ML', 'MM', 'MN', 'MO', 'MP', 'MQ', 'MR', 'MS', 'MT', 'MU', 'MV', 'MW', 'MX', 'MY', 'MZ', 'NA',
    'NC', 'NE', 'NF', 'NG', 'NI', 'NL', 'NO', 'NP', 'NR', 'NU', 'NZ', 'OM', 'PA', 'PE', 'PF', 'PG',
    'PH', 'PK', 'PL', 'PM', 'PN', 'PR', 'PS', 'PT', 'PW', 'PY', 'QA', 'RE', 'RO', 'RS', 'RU', 'RW',
    'SA', 'SB', 'SC', 'SD', 'SE', 'SG', 'SH', 'SI', 'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS',
    'ST', 'SV', 'SX', 'SY', 'SZ', 'TC', 'TD', 'TF', 'TG', 'TH', 'TJ', 'TK', 'TL', 'TM', 'TN', 'TO',
    'TR', 'TT', 'TV', 'TW', 'TZ', 'UA', 'UG', 'UM', 'US', 'UY', 'UZ', 'VA', 'VC', 'VE', 'VG', 'VI',
    'VN', 'VU', 'WF', 'WS', 'YE', 'YT', 'ZA', 'ZM', 'ZW',
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


def _meta_targeting_option_list(description: str, targeting_type: str) -> dict[str, Any]:
    """A searchable Meta targeting dimension for ``flexible_spec``."""
    return _field(
        "array", description,
        items=_object({
            "id": _field("string", "Meta targeting option ID"),
            "key": _field("string", "Meta targeting option key"),
            "name": _field("string", "Targeting option name"),
        }, "Meta targeting option", additional_properties=True),
        lookup_tool="meta_search_targeting_options",
        lookup_result_key="targeting_options",
        lookup_query_field="query",
        lookup_defaults={"type": targeting_type},
        selection_value_fields=["key", "id", "value"],
        selection_label_fields=["name", "label", "key", "id"],
        presentation="lookup",
    )


def _meta_asset_ref(
    description: str, lookup_tool: str, result_key: str,
    value_fields: list[str], label_fields: list[str],
) -> dict[str, Any]:
    """Provider resource reference used by nested Meta creative objects."""
    return _field(
        "string", description, minLength=1,
        lookup_tool=lookup_tool, lookup_result_key=result_key,
        selection_value_fields=value_fields,
        selection_label_fields=label_fields,
    )


def _meta_lead_gen_config_schema() -> dict[str, Any]:
    """Known account/page/form references for lead ad-set configuration."""
    return _object({
        "page_id": _meta_asset_ref(
            "Facebook Page used by the lead flow", "meta_list_pages", "pages",
            ["id", "page_id"], ["name", "id"],
        ),
        "form_id": _meta_asset_ref(
            "Published Instant Form", "meta_list_lead_forms", "lead_forms",
            ["id", "form_id"], ["name", "id"],
        ),
    }, "Meta lead generation configuration", additional_properties=True)


def meta_targeting_schema() -> dict[str, Any]:
    """Known Meta targeting dimensions; IDs remain provider/account scoped."""
    audience_ref = _object({
        "id": _field("string", "Meta audience ID"),
        "name": _field("string", "Optional display name"),
    }, "Custom audience reference")
    return _object({
        "geo_locations": _object({
            "countries": _field(
                "array", "ISO country codes; search by country name or code",
                items={"type": "string", "enum": META_COUNTRY_CODES},
                option_labels={
                    "US": "美国", "CA": "加拿大", "GB": "英国", "AU": "澳大利亚",
                    "SG": "新加坡", "JP": "日本", "KR": "韩国", "IN": "印度",
                    "ID": "印度尼西亚", "MY": "马来西亚", "TH": "泰国", "VN": "越南",
                    "PH": "菲律宾", "CN": "中国", "TW": "中国台湾地区", "HK": "中国香港地区",
                },
            ),
            "regions": _field(
                "array", "Region IDs; search by region name",
                items=_object({"key": _field("string")}, "Region reference"),
                lookup_tool="meta_search_targeting_options",
                lookup_result_key="targeting_options",
                lookup_query_field="query",
                lookup_defaults={"type": "adgeolocation"},
                selection_value_fields=["key", "id", "value"],
                selection_label_fields=["name", "label", "key", "id"],
            ),
            "cities": _field(
                "array", "City references; search by city name",
                items=_object({"key": _field("string")}, "City reference"),
                lookup_tool="meta_search_targeting_options",
                lookup_result_key="targeting_options",
                lookup_query_field="query",
                lookup_defaults={"type": "adgeolocation"},
                selection_value_fields=["key", "id", "value"],
                selection_label_fields=["name", "label", "key", "id"],
            ),
            "location_types": _field("array", "Location semantics", items={"type": "string", "enum": ["home", "recent"]}),
        }, "Geographic targeting"),
        # Meta Graph v19 requires the caller to make an explicit choice for
        # Advantage Audience on this account. Keep it inside the targeting
        # spec, where Meta expects it, instead of silently choosing a mode.
        "targeting_automation": _object({
            "advantage_audience": _field(
                "integer", "Advantage Audience: 1 enabled, 0 disabled",
                enum=[0, 1],
            ),
        }, "Meta Advantage Audience setting", required=["advantage_audience"]),
        "age_min": _field("integer", "Minimum age", minimum=13, maximum=65),
        "age_max": _field("integer", "Maximum age", minimum=13, maximum=65),
        "genders": _field("array", "1 male, 2 female", items={"type": "integer", "enum": [1, 2]}),
        "locales": _field(
            "array", "Meta locale IDs; search by language name",
            items={"type": "integer", "minimum": 0},
            lookup_tool="meta_search_targeting_options",
            lookup_result_key="targeting_options",
            lookup_query_field="query",
            lookup_defaults={"type": "adlocale"},
            selection_value_fields=["key", "id", "value"],
            selection_label_fields=["name", "label", "locale", "id"],
        ),
        "device_platforms": _field(
            "array", "Device platforms",
            items={"type": "string", "enum": META_DEVICE_PLATFORMS},
        ),
        "user_os": _field(
            "array", "Mobile operating systems; required when promoting an app",
            items={"type": "string", "enum": ["Android", "iOS"]},
        ),
        "publisher_platforms": _field(
            "array", "Publisher platforms",
            items={"type": "string", "enum": META_PUBLISHER_PLATFORMS},
        ),
        "facebook_positions": _field(
            "array", "Facebook placements",
            items={"type": "string", "enum": META_FACEBOOK_POSITIONS},
        ),
        "instagram_positions": _field(
            "array", "Instagram placements",
            items={"type": "string", "enum": META_INSTAGRAM_POSITIONS},
        ),
        "custom_audiences": _field(
            "array", "Included custom audiences", items=audience_ref,
            lookup_tool="meta_list_audiences", lookup_result_key="audiences",
            selection_value_fields=["id", "audience_id"],
            selection_label_fields=["name", "audience_name", "id"],
        ),
        "excluded_custom_audiences": _field(
            "array", "Excluded custom audiences", items=audience_ref,
            lookup_tool="meta_list_audiences", lookup_result_key="audiences",
            selection_value_fields=["id", "audience_id"],
            selection_label_fields=["name", "audience_name", "id"],
        ),
        "flexible_spec": _field(
            "array", "Interest/behavior groups; choose values from Meta targeting search",
            items=_object({
                "interests": _meta_targeting_option_list("兴趣", "adinterest"),
                "behaviors": _meta_targeting_option_list("行为", "adtargetingcategory"),
                "life_events": _meta_targeting_option_list("人生大事", "adtargetingcategory"),
                "industries": _meta_targeting_option_list("行业", "adtargetingcategory"),
                "work_employers": _meta_targeting_option_list("雇主", "adworkemployer"),
                "work_positions": _meta_targeting_option_list("职位", "adworkposition"),
                "education_schools": _meta_targeting_option_list("学校", "adtargetingcategory"),
                "education_majors": _meta_targeting_option_list("专业", "adtargetingcategory"),
            }, "Meta flexible targeting group", additional_properties=True),
            minItems=1,
            presentation="object_editor",
        ),
    }, "Meta ad set targeting")


def meta_targeting_search_schema() -> dict[str, Any]:
    """Schema for Meta's account-scoped Targeting Search endpoint."""
    return {
        "required": ["account_id", "query"],
        "capability_required": ["account_id", "query"],
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "query": _field("string", "Search text or location name", minLength=1, maxLength=200),
            "type": _field(
                "string", "Meta targeting search category",
                enum=META_TARGETING_SEARCH_TYPES, default="adinterest",
            ),
            "limit": _field("integer", "Maximum options to return", minimum=1, maximum=100),
        },
    }


def meta_audience_schema() -> dict[str, Any]:
    """Contract for Meta Custom and Lookalike Audience management."""
    return {
        "required": ["account_id", "name", "subtype"],
        "capability_required": ["name", "subtype"],
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "audience_id": _field("string", "Meta Custom Audience ID", minLength=1),
            "name": _field("string", "Audience name", minLength=1, maxLength=400),
            "subtype": _field("string", "Audience subtype", enum=META_AUDIENCE_SUBTYPES),
            "description": _field("string", "Audience description", maxLength=1000),
            "customer_file_source": _field(
                "string", "Source of customer-file data", enum=META_CUSTOMER_FILE_SOURCES,
            ),
            "retention_days": _field("integer", "Website/event retention window", minimum=1, maximum=180),
            "rule": _field(
                "object", "Meta website/event audience rule",
                additionalProperties=True, presentation="advanced_json",
                manual_entry={
                    "title": "受众规则高级配置",
                    "instructions": "规则结构取决于 Pixel、事件源和 Meta API 版本；请使用已审核的事件规则对象，系统不会替你推断事件字段。",
                    "source": "meta_audience_rule_expression",
                },
            ),
            "prefill": _field("boolean", "Prefill audience with prior events"),
            "pixel_id": _field(
                "string", "Meta Pixel source ID",
                lookup_tool="meta_list_pixels", lookup_result_key="pixels",
                selection_value_fields=["id", "pixel_id"],
                selection_label_fields=["name", "id"],
            ),
            "event_source_group": _field(
                "string", "Meta event source group ID; provide the ID from Events Manager",
                minLength=1,
                manual_entry={
                    "title": "事件源组 ID",
                    "instructions": "Meta 当前没有稳定的通用事件源组列表接口；请从 Events Manager 复制该事件源组 ID。",
                    "source": "provider_event_source",
                },
            ),
            "origin_audience_id": _field(
                "string", "Source Custom Audience ID for Lookalike",
                lookup_tool="meta_list_audiences", lookup_result_key="audiences",
                selection_value_fields=["id", "audience_id"],
                selection_label_fields=["name", "audience_name", "id"],
            ),
            "country": _field(
                "string", "Two-letter ISO lookalike country code",
                minLength=2, maxLength=2,
                manual_entry={
                    "title": "相似受众国家/地区",
                    "instructions": "请输入两位 ISO 国家代码，例如 US、GB；Meta 没有为该字段提供可复用的账号列表接口。",
                    "example": "US",
                },
            ),
            "ratio": _field("number", "Lookalike ratio", minimum=0.01, maximum=0.20),
            "lookalike_type": _field("string", "Lookalike expansion type", enum=META_LOOKALIKE_TYPES),
            "limit": _field("integer", "Maximum number of audiences", minimum=1, maximum=1000),
            "updates": _object({
                "name": _field("string", "Audience name", minLength=1, maxLength=400),
                "description": _field("string", "Audience description", maxLength=1000),
                "retention_days": _field("integer", "Website/event retention window", minimum=1, maximum=180),
                "rule": _field("object", "Meta website/event audience rule", additionalProperties=True),
            }, "Allowed Custom Audience update fields"),
            "upload_schema": _field(
                "array", "Meta customer-data upload schema", minItems=1, maxItems=15,
                items={"type": "string", "enum": META_AUDIENCE_UPLOAD_SCHEMAS},
            ),
            "upload_data": _field(
                "array", "Rows of normalized SHA-256 customer identifiers",
                minItems=1, maxItems=10000,
                items={
                    "type": "array", "minItems": 1, "maxItems": 15,
                    "items": {"type": "string", "minLength": 64, "maxLength": 64},
                },
            ),
        },
        "conditional_rules": [
            {
                "id": "lookalike_source",
                "if": {"subtype": "LOOKALIKE"},
                "required": ["origin_audience_id", "country"],
                "message": "LOOKALIKE requires origin_audience_id and country",
            },
        ],
        "upload_required": ["account_id", "audience_id", "upload_schema", "upload_data"],
    }


def meta_lookalike_audience_schema() -> dict[str, Any]:
    """Dedicated contract for Meta Lookalike Audience creation.

    Meta exposes Lookalike creation through the Custom Audience edge, but the
    provider payload has a different required relationship than a generic
    Custom Audience.  Keep that relationship visible to callers instead of
    asking an LLM/UI to infer it from a free-form ``subtype`` field.
    """
    return {
        "required": ["account_id", "name", "origin_audience_id", "country"],
        "capability_required": [
            "name", "origin_audience_id", "country",
        ],
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "name": _field("string", "Lookalike Audience name", minLength=1, maxLength=400),
            "description": _field("string", "Audience description", maxLength=1000),
            "origin_audience_id": _field(
                "string", "Source Custom Audience ID for Lookalike",
                minLength=1,
                lookup_tool="meta_list_audiences",
                lookup_result_key="audiences",
                selection_value_fields=["id", "audience_id"],
                selection_label_fields=["name", "id"],
            ),
            "country": _field(
                "string", "Two-letter ISO lookalike country code",
                minLength=2, maxLength=2,
            ),
            "ratio": _field(
                "number", "Lookalike ratio", minimum=0.01, maximum=0.20,
                default=0.01,
            ),
            "lookalike_type": _field(
                "string", "Lookalike expansion type",
                enum=META_LOOKALIKE_TYPES, default="similarity",
            ),
        },
    }


def meta_catalog_schema() -> dict[str, Any]:
    """Contracts for Meta Catalog and Product Set management."""
    catalog_ref = {
        "account_id": _field("string", "Meta ad account ID"),
        "catalog_id": _field("string", "Meta Product Catalog ID", minLength=1),
        "business_id": _field(
            "string", "Meta Business ID used only for Catalog creation", minLength=1,
            manual_entry={
                "title": "Business ID",
                "instructions": "请输入有权创建 Catalog 的 Meta Business ID，或先通过 Business 查询结果选择。",
            },
        ),
        "name": _field("string", "Catalog name", minLength=1, maxLength=200),
        "vertical": _field("string", "Catalog vertical", enum=META_CATALOG_VERTICALS),
        "is_checkout": _field("boolean", "Whether checkout is enabled"),
        "fields": _field("array", "Fields to return", items={"type": "string"}),
        "limit": _field("integer", "Maximum number of records", minimum=1, maximum=1000),
        "updates": _object({
            "name": _field("string", "Catalog name", minLength=1, maxLength=200),
        }, "Supported Catalog update fields"),
    }
    return {
        "properties": catalog_ref,
        "create_required": ["business_id", "name", "vertical"],
        "update_required": ["account_id", "catalog_id", "updates"],
    }


def meta_product_set_schema() -> dict[str, Any]:
    """Contracts for Meta Product Set management under an account-owned Catalog."""
    return {
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "catalog_id": _field(
                "string", "Parent Meta Product Catalog ID",
                lookup_tool="meta_list_catalogs", lookup_result_key="catalogs",
                selection_value_fields=["id", "catalog_id"],
                selection_label_fields=["name", "id"],
            ),
            "product_set_id": _field("string", "Meta Product Set ID", minLength=1),
            "name": _field("string", "Product Set name", minLength=1, maxLength=200),
            "filter": _field(
                "object", "Meta product set filter expression",
                additionalProperties=True, presentation="advanced_json",
                manual_entry={
                    "title": "Product Set 过滤表达式",
                    "instructions": "过滤字段和操作符由 Catalog 商品类型及 Meta API 版本决定；优先从 Meta 返回结果或已审核模板复制，系统不会猜测表达式。",
                    "source": "meta_product_set_filter_expression",
                },
            ),
            "fields": _field("array", "Fields to return", items={"type": "string"}),
            "limit": _field("integer", "Maximum number of records", minimum=1, maximum=1000),
            "updates": _object({
                "name": _field("string", "Product Set name", minLength=1, maxLength=200),
                "filter": _field(
                    "object", "Meta product set filter expression",
                    additionalProperties=True, presentation="advanced_json",
                    manual_entry={
                        "title": "Product Set 过滤表达式",
                        "instructions": "请使用与当前 Catalog 商品类型匹配的已审核过滤表达式。",
                        "source": "meta_product_set_filter_expression",
                    },
                ),
            }, "Supported Product Set update fields"),
        },
        "create_required": ["account_id", "catalog_id", "name"],
        "get_required": ["account_id", "catalog_id", "product_set_id"],
        "update_required": ["account_id", "catalog_id", "product_set_id", "updates"],
    }


def meta_conversion_event_schema() -> dict[str, Any]:
    """Contract for server-side Meta Conversions API events."""
    event = _object({
        "event_name": _field(
            "string", "Meta standard or custom event name", minLength=1, maxLength=100,
            known_values=META_CAPI_EVENT_NAMES, allow_custom=True,
        ),
        "event_time": _field("integer", "Unix event timestamp in seconds", minimum=1),
        "action_source": _field(
            "string", "Origin of the conversion event", enum=META_CAPI_ACTION_SOURCES
        ),
        "event_source_url": _field("string", "URL where the event occurred"),
        "event_id": _field("string", "Stable deduplication ID"),
        "user_data": _object(
            {}, "Normalized/hashed user matching data", additional_properties=True
        ),
        "custom_data": _object(
            {}, "Purchase, content and order metadata", additional_properties=True
        ),
        "app_data": _object(
            {}, "Mobile app event metadata", additional_properties=True
        ),
        "opt_out": _field("boolean", "Whether the user opted out of processing"),
        "data_processing_options": _field(
            "array", "Limited data use options", items={"type": "string"}
        ),
        "data_processing_options_country": _field(
            "integer", "Data processing country code"
        ),
        "data_processing_options_state": _field(
            "integer", "Data processing state code"
        ),
    }, "Meta Conversions API event")
    event["required"] = ["event_name", "event_time", "action_source", "user_data"]
    return {
        "required": ["account_id", "pixel_id", "events"],
        "capability_required": ["pixel_id", "events"],
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "pixel_id": _field(
                "string", "Meta Pixel ID",
                lookup_tool="meta_list_pixels", lookup_result_key="pixels",
                selection_value_fields=["id", "pixel_id"],
                selection_label_fields=["name", "id"],
            ),
            "events": _field(
                "array", "One or more CAPI events", items=event,
                minItems=1, maxItems=1000,
            ),
            "test_event_code": _field(
                "string", "Optional Meta Events Manager test code"
            ),
        },
    }


def meta_custom_conversion_schema() -> dict[str, Any]:
    """Contract for the Meta-documented Pixel Custom Conversion create edge."""
    pixel_id = _field(
        "string", "Meta Pixel ID", minLength=1,
        lookup_tool="meta_list_pixels", lookup_result_key="pixels",
        selection_value_fields=["id", "pixel_id"],
        selection_label_fields=["name", "id"],
    )
    return {
        "required": ["account_id", "pixel_id", "name", "rule"],
        # ``pixel_id`` is translated to the provider's ``event_source_id``
        # inside the Client; provider validation runs before that adapter.
        "capability_required": ["name", "rule"],
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "pixel_id": pixel_id,
            "name": _field("string", "Custom conversion name", minLength=1, maxLength=400),
            "rule": _field(
                "string", "Rule expression used to count matching Pixel events",
                minLength=1, maxLength=5000,
            ),
            "action_source_type": _field(
                "string", "Action source type", enum=META_CUSTOM_CONVERSION_ACTION_SOURCES,
            ),
            "advanced_rule": _field("string", "Advanced multi-source rule", maxLength=5000),
            "custom_event_type": _field(
                "string", "Custom conversion event type", enum=META_CUSTOM_CONVERSION_EVENT_TYPES,
            ),
            "default_conversion_value": _field(
                "number", "Default conversion value", minimum=0,
            ),
            "description": _field("string", "Custom conversion description", maxLength=1000),
        },
    }


def meta_custom_conversion_management_schema() -> dict[str, Any]:
    """Contracts for the verified Meta Custom Conversion node lifecycle.

    Meta only exposes a small mutable field set for this resource.  Keeping
    it separate from the create contract prevents create-only fields such as
    ``pixel_id`` and ``rule`` from accidentally becoming update inputs.
    """
    return {
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "custom_conversion_id": _field(
                "string", "Meta Custom Conversion ID", minLength=1
            ),
            "fields": _field(
                "array", "Optional Graph fields to return",
                items={"type": "string", "minLength": 1},
            ),
            "limit": _field(
                "integer", "Maximum number of Custom Conversions",
                minimum=1, maximum=1000,
            ),
            "updates": _object({
                "name": _field(
                    "string", "Custom conversion name", minLength=1, maxLength=400
                ),
                "default_conversion_value": _field(
                    "number", "Default conversion value", minimum=0
                ),
                "description": _field(
                    "string", "Custom conversion description", maxLength=1000
                ),
            }, "Mutable Custom Conversion fields"),
        },
        "update_required": ["account_id", "custom_conversion_id", "updates"],
    }


def meta_lead_form_schema() -> dict[str, Any]:
    """Contracts for Page-scoped Meta Lead Ads Instant Forms.

    ``questions`` and the presentation blocks are converted to the JSON
    strings required by the Graph API in the Provider Client.  The top-level
    ``account_id`` is an authorization scope for the Runtime; the Page ID is
    the provider resource parent used by the API.
    """
    question = _object({
        "type": _field(
            "string", "Standard or custom Instant Form question type",
            enum=META_LEAD_FORM_QUESTION_TYPES,
        ),
        "key": _field("string", "Stable key for a CUSTOM question", minLength=1, maxLength=100),
        "label": _field("string", "Label for a CUSTOM question", minLength=1, maxLength=200),
        "options": _field(
            "array", "Optional answer choices for a CUSTOM question",
            items={"type": "string"}, minItems=1, maxItems=50,
        ),
    }, "Meta Instant Form question", additional_properties=False)
    privacy_policy = _object({
        "url": _field("string", "Privacy policy URL", minLength=1),
        "link_text": _field("string", "Privacy policy link text", minLength=1),
    }, "Privacy policy displayed in the Instant Form", additional_properties=False)
    presentation = _object({}, "Provider presentation block", additional_properties=True)
    return {
        "required": ["account_id", "page_id", "name", "questions", "privacy_policy"],
        "capability_required": ["name", "questions", "privacy_policy"],
        "properties": {
            "account_id": _field("string", "Meta ad account authorization scope"),
            "page_id": _field(
                "string", "Facebook Page that owns the Instant Form",
                minLength=1, lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "form_id": _field("string", "Meta Instant Form ID", minLength=1),
            "name": _field("string", "Instant Form name", minLength=1, maxLength=400),
            "questions": _field("array", "Instant Form questions", items=question, minItems=1, maxItems=15),
            "privacy_policy": privacy_policy,
            "follow_up_action_url": _field("string", "Optional post-submit follow-up URL"),
            "context_card": presentation,
            "thank_you_page": presentation,
            "locale": _field("string", "Form locale, for example en_US"),
            "is_for_calling": _field("boolean", "Whether the form is intended for calling"),
            "fields": _field("array", "Fields to return", items={"type": "string"}),
            "limit": _field("integer", "Maximum number of forms", minimum=1, maximum=1000),
            "updates": _object({
                "name": _field("string", "Instant Form name", minLength=1, maxLength=400),
            }, "Supported Instant Form update fields", additional_properties=False),
        },
        "create_required": ["account_id", "page_id", "name", "questions", "privacy_policy"],
        "update_required": ["account_id", "page_id", "form_id", "updates"],
    }


def meta_lead_schema() -> dict[str, Any]:
    """Schema for reading leads submitted through a Meta Instant Form."""
    return {
        "required": ["account_id", "page_id", "form_id"],
        "capability_required": ["page_id", "form_id"],
        "properties": {
            "account_id": _field("string", "Meta ad account authorization scope"),
            "page_id": _field(
                "string", "Facebook Page that owns the Instant Form",
                minLength=1, lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "form_id": _field("string", "Meta Instant Form ID", minLength=1),
            "lead_id": _field("string", "Meta Lead ID", minLength=1),
            "fields": _field("array", "Lead fields to return", items={"type": "string"}),
            "limit": _field("integer", "Maximum number of leads", minimum=1, maximum=1000),
        },
    }


def meta_business_schema() -> dict[str, Any]:
    """Schema for Meta Business Manager read operations."""
    return {
        "properties": {
            "business_id": _field("string", "Meta Business ID", minLength=1),
            "fields": _field("array", "Business fields to return", items={"type": "string"}),
            "limit": _field("integer", "Maximum number of businesses", minimum=1, maximum=100),
        },
    }


def meta_creative_schema() -> dict[str, Any]:
    """Contract for Meta Creative reads and the supported mutable fields."""
    return {
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "creative_id": _field(
                "string", "Meta Creative ID", minLength=1,
                lookup_tool="meta_list_creatives", lookup_result_key="creatives",
                selection_value_fields=["id", "creative_id"],
                selection_label_fields=["name", "id"],
            ),
            "name": _field("string", "Creative name", minLength=1, maxLength=400),
            "page_id": _field(
                "string", "Facebook Page ID", minLength=1,
                lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "link": _field("string", "Destination URL"),
            "message": _field("string", "Primary text"),
            "call_to_action_type": _field(
                "string", "Creative CTA", enum=META_CTA_TYPES,
            ),
            "image_hash": _field(
                "string", "Uploaded image hash",
                lookup_tool="meta_list_image_assets", lookup_result_key="images",
                selection_value_fields=["hash", "image_hash", "id"],
                selection_label_fields=["name", "hash", "id"],
            ),
            "image_url": _field("string", "Image URL for create"),
            "fields": _field("array", "Fields to return", items={"type": "string"}),
            "limit": _field("integer", "Maximum number of creatives", minimum=1, maximum=1000),
            "updates": _object({
                "name": _field("string", "Creative name", minLength=1, maxLength=400),
            }, "Supported Creative update fields"),
        },
    }


def meta_image_asset_schema() -> dict[str, Any]:
    """Contract for Meta ad-image upload and listing."""
    return {
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "image_url": _field(
                "string", "HTTPS URL of an image that Meta can fetch",
                minLength=1, maxLength=2048,
            ),
            "name": _field("string", "Optional image asset name", maxLength=400),
            "limit": _field("integer", "Maximum number of image assets", minimum=1, maximum=1000),
        },
        "upload_required": ["account_id", "image_url"],
    }


def meta_video_asset_schema() -> dict[str, Any]:
    """Contract for Meta ad-video upload and listing."""
    return {
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "file_url": _field(
                "string", "HTTPS URL of a video file that Meta can fetch",
                minLength=1, maxLength=2048,
            ),
            "title": _field("string", "Optional video title", maxLength=400),
            "description": _field("string", "Optional video description", maxLength=2000),
            "limit": _field("integer", "Maximum number of video assets", minimum=1, maximum=1000),
        },
        "upload_required": ["account_id", "file_url"],
    }


def meta_promoted_object_schema() -> dict[str, Any]:
    return _object({
        "pixel_id": _field(
            "string", "Meta Pixel ID",
            lookup_tool="meta_list_pixels", lookup_result_key="pixels",
            selection_value_fields=["id", "pixel_id"],
            selection_label_fields=["name", "id"],
        ),
        "application_id": _field(
            "string", "Meta application ID",
            manual_entry={
                "title": "应用 ID",
                "instructions": "当前 Meta Capability 未声明通用应用列表查询 Tool，请提供已在 Meta 账号中关联的应用 ID。",
            },
        ),
        "object_store_url": _field("string", "App store URL"),
        "product_set_id": _field(
            "string", "Catalog product set ID",
            lookup_tool="meta_list_product_sets", lookup_result_key="product_sets",
            selection_value_fields=["id", "product_set_id"],
            selection_label_fields=["name", "id"],
        ),
        "page_id": _field(
            "string", "Facebook Page ID",
            lookup_tool="meta_list_pages", lookup_result_key="pages",
            selection_value_fields=["id", "page_id"],
            selection_label_fields=["name", "id"],
        ),
        "custom_event_type": _field("string", "Conversion event", enum=META_CUSTOM_EVENT_TYPES),
        "custom_event_str": _field(
            "string", "Provider custom event name",
            manual_entry={
                "title": "Meta 自定义事件名",
                "instructions": "标准事件请直接选择上面的选项；自定义事件名由你的 Pixel/应用上报定义，请按事件源中的原始名称填写。",
                "source": "provider_event_source",
            },
        ),
    }, "Meta promoted object")


def meta_campaign_schema() -> dict[str, Any]:
    return {
        "required": ["account_id", "name"],
        "capability_required": ["objective", "special_ad_categories"],
        "capability_any_of": [["daily_budget", "lifetime_budget", "budget"]],
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "name": _field("string", "Campaign name", maxLength=400),
            "objective": _field(
                "string", "Campaign objective", enum=META_OBJECTIVES,
                option_aliases={
                    "OUTCOME_SALES": ["sales campaign", "product sales", "销售广告", "商品销售"],
                    "OUTCOME_LEADS": ["lead generation", "lead gen", "潜在客户", "线索获客"],
                    "OUTCOME_TRAFFIC": ["traffic campaign", "website traffic", "流量广告", "网站流量"],
                    "OUTCOME_AWARENESS": ["brand awareness", "awareness campaign", "品牌曝光", "品牌认知"],
                    "OUTCOME_ENGAGEMENT": ["engagement campaign", "互动广告"],
                    "OUTCOME_APP_PROMOTION": ["app promotion", "app conversion", "app install", "App 转化", "App 广告", "应用推广", "应用转化"],
                    "OUTCOME_CONVERSIONS": ["conversion campaign", "转化广告", "网站转化"],
                    "OUTCOME_MESSAGES": ["messaging campaign", "message ads", "消息广告", "私信广告"],
                    "PRODUCT_CATALOG_SALES": ["catalog sales", "catalog ad", "商品目录销售", "目录广告"],
                },
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
            "daily_budget": _field(
                "number", "Daily budget", minimum=0,
                ui_visible_when={"not": {"field": "buying_type", "equals": "RESERVED"}},
            ),
            "lifetime_budget": _field(
                "number", "Lifetime budget", minimum=0,
                **_ui_equals("buying_type", "RESERVED"),
            ),
            "budget": _field(
                "number", "User-facing daily budget alias", minimum=0,
                ui_hidden=True,
            ),
            "spend_cap": _field("number", "Campaign spend cap", minimum=0),
            "start_time": _field("string", "ISO-8601 start time"),
            "end_time": _field("string", "ISO-8601 end time"),
            "catalog_id": _field(
                "string", "Meta product catalog ID",
                lookup_tool="meta_list_catalogs", lookup_result_key="catalogs",
                selection_value_fields=["id", "catalog_id"],
                selection_label_fields=["name", "id"],
                **_ui_when("objective", "PRODUCT_CATALOG_SALES"),
            ),
            "conversion_specs": _field(
                "array", "Conversion event specifications",
                items=_object({
                    "action_type": _field("string", "Meta conversion action type", enum=META_CUSTOM_EVENT_TYPES),
                    "event_type": _field("string", "Meta conversion event name", enum=META_CUSTOM_EVENT_TYPES),
                    "event_source": _meta_asset_ref(
                        "Pixel or app event source ID", "meta_list_pixels", "pixels",
                        ["id", "pixel_id"], ["name", "id"],
                    ),
                }, "Meta conversion specification", additional_properties=True),
                **_ui_when("objective", "OUTCOME_CONVERSIONS", "CONVERSIONS"),
            ),
            "messaging_apps": _field(
                "array", "Messaging destinations", items={"type": "string", "enum": ["MESSENGER", "WHATSAPP", "INSTAGRAM_DIRECT"]},
                **_ui_equals("objective", "OUTCOME_MESSAGES"),
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
        "capability_required": ["optimization_goal", "billing_event", "targeting"],
        # The parent Campaign may own the budget. Sending a second Ad Set
        # budget is rejected by Meta, so this cannot be a global one-of.
        "capability_any_of": [],
        "properties": {
            "campaign_id": _field("string", "Parent Campaign ID"),
            "name": _field("string", "Ad Set name", maxLength=400),
            "targeting": meta_targeting_schema(),
            "optimization_goal": _field("string", "Optimization goal", enum=META_OPTIMIZATION_GOALS),
            "billing_event": _field("string", "Billing event", enum=META_BILLING_EVENTS),
            "bid_strategy": _field(
                "string", "Bid strategy", enum=META_BID_STRATEGIES,
                input_aliases=["bidding_strategy"],
            ),
            "bidding_strategy": _field(
                "string", "Bid strategy alias", enum=META_BID_STRATEGIES,
                ui_hidden=True,
            ),
            "roas_average_floor": _field(
                "number", "Minimum ROAS floor for LOWEST_COST_WITH_MIN_ROAS", minimum=0.01,
            ),
            "promoted_object": {
                **meta_promoted_object_schema(),
                **_ui_when("optimization_goal", "OFFSITE_CONVERSIONS", "VALUE", "APP_INSTALLS"),
            },
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "lifetime_budget": _field("number", "Lifetime budget", minimum=0),
            "budget": _field(
                "number", "User-facing daily budget alias", minimum=0,
                ui_hidden=True,
            ),
            "bid_amount": _field(
                "number", "Bid amount", minimum=0,
                **_ui_when("bid_strategy", "LOWEST_COST_WITH_BID_CAP", "COST_CAP"),
            ),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
            "start_time": _field("string", "ISO-8601 start time"),
            "end_time": _field("string", "ISO-8601 end time"),
            "lead_gen_config": {
                **_meta_lead_gen_config_schema(),
                **_ui_when("optimization_goal", "LEAD_GENERATION", "LEADS"),
            },
            "product_set_id": _field(
                "string", "Catalog product set ID",
                lookup_tool="meta_list_product_sets", lookup_result_key="product_sets",
                selection_value_fields=["id", "product_set_id"],
                selection_label_fields=["name", "id"],
                **_ui_when("optimization_goal", "PRODUCT_CATALOG_SALES", "CATALOG_SALES"),
            ),
            "messaging_apps": _field(
                "array", "Messaging destinations", items={"type": "string", "enum": ["MESSENGER", "WHATSAPP", "INSTAGRAM_DIRECT"]},
                **_ui_equals("optimization_goal", "MESSAGES"),
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
            {
                "id": "bid_cap_requires_bid_amount",
                "if": {"bid_strategy": "LOWEST_COST_WITH_BID_CAP"},
                "required": ["bid_amount"],
                "message": "LOWEST_COST_WITH_BID_CAP requires bid_amount",
            },
            {
                "id": "cost_cap_requires_bid_amount",
                "if": {"bid_strategy": "COST_CAP"},
                "required": ["bid_amount"],
                "message": "COST_CAP requires bid_amount",
            },
            {
                "id": "min_roas_requires_floor",
                "if": {"bid_strategy": "LOWEST_COST_WITH_MIN_ROAS"},
                "required": ["roas_average_floor"],
                "message": "LOWEST_COST_WITH_MIN_ROAS requires roas_average_floor",
            },
            {
                "id": "bid_cap_alias_requires_bid_amount",
                "if": {"bidding_strategy": "LOWEST_COST_WITH_BID_CAP"},
                "required": ["bid_amount"],
                "message": "LOWEST_COST_WITH_BID_CAP requires bid_amount",
            },
            {
                "id": "cost_cap_alias_requires_bid_amount",
                "if": {"bidding_strategy": "COST_CAP"},
                "required": ["bid_amount"],
                "message": "COST_CAP requires bid_amount",
            },
            {
                "id": "min_roas_alias_requires_floor",
                "if": {"bidding_strategy": "LOWEST_COST_WITH_MIN_ROAS"},
                "required": ["roas_average_floor"],
                "message": "LOWEST_COST_WITH_MIN_ROAS requires roas_average_floor",
            },
            {
                "id": "billing_event_for_link_clicks",
                "if": {"optimization_goal": "LINK_CLICKS"},
                "allowed": {"billing_event": ["IMPRESSIONS", "LINK_CLICKS"]},
                "message": "LINK_CLICKS only supports IMPRESSIONS or LINK_CLICKS billing",
            },
            {
                "id": "billing_event_for_landing_page_views",
                "if": {"optimization_goal": "LANDING_PAGE_VIEWS"},
                "allowed": {"billing_event": ["IMPRESSIONS"]},
                "message": "LANDING_PAGE_VIEWS only supports IMPRESSIONS billing",
            },
            {
                "id": "billing_event_for_video_views",
                "if": {"optimization_goal": {"in": ["VIDEO_VIEWS", "THRUPLAY", "THRU_PLAY"]}},
                "allowed": {"billing_event": ["IMPRESSIONS", "THRUPLAY"]},
                "message": "Video-view optimization only supports IMPRESSIONS or THRUPLAY billing",
            },
            {
                "id": "billing_event_for_impression_optimized_goals",
                "if": {"optimization_goal": {"in": [
                    "APP_INSTALLS", "OFFSITE_CONVERSIONS", "VALUE", "LEAD_GENERATION",
                    "LEADS", "IMPRESSIONS", "REACH", "POST_ENGAGEMENT", "EVENT_RESPONSES",
                    "CONVERSIONS", "MESSAGES", "PAGE_LIKES", "PRODUCT_CATALOG_SALES",
                    "CATALOG_SALES",
                ]}},
                "allowed": {"billing_event": ["IMPRESSIONS"]},
                "message": "This optimization goal only supports IMPRESSIONS billing",
            },
        ],
    }


def meta_ad_schema() -> dict[str, Any]:
    image_ref = _meta_asset_ref(
        "Uploaded image hash", "meta_list_image_assets", "images",
        ["hash", "image_hash", "id"], ["name", "hash", "id"],
    )
    video_ref = _meta_asset_ref(
        "Uploaded video ID", "meta_list_video_assets", "videos",
        ["video_id", "id"], ["title", "name", "video_id", "id"],
    )
    cta_value = _object({
        "link": _field("string", "CTA destination URL", minLength=1),
        "app_link": _field("string", "CTA app deep link"),
        "lead_gen_form_id": _meta_asset_ref(
            "Instant Form ID", "meta_list_lead_forms", "lead_forms",
            ["id", "form_id"], ["name", "id"],
        ),
    }, "Meta CTA destination", additional_properties=True)
    carousel_attachment = _object({
        "link": _field("string", "Card destination URL", minLength=1),
        "name": _field("string", "Card headline"),
        "description": _field("string", "Card description"),
        "image_hash": image_ref,
        "video_id": video_ref,
        "call_to_action": _object({
            "type": _field("string", "Card CTA type", enum=META_CTA_TYPES),
            "value": cta_value,
        }, "Carousel card CTA", additional_properties=True),
    }, "Meta carousel attachment", additional_properties=True)
    return {
        "required": ["adset_id", "name"],
        # ``media`` is a supported provider-side shortcut for a simple image
        # ad. Keep it in the same source contract as the explicit Creative
        # variants so the Tool schema matches MetaClient.create_ad.
        "capability_any_of": [[
            "creative_id", "object_story_spec", "creative", "media", "image_url"
        ]],
        "properties": {
            "adset_id": _field("string", "Parent Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "ad_format": _field("string", "Inline creative format", enum=META_AD_FORMATS),
            "creative_id": _field(
                "string", "Existing Creative ID", minLength=1,
                lookup_tool="meta_list_creatives", lookup_result_key="creatives",
                selection_value_fields=["id", "creative_id"],
                selection_label_fields=["name", "id"],
            ),
            "object_story_spec": _object({
                "page_id": _field(
                    "string", "Page ID", minLength=1,
                    lookup_tool="meta_list_pages", lookup_result_key="pages",
                    selection_value_fields=["id", "page_id"],
                    selection_label_fields=["name", "id"],
                ),
                "link_data": _object({
                    "link": _field("string", "Destination URL"),
                    "message": _field("string", "Primary text"),
                    "name": _field("string", "Headline"),
                    "description": _field("string", "Description"),
                    "image_hash": image_ref,
                    "call_to_action": _object({
                        "type": _field("string", "Call to action type", enum=META_CTA_TYPES),
                        "value": cta_value,
                    }, "Link ad call to action", additional_properties=True),
                }, "Link ad story"),
                "video_data": _object({
                    "video_id": video_ref,
                    "message": _field("string", "Primary text"),
                    "title": _field("string", "Video title"),
                    "call_to_action": _object({
                        "type": _field("string", "Call to action type", enum=META_CTA_TYPES),
                        "value": cta_value,
                    }, "Video ad call to action", additional_properties=True),
                }, "Video ad story"),
                "carousel_data": _object({
                    "link": _field("string", "Carousel fallback URL"),
                    "message": _field("string", "Carousel primary text"),
                    "name": _field("string", "Carousel headline"),
                    "description": _field("string", "Carousel description"),
                    "child_attachments": _field(
                        "array", "Carousel cards", minItems=2, maxItems=10,
                        items=carousel_attachment,
                        presentation="object_editor",
                    ),
                }, "Carousel ad story", additional_properties=True),
                "lead_gen": _object({
                    "page_id": _meta_asset_ref(
                        "Facebook Page ID", "meta_list_pages", "pages",
                        ["id", "page_id"], ["name", "id"],
                    ),
                    "form_id": _meta_asset_ref(
                        "Published Instant Form ID", "meta_list_lead_forms", "lead_forms",
                        ["id", "form_id"], ["name", "id"],
                    ),
                }, "Lead generation creative reference", additional_properties=True),
            }, "Meta object story specification"),
            "creative": {
                **_object({}, "Creative reference or inline payload", additional_properties=True),
                "manual_entry": {
                    "title": "高级 Creative Payload",
                    "instructions": "可直接选择已有 Creative；只有 Provider 已明确要求内联字段时才填写此高级 JSON。优先使用已声明的 Page、素材和 CTA 字段。",
                    "source": "provider_inline_creative",
                },
            },
            "media": _field(
                "array", "Simple media shortcut; the first item must contain a provider URL",
                minItems=1,
                manual_entry={
                    "title": "素材 URL 快捷方式",
                    "instructions": "优先上传并选择 Meta image_hash/video_id；此字段仅用于 Meta 可直接抓取的 HTTPS 素材 URL。",
                    "source": "provider_media_url",
                },
                presentation="asset_picker",
                items=_object({
                    "type": _field("string", "Media type", enum=["image", "video"]),
                    "url": _field("string", "Provider-accessible media URL", minLength=1),
                }, "Meta media item", additional_properties=True, required=["url"]),
            ),
            "image_url": _field("string", "Simple image creative URL", minLength=1),
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
        "capability_required": ["page_id", "form_id"],
        "properties": {
            "adset_id": _field("string", "Parent Meta Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "page_id": _field(
                "string", "Facebook Page ID", minLength=1,
                lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "form_id": _field(
                "string", "Published Instant Form ID", minLength=1,
                lookup_tool="meta_list_lead_forms", lookup_result_key="lead_forms",
                selection_value_fields=["id", "form_id"],
                selection_label_fields=["name", "id"],
            ),
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


def meta_catalog_ad_schema() -> dict[str, Any]:
    """Create contract for a Meta Catalog/Dynamic Product Ad."""
    return {
        "required": ["adset_id", "name", "page_id", "product_set_id", "link", "ad_style"],
        "capability_required": ["page_id", "product_set_id", "link"],
        "properties": {
            "adset_id": _field("string", "Parent Meta Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "page_id": _field(
                "string", "Facebook Page ID", minLength=1,
                lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "product_set_id": _field(
                "string", "Meta product set ID", minLength=1,
                lookup_tool="meta_list_product_sets",
                lookup_result_key="product_sets",
                selection_value_fields=["id", "product_set_id"],
                selection_label_fields=["name", "id"],
            ),
            "link": _field("string", "Catalog landing URL", minLength=1),
            "message": _field("string", "Primary text"),
            "headline": _field("string", "Headline"),
            "description": _field("string", "Description"),
            "ad_style": _field(
                "string", "Catalog ad style",
                enum=["CAROUSEL", "COLLAGE", "PRODUCT_SET"],
            ),
            "call_to_action_type": _field(
                "string", "Catalog ad CTA",
                enum=["SHOP_NOW", "LEARN_MORE", "BUY_NOW"],
                default="SHOP_NOW",
            ),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
        },
    }


def meta_messaging_ad_schema() -> dict[str, Any]:
    """Create contract for a Meta click-to-message creative."""
    return {
        "required": [
            "adset_id", "name", "page_id", "messaging_app",
            "call_to_action_type",
        ],
        "capability_required": ["page_id", "messaging_app", "call_to_action_type"],
        "properties": {
            "adset_id": _field("string", "Parent Meta Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "page_id": _field(
                "string", "Facebook Page ID", minLength=1,
                lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "messaging_app": _field(
                "string", "Click-to-message destination",
                enum=META_MESSAGING_APPS,
            ),
            "link": _field("string", "Optional destination URL", minLength=1),
            "message": _field("string", "Primary text"),
            "headline": _field("string", "Headline"),
            "description": _field("string", "Description"),
            "call_to_action_type": _field(
                "string", "Messaging CTA type", enum=["SEND_MESSAGE", "WHATSAPP"],
            ),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
        },
        "conditional_rules": [
            {
                "id": "whatsapp_requires_whatsapp_cta",
                "if": {"messaging_app": "WHATSAPP"},
                "allowed": {"call_to_action_type": ["WHATSAPP"]},
                "message": "WHATSAPP destination requires WHATSAPP CTA",
            },
            {
                "id": "messenger_requires_send_message_cta",
                "if": {"messaging_app": "MESSENGER"},
                "allowed": {"call_to_action_type": ["SEND_MESSAGE"]},
                "message": "MESSENGER destination requires SEND_MESSAGE CTA",
            },
            {
                "id": "instagram_direct_requires_send_message_cta",
                "if": {"messaging_app": "INSTAGRAM_DIRECT"},
                "allowed": {"call_to_action_type": ["SEND_MESSAGE"]},
                "message": "INSTAGRAM_DIRECT destination requires SEND_MESSAGE CTA",
            },
        ],
    }


def meta_link_ad_schema() -> dict[str, Any]:
    """Create contract for a website-link image or video creative."""
    return {
        "required": ["adset_id", "name", "page_id", "link"],
        "capability_required": ["page_id", "link"],
        "properties": {
            "adset_id": _field("string", "Parent Meta Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "page_id": _field(
                "string", "Facebook Page ID", minLength=1,
                lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "link": _field("string", "Destination URL", minLength=1),
            "media_type": _field(
                "string", "Link creative media type", enum=["IMAGE", "VIDEO"],
                default="IMAGE",
            ),
            "image_hash": _field(
                "string", "Uploaded image hash", minLength=1,
                lookup_tool="meta_list_image_assets", lookup_result_key="images",
                selection_value_fields=["hash", "image_hash", "id"],
                selection_label_fields=["name", "hash", "id"],
                **_ui_equals("media_type", "IMAGE"),
            ),
            "video_id": _field(
                "string", "Uploaded video ID", minLength=1,
                lookup_tool="meta_list_video_assets", lookup_result_key="videos",
                selection_value_fields=["video_id", "id"],
                selection_label_fields=["title", "name", "video_id", "id"],
                **_ui_equals("media_type", "VIDEO"),
            ),
            "message": _field("string", "Primary text"),
            "headline": _field("string", "Headline"),
            "description": _field("string", "Description"),
            "call_to_action_type": _field(
                "string", "Link ad CTA",
                enum=["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "CONTACT_US"],
                default="LEARN_MORE",
            ),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
        },
        "conditional_rules": [
            {
                "id": "image_link_requires_image_hash",
                "if": {"media_type": "IMAGE"},
                "required": ["image_hash"],
                "message": "IMAGE link creatives require image_hash",
            },
            {
                "id": "video_link_requires_video_id",
                "if": {"media_type": "VIDEO"},
                "required": ["video_id"],
                "message": "VIDEO link creatives require video_id",
            },
        ],
    }


def meta_engagement_ad_schema() -> dict[str, Any]:
    """Create contract for post-engagement and video-view creatives."""
    return {
        "required": ["adset_id", "name", "page_id", "engagement_type"],
        "capability_required": ["page_id", "engagement_type"],
        "properties": {
            "adset_id": _field("string", "Parent Meta Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "page_id": _field(
                "string", "Facebook Page ID", minLength=1,
                lookup_tool="meta_list_pages", lookup_result_key="pages",
                selection_value_fields=["id", "page_id"],
                selection_label_fields=["name", "id"],
            ),
            "engagement_type": _field(
                "string", "Engagement creative type",
                enum=["POST_ENGAGEMENT", "VIDEO_VIEWS"],
            ),
            "post_id": _field(
                "string", "Existing Page post ID", minLength=1,
                manual_entry={
                    "title": "帖子 ID",
                    "instructions": "请提供该 Facebook Page 上已有帖子的 ID；当前 Capability 没有通用 Page 帖子列表接口。",
                    "source": "provider_page_post",
                },
            ),
            "video_id": _field(
                "string", "Video ID", minLength=1,
                lookup_tool="meta_list_video_assets", lookup_result_key="videos",
                selection_value_fields=["video_id", "id"],
                selection_label_fields=["title", "name", "video_id", "id"],
            ),
            "message": _field("string", "Primary text"),
            "headline": _field("string", "Video title"),
            "call_to_action_type": _field(
                "string", "Video engagement CTA", enum=["WATCH_VIDEO"],
                default="WATCH_VIDEO",
            ),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
        },
        "conditional_rules": [
            {
                "id": "post_engagement_requires_post_id",
                "if": {"engagement_type": "POST_ENGAGEMENT"},
                "required": ["post_id"],
                "message": "POST_ENGAGEMENT creatives require post_id",
            },
            {
                "id": "video_views_requires_video_id",
                "if": {"engagement_type": "VIDEO_VIEWS"},
                "required": ["video_id", "call_to_action_type"],
                "message": "VIDEO_VIEWS creatives require video_id and WATCH_VIDEO CTA",
            },
        ],
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
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_traffic_ad"],
            "dependencies": ["targeting", "optimization_goal", "link_data"],
            "supported_fields": ["OUTCOME_TRAFFIC", "LINK_CLICKS", "targeting", "object_story_spec.link_data"],
            "gaps": ["placement compatibility validation"],
            "source_document": source_document,
        },
        {
            "format_id": "conversion",
            "category": "conversion",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_conversion_ad"],
            "dependencies": ["promoted_object", "conversion_specs", "pixel_or_capi"],
            "supported_fields": ["OUTCOME_CONVERSIONS", "OFFSITE_CONVERSIONS", "CONVERSIONS", "promoted_object"],
            "gaps": ["conversion event lookup/validation"],
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
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_engagement_ad"],
            "dependencies": ["post_id_or_story", "targeting", "optimization_goal"],
            "supported_fields": ["OUTCOME_ENGAGEMENT", "POST_ENGAGEMENT", "VIDEO_VIEWS"],
            "gaps": ["Page Likes specialized creative validation", "placement compatibility validation"],
            "source_document": source_document,
        },
        {
            "format_id": "link_image",
            "category": "traffic",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["meta_create_traffic_ad"],
            "payload_adapter": "MetaAPIClient.create_link_ad",
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
            "tool_names": ["meta_create_engagement_ad"],
            "payload_adapter": "MetaAPIClient.create_engagement_ad",
            "dependencies": ["adset", "page_id", "video_data"],
            "supported_fields": ["page_id", "video_id", "message", "headline", "call_to_action_type"],
            "gaps": ["live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "catalog",
            "category": "catalog",
            "resource_type": "campaign",
            "coverage": "supported_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_catalog_ad"],
            "payload_adapter": "MetaAPIClient.create_catalog_ad",
            "dependencies": ["catalog_id", "product_set_id", "catalog creative"],
            "gaps": ["dynamic product rules", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "catalog.dynamic_product",
            "category": "catalog",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["meta_create_adset", "meta_create_catalog_ad"],
            "payload_adapter": "MetaAPIClient.create_catalog_ad",
            "dependencies": ["catalog_id", "product_set_id", "dynamic product rules"],
            "gaps": ["dynamic product rules", "live mutation approval"],
            "source_document": source_document,
        },
        {
            "format_id": "messaging",
            "category": "messaging",
            "resource_type": "campaign",
            "coverage": "partial_dry_run",
            "tool_names": ["meta_create_campaign", "meta_create_adset", "meta_create_ad", "meta_create_messaging_ad"],
            "dependencies": ["messaging_apps", "SEND_MESSAGE CTA", "page_or_business_messaging_identity"],
            "supported_fields": ["OUTCOME_MESSAGES", "MESSAGES", "messaging_apps", "call_to_action"],
            "gaps": ["objective-specific placement compatibility validation"],
            "source_document": source_document,
        },
        {
            "format_id": "messaging.click_to_message",
            "category": "messaging",
            "resource_type": "ad",
            "coverage": "supported_dry_run",
            "tool_names": ["meta_create_messaging_ad"],
            "payload_adapter": "MetaAPIClient.create_messaging_ad",
            "dependencies": ["page_id", "messaging_app", "SEND_MESSAGE/WHATSAPP CTA"],
            "supported_fields": ["page_id", "messaging_app", "link", "message", "headline", "description", "call_to_action_type"],
            "gaps": ["live mutation approval"],
            "source_document": source_document,
        },
    ]
