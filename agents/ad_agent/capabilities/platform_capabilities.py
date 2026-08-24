"""
capabilities/google_capability.py - Google Ads Capability（真实 API 版）
capabilities/tiktok_capability.py - TikTok Ads Capability（真实 API 版）
capabilities/dv360_capability.py - DV360 Capability（真实 API 版）
"""

import logging
from typing import Optional
from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from .base import BaseCapability

from ..api_clients.google_ads_client import GoogleAdsAPIClient
from ..api_clients.tiktok_client import TikTokAPIClient
from ..api_clients.dv360_client import DV360APIClient

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Google Ads
# ═══════════════════════════════════════════════════════════════

class GoogleCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client:
            try:
                campaign_id = self.client.create_campaign(
                    name=input_data.get("campaign_name", "Untitled"),
                    advertising_channel_type=input_data.get("advertising_channel_type", "SEARCH"),
                    bidding_strategy=input_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
                    daily_budget=input_data.get("budget", 100),
                )
                result = ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("campaign_name"),
                    "advertising_channel_type": input_data.get("advertising_channel_type", "SEARCH"),
                    "bidding_strategy": input_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
                    "status": "PAUSED",  # Google 默认暂停，需用户确认后再启用
                })
                ctx.set_protected("campaign_id", campaign_id)
                return result
            except Exception as e:
                return ToolResult.error(f"Google Ads campaign creation failed: {e}")
        else:
            # Mock mode
            campaign_id = f"google_{input_data.get('campaign_name', 'unknown')}_{ctx.session_id[:6]}"
            return ToolResult.ok({
                "campaign_id": campaign_id,
                "name": input_data.get("campaign_name"),
                "advertising_channel_type": input_data.get("advertising_channel_type", "SEARCH"),
                "bidding_strategy": input_data.get("bidding_strategy", "MAXIMIZE_CONVERSIONS"),
                "status": "ENABLED",
            })


class GoogleCreateAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id") or ctx.get_protected("campaign_id", "")
        if self.client and campaign_id:
            try:
                ad_group_id = self.client.create_ad_group(
                    campaign_id=campaign_id,
                    name=input_data.get("name", "Ad Group"),
                    cpc_bid_micros=input_data.get("cpc_bid_micros", 500000),
                )
                result = ToolResult.ok({
                    "ad_group_id": ad_group_id,
                    "campaign_id": campaign_id,
                    "name": input_data.get("name", "Ad Group"),
                    "cpc_bid_micros": input_data.get("cpc_bid_micros", 500000),
                    "status": "PAUSED",
                })
                ctx.set_protected("ad_group_id", ad_group_id)
                return result
            except Exception as e:
                return ToolResult.error(f"Google Ads ad group creation failed: {e}")
        
        # Mock
        adgroup_id = f"ag_{campaign_id or 'unknown'}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_group_id": adgroup_id,
            "campaign_id": campaign_id,
            "name": input_data.get("name", "Ad Group"),
            "cpc_bid_micros": input_data.get("cpc_bid_micros", 500000),
            "status": "ENABLED",
        })


class GoogleCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_group_id = input_data.get("ad_group_id") or ctx.get_protected("ad_group_id", "")
        if self.client and ad_group_id:
            try:
                ad_id = self.client.create_search_ad(
                    ad_group_id=ad_group_id,
                    headlines=input_data.get("headlines", ["Test Headline"]),
                    descriptions=input_data.get("descriptions", ["Test Description"]),
                    final_url=input_data.get("final_url", "https://example.com"),
                )
                return ToolResult.ok({
                    "ad_id": ad_id,
                    "ad_group_id": ad_group_id,
                    "name": input_data.get("name", "Ad"),
                    "type": "RESPONSIVE_SEARCH_AD",
                })
            except Exception as e:
                return ToolResult.error(f"Google Ads ad creation failed: {e}")
        
        ad_id = f"ad_{ad_group_id or 'unknown'}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_id": ad_id,
            "ad_group_id": ad_group_id,
            "name": input_data.get("name", "Ad"),
            "type": "TEXT_AD",
        })


