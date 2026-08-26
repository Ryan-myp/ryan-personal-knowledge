"""
capabilities/tiktok/campaigns.py - TikTok Campaign 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.tiktok_client import TikTokAPIClient

logger = logging.getLogger(__name__)


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
        return ToolResult.error("TikTok client not configured or account_id missing")


class TikTokGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client:
            try:
                campaign = self.client.get_campaign(ctx.account_id, campaign_id)
                return ToolResult.ok({"campaign": campaign})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok campaign: {e}")
        return ToolResult.error("TikTok client not configured")


class TikTokCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaign_id = self.client.create_campaign(
                    advertiser_id=advertiser_id,
                    campaign=input_data,
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("name"),
                    "status": "DISABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok campaign: {e}")
        return ToolResult.error("TikTok client not configured or account_id missing")
