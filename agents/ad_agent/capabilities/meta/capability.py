"""
capabilities/meta/capability.py - Meta Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
from ..provider_tools import account_from, bind_provider_method, method_tool
from .campaigns import MetaListCampaignsHandler, MetaGetCampaignHandler, MetaCreateCampaignHandler
from .ad_sets import MetaListAdSetsHandler, MetaGetAdSetHandler, MetaCreateAdSetHandler
from .ads import MetaListAdsHandler, MetaGetAdHandler, MetaCreateAdHandler
from .reports import MetaGetReportHandler
from .audiences import MetaListAudiencesHandler
from .boost import MetaBoostPostHandler
from .creatives import MetaCreateCreativeHandler
from .parameters import (
    meta_campaign_schema, meta_adset_schema, meta_ad_schema,
    meta_ad_format_catalog, meta_lead_ad_schema, meta_catalog_ad_schema,
    meta_audience_schema, meta_conversion_event_schema, meta_creative_schema,
    meta_catalog_schema, meta_product_set_schema,
    meta_lead_form_schema,
)
from ...api_clients.meta_client import MetaAPIClient
from ..update_contracts import meta_updates

logger = logging.getLogger(__name__)


def _meta_update_adapter(client, ctx, resource_type, resource_id, _parent_id, updates):
    """Adapt Meta's object-specific Graph update methods for one Tool."""
    method_name = {
        "campaign": "update_campaign",
        "ad_set": "update_adset",
        "ad": "update_ad",
    }.get(resource_type)
    method = getattr(client, method_name, None) if method_name else None
    if not callable(method):
        raise AttributeError(f"Meta {resource_type} update adapter is unavailable")
    # A Graph object can be addressed directly by ID even when the same token
    # can see more than one account. Verify ownership before the write.
    if isinstance(client, MetaAPIClient) and not client.resource_belongs_to_account(
        ctx.account_id, resource_type, resource_id
    ):
        raise PermissionError(
            f"Meta {resource_type} {resource_id} does not belong to account {ctx.account_id}"
        )
    return method(resource_id, updates)


