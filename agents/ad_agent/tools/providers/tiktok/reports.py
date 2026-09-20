"""
tools/providers/tiktok/reports.py - TikTok 报表相关 Handler
"""
import logging
from typing import Optional
from ....core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ....api_clients.tiktok_client import TikTokAPIClient

logger = logging.getLogger(__name__)


class TikTokGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if self.client and account_id:
            try:
                campaign_ids = input_data.get("campaign_ids") or []
                # get_report() is account-level. Use the campaign report API
                # whenever a comparison supplies campaign IDs.
                if campaign_ids and hasattr(self.client, "get_campaign_report"):
                    date_range = input_data.get("date_range")
                    report = self.client.get_campaign_report(
                        advertiser_id=account_id,
                        campaign_ids=campaign_ids,
                        time_range=date_range,
                    )
                else:
                    date_range = input_data.get("date_range")
                    report = self.client.get_report(
                        advertiser_id=account_id,
                        date_preset=(
                            date_range
                            if isinstance(date_range, str) and date_range
                            else "LAST_7_DAYS"
                        ),
                        time_range=date_range if isinstance(date_range, dict) else None,
                    )
                return ToolResult.ok({"report": report, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get TikTok report: {e}")
        else:
            return ToolResult.ok({
                "metrics": {
                    "impressions": 125000,
                    "clicks": 3200,
                    "spend": 480.50,
                    "ctr": 0.0256,
                    "conversions": 48,
                },
                "data_status": "offline_no_client",
                "simulated": True,
            })
