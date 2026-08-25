"""
capabilities/meta/capability.py - Meta Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability
from .campaigns import MetaListCampaignsHandler, MetaGetCampaignHandler, MetaCreateCampaignHandler
from .ad_sets import MetaListAdSetsHandler, MetaGetAdSetHandler, MetaCreateAdSetHandler
from .ads import MetaListAdsHandler, MetaGetAdHandler, MetaCreateAdHandler
from .reports import MetaGetReportHandler
from ...api_clients.meta_client import MetaAPIClient

logger = logging.getLogger(__name__)


class MetaCapability(BaseCapability):
    platform_name = "meta"

    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        api_client = getattr(self, '_api_client', None)

        # List Campaigns
        tools.append((ToolDefinition(
            name="meta_list_campaigns",
            skill="meta-marketing-api",
            platform="meta",
            description="列出 Meta Campaign 列表。",
            input_schema=ToolSchema(
                required=["account_id"],
                properties={"account_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), MetaListCampaignsHandler(api_client)))

        # Get Campaign
        tools.append((ToolDefinition(
            name="meta_get_campaign",
            skill="meta-marketing-api",
            platform="meta",
            description="获取 Meta Campaign 详情。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), MetaGetCampaignHandler(api_client)))

        # Create Campaign
        tools.append((ToolDefinition(
            name="meta_create_campaign",
            skill="meta-marketing-api",
            platform="meta",
            description="创建 Meta Campaign。",
            input_schema=ToolSchema(
                required=["account_id", "name"],
                properties={
                    "account_id": {"type": "string"},
                    "name": {"type": "string"},
                    "objective": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "campaign"],
        ), MetaCreateCampaignHandler(api_client)))

        # List Ad Sets
        tools.append((ToolDefinition(
            name="meta_list_ad_sets",
            skill="meta-marketing-api",
            platform="meta",
            description="列出 Meta Ad Set 列表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad_set"],
        ), MetaListAdSetsHandler(api_client)))

        # Get Ad Set
        tools.append((ToolDefinition(
            name="meta_get_adset",
            skill="meta-marketing-api",
            platform="meta",
            description="获取 Meta Ad Set 详情。",
            input_schema=ToolSchema(
                required=["adset_id"],
                properties={"adset_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad_set"],
        ), MetaGetAdSetHandler(api_client)))

        # Create Ad Set
        tools.append((ToolDefinition(
            name="meta_create_adset",
            skill="meta-marketing-api",
            platform="meta",
            description="创建 Meta Ad Set。",
            input_schema=ToolSchema(
                required=["campaign_id", "name"],
                properties={
                    "campaign_id": {"type": "string"},
                    "name": {"type": "string"},
                    "targeting": {"type": "object"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "ad_set"],
        ), MetaCreateAdSetHandler(api_client)))

        # List Ads
        tools.append((ToolDefinition(
            name="meta_list_ads",
            skill="meta-marketing-api",
            platform="meta",
            description="列出 Meta Ad 列表。",
            input_schema=ToolSchema(
                required=["adset_id"],
                properties={"adset_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), MetaListAdsHandler(api_client)))

        # Get Ad
        tools.append((ToolDefinition(
            name="meta_get_ad",
            skill="meta-marketing-api",
            platform="meta",
            description="获取 Meta Ad 详情。",
            input_schema=ToolSchema(
                required=["ad_id"],
                properties={"ad_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), MetaGetAdHandler(api_client)))

        # Create Ad
        tools.append((ToolDefinition(
            name="meta_create_ad",
            skill="meta-marketing-api",
            platform="meta",
            description="创建 Meta Ad。",
            input_schema=ToolSchema(
                required=["adset_id", "name"],
                properties={
                    "adset_id": {"type": "string"},
                    "name": {"type": "string"},
                    "creative": {"type": "object"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.IDEMPOTENT,
            traits=["write", "ad"],
        ), MetaCreateAdHandler(api_client)))

        # Get Report
        tools.append((ToolDefinition(
            name="meta_get_campaign_report",
            skill="meta-marketing-api",
            platform="meta",
            description="查询 Meta Campaign 报表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "date_preset": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), MetaGetReportHandler(api_client)))

        return tools

    def _get_campaign_tool_sequence(self):
        return ["meta_create_campaign", "meta_create_adset", "meta_create_ad"]

    def _get_report_tool_sequence(self):
        return ["meta_get_campaign_report"]


def create_meta_capability(api_client: Optional[MetaAPIClient] = None) -> MetaCapability:
    cap = MetaCapability()
    cap._api_client = api_client
    return cap