class MetaCapability(BaseCapability):
    platform_name = "meta"
    provider_client_class = MetaAPIClient
    provider_method_exclusions = {"resource_belongs_to_account"}
    capability_version = "1.2.0"
    provider_api_version = "v19.0"
    # Provider endpoint -> executable Tool(s).  This lives with the provider
    # package and is consumed only by the release audit, never by Runtime
    # routing.
    provider_method_coverage = {
        "list_accounts": ["meta_list_accounts"], "get_account": ["meta_get_account"],
        "list_audiences": ["meta_list_audiences"], "get_audience": ["meta_get_audience"],
        "create_audience": ["meta_create_audience"], "update_audience": ["meta_update_audience"],
        "delete_audience": ["meta_delete_audience"], "upload_audience_users": ["meta_upload_audience_users"],
        "list_catalogs": ["meta_list_catalogs"],
        "get_catalog": ["meta_get_catalog"], "create_catalog": ["meta_create_catalog"],
        "update_catalog": ["meta_update_catalog"], "delete_catalog": ["meta_delete_catalog"],
        "list_product_sets": ["meta_list_product_sets"],
        "get_product_set": ["meta_get_product_set"],
        "create_product_set": ["meta_create_product_set"],
        "update_product_set": ["meta_update_product_set"],
        "delete_product_set": ["meta_delete_product_set"],
        "list_campaigns": ["meta_list_campaigns"],
        "list_pages": ["meta_list_pages"], "list_pixels": ["meta_list_pixels"],
        "get_pixel": ["meta_get_pixel"],
        "send_conversion_events": [
            "meta_send_conversion_events", "meta_test_conversion_events"
        ],
        "list_lead_forms": ["meta_list_lead_forms"], "get_lead_form": ["meta_get_lead_form"],
        "create_lead_form": ["meta_create_lead_form"], "update_lead_form": ["meta_update_lead_form"],
        "get_campaign": ["meta_get_campaign"], "create_campaign": ["meta_create_campaign"],
        "update_campaign": ["meta_update_campaign"], "pause_campaign": ["meta_pause_campaign"],
        "resume_campaign": ["meta_resume_campaign"], "list_adsets": ["meta_list_ad_sets"],
        "get_adset": ["meta_get_adset"], "create_adset": ["meta_create_adset"],
        "update_adset": ["meta_update_adset"], "pause_adset": ["meta_pause_adset"],
        "list_ads": ["meta_list_ads"], "get_ad": ["meta_get_ad"],
        "create_ad": ["meta_create_ad"], "create_lead_ad": ["meta_create_lead_ad"],
        "create_catalog_ad": ["meta_create_catalog_ad"],
        "update_ad": ["meta_update_ad"],
        "pause_ad": ["meta_pause_ad"], "create_creative": ["meta_create_creative"],
        "list_creatives": ["meta_list_creatives"], "get_creative": ["meta_get_creative"],
        "update_creative": ["meta_update_creative"], "delete_creative": ["meta_delete_creative"],
        "get_campaign_report": ["meta_get_campaign_report"],
        "get_adset_report": ["meta_get_adset_report"], "get_ad_report": ["meta_get_ad_report"],
        "boost_post": ["meta_boost_post"],
    }

    def get_ad_format_catalog(self) -> list[dict]:
        return meta_ad_format_catalog()

    def _extended_provider_tools(self, client):
        """Expose Meta client endpoints not represented by hierarchy handlers."""
        account = lambda ctx, data: account_from(ctx, data, "account_id")
        audience_schema = meta_audience_schema()
        audience_properties = audience_schema["properties"]
        conversion_schema = meta_conversion_event_schema()
        test_conversion_schema = {
            **conversion_schema,
            "required": [*conversion_schema["required"], "test_event_code"],
            "provider_required": [
                *conversion_schema["provider_required"], "test_event_code"
            ],
            "properties": {
                **conversion_schema["properties"],
                "test_event_code": {
                    "type": "string",
                    "description": "Meta Test Events code; required for test delivery",
                    "minLength": 1,
                    "maxLength": 100,
                },
            },
        }
        creative_schema = meta_creative_schema()
        creative_properties = creative_schema["properties"]
        catalog_schema = meta_catalog_schema()
        catalog_properties = catalog_schema["properties"]
        product_set_schema = meta_product_set_schema()
        product_set_properties = product_set_schema["properties"]
        lead_form_schema = meta_lead_form_schema()
        tools = [
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_list_pages",
                description="查询广告账户可推广的 Facebook Page。", method_name="list_pages",
                result_key="pages", properties={
                    "account_id": {"type": "string"}, "limit": {"type": "integer"},
                }, required=["account_id"], action="list", resource_type="page",
                intent_types=["list_pages"], traits=["read", "page"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "limit": data.get("limit", 25),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_upload_audience_users",
                description="向 Meta Custom Audience 上传已 SHA-256 哈希的客户标识；默认仅生成 dry-run 计划。",
                method_name="upload_audience_users", result_key="audience_upload",
                properties=audience_properties,
                required=audience_schema["upload_required"],
                provider_required=["audience_id", "upload_schema", "upload_data"],
                action="upload", resource_type="audience", resource_id_field="audience_id",
                intent_types=["upload_audience_users"], traits=["write", "audience", "source_upload"],
                write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["audience_id"],
                    data["upload_schema"], data["upload_data"],
                ), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_list_pixels",
                description="查询 Meta 广告账户下的 Pixel。", method_name="list_pixels",
                result_key="pixels", properties={
                    "account_id": {"type": "string"}, "limit": {"type": "integer"},
                }, required=["account_id"], action="list", resource_type="pixel",
                intent_types=["list_pixels"], traits=["read", "pixel"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "limit": data.get("limit", 25),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_pixel",
                description="查询 Meta Pixel 详情。", method_name="get_pixel",
                result_key="pixel", properties={
                    "account_id": {"type": "string"},
                    "pixel_id": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                }, required=["account_id", "pixel_id"], action="get", resource_type="pixel",
                resource_id_field="pixel_id", intent_types=["get_pixel"], traits=["read", "pixel"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["pixel_id"]), {
                    "fields": data.get("fields"),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_send_conversion_events",
                description="向 Meta Pixel 发送 Conversions API 事件；默认仅生成 dry-run 计划。",
                method_name="send_conversion_events", result_key="conversion_result",
                properties=conversion_schema["properties"], required=conversion_schema["required"],
                provider_required=conversion_schema["provider_required"], action="send",
                resource_type="conversion", resource_id_field="pixel_id",
                intent_types=["send_conversion_events", "send_capi_events"],
                traits=["write", "conversion", "pixel", "capi"], write=True,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["pixel_id"], data["events"],
                ), {"test_event_code": data.get("test_event_code")}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_test_conversion_events",
                description=(
                    "向 Meta Test Events 发送一批 Conversions API 测试事件；"
                    "默认仅生成 dry-run 计划。"
                ),
                method_name="send_conversion_events", result_key="conversion_test_result",
                properties=test_conversion_schema["properties"],
                required=test_conversion_schema["required"],
                provider_required=test_conversion_schema["provider_required"],
                action="test", resource_type="pixel_event", resource_id_field="pixel_id",
                intent_types=["test_conversion_events", "test_capi_events"],
                traits=["write", "conversion", "pixel", "capi", "test"],
                write=True, live_support=False,
                argument_builder=lambda ctx, data: ((
                    account(ctx, data), data["pixel_id"], data["events"],
                ), {"test_event_code": data["test_event_code"]}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_list_lead_forms",
                description="查询 Facebook Page 下已发布的 Lead Ads Instant Form。",
                method_name="list_lead_forms", result_key="lead_forms", properties={
                    "page_id": {"type": "string"}, "limit": {"type": "integer"},
                }, required=["page_id"], action="list", resource_type="lead_form",
                intent_types=["list_lead_forms"], traits=["read", "lead_form"],
                argument_builder=lambda _ctx, data: ((data["page_id"],), {
                    "limit": data.get("limit", 25),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_list_creatives",
                description="查询 Meta 广告账户下的 Creative。", method_name="list_creatives",
                result_key="creatives", properties={
                    key: creative_properties[key] for key in ("account_id", "limit")
                }, required=["account_id"], action="list", resource_type="creative",
                intent_types=["list_creatives"], traits=["read", "creative"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "limit": data.get("limit", 25),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_creative",
                description="查询 Meta Creative 详情。", method_name="get_creative",
                result_key="creative", properties={
                    key: creative_properties[key] for key in ("account_id", "creative_id", "fields")
                }, required=["account_id", "creative_id"], action="get", resource_type="creative",
                resource_id_field="creative_id", intent_types=["get_creative"], traits=["read", "creative"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["creative_id"]), {
                    "fields": data.get("fields"),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_update_creative",
                description="更新 Meta Creative 名称；默认仅生成 dry-run 计划。",
                method_name="update_creative", result_key="creative_result",
                properties={key: creative_properties[key] for key in ("account_id", "creative_id", "updates")},
                required=["account_id", "creative_id", "updates"], action="update", resource_type="creative",
                resource_id_field="creative_id", intent_types=["update_creative"], traits=["write", "creative"],
                write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["creative_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_delete_creative",
                description="删除 Meta Creative；默认仅生成 dry-run 计划。",
                method_name="delete_creative", result_key="creative_result",
                properties={key: creative_properties[key] for key in ("account_id", "creative_id")},
                required=["account_id", "creative_id"], action="delete", resource_type="creative",
                resource_id_field="creative_id", intent_types=["delete_creative"], traits=["write", "creative"],
                write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["creative_id"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_lead_form",
                description="查询 Meta Lead Ads Instant Form 详情。", method_name="get_lead_form",
                result_key="lead_form", properties={
                    "page_id": {"type": "string"},
                    "form_id": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                }, required=["page_id", "form_id"], action="get", resource_type="lead_form",
                resource_id_field="form_id", intent_types=["get_lead_form"], traits=["read", "lead_form"],
                argument_builder=lambda _ctx, data: ((data["page_id"], data["form_id"]), {
                    "fields": data.get("fields"),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_create_lead_form",
                description="创建 Meta Lead Ads Instant Form；默认仅生成 dry-run 计划。",
                method_name="create_lead_form", result_key="lead_form_id",
                properties=lead_form_schema["properties"],
                required=lead_form_schema["required"],
                provider_required=lead_form_schema["provider_required"],
                action="create", resource_type="lead_form",
                parent_resource_type="page", parent_resource_id_field="page_id",
                intent_types=["create_lead_form"], traits=["write", "lead_form"],
                write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((data["page_id"], {
                    key: value for key, value in data.items()
                    if key not in {"account_id", "page_id", "form_id", "fields", "limit", "updates"}
                }), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_update_lead_form",
                description="更新 Meta Lead Ads Instant Form 名称；默认仅生成 dry-run 计划。",
                method_name="update_lead_form", result_key="lead_form",
                properties=lead_form_schema["properties"],
                required=lead_form_schema["update_required"],
                action="update", resource_type="lead_form",
                parent_resource_type="page", resource_id_field="form_id",
                parent_resource_id_field="page_id",
                intent_types=["update_lead_form"], traits=["write", "lead_form"],
                write=True, live_support=False,
                argument_builder=lambda _ctx, data: ((
                    data["page_id"], data["form_id"], data["updates"]
                ), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_list_accounts",
                description="列出 Meta 可访问的广告账户。", method_name="list_accounts",
                result_key="accounts", properties={"business_id": {"type": "string"}},
                argument_builder=lambda _ctx, data: ((data.get("business_id"),), {}),
                action="list", resource_type="account", intent_types=["list_accounts"],
                traits=["read", "account"],
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_account",
                description="获取 Meta 广告账户详情。", method_name="get_account",
                result_key="account", properties={
                    "account_id": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                }, required=["account_id"], action="get", resource_type="account",
                intent_types=["get_account"], traits=["read", "account"],
                argument_builder=lambda ctx, data: ((account_from(ctx, data, "account_id"),), {
                    "fields": data.get("fields")
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_list_catalogs",
                description="查询 Meta 商品目录。", method_name="list_catalogs",
                result_key="catalogs", properties={
                    "account_id": {"type": "string"},
                    "limit": {"type": "integer"},
                }, required=["account_id"], action="list", resource_type="catalog",
                intent_types=["list_catalogs"], traits=["read", "catalog"],
                argument_builder=lambda ctx, data: ((account_from(ctx, data, "account_id"),), {
                    "limit": data.get("limit", 25),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_list_product_sets",
                description="查询 Meta 商品目录下的商品集。", method_name="list_product_sets",
                result_key="product_sets", properties={
                    "account_id": {"type": "string"},
                    "catalog_id": {"type": "string"},
                    "limit": {"type": "integer"},
                }, required=["account_id", "catalog_id"], action="list", resource_type="product_set",
                intent_types=["list_product_sets"], traits=["read", "catalog", "product_set"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"]), {
                    "limit": data.get("limit", 25),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_catalog",
                description="查询 Meta 商品目录详情。", method_name="get_catalog",
                result_key="catalog", properties={
                    key: catalog_properties[key] for key in ("account_id", "catalog_id", "fields")
                }, required=["account_id", "catalog_id"], action="get", resource_type="catalog",
                resource_id_field="catalog_id", intent_types=["get_catalog"], traits=["read", "catalog"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"]), {
                    "fields": data.get("fields"),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_create_catalog",
                description="创建 Meta 商品目录；默认仅生成 dry-run 计划。",
                method_name="create_catalog", result_key="catalog_id", properties={
                    key: catalog_properties[key] for key in ("business_id", "name", "vertical", "is_checkout")
                }, required=catalog_schema["create_required"], action="create", resource_type="catalog",
                resource_id_field="catalog_id", intent_types=["create_catalog"], traits=["write", "catalog"], write=True,
                argument_builder=lambda _ctx, data: ((data["business_id"], {
                    key: data[key] for key in ("name", "vertical", "is_checkout") if key in data
                }), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_update_catalog",
                description="更新 Meta 商品目录名称；默认仅生成 dry-run 计划。",
                method_name="update_catalog", result_key="catalog_result", properties={
                    key: catalog_properties[key] for key in ("account_id", "catalog_id", "updates")
                }, required=catalog_schema["update_required"], action="update", resource_type="catalog",
                resource_id_field="catalog_id", intent_types=["update_catalog"], traits=["write", "catalog"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_delete_catalog",
                description="删除 Meta 商品目录；默认仅生成 dry-run 计划。",
                method_name="delete_catalog", result_key="catalog_result", properties={
                    key: catalog_properties[key] for key in ("account_id", "catalog_id")
                }, required=["account_id", "catalog_id"], action="delete", resource_type="catalog",
                resource_id_field="catalog_id", intent_types=["delete_catalog"], traits=["write", "catalog"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_product_set",
                description="查询 Meta 商品集详情。", method_name="get_product_set",
                result_key="product_set", properties={
                    key: product_set_properties[key] for key in ("account_id", "catalog_id", "product_set_id", "fields")
                }, required=product_set_schema["get_required"], action="get", resource_type="product_set",
                parent_resource_type="catalog", resource_id_field="product_set_id",
                parent_resource_id_field="catalog_id", intent_types=["get_product_set"], traits=["read", "catalog", "product_set"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"], data["product_set_id"]), {
                    "fields": data.get("fields"),
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_create_product_set",
                description="在 Meta 商品目录下创建商品集；默认仅生成 dry-run 计划。",
                method_name="create_product_set", result_key="product_set_id", properties={
                    key: product_set_properties[key] for key in ("account_id", "catalog_id", "name", "filter")
                }, required=product_set_schema["create_required"], action="create", resource_type="product_set",
                parent_resource_type="catalog", resource_id_field="product_set_id", parent_resource_id_field="catalog_id",
                intent_types=["create_product_set"], traits=["write", "catalog", "product_set"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"], {
                    key: data[key] for key in ("name", "filter") if key in data
                }), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_update_product_set",
                description="更新 Meta 商品集名称或筛选条件；默认仅生成 dry-run 计划。",
                method_name="update_product_set", result_key="product_set_result", properties={
                    key: product_set_properties[key] for key in ("account_id", "catalog_id", "product_set_id", "updates")
                }, required=product_set_schema["update_required"], action="update", resource_type="product_set",
                parent_resource_type="catalog", resource_id_field="product_set_id", parent_resource_id_field="catalog_id",
                intent_types=["update_product_set"], traits=["write", "catalog", "product_set"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"], data["product_set_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_delete_product_set",
                description="删除 Meta 商品集；默认仅生成 dry-run 计划。",
                method_name="delete_product_set", result_key="product_set_result", properties={
                    key: product_set_properties[key] for key in ("account_id", "catalog_id", "product_set_id")
                }, required=product_set_schema["get_required"], action="delete", resource_type="product_set",
                parent_resource_type="catalog", resource_id_field="product_set_id", parent_resource_id_field="catalog_id",
                intent_types=["delete_product_set"], traits=["write", "catalog", "product_set"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["catalog_id"], data["product_set_id"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_adset_report",
                description="查询 Meta Ad Set 级报表。", method_name="get_adset_report",
                result_key="report", properties={
                    "account_id": {"type": "string"},
                    "adset_ids": {"type": "array", "items": {"type": "string"}},
                    "date_range": {"type": "object"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                }, required=["account_id", "adset_ids"], action="report",
                resource_type="ad_set", intent_types=["download_report"], traits=["read", "report", "ad_set"],
                argument_builder=lambda ctx, data: ((account_from(ctx, data, "account_id"), data["adset_ids"]), {
                    "time_range": data.get("date_range"), "fields": data.get("fields")
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_ad_report",
                description="查询 Meta Ad 级报表。", method_name="get_ad_report",
                result_key="report", properties={
                    "account_id": {"type": "string"},
                    "ad_ids": {"type": "array", "items": {"type": "string"}},
                    "date_range": {"type": "object"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                }, required=["account_id", "ad_ids"], action="report",
                resource_type="ad", intent_types=["download_report"], traits=["read", "report", "ad"],
                argument_builder=lambda ctx, data: ((account_from(ctx, data, "account_id"), data["ad_ids"]), {
                    "time_range": data.get("date_range"), "fields": data.get("fields")
                }),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_create_lead_ad",
                description="创建 Meta Lead Ads Instant Form 广告；默认仅生成 dry-run 计划。",
                method_name="create_lead_ad", result_key="ad_id",
                properties=meta_lead_ad_schema()["properties"],
                required=meta_lead_ad_schema()["required"],
                provider_required=meta_lead_ad_schema()["provider_required"],
                action="create", resource_type="ad", parent_resource_type="ad_set",
                resource_id_field="ad_id", parent_resource_id_field="adset_id",
                intent_types=["create_lead_ad"], traits=["write", "ad", "lead", "instant_form"], write=True,
                argument_builder=lambda ctx, data: ((account_from(ctx, data, "account_id"), data["adset_id"], {
                    key: data[key] for key in (
                        "name", "page_id", "form_id", "link", "message", "headline",
                        "description", "call_to_action_type", "status",
                    ) if key in data
                }), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_create_catalog_ad",
                description="创建 Meta Catalog/Dynamic Product Ad；默认仅生成 dry-run 计划。",
                method_name="create_catalog_ad", result_key="ad_id",
                properties=meta_catalog_ad_schema()["properties"],
                required=meta_catalog_ad_schema()["required"],
                provider_required=meta_catalog_ad_schema()["provider_required"],
                action="create", resource_type="ad", parent_resource_type="ad_set",
                resource_id_field="ad_id", parent_resource_id_field="adset_id",
                intent_types=["create_catalog_ad"],
                traits=["write", "ad", "catalog", "dynamic_product"], write=True,
                argument_builder=lambda ctx, data: ((account_from(ctx, data, "account_id"), data["adset_id"], {
                    key: data[key] for key in (
                        "name", "page_id", "product_set_id", "link", "message",
                        "headline", "description", "ad_style", "call_to_action_type", "status",
                    ) if key in data
                }), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_get_audience",
                description="查询 Meta Custom 或 Lookalike Audience 详情。", method_name="get_audience",
                result_key="audience", properties={
                    key: audience_properties[key] for key in ("account_id", "audience_id")
                }, required=["account_id", "audience_id"], action="get", resource_type="audience",
                resource_id_field="audience_id", intent_types=["get_audience"], traits=["read", "audience"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["audience_id"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_create_audience",
                description="创建 Meta Custom 或 Lookalike Audience；默认仅生成 dry-run 计划。",
                method_name="create_audience", result_key="audience_id", properties={
                    key: audience_properties[key] for key in (
                        "account_id", "name", "subtype", "description", "customer_file_source",
                        "retention_days", "rule", "prefill", "pixel_id", "event_source_group",
                        "origin_audience_id", "country", "ratio", "lookalike_type",
                    )
                }, required=["account_id", "name", "subtype"],
                provider_required=["name", "subtype"],
                conditional_rules=audience_schema["conditional_rules"], action="create", resource_type="audience",
                resource_id_field="audience_id", intent_types=["create_audience"], traits=["write", "audience"],
                write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), {
                    key: value for key, value in data.items() if key != "account_id"
                }), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_update_audience",
                description="更新 Meta Audience 的名称、描述、规则或来源属性；默认仅生成 dry-run 计划。",
                method_name="update_audience", result_key="audience_result", properties={
                    key: audience_properties[key] for key in ("account_id", "audience_id", "updates")
                }, required=["account_id", "audience_id", "updates"], action="update", resource_type="audience",
                resource_id_field="audience_id", intent_types=["update_audience"], traits=["write", "audience"],
                write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["audience_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="meta", skill="meta-marketing-api", name="meta_delete_audience",
                description="删除 Meta Custom 或 Lookalike Audience；默认仅生成 dry-run 计划。",
                method_name="delete_audience", result_key="audience_result", properties={
                    key: audience_properties[key] for key in ("account_id", "audience_id")
                }, required=["account_id", "audience_id"], action="delete", resource_type="audience",
                resource_id_field="audience_id", intent_types=["delete_audience"], traits=["write", "audience"],
                write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["audience_id"]), {}),
            ),
        ]
        for method_name, resource_type, resource_id, intent in (
            ("pause_campaign", "campaign", "campaign_id", "pause_campaign"),
            ("resume_campaign", "campaign", "campaign_id", "resume_campaign"),
            ("pause_adset", "ad_set", "adset_id", "pause_adset"),
            ("pause_ad", "ad", "ad_id", "pause_ad"),
        ):
            tools.append(method_tool(
                platform="meta", skill="meta-marketing-api", name=f"meta_{method_name}",
                description=f"调用 Meta {method_name} 管理接口；默认仅生成 dry-run 计划。",
                method_name=method_name, result_key=f"{resource_type}_result",
                properties={resource_id: {"type": "string"}}, required=[resource_id],
                action=method_name.split("_", 1)[0], resource_type=resource_type,
                resource_id_field=resource_id, intent_types=[f"provider_{intent}"],
                traits=["write", resource_type], write=True,
                argument_builder=lambda _ctx, data, field=resource_id: ((data[field],), {}),
            ))
        return [bind_provider_method(tool, client) for tool in tools]

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
            input_schema=ToolSchema(**meta_campaign_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
            live_support=False,
            resource_id_field="campaign_id",
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
            input_schema=ToolSchema(**meta_adset_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad_set"],
            live_support=False,
            resource_id_field="adset_id",
            parent_resource_id_field="campaign_id",
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
            parent_resource_type="ad_set",
            parent_resource_id_field="adset_id",
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
            parent_resource_type="ad_set",
        ), MetaGetAdHandler(api_client)))

        # Create Ad
        tools.append((ToolDefinition(
            name="meta_create_ad",
            skill="meta-marketing-api",
            platform="meta",
            description="创建 Meta Ad。",
            input_schema=ToolSchema(**meta_ad_schema()),
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
            live_support=False,
            resource_id_field="ad_id",
            parent_resource_type="ad_set",
            parent_resource_id_field="adset_id",
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
                    "date_preset": {
                        "type": "string",
                        "intent_field": "date_range",
                        "intent_map": {
                            "LAST_7_DAYS": "last_7d",
                            "LAST_14_DAYS": "last_14d",
                            "LAST_30_DAYS": "last_30d",
                        },
                    },
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
            live_support=False,
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
            resource_id_field="creative_id",
        ), MetaCreateCreativeHandler(api_client)))

        # Update tools: dry-run 可完整生成计划；live 仅调用已存在的 Client 方法。
        for resource_type, resource_id, tool_suffix in [
            ("campaign", "campaign_id", "campaign"),
            ("ad_set", "adset_id", "adset"),
            ("ad", "ad_id", "ad"),
        ]:
            tools.append((ToolDefinition(
                name=f"meta_update_{tool_suffix}",
                skill="meta-marketing-api",
                platform="meta",
                description=f"更新 Meta {resource_type}，默认仅生成 dry-run 计划。",
                input_schema=ToolSchema(
                    required=[resource_id, "updates"],
                    properties={
                        resource_id: {"type": "string"},
                        "updates": meta_updates(tool_suffix),
                    },
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                live_support=False,
                resource_id_field=resource_id,
            ), CampaignUpdateHandler(
                api_client, resource_type, _meta_update_adapter,
                resource_id_field=resource_id,
                parent_resource_id_field={
                    "ad_set": "campaign_id", "ad": "adset_id",
                }.get(resource_type),
            )))

        tools.extend(self._extended_provider_tools(api_client))

        return tools

def create_meta_capability(api_client: Optional[MetaAPIClient] = None) -> MetaCapability:
    cap = MetaCapability()
    cap._api_client = api_client
    return cap
