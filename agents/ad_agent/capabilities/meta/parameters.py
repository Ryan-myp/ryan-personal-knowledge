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
]
META_AD_FORMATS = ["LINK", "VIDEO", "CAROUSEL", "LEAD", "CATALOG"]
META_SPECIAL_AD_CATEGORIES = ["NONE", "EMPLOYMENT", "HOUSING", "CREDIT"]
META_STATUS = ["ACTIVE", "PAUSED"]
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
    "adworkposition", "adtargetingcategory",
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


def meta_targeting_search_schema() -> dict[str, Any]:
    """Schema for Meta's account-scoped Targeting Search endpoint."""
    return {
        "required": ["account_id", "query"],
        "provider_required": ["account_id", "query"],
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
        "provider_required": ["name", "subtype"],
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
            "rule": _field("object", "Meta website/event audience rule", additionalProperties=True),
            "prefill": _field("boolean", "Prefill audience with prior events"),
            "pixel_id": _field("string", "Meta Pixel source ID"),
            "event_source_group": _field("string", "Meta event source group ID"),
            "origin_audience_id": _field("string", "Source Custom Audience ID for Lookalike"),
            "country": _field("string", "Two-letter lookalike country code", minLength=2, maxLength=2),
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


def meta_catalog_schema() -> dict[str, Any]:
    """Contracts for Meta Catalog and Product Set management."""
    catalog_ref = {
        "account_id": _field("string", "Meta ad account ID"),
        "catalog_id": _field("string", "Meta Product Catalog ID", minLength=1),
        "business_id": _field(
            "string", "Meta Business ID used only for Catalog creation", minLength=1
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
                additionalProperties=True,
            ),
            "fields": _field("array", "Fields to return", items={"type": "string"}),
            "limit": _field("integer", "Maximum number of records", minimum=1, maximum=1000),
            "updates": _object({
                "name": _field("string", "Product Set name", minLength=1, maxLength=200),
                "filter": _field(
                    "object", "Meta product set filter expression",
                    additionalProperties=True,
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
        "provider_required": ["pixel_id", "events"],
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
        "provider_required": ["name", "rule"],
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
        "provider_required": ["name", "questions", "privacy_policy"],
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


def meta_creative_schema() -> dict[str, Any]:
    """Contract for Meta Creative reads and the supported mutable fields."""
    return {
        "properties": {
            "account_id": _field("string", "Meta ad account ID"),
            "creative_id": _field("string", "Meta Creative ID", minLength=1),
            "name": _field("string", "Creative name", minLength=1, maxLength=400),
            "page_id": _field("string", "Facebook Page ID"),
            "link": _field("string", "Destination URL"),
            "message": _field("string", "Primary text"),
            "image_hash": _field("string", "Uploaded image hash"),
            "image_url": _field("string", "Image URL for create"),
            "fields": _field("array", "Fields to return", items={"type": "string"}),
            "limit": _field("integer", "Maximum number of creatives", minimum=1, maximum=1000),
            "updates": _object({
                "name": _field("string", "Creative name", minLength=1, maxLength=400),
            }, "Supported Creative update fields"),
        },
    }


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
            "catalog_id": _field(
                "string", "Meta product catalog ID",
                lookup_tool="meta_list_catalogs", lookup_result_key="catalogs",
                selection_value_fields=["id", "catalog_id"],
                selection_label_fields=["name", "id"],
            ),
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
            "roas_average_floor": _field(
                "number", "Minimum ROAS floor for LOWEST_COST_WITH_MIN_ROAS", minimum=0.01,
            ),
            "promoted_object": meta_promoted_object_schema(),
            "daily_budget": _field("number", "Daily budget", minimum=0),
            "lifetime_budget": _field("number", "Lifetime budget", minimum=0),
            "budget": _field("number", "User-facing daily budget alias", minimum=0),
            "bid_amount": _field("number", "Bid amount", minimum=0),
            "status": _field("string", "Initial delivery status", enum=META_STATUS),
            "start_time": _field("string", "ISO-8601 start time"),
            "end_time": _field("string", "ISO-8601 end time"),
            "lead_gen_config": _field("object", "Instant Form configuration", additionalProperties=True),
            "product_set_id": _field(
                "string", "Catalog product set ID",
                lookup_tool="meta_list_product_sets", lookup_result_key="product_sets",
                selection_value_fields=["id", "product_set_id"],
                selection_label_fields=["name", "id"],
            ),
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
        ],
    }


def meta_ad_schema() -> dict[str, Any]:
    return {
        "required": ["adset_id", "name"],
        "provider_any_of": [["creative_id", "object_story_spec", "creative"]],
        "properties": {
            "adset_id": _field("string", "Parent Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "ad_format": _field("string", "Inline creative format", enum=META_AD_FORMATS),
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
                        "type": _field("string", "Call to action type", enum=META_CTA_TYPES),
                        "value": _field("object", "Call to action destination", additionalProperties=True),
                    }, "Link ad call to action"),
                }, "Link ad story"),
                "video_data": _object({
                    "video_id": _field("string", "Video ID"),
                    "message": _field("string", "Primary text"),
                    "title": _field("string", "Video title"),
                    "call_to_action": _object({
                        "type": _field("string", "Call to action type", enum=META_CTA_TYPES),
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


def meta_catalog_ad_schema() -> dict[str, Any]:
    """Create contract for a Meta Catalog/Dynamic Product Ad."""
    return {
        "required": ["adset_id", "name", "page_id", "product_set_id", "link", "ad_style"],
        "provider_required": ["page_id", "product_set_id", "link"],
        "properties": {
            "adset_id": _field("string", "Parent Meta Ad Set ID"),
            "name": _field("string", "Ad name", maxLength=400),
            "page_id": _field("string", "Facebook Page ID", minLength=1),
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
