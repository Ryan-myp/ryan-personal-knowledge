"""
capabilities/google/capability.py - Google Capability 定义
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler, apply_lookup_contracts
from ..provider_tools import bind_provider_method, method_tool
from .campaigns import (
    GoogleListCampaignsHandler,
    GoogleGetCampaignHandler,
    GoogleCreateCampaignHandler,
)
from .ad_groups import (
    GoogleListAdGroupsHandler,
    GoogleGetAdGroupHandler,
    GoogleCreateAdGroupHandler,
)
from .ads import GoogleListAdsHandler, GoogleGetAdHandler, GoogleCreateAdHandler
from .assets import (
    GoogleListAssetGroupsHandler,
    GoogleGetAssetGroupHandler,
    GoogleCreateAssetGroupHandler,
)
from .reports import GoogleGetReportHandler
from .keywords import GoogleListKeywordsHandler
from ._utils import for_customer
from .parameters import (
    google_campaign_schema, google_ad_group_schema, google_app_ad_group_schema,
    google_app_ad_schema, google_ad_schema,
    google_asset_schema, google_asset_create_schema, google_campaign_asset_schema,
    google_asset_group_asset_schema, google_asset_group_schema, google_ad_format_catalog, google_keyword_schema,
    google_product_group_schema, google_responsive_display_ad_schema,
    google_video_ad_schema, google_campaign_budget_schema,
    google_demand_gen_multi_asset_ad_schema, google_demand_gen_carousel_ad_schema,
    google_demand_gen_video_responsive_ad_schema, google_demand_gen_product_ad_schema,
    google_hotel_ad_schema, google_local_ad_schema, google_smart_campaign_ad_schema,
    google_travel_ad_schema,
    google_campaign_budget_update_schema,
    google_experiment_schema, google_experiment_update_schema,
    google_conversion_action_schema, google_conversion_action_update_schema,
    google_campaign_criterion_schema, google_keyword_update_schema,
    google_user_list_schema, google_user_list_update_schema,
    google_bidding_strategy_schema, google_bidding_strategy_update_schema,
    google_product_group_update_schema, google_product_group_read_schema,
    google_asset_group_listing_group_filter_schema,
    google_asset_group_listing_group_filter_update_schema,
    google_asset_group_listing_group_filter_read_schema,
    google_feed_schema, google_conversion_goal_schema,
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient
from ...core.blueprint import load_blueprint_file
from ..update_contracts import google_updates

logger = logging.getLogger(__name__)


def _google_lookup(tool: str, result_key: str, values: list[str], labels: list[str], *, depends_on: list[dict] | None = None) -> dict:
    """Build a declarative Google resource picker contract."""
    metadata = {
        "lookup_tool": tool,
        "lookup_result_key": result_key,
        "selection_value_fields": values,
        "selection_label_fields": labels,
    }
    if depends_on:
        metadata["lookup_dependencies"] = depends_on
    return metadata


def _build_specialized_ad_args(
    data: dict[str, Any], positional: list[str], optional: list[str], tool_name: str,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Build typed-ad arguments without leaking a Python ``KeyError``.

    Provider requirements are validated by Runtime/Registry before normal
    execution.  This second guard protects direct Capability handler calls and
    turns a partially assembled conversational draft into an actionable
    validation error instead of an internal exception.
    """
    missing = [
        key for key in positional
        if data.get(key) in (None, "", {}, [])
    ]
    if missing:
        raise ValueError(
            f"{tool_name} requires provider fields: {', '.join(missing)}"
        )
    return tuple(data[key] for key in positional), {
        key: data.get(key) for key in optional
    }


# The mapping is provider-owned metadata, not Runtime routing.  It covers
# every reusable Google resource ID exposed by the Capability, including
# standalone lifecycle Tools and the creation blueprints.
GOOGLE_LOOKUP_CONTRACTS = {
    "*": {
        "campaign_id": _google_lookup(
            "google_list_campaigns", "campaigns", ["id", "campaign_id", "resource_name"],
            ["name", "campaign_name", "id"],
        ),
        "ad_group_id": _google_lookup(
            "google_list_ad_groups", "ad_groups", ["id", "ad_group_id", "resource_name"],
            ["name", "ad_group_name", "id"], depends_on=[{
                "input_field": "campaign_id", "value_path": "campaign_id",
                "label": "所属 Campaign", "required": True,
            }],
        ),
        "ad_id": _google_lookup(
            "google_list_ads", "ads", ["id", "ad_id", "resource_name"],
            ["name", "ad_name", "id"], depends_on=[{
                "input_field": "ad_group_id", "value_path": "ad_group_id",
                "label": "所属广告组", "required": True,
            }],
        ),
        "asset_group_id": _google_lookup(
            "google_list_asset_groups", "asset_groups", ["id", "asset_group_id", "resource_name"],
            ["name", "asset_group_name", "id"], depends_on=[{
                "input_field": "campaign_id", "value_path": "campaign_id",
                "label": "所属 Campaign", "required": True,
            }],
        ),
        "asset_id": _google_lookup(
            "google_list_assets", "assets", ["id", "asset_id", "resource_name"],
            ["name", "asset_name", "id"],
        ),
        "budget_id": _google_lookup(
            "google_list_campaign_budgets", "budgets", ["id", "budget_id", "resource_name"],
            ["name", "budget_name", "id"],
        ),
        "conversion_action_id": _google_lookup(
            "google_list_conversion_actions", "conversion_actions",
            ["id", "conversion_action_id", "resource_name"],
            ["name", "conversion_action_name", "id"],
        ),
        "bidding_strategy_id": _google_lookup(
            "google_list_bidding_strategies", "bidding_strategies",
            ["id", "bidding_strategy_id", "resource_name"],
            ["name", "bidding_strategy_name", "id"],
        ),
        "user_list_id": _google_lookup(
            "google_list_user_lists", "user_lists", ["id", "user_list_id", "resource_name"],
            ["name", "user_list_name", "id"],
        ),
        "experiment_id": _google_lookup(
            "google_list_experiments", "experiments", ["id", "experiment_id", "resource_name"],
            ["name", "experiment_name", "id"],
        ),
        "criterion_id": _google_lookup(
            "google_list_campaign_criteria", "criteria", ["id", "criterion_id", "resource_name"],
            ["name", "criterion_name", "id"], depends_on=[{
                "input_field": "campaign_id", "value_path": "campaign_id",
                "label": "所属 Campaign", "required": True,
            }],
        ),
        "product_group_id": _google_lookup(
            "google_list_product_groups", "product_groups", ["id", "product_group_id", "resource_name"],
            ["name", "product_group_name", "id"], depends_on=[{
                "input_field": "ad_group_id", "value_path": "ad_group_id",
                "label": "所属商品广告组", "required": True,
            }],
        ),
        "parent_criterion_id": _google_lookup(
            "google_list_product_groups", "product_groups",
            ["id", "product_group_id", "criterion_id", "resource_name"],
            ["name", "product_group_name", "criterion_id", "id"],
            depends_on=[{
                "input_field": "ad_group_id", "value_path": "ad_group_id",
                "label": "所属商品广告组", "required": True,
            }],
        ),
        "parent_filter_id": _google_lookup(
            "google_list_asset_group_listing_group_filters", "listing_group_filters",
            ["listing_group_filter_id", "id", "resource_name"],
            ["product_dimension", "value", "id", "resource_name"],
            depends_on=[{
                "input_field": "asset_group_id", "value_path": "asset_group_id",
                "label": "所属 Asset Group", "required": True,
            }],
        ),
        # Google Ads API does not expose a customer-scoped App catalog.  An
        # App ID is an external store identifier and must never be fabricated
        # from a campaign/account lookup.
        "app_id": {
            "manual_entry": {
                "title": "外部应用标识",
                "instructions": "Google Play 填应用包名（例如 com.example.app）；Apple App Store 填数字 App Store ID。Google Ads API 没有可按账户列出的应用列表。",
                "example": "com.example.app 或 1234567890",
                "source": "external_store_identifier",
            },
        },
        "merchant_id": {
            "manual_entry": {
                "title": "Merchant Center ID",
                "instructions": "该 ID 来自 Merchant Center，不属于 Google Ads 可枚举资源，请从 Merchant Center 账户设置中复制。",
                "example": "1234567890",
                "source": "external_provider_identifier",
            },
        },
        "video_id": {
            "manual_entry": {
                "title": "YouTube 视频 ID",
                "instructions": "Google Ads API 当前不提供可直接用于此字段的 YouTube 视频目录查询，请粘贴 YouTube 视频 URL 中的 11 位视频 ID。",
                "example": "dQw4w9WgXcQ",
                "source": "external_youtube_identifier",
            },
        },
        "youtube_video_id": {
            "manual_entry": {
                "title": "YouTube 视频 ID",
                "instructions": "请粘贴 YouTube 视频 URL 中的 11 位视频 ID。",
                "example": "dQw4w9WgXcQ",
                "source": "external_youtube_identifier",
            },
        },
    },
}


def _google_update_adapter(client, ctx, resource_type, resource_id, _parent_id, updates):
    """Adapt Google Ads' customer-scoped resource update methods."""
    method_name = {
        "campaign": "update_campaign",
        "ad_group": "update_ad_group",
        "ad": "update_ad",
        "asset_group": "update_asset_group",
    }.get(resource_type)
    if not method_name:
        raise AttributeError(f"Google {resource_type} update adapter is unavailable")
    factory = getattr(type(client), "for_customer", None)
    scoped_client = factory(client, ctx.account_id) if factory and ctx.account_id else client
    if scoped_client is client and ctx.account_id and hasattr(client, "customer_id"):
        client.customer_id = ctx.account_id
    method = getattr(scoped_client, method_name, None)
    if not callable(method):
        raise AttributeError(f"Google {resource_type} update adapter is unavailable")
    return method(resource_id, updates)


