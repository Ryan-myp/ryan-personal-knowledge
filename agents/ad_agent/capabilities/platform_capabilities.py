"""
capabilities/google_capability.py - Google Ads Capability
capabilities/tiktok_capability.py - TikTok Ads Capability
capabilities/dv360_capability.py - DV360 Capability
"""

# ─── Google Ads ────────────────────────────────────────────────

from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from .base import BaseCapability


class GoogleCreateCampaignHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = f"google_{input_data.get('campaign_name', 'unknown')}_{ctx.session_id[:6]}"
        return ToolResult.ok({
            "campaign_id": campaign_id,
            "resource_name": f"customers/{ctx.account_id or '000'}/campaigns/{campaign_id}",
            "name": input_data.get("campaign_name"),
            "advertising_channel_type": input_data.get("advertising_channel_type", "SEARCH"),
            "bidding_strategy": input_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
            "status": "ENABLED",
        })


class GoogleCreateAdGroupHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = f"ag_{input_data.get('campaign_id')}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_group_id": adgroup_id,
            "campaign_id": input_data.get("campaign_id"),
            "name": input_data.get("name", "Ad Group"),
            "cpc_bid_micros": input_data.get("cpc_bid_micros", 500000),  # $0.05
            "status": "ENABLED",
        })


class GoogleCreateAdHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = f"ad_{input_data.get('ad_group_id')}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_id": ad_id,
            "ad_group_id": input_data.get("ad_group_id"),
            "name": input_data.get("name", "Ad"),
            "type": input_data.get("ad_type", "TEXT_AD"),
        })


class GoogleGetReportHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        return ToolResult.ok({
            "campaign_id": input_data.get("campaign_id"),
            "metrics": {"impressions": 250000, "clicks": 5600, "cost_micros": 84000000},
        })


