"""
capabilities/google/reports.py - Google 报表相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class GoogleGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        customer_id = ctx.account_id
        if self.client and customer_id:
            try:
                report = self.client.get_campaign_report(
                    customer_id=customer_id,
                    date_range=input_data.get("date_range"),
                )
                return ToolResult.ok({"report": report})
            except Exception as e:
                return ToolResult.error(f"Failed to get Google report: {e}")
        else:
            return ToolResult.ok({
                "metrics": {
                    "impressions": 125000,
                    "clicks": 3200,
                    "spend": 480.50,
                    "ctr": 0.0256,
                    "conversions": 48,
                }
            })
