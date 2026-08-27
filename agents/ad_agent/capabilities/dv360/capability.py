"""
capabilities/dv360/capability.py - DV360 Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
from .campaigns import (
    DV360ListCampaignsHandler,
    DV360GetCampaignHandler,
    DV360CreateCampaignHandler,
)
from .io import DV360CreateIOHandler, DV360ListIOHandler, DV360GetIOHandler
from .line_items import (
    DV360CreateLineItemHandler,
    DV360ListLineItemsHandler,
    DV360GetLineItemHandler,
)
from .reports import DV360GetLineItemReportHandler
from .advertisers import DV360ListAdvertisersHandler
from ...api_clients.dv360_client import DV360APIClient
from ..update_contracts import dv360_updates

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
            description="查询 DV360 Campaign 详情（支持 campaign_id 或 campaign_name）。",
            input_schema=ToolSchema(
                properties={
                    "campaign_id": {"type": "string"},
                    "campaign_name": {"type": "string", "description": "Campaign 名称（可通过名称查找 ID）"},
                },
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
                properties={
                    "advertiser_id": {"type": "string"},
                    "name": {"type": "string"},
                    "campaign_type": {"type": "string"},
                    "objective": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
            live_support=False,
        ), DV360CreateCampaignHandler(api_client)))

        tools.append((ToolDefinition(
            name="dv360_list_ios",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Insertion Order 列表。",
            input_schema=ToolSchema(
                required=["advertiser_id"],
                properties={"advertiser_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "io"],
        ), DV360ListIOHandler(api_client)))

        tools.append((ToolDefinition(
            name="dv360_get_io",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Insertion Order 详情。",
            input_schema=ToolSchema(
                required=["io_id"],
                properties={"io_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "io"],
        ), DV360GetIOHandler(api_client)))

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
                properties={
                    "advertiser_id": {"type": "string"},
                    "name": {"type": "string"},
                    "budget": {"type": "number"},
                    "spend_cap_micros": {"type": "integer"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "status": {"type": "string", "enum": ["DRAFT", "ACTIVE", "PAUSED"]},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
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
                properties={
                    "io_id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "goal": {"type": "object"},
                    "targeting": {"type": "object"},
                    "budget": {"type": "number"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "status": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "line_item"],
        ), DV360CreateLineItemHandler(api_client)))

        tools.append((ToolDefinition(
            name="dv360_list_line_items",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Line Item 列表，可按 IO 过滤。",
            input_schema=ToolSchema(
                required=["advertiser_id"],
                properties={
                    "advertiser_id": {"type": "string"},
                    "io_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "line_item"],
        ), DV360ListLineItemsHandler(api_client)))

        tools.append((ToolDefinition(
            name="dv360_get_line_item",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Line Item 详情。",
            input_schema=ToolSchema(
                required=["io_id", "line_item_id"],
                properties={
                    "io_id": {"type": "string"},
                    "line_item_id": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "line_item"],
        ), DV360GetLineItemHandler(api_client)))

        # Get Line Item Report
        # DV360 campaign-level reporting is not implemented by the current
        # client. Register the verified Line Item scope explicitly instead of
        # exposing a campaign report name that cannot satisfy its contract.
        tools.append((ToolDefinition(
            name="dv360_get_line_item_report",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Line Item 报表；当前不提供 Campaign-level report。",
            input_schema=ToolSchema(
                required=["advertiser_id", "line_item_id"],
                properties={
                    "advertiser_id": {"type": "string"},
                    "line_item_id": {"type": "string"},
                    # Runtime callers may provide either a common preset
                    # (LAST_7_DAYS/TODAY/...) or an explicit date object.
                    "date_range": {"type": ["object", "string"]},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
            live_support=False,
        ), DV360GetLineItemReportHandler(api_client)))

        for resource_type, resource_id in [("campaign", "campaign_id"), ("io", "io_id"), ("line_item", "line_item_id")]:
            properties = {
                resource_id: {"type": "string"},
                "updates": {"type": "object"},
            }
            if resource_type == "line_item":
                properties["io_id"] = {"type": "string"}
            properties["updates"] = dv360_updates(resource_type)
            tools.append((ToolDefinition(
                name=f"dv360_update_{resource_type}",
                skill="dv360-expert",
                platform="dv360",
                description=f"更新 DV360 {resource_type}，默认仅生成 dry-run 计划。",
                input_schema=ToolSchema(
                    required=[resource_id, "updates"], properties=properties,
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                live_support=False,
            ), CampaignUpdateHandler(api_client, resource_type)))

        return tools

def create_dv360_capability(api_client: Optional[DV360APIClient] = None) -> DV360Capability:
    cap = DV360Capability()
    cap._api_client = api_client
    return cap
