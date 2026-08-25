"""
capabilities/meta/ads.py - Meta Ad 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.meta_client import MetaAPIClient

logger = logging.getLogger(__name__)


class MetaListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client and adset_id:
            try:
                ads = self.client.list_ads(adset_id)
                return ToolResult.ok({"ads": ads})
            except Exception as e:
                return ToolResult.error(f"Failed to list Meta ads: {e}")
        else:
            return ToolResult.ok({"ads": []})


class MetaGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get("ad_id")
        if self.client:
            try:
                ad = self.client.get_ad(ad_id)
                return ToolResult.ok({"ad": ad})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta ad: {e}")
        else:
            return ToolResult.ok({
                "id": ad_id,
                "name": "Test Ad",
                "status": "ACTIVE",
            })


class MetaCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client and adset_id:
            try:
                ad_id = self.client.create_ad(
                    adset_id=adset_id,
                    name=input_data.get("name"),
                    creative=input_data.get("creative", {}),
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "name": input_data.get("name"),
                    "status": "ACTIVE",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Meta ad: {e}")
        else:
            return ToolResult.ok({
                "ad_id": f"act_{adset_id}_ad",
                "name": input_data.get("name"),
                "status": "ACTIVE",
            })
