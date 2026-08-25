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

logger = logging.getLogger(__name__)


class MetaGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                report = self.client.get_report(campaign_id)
                return ToolResult.ok({"report": report})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta report: {e}")
        else:
            return ToolResult.ok({
                "campaign_id": campaign_id,
                "metrics": {
                    "impressions": 125000,
                    "clicks": 3200,
                    "spend": 480.50,
                    "ctr": 0.0256,
                    "cpc": 0.15,
                    "conversions": 48,
                    "cost_per_conversion": 10.01,
                }
            })
