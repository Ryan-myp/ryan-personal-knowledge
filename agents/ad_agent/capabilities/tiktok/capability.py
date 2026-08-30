"""
capabilities/tiktok/capability.py - TikTok Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
from ..provider_tools import account_from, bind_provider_method, method_tool
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
    tiktok_lead_ad_schema,
    tiktok_app_ad_schema,
    tiktok_ad_format_catalog,
    tiktok_audience_schema,
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
    provider_client_class = TikTokAPIClient
    capability_version = "1.2.0"
    provider_api_version = "v1.3"
    provider_method_coverage = {
        "list_accounts": ["tiktok_list_accounts"], "list_campaigns": ["tiktok_list_campaigns"],
        "get_campaign": ["tiktok_get_campaign"], "create_campaign": ["tiktok_create_campaign"],
        "update_campaign": ["tiktok_update_campaign"], "pause_campaign": ["tiktok_pause_campaign"],
        "resume_campaign": ["tiktok_resume_campaign"], "delete_campaign": ["tiktok_delete_campaign"],
        "list_adgroups": ["tiktok_list_adgroups"], "get_adgroup": ["tiktok_get_adgroup"],
        "create_adgroup": ["tiktok_create_adgroup"], "update_adgroup": ["tiktok_update_adgroup"],
        "update_ad": ["tiktok_update_ad"], "pause_adgroup": ["tiktok_pause_adgroup"],
        "list_ads": ["tiktok_list_ads"], "get_ad": ["tiktok_get_ad"],
        "create_ad": ["tiktok_create_ad"], "create_lead_ad": ["tiktok_create_lead_ad"],
        "create_app_ad": ["tiktok_create_app_ad"], "create_spark_ad": ["tiktok_spark_ads_create"],
        "get_campaign_report": ["tiktok_get_campaign_report"], "get_adgroup_report": ["tiktok_get_adgroup_report"],
        "list_audiences": ["tiktok_list_audiences"], "get_audience": ["tiktok_get_audience"],
        "create_audience": ["tiktok_create_audience"],
        "delete_audience": ["tiktok_delete_audience"],
        "list_interest_categories": ["tiktok_list_interest_categories"],
        "get_interest_category": ["tiktok_get_interest_category"], "list_locations": ["tiktok_list_locations"],
        "search_locations": ["tiktok_search_locations"], "list_devices": ["tiktok_list_devices"],
        "list_operating_systems": ["tiktok_list_operating_systems"], "list_carriers": ["tiktok_list_carriers"],
        "list_browsers": ["tiktok_list_browsers"], "list_creatives": ["tiktok_list_creatives"],
        "list_videos": ["tiktok_list_videos"], "list_images": ["tiktok_list_images"],
        "list_conversions": ["tiktok_list_conversions"], "get_conversion": ["tiktok_get_conversion"],
        "list_catalogs": ["tiktok_list_catalogs"], "list_product_sets": ["tiktok_list_product_sets"],
        "list_apps": ["tiktok_list_apps"], "list_brand_safety": ["tiktok_list_brand_safety"],
        "get_report": ["tiktok_get_report"],
    }

    def get_ad_format_catalog(self) -> list[dict]:
        return tiktok_ad_format_catalog()

    def _extended_provider_tools(self, client):
        """Expose TikTok account, reference, reporting and lifecycle APIs."""
        account = lambda ctx, data: account_from(ctx, data, "account_id", "advertiser_id")
        tools = [
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_accounts",
                description="列出 TikTok 广告主账户。", method_name="list_accounts", result_key="accounts",
                properties={"advertiser_ids": {"type": "array", "items": {"type": "string"}}},
                required=["advertiser_ids"], action="list", resource_type="account",
                intent_types=["list_accounts"], traits=["read", "account"],
                argument_builder=lambda _ctx, data: ((data["advertiser_ids"],), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_audience",
                description="获取 TikTok Audience 详情。", method_name="get_audience", result_key="audience",
                properties={"account_id": {"type": "string"}, "audience_id": {"type": "string"}},
                required=["account_id", "audience_id"], action="get", resource_type="audience",
                intent_types=["get_audience"], traits=["read", "audience"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["audience_id"]), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_create_audience",
                description="创建 TikTok 自定义或相似受众；默认仅生成 dry-run 计划。",
                method_name="create_audience", result_key="audience_id",
                properties=tiktok_audience_schema()["properties"],
                required=tiktok_audience_schema()["required"],
                provider_required=tiktok_audience_schema()["provider_required"],
                action="create", resource_type="audience", resource_id_field="audience_id",
                intent_types=["create_audience"], traits=["write", "audience"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), {
                    key: value for key, value in data.items() if key != "account_id"
                }), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_delete_audience",
                description="删除 TikTok Custom 或 Lookalike Audience；默认仅生成 dry-run 计划。",
                method_name="delete_audience", result_key="audience_result",
                properties={
                    "account_id": {"type": "string", "description": "TikTok advertiser ID"},
                    "audience_id": {"type": "string", "description": "TikTok audience ID"},
                },
                required=["account_id", "audience_id"], action="delete", resource_type="audience",
                resource_id_field="audience_id", intent_types=["delete_audience"],
                traits=["write", "audience"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["audience_id"]), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_interest_categories",
                description="查询 TikTok 兴趣类别。", method_name="list_interest_categories", result_key="interest_categories",
                properties={"parent_ids": {"type": "array", "items": {"type": "string"}}},
                action="list", resource_type="interest_category", intent_types=["list_interests"],
                traits=["read", "targeting"], argument_builder=lambda _ctx, data: ((data.get("parent_ids"),), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_interest_category",
                description="获取 TikTok 兴趣类别详情。", method_name="get_interest_category", result_key="interest_category",
                properties={"category_id": {"type": "string"}}, required=["category_id"], action="get",
                resource_type="interest_category", intent_types=["get_interest_category"], traits=["read", "targeting"],
                argument_builder=lambda _ctx, data: ((data["category_id"],), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_search_locations",
                description="按关键词搜索 TikTok 投放地域。", method_name="search_locations", result_key="locations",
                properties={"keyword": {"type": "string"}, "location_type": {"type": "string"}},
                required=["keyword"], action="list", resource_type="location", intent_types=["search_locations"],
                traits=["read", "targeting"], argument_builder=lambda _ctx, data: ((data["keyword"],), {
                    "location_type": data.get("location_type")
                }),
            ),
        ]
        for method_name, result_key, resource_type in (
            ("list_operating_systems", "operating_systems", "operating_system"),
            ("list_carriers", "carriers", "carrier"),
            ("list_browsers", "browsers", "browser"),
        ):
            tools.append(method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name=f"tiktok_{method_name}",
                description=f"查询 TikTok {resource_type} 定向选项。", method_name=method_name,
                result_key=result_key, properties={}, action="list", resource_type=resource_type,
                intent_types=[f"list_{resource_type}s"], traits=["read", "targeting"],
                argument_builder=lambda _ctx, _data: ((), {}),
            ))
        tools.extend([
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_conversion",
                description="获取 TikTok 转化事件详情。", method_name="get_conversion", result_key="conversion",
                properties={"account_id": {"type": "string"}, "conversion_id": {"type": "string"}},
                required=["account_id", "conversion_id"], action="get", resource_type="conversion",
                intent_types=["get_conversion"], traits=["read", "conversion"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["conversion_id"]), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_create_lead_ad",
                description="创建 TikTok Lead Generation Instant Form 广告；默认仅生成 dry-run 计划。",
                method_name="create_lead_ad", result_key="ad_id",
                properties=tiktok_lead_ad_schema()["properties"],
                required=tiktok_lead_ad_schema()["required"],
                provider_required=tiktok_lead_ad_schema()["provider_required"],
                provider_any_of=tiktok_lead_ad_schema()["provider_any_of"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="adgroup_id",
                intent_types=["create_lead_ad"],
                traits=["write", "ad", "lead", "instant_form"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["campaign_id"], data["adgroup_id"], {
                    key: data[key] for key in tiktok_lead_ad_schema()["properties"] if key in data
                }), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_create_app_ad",
                description="创建 TikTok App Promotion 广告；默认仅生成 dry-run 计划。",
                method_name="create_app_ad", result_key="ad_id",
                properties=tiktok_app_ad_schema()["properties"],
                required=tiktok_app_ad_schema()["required"],
                provider_required=tiktok_app_ad_schema()["provider_required"],
                provider_any_of=tiktok_app_ad_schema()["provider_any_of"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="adgroup_id",
                intent_types=["create_app_ad"],
                traits=["write", "ad", "app", "app_promotion"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["campaign_id"], data["adgroup_id"], {
                    key: data[key] for key in tiktok_app_ad_schema()["properties"] if key in data
                }), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_product_sets",
                description="查询 TikTok 商品集。", method_name="list_product_sets", result_key="product_sets",
                properties={"account_id": {"type": "string"}, "catalog_id": {"type": "string"},
                            "filtering": {"type": "array"}, "limit": {"type": "integer"}},
                required=["account_id"], action="list", resource_type="product_set",
                intent_types=["list_product_sets"], traits=["read", "catalog"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "catalog_id": data.get("catalog_id"), "filtering": data.get("filtering"),
                    "page_size": data.get("limit", 20),
                }),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_adgroup_report",
                description="查询 TikTok Ad Group 级报表。", method_name="get_adgroup_report", result_key="report",
                properties={"account_id": {"type": "string"}, "campaign_id": {"type": "string"},
                            "adgroup_ids": {"type": "array", "items": {"type": "string"}},
                            "date_range": {"type": "object"}},
                required=["account_id", "campaign_id"], action="report", resource_type="ad_group",
                intent_types=["download_report"], traits=["read", "report", "ad_group"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["campaign_id"]), {
                    "adgroup_ids": data.get("adgroup_ids"), "time_range": data.get("date_range"),
                }),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_report",
                description="查询 TikTok 广告报表。", method_name="get_report", result_key="report",
                properties={"account_id": {"type": "string"}, "report_type": {"type": "string"},
                            "date_preset": {"type": "string"}, "date_range": {"type": "object"}},
                required=["account_id"], action="report", resource_type="report",
                intent_types=["download_report"], traits=["read", "report"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "report_type": data.get("report_type", "CAMPAIGN"),
                    "date_preset": data.get("date_preset", "LAST_7_DAYS"),
                    "time_range": data.get("date_range"),
                }),
            ),
        ])
        for method_name, resource_type, resource_id, intent in (
            ("delete_campaign", "campaign", "campaign_id", "delete_campaign"),
            ("pause_campaign", "campaign", "campaign_id", "pause_campaign"),
            ("resume_campaign", "campaign", "campaign_id", "resume_campaign"),
            ("pause_adgroup", "ad_group", "adgroup_id", "pause_adgroup"),
        ):
            properties = {"account_id": {"type": "string"}, resource_id: {"type": "string"}}
            if method_name == "pause_adgroup":
                properties["campaign_id"] = {"type": "string"}
            tools.append(method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name=f"tiktok_{method_name}",
                description=f"调用 TikTok {method_name} 管理接口；默认仅生成 dry-run 计划。",
                method_name=method_name, result_key=f"{resource_type}_result", properties=properties,
                required=["account_id", resource_id] + (["campaign_id"] if method_name == "pause_adgroup" else []),
                action=method_name.split("_", 1)[0], resource_type=resource_type,
                resource_id_field=resource_id, parent_resource_type="campaign" if method_name == "pause_adgroup" else None,
                parent_resource_id_field="campaign_id" if method_name == "pause_adgroup" else None,
                intent_types=[f"provider_{intent}"], traits=["write", resource_type], write=True,
                argument_builder=(
                    (lambda ctx, data, field=resource_id: ((account(ctx, data), data["campaign_id"], data[field]), {}))
                    if method_name == "pause_adgroup" else
                    (lambda ctx, data, field=resource_id: ((account(ctx, data), data[field]), {}))
                ),
            ))
        return [bind_provider_method(tool, client) for tool in tools]

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

        tools.extend(self._extended_provider_tools(api_client))

        return tools

def create_tiktok_capability(api_client: Optional[TikTokAPIClient] = None) -> TikTokCapability:
    cap = TikTokCapability()
    cap._api_client = api_client
    return cap
