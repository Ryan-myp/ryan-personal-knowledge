"""
core/tool_selector.py - 动态工具选择器

核心功能：
1. 根据用户意图 + 目标平台，动态选择相关工具
2. 注入平台专家知识作为上下文
3. 优化 LLM 的 tool 列表，避免信息过载
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

from .interfaces import ToolDefinition, ParsedIntent, ToolContext
from ..skills.loader import get_skill_loader
from ..skills.registry import get_skill_registry

logger = logging.getLogger(__name__)


@dataclass
class BusinessContext:
    """业务上下文 - 定义业务可用的渠道和规则"""
    business_name: str = ""
    allowed_channels: List[str] = field(default_factory=list)
    disallowed_channels: List[str] = field(default_factory=list)
    allowed_campaign_types: List[str] = field(default_factory=list)
    business_rules: Dict = field(default_factory=dict)
    focus_metrics: List[str] = field(default_factory=list)

    def is_channel_allowed(self, channel: str) -> bool:
        """检查渠道是否被允许"""
        if channel in self.disallowed_channels:
            return False
        if self.allowed_channels and channel not in self.allowed_channels:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "business": self.business_name,
            "allowed_channels": self.allowed_channels,
            "disallowed_channels": self.disallowed_channels,
            "focus_metrics": self.focus_metrics,
        }


@dataclass
class ToolSelection:
    """工具选择结果"""
    selected_tools: List[ToolDefinition] = field(default_factory=list)
    platform: str = ""
    context: Dict = field(default_factory=dict)
    expert_knowledge: str = ""
    
    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "tool_count": len(self.selected_tools),
            "tools": [t.name for t in self.selected_tools],
            "context_keys": list(self.context.keys()),
            "expert_knowledge_available": bool(self.expert_knowledge),
        }


class DynamicToolSelector:
    """
    动态工具选择器
    
    工作原理：
    1. 根据用户意图识别目标平台
    2. 从 Skill Registry 获取该平台的所有工具
    3. 根据意图类型筛选相关工具（如查询→只选报表类工具）
    4. 注入平台专家知识作为上下文
    5. 返回精简的工具列表给 LLM
    """
    
    # 意图类型 → 工具关键词映射（用于筛选）
    INTENT_TOOL_MAP = {
        "create_campaign": ["create", "add", "new"],
        "update_campaign": ["update", "modify", "edit"],
        "pause_campaign": ["pause", "stop", "disable"],
        "resume_campaign": ["resume", "start", "enable"],
        "list_campaigns": ["list", "query", "search", "get_", "campaign"],
        "get_report": ["report", "get_", "list_", "query", "search"],
        "optimize_bidding": ["optimize", "bid", "pricing"],
        "get_audience": ["audience", "target", "demographic"],
        "manage_creative": ["creative", "ad", "material"],
        "cross_channel": ["overview", "compare", "budget", "cross"],
    }
    
    def __init__(self):
        self.skill_loader = get_skill_loader()
        self.skill_registry = get_skill_registry()
        self.business_context: Optional[BusinessContext] = None
    
    def set_business_context(self, business_name: str, context: BusinessContext):
        """设置业务上下文"""
        self.business_context = context
        logger.info(f"Business context set: {business_name}, allowed_channels: {context.allowed_channels}")
    
    def select_tools(
        self,
        user_input: str,
        intent: ParsedIntent,
        available_tools: List[ToolDefinition],
    ) -> ToolSelection:
        """
        根据用户输入和意图，动态选择相关工具
        
        Args:
            user_input: 用户原始输入
            intent: 解析后的意图
            available_tools: 所有可用工具
            
        Returns:
            ToolSelection: 选中的工具 + 上下文
        """
        # 1. 确定目标平台
        platforms = intent.platforms or self._detect_platforms(user_input)
        
        # 2. 根据业务上下文过滤平台
        if self.business_context:
            platforms = [p for p in platforms if self.business_context.is_channel_allowed(p)]
            if not platforms:
                platforms = self.business_context.allowed_channels[:2]  # 回退到默认
        
        # 3. 根据意图类型筛选工具
        intent_type = intent.intent_type
        selected_tools = []
        
        for platform in platforms:
            # 从 Skill Registry 获取该平台工具
            platform_tools = self._get_platform_tools(platform, available_tools)
            
            # 根据意图类型筛选
            filtered_tools = self._filter_by_intent(platform_tools, intent_type)
            
            # 4. 获取专家知识
            expert_knowledge = self._get_expert_knowledge(platform, intent_type)
            
            if filtered_tools:
                selection = ToolSelection(
                    selected_tools=filtered_tools,
                    platform=platform,
                    context={
                        "intent_type": intent_type,
                        "objective": intent.objective,
                        "budget": intent.budget,
                        "business": self.business_context.business_name if self.business_context else None,
                    },
                    expert_knowledge=expert_knowledge,
                )
                selected_tools.extend(filtered_tools)
        
        return ToolSelection(
            selected_tools=selected_tools,
            platform=",".join(platforms),
            expert_knowledge=self._merge_expert_knowledge(selected_tools),
            context={
                "business_context": self.business_context.to_dict() if self.business_context else None,
            },
        )
    
    def _detect_platforms(self, user_input: str) -> List[str]:
        """从用户输入中检测平台"""
        platforms = []
        text = user_input.lower()
        
        platform_keywords = {
            "meta": ["meta", "facebook", "instagram", "fb"],
            "google": ["google", "gads", "google ads"],
            "tiktok": ["tiktok", "douyin"],
            "dv360": ["dv360", "display video"],
        }
        
        for platform, keywords in platform_keywords.items():
            if any(kw in text for kw in keywords):
                platforms.append(platform)
        
        return platforms if platforms else ["meta", "google"]  # 默认
    
    def _get_platform_tools(
        self, 
        platform: str, 
        available_tools: List[ToolDefinition]
    ) -> List[ToolDefinition]:
        """获取指定平台的所有工具"""
        return [t for t in available_tools if t.platform == platform]
    
    def _filter_by_intent(
        self,
        tools: List[ToolDefinition],
        intent_type: str,
    ) -> List[ToolDefinition]:
        """根据意图类型筛选工具"""
        if not intent_type:
            return tools[:5]  # 限制返回数量，避免过长
        
        # 获取该意图类型的关键词
        keywords = self.INTENT_TOOL_MAP.get(intent_type, [])
        
        if not keywords:
            return tools
        
        # 筛选匹配关键词的工具
        filtered = []
        for tool in tools:
            tool_name = tool.name.lower()
            tool_desc = tool.description.lower()
            
            # 检查工具名或描述是否包含关键词
            if any(kw in tool_name or kw in tool_desc for kw in keywords):
                filtered.append(tool)
        
        # 如果没有匹配，返回前 N 个最常用的工具
        if not filtered:
            # 按使用频率排序（查询类工具优先）
            priority_tools = ["get_", "list_", "query_", "report", "optimize"]
            filtered = sorted(
                tools,
                key=lambda t: next((i for i, p in enumerate(priority_tools) if p in t.name), 99)
            )[:5]
        
        return filtered[:8]  # 限制最多 8 个工具
    
    def _get_expert_knowledge(
        self, 
        platform: str, 
        intent_type: str
    ) -> str:
        """获取平台专家知识"""
        skill = self.skill_loader.get_skill(platform)
        if not skill:
            return ""
        
        # 根据意图类型选择专家知识
        knowledge_map = {
            "create_campaign": ["bidding_strategies", "targeting_guide", "best_practices"],
            "get_report": ["report_metrics", "optimization_tips"],
            "optimize_bidding": ["bidding_strategies", "cost_control"],
            "manage_creative": ["creative_best_practices", "ad_copy_tips"],
        }
        
        needed_keys = knowledge_map.get(intent_type, ["general"])
        
        expert_knowledge = []
        for key in needed_keys:
            if key in skill.expert_knowledge:
                expert_knowledge.append(f"## {key}\n{skill.expert_knowledge[key]}")
        
        return "\n\n".join(expert_knowledge) if expert_knowledge else ""
    
    def _merge_expert_knowledge(self, tools: List[ToolDefinition]) -> str:
        """合并多个工具的专家知识"""
        platforms = set(t.platform for t in tools)
        knowledge = []
        
        for platform in platforms:
            skill = self.skill_loader.get_skill(platform)
            if skill and skill.expert_knowledge:
                # 提取关键专家知识摘要
                for key, content in list(skill.expert_knowledge.items())[:2]:
                    # 截取前 500 字符
                    summary = content[:500] + "..." if len(content) > 500 else content
                    knowledge.append(f"[{platform}] {key}: {summary}")
        
        return "\n\n".join(knowledge)
    
    def build_tool_prompt(self, selection: ToolSelection) -> str:
        """构建工具列表 prompt（给 LLM 使用）"""
        if not selection.selected_tools:
            return "暂无可用工具"
        
        lines = [f"## 可用工具（平台: {selection.platform}）"]
        
        for i, tool in enumerate(selection.selected_tools, 1):
            lines.append(f"{i}. **{tool.name}** ({tool.risk_level.value})")
            lines.append(f"   描述: {tool.description[:100]}...")
            if tool.input_schema.properties:
                lines.append(f"   参数: {list(tool.input_schema.properties.keys())}")
            lines.append("")
        
        if selection.expert_knowledge:
            lines.append("## 专家知识")
            lines.append(selection.expert_knowledge[:1000] + "..." if len(selection.expert_knowledge) > 1000 else selection.expert_knowledge)
        
        return "\n".join(lines)
    
    def optimize_for_llm(
        self,
        user_input: str,
        intent: ParsedIntent,
        all_tools: List[ToolDefinition],
    ) -> dict:
        """
        为 LLM 优化工具选择
        
        Returns:
            {
                "selected_tools": [...],
                "tool_prompt": "...",
                "expert_knowledge": "...",
                "context": {...}
            }
        """
        selection = self.select_tools(user_input, intent, all_tools)
        
        return {
            "selected_tools": selection.selected_tools,
            "tool_count": len(selection.selected_tools),
            "tool_prompt": self.build_tool_prompt(selection),
            "expert_knowledge": selection.expert_knowledge,
            "context": selection.context,
            "platforms": selection.platform,
        }


# 全局实例
_tool_selector: Optional[DynamicToolSelector] = None


def get_tool_selector() -> DynamicToolSelector:
    """获取全局工具选择器"""
    global _tool_selector
    if _tool_selector is None:
        _tool_selector = DynamicToolSelector()
    return _tool_selector


def select_tools_for_intent(
    user_input: str,
    intent: ParsedIntent,
    all_tools: List[ToolDefinition],
) -> dict:
    """便捷函数：为意图选择工具"""
    return get_tool_selector().optimize_for_llm(user_input, intent, all_tools)

# 扩展的意图类型映射（补充缺失的）
