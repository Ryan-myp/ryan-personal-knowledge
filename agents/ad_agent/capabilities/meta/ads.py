"""
capabilities/meta/ads.py - Meta Ad 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.meta_client import MetaAPIClient

logger = logging.getLogger(__name__)


class MetaListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client and ctx.account_id and adset_id:
            try:
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    ctx.account_id, "adset", adset_id
                ):
                    return ToolResult.error(
                        f"Ad Set {adset_id} does not belong to account {ctx.account_id}"
                    )
                ads = self.client.list_ads(ctx.account_id, adset_id)
                return ToolResult.ok({"ads": ads})
            except Exception as e:
                return ToolResult.error(f"Failed to list Meta ads: {e}")
        else:
            return ToolResult.ok({"ads": []})


class MetaGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get("ad_id")
        if self.client:
            try:
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    ctx.account_id, "ad", ad_id
                ):
                    return ToolResult.error(
                        f"Ad {ad_id} does not belong to account {ctx.account_id}"
                    )
                ad = self.client.get_ad(ad_id)
                return ToolResult.ok({"ad": ad})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta ad: {e}")
        else:
            return ToolResult.ok({
                "id": ad_id,
                "name": "Test Ad",
                "status": "ACTIVE",
            })


class MetaCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client and adset_id:
            try:
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    ctx.account_id, "adset", adset_id
                ):
                    return ToolResult.error(
                        f"Ad Set {adset_id} does not belong to account {ctx.account_id}"
                    )
                ad_id = self.client.create_ad(
                    account_id=ctx.account_id,
                    adset_id=adset_id,
                    ad=input_data,
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "name": input_data.get("name"),
                    "status": "ACTIVE",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Meta ad: {e}")
        else:
            return ToolResult.ok({
                "ad_id": f"act_{adset_id}_ad",
                "name": input_data.get("name"),
                "status": "ACTIVE",
            })
