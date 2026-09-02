"""
capabilities/meta/reports.py - Meta 报表相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.meta_client import MetaAPIClient
from ..base import call_with_optional_page_size

logger = logging.getLogger(__name__)


class MetaGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        campaign_ids = input_data.get("campaign_ids") or ([campaign_id] if campaign_id else [])
        date_preset = input_data.get("date_preset") or input_data.get("date_range")
        if self.client and ctx.account_id:
            try:
                # A natural-language account report normally has no campaign
                # IDs. Resolve the account's campaigns through the same
                # provider client before requesting campaign-scoped insights;
                # never fabricate metrics just because the selector omitted
                # an optional filter.
                if not campaign_ids:
                    campaigns = call_with_optional_page_size(
                        self.client.list_campaigns,
                        ctx.account_id,
                        limit=input_data.get("limit", 25),
                    )
                    campaign_ids = [
                        str(item.get("id") or item.get("campaign_id"))
                        for item in (campaigns or [])
                        if isinstance(item, dict)
                        and (item.get("id") or item.get("campaign_id"))
                    ]
                if not campaign_ids:
                    return ToolResult.ok({
                        "report": [],
                        "campaign_ids": [],
                        "data_status": "live",
                        "summary": "当前账户没有可查询的 Campaign",
                    })
                report = self.client.get_campaign_report(
                    ctx.account_id,
                    campaign_ids,
                    time_range=date_preset,
                )
                return ToolResult.ok({"report": report, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta report: {e}")
        else:
            return ToolResult.ok({
                "campaign_id": campaign_id,
                "campaign_ids": campaign_ids,
                "metrics": {
                    "impressions": 125000,
                    "clicks": 3200,
                    "spend": 480.50,
                    "ctr": 0.0256,
                    "cpc": 0.15,
                    "conversions": 48,
                    "cost_per_conversion": 10.01,
                },
                "data_status": "offline_no_client",
                "simulated": True,
            })
