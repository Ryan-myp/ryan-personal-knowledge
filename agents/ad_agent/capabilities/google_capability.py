"""
capabilities/google_capability.py - Google Ads Capability（真实 API 版）

Google Ads API Handler 实现：Campaign/Ad Group/Ad/Asset 全层级管理
"""

import logging
from typing import Optional
from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from .base import BaseCapability

from ..api_clients.google_ads_client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Google Ads Handler
# ═══════════════════════════════════════════════════════════════

class GoogleListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                campaigns = self.client.list_campaigns()
                return ToolResult.ok({"campaigns": campaigns})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google campaigns: {e}")
        else:
            return ToolResult.ok({
                "campaigns": [
                    {"id": "test_campaign_1", "name": "Test Campaign 1", "status": "ENABLED", "budget": 100},
                    {"id": "test_campaign_2", "name": "Test Campaign 2", "status": "PAUSED", "budget": 50},
                ],
            })


class GoogleCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                campaign_id = self.client.create_campaign(
                    name=input_data.get("campaign_name", "Untitled"),
                    advertising_channel_type=input_data.get("advertising_channel_type", "SEARCH"),
                    bidding_strategy=input_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
                    daily_budget=input_data.get("budget", 100),
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("campaign_name"),
                    "status": "ENABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Google campaign: {e}")
        else:
            return ToolResult.ok({
                "campaign_id": "test_campaign_new",
                "name": input_data.get("campaign_name"),
                "status": "ENABLED",
            })


class GoogleCreateAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                ad_group_id = self.client.create_ad_group(
                    campaign_id=input_data.get("campaign_id"),
                    name=input_data.get("name"),
                    cpc_bid=input_data.get("cpc_bid"),
                )
                return ToolResult.ok({"ad_group_id": ad_group_id})
            except Exception as e:
                return ToolResult.error(f"Failed to create Google ad group: {e}")
        else:
            return ToolResult.ok({"ad_group_id": "test_ad_group"})


class GoogleCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                ad_id = self.client.create_ad(
                    ad_group_id=input_data.get("ad_group_id"),
                    name=input_data.get("name"),
                )
                return ToolResult.ok({"ad_id": ad_id})
            except Exception as e:
                return ToolResult.error(f"Failed to create Google ad: {e}")
        else:
            return ToolResult.ok({"ad_id": "test_ad"})


class GoogleGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                report = self.client.get_campaign_report(
                    customer_id=ctx.account_id,
                    date_range=input_data.get("date_range"),
                )
                return ToolResult.ok({"report": report})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google report: {e}")
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


class GoogleGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                campaign = self.client.get_campaign(input_data.get("campaign_id"))
                return ToolResult.ok({"campaign": campaign})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google campaign: {e}")
        else:
            return ToolResult.ok({
                "id": input_data.get("campaign_id"),
                "name": "Test Campaign",
                "status": "ENABLED",
            })


class GoogleListAdGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                ad_groups = self.client.list_ad_groups(input_data.get("campaign_id"))
                return ToolResult.ok({"ad_groups": ad_groups})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google ad groups: {e}")
        else:
            return ToolResult.ok({"ad_groups": []})


class GoogleGetAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                ad_group = self.client.get_ad_group(input_data.get("ad_group_id"))
                return ToolResult.ok({"ad_group": ad_group})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google ad group: {e}")
        else:
            return ToolResult.ok({"id": input_data.get("ad_group_id"), "name": "Test Ad Group"})


class GoogleListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                ads = self.client.list_ads(input_data.get("ad_group_id"))
                return ToolResult.ok({"ads": ads})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google ads: {e}")
        else:
            return ToolResult.ok({"ads": []})


class GoogleGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                ad = self.client.get_ad(input_data.get("ad_id"))
                return ToolResult.ok({"ad": ad})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google ad: {e}")
        else:
            return ToolResult.ok({"id": input_data.get("ad_id"), "name": "Test Ad"})


class GoogleListAssetGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                asset_groups = self.client.list_asset_groups(input_data.get("campaign_id"))
                return ToolResult.ok({"asset_groups": asset_groups})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google asset groups: {e}")
        else:
            return ToolResult.ok({"asset_groups": []})


class GoogleGetAssetGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                asset_group = self.client.get_asset_group(input_data.get("asset_group_id"))
                return ToolResult.ok({"asset_group": asset_group})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google asset group: {e}")
        else:
            return ToolResult.ok({"id": input_data.get("asset_group_id"), "name": "Test Asset Group"})


# ═══════════════════════════════════════════════════════════════
# Google Capability
# ═══════════════════════════════════════════════════════════════

class GoogleCapability(BaseCapability):
    platform_name = "google-ads"
    
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        
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
        ), GoogleListCampaignsHandler(self._api_client)))
        
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
                    "bidding_strategy": {"type": "string"},
                    "budget": {"type": "number"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "campaign"],
        ), GoogleCreateCampaignHandler(self._api_client)))
        
        # Create Ad Group
        tools.append((ToolDefinition(
            name="google_create_ad_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Ad Group。",
            input_schema=ToolSchema(
                required=["campaign_id", "name"],
                properties={"campaign_id": {"type": "string"}, "name": {"type": "string"}, "cpc_bid": {"type": "number"}},
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "ad_group"],
        ), GoogleCreateAdGroupHandler(self._api_client)))
        
        # Create Ad
        tools.append((ToolDefinition(
            name="google_create_ad",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Ad。",
            input_schema=ToolSchema(
                required=["ad_group_id", "name"],
                properties={"ad_group_id": {"type": "string"}, "name": {"type": "string"}},
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "ad"],
        ), GoogleCreateAdHandler(self._api_client)))
        
        # Get Campaign Report
        tools.append((ToolDefinition(
            name="google_get_campaign_report",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 报表。",
            input_schema=ToolSchema(
                required=["customer_id"],
                properties={"customer_id": {"type": "string"}, "date_range": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), GoogleGetReportHandler(self._api_client)))
        
        # Get Campaign
        tools.append((ToolDefinition(
            name="google_get_campaign",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 详情。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), GoogleGetCampaignHandler(self._api_client)))
        
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
        ), GoogleListAdGroupsHandler(self._api_client)))
        
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
        ), GoogleGetAdGroupHandler(self._api_client)))
        
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
        ), GoogleListAdsHandler(self._api_client)))
        
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
        ), GoogleGetAdHandler(self._api_client)))
        
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
        ), GoogleListAssetGroupsHandler(self._api_client)))
        
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
        ), GoogleGetAssetGroupHandler(self._api_client)))
        
        return tools
    
    def _get_campaign_tool_sequence(self):
        return ["google_create_campaign", "google_create_ad_group", "google_create_ad"]
    
    def _get_report_tool_sequence(self):
        return ["google_get_campaign_report"]


def create_google_capability(api_client: Optional[GoogleAdsAPIClient] = None) -> GoogleCapability:
    return GoogleCapability(api_client)
