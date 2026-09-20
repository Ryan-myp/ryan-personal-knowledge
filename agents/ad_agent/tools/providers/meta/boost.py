"""Meta Boost Post Handler。"""

from typing import Optional

from ....api_clients.meta_client import MetaAPIClient
from ....core.interfaces import ToolContext, ToolHandler, ToolResult


class MetaBoostPostHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if not self.client or not ctx.account_id:
            return ToolResult.error("Meta client not configured or account_id missing")
        try:
            resource_id = self.client.boost_post(
                account_id=ctx.account_id,
                page_id=input_data["page_id"],
                post_id=input_data["post_id"],
                budget=float(input_data["budget"]),
                duration_days=int(input_data["duration_days"]),
            )
            return ToolResult.ok({"ad_id": resource_id, "status": "ACTIVE"})
        except Exception as exc:
            return ToolResult.error(f"Failed to boost Meta post: {exc}")
