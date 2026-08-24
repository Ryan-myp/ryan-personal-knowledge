"""
core/context_optimizer.py - LLM 上下文优化器

核心功能：
1. 根据用户意图动态选择相关工具和专家知识
2. 构建精简的 system prompt，避免信息过载
3. 注入平台特定的最佳实践
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from .interfaces import ToolDefinition, ParsedIntent
from .tool_selector import DynamicToolSelector, get_tool_selector

logger = logging.getLogger(__name__)


@dataclass
class OptimizedContext:
    """优化后的 LLM 上下文"""
    system_prompt: str
    available_tools: List[ToolDefinition]
    tool_count: int
    expert_knowledge: str
    platform: str
    context: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "tool_count": self.tool_count,
            "platform": self.platform,
            "expert_knowledge_available": bool(self.expert_knowledge),
            "context_keys": list(self.context.keys()),
        }


class ContextOptimizer:
    """
    LLM 上下文优化器
    
    工作原理：
    1. 解析用户意图
    2. 动态选择相关工具和专家知识
    3. 构建精简的 system prompt
    4. 返回优化后的上下文给 LLM
    """
    
    # System prompt 模板
    SYSTEM_PROMPT_TEMPLATE = """你是广告投放专家助手，具备以下平台的专家知识：

## 可用工具
{tool_list}

## 专家知识
{expert_knowledge}

## 当前任务
- 意图: {intent_type}
- 平台: {platform}
- 目标: {objective}
- 预算: {budget}

请用专业、简洁的方式回应用户需求。如需调用工具，请说明调用原因和预期结果。
"""
    
    def __init__(self):
        self.tool_selector = get_tool_selector()
    
    def optimize(
        self,
        user_input: str,
        intent: ParsedIntent,
        all_tools: List[ToolDefinition],
    ) -> OptimizedContext:
        """
        优化 LLM 上下文
        
        Args:
            user_input: 用户原始输入
            intent: 解析后的意图
            all_tools: 所有可用工具
            
        Returns:
            OptimizedContext: 优化后的上下文
        """
        # 1. 动态选择工具
        selection = self.tool_selector.select_tools(user_input, intent, all_tools)
        
        # 2. 构建精简的工具列表
        tool_list = self._build_tool_list(selection.selected_tools)
        
        # 3. 构建 system prompt
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            tool_list=tool_list,
            expert_knowledge=selection.expert_knowledge or "暂无专家知识",
            intent_type=intent.intent_type,
            platform=selection.platform,
            objective=intent.objective or "未指定",
            budget=f"{intent.budget}元" if intent.budget else "未指定",
        )
        
        return OptimizedContext(
            system_prompt=system_prompt,
            available_tools=selection.selected_tools,
            tool_count=len(selection.selected_tools),
            expert_knowledge=selection.expert_knowledge,
            platform=selection.platform,
            context=selection.context,
        )
    
    def _build_tool_list(self, tools: List[ToolDefinition]) -> str:
        """构建精简的工具列表"""
        if not tools:
            return "暂无可用工具"
        
        lines = []
        for i, tool in enumerate(tools, 1):
            # 只显示核心信息
            lines.append(f"{i}. **{tool.name}** - {tool.description[:60]}...")
            if tool.input_schema.properties:
                params = list(tool.input_schema.properties.keys())[:3]
                lines.append(f"   参数: {', '.join(params)}{'...' if len(params) > 3 else ''}")
            lines.append("")
        
        return "\n".join(lines)
    
    def build_messages(
        self,
        user_input: str,
        optimized_context: OptimizedContext,
    ) -> List[Dict]:
        """构建 LLM 消息列表"""
        return [
            {
                "role": "system",
                "content": optimized_context.system_prompt,
            },
            {
                "role": "user",
                "content": user_input,
            },
        ]


# 全局实例
_optimizer: Optional[ContextOptimizer] = None


def get_context_optimizer() -> ContextOptimizer:
    """获取全局上下文优化器"""
    global _optimizer
    if _optimizer is None:
        _optimizer = ContextOptimizer()
    return _optimizer


def optimize_context(
    user_input: str,
    intent: ParsedIntent,
    all_tools: List[ToolDefinition],
) -> OptimizedContext:
    """便捷函数：优化 LLM 上下文"""
    return get_context_optimizer().optimize(user_input, intent, all_tools)
