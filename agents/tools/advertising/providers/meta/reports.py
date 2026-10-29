"""
tools/providers/meta/reports.py - Meta 报表相关 Handler
"""
import logging
from typing import Optional
from agents.agent_harness.core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from agents.tools.advertising.clients.meta_client import MetaAPIClient
from agents.tools.advertising.shared.domain.reporting import build_report_context

logger = logging.getLogger(__name__)


class MetaGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        try:
            statuses = MetaAPIClient.normalize_report_statuses(input_data.get("effective_status"))
            time_range = input_data.get("date_range") or input_data.get("date_preset")
            if time_range is not None and not isinstance(time_range, dict):
                time_range = MetaAPIClient.normalize_report_preset(time_range)
        except ValueError as error:
            return ToolResult.error(str(error))
        campaign_id = input_data.get("campaign_id")
        campaign_ids = input_data.get("campaign_ids") or ([campaign_id] if campaign_id else [])
        if self.client and ctx.account_id:
            try:
                report_options = {}
                if "limit" in input_data:
                    report_options["limit"] = input_data["limit"]
                if "time_increment" in input_data:
                    report_options["time_increment"] = input_data["time_increment"]
                if statuses is not None:
                    report_options["effective_status"] = statuses
                report = self.client.get_campaign_report(
                    ctx.account_id,
                    campaign_ids,
                    time_range=time_range,
                    **report_options,
                )
                return ToolResult.ok({
                    "report": report,
                    "report_context": self._context(input_data, report, executed=True),
                    "data_status": "live",
                })
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
                **({"report_context": self._context(input_data, [], executed=False)}
                   if statuses else {}),
            })

    @staticmethod
    def _context(input_data: dict, rows: list, *, executed: bool) -> dict:
        context = build_report_context(
            provider="meta", resource_level="campaign", input_data=input_data,
            rows=rows, default_period="last_7d", default_limit=1000,
        )
        if input_data.get("effective_status") is not None:
            context["filters"] = {
                "effective_status": list(input_data["effective_status"]),
                "status_basis": "current_campaign_effective_status",
            }
            context["filters_executed"] = executed
        return context
