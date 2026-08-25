"""
capabilities/dv360/capability.py - DV360 Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability
from .campaigns import (
    DV360ListCampaignsHandler,
    DV360GetCampaignHandler,
    DV360CreateCampaignHandler,
)
from .io import DV360CreateIOHandler
from .line_items import DV360CreateLineItemHandler
from .reports import DV360GetReportHandler
from .advertisers import DV360ListAdvertisersHandler
from ...api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


class DV360Capability(BaseCapability):
    platform_name = "dv360"

    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        api_client = getattr(self, '_api_client', None)

        # List Campaigns
        tools.append((ToolDefinition(
            name="dv360_list_campaigns",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Campaign 列表。",
            input_schema=ToolSchema(
                required=["advertiser_id"],
                properties={"advertiser_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), DV360ListCampaignsHandler(api_client)))

        # Get Campaign
        tools.append((ToolDefinition(
            name="dv360_get_campaign",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Campaign 详情。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), DV360GetCampaignHandler(api_client)))

        # Create Campaign
        tools.append((ToolDefinition(
            name="dv360_create_campaign",
            skill="dv360-api",
            platform="dv360",
            description="创建 DV360 Campaign。",
            input_schema=ToolSchema(
                required=["advertiser_id", "name"],
                properties={"advertiser_id": {"type": "string"}, "name": {"type": "string"}},
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "campaign"],
        ), DV360CreateCampaignHandler(api_client)))

        # List Advertisers
        tools.append((ToolDefinition(
            name="dv360_list_advertisers",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Advertiser 列表。",
            input_schema=ToolSchema(
                required=[],
                properties={},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "advertiser"],
        ), DV360ListAdvertisersHandler(api_client)))

        # Create IO
        tools.append((ToolDefinition(
            name="dv360_create_io",
            skill="dv360-api",
            platform="dv360",
            description="创建 DV360 IO（Order & Invoice）。",
            input_schema=ToolSchema(
                required=["advertiser_id", "name"],
                properties={"advertiser_id": {"type": "string"}, "name": {"type": "string"}},
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "io"],
        ), DV360CreateIOHandler(api_client)))

        # Create Line Item
        tools.append((ToolDefinition(
            name="dv360_create_line_item",
            skill="dv360-api",
            platform="dv360",
            description="创建 DV360 Line Item。",
            input_schema=ToolSchema(
                required=["io_id", "name"],
                properties={"io_id": {"type": "string"}, "name": {"type": "string"}},
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "line_item"],
        ), DV360CreateLineItemHandler(api_client)))

        # Get Report
        tools.append((ToolDefinition(
            name="dv360_get_campaign_report",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Campaign 报表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "date_range": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), DV360GetReportHandler(api_client)))

        return tools

    def _get_campaign_tool_sequence(self):
        return ["dv360_create_campaign", "dv360_create_io", "dv360_create_line_item"]

    def _get_report_tool_sequence(self):
        return ["dv360_get_campaign_report"]


def create_dv360_capability() -> DV360Capability:
    return DV360Capability()
