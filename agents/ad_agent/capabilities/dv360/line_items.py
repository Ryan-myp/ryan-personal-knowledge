"""
capabilities/dv360/line_items.py - DV360 Line Item 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


class DV360ListLineItemsHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client and ctx.account_id:
            try:
                items = self.client.list_line_items(
                    ctx.account_id, input_data.get("io_id"), input_data.get("limit", 20)
                )
                return ToolResult.ok({"line_items": items, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to list DV360 line items: {exc}")
        return ToolResult.ok({"line_items": [], "data_status": "offline_no_client", "simulated": True})


class DV360GetLineItemHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        io_id = input_data.get("io_id")
        line_item_id = input_data.get("line_item_id")
        if self.client and ctx.account_id and io_id and line_item_id:
            try:
                item = self.client.get_line_item(ctx.account_id, io_id, line_item_id)
                return ToolResult.ok({"line_item": item, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to get DV360 line item: {exc}")
        return ToolResult.ok({
            "line_item": {"id": line_item_id, "io_id": io_id, "name": "Mock Line Item", "status": "UNKNOWN"},
            "data_status": "offline_no_client",
            "simulated": True,
        })


class DV360CreateLineItemHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        io_id = input_data.get("io_id")
        if self.client and io_id:
            try:
                line_item_id = self.client.create_line_item(
                    advertiser_id=ctx.account_id,
                    io_id=io_id,
                    line_item=input_data,
                )
                return ToolResult.ok({
                    "line_item_id": line_item_id,
                    "name": input_data.get("name"),
                    "status": "ACTIVE",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create DV360 line item: {e}")
        else:
            return ToolResult.ok({
                "line_item_id": "dv360_li_1",
                "name": input_data.get("name"),
                "status": "ACTIVE",
            })
