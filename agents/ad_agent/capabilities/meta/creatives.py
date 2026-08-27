"""Meta Creative capability handlers."""

from typing import Optional

from ...api_clients.meta_client import MetaAPIClient
from ...core.interfaces import ToolContext, ToolHandler, ToolResult


class MetaCreateCreativeHandler(ToolHandler):
    """Create a Meta Creative when an explicitly approved live path exists.

    The normal Runtime intercepts this write in dry-run mode.  Keeping the
    provider call in a dedicated handler makes the capability extensible and
    allows later white-listed adapter verification without changing routing.
    """

    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if not self.client or not ctx.account_id:
            return ToolResult.error("Meta client not configured or account_id missing")
        try:
            creative_id = self.client.create_creative(
                ctx.account_id,
                {
                    key: value
                    for key, value in input_data.items()
                    if key != "account_id"
                },
            )
            return ToolResult.ok({
                "creative_id": creative_id,
                "name": input_data.get("name"),
            })
        except Exception as exc:
            return ToolResult.error(f"Failed to create Meta creative: {exc}")
