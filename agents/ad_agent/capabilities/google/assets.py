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
from ._utils import for_customer

logger = logging.getLogger(__name__)


class GoogleListAssetGroupsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                client = for_customer(self.client, ctx.account_id)
                asset_groups = client.list_asset_groups(campaign_id)
                return ToolResult.ok({"asset_groups": asset_groups, "data_status": "live"})
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
                client = for_customer(self.client, ctx.account_id)
                asset_group = client.get_asset_group(asset_group_id)
                return ToolResult.ok({"asset_group": asset_group, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google asset group: {e}")
        else:
            return ToolResult.ok({
                "asset_group": {
                    "id": asset_group_id,
                    "name": "Test Asset Group",
                    "status": "PAUSED",
                },
                "data_status": "offline_no_client",
                "simulated": True,
            })


class GoogleCreateAssetGroupHandler(ToolHandler):
    """Create a PMax Asset Group plan.

    The current Google client exposes only a placeholder adapter for this
    multi-step Google Ads operation.  Runtime therefore intercepts this write
    in dry-run mode and blocks it in live mode until a verified adapter is
    explicitly approved.
    """

    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if not self.client:
            return ToolResult.error("Google Ads client not configured")
        creator = getattr(self.client, "create_pmax_asset_group", None)
        if not creator:
            return ToolResult.error("Google PMax Asset Group adapter is unavailable")
        try:
            asset_group_id = creator(
                campaign_id=input_data["campaign_id"],
                name=input_data["name"],
                headlines=input_data.get("headlines", []),
                descriptions=input_data.get("descriptions", []),
                images=input_data.get("images", []),
                videos=input_data.get("videos", []),
            )
            return ToolResult.ok({
                "asset_group_id": asset_group_id,
                "name": input_data.get("name"),
                "status": "PAUSED",
            })
        except Exception as exc:
            return ToolResult.error(f"Failed to create Google asset group: {exc}")
