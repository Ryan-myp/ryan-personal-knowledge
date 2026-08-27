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
import os
import copy
import re
import hashlib
import threading
import logging
import importlib.util
from types import MappingProxyType
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import yaml

from ..core.interfaces import (
    ToolContext, ToolResult, ChatMessage, CapabilityModule,
    CapabilityRuntime, ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent, ToolHandler, ToolEffect, ExecutionMode
)
from ..core.tool_registry import GuardedToolRegistry, SimpleToolRegistry, validate_tool_input
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from ..core.cross_channel import CrossChannelAggregator, CrossChannelAnalyzer, build_batch_operations
from ..core.tool_selector import BusinessContext, DynamicToolSelector
from ..core.parameter_catalog import ParameterCatalogRegistry
from .skill import Skill, SkillLoader
from ..persistence.session_manager import SessionManager
from ..persistence.store import AdAgentStore, ToolCallRecord

logger = logging.getLogger(__name__)


# ─── 账户白名单验证器 ───────────────────────────────────────────

class AccountWhitelistValidator:
    """
    账户白名单验证器
    
    只允许操作配置文件中指定的测试账户，防止误操作生产账户
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        self.allowed_accounts: dict[str, list[str]] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self.allowed_accounts = config.get('allowed_accounts', {})
        except Exception as e:
            logger.warning(f"加载账户白名单配置失败: {e}")
    
    def reload(self):
        """重新加载配置"""
        self._load_config()
    
    def validate_account(self, platform: str, account_id: str) -> tuple[bool, str]:
        """
        验证账户是否在白名单中
        
        Returns:
            (is_allowed, error_message)
        """
        allowed = self.allowed_accounts.get(platform, [])
        
        # 空白名单必须 fail closed：凭证中出现的账户 ID 不能自动成为
        # 可操作账户。测试/本地开发应显式提供受控白名单。
        if not allowed:
            return False, f"{platform} 未配置受控账户白名单"
        
        # 检查账户是否匹配
        normalized_account = account_id.replace("act_", "")
        is_allowed = any(
            acc.replace("act_", "") == normalized_account 
            for acc in allowed
        )
        
        if not is_allowed:
            return False, f"账户 {account_id} 不在 {platform} 白名单中。允许操作的账户: {', '.join(allowed)}"
        
        return True, ""
    
    def get_allowed_accounts(self, platform: str) -> list[str]:
        """获取平台允许操作的账户列表"""
        return self.allowed_accounts.get(platform, [])


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
    
    # 平台名称标准化映射（intent 短名 → registry 完整名）
    PLATFORM_NAME_MAP: dict[str, str] = {
        'google': 'google-ads',
        'google-ads': 'google-ads',
    }

    # 平台账户 ID 字段名映射
    PLATFORM_ACCOUNT_KEY: dict[str, str] = {
        'google-ads': 'customer_id',
        'meta': 'account_id',
        'tiktok': 'advertiser_id',
        'dv360': 'advertiser_id',
    }

    # These fields are configuration/credential material, not advertising
    # resource fields.  They must never be accepted inside a tool payload or
    # an ``updates`` object.  Request-scoped ``credentials=...`` remains a
    # separate, in-memory transport input and is intentionally not scanned by
    # this validator.
    PROTECTED_INPUT_FIELDS = frozenset({
        "token", "accesstoken", "refreshtoken", "developertoken", "clientid",
        "clientsecret", "privatekey", "bcid", "partnerid", "mcc",
        "authorization", "credential", "credentials", "perterid",
    })

    def __init__(
        self,
        registry: ToolRegistry = None,
        intent_parser: IntentParser = None,
        intent_router: IntentRouter = None,
        write_guard: WriteGuard = None,
        skill_roots: list[str] = None,
        llm_client=None,  # 可选：自定义 LLM 客户端
        persistence_store: AdAgentStore = None,
        whitelist_validator: AccountWhitelistValidator = None,
        read_only_mode: bool = False,
        execution_mode: str = ExecutionMode.DRY_RUN.value,
        enforce_account_scope: bool = True,
        live_approved_tools: Optional[set[str]] = None,
        business_context: Optional[BusinessContext] = None,
        tool_selector: Optional[DynamicToolSelector] = None,
        offline_mode: bool = False,
        max_tool_calls: int = 32,
        turn_timeout_seconds: float = 120.0,
        max_user_input_chars: int = 12_000,
        max_platform_params_bytes: int = 256_000,
    ):
        base_registry = registry or SimpleToolRegistry()
        self.registry = (
            base_registry
            if isinstance(base_registry, GuardedToolRegistry)
            else GuardedToolRegistry(base_registry)
        )
        # GuardedToolRegistry exposes only non-executable Handler views to
        # callers. Runtime keeps the opaque capability needed for its
        # post-policy execution path.
        self._registry_execution_token = getattr(
            self.registry, "_execution_token", None
        )
        self.intent_parser = intent_parser or LLMIntentParser(llm_client)
        self.intent_router = intent_router or SimpleIntentRouter()
        self.write_guard = write_guard
        self.skill_loader = SkillLoader(skill_roots)
        self._llm = llm_client
        self._sessions: dict[str, "SessionContext"] = {}
        self._session_locks: dict[str, threading.RLock] = {}
        self._session_locks_guard = threading.RLock()
        self._background_tasks: list[dict] = []
        self._loaded_skills: dict[str, Skill] = {}  # platform -> Skill
        # Keep exact registration ownership so multiple Skills can share a
        # platform and unload cannot rely on a non-existent ``skill.tools``
        # attribute or accidentally remove another Skill's tools.
        # ``_loaded_skills`` remains a primary-by-platform compatibility view;
        # these indexes retain every Skill for exact lifecycle operations.
        self._skill_objects: dict[str, Skill] = {}
        self._skill_keys_by_platform: dict[str, list[str]] = {}
        self._skill_tool_names: dict[str, list[str]] = {}
        self._skill_platforms: dict[str, str] = {}
        self._skill_factories: dict[str, callable] = {}  # platform -> Capability factory
        self._credentials: dict = {}  # API 凭证配置
        self.tool_selector = tool_selector or DynamicToolSelector()
        self.parameter_catalogs = ParameterCatalogRegistry()
        self.business_context = business_context
        if business_context:
            self.tool_selector.set_business_context(
                business_context.business_name, business_context
            )

        if execution_mode not in {mode.value for mode in ExecutionMode}:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        # dry_run 是安全默认值；只有调用方显式指定 live 才允许进入真实写入分支。
        self.execution_mode = execution_mode
        # ``ToolDefinition.live_support`` describes adapter intent, but is not
        # an approval.  Keep a separate, code-side allowlist so an unverified
        # write can never become live merely because a definition defaulted to
        # True.  This set is deliberately not populated from user input or
        # provider credentials.
        self._live_approved_tools = set(live_approved_tools or set())
        # 读请求也默认受受控账户边界约束，避免带凭证的服务被用来查询
        # 任意账户。需要本地离线探索时应显式提供测试 validator。
        self.enforce_account_scope = enforce_account_scope
        # Offline fixtures are useful for local development, but a normal
        # Runtime must not present provider-free mock rows as real query
        # results.  Write planning remains available without a client because
        # dry-run writes are intercepted before handlers execute.
        self.offline_mode = bool(offline_mode)
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if turn_timeout_seconds <= 0:
            raise ValueError("turn_timeout_seconds must be positive")
        self.max_tool_calls = int(max_tool_calls)
        self.turn_timeout_seconds = float(turn_timeout_seconds)
        self.max_user_input_chars = int(max_user_input_chars)
        self.max_platform_params_bytes = int(max_platform_params_bytes)
        
        # 账户白名单验证器
        self.whitelist_validator = whitelist_validator or AccountWhitelistValidator()
        
        # 预留：多 Agent 桥接
        self._multi_agent_bridge: Optional["MultiAgentBridge"] = None
        
        # 持久化层（可选）
        self._session_manager: Optional[SessionManager] = None
        if persistence_store:
            self._session_manager = SessionManager(persistence_store)
            if self.write_guard and hasattr(self.write_guard, "bind_store"):
                self.write_guard.bind_store(persistence_store)

        # 只读模式：只注册 READ 类工具，跳过写保护检查
        self._read_only_mode = read_only_mode
        if read_only_mode:
            logger.info("🔒 只读模式已启用，仅允许查询操作")

    def set_execution_mode(self, execution_mode: str) -> None:
        """设置执行模式。外部请求不能通过 user_input 修改此值。"""
        if execution_mode not in {mode.value for mode in ExecutionMode}:
            raise ValueError(f"Unsupported execution_mode: {execution_mode}")
        self.execution_mode = execution_mode

    def set_business_context(self, context: Optional[BusinessContext]) -> None:
        """Set the business policy used to constrain future turns."""
        self.business_context = context
        self.tool_selector.business_context = context
        if context:
            self.tool_selector.set_business_context(context.business_name, context)

    def load_business_context(
        self, business_name: str, skills_root: Optional[str] = None,
    ) -> BusinessContext:
        """Load a business policy from ``businesses/<name>/SKILL.md``.

        Business files are declarative policy only.  Loading one never
        creates a provider client and never changes credentials or account
        allowlists.
        """
        from pathlib import Path

        root = Path(skills_root) if skills_root else Path(__file__).parent.parent / "skills"
        skill_file = root / "businesses" / business_name / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Business Skill not found: {skill_file}")
        content = skill_file.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        metadata = yaml.safe_load(match.group(1)) if match else {}
        business = metadata.get("business", {}) if isinstance(metadata, dict) else {}
        if not isinstance(business, dict):
            raise ValueError(f"Invalid business metadata in {skill_file}")
        context = BusinessContext(
            business_name=str(business.get("name") or business_name),
            allowed_channels=list(business.get("allowed_channels") or []),
            disallowed_channels=list(business.get("disallowed_channels") or []),
            allowed_campaign_types=list(business.get("allowed_campaign_types") or []),
            business_rules=dict(business.get("business_rules") or {}),
            focus_metrics=list(
                (business.get("business_rules") or {}).get("focus_metrics") or []
            ),
        )
        self.set_business_context(context)
        return context

    def _check_business_policy(self, intent: ParsedIntent) -> list[str]:
        """Validate channel and budget policy before any tool is routed."""
        context = self.business_context
        if not context:
            return []
        errors: list[str] = []
        for platform in intent.platforms:
            if not context.is_channel_allowed(platform):
                errors.append(
                    f"业务 {context.business_name} 不允许使用 {platform} 渠道"
                )
        rules = context.business_rules or {}

        # Campaign type is intentionally explicit.  Guessing a provider type
        # from a generic objective could bypass a business allowlist.
        if intent.intent_type == "create_campaign" and context.allowed_campaign_types:
            supplied_types = set()
            if getattr(intent, "campaign_type", None):
                supplied_types.add(str(intent.campaign_type).upper())
            for params in (intent.platform_params or {}).values():
                if not isinstance(params, dict):
                    continue
                for key in ("campaign_type", "type", "campaignType"):
                    value = params.get(key)
                    if value not in (None, ""):
                        supplied_types.add(str(value).upper())
            allowed_types = {str(value).upper() for value in context.allowed_campaign_types}
            if not supplied_types:
                errors.append(
                    f"业务 {context.business_name} 创建 Campaign 必须明确 campaign_type；"
                    f"允许值: {', '.join(sorted(allowed_types))}"
                )
            elif not supplied_types.intersection(allowed_types):
                errors.append(
                    f"Campaign 类型 {', '.join(sorted(supplied_types))} 不在业务允许范围内："
                    f"{', '.join(sorted(allowed_types))}"
                )

        # Validate both the common budget and every platform-specific budget.
        # Previously a platform-level daily_budget could silently skip the
        # business min/max guard when intent.budget was empty.
        budgets: list[tuple[str, Any]] = []
        if intent.budget is not None:
            budgets.append(("common", intent.budget))
        for platform, params in (intent.platform_params or {}).items():
            if not isinstance(params, dict):
                continue
            for key in ("budget", "daily_budget"):
                if params.get(key) not in (None, ""):
                    budgets.append((str(platform), params[key]))
                    break
        should_check_budget = intent.intent_type in {
            "create_campaign", "cross_channel_batch_update_budget",
        } or bool(budgets)
        if should_check_budget:
            minimum = rules.get("min_budget")
            maximum = rules.get("max_budget")
            for scope, raw_budget in budgets:
                try:
                    budget = float(raw_budget)
                except (TypeError, ValueError):
                    errors.append(f"{scope} 预算必须是数字")
                    continue
                if minimum is not None and budget < float(minimum):
                    errors.append(f"{scope} 预算低于业务下限 {minimum}")
                if maximum is not None and budget > float(maximum):
                    errors.append(f"{scope} 预算超过业务上限 {maximum}")
        return errors

    @property
    def is_dry_run(self) -> bool:
        return self.execution_mode == ExecutionMode.DRY_RUN.value

    def _validate_request_limits(
        self, user_input: str, platform_params: Optional[dict],
    ) -> Optional[str]:
        """Fail closed on oversized request envelopes before parsing/LLM use."""
        if not isinstance(user_input, str) or not user_input.strip():
            return "user_input 不能为空"
        if len(user_input) > self.max_user_input_chars:
            return f"user_input 超过长度限制（最多 {self.max_user_input_chars} 个字符）"
        if platform_params is not None:
            try:
                size = len(json.dumps(platform_params, ensure_ascii=False, default=str).encode("utf-8"))
            except (TypeError, ValueError):
                return "platform_params 不是可序列化的对象"
            if size > self.max_platform_params_bytes:
                return (
                    "platform_params 超过大小限制（最多 "
                    f"{self.max_platform_params_bytes} 字节）"
                )
        return None

    @staticmethod
    def _check_turn_budget(deadline: float, tool_call_count: int, max_tool_calls: int = 32) -> Optional[str]:
        if tool_call_count > max_tool_calls:
            return f"工具调用次数超过本回合上限（最多 {max_tool_calls} 次）"
        if time.monotonic() > deadline:
            return "本回合执行超时，已停止后续工具调用"
        return None

    def _enforce_result_limit(self, result: ToolResult, tool_def: Any) -> ToolResult:
        """Bound provider/LLM output before it reaches history or HTTP JSON."""
        limit = int(getattr(tool_def, "max_output_bytes", 1_000_000) or 1_000_000)
        try:
            size = len(json.dumps(result.data, ensure_ascii=False, default=str).encode("utf-8"))
        except (TypeError, ValueError):
            return ToolResult.error(f"{tool_def.name} 返回了不可序列化的结果")
        if size <= limit:
            return result
        return ToolResult.error(
            f"{tool_def.name} 返回结果超过大小限制（最多 {limit} 字节）"
        )
    
    def inject_llm(self, llm_client) -> None:
        """注入 LLM 客户端"""
        self._llm = llm_client
        if isinstance(self.intent_parser, LLMIntentParser):
            self.intent_parser.inject_llm(llm_client)

    def enable_read_only_mode(self) -> None:
        """
        启用只读模式：从注册表中移除所有 WRITE 类工具。
        调用此方法后，所有写操作工具将不可用。
        """
        self._read_only_mode = True

        self._filter_write_tools()

    def _filter_write_tools(self) -> None:
        """Remove write tools from the registry at every registration seam."""

        # 收集所有 WRITE 类工具名称
        write_tools = []
        for tool_def in self.registry.list_all():
            if tool_def.effect_class in (ToolEffect.WRITE, ToolEffect.EXTERNAL_WRITE):
                write_tools.append(tool_def.name)

        # 从注册表中移除
        for name in write_tools:
            try:
                self.registry.unregister(name)
                logger.debug(f"只读模式：已移除写工具 {name}")
            except Exception as e:
                logger.warning(f"移除工具 {name} 失败: {e}")

        logger.info(f"✅ 只读模式已启用，已过滤 {len(write_tools)} 个写工具")
    
    # ─── Capability 注册 ───────────────────────────────────────
    
    def register_capability(self, module: CapabilityModule) -> CapabilityRuntime:
        """
        注册一个 CapabilityModule。
        
        对应 DAP Agent 的 CapabilityModule.Configure() 模式：
        业务模块不直接操作 Runtime，而是通过接口注入能力。
        """
        context = CapabilityContextWrapper(self.registry)
        runtime = module.configure(context)

        # Publish provider parameter options as data owned by the Capability.
        # Existing tools get enum/lookup discovery automatically; a future
        # Skill can additionally provide richer versioned catalogs through the
        # CapabilityRuntime extension field.
        for definition in self.registry.list_all():
            self.parameter_catalogs.register_tool_schema(
                definition.platform,
                getattr(definition.input_schema, "properties", {})
                if definition.input_schema else {},
            )
        self.parameter_catalogs.register_many(
            getattr(runtime, "parameter_catalogs", []) or []
        )

        # Capability.configure() registers platform tools before returning.
        # Apply the read-only boundary immediately so callers cannot forget a
        # second, manually-invoked enable_read_only_mode() call.
        if self._read_only_mode:
            self._filter_write_tools()

        # Capability-provided mappings are the preferred routing source.  The
        # router retains its static map only as a compatibility fallback for
        # legacy/custom modules that predate CapabilityRuntime mappings.
        if runtime.intent_to_tools and hasattr(self.intent_router, "register_capability_mappings"):
            self.intent_router.register_capability_mappings(runtime.intent_to_tools)
        
        # 注册编排 Skill
        for skill in runtime.orchestrator_skills:
            self._register_skill(skill)
            if skill.platform and skill.platform != "multi_platform":
                self._loaded_skills.setdefault(skill.platform, skill)
        
        # 注册后台任务
        self._background_tasks.extend(runtime.background_tasks)
        
        # 注册写入保护
        if runtime.write_guard:
            self.write_guard = runtime.write_guard
            if self._session_manager and hasattr(self.write_guard, "bind_store"):
                self.write_guard.bind_store(self._session_manager.store)

        # A caller may set credentials before registering a Capability.  Bind
        # a client only to handlers that were created without an explicit
        # client; never replace an injected fake/test/client instance.
        self._refresh_unbound_clients()
        
        return runtime

    def list_parameter_options(
        self, platform: Optional[str] = None, field: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return JSON-safe static or dynamic provider parameter metadata."""
        if field:
            catalog = self.parameter_catalogs.get(platform or "", field)
            return [catalog.to_dict()] if catalog else []
        return self.parameter_catalogs.to_dict(platform)
    
    def _register_skill(self, skill: Skill) -> None:
        """将 Skill 的工具注册到 Registry"""
        registered_names: list[str] = []
        for tool_def in skill.get_tools():
            skill_platform = self.PLATFORM_NAME_MAP.get(skill.platform, skill.platform)
            tool_platform = self.PLATFORM_NAME_MAP.get(tool_def.platform, tool_def.platform)
            if skill.platform != "multi_platform" and tool_platform != skill_platform:
                raise ValueError(
                    f"Tool '{tool_def.name}' platform '{tool_platform}' "
                    f"does not match Skill platform '{skill_platform}'"
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            handler = skill.get_tool_handler(tool_def.name)
            if handler:
                self.registry.register(tool_def, handler)
                registered_names.append(tool_def.name)
        if not registered_names and skill.platform and skill.platform != "multi_platform":
            # BaseCapability's orchestrator Skill intentionally carries
            # knowledge/handlers but no duplicate ToolDefinitions; the
            # platform definitions were registered just before it was built.
            registered_names = [
                definition.name
                for definition in self.registry.list_by_platform(skill.platform)
            ]
        if registered_names:
            skill_key = str(getattr(skill, "name", "") or skill.platform)
            self._skill_tool_names[skill_key] = registered_names
            self._skill_platforms[skill_key] = skill.platform
            self._skill_objects[skill_key] = skill
            platform_key = self.PLATFORM_NAME_MAP.get(skill.platform, skill.platform)
            keys = self._skill_keys_by_platform.setdefault(platform_key, [])
            if skill_key not in keys:
                keys.append(skill_key)
    
    # ─── Skill 动态注册 ────────────────────────────────────────
    
    def register_skill(self, skill: Skill, platform: str, api_client=None) -> bool:
        """
        动态注册一个 Skill。
        
        策略：直接使用 Capability 的工具定义，而不是动态创建 Handler。
        
        Args:
            skill: Skill 对象（从 SKILL.md 解析）
            platform: 平台名称
            api_client: API 客户端（None 时使用 mock 模式）
        """
        # Dynamic Skill loading and the API/CLI path must use the same
        # canonical Capability factory.  The factory only constructs local
        # objects and does not contact a provider.
        from ..capabilities.factory import create_capability, normalize_platform
        canonical_platform = normalize_platform(platform)
        declared_platform = normalize_platform(getattr(skill, "platform", ""))
        if declared_platform and declared_platform != canonical_platform:
            raise ValueError(
                f"Skill '{getattr(skill, 'name', '')}' platform '{declared_platform}' "
                f"does not match requested platform '{canonical_platform}'"
            )
        skill_key = str(getattr(skill, "name", "") or f"{canonical_platform}:{id(skill)}")
        if skill_key in self._skill_tool_names:
            logger.info("ⓘ Skill '%s' 已加载，跳过重复注册", skill_key)
            return True
        
        # Capability is the compatibility source for built-in channel Skills.
        # A custom Skill may provide its own ToolDefinitions and handlers; in
        # that case register only the declared executable tools instead of
        # exposing every tool belonging to the platform.
        declared_tools = []
        get_tools = getattr(skill, "get_tools", None)
        get_handler = getattr(skill, "get_tool_handler", None)
        if callable(get_tools) and callable(get_handler):
            try:
                declared_tools = list(get_tools() or [])
            except Exception as exc:
                logger.warning("解析 Skill '%s' 工具声明失败: %s", skill_key, exc)

        # A custom Skill can target a new platform and provide all of its own
        # handlers.  Only built-in fallback Skills require a known Capability;
        # this keeps the extension seam genuinely Skill + Tools based.
        capability = None
        try:
            capability = create_capability(canonical_platform, api_client)
        except ValueError:
            if not declared_tools:
                logger.warning("⚠️ 未找到平台 '%s' 的 Capability，且 Skill 没有声明可执行工具", platform)
                return

        capability_tools = {
            definition.name: (definition, handler)
            for definition, handler in capability.register_tools()
        } if capability is not None else {}

        tools = []
        if declared_tools:
            for declared in declared_tools:
                declared_tool_platform = normalize_platform(
                    getattr(declared, "platform", "")
                )
                if declared_tool_platform != canonical_platform:
                    raise ValueError(
                        f"Tool '{declared.name}' platform '{declared_tool_platform}' "
                        f"does not match Skill platform '{canonical_platform}'"
                    )
                handler = get_handler(declared.name)
                if handler is None and declared.name in capability_tools:
                    # Allow a declarative channel Skill to reuse the verified
                    # provider handler while retaining the Skill's own scope.
                    _, handler = capability_tools[declared.name]
                if handler is not None:
                    tools.append((declared, handler))
            if not tools:
                logger.warning(
                    "⚠️ Skill '%s' 的工具均没有可执行 Handler，未注册",
                    skill_key,
                )
                return False
        else:
            # Legacy ``skills.loader.SkillDefinition`` does not implement the
            # core Skill interface; retain its platform-capability fallback.
            tools = list(capability_tools.values())

        if not tools:
            logger.warning(f"⚠️ Capability '{platform}' 没有定义任何工具")
            return False
        
        # 注册工具
        registered_count = 0
        for tool_def, handler in tools:
            tool_platform = normalize_platform(getattr(tool_def, "platform", ""))
            if tool_platform != canonical_platform:
                raise ValueError(
                    f"Tool '{tool_def.name}' platform '{tool_platform}' "
                    f"does not match Skill platform '{canonical_platform}'"
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            try:
                self.registry.register(tool_def, handler)
                self.parameter_catalogs.register_tool_schema(
                    tool_def.platform,
                    getattr(tool_def.input_schema, "properties", {})
                    if tool_def.input_schema else {},
                )
                registered_count += 1
                logger.debug(f"✅ 注册工具: {tool_def.name} (platform={platform})")
            except Exception as e:
                logger.warning(f"⚠️ 注册工具失败 '{tool_def.name}': {e}")
        
        if registered_count == 0:
            logger.warning("⚠️ Skill '%s' 没有实际注册任何工具", skill_key)
            return False

        # 保存 Skill 和平台映射
        self._loaded_skills.setdefault(canonical_platform, skill)
        self._skill_tool_names[skill_key] = [tool_def.name for tool_def, _ in tools]
        self._skill_platforms[skill_key] = canonical_platform
        self._skill_objects[skill_key] = skill
        keys = self._skill_keys_by_platform.setdefault(canonical_platform, [])
        if skill_key not in keys:
            keys.append(skill_key)

        # Optional Skill-level routing lets an extension introduce a new
        # intent without changing the built-in platform router.  The router
        # still resolves names through the registry, so a mapping can never
        # expose an unregistered tool.
        intent_mappings = getattr(skill, "intent_to_tools", None)
        if callable(intent_mappings):
            intent_mappings = intent_mappings()
        if intent_mappings and hasattr(self.intent_router, "register_capability_mappings"):
            self.intent_router.register_capability_mappings(intent_mappings)
            if hasattr(self.intent_parser, "register_intents"):
                self.intent_parser.register_intents(set(intent_mappings))
        logger.info(f"✅ 已动态注册 Skill '{skill.name}'，共 {registered_count} 个工具")
        return True

    @staticmethod
    def _load_skill_plugin(skill_dir: Any, api_client=None) -> Optional[Skill]:
        """Load an optional executable Skill plugin from a Skill directory.

        Supported convention:

        ``skills/<name>/tools.py`` or ``skills/<name>/tools/__init__.py``
        exports ``create_skill(api_client=None)`` (``get_skill`` is accepted
        as a compatibility alias).  The factory must return a Core ``Skill``
        implementation with ``get_tools`` and ``get_tool_handler`` methods.

        Importing a plugin only constructs local objects; provider I/O remains
        inside Runtime's normal execution gates.
        """
        from pathlib import Path

        skill_dir = Path(skill_dir)
        candidates = [skill_dir / "tools.py", skill_dir / "tools" / "__init__.py"]
        plugin_path = next((path for path in candidates if path.exists()), None)
        if plugin_path is None:
            return None

        module_name = "ad_agent_skill_" + hashlib.sha256(
            str(plugin_path.resolve()).encode("utf-8")
        ).hexdigest()[:16]
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            factory = getattr(module, "create_skill", None) or getattr(module, "get_skill", None)
            if not callable(factory):
                logger.warning("Skill plugin %s 缺少 create_skill(api_client=None)", plugin_path)
                return None
            try:
                skill = factory(api_client)
            except TypeError:
                skill = factory()
            if not (
                skill is not None
                and callable(getattr(skill, "get_tools", None))
                and callable(getattr(skill, "get_tool_handler", None))
            ):
                logger.warning("Skill plugin %s 未返回可执行 Core Skill", plugin_path)
                return None
            return skill
        except Exception as exc:
            logger.warning("加载 Skill plugin %s 失败: %s", plugin_path, exc)
            return None
    
    def load_skill(self, platform: str, skill: Skill, api_client=None) -> bool:
        """
        根据平台名称加载对应的 Skill。
        
        Args:
            platform: 平台名称 (meta/google/tiktok/dv360)
            skill: Skill 对象
            api_client: API 客户端
            
        Returns:
            是否加载成功
        """
        skill_key = str(getattr(skill, "name", "") or platform)
        if skill_key in self._skill_tool_names:
            logger.info(f"ⓘ Skill '{skill_key}' 已加载，跳过")
            return True
        
        try:
            return bool(self.register_skill(skill, platform, api_client))
        except Exception as e:
            logger.error(f"❌ 加载 Skill '{platform}' 失败: {e}")
            return False
    
    def unload_skill(self, platform: str, skill_name: Optional[str] = None) -> bool:
        """
        卸载指定平台的 Skill 工具。
        
        Args:
            platform: 平台名称
            
        Returns:
            是否卸载成功
        """
        canonical_platform = self.PLATFORM_NAME_MAP.get(platform, platform)
        candidates = list(self._skill_keys_by_platform.get(canonical_platform, []))
        if not candidates:
            primary = self._loaded_skills.get(canonical_platform) or self._loaded_skills.get(platform)
            if primary is not None:
                candidates = [str(getattr(primary, "name", "") or canonical_platform)]
        if not candidates and platform not in self._loaded_skills and canonical_platform not in self._loaded_skills:
            return True
        
        try:
            if skill_name:
                if skill_name not in candidates:
                    return False
                target_key = skill_name
            else:
                primary = self._loaded_skills.get(canonical_platform)
                target_key = str(getattr(primary, "name", "") or "") if primary else ""
                if target_key not in candidates:
                    target_key = candidates[0]
            tool_names = list(self._skill_tool_names.get(target_key, []))

            # Use the registry's locking/unregister seam instead of mutating
            # private indexes directly.
            for name in dict.fromkeys(tool_names):
                self.registry.unregister(name)
            self._skill_tool_names.pop(target_key, None)
            self._skill_platforms.pop(target_key, None)
            self._skill_objects.pop(target_key, None)

            remaining = [key for key in candidates if key != target_key]
            if remaining:
                self._skill_keys_by_platform[canonical_platform] = remaining
                replacement = self._skill_objects.get(remaining[0])
                if replacement is not None:
                    self._loaded_skills[canonical_platform] = replacement
            else:
                self._skill_keys_by_platform.pop(canonical_platform, None)
                self._loaded_skills.pop(canonical_platform, None)

            if platform != canonical_platform:
                self._loaded_skills.pop(platform, None)
            logger.info(
                "✅ 已卸载 Skill '%s' (platform=%s)，移除 %s 个工具",
                target_key, canonical_platform, len(set(tool_names)),
            )
            return True
        except Exception as e:
            logger.error(f"❌ 卸载 Skill '{platform}' 失败: {e}")
            return False
    
    def get_loaded_skills(self) -> dict[str, Skill]:
        """获取所有已加载的 Skills"""
        return self._loaded_skills.copy()
    
    def get_available_skills(self) -> dict[str, Skill]:
        """获取所有可用的 Skills（包括未加载的）"""
        all_skills = {}
        for root in self.skill_loader._roots:
            if not root.exists():
                continue
            for skill_file in root.rglob("SKILL.md"):
                try:
                    self.skill_loader._load_single_skill(str(skill_file.parent))
                except Exception as exc:
                    logger.debug("加载可用 Skill 失败 %s: %s", skill_file, exc)
        all_skills.update(self.skill_loader._skills)
        return all_skills
    
    def _load_required_skills(self, platforms: list[str]) -> None:
        """
        根据平台列表动态加载对应的 Skill 工具。

        Args:
            platforms: 需要加载的平台列表
        """
        if not platforms:
            return

        for platform in platforms:
            actual_platform = self.PLATFORM_NAME_MAP.get(platform, platform)

            if actual_platform in self._loaded_skills:
                continue  # 已加载，跳过

            # 查找对应的 Skill
            skill = self._find_skill_by_platform(actual_platform)
            if not skill:
                logger.warning(f"未找到平台 '{actual_platform}' 的 Skill 定义")
                continue

            # 获取 API 客户端
            api_client = self._get_api_client(platform)

            # 加载 Skill
            self.load_skill(actual_platform, skill, api_client)
    
    def _find_skill_by_platform(self, platform: str) -> 'Skill':
        """
        根据平台名称查找对应的 Skill。
        
        策略：
        1. 从已加载的 Skill 中查找
        2. 从 SkillLoader 缓存中查找
        """
        # 先从已加载的 Skill 中查找
        if platform in self._loaded_skills:
            return self._loaded_skills[platform]
        canonical_platform = self.PLATFORM_NAME_MAP.get(platform, platform)
        for skill_key in self._skill_keys_by_platform.get(canonical_platform, []):
            skill = self._skill_objects.get(skill_key)
            if skill is not None:
                return skill

        # 从 skill_loader 中递归查找。旧实现只扫描 root 的直接子目录，
        # 会漏掉 skills/channels/* 等真实 Skill 目录。
        for root in self.skill_loader._roots:
            if not root.exists():
                continue
            for skill_file in root.rglob("SKILL.md"):
                skill_dir = skill_file.parent
                try:
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if not content.startswith('---'):
                        continue
                    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                    if not match:
                        continue
                    metadata = yaml.safe_load(match.group(1)) or {}
                    skill_meta = metadata.get("skill", {}) if isinstance(metadata.get("skill"), dict) else {}
                    skill_platform = metadata.get('platform') or skill_meta.get('platform') or skill_dir.name
                    if skill_platform == platform or skill_dir.name == platform:
                        # 直接加载这个 skill，避免再次使用浅层 loader。
                        self.skill_loader._load_single_skill(str(skill_dir))
                        for loaded in self.skill_loader._skills.values():
                            if loaded.platform == platform or skill_dir.name == platform:
                                return loaded
                except Exception as e:
                    logger.debug(f"解析 Skill 文件失败 {skill_dir.name}: {e}")
        return None
    
    def set_credentials(self, credentials: dict) -> None:
        """设置凭证，仅保存在进程内；绝不据此修改账户白名单。

        白名单必须来自受控配置文件，不能由线上凭证中的 account/customer ID
        自动扩大，否则会把凭证范围误当成允许操作范围。
        """
        self._credentials = copy.deepcopy(credentials or {})
        self._refresh_unbound_clients()

    def _refresh_unbound_clients(self) -> None:
        """Attach configured clients to handlers that are still offline.

        This makes ``runtime.set_credentials(...)`` and
        ``runtime.run(credentials=...)`` useful even when Capabilities were
        registered first.  Explicitly injected clients are left untouched.
        Client construction itself is side-effect free; network access only
        occurs when a read Handler is actually executed.
        """
        if not self._credentials:
            return
        clients: dict[str, Any] = {}
        for tool_def in self.registry.list_all():
            try:
                _, handler = self._get_registered_tool(tool_def.name)
            except KeyError:
                continue
            if not hasattr(handler, "client") or getattr(handler, "client") is not None:
                continue
            platform = self.PLATFORM_NAME_MAP.get(tool_def.platform, tool_def.platform)
            if platform not in clients:
                clients[platform] = self._get_api_client(platform)
            client = clients[platform]
            if client is not None:
                handler.client = client
    
    def _get_api_client(self, platform: str):
        """获取指定平台的 API 客户端"""
        if not self._credentials:
            return None

        # Keep provider construction in one side-effect-free factory.  The
        # previous implementation duplicated this map in Runtime and could
        # drift from the CLI/server construction path.
        cred_key = "google" if platform in ("google", "google-ads") else platform

        credentials = self._credentials.get(cred_key, {})
        if not credentials:
            credentials = self._credentials.get(platform, {})
        if not credentials:
            return None

        try:
            from ..api_clients.factory import create_platform_client
            return create_platform_client(platform, credentials)
        except Exception as e:
            logger.debug(f"创建 {platform} API Client 失败: {e}")

        return None

    def _build_request_clients(self, credentials: Optional[dict]) -> dict[str, Any]:
        """Build per-request clients without replacing shared handlers.

        ``run(credentials=...)`` is request-scoped input. Mutating the
        Runtime's global credential/client state here would allow one user to
        affect another user's request, so these clients are passed through a
        copied Handler at execution time instead.
        """
        if not credentials:
            return {}
        from ..api_clients.factory import create_platform_client

        clients: dict[str, Any] = {}
        for platform in ("meta", "google-ads", "tiktok", "dv360"):
            key = "google" if platform == "google-ads" else platform
            provider_credentials = credentials.get(key) or credentials.get(platform)
            if not isinstance(provider_credentials, dict) or not provider_credentials:
                continue
            try:
                client = create_platform_client(platform, provider_credentials)
                if client is not None:
                    clients[platform] = client
            except Exception as exc:
                logger.warning("创建请求级 %s client 失败: %s", platform, exc)
        return clients

    def _execute_tool(
        self, ctx: ToolContext, tool_name: str, input_data: dict,
        request_clients: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        """Execute a tool with an optional request-scoped provider client."""
        definition, handler = self._get_registered_tool(tool_name)

        # A handler's fixture fallback is useful for explicit offline unit
        # tests, but it must not look like live provider data in the normal
        # Runtime path.  Guard before invoking the handler so detail reads
        # cannot bypass the result-level simulated/data_status check.
        if (
            definition.is_read_tool
            and not self.offline_mode
            and hasattr(handler, "client")
            and getattr(handler, "client", None) is None
        ):
            return ToolResult.error(
                f"{tool_name} 没有配置 Provider Client；当前未启用 offline_mode，"
                "不会返回模拟查询数据"
            )

        if not request_clients:
            result = self._execute_registered_tool(ctx, tool_name, input_data)
            return self._apply_read_data_boundary(tool_name, result)

        client = request_clients.get(
            self.PLATFORM_NAME_MAP.get(definition.platform, definition.platform)
        )
        if client is None or not hasattr(handler, "client"):
            result = self._execute_registered_tool(ctx, tool_name, input_data)
            return self._apply_read_data_boundary(tool_name, result)

        # Registered handlers are global. Copy only the handler for this call
        # so request-level credentials cannot race with another session.
        isolated_handler = copy.copy(handler)
        isolated_handler.client = client
        if definition.input_schema:
            errors = validate_tool_input(definition.input_schema, input_data)
            if errors:
                return ToolResult.error(f"Input validation failed: {errors}")
        if hasattr(isolated_handler, "execute"):
            result = isolated_handler.execute(ctx, input_data)
            return self._apply_read_data_boundary(tool_name, result)
        if callable(isolated_handler):
            result = isolated_handler(ctx, input_data)
            return self._apply_read_data_boundary(tool_name, result)
        return ToolResult.error(f"Tool '{tool_name}' has no executable handler")

    def _execute_registered_tool(
        self, ctx: ToolContext, tool_name: str, input_data: dict,
    ) -> ToolResult:
        """Execute through the registry's Runtime-only authorized seam."""
        execute = getattr(self.registry, "execute_authorized", None)
        if callable(execute):
            return execute(
                ctx, tool_name, input_data,
                _execution_token=self._registry_execution_token,
            )
        return self.registry.execute(ctx, tool_name, input_data)

    def _get_registered_tool(self, tool_name: str):
        """Get a raw tool tuple only through Runtime's guarded seam."""
        getter = getattr(self.registry, "get_authorized", None)
        if callable(getter):
            return getter(tool_name, self._registry_execution_token)
        return self.registry.get(tool_name)

    @classmethod
    def _protected_field_paths(cls, value: Any, path: str = "") -> list[str]:
        """Return structured paths containing configuration/credential keys."""
        found: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                normalized = re.sub(r"[^a-z0-9]", "", key_text.lower())
                current = f"{path}.{key_text}" if path else key_text
                if normalized in cls.PROTECTED_INPUT_FIELDS:
                    found.append(current)
                else:
                    found.extend(cls._protected_field_paths(item, current))
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                found.extend(cls._protected_field_paths(item, f"{path}[{index}]"))
        return found

    @classmethod
    def _validate_protected_input(cls, value: Any) -> list[str]:
        paths = cls._protected_field_paths(value)
        return paths[:10]

    @staticmethod
    def _confirmation_plan(
        session_id: str,
        user_id: str,
        account_id: str,
        tool_def: Any,
        input_data: dict,
    ) -> dict[str, str]:
        """Build a stable, opaque confirmation binding for one write plan."""
        normalized = json.dumps(input_data, sort_keys=True, default=str, separators=(",", ":"))
        idempotency_key = hashlib.sha256(
            f"{user_id}:{tool_def.name}:{normalized}".encode("utf-8")
        ).hexdigest()[:16]
        material = "|".join((
            str(session_id), str(account_id or ""), tool_def.name,
            normalized, idempotency_key,
        ))
        fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
        token = hashlib.sha256(
            f"ad-agent-confirm-v1:{fingerprint}".encode("utf-8")
        ).hexdigest()
        return {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "account_id": str(account_id or ""),
            "tool": tool_def.name,
            "plan_fingerprint": fingerprint,
            "confirmation_token": token,
            "idempotency_key": idempotency_key,
        }

    def _prepare_confirmation(
        self, expected: dict[str, str], create: bool = False,
        ttl_seconds: int = 600,
    ) -> dict[str, str]:
        """Attach durable expiry metadata to a live write approval plan."""
        if not self._session_manager:
            if create:
                # A non-persistent Runtime can still be used by local tests;
                # the API/server path always supplies a persistent store.
                expected = {**expected, "approval_persistence": "in_memory"}
            return expected
        store = self._session_manager.store
        existing = store.get_approval(expected["plan_fingerprint"])
        if existing:
            expected = {**expected, "expires_at": str(existing.get("expires_at", ""))}
            return expected
        if create:
            expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
            store.create_approval(
                expected["plan_fingerprint"], expected["confirmation_token"],
                expected["session_id"], expected.get("user_id", ""),
                expected["account_id"], expected["tool"], expires_at,
            )
            expected = {**expected, "expires_at": expires_at}
        return expected

    def _validate_confirmation_record(
        self, expected: dict[str, str], payload: dict,
    ) -> tuple[bool, str]:
        if not self._session_manager:
            return True, ""
        return self._session_manager.store.validate_approval(
            expected["plan_fingerprint"], expected["confirmation_token"],
            expected["session_id"], expected.get("user_id", ""),
            expected["account_id"], expected["tool"],
        )

    @classmethod
    def _confirmation_matches(
        cls,
        payload: Optional[dict],
        expected: dict[str, str],
    ) -> bool:
        if not isinstance(payload, dict) or payload.get("type") != "confirm_write":
            return False
        for key in ("session_id", "user_id", "account_id", "tool", "plan_fingerprint", "confirmation_token", "idempotency_key"):
            if str(payload.get(key, "")) != str(expected.get(key, "")):
                return False
        return True

    def _apply_read_data_boundary(self, tool_name: str, result: ToolResult) -> ToolResult:
        """Prevent provider-free fixtures from masquerading as live data.

        Handlers retain their direct offline fallback for unit tests and
        explicitly enabled local demos.  The normal Runtime path is stricter:
        a read without a configured provider client must fail closed unless
        ``offline_mode=True`` was explicitly selected by the caller.
        """
        if self.offline_mode or not result or not result.success:
            return result
        try:
            definition, _ = self._get_registered_tool(tool_name)
        except KeyError:
            return result
        if not definition.is_read_tool:
            return result
        data = result.data if isinstance(result.data, dict) else {}
        data_status = str(data.get("data_status") or "")
        if result.simulated or data.get("simulated") is True or data_status.startswith("offline"):
            return ToolResult.error(
                f"{tool_name} 没有配置 Provider Client；当前未启用 offline_mode，"
                "不会返回模拟查询数据"
            )
        return result
    
    def auto_load_skills(self, skills_root: str, credentials: dict = None) -> int:
        """
        自动加载 skills 目录下的所有 Skills。
        
        策略：
        1. 扫描 channels/ 子目录（渠道层 Skills）
        2. 扫描 businesses/ 子目录（业务层 Skills）
        3. 扫描 cross-channel/ 子目录（跨渠道 Skills）
        4. 只加载有工具定义的 Skill
        
        Args:
            skills_root: Skills 根目录路径
            credentials: API 凭证配置
            
        Returns:
            成功加载的 Skill 数量
        """
        import yaml
        from pathlib import Path
        
        loaded_count = 0
        credentials = credentials or {}
        # 保存凭证配置
        if credentials:
            self._credentials = copy.deepcopy(credentials)
        
        skill_roots = [
            Path(skills_root) / "channels",
            Path(skills_root) / "businesses",
            Path(skills_root) / "cross-channel",
        ]
        
        for root in skill_roots:
            if not root.exists():
                continue
            
            for skill_dir in root.iterdir():
                if not skill_dir.is_dir():
                    continue
                
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                
                try:
                    # 解析 SKILL.md frontmatter
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    metadata = {}
                    if content.startswith('---'):
                        import re
                        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                        if match:
                            metadata = yaml.safe_load(match.group(1))
                    
                    metadata = metadata if isinstance(metadata, dict) else {}
                    skill_metadata = metadata.get('skill', {})
                    skill_metadata = skill_metadata if isinstance(skill_metadata, dict) else {}
                    platform = (
                        metadata.get('platform')
                        or skill_metadata.get('platform')
                        or skill_dir.name
                    )

                    # Executable extensions take precedence over the legacy
                    # Markdown-only compatibility loader.  A plugin is still
                    # subject to the same registry, schema, account and write
                    # gates as built-in capabilities.
                    cred_key = platform
                    if platform not in credentials:
                        cred_key = {'google-ads': 'google'}.get(platform, platform)
                    api_client = None
                    if credentials and isinstance(credentials.get(cred_key), dict):
                        try:
                            from ..api_clients.factory import create_platform_client
                            api_client = create_platform_client(platform, credentials[cred_key])
                        except Exception as e:
                            logger.debug(f"创建 {platform} API Client 失败: {e}")
                    plugin_skill = self._load_skill_plugin(skill_dir, api_client)
                    if plugin_skill is not None:
                        before_tool_count = len(self.registry.list_all())
                        self.register_skill(plugin_skill, platform, api_client)
                        loaded_count += 1
                        logger.info(
                            f"✅ 自动加载 Skill plugin: {plugin_skill.name} ({platform}, "
                            f"{len(self.registry.list_all()) - before_tool_count} executable tools)"
                        )
                        continue
                    
                    # 检查是否有工具定义（从表格解析）
                    has_tools = '| Tool |' in content or 'name:' in content
                    
                    if has_tools:
                        # 加载 Skill
                        from ..skills.loader import SkillLoader
                        loader = SkillLoader()
                        loader.add_root(str(root))
                        skills = loader.load_all()
                        
                        skill = skills.get(skill_dir.name)
                        if not skill:
                            # 尝试从 name 字段获取
                            for s_name, s in skills.items():
                                if s.platform == platform:
                                    skill = s
                                    break
                        
                        if skill and skill.tools:
                            # 加载 Skill；以实际注册到 Registry 的定义计数，
                            # 不要把 SKILL.md 中的设计工具数量误报为可执行工具。
                            before_tool_count = len(self.registry.list_all())
                            if self.load_skill(self.PLATFORM_NAME_MAP.get(platform, platform), skill, api_client):
                                loaded_count += 1
                                actual_tool_count = len(self.registry.list_all()) - before_tool_count
                                logger.info(
                                    f"✅ 自动加载 Skill: {skill.name} ({platform}, "
                                    f"{actual_tool_count} executable tools)"
                                )
                            else:
                                logger.warning(f"⚠️ 加载 Skill 失败: {skill.name}")
                
                except Exception as e:
                    logger.warning(f"⚠️ 解析 Skill {skill_dir.name}/SKILL.md 失败: {e}")
        
        logger.info(f"✅ 自动加载完成，共加载 {loaded_count} 个 Skills")
        return loaded_count
    
    def _create_handler(self, skill: Skill, platform: str, api_client=None) -> Optional[ToolHandler]:
        """
        根据 Skill 和平台动态创建 Handler。
        
        策略：
        1. 根据 tool_name 推断 Handler 类名
        2. 从对应的 Capability 模块动态导入
        3. 支持多种命名约定：
           - {Prefix}{Action}RealHandler
           - {Prefix}{Action}Handler
           - {Prefix}{Action}MockHandler
        """
        import importlib
        
        # 根据 platform 选择模块和 prefix
        platform_map = {
            'meta': ('meta', 'Meta'),
            'google-ads': ('google', 'Google'),
            'tiktok': ('tiktok', 'TikTok'),
            'dv360': ('dv360', 'DV360'),
        }
        
        module_name, prefix = platform_map.get(platform, (None, None))
        if not module_name:
            return None
        
        try:
            # 导入模块
            module = importlib.import_module(f'..capabilities.{module_name}', __package__)
            
            # 返回工厂函数
            def handler_factory(tool_name):
                # 移除 platform 前缀
                parts = tool_name.split('_', 1)
                if len(parts) < 2:
                    return None
                
                action_part = parts[1]  # 'auth', 'create_campaign', 'list_campaigns'
                
                # 转换为 TitleCase
                words = action_part.split('_')
                title_case = ''.join(w.capitalize() for w in words)
                
                # 生成多种可能的 Handler 类名
                possible_names = [
                    f"{prefix}{title_case}RealHandler",     # MetaListCampaignsRealHandler
                    f"{prefix}{title_case}Handler",         # TikTokListCampaignsHandler
                    f"{prefix}{title_case}MockHandler",     # MetaListCampaignsMockHandler
                ]
                
                # 尝试找到对应的 Handler 类
                for handler_name in possible_names:
                    if hasattr(module, handler_name):
                        handler_class = getattr(module, handler_name)
                        
                        # 检查构造函数签名
                        import inspect
                        sig = inspect.signature(handler_class.__init__)
                        params = list(sig.parameters.keys())
                        
                        # 根据参数决定如何实例化
                        if 'api_client' in params or 'client' in params:
                            return handler_class(api_client)
                        else:
                            return handler_class()
                
                return None
            
            # 绑定当前 tool_name
            return lambda tool_name: handler_factory(tool_name)
            
        except Exception as e:
            logger.debug(f"创建 Handler 失败 {platform}: {e}")
            return None

    def _validate_account_for_tool(self, platform: str, account_id: str, is_write: bool) -> tuple[bool, str]:
        """统一账户边界。

        写操作无论是 dry-run 还是 live，都必须命中显式测试账户白名单；
        dry-run 也不能用任意生产账户生成看似可执行的计划。
        """
        if not account_id:
            return False, "缺少账户ID"
        allowed = self.whitelist_validator.get_allowed_accounts(platform)
        if (is_write or self.enforce_account_scope) and not allowed:
            return False, f"{platform} 未配置受控账户白名单，当前请求被拒绝"
        return self.whitelist_validator.validate_account(platform, account_id)

    def _simulate_write(self, tool_def: Any, input_data: dict, platform: str) -> ToolResult:
        """生成本地模拟结果，保证 dry-run 不触发任何平台 API。"""
        key = self.registry.generate_idempotency_key(tool_def.name, input_data, "dry-run") \
            if hasattr(self.registry, "generate_idempotency_key") else uuid.uuid4().hex[:16]
        name = input_data.get("name") or input_data.get("campaign_name") or f"dry_run_{key}"
        tool_name = tool_def.name.lower()
        if "line_item" in tool_name:
            resource_key = "line_item_id"
        elif "ad_group" in tool_name or "adgroup" in tool_name:
            resource_key = "ad_group_id" if "ad_group" in tool_name else "adgroup_id"
        elif "ad_set" in tool_name or "adset" in tool_name:
            resource_key = "ad_set_id" if "ad_set" in tool_name else "adset_id"
        elif "campaign" in tool_name:
            resource_key = "campaign_id"
        elif "creative" in tool_name:
            resource_key = "creative_id"
        elif "io" in tool_name:
            resource_key = "io_id"
        else:
            resource_key = "ad_id"

        is_update = any(word in tool_name for word in ("update", "pause", "resume", "enable", "disable"))
        resource_id = input_data.get(resource_key) or f"dry_{platform}_{key}"
        data = {
            "mode": ExecutionMode.DRY_RUN.value,
            "simulated": True,
            "live_support": bool(getattr(tool_def, "live_support", False)),
            "operation": "update" if is_update else "create",
            resource_key: resource_id,
            "name": name,
            "status": "SIMULATED_UPDATED" if is_update else "SIMULATED_DRAFT",
            "input": {k: v for k, v in input_data.items() if k != "credentials"},
        }
        provider_errors = validate_tool_input(
            tool_def.input_schema,
            input_data,
            include_provider_contract=True,
        ) if tool_def.input_schema else []
        data["provider_validation"] = {
            "ready": not provider_errors,
            "errors": provider_errors,
        }
        return ToolResult.dry_run(data)

    @staticmethod
    def _validate_semantic_write_input(tool_def: Any, input_data: dict) -> list[str]:
        """Validate invariants that the small ToolSchema cannot express."""
        errors: list[str] = []
        for key in ("budget", "daily_budget"):
            if key not in input_data or input_data[key] is None:
                continue
            value = input_data[key]
            if isinstance(value, bool):
                errors.append(f"{key} must be a number greater than 0")
                continue
            try:
                if float(value) <= 0:
                    errors.append(f"{key} must be a number greater than 0")
            except (TypeError, ValueError):
                errors.append(f"{key} must be a number greater than 0")

        updates = input_data.get("updates")
        if "updates" in tool_def.input_schema.required:
            if not isinstance(updates, dict) or not updates:
                errors.append("updates must be a non-empty object")

        duration = input_data.get("duration_days")
        if duration is not None:
            try:
                if int(duration) <= 0:
                    errors.append("duration_days must be greater than 0")
            except (TypeError, ValueError):
                errors.append("duration_days must be a positive integer")
        return errors

    @staticmethod
    def _freeze_credentials(value: Any) -> Any:
        """Make credentials visible to handlers as a read-only snapshot."""
        if isinstance(value, dict):
            return MappingProxyType({
                key: AgentRuntime._freeze_credentials(item)
                for key, item in value.items()
            })
        if isinstance(value, list):
            return tuple(AgentRuntime._freeze_credentials(item) for item in value)
        return value

    @staticmethod
    def _redact_for_persistence(value: Any) -> Any:
        """移除可能包含凭证的字段后再写入 SQLite。"""
        sensitive = (
            "token", "secret", "private_key", "credential", "authorization",
            "bc_id", "bcid", "partner_id", "partnerid", "perter_id", "perterid", "developer_token",
            "mcc", "client_id", "clientid",
        )
        if isinstance(value, dict):
            return {
                k: "<redacted>" if any(part in str(k).lower() for part in sensitive)
                else AgentRuntime._redact_for_persistence(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [AgentRuntime._redact_for_persistence(v) for v in value]
        if isinstance(value, str):
            # User messages are persisted as strings, so key-based redaction
            # alone is insufficient when a secret is pasted into chat.
            patterns = (
                # Quoted JSON/Python values, e.g. {'access_token': '...'}.
                r"(?is)(?P<prefix>['\"]?(?:access|refresh|developer)[_-]?token['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"]-----BEGIN.*?-----END[^\r\n]*-----['\"]",
                r"(?is)(?P<prefix>['\"]?private[_-]?key['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?client[_-]?secret['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|client[_-]?id)['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?authorization['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                # Unquoted key/value forms used by logs and CLI snippets.
                r"(?i)(?P<prefix>\b(?:access|refresh|developer)[_-]?token\s*[:=]\s*)[^\s,;}]+",
                r"(?is)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)-----BEGIN.*?-----END[^\r\n]*-----",
                r"(?i)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\bclient[_-]?secret\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\b(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|client[_-]?id|authorization)\s*[:=]\s*)[^\s,;}]+",
            )
            redacted = value
            for pattern in patterns:
                redacted = re.sub(
                    pattern,
                    lambda match: f"{match.group('prefix')}<redacted>",
                    redacted,
                )
            return redacted
        return value

    def _persist_tool_result(
        self, session: "SessionContext", turn_id: str, tool_def: Any,
        platform: str, input_data: dict, result: ToolResult,
    ) -> None:
        """记录安全的工具审计信息和模拟资源状态。"""
        if not self._session_manager:
            return
        now = datetime.now().isoformat()
        safe_input = self._redact_for_persistence(input_data)
        safe_output = self._redact_for_persistence(result.data)
        self._session_manager.record_tool_call(
            session.session_id,
            turn_id,
            ToolCallRecord(
                id=str(uuid.uuid4()), session_id=session.session_id, turn_id=turn_id,
                tool_name=tool_def.name, platform=platform, input_data=safe_input,
                output_data=safe_output, success=result.success,
                error=self._redact_for_persistence(result.error),
                started_at=now, ended_at=datetime.now().isoformat(),
            ),
        )

        campaign_id = result.data.get("campaign_id") if isinstance(result.data, dict) else None
        if campaign_id:
            self._session_manager.save_campaign(
                platform=platform,
                campaign_id=str(campaign_id),
                name=str(result.data.get("name") or input_data.get("name") or ""),
                status=str(result.data.get("status") or "DRAFT"),
                objective=input_data.get("objective"),
                budget_daily=input_data.get("budget"),
                metadata={"simulated": result.simulated},
                account_id=session.ctx.account_id,
            )

    def _start_workflow(
        self, session: "SessionContext", intent: ParsedIntent,
        tool_plan: dict[str, list[Any]],
    ) -> Optional[str]:
        """Create a local write-workflow record without contacting a provider."""
        if not self._session_manager:
            return None
        if not any(tool.is_write_tool for tools in tool_plan.values() for tool in tools):
            return None
        workflow_id = str(uuid.uuid4())
        self._session_manager.create_workflow(
            workflow_id,
            session.session_id,
            intent.intent_type,
            self.execution_mode,
            status="running",
            metadata={
                "platforms": list(intent.platforms),
                "dry_run": self.is_dry_run,
                "compensation_policy": "manual_review_required",
            },
        )
        return workflow_id

    def _finish_workflow(
        self,
        workflow_id: Optional[str],
        tool_plan: dict[str, list[Any]],
        results: list[dict],
        workflow_inputs: dict[int, dict],
    ) -> None:
        """Persist item-level state and record when a live chain needs review."""
        if not workflow_id or not self._session_manager:
            return
        write_tools = {
            tool.name for tools in tool_plan.values() for tool in tools
            if tool.is_write_tool
        }
        item_sequences = []
        successful_sequences = []
        failed_sequences = []
        unsupported_sequences = []
        for index, item in enumerate(results):
            if item.get("tool") not in write_tools:
                continue
            sequence = len(item_sequences) + 1
            item_sequences.append(sequence)
            skipped = bool(item.get("skipped"))
            if skipped:
                status = "skipped"
            elif isinstance(item.get("data"), dict) and item["data"].get("execution_status") == "unsupported":
                status = "unsupported"
                unsupported_sequences.append(sequence)
            elif item.get("needs_confirmation"):
                status = "awaiting_confirmation"
            elif item.get("success"):
                status = "succeeded"
                successful_sequences.append(sequence)
            else:
                status = "failed"
                failed_sequences.append(sequence)
            self._session_manager.record_workflow_item(
                workflow_id=workflow_id,
                sequence=sequence,
                platform=str(item.get("platform") or ""),
                tool_name=str(item.get("tool") or ""),
                status=status,
                input_data=self._redact_for_persistence(workflow_inputs.get(index, {})),
                output_data=self._redact_for_persistence(item.get("data")),
                error=item.get("error"),
            )

        if failed_sequences and successful_sequences and self.execution_mode == ExecutionMode.LIVE.value:
            self._session_manager.mark_workflow_items_for_compensation(
                workflow_id, successful_sequences
            )
            status = "partially_failed"
            compensation_required = True
        elif failed_sequences:
            status = "blocked" if self.is_dry_run else "failed"
            compensation_required = False
        elif unsupported_sequences:
            status = "blocked"
            compensation_required = False
        elif any(
            item.get("needs_confirmation")
            for item in results if item.get("tool") in write_tools
        ):
            status = "awaiting_confirmation"
            compensation_required = False
        else:
            status = "planned" if self.is_dry_run else "succeeded"
            compensation_required = False
        self._session_manager.update_workflow(
            workflow_id,
            status,
            {
                "write_item_count": len(item_sequences),
                "successful_items": len(successful_sequences),
                "failed_items": len(failed_sequences),
                "compensation_required": compensation_required,
                "compensation_policy": "manual_review_required",
            },
        )

    def _run_batch_plan(
        self,
        user_input: str,
        session: "SessionContext",
        turn_id: str,
        intent: ParsedIntent,
        tool_plan: dict[str, list[Any]],
        account_id: Optional[str],
        workflow_id: Optional[str],
    ) -> dict:
        """Expand a cross-channel batch request into safe local plan items.

        This intentionally stops at planning.  Each item carries a
        platform-scoped Campaign ID and account, so a future live executor can
        require a second explicit approval without ever guessing IDs across
        channels.
        """
        accounts: dict[str, str] = {}
        errors: list[str] = []
        for platform, tools in tool_plan.items():
            actual_platform = self.PLATFORM_NAME_MAP.get(platform, platform)
            resolved = self._resolve_platform_account(
                intent, platform, tools, account_id
            )
            allowed, error = self._validate_account_for_tool(
                actual_platform, resolved, True
            )
            if not allowed:
                errors.append(f"{platform}: {error}")
            else:
                accounts[platform] = resolved

        operations, planning_errors = build_batch_operations(intent, accounts)
        errors.extend(planning_errors)
        results: list[dict] = []
        workflow_inputs: dict[int, dict] = {}
        if len(operations) > self.max_tool_calls:
            errors.append(
                "批量操作数量超过本回合上限："
                f"最多允许 {self.max_tool_calls} 项"
            )
            operations = []
        tool_name_by_platform = {
            platform: tools[0].name
            for platform, tools in tool_plan.items()
            if tools
        }
        for message in errors:
            platform = message.split(":", 1)[0]
            results.append({
                "tool": tool_name_by_platform.get(platform, "cross_channel_batch"),
                "platform": platform,
                "success": False,
                "data": {"batch": True, "planned": False},
                "error": message,
            })

        for operation in operations:
            tool_name = tool_name_by_platform.get(operation.platform)
            if not tool_name:
                results.append({
                    "tool": "cross_channel_batch",
                    "platform": operation.platform,
                    "success": False,
                    "data": {"batch": True, "planned": False},
                    "error": "该平台没有已注册的 Campaign 更新工具",
                })
                continue
            tool_def = next(
                (tool for tool in tool_plan[operation.platform] if tool.name == tool_name),
                None,
            )
            if tool_def is None:
                continue
            tool_input = {
                "campaign_id": operation.campaign_id,
                "updates": operation.updates,
            }
            schema_errors = validate_tool_input(tool_def.input_schema, tool_input)
            if schema_errors:
                results.append({
                    "tool": tool_name,
                    "platform": operation.platform,
                    "success": False,
                    "data": {"batch": True, "planned": False},
                    "error": f"Input validation failed: {schema_errors}",
                })
                continue
            simulated = self._simulate_write(
                tool_def, tool_input, self.PLATFORM_NAME_MAP.get(operation.platform, operation.platform)
            )
            data = dict(simulated.data)
            data.update({
                "batch": True,
                "planned": True,
                "action": operation.action,
                "account_id": operation.account_id,
                "campaign_id": operation.campaign_id,
            })
            live_batch = self.execution_mode == ExecutionMode.LIVE.value
            if live_batch:
                data.update({
                    "mode": ExecutionMode.LIVE.value,
                    "execution_status": "unsupported",
                })
            result_index = len(results)
            results.append({
                "tool": tool_name,
                "platform": operation.platform,
                # Batch management currently has a planning implementation
                # only.  In live mode never report a simulated item as a
                # successful external write.
                "success": not live_batch,
                "data": data,
                "error": (
                    "跨渠道批量 Campaign 更新当前仅支持 dry-run，未调用线上 API"
                    if live_batch else None
                ),
                "needs_confirmation": False,
            })
            workflow_inputs[result_index] = tool_input

        session.add_message({"role": "user", "content": user_input})
        reply = self._generate_reply(intent, results, bool(errors and not operations))
        session.add_message({"role": "assistant", "content": reply})
        self._finish_workflow(workflow_id, tool_plan, results, workflow_inputs)
        if self._session_manager:
            self._session_manager.update_session(
                session.session_id,
                {
                    "execution_mode": self.execution_mode,
                    "read_only_mode": self._read_only_mode,
                    "message_count": len(session.messages),
                    "messages": self._redact_for_persistence(session.messages[-20:]),
                },
            )
        return {
            "session_id": session.session_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "results": results,
            "workflow_id": workflow_id,
            "reply": reply,
            "needs_confirmation": False,
            "confirmation_payload": None,
        }

    def _collect_cross_channel_metrics(
        self,
        intent: ParsedIntent,
        tool_plan: dict[str, list[Any]],
        results: list[dict],
        session: "SessionContext",
        turn_id: str,
        request_clients: Optional[dict[str, Any]] = None,
    ) -> None:
        """Collect campaign-scoped metrics for a cross-channel comparison.

        Campaign listing and reporting have different platform contracts.  A
        comparison therefore performs a second, read-only phase after the
        campaign IDs are known.  This method deliberately dispatches through
        the normal registry/runtime context so account scoping, schema
        validation, audit persistence, and client injection remain unchanged.
        It never calls a write tool.
        """
        if intent.intent_type not in {
            "cross_channel_compare",
            "cross_channel_performance_insights",
            "cross_channel_optimize_budget",
            "cross_channel_export_report",
        }:
            return

        report_tools = {
            "meta": "meta_get_campaign_report",
            "google": "google_get_campaign_report",
            "tiktok": "tiktok_get_campaign_report",
            # DV360 currently has no verified campaign-level report adapter.
            # Do not silently substitute a Line Item report in a Campaign
            # comparison; that would produce a semantically incorrect result.
        }
        already_collected = {item.get("tool") for item in results}
        listing_results = {
            item.get("platform"): item
            for item in results
            if item.get("success") and item.get("tool", "").endswith("list_campaigns")
        }

        for platform, listing in listing_results.items():
            report_name = report_tools.get(platform)
            if not report_name or report_name in already_collected:
                continue
            try:
                report_def, _ = self._get_registered_tool(report_name)
            except KeyError:
                continue

            listing_data = listing.get("data") if isinstance(listing.get("data"), dict) else {}
            campaigns = listing_data.get("campaigns") or []
            campaign_ids = []
            for campaign in campaigns if isinstance(campaigns, list) else []:
                if not isinstance(campaign, dict):
                    continue
                campaign_id = (
                    campaign.get("id") or campaign.get("campaign_id")
                    or campaign.get("campaign_group_id")
                )
                if campaign_id is not None and str(campaign_id) not in campaign_ids:
                    campaign_ids.append(str(campaign_id))
            if not campaign_ids:
                continue
            # Expose the second phase in the returned execution plan so the
            # caller can distinguish a comparison from a campaign-only list.
            tool_plan.setdefault(platform, []).append(report_def)

            per_platform_account = self._resolve_platform_account(
                intent, platform, [report_def], session.ctx.account_id
            )
            actual_platform = self.PLATFORM_NAME_MAP.get(platform, platform)
            allowed, account_error = self._validate_account_for_tool(
                actual_platform, per_platform_account, False
            )
            if not allowed:
                results.append({
                    "tool": report_name,
                    "platform": platform,
                    "success": False,
                    "error": f"指标采集账户校验失败: {account_error}",
                })
                continue

            platform_params = intent.platform_params.get(platform, {}) or {}
            if not isinstance(platform_params, dict):
                platform_params = {}
            report_input = {
                key: value
                for key, value in platform_params.items()
                if key in report_def.input_schema.properties
                and key not in {"campaign_id", "campaign_ids", "account_id", "customer_id", "advertiser_id"}
            }
            if getattr(intent, "date_range", None):
                if "date_range" in report_def.input_schema.properties:
                    report_input.setdefault("date_range", intent.date_range)
                if "date_preset" in report_def.input_schema.properties:
                    report_input.setdefault(
                        "date_preset", self._platform_date_range(platform, intent.date_range)
                    )
            if "campaign_ids" in report_def.input_schema.properties:
                report_input["campaign_ids"] = campaign_ids
            elif "campaign_id" in report_def.input_schema.properties:
                # Legacy adapters that accept one ID are intentionally limited
                # to the first ID; the result is marked by its adapter data.
                report_input["campaign_id"] = campaign_ids[0]
            for account_key in ("account_id", "advertiser_id", "customer_id"):
                if account_key in report_def.input_schema.properties:
                    report_input[account_key] = per_platform_account
                    break

            missing = validate_tool_input(report_def.input_schema, report_input)
            if missing:
                results.append({
                    "tool": report_name,
                    "platform": platform,
                    "success": False,
                    "error": f"指标采集参数不完整: {missing}",
                })
                continue

            original_account = session.ctx.account_id
            session.ctx.account_id = per_platform_account
            started_at = datetime.now().isoformat()
            try:
                report_result = self._execute_tool(
                    session.ctx, report_name, report_input, request_clients
                )
                results.append({
                    "tool": report_name,
                    "platform": platform,
                    "success": report_result.success,
                    "account_id": per_platform_account,
                    "data": self._redact_for_persistence(report_result.data),
                    "error": self._redact_for_persistence(report_result.error),
                    "needs_confirmation": report_result.requires_confirmation,
                })
                session.save_result(report_name, report_result, platform=actual_platform)
                session.ctx.protected_state.update(session.protected_state)
                self._persist_tool_result(
                    session, turn_id, report_def, actual_platform,
                    report_input, report_result,
                )
            except Exception as exc:
                logger.exception("跨渠道指标采集失败: %s", report_name)
                results.append({
                    "tool": report_name,
                    "platform": platform,
                    "success": False,
                    "error": f"跨渠道指标采集失败: {exc}",
                })
            finally:
                session.ctx.account_id = original_account
    
    # ─── 主循环入口 ────────────────────────────────────────────
    
    def _get_session_lock(self, session_id: str) -> threading.RLock:
        """Return the per-session lock used to serialize mutable turn state."""
        with self._session_locks_guard:
            return self._session_locks.setdefault(session_id, threading.RLock())

    def run(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
        credentials: dict = None,
        platform_params: dict = None,
        confirmed: bool = False,
        confirmation_payload: Optional[dict] = None,
    ) -> dict:
        """Execute one turn while serializing turns for the same session.

        SessionContext, credentials and protected state are mutable.  Without
        this boundary two concurrent requests for one session can interleave
        account context, tool outputs and confirmation state.
        """
        lock = self._get_session_lock(session_id or "__new_session__")
        with lock:
            return self._run_unlocked(
                user_input=user_input,
                session_id=session_id,
                user_id=user_id,
                account_id=account_id,
                credentials=credentials,
                platform_params=platform_params,
                confirmed=confirmed,
                confirmation_payload=confirmation_payload,
            )

    def _run_unlocked(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
        credentials: dict = None,
        platform_params: dict = None,
        confirmed: bool = False,
        confirmation_payload: Optional[dict] = None,
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
        input_error = self._validate_request_limits(user_input, platform_params)
        if input_error:
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": None,
                "tool_plan": {},
                "tool_selection": None,
                "results": [],
                "reply": f"❌ {input_error}",
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": [input_error],
            }
        # Secrets must not be sent to the LLM or retained in session history,
        # even when a caller accidentally pastes them into the chat text.
        safe_user_input = self._redact_for_persistence(user_input)
        
        # Step 1: 确保 Session 存在
        request_clients = self._build_request_clients(credentials)
        session = self._ensure_session(session_id, user_id, account_id, credentials)
        turn_deadline = time.monotonic() + self.turn_timeout_seconds
        session.ctx.metadata["turn_deadline"] = turn_deadline
        
        # Step 2: 解析用户意图
        # Give an injected LLM the bounded Skill/tool context before it emits
        # an intent.  The post-parse IntentRouter remains authoritative, so
        # this context can improve recognition but cannot grant execution.
        try:
            session.ctx.metadata["skill_context"] = self.tool_selector.build_context_for_input(
                safe_user_input, self.registry.list_all()
            )
        except Exception as exc:
            logger.debug("构建 Skill 解析上下文失败: %s", exc)
        intent = self.intent_parser.parse(safe_user_input, session.ctx)
        
        # 如果提供了 platform_params（来自确认请求），合并到意图中
        if platform_params:
            protected_paths = self._validate_protected_input(platform_params)
            if protected_paths:
                error = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected_paths)
                session.add_message({"role": "user", "content": safe_user_input})
                session.add_message({"role": "assistant", "content": error})
                return {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "timestamp": datetime.now().isoformat(),
                    "intent": None,
                    "tool_plan": {},
                    "tool_selection": None,
                    "results": [],
                    "reply": f"❌ {error}",
                    "needs_confirmation": False,
                    "confirmation_payload": None,
                    "policy_errors": [error],
                }
            merged_params = copy.deepcopy(intent.platform_params or {})
            for platform, values in platform_params.items():
                if isinstance(values, dict) and isinstance(merged_params.get(platform), dict):
                    merged_params[platform] = {
                        **merged_params[platform],
                        **self._redact_for_persistence(values),
                    }
                else:
                    merged_params[platform] = self._redact_for_persistence(values)
            intent.platform_params = merged_params
        
        # Step 2.5: 动态加载相关平台的 Skill 工具
        self._load_required_skills(intent.platforms)

        policy_errors = self._check_business_policy(intent)
        if policy_errors:
            reply = "❌ 业务策略阻止本次请求：" + "；".join(policy_errors)
            session.add_message({"role": "user", "content": safe_user_input})
            session.add_message({"role": "assistant", "content": reply})
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {},
                "tool_selection": None,
                "results": [],
                "reply": reply,
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": policy_errors,
            }

        # Step 3: 路由到平台工具.  Capability mappings are the executable
        # contract; the selector is then applied to that bounded candidate
        # set, so it can never expose or select an unrelated registered tool.
        tool_plan = self.intent_router.route(intent, self.registry)
        routed_tools = [tool for tools in tool_plan.values() for tool in tools]
        tool_selection = self.tool_selector.optimize_for_llm(
            safe_user_input, intent, routed_tools
        )
        selected_names = {tool.name for tool in tool_selection["selected_tools"]}
        if selected_names:
            tool_plan = {
                platform: [tool for tool in tools if tool.name in selected_names]
                for platform, tools in tool_plan.items()
            }
            tool_plan = {platform: tools for platform, tools in tool_plan.items() if tools}

        parameter_errors = self._validate_platform_parameter_contract(
            intent, tool_plan
        )
        if parameter_errors:
            reply = "❌ 参数契约阻止本次请求：" + "；".join(parameter_errors)
            session.add_message({"role": "user", "content": safe_user_input})
            session.add_message({"role": "assistant", "content": reply})
            first_tool = next(
                (tool for tools in tool_plan.values() for tool in tools), None
            )
            parameter_result = {
                "tool": first_tool.name if first_tool else "parameter_contract",
                "platform": first_tool.platform if first_tool else "",
                "success": False,
                "data": {},
                "error": "; ".join(parameter_errors),
                "needs_confirmation": False,
            }
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
                "tool_selection": None,
                "results": [parameter_result],
                "reply": reply,
                "needs_confirmation": False,
                "confirmation_payload": None,
                "policy_errors": parameter_errors,
            }
        
        # 检查是否需要执行任何工具
        if not tool_plan:
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {},
                "tool_selection": {
                    "tool_count": tool_selection["tool_count"],
                    "tools": [tool.name for tool in tool_selection["selected_tools"]],
                    "platforms": tool_selection["platforms"],
                    "context": tool_selection["context"],
                    "tool_prompt": tool_selection["tool_prompt"],
                    "expert_knowledge": tool_selection["expert_knowledge"],
                },
                "results": [],
                "reply": self._generate_chat_reply(safe_user_input),
                "needs_confirmation": False,
                "confirmation_payload": None,
            }

        # Batch management is a first-class planning operation.  It expands
        # IDs into independent items while retaining the normal whitelist and
        # workflow audit boundaries; no provider Handler is called here.
        if intent.intent_type in {
            "cross_channel_batch_pause",
            "cross_channel_batch_resume",
            "cross_channel_batch_update_budget",
        }:
            workflow_id = self._start_workflow(session, intent, tool_plan)
            return self._run_batch_plan(
                safe_user_input, session, turn_id, intent, tool_plan,
                account_id, workflow_id,
            )
        
        # Keep the caller's approval separate from the response payload that
        # is built during this turn.  Reusing the same variable would erase a
        # supplied plan token before the live validation branch.
        incoming_confirmation_payload = confirmation_payload

        # Step 4: 执行工具（按平台顺序）
        results = []
        needs_confirmation = False
        confirmation_payload = None
        workflow_id = self._start_workflow(session, intent, tool_plan)
        # Keep sensitive execution inputs local; they are only copied through
        # the redaction path when a workflow is persisted and are never added
        # to the public result payload.
        workflow_inputs: dict[int, dict] = {}
        
        tool_call_count = 0
        for platform, tools in tool_plan.items():
            # 转换平台名称
            actual_platform = self.PLATFORM_NAME_MAP.get(platform, platform)

            # 每个平台使用自己的账户（不跨平台共享）。没有显式账户时，
            # 只允许从配置的测试白名单中自动选择。
            per_platform_account = self._resolve_platform_account(
                intent, platform, tools, account_id
            )
            if not per_platform_account:
                test_accounts = self.whitelist_validator.get_allowed_accounts(actual_platform)
                # A single configured test account is a safe compatibility
                # fallback.  Once an operator configures multiple accounts,
                # silently picking the first one could target the wrong
                # advertiser; require the caller to select it explicitly.
                if len(test_accounts) == 1:
                    per_platform_account = test_accounts[0]
                else:
                    results.append({
                        "tool": tools[0].name if tools else "unknown",
                        "platform": actual_platform,
                        "success": False,
                        "data": {},
                        "error": "缺少账户ID",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "ask_account",
                            "platform": actual_platform,
                            "question": f"请提供 {actual_platform} 账户ID（当前只读模式仅允许查询测试账户）",
                        },
                    })
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    continue

            # 只读模式验证所有操作；写操作在 dry-run/live 两种模式下都必须
            # 命中显式测试账户白名单。
            platform_has_write = any(tool.is_write_tool for tool in tools)
            if self._read_only_mode or platform_has_write or self.enforce_account_scope:
                allowed, error_msg = self._validate_account_for_tool(
                    actual_platform, per_platform_account, platform_has_write
                )
                if not allowed:
                    results.append({
                        "tool": tools[0].name if tools else "unknown",
                        "platform": actual_platform,
                        "success": False,
                        "error": f"账户不在白名单中: {error_msg}",
                    })
                    continue

            # 非只读模式：写操作需要白名单 + 幂等保护
            chain_blocked = False
            chain_blocker = None
            for tool_def in tools:
                tool_call_count += 1
                budget_error = self._check_turn_budget(
                    turn_deadline, tool_call_count, self.max_tool_calls
                )
                if budget_error:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {"execution_status": "budget_exceeded"},
                        "error": budget_error,
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    continue
                if chain_blocked:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {"skipped": True, "mode": self.execution_mode},
                        "error": f"前置工具 {chain_blocker} 未成功，已停止后续依赖步骤",
                        "skipped": True,
                    })
                    continue
                if not self._read_only_mode:
                    if tool_def.is_write_tool and per_platform_account:
                        allowed, error_msg = self.whitelist_validator.validate_account(actual_platform, per_platform_account)
                        if not allowed:
                            results.append({
                                "tool": tool_def.name,
                                "platform": actual_platform,
                                "success": False,
                                "error": f"账户验证失败: {error_msg}",
                            })
                            continue
                # 为当前平台临时设置账户上下文
                original_account = session.ctx.account_id
                session.ctx.account_id = per_platform_account

                # 构建执行输入
                tool_input = self._build_tool_input(
                    tool_def, intent, platform, session.ctx
                )

                protected_paths = self._validate_protected_input(tool_input)
                if protected_paths:
                    error = "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected_paths)
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {},
                        "error": error,
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                unknown_params = tool_input.pop("_unknown_params", None)
                if unknown_params:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {},
                        "error": (
                            "工具参数契约不支持以下字段："
                            + ", ".join(unknown_params)
                            + "；请使用该工具 Schema 中声明的参数"
                        ),
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue
                
                # 检查必需参数是否齐全，不齐全则询问用户
                missing_params = tool_input.pop("_missing_params", None)
                if missing_params:
                    lookup_tools = self._lookup_tools_for_fields(
                        tool_def, missing_params
                    )
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"缺少必需参数: {', '.join(missing_params)}",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "ask_params",
                            "tool": tool_def.name,
                            "missing": missing_params,
                            "lookup_tools": lookup_tools,
                            "question": f"⚠️ 执行 {tool_def.name} 需要以下参数：{', '.join(missing_params)}，请提供这些参数",
                        },
                    })
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                semantic_errors = self._validate_semantic_write_input(
                    tool_def, tool_input
                ) if tool_def.is_write_tool else []
                if semantic_errors:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"Input validation failed: {semantic_errors}",
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                # Provider-specific requirements are stricter than the
                # fields needed to generate a dry-run plan.  Validate them
                # before confirmation/client execution only in the live path,
                # so dry-run can still preview an incomplete plan while live
                # can fail with an actionable error before any API call.
                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value:
                    provider_errors = validate_tool_input(
                        tool_def.input_schema,
                        tool_input,
                        include_provider_contract=True,
                    )
                    if provider_errors:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"Provider contract validation failed: {provider_errors}",
                            "needs_confirmation": False,
                        })
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue

                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value and (
                    not tool_def.live_support
                    or tool_def.name not in self._live_approved_tools
                ):
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"{tool_def.name} 当前未获 live 执行批准；仅支持 dry-run",
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                # live 写入必须由调用方显式确认；dry-run 不需要确认，因为不会
                # 触发外部写 API。确认状态只来自受信任的请求字段，不从自然语言推断。
                expected_confirmation = None
                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value:
                    expected_confirmation = self._prepare_confirmation(
                        self._confirmation_plan(
                            session_id, session.ctx.user_id, session.ctx.account_id,
                            tool_def, tool_input,
                        ),
                        create=not confirmed,
                    )

                if (
                    tool_def.is_write_tool
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and confirmed
                    and incoming_confirmation_payload is None
                ):
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "confirmed=true 必须携带当前写入计划的 confirmation_payload",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "confirm_write",
                            **(expected_confirmation or {}),
                            "input": self._redact_for_persistence(tool_input),
                            "question": "请使用当前计划返回的 confirmation_payload 确认。",
                        },
                    })
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value and confirmed and incoming_confirmation_payload is not None and not self._confirmation_matches(
                    incoming_confirmation_payload, expected_confirmation or {}
                ):
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "确认信息与当前写入计划不匹配，已拒绝执行",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "confirm_write",
                            **(expected_confirmation or {}),
                            "input": self._redact_for_persistence(tool_input),
                            "question": "写入计划已变化，请使用最新计划重新确认。",
                        },
                    })
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                if (
                    tool_def.is_write_tool
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and confirmed
                    and incoming_confirmation_payload is not None
                ):
                    approval_ok, approval_error = self._validate_confirmation_record(
                        expected_confirmation or {}, incoming_confirmation_payload
                    )
                    if not approval_ok:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"确认记录无效：{approval_error}",
                            "needs_confirmation": True,
                            "confirmation_payload": {
                                "type": "confirm_write",
                                **(expected_confirmation or {}),
                                "input": self._redact_for_persistence(tool_input),
                                "question": "确认记录已过期或已使用，请重新生成计划并确认。",
                            },
                        })
                        needs_confirmation = True
                        confirmation_payload = results[-1]["confirmation_payload"]
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue

                if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value and not confirmed:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "live 写操作等待显式确认",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "confirm_write",
                            "tool": tool_def.name,
                            "platform": actual_platform,
                            "input": self._redact_for_persistence(tool_input),
                            **(expected_confirmation or {}),
                            "question": f"即将对 {actual_platform} 执行 live 写操作 {tool_def.name}，请确认。",
                        },
                    })
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                # 使用最终规范化后的输入生成幂等键，保证 reserve 与成功后的
                # mark_executed 使用同一组字段；不能使用原始自然语言参数。
                if (
                    self.execution_mode == ExecutionMode.LIVE.value
                    and not self._read_only_mode
                    and tool_def.is_write_tool
                    and self.write_guard
                ):
                    allowed, reason = self.write_guard.reserve_write(
                        session.ctx, tool_def, tool_input
                    )
                    if not allowed:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"Write guard blocked: {reason}",
                        })
                        chain_blocked = True
                        chain_blocker = tool_def.name
                        session.ctx.account_id = original_account
                        continue
                
                # dry-run 下写工具只生成本地模拟结果，绝不触发 API Client。
                started_at = datetime.now().isoformat()
                try:
                    if tool_def.is_write_tool and self.is_dry_run:
                        schema_errors = validate_tool_input(tool_def.input_schema, tool_input) if tool_def.input_schema else []
                        if schema_errors:
                            result = ToolResult.error(f"Input validation failed: {schema_errors}")
                        else:
                            result = self._simulate_write(tool_def, tool_input, actual_platform)
                    else:
                        result = self._execute_tool(
                            session.ctx, tool_def.name, tool_input, request_clients
                        )
                except Exception as exc:
                    logger.exception("工具执行失败: %s", tool_def.name)
                    result = ToolResult.error(f"工具执行失败: {exc}")

                result = self._enforce_result_limit(result, tool_def)
                
                result_index = len(results)
                safe_result_data = self._redact_for_persistence(result.data)
                safe_result_error = self._redact_for_persistence(result.error)
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "account_id": per_platform_account,
                    "success": result.success,
                    "data": safe_result_data,
                    "error": safe_result_error,
                    "needs_confirmation": result.requires_confirmation,
                })
                workflow_inputs[result_index] = copy.deepcopy(tool_input)

                if not result.success or result.requires_confirmation:
                    chain_blocked = True
                    chain_blocker = tool_def.name
                
                if result.requires_confirmation:
                    needs_confirmation = True
                    confirmation_payload = result.card_payload
                
                # 保存执行结果到会话上下文（跨 Tool 传递）
                safe_result = ToolResult(
                    success=result.success,
                    data=safe_result_data,
                    error=safe_result_error,
                    requires_confirmation=result.requires_confirmation,
                    card_payload=self._redact_for_persistence(result.card_payload),
                    simulated=result.simulated,
                )
                session.save_result(tool_def.name, safe_result, platform=actual_platform)

                # 将 protected_state 同步回 ctx，使后续 Tool 可以读取
                session.ctx.protected_state.update(session.protected_state)

                # 成功的 live 写入才进入幂等记录；dry-run 不污染 live 去重状态。
                if (
                    result.success and not result.simulated and not result.requires_confirmation
                    and tool_def.is_write_tool
                    and self.write_guard and hasattr(self.write_guard, "mark_executed")
                ):
                    self.write_guard.mark_executed(tool_def.name, tool_input, session.ctx.user_id)
                    if expected_confirmation and incoming_confirmation_payload:
                        if self._session_manager:
                            self._session_manager.store.consume_approval(
                                expected_confirmation["plan_fingerprint"],
                                expected_confirmation["confirmation_token"],
                            )
                elif (
                    (not result.success or result.requires_confirmation)
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and tool_def.is_write_tool
                    and self.write_guard
                    and hasattr(self.write_guard, "release_write")
                ):
                    self.write_guard.release_write(
                        tool_def.name, tool_input, session.ctx.user_id
                    )

                # 记录安全审计信息，并保存本地模拟 Campaign 状态。
                self._persist_tool_result(
                    session, turn_id, tool_def, actual_platform,
                    tool_input, result,
                )

                # 恢复原始账户上下文
                session.ctx.account_id = original_account

        # Cross-channel comparison is a two-phase read workflow: first list
        # campaigns, then collect campaign-scoped report rows.
        self._collect_cross_channel_metrics(
            intent, tool_plan, results, session, turn_id, request_clients
        )
        self._finish_workflow(workflow_id, tool_plan, results, workflow_inputs)

        # Step 5: 生成回复
        cross_channel_summary = None
        cross_channel_insights = None
        cross_channel_budget_plan = None
        cross_channel_export = None
        if intent.intent_type in (
            "cross_channel_overview", "cross_channel_compare",
            "cross_channel_performance_insights", "cross_channel_optimize_budget",
            "cross_channel_export_report",
        ):
            cross_channel_summary = CrossChannelAggregator().aggregate(results)
            if intent.intent_type == "cross_channel_performance_insights":
                cross_channel_insights = CrossChannelAnalyzer.performance_insights(cross_channel_summary)
            elif intent.intent_type == "cross_channel_optimize_budget":
                params = intent.platform_params or {}
                common = params.get("_common", {}) if isinstance(params, dict) else {}
                common = common if isinstance(common, dict) else {}
                cross_channel_budget_plan = CrossChannelAnalyzer.budget_plan(
                    cross_channel_summary,
                    intent.budget,
                    common.get("minimum_budget"),
                    common.get("maximum_budget"),
                )
            elif intent.intent_type == "cross_channel_export_report":
                cross_channel_export = CrossChannelAnalyzer.export_csv(cross_channel_summary)
        reply = self._generate_reply(intent, results, needs_confirmation)
        if cross_channel_insights is not None:
            reply += self._format_cross_channel_insights(cross_channel_insights)
        if cross_channel_budget_plan is not None:
            reply += self._format_cross_channel_budget_plan(cross_channel_budget_plan)
        if cross_channel_export is not None:
            reply += "\n\n📄 已生成规范化 CSV 文本（仅本地生成，未写入平台）；请从返回字段 `cross_channel_export` 获取。"
        
        # Step 6: 记录消息历史
        session.add_message({"role": "user", "content": safe_user_input})
        session.add_message({"role": "assistant", "content": reply})
        if self._session_manager:
            self._session_manager.update_session(
                session_id,
                {
                    "execution_mode": self.execution_mode,
                    "read_only_mode": self._read_only_mode,
                    "message_count": len(session.messages),
                    "messages": self._redact_for_persistence(session.messages[-20:]),
                },
            )
        
        return {
            "session_id": session_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "tool_selection": {
                "tool_count": tool_selection["tool_count"],
                "tools": [tool.name for tool in tool_selection["selected_tools"]],
                "platforms": tool_selection["platforms"],
                "context": tool_selection["context"],
                "tool_prompt": tool_selection["tool_prompt"],
                "expert_knowledge": tool_selection["expert_knowledge"],
            },
            "results": results,
            "workflow_id": workflow_id,
            "cross_channel_summary": cross_channel_summary,
            "cross_channel_insights": cross_channel_insights,
            "cross_channel_budget_plan": cross_channel_budget_plan,
            "cross_channel_export": cross_channel_export,
            "reply": reply,
            "needs_confirmation": needs_confirmation,
            "confirmation_payload": confirmation_payload,
        }
    
    @staticmethod
    def _platform_date_range(platform: str, date_range: Any) -> Any:
        """Map common date-range vocabulary to a platform contract."""
        if not isinstance(date_range, str):
            return date_range
        if platform == "meta":
            return date_range.lower().replace("_days", "d")
        if platform == "google":
            return date_range.upper()
        return date_range

    def _build_tool_input(
        self,
        tool_def: Any,
        intent: ParsedIntent,
        platform: str,
        ctx: Any = None,
    ) -> dict:
        """
        根据意图和工具定义，构建执行输入。
        
        优先级：
        1. intent.platform_params[platform][tool_name]  ← 最具体
        2. intent.platform_params[platform].get(...)     ← 平台级参数
        3. ctx.account_id                              ← 账户ID
        4. intent 通用字段（budget, objective 等）
        5. 工具定义的默认值
        """
        platform_params = intent.platform_params.get(platform, {}) or {}
        actual_platform = self.PLATFORM_NAME_MAP.get(platform, platform)
        tool_input = {}

        # 支持平台级参数和 tool_name 级参数两种输入形式。
        specific_params = platform_params.get(tool_def.name, {}) if isinstance(platform_params, dict) else {}
        unknown_specific_params: list[str] = []
        if isinstance(specific_params, dict):
            platform_params = {**platform_params, **specific_params}

        # 从平台参数中提取该工具需要的字段，并统一跨渠道命名。
        aliases = {
            "name": ["name", "campaign_name", "adset_name", "ad_set_name", "adgroup_name", "line_item_name"],
            "campaign_name": ["campaign_name", "name"],
            "account_id": ["account_id", "ad_account_id", "advertiser_id", "customer_id"],
            "customer_id": ["customer_id", "account_id"],
            "advertiser_id": ["advertiser_id", "account_id"],
            "ad_set_id": ["ad_set_id", "adset_id"],
            "adset_id": ["adset_id", "ad_set_id"],
            "ad_group_id": ["ad_group_id", "adgroup_id"],
            "adgroup_id": ["adgroup_id", "ad_group_id"],
        }
        if isinstance(specific_params, dict):
            accepted_specific = set(tool_def.input_schema.properties)
            for param_name in tool_def.input_schema.properties:
                accepted_specific.update(aliases.get(param_name, [param_name]))
            unknown_specific_params = sorted(
                key for key in specific_params
                if key not in accepted_specific
            )
        for param_name in tool_def.input_schema.properties:
            candidates = aliases.get(param_name, [param_name])
            for candidate in candidates:
                if candidate in platform_params and platform_params[candidate] not in (None, ""):
                    tool_input[param_name] = platform_params[candidate]
                    break
        
        # 填充账户 ID（从上下文）
        if ctx and ctx.account_id:
            for account_field in ["account_id", "advertiser_id", "customer_id"]:
                if account_field in tool_def.input_schema.properties and account_field not in tool_input:
                    tool_input[account_field] = ctx.account_id
                    break

        # 使用上一步工具产生的资源 ID，形成 campaign → 下级层级的依赖链。
        if ctx:
            protected = getattr(ctx, "protected_state", {}) or {}
            scoped_keys_exist = any(":" in key for key in protected)
            for param_name in tool_def.input_schema.properties:
                if param_name in tool_input:
                    continue
                for candidate in aliases.get(param_name, [param_name]):
                    scoped_candidates = (
                        f"{actual_platform}:{candidate}",
                        f"{platform}:{candidate}",
                    )
                    scoped_value = next(
                        (
                            protected[key]
                            for key in scoped_candidates
                            if key in protected and protected[key] not in (None, "")
                        ),
                        None,
                    )
                    if scoped_value is not None:
                        tool_input[param_name] = scoped_value
                        break
                    # Compatibility for sessions created before namespaced
                    # state existed. Never use an unscoped ID once the session
                    # contains any platform-scoped state.
                    if (
                        not scoped_keys_exist
                        and candidate in protected
                        and protected[candidate] not in (None, "")
                    ):
                        tool_input[param_name] = protected[candidate]
                        break
        
        # 填充通用字段
        if intent.budget is not None and "budget" not in tool_input:
            tool_input["budget"] = intent.budget
        # Meta/TikTok/DV360 payloads use daily_budget or budget depending on
        # resource level. Preserve the common user-facing budget in the
        # provider field as well; otherwise a valid dry-run request would
        # produce an incomplete future live payload.
        if intent.budget is not None and "daily_budget" in tool_def.input_schema.properties:
            tool_input.setdefault("daily_budget", intent.budget)
        # Map the common business objective through provider-owned metadata.
        # The shared Runtime does not maintain a provider enum table; a Skill
        # can add/replace this mapping in its own field schema.
        if intent.objective:
            for param_name, field_schema in tool_def.input_schema.properties.items():
                if param_name in tool_input or not isinstance(field_schema, dict):
                    continue
                if field_schema.get("intent_field") != "objective":
                    continue
                mapped = (field_schema.get("intent_map") or {}).get(
                    str(intent.objective).lower(), intent.objective
                )
                tool_input[param_name] = mapped
            if "objective" in tool_def.input_schema.properties:
                tool_input.setdefault("objective", intent.objective)
        if getattr(intent, "campaign_type", None) and "campaign_type" in tool_def.input_schema.properties:
            tool_input.setdefault("campaign_type", intent.campaign_type)
        if getattr(intent, "date_range", None):
            if "date_range" in tool_def.input_schema.properties:
                tool_input.setdefault("date_range", intent.date_range)
            if "date_preset" in tool_def.input_schema.properties:
                tool_input.setdefault(
                    "date_preset", self._platform_date_range(platform, intent.date_range)
                )
        if intent.creative_materials and "creative_materials" not in tool_input:
            tool_input["creative_materials"] = intent.creative_materials

        # 从自然语言解析出的 campaign_name 兼容 name 型平台工具。
        if "name" in tool_def.input_schema.properties and "name" not in tool_input:
            campaign_name = platform_params.get("campaign_name")
            if campaign_name:
                tool_input["name"] = campaign_name

        # dry-run 创建下级资源时提供确定性的本地默认名称，不生成任何线上对象。
        if "name" in tool_def.input_schema.required and "name" not in tool_input:
            if self.is_dry_run and ("adset" in tool_def.name or "ad_set" in tool_def.name):
                tool_input["name"] = f"{platform}_dry_run_adset"
            elif self.is_dry_run and ("adgroup" in tool_def.name or "ad_group" in tool_def.name):
                tool_input["name"] = f"{platform}_dry_run_adgroup"
            elif self.is_dry_run and "line_item" in tool_def.name:
                tool_input["name"] = f"{platform}_dry_run_line_item"

        if "updates" in tool_def.input_schema.required:
            if intent.intent_type in ("pause_campaign", "resume_campaign"):
                paused = intent.intent_type == "pause_campaign"
                if actual_platform == "tiktok":
                    tool_input["updates"] = {"campaign_group_status": 0 if paused else 1}
                elif actual_platform == "meta":
                    tool_input["updates"] = {"status": "PAUSED" if paused else "ACTIVE"}
                else:
                    tool_input["updates"] = {"status": "PAUSED" if paused else "ENABLED"}
            elif "updates" not in tool_input:
                pass

        # Normalize generic status wording into the provider field used by
        # update adapters.  The parser can safely understand "暂停/恢复" once,
        # while each Capability owns the final wire-level representation.
        updates = tool_input.get("updates")
        if isinstance(updates, dict) and "status" in updates:
            status = str(updates.get("status", "")).upper()
            if actual_platform == "tiktok":
                status_key = "ad_group_status" if "adgroup" in tool_def.name else "campaign_group_status"
                if status in {"ACTIVE", "ENABLED", "RUNNING"}:
                    updates[status_key] = 1
                    updates.pop("status", None)
                elif status in {"PAUSED", "DISABLED", "STOPPED"}:
                    updates[status_key] = 0
                    updates.pop("status", None)
            elif actual_platform == "google-ads" and status == "ACTIVE":
                updates["status"] = "ENABLED"
            elif actual_platform == "dv360" and status == "ENABLED":
                updates["status"] = "ACTIVE"
        
        # 检查必需参数是否齐全
        missing = []
        for req in tool_def.input_schema.required or []:
            if req not in tool_input:
                missing.append(req)

        # Conditional requirements are part of the same parameter contract as
        # flat ``required`` fields. Surface them as missing parameters so a
        # caller can immediately follow the field's lookup_tool metadata
        # instead of receiving a late, opaque validation error.
        for rule in tool_def.input_schema.conditional_rules or []:
            if not isinstance(rule, dict):
                continue
            conditions = rule.get("if", rule.get("when", {}))
            if not isinstance(conditions, dict) or any(
                tool_input.get(key) != expected
                for key, expected in conditions.items()
            ):
                continue
            for req in rule.get("required", rule.get("required_fields", [])) or []:
                if req not in tool_input and req not in missing:
                    missing.append(req)
        
        if missing:
            # 参数不全，标记为需要确认
            tool_input["_missing_params"] = missing
        if unknown_specific_params:
            tool_input["_unknown_params"] = unknown_specific_params

        return tool_input

    @staticmethod
    def _validate_platform_parameter_contract(
        intent: ParsedIntent, tool_plan: dict[str, list[Any]],
    ) -> list[str]:
        """Reject platform parameters that no planned tool can consume.

        ``platform_params`` is an aggregate payload for a multi-step create
        chain, so a field may belong to a later child tool.  Validate against
        the union of all planned tool schemas instead of rejecting those
        legitimate sibling fields at the first parent step.
        """
        errors: list[str] = []
        aliases = {
            "name", "campaign_name", "adset_name", "ad_set_name",
            "adgroup_name", "line_item_name", "account_id", "advertiser_id",
            "customer_id", "ad_account_id", "ad_set_id", "adset_id",
            "ad_group_id", "adgroup_id",
        }
        common = {
            "budget", "daily_budget", "objective", "campaign_type",
            "date_range", "date_preset", "creative_materials", "campaign_id",
            "campaign_ids", "line_item_id", "asset_group_id",
        }
        for platform, values in (intent.platform_params or {}).items():
            if platform.startswith("_") or not isinstance(values, dict):
                continue
            tools = tool_plan.get(platform, [])
            allowed = set(common) | aliases | {tool.name for tool in tools}
            for tool in tools:
                allowed.update(getattr(tool.input_schema, "properties", {}) or {})
            for key, value in values.items():
                if key.startswith("_") or key in allowed:
                    continue
                errors.append(f"{platform}.{key} 未被当前工具链声明")

            # Tool-scoped payloads are unambiguous and can be checked against
            # that exact schema, including its alias-compatible identifiers.
            for tool in tools:
                scoped = values.get(tool.name)
                if not isinstance(scoped, dict):
                    continue
                properties = set(getattr(tool.input_schema, "properties", {}) or {})
                scoped_allowed = properties | aliases
                for key in scoped:
                    if key not in scoped_allowed:
                        errors.append(f"{platform}.{tool.name}.{key} 未被工具 Schema 声明")
        return errors[:20]

    @staticmethod
    def _lookup_tools_for_fields(tool_def: Any, fields: list[str]) -> dict[str, str]:
        """Expose the lookup tool associated with missing dynamic fields."""
        properties = getattr(tool_def.input_schema, "properties", {}) or {}
        lookups: dict[str, str] = {}
        for field in fields or []:
            spec = properties.get(field, {})
            if not isinstance(spec, dict):
                continue
            lookup_tool = spec.get("lookup_tool")
            if not lookup_tool and isinstance(spec.get("lookup"), dict):
                lookup_tool = spec["lookup"].get("tool")
            if lookup_tool:
                lookups[field] = str(lookup_tool)
        return lookups

    def _resolve_platform_account(
        self,
        intent: ParsedIntent,
        platform: str,
        tools: list[Any],
        fallback_account: Optional[str],
    ) -> Optional[str]:
        """解析单个平台账户，优先使用平台/工具级参数，再回退到公共账户。"""
        params = intent.platform_params.get(platform, {}) or {}
        if not isinstance(params, dict):
            params = {}
        actual_platform = self.PLATFORM_NAME_MAP.get(platform, platform)
        preferred_key = self.PLATFORM_ACCOUNT_KEY.get(actual_platform)
        candidate_keys = [preferred_key, "account_id", "advertiser_id", "customer_id"]
        candidate_keys = [key for key in candidate_keys if key]

        sources = [params]
        for tool in tools:
            specific = params.get(tool.name)
            if isinstance(specific, dict):
                sources.append(specific)
        for source in sources:
            for key in candidate_keys:
                value = source.get(key)
                if value not in (None, ""):
                    return str(value)

        if fallback_account:
            return str(fallback_account)
        allowed = self.whitelist_validator.get_allowed_accounts(actual_platform)
        # Do not infer an account when the whitelist contains more than one
        # candidate.  The caller must provide the exact test account in that
        # case; a one-account fallback keeps the existing local UX intact.
        return str(allowed[0]) if len(allowed) == 1 else None
    
    def _generate_reply(
        self,
        intent: ParsedIntent,
        results: list[dict],
        needs_confirmation: bool,
    ) -> str:
        """根据执行结果生成用户友好的回复"""
        success_count = sum(1 for r in results if r.get("success"))
        fail_count = len(results) - success_count
        
        # 检查是否有需要确认的情况
        ask_params_results = [r for r in results if r.get("needs_confirmation") and r.get("confirmation_payload")]
        if ask_params_results:
            # 需要用户提供参数
            questions = []
            for r in ask_params_results:
                payload = r.get("confirmation_payload", {})
                if payload.get("type") == "ask_params":
                    questions.append(payload.get("question", "请提供必要参数"))
            if questions:
                return "\n\n".join(questions)
        
        if needs_confirmation:
            return "⚠️ 需要确认：部分操作需要您的确认才能继续。"

        if intent.intent_type in ("cross_channel_overview", "cross_channel_compare"):
            aggregate = CrossChannelAggregator().aggregate(results)
            title = "跨渠道 Campaign 对比" if intent.intent_type == "cross_channel_compare" else "跨渠道 Campaign 总览"
            reply = CrossChannelAggregator().format_markdown(aggregate, title)
            failures = [
                f"  - {item.get('platform', '?')} {item.get('tool', '')}: {item.get('error', 'failed')}"
                for item in results
                if not item.get("success")
            ]
            if failures:
                reply += "\n\n⚠️ 部分渠道未完成：\n" + "\n".join(failures)
            return reply

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
            # Read-only offline adapters may also annotate their fixture data
            # with ``simulated``.  Only Runtime-generated write plans carry a
            # create/update operation, so do not describe a list/report as a
            # simulated write.
            simulated_results = [
                r for r in results
                if isinstance(r.get("data"), dict)
                and r["data"].get("simulated")
                and r["data"].get("operation") in ("create", "update")
            ]
            if simulated_results and len(simulated_results) == len(results):
                operation = "更新" if (
                    intent.intent_type.startswith("update")
                    or intent.intent_type in (
                        "pause_campaign", "resume_campaign",
                        "cross_channel_batch_pause", "cross_channel_batch_resume",
                        "cross_channel_batch_update_budget",
                    )
                ) else "创建"
                return (
                    f"🧪 dry-run：已模拟{operation} {len(simulated_results)} 个广告资源，"
                    "未调用任何线上写 API。\n"
                    + "\n".join(
                        f"  - [{r.get('platform', '?')}] {r['tool']} → "
                        f"{next((v for k, v in r.get('data', {}).items() if k.endswith('_id')), 'planned')}"
                        for r in simulated_results
                    )
                )

            # 根据工具名判断操作类型
            is_list_op = any('list' in r.get('tool', '').lower() for r in results)
            is_get_op = any('get_' in r.get('tool', '').lower() or 'report' in r.get('tool', '').lower() for r in results)
            
            if is_list_op or is_get_op:
                # 查询类操作
                lines = []
                for r in results:
                    tool = r.get('tool', '')
                    platform = r.get('platform', '')
                    data = r.get('data', {})
                    
                    # 提取并格式化结果数据
                    if 'campaigns' in data:
                        campaigns = data['campaigns']
                        if campaigns:
                            lines.append(f"📊 [{platform}] 找到 {len(campaigns)} 个 Campaign:\n")
                            # 显示为表格格式
                            lines.append("| # | 名称 | 状态 | 预算 | 目标 |")
                            lines.append("|---|------|------|------|------|")
                            for i, c in enumerate(campaigns[:10], 1):  # 最多显示 10 个
                                name = str(c.get('campaign_name') or c.get('name') or 'N/A')[:30]
                                status = str(c.get('operation_status') or c.get('status') or 'N/A')
                                budget = c.get('budget') or c.get('daily_budget') or 0
                                objective = str(c.get('objective') or c.get('objective_type') or 'N/A')
                                lines.append(f"| {i} | {name} | {status} | ¥{budget} | {objective} |")
                            if len(campaigns) > 10:
                                lines.append(f"\n... 还有 {len(campaigns) - 10} 个 Campaign")
                        else:
                            lines.append(f"📊 [{platform}] 没有找到 Campaign")
                    elif 'accounts' in data:
                        accounts = data['accounts']
                        if accounts:
                            lines.append(f"📊 [{platform}] 找到 {len(accounts)} 个账户:\n")
                            for i, a in enumerate(accounts[:5], 1):
                                lines.append(f"  📌 Account #{i}:")
                                for k, v in a.items():
                                    if v is not None and v != '':
                                        lines.append(f"    • {k}: {v}")
                        else:
                            lines.append(f"📊 [{platform}] 没有找到账户")
                    elif 'metrics' in data:
                        metrics = data['metrics']
                        lines.append(f"📊 [{platform}] 报表数据:\n")
                        for k, v in metrics.items():
                            if isinstance(v, float):
                                lines.append(f"  • {k}: {v:.2f}")
                            else:
                                lines.append(f"  • {k}: {v}")
                    elif 'campaign' in data:
                        c = data['campaign']
                        if isinstance(c, dict):
                            name = c.get('name') or c.get('campaign_name') or c.get('id') or 'N/A'
                            status = c.get('status') or c.get('operation_status') or 'N/A'
                            objective = c.get('objective') or c.get('objective_type') or 'N/A'
                            budget = c.get('daily_budget') or c.get('budget') or c.get('budget_remaining') or 0
                            cam_id = c.get('id', '')
                            lines.append(f"📊 [{platform}] Campaign 详情:")
                            lines.append(f"**名称**: {name}")
                            lines.append(f"**ID**: {cam_id}")
                            lines.append(f"**状态**: {status}")
                            lines.append(f"**目标**: {objective}")
                            if budget:
                                lines.append(f"**日预算**: ¥{budget}")
                            # 显示关联的 adsets 和 ads
                            adsets = c.get('adsets', {})
                            if isinstance(adsets, dict) and adsets.get('data'):
                                lines.append(f"**广告组数**: {len(adsets['data'])}")
                            ads = c.get('ads', {})
                            if isinstance(ads, dict) and ads.get('data'):
                                lines.append(f"**广告数**: {len(ads['data'])}")
                        else:
                            lines.append(f"✅ [{platform}] {tool}")
                    elif 'report' in data:
                        report = data['report']
                        summary = data.get('summary', {})
                        if report:
                            lines.append(f"📊 [{platform}] 报表数据（共 {len(report)} 条记录）:")
                            lines.append("")
                            # 显示汇总
                            if summary:
                                lines.append(f"**汇总**: 展示 {summary.get('total_impressions', 0):,} | 点击 {summary.get('total_clicks', 0):,} | 花费 ¥{summary.get('total_spend', 0):.2f}")
                                lines.append("")
                            # 显示每条记录的详细信息
                            for i, r in enumerate(report[:5], 1):  # 最多显示5条
                                campaign = r.get('campaign', {})
                                lines.append(f"**Campaign #{i}**: {campaign.get('name', 'N/A')}")
                                lines.append(f"  • 状态: {campaign.get('status', 'N/A')}")
                                metrics = campaign.get('metrics', {})
                                if metrics:
                                    lines.append(f"  • 展示: {metrics.get('impressions', 0):,} | 点击: {metrics.get('clicks', 0):,} | CTR: {metrics.get('ctr', 0):.2%}")
                                    lines.append(f"  • 花费: ¥{metrics.get('cost_micros', 0) / 1_000_000:.2f} | 转化: {metrics.get('conversions', 0):,}")
                                lines.append("")
                            if len(report) > 5:
                                lines.append(f"... 还有 {len(report) - 5} 条记录")
                        else:
                            lines.append(f"📊 [{platform}] 没有找到报表数据，请确认账户和日期范围")
                    else:
                        lines.append(f"✅ [{platform}] {tool}")
                
                return "\n".join(lines) if lines else f"✅ 成功执行 {success_count} 个查询操作"
            else:
                # 创建类操作
                return (
                    f"✅ 成功创建 {success_count} 个广告操作：\n"
                    + "\n".join(f"  - [{r.get('platform', '?')}] {r['tool']}"
                              for r in results)
                )

    @staticmethod
    def _format_cross_channel_insights(payload: dict[str, Any]) -> str:
        """Render read-only cross-channel recommendations for the reply."""
        lines = ["\n\n🔎 跨渠道表现洞察："]
        insights = payload.get("insights") if isinstance(payload, dict) else []
        if not insights:
            lines.append("暂无可用的渠道指标。")
        else:
            for item in insights:
                if not isinstance(item, dict):
                    continue
                platform = item.get("platform", "unknown")
                status = item.get("data_status", "unknown")
                currency = item.get("currency")
                suffix = f" / {currency}" if currency else ""
                lines.append(f"\n• {platform}（数据：{status}{suffix}）")
                for recommendation in item.get("recommendations", []) or []:
                    lines.append(f"  - {recommendation}")
        comparability = payload.get("comparability", {}) if isinstance(payload, dict) else {}
        if isinstance(comparability, dict) and comparability.get("status") == "partial":
            reason = comparability.get("reason") or "指标不完整"
            lines.append(f"\n⚠️ 以上结论部分可比：{reason}。")
        lines.append("以上仅为只读分析建议，不会自动修改任何平台 Campaign。")
        return "\n".join(lines)

    @staticmethod
    def _format_cross_channel_budget_plan(payload: dict[str, Any]) -> str:
        """Render a deterministic budget proposal without implying execution."""
        lines = ["\n\n💰 跨渠道预算建议："]
        if not isinstance(payload, dict) or payload.get("status") == "blocked":
            error = payload.get("error", "输入或指标不足") if isinstance(payload, dict) else "输入或指标不足"
            lines.append(f"无法生成预算建议：{error}")
            return "\n".join(lines)

        lines.extend([
            "| 平台 | 建议预算 | 评分依据 | 数据状态 |",
            "|---|---:|---|---|",
        ])
        for item in payload.get("recommendations", []) or []:
            if not isinstance(item, dict):
                continue
            budget = item.get("recommended_budget")
            budget_text = "N/A" if budget is None else f"{float(budget):.2f}"
            currency = item.get("currency")
            if currency:
                budget_text += f" {currency}"
            lines.append(
                f"| {item.get('platform', 'unknown')} | {budget_text} | "
                f"{item.get('evidence', '无足够指标')} | {item.get('data_status', 'unknown')} |"
            )
        unallocated = payload.get("unallocated_budget", 0)
        if unallocated:
            lines.append(f"\n未分配预算：{float(unallocated):.2f}")
        lines.append(payload.get("disclaimer", "这是只读预算建议；不会自动修改任何平台 Campaign。"))
        return "\n".join(lines)
    
    def _generate_chat_reply(self, user_input: str) -> str:
        """生成闲聊回复"""
        text = user_input.lower()
        
        # 问候语
        if any(kw in text for kw in ["你好", "hello", "hi", "在吗"]):
            return (
                "👋 你好！我是 ad-agent，您的广告投放专家助手。\n\n"
                "我可以帮您：\n"
                "• 创建 Meta/TikTok/Google Ads/DV360 广告系列\n"
                "• 查询投放报表和性能数据\n"
                "• 优化跨渠道预算分配\n\n"
                "请告诉我您的需求，例如：\n"
                '- "帮我创建一个 Meta 广告系列"\n'
                '- "列出 TikTok Campaign 列表"'
            )
        
        # 帮助请求
        if any(kw in text for kw in ["帮助", "help", "你能做什么", "怎么使用"]):
            return (
                "🤖 我是广告投放专家助手，支持以下功能：\n\n"
                "📊 **查询功能**\n"
                "• 列出各平台 Campaign 列表\n"
                "• 查看投放报表和性能数据\n\n"
                "✏️ **创建功能**\n"
                "• Meta: 创建 Campaign/Ad Set/Ad\n"
                "• TikTok: 创建 Campaign/Ad Group/Ad\n"
                "• Google Ads: 创建 Campaign（搜索/购物/PMax）\n"
                "• DV360: 创建 Campaign/IO/Line Item\n\n"
                "⚡ **优化功能**\n"
                "• 跨渠道预算分配建议\n"
                "• 出价策略优化\n\n"
                "💡 **提示**：请明确指定平台和操作，例如：\n"
                '- "帮我创建一个 Meta 广告系列"\n'
                '- "列出 TikTok Campaign 列表"'
            )
        
        # 默认回复
        return "👋 你好！我是 ad-agent，您的广告投放专家助手。请告诉我您的需求。"

