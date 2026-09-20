"""
tools/providers/tiktok/campaigns.py - TikTok Campaign 相关 Handler
"""
import logging
from typing import Optional
from ....core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ....api_clients.tiktok_client import TikTokAPIClient
from ..provider_base import call_with_optional_page_size

logger = logging.getLogger(__name__)


class TikTokListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaigns = call_with_optional_page_size(
                    self.client.list_campaigns,
                    advertiser_id,
                    limit=input_data.get("limit", 20),
                    parameter_names=("page_size", "limit"),
                )
                return ToolResult.ok({
                    "campaigns": campaigns,
                    "account_id": advertiser_id,
                    "data_status": "live",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to list TikTok campaigns: {e}")
        # Runtime decides whether this explicitly simulated fixture may be
        # exposed; the Handler itself reports that no Provider Client exists.
        return ToolResult.ok({
            "campaigns": [
                {"id": "30001", "campaign_name": "Test TikTok Campaign", "status": "ACTIVE",
                 "daily_budget": 150.0, "objective": "PRODUCT_SALES"},
            ],
            "account_id": advertiser_id,
            "data_status": "offline_no_client",
            "simulated": True,
        })


class TikTokGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        campaign_name = input_data.get("campaign_name")
        advertiser_id = ctx.account_id

        if not campaign_id and campaign_name:
            try:
                if self.client and advertiser_id:
                    campaigns = call_with_optional_page_size(
                        self.client.list_campaigns,
                        advertiser_id,
                        limit=input_data.get("limit", 20),
                        parameter_names=("page_size", "limit"),
                    )
                    name_lower = campaign_name.lower()
                    for c in campaigns:
                        cname = (
                            c.get("name")
                            or c.get("campaign_name")
                            or ""
                        ).lower()
                        if cname == name_lower or name_lower in cname or cname in name_lower:
                            campaign_id = str(
                                c.get("id") or c.get("campaign_id") or ""
                            )
                            break
                if not campaign_id:
                    return ToolResult.error(f"未找到名为 '{campaign_name}' 的 Campaign，请先列出 Campaign 列表获取准确 ID")
            except Exception as e:
                return ToolResult.error(f"查找 Campaign 失败: {e}")

        if self.client and campaign_id:
            try:
                campaign = self.client.get_campaign(advertiser_id, campaign_id)
                return ToolResult.ok({
                    "campaign": campaign,
                    "account_id": advertiser_id,
                    "data_status": "live",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok campaign: {e}")
        return ToolResult.ok({
            "campaign": {
                "id": campaign_id or "mock_id",
                "name": campaign_name or "Mock Campaign",
                "status": "ACTIVE",
                "daily_budget": 150.0,
                "objective": "PRODUCT_SALES",
            },
            "account_id": advertiser_id,
            "data_status": "offline_no_client",
            "simulated": True,
        })


class TikTokCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaign_id = self.client.create_campaign(
                    advertiser_id=advertiser_id,
                    campaign=input_data,
                    live=str(ctx.metadata.get("execution_mode", "dry_run")) == "live",
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("name"),
                    "status": input_data.get("status", 0),
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create TikTok campaign: {e}")
        return ToolResult.error("TikTok client not configured or account_id missing")
