"""
capabilities/google/assets.py - Google Asset（PMax）相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class GoogleListAssetGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                asset_groups = self.client.list_asset_groups(campaign_id)
                return ToolResult.ok({"asset_groups": asset_groups})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google asset groups: {e}")
        else:
            return ToolResult.ok({"asset_groups": []})


class GoogleGetAssetGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        asset_group_id = input_data.get("asset_group_id")
        if self.client:
            try:
                asset_group = self.client.get_asset_group(asset_group_id)
                return ToolResult.ok({"asset_group": asset_group})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google asset group: {e}")
        else:
            return ToolResult.ok({
                "id": asset_group_id,
                "name": "Test Asset Group",
                "status": "ENABLED",
            })
