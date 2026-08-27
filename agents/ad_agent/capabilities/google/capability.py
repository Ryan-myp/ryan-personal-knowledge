"""
capabilities/google/capability.py - Google Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
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
from ...api_clients.google_ads_client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class GoogleCapability(BaseCapability):
    platform_name = "google-ads"

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
            input_schema=ToolSchema(
                required=["customer_id", "campaign_name"],
                properties={
                    "customer_id": {"type": "string"},
                    "campaign_name": {"type": "string"},
                    "advertising_channel_type": {"type": "string"},
                    "campaign_type": {"type": "string"},
                    "bidding_strategy": {"type": "string"},
                    "budget": {"type": "number"},
                    "status": {"type": "string"},
                    "target_cpa_micros": {"type": "integer"},
                    "target_roas": {"type": "number"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
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
            input_schema=ToolSchema(
                required=["campaign_id", "name"],
                properties={
                    "campaign_id": {"type": "string"},
                    "name": {"type": "string"},
                    "cpc_bid": {"type": "number"},
                    "status": {"type": "string"},
                    "type": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad_group"],
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
            input_schema=ToolSchema(
                required=["ad_group_id", "name"],
                provider_required=["final_url"],
                properties={
                    "ad_group_id": {"type": "string"},
                    "name": {"type": "string"},
                    "headlines": {"type": "array", "items": {"type": "string"}},
                    "descriptions": {"type": "array", "items": {"type": "string"}},
                    "final_url": {"type": "string"},
                    "path1": {"type": "string"},
                    "path2": {"type": "string"},
                    "status": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
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
            input_schema=ToolSchema(
                required=["campaign_id", "name"],
                properties={
                    "campaign_id": {"type": "string"},
                    "name": {"type": "string"},
                    "headlines": {"type": "array"},
                    "descriptions": {"type": "array"},
                    "images": {"type": "array"},
                    "videos": {"type": "array"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "pmax", "asset_group"],
            live_support=False,
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
                    properties={resource_id: {"type": "string"}, "updates": {"type": "object"}},
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                live_support=(resource_type == "campaign"),
            ), CampaignUpdateHandler(api_client, resource_type)))

        return tools

    def _get_campaign_tool_sequence(self):
        return ["google_create_campaign", "google_create_ad_group", "google_create_ad"]

    def _get_report_tool_sequence(self):
        return ["google_get_campaign_report"]


def create_google_capability(api_client: Optional[GoogleAdsAPIClient] = None) -> GoogleCapability:
    cap = GoogleCapability()
    cap._api_client = api_client
    return cap
