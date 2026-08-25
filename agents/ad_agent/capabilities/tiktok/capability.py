"""
capabilities/tiktok/capability.py - TikTok Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability
from .campaigns import (
    TikTokListCampaignsHandler,
    TikTokGetCampaignHandler,
    TikTokCreateCampaignHandler,
)
from .ad_groups import (
    TikTokListAdGroupsHandler,
    TikTokGetAdGroupHandler,
    TikTokCreateAdGroupHandler,
)
from .ads import TikTokListAdsHandler, TikTokGetAdHandler, TikTokCreateAdHandler
from .reports import TikTokGetReportHandler
from ...api_clients.tiktok_client import TikTokAPIClient

logger = logging.getLogger(__name__)


class TikTokCapability(BaseCapability):
    platform_name = "tiktok"

    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        api_client = getattr(self, '_api_client', None)

        # List Campaigns
        tools.append((ToolDefinition(
            name="tiktok_list_campaigns",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Campaign 列表。",
            input_schema=ToolSchema(
                required=["account_id"],
                properties={"account_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), TikTokListCampaignsHandler(api_client)))

        # Get Campaign
        tools.append((ToolDefinition(
            name="tiktok_get_campaign",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Campaign 详情。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), TikTokGetCampaignHandler(api_client)))

        # Create Campaign
        tools.append((ToolDefinition(
            name="tiktok_create_campaign",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="创建 TikTok Ads Campaign。",
            input_schema=ToolSchema(
                required=["account_id", "name"],
                properties={
                    "account_id": {"type": "string"},
                    "name": {"type": "string"},
                    "budget": {"type": "number"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.SAFE,
            traits=["write", "campaign"],
        ), TikTokCreateCampaignHandler(api_client)))

        # List Ad Groups
        tools.append((ToolDefinition(
            name="tiktok_list_adgroups",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad Group 列表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "adgroup"],
        ), TikTokListAdGroupsHandler(api_client)))

        # Get Ad Group
        tools.append((ToolDefinition(
            name="tiktok_get_adgroup",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad Group 详情。",
            input_schema=ToolSchema(
                required=["adgroup_id"],
                properties={"adgroup_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "adgroup"],
        ), TikTokGetAdGroupHandler(api_client)))

        # Create Ad Group
        tools.append((ToolDefinition(
            name="tiktok_create_adgroup",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="创建 TikTok Ads Ad Group。",
            input_schema=ToolSchema(
                required=["campaign_id", "name"],
                properties={"campaign_id": {"type": "string"}, "name": {"type": "string"}},
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.SAFE,
            traits=["write", "adgroup"],
        ), TikTokCreateAdGroupHandler(api_client)))

        # List Ads
        tools.append((ToolDefinition(
            name="tiktok_list_ads",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad 列表。",
            input_schema=ToolSchema(
                required=["adgroup_id"],
                properties={"adgroup_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), TikTokListAdsHandler(api_client)))

        # Get Ad
        tools.append((ToolDefinition(
            name="tiktok_get_ad",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad 详情。",
            input_schema=ToolSchema(
                required=["ad_id"],
                properties={"ad_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), TikTokGetAdHandler(api_client)))

        # Create Ad
        tools.append((ToolDefinition(
            name="tiktok_create_ad",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="创建 TikTok Ads Ad。",
            input_schema=ToolSchema(
                required=["adgroup_id", "name"],
                properties={"adgroup_id": {"type": "string"}, "name": {"type": "string"}},
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.SAFE,
            traits=["write", "ad"],
        ), TikTokCreateAdHandler(api_client)))

        # Get Report
        tools.append((ToolDefinition(
            name="tiktok_get_campaign_report",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Campaign 报表。",
            input_schema=ToolSchema(
                required=["account_id"],
                properties={"account_id": {"type": "string"}, "date_range": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), TikTokGetReportHandler(api_client)))

        return tools

    def _get_campaign_tool_sequence(self):
        return ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_ad"]

    def _get_report_tool_sequence(self):
        return ["tiktok_get_campaign_report"]


def create_tiktok_capability(api_client: Optional[TikTokAPIClient] = None) -> TikTokCapability:
    cap = TikTokCapability()
    cap._api_client = api_client
    return cap