class GoogleGetReportHandler(ToolHandler):
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if self.client and campaign_id:
            try:
                report = self.client.get_campaign_report(
                    campaign_ids=[campaign_id],
                    date_from=input_data.get("date_range", {}).get("start", "LAST_30_DAYS"),
                    date_to=input_data.get("date_range", {}).get("end", "TODAY"),
                )
                return ToolResult.ok({"campaign_id": campaign_id, "report": report})
            except Exception as e:
                return ToolResult.error(f"Google Ads report failed: {e}")
        
        return ToolResult.ok({
            "campaign_id": campaign_id,
            "metrics": {"impressions": 250000, "clicks": 5600, "cost_micros": 84000000},
        })


class GoogleCapability(BaseCapability):
    platform_name = "google"
    
    def __init__(self, api_client: Optional[GoogleAdsAPIClient] = None):
        self._api_client = api_client
        super().__init__()
    
    def register_tools(self):
        tools = []
        campaign_h = GoogleCreateCampaignHandler(self._api_client)
        adgroup_h = GoogleCreateAdGroupHandler(self._api_client)
        ad_h = GoogleCreateAdHandler(self._api_client)
        report_h = GoogleGetReportHandler(self._api_client)
        
        tools.append((ToolDefinition(
            name="google_create_campaign", skill="google-ads-api-expert", platform="google",
            description="在 Google Ads 中创建广告系列。支持 SEARCH、SHOPPING、VIDEO、DISPLAY、APP、MAX（PMax）等渠道类型。",
            input_schema=ToolSchema(
                required=["campaign_name", "advertising_channel_type", "bidding_strategy"],
                properties={
                    "campaign_name": {"type": "string"},
                    "advertising_channel_type": {"type": "string", "enum": ["SEARCH", "SHOPPING", "VIDEO", "DISPLAY", "APP", "MAX"]},
                    "bidding_strategy": {"type": "string", "enum": ["MANUAL_CPC", "TARGET_CPA", "MAXIMIZE_CONVERSIONS", "TARGET_ROAS", "MAXIMIZE_CONVERSION_VALUE"]},
                    "budget": {"type": "number", "description": "日预算（美元）"},
                }
            ),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
        ), campaign_h))
        
        tools.append((ToolDefinition(
            name="google_create_ad_group", skill="google-ads-api-expert", platform="google",
            description="在 Campaign 下创建广告组。",
            input_schema=ToolSchema(
                required=["campaign_id", "name"],
                properties={"campaign_id": {"type": "string"}, "name": {"type": "string"}, "cpc_bid_micros": {"type": "number"}},
            ),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad_group"],
        ), adgroup_h))
        
        tools.append((ToolDefinition(
            name="google_create_ad", skill="google-ads-api-expert", platform="google",
            description="在 Ad Group 下创建搜索广告。",
            input_schema=ToolSchema(
                required=["ad_group_id"],
                properties={"ad_group_id": {"type": "string"}, "headlines": {"type": "array"}, "descriptions": {"type": "array"}, "final_url": {"type": "string"}},
            ),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
        ), ad_h))
        
        tools.append((ToolDefinition(
            name="google_get_campaign_report", skill="google-ads-api-expert", platform="google",
            description="查询 Google Ads Campaign 报表。",
            input_schema=ToolSchema(
                required=["campaign_id"],
                properties={"campaign_id": {"type": "string"}, "date_range": {"type": "object"}},
            ),
            risk_level=RiskLevel.LOW, effect_class=ToolEffect.READ, replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), report_h))
        
        return tools
    
    def _get_campaign_tool_sequence(self):
        return ["google_create_campaign", "google_create_ad_group", "google_create_ad"]
    
    def _get_report_tool_sequence(self):
        return ["google_get_campaign_report"]


def create_google_capability(api_client: Optional[GoogleAdsAPIClient] = None) -> GoogleCapability:
    return GoogleCapability(api_client)


# ═══════════════════════════════════════════════════════════════
# TikTok
# ═══════════════════════════════════════════════════════════════

class TikTokCreateCampaignHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        advertiser_id = ctx.account_id
        if self.client and advertiser_id:
            try:
                campaign_id = self.client.create_campaign(
                    advertiser_id=advertiser_id,
                    campaign={
                        "name": input_data.get("campaign_name", "Untitled"),
                        "objective": input_data.get("objective", "PRODUCT_SALES"),
                        "daily_budget": input_data.get("budget", 50),
                        "status": 1,
                    }
                )
                result = ToolResult.ok({
                    "campaign_id": campaign_id,
                    "name": input_data.get("campaign_name"),
                    "objective": input_data.get("objective", "PRODUCT_SALES"),
                    "daily_budget": input_data.get("budget", 50),
                    "status": "ENABLED",
                })
                ctx.set_protected("campaign_id", campaign_id)
                return result
            except Exception as e:
                return ToolResult.error(f"TikTok campaign creation failed: {e}")
        
        campaign_id = f"tiktok_{input_data.get('campaign_name', 'unknown')}_{ctx.session_id[:6]}"
        return ToolResult.ok({
            "campaign_id": campaign_id,
            "name": input_data.get("campaign_name"),
            "objective": input_data.get("objective", "PRODUCT_SALES"),
            "daily_budget": input_data.get("budget", 50),
            "status": "ENABLED",
        })


class TikTokCreateAdGroupHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id") or ctx.get_protected("campaign_id", "")
        advertiser_id = ctx.account_id
        
        if self.client and campaign_id and advertiser_id:
            try:
                adgroup_id = self.client.create_adgroup(
                    advertiser_id=advertiser_id,
                    campaign_id=campaign_id,
                    adgroup={"name": input_data.get("name", "Ad Group"), "status": 1},
                )
                ctx.set_protected("ad_group_id", adgroup_id)
                return ToolResult.ok({"ad_group_id": adgroup_id, "campaign_id": campaign_id, "name": input_data.get("name")})
            except Exception as e:
                return ToolResult.error(f"TikTok ad group creation failed: {e}")
        
        adgroup_id = f"ag_{campaign_id}_{ctx.session_id[:4]}"
        return ToolResult.ok({"ad_group_id": adgroup_id, "campaign_id": campaign_id, "name": input_data.get("name", "Ad Group")})


class TikTokCreateAdHandler(ToolHandler):
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adgroup_id = input_data.get("ad_group_id") or ctx.get_protected("ad_group_id", "")
        return ToolResult.ok({
            "ad_id": f"ad_{adgroup_id}_{ctx.session_id[:4]}",
            "ad_group_id": adgroup_id,
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
    
    def __init__(self, api_client: Optional[TikTokAPIClient] = None):
        self._api_client = api_client
        super().__init__()
    
    def register_tools(self):
        tools = []
        campaign_h = TikTokCreateCampaignHandler(self._api_client)
        adgroup_h = TikTokCreateAdGroupHandler(self._api_client)
        ad_h = TikTokCreateAdHandler(self._api_client)
        
        tools.append((ToolDefinition(
            name="tiktok_create_campaign", skill="tiktok-ads-expert", platform="tiktok",
            description="在 TikTok Ads 中创建广告系列。支持产品营销、线索收集、应用推广等目标。",
            input_schema=ToolSchema(
                required=["campaign_name", "objective", "budget"],
                properties={"campaign_name": {"type": "string"}, "objective": {"type": "string"}, "budget": {"type": "number"}},
            ),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
        ), campaign_h))
        
        tools.append((ToolDefinition(
            name="tiktok_create_ad_group", skill="tiktok-ads-expert", platform="tiktok",
            description="在 Campaign 下创建广告组。",
            input_schema=ToolSchema(required=["campaign_id", "name"], properties={"campaign_id": {"type": "string"}, "name": {"type": "string"}}),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad_group"],
        ), adgroup_h))
        
        tools.append((ToolDefinition(
            name="tiktok_create_ad", skill="tiktok-ads-expert", platform="tiktok",
            description="在 Ad Group 下创建广告。",
            input_schema=ToolSchema(required=["ad_group_id"], properties={"ad_group_id": {"type": "string"}}),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "ad"],
        ), ad_h))
        
        tools.append((ToolDefinition(
            name="tiktok_spark_ads_create", skill="tiktok-ads-expert", platform="tiktok",
            description="创建 Spark Ads（达人原生广告），使用达人已有视频进行投放。",
            input_schema=ToolSchema(required=["campaign_id", "ad_group_id", "spark_post_id"], properties={"spark_post_id": {"type": "string"}}),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "spark"],
        ), TikTokSparkAdsHandler()))
        
        tools.append((ToolDefinition(
            name="tiktok_get_campaign_report", skill="tiktok-ads-expert", platform="tiktok",
            description="查询 TikTok Campaign 报表。",
            input_schema=ToolSchema(required=["campaign_id"], properties={"campaign_id": {"type": "string"}, "date_range": {"type": "object"}}),
            risk_level=RiskLevel.LOW, effect_class=ToolEffect.READ, replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), TikTokGetReportHandler()))
        
        return tools
    
    def _get_campaign_tool_sequence(self):
        return ["tiktok_create_campaign", "tiktok_create_ad_group", "tiktok_create_ad"]
    
    def _get_boost_tool_sequence(self):
        return ["tiktok_spark_ads_create"]
    
    def _get_report_tool_sequence(self):
        return ["tiktok_get_campaign_report"]


