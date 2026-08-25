"""
capabilities/tiktok_capability.py - TikTok Ads Capability（真实 API 版）

TikTok Ads API Handler 实现：Campaign/Ad Group/Ad 全层级管理
"""

import logging
from typing import Optional
from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from .base import BaseCapability

from ..api_clients.tiktok_client import TikTokAPIClient

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# TikTok Handler
# ═══════════════════════════════════════════════════════════════

class TikTokCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaign_id = self.client.create_campaign(
                    account_id=advertiser_id,
                    name=input_data.get("name"),
                    budget=input_data.get("budget"),
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("name"),
                    "status": "DISABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok campaign: {e}")
        else:
            return ToolResult.ok({
                "campaign_id": f"tiktok_{input_data.get('name', 'unknown')}",
                "name": input_data.get("name"),
                "status": "DISABLED",
            })


class TikTokCreateAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                adgroup_id = self.client.create_adgroup(
                    account_id=advertiser_id,
                    campaign_id=input_data.get("campaign_id"),
                    name=input_data.get("name"),
                )
                return ToolResult.ok({"adgroup_id": adgroup_id})
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok adgroup: {e}")
        else:
            return ToolResult.ok({"adgroup_id": f"adgroup_{input_data.get('campaign_id')}"})


class TikTokCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                ad_id = self.client.create_ad(
                    account_id=advertiser_id,
                    adgroup_id=input_data.get("adgroup_id"),
                    name=input_data.get("name"),
                )
                return ToolResult.ok({"ad_id": ad_id})
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok ad: {e}")
        else:
            return ToolResult.ok({"ad_id": f"ad_{input_data.get('adgroup_id')}"})


class TikTokListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaigns = self.client.list_campaigns(advertiser_id)
                return ToolResult.ok({"campaigns": campaigns})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok campaigns: {e}")
        else:
            return ToolResult.ok({
                "campaigns": [
                    {"id": "test_campaign_1", "name": "Test Campaign 1", "status": "ENABLED"},
                    {"id": "test_campaign_2", "name": "Test Campaign 2", "status": "DISABLED"},
                ],
            })


class TikTokListAdGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        campaign_id = input_data.get("campaign_id")
        if self.client and advertiser_id and campaign_id:
            try:
                adgroups = self.client.list_adgroups(campaign_id)
                return ToolResult.ok({"adgroups": adgroups})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok adgroups: {e}")
        else:
            return ToolResult.ok({"adgroups": []})


class TikTokListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        adgroup_id = input_data.get("adgroup_id")
        if self.client and advertiser_id and adgroup_id:
            try:
                ads = self.client.list_ads(adgroup_id)
                return ToolResult.ok({"ads": ads})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok ads: {e}")
        else:
            return ToolResult.ok({"ads": []})


class TikTokGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client:
            try:
                campaign = self.client.get_campaign(campaign_id)
                return ToolResult.ok({"campaign": campaign})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok campaign: {e}")
        else:
            return ToolResult.ok({
                "id": campaign_id,
                "name": "Test Campaign",
                "status": "ENABLED",
            })


class TikTokGetAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("adgroup_id")
        if self.client:
            try:
                adgroup = self.client.get_adgroup(adgroup_id)
                return ToolResult.ok({"adgroup": adgroup})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok adgroup: {e}")
        else:
            return ToolResult.ok({"id": adgroup_id, "name": "Test AdGroup"})


class TikTokGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get("ad_id")
        if self.client:
            try:
                ad = self.client.get_ad(ad_id)
                return ToolResult.ok({"ad": ad})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok ad: {e}")
        else:
            return ToolResult.ok({"id": ad_id, "name": "Test Ad"})


class TikTokListAudiencesHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                audiences = self.client.list_audiences(advertiser_id)
                return ToolResult.ok({"audiences": audiences})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok audiences: {e}")
        else:
            return ToolResult.ok({"audiences": []})


class TikTokSparkAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                result = self.client.create_spark_ads(
                    account_id=advertiser_id,
                    adgroup_id=input_data.get("adgroup_id"),
                    video_id=input_data.get("video_id"),
                )
                return ToolResult.ok(result)
            except Exception as e:
                return ToolResult.error(f"Failed to create Spark Ads: {e}")
        else:
            return ToolResult.ok({"spark_ad_id": "test_spark_ad"})


class TikTokGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                report = self.client.get_report(
                    account_id=advertiser_id,
                    date_range=input_data.get("date_range"),
                )
                return ToolResult.ok({"report": report})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok report: {e}")
        else:
            return ToolResult.ok({
                "metrics": {
                    "impressions": 125000,
                    "clicks": 3200,
                    "spend": 480.50,
                    "ctr": 0.0256,
                    "conversions": 48,
                }
            })


# ═══════════════════════════════════════════════════════════════
# TikTok Capability
# ═══════════════════════════════════════════════════════════════

class TikTokCapability(BaseCapability):
    platform_name = "tiktok"
    
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        
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
        ), TikTokListCampaignsHandler(self._api_client)))
        
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
        ), TikTokGetCampaignHandler(self._api_client)))
        
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
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "campaign"],
        ), TikTokCreateCampaignHandler(self._api_client)))
        
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
        ), TikTokListAdGroupsHandler(self._api_client)))
        
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
        ), TikTokGetAdGroupHandler(self._api_client)))
        
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
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "adgroup"],
        ), TikTokCreateAdGroupHandler(self._api_client)))
        
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
        ), TikTokListAdsHandler(self._api_client)))
        
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
        ), TikTokGetAdHandler(self._api_client)))
        
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
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "ad"],
        ), TikTokCreateAdHandler(self._api_client)))
        
        # Get Campaign Report
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
        ), TikTokGetReportHandler(self._api_client)))
        
        return tools
    
    def _get_campaign_tool_sequence(self):
        return ["tiktok_create_campaign", "tiktok_create_adgroup", "tiktok_create_ad"]
    
    def _get_report_tool_sequence(self):
        return ["tiktok_get_campaign_report"]


def create_tiktok_capability(api_client: Optional[TikTokAPIClient] = None) -> TikTokCapability:
    return TikTokCapability(api_client)
