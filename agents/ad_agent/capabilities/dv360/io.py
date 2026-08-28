"""
capabilities/dv360/io.py - DV360 IO（Order & Invoice）相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


class DV360ListIOHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client and ctx.account_id:
            try:
                ios = self.client.list_ios(ctx.account_id, input_data.get("limit", 20))
                return ToolResult.ok({"ios": ios, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to list DV360 IOs: {exc}")
        return ToolResult.ok({"ios": [], "data_status": "offline_no_client", "simulated": True})


class DV360GetIOHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        io_id = input_data.get("io_id")
        if self.client and ctx.account_id and io_id:
            try:
                io = self.client.get_io(ctx.account_id, io_id)
                return ToolResult.ok({"io": io, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to get DV360 IO: {exc}")
        return ToolResult.ok({
            "io": {"id": io_id, "name": "Mock IO", "status": "UNKNOWN"},
            "data_status": "offline_no_client",
            "simulated": True,
        })


class DV360CreateIOHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                io_id = self.client.create_io(
                    advertiser_id=advertiser_id,
                    io=input_data,
                )
                return ToolResult.ok({
                    "io_id": io_id,
                    "name": input_data.get("name"),
                    "status": input_data.get("status", "DRAFT"),
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create DV360 IO: {e}")
        else:
            return ToolResult.ok({
                "io_id": "dv360_io_1",
                "name": input_data.get("name"),
                "status": input_data.get("status", "DRAFT"),
            })
