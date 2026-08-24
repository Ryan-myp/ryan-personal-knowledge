"""
runtime/runtime.py - Agent Runtime 主循环

借鉴 DAP Agent internal/core/engine/runtime.go
核心职责：
1. 管理 Session 生命周期
2. 处理用户输入 → LLM → ToolCall → 执行 → 返回结果
3. 多平台 Skill 工具的统一调度
4. 跨 Skill 上下文传递
5. 预留 MultiAgentBridge 接口（用于后续切换到多 Agent）
"""

import uuid
import time
import json
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..core.interfaces import (
    ToolContext, ToolResult, ChatMessage, CapabilityModule,
    CapabilityRuntime, ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent
)
from ..core.tool_registry import SimpleToolRegistry
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from .skill import Skill, SkillLoader
from ..persistence.session_manager import SessionManager
from ..persistence.store import AdAgentStore


# ─── Agent Runtime ─────────────────────────────────────────────

class AgentRuntime:
    """
    单 Agent + 多 Skills 的主运行时。
    
    架构层次：
    ┌─────────────────────────────────────────┐
    │  AgentRuntime（主循环）                   │
    │  ├─ SessionManager（会话管理）             │
    │  ├─ IntentRouter（意图路由）               │
    │  ├─ ToolRegistry（工具执行）               │
    │  ├─ WriteGuard（写入保护）                 │
    │  └─ MultiAgentBridge（多 Agent 预留）      │
    └─────────────────────────────────────────┘
    
    借鉴 DAP Agent internal/core/engine/runtime.go 的核心设计：
    - Core 只认接口，不 import 业务
    - 业务通过 CapabilityModule 注入
    - Tool 执行有统一的生命周期（权限→审批→幂等→执行→审计）
    """
    
    def __init__(
        self,
        registry: ToolRegistry = None,
        intent_parser: IntentParser = None,
        intent_router: IntentRouter = None,
        write_guard: WriteGuard = None,
        skill_roots: list[str] = None,
        llm_client=None,  # 可选：自定义 LLM 客户端
        persistence_store: AdAgentStore = None,
    ):
        self.registry = registry or SimpleToolRegistry()
        self.intent_parser = intent_parser or LLMIntentParser(llm_client)
        self.intent_router = intent_router or SimpleIntentRouter()
        self.write_guard = write_guard
        self.skill_loader = SkillLoader(skill_roots)
        self._llm = llm_client
        self._sessions: dict[str, "SessionContext"] = {}
        self._background_tasks: list[dict] = []
        
        # 预留：多 Agent 桥接
        self._multi_agent_bridge: Optional["MultiAgentBridge"] = None
        
        # 持久化层（可选）
        self._session_manager: Optional[SessionManager] = None
        if persistence_store:
            self._session_manager = SessionManager(persistence_store)
    
    def inject_llm(self, llm_client) -> None:
        """注入 LLM 客户端"""
        self._llm = llm_client
        if isinstance(self.intent_parser, LLMIntentParser):
            self.intent_parser.inject_llm(llm_client)
    
    # ─── Capability 注册 ───────────────────────────────────────
    
    def register_capability(self, module: CapabilityModule) -> CapabilityRuntime:
        """
        注册一个 CapabilityModule。
        
        对应 DAP Agent 的 CapabilityModule.Configure() 模式：
        业务模块不直接操作 Runtime，而是通过接口注入能力。
        """
        context = CapabilityContextWrapper(self.registry)
        runtime = module.configure(context)
        
        # 注册编排 Skill
        for skill in runtime.orchestrator_skills:
            self._register_skill(skill)
        
        # 注册后台任务
        self._background_tasks.extend(runtime.background_tasks)
        
        # 注册写入保护
        if runtime.write_guard:
            self.write_guard = runtime.write_guard
        
        return runtime
    
    def _register_skill(self, skill: Skill) -> None:
        """将 Skill 的工具注册到 Registry"""
        for tool_def in skill.get_tools():
            handler = skill.get_tool_handler(tool_def.name)
            if handler:
                self.registry.register(tool_def, handler)
    
    # ─── 主循环入口 ────────────────────────────────────────────
    
    def run(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
        credentials: dict = None,
    ) -> dict:
        """
        执行一次完整的对话回合。
        
        对应 DAP Agent 的 Core Engine 主循环：
        用户输入 → 意图解析 → 工具路由 → 执行 → 返回结果
        
        Returns:
            {
                "session_id": str,
                "turn_id": str,
                "intent": dict,           # 解析后的意图
                "tool_calls": [...],       # 计划调用的工具
                "results": [...],          # 各工具执行结果
                "reply": str,              # 给用户的回复
                "needs_confirmation": bool, # 是否需要用户确认
            }
        """
        session_id = session_id or str(uuid.uuid4())
        turn_id = str(uuid.uuid4())[:8]
        
        # Step 1: 确保 Session 存在
        session = self._ensure_session(session_id, user_id, account_id, credentials)
        
        # Step 2: 解析用户意图
        intent = self.intent_parser.parse(user_input, session.ctx)
        
        # Step 3: 路由到平台工具
        tool_plan = self.intent_router.route(intent, self.registry)
        
        # Step 4: 执行工具（按平台顺序）
        results = []
        needs_confirmation = False
        confirmation_payload = None
        
        for platform, tools in tool_plan.items():
            for tool_def in tools:
                # 检查是否需要写入保护
                if tool_def.is_write_tool and self.write_guard:
                    allowed, reason = self.write_guard.reserve_write(
                        session.ctx, tool_def, intent.platform_params.get(platform, {})
                    )
                    if not allowed:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"Write guard blocked: {reason}",
                        })
                        continue
                
                # 构建执行输入
                tool_input = self._build_tool_input(
                    tool_def, intent, platform
                )
                
                # 执行工具
                result = self.registry.execute(session.ctx, tool_def.name, tool_input)
                
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                    "needs_confirmation": result.requires_confirmation,
                })
                
                if result.requires_confirmation:
                    needs_confirmation = True
                    confirmation_payload = result.card_payload
                
                # 保存执行结果到会话上下文（跨 Tool 传递）
                session.save_result(tool_def.name, result)
                
                # 将 protected_state 同步回 ctx，使后续 Tool 可以读取
                session.ctx.protected_state.update(session.protected_state)
        
        # Step 5: 生成回复
        reply = self._generate_reply(intent, results, needs_confirmation)
        
        # Step 6: 记录消息历史
        session.add_message({"role": "user", "content": user_input})
        session.add_message({"role": "assistant", "content": reply})
        
        return {
            "session_id": session_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "results": results,
            "reply": reply,
            "needs_confirmation": needs_confirmation,
            "confirmation_payload": confirmation_payload,
        }
    
    def _build_tool_input(
        self,
        tool_def: Any,
        intent: ParsedIntent,
        platform: str,
    ) -> dict:
        """
        根据意图和工具定义，构建执行输入。
        
        优先级：
        1. intent.platform_params[platform][tool_name]  ← 最具体
        2. intent.platform_params[platform].get(...)     ← 平台级参数
        3. intent 通用字段（budget, objective 等）
        4. 工具定义的默认值
        """
        platform_params = intent.platform_params.get(platform, {})
        tool_input = {}
        
        # 从平台参数中提取该工具需要的字段
        tool_prefix = tool_def.name.replace(f"{platform}_", "")
        for param_name, param_value in platform_params.items():
            if param_name in tool_def.input_schema.properties:
                tool_input[param_name] = param_value
        
        # 填充通用字段
        if intent.budget and "budget" not in tool_input:
            tool_input["budget"] = intent.budget
        if intent.objective and "objective" not in tool_input:
            tool_input["objective"] = intent.objective
        if intent.creative_materials and "creative_materials" not in tool_input:
            tool_input["creative_materials"] = intent.creative_materials
        
        return tool_input
    
    def _generate_reply(
        self,
        intent: ParsedIntent,
        results: list[dict],
        needs_confirmation: bool,
    ) -> str:
        """根据执行结果生成用户友好的回复"""
        success_count = sum(1 for r in results if r.get("success"))
        fail_count = len(results) - success_count
        
        if needs_confirmation:
            return "⚠️ 需要确认：部分操作需要您的确认才能继续。"
        
        if fail_count > 0 and success_count == 0:
            errors = [r.get("error", "unknown") for r in results if not r.get("success")]
            return f"❌ 执行失败：{errors}"
        elif fail_count > 0:
            return (
                f"⚠️ 部分成功：{success_count} 个操作完成，{fail_count} 个失败。\n"
                + "\n".join(f"  - {r['tool']}: {r.get('error', 'failed')}"
                          for r in results if not r.get("success"))
            )
        else:
            return (
                f"✅ 成功创建 {success_count} 个广告操作：\n"
                + "\n".join(f"  - [{r.get('platform', '?')}] {r['tool']}"
                          for r in results)
            )
    
    # ─── Session 管理 ──────────────────────────────────────────
    
    def _ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
    ) -> "SessionContext":
        if session_id not in self._sessions:
            ctx = ToolContext(
                session_id=session_id,
                user_id=user_id,
                account_id=account_id,
                credentials=credentials or {},
            )
            session = SessionContext(session_id, ctx)
            self._sessions[session_id] = session
            
            # Save to persistence if available
            if self._session_manager:
                self._session_manager.create_session(
                    session_id, user_id, account_id, {"credentials": credentials or {}}
                )
        return self._sessions[session_id]
    
    # ─── 多 Agent 桥接（预留） ─────────────────────────────────
    
    def attach_multi_agent_bridge(self, bridge: "MultiAgentBridge") -> None:
        """
        附加多 Agent 桥接器。
        
        当前是单 Agent 模式，调用此方法后可无缝切换到多 Agent 模式。
        桥接器负责将单次 run() 拆分为多个 Agent 实例的协作调用。
        """
        self._multi_agent_bridge = bridge
    
    def run_multi_agent(self, user_input: str, **kwargs) -> dict:
        """
        多 Agent 模式入口（预留接口）。
        
        当 attach_multi_agent_bridge() 被调用后，此方法生效。
        否则回退到单 Agent 模式（调用 run()）。
        """
        if self._multi_agent_bridge:
            return self._multi_agent_bridge.dispatch(user_input, **kwargs)
        return self.run(user_input, **kwargs)


