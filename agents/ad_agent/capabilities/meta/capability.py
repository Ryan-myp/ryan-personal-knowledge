"""
capabilities/meta/capability.py - Meta Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
from .campaigns import MetaListCampaignsHandler, MetaGetCampaignHandler, MetaCreateCampaignHandler
from .ad_sets import MetaListAdSetsHandler, MetaGetAdSetHandler, MetaCreateAdSetHandler
from .ads import MetaListAdsHandler, MetaGetAdHandler, MetaCreateAdHandler
from .reports import MetaGetReportHandler
from .audiences import MetaListAudiencesHandler
from .boost import MetaBoostPostHandler
from .creatives import MetaCreateCreativeHandler
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
                properties={
                    "campaign_id": {"type": "string"},
                    "campaign_name": {"type": "string", "description": "Campaign 名称（可通过名称查找 ID）"},
                },
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
                    "objective": {"type": "string", "enum": [
                        "APP_INSTALLS", "PRODUCT_CATALOG_SALES", "CONVERSIONS",
                        "TRAFFIC", "LINK_CLICKS", "OUTCOME_SALES",
                        "OUTCOME_APP_PROMOTION", "OUTCOME_TRAFFIC",
                        "OUTCOME_AWARENESS", "OUTCOME_LEADS", "OUTCOME_ENGAGEMENT",
                    ]},
                    "budget": {"type": "number"},
                    "daily_budget": {"type": "number"},
                    "status": {"type": "string", "enum": ["ACTIVE", "PAUSED"]},
                    "special_ad_categories": {"type": ["array", "string"], "items": {"type": "string"}},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
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
                    "optimization_goal": {"type": "string", "enum": [
                        "APP_INSTALLS", "OFFSITE_CONVERSIONS", "VALUE", "LINK_CLICKS",
                        "LANDING_PAGE_VIEWS", "LEAD_GENERATION", "IMPRESSIONS",
                        "REACH", "THRUPLAY",
                    ]},
                    "billing_event": {"type": "string", "enum": ["IMPRESSIONS", "LINK_CLICKS", "THRUPLAY"]},
                    "bidding_strategy": {"type": "string", "enum": [
                        "LOWEST_COST_WITHOUT_CAP", "LOWEST_COST_WITH_BID_CAP",
                        "COST_CAP", "LOWEST_COST_WITH_MIN_ROAS",
                    ]},
                    "promoted_object": {"type": "object"},
                    "budget": {"type": "number"},
                    "bid_amount": {"type": "number"},
                    "daily_budget": {"type": "number"},
                    "status": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
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
                provider_any_of=[["creative_id", "object_story_spec"]],
                properties={
                    "adset_id": {"type": "string"},
                    "name": {"type": "string"},
                    "creative": {"type": "object"},
                    "creative_id": {"type": "string"},
                    "object_story_spec": {"type": "object"},
                    "body": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "url_tags": {"type": "string"},
                    "status": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
        ), MetaCreateAdHandler(api_client)))

        # Get Report
        tools.append((ToolDefinition(
            name="meta_get_campaign_report",
            skill="meta-marketing-api",
            platform="meta",
            description="查询 Meta Campaign 报表。",
            input_schema=ToolSchema(
                properties={
                    "campaign_id": {"type": "string"},
                    "campaign_ids": {"type": "array", "items": {"type": "string"}},
                    "date_preset": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), MetaGetReportHandler(api_client)))

        tools.append((ToolDefinition(
            name="meta_list_audiences",
            skill="meta-marketing-api",
            platform="meta",
            description="查询 Meta Custom Audience 列表。",
            input_schema=ToolSchema(
                properties={"account_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "audience"],
        ), MetaListAudiencesHandler(api_client)))

        tools.append((ToolDefinition(
            name="meta_boost_post",
            skill="meta-marketing-api",
            platform="meta",
            description="将已有 Meta Page 帖子创建为推广广告。",
            input_schema=ToolSchema(
                required=["account_id", "page_id", "post_id", "budget", "duration_days"],
                properties={
                    "account_id": {"type": "string"},
                    "page_id": {"type": "string"},
                    "post_id": {"type": "string"},
                    "budget": {"type": "number"},
                    "duration_days": {"type": "integer"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "boost", "ad"],
        ), MetaBoostPostHandler(api_client)))

        tools.append((ToolDefinition(
            name="meta_create_creative",
            skill="meta-marketing-api-expert",
            platform="meta",
            description="创建 Meta Creative；当前仅支持 dry-run 计划。",
            input_schema=ToolSchema(
                required=["account_id", "name", "page_id", "link"],
                properties={
                    "account_id": {"type": "string"},
                    "name": {"type": "string"},
                    "page_id": {"type": "string"},
                    "link": {"type": "string"},
                    "message": {"type": "string"},
                    "image_hash": {"type": "string"},
                    "image_url": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "creative"],
            live_support=False,
        ), MetaCreateCreativeHandler(api_client)))

        # Update tools: dry-run 可完整生成计划；live 仅调用已存在的 Client 方法。
        for resource_type, resource_id in [("campaign", "campaign_id"), ("adset", "adset_id"), ("ad", "ad_id")]:
            tools.append((ToolDefinition(
                name=f"meta_update_{resource_type}",
                skill="meta-marketing-api",
                platform="meta",
                description=f"更新 Meta {resource_type}，默认仅生成 dry-run 计划。",
                input_schema=ToolSchema(
                    required=[resource_id, "updates"],
                    properties={resource_id: {"type": "string"}, "updates": {"type": "object"}},
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
            ), CampaignUpdateHandler(api_client, resource_type)))

        return tools

    def _get_campaign_tool_sequence(self):
        return ["meta_create_campaign", "meta_create_adset", "meta_create_ad"]

    def _get_report_tool_sequence(self):
        return ["meta_get_campaign_report"]


def create_meta_capability(api_client: Optional[MetaAPIClient] = None) -> MetaCapability:
    cap = MetaCapability()
    cap._api_client = api_client
    return cap
