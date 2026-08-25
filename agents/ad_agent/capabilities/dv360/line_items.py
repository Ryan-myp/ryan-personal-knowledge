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


class DV360CreateLineItemHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        io_id = input_data.get("io_id")
        if self.client and io_id:
            try:
                line_item_id = self.client.create_line_item(
                    io_id=io_id,
                    name=input_data.get("name"),
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
