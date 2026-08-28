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
from ..base import call_with_optional_page_size

logger = logging.getLogger(__name__)


class TikTokListAdGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and ctx.account_id and campaign_id:
            try:
                adgroups = call_with_optional_page_size(
                    self.client.list_adgroups,
                    ctx.account_id,
                    campaign_id,
                    limit=input_data.get("limit", 20),
                    parameter_names=("page_size", "limit"),
                )
                return ToolResult.ok({"adgroups": adgroups, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok adgroups: {e}")
        else:
            return ToolResult.ok({"adgroups": []})


class TikTokGetAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("adgroup_id")
        campaign_id = input_data.get("campaign_id")
        if self.client and ctx.account_id and campaign_id and adgroup_id:
            try:
                adgroup = self.client.get_adgroup(
                    ctx.account_id, campaign_id, adgroup_id
                )
                return ToolResult.ok({"adgroup": adgroup, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok adgroup: {e}")
        else:
            return ToolResult.ok({
                "adgroup": {
                    "id": adgroup_id,
                    "name": "Test AdGroup",
                    "status": "ENABLED",
                },
                "data_status": "offline_no_client",
                "simulated": True,
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
