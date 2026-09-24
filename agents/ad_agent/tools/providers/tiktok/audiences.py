"""TikTok Audience 查询 Handler。"""

from typing import Optional

from ....api_clients.tiktok_client import TikTokAPIClient
from ....core.interfaces import ToolContext, ToolHandler, ToolResult
from ..provider_base import call_with_optional_page_size


class TikTokListAudiencesHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client and ctx.account_id:
            try:
                audiences = call_with_optional_page_size(
                    self.client.list_audiences,
                    ctx.account_id,
                    limit=input_data.get("limit", 20),
                    parameter_names=("max_results", "page_size", "limit"),
                )
                return ToolResult.ok({"audiences": audiences, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to list TikTok audiences: {exc}")
        return ToolResult.ok({
            "audiences": [],
            "data_status": "offline_no_client",
            "simulated": True,
        })
