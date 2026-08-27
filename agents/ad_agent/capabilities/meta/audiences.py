"""Meta Audience 查询 Handler。"""

from typing import Optional

from ...api_clients.meta_client import MetaAPIClient
from ...core.interfaces import ToolContext, ToolHandler, ToolResult


class MetaListAudiencesHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client and ctx.account_id:
            try:
                audiences = self.client.list_audiences(
                    ctx.account_id,
                    limit=input_data.get("limit", 25),
                )
                return ToolResult.ok({"audiences": audiences, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to list Meta audiences: {exc}")
        return ToolResult.ok({
            "audiences": [],
            "data_status": "offline_no_client",
            "simulated": True,
        })
