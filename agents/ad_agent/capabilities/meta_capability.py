"""
capabilities/meta_capability.py - Meta Marketing API Capability

对应 DAP Agent 的 tiktokruntime.NewModule() 模式。
"""

from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from .base import BaseCapability


# ─── Meta 工具处理器 ───────────────────────────────────────────

class MetaCreateCampaignHandler(ToolHandler):
    """创建 Meta Campaign"""
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        # 实际实现会调用 Meta Marketing API
        # 这里返回模拟结果
        campaign_id = f"meta_{input_data.get('campaign_name', 'unknown')}_{ctx.session_id[:6]}"
        return ToolResult.ok({
            "campaign_id": campaign_id,
            "name": input_data.get("campaign_name"),
            "objective": input_data.get("objective", "OUTCOME_SALES"),
            "status": "ACTIVE",
            "daily_budget": input_data.get("budget", 100),
        })


class MetaCreateAdSetHandler(ToolHandler):
    """创建 Meta Ad Set"""
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        # 从上一个工具的 result 中获取 campaign_id
        campaign_id = input_data.get("campaign_id") or ctx.get_protected("campaign_id")
        adset_id = f"adset_{campaign_id}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "adset_id": adset_id,
            "campaign_id": campaign_id,
            "optimization_goal": input_data.get("optimization_goal", "LINK_CLICKS"),
            "targeting": input_data.get("targeting", {}),
            "bid_amount": input_data.get("bid_amount"),
        })


class MetaCreateAdHandler(ToolHandler):
    """创建 Meta Ad"""
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        adset_id = input_data.get("adset_id") or ctx.get_protected("adset_id")
        ad_id = f"ad_{adset_id}_{ctx.session_id[:4]}"
        return ToolResult.ok({
            "ad_id": ad_id,
            "adset_id": adset_id,
            "name": input_data.get("name", "Untitled Ad"),
            "creative_id": input_data.get("creative_id"),
        })


class MetaGetReportHandler(ToolHandler):
    """查询 Meta Campaign 报表"""
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        campaign_id = input_data.get("campaign_id")
        return ToolResult.ok({
            "campaign_id": campaign_id,
            "metrics": {
                "impressions": 125000,
                "clicks": 3200,
                "spend": 480.50,
                "ctr": 0.0256,
                "cpm": 3.84,
                "cpc": 0.15,
                "conversions": 48,
                "cost_per_conversion": 10.01,
            },
            "date_range": input_data.get("date_range", {"start": "2024-01-01", "end": "2024-01-31"}),
        })


# ─── Meta Capability ───────────────────────────────────────────

