"""
capabilities/meta/campaigns.py - Meta Campaign 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.meta_client import MetaAPIClient
from ..base import call_with_optional_page_size

logger = logging.getLogger(__name__)


class MetaListCampaignsHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if self.client and account_id:
            try:
                campaigns = call_with_optional_page_size(
                    self.client.list_campaigns,
                    account_id,
                    limit=input_data.get("limit", 25),
                )
                return ToolResult.ok({
                    "campaigns": campaigns,
                    "account_id": account_id,
                    "data_status": "live",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to list Meta campaigns: {e}")
        # The Handler has no authority to decide that a query is simulated.
        # Runtime may expose this fixture only when offline_mode=True.
        return ToolResult.ok({
            "campaigns": [
                {"id": "10001", "campaign_name": "Test Campaign", "status": "ACTIVE",
                 "daily_budget": 100.0, "objective": "OUTCOME_SALES"},
            ],
            "account_id": account_id,
            "data_status": "offline_no_client",
            "simulated": True,
        })


class MetaGetCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        campaign_name = input_data.get("campaign_name")
        account_id = ctx.account_id

        # 如果只有名称没有 ID，先列出 campaigns 找匹配的
        if not campaign_id and campaign_name:
            try:
                campaigns = (
                    call_with_optional_page_size(
                        self.client.list_campaigns,
                        account_id,
                        limit=input_data.get("limit", 25),
                    )
                    if self.client else []
                )
                name_lower = campaign_name.lower()
                for c in campaigns:
                    cname = (c.get("name") or c.get("campaign_name") or "").lower()
                    if cname == name_lower or name_lower in cname or cname in name_lower:
                        campaign_id = str(c.get("id") or c.get("campaign_id", ""))
                        break
                if not campaign_id:
                    names = [c.get("name") or c.get("campaign_name") for c in campaigns[:5]]
                    return ToolResult.error(
                        f"未找到名为 '{campaign_name}' 的 Campaign。"
                        f"找到的相近 Campaign: {', '.join(names)}"
                        f"，请提供准确 ID 或完整名称。"
                    )
            except Exception as e:
                return ToolResult.error(f"查找 Campaign 失败: {e}")

        if self.client and campaign_id:
            try:
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    account_id, "campaign", campaign_id
                ):
                    return ToolResult.error(
                        f"Campaign {campaign_id} does not belong to account {account_id}"
                    )
                campaign = self.client.get_campaign(campaign_id)
                return ToolResult.ok({
                    "campaign": campaign,
                    "account_id": account_id,
                    "data_status": "live",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta campaign: {e}")
        # Mock fallback
        return ToolResult.ok({
            "campaign": {
                "id": campaign_id or "mock_id",
                "name": campaign_name or "Mock Campaign",
                "status": "ACTIVE",
                "daily_budget": 100.0,
                "objective": "OUTCOME_SALES",
            },
            "account_id": account_id,
            "data_status": "offline_no_client",
            "simulated": True,
        })


class MetaCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if self.client and account_id:
            try:
                campaign_id = self.client.create_campaign(
                    account_id=account_id,
                    campaign=input_data,
                )
                return ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("name"),
                    "status": "ACTIVE",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Meta campaign: {e}")
        return ToolResult.error("Meta client not configured or account_id missing")
