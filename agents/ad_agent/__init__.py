"""
ad_agent - 单 Agent + 多 Skills 广告投放架构

核心设计：
1. AgentRuntime：单 Agent 主循环，协调所有平台 Skill
2. CapabilityModule：各平台能力模块标准接口
3. IntentRouter：意图识别 → 平台工具映射
4. WriteGuard：写入前保护（幂等、冲突检测）
5. MultiAgentBridge：预留接口，后续切换到多 Agent

借鉴 DAP Agent（Go）架构模式：
- internal/core/interfaces.go    → core/interfaces.py
- internal/core/engine/runtime.go → runtime/runtime.py
- internal/capabilities/tiktok/   → capabilities/*.py
- internal/skill/loader.go        → runtime/skill.py
"""

from .core.interfaces import (
    ToolDefinition, ToolHandler, ToolResult, ToolContext,
    CapabilityModule, CapabilityRuntime, WriteGuard,
    ParsedIntent, ToolRegistry, IntentParser, IntentRouter,
    RiskLevel, ToolEffect, ReplayPolicy,
)
from .core.tool_registry import SimpleToolRegistry
from .core.intent import LLMIntentParser, SimpleIntentRouter, ParsedIntent
from .runtime.runtime import AgentRuntime, SessionContext
from .runtime.skill import SkillLoader, BaseSkill, SkillContract
from .capabilities.base import BaseCapability
from .capabilities.meta_capability import MetaCapability, create_meta_capability
from .capabilities.platform_capabilities import (
    GoogleCapability, create_google_capability,
    TikTokCapability, create_tiktok_capability,
    DV360Capability, create_dv360_capability,
)
from .user_skills.orchestrator import (
    AdCampaignOrchestratorSkill, create_orchestrator_skill,
)


__version__ = "0.1.0"
__all__ = [
    # Core interfaces
    "ToolDefinition", "ToolHandler", "ToolResult", "ToolContext",
    "CapabilityModule", "CapabilityRuntime", "WriteGuard",
    "ParsedIntent", "ToolRegistry", "IntentParser", "IntentRouter",
    "RiskLevel", "ToolEffect", "ReplayPolicy",
    # Registry
    "SimpleToolRegistry",
    # Intent
    "LLMIntentParser", "SimpleIntentRouter",
    # Runtime
    "AgentRuntime", "SessionContext",
    # Skill
    "SkillLoader", "BaseSkill", "SkillContract",
    # Capabilities
    "BaseCapability",
    "MetaCapability", "GoogleCapability", "TikTokCapability", "DV360Capability",
    "create_meta_capability", "create_google_capability",
    "create_tiktok_capability", "create_dv360_capability",
    # User Skills
    "AdCampaignOrchestratorSkill", "create_orchestrator_skill",
]