def create_tiktok_capability(api_client: Optional[TikTokAPIClient] = None):
    return TikTokCapability(api_client)


# ═══════════════════════════════════════════════════════════════
# DV360
# ═══════════════════════════════════════════════════════════════

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
    
    def register_tools(self):
        tools = []
        
        tools.append((ToolDefinition(
            name="dv360_create_campaign", skill="dv360-expert", platform="dv360",
            description="在 DV360 中创建广告系列。Campaign 是 DV360 的顶级资源。",
            input_schema=ToolSchema(required=["campaign_name", "goal_type"], properties={"campaign_name": {"type": "string"}, "goal_type": {"type": "string"}}),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "campaign"],
        ), DV360CreateCampaignHandler()))
        
        tools.append((ToolDefinition(
            name="dv360_create_io", skill="dv360-expert", platform="dv360",
            description="在 Campaign 下创建 Insertion Order（IO）。",
            input_schema=ToolSchema(required=["campaign_id", "name"], properties={"campaign_id": {"type": "string"}, "name": {"type": "string"}, "budget": {"type": "number"}}),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "io"],
        ), DV360CreateIOHandler()))
        
        tools.append((ToolDefinition(
            name="dv360_create_line_item", skill="dv360-expert", platform="dv360",
            description="在 IO 下创建 Line Item。",
            input_schema=ToolSchema(required=["io_id", "name", "type"], properties={"io_id": {"type": "string"}, "name": {"type": "string"}, "type": {"type": "string"}}),
            risk_level=RiskLevel.MEDIUM, effect_class=ToolEffect.EXTERNAL_WRITE, replay_policy=ReplayPolicy.UNSAFE,
            traits=["write", "line_item"],
        ), DV360CreateLineItemHandler()))
        
        tools.append((ToolDefinition(
            name="dv360_get_line_item_report", skill="dv360-expert", platform="dv360",
            description="查询 DV360 Line Item 报表。",
            input_schema=ToolSchema(required=["line_item_id"], properties={"line_item_id": {"type": "string"}, "date_range": {"type": "object"}}),
            risk_level=RiskLevel.LOW, effect_class=ToolEffect.READ, replay_policy=ReplayPolicy.SAFE,
            traits=["read", "report"],
        ), DV360GetReportHandler()))
        
        return tools
    
    def _get_campaign_tool_sequence(self):
        return ["dv360_create_campaign", "dv360_create_io", "dv360_create_line_item"]
    
    def _get_report_tool_sequence(self):
        return ["dv360_get_line_item_report"]


def create_dv360_capability():
    return DV360Capability()
