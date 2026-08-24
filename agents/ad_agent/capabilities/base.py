"""
capabilities/base.py - 平台 Capability 基类

所有广告平台 Capability 都继承此类。
提供标准化的工具注册、意图映射、写入保护等能力。

借鉴 DAP Agent internal/capabilities/tiktok/runtime/module.go
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..core.interfaces import (
    ToolContext, ToolResult, ToolDefinition, ToolHandler,
    CapabilityModule, CapabilityContext, CapabilityRuntime,
    WriteGuard, RiskLevel, ToolEffect
)
from ..core.tool_registry import SimpleToolRegistry


class BaseCapability(CapabilityModule, ABC):
    """
    平台 Capability 基类。
    
    子类只需实现：
    1. platform_name: 平台名称（meta/google/tiktok/dv360）
    2. register_tools(): 注册该平台的工具
    3. get_intent_mappings(): 返回 intent_type → [tool_names] 映射
    
    不实现的部分由基类提供默认行为。
    """
    
    # 平台名称（子类必须覆盖）
    platform_name: str = ""
    
    # Skill 描述模板
    SKILL_DESCRIPTION_TEMPLATE = """
## {platform} 广告投放能力

本 Skill 提供 {platform} 平台的完整广告投放操作能力。

### 支持的广告类型
- 搜索广告（Search Ads）
- 展示广告（Display Ads）
- 视频广告（Video Ads）
- 应用广告（App Ads）
- 购物广告（Shopping Ads）

### 支持的投放目标
- sales：电商销售转化
- leads：线索收集
- traffic：网站流量
- brand：品牌曝光

### 可用工具
{tool_list}
""".strip()
    
    def configure(self, context: CapabilityContext) -> CapabilityRuntime:
        """
        配置并返回 CapabilityRuntime。
        
        对应 DAP Agent CapabilityModule.Configure() 模式：
        1. 读取业务依赖
        2. 创建工具处理器
        3. 注册到 Registry
        4. 返回 CapabilityRuntime
        """
        # Step 1: 注册平台工具
        self._register_platform_tools(context.registry)
        
        # Step 2: 创建编排 Skill
        orchestrator_skill = self._build_orchestrator_skill(context.registry)
        
        # Step 3: 构建意图映射
        intent_mappings = self._build_intent_mappings()
        
        # Step 4: 构建写入保护（子类可覆盖）
        write_guard = self._build_write_guard()
        
        # Step 5: 返回运行时声明
        return CapabilityRuntime(
            orchestrator_skills=[orchestrator_skill],
            intent_to_tools=intent_mappings,
            write_guard=write_guard,
        )
    
    def _register_platform_tools(self, registry: SimpleToolRegistry) -> None:
        """子类实现：将平台工具注册到 Registry"""
        tools = self.register_tools()
        for defn, handler in tools:
            registry.register(defn, handler)
    
    @abstractmethod
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        """
        注册平台工具。
        
        Returns:
            [(ToolDefinition, ToolHandler), ...]
        """
        pass
    
    def _build_orchestrator_skill(self, registry: SimpleToolRegistry):
        """
        构建编排 Skill（用于跨平台协调）。
        
        这是单 Agent 架构的核心：一个 Skill 可以协调多个平台。
        """
        from ..runtime.skill import BaseSkill, SkillContract
        
        tool_names = [
            t.name for t in registry.list_by_platform(self.platform_name)
        ]
        tool_list_str = "\n".join(f"- `{t}`" for t in tool_names)
        
        description = self.SKILL_DESCRIPTION_TEMPLATE.format(
            platform=self.platform_name.capitalize(),
            tool_list=tool_list_str,
        )
        
        contract = SkillContract.__new__(SkillContract)
        contract.name = f"{self.platform_name}-ads"
        contract.platform = self.platform_name
        contract.description = description
        contract.capabilities = {}
        contract.triggers = [
            type('T', (), {'keywords': [self.platform_name, f'{self.platform_name} ads']})()
        ]
        
        skill = BaseSkill(contract)
        
        # 将已注册的工具处理器绑定到 Skill
        for tool_def in registry.list_by_platform(self.platform_name):
            _, handler = registry.get(tool_def.name)
            if handler:
                skill.register_handler(tool_def.name, handler)
        
        return skill
    
    def _build_intent_mappings(self) -> dict[str, dict[str, list[str]]]:
        """
        构建意图 → 平台工具映射。
        
        默认实现：为常见意图类型提供标准工具序列。
        子类可覆盖以提供平台特定映射。
        """
        return {
            "create_campaign": {
                self.platform_name: self._get_campaign_tool_sequence(),
            },
            "boost_post": {
                self.platform_name: self._get_boost_tool_sequence(),
            },
            "download_report": {
                self.platform_name: self._get_report_tool_sequence(),
            },
        }
    
    def _get_campaign_tool_sequence(self) -> list[str]:
        """子类覆盖：返回创建 Campaign 的工具序列"""
        return []
    
    def _get_boost_tool_sequence(self) -> list[str]:
        return []
    
    def _get_report_tool_sequence(self) -> list[str]:
        return []
    
    def _build_write_guard(self) -> Optional[WriteGuard]:
        """
        构建写入保护。
        
        默认实现：检查幂等性（相同参数不重复创建）。
        子类可覆盖以添加更复杂的业务保护逻辑。
        """
        return SimpleIdempotencyGuard()
    
    def _generate_tool_name(self, action: str, suffix: str = "") -> str:
        """生成平台工具名，格式：{platform}_{action}[_suffix]"""
        base = f"{self.platform_name}_{action}"
        return f"{base}_{suffix}" if suffix else base


class SimpleIdempotencyGuard(WriteGuard):
    """
    简单的幂等性写入保护。
    
    通过生成幂等键，防止同一参数重复提交。
    对应 DAP Agent 的 WriteExecutionGuard 模式的简化版。
    """
    
    def __init__(self, max_retries: int = 3):
        self._executed: dict[str, datetime] = {}
        self._max_retries = max_retries
    
    def reserve_write(
        self,
        ctx: ToolContext,
        tool_def: ToolDefinition,
        input_data: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """检查是否允许写入"""
        # 生成幂等键
        key = self._generate_key(tool_def.name, input_data, ctx.user_id)
        
        # 检查是否最近执行过（5分钟内去重）
        last_run = self._executed.get(key)
        if last_run:
            elapsed = (datetime.now() - last_run).total_seconds()
            if elapsed < 300:  # 5分钟窗口
                return False, f"Duplicate write detected for '{tool_def.name}' (last run {elapsed:.0f}s ago)"
        
        return True, None
    
    def _generate_key(self, tool_name: str, input_data: dict, user_id: str) -> str:
        """生成幂等键"""
        import json as _json
        input_str = _json.dumps(input_data, sort_keys=True, default=str)
        raw = f"{user_id}:{tool_name}:{input_str}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
    
    def mark_executed(self, tool_name: str, input_data: dict, user_id: str) -> None:
        """标记某次写入已执行（调用方在工具执行成功后调用）"""
        key = self._generate_key(tool_name, input_data, user_id)
        self._executed[key] = datetime.now()
