"""
capabilities/dv360/capability.py - DV360 Capability 定义
"""
import logging
from typing import Optional
from ...core.interfaces import ToolDefinition, ToolSchema, RiskLevel, ToolEffect, ReplayPolicy, ToolHandler
from ..base import BaseCapability, CampaignUpdateHandler
from ..provider_tools import account_from, bind_provider_method, method_tool
from .campaigns import (
    DV360ListCampaignsHandler,
    DV360GetCampaignHandler,
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
from .parameters import dv360_io_schema, dv360_line_item_schema

logger = logging.getLogger(__name__)


class DV360Capability(BaseCapability):
    platform_name = "dv360"
    provider_client_class = DV360APIClient
    capability_version = "1.2.0"
    provider_api_version = "v4"
    provider_method_coverage = {
        "list_advertisers": ["dv360_list_advertisers"], "get_advertiser": ["dv360_get_advertiser"],
        "list_campaigns": ["dv360_list_campaigns"], "get_campaign": ["dv360_get_campaign"],
        "delete_campaign": ["dv360_delete_campaign"],
        "update_resource": [
            "dv360_update_campaign", "dv360_update_io", "dv360_update_line_item",
        ],
        "list_ios": ["dv360_list_ios"], "get_io": ["dv360_get_io"], "create_io": ["dv360_create_io"],
        "delete_io": ["dv360_delete_io"],
        "activate_io": ["dv360_activate_io"], "pause_io": ["dv360_pause_io"],
        "list_line_items": ["dv360_list_line_items"], "create_line_item": ["dv360_create_line_item"],
        "delete_line_item": ["dv360_delete_line_item"],
        "activate_line_item": ["dv360_activate_line_item"], "get_line_item": ["dv360_get_line_item"],
        "list_creatives": ["dv360_list_creatives"], "get_creative": ["dv360_get_creative"],
        "create_creative": ["dv360_create_creative"], "update_creative": ["dv360_update_creative"],
        "delete_creative": ["dv360_delete_creative"],
        "list_targeting_options": ["dv360_list_targeting_options"],
        "list_line_item_assigned_targeting_options": ["dv360_list_line_item_assigned_targeting_options"],
        "create_line_item_assigned_targeting_option": ["dv360_create_line_item_assigned_targeting_option"],
        "delete_line_item_assigned_targeting_option": ["dv360_delete_line_item_assigned_targeting_option"],
        "create_report": ["dv360_create_report", "dv360_get_line_item_report"],
        "get_report_result": ["dv360_get_report_result", "dv360_get_line_item_report"],
        "get_line_item_report": ["dv360_get_line_item_report"],
    }

    def _extended_provider_tools(self, client):
        """Expose DV360 advertiser, lifecycle and asynchronous report APIs."""
        account = lambda ctx, data: account_from(ctx, data, "advertiser_id", "account_id")
        tools = [
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_delete_campaign",
                description="删除 DV360 Campaign；默认仅生成 dry-run 计划。",
                method_name="delete_campaign", result_key="campaign_result",
                properties={"advertiser_id": {"type": "string"}, "campaign_id": {"type": "string"}},
                required=["advertiser_id", "campaign_id"], action="delete", resource_type="campaign",
                resource_id_field="campaign_id",
                intent_types=["delete_campaign", "cross_channel_batch_delete"],
                traits=["write", "campaign"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["campaign_id"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_delete_io",
                description="删除 DV360 Insertion Order；默认仅生成 dry-run 计划。",
                method_name="delete_io", result_key="io_result",
                properties={"advertiser_id": {"type": "string"}, "io_id": {"type": "string"}},
                required=["advertiser_id", "io_id"], action="delete", resource_type="io",
                resource_id_field="io_id", intent_types=["delete_io"], traits=["write", "io"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["io_id"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_delete_line_item",
                description="删除 DV360 Line Item；默认仅生成 dry-run 计划。",
                method_name="delete_line_item", result_key="line_item_result",
                properties={"advertiser_id": {"type": "string"}, "io_id": {"type": "string"},
                            "line_item_id": {"type": "string"}},
                required=["advertiser_id", "io_id", "line_item_id"], action="delete", resource_type="line_item",
                parent_resource_type="io", resource_id_field="line_item_id", parent_resource_id_field="io_id",
                intent_types=["delete_line_item"], traits=["write", "line_item"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["io_id"], data["line_item_id"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_list_creatives",
                description="查询 DV360 Advertiser 下的 Creative 列表。", method_name="list_creatives",
                result_key="creatives", properties={"advertiser_id": {"type": "string"},
                "filter": {"type": "string"}, "limit": {"type": "integer"}},
                required=["advertiser_id"], action="list", resource_type="creative",
                intent_types=["list_creatives"], traits=["read", "creative"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {
                    "filter": data.get("filter"), "page_size": data.get("limit", 20)
                }),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_get_creative",
                description="查询 DV360 Creative 详情。", method_name="get_creative", result_key="creative",
                properties={"advertiser_id": {"type": "string"}, "creative_id": {"type": "string"}},
                required=["advertiser_id", "creative_id"], action="get", resource_type="creative",
                resource_id_field="creative_id", intent_types=["get_creative"], traits=["read", "creative"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["creative_id"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_create_creative",
                description="创建 DV360 Creative；默认仅生成 dry-run 计划。", method_name="create_creative",
                result_key="creative_id", properties={"advertiser_id": {"type": "string"},
                "creative": {
                    "type": "object",
                    "description": "DV360 Creative provider payload",
                    "additionalProperties": True,
                    "manual_entry": {
                        "title": "DV360 Creative Payload",
                        "instructions": "请填写已按 DV360 Creative API 准备好的对象；DV360 专用字段暂按现有能力保留为高级 Provider 输入。",
                        "source": "provider_creative_payload",
                    },
                }}, required=["advertiser_id", "creative"], action="create",
                resource_type="creative", resource_id_field="creative_id", intent_types=["create_creative"],
                traits=["write", "creative"], write=True,
                provider_required=["creative"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["creative"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_update_creative",
                description="更新 DV360 Creative；默认仅生成 dry-run 计划。", method_name="update_creative",
                result_key="creative_result", properties={"advertiser_id": {"type": "string"},
                "creative_id": {"type": "string"}, "updates": {"type": "object"}},
                required=["advertiser_id", "creative_id", "updates"], action="update", resource_type="creative",
                resource_id_field="creative_id", intent_types=["update_creative"], traits=["write", "creative"],
                write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["creative_id"], data["updates"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_delete_creative",
                description="删除 DV360 Creative；默认仅生成 dry-run 计划。", method_name="delete_creative",
                result_key="creative_result", properties={"advertiser_id": {"type": "string"},
                "creative_id": {"type": "string"}}, required=["advertiser_id", "creative_id"], action="delete",
                resource_type="creative", resource_id_field="creative_id", intent_types=["delete_creative"],
                traits=["write", "creative"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["creative_id"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_list_targeting_options",
                description="查询 DV360 Targeting Option 目录（枚举/参考数据）。", method_name="list_targeting_options",
                result_key="targeting_options", properties={"targeting_type": {"type": "string"},
                "filter": {"type": "string"}, "limit": {"type": "integer"}},
                required=["targeting_type"], action="list", resource_type="targeting_option",
                intent_types=["list_targeting_options"], traits=["read", "targeting"],
                argument_builder=lambda _ctx, data: ((data["targeting_type"],), {
                    "filter": data.get("filter"), "page_size": data.get("limit", 100)
                }),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_list_line_item_assigned_targeting_options",
                description="查询 DV360 Line Item 已绑定的定向选项。",
                method_name="list_line_item_assigned_targeting_options", result_key="assigned_targeting_options",
                properties={"advertiser_id": {"type": "string"}, "line_item_id": {"type": "string"},
                            "targeting_type": {"type": "string"}, "limit": {"type": "integer"}},
                required=["advertiser_id", "line_item_id", "targeting_type"], action="list",
                resource_type="targeting_assignment", parent_resource_type="line_item",
                parent_resource_id_field="line_item_id", intent_types=["list_targeting_assignments"],
                traits=["read", "targeting"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["line_item_id"], data["targeting_type"]), {
                    "page_size": data.get("limit", 100)
                }),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_create_line_item_assigned_targeting_option",
                description="为 DV360 Line Item 绑定定向选项；默认仅生成 dry-run 计划。",
                method_name="create_line_item_assigned_targeting_option", result_key="assigned_targeting_option_id",
                properties={"advertiser_id": {"type": "string"}, "line_item_id": {"type": "string"},
                            "targeting_type": {"type": "string"}, "assigned_targeting_option": {"type": "object"}},
                required=["advertiser_id", "line_item_id", "targeting_type", "assigned_targeting_option"],
                action="create", resource_type="targeting_assignment", parent_resource_type="line_item",
                resource_id_field="assigned_targeting_option_id", parent_resource_id_field="line_item_id",
                intent_types=["create_targeting_assignment"], traits=["write", "targeting"], write=True,
                provider_required=["targeting_type", "assigned_targeting_option"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["line_item_id"], data["targeting_type"],
                    data["assigned_targeting_option"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_delete_line_item_assigned_targeting_option",
                description="解除 DV360 Line Item 的定向绑定；默认仅生成 dry-run 计划。",
                method_name="delete_line_item_assigned_targeting_option", result_key="targeting_result",
                properties={"advertiser_id": {"type": "string"}, "line_item_id": {"type": "string"},
                            "targeting_type": {"type": "string"}, "assigned_targeting_option_id": {"type": "string"}},
                required=["advertiser_id", "line_item_id", "targeting_type", "assigned_targeting_option_id"],
                action="delete", resource_type="targeting_assignment", parent_resource_type="line_item",
                resource_id_field="assigned_targeting_option_id", parent_resource_id_field="line_item_id",
                intent_types=["delete_targeting_assignment"], traits=["write", "targeting"], write=True,
                argument_builder=lambda ctx, data: ((account(ctx, data), data["line_item_id"], data["targeting_type"],
                    data["assigned_targeting_option_id"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_get_advertiser",
                description="获取 DV360 Advertiser 详情。", method_name="get_advertiser",
                result_key="advertiser", properties={"advertiser_id": {"type": "string"}},
                required=["advertiser_id"], action="get", resource_type="advertiser",
                intent_types=["get_advertiser"], traits=["read", "advertiser"],
                argument_builder=lambda ctx, data: ((account(ctx, data),), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_create_report",
                description="创建 DV360 异步报表任务；默认仅生成 dry-run 计划。",
                method_name="create_report", result_key="report_id",
                properties={"advertiser_id": {"type": "string"}, "report": {"type": "object"}},
                required=["advertiser_id", "report"], action="create", resource_type="report",
                resource_id_field="report_id",
                intent_types=["create_report"], traits=["write", "report"], write=True,
                provider_required=["report"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["report"]), {}),
            ),
            method_tool(
                platform="dv360", skill="dv360-api", name="dv360_get_report_result",
                description="获取 DV360 异步报表结果。", method_name="get_report_result", result_key="report",
                properties={"advertiser_id": {"type": "string"}, "report_id": {"type": "string"},
                            "limit": {"type": "integer"}},
                required=["advertiser_id", "report_id"], action="get", resource_type="report",
                intent_types=["get_report_result"], traits=["read", "report"],
                argument_builder=lambda ctx, data: ((account(ctx, data), data["report_id"]), {
                    "limit": data.get("limit", 1000)
                }),
            ),
        ]
        for method_name, resource_type, resource_id, intent in (
            ("activate_io", "io", "io_id", "activate_io"),
            ("pause_io", "io", "io_id", "pause_io"),
        ):
            tools.append(method_tool(
                platform="dv360", skill="dv360-api", name=f"dv360_{method_name}",
                description=f"调用 DV360 {method_name} 管理接口；默认仅生成 dry-run 计划。",
                method_name=method_name, result_key="io_result",
                properties={"advertiser_id": {"type": "string"}, resource_id: {"type": "string"}},
                required=["advertiser_id", resource_id], action=method_name.split("_", 1)[0],
                resource_type=resource_type, resource_id_field=resource_id, intent_types=[intent],
                traits=["write", resource_type], write=True,
                argument_builder=lambda ctx, data, field=resource_id: ((account(ctx, data), data[field]), {}),
            ))
        tools.append(method_tool(
            platform="dv360", skill="dv360-api", name="dv360_activate_line_item",
            description="激活 DV360 Line Item；默认仅生成 dry-run 计划。",
            method_name="activate_line_item", result_key="line_item_result",
            properties={"advertiser_id": {"type": "string"}, "io_id": {"type": "string"},
                        "line_item_id": {"type": "string"}},
            required=["advertiser_id", "io_id", "line_item_id"], action="activate",
            resource_type="line_item", parent_resource_type="io", resource_id_field="line_item_id",
            parent_resource_id_field="io_id", intent_types=["activate_line_item"],
            traits=["write", "line_item"], write=True,
            argument_builder=lambda ctx, data: ((account(ctx, data), data["io_id"], data["line_item_id"]), {}),
        ))
        return [bind_provider_method(tool, client) for tool in tools]

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
            action="list", resource_type="campaign", intent_types=[
                "list_campaigns", "cross_channel_overview", "cross_channel_compare",
                "cross_channel_performance_insights", "cross_channel_optimize_budget",
                "cross_channel_export_report",
            ],
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
            action="get", resource_type="campaign", resource_id_field="campaign_id",
            intent_types=["get_campaign"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "campaign"],
        ), DV360GetCampaignHandler(api_client)))

        tools.append((ToolDefinition(
            name="dv360_list_ios",
            skill="dv360-api",
            platform="dv360",
            description="查询 DV360 Insertion Order 列表。",
            input_schema=ToolSchema(
                required=["advertiser_id"],
                properties={"advertiser_id": {"type": "string"}, "limit": {"type": "integer"}},
            ),
            action="list", resource_type="io", parent_resource_type="campaign",
            intent_types=["list_ios"],
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
            action="get", resource_type="io", parent_resource_type="campaign",
            resource_id_field="io_id",
            intent_types=["get_io"],
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
            action="list", resource_type="advertiser", intent_types=["list_advertisers"],
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
            input_schema=ToolSchema(**dv360_io_schema()),
            action="create", resource_type="io", parent_resource_type="campaign",
            intent_types=["create_io", "create_campaign"],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "io"],
            live_support=False,
            resource_id_field="io_id",
            parent_resource_id_field="campaign_id",
        ), DV360CreateIOHandler(api_client)))

        # Create Line Item
        tools.append((ToolDefinition(
            name="dv360_create_line_item",
            skill="dv360-api",
            platform="dv360",
            description="创建 DV360 Line Item。",
            input_schema=ToolSchema(**dv360_line_item_schema()),
            action="create", resource_type="line_item", parent_resource_type="io",
            intent_types=["create_line_item", "create_campaign"],
            risk_level=RiskLevel.MEDIUM,
            effect_class=ToolEffect.WRITE,
            replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "line_item"],
            live_support=False,
            resource_id_field="line_item_id",
            parent_resource_id_field="io_id",
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
            action="list", resource_type="line_item", parent_resource_type="io",
            parent_resource_id_field="io_id",
            intent_types=["list_line_items"],
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
            action="get", resource_type="line_item", parent_resource_type="io",
            resource_id_field="line_item_id", parent_resource_id_field="io_id",
            intent_types=["get_line_item"],
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
            action="report", resource_type="report", intent_types=["download_report"],
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,
            replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
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
                action="update", resource_type=resource_type,
                parent_resource_type={"io": "campaign", "line_item": "io"}.get(resource_type),
                intent_types={
                    "campaign": [
                        "update_campaign", "pause_campaign", "resume_campaign",
                        "cross_channel_batch_pause", "cross_channel_batch_resume",
                        "cross_channel_batch_update_budget",
                    ],
                    "io": ["update_io"],
                    "line_item": ["update_line_item"],
                }[resource_type],
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", resource_type],
                live_support=False,
                resource_id_field=resource_id,
                parent_resource_id_field=(
                    "io_id" if resource_type == "line_item" else None
                ),
            ), CampaignUpdateHandler(api_client, resource_type)))

        tools.extend(self._extended_provider_tools(api_client))

        return tools

def create_dv360_capability(api_client: Optional[DV360APIClient] = None) -> DV360Capability:
    cap = DV360Capability()
    cap._api_client = api_client
    return cap
