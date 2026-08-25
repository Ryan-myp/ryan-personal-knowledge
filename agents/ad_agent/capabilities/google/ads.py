"""
capabilities/google/ads.py - Google Ad 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class GoogleListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_group_id = input_data.get("ad_group_id")
        if self.client and ad_group_id:
            try:
                ads = self.client.list_ads(ad_group_id)
                return ToolResult.ok({"ads": ads})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google ads: {e}")
        else:
            return ToolResult.ok({"ads": []})


class GoogleGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get("ad_id")
        if self.client:
            try:
                ad = self.client.get_ad(ad_id)
                return ToolResult.ok({"ad": ad})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google ad: {e}")
        else:
            return ToolResult.ok({
                "id": ad_id,
                "name": "Test Ad",
                "status": "ENABLED",
            })


class GoogleCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_group_id = input_data.get("ad_group_id")
        if self.client and ad_group_id:
            try:
                ad_id = self.client.create_ad(
                    ad_group_id=ad_group_id,
                    name=input_data.get("name"),
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "name": input_data.get("name"),
                    "status": "ENABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Google ad: {e}")
        else:
            return ToolResult.ok({
                "ad_id": f"ad_{ad_group_id}",
                "name": input_data.get("name"),
                "status": "ENABLED",
            })
