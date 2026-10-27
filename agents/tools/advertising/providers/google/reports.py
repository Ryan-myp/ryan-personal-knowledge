"""
tools/providers/google/reports.py - Google 报表相关 Handler
"""
import logging
from typing import Optional
from agents.agent_harness.core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from agents.tools.advertising.clients.google_ads_client import GoogleAdsAPIClient
from agents.tools.advertising.shared.domain.reporting import build_report_context
from ._utils import for_customer

logger = logging.getLogger(__name__)


class GoogleGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        customer_id = ctx.account_id
        if self.client and customer_id:
            try:
                client = for_customer(self.client, customer_id)
                campaign_ids = input_data.get("campaign_ids", [])
                start_date = input_data.get("start_date")
                end_date = input_data.get("end_date")
                date_range = input_data.get("date_range", "LAST_30_DAYS")
                if bool(start_date) != bool(end_date):
                    return ToolResult.error(
                        "Both start_date and end_date are required for an explicit range"
                    )
                report_options = {}
                if "limit" in input_data:
                    report_options["limit"] = input_data["limit"]
                report = client.get_campaign_report(
                    campaign_ids=campaign_ids,
                    date_from=start_date or date_range,
                    date_to=end_date or "TODAY",
                    **report_options,
                )
                # 返回结构化的报表数据
                return ToolResult.ok({
                    "report": report,
                    "summary": self._summarize_report(report),
                    "report_context": self._build_report_context(
                        input_data, report, date_range, end_date
                    ),
                    "data_status": "live",
                })
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
                },
                "summary": "Mock data for testing",
                "data_status": "offline_no_client",
                "simulated": True,
            })

    @staticmethod
    def _build_report_context(
        input_data: dict,
        report: list,
        date_range: str,
        end_date: Optional[str],
    ) -> dict:
        return build_report_context(
            provider="google-ads",
            resource_level="campaign",
            input_data=input_data,
            rows=report,
            default_period={
                "start": date_range,
                "end": end_date or "TODAY",
            },
            default_limit=1000,
        )
    
    def _summarize_report(self, report: list) -> dict:
        """汇总报表数据"""
        if not report:
            return {
                "total_impressions": None,
                "total_clicks": None,
                "total_spend": None,
                "total_conversions": None,
                "campaign_count": 0,
            }
        
        def metrics(row):
            return row.get('metrics', {}) or row.get('campaign', {}).get('metrics', {})

        total_impressions = sum(metrics(r).get('impressions', 0) or 0 for r in report)
        total_clicks = sum(metrics(r).get('clicks', 0) or 0 for r in report)
        total_spend = sum(metrics(r).get('cost_micros', 0) or 0 for r in report) / 1_000_000
        total_conversions = sum(metrics(r).get('conversions', 0) or 0 for r in report)
        
        return {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_spend": round(total_spend, 2),
            "total_conversions": total_conversions,
            "campaign_count": len(report)
        }
