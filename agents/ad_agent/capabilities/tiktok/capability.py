"""
capabilities/tiktok/capability.py - TikTok Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
from .campaigns import (
    TikTokListCampaignsHandler,
    TikTokGetCampaignHandler,
    TikTokCreateCampaignHandler,
)
from .ad_groups import (
    TikTokListAdGroupsHandler,
    TikTokGetAdGroupHandler,
    TikTokCreateAdGroupHandler,
)
from .ads import TikTokListAdsHandler, TikTokGetAdHandler, TikTokCreateAdHandler
from .reports import TikTokGetReportHandler
from .audiences import TikTokListAudiencesHandler
from .spark import TikTokSparkAdsCreateHandler
from .creatives import (
    TikTokListCreativesHandler,
    TikTokListVideosHandler,
    TikTokListImagesHandler,
)
from .reference import (
    TikTokListConversionsHandler,
    TikTokListLocationsHandler,
    TikTokListDevicesHandler,
    TikTokListCatalogsHandler,
    TikTokListAppsHandler,
    TikTokListBrandSafetyHandler,
)
from ...api_clients.tiktok_client import TikTokAPIClient
from .parameters import (
    tiktok_campaign_schema,
    tiktok_adgroup_schema,
    tiktok_ad_schema,
)
from ..update_contracts import tiktok_updates

logger = logging.getLogger(__name__)


def _tiktok_update_adapter(client, ctx, resource_type, resource_id, parent_id, updates):
    """Adapt TikTok's advertiser- and parent-scoped update methods."""
    if resource_type == "campaign":
        method = getattr(client, "update_campaign", None)
        args = (ctx.account_id, resource_id, updates)
    elif resource_type == "ad_group":
        method = getattr(client, "update_adgroup", None)
        args = (ctx.account_id, parent_id, resource_id, updates)
    elif resource_type == "ad":
        method = getattr(client, "update_ad", None)
        args = (ctx.account_id, parent_id, resource_id, updates)
    else:
        raise AttributeError(
            f"TikTok {resource_type} update adapter is unavailable"
        )
    if not callable(method):
        raise AttributeError(
            f"TikTok {resource_type} update adapter is unavailable"
        )
    if resource_type == "ad_group" and not parent_id:
        raise ValueError("TikTok ad group update requires campaign_id")
    if resource_type == "ad" and not parent_id:
        raise ValueError("TikTok ad update requires adgroup_id")
    return method(*args)