# ─── Session Context ────────────────────────────────────────────

class SessionContext:
    """
    会话上下文 - 对应 Go 的 core.AgentContext + Session
    
    管理单次对话的历史消息和跨 Tool 调用状态。
    """
    
    def __init__(self, session_id: str, ctx: ToolContext):
        self.session_id = session_id
        self.ctx = ctx
        self.messages: list[dict] = []
        self.tool_results: dict[str, ToolResult] = {}  # tool_name -> last result
        self.protected_state: dict[str, Any] = {}      # 跨 Tool 保持的状态
    
    def add_message(self, message: dict) -> None:
        """添加对话消息"""
        self.messages.append(message)
    
    def save_result(self, tool_name: str, result: ToolResult) -> None:
        """保存工具执行结果，供后续 Tool 引用"""
        self.tool_results[tool_name] = result
        # 如果结果中有 campaign_id 等关键字段，自动保存到 protected_state
        for key in ["campaign_id", "ad_set_id", "ad_group_id", "creative_id"]:
            if key in result.data:
                self.protected_state[key] = result.data[key]
    
    def get_protected(self, key: str, default=None) -> Any:
        """获取跨 Tool 共享的受保护状态"""
        return self.protected_state.get(key, default)
    
    def to_chat_messages(self) -> list[ChatMessage]:
        """转换为 ChatMessage 列表（供 LLM 使用）"""
        return [
            ChatMessage(
                role=m["role"],
                content=m["content"],
            )
            for m in self.messages
        ]


