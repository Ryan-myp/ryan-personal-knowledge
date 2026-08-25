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
        else:
            return ToolResult.ok({
                "campaigns": [
                    {"id": "test_campaign_1", "name": "Test Campaign 1", "status": "ENABLED", "budget": 100},
                    {"id": "test_campaign_2", "name": "Test Campaign 2", "status": "PAUSED", "budget": 50},
                ],
            })


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
        else:
            return ToolResult.ok({
                "id": campaign_id,
                "name": "Test Campaign",
                "status": "ENABLED",
            })


class GoogleCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        customer_id = ctx.account_id
        if self.client and customer_id:
            try:
                campaign_id = self.client.create_campaign(
                    customer_id=customer_id,
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