class TikTokCapability(BaseCapability):
    platform_name = "tiktok"

    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        api_client = getattr(self, '_api_client', None)

        # List Campaigns
        tools.append((ToolDefinition(
            name="tiktok_list_campaigns",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Campaign 列表。",
            input_schema=ToolSchema(
                required=["account_id"],
                properties={"account_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), TikTokListCampaignsHandler(api_client)))

        # Get Campaign
        tools.append((ToolDefinition(
            name="tiktok_get_campaign",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Campaign 详情（支持 campaign_id 或 campaign_name）。",
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
        ), TikTokGetCampaignHandler(api_client)))

        # Create Campaign
        tools.append((ToolDefinition(
            name="tiktok_create_campaign",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="创建 TikTok Ads Campaign。",
            input_schema=ToolSchema(**tiktok_campaign_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
            live_support=False,
            resource_id_field="campaign_id",
        ), TikTokCreateCampaignHandler(api_client)))

        # List Ad Groups
        tools.append((ToolDefinition(
            name="tiktok_list_adgroups",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad Group 列表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "adgroup"],
        ), TikTokListAdGroupsHandler(api_client)))

        # Get Ad Group
        tools.append((ToolDefinition(
            name="tiktok_get_adgroup",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad Group 详情。",
            input_schema=ToolSchema(
                required=["campaign_id", "adgroup_id"],
                properties={
                    "campaign_id": {"type": "string"},
                    "adgroup_id": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "adgroup"],
        ), TikTokGetAdGroupHandler(api_client)))

        # Create Ad Group
        tools.append((ToolDefinition(
            name="tiktok_create_adgroup",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="创建 TikTok Ads Ad Group。",
            input_schema=ToolSchema(**tiktok_adgroup_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "adgroup"],
            live_support=False,
            resource_id_field="adgroup_id",
            parent_resource_id_field="campaign_id",
        ), TikTokCreateAdGroupHandler(api_client)))

        # List Ads
        tools.append((ToolDefinition(
            name="tiktok_list_ads",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad 列表。",
            input_schema=ToolSchema(
                required=["adgroup_id"],
                properties={"adgroup_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), TikTokListAdsHandler(api_client)))

        # Get Ad
        tools.append((ToolDefinition(
            name="tiktok_get_ad",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Ad 详情。",
            input_schema=ToolSchema(
                required=["adgroup_id", "ad_id"],
                properties={
                    "adgroup_id": {"type": "string"},
                    "ad_id": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), TikTokGetAdHandler(api_client)))

        # Create Ad
        tools.append((ToolDefinition(
            name="tiktok_create_ad",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="创建 TikTok Ads Ad。",
            input_schema=ToolSchema(**tiktok_ad_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
            live_support=False,
            resource_id_field="ad_id",
            parent_resource_id_field="adgroup_id",
        ), TikTokCreateAdHandler(api_client)))

        # Get Report
        tools.append((ToolDefinition(
            name="tiktok_get_campaign_report",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Ads Campaign 报表。",
            input_schema=ToolSchema(
                required=["account_id"],
                properties={
                    "account_id": {"type": "string"},
                    "campaign_ids": {"type": "array", "items": {"type": "string"}},
                    "date_range": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), TikTokGetReportHandler(api_client)))

        tools.append((ToolDefinition(
            name="tiktok_list_audiences",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="查询 TikTok Audience 列表。",
            input_schema=ToolSchema(
                properties={"account_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "audience"],
        ), TikTokListAudiencesHandler(api_client)))

        tools.append((ToolDefinition(
            name="tiktok_spark_ads_create",
            skill="tiktok-ads-api-expert",
            platform="tiktok",
            description="使用达人已有帖子创建 TikTok Spark Ad。",
            input_schema=ToolSchema(
                required=["account_id", "campaign_id", "adgroup_id", "spark_post_id"],
                properties={
                    "account_id": {"type": "string"},
                    "campaign_id": {"type": "string"},
                    "adgroup_id": {"type": "string"},
                    "spark_post_id": {"type": "string"},
                },
            ),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "spark", "ad"],
            live_support=False,
            resource_id_field="ad_id",
            parent_resource_id_field="adgroup_id",
        ), TikTokSparkAdsCreateHandler(api_client)))

        for resource_name, result_key, handler in [
            ("creatives", "creatives", TikTokListCreativesHandler(api_client)),
            ("videos", "videos", TikTokListVideosHandler(api_client)),
            ("images", "images", TikTokListImagesHandler(api_client)),
        ]:
            tools.append((ToolDefinition(
                name=f"tiktok_list_{resource_name}",
                skill="tiktok-ads-api-expert",
                platform="tiktok",
                description=f"查询 TikTok {resource_name} 素材库。",
                input_schema=ToolSchema(
                    required=["account_id"],
                    properties={
                        "account_id": {"type": "string"},
                        "filtering": {"type": "array"},
                        "limit": {"type": "integer"},
                    },
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "creative", resource_name],
            ), handler))

        reference_tools = [
            ("conversions", "account", TikTokListConversionsHandler(api_client)),
            ("locations", None, TikTokListLocationsHandler(api_client)),
            ("devices", None, TikTokListDevicesHandler(api_client)),
            ("catalogs", "account", TikTokListCatalogsHandler(api_client)),
            ("apps", None, TikTokListAppsHandler(api_client)),
            ("brand_safety", None, TikTokListBrandSafetyHandler(api_client)),
        ]
        for resource_name, account_scope, handler in reference_tools:
            properties = {
                "location_type": {"type": "string"},
                "filtering": {"type": "array"},
                "limit": {"type": "integer"},
            }
            required = []
            if account_scope == "account":
                properties["account_id"] = {"type": "string"}
                required = ["account_id"]
            tools.append((ToolDefinition(
                name=f"tiktok_list_{resource_name}",
                skill="tiktok-ads-api-expert",
                platform="tiktok",
                description=f"查询 TikTok {resource_name} 参考数据。",
                input_schema=ToolSchema(required=required, properties=properties),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", resource_name],
            ), handler))

        for resource_type, resource_id, tool_suffix in [
            ("campaign", "campaign_id", "campaign"),
            ("ad_group", "adgroup_id", "adgroup"),
            ("ad", "ad_id", "ad"),
        ]:
            properties = {resource_id: {"type": "string"}, "updates": {"type": "object"}}
            parent_field = {
                "ad_group": "campaign_id", "ad": "adgroup_id",
            }.get(resource_type)
            if parent_field:
                properties[parent_field] = {"type": "string"}
            properties["updates"] = tiktok_updates(tool_suffix)
            tools.append((ToolDefinition(
                name=f"tiktok_update_{tool_suffix}",
                skill="tiktok-ads-api-expert",
                platform="tiktok",
                description=f"更新 TikTok Ads {resource_type}，默认仅生成 dry-run 计划。",
                input_schema=ToolSchema(
                    required=[resource_id, "updates"], properties=properties,
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                live_support=False,
                resource_id_field=resource_id,
                parent_resource_id_field=parent_field,
            ), CampaignUpdateHandler(
                api_client, resource_type, _tiktok_update_adapter,
                resource_id_field=resource_id,
                parent_resource_id_field=parent_field,
            )))

        return tools

def create_tiktok_capability(api_client: Optional[TikTokAPIClient] = None) -> TikTokCapability:
    cap = TikTokCapability()
    cap._api_client = api_client
    return cap
