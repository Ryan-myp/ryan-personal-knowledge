"""
capabilities/tiktok/ad_groups.py - TikTok Ad Group 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.tiktok_client import TikTokAPIClient

logger = logging.getLogger(__name__)


class TikTokListAdGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and ctx.account_id and campaign_id:
            try:
                adgroups = self.client.list_adgroups(ctx.account_id, campaign_id)
                return ToolResult.ok({"adgroups": adgroups})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok adgroups: {e}")
        else:
            return ToolResult.ok({"adgroups": []})


class TikTokGetAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("adgroup_id")
        if self.client and ctx.account_id and input_data.get("campaign_id"):
            try:
                adgroup = self.client.get_adgroup(
                    ctx.account_id, input_data.get("campaign_id"), adgroup_id
                )
                return ToolResult.ok({"adgroup": adgroup})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok adgroup: {e}")
        else:
            return ToolResult.ok({
                "id": adgroup_id,
                "name": "Test AdGroup",
                "status": "ENABLED",
            })


class TikTokCreateAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                adgroup_id = self.client.create_adgroup(
                    advertiser_id=ctx.account_id,
                    campaign_id=campaign_id,
                    adgroup=input_data,
                )
                return ToolResult.ok({
                    "adgroup_id": adgroup_id,
                    "name": input_data.get("name"),
                    "status": "ENABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok adgroup: {e}")
        else:
            return ToolResult.ok({
                "adgroup_id": f"adgroup_{campaign_id}",
                "name": input_data.get("name"),
                "status": "ENABLED",
            })
