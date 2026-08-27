"""
capabilities/dv360/reports.py - DV360 报表相关 Handler
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


class DV360GetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        line_item_id = input_data.get("line_item_id")
        if self.client and ctx.account_id and line_item_id:
            try:
                report = self.client.get_line_item_report(
                    ctx.account_id,
                    line_item_id,
                    date_from=input_data.get("date_from"),
                    date_to=input_data.get("date_to"),
                )
                return ToolResult.ok({"report": report})
            except Exception as e:
                return ToolResult.error(f"Failed to get DV360 report: {e}")
        elif not self.client:
            return ToolResult.ok({
                "metrics": {
                    "impressions": 125000,
                    "clicks": 3200,
                    "spend": 480.50,
                }
            })
        return ToolResult.error("DV360 report requires line_item_id; campaign-level adapter is not enabled")


class DV360GetLineItemReportHandler(ToolHandler):
    """Verified DV360 report seam for the supported Line Item scope."""

    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        line_item_id = input_data.get("line_item_id")
        if self.client and ctx.account_id and line_item_id:
            try:
                date_from, date_to = self._resolve_dates(input_data)
                report = self.client.get_line_item_report(
                    ctx.account_id,
                    str(line_item_id),
                    date_from=date_from,
                    date_to=date_to,
                )
                return ToolResult.ok({"report": report, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to get DV360 line item report: {exc}")
        if not self.client:
            return ToolResult.ok({
                "report": [],
                "data_status": "offline_no_client",
                "simulated": True,
            })
        return ToolResult.error("DV360 line item report requires line_item_id and advertiser account")

    @staticmethod
    def _resolve_dates(input_data: dict) -> Tuple[Optional[str], Optional[str]]:
        """Normalize Runtime date ranges to the client's ISO-date contract."""
        date_from = input_data.get("date_from")
        date_to = input_data.get("date_to")
        date_range = input_data.get("date_range")
        if isinstance(date_range, dict):
            date_from = date_from or date_range.get("start_date")
            date_to = date_to or date_range.get("end_date")
        elif isinstance(date_range, str):
            # Programmatic callers do not necessarily pass through the rule
            # parser, so normalize the same preset vocabulary here as well.
            date_from = date_from or date_range
            date_to = date_to or "TODAY"

        # The DV360 report API needs concrete dates. Resolve the one supported
        # relative form locally; never pass a Google/TikTok preset through as
        # if it were an ISO date.
        date_from_text = str(date_from or "")
        date_to_text = str(date_to or "")
        today = date.today()
        match = re.fullmatch(r"LAST_(\d+)_DAYS", date_from_text, re.IGNORECASE)
        if match:
            days = max(int(match.group(1)), 1)
            end = today
            return (
                (end - timedelta(days=days - 1)).isoformat(),
                end.isoformat() if date_to_text.upper() in {"", "TODAY"} else date_to,
            )
        if date_from_text.upper() == "TODAY":
            date_from = today.isoformat()
        elif date_from_text.upper() == "YESTERDAY":
            date_from = (today - timedelta(days=1)).isoformat()
        elif date_from_text.upper() == "THIS_MONTH":
            date_from = today.replace(day=1).isoformat()
        if date_to_text.upper() == "TODAY":
            date_to = today.isoformat()
        elif date_to_text.upper() == "YESTERDAY":
            date_to = (today - timedelta(days=1)).isoformat()
        elif date_to_text.upper() == "THIS_MONTH":
            date_to = today.replace(day=1).isoformat()
        return date_from, date_to