class MetaCapability(BaseCapability):
    """Meta Marketing API 能力模块"""
    
    platform_name = "meta"
    
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        """注册 Meta 平台所有工具"""
        tools = []
        
        # Campaign 相关
        tools.append((
            ToolDefinition(
                name="meta_create_campaign",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="在 Meta Marketing API 中创建新的广告系列（Campaign）。支持流量、转化、线索、商品销售等多种目标。",
                input_schema=ToolSchema(
                    required=["campaign_name", "objective", "budget"],
                    properties={
                        "campaign_name": {"type": "string", "description": "广告系列名称"},
                        "objective": {
                            "type": "string",
                            "enum": ["OUTCOME_TRAFFIC", "OUTCOME_CONVERSIONS", "OUTCOME_LEADS", "OUTCOME_SALES", "OUTCOME_ENGAGEMENT"],
                            "description": "广告系列目标"
                        },
                        "budget": {"type": "number", "description": "每日预算（元）"},
                        "special_ad_categories": {"type": "array", "description": "特殊广告类别（美国要求）"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "campaign"],
            ),
            MetaCreateCampaignHandler(),
        ))
        
        # Ad Set 相关
        tools.append((
            ToolDefinition(
                name="meta_create_ad_set",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="在指定 Campaign 下创建广告组（Ad Set）。设置定向、出价、优化目标等。",
                input_schema=ToolSchema(
                    required=["campaign_id", "optimization_goal", "targeting", "bid_amount"],
                    properties={
                        "campaign_id": {"type": "string", "description": "父级 Campaign ID"},
                        "optimization_goal": {
                            "type": "string",
                            "enum": ["LINK_CLICKS", "CONVERSIONS", "LEADS", "REACH", "IMPRESSIONS"],
                            "description": "优化目标"
                        },
                        "targeting": {"type": "object", "description": "定向设置"},
                        "bid_amount": {"type": "number", "description": "出价金额（分）"},
                        "daily_budget": {"type": "number", "description": "广告组日预算"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad_set"],
            ),
            MetaCreateAdSetHandler(),
        ))
        
        # Ad 相关
        tools.append((
            ToolDefinition(
                name="meta_create_ad",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="在指定 Ad Set 下创建广告创意（Ad）。",
                input_schema=ToolSchema(
                    required=["adset_id", "creative_id"],
                    properties={
                        "adset_id": {"type": "string", "description": "父级 Ad Set ID"},
                        "creative_id": {"type": "string", "description": "创意 ID"},
                        "name": {"type": "string", "description": "广告名称"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "ad"],
            ),
            MetaCreateAdHandler(),
        ))
        
        # Boost Post
        tools.append((
            ToolDefinition(
                name="meta_boost_post",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="Boost 已有帖子为广告（快速投放模式）。",
                input_schema=ToolSchema(
                    required=["post_id", "budget", "duration_days"],
                    properties={
                        "post_id": {"type": "string", "description": "要推广的帖子 ID"},
                        "budget": {"type": "number", "description": "总预算（元）"},
                        "duration_days": {"type": "integer", "description": "投放天数"},
                        "targeting": {"type": "object", "description": "定向设置"},
                    }
                ),
                risk_level=RiskLevel.MEDIUM,
                effect_class=ToolEffect.EXTERNAL_WRITE,
                replay_policy=ReplayPolicy.UNSAFE,
                traits=["write", "boost"],
            ),
            MetaCreateCampaignHandler(),  # 复用创建逻辑
        ))
        
        # 查询工具
        tools.append((
            ToolDefinition(
                name="meta_get_campaign_report",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询 Meta Campaign 的投放报表和性能指标。",
                input_schema=ToolSchema(
                    required=["campaign_id"],
                    properties={
                        "campaign_id": {"type": "string", "description": "Campaign ID"},
                        "date_range": {"type": "object", "description": "日期范围 {start, end}"},
                        "breakdowns": {"type": "array", "description": "分解维度，如 ['age', 'gender', 'platform']"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "report"],
            ),
            MetaGetReportHandler(),
        ))
        
        tools.append((
            ToolDefinition(
                name="meta_list_accounts",
                skill="meta-marketing-api-expert",
                platform="meta",
                description="查询当前账户可访问的广告账户列表。",
                input_schema=ToolSchema(
                    properties={
                        "limit": {"type": "integer", "description": "返回数量上限"},
                    }
                ),
                risk_level=RiskLevel.LOW,
                effect_class=ToolEffect.READ,
                replay_policy=ReplayPolicy.SAFE,
                traits=["read", "account"],
            ),
            self._make_list_accounts_handler(),
        ))
        
        return tools
    
    def _get_campaign_tool_sequence(self) -> list[str]:
        return ["meta_create_campaign", "meta_create_ad_set", "meta_create_ad"]
    
    def _get_boost_tool_sequence(self) -> list[str]:
        return ["meta_boost_post"]
    
    def _get_report_tool_sequence(self) -> list[str]:
        return ["meta_get_campaign_report"]
    
    def _make_list_accounts_handler(self):
        """工厂方法：创建 list_accounts 处理器"""
        class ListAccountsHandler(ToolHandler):
            def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
                return ToolResult.ok({
                    "accounts": [
                        {"id": "2806375919473667", "name": "Ryan Test Account", "status": "active"},
                    ],
                    "limit": input_data.get("limit", 10),
                })
        return ListAccountsHandler()


# ─── 便捷入口 ──────────────────────────────────────────────────

def create_meta_capability() -> BaseCapability:
    """工厂函数：创建 Meta Capability 实例"""
    return MetaCapability()
