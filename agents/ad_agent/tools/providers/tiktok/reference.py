"""TikTok account-scoped application lookup handler."""

import inspect
from typing import Optional

from ....api_clients.tiktok_client import TikTokAPIClient
from ....core.interfaces import ToolContext, ToolHandler, ToolResult


class TikTokListAppsHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if not self.client:
            return ToolResult.ok({
                "apps": [],
                "data_status": "offline_no_client",
                "simulated": True,
            })
        try:
            method = self.client.list_apps
            kwargs = {
                "filtering": input_data.get("filtering"),
                "page_size": input_data.get("limit", 20),
            }
            try:
                inspect.signature(method).bind(
                    advertiser_id=ctx.account_id, **kwargs
                )
            except (TypeError, ValueError):
                apps = method(**kwargs)
            else:
                apps = method(advertiser_id=ctx.account_id, **kwargs)
            return ToolResult.ok({"apps": apps, "data_status": "live"})
        except Exception as exc:
            return ToolResult.error(f"Failed to query TikTok apps: {exc}")
