"""TikTok creative and media library read handlers."""

from typing import Optional

from ....api_clients.tiktok_client import TikTokAPIClient
from ....core.interfaces import ToolContext, ToolHandler, ToolResult


class _TikTokListMediaHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient], method_name: str, result_key: str):
        self.client = api_client
        self.method_name = method_name
        self.result_key = result_key

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client and ctx.account_id:
            try:
                items = getattr(self.client, self.method_name)(
                    ctx.account_id,
                    filtering=input_data.get("filtering"),
                    page_size=input_data.get("limit", 20),
                )
                return ToolResult.ok({self.result_key: items, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to list TikTok {self.result_key}: {exc}")
        return ToolResult.ok({
            self.result_key: [],
            "data_status": "offline_no_client",
            "simulated": True,
        })


class TikTokListCreativesHandler(_TikTokListMediaHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_creatives", "creatives")


class TikTokListVideosHandler(_TikTokListMediaHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_videos", "videos")


class TikTokListImagesHandler(_TikTokListMediaHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_images", "images")
