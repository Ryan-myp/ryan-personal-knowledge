"""
user_skills/orchestrator.py - 跨平台编排 Skill

这是单 Agent 架构的核心：一个 Skill 可以协调多个平台工具的执行。
它不直接调用任何平台 API，而是通过 IntentRouter 分发到对应平台 Skill。

对应 DAP Agent 的 workflow/compiled/ 模式，但更简化。
"""

import json
from typing import Any
from ..core.interfaces import (
    ToolDefinition, ToolHandler, ToolSchema, ToolResult,
    ToolContext, RiskLevel, ToolEffect, ReplayPolicy
)
from ..core.intent import ParsedIntent


class AdCampaignOrchestratorHandler(ToolHandler):
    """
    跨平台广告投放编排器。
    
    这是一个"元工具"：它接受用户的高层投放需求，自动分解为各平台的具体操作。
    实际执行仍由各平台的 ToolHandler 完成。
    
    使用场景：
    - 用户说："用这张海报图，投放 Meta 和 Google，预算100元/天"
    - 此工具解析意图，生成各平台的 Campaign 创建计划
    - 返回可执行的步骤列表（含确认卡片）
    """
    
    def __init__(self, intent_router=None):
        self.intent_router = intent_router
    
    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        """
        执行编排逻辑。
        
        input_data 包含：
        - user_input: 原始用户输入
        - platforms: 目标平台列表
        - objective: 投放目标
        - budget: 预算
        - creative_materials: 素材
        """
        user_input = input_data.get("user_input", "")
        platforms = input_data.get("platforms", [])
        objective = input_data.get("objective", "sales")
        budget = input_data.get("budget", 100)
        materials = input_data.get("creative_materials", [])
        
        # 构建结构化意图
        intent = ParsedIntent(
            intent_type="create_campaign",
            raw_input=user_input,
            platforms=platforms,
            objective=objective,
            budget=budget,
            creative_materials=materials,
            platform_params={p: {} for p in platforms},
        )
        
        # 生成分步执行计划
        plan = self._build_execution_plan(intent)
        
        # 构建确认卡片（需要用户确认后才真正执行）
        card_payload = {
            "type": "ad_campaign_confirmation",
            "title": "确认广告投放计划",
            "summary": f"将在 {', '.join(platforms)} 创建 {objective} 广告系列",
            "plan": plan,
            "actions": [
                {"id": "confirm_all", "label": "确认全部投放", "type": "primary"},
                {"id": "confirm_selective", "label": "选择平台投放", "type": "secondary"},
                {"id": "cancel", "label": "取消", "type": "danger"},
            ],
        }
        
        return ToolResult.needs_confirmation(card_payload)
    
    def _build_execution_plan(self, intent: ParsedIntent) -> list[dict]:
        """构建各平台的执行步骤"""
        plan = []
        
        platform_configs = {
            "meta": {
                "tool_sequence": ["meta_create_campaign", "meta_create_ad_set", "meta_create_ad"],
                "params_template": {
                    "campaign_name": f"{intent.objective or 'sales'}_campaign",
                    "objective": self._map_objective_to_meta(intent.objective),
                    "budget": intent.budget or 100,
                }
            },
            "google": {
                "tool_sequence": ["google_create_campaign", "google_create_ad_group", "google_create_ad"],
                "params_template": {
                    "campaign_name": f"{intent.objective or 'sales'}_campaign",
                    "advertising_channel_type": self._map_objective_to_google(intent.objective),
                    "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                    "campaign_budget": intent.budget or 100,
                }
            },
            "tiktok": {
                "tool_sequence": ["tiktok_create_campaign", "tiktok_create_ad_group", "tiktok_create_ad"],
                "params_template": {
                    "campaign_name": f"{intent.objective or 'sales'}_campaign",
                    "objective": self._map_objective_to_tiktok(intent.objective),
                    "budget": intent.budget or 50,
                }
            },
            "dv360": {
                "tool_sequence": ["dv360_create_campaign", "dv360_create_io", "dv360_create_line_item"],
                "params_template": {
                    "campaign_name": f"{intent.objective or 'brand'}_campaign",
                    "goal_type": "IMPRESSIONS",
                }
            },
        }
        
        for platform in intent.platforms:
            config = platform_configs.get(platform, {})
            plan.append({
                "platform": platform,
                "tools": config.get("tool_sequence", []),
                "params": config.get("params_template", {}),
                "description": self._get_platform_description(platform),
            })
        
        return plan
    
    def _map_objective_to_meta(self, objective: str) -> str:
        mapping = {
            "sales": "OUTCOME_SALES",
            "leads": "OUTCOME_LEADS",
            "traffic": "OUTCOME_TRAFFIC",
            "brand": "OUTCOME_ENGAGEMENT",
        }
        return mapping.get(objective, "OUTCOME_SALES")
    
    def _map_objective_to_google(self, objective: str) -> str:
        mapping = {
            "sales": "SHOPPING",
            "leads": "SEARCH",
            "traffic": "SEARCH",
            "brand": "DISPLAY",
        }
        return mapping.get(objective, "SEARCH")
    
    def _map_objective_to_tiktok(self, objective: str) -> str:
        mapping = {
            "sales": "PRODUCT_SALES",
            "leads": "LEAD_GENERATION",
            "traffic": "TRAFFIC",
            "brand": "BRAND_AWARENESS",
        }
        return mapping.get(objective, "PRODUCT_SALES")
    
    def _get_platform_description(self, platform: str) -> str:
        descs = {
            "meta": "Meta（Facebook + Instagram）广告投放",
            "google": "Google Ads 广告投放",
            "tiktok": "TikTok Ads 广告投放",
            "dv360": "DV360 程序化广告投放",
        }
        return descs.get(platform, platform)


class AdCampaignOrchestratorSkill:
    """
    跨平台编排 Skill。
    
    提供单个工具入口，接受用户的自然语言投放需求，
    输出结构化的多平台执行计划。
    """
    
    TOOL_NAME = "ad_campaign_orchestrator"
    
    def get_tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.TOOL_NAME,
            skill="ad-campaign-orchestrator",
            platform="multi_platform",
            description=(
                "跨平台广告投放编排工具。接受用户的自然语言投放需求，"
                "自动生成多平台广告创建计划并返回确认卡片。"
                "支持 Meta、Google Ads、TikTok、DV360 四大平台。"
            ),
            input_schema=ToolSchema(
                required=["user_input"],
                properties={
                    "user_input": {"type": "string", "description": "用户的投放需求描述"},
                    "platforms": {"type": "array", "description": "目标平台列表，如 ['meta', 'google']"},
                    "objective": {"type": "string", "enum": ["sales", "leads", "traffic", "brand"]},
                    "budget": {"type": "number", "description": "每日预算（元）"},
                    "duration_days": {"type": "integer", "description": "投放天数"},
                    "creative_materials": {"type": "array", "description": "素材列表"},
                }
            ),
            risk_level=RiskLevel.LOW,
            effect_class=ToolEffect.READ,  # 编排工具本身不直接写入，只是生成计划
            replay_policy=ReplayPolicy.SAFE,
            traits=["orchestrator", "planning"],
        )
    
    def get_handler(self) -> ToolHandler:
        return AdCampaignOrchestratorHandler()


def create_orchestrator_skill():
    """工厂函数：创建编排 Skill"""
    skill = AdCampaignOrchestratorSkill()
    return skill.get_tool_definition(), skill.get_handler()
