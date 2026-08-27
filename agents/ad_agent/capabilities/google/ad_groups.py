"""
capabilities/google/ad_groups.py - Google Ad Group 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient
from ._utils import for_customer

logger = logging.getLogger(__name__)


class GoogleListAdGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                client = for_customer(self.client, ctx.account_id)
                ad_groups = client.list_ad_groups(campaign_id)
                return ToolResult.ok({"ad_groups": ad_groups})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google ad groups: {e}")
        else:
            return ToolResult.ok({"ad_groups": []})


class GoogleGetAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_group_id = input_data.get("ad_group_id")
        if self.client:
            try:
                client = for_customer(self.client, ctx.account_id)
                ad_group = client.get_ad_group(ad_group_id)
                return ToolResult.ok({"ad_group": ad_group})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google ad group: {e}")
        else:
            return ToolResult.ok({
                "id": ad_group_id,
                "name": "Test Ad Group",
                "status": "ENABLED",
            })


class GoogleCreateAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                client = for_customer(self.client, ctx.account_id)
                ad_group_id = client.create_ad_group(
                    campaign_id=campaign_id,
                    name=input_data.get("name"),
                    cpc_bid_micros=int(float(input_data.get("cpc_bid", 0.5)) * 1_000_000),
                    type=input_data.get("type", "SEARCH_DYNAMIC_ADS"),
                )
                return ToolResult.ok({
                    "ad_group_id": ad_group_id,
                    "name": input_data.get("name"),
                    "status": "ENABLED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Google ad group: {e}")
        else:
            return ToolResult.ok({
                "ad_group_id": f"adgroup_{campaign_id}",
                "name": input_data.get("name"),
                "status": "ENABLED",
            })
