"""
capabilities/meta_capability.py - Meta Marketing API Capability（真实 API 版）

支持两种模式：
- mock 模式：无需凭证，返回模拟结果（测试/演示用）
- real 模式：调用真实 Meta Marketing API

切换方式：创建时传入 api_client 参数
"""

import logging
from typing import Optional

from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from .base import BaseCapability
from ..api_clients.meta_client import MetaAPIClient

logger = logging.getLogger(__name__)


# ─── Mock Handler（无需 API 调用）───────────────────────────────

class MetaCreateCampaignMockHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = f"meta_{input_data.get('campaign_name', 'unknown')}_{ctx.session_id[:6]}"
        result = ToolResult.ok({
            "campaign_id": campaign_id,
            "name": input_data.get("campaign_name"),
            "objective": input_data.get("objective", "OUTCOME_SALES"),
            "status": "ACTIVE",
            "daily_budget": input_data.get("budget", 100),
        })
        # 保存到 protected_state 供后续工具使用
        ctx.set_protected("campaign_id", campaign_id)
        return result


class MetaCreateAdSetMockHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id") or ctx.get_protected("campaign_id", "")
        adset_id = f"adset_{campaign_id}_{ctx.session_id[:4]}"
        result = ToolResult.ok({
            "adset_id": adset_id,
            "campaign_id": campaign_id,
            "optimization_goal": input_data.get("optimization_goal", "LINK_CLICKS"),
            "targeting": input_data.get("targeting", {}),
            "bid_amount": input_data.get("bid_amount"),
        })
        ctx.set_protected("adset_id", adset_id)
        return result


class MetaCreateAdMockHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id") or ctx.get_protected("adset_id", "")
        ad_id = f"ad_{adset_id}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_id": ad_id,
            "adset_id": adset_id,
            "name": input_data.get("name", "Untitled Ad"),
            "creative_id": input_data.get("creative_id"),
        })


class MetaGetReportMockHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        return ToolResult.ok({
            "campaign_id": input_data.get("campaign_id"),
            "metrics": {
                "impressions": 125000,
                "clicks": 3200,
                "spend": 480.50,
                "ctr": 0.0256,
                "cpc": 0.15,
                "conversions": 48,
                "cost_per_conversion": 10.01,
            },
            "date_range": input_data.get("date_range", {}),
        })


class MetaListAccountsMockHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        return ToolResult.ok({
            "accounts": [
                {"id": "2806375919473667", "name": "Ryan Test Account", "status": "active"},
            ],
        })


class MetaListCampaignsMockHandler(ToolHandler):
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        return ToolResult.ok({
            "campaigns": [
                {"id": "act_2806375919473667_101", "name": "Test Campaign 1", "status": "ACTIVE", "objective": "OUTCOME_SALES"},
                {"id": "act_2806375919473667_102", "name": "Test Campaign 2", "status": "PAUSED", "objective": "OUTCOME_TRAFFIC"},
            ],
        })


class MetaListCampaignsRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if not account_id:
            return ToolResult.error("Missing account_id in context")
        
        try:
            campaigns = self.client.list_campaigns(account_id)
            return ToolResult.ok({"campaigns": campaigns})
        except Exception as e:
            return ToolResult.error(f"Failed to list Meta campaigns: {e}")


# ─── Real Handler（调用真实 API）────────────────────────────────

class MetaCreateCampaignRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if not account_id:
            return ToolResult.error("Missing account_id in context")
        
        try:
            campaign_id = self.client.create_campaign(
                account_id=account_id,
                campaign={
                    'name': input_data.get('campaign_name', 'Untitled'),
                    'objective': input_data.get('objective', 'OUTCOME_SALES'),
                    'daily_budget': input_data.get('budget', 100),
                    'special_ad_categories': input_data.get('special_ad_categories', []),
                }
            )
            result = ToolResult.ok({
                "campaign_id": campaign_id,
                "name": input_data.get("campaign_name"),
                "objective": input_data.get("objective", "OUTCOME_SALES"),
                "status": "ACTIVE",
                "daily_budget": input_data.get("budget", 100),
            })
            ctx.set_protected("campaign_id", campaign_id)
            return result
        except Exception as e:
            return ToolResult.error(f"Failed to create Meta campaign: {e}")


class MetaCreateAdSetRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id") or ctx.get_protected("campaign_id")
        if not campaign_id:
            return ToolResult.error("Missing campaign_id")
        
        account_id = ctx.account_id
        try:
            adset_id = self.client.create_adset(
                account_id=account_id,
                campaign_id=campaign_id,
                adset={
                    "name": input_data.get("name", "Ad Set"),
                    "optimization_goal": input_data.get("optimization_goal", "LINK_CLICKS"),
                    "targeting": input_data.get("targeting", {}),
                    "bid_amount": input_data.get("bid_amount", 100),
                    "daily_budget": input_data.get("daily_budget"),
                }
            )
            result = ToolResult.ok({
                "adset_id": adset_id,
                "campaign_id": campaign_id,
                "optimization_goal": input_data.get("optimization_goal", "LINK_CLICKS"),
                "targeting": input_data.get("targeting", {}),
            })
            ctx.set_protected("adset_id", adset_id)
            return result
        except Exception as e:
            return ToolResult.error(f"Failed to create Meta ad set: {e}")


class MetaCreateAdRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id") or ctx.get_protected("adset_id")
        if not adset_id:
            return ToolResult.error("Missing adset_id")
        
        account_id = ctx.account_id
        try:
            ad_id = self.client.create_ad(
                account_id=account_id,
                adset_id=adset_id,
                ad=input_data,
            )
            return ToolResult.ok({
                "ad_id": ad_id,
                "adset_id": adset_id,
                "name": input_data.get("name", "Untitled Ad"),
            })
        except Exception as e:
            return ToolResult.error(f"Failed to create Meta ad: {e}")


class MetaGetReportRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        if not campaign_id:
            return ToolResult.error("Missing campaign_id")
        
        account_id = ctx.account_id
        try:
            report = self.client.get_campaign_report(
                account_id=account_id,
                campaign_ids=[campaign_id],
                time_range=input_data.get("date_range"),
            )
            return ToolResult.ok({"campaign_id": campaign_id, "report": report})
        except Exception as e:
            return ToolResult.error(f"Failed to get Meta report: {e}")


class MetaListAccountsRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        try:
            accounts = self.client.list_accounts()
            return ToolResult.ok({"accounts": accounts})
        except Exception as e:
            return ToolResult.error(f"Failed to list Meta accounts: {e}")


class MetaGetCampaignRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get('campaign_id', '')
        if not campaign_id:
            return ToolResult.error("campaign_id is required")
        try:
            campaign = self.client.get_campaign(campaign_id)
            return ToolResult.ok({"campaign": campaign})
        except Exception as e:
            return ToolResult.error(f"Failed to get Meta campaign: {e}")


class MetaGetAdSetRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get('adset_id', '')
        if not adset_id:
            return ToolResult.error("adset_id is required")
        try:
            adset = self.client.get_adset(adset_id)
            return ToolResult.ok({"adset": adset})
        except Exception as e:
            return ToolResult.error(f"Failed to get Meta adset: {e}")


class MetaGetAdRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        ad_id = input_data.get('ad_id', '')
        if not ad_id:
            return ToolResult.error("ad_id is required")
        try:
            ad = self.client.get_ad(ad_id)
            return ToolResult.ok({"ad": ad})
        except Exception as e:
            return ToolResult.error(f"Failed to get Meta ad: {e}")


class MetaListAdSetsRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if not account_id:
            return ToolResult.error("Missing account_id in context")
        
        try:
            adsets = self.client.list_adsets(account_id)
            return ToolResult.ok({"adsets": adsets})
        except Exception as e:
            return ToolResult.error(f"Failed to list Meta adsets: {e}")


