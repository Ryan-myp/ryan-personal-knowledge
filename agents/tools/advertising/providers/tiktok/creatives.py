"""TikTok creative and media library read handlers."""

from typing import Optional

from agents.tools.advertising.clients.tiktok_client import TikTokAPIClient
from agents.agent_harness.core.interfaces import ToolContext, ToolHandler, ToolResult


class _TikTokListMediaHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient], method_name: str, result_key: str):
        self.client = api_client
        self.method_name = method_name
        self.result_key = result_key

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client and ctx.account_id:
            try:
                items = self._items(ctx, input_data)
                return ToolResult.ok({self.result_key: items, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to list TikTok {self.result_key}: {exc}")
        return ToolResult.ok({
            self.result_key: [],
            "data_status": "offline_no_client",
            "simulated": True,
        })

    def _items(self, ctx: ToolContext, input_data: dict) -> list:
        return getattr(self.client, self.method_name)(
            ctx.account_id,
            filtering=input_data.get("filtering"),
            page_size=input_data.get("limit", 20),
        )


class TikTokListCreativesHandler(_TikTokListMediaHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_creatives", "creatives")


class TikTokListVideosHandler(_TikTokListMediaHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_videos", "videos")


class TikTokListImagesHandler(_TikTokListMediaHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        super().__init__(api_client, "list_images", "images")

    def _items(self, ctx: ToolContext, input_data: dict) -> list:
        if input_data.get("image_id"):
            image = self.client.get_image(ctx.account_id, input_data["image_id"])
            return [image] if image else []
        return super()._items(ctx, input_data)
