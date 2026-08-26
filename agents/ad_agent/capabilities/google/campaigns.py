"""
capabilities/google/campaigns.py - Google Campaign 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class GoogleListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        customer_id = ctx.account_id
        if self.client and customer_id:
            try:
                campaigns = self.client.list_campaigns()
                return ToolResult.ok({"campaigns": campaigns})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google campaigns: {e}")
        return ToolResult.error("Google Ads client not configured or customer_id missing")


class GoogleGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client:
            try:
                campaign = self.client.get_campaign(campaign_id)
                return ToolResult.ok({"campaign": campaign})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google campaign: {e}")
        return ToolResult.error("Google Ads client not configured")


class GoogleCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        customer_id = ctx.account_id
        if self.client and customer_id:
            try:
                campaign_id = self.client.create_campaign(
                    customer_id=customer_id,
                    campaign=input_data,
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("campaign_name"),
                    "status": "ENABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Google campaign: {e}")
        return ToolResult.error("Google Ads client not configured or customer_id missing")
