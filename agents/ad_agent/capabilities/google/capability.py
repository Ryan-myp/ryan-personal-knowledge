"""
capabilities/google/capability.py - Google Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
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
    google_campaign_schema, google_ad_group_schema, google_ad_schema,
    google_asset_schema, google_asset_group_schema, google_ad_format_catalog, google_keyword_schema,
    google_product_group_schema, google_responsive_display_ad_schema,
    google_video_ad_schema, google_campaign_budget_schema,
    google_campaign_budget_update_schema,
    google_conversion_action_schema, google_conversion_action_update_schema,
    google_campaign_criterion_schema,
    google_user_list_schema, google_user_list_update_schema,
    google_bidding_strategy_schema, google_bidding_strategy_update_schema,
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient
from ..update_contracts import google_updates

logger = logging.getLogger(__name__)


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
    provider_method_exclusions = {"for_customer"}
    capability_version = "1.3.0"
    provider_api_version = "v24"
    provider_method_coverage = {
        "list_campaigns": ["google_list_campaigns"], "get_campaign": ["google_get_campaign"],
        "list_ad_groups": ["google_list_ad_groups"], "get_ad_group": ["google_get_ad_group"],
        "list_ads": ["google_list_ads"], "get_ad": ["google_get_ad"],
        "list_keywords": ["google_list_keywords"], "list_asset_groups": ["google_list_asset_groups"],
        "list_assets": ["google_list_assets"], "get_asset": ["google_get_asset"],
        "create_keywords": ["google_create_keywords"],
        "get_asset_group": ["google_get_asset_group"], "create_campaign": ["google_create_campaign"],
        "update_campaign": ["google_update_campaign"], "update_ad_group": ["google_update_ad_group"],
        "update_ad": ["google_update_ad"], "update_asset_group": ["google_update_asset_group"],
        "pause_campaign": ["google_pause_campaign"], "resume_campaign": ["google_resume_campaign"],
        "create_ad_group": ["google_create_ad_group"], "create_search_ad": ["google_create_search_ad", "google_create_ad"],
        "create_pmax_asset_group": ["google_create_pmax_asset_group", "google_create_asset_group"],
        "create_product_group": ["google_create_product_group"],
        "create_responsive_display_ad": ["google_create_responsive_display_ad"],
        "create_video_ad": ["google_create_video_ad"],
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
        "get_campaign_report": ["google_get_campaign_report"], "get_adgroup_report": ["google_get_adgroup_report"],
    }

    def get_ad_format_catalog(self) -> list[dict]:
        return google_ad_format_catalog()

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
        tools = [
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
                properties={
                    "ad_group_id": {"type": "string"},
                    "headlines": {"type": "array", "items": {"type": "string"}},
                    "descriptions": {"type": "array", "items": {"type": "string"}},
                    "final_url": {"type": "string"}, "ad_type": {"type": "string"},
                    "path1": {"type": "string"}, "path2": {"type": "string"},
                    "responsive_search_ad": {"type": "object"}, "status": {"type": "string"},
                }, required=["ad_group_id", "headlines", "descriptions", "final_url"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="ad_group_id",
                intent_types=["create_search_ad"], traits=["write", "ad"], write=True,
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
                intent_types=["create_keywords"], traits=["write", "keyword"], write=True,
                argument_builder=lambda _ctx, data: ((data["ad_group_id"], data["keywords"]), {}),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_pmax_asset_group", description="创建 Google PMax Asset Group；默认仅生成 dry-run 计划。",
                method_name="create_pmax_asset_group", result_key="asset_group_id",
                properties={
                    "campaign_id": {"type": "string"}, "name": {"type": "string"},
                    "headlines": {"type": "array", "items": {"type": "string"}},
                    "descriptions": {"type": "array", "items": {"type": "string"}},
                    "images": {"type": "array"}, "videos": {"type": "array"},
                }, required=["campaign_id", "name", "headlines"], action="create",
                resource_type="asset_group", parent_resource_type="campaign",
                resource_id_field="asset_group_id", parent_resource_id_field="campaign_id",
                intent_types=["create_pmax_asset_group"], traits=["write", "asset_group"], write=True,
                argument_builder=lambda _ctx, data: ((data["campaign_id"], data["name"], data["headlines"]), {
                    "descriptions": data.get("descriptions"), "images": data.get("images"), "videos": data.get("videos"),
                }),
            ),
            method_tool(
                platform="google-ads", skill="google-ads-api-expert",
                name="google_create_product_group",
                description="创建 Google Shopping Product Group/Listing Group；默认仅生成 dry-run 计划。",
                method_name="create_product_group", result_key="product_group_id",
                properties=google_product_group_schema()["properties"],
                required=google_product_group_schema()["required"],
                provider_required=google_product_group_schema()["provider_required"],
                conditional_rules=google_product_group_schema()["conditional_rules"],
                action="create", resource_type="product_group", parent_resource_type="ad_group",
                resource_id_field="product_group_id", parent_resource_id_field="ad_group_id",
                intent_types=["create_product_group"], traits=["write", "product_group", "shopping"], write=True,
                argument_builder=lambda _ctx, data: ((data["ad_group_id"], data["product_group_type"]), {
                    "value": data.get("value"),
                    "partition_type": data.get("partition_type", "UNIT"),
                    "parent_criterion_id": data.get("parent_criterion_id"),
                    "cpc_bid_micros": data.get("cpc_bid_micros"),
                    "bidding_category_level": data.get("bidding_category_level", "LEVEL1"),
                }),
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
                intent_types=["create_responsive_display_ad"], traits=["write", "ad", "display"], write=True,
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
                intent_types=["create_video_ad"], traits=["write", "ad", "video"], write=True,
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
                intent_types=["download_report"], traits=["read", "report", "ad_group"],
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
                properties={"customer_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
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
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
            live_support=False,
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
                properties={"ad_group_id": {"type": "string"}},
            ),
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
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad_group"],
            live_support=False,
            resource_id_field="ad_group_id",
            parent_resource_id_field="campaign_id",
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
                properties={"ad_id": {"type": "string"}},
            ),
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
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
            live_support=False,
            resource_id_field="ad_id",
            parent_resource_id_field="ad_group_id",
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
                properties={"asset_group_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "pmax"],
        ), GoogleGetAssetGroupHandler(api_client)))

        tools.append((ToolDefinition(
            name="google_create_asset_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google PMax Asset Group；当前仅支持 dry-run 计划。",
            input_schema=ToolSchema(**google_asset_group_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "pmax", "asset_group"],
            live_support=False,
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
                        "updates": google_updates(resource_type),
                    },
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                live_support=False,
                resource_id_field=resource_id,
            ), CampaignUpdateHandler(
                api_client, resource_type, _google_update_adapter,
                resource_id_field=resource_id,
            )))

        tools.extend(self._extended_provider_tools(api_client))

        return tools

def create_google_capability(api_client: Optional[GoogleAdsAPIClient] = None) -> GoogleCapability:
    cap = GoogleCapability()
    cap._api_client = api_client
    return cap