# ─── CapabilityContextWrapper ───────────────────────────────────

class CapabilityContextWrapper:
    """
    Capability 配置上下文包装器。
    
    对应 DAP Agent 的 CapabilityContext，提供给 CapabilityModule.configure()。
    """
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.skills: dict[str, Skill] = {}
        self.config: dict[str, Any] = {}
    
    def register_skill(self, skill: Skill) -> None:
        """注册一个 Skill"""
        self.skills[skill.name] = skill


# ─── MultiAgentBridge（预留接口） ──────────────────────────────

class MultiAgentBridge:
    """
    多 Agent 桥接器接口。
    
    预留：未来可从单 Agent 切换到多 Agent 架构时，
    实现此接口并 attach 到 AgentRuntime。
    
    职责：
    - 将单次 run() 请求拆分为多个子 Agent 任务
    - 协调各子 Agent 的执行顺序和依赖
    - 汇总各子 Agent 的执行结果
    """
    
    @abstractmethod
    def dispatch(self, user_input: str, **kwargs) -> dict:
        """分发请求到多个子 Agent"""
        pass
    
    @abstractmethod
    def collect_results(self, agent_results: list[dict]) -> dict:
        """收集并汇总各子 Agent 的结果"""
        pass


from abc import ABC
MultiAgentBridge.__abstractmethods__ = {"dispatch", "collect_results"}