class MetaListAdsRealHandler(ToolHandler):
    def __init__(self, api_client: MetaAPIClient):
        self.client = api_client
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        account_id = ctx.account_id
        if not account_id:
            return ToolResult.error("Missing account_id in context")
        
        try:
            ads = self.client.list_ads(account_id)
            return ToolResult.ok({"ads": ads})
        except Exception as e:
            return ToolResult.error(f"Failed to list Meta ads: {e}")


# ─── Capability ────────────────────────────────────────────────

class MetaCapability(BaseCapability):
    """Meta Marketing API 能力模块"""
    
    platform_name = "meta"
    
    def __init__(self, api_client: Optional[MetaAPIClient] = None):
        """
        Args:
            api_client: 真实 API 客户端（None 时使用 mock 模式）
        """
        self._api_client = api_client
        super().__init__()
    
    @property
    def is_real_mode(self) -> bool:
        return self._api_client is not None
    
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        tools = []
        
        # 根据模式选择 Handler
        if self.is_real_mode:
            create_campaign_h = MetaCreateCampaignRealHandler(self._api_client)
            create_adset_h = MetaCreateAdSetRealHandler(self._api_client)
            create_ad_h = MetaCreateAdRealHandler(self._api_client)
            get_report_h = MetaGetReportRealHandler(self._api_client)
            list_accounts_h = MetaListAccountsRealHandler(self._api_client)
            list_campaigns_h = MetaListCampaignsRealHandler(self._api_client)
            get_campaign_h = MetaGetCampaignRealHandler(self._api_client)
            get_adset_h = MetaGetAdSetRealHandler(self._api_client)
            get_ad_h = MetaGetAdRealHandler(self._api_client)
            list_adsets_h = MetaListAdSetsRealHandler(self._api_client)
            list_ads_h = MetaListAdsRealHandler(self._api_client)
        else:
            create_campaign_h = MetaCreateCampaignMockHandler()
            create_adset_h = MetaCreateAdSetMockHandler()
            create_ad_h = MetaCreateAdMockHandler()
            get_report_h = MetaGetReportMockHandler()
            list_accounts_h = MetaListAccountsMockHandler()
            list_campaigns_h = MetaListCampaignsMockHandler()
        
        # Campaign
        tools.append((
            ToolDefinition(
                name="meta_create_campaign",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="在 Meta Marketing API 中创建广告系列（Campaign）。支持流量、转化、线索、商品销售等多种目标。",
                input_schema=ToolSchema(
                    required=["campaign_name", "objective", "budget"],
                    properties={
                        "campaign_name": {"type": "string"},
                        "objective": {"type": "string", "enum": ["OUTCOME_TRAFFIC", "OUTCOME_CONVERSIONS", "OUTCOME_LEADS", "OUTCOME_SALES", "OUTCOME_ENGAGEMENT"]},
                        "budget": {"type": "number", "description": "每日预算（元）"},
                        "special_ad_categories": {"type": "array"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "campaign"],
            ),
            create_campaign_h,
        ))
        
        # Ad Set
        tools.append((
            ToolDefinition(
                name="meta_create_ad_set",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="在 Campaign 下创建广告组（Ad Set）。设置定向、出价、优化目标等。",
                input_schema=ToolSchema(
                    required=["campaign_id", "optimization_goal", "targeting", "bid_amount"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "optimization_goal": {"type": "string", "enum": ["LINK_CLICKS", "CONVERSIONS", "LEADS", "REACH", "IMPRESSIONS"]},
                        "targeting": {"type": "object"},
                        "bid_amount": {"type": "number"},
                        "daily_budget": {"type": "number"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad_set"],
            ),
            create_adset_h,
        ))
        
        # Ad
        tools.append((
            ToolDefinition(
                name="meta_create_ad",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="在 Ad Set 下创建广告创意（Ad）。",
                input_schema=ToolSchema(
                    required=["adset_id"],
                    properties={
                        "adset_id": {"type": "string"},
                        "creative_id": {"type": "string"},
                        "name": {"type": "string"},
                        "body": {"type": "string"},
                        "title": {"type": "string"},
                        "url_tags": {"type": "string"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad"],
            ),
            create_ad_h,
        ))
        
        # Boost Post
        tools.append((
            ToolDefinition(
                name="meta_boost_post",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="为 Page 帖子创建 Boost（快速投放模式）。",
                input_schema=ToolSchema(
                    required=["post_id", "budget", "duration_days"],
                    properties={
                        "post_id": {"type": "string"},
                        "budget": {"type": "number"},
                        "duration_days": {"type": "integer"},
                        "targeting": {"type": "object"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "boost"],
            ),
            create_campaign_h,  # 复用创建逻辑
        ))
        
        # Report
        tools.append((
            ToolDefinition(
                name="meta_get_campaign_report",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Campaign 的投放报表和性能指标。",
                input_schema=ToolSchema(
                    required=["campaign_id"],
                    properties={
                        "campaign_id": {"type": "string"},
                        "date_range": {"type": "object"},
                        "breakdowns": {"type": "array"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "report"],
            ),
            get_report_h,
        ))
        
        # List Campaigns
        tools.append((
            ToolDefinition(
                name="meta_list_campaigns",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Campaign 列表，支持按状态筛选。",
                input_schema=ToolSchema(
                    properties={
                        "status": {"type": "string", "enum": ["ACTIVE", "PAUSED", "DELETED"]},
                        "limit": {"type": "integer"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "campaign"],
            ),
            list_campaigns_h,
        ))
        
        # List Accounts
        tools.append((
            ToolDefinition(
                name="meta_list_accounts",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询当前账户可访问的广告账户列表。",
                input_schema=ToolSchema(
                    properties={"limit": {"type": "integer"}}
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "account"],
            ),
            list_accounts_h,
        ))
        
        # Get Campaign
        tools.append((
            ToolDefinition(
                name="meta_get_campaign",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Campaign 详情。",
                input_schema=ToolSchema(
                    required=["campaign_id"],
                    properties={"campaign_id": {"type": "string"}}
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "campaign"],
            ),
            get_campaign_h,
        ))
        
        # Get Ad Set
        tools.append((
            ToolDefinition(
                name="meta_get_adset",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Ad Set 详情。",
                input_schema=ToolSchema(
                    required=["adset_id"],
                    properties={"adset_id": {"type": "string"}}
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "adset"],
            ),
            get_adset_h,
        ))
        
        # Get Ad
        tools.append((
            ToolDefinition(
                name="meta_get_ad",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Ad 详情。",
                input_schema=ToolSchema(
                    required=["ad_id"],
                    properties={"ad_id": {"type": "string"}}
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "ad"],
            ),
            get_ad_h,
        ))
        
        # List Ad Sets
        tools.append((
            ToolDefinition(
                name="meta_list_ad_sets",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Ad Set 列表。",
                input_schema=ToolSchema(
                    properties={
                        "status": {"type": "string", "enum": ["ACTIVE", "PAUSED", "DELETED"]},
                        "limit": {"type": "integer"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "adset"],
            ),
            list_adsets_h,
        ))
        
        # List Ads
        tools.append((
            ToolDefinition(
                name="meta_list_ads",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Ad 列表。",
                input_schema=ToolSchema(
                    properties={
                        "status": {"type": "string", "enum": ["ACTIVE", "PAUSED", "DELETED"]},
                        "limit": {"type": "integer"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "ad"],
            ),
            list_ads_h,
        ))
        
        return tools
    
    def _get_campaign_tool_sequence(self) -> list[str]:
        return ["meta_create_campaign", "meta_create_ad_set", "meta_create_ad"]
    
    def _get_boost_tool_sequence(self) -> list[str]:
        return ["meta_boost_post"]
    
    def _get_report_tool_sequence(self) -> list[str]:
        return ["meta_get_campaign_report"]


def create_meta_capability(api_client: Optional[MetaAPIClient] = None) -> MetaCapability:
    """工厂函数"""
    return MetaCapability(api_client=api_client)