# ─── Session 管理 ──────────────────────────────────────────
    
    def _ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
    ) -> "SessionContext":
        if session_id not in self._sessions:
            persisted = self._session_manager.get_session(session_id) if self._session_manager else None
            if persisted:
                persisted_user = persisted.get("user_id")
                persisted_account = persisted.get("account_id")
                if persisted_user and persisted_user != user_id:
                    raise PermissionError("session belongs to a different user")
                if account_id and persisted_account and str(account_id) != str(persisted_account):
                    raise PermissionError("session belongs to a different account")
            persisted_metadata = {}
            if persisted and persisted.get("metadata"):
                try:
                    persisted_metadata = json.loads(persisted["metadata"])
                except (TypeError, ValueError):
                    persisted_metadata = {}
            ctx = ToolContext(
                session_id=session_id,
                user_id=user_id,
                account_id=account_id or (persisted or {}).get("account_id"),
                credentials=self._freeze_credentials(copy.deepcopy(credentials or {})),
            )
            session = SessionContext(session_id, ctx)
            session.messages = persisted_metadata.get("messages", [])[-20:]
            ctx.messages = list(session.messages)
            if self._session_manager and persisted:
                for record in reversed(self._session_manager.get_session_history(session_id, limit=20)):
                    if record.output_data:
                        session.save_result(
                            record.tool_name,
                            ToolResult.ok(record.output_data),
                            platform=record.platform,
                        )
                # Restore resource IDs into the actual ToolContext before the
                # first tool of the new turn, not only after a new tool runs.
                ctx.protected_state.update(session.protected_state)
            self._sessions[session_id] = session
            
            # Create only genuinely new sessions. INSERT OR REPLACE here would
            # otherwise erase a persisted account_id when the caller omits it
            # during session restoration.
            if self._session_manager and not persisted:
                self._session_manager.create_session(
                    session_id,
                    user_id,
                    account_id,
                    {
                        "execution_mode": self.execution_mode,
                        "read_only_mode": self._read_only_mode,
                    },
                )
        session = self._sessions[session_id]
        if session.ctx.user_id != user_id:
            raise PermissionError("session belongs to a different user")
        if account_id and session.ctx.account_id and str(account_id) != str(session.ctx.account_id):
            raise PermissionError("session belongs to a different account")
        if credentials:
            session.ctx.credentials = self._freeze_credentials(copy.deepcopy(credentials))
        return session
    
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

    def get_workflow(self, workflow_id: str, user_id: Optional[str] = None) -> Optional[dict]:
        """Read a durable workflow while enforcing its owning user boundary."""
        if not self._session_manager:
            return None
        workflow = self._session_manager.get_workflow(workflow_id)
        if not workflow:
            return None
        if user_id is not None:
            session = self._session_manager.get_session(workflow.get("session_id")) or {}
            if str(session.get("user_id")) != str(user_id):
                raise PermissionError("workflow belongs to a different user")
        return workflow

    def cancel_workflow(self, workflow_id: str, user_id: str) -> bool:
        """Cancel a non-terminal workflow without contacting a provider."""
        workflow = self.get_workflow(workflow_id, user_id=user_id)
        if not workflow:
            return False
        return self._session_manager.update_workflow(
            workflow_id, "cancelled", {"cancelled_by": str(user_id)}
        )


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
        self.ctx.messages = list(self.messages)
    
    def save_result(
        self, tool_name: str, result: ToolResult, platform: str = None
    ) -> None:
        """保存工具执行结果，供后续 Tool 引用"""
        self.tool_results[tool_name] = result
        # 如果结果中有 campaign_id 等关键字段，自动保存到 protected_state
        for key in [
            "campaign_id", "ad_set_id", "adset_id", "ad_group_id", "adgroup_id",
            "creative_id", "io_id", "line_item_id", "ad_id",
        ]:
            if key in result.data:
                self.protected_state[key] = result.data[key]
                if platform:
                    self.protected_state[f"{platform}:{key}"] = result.data[key]
    
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
