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

logger = logging.getLogger(__name__)


class MetaListAdSetsHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                ad_sets = self.client.list_ad_sets(campaign_id)
                return ToolResult.ok({"ad_sets": ad_sets})
            except Exception as e:
                return ToolResult.error(f"Failed to list Meta ad sets: {e}")
        else:
            return ToolResult.ok({"ad_sets": []})


class MetaGetAdSetHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id")
        if self.client:
            try:
                adset = self.client.get_adset(adset_id)
                return ToolResult.ok({"adset": adset})
            except Exception as e:
                return ToolResult.error(f"Failed to get Meta adset: {e}")
        else:
            return ToolResult.ok({
                "id": adset_id,
                "name": "Test AdSet",
                "status": "ACTIVE",
            })


class MetaCreateAdSetHandler(ToolHandler):
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        self.client = api_client

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                adset_id = self.client.create_adset(
                    campaign_id=campaign_id,
                    name=input_data.get("name"),
                    targeting=input_data.get("targeting", {}),
                )
                return ToolResult.ok({
                    "adset_id": adset_id,
                    "name": input_data.get("name"),
                    "status": "ACTIVE",
                })
            except Exception as e:
                return ToolResult.error(f"Failed to create Meta adset: {e}")
        else:
            return ToolResult.ok({
                "adset_id": f"act_{campaign_id}_adset",
                "name": input_data.get("name"),
                "status": "ACTIVE",
            })
