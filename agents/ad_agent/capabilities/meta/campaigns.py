"""
capabilities/meta/campaigns.py - Meta Campaign 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.meta_client import MetaAPIClient

logger = logging.getLogger(__name__)


class MetaListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if self.client and account_id:
            try:
                campaigns = self.client.list_campaigns(account_id)
                return ToolResult.ok({"campaigns": campaigns})
            except Exception as e:
                return ToolResult.error(f"Failed to list Meta campaigns: {e}")
        else:
            return ToolResult.ok({
                "campaigns": [
                    {"id": "act_2806375919473667_101", "name": "Test Campaign 1", "status": "ACTIVE", "objective": "OUTCOME_SALES"},
                    {"id": "act_2806375919473667_102", "name": "Test Campaign 2", "status": "PAUSED", "objective": "OUTCOME_TRAFFIC"},
                ],
            })


class MetaGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client:
            try:
                campaign = self.client.get_campaign(campaign_id)
                return ToolResult.ok({"campaign": campaign})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta campaign: {e}")
        else:
            return ToolResult.ok({
                "id": campaign_id,
                "name": "Test Campaign",
                "status": "ACTIVE",
            })


class MetaCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if self.client and account_id:
            try:
                campaign_id = self.client.create_campaign(
                    account_id=account_id,
                    name=input_data.get("name"),
                    objective=input_data.get("objective", "OUTCOME_SALES"),
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("name"),
                    "status": "ACTIVE",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Meta campaign: {e}")
        else:
            return ToolResult.ok({
                "campaign_id": f"meta_{input_data.get('name', 'unknown')}",
                "name": input_data.get("name"),
                "status": "ACTIVE",
            })
