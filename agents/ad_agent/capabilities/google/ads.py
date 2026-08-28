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
from ._utils import for_customer
from ..base import call_with_optional_page_size

logger = logging.getLogger(__name__)


class GoogleListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_group_id = input_data.get("ad_group_id")
        if self.client and ctx.account_id and ad_group_id:
            try:
                client = for_customer(self.client, ctx.account_id)
                ads = call_with_optional_page_size(
                    client.list_ads,
                    ad_group_id,
                    limit=input_data.get("limit", 100),
                    parameter_names=("page_size", "limit"),
                )
                return ToolResult.ok({"ads": ads, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google ads: {e}")
        else:
            return ToolResult.ok({
                "ads": [],
                "account_id": ctx.account_id,
                "data_status": "offline_no_client",
                "simulated": True,
            })


class GoogleGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get("ad_id")
        if self.client:
            try:
                client = for_customer(self.client, ctx.account_id)
                ad = client.get_ad(ad_id)
                return ToolResult.ok({"ad": ad, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google ad: {e}")
        else:
            return ToolResult.ok({
                "ad": {
                    "id": ad_id,
                    "name": "Test Ad",
                    "status": "PAUSED",
                },
                "data_status": "offline_no_client",
                "simulated": True,
            })


class GoogleCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_group_id = input_data.get("ad_group_id")
        if self.client and ad_group_id:
            try:
                client = for_customer(self.client, ctx.account_id)
                final_url = input_data.get("final_url") or input_data.get("landing_page_url")
                if not final_url:
                    raise ValueError("Google Search Ad requires final_url")
                ad_id = client.create_search_ad(
                    ad_group_id=ad_group_id,
                    headlines=input_data.get("headlines") or [input_data.get("name", "Ad")],
                    descriptions=input_data.get("descriptions") or [input_data.get("description", "")],
                    final_url=final_url,
                    ad_type=input_data.get("ad_type"),
                    path1=input_data.get("path1"),
                    path2=input_data.get("path2"),
                    responsive_search_ad=input_data.get("responsive_search_ad"),
                    status=input_data.get("status"),
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "name": input_data.get("name"),
                    "status": input_data.get("status", "PAUSED"),
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Google ad: {e}")
        else:
            return ToolResult.error("Google Ads client not configured or customer_id/ad_group_id missing")