class GoogleCapability(BaseCapability):
    platform_name = "google-ads"
    provider_client_class = GoogleAdsAPIClient
    # Google Ads v24 no longer exposes the legacy Feed/FeedItem GAQL
    # resources. Keep the old client adapters for isolated contract tests and
    # a future versioned adapter, but do not publish them as executable Tools
    # in the current Capability. This is deliberately an explicit exclusion,
    # so the capability audit cannot mistake compatibility code for coverage.
    provider_method_exclusions = {
        "for_customer",
        "list_feeds", "get_feed", "create_feed", "update_feed", "delete_feed",
        "list_feed_items", "get_feed_item", "create_feed_item",
        "update_feed_item", "delete_feed_item",
    }
    capability_version = "1.4.0"
    provider_api_version = "v24"
    provider_method_coverage = {
        "list_campaigns": ["google_list_campaigns"], "get_campaign": ["google_get_campaign"],
        "list_ad_groups": ["google_list_ad_groups"], "get_ad_group": ["google_get_ad_group"],
        "list_ads": ["google_list_ads"], "get_ad": ["google_get_ad"],
        "delete_campaign": ["google_delete_campaign"],
        "delete_ad_group": ["google_delete_ad_group"], "delete_ad": ["google_delete_ad"],
        "list_keywords": ["google_list_keywords"], "list_asset_groups": ["google_list_asset_groups"],
        "list_assets": ["google_list_assets"], "get_asset": ["google_get_asset"],
        "create_asset": ["google_create_asset"], "delete_asset": ["google_delete_asset"],
        "list_campaign_assets": ["google_list_campaign_assets"],
        "create_campaign_asset": ["google_create_campaign_asset"],
        "delete_campaign_asset": ["google_delete_campaign_asset"],
        "list_asset_group_assets": ["google_list_asset_group_assets"],
        "create_asset_group_asset": ["google_create_asset_group_asset"],
        "delete_asset_group_asset": ["google_delete_asset_group_asset"],
        "list_asset_group_listing_group_filters": [
            "google_list_asset_group_listing_group_filters"
        ],
        "get_asset_group_listing_group_filter": [
            "google_get_asset_group_listing_group_filter"
        ],
        "create_asset_group_listing_group_filter": [
            "google_create_asset_group_listing_group_filter"
        ],
        "update_asset_group_listing_group_filter": [
            "google_update_asset_group_listing_group_filter"
        ],
        "delete_asset_group_listing_group_filter": [
            "google_delete_asset_group_listing_group_filter"
        ],
        "create_keywords": ["google_create_keywords"],
        "update_keyword": ["google_update_keyword"],
        "delete_keyword": ["google_delete_keyword"],
        "get_asset_group": ["google_get_asset_group"], "create_campaign": ["google_create_campaign"],
        "update_campaign": ["google_update_campaign"], "update_ad_group": ["google_update_ad_group"],
        "update_ad": ["google_update_ad"], "update_asset_group": ["google_update_asset_group"],
        "pause_campaign": ["google_pause_campaign"], "resume_campaign": ["google_resume_campaign"],
        "create_ad_group": [
            "google_create_ad_group", "google_create_app_ad_group",
            "google_create_specialized_ad_group",
        ],
        "create_app_ad": ["google_create_app_ad"],
        "create_search_ad": ["google_create_search_ad", "google_create_ad"],
        "create_pmax_asset_group": ["google_create_pmax_asset_group", "google_create_asset_group"],
        "create_product_group": ["google_create_product_group"],
        "list_product_groups": ["google_list_product_groups"],
        "get_product_group": ["google_get_product_group"],
        "update_product_group": ["google_update_product_group"],
        "delete_product_group": ["google_delete_product_group"],
        "create_responsive_display_ad": ["google_create_responsive_display_ad"],
        "create_video_ad": ["google_create_video_ad"],
        "create_demand_gen_multi_asset_ad": ["google_create_demand_gen_multi_asset_ad"],
        "create_demand_gen_carousel_ad": ["google_create_demand_gen_carousel_ad"],
        "create_demand_gen_video_responsive_ad": ["google_create_demand_gen_video_responsive_ad"],
        "create_demand_gen_product_ad": ["google_create_demand_gen_product_ad"],
        "create_hotel_ad": ["google_create_hotel_ad"],
        "create_local_ad": ["google_create_local_ad"],
        "create_smart_campaign_ad": ["google_create_smart_campaign_ad"],
        "create_travel_ad": ["google_create_travel_ad"],
        "list_campaign_budgets": ["google_list_campaign_budgets"],
        "get_campaign_budget": ["google_get_campaign_budget"],
        "create_campaign_budget": ["google_create_campaign_budget"],
        "update_campaign_budget": ["google_update_campaign_budget"],
        "delete_campaign_budget": ["google_delete_campaign_budget"],
        "list_campaign_criteria": ["google_list_campaign_criteria"],
        "get_campaign_criterion": ["google_get_campaign_criterion"],
        "create_campaign_criteria": ["google_create_campaign_criteria"],
        "update_campaign_criterion": ["google_update_campaign_criterion"],
        "delete_campaign_criterion": ["google_delete_campaign_criterion"],
        "list_conversion_actions": ["google_list_conversion_actions"],
        "get_conversion_action": ["google_get_conversion_action"],
        "create_conversion_action": ["google_create_conversion_action"],
        "update_conversion_action": ["google_update_conversion_action"],
        "delete_conversion_action": ["google_delete_conversion_action"],
        "list_bidding_strategies": ["google_list_bidding_strategies"],
        "get_bidding_strategy": ["google_get_bidding_strategy"],
        "create_bidding_strategy": ["google_create_bidding_strategy"],
        "update_bidding_strategy": ["google_update_bidding_strategy"],
        "delete_bidding_strategy": ["google_delete_bidding_strategy"],
        "list_user_lists": ["google_list_user_lists"],
        "get_user_list": ["google_get_user_list"],
        "create_user_list": ["google_create_user_list"],
        "update_user_list": ["google_update_user_list"],
        "delete_user_list": ["google_delete_user_list"],
        "upload_user_list_data": ["google_upload_user_list_data"],
        "list_customer_clients": ["google_list_customer_clients"],
        "list_experiments": ["google_list_experiments"],
        "list_experiment_arms": ["google_list_experiment_arms"],
        "get_experiment": ["google_get_experiment"],
        "create_experiment": ["google_create_experiment"],
        "update_experiment": ["google_update_experiment"],
        "delete_experiment": ["google_delete_experiment"],
        "schedule_experiment": ["google_schedule_experiment"],
        "end_experiment": ["google_end_experiment"],
        "graduate_experiment": ["google_graduate_experiment"],
        "promote_experiment": ["google_promote_experiment"],
        "get_campaign_report": ["google_get_campaign_report"], "get_adgroup_report": ["google_get_adgroup_report"],
        "list_customer_conversion_goals": ["google_list_customer_conversion_goals"],
        "update_customer_conversion_goal": ["google_update_customer_conversion_goal"],
        "list_campaign_conversion_goals": ["google_list_campaign_conversion_goals"],
        "update_campaign_conversion_goal": ["google_update_campaign_conversion_goal"],
    }

    def get_ad_format_catalog(self) -> list[dict]:
        return google_ad_format_catalog()

    def get_creation_blueprints(self) -> list:
        """Load provider-owned Google Ads creation blueprints from JSON."""
        blueprint_dir = Path(__file__).with_name("blueprints")
        return [load_blueprint_file(path) for path in sorted(blueprint_dir.glob("*.json"))]

    def _extended_provider_tools(self, client):
        """Expose Google Ads client endpoints with dedicated contracts."""
        budget_schema = google_campaign_budget_schema()
        conversion_action_schema = google_conversion_action_schema()
        conversion_action_update_schema = google_conversion_action_update_schema()
        user_list_schema = google_user_list_schema()
        user_list_update_schema = google_user_list_update_schema()
        bidding_strategy_schema = google_bidding_strategy_schema()
        bidding_strategy_update_schema = google_bidding_strategy_update_schema()
        user_list_properties = user_list_schema["properties"]
        create_user_list_properties = {
            key: user_list_properties[key]
            for key in (
                "customer_id", "name", "description", "membership_life_span",
                "integration_code", "eligible_for_search", "upload_key_type",
                "data_source_type", "app_id",
            )
        }
        criterion_schema = google_campaign_criterion_schema()
        criterion_properties = criterion_schema["properties"]
        list_criterion_properties = {
            key: criterion_properties[key]
            for key in ("customer_id", "campaign_id", "limit")
        }
        get_criterion_properties = {
            key: criterion_properties[key]
            for key in ("customer_id", "campaign_id", "criterion_id")
        }
        create_criterion_properties = {
            key: criterion_properties[key]
            for key in ("customer_id", "campaign_id", "criteria")
        }
        update_criterion_properties = {
            key: criterion_properties[key]
            for key in ("customer_id", "campaign_id", "criterion_id", "updates")
        }
        delete_criterion_properties = {
            key: criterion_properties[key]
            for key in ("customer_id", "campaign_id", "criterion_id")
        }
        asset_schema = google_asset_schema()
        asset_create_schema = google_asset_create_schema()
        campaign_asset_schema = google_campaign_asset_schema()
        asset_group_asset_schema = google_asset_group_asset_schema()
        asset_group_schema = google_asset_group_schema()
        app_ad_group_schema = google_app_ad_group_schema()
        app_ad_schema = google_app_ad_schema()
        product_group_read_schema = google_product_group_read_schema()
        product_group_update_schema = google_product_group_update_schema()
        listing_filter_schema = google_asset_group_listing_group_filter_schema()
        listing_filter_update_schema = google_asset_group_listing_group_filter_update_schema()
        listing_filter_read_schema = google_asset_group_listing_group_filter_read_schema()
        product_group_read_properties = product_group_read_schema["properties"]
        experiment_schema = google_experiment_schema()
        experiment_update_schema = google_experiment_update_schema()
        feed_schema = google_feed_schema()
        conversion_goal_schema = google_conversion_goal_schema()
        search_ad_contract = google_ad_schema()
        search_ad_properties = {
            key: search_ad_contract["properties"][key]
            for key in (
                "ad_group_id", "name", "headlines", "descriptions", "final_url",
                "ad_type", "path1", "path2", "responsive_search_ad", "status",
            )
        }

        def _experiment_input(data: dict[str, Any]) -> dict[str, Any]:
            return {
                key: data[key]
                for key in (
                    "name", "description", "suffix", "type", "status", "start_date",
                    "end_date", "goals", "sync_enabled", "video_experiment_subtype",
                    "optimize_assets_experiment_subtype",
                )
                if key in data
            }

        tools = [
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_experiments",
                description="查询 Google Ads Campaign Experiment。",
                method_name="list_experiments", result_key="experiments",
                properties={
                    "customer_id": {"type": "string"},
                    "query": {"type": "string", "description": "可选 GAQL 查询"},
                    "limit": {"type": "integer"},
                },
                required=["customer_id"], action="list", resource_type="experiment",
                intent_types=["list_experiments"], traits=["read", "experiment"],
                argument_builder=lambda _ctx, data: ((), {
                    "query": data.get("query"), "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_experiment_arms",
                description="查询 Google Ads Experiment Arm。",
                method_name="list_experiment_arms", result_key="experiment_arms",
                properties={
                    "customer_id": {"type": "string"},
                    "query": {"type": "string", "description": "可选 GAQL 查询"},
                    "limit": {"type": "integer"},
                },
                required=["customer_id"], action="list", resource_type="experiment_arm",
                intent_types=["list_experiment_arms"], traits=["read", "experiment"],
                argument_builder=lambda _ctx, data: ((), {
                    "query": data.get("query"), "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_experiment",
                description="查询 Google Ads 单个 Experiment 详情。",
                method_name="get_experiment", result_key="experiment",
                properties=experiment_schema["properties"],
                required=["experiment_id"], action="get", resource_type="experiment",
                resource_id_field="experiment_id", intent_types=["get_experiment"],
                traits=["read", "experiment"],
                argument_builder=lambda _ctx, data: ((data["experiment_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_experiment",
                description="创建 Google Ads Experiment；默认仅生成 dry-run 计划。",
                method_name="create_experiment", result_key="experiment_id",
                properties=experiment_schema["properties"],
                required=["name", "type"], provider_required=["name", "type"],
                conditional_rules=experiment_schema["conditional_rules"],
                action="create", resource_type="experiment", resource_id_field="experiment_id",
                intent_types=["create_experiment"], traits=["write", "experiment"],
                write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((_experiment_input(data),), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_experiment",
                description="更新 Google Ads Experiment 可变字段；默认仅生成 dry-run 计划。",
                method_name="update_experiment", result_key="experiment_result",
                properties={
                    "experiment_id": experiment_schema["properties"]["experiment_id"],
                    "updates": experiment_update_schema,
                },
                required=["experiment_id", "updates"], provider_required=["updates"],
                action="update", resource_type="experiment", resource_id_field="experiment_id",
                intent_types=["update_experiment"], traits=["write", "experiment"],
                write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((data["experiment_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_experiment",
                description="删除 Google Ads Experiment；默认仅生成 dry-run 计划。",
                method_name="delete_experiment", result_key="experiment_result",
                properties={"experiment_id": experiment_schema["properties"]["experiment_id"]},
                required=["experiment_id"], action="delete", resource_type="experiment",
                resource_id_field="experiment_id", intent_types=["delete_experiment"],
                traits=["write", "experiment"], write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((data["experiment_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_campaign",
                description="删除 Google Ads Campaign；默认仅生成 dry-run 计划。",
                method_name="delete_campaign", result_key="campaign_result",
                properties={"campaign_id": {"type": "string"}},
                required=["campaign_id"], provider_required=["campaign_id"],
                action="delete", resource_type="campaign", resource_id_field="campaign_id",
                intent_types=["delete_campaign", "cross_channel_batch_delete"],
                intent_aliases=["删除 Google Ads campaign", "删除 Google campaign"],
                traits=["write", "campaign"], write=True,
                argument_builder=lambda _ctx, data: ((data["campaign_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_app_ad_group",
                description="创建 Google App Campaign Ad Group；live 仅在受控测试账号和确认后执行。",
                method_name="create_ad_group", result_key="ad_group_id",
                properties=app_ad_group_schema["properties"],
                required=app_ad_group_schema["required"],
                provider_required=app_ad_group_schema["provider_required"],
                action="create", resource_type="ad_group", parent_resource_type="campaign",
                resource_id_field="ad_group_id", parent_resource_id_field="campaign_id",
                intent_types=["create_app_ad_group", "create_campaign"],
                activation_rules=[{
                    "if": {
                        "campaign_type": {"aliases": ["advertising_channel_type"], "in": [
                            "MULTI_CHANNEL", "APP",
                        ]},
                        "advertising_channel_sub_type": {"in": [
                            "APP_CAMPAIGN", "APP_CAMPAIGN_FOR_ENGAGEMENT",
                        ]},
                    },
                }],
                traits=["write", "ad_group", "app"], write=True, live_support=True,
                readback_tool="google_get_ad_group",
                argument_builder=lambda _ctx, data: ((
                    data["campaign_id"], data["name"],
                ), {
                    "cpc_bid_micros": None,
                    "status": data.get("status"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_app_ad",
                description="创建 Google App Campaign AppAd 素材广告；live 仅在受控测试账号和确认后执行。",
                method_name="create_app_ad", result_key="app_ad_plan",
                properties=app_ad_schema["properties"],
                required=app_ad_schema["required"],
                provider_required=app_ad_schema["provider_required"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="ad_group_id",
                intent_types=["create_app_ad", "create_campaign"],
                activation_rules=[{
                    "if": {
                        "campaign_type": {"aliases": ["advertising_channel_type"], "in": [
                            "MULTI_CHANNEL", "APP",
                        ]},
                        "advertising_channel_sub_type": {"in": [
                            "APP_CAMPAIGN", "APP_CAMPAIGN_FOR_ENGAGEMENT",
                        ]},
                    },
                }],
                traits=["write", "ad", "app"], write=True, live_support=True,
                readback_tool="google_get_ad",
                argument_builder=lambda _ctx, data: ((
                    data["ad_group_id"], data["name"], data["headlines"], data["descriptions"],
                ), {
                    "images": data.get("images"),
                    "videos": data.get("videos"),
                    "html5_media_bundles": data.get("html5_media_bundles"),
                    "status": data.get("status"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_ad_group",
                description="删除 Google Ads Ad Group；默认仅生成 dry-run 计划。",
                method_name="delete_ad_group", result_key="ad_group_result",
                properties={"ad_group_id": {"type": "string"}},
                required=["ad_group_id"], provider_required=["ad_group_id"],
                action="delete", resource_type="ad_group", resource_id_field="ad_group_id",
                intent_types=["delete_ad_group"], traits=["write", "ad_group"], write=True,
                argument_builder=lambda _ctx, data: ((data["ad_group_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_ad",
                description="删除 Google Ads Ad；默认仅生成 dry-run 计划。",
                method_name="delete_ad", result_key="ad_result",
                properties={
                    "ad_group_id": {"type": "string"},
                    "ad_id": {"type": "string"},
                },
                required=["ad_group_id", "ad_id"],
                provider_required=["ad_group_id", "ad_id"],
                action="delete", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="ad_group_id",
                intent_types=["delete_ad"], traits=["write", "ad"], write=True,
                argument_builder=lambda _ctx, data: ((data["ad_group_id"], data["ad_id"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_assets", description="查询 Google Ads 客户级可复用 Asset 列表。",
                method_name="list_assets", result_key="assets",
                properties=asset_schema["properties"], required=["customer_id"],
                action="list", resource_type="asset", intent_types=["list_assets"],
                traits=["read", "asset"],
                argument_builder=lambda _ctx, data: ((data.get("customer_id"),), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_asset", description="查询 Google Ads 客户级 Asset 详情。",
                method_name="get_asset", result_key="asset",
                properties=asset_schema["properties"], required=["customer_id", "asset_id"],
                action="get", resource_type="asset", resource_id_field="asset_id",
                intent_types=["get_asset"], traits=["read", "asset"],
                argument_builder=lambda _ctx, data: ((data["asset_id"], data.get("customer_id")), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_asset",
                description=(
                    "创建 Google Ads 可复用 Asset（文本、图片、YouTube 视频或 HTML5 ZIP）；"
                    "默认仅生成 dry-run 计划。"
                ),
                method_name="create_asset", result_key="asset_id",
                properties=asset_create_schema["properties"],
                required=asset_create_schema["required"],
                provider_required=asset_create_schema["provider_required"],
                conditional_rules=asset_create_schema["conditional_rules"],
                action="create", resource_type="asset", resource_id_field="asset_id",
                intent_types=["create_asset"], traits=["write", "asset"], write=True,
                argument_builder=lambda _ctx, data: (({
                    key: data.get(key)
                    for key in (
                        "asset_type", "name", "text", "file_path", "mime_type",
                        "youtube_video_id", "youtube_video_title", "final_urls",
                        "final_mobile_urls", "tracking_url_template", "final_url_suffix",
                    )
                    if data.get(key) is not None
                },), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_asset",
                description=(
                    "移除 Google Ads 客户级可复用 Asset；Asset 仍被引用时由 Google Ads 拒绝；"
                    "默认仅生成 dry-run 计划。"
                ),
                method_name="delete_asset", result_key="asset_result",
                properties=asset_schema["properties"],
                required=["customer_id", "asset_id"],
                action="delete", resource_type="asset", resource_id_field="asset_id",
                intent_types=["delete_asset"], traits=["write", "asset"], write=True,
                argument_builder=lambda _ctx, data: ((data["asset_id"], data.get("customer_id")), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_campaign_assets",
                description="查询 Google Ads Campaign 已关联的 Asset 列表。",
                method_name="list_campaign_assets", result_key="campaign_assets",
                properties=campaign_asset_schema["properties"],
                required=["customer_id", "campaign_id"],
                action="list", resource_type="campaign_asset",
                parent_resource_type="campaign",
                parent_resource_id_field="campaign_id",
                intent_types=["list_campaign_assets"],
                traits=["read", "asset", "campaign_asset"],
                argument_builder=lambda _ctx, data: ((data["campaign_id"],), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_campaign_asset",
                description="将 Google Asset 关联到 Campaign；默认仅生成 dry-run 计划。",
                method_name="create_campaign_asset", result_key="campaign_asset_id",
                properties=campaign_asset_schema["properties"],
                required=["customer_id", "campaign_id", "asset_id", "field_type"],
                provider_required=["campaign_id", "asset_id", "field_type"],
                action="create", resource_type="campaign_asset",
                parent_resource_type="campaign",
                resource_id_field="campaign_asset_id",
                parent_resource_id_field="campaign_id",
                intent_types=["create_campaign_asset"],
                traits=["write", "asset", "campaign_asset"], write=True,
                argument_builder=lambda _ctx, data: ((
                    data["campaign_id"], data["asset_id"], data["field_type"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_campaign_asset",
                description="移除 Campaign 与 Google Asset 的关联；默认仅生成 dry-run 计划。",
                method_name="delete_campaign_asset", result_key="campaign_asset_result",
                properties=campaign_asset_schema["properties"],
                required=["customer_id", "campaign_id", "asset_id", "field_type"],
                provider_required=["campaign_id", "asset_id", "field_type"],
                action="delete", resource_type="campaign_asset",
                parent_resource_type="campaign",
                resource_id_field="campaign_asset_id",
                parent_resource_id_field="campaign_id",
                intent_types=["delete_campaign_asset"],
                traits=["write", "asset", "campaign_asset"], write=True,
                argument_builder=lambda _ctx, data: ((
                    data["campaign_id"], data["asset_id"], data["field_type"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_asset_group_assets",
                description="查询 Google PMax Asset Group 已关联的 Asset 列表。",
                method_name="list_asset_group_assets", result_key="asset_group_assets",
                properties=asset_group_asset_schema["properties"],
                required=["customer_id", "asset_group_id"],
                action="list", resource_type="asset_group_asset",
                parent_resource_type="asset_group",
                resource_id_field="asset_group_asset_id",
                parent_resource_id_field="asset_group_id",
                intent_types=["list_asset_group_assets"],
                traits=["read", "asset", "asset_group_asset", "pmax"],
                argument_builder=lambda _ctx, data: ((data["asset_group_id"],), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_asset_group_asset",
                description="将 Google Asset 关联到 PMax Asset Group；默认仅生成 dry-run 计划。",
                method_name="create_asset_group_asset", result_key="asset_group_asset_id",
                properties=asset_group_asset_schema["properties"],
                required=["customer_id", "asset_group_id", "asset_id", "field_type"],
                provider_required=["asset_group_id", "asset_id", "field_type"],
                action="create", resource_type="asset_group_asset",
                parent_resource_type="asset_group",
                resource_id_field="asset_group_asset_id",
                parent_resource_id_field="asset_group_id",
                intent_types=["create_asset_group_asset"],
                traits=["write", "asset", "asset_group_asset", "pmax"], write=True,
                argument_builder=lambda _ctx, data: ((
                    data["asset_group_id"], data["asset_id"], data["field_type"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_asset_group_asset",
                description="移除 PMax Asset Group 与 Google Asset 的关联；默认仅生成 dry-run 计划。",
                method_name="delete_asset_group_asset", result_key="asset_group_asset_result",
                properties=asset_group_asset_schema["properties"],
                required=["customer_id", "asset_group_id", "asset_id", "field_type"],
                provider_required=["asset_group_id", "asset_id", "field_type"],
                action="delete", resource_type="asset_group_asset",
                parent_resource_type="asset_group",
                resource_id_field="asset_group_asset_id",
                parent_resource_id_field="asset_group_id",
                intent_types=["delete_asset_group_asset"],
                traits=["write", "asset", "asset_group_asset", "pmax"], write=True,
                argument_builder=lambda _ctx, data: ((
                    data["asset_group_id"], data["asset_id"], data["field_type"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_campaign_budgets", description="查询 Google Ads CampaignBudget 列表。",
                method_name="list_campaign_budgets", result_key="budgets",
                properties=budget_schema["properties"], required=["customer_id"],
                action="list", resource_type="campaign_budget", intent_types=["list_campaign_budgets"],
                traits=["read", "campaign_budget"],
                argument_builder=lambda _ctx, data: ((), {"page_size": data.get("limit", 100)}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_campaign_budget", description="查询 Google Ads CampaignBudget 详情。",
                method_name="get_campaign_budget", result_key="budget",
                properties=budget_schema["properties"], required=["budget_id"],
                action="get", resource_type="campaign_budget", resource_id_field="budget_id",
                intent_types=["get_campaign_budget"], traits=["read", "campaign_budget"],
                argument_builder=lambda _ctx, data: ((data["budget_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_campaign_budget", description="创建 Google Ads CampaignBudget；默认仅生成 dry-run 计划。",
                method_name="create_campaign_budget", result_key="budget_id",
                properties=budget_schema["properties"], required=["customer_id", "name", "daily_budget"],
                provider_required=["name", "daily_budget"],
                action="create", resource_type="campaign_budget", resource_id_field="budget_id",
                intent_types=["create_campaign_budget"], traits=["write", "campaign_budget"], write=True,
                argument_builder=lambda _ctx, data: ((data["name"], data["daily_budget"]), {
                    "delivery_method": data.get("delivery_method", "STANDARD"),
                    "explicitly_shared": data.get("explicitly_shared", False),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_campaign_budget", description="更新 Google Ads CampaignBudget；默认仅生成 dry-run 计划。",
                method_name="update_campaign_budget", result_key="budget_result",
                properties={**budget_schema["properties"], "updates": google_campaign_budget_update_schema()},
                required=["budget_id", "updates"], action="update", resource_type="campaign_budget",
                resource_id_field="budget_id", intent_types=["update_campaign_budget"],
                traits=["write", "campaign_budget"], write=True,
                argument_builder=lambda _ctx, data: ((data["budget_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_campaign_budget", description="删除未被引用的 Google Ads CampaignBudget；默认仅生成 dry-run 计划。",
                method_name="delete_campaign_budget", result_key="budget_result",
                properties=budget_schema["properties"], required=["budget_id"], action="delete",
                resource_type="campaign_budget", resource_id_field="budget_id",
                intent_types=["delete_campaign_budget"], traits=["write", "campaign_budget"], write=True,
                argument_builder=lambda _ctx, data: ((data["budget_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_conversion_action",
                description="创建 Google Ads Conversion Action；默认仅生成 dry-run 计划。",
                method_name="create_conversion_action", result_key="conversion_action_id",
                properties=conversion_action_schema["properties"],
                required=conversion_action_schema["required"],
                provider_required=conversion_action_schema["provider_required"],
                action="create", resource_type="conversion_action",
                resource_id_field="conversion_action_id",
                intent_types=["create_conversion_action"],
                traits=["write", "conversion"], write=True, live_support=False,
                argument_builder=lambda _ctx, data: (({
                    key: value for key, value in data.items() if key != "customer_id"
                },), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_conversion_action",
                description="更新 Google Ads Conversion Action；默认仅生成 dry-run 计划。",
                method_name="update_conversion_action", result_key="conversion_action_result",
                properties={
                    "customer_id": conversion_action_schema["properties"]["customer_id"],
                    "conversion_action_id": {"type": "string", "description": "Conversion Action ID"},
                    "updates": conversion_action_update_schema,
                },
                required=["customer_id", "conversion_action_id", "updates"],
                action="update", resource_type="conversion_action",
                resource_id_field="conversion_action_id",
                intent_types=["update_conversion_action"],
                traits=["write", "conversion"], write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((
                    data["conversion_action_id"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_conversion_action",
                description="删除 Google Ads Conversion Action；默认仅生成 dry-run 计划。",
                method_name="delete_conversion_action", result_key="conversion_action_result",
                properties={
                    "customer_id": conversion_action_schema["properties"]["customer_id"],
                    "conversion_action_id": {"type": "string", "description": "Conversion Action ID"},
                },
                required=["customer_id", "conversion_action_id"],
                action="delete", resource_type="conversion_action",
                resource_id_field="conversion_action_id",
                intent_types=["delete_conversion_action"],
                traits=["write", "conversion"], write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((data["conversion_action_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_campaign_criteria", description="查询 Google Ads CampaignCriterion（地域、语言、设备、受众和人口属性定向）。",
                method_name="list_campaign_criteria", result_key="criteria",
                properties=list_criterion_properties, required=[],
                action="list", resource_type="campaign_criterion",
                intent_types=["list_campaign_criteria"], traits=["read", "campaign_criterion", "targeting"],
                argument_builder=lambda _ctx, data: ((data.get("campaign_id"),), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_campaign_criterion", description="查询 Google Ads 单个 CampaignCriterion 详情。",
                method_name="get_campaign_criterion", result_key="criterion",
                properties=get_criterion_properties, required=["campaign_id", "criterion_id"],
                action="get", resource_type="campaign_criterion", resource_id_field="criterion_id",
                intent_types=["get_campaign_criterion"], traits=["read", "campaign_criterion", "targeting"],
                argument_builder=lambda _ctx, data: ((data["campaign_id"], data["criterion_id"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_campaign_criteria", description="批量创建 Google Ads CampaignCriterion；默认仅生成 dry-run 计划。",
                method_name="create_campaign_criteria", result_key="criterion_ids",
                properties=create_criterion_properties, required=["campaign_id", "criteria"],
                provider_required=["criteria"], action="create", resource_type="campaign_criterion",
                parent_resource_type="campaign", resource_id_field="criterion_ids",
                parent_resource_id_field="campaign_id", intent_types=["create_campaign_criteria"],
                traits=["write", "campaign_criterion", "targeting"], write=True,
                argument_builder=lambda _ctx, data: ((data["campaign_id"], data["criteria"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_campaign_criterion", description="更新 Google Ads CampaignCriterion 的状态、排除标记或出价系数；默认仅生成 dry-run 计划。",
                method_name="update_campaign_criterion", result_key="criterion_result",
                properties=update_criterion_properties,
                required=["campaign_id", "criterion_id", "updates"], action="update",
                resource_type="campaign_criterion", resource_id_field="criterion_id",
                intent_types=["update_campaign_criterion"], traits=["write", "campaign_criterion", "targeting"],
                write=True,
                argument_builder=lambda _ctx, data: ((data["campaign_id"], data["criterion_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_campaign_criterion", description="删除 Google Ads CampaignCriterion；默认仅生成 dry-run 计划。",
                method_name="delete_campaign_criterion", result_key="criterion_result",
                properties=delete_criterion_properties, required=["campaign_id", "criterion_id"],
                action="delete", resource_type="campaign_criterion", resource_id_field="criterion_id",
                intent_types=["delete_campaign_criterion"], traits=["write", "campaign_criterion", "targeting"],
                write=True,
                argument_builder=lambda _ctx, data: ((data["campaign_id"], data["criterion_id"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_conversion_actions", description="查询 Google Ads 转化动作列表。",
                method_name="list_conversion_actions", result_key="conversion_actions",
                properties={"customer_id": {"type": "string"}, "limit": {"type": "integer"}},
                required=["customer_id"], action="list", resource_type="conversion_action",
                intent_types=["list_conversion_actions"], traits=["read", "conversion"],
                argument_builder=lambda _ctx, data: ((), {"page_size": data.get("limit", 100)}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_conversion_action", description="查询 Google Ads 转化动作详情。",
                method_name="get_conversion_action", result_key="conversion_action",
                properties={
                    "customer_id": {"type": "string"},
                    "conversion_action_id": {"type": "string"},
                },
                required=["customer_id", "conversion_action_id"], action="get",
                resource_type="conversion_action", resource_id_field="conversion_action_id",
                intent_types=["get_conversion_action"], traits=["read", "conversion"],
                argument_builder=lambda _ctx, data: ((data["conversion_action_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_bidding_strategies", description="查询 Google Ads 出价策略列表。",
                method_name="list_bidding_strategies", result_key="bidding_strategies",
                properties={"customer_id": {"type": "string"}, "limit": {"type": "integer"}},
                required=["customer_id"], action="list", resource_type="bidding_strategy",
                intent_types=["list_bidding_strategies"], traits=["read", "bidding"],
                argument_builder=lambda _ctx, data: ((), {"page_size": data.get("limit", 100)}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_bidding_strategy", description="查询 Google Ads 出价策略详情。",
                method_name="get_bidding_strategy", result_key="bidding_strategy",
                properties={
                    "customer_id": {"type": "string"},
                    "bidding_strategy_id": {"type": "string"},
                },
                required=["customer_id", "bidding_strategy_id"], action="get",
                resource_type="bidding_strategy", resource_id_field="bidding_strategy_id",
                intent_types=["get_bidding_strategy"], traits=["read", "bidding"],
                argument_builder=lambda _ctx, data: ((data["bidding_strategy_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_bidding_strategy",
                description="创建 Google Ads Portfolio BiddingStrategy；默认仅生成 dry-run 计划。",
                method_name="create_bidding_strategy", result_key="bidding_strategy_id",
                properties={
                    key: bidding_strategy_schema["properties"][key]
                    for key in (
                        "customer_id", "name", "strategy_type", "target_cpa_micros",
                        "target_roas", "target_impression_share",
                        "target_impression_share_location", "cpc_bid_ceiling_micros",
                        "cpc_bid_floor_micros", "enhanced_cpc_enabled",
                    )
                },
                required=bidding_strategy_schema["required"],
                provider_required=bidding_strategy_schema["provider_required"],
                conditional_rules=bidding_strategy_schema["conditional_rules"],
                action="create", resource_type="bidding_strategy",
                resource_id_field="bidding_strategy_id",
                intent_types=["create_bidding_strategy"], traits=["write", "bidding"], write=True,
                argument_builder=lambda _ctx, data: (({
                    key: data.get(key)
                    for key in (
                        "name", "strategy_type", "target_cpa_micros", "target_roas",
                        "target_impression_share", "target_impression_share_location",
                        "cpc_bid_ceiling_micros", "cpc_bid_floor_micros",
                        "enhanced_cpc_enabled",
                    )
                    if data.get(key) is not None
                },), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_bidding_strategy",
                description="更新 Google Ads Portfolio BiddingStrategy；默认仅生成 dry-run 计划。",
                method_name="update_bidding_strategy", result_key="bidding_strategy_result",
                properties={
                    "customer_id": bidding_strategy_schema["properties"]["customer_id"],
                    "bidding_strategy_id": bidding_strategy_schema["properties"]["bidding_strategy_id"],
                    "updates": bidding_strategy_update_schema,
                },
                required=["customer_id", "bidding_strategy_id", "updates"],
                action="update", resource_type="bidding_strategy",
                resource_id_field="bidding_strategy_id",
                intent_types=["update_bidding_strategy"], traits=["write", "bidding"], write=True,
                argument_builder=lambda _ctx, data: ((data["bidding_strategy_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_bidding_strategy",
                description="删除 Google Ads Portfolio BiddingStrategy；默认仅生成 dry-run 计划。",
                method_name="delete_bidding_strategy", result_key="bidding_strategy_result",
                properties={
                    "customer_id": bidding_strategy_schema["properties"]["customer_id"],
                    "bidding_strategy_id": bidding_strategy_schema["properties"]["bidding_strategy_id"],
                },
                required=["customer_id", "bidding_strategy_id"],
                action="delete", resource_type="bidding_strategy",
                resource_id_field="bidding_strategy_id",
                intent_types=["delete_bidding_strategy"], traits=["write", "bidding"], write=True,
                argument_builder=lambda _ctx, data: ((data["bidding_strategy_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_user_lists", description="查询 Google Ads 第一方 User List 列表。",
                method_name="list_user_lists", result_key="user_lists",
                properties={"customer_id": {"type": "string"}, "limit": {"type": "integer"}},
                required=["customer_id"], action="list", resource_type="user_list",
                intent_types=["list_user_lists"], traits=["read", "audience"],
                argument_builder=lambda _ctx, data: ((), {"page_size": data.get("limit", 100)}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_user_list", description="查询 Google Ads 第一方 User List 详情。",
                method_name="get_user_list", result_key="user_list",
                properties={
                    "customer_id": {"type": "string"},
                    "user_list_id": {"type": "string"},
                },
                required=["customer_id", "user_list_id"], action="get",
                resource_type="user_list", resource_id_field="user_list_id",
                intent_types=["get_user_list"], traits=["read", "audience"],
                argument_builder=lambda _ctx, data: ((data["user_list_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_user_list",
                description="创建 Google Ads Customer Match User List；默认仅生成 dry-run 计划。",
                method_name="create_user_list", result_key="user_list_id",
                properties=create_user_list_properties,
                required=user_list_schema["required"],
                provider_required=user_list_schema["provider_required"],
                conditional_rules=user_list_schema["conditional_rules"],
                action="create", resource_type="user_list", resource_id_field="user_list_id",
                intent_types=["create_user_list"], traits=["write", "audience"], write=True,
                argument_builder=lambda _ctx, data: (({
                    key: data.get(key)
                    for key in (
                        "name", "description", "membership_life_span",
                        "integration_code", "eligible_for_search", "upload_key_type",
                        "data_source_type", "app_id",
                    )
                    if data.get(key) is not None
                },), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_user_list",
                description="更新 Google Ads User List 的可变字段；默认仅生成 dry-run 计划。",
                method_name="update_user_list", result_key="user_list_result",
                properties={
                    "customer_id": user_list_properties["customer_id"],
                    "user_list_id": user_list_properties["user_list_id"],
                    "updates": user_list_update_schema,
                },
                required=["customer_id", "user_list_id", "updates"],
                action="update", resource_type="user_list", resource_id_field="user_list_id",
                intent_types=["update_user_list"], traits=["write", "audience"], write=True,
                argument_builder=lambda _ctx, data: ((data["user_list_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_user_list",
                description="删除 Google Ads User List；默认仅生成 dry-run 计划。",
                method_name="delete_user_list", result_key="user_list_result",
                properties={
                    "customer_id": user_list_properties["customer_id"],
                    "user_list_id": user_list_properties["user_list_id"],
                },
                required=["customer_id", "user_list_id"],
                action="delete", resource_type="user_list", resource_id_field="user_list_id",
                intent_types=["delete_user_list"], traits=["write", "audience"], write=True,
                argument_builder=lambda _ctx, data: ((data["user_list_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_upload_user_list_data",
                description=(
                    "向 Google Ads Customer Match User List 上传仅含 SHA-256 邮箱/手机号的本地 CSV/TSV；"
                    "默认仅生成 dry-run 计划。"
                ),
                method_name="upload_user_list_data", result_key="upload_result",
                properties={
                    "customer_id": user_list_properties["customer_id"],
                    "user_list_id": user_list_properties["user_list_id"],
                    "file_path": user_list_properties["file_path"],
                },
                required=["customer_id", "user_list_id", "file_path"],
                action="upload", resource_type="user_list", resource_id_field="user_list_id",
                intent_types=["upload_user_list_data"], traits=["write", "audience", "data_upload"], write=True,
                argument_builder=lambda _ctx, data: ((data["user_list_id"], data["file_path"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_customer_clients",
                description="查询 Google Ads 经理账户下可访问的客户账户。",
                method_name="list_customer_clients", result_key="customer_clients",
                properties={
                    "customer_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                required=["customer_id"], action="list", resource_type="customer_client",
                intent_types=["list_customer_clients"], traits=["read", "account"],
                argument_builder=lambda _ctx, data: ((), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_search_ad", description="创建 Google Responsive Search Ad；默认仅生成 dry-run 计划。",
                method_name="create_search_ad", result_key="ad_id",
                properties=search_ad_properties,
                # Search Ad's existing client method identifies the ad by its
                # parent ad group and does not accept/require the generic
                # management-contract ``name`` field.  Keep that distinction
                # explicit while reusing the provider-owned field schemas.
                required=["ad_group_id", "headlines", "descriptions", "final_url"],
                provider_required=["headlines", "descriptions", "final_url"],
                conditional_rules=search_ad_contract["conditional_rules"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="ad_group_id",
                intent_types=["create_search_ad"], traits=["write", "ad"], write=True,
                live_support=True, readback_tool="google_get_ad",
                argument_builder=lambda _ctx, data: ((data["ad_group_id"], data["headlines"], data["descriptions"], data["final_url"]), {
                    "ad_type": data.get("ad_type"), "path1": data.get("path1"), "path2": data.get("path2"),
                    "responsive_search_ad": data.get("responsive_search_ad"), "status": data.get("status"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_keywords", description="批量创建 Google Ad Group 关键词/否定关键词；默认仅生成 dry-run 计划。",
                method_name="create_keywords", result_key="keyword_ids",
                properties=google_keyword_schema()["properties"],
                required=google_keyword_schema()["required"],
                provider_required=google_keyword_schema()["provider_required"],
                action="create", resource_type="keyword", parent_resource_type="ad_group",
                resource_id_field="keyword_ids", parent_resource_id_field="ad_group_id",
                intent_types=["create_keywords"],
                intent_aliases=["创建 Google 关键词", "添加 Google 关键词"],
                traits=["write", "keyword"], write=True,
                argument_builder=lambda _ctx, data: ((data["ad_group_id"], data["keywords"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_keyword",
                description="更新 Google Ad Group 关键词状态或 CPC 出价；默认仅生成 dry-run 计划。",
                method_name="update_keyword", result_key="keyword_id",
                properties={
                    "ad_group_id": {"type": "string"},
                    "criterion_id": {"type": "string"},
                    "updates": google_keyword_update_schema(),
                },
                required=["ad_group_id", "criterion_id", "updates"],
                provider_required=["updates"], action="update", resource_type="keyword",
                parent_resource_type="ad_group", resource_id_field="keyword_id",
                parent_resource_id_field="ad_group_id",
                intent_types=["update_keyword"], traits=["write", "keyword"], write=True,
                argument_builder=lambda _ctx, data: ((
                    data["ad_group_id"], data["criterion_id"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_keyword",
                description="删除 Google Ad Group 关键词；默认仅生成 dry-run 计划。",
                method_name="delete_keyword", result_key="keyword_id",
                properties={
                    "ad_group_id": {"type": "string"},
                    "criterion_id": {"type": "string"},
                },
                required=["ad_group_id", "criterion_id"], action="delete",
                resource_type="keyword", parent_resource_type="ad_group",
                resource_id_field="keyword_id", parent_resource_id_field="ad_group_id",
                intent_types=["delete_keyword"], traits=["write", "keyword"], write=True,
                argument_builder=lambda _ctx, data: ((
                    data["ad_group_id"], data["criterion_id"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_pmax_asset_group", description="创建 Google PMax Asset Group；live 仅在受控测试账号和确认后执行。",
                method_name="create_pmax_asset_group", result_key="asset_group_plan",
                properties=asset_group_schema["properties"], required=asset_group_schema["required"],
                provider_required=asset_group_schema["provider_required"], action="create",
                resource_type="asset_group", parent_resource_type="campaign",
                resource_id_field="asset_group_id", parent_resource_id_field="campaign_id",
                intent_types=["create_pmax_asset_group", "create_campaign"],
                activation_rules=[{
                    "field": "campaign_type", "aliases": ["advertising_channel_type"],
                    "in": ["PERFORMANCE_MAX", "MAX"],
                }],
                traits=["write", "asset_group"], write=True, live_support=True,
                readback_tool="google_get_asset_group",
                argument_builder=lambda _ctx, data: ((data["campaign_id"], data["name"], data["headlines"]), {
                    "descriptions": data["descriptions"], "images": data.get("images"),
                    "square_marketing_images": data.get("square_marketing_images"),
                    "videos": data.get("videos"), "asset_group_type": data["asset_group_type"],
                    "final_urls": data["final_urls"], "long_headlines": data["long_headlines"],
                    "logos": data.get("logos"), "business_names": data.get("business_names"),
                    "final_mobile_urls": data.get("final_mobile_urls"),
                    "status": data.get("status"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_product_group",
                description="创建 Google Shopping Product Group/Listing Group；live 仅在受控测试账号和确认后执行。",
                method_name="create_product_group", result_key="product_group_id",
                properties=google_product_group_schema()["properties"],
                required=google_product_group_schema()["required"],
                provider_required=google_product_group_schema()["provider_required"],
                conditional_rules=google_product_group_schema()["conditional_rules"],
                action="create", resource_type="product_group", parent_resource_type="ad_group",
                resource_id_field="product_group_id", parent_resource_id_field="ad_group_id",
                intent_types=["create_product_group", "create_campaign"],
                activation_rules=[{
                    "field": "campaign_type", "aliases": ["advertising_channel_type"],
                    "in": ["SHOPPING"],
                }],
                traits=["write", "product_group", "shopping"], write=True,
                live_support=True, readback_tool="google_get_product_group",
                argument_builder=lambda _ctx, data: ((data["ad_group_id"], data["product_group_type"]), {
                    "value": data.get("value"),
                    "partition_type": data.get("partition_type", "UNIT"),
                    "parent_criterion_id": data.get("parent_criterion_id"),
                    "cpc_bid_micros": data.get("cpc_bid_micros"),
                    "bidding_category_level": data.get("bidding_category_level", "LEVEL1"),
                    "status": data.get("status", "PAUSED"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_product_groups",
                description="查询 Google Shopping Ad Group 下的 Product Group/Listing Group 列表。",
                method_name="list_product_groups", result_key="product_groups",
                properties=product_group_read_properties,
                required=["ad_group_id"], action="list", resource_type="product_group",
                parent_resource_type="ad_group", parent_resource_id_field="ad_group_id",
                intent_types=["list_product_groups"], traits=["read", "product_group", "shopping"],
                argument_builder=lambda _ctx, data: ((data["ad_group_id"],), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_product_group",
                description="查询 Google Shopping 单个 Product Group/Listing Group 详情。",
                method_name="get_product_group", result_key="product_group",
                properties=product_group_read_properties,
                required=["ad_group_id", "product_group_id"], action="get",
                resource_type="product_group", parent_resource_type="ad_group",
                resource_id_field="product_group_id", parent_resource_id_field="ad_group_id",
                intent_types=["get_product_group"], traits=["read", "product_group", "shopping"],
                argument_builder=lambda _ctx, data: ((
                    data["ad_group_id"], data["product_group_id"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_product_group",
                description="更新 Google Shopping Product Group 状态或 CPC 出价；默认仅生成 dry-run 计划。",
                method_name="update_product_group", result_key="product_group_result",
                properties={
                    **product_group_read_properties,
                    "updates": product_group_update_schema,
                },
                required=["ad_group_id", "product_group_id", "updates"],
                provider_required=["updates"], action="update", resource_type="product_group",
                parent_resource_type="ad_group", resource_id_field="product_group_id",
                parent_resource_id_field="ad_group_id", intent_types=["update_product_group"],
                traits=["write", "product_group", "shopping"], write=True,
                live_support=True, readback_tool="google_get_product_group",
                argument_builder=lambda _ctx, data: ((
                    data["ad_group_id"], data["product_group_id"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_product_group",
                description="删除 Google Shopping Product Group/Listing Group；默认仅生成 dry-run 计划。",
                method_name="delete_product_group", result_key="product_group_result",
                properties=product_group_read_properties,
                required=["ad_group_id", "product_group_id"], action="delete",
                resource_type="product_group", parent_resource_type="ad_group",
                resource_id_field="product_group_id", parent_resource_id_field="ad_group_id",
                intent_types=["delete_product_group"], traits=["write", "product_group", "shopping"],
                write=True,
                argument_builder=lambda _ctx, data: ((
                    data["ad_group_id"], data["product_group_id"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_asset_group_listing_group_filters",
                description="查询 Google PMax Asset Group 下的 Listing Group Filter 树。",
                method_name="list_asset_group_listing_group_filters",
                result_key="listing_group_filters",
                properties=listing_filter_read_schema["properties"],
                required=["asset_group_id"], action="list",
                resource_type="listing_group_filter",
                parent_resource_type="asset_group",
                parent_resource_id_field="asset_group_id",
                intent_types=["list_asset_group_listing_group_filters"],
                traits=["read", "listing_group_filter", "pmax"],
                argument_builder=lambda _ctx, data: ((data["asset_group_id"],), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_asset_group_listing_group_filter",
                description="查询 Google PMax 单个 Listing Group Filter 节点。",
                method_name="get_asset_group_listing_group_filter",
                result_key="listing_group_filter",
                properties=listing_filter_read_schema["properties"],
                required=["asset_group_id", "listing_group_filter_id"],
                action="get", resource_type="listing_group_filter",
                parent_resource_type="asset_group",
                resource_id_field="listing_group_filter_id",
                parent_resource_id_field="asset_group_id",
                intent_types=["get_asset_group_listing_group_filter"],
                traits=["read", "listing_group_filter", "pmax"],
                argument_builder=lambda _ctx, data: ((
                    data["asset_group_id"], data["listing_group_filter_id"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_asset_group_listing_group_filter",
                description="创建 Google PMax Listing Group Filter；根节点或商品/网页/Retail 子节点，默认仅生成 dry-run 计划。",
                method_name="create_asset_group_listing_group_filter",
                result_key="listing_group_filter_id",
                properties=listing_filter_schema["properties"],
                required=listing_filter_schema["required"],
                provider_required=listing_filter_schema["provider_required"],
                conditional_rules=listing_filter_schema["conditional_rules"],
                action="create", resource_type="listing_group_filter",
                parent_resource_type="asset_group",
                resource_id_field="listing_group_filter_id",
                parent_resource_id_field="asset_group_id",
                intent_types=["create_asset_group_listing_group_filter", "create_campaign"],
                activation_rules=[{
                    "field": "campaign_type", "aliases": ["advertising_channel_type"],
                    "in": ["PERFORMANCE_MAX", "MAX"],
                }],
                traits=["write", "listing_group_filter", "pmax"], write=True,
                live_support=True,
                readback_tool="google_get_asset_group_listing_group_filter",
                argument_builder=lambda _ctx, data: ((data["asset_group_id"],), {
                    "filter_type": data.get("filter_type", "SUBDIVISION"),
                    "listing_source": data.get("listing_source", "SHOPPING"),
                    "product_dimension": data.get("product_dimension"),
                    "value": data.get("value"),
                    "dimension_level": data.get("dimension_level", "LEVEL1"),
                    "custom_attribute_index": data.get("custom_attribute_index", "INDEX0"),
                    "parent_filter_id": data.get("parent_filter_id"),
                    "webpage_conditions": data.get("webpage_conditions"),
                    "retail_filter_shared_set": data.get("retail_filter_shared_set"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_asset_group_listing_group_filter",
                description="更新 Google PMax Listing Group Filter 的 case value；默认仅生成 dry-run 计划。",
                method_name="update_asset_group_listing_group_filter",
                result_key="listing_group_filter_result",
                properties={
                    **listing_filter_read_schema["properties"],
                    "updates": listing_filter_update_schema,
                },
                required=["asset_group_id", "listing_group_filter_id", "updates"],
                provider_required=["updates"], action="update",
                resource_type="listing_group_filter",
                parent_resource_type="asset_group",
                resource_id_field="listing_group_filter_id",
                parent_resource_id_field="asset_group_id",
                intent_types=["update_asset_group_listing_group_filter"],
                traits=["write", "listing_group_filter", "pmax"], write=True,
                live_support=True,
                readback_tool="google_get_asset_group_listing_group_filter",
                argument_builder=lambda _ctx, data: ((
                    data["asset_group_id"], data["listing_group_filter_id"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_asset_group_listing_group_filter",
                description="删除 Google PMax Listing Group Filter 节点；需先删除其子节点，默认仅生成 dry-run 计划。",
                method_name="delete_asset_group_listing_group_filter",
                result_key="listing_group_filter_result",
                properties=listing_filter_read_schema["properties"],
                required=["asset_group_id", "listing_group_filter_id"],
                action="delete", resource_type="listing_group_filter",
                parent_resource_type="asset_group",
                resource_id_field="listing_group_filter_id",
                parent_resource_id_field="asset_group_id",
                intent_types=["delete_asset_group_listing_group_filter"],
                traits=["write", "listing_group_filter", "pmax"], write=True,
                live_support=True,
                readback_tool="google_get_asset_group_listing_group_filter",
                argument_builder=lambda _ctx, data: ((
                    data["asset_group_id"], data["listing_group_filter_id"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_responsive_display_ad",
                description="创建 Google Responsive Display Ad；默认仅生成 dry-run 计划。",
                method_name="create_responsive_display_ad", result_key="ad_id",
                properties=google_responsive_display_ad_schema()["properties"],
                required=google_responsive_display_ad_schema()["required"],
                provider_required=google_responsive_display_ad_schema()["provider_required"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="ad_group_id",
                intent_types=["create_responsive_display_ad", "create_campaign"],
                activation_rules=[{
                    "field": "campaign_type", "aliases": ["advertising_channel_type"],
                    "in": ["DISPLAY"],
                }],
                traits=["write", "ad", "display"], write=True, live_support=True,
                readback_tool="google_get_ad", provider_api_version="v24",
                required_permissions=["ads.plan"],
                argument_builder=lambda _ctx, data: ((data["ad_group_id"], data["name"], data["final_url"]), {
                    "headlines": data["headlines"], "long_headline": data["long_headline"],
                    "descriptions": data["descriptions"], "business_name": data["business_name"],
                    "marketing_images": data.get("marketing_images"),
                    "square_marketing_images": data.get("square_marketing_images"),
                    "logos": data.get("logos"), "landscape_logos": data.get("landscape_logos"),
                    "videos": data.get("videos"), "call_to_action_text": data.get("call_to_action_text"),
                    "main_color": data.get("main_color"), "accent_color": data.get("accent_color"),
                    "allow_flexible_color": data.get("allow_flexible_color"),
                    "ad_type": data.get("ad_type"), "status": data.get("status"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_video_ad",
                description="创建 Google Video Ad（可跳过、不可跳过、Bumper 或 Outstream）；默认仅生成 dry-run 计划。",
                method_name="create_video_ad", result_key="ad_id",
                properties=google_video_ad_schema()["properties"],
                required=google_video_ad_schema()["required"],
                provider_required=google_video_ad_schema()["provider_required"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="ad_group_id",
                intent_types=["create_video_ad", "create_campaign"],
                activation_rules=[{
                    "field": "campaign_type", "aliases": ["advertising_channel_type"],
                    "in": ["VIDEO"],
                }],
                traits=["write", "ad", "video"], write=True, live_support=True,
                readback_tool="google_get_ad", provider_api_version="v24",
                required_permissions=["ads.plan"],
                argument_builder=lambda _ctx, data: ((
                    data["ad_group_id"], data["name"], data["video_ad_format"],
                    data["video_id"], data["final_url"],
                ), {
                    "display_url": data.get("display_url"),
                    "action_button_label": data.get("action_button_label"),
                    "action_headline": data.get("action_headline"),
                    "companion_banner": data.get("companion_banner"),
                    "ad_type": data.get("ad_type"), "status": data.get("status"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_adgroup_report", description="查询 Google Ads Ad Group 级报表。",
                method_name="get_adgroup_report", result_key="report",
                properties={
                    "campaign_id": {"type": "string"},
                    "adgroup_ids": {"type": "array", "items": {"type": "string"}},
                    "date_from": {"type": "string"}, "date_to": {"type": "string"},
                }, required=["campaign_id"], action="report", resource_type="ad_group",
                # ``download_report`` is the provider-neutral/account-level
                # report intent. A child-level report must be selected by its
                # explicit Tool-owned intent so a generic report request does
                # not stop on the missing parent campaign_id.
                intent_types=["get_adgroup_report"], traits=["read", "report", "ad_group"],
                argument_builder=lambda _ctx, data: ((data["campaign_id"],), {
                    "adgroup_ids": data.get("adgroup_ids"), "date_from": data.get("date_from", "LAST_30_DAYS"),
                    "date_to": data.get("date_to", "TODAY"),
                }),
            ),
        ]
        for method_name, intent in (("pause_campaign", "pause_campaign"), ("resume_campaign", "resume_campaign")):
            tools.append(method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name=f"google_{method_name}", description=f"调用 Google Ads {method_name} 管理接口；默认仅生成 dry-run 计划。",
                method_name=method_name, result_key="campaign_result",
                properties={"campaign_id": {"type": "string"}}, required=["campaign_id"],
                action=method_name.split("_", 1)[0], resource_type="campaign",
                resource_id_field="campaign_id", intent_types=[f"provider_{intent}"], traits=["write", "campaign"], write=True,
                argument_builder=lambda _ctx, data: ((data["campaign_id"],), {}),
            ))

        # Experiment lifecycle RPCs are separate from normal status updates;
        # publishing them as explicit Tools prevents the Agent from treating
        # schedule/end/graduate/promote as Campaign mutations.
        for method_name, intent, description in (
            ("schedule_experiment", "schedule_experiment", "排期并启动 Google Ads Experiment"),
            ("end_experiment", "end_experiment", "结束 Google Ads Experiment"),
            ("graduate_experiment", "graduate_experiment", "将 Google Ads Experiment 正式毕业"),
            ("promote_experiment", "promote_experiment", "推广 Google Ads Experiment 结果"),
        ):
            tools.append(method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name=f"google_{method_name}",
                description=f"{description}；默认仅生成 dry-run 计划。",
                method_name=method_name, result_key="experiment_result",
                properties={"experiment_id": experiment_schema["properties"]["experiment_id"]},
                required=["experiment_id"], action=method_name.split("_", 1)[0],
                resource_type="experiment", resource_id_field="experiment_id",
                intent_types=[intent], traits=["write", "experiment", "lifecycle"],
                write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((data["experiment_id"],), {}),
            ))

        # Google v24 uses the regular AdGroup/AdGroupAd resources for these
        # channel-specific formats.  They stay separate Tools so Skills can
        # compose an explicit creation chain and callers never have to pass a
        # provider-specific discriminator through an untyped payload object.
        tools.append(method_tool(
            platform="google-ads", skill="google-ads-api-expert",
            name="google_create_specialized_ad_group",
            description="创建 Google Demand Gen、Hotel、Local、Smart 或 Travel Ad Group；默认仅生成 dry-run 计划。",
            method_name="create_ad_group", result_key="ad_group_id",
            properties=google_ad_group_schema()["properties"],
            required=google_ad_group_schema()["required"],
            provider_required=google_ad_group_schema()["provider_required"],
            action="create", resource_type="ad_group", parent_resource_type="campaign",
            resource_id_field="ad_group_id",
            parent_resource_id_field="campaign_id",
            intent_types=["create_ad_group", "create_campaign"],
            activation_rules=[{
                "field": "campaign_type", "aliases": ["advertising_channel_type"],
                "in": ["DEMAND_GEN", "HOTEL", "LOCAL", "SMART", "TRAVEL"],
            }],
            traits=["write", "ad_group", "specialized_campaign"], write=True,
            live_support=True, readback_tool="google_get_ad_group",
            provider_api_version="v24", required_permissions=["ads.plan"],
            argument_builder=lambda _ctx, data: ((data["campaign_id"], data["name"]), {
                "cpc_bid_micros": data.get("cpc_bid_micros") or int(float(data.get("cpc_bid", 0.5)) * 1_000_000),
                "type": ({
                    "DEMAND_GEN": "DISPLAY_STANDARD",
                    "HOTEL": "HOTEL_ADS",
                    "LOCAL": "SMART_CAMPAIGN_ADS",
                    "SMART": "SMART_CAMPAIGN_ADS",
                    "TRAVEL": "TRAVEL_ADS",
                }.get(str(data.get("campaign_type") or "").upper())
                or data.get("type", "SEARCH_STANDARD")),
                "status": data.get("status"), "targeting": data.get("targeting"),
                "demand_gen_ad_group_settings": data.get("demand_gen_ad_group_settings"),
            }),
        ))

        def _ad_tool(
            *, name: str, description: str, method_name: str, schema: dict[str, Any],
            channel_types: list[str], positional: list[str], optional: list[str],
        ) -> tuple[ToolDefinition, ToolHandler]:
            return method_tool(
                platform="google-ads", skill="google-ads-api-expert", name=name,
                description=description, method_name=method_name, result_key="ad_plan",
                properties=schema["properties"], required=schema["required"],
                provider_required=schema.get("provider_required", []),
                provider_any_of=schema.get("provider_any_of", []),
                conditional_rules=schema.get("conditional_rules", []),
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="ad_group_id",
                intent_types=[method_name, "create_campaign"],
                activation_rules=[{
                    "field": "campaign_type", "aliases": ["advertising_channel_type"],
                    "in": channel_types,
                }],
                traits=["write", "ad", "specialized_campaign"], write=True,
                live_support=True, readback_tool="google_get_ad",
                provider_api_version="v24", required_permissions=["ads.plan"],
                argument_builder=lambda _ctx, data, p=positional, o=optional: _build_specialized_ad_args(
                    data, p, o, name
                ),
            )

        # These Feed/FeedItem definitions are retained as compatibility
        # metadata while the v24 surface is being migrated, but are filtered
        # before binding below. A planned surface must not become a runtime
        # Tool simply because an old adapter method still exists.
        tools.extend([
            _ad_tool(
                name="google_create_demand_gen_multi_asset_ad",
                description="创建 Google Demand Gen Multi Asset Ad；默认仅生成 dry-run 计划。",
                method_name="create_demand_gen_multi_asset_ad",
                schema=google_demand_gen_multi_asset_ad_schema(), channel_types=["DEMAND_GEN"],
                positional=["ad_group_id", "name", "final_url", "headlines", "descriptions", "business_name"],
                optional=["marketing_images", "square_marketing_images", "portrait_marketing_images", "tall_portrait_marketing_images", "classic_display_images", "logo_images", "call_to_action_text", "status"],
            ),
            _ad_tool(
                name="google_create_demand_gen_carousel_ad",
                description="创建 Google Demand Gen Carousel Ad；默认仅生成 dry-run 计划。",
                method_name="create_demand_gen_carousel_ad",
                schema=google_demand_gen_carousel_ad_schema(), channel_types=["DEMAND_GEN"],
                positional=["ad_group_id", "name", "final_url", "headline", "description", "carousel_cards"],
                optional=["business_name", "logo_image", "call_to_action_text", "status"],
            ),
            _ad_tool(
                name="google_create_demand_gen_video_responsive_ad",
                description="创建 Google Demand Gen Video Responsive Ad；默认仅生成 dry-run 计划。",
                method_name="create_demand_gen_video_responsive_ad",
                schema=google_demand_gen_video_responsive_ad_schema(), channel_types=["DEMAND_GEN"],
                positional=["ad_group_id", "name", "business_name", "videos", "headlines", "descriptions"],
                optional=["final_url", "long_headlines", "logo_images", "companion_banners", "call_to_actions", "breadcrumb1", "breadcrumb2", "status"],
            ),
            _ad_tool(
                name="google_create_demand_gen_product_ad",
                description="创建 Google Demand Gen Product Ad；默认仅生成 dry-run 计划。",
                method_name="create_demand_gen_product_ad",
                schema=google_demand_gen_product_ad_schema(), channel_types=["DEMAND_GEN"],
                positional=["ad_group_id", "name", "headline", "description", "business_name", "logo_image", "call_to_action"],
                optional=["final_url", "breadcrumb1", "breadcrumb2", "status"],
            ),
            _ad_tool(
                name="google_create_hotel_ad", description="创建 Google Hotel Ad；默认仅生成 dry-run 计划。",
                method_name="create_hotel_ad", schema=google_hotel_ad_schema(), channel_types=["HOTEL"],
                positional=["ad_group_id", "name"], optional=["status"],
            ),
            _ad_tool(
                name="google_create_local_ad", description="创建 Google Local Ad；默认仅生成 dry-run 计划。",
                method_name="create_local_ad", schema=google_local_ad_schema(), channel_types=["LOCAL"],
                positional=["ad_group_id", "name", "final_url", "headlines", "descriptions"],
                optional=["path1", "path2", "logo_images", "videos", "marketing_images", "call_to_actions", "status"],
            ),
            _ad_tool(
                name="google_create_smart_campaign_ad", description="创建 Google Smart Campaign Ad；默认仅生成 dry-run 计划。",
                method_name="create_smart_campaign_ad", schema=google_smart_campaign_ad_schema(), channel_types=["SMART"],
                positional=["ad_group_id", "name", "final_url", "headlines", "descriptions"], optional=["status"],
            ),
            _ad_tool(
                name="google_create_travel_ad", description="创建 Google Travel Ad；默认仅生成 dry-run 计划。",
                method_name="create_travel_ad", schema=google_travel_ad_schema(), channel_types=["TRAVEL"],
                positional=["ad_group_id", "name"], optional=["status"],
            ),
        ])

        # Feed/FeedItem and ConversionGoal are first-class Google Ads
        # resources.  They are exposed with explicit provider-owned schemas so
        # Skills can compose them without a generic passthrough endpoint.
        tools.extend([
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_feeds",
                description="查询 Google Ads Feed 列表。",
                method_name="list_feeds", result_key="feeds",
                properties=feed_schema["properties"], required=["customer_id"],
                action="list", resource_type="feed",
                intent_types=["list_feeds"], traits=["read", "feed"],
                argument_builder=lambda _ctx, data: ((), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_feed",
                description="查询 Google Ads Feed 详情。",
                method_name="get_feed", result_key="feed",
                properties=feed_schema["properties"], required=["customer_id", "feed_id"],
                action="get", resource_type="feed", resource_id_field="feed_id",
                intent_types=["get_feed"], traits=["read", "feed"],
                argument_builder=lambda _ctx, data: ((data["feed_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_feed",
                description="创建 Google Ads Feed；默认仅生成 dry-run 计划。",
                method_name="create_feed", result_key="feed_id",
                properties=feed_schema["properties"], required=["customer_id", "name"],
                provider_required=["name"],
                action="create", resource_type="feed", resource_id_field="feed_id",
                intent_types=["create_feed"], traits=["write", "feed"],
                write=True,
                argument_builder=lambda _ctx, data: (({
                    key: data.get(key)
                    for key in ("name", "origin", "attributes")
                    if data.get(key) is not None
                },), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_feed",
                description="更新 Google Ads Feed；默认仅生成 dry-run 计划。",
                method_name="update_feed", result_key="feed_result",
                properties=feed_schema["properties"] | {
                    "updates": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
                required=["customer_id", "feed_id", "updates"],
                provider_required=["feed_id", "updates"],
                action="update", resource_type="feed", resource_id_field="feed_id",
                intent_types=["update_feed"], traits=["write", "feed"],
                write=True,
                argument_builder=lambda _ctx, data: ((data["feed_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_feed",
                description="删除 Google Ads Feed；默认仅生成 dry-run 计划。",
                method_name="delete_feed", result_key="feed_result",
                properties=feed_schema["properties"], required=["customer_id", "feed_id"],
                action="delete", resource_type="feed", resource_id_field="feed_id",
                intent_types=["delete_feed"], traits=["write", "feed"],
                write=True,
                argument_builder=lambda _ctx, data: ((data["feed_id"],), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_feed_items",
                description="查询 Google Ads FeedItem 列表。",
                method_name="list_feed_items", result_key="feed_items",
                properties=feed_schema["properties"],
                required=["customer_id", "feed_id"],
                action="list", resource_type="feed_item",
                parent_resource_type="feed", parent_resource_id_field="feed_id",
                intent_types=["list_feed_items"], traits=["read", "feed", "feed_item"],
                argument_builder=lambda _ctx, data: ((data["feed_id"],), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_get_feed_item",
                description="查询 Google Ads FeedItem 详情。",
                method_name="get_feed_item", result_key="feed_item",
                properties=feed_schema["properties"],
                required=["customer_id", "feed_id", "feed_item_resource_name"],
                action="get", resource_type="feed_item",
                parent_resource_type="feed",
                parent_resource_id_field="feed_id",
                resource_id_field="feed_item_resource_name",
                intent_types=["get_feed_item"], traits=["read", "feed", "feed_item"],
                argument_builder=lambda _ctx, data: ((
                    data["feed_id"], data["feed_item_resource_name"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_feed_item",
                description="创建 Google Ads FeedItem；默认仅生成 dry-run 计划。",
                method_name="create_feed_item", result_key="feed_item_id",
                properties=feed_schema["properties"],
                required=["customer_id", "feed_id", "attribute_values"],
                provider_required=["feed_id", "attribute_values"],
                action="create", resource_type="feed_item",
                parent_resource_type="feed", parent_resource_id_field="feed_id",
                resource_id_field="feed_item_id",
                intent_types=["create_feed_item"], traits=["write", "feed", "feed_item"],
                write=True,
                argument_builder=lambda _ctx, data: (
                    (data["feed_id"], data["attribute_values"]), {}
                ),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_feed_item",
                description="更新 Google Ads FeedItem；默认仅生成 dry-run 计划。",
                method_name="update_feed_item", result_key="feed_item_result",
                properties={
                    "customer_id": feed_schema["properties"]["customer_id"],
                    "feed_item_resource_name": feed_schema["properties"]["feed_item_resource_name"],
                    "updates": {
                        "type": "object",
                        "properties": {
                            "attribute_values": feed_schema["properties"]["attribute_values"],
                        },
                        "required": ["attribute_values"],
                        "additionalProperties": False,
                    },
                },
                required=["customer_id", "feed_item_resource_name", "updates"],
                provider_required=["feed_item_resource_name", "updates"],
                action="update", resource_type="feed_item",
                resource_id_field="feed_item_resource_name",
                intent_types=["update_feed_item"], traits=["write", "feed", "feed_item"],
                write=True,
                argument_builder=lambda _ctx, data: (
                    (data["feed_item_resource_name"], data["updates"]), {}
                ),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_delete_feed_item",
                description="删除 Google Ads FeedItem；默认仅生成 dry-run 计划。",
                method_name="delete_feed_item", result_key="feed_item_result",
                properties=feed_schema["properties"],
                required=["customer_id", "feed_item_resource_name"],
                action="delete", resource_type="feed_item",
                resource_id_field="feed_item_resource_name",
                intent_types=["delete_feed_item"], traits=["write", "feed", "feed_item"],
                write=True,
                argument_builder=lambda _ctx, data: (
                    (data["feed_item_resource_name"],), {}
                ),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_customer_conversion_goals",
                description="查询 Google Ads Customer Conversion Goal 列表。",
                method_name="list_customer_conversion_goals",
                result_key="conversion_goals",
                properties=conversion_goal_schema["properties"],
                required=["customer_id"],
                action="list", resource_type="customer_conversion_goal",
                intent_types=["list_customer_conversion_goals"],
                traits=["read", "conversion_goal"],
                argument_builder=lambda _ctx, data: ((), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_customer_conversion_goal",
                description="更新 Google Ads Customer Conversion Goal；默认仅生成 dry-run 计划。",
                method_name="update_customer_conversion_goal",
                result_key="conversion_goal_result",
                properties=conversion_goal_schema["properties"],
                required=["customer_id", "category", "origin", "updates"],
                provider_required=["category", "origin", "updates"],
                action="update", resource_type="customer_conversion_goal",
                resource_id_field="category",
                intent_types=["update_customer_conversion_goal"],
                traits=["write", "conversion_goal"],
                write=True,
                argument_builder=lambda _ctx, data: ((
                    data["category"], data["origin"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_list_campaign_conversion_goals",
                description="查询 Google Ads Campaign Conversion Goal 列表。",
                method_name="list_campaign_conversion_goals",
                result_key="conversion_goals",
                properties=conversion_goal_schema["properties"],
                required=["customer_id", "campaign_id"],
                action="list", resource_type="campaign_conversion_goal",
                parent_resource_type="campaign",
                parent_resource_id_field="campaign_id",
                intent_types=["list_campaign_conversion_goals"],
                traits=["read", "conversion_goal"],
                argument_builder=lambda _ctx, data: ((data["campaign_id"],), {
                    "page_size": data.get("limit", 100),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_update_campaign_conversion_goal",
                description="更新 Google Ads Campaign Conversion Goal；默认仅生成 dry-run 计划。",
                method_name="update_campaign_conversion_goal",
                result_key="conversion_goal_result",
                properties=conversion_goal_schema["properties"],
                required=["customer_id", "campaign_id", "category", "origin", "updates"],
                provider_required=["campaign_id", "category", "origin", "updates"],
                action="update", resource_type="campaign_conversion_goal",
                parent_resource_type="campaign",
                parent_resource_id_field="campaign_id",
                resource_id_field="category",
                intent_types=["update_campaign_conversion_goal"],
                traits=["write", "conversion_goal"],
                write=True,
                argument_builder=lambda _ctx, data: ((
                    data["campaign_id"], data["category"], data["origin"],
                    data["updates"],
                ), {}),
            ),
        ])

        unavailable_methods = set(self.provider_method_exclusions) - {"for_customer"}
        tools = [
            tool for tool in tools
            if getattr(tool[1], "method_name", "") not in unavailable_methods
        ]

        bound_tools = []
        for tool in tools:
            definition, handler = bind_provider_method(tool, client)
            handler.client_resolver = lambda ctx, data, base=client: for_customer(
                base, ctx.account_id or data.get("customer_id")
            )
            bound_tools.append((definition, handler))
        return bound_tools

    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        api_client = getattr(self, '_api_client', None)

        # List Campaigns
        tools.append((ToolDefinition(
            name="google_list_campaigns",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 列表。",
            input_schema=ToolSchema(
                required=["customer_id"],
                properties={
                    "customer_id": {"type": "string"},
                    "campaign_id": {
                        "type": "string",
                        "description": "可选：精确查询一个 Campaign ID，适用于父资源选择",
                    },
                    "limit": {"type": "integer"},
                },
            ),
            action="list", resource_type="campaign",
            intent_types=[
                "list_campaigns", "cross_channel_overview", "cross_channel_compare",
                "cross_channel_performance_insights", "cross_channel_optimize_budget",
                "cross_channel_export_report",
            ],
            intent_aliases=[
                "列出 Google 广告系列", "查询 Google Ads 广告系列",
                "列出 Google Ads campaign 列表", "列出 Google Ads campaign",
                "查询 Google Ads campaign 列表",
            ],
            result_items_key="campaigns",
            result_id_fields=["id", "campaign_id", "resource_name"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), GoogleListCampaignsHandler(api_client)))

        # Get Campaign
        tools.append((ToolDefinition(
            name="google_get_campaign",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 详情（支持 campaign_id 或 campaign_name）。",
            input_schema=ToolSchema(
                properties={
                    "campaign_id": {"type": "string"},
                    "campaign_name": {"type": "string", "description": "Campaign 名称（可通过名称查找 ID）"},
                },
            ),
            action="get", resource_type="campaign", resource_id_field="campaign_id",
            intent_types=["get_campaign"],
            intent_aliases=[
                "查询 Google campaign 详情", "查看 Google campaign 详情",
                "查询 Google Ads campaign 详情", "查询 Google Ads 广告系列详情",
            ],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), GoogleGetCampaignHandler(api_client)))

        # Create Campaign
        tools.append((ToolDefinition(
            name="google_create_campaign",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Campaign。",
            input_schema=ToolSchema(**google_campaign_schema()),
            action="create", resource_type="campaign",
            intent_types=["create_campaign", "create_campaign_only"],
            intent_aliases=[
                "创建 Google 广告系列", "创建 Google App 广告", "创建 Google campaign",
            ],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign", "campaign_only"],
            # The v24 Campaign -> Ad Group -> Ad mutate adapter is verified
            # for controlled test-account runs. Runtime still requires the
            # deployment live fuse, tool allowlist and confirmation.
            live_support=True,
            readback_tool="google_get_campaign",
            resource_id_field="campaign_id",
        ), GoogleCreateCampaignHandler(api_client)))

        # List Ad Groups
        tools.append((ToolDefinition(
            name="google_list_ad_groups",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad Group 列表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            action="list", resource_type="ad_group", parent_resource_type="campaign",
            parent_resource_id_field="campaign_id",
            intent_types=["list_adgroups"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad_group"],
        ), GoogleListAdGroupsHandler(api_client)))

        # Get Ad Group
        tools.append((ToolDefinition(
            name="google_get_ad_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad Group 详情。",
            input_schema=ToolSchema(
                required=["ad_group_id"],
                properties={
                    "ad_group_id": {"type": "string"},
                    # The parent is part of the routing contract.  Google can
                    # resolve a resource by its own ID, so it remains
                    # optional for direct lookups while still being explicit
                    # to planners, validators and readback reconciliation.
                    "campaign_id": {"type": "string"},
                },
            ),
            action="get", resource_type="ad_group", parent_resource_type="campaign",
            resource_id_field="ad_group_id",
            parent_resource_id_field="campaign_id",
            intent_types=["get_adgroup"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad_group"],
        ), GoogleGetAdGroupHandler(api_client)))

        # Create Ad Group
        tools.append((ToolDefinition(
            name="google_create_ad_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Ad Group。",
            input_schema=ToolSchema(**google_ad_group_schema()),
            action="create", resource_type="ad_group", parent_resource_type="campaign",
            intent_types=["create_campaign", "create_adgroup"],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad_group"],
            live_support=True,
            readback_tool="google_get_ad_group",
            resource_id_field="ad_group_id",
            parent_resource_id_field="campaign_id",
            activation_rules=[{
                "field": "campaign_type",
                "aliases": ["advertising_channel_type"],
                "not_in": [
                    "PERFORMANCE_MAX", "MAX", "MULTI_CHANNEL", "DEMAND_GEN",
                    "HOTEL", "LOCAL", "SMART", "TRAVEL", "LOCAL_SERVICES",
                ],
            }],
        ), GoogleCreateAdGroupHandler(api_client)))

        # List Ads
        tools.append((ToolDefinition(
            name="google_list_ads",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad 列表。",
            input_schema=ToolSchema(
                required=["ad_group_id"],
                properties={"ad_group_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            action="list", resource_type="ad", parent_resource_type="ad_group",
            parent_resource_id_field="ad_group_id",
            intent_types=["list_ads"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), GoogleListAdsHandler(api_client)))

        # Get Ad
        tools.append((ToolDefinition(
            name="google_get_ad",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad 详情。",
            input_schema=ToolSchema(
                required=["ad_id"],
                properties={
                    "ad_id": {"type": "string"},
                    "ad_group_id": {"type": "string"},
                },
            ),
            action="get", resource_type="ad", parent_resource_type="ad_group",
            resource_id_field="ad_id",
            parent_resource_id_field="ad_group_id",
            intent_types=["get_ad"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), GoogleGetAdHandler(api_client)))

        # Create Ad
        tools.append((ToolDefinition(
            name="google_create_ad",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Ad。",
            input_schema=ToolSchema(**google_ad_schema()),
            action="create", resource_type="ad", parent_resource_type="ad_group",
            intent_types=["create_campaign", "create_ad"],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
            live_support=True,
            readback_tool="google_get_ad",
            resource_id_field="ad_id",
            parent_resource_id_field="ad_group_id",
            activation_rules=[{
                "field": "campaign_type",
                "aliases": ["advertising_channel_type"],
                "in": ["SEARCH"],
                "default": "SEARCH",
            }],
        ), GoogleCreateAdHandler(api_client)))

        # List Asset Groups (PMax)
        tools.append((ToolDefinition(
            name="google_list_asset_groups",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 PMax Campaign 的 Asset Group 列表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            action="list", resource_type="asset_group", parent_resource_type="campaign",
            parent_resource_id_field="campaign_id",
            intent_types=["list_asset_groups"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "pmax"],
        ), GoogleListAssetGroupsHandler(api_client)))

        # Get Asset Group (PMax)
        tools.append((ToolDefinition(
            name="google_get_asset_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 PMax Asset Group 详情。",
            input_schema=ToolSchema(
                required=["asset_group_id"],
                properties={
                    "asset_group_id": {"type": "string"},
                    "campaign_id": {"type": "string"},
                },
            ),
            action="get", resource_type="asset_group", parent_resource_type="campaign",
            resource_id_field="asset_group_id",
            parent_resource_id_field="campaign_id",
            intent_types=["get_asset_group"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "pmax"],
        ), GoogleGetAssetGroupHandler(api_client)))

        tools.append((ToolDefinition(
            name="google_create_asset_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google PMax Asset Group；live 仅在受控测试账号和确认后执行。",
            input_schema=ToolSchema(**google_asset_group_schema()),
            action="create", resource_type="asset_group", parent_resource_type="campaign",
            intent_types=["create_asset_group"],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "pmax", "asset_group"],
            live_support=True,
            readback_tool="google_get_asset_group",
            resource_id_field="asset_group_id",
            parent_resource_id_field="campaign_id",
        ), GoogleCreateAssetGroupHandler(api_client)))

        # Get Campaign Report
        tools.append((ToolDefinition(
            name="google_get_campaign_report",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 报表。支持按 campaign_ids 过滤，默认查询最近30天数据。",
            input_schema=ToolSchema(
                required=[],
                properties={
                    "customer_id": {"type": "string", "description": "Google Ads 账户 ID（从上下文自动获取）"},
                    "campaign_ids": {"type": "array", "items": {"type": "string"}, "description": "要查询的 Campaign ID 列表，不填则默认查前5个"},
                    "date_range": {"type": "string", "description": "日期范围，如 LAST_30_DAYS, YESTERDAY, THIS_MONTH"},
                },
            ),
            action="report", resource_type="report",
            intent_types=["get_campaign_report", "download_report"],
            intent_aliases=[
                "查询 Google Ads 报表", "查询 Google campaign 报表",
                "查看 Google 广告系列表现",
            ],
            related_resource_type="campaign",
            related_resource_id_fields=["campaign_ids", "campaign_id"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), GoogleGetReportHandler(api_client)))

        tools.append((ToolDefinition(
            name="google_list_keywords",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads 关键词，可按 Campaign 或 Ad Group 过滤。",
            input_schema=ToolSchema(
                properties={
                    "customer_id": {"type": "string"},
                    "campaign_id": {"type": "string"},
                    "ad_group_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            ),
            action="list", resource_type="keyword", intent_types=["list_keywords"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "keyword"],
        ), GoogleListKeywordsHandler(api_client)))

        for resource_type, resource_id in [
            ("campaign", "campaign_id"),
            ("ad_group", "ad_group_id"),
            ("ad", "ad_id"),
            ("asset_group", "asset_group_id"),
        ]:
            tools.append((ToolDefinition(
                name=f"google_update_{resource_type}",
                skill="google-ads-api-expert",
                platform="google-ads",
                description=f"更新 Google Ads {resource_type}，默认仅生成 dry-run 计划。",
                input_schema=ToolSchema(
                    required=[resource_id, "updates"],
                    properties={
                        resource_id: {"type": "string"},
                        **({
                            "campaign_id": {"type": "string"},
                        } if resource_type in {"ad_group", "asset_group"} else {
                            "ad_group_id": {"type": "string"},
                        } if resource_type == "ad" else {}),
                        "updates": google_updates(resource_type),
                    },
                ),
                action="update", resource_type=resource_type,
                parent_resource_type={
                    "ad_group": "campaign", "ad": "ad_group", "asset_group": "campaign",
                }.get(resource_type),
                intent_types={
                    "campaign": [
                        "update_campaign", "pause_campaign", "resume_campaign",
                        "cross_channel_batch_pause", "cross_channel_batch_resume",
                        "cross_channel_batch_update_budget",
                    ],
                    "ad_group": ["update_adgroup"], "ad": ["update_ad"],
                    "asset_group": ["update_asset_group"],
                }[resource_type],
                intent_aliases=(
                    ["更新 Google campaign", "更新 Google Ads campaign"]
                    if resource_type == "campaign" else
                    ["更新 Google ad group", "更新 Google Ads ad group"]
                    if resource_type == "ad_group" else []
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                # AssetGroup is a first-class mutable PMax child resource.
                # Product groups and listing filters have their own explicit
                # Tools above; this generic adapter covers the Campaign,
                # AdGroup, Ad and PMax AssetGroup lifecycle.
                live_support=(resource_type in {"campaign", "ad_group", "ad", "asset_group"}),
                readback_tool={
                    "campaign": "google_get_campaign",
                    "ad_group": "google_get_ad_group",
                    "ad": "google_get_ad",
                    "asset_group": "google_get_asset_group",
                }.get(resource_type),
                resource_id_field=resource_id,
                parent_resource_id_field={
                    "ad_group": "campaign_id", "ad": "ad_group_id",
                    "asset_group": "campaign_id",
                }.get(resource_type),
            ), CampaignUpdateHandler(
                api_client, resource_type, _google_update_adapter,
                resource_id_field=resource_id,
                parent_resource_id_field={
                    "ad_group": "campaign_id", "ad": "ad_group_id",
                    "asset_group": "campaign_id",
                }.get(resource_type),
            )))

        tools.extend(self._extended_provider_tools(api_client))

        return apply_lookup_contracts(tools, GOOGLE_LOOKUP_CONTRACTS)

def create_google_capability(api_client: Optional[GoogleAdsAPIClient] = None) -> GoogleCapability:
    cap = GoogleCapability()
    cap._api_client = api_client
    return cap
