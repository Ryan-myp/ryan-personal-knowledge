"""TikTok Spark Ads Handler。"""

from typing import Optional

from ...api_clients.tiktok_client import TikTokAPIClient
from ...core.interfaces import ToolContext, ToolHandler, ToolResult


class TikTokSparkAdsCreateHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if not self.client or not ctx.account_id:
            return ToolResult.error("TikTok client not configured or advertiser_id missing")
        try:
            ad_id = self.client.create_spark_ad(
                advertiser_id=ctx.account_id,
                campaign_id=input_data["campaign_id"],
                adgroup_id=input_data["adgroup_id"],
                spark_post_id=input_data["spark_post_id"],
            )
            return ToolResult.ok({"ad_id": ad_id, "status": "ENABLED"})
        except Exception as exc:
            return ToolResult.error(f"Failed to create TikTok Spark Ad: {exc}")
