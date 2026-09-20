"""Google Ads keyword handlers."""

from typing import Optional

from ....api_clients.google_ads_client import GoogleAdsAPIClient
from ....core.interfaces import ToolContext, ToolHandler, ToolResult
from ._utils import for_customer


class GoogleListKeywordsHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client and ctx.account_id:
            try:
                client = for_customer(self.client, ctx.account_id)
                keywords = client.list_keywords(
                    campaign_id=input_data.get("campaign_id"),
                    ad_group_id=input_data.get("ad_group_id"),
                    page_size=input_data.get("limit", 100),
                )
                return ToolResult.ok({"keywords": keywords, "data_status": "live"})
            except Exception as exc:
                return ToolResult.error(f"Failed to list Google keywords: {exc}")
        return ToolResult.ok({
            "keywords": [],
            "data_status": "offline_no_client",
            "simulated": True,
        })
