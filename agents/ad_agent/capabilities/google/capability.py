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
from .parameters import (
    google_campaign_schema, google_ad_group_schema, google_ad_schema,
    google_asset_group_schema, google_ad_format_catalog, google_keyword_schema,
    google_product_group_schema,
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
    capability_version = "1.1.0"
    provider_api_version = "v24"
    provider_method_coverage = {
        "list_campaigns": ["google_list_campaigns"], "get_campaign": ["google_get_campaign"],
        "list_ad_groups": ["google_list_ad_groups"], "get_ad_group": ["google_get_ad_group"],
        "list_ads": ["google_list_ads"], "get_ad": ["google_get_ad"],
        "list_keywords": ["google_list_keywords"], "list_asset_groups": ["google_list_asset_groups"],
        "create_keywords": ["google_create_keywords"],
        "get_asset_group": ["google_get_asset_group"], "create_campaign": ["google_create_campaign"],
        "update_campaign": ["google_update_campaign"], "update_ad_group": ["google_update_ad_group"],
        "update_ad": ["google_update_ad"], "update_asset_group": ["google_update_asset_group"],
        "pause_campaign": ["google_pause_campaign"], "resume_campaign": ["google_resume_campaign"],
        "create_ad_group": ["google_create_ad_group"], "create_search_ad": ["google_create_search_ad", "google_create_ad"],
        "create_pmax_asset_group": ["google_create_pmax_asset_group", "google_create_asset_group"],
        "create_product_group": ["google_create_product_group"],
        "get_campaign_report": ["google_get_campaign_report"], "get_adgroup_report": ["google_get_adgroup_report"],
    }

    def get_ad_format_catalog(self) -> list[dict]:
        return google_ad_format_catalog()

    def _extended_provider_tools(self, client):
        """Expose Google Ads client endpoints with dedicated contracts."""
        tools = [
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
        return [bind_provider_method(tool, client) for tool in tools]

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
