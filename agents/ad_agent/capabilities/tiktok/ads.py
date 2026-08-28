"""
capabilities/tiktok/ads.py - TikTok Ad 相关 Handler
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


class TikTokListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("adgroup_id")
        if self.client and ctx.account_id and adgroup_id:
            try:
                ads = call_with_optional_page_size(
                    self.client.list_ads,
                    ctx.account_id,
                    adgroup_id,
                    limit=input_data.get("limit", 20),
                    parameter_names=("page_size", "limit"),
                )
                return ToolResult.ok({"ads": ads, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok ads: {e}")
        else:
            return ToolResult.ok({
                "ads": [],
                "account_id": ctx.account_id,
                "data_status": "offline_no_client",
                "simulated": True,
            })


class TikTokGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get("ad_id")
        adgroup_id = input_data.get("adgroup_id")
        if self.client and ctx.account_id and adgroup_id and ad_id:
            try:
                ad = self.client.get_ad(ctx.account_id, adgroup_id, ad_id)
                return ToolResult.ok({"ad": ad, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok ad: {e}")
        else:
            return ToolResult.ok({
                "ad": {
                    "id": ad_id,
                    "name": "Test Ad",
                    "status": input_data.get("status", 1),
                },
                "data_status": "offline_no_client",
                "simulated": True,
            })


class TikTokCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("adgroup_id")
        if self.client and ctx.account_id and adgroup_id and input_data.get("campaign_id"):
            try:
                ad_id = self.client.create_ad(
                    advertiser_id=ctx.account_id,
                    campaign_id=input_data.get("campaign_id"),
                    adgroup_id=adgroup_id,
                    ad=input_data,
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "name": input_data.get("name"),
                    "status": input_data.get("status", 1),
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok ad: {e}")
        else:
            return ToolResult.error("TikTok client not configured or advertiser_id/campaign_id/adgroup_id missing")
