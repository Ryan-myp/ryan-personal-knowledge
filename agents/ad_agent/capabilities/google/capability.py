"""
capabilities/google/capability.py - Google Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
from .campaigns import (
    GoogleListCampaignsHandler,
    GoogleGetCampaignHandler,
    GoogleCreateCampaignHandler,
)
from .ad_groups import (
    GoogleListAdGroupsHandler,
    GoogleGetAdGroupHandler,
    GoogleCreateAdGroupHandler,
)
from .ads import GoogleListAdsHandler, GoogleGetAdHandler, GoogleCreateAdHandler
from .assets import (
    GoogleListAssetGroupsHandler,
    GoogleGetAssetGroupHandler,
    GoogleCreateAssetGroupHandler,
)
from .reports import GoogleGetReportHandler
from .keywords import GoogleListKeywordsHandler
from .parameters import (
    google_campaign_schema, google_ad_group_schema, google_ad_schema,
    google_asset_group_schema,
)
from ...api_clients.google_ads_client import GoogleAdsAPIClient
from ..update_contracts import google_updates

logger = logging.getLogger(__name__)


def _google_update_adapter(client, ctx, resource_type, resource_id, _parent_id, updates):
    """Adapt Google Ads' customer-scoped campaign update method."""
    if resource_type != "campaign":
        raise AttributeError(
            f"Google {resource_type} update adapter is unavailable"
        )
    factory = getattr(type(client), "for_customer", None)
    scoped_client = factory(client, ctx.account_id) if factory and ctx.account_id else client
    if scoped_client is client and ctx.account_id and hasattr(client, "customer_id"):
        client.customer_id = ctx.account_id
    method = getattr(scoped_client, "update_campaign", None)
    if not callable(method):
        raise AttributeError("Google campaign update adapter is unavailable")
    return method(resource_id, updates)


class GoogleCapability(BaseCapability):
    platform_name = "google-ads"

    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        api_client = getattr(self, '_api_client', None)

        # List Campaigns
        tools.append((ToolDefinition(
            name="google_list_campaigns",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 列表。",
            input_schema=ToolSchema(
                required=["customer_id"],
                properties={"customer_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), GoogleListCampaignsHandler(api_client)))

        # Get Campaign
        tools.append((ToolDefinition(
            name="google_get_campaign",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 详情（支持 campaign_id 或 campaign_name）。",
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
        ), GoogleGetCampaignHandler(api_client)))

        # Create Campaign
        tools.append((ToolDefinition(
            name="google_create_campaign",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Campaign。",
            input_schema=ToolSchema(**google_campaign_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
            live_support=False,
            resource_id_field="campaign_id",
        ), GoogleCreateCampaignHandler(api_client)))

        # List Ad Groups
        tools.append((ToolDefinition(
            name="google_list_ad_groups",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad Group 列表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad_group"],
        ), GoogleListAdGroupsHandler(api_client)))

        # Get Ad Group
        tools.append((ToolDefinition(
            name="google_get_ad_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad Group 详情。",
            input_schema=ToolSchema(
                required=["ad_group_id"],
                properties={"ad_group_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad_group"],
        ), GoogleGetAdGroupHandler(api_client)))

        # Create Ad Group
        tools.append((ToolDefinition(
            name="google_create_ad_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Ad Group。",
            input_schema=ToolSchema(**google_ad_group_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad_group"],
            live_support=False,
            resource_id_field="ad_group_id",
            parent_resource_id_field="campaign_id",
        ), GoogleCreateAdGroupHandler(api_client)))

        # List Ads
        tools.append((ToolDefinition(
            name="google_list_ads",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad 列表。",
            input_schema=ToolSchema(
                required=["ad_group_id"],
                properties={"ad_group_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), GoogleListAdsHandler(api_client)))

        # Get Ad
        tools.append((ToolDefinition(
            name="google_get_ad",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Ad 详情。",
            input_schema=ToolSchema(
                required=["ad_id"],
                properties={"ad_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "ad"],
        ), GoogleGetAdHandler(api_client)))

        # Create Ad
        tools.append((ToolDefinition(
            name="google_create_ad",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google Ads Ad。",
            input_schema=ToolSchema(**google_ad_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
            live_support=False,
            resource_id_field="ad_id",
            parent_resource_id_field="ad_group_id",
        ), GoogleCreateAdHandler(api_client)))

        # List Asset Groups (PMax)
        tools.append((ToolDefinition(
            name="google_list_asset_groups",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 PMax Campaign 的 Asset Group 列表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "pmax"],
        ), GoogleListAssetGroupsHandler(api_client)))

        # Get Asset Group (PMax)
        tools.append((ToolDefinition(
            name="google_get_asset_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 PMax Asset Group 详情。",
            input_schema=ToolSchema(
                required=["asset_group_id"],
                properties={"asset_group_id": {"type": "string"}},
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "pmax"],
        ), GoogleGetAssetGroupHandler(api_client)))

        tools.append((ToolDefinition(
            name="google_create_asset_group",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="创建 Google PMax Asset Group；当前仅支持 dry-run 计划。",
            input_schema=ToolSchema(**google_asset_group_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "pmax", "asset_group"],
            live_support=False,
            resource_id_field="asset_group_id",
            parent_resource_id_field="campaign_id",
        ), GoogleCreateAssetGroupHandler(api_client)))

        # Get Campaign Report
        tools.append((ToolDefinition(
            name="google_get_campaign_report",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads Campaign 报表。支持按 campaign_ids 过滤，默认查询最近30天数据。",
            input_schema=ToolSchema(
                required=[],
                properties={
                    "customer_id": {"type": "string", "description": "Google Ads 账户 ID（从上下文自动获取）"},
                    "campaign_ids": {"type": "array", "items": {"type": "string"}, "description": "要查询的 Campaign ID 列表，不填则默认查前5个"},
                    "date_range": {"type": "string", "description": "日期范围，如 LAST_30_DAYS, YESTERDAY, THIS_MONTH"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), GoogleGetReportHandler(api_client)))

        tools.append((ToolDefinition(
            name="google_list_keywords",
            skill="google-ads-api-expert",
            platform="google-ads",
            description="查询 Google Ads 关键词，可按 Campaign 或 Ad Group 过滤。",
            input_schema=ToolSchema(
                properties={
                    "customer_id": {"type": "string"},
                    "campaign_id": {"type": "string"},
                    "ad_group_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "keyword"],
        ), GoogleListKeywordsHandler(api_client)))

        for resource_type, resource_id in [
            ("campaign", "campaign_id"),
            ("ad_group", "ad_group_id"),
            ("ad", "ad_id"),
            ("asset_group", "asset_group_id"),
        ]:
            tools.append((ToolDefinition(
                name=f"google_update_{resource_type}",
                skill="google-ads-api-expert",
                platform="google-ads",
                description=f"更新 Google Ads {resource_type}，默认仅生成 dry-run 计划。",
                input_schema=ToolSchema(
                    required=[resource_id, "updates"],
                    properties={
                        resource_id: {"type": "string"},
                        "updates": google_updates(resource_type),
                    },
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                live_support=False,
                resource_id_field=resource_id,
            ), CampaignUpdateHandler(
                api_client, resource_type, _google_update_adapter,
                resource_id_field=resource_id,
            )))

        return tools

def create_google_capability(api_client: Optional[GoogleAdsAPIClient] = None) -> GoogleCapability:
    cap = GoogleCapability()
    cap._api_client = api_client
    return cap