class GoogleCapability(BaseCapability):
    platform_name = "google"
    
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        
        tools.append((
            ToolDefinition(
                name="google_create_campaign",
                skill="google-ads-api-expert",
                platform="google",
                description="在 Google Ads 中创建广告系列。支持 SEARCH、SHOPPING、VIDEO、DISPLAY、APP、MAX（PMax）等渠道类型。",
                input_schema=ToolSchema(
                    required=["campaign_name", "advertising_channel_type", "bidding_strategy"],
                    properties={
                        "campaign_name": {"type": "string"},
                        "advertising_channel_type": {
                            "type": "string",
                            "enum": ["SEARCH", "SHOPPING", "VIDEO", "DISPLAY", "APP", "MAX"],
                        },
                        "bidding_strategy": {
                            "type": "string",
                            "enum": ["MANUAL_CPC", "TARGET_CPA", "MAXIMIZE_CONVERSIONS", "TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE"],
                        },
                        "campaign_budget": {"type": "number", "description": "日预算（元）"},
                        "network_setting": {"type": "object"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "campaign"],
            ),
            GoogleCreateCampaignHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="google_create_ad_group",
                skill="google-ads-api-expert",
                platform="google",
                description="在 Campaign 下创建广告组（Ad Group）。支持搜索广告组、PMax Asset Group 等。",
                input_schema=ToolSchema(
                    required=["campaign_id", "name"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "name": {"type": "string"},
                        "cpc_bid_micros": {"type": "number", "description": "CPC 出价（微单位）"},
                        "bidding_strategy_override": {"type": "object"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad_group"],
            ),
            GoogleCreateAdGroupHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="google_create_ad",
                skill="google-ads-api-expert",
                platform="google",
                description="在 Ad Group 下创建广告创意。支持文本广告、响应式展示广告、PMax Asset 等。",
                input_schema=ToolSchema(
                    required=["ad_group_id", "ad_type"],
                    properties={
                        "ad_group_id": {"type": "string"},
                        "ad_type": {"type": "string", "enum": ["TEXT_AD", "RESPONSIVE_SEARCH_AD", "RESPONSIVE_DISPLAY_AD", "PERFORMANCE_MAX_ASSET"]},
                        "name": {"type": "string"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad"],
            ),
            GoogleCreateAdHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="google_get_campaign_report",
                skill="google-ads-api-expert",
                platform="google",
                description="查询 Google Ads Campaign 报表，使用 GAQL 查询语言。",
                input_schema=ToolSchema(
                    required=["campaign_id"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "date_range": {"type": "object"},
                        "metrics": {"type": "array", "description": "指标列表，如 ['impressions', 'clicks', 'cost_micros']"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "report"],
            ),
            GoogleGetReportHandler(),
        ))
        
        return tools
    
    def _get_campaign_tool_sequence(self) -> list[str]:
        return ["google_create_campaign", "google_create_ad_group", "google_create_ad"]
    
    def _get_report_tool_sequence(self) -> list[str]:
        return ["google_get_campaign_report"]


def create_google_capability() -> BaseCapability:
    return GoogleCapability()


# ─── TikTok Ads ────────────────────────────────────────────────

class TikTokCreateCampaignHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = f"tiktok_{input_data.get('campaign_name', 'unknown')}_{ctx.session_id[:6]}"
        return ToolResult.ok({
            "campaign_id": campaign_id,
            "name": input_data.get("campaign_name"),
            "objective": input_data.get("objective", "PRODUCT_SALES"),
            "daily_budget": input_data.get("budget", 5000),  # 分
            "status": "ENABLED",
        })


class TikTokCreateAdGroupHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = f"ag_{input_data.get('campaign_id')}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_group_id": adgroup_id,
            "campaign_id": input_data.get("campaign_id"),
            "name": input_data.get("name", "Ad Group"),
            "bid_type": input_data.get("bid_type", "AUTO_BID"),
            "status": "ENABLED",
        })


class TikTokCreateAdHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = f"ad_{input_data.get('ad_group_id')}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_id": ad_id,
            "ad_group_id": input_data.get("ad_group_id"),
            "name": input_data.get("name", "Ad"),
        })


class TikTokSparkAdsHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        return ToolResult.ok({
            "spark_ad_id": f"spark_{input_data.get('spark_post_id')}_{ctx.session_id[:4]}",
            "spark_post_id": input_data.get("spark_post_id"),
            "status": "ENABLED",
        })


class TikTokGetReportHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        return ToolResult.ok({
            "campaign_id": input_data.get("campaign_id"),
            "metrics": {"impressions": 80000, "clicks": 2400, "cost": 360.00},
        })


class TikTokCapability(BaseCapability):
    platform_name = "tiktok"
    
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        
        tools.append((
            ToolDefinition(
                name="tiktok_create_campaign",
                skill="tiktok-ads-expert",
                platform="tiktok",
                description="在 TikTok Ads 中创建广告系列。支持产品营销、线索收集、应用推广等目标。",
                input_schema=ToolSchema(
                    required=["campaign_name", "objective", "budget"],
                    properties={
                        "campaign_name": {"type": "string"},
                        "objective": {
                            "type": "string",
                            "enum": ["PRODUCT_SALES", "LEAD_GENERATION", "APP_INSTALLS", "BRAND_AWARENESS", "TRAFFIC"],
                        },
                        "budget": {"type": "number", "description": "每日预算（元）"},
                        "budget_total": {"type": "number", "description": "总预算（元）"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "campaign"],
            ),
            TikTokCreateCampaignHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="tiktok_create_ad_group",
                skill="tiktok-ads-expert",
                platform="tiktok",
                description="在 Campaign 下创建广告组。设置出价策略、定向、素材等。",
                input_schema=ToolSchema(
                    required=["campaign_id", "name"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "name": {"type": "string"},
                        "bid_type": {"type": "string", "enum": ["AUTO_BID", "MANUAL_BID"]},
                        "bid_value": {"type": "number"},
                        "targeting": {"type": "object"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad_group"],
            ),
            TikTokCreateAdGroupHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="tiktok_create_ad",
                skill="tiktok-ads-expert",
                platform="tiktok",
                description="在 Ad Group 下创建广告。",
                input_schema=ToolSchema(
                    required=["ad_group_id"],
                    properties={
                        "ad_group_id": {"type": "string"},
                        "name": {"type": "string"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad"],
            ),
            TikTokCreateAdHandler(),
        ))
        
        # Spark Ads（达人原生广告）
        tools.append((
            ToolDefinition(
                name="tiktok_spark_ads_create",
                skill="tiktok-ads-expert",
                platform="tiktok",
                description="创建 Spark Ads（达人原生广告），使用达人已有视频进行投放。",
                input_schema=ToolSchema(
                    required=["campaign_id", "ad_group_id", "spark_post_id"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "ad_group_id": {"type": "string"},
                        "spark_post_id": {"type": "string", "description": "达人帖子 ID"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "spark"],
            ),
            TikTokSparkAdsHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="tiktok_get_campaign_report",
                skill="tiktok-ads-expert",
                platform="tiktok",
                description="查询 TikTok Campaign 报表。",
                input_schema=ToolSchema(
                    required=["campaign_id"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "date_range": {"type": "object"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "report"],
            ),
            TikTokGetReportHandler(),
        ))
        
        return tools
    
    def _get_campaign_tool_sequence(self) -> list[str]:
        return ["tiktok_create_campaign", "tiktok_create_ad_group", "tiktok_create_ad"]
    
    def _get_boost_tool_sequence(self) -> list[str]:
        return ["tiktok_spark_ads_create"]
    
    def _get_report_tool_sequence(self) -> list[str]:
        return ["tiktok_get_campaign_report"]


def create_tiktok_capability() -> BaseCapability:
    return TikTokCapability()


# ─── DV360 ─────────────────────────────────────────────────────

class DV360CreateCampaignHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = f"dv360_{input_data.get('campaign_name', 'unknown')}_{ctx.session_id[:6]}"
        return ToolResult.ok({
            "campaign_id": campaign_id,
            "name": input_data.get("campaign_name"),
            "goal_type": input_data.get("goal_type", "IMPRESSIONS"),
            "status": "ACTIVE",
        })


class DV360CreateIOHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        io_id = f"io_{input_data.get('campaign_id')}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "io_id": io_id,
            "campaign_id": input_data.get("campaign_id"),
            "name": input_data.get("name", "Insertion Order"),
            "funding_bundle_id": input_data.get("funding_bundle_id"),
        })


class DV360CreateLineItemHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        li_id = f"li_{input_data.get('io_id')}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "line_item_id": li_id,
            "io_id": input_data.get("io_id"),
            "type": input_data.get("type", "SPONSORED"),
            "status": "ACTIVE",
        })


class DV360GetReportHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        return ToolResult.ok({
            "line_item_id": input_data.get("line_item_id"),
            "metrics": {"impressions": 500000, "clicks": 12000, "cost": 6000.00},
        })


class DV360Capability(BaseCapability):
    platform_name = "dv360"
    
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        
        tools.append((
            ToolDefinition(
                name="dv360_create_campaign",
                skill="dv360-expert",
                platform="dv360",
                description="在 DV360 中创建广告系列。Campaign 是 DV360 的顶级资源。",
                input_schema=ToolSchema(
                    required=["campaign_name", "goal_type"],
                    properties={
                        "campaign_name": {"type": "string"},
                        "goal_type": {"type": "string", "enum": ["IMPRESSIONS", "CLICKS", "CONVERSIONS"]},
                        "status": {"type": "string", "default": "ACTIVE"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "campaign"],
            ),
            DV360CreateCampaignHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="dv360_create_io",
                skill="dv360-expert",
                platform="dv360",
                description="在 Campaign 下创建 Insertion Order（IO）。IO 是 DV360 的预算和订单管理单元。",
                input_schema=ToolSchema(
                    required=["campaign_id", "name"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "name": {"type": "string"},
                        "funding_bundle_id": {"type": "string", "description": "资金包 ID"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "io"],
            ),
            DV360CreateIOHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="dv360_create_line_item",
                skill="dv360-expert",
                platform="dv360",
                description="在 IO 下创建 Line Item。Line Item 定义具体的投放策略和目标。",
                input_schema=ToolSchema(
                    required=["io_id", "name", "type"],
                    properties={
                        "io_id": {"type": "string"},
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["SPONSORED", "RETARGETING", "BRANDED", "UNBRANDED"]},
                        "goal": {"type": "object", "description": "目标设置 {goal_type, ...}"},
                        "targeting": {"type": "object"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "line_item"],
            ),
            DV360CreateLineItemHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="dv360_get_line_item_report",
                skill="dv360-expert",
                platform="dv360",
                description="查询 DV360 Line Item 报表。",
                input_schema=ToolSchema(
                    required=["line_item_id"],
                    properties={
                        "line_item_id": {"type": "string"},
                        "date_range": {"type": "object"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "report"],
            ),
            DV360GetReportHandler(),
        ))
        
        return tools
    
    def _get_campaign_tool_sequence(self) -> list[str]:
        # DV360 层级：Campaign → IO → Line Item
        return ["dv360_create_campaign", "dv360_create_io", "dv360_create_line_item"]
    
    def _get_report_tool_sequence(self) -> list[str]:
        return ["dv360_get_line_item_report"]


def create_dv360_capability() -> BaseCapability:
    return DV360Capability()
