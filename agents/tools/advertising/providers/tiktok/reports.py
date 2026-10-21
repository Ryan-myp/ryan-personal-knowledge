"""
tools/providers/tiktok/reports.py - TikTok 报表相关 Handler
"""
import logging
from typing import Optional
from agents.agent_harness.core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from agents.tools.advertising.shared.domain.reporting import build_report_context

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
                    report_options = {}
                    if "limit" in input_data:
                        report_options["limit"] = input_data["limit"]
                    if "metrics" in input_data:
                        report_options["metrics"] = input_data["metrics"]
                    if "dimensions" in input_data:
                        report_options["dimensions"] = input_data["dimensions"]
                    report = self.client.get_campaign_report(
                        advertiser_id=account_id,
                        campaign_ids=campaign_ids,
                        time_range=date_range,
                        **report_options,
                    )
                else:
                    date_range = input_data.get("date_range")
                    date_preset = input_data.get(
                        "date_preset", "LAST_7_DAYS"
                    )
                    time_range = date_range
                    if isinstance(date_range, str):
                        date_preset = date_range
                        time_range = None
                    report = self.client.get_report(
                        advertiser_id=account_id,
                        report_type=input_data.get("report_type", "BASIC"),
                        service_type=input_data.get("service_type", "AUCTION"),
                        data_level=input_data.get(
                            "data_level", "AUCTION_CAMPAIGN"
                        ),
                        dimensions=input_data.get("dimensions"),
                        metrics=input_data.get("metrics"),
                        date_preset=date_preset,
                        time_range=time_range,
                        filtering=input_data.get("filtering"),
                        limit=input_data.get("limit", 100),
                    )
                return ToolResult.ok({
                    "report": report,
                    "report_context": self._build_report_context(
                        input_data, report
                    ),
                    "data_status": "live",
                })
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

    @staticmethod
    def _build_report_context(input_data: dict, report: list) -> dict:
        data_level = str(
            input_data.get("data_level", "AUCTION_CAMPAIGN")
        ).upper()
        resource_level = {
            "AUCTION_CAMPAIGN": "campaign",
            "AUCTION_ADGROUP": "ad_group",
            "AUCTION_AD": "ad",
        }.get(data_level, "unknown")
        return build_report_context(
            provider="tiktok",
            resource_level=resource_level,
            input_data=input_data,
            rows=report,
            default_period="LAST_7_DAYS",
            default_limit=100,
        )
