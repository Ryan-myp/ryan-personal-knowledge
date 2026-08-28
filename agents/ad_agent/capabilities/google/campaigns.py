"""
capabilities/google/campaigns.py - Google Campaign 相关 Handler
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


class GoogleListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        customer_id = ctx.account_id
        if self.client and customer_id:
            try:
                client = for_customer(self.client, customer_id)
                campaigns = client.list_campaigns()
                return ToolResult.ok({"campaigns": campaigns, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to list Google campaigns: {e}")
        # Mock data for testing / offline mode
        return ToolResult.ok({
            "campaigns": [
                {"id": "20001", "campaign_name": "Test Google Campaign", "status": "ENABLED",
                 "daily_budget": 200.0, "objective": "SALES"},
            ],
            "data_status": "offline_mock",
            "simulated": True,
        })


class GoogleGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        campaign_name = input_data.get("campaign_name")
        customer_id = ctx.account_id

        if not campaign_id and campaign_name:
            try:
                if self.client and customer_id:
                    client = for_customer(self.client, customer_id)
                    campaigns = client.list_campaigns()
                    name_lower = campaign_name.lower()
                    for c in campaigns:
                        cname = (c.get("campaign_name") or "").lower()
                        if cname == name_lower or name_lower in cname or cname in name_lower:
                            campaign_id = str(c.get("id", ""))
                            break
                if not campaign_id:
                    return ToolResult.error(f"未找到名为 '{campaign_name}' 的 Campaign，请先列出 Campaign 列表获取准确 ID")
            except Exception as e:
                return ToolResult.error(f"查找 Campaign 失败: {e}")

        if self.client and campaign_id:
            try:
                client = for_customer(self.client, customer_id)
                campaign = client.get_campaign(campaign_id)
                return ToolResult.ok({"campaign": campaign})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google campaign: {e}")
        return ToolResult.ok({
            "campaign": {
                "id": campaign_id or "mock_id",
                "campaign_name": campaign_name or "Mock Campaign",
                "status": "ENABLED",
                "daily_budget": 200.0,
                "objective": "SALES",
            }
        })


class GoogleCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        customer_id = ctx.account_id
        if self.client and customer_id:
            try:
                client = for_customer(self.client, customer_id)
                campaign_id = client.create_campaign(
                    name=input_data.get("campaign_name") or input_data.get("name"),
                    advertising_channel_type=input_data.get("advertising_channel_type", "SEARCH"),
                    bidding_strategy=input_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
                    daily_budget=float(input_data.get("budget", input_data.get("daily_budget", 0))),
                    target_cpa_micros=input_data.get("target_cpa_micros"),
                    target_roas=input_data.get("target_roas"),
                    target_impression_share=input_data.get("target_impression_share"),
                    status=input_data.get("status"),
                    networks=input_data.get("networks"),
                    start_date=input_data.get("start_date"),
                    end_date=input_data.get("end_date"),
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("campaign_name"),
                    # Google Ads mutates are created paused by the client;
                    # report the actual safe initial state in the unified
                    # result instead of claiming the campaign is enabled.
                    "status": "PAUSED",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Google campaign: {e}")
        return ToolResult.error("Google Ads client not configured or customer_id missing")
