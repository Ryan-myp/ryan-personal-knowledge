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
from ..base import call_with_optional_page_size, resource_was_created_in_current_run

logger = logging.getLogger(__name__)


class MetaListAdsHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client and ctx.account_id and adset_id:
            try:
                if (
                    isinstance(self.client, MetaAPIClient)
                    and not resource_was_created_in_current_run(ctx, "ad_set", adset_id)
                    and not self.client.resource_belongs_to_account(
                        ctx.account_id, "adset", adset_id
                    )
                ):
                    return ToolResult.error(
                        f"Ad Set {adset_id} does not belong to account {ctx.account_id}"
                    )
                ads = call_with_optional_page_size(
                    self.client.list_ads,
                    ctx.account_id,
                    adset_id,
                    limit=input_data.get("limit", 25),
                )
                return ToolResult.ok({"ads": ads, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to list Meta ads: {e}")
        else:
            return ToolResult.ok({
                "ads": [],
                "account_id": ctx.account_id,
                "data_status": "offline_no_client",
                "simulated": True,
            })


class MetaGetAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get("ad_id")
        if self.client:
            try:
                if (
                    isinstance(self.client, MetaAPIClient)
                    and not resource_was_created_in_current_run(ctx, "ad", ad_id)
                    and not self.client.resource_belongs_to_account(ctx.account_id, "ad", ad_id)
                ):
                    return ToolResult.error(
                        f"Ad {ad_id} does not belong to account {ctx.account_id}"
                    )
                ad = self.client.get_ad(ad_id)
                return ToolResult.ok({"ad": ad, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta ad: {e}")
        else:
            return ToolResult.ok({
                "ad": {
                    "id": ad_id,
                    "name": "Test Ad",
                    "status": "ACTIVE",
                },
                "data_status": "offline_no_client",
                "simulated": True,
            })


class MetaCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client and ctx.account_id and adset_id:
            try:
                requested_status = str(input_data.get("status") or "PAUSED").upper()
                if requested_status != "PAUSED":
                    return ToolResult.error(
                        "受控 Meta 创建链路只允许以 PAUSED 状态创建 Ad"
                    )
                if (
                    isinstance(self.client, MetaAPIClient)
                    and not resource_was_created_in_current_run(ctx, "ad_set", adset_id)
                    and not self.client.resource_belongs_to_account(ctx.account_id, "adset", adset_id)
                ):
                    return ToolResult.error(
                        f"Ad Set {adset_id} does not belong to account {ctx.account_id}"
                    )
                ad_id = self.client.create_ad(
                    account_id=ctx.account_id,
                    adset_id=adset_id,
                    ad=input_data,
                    live=str(ctx.metadata.get("execution_mode", "dry_run")) == "live",
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "name": input_data.get("name"),
                    "status": requested_status,
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Meta ad: {e}")
        else:
            return ToolResult.error("Meta client not configured or account_id/adset_id missing")
