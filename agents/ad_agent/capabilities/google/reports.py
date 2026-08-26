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
                # 获取 campaign_ids（从 input_data 或默认）
                campaign_ids = input_data.get("campaign_ids", [])
                if not campaign_ids:
                    # 如果没指定，先列出所有 campaigns
                    campaigns = self.client.list_campaigns()
                    campaign_ids = [str(c["id"]) for c in campaigns[:5]]  # 默认前5个
                
                date_range = input_data.get("date_range", "LAST_30_DAYS")
                report = self.client.get_campaign_report(
                    campaign_ids=campaign_ids,
                    date_from=date_range,
                    date_to="TODAY",
                )
                # 返回结构化的报表数据
                return ToolResult.ok({
                    "report": report,
                    "summary": self._summarize_report(report),
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
                "summary": "Mock data for testing"
            })
    
    def _summarize_report(self, report: list) -> dict:
        """汇总报表数据"""
        if not report:
            return {"total_impressions": 0, "total_clicks": 0, "total_spend": 0}
        
        total_impressions = sum(r.get('campaign', {}).get('metrics', {}).get('impressions', 0) or 0 for r in report)
        total_clicks = sum(r.get('campaign', {}).get('metrics', {}).get('clicks', 0) or 0 for r in report)
        total_spend = sum(r.get('campaign', {}).get('metrics', {}).get('cost_micros', 0) or 0 for r in report) / 1_000_000
        
        return {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_spend": round(total_spend, 2),
            "campaign_count": len(report)
        }
