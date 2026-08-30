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
    tiktok_product_sales_adgroup_schema,
    tiktok_product_sales_ad_schema,
    tiktok_lead_ad_schema,
    tiktok_app_ad_schema,
    tiktok_ad_format_catalog,
    tiktok_audience_schema,
    tiktok_audience_update_schema,
    tiktok_audience_file_upload_schema,
    tiktok_image_upload_schema,
    tiktok_video_upload_schema,
    tiktok_pixel_schema,
    tiktok_pixel_event_schema,
    tiktok_pixel_batch_schema,
    tiktok_creative_portfolio_schema,
    tiktok_creative_portfolio_get_schema,
    tiktok_creative_portfolio_preview_schema,
    tiktok_identity_create_schema,
    tiktok_identity_list_schema,
    tiktok_identity_video_info_schema,
    tiktok_single_video_ad_schema,
    tiktok_single_image_ad_schema,
    tiktok_carousel_ad_schema,
    tiktok_targeting_update_schema,
    TIKTOK_OBJECTIVE_TYPES,
    TIKTOK_PLACEMENTS,
    TIKTOK_KEYWORD_LANGUAGES,
    TIKTOK_INTEREST_KEYWORD_MODES,
    TIKTOK_INTEREST_AUDIENCE_TYPES,
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
    capability_version = "1.3.0"
    provider_api_version = "v1.3"
    provider_method_coverage = {
        "list_accounts": ["tiktok_list_accounts"], "list_campaigns": ["tiktok_list_campaigns"],
        "get_campaign": ["tiktok_get_campaign"], "create_campaign": ["tiktok_create_campaign"],
        "update_campaign": ["tiktok_update_campaign"], "pause_campaign": ["tiktok_pause_campaign"],
        "resume_campaign": ["tiktok_resume_campaign"], "delete_campaign": ["tiktok_delete_campaign"],
        "list_adgroups": ["tiktok_list_adgroups"], "get_adgroup": ["tiktok_get_adgroup"],
        "create_adgroup": ["tiktok_create_adgroup"], "create_product_sales_adgroup": ["tiktok_create_product_sales_adgroup"], "update_adgroup": ["tiktok_update_adgroup"],
        "update_adgroup_targeting": ["tiktok_update_adgroup_targeting"],
        "update_ad": ["tiktok_update_ad"], "pause_adgroup": ["tiktok_pause_adgroup"],
        "list_ads": ["tiktok_list_ads"], "get_ad": ["tiktok_get_ad"],
        "create_ad": ["tiktok_create_ad"], "create_product_sales_ad": ["tiktok_create_product_sales_ad"], "create_lead_ad": ["tiktok_create_lead_ad"],
        "create_single_video_ad": ["tiktok_create_single_video_ad"],
        "create_single_image_ad": ["tiktok_create_single_image_ad"],
        "create_carousel_ad": ["tiktok_create_carousel_ad"],
        "create_app_ad": ["tiktok_create_app_ad"], "create_spark_ad": ["tiktok_spark_ads_create"],
        "get_campaign_report": ["tiktok_get_campaign_report"], "get_adgroup_report": ["tiktok_get_adgroup_report"],
        "list_audiences": ["tiktok_list_audiences"], "get_audience": ["tiktok_get_audience"],
        "create_audience": ["tiktok_create_audience"],
        "update_audience": ["tiktok_update_audience"],
        "upload_audience_file": ["tiktok_upload_audience_file"],
        "delete_audience": ["tiktok_delete_audience"],
        "list_interest_categories": ["tiktok_list_interest_categories"],
        "list_action_categories": ["tiktok_list_action_categories"],
        "get_interest_category": ["tiktok_get_interest_category"], "list_locations": ["tiktok_list_locations"],
        "list_languages": ["tiktok_list_languages"],
        "list_device_models": ["tiktok_list_device_models"],
        "recommend_interest_keywords": ["tiktok_recommend_interest_keywords"],
        "search_locations": ["tiktok_search_locations"], "list_regions": ["tiktok_list_regions"],
        "list_devices": ["tiktok_list_devices"],
        "list_operating_systems": ["tiktok_list_operating_systems"], "list_carriers": ["tiktok_list_carriers"],
        "list_browsers": ["tiktok_list_browsers"], "list_creatives": ["tiktok_list_creatives"],
        "list_videos": ["tiktok_list_videos"], "list_images": ["tiktok_list_images"],
        "upload_image": ["tiktok_upload_image"], "upload_video": ["tiktok_upload_video"],
        "list_conversions": ["tiktok_list_conversions"], "get_conversion": ["tiktok_get_conversion"],
        "list_pixels": ["tiktok_list_pixels"], "get_pixel": ["tiktok_get_pixel"],
        "create_pixel": ["tiktok_create_pixel"], "update_pixel": ["tiktok_update_pixel"],
        "send_pixel_event": ["tiktok_send_pixel_event"],
        "send_pixel_events": ["tiktok_send_pixel_events"],
        "create_creative_portfolio": ["tiktok_create_creative_portfolio"],
        "get_creative_portfolio": ["tiktok_get_creative_portfolio"],
        "preview_creative_portfolio": ["tiktok_preview_creative_portfolio"],
        "create_identity": ["tiktok_create_identity"],
        "list_identities": ["tiktok_list_identities"],
        "get_identity_video_info": ["tiktok_get_identity_video_info"],
        "list_catalogs": ["tiktok_list_catalogs"], "list_product_sets": ["tiktok_list_product_sets"],
        "validate_product_selection": ["tiktok_validate_product_selection"],
        "list_apps": ["tiktok_list_apps"], "list_brand_safety": ["tiktok_list_brand_safety"],
        "get_report": ["tiktok_get_report"],
    }

    def get_ad_format_catalog(self) -> list[dict]:
        return tiktok_ad_format_catalog()

    def _extended_provider_tools(self, client):
        """Expose TikTok account, reference, reporting and lifecycle APIs."""
        account = lambda ctx, data: account_from(ctx, data, "account_id", "advertiser_id")
        targeting_schema = tiktok_targeting_update_schema()
        image_upload = tiktok_image_upload_schema()
        video_upload = tiktok_video_upload_schema()
        pixel_event = tiktok_pixel_event_schema()
        pixel_batch = tiktok_pixel_batch_schema()
        pixel = tiktok_pixel_schema()
        creative_portfolio = tiktok_creative_portfolio_schema()
        creative_portfolio_get = tiktok_creative_portfolio_get_schema()
        creative_portfolio_preview = tiktok_creative_portfolio_preview_schema()
        identity_create = tiktok_identity_create_schema()
        identity_list = tiktok_identity_list_schema()
        identity_video_info = tiktok_identity_video_info_schema()
        tools = [
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_upload_image",
                description="上传或绑定 TikTok 广告图片素材；默认仅生成 dry-run 计划。",
                method_name="upload_image", result_key="image_id",
                properties=image_upload["properties"], required=image_upload["required"],
                provider_required=image_upload["provider_required"],
                provider_exactly_one_of=image_upload["provider_exactly_one_of"],
                action="upload", resource_type="image", resource_id_field="image_id",
                intent_types=["upload_image"], traits=["write", "creative", "image", "source_upload"],
                write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data.get("file_path"), data.get("image_url"),
                    data.get("file_id"), data.get("file_name"), data.get("upload_type"),
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_upload_video",
                description="上传或绑定 TikTok 广告视频素材；默认仅生成 dry-run 计划。",
                method_name="upload_video", result_key="video_id",
                properties=video_upload["properties"], required=video_upload["required"],
                provider_required=video_upload["provider_required"],
                provider_exactly_one_of=video_upload["provider_exactly_one_of"],
                action="upload", resource_type="video", resource_id_field="video_id",
                intent_types=["upload_video"], traits=["write", "creative", "video", "source_upload"],
                write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data.get("file_path"), data.get("video_url"),
                    data.get("video_id"), data.get("file_id"), data.get("file_name"),
                    data.get("upload_type"), data.get("flaw_detect"),
                    data.get("auto_fix_enabled"), data.get("auto_bind_enabled"),
                    data.get("is_third_party"),
                ), {}),
            ),
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
                description="通过已上传的加密文件创建 TikTok Custom Audience；默认仅生成 dry-run 计划。",
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
                description="删除 TikTok Custom Audience；默认仅生成 dry-run 计划。",
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
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_update_audience",
                description="更新 TikTok Custom Audience 名称或已上传文件；默认仅生成 dry-run 计划。",
                method_name="update_audience", result_key="audience_result",
                properties=tiktok_audience_update_schema()["properties"],
                required=tiktok_audience_update_schema()["required"],
                provider_required=tiktok_audience_update_schema()["provider_required"],
                action="update", resource_type="audience", resource_id_field="audience_id",
                intent_types=["update_audience"], traits=["write", "audience"],
                write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["audience_id"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_upload_audience_file",
                description="上传 TikTok Custom Audience 的加密 CSV/TXT 文件；默认仅生成 dry-run 计划。",
                method_name="upload_audience_file", result_key="audience_file",
                properties=tiktok_audience_file_upload_schema()["properties"],
                required=tiktok_audience_file_upload_schema()["required"],
                provider_required=tiktok_audience_file_upload_schema()["provider_required"],
                action="upload", resource_type="audience", resource_id_field=None,
                intent_types=["upload_audience_file"], traits=["write", "audience", "source_upload"],
                write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["file_path"], data["calculate_type"], data.get("file_name")
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert",
                name="tiktok_update_adgroup_targeting",
                description="独立更新 TikTok Ad Group 定向；动态 ID 必须来自对应 lookup Tool，默认仅生成 dry-run 计划。",
                method_name="update_adgroup_targeting", result_key="targeting_result",
                properties=targeting_schema["properties"],
                required=targeting_schema["required"],
                provider_required=targeting_schema["provider_required"],
                action="update", resource_type="ad_group", parent_resource_type="campaign",
                resource_id_field="adgroup_id", parent_resource_id_field="campaign_id",
                intent_types=["update_adgroup_targeting"], traits=["write", "ad_group", "targeting"],
                write=True,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["campaign_id"], data["adgroup_id"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_interest_categories",
                description="查询 TikTok 兴趣类别。", method_name="list_interest_categories", result_key="interest_categories",
                properties={
                    "account_id": {"type": "string"}, "version": {"type": "integer", "enum": [1, 2]},
                    "placements": {"type": "array", "items": {"type": "string", "enum": TIKTOK_PLACEMENTS}},
                    "special_industries": {"type": "array", "items": {"type": "string", "enum": ["HOUSING", "EMPLOYMENT", "CREDIT"]}},
                    "language": {"type": "string", "enum": ["en", "zh", "ja", "de", "es", "fr", "id", "it", "ko", "ru", "th", "tr", "vi", "ar", "pt", "ms"]},
                },
                required=["account_id"], provider_required=["account_id"],
                action="list", resource_type="interest_category", intent_types=["list_interests"],
                traits=["read", "targeting", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "version": data.get("version", 2), "placements": data.get("placements"),
                    "special_industries": data.get("special_industries"),
                    "language": data.get("language", "en"),
                }),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_action_categories",
                description="查询 TikTok Action 类别和特殊行业类别。", method_name="list_action_categories",
                result_key="action_categories",
                properties={
                    "account_id": {"type": "string"},
                    "special_industries": {"type": "array", "items": {"type": "string", "enum": ["HOUSING", "EMPLOYMENT", "CREDIT"]}},
                },
                required=["account_id"], provider_required=["account_id"],
                action="list", resource_type="action_category", intent_types=["list_action_categories"],
                traits=["read", "targeting", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "special_industries": data.get("special_industries"),
                }),
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
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_regions",
                description="按投放位置、广告目标和业务条件查询 TikTok 官方可用地域。",
                method_name="list_regions", result_key="regions",
                properties={
                    "account_id": {"type": "string"},
                    "placements": {"type": "array", "items": {"type": "string", "enum": TIKTOK_PLACEMENTS}},
                    "objective_type": {"type": "string", "enum": TIKTOK_OBJECTIVE_TYPES},
                    "promotion_target_type": {"type": "string", "enum": ["INSTANT_PAGE", "EXTERNAL_WEBSITE"]},
                    "operating_system": {"type": "string", "enum": ["ANDROID", "IOS"]},
                    "brand_safety_type": {"type": "string"},
                    "brand_safety_partner": {"type": "string", "enum": ["IAS", "OPEN_SLATE"]},
                    "level_range": {"type": "string", "enum": ["ALL", "TO_COUNTRY", "TO_PROVINCE", "TO_CITY", "TO_DISTRICT"]},
                    "rf_campaign_type": {"type": "string", "enum": ["STANDARD", "PULSE"]},
                },
                required=["account_id", "placements", "objective_type"],
                action="list", resource_type="region", intent_types=["list_regions"],
                traits=["read", "targeting", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["placements"], data["objective_type"]), {
                    "promotion_target_type": data.get("promotion_target_type"),
                    "operating_system": data.get("operating_system"),
                    "brand_safety_type": data.get("brand_safety_type"),
                    "brand_safety_partner": data.get("brand_safety_partner"),
                    "level_range": data.get("level_range"),
                    "rf_campaign_type": data.get("rf_campaign_type"),
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
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_languages",
                description="查询 TikTok 官方语言定向选项。", method_name="list_languages",
                result_key="languages", properties={"account_id": {"type": "string"}},
                required=["account_id"], provider_required=["account_id"],
                action="list", resource_type="language", intent_types=["list_languages"],
                traits=["read", "targeting", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_device_models",
                description="查询 TikTok 官方设备型号定向选项。", method_name="list_device_models",
                result_key="device_models", properties={"account_id": {"type": "string"}},
                required=["account_id"], provider_required=["account_id"],
                action="list", resource_type="device_model", intent_types=["list_device_models"],
                traits=["read", "targeting", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_recommend_interest_keywords",
                description="根据种子词查询 TikTok 兴趣定向推荐关键词。",
                method_name="recommend_interest_keywords", result_key="interest_keywords",
                properties={
                    "account_id": {"type": "string"}, "keyword": {"type": "string", "minLength": 1},
                    "language": {"type": "string", "enum": TIKTOK_KEYWORD_LANGUAGES},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "mode": {"type": "string", "enum": TIKTOK_INTEREST_KEYWORD_MODES},
                    "audience_type": {"type": "string", "enum": TIKTOK_INTEREST_AUDIENCE_TYPES},
                },
                required=["account_id", "keyword"], provider_required=["account_id", "keyword"],
                action="recommend", resource_type="interest_keyword",
                intent_types=["recommend_interest_keywords"], traits=["read", "targeting", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["keyword"]), {
                    "language": data.get("language", "en"), "limit": data.get("limit", 50),
                    "mode": data.get("mode", "FUZZ_MATCH"),
                    "audience_type": data.get("audience_type", "GENERAL_INTEREST"),
                }),
            ),
        ])
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
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_pixels",
                description="查询 TikTok 广告主下的 Pixel。", method_name="list_pixels",
                result_key="pixels", properties={key: pixel["properties"][key]
                for key in ("account_id", "pixel_ids", "limit")},
                required=["account_id"], action="list", resource_type="pixel",
                intent_types=["list_pixels"], traits=["read", "pixel", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data.get("pixel_ids")), {
                    "page_size": data.get("limit", 20),
                }),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_pixel",
                description="查询 TikTok Pixel 详情。", method_name="get_pixel",
                result_key="pixel", properties={key: pixel["properties"][key]
                for key in ("account_id", "pixel_id")},
                required=["account_id", "pixel_id"], action="get", resource_type="pixel",
                resource_id_field="pixel_id", intent_types=["get_pixel"],
                traits=["read", "pixel"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["pixel_id"]), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_create_pixel",
                description="创建 TikTok Website 或 App Pixel；默认仅生成 dry-run 计划。",
                method_name="create_pixel", result_key="pixel_id",
                properties={key: pixel["properties"][key]
                for key in ("account_id", "name", "object_type", "tracking_url")},
                required=pixel["create_required"], action="create", resource_type="pixel",
                provider_required=["name", "object_type"],
                resource_id_field="pixel_id", intent_types=["create_pixel"],
                traits=["write", "pixel"], write=True, live_support=False,
                argument_builder=lambda ctx, data: ((account(ctx, data), {
                    key: value for key, value in data.items() if key != "account_id"
                }), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_update_pixel",
                description="更新 TikTok Pixel 名称；默认仅生成 dry-run 计划。",
                method_name="update_pixel", result_key="pixel_result",
                properties={key: pixel["properties"][key]
                for key in ("account_id", "pixel_id", "updates")},
                required=pixel["update_required"], action="update", resource_type="pixel",
                resource_id_field="pixel_id", intent_types=["update_pixel"],
                traits=["write", "pixel"], write=True, live_support=False,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["pixel_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_send_pixel_event",
                description="通过 TikTok Pixel Track 发送单个转化事件；默认仅生成 dry-run 计划。",
                method_name="send_pixel_event", result_key="pixel_event_result",
                properties=pixel_event["properties"], required=pixel_event["required"],
                provider_required=pixel_event["provider_required"],
                action="send", resource_type="pixel_event", resource_id_field="pixel_id",
                intent_types=["send_pixel_event", "track_tiktok_pixel"],
                traits=["write", "pixel", "conversion", "event"], write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["pixel_id"], {
                        key: value for key, value in data.items()
                        if key not in {"account_id", "pixel_id"}
                    },
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_send_pixel_events",
                description="通过 TikTok Pixel Batch 发送一批转化事件；默认仅生成 dry-run 计划。",
                method_name="send_pixel_events", result_key="pixel_events_result",
                properties=pixel_batch["properties"], required=pixel_batch["required"],
                provider_required=pixel_batch["provider_required"],
                action="send", resource_type="pixel_event_batch", resource_id_field="pixel_id",
                intent_types=["send_pixel_events", "track_tiktok_pixel_batch"],
                traits=["write", "pixel", "conversion", "event", "batch"], write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["pixel_id"], data["events"],
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_create_creative_portfolio",
                description="创建 TikTok Creative Portfolio（CTA/Card 等增强素材）；默认仅生成 dry-run 计划。",
                method_name="create_creative_portfolio", result_key="creative_portfolio_result",
                properties=creative_portfolio["properties"], required=creative_portfolio["required"],
                provider_required=creative_portfolio["provider_required"],
                action="create", resource_type="creative_portfolio", resource_id_field="creative_portfolio_id",
                intent_types=["create_creative_portfolio"],
                traits=["write", "creative", "portfolio"], write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data.get("creative_portfolio_type", "CTA"),
                    data.get("portfolio_content"),
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_creative_portfolio",
                description="查询 TikTok Creative Portfolio 详情。",
                method_name="get_creative_portfolio", result_key="creative_portfolio",
                properties=creative_portfolio_get["properties"],
                required=creative_portfolio_get["required"],
                provider_required=creative_portfolio_get["provider_required"],
                action="get", resource_type="creative_portfolio",
                resource_id_field="creative_portfolio_id",
                intent_types=["get_creative_portfolio"],
                traits=["read", "creative", "portfolio"],
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["creative_portfolio_id"],
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_preview_creative_portfolio",
                description="生成 TikTok Creative Portfolio 预览链接。",
                method_name="preview_creative_portfolio", result_key="creative_portfolio_preview",
                properties=creative_portfolio_preview["properties"],
                required=creative_portfolio_preview["required"],
                provider_required=creative_portfolio_preview["provider_required"],
                action="preview", resource_type="creative_portfolio",
                resource_id_field="creative_portfolio_id",
                intent_types=["preview_creative_portfolio"],
                traits=["read", "creative", "portfolio", "preview"],
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["creative_portfolio_id"],
                    data.get("preview_type", "CARD"),
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_create_identity",
                description="创建 TikTok 自定义广告身份；默认仅生成 dry-run 计划。",
                method_name="create_identity", result_key="identity_result",
                properties=identity_create["properties"], required=identity_create["required"],
                provider_required=identity_create["provider_required"],
                action="create", resource_type="identity", resource_id_field="identity_id",
                intent_types=["create_identity"], traits=["write", "identity", "creative"],
                write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["display_name"], data["image_uri"],
                ), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_identities",
                description="查询 TikTok 广告账户下的可用广告身份。",
                method_name="list_identities", result_key="identities",
                properties=identity_list["properties"], required=identity_list["required"],
                provider_required=identity_list["provider_required"],
                action="list", resource_type="identity", intent_types=["list_identities"],
                traits=["read", "identity", "creative"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "identity_type": data.get("identity_type"),
                    "page": data.get("page", 1), "page_size": data.get("limit", 20),
                }),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_get_identity_video_info",
                description="查询 TikTok 身份关联的自有帖子信息，用于 Spark Ads 预校验。",
                method_name="get_identity_video_info", result_key="identity_video",
                properties=identity_video_info["properties"], required=identity_video_info["required"],
                provider_required=identity_video_info["provider_required"],
                action="get", resource_type="identity_video", resource_id_field="item_id",
                intent_types=["get_identity_video_info"], traits=["read", "identity", "spark"],
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["identity_type"], data["identity_id"], data["item_id"],
                ), {}),
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
                intent_types=["create_lead_ad", "create_campaign"],
                activation_rules=[
                    {"field": "objective", "aliases": ["objective_type"], "in": [
                        "leads", "LEAD_GENERATION",
                    ]},
                    {"field": "promotion_type", "in": ["LEAD_FORM"]},
                    {"field": "ad_format", "in": ["LEAD"]},
                    {"field": "page_id", "exists": True},
                ],
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
                intent_types=["create_app_ad", "create_campaign"],
                activation_rules=[
                    {"field": "objective", "aliases": ["objective_type"], "in": [
                        "APP_PROMOTION", "APP_INSTALL", "app",
                    ]},
                    {"field": "promotion_type", "in": ["APP_ANDROID", "APP_IOS"]},
                    {"field": "app_id", "exists": True},
                ],
                traits=["write", "ad", "app", "app_promotion"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["campaign_id"], data["adgroup_id"], {
                    key: data[key] for key in tiktok_app_ad_schema()["properties"] if key in data
                }), {}),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_catalogs",
                description="查询 TikTok 商品目录；Catalog/Product Set 的创建、更新和删除当前没有经过验证的 Ads API Tool。",
                method_name="list_catalogs", result_key="catalogs",
                properties={
                    "account_id": {"type": "string"},
                    "filtering": {"type": "array"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                required=["account_id"], provider_required=["account_id"],
                action="list", resource_type="catalog", intent_types=["list_catalogs"],
                traits=["read", "catalog", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "filtering": data.get("filtering"),
                    "page_size": data.get("limit", 20),
                }),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name="tiktok_list_product_sets",
                description="查询 TikTok 商品集。", method_name="list_product_sets", result_key="product_sets",
                properties={"account_id": {"type": "string"}, "catalog_id": {"type": "string"},
                            "filtering": {"type": "array"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                required=["account_id"], provider_required=["account_id"],
                action="list", resource_type="product_set",
                intent_types=["list_product_sets"], traits=["read", "catalog", "lookup"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "catalog_id": data.get("catalog_id"), "filtering": data.get("filtering"),
                    "page_size": data.get("limit", 20),
                }),
            ),
            method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert",
                name="tiktok_validate_product_selection",
                description=(
                    "校验 TikTok Catalog 与 Product Set 的归属关系；通过 product_set/get "
                    "完成可用的引用校验，不声称覆盖商品 Feed 健康度诊断。"
                ),
                method_name="validate_product_selection", result_key="validation",
                properties={
                    "account_id": {"type": "string"},
                    "catalog_id": {"type": "string", "minLength": 1},
                    "product_set_id": {"type": "string", "minLength": 1},
                },
                required=["account_id", "catalog_id", "product_set_id"],
                provider_required=["account_id", "catalog_id", "product_set_id"],
                action="validate", resource_type="product_selection",
                intent_types=["validate_product_selection"],
                traits=["read", "catalog", "product_set", "validation"],
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["catalog_id"], data["product_set_id"],
                ), {}),
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
                intent_types=(
                    ["provider_delete_campaign", "cross_channel_batch_delete"]
                    if intent == "delete_campaign" else [f"provider_{intent}"]
                ),
                traits=["write", resource_type], write=True,
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
            action="list", resource_type="campaign",
            intent_types=[
                "list_campaigns", "cross_channel_overview", "cross_channel_compare",
                "cross_channel_performance_insights", "cross_channel_optimize_budget",
                "cross_channel_export_report",
            ],
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
            action="get", resource_type="campaign", intent_types=["get_campaign"],
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
            action="create", resource_type="campaign", intent_types=["create_campaign"],
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
            action="list", resource_type="ad_group", parent_resource_type="campaign",
            intent_types=["list_adgroups"],
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
            action="get", resource_type="ad_group", parent_resource_type="campaign",
            intent_types=["get_adgroup"],
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
            action="create", resource_type="ad_group", parent_resource_type="campaign",
            intent_types=["create_campaign"],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "adgroup"],
            live_support=False,
            resource_id_field="adgroup_id",
            parent_resource_id_field="campaign_id",
            activation_rules=[{
                "if": {
                    "objective_type": {"aliases": ["objective"], "not_in": ["PRODUCT_SALES", "sales"]},
                    "product_source": {"not_in": ["CATALOG", "STORE", "SHOWCASE"]},
                    "catalog_id": {"exists": False},
                    "product_set_id": {"exists": False},
                    "store_id": {"exists": False},
                },
            }],
        ), TikTokCreateAdGroupHandler(api_client)))

        # Product Sales Ad Group: provider-specific product/Shop references
        # live on the normal Ad Group endpoint, but are exposed through a
        # dedicated contract so Skills can compose this path explicitly.
        product_sales_adgroup = tiktok_product_sales_adgroup_schema()
        tools.append(method_tool(
            platform="tiktok", skill="tiktok-ads-api-expert",
            name="tiktok_create_product_sales_adgroup",
            description=(
                "创建 TikTok Product Sales 商品销售广告组，支持 Website、Catalog 和 Shop "
                "商品来源；默认仅生成 dry-run 计划。"
            ),
            method_name="create_product_sales_adgroup", result_key="adgroup_id",
            properties=product_sales_adgroup["properties"],
            required=product_sales_adgroup["required"],
            provider_required=product_sales_adgroup["provider_required"],
            conditional_rules=product_sales_adgroup["conditional_rules"],
            action="create", resource_type="ad_group", parent_resource_type="campaign",
            resource_id_field="adgroup_id", parent_resource_id_field="campaign_id",
            intent_types=["create_product_sales_adgroup", "create_campaign"],
            activation_rules=[
                {"field": "objective_type", "aliases": ["objective"], "in": ["PRODUCT_SALES", "sales"]},
                {"field": "product_source", "in": ["CATALOG", "STORE", "SHOWCASE"]},
                {"field": "catalog_id", "exists": True},
                {"field": "product_set_id", "exists": True},
                {"field": "store_id", "exists": True},
            ],
            traits=["write", "adgroup", "product_sales", "catalog", "shop"],
            write=True, live_support=False,
            argument_builder=lambda ctx, data: ((
                account_from(ctx, data), data["campaign_id"], {
                    key: value for key, value in data.items()
                    if key not in {"account_id", "campaign_id"}
                },
            ), {}),
        ))

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
            action="list", resource_type="ad", parent_resource_type="ad_group",
            intent_types=["list_ads"],
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
            action="get", resource_type="ad", parent_resource_type="ad_group",
            intent_types=["get_ad"],
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
            action="create", resource_type="ad", parent_resource_type="ad_group",
            intent_types=["create_campaign"],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
            live_support=False,
            resource_id_field="ad_id",
            parent_resource_id_field="adgroup_id",
            activation_rules=[{
                "if": {
                    "ad_format": {"aliases": ["creative_type"], "not_in": [
                        "SINGLE_VIDEO", "SINGLE_IMAGE", "CAROUSEL", "SPARK_AD", "SPARK",
                    ]},
                    "objective": {"aliases": ["objective_type"], "not_in": [
                        "leads", "LEAD_GENERATION", "APP_PROMOTION", "APP_INSTALL", "app",
                        "PRODUCT_SALES", "sales",
                    ]},
                    "promotion_type": {"not_in": ["LEAD_FORM", "APP_ANDROID", "APP_IOS"]},
                    "spark_post_id": {"aliases": ["tiktok_item_id"], "exists": False},
                    "catalog_id": {"exists": False},
                    "product_set_id": {"exists": False},
                    "store_id": {"exists": False},
                    "product_source": {"not_in": ["CATALOG", "STORE", "SHOWCASE"]},
                },
            }],
        ), TikTokCreateAdHandler(api_client)))

        # Product Sales Ad: typed product/Shop destination contract over the
        # same provider ad-create endpoint. It owns catalog/product-set and
        # Shop reference validation without adding provider logic to Core.
        product_sales_ad = tiktok_product_sales_ad_schema()
        tools.append(method_tool(
            platform="tiktok", skill="tiktok-ads-api-expert",
            name="tiktok_create_product_sales_ad",
            description=(
                "创建 TikTok Product Sales 商品销售广告，支持 Catalog、Shop 商品引用和素材创意；"
                "默认仅生成 dry-run 计划。"
            ),
            method_name="create_product_sales_ad", result_key="ad_id",
            properties=product_sales_ad["properties"],
            required=product_sales_ad["required"],
            provider_required=product_sales_ad["provider_required"],
            provider_any_of=product_sales_ad["provider_any_of"],
            conditional_rules=product_sales_ad["conditional_rules"],
            action="create", resource_type="ad", parent_resource_type="ad_group",
            resource_id_field="ad_id", parent_resource_id_field="adgroup_id",
            intent_types=["create_product_sales_ad", "create_campaign"],
            activation_rules=[
                {"field": "objective_type", "aliases": ["objective"], "in": ["PRODUCT_SALES", "sales"]},
                {"field": "product_source", "in": ["CATALOG", "STORE", "SHOWCASE"]},
                {"field": "catalog_id", "exists": True},
                {"field": "product_set_id", "exists": True},
                {"field": "store_id", "exists": True},
            ],
            traits=["write", "ad", "product_sales", "catalog", "shop"],
            write=True, live_support=False,
            argument_builder=lambda ctx, data: ((
                account_from(ctx, data), data["campaign_id"], data["adgroup_id"], {
                    key: value for key, value in data.items()
                    if key not in {"account_id", "campaign_id", "adgroup_id"}
                },
            ), {}),
        ))

        for format_name, tool_name, method_name, schema_factory, intent_name in (
            ("SINGLE_VIDEO", "tiktok_create_single_video_ad", "create_single_video_ad", tiktok_single_video_ad_schema, "create_single_video_ad"),
            ("SINGLE_IMAGE", "tiktok_create_single_image_ad", "create_single_image_ad", tiktok_single_image_ad_schema, "create_single_image_ad"),
            ("CAROUSEL", "tiktok_create_carousel_ad", "create_carousel_ad", tiktok_carousel_ad_schema, "create_carousel_ad"),
        ):
            schema = schema_factory()
            tools.append(method_tool(
                platform="tiktok", skill="tiktok-ads-api-expert", name=tool_name,
                description=f"创建 TikTok {format_name} 广告；默认仅生成 dry-run 计划。",
                method_name=method_name, result_key="ad_id",
                properties=schema["properties"], required=schema["required"],
                provider_required=schema["provider_required"],
                provider_any_of=schema["provider_any_of"],
                action="create", resource_type="ad", parent_resource_type="ad_group",
                resource_id_field="ad_id", parent_resource_id_field="adgroup_id",
                intent_types=[intent_name, "create_campaign"],
                activation_rules=[{
                    "field": "ad_format", "aliases": ["creative_type"], "in": [format_name],
                }],
                traits=["write", "ad", format_name.lower()],
                write=True,
                argument_builder=lambda ctx, data: ((
                    account_from(ctx, data), data["campaign_id"], data["adgroup_id"], {
                        key: value for key, value in data.items()
                        if key not in {"account_id", "campaign_id", "adgroup_id"}
                    },
                ), {}),
            ))

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
            action="report", resource_type="report", intent_types=["download_report"],
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
            action="list", resource_type="audience", intent_types=["list_audiences"],
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
            action="create", resource_type="ad", intent_types=["create_spark_ad", "create_campaign"],
            live_support=False,
            resource_id_field="ad_id",
            parent_resource_type="ad_group",
            parent_resource_id_field="adgroup_id",
            activation_rules=[{
                "field": "spark_post_id", "aliases": ["tiktok_item_id"], "exists": True,
            }, {
                "field": "ad_format", "in": ["SPARK_AD", "SPARK"],
            }],
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
                action="list", resource_type={
                    "creatives": "creative", "videos": "video", "images": "image",
                }[resource_name],
                intent_types={
                    "creatives": ["list_creatives"], "videos": ["list_videos"],
                    "images": ["list_images"],
                }[resource_name],
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "creative", resource_name],
            ), handler))

        reference_tools = [
            ("conversions", "account", TikTokListConversionsHandler(api_client)),
            ("locations", None, TikTokListLocationsHandler(api_client)),
            ("devices", None, TikTokListDevicesHandler(api_client)),
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
                action="list", resource_type={
                    "conversions": "conversion", "locations": "location", "devices": "device",
                    "apps": "app", "brand_safety": "brand_safety",
                }[resource_name],
                intent_types={
                    "conversions": ["list_conversions"], "locations": ["list_locations"],
                    "devices": ["list_devices"], "apps": ["list_apps"],
                    "brand_safety": ["list_brand_safety"],
                }[resource_name],
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
                action="update", resource_type=resource_type,
                parent_resource_type={"ad_group": "campaign", "ad": "ad_group"}.get(resource_type),
                intent_types={
                    "campaign": [
                        "update_campaign", "pause_campaign", "resume_campaign",
                        "cross_channel_batch_pause", "cross_channel_batch_resume",
                        "cross_channel_batch_update_budget",
                    ],
                    "ad_group": ["update_adgroup"], "ad": ["update_ad"],
                }[resource_type],
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
