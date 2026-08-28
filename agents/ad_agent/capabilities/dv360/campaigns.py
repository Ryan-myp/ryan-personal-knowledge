"""
capabilities/dv360/campaigns.py - DV360 Campaign 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


class DV360ListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaigns = self.client.list_campaigns(advertiser_id)
                return ToolResult.ok({
                    "campaigns": campaigns,
                    "account_id": advertiser_id,
                    "data_status": "live",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to list DV360 campaigns: {e}")
        else:
            return ToolResult.ok({
                "campaigns": [],
                "data_status": "offline_no_client",
                "simulated": True,
            })


class DV360GetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        campaign_name = input_data.get("campaign_name")
        advertiser_id = ctx.account_id

        if not campaign_id and campaign_name:
            try:
                if self.client and advertiser_id:
                    campaigns = self.client.list_campaigns(advertiser_id)
                    name_lower = campaign_name.lower()
                    for c in campaigns:
                        cname = (c.get("name") or "").lower()
                        if cname == name_lower or name_lower in cname or cname in name_lower:
                            campaign_id = str(c.get("id", ""))
                            break
                if not campaign_id:
                    return ToolResult.ok({"campaign": {"id": campaign_id, "name": campaign_name, "status": "UNKNOWN", "message": f"未找到名为 '{campaign_name}' 的 Campaign"}})
            except Exception:
                pass

        if self.client and campaign_id:
            try:
                campaign = self.client.get_campaign(advertiser_id, campaign_id)
                return ToolResult.ok({"campaign": campaign, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get DV360 campaign: {e}")
        return ToolResult.ok({
            "campaign": {
                "id": campaign_id or "mock_id",
                "name": campaign_name or "Mock Campaign",
                "status": "ACTIVE",
            },
            "data_status": "offline_no_client",
            "simulated": True,
        })


class DV360CreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            # DV360 API Client 当前未提供 Campaign create 适配器；在 live 模式
            # 下明确拒绝，避免把不存在的方法当成已支持能力。
            return ToolResult.error("DV360 Campaign live create adapter is not enabled")
        else:
            return ToolResult.ok({
                "campaign_id": "dv360_campaign_1",
                "name": input_data.get("name"),
                "status": "DRAFT",
            })
