"""
capabilities/meta/ad_sets.py - Meta Ad Set 相关 Handler
"""
import logging
from typing import Optional
from ...core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ...api_clients.meta_client import MetaAPIClient
from ..base import call_with_optional_page_size

logger = logging.getLogger(__name__)


class MetaListAdSetsHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        account_id = ctx.account_id
        if self.client and account_id and campaign_id:
            try:
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    account_id, "campaign", campaign_id
                ):
                    return ToolResult.error(
                        f"Campaign {campaign_id} does not belong to account {account_id}"
                    )
                ad_sets = call_with_optional_page_size(
                    self.client.list_adsets,
                    account_id,
                    campaign_id,
                    limit=input_data.get("limit", 25),
                )
                return ToolResult.ok({"ad_sets": ad_sets, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to list Meta ad sets: {e}")
        else:
            return ToolResult.ok({
                "ad_sets": [],
                "account_id": account_id,
                "data_status": "offline_no_client",
                "simulated": True,
            })


class MetaGetAdSetHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client:
            try:
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    ctx.account_id, "adset", adset_id
                ):
                    return ToolResult.error(
                        f"Ad Set {adset_id} does not belong to account {ctx.account_id}"
                    )
                adset = self.client.get_adset(adset_id)
                return ToolResult.ok({"adset": adset, "data_status": "live"})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta adset: {e}")
        else:
            return ToolResult.ok({
                "adset": {
                    "id": adset_id,
                    "name": "Test AdSet",
                    "status": "ACTIVE",
                },
                "data_status": "offline_no_client",
                "simulated": True,
            })


class MetaCreateAdSetHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and ctx.account_id and campaign_id:
            try:
                requested_status = str(input_data.get("status") or "PAUSED").upper()
                if requested_status != "PAUSED":
                    return ToolResult.error(
                        "受控 Meta 创建链路只允许以 PAUSED 状态创建 Ad Set"
                    )
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    ctx.account_id, "campaign", campaign_id
                ):
                    return ToolResult.error(
                        f"Campaign {campaign_id} does not belong to account {ctx.account_id}"
                    )
                adset_id = self.client.create_adset(
                    account_id=ctx.account_id,
                    campaign_id=campaign_id,
                    adset=input_data,
                )
                return ToolResult.ok({
                    "adset_id": adset_id,
                    "name": input_data.get("name"),
                    # The client creates Ad Sets paused by default unless the
                    # request explicitly selected another provider status.
                    "status": requested_status,
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Meta adset: {e}")
        else:
            return ToolResult.error("Meta client not configured or account_id/campaign_id missing")
