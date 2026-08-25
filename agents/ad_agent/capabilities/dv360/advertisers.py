"""
capabilities/dv360/advertisers.py - DV360 Advertiser 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


class DV360ListAdvertisersHandler(ToolHandler):
    def __init__(self, api_client: Optional[DV360APIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                advertisers = self.client.list_advertisers()
                return ToolResult.ok({"advertisers": advertisers})
            except Exception as e:
                return ToolResult.error(f"Failed to list DV360 advertisers: {e}")
        else:
            return ToolResult.ok({"advertisers": []})
