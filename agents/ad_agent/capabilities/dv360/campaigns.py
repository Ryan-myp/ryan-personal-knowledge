"""
capabilities/dv360/campaigns.py - DV360 Campaign 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


class DV360ListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaigns = self.client.list_campaigns(advertiser_id)
                return ToolResult.ok({"campaigns": campaigns})
            except Exception as e:
                return ToolResult.error(f"Failed to list DV360 campaigns: {e}")
        else:
            return ToolResult.ok({"campaigns": []})


class DV360GetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client:
            try:
                campaign = self.client.get_campaign(campaign_id)
                return ToolResult.ok({"campaign": campaign})
            except Exception as e:
                return ToolResult.error(f"Failed to get DV360 campaign: {e}")
        else:
            return ToolResult.ok({
                "id": campaign_id,
                "name": "Test Campaign",
                "status": "ACTIVE",
            })


class DV360CreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaign_id = self.client.create_campaign(
                    advertiser_id=advertiser_id,
                    name=input_data.get("name"),
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("name"),
                    "status": "DRAFT",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create DV360 campaign: {e}")
        else:
            return ToolResult.ok({
                "campaign_id": "dv360_campaign_1",
                "name": input_data.get("name"),
                "status": "DRAFT",
            })
