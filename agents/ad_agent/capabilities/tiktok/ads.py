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

logger = logging.getLogger(__name__)


class TikTokListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("adgroup_id")
        if self.client and adgroup_id:
            try:
                ads = self.client.list_ads(adgroup_id)
                return ToolResult.ok({"ads": ads})
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok ads: {e}")
        else:
            return ToolResult.ok({"ads": []})


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
            return ToolResult.ok({
                "id": ad_id,
                "name": "Test Ad",
                "status": "ENABLED",
            })


class TikTokCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("adgroup_id")
        if self.client and adgroup_id:
            try:
                ad_id = self.client.create_ad(
                    adgroup_id=adgroup_id,
                    name=input_data.get("name"),
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "name": input_data.get("name"),
                    "status": "ENABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok ad: {e}")
        else:
            return ToolResult.ok({
                "ad_id": f"ad_{adgroup_id}",
                "name": input_data.get("name"),
                "status": "ENABLED",
            })
