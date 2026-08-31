"""
runtime/runtime.py - Agent Runtime 主循环

借鉴 DAP Agent internal/core/engine/runtime.go
核心职责：
1. 管理 Session 生命周期
2. 处理用户输入 → LLM → ToolCall → 执行 → 返回结果
3. 多平台 Skill 工具的统一调度
4. 跨 Skill 上下文传递
"""

from __future__ import annotations

import uuid
import time
import json
import os
import copy
import re
import hashlib
import hmac
import threading
import logging
import importlib.util
import inspect
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import yaml

from ..core.interfaces import (
    ToolContext, ToolResult, ChatMessage, CapabilityModule,
    CapabilityRuntime, ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent, ToolHandler, ToolEffect, ExecutionMode, ProviderReconciler,
    ReconciliationContext, ReconciliationObservation, ResourceResult,
    AdFormatCoverage,
)
from ..core.tool_registry import GuardedToolRegistry, SimpleToolRegistry, validate_tool_input
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from ..core.features import RuntimeFeature
from ..core.response import ResponseRenderer
from ..features.factory import discover_features, feature_for_intent
from ..features.factory import discover_response_renderer
from ..core.tool_selector import DynamicToolSelector
from ..core.policy import RuntimePolicy, validate_policies
from ..core.knowledge import KnowledgeProvider, LocalMarkdownKnowledgeProvider
from ..core.parameter_catalog import ParameterCatalogRegistry
from ..core.parameter_selection import (
    ParameterSelectionSigner,
)
from ..core.auth import RequestPrincipal, normalize_account_id, normalize_platform
from ..core.security import (
    PROTECTED_INPUT_FIELDS,
    normalize_field_name,
    protected_field_paths,
    protected_update_paths,
)
from .skill import BaseSkill, Skill, SkillContract, SkillLoader
from .input_builder import ToolInputBuilder
from .account_context import AccountResolver
from ..persistence.session_manager import SessionManager
from ..persistence.interfaces import PersistenceBackend
from ..persistence.models import ToolCallRecord
from .reconciliation import ToolReadbackReconciler

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
                    allowed_accounts = config.get('allowed_accounts', {}) if isinstance(config, dict) else {}
                    self.allowed_accounts = (
                        allowed_accounts if isinstance(allowed_accounts, dict) else {}
                    )
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
        canonical_platform = normalize_platform(platform)
        allowed = self._accounts_for_platform(canonical_platform)
        
        # 空白名单必须 fail closed：凭证中出现的账户 ID 不能自动成为
        # 可操作账户。测试/本地开发应显式提供受控白名单。
        if not allowed:
            return False, f"{canonical_platform} 未配置受控账户白名单"
        
        # 检查账户是否匹配
        normalized_account = normalize_account_id(account_id)
        is_allowed = bool(normalized_account) and normalized_account in {
            normalize_account_id(acc) for acc in allowed
        }
        
        if not is_allowed:
            return False, (
                f"账户 {account_id} 不在 {canonical_platform} 白名单中。"
                f"允许操作的账户: {', '.join(str(acc) for acc in allowed)}"
            )
        
        return True, ""
    
    def get_allowed_accounts(self, platform: str) -> list[str]:
        """获取平台允许操作的账户列表"""
        return list(self._accounts_for_platform(normalize_platform(platform)))

    def _accounts_for_platform(self, platform: str) -> list[Any]:
        """Return only well-formed configured accounts for a canonical platform.

        Configuration is untrusted input at process startup.  A malformed
        platform entry (for example a scalar string) must never be iterated as
        account IDs, and an alias must not create a second authorization map.
        Invalid entries fail closed while valid entries for other platforms
        remain usable.
        """
        configured = self.allowed_accounts
        if not platform or not isinstance(configured, dict):
            return []
        values = []
        for raw_platform, raw_accounts in configured.items():
            if normalize_platform(raw_platform) != platform:
                continue
            if isinstance(raw_accounts, (str, bytes)) or not isinstance(
                raw_accounts, (list, tuple, set, frozenset)
            ):
                return []
            for account in raw_accounts:
                if not isinstance(account, (str, int)) or isinstance(account, bool):
                    return []
                normalized = normalize_account_id(account)
                if normalized:
                    values.append(account)
        return values


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
    │  └─ WriteGuard（写入保护）                 │
    └─────────────────────────────────────────┘
    
    借鉴 DAP Agent internal/core/engine/runtime.go 的核心设计：
    - Core 只认接口，不 import 业务
    - 业务通过 CapabilityModule 注入
    - Tool 执行有统一的生命周期（权限→审批→幂等→执行→审计）
    """
    
    # These fields are configuration/credential material, not advertising
    # resource fields.  They must never be accepted inside a tool payload or
    # an ``updates`` object.  Request-scoped ``credentials=...`` remains a
    # separate, in-memory transport input and is intentionally not scanned by
    # this validator.
    PROTECTED_INPUT_FIELDS = PROTECTED_INPUT_FIELDS

    def __init__(
        self,
        registry: ToolRegistry = None,
        intent_parser: IntentParser = None,
        intent_router: IntentRouter = None,
        write_guard: WriteGuard = None,
        skill_roots: list[str] = None,
        llm_client=None,  # 可选：自定义 LLM 客户端
        # A production Agent is model-backed by definition.  Tests and
        # explicitly offline tooling may opt into the legacy rule parser with
        # ``require_llm=False``; the default must never silently degrade.
        require_llm: bool = True,
        persistence_store: PersistenceBackend = None,
        whitelist_validator: AccountWhitelistValidator = None,
        read_only_mode: bool = False,
        execution_mode: str = ExecutionMode.DRY_RUN.value,
        enforce_account_scope: bool = True,
        live_approved_tools: Optional[set[str]] = None,
        allow_live_writes: bool = False,
        policies: Optional[Iterable[RuntimePolicy]] = None,
        tool_selector: Optional[DynamicToolSelector] = None,
        knowledge_provider: Optional[KnowledgeProvider] = None,
        offline_mode: bool = False,
        granted_permissions: Optional[set[str]] = None,
        max_tool_calls: int = 32,
        turn_timeout_seconds: float = 120.0,
        max_user_input_chars: int = 12_000,
        max_platform_params_bytes: int = 256_000,
        provider_reconcilers: Optional[Mapping[str, ProviderReconciler]] = None,
        features: Optional[Iterable[RuntimeFeature]] = None,
        response_renderer: Optional[ResponseRenderer] = None,
        workflow_stale_after_seconds: float = 300.0,
        selection_token_secret: Optional[str] = None,
        parameter_selection_ttl_seconds: int = 600,
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
        self.require_llm = bool(require_llm)
        self.intent_parser = intent_parser or LLMIntentParser(
            llm_client, allow_rule_fallback=not self.require_llm
        )
        if self.require_llm and isinstance(self.intent_parser, LLMIntentParser):
            # An explicitly supplied LLMIntentParser must obey the Runtime's
            # production boundary too; it cannot silently fall back to rules.
            self.intent_parser.allow_rule_fallback = False
        self.intent_router = intent_router or SimpleIntentRouter()
        self.write_guard = write_guard
        self.skill_loader = SkillLoader(skill_roots)
        self.skill_loader.load_all()
        self._llm = llm_client
        # A caller may inject an already-configured LLMIntentParser instead
        # of passing the model separately.  Treat that parser-owned model as
        # the same model-backed Agent dependency; otherwise the strict
        # startup gate would reject a valid LLM configuration while checking
        # only the Runtime field.
        if self._llm is None and isinstance(self.intent_parser, LLMIntentParser):
            self._llm = getattr(self.intent_parser, "_llm", None)
        self._sessions: dict[str, "SessionContext"] = {}
        self._session_locks: dict[str, threading.RLock] = {}
        self._session_locks_guard = threading.RLock()
        self._background_tasks: list[dict] = []
        # Optional domain workflows are discovered by package convention.
        # Runtime only knows the generic feature seam; it does not import a
        # domain workflow or maintain an intent-to-feature table.
        self.features: list[RuntimeFeature] = list(
            discover_features() if features is None else features
        )
        self.response_renderer: ResponseRenderer = (
            response_renderer or discover_response_renderer()
        )
        if self.response_renderer is None:
            raise RuntimeError("no response renderer is registered")
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
        self._skill_format_ids: dict[str, set[str]] = {}
        # User-managed Skills are tenant-owned context packages.  They are
        # deliberately tracked separately from executable provider Skills so
        # an uploaded directory cannot become a Tool merely by containing a
        # contract or a Python file.  The Runtime itself is process-global,
        # therefore this index must be tenant-scoped.
        self._managed_context_skills: dict[str, dict[str, Skill]] = {}
        self._managed_skill_lock = threading.RLock()
        self._skill_factories: dict[str, callable] = {}  # platform -> Capability factory
        self._credentials: dict = {}  # API 凭证配置
        self.knowledge_provider = knowledge_provider or LocalMarkdownKnowledgeProvider(
            Path(__file__).resolve().parent.parent / "knowledge_base"
        )
        self.tool_selector = tool_selector or DynamicToolSelector(
            skill_loader=self.skill_loader,
            knowledge_provider=self.knowledge_provider,
        )
        self.parameter_catalogs = ParameterCatalogRegistry()
        # This is a metadata index, not a second executable routing table.
        # Each provider Capability owns and publishes its own entries.
        self.ad_format_catalogs: dict[str, list[dict[str, Any]]] = {}
        # Provider-owned compatibility metadata is a diagnostic/release
        # index, never a routing table.  Keeping it on Runtime lets the
        # contract snapshot detect an API version change even when Tool names
        # and schemas remain unchanged.
        self.provider_version_contracts: dict[str, dict[str, Any]] = {}
        self.provider_api_surfaces: dict[str, list[dict[str, Any]]] = {}
        selection_secret = selection_token_secret or os.environ.get(
            "AD_AGENT_SELECTION_TOKEN_KEY"
        )
        self._parameter_selection_signer = ParameterSelectionSigner(
            selection_secret, parameter_selection_ttl_seconds
        )
        self.input_builder = ToolInputBuilder(self)
        self.account_resolver = AccountResolver(self)
        self.policies: list[RuntimePolicy] = list(policies or [])
        if self.policies and hasattr(self.tool_selector, "set_policies"):
            self.tool_selector.set_policies(self.policies)

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
        # This is a second, deployment-level fuse.  A configured execution
        # mode or tool allowlist must never be sufficient to turn on provider
        # mutations.  The embedding/application must opt in explicitly after
        # the operator has selected and verified the test accounts.
        self.allow_live_writes = bool(allow_live_writes)
        # 读请求也默认受受控账户边界约束，避免带凭证的服务被用来查询
        # 任意账户。需要本地离线探索时应显式提供测试 validator。
        self.enforce_account_scope = enforce_account_scope
        # Offline fixtures are useful for local development, but a normal
        # Runtime must not present provider-free mock rows as real query
        # results.  Write planning remains available without a client because
        # dry-run writes are intercepted before handlers execute.
        self.offline_mode = bool(offline_mode)
        # Permissions are injected by the trusted embedding/auth layer, never
        # inferred from user text or provider credentials. Missing permissions
        # fail closed for both read and write tools.
        # A direct/local embedding gets the safe baseline needed to inspect
        # data and build dry-run plans.  Passing an explicit empty set is
        # different: it intentionally denies every permissioned tool.  The
        # HTTP server always passes its configured principal permissions.
        default_permissions = {"ads.read", "ads.plan"}
        self._granted_permissions = frozenset(
            str(permission)
            for permission in (
                default_permissions if granted_permissions is None else granted_permissions
            )
        )
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if turn_timeout_seconds <= 0:
            raise ValueError("turn_timeout_seconds must be positive")
        self.max_tool_calls = int(max_tool_calls)
        self.turn_timeout_seconds = float(turn_timeout_seconds)
        self.max_user_input_chars = int(max_user_input_chars)
        self.max_platform_params_bytes = int(max_platform_params_bytes)
        if workflow_stale_after_seconds <= 0:
            raise ValueError("workflow_stale_after_seconds must be positive")
        self.workflow_stale_after_seconds = float(workflow_stale_after_seconds)
        self._workflow_lease_owner = (
            f"runtime:{os.getpid()}:{id(self)}"
        )
        # Reconciliation is provider-owned. Built-in adapters use only
        # registered read tools; custom providers can replace/extend them
        # without adding provider branches to the Runtime.
        # Custom provider reconcilers are optional. The default reconciler
        # discovers a matching read Tool from registered metadata at use time.
        self._provider_reconcilers: dict[str, ProviderReconciler] = {}
        for platform, reconciler in (provider_reconcilers or {}).items():
            if not isinstance(reconciler, ProviderReconciler):
                raise TypeError("provider reconciler must implement ProviderReconciler")
            canonical = self._canonical_platform(platform)
            self._provider_reconcilers[canonical] = reconciler
        
        # 账户白名单验证器
        self.whitelist_validator = whitelist_validator or AccountWhitelistValidator()
        
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

    def set_policies(self, policies: Optional[Iterable[RuntimePolicy]]) -> None:
        """Replace Skill-owned policies without interpreting their vocabulary."""
        self.policies = list(policies or [])
        setter = getattr(self.tool_selector, "set_policies", None)
        if callable(setter):
            setter(self.policies)

    def _feature_for_intent(self, intent: Any) -> Optional[RuntimeFeature]:
        """Resolve an optional domain feature through its generic contract."""
        return feature_for_intent(self.features, intent)

    def _refresh_parser_catalog(self) -> None:
        """Synchronize parser discovery data with the active Tool registry."""
        refresh = getattr(self.intent_parser, "refresh_tool_catalog", None)
        definitions = self.registry.list_all()
        if callable(refresh):
            refresh(definitions)
        elif hasattr(self.intent_parser, "register_tool_definitions"):
            self.intent_parser.register_tool_definitions(definitions)

        # Skill aliases are context metadata, but they must follow the same
        # lifecycle as their active Skill.  Provider identity itself remains
        # discovered from Tool metadata; aliases never create Tools.
        for skill in list(self._skill_objects.values()):
            if hasattr(self.intent_parser, "register_platform_aliases"):
                self.intent_parser.register_platform_aliases(
                    getattr(skill, "platform", ""),
                    getattr(skill, "platform_aliases", []) or [],
                )

    @staticmethod
    def _canonical_platform(platform: str) -> str:
        """Normalize aliases without keeping a Runtime platform registry."""
        from ..capabilities.factory import normalize_platform

        return normalize_platform(platform)

    @property
    def persistence_store(self):
        """Expose the persistence abstraction to management services."""
        return self._session_manager.store if self._session_manager else None

    def load_managed_skill(self, skill_dir: str, tenant_id: str = "default") -> bool:
        """Load a published standard Skill directory as advisory context.

        This path intentionally does not call ``register_skill`` and never
        imports ``tools.py``.  Provider Tools must continue to come from
        built-in/verified Capabilities; a managed Skill can guide the Agent
        but cannot create a new side-effect path.
        """
        from pathlib import Path

        tenant_id = str(tenant_id or "default")
        directory = Path(skill_dir).resolve()
        if not directory.is_dir() or not (directory / "SKILL.md").is_file():
            raise ValueError("managed Skill directory must contain SKILL.md")
        contract = SkillContract(str(directory)).load()
        if contract.context_only or not contract.name:
            raise ValueError("managed Skill must be a standalone Skill with a name")
        # Build the complete advisory object before touching any Runtime
        # indexes. A malformed package therefore cannot remove the old
        # published context.
        skill = BaseSkill(contract)
        setattr(skill, "skill_dir", str(directory))

        with self._managed_skill_lock:
            if (
                contract.name in self._skill_objects
            ):
                raise ValueError(
                    "managed Skill name conflicts with executable Skill: "
                    f"{contract.name}"
                )

            # Replace only a previous managed version for this tenant. A
            # built-in Skill with the same name is protected by the conflict
            # check above. Managed Skills never enter SkillLoader or the
            # global parser alias index; both are process-wide and would leak
            # tenant-owned context.
            self._managed_context_skills.setdefault(tenant_id, {})[contract.name] = skill
            if hasattr(self.tool_selector, "register_context_skill"):
                self.tool_selector.register_context_skill(skill, tenant_id=tenant_id)
            self._refresh_parser_catalog()
        return True

    def unload_managed_skill(self, skill_name: str, tenant_id: str = "default") -> bool:
        """Remove advisory context without touching executable provider Tools."""
        key = str(skill_name or "")
        tenant_id = str(tenant_id or "default")
        with self._managed_skill_lock:
            tenant_skills = self._managed_context_skills.get(tenant_id)
            skill = tenant_skills.pop(key, None) if tenant_skills else None
            if skill is None:
                return False
            if hasattr(self.tool_selector, "unregister_context_skill"):
                self.tool_selector.unregister_context_skill(key, tenant_id=tenant_id)
            if not tenant_skills:
                self._managed_context_skills.pop(tenant_id, None)
            self._refresh_parser_catalog()
            return True

    def get_managed_skills(self, tenant_id: Optional[str] = None) -> dict[str, Skill]:
        """Return tenant-scoped managed Skills for diagnostics/UI.

        The no-argument form is retained for single-tenant callers. Once the
        Runtime contains multiple non-default tenants it returns an empty
        mapping instead of guessing and exposing another tenant's context.
        """
        with self._managed_skill_lock:
            if tenant_id is not None:
                return dict(self._managed_context_skills.get(str(tenant_id or "default"), {}))
            if len(self._managed_context_skills) == 1:
                return dict(next(iter(self._managed_context_skills.values())))
            if "default" in self._managed_context_skills:
                return dict(self._managed_context_skills["default"])
            return {}

    def _build_skill_context(
        self,
        user_input: str,
        available_tools: list,
        intent_type: Optional[str],
        tenant_id: str,
    ) -> dict:
        """Call selector extensions without breaking older injected selectors."""
        builder = getattr(self.tool_selector, "build_context_for_input", None)
        if not callable(builder):
            return {}
        try:
            parameters = inspect.signature(builder).parameters.values()
        except (TypeError, ValueError):
            parameters = ()
        supports_keyword = any(
            parameter.name == "tenant_id" or parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        supports_extra_positional = any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL
            for parameter in parameters
        )
        if supports_keyword:
            return builder(
                user_input, available_tools, intent_type, tenant_id=tenant_id
            )
        if supports_extra_positional:
            return builder(user_input, available_tools, intent_type, tenant_id)
        return builder(user_input, available_tools, intent_type)

    def _build_prior_tool_results_context(
        self, session: "SessionContext", max_results: int = 8, max_chars: int = 4000
    ) -> str:
        """Build a bounded, redacted context view of prior Tool results.

        Tool results are durable execution evidence, not conversation prose.
        Keeping this bridge explicit lets a later LLM turn understand IDs,
        statuses and lookup output without exposing raw result objects as a
        new execution interface or allowing the model to bypass Runtime gates.
        """
        rows: list[str] = []
        for tool_name, result in list(session.tool_results.items())[-max_results:]:
            if not isinstance(result, ToolResult):
                continue
            safe = self._redact_for_persistence(result.to_dict())
            try:
                encoded = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
            except (TypeError, ValueError):
                encoded = json.dumps(
                    {"success": result.success, "error": str(result.error or "")},
                    ensure_ascii=False,
                )
            rows.append(f"[{tool_name}] {encoded[:1200]}")
        return "\n".join(rows)[:max_chars]

    def _validate_policies(self, intent: ParsedIntent) -> list[str]:
        """Run Skill-owned policies through the generic policy contract."""
        return validate_policies(self.policies, intent)

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
            if not isinstance(platform_params, dict):
                return "platform_params 必须是对象"
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

    def _check_tool_permissions(
        self,
        tool_def: Any,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> Optional[str]:
        required = {
            str(permission) for permission in (getattr(tool_def, "required_permissions", []) or [])
        }
        # Planning and live execution are distinct grants.  A write tool may
        # be used to produce a dry-run plan with ads.plan, but executing it
        # against a provider additionally requires ads.write.
        if tool_def.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value:
            required.add("ads.write")
        granted = self._granted_permissions if granted_permissions is None else frozenset(granted_permissions)
        missing = sorted(required - granted)
        if missing:
            return "缺少工具所需权限：" + ", ".join(missing)
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

    @staticmethod
    def _is_uncertain_provider_failure(tool_def: Any, result: ToolResult) -> bool:
        """Identify write failures where the provider may have committed.

        Handlers normalize provider exceptions into ``ToolResult.error``.  A
        transport-aware Result field is not required from every custom Skill,
        so the Runtime also recognizes the stable error vocabulary emitted by
        BasePlatformClient.  These outcomes must remain recoverable rather
        than releasing the idempotency reservation for an unsafe blind retry.
        """
        if not tool_def.is_write_tool or not result or result.success:
            return False
        data = result.data if isinstance(result.data, dict) else {}
        if str(data.get("execution_status") or "").lower() in {
            "unknown", "timed_out", "timeout", "transport_unknown",
        }:
            return True
        message = str(result.error or "").lower()
        return any(marker in message for marker in (
            "timeout", "timed out", "deadline", "connection error",
            "rate limit", "rate limited", "server error", "http 5",
            "temporarily unavailable", "temporary error",
        ))
    
    def inject_llm(self, llm_client) -> None:
        """注入 LLM 客户端"""
        self._llm = llm_client
        if isinstance(self.intent_parser, LLMIntentParser):
            self.intent_parser.inject_llm(llm_client)

    def assert_llm_ready(self) -> None:
        """Fail fast when a production Runtime has no model-backed parser."""
        if (
            self.require_llm
            and isinstance(self.intent_parser, LLMIntentParser)
            and self._llm is None
        ):
            raise RuntimeError(
                "LLM client is required; configure the model before starting the Agent"
            )

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
        """Register a Capability atomically from the Runtime's perspective.

        Capability ``configure`` implementations register Tools through a
        callback, so a failure after the first Tool would otherwise leave a
        half-loaded provider in the live Registry.  Keep the rollback here,
        at the boundary that owns the derived indexes, rather than requiring
        every provider package to implement its own transaction protocol.
        """
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
        before_formats = copy.deepcopy(self.ad_format_catalogs)
        before_provider_versions = copy.deepcopy(self.provider_version_contracts)
        before_provider_surfaces = copy.deepcopy(self.provider_api_surfaces)
        try:
            return self._register_capability_unchecked(module)
        except Exception:
            current_tool_names = {
                definition.name for definition in self.registry.list_all()
            }
            added_tool_names = current_tool_names - before_tool_names
            for name in added_tool_names:
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(list(added_tool_names))

            # Normally ownership indexes are written only after all metadata
            # validation succeeds.  Remove them defensively as well so a
            # future failure in the final parser refresh cannot leave an
            # unloadable Skill marker behind.
            for skill_key, tool_names in list(self._skill_tool_names.items()):
                if not (set(tool_names) & added_tool_names):
                    continue
                platform = self._skill_platforms.pop(skill_key, None)
                self._skill_tool_names.pop(skill_key, None)
                self._skill_objects.pop(skill_key, None)
                self._skill_format_ids.pop(skill_key, None)
                if platform:
                    canonical = self._canonical_platform(platform)
                    keys = [
                        key for key in self._skill_keys_by_platform.get(canonical, [])
                        if key != skill_key
                    ]
                    if keys:
                        self._skill_keys_by_platform[canonical] = keys
                    else:
                        self._skill_keys_by_platform.pop(canonical, None)
                        self._loaded_skills.pop(canonical, None)
            self.ad_format_catalogs = before_formats
            self.provider_version_contracts = before_provider_versions
            self.provider_api_surfaces = before_provider_surfaces
            try:
                self._refresh_parser_catalog()
            except Exception:
                logger.exception("Capability rollback could not refresh parser catalog")
            raise

    def _register_capability_unchecked(
        self, module: CapabilityModule
    ) -> CapabilityRuntime:
        """
        注册一个 CapabilityModule。
        
        对应 DAP Agent 的 CapabilityModule.Configure() 模式：
        业务模块不直接操作 Runtime，而是通过接口注入能力。
        """
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
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
                tool_name=definition.name,
            )
        self.parameter_catalogs.register_many(
            getattr(runtime, "parameter_catalogs", []) or []
        )
        self._register_ad_format_catalog(
            getattr(module, "platform_name", "") or "",
            getattr(runtime, "ad_format_catalogs", []) or [],
        )
        provider_contract_getter = getattr(module, "get_provider_version_contract", None)
        if callable(provider_contract_getter):
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.provider_version_contracts[platform] = copy.deepcopy(
                    provider_contract_getter()
                )
        provider_surface_getter = getattr(module, "get_api_surface", None)
        if callable(provider_surface_getter):
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.provider_api_surfaces[platform] = copy.deepcopy(
                    provider_surface_getter()
                )
        self._validate_parameter_lookup_contract()
        # Capability.configure() registers platform tools before returning.
        # Apply the read-only boundary immediately so callers cannot forget a
        # second, manually-invoked enable_read_only_mode() call.
        if self._read_only_mode:
            self._filter_write_tools()

        # Keep the Parser's language catalog derived from the actual Registry
        # rather than from a central intent table.  Custom parsers may ignore
        # this optional extension seam.
        if hasattr(self.intent_parser, "register_tool_definitions"):
            self.intent_parser.register_tool_definitions(self.registry.list_all())

        # Register executable tools supplied by the Capability.  Tool metadata
        # is the routing contract; no workflow file is consulted here.
        capability_platform = getattr(module, "platform_name", None)
        # A Capability registration already activated the platform's tools.
        # Keep the declarative Skill as the platform lifecycle marker so the
        # next turn does not try to register the same tools again.
        if capability_platform:
            canonical_platform = self._canonical_platform(capability_platform)
            skill_candidates = self.skill_loader.get_by_platform(canonical_platform)
            if skill_candidates:
                primary_skill = skill_candidates[0]
                self._loaded_skills.setdefault(canonical_platform, primary_skill)
                skill_key = str(getattr(primary_skill, "name", "") or canonical_platform)
            else:
                primary_skill = None
                skill_key = f"{canonical_platform}:capability:{id(module)}"
            registered_names = sorted(
                definition.name
                for definition in self.registry.list_all()
                if definition.name not in before_tool_names
            )
            if registered_names:
                self._skill_tool_names[skill_key] = registered_names
                self._skill_platforms[skill_key] = canonical_platform
                if primary_skill is not None:
                    self._skill_objects[skill_key] = primary_skill
                self._skill_keys_by_platform.setdefault(canonical_platform, []).append(
                    skill_key
                )
                self._skill_format_ids[skill_key] = {
                    str(item.get("format_id"))
                    for item in (getattr(runtime, "ad_format_catalogs", []) or [])
                    if isinstance(item, dict) and item.get("format_id")
                }

        # Rebuild derived discovery state after ownership has been recorded.
        # This is the same lifecycle boundary used by unload_skill().
        self._refresh_parser_catalog()
        
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

    def _register_ad_format_catalog(
        self, platform: str, catalogs: list[dict[str, Any]]
    ) -> None:
        """Validate and index a Capability's format metadata.

        The catalog is intentionally declarative.  It cannot register a
        handler, expand permissions, or enable live writes.  Duplicate IDs
        are rejected so two provider packages cannot silently disagree about
        the same format contract.
        """
        if not catalogs:
            return
        canonical = self._canonical_platform(platform)
        allowed = {item.value for item in AdFormatCoverage}
        existing = {
            str(item.get("format_id")): item
            for item in self.ad_format_catalogs.get(canonical, [])
        }
        normalized: list[dict[str, Any]] = list(
            self.ad_format_catalogs.get(canonical, [])
        )
        for item in catalogs:
            if not isinstance(item, dict):
                raise ValueError(f"{canonical}: ad format catalog entry must be an object")
            entry = dict(item)
            format_id = str(entry.get("format_id", "")).strip()
            status = str(entry.get("coverage", "")).strip().lower()
            if not format_id:
                raise ValueError(f"{canonical}: ad format catalog entry needs format_id")
            if status not in allowed:
                raise ValueError(
                    f"{canonical}.{format_id}: unsupported coverage {status!r}"
                )
            if not str(entry.get("category", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: category is required")
            if not str(entry.get("resource_type", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: resource_type is required")
            tool_names = entry.get("tool_names", []) or []
            if not isinstance(tool_names, list) or not all(
                isinstance(name, str) and name for name in tool_names
            ):
                raise ValueError(f"{canonical}.{format_id}: tool_names must be a string list")
            entry["format_id"] = format_id
            entry["coverage"] = status
            entry["tool_names"] = list(dict.fromkeys(tool_names))
            entry["live_support"] = bool(entry.get("live_support", False))
            registered_tools = {
                definition.name for definition in self.registry.list_all()
            }
            missing_tools = sorted(set(entry["tool_names"]) - registered_tools)
            if missing_tools:
                raise ValueError(
                    f"{canonical}.{format_id}: unknown tool_names: {', '.join(missing_tools)}"
                )
            if entry["live_support"]:
                raise ValueError(
                    f"{canonical}.{format_id}: ad-format live_support must remain false; "
                    "live enablement is a separate deployment approval"
                )
            if status == AdFormatCoverage.SUPPORTED_DRY_RUN.value and not entry.get(
                "payload_adapter"
            ):
                raise ValueError(
                    f"{canonical}.{format_id}: supported_dry_run needs payload_adapter"
                )
            previous = existing.get(format_id)
            if previous is not None and previous != entry:
                raise ValueError(f"{canonical}.{format_id}: conflicting catalog entry")
            if previous is None:
                existing[format_id] = entry
                normalized.append(entry)
        self.ad_format_catalogs[canonical] = normalized

    def list_ad_formats(
        self, platform: Optional[str] = None, coverage: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return JSON-safe format coverage metadata for UI/planners."""
        if coverage is not None:
            coverage = str(coverage).strip().lower()
            if coverage not in {item.value for item in AdFormatCoverage}:
                raise ValueError(f"unsupported ad format coverage: {coverage}")
        platforms = [self._canonical_platform(platform)] if platform else sorted(
            self.ad_format_catalogs
        )
        result: list[dict[str, Any]] = []
        for current in platforms:
            for entry in self.ad_format_catalogs.get(current, []):
                if coverage and entry.get("coverage") != coverage:
                    continue
                result.append({"platform": current, **dict(entry)})
        return result

    def list_parameter_options(
        self, platform: Optional[str] = None, field: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return JSON-safe static or dynamic provider parameter metadata."""
        return [
            catalog.to_dict()
            for catalog in self.parameter_catalogs.list(
                platform=platform, field=field, tool_name=tool_name
            )
        ]

    def resolve_parameter_options(
        self,
        platform: str,
        field: str,
        tool_name: str,
        account_id: str,
        *,
        session_id: Optional[str] = None,
        user_id: str = "parameter-options",
        tenant_id: str = "default",
        account_scope: Optional[Mapping[str, set[str]]] = None,
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
    ) -> dict[str, Any]:
        """Resolve one dynamic catalog through a registered read Tool.

        The metadata endpoint intentionally does not make network calls. This
        explicit resolver is the provider-backed counterpart for a form/UI:
        it reuses the normal account, permission, timeout and read-data
        boundaries, then returns short-lived selection tokens that are bound
        to this user/session/account/tool/field context.
        """
        actual_platform = self._canonical_platform(platform)
        catalog = self.parameter_catalogs.get(actual_platform, field, tool_name)
        if catalog is None:
            raise KeyError(
                f"parameter catalog not found for {actual_platform}.{field} ({tool_name})"
            )
        if catalog.source != "lookup":
            return catalog.to_dict()
        source_tool = str(catalog.lookup_tool or "")
        definition, _handler = self._get_registered_tool(source_tool)
        if not definition.is_read_tool:
            raise PermissionError("parameter lookup source must be read-only")
        if self._canonical_platform(definition.platform) != actual_platform:
            raise ValueError("parameter lookup source belongs to a different platform")
        if not account_id:
            raise ValueError("dynamic parameter lookup requires account_id")
        allowed, account_error = self._validate_account_with_principal(
            actual_platform, str(account_id), False, account_scope
        )
        if not allowed:
            raise PermissionError(account_error)
        permissions = self._granted_permissions if granted_permissions is None else frozenset(granted_permissions)
        permission_error = self._check_tool_permissions(definition, permissions)
        if permission_error:
            raise PermissionError(permission_error)

        session = self._ensure_session(
            session_id or str(uuid.uuid4()), user_id, str(account_id),
            None, tenant_id=tenant_id,
        )
        session.ctx.account_id = str(account_id)
        input_data: dict[str, Any] = {}
        properties = getattr(definition.input_schema, "properties", {}) or {}
        for account_field in ("account_id", "advertiser_id", "customer_id"):
            if account_field in properties:
                input_data[account_field] = str(account_id)
                break
        result = self._execute_tool(session.ctx, source_tool, input_data)
        result = self.input_builder.decorate_lookup_result(
            definition, result, session.ctx, actual_platform
        )
        result = self._enforce_result_limit(result, definition)
        if not result.success:
            raise RuntimeError(result.error or "parameter lookup failed")
        for selection in result.data.get("parameter_selections", []):
            if (
                selection.get("tool_name") == tool_name
                and selection.get("field") == field
            ):
                return selection
        raise RuntimeError(
            f"provider lookup {source_tool} returned no options for {tool_name}.{field}"
        )

    def _validate_parameter_lookup_contract(self) -> None:
        """Ensure dynamic fields point to executable same-provider read tools.

        A lookup descriptor is part of the Skill contract, not a free-form
        hint. Failing at registration keeps a typo or a write-tool reference
        from reaching the UI as a selectable option that Runtime cannot
        safely attest later.
        """
        definitions = {tool.name: tool for tool in self.registry.list_all()}
        errors: list[str] = []
        for tool in definitions.values():
            properties = getattr(tool.input_schema, "properties", {}) or {}
            for field_name, field_schema in properties.items():
                lookup_tool = self.input_builder.lookup_tool_for_schema_field(
                    field_schema
                )
                if not lookup_tool:
                    continue
                source = definitions.get(lookup_tool)
                if source is None:
                    errors.append(
                        f"{tool.name}.{field_name} references unknown lookup tool {lookup_tool}"
                    )
                    continue
                tool_platform = self._canonical_platform(tool.platform)
                source_platform = self._canonical_platform(source.platform)
                if tool_platform != source_platform:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} "
                        f"belongs to {source_platform}, not {tool_platform}"
                    )
                if not source.is_read_tool:
                    errors.append(
                        f"{tool.name}.{field_name} lookup tool {lookup_tool} must be read-only"
                    )
        if errors:
            raise ValueError("Invalid parameter lookup contract: " + "; ".join(errors[:20]))

    def _register_skill(self, skill: Skill) -> None:
        """将 Skill 的工具注册到 Registry"""
        if hasattr(self.intent_parser, "register_platform_aliases"):
            self.intent_parser.register_platform_aliases(
                getattr(skill, "platform", ""),
                getattr(skill, "platform_aliases", []) or [],
            )
        registered_names: list[str] = []
        for tool_def in skill.get_tools():
            skill_platform = self._canonical_platform(skill.platform)
            tool_platform = self._canonical_platform(tool_def.platform)
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
        if registered_names:
            skill_key = str(getattr(skill, "name", "") or skill.platform)
            self._skill_tool_names[skill_key] = registered_names
            self._skill_platforms[skill_key] = skill.platform
            self._skill_objects[skill_key] = skill
            platform_key = self._canonical_platform(skill.platform)
            keys = self._skill_keys_by_platform.setdefault(platform_key, [])
            if skill_key not in keys:
                keys.append(skill_key)
            if hasattr(self.intent_parser, "register_tool_definitions"):
                self.intent_parser.register_tool_definitions(
                    [self.registry.get(name)[0] for name in registered_names]
                )
    
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
        capability = self._discover_capability(canonical_platform, api_client)
        if capability is None:
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
            # A declarative Skill with no executable declarations uses the
            # provider Capability for its platform's verified handlers.
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
            metadata_errors = tool_def.routing_metadata_errors()
            if metadata_errors:
                raise ValueError(
                    f"Skill '{skill_key}' Tool '{tool_def.name}' is missing explicit "
                    "routing metadata: " + ", ".join(metadata_errors)
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            if not tool_def.required_permissions:
                tool_def.required_permissions = [
                    "ads.plan" if tool_def.is_write_tool else "ads.read"
                ]
            try:
                self.registry.register(tool_def, handler)
                self.parameter_catalogs.register_tool_schema(
                    tool_def.platform,
                    getattr(tool_def.input_schema, "properties", {})
                    if tool_def.input_schema else {},
                    tool_name=tool_def.name,
                )
                registered_count += 1
                logger.debug(f"✅ 注册工具: {tool_def.name} (platform={platform})")
            except Exception as e:
                logger.warning(f"⚠️ 注册工具失败 '{tool_def.name}': {e}")
        
        if registered_count == 0:
            logger.warning("⚠️ Skill '%s' 没有实际注册任何工具", skill_key)
            return False

        self._validate_parameter_lookup_contract()
        if hasattr(self.intent_parser, "register_tool_definitions"):
            self.intent_parser.register_tool_definitions(self.registry.list_all())

        # 保存 Skill 和平台映射
        self._loaded_skills.setdefault(canonical_platform, skill)
        self._skill_tool_names[skill_key] = [tool_def.name for tool_def, _ in tools]
        self._skill_platforms[skill_key] = canonical_platform
        self._skill_objects[skill_key] = skill
        keys = self._skill_keys_by_platform.setdefault(canonical_platform, [])
        if skill_key not in keys:
            keys.append(skill_key)

        self._refresh_parser_catalog()

        logger.info(f"✅ 已动态注册 Skill '{skill.name}'，共 {registered_count} 个工具")
        return True

    @staticmethod
    def _verify_skill_plugin(skill_dir: Any, plugin_path: Any) -> tuple[bool, str]:
        """Verify an optional Skill manifest before importing executable code."""
        skill_dir = os.fspath(skill_dir)
        plugin_path = os.fspath(plugin_path)
        manifest_path = os.path.join(skill_dir, "skill.manifest.json")
        require_manifest = os.environ.get("AD_AGENT_REQUIRE_SKILL_MANIFEST") == "1"
        if not os.path.exists(manifest_path):
            if require_manifest:
                return False, "skill.manifest.json is required"
            return True, "manifest not configured"
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                manifest = json.load(file)
        except (OSError, TypeError, ValueError) as exc:
            return False, f"invalid skill manifest: {exc}"
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, dict):
            return False, "skill manifest files must be an object"
        relative_name = os.path.basename(plugin_path)
        expected = files.get(relative_name) or files.get(os.path.relpath(plugin_path, skill_dir))
        if not isinstance(expected, str):
            return False, f"skill manifest does not cover {relative_name}"
        digest = hashlib.sha256()
        try:
            with open(plugin_path, "rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            return False, f"cannot hash Skill plugin: {exc}"
        if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
            return False, f"hash mismatch for {relative_name}"

        signing_key = os.environ.get("AD_AGENT_SKILL_MANIFEST_KEY")
        signature = manifest.get("signature") if isinstance(manifest, dict) else None
        if require_manifest and not signing_key:
            return False, "AD_AGENT_SKILL_MANIFEST_KEY is required with manifest enforcement"
        if signing_key:
            if not isinstance(signature, str) or not signature:
                return False, "signed Skill manifest is required"
            signed_payload = json.dumps(
                {
                    "skill": manifest.get("skill", os.path.basename(skill_dir)),
                    "version": manifest.get("version", "1"),
                    "files": files,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            expected_signature = hmac.new(
                signing_key.encode("utf-8"), signed_payload, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return False, "skill manifest signature mismatch"
        return True, "verified"

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

        verified, reason = AgentRuntime._verify_skill_plugin(skill_dir, plugin_path)
        if not verified:
            logger.error("拒绝加载 Skill plugin %s: %s", plugin_path, reason)
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
                signature = inspect.signature(factory)
            except (TypeError, ValueError):
                skill = factory(api_client)
            else:
                try:
                    signature.bind(api_client)
                except TypeError:
                    skill = factory()
                else:
                    # Do not catch TypeError from inside the factory: that is
                    # an implementation failure, not evidence of a zero-arg
                    # compatibility signature.
                    skill = factory(api_client)
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
        canonical_platform = self._canonical_platform(platform)
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
            target_skill = self._skill_objects.get(target_key)

            # Use the registry's locking/unregister seam instead of mutating
            # private indexes directly.
            for name in dict.fromkeys(tool_names):
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(tool_names)
            format_ids = self._skill_format_ids.pop(target_key, set())
            if format_ids:
                self.ad_format_catalogs[canonical_platform] = [
                    entry for entry in self.ad_format_catalogs.get(canonical_platform, [])
                    if str(entry.get("format_id")) not in format_ids
                ]
                if not self.ad_format_catalogs[canonical_platform]:
                    self.ad_format_catalogs.pop(canonical_platform, None)
            self._skill_tool_names.pop(target_key, None)
            self._skill_platforms.pop(target_key, None)
            self._skill_objects.pop(target_key, None)
            if target_skill is not None:
                self.skill_loader.unload(getattr(target_skill, "name", ""))

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
            self._refresh_parser_catalog()
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
        for skill_dir in self.skill_loader.iter_skill_dirs():
            try:
                self.skill_loader.load_skill_dir(skill_dir)
            except Exception as exc:
                logger.debug("加载可用 Skill 失败 %s: %s", skill_dir, exc)
        return self.skill_loader.list_all()
    
    def _load_required_skills(self, platforms: list[str]) -> None:
        """
        根据平台列表动态加载对应的 Skill 工具。

        Args:
            platforms: 需要加载的平台列表
        """
        if not platforms:
            return

        for platform in platforms:
            actual_platform = self._canonical_platform(platform)

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
        canonical_platform = self._canonical_platform(platform)
        for skill_key in self._skill_keys_by_platform.get(canonical_platform, []):
            skill = self._skill_objects.get(skill_key)
            if skill is not None:
                return skill

        # SkillLoader owns recursive discovery and package validation.  Runtime
        # only asks for the loaded package by its declared platform; it does not
        # parse another copy of SKILL.md or inspect loader internals.
        candidates = self.skill_loader.get_by_platform(canonical_platform)
        if candidates:
            return candidates[0]
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
            platform = self._canonical_platform(tool_def.platform)
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
        credentials = self._credentials_for_platform(platform)
        if not credentials:
            return None

        try:
            from ..api_clients.factory import create_platform_client
            return create_platform_client(platform, credentials)
        except Exception as e:
            logger.debug(f"创建 {platform} API Client 失败: {e}")

        return None

    def _credentials_for_platform(
        self, platform: str, credentials: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Resolve credentials by the same canonical platform identity.

        Credential dictionaries are request/application configuration, not a
        second provider registry.  Normalizing their keys lets a newly added
        Capability use its own platform ID without adding another Runtime
        branch.  The returned value is copied so callers cannot mutate the
        request envelope through a Client constructor.
        """
        source = credentials if credentials is not None else self._credentials
        if not isinstance(source, Mapping):
            return {}
        from ..capabilities.factory import normalize_platform

        wanted = normalize_platform(platform)
        for key, value in source.items():
            if normalize_platform(str(key)) == wanted and isinstance(value, dict):
                return copy.deepcopy(value)
        return {}

    @staticmethod
    def _discover_capability(platform: str, api_client: Any = None) -> Any:
        """Discover a built-in Capability by package convention.

        This keeps adding a provider out of the central Router and factory
        table. A channel package only needs
        ``capabilities/<platform>/capability.py`` and a
        ``create_<platform>_capability`` factory. Custom channels can instead
        expose executable Tools from their Skill plugin.
        """
        from ..capabilities.factory import discover_capability_factory, _call_factory

        factory = discover_capability_factory(platform)
        if not callable(factory):
            return None
        return _call_factory(factory, api_client)

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
        for raw_platform in credentials:
            platform = self._canonical_platform(str(raw_platform))
            provider_credentials = self._credentials_for_platform(platform, credentials)
            if not provider_credentials:
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

        protected_paths = self._validate_tool_input_redline(input_data)
        if protected_paths:
            return ToolResult.error(
                "请求包含禁止传入的凭证/账户配置字段："
                + ", ".join(protected_paths)
            )

        # Some legacy handlers retain an offline fixture fallback when their
        # ``client`` is None. That is useful for explicit dry-run/unit tests,
        # but it must never be reachable from an approved live write: a
        # locally generated ID would otherwise be reported as a provider
        # mutation. Keep this check in the shared execution seam so every
        # built-in and dynamically registered handler gets the same boundary.
        if definition.is_write_tool and self.execution_mode == ExecutionMode.LIVE.value:
            platform = self._canonical_platform(definition.platform)
            request_client = (request_clients or {}).get(platform)
            handler_has_client = hasattr(handler, "client")
            handler_client = getattr(handler, "client", None) if handler_has_client else None
            if not handler_has_client:
                return ToolResult(
                    success=False,
                    data={"execution_status": "provider_unavailable"},
                    error=(
                        f"{tool_name} 的 live Handler 未暴露受控 Provider Client；"
                        "live 写入已拒绝"
                    ),
                )
            if request_client is None and handler_client is None:
                return ToolResult(
                    success=False,
                    data={"execution_status": "provider_unavailable"},
                    error=(
                        f"{tool_name} 未配置 Provider Client；live 写入已拒绝，"
                        "不会返回本地模拟结果"
                    ),
                )

        turn_deadline = ctx.metadata.get("turn_deadline") if ctx else None
        now = time.monotonic()
        tool_deadline = now + float(getattr(definition, "timeout_seconds", 30.0))
        if turn_deadline is not None:
            tool_deadline = min(tool_deadline, float(turn_deadline))
        if tool_deadline <= now:
            return ToolResult(
                success=False,
                data={"execution_status": "timed_out"},
                error=f"工具 {tool_name} 在执行前已超过 timeout_seconds",
            )

        previous_deadline = ctx.metadata.get("tool_deadline") if ctx else None
        cancel_event = threading.Event()
        if ctx:
            ctx.metadata["tool_deadline"] = tool_deadline
            ctx.metadata["cancel_event"] = cancel_event

        def timeout_result() -> ToolResult:
            cancel_event.set()
            return ToolResult(
                success=False,
                data={"execution_status": "timed_out"},
                error=(
                    f"工具 {tool_name} 执行超过限制（最多 "
                    f"{float(getattr(definition, 'timeout_seconds', 30.0)):.3g} 秒）"
                ),
            )

        def prepare_handler(source_handler: Any, source_client: Any = None) -> tuple[Any, bool]:
            """Isolate client state and return ``(handler, is_isolated)``."""
            if source_client is None:
                return source_handler, False
            client_type = type(source_client)
            timeout_setter = getattr(client_type, "set_request_timeout", None)
            timeout_attribute = "request_timeout" in getattr(source_client, "__dict__", {})
            # Test doubles and third-party clients sometimes implement a
            # permissive __getattr__.  Do not shallow-copy those objects just
            # because an arbitrary attribute lookup appeared to succeed.
            expected = str(getattr(definition, "provider_api_version", "") or "").strip()
            client_state = getattr(source_client, "__dict__", {})
            actual_value = client_state.get("api_version") if isinstance(client_state, dict) else None
            if actual_value in (None, ""):
                actual_value = getattr(type(source_client), "api_version", "")
            actual = str(actual_value or "").strip()
            needs_version_marker = bool(expected and actual and expected != actual)
            if not callable(timeout_setter) and not timeout_attribute and not needs_version_marker:
                return source_handler, False
            try:
                isolated_handler = copy.copy(source_handler)
                isolated_client = copy.copy(source_client)
            except Exception as exc:
                if expected and actual and expected != actual:
                    raise RuntimeError(
                        f"{tool_name} 的 Provider Client 不支持请求级隔离，无法安全使用版本 adapter"
                    ) from exc
                if not callable(timeout_setter) and not timeout_attribute:
                    return source_handler, False
                raise RuntimeError(
                    f"{tool_name} 的 Provider Client 无法创建请求级隔离副本"
                ) from exc
            remaining = max(tool_deadline - time.monotonic(), 0.001)
            budget_setter = getattr(isolated_client, "set_request_budget", None)
            if callable(budget_setter):
                budget_setter(remaining)
            else:
                setter = getattr(isolated_client, "set_request_timeout", None)
                if callable(setter):
                    setter(remaining)
                elif hasattr(isolated_client, "request_timeout"):
                    isolated_client.request_timeout = remaining
            isolated_handler.client = isolated_client
            return isolated_handler, True

        def provider_version_error(client: Any) -> Optional[str]:
            """Reject a Tool/client version mismatch before provider I/O."""
            expected = str(getattr(definition, "provider_api_version", "") or "").strip()
            if not expected or client is None:
                return None
            checker = getattr(type(client), "supports_tool_api_version", None)
            if callable(checker):
                compatible = bool(checker(client, expected))
            else:
                client_state = getattr(client, "__dict__", {})
                actual_value = client_state.get("api_version") if isinstance(client_state, dict) else None
                if actual_value in (None, ""):
                    actual_value = getattr(type(client), "api_version", "")
                actual = str(actual_value or "").strip()
                compatible = not actual or actual == expected
            if compatible:
                return None
            client_state = getattr(client, "__dict__", {})
            actual_value = client_state.get("api_version") if isinstance(client_state, dict) else None
            if actual_value in (None, ""):
                actual_value = getattr(type(client), "api_version", "")
            actual = str(actual_value or "unknown")
            supported = getattr(type(client), "SUPPORTED_API_VERSIONS", ()) or ()
            return (
                f"{tool_name} 要求 Provider API {expected}，当前 Client 为 {actual}；"
                f"支持版本: {list(supported)}。请升级 Client 或提供版本 adapter"
            )

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

        try:
            if not request_clients:
                # A registered handler may own a provider client. Copy it for
                # this invocation so request timeout state cannot race with a
                # different session using the same handler.
                source_client = getattr(handler, "client", None)
                invocation_handler, client_isolated = prepare_handler(handler, source_client)
            else:
                client = request_clients.get(
                    self._canonical_platform(definition.platform)
                )
                if client is None or not hasattr(handler, "client"):
                    invocation_handler = handler
                    client_isolated = False
                else:
                    invocation_handler, client_isolated = prepare_handler(handler, client)

            active_client = getattr(invocation_handler, "client", None)
            version_error = provider_version_error(active_client)
            if version_error:
                return ToolResult.error(version_error)
            if active_client is not None and client_isolated:
                # BasePlatformClient reads this marker when selecting a
                # provider-owned request/response adapter. It is invocation
                # scoped because one Runtime may host multiple Tool versions.
                try:
                    active_client.requested_tool_api_version = str(
                        getattr(definition, "provider_api_version", "") or ""
                    ) or None
                except Exception:
                    # Third-party clients may be immutable; compatibility was
                    # already checked, so they can still execute exact-match
                    # contracts without the optional adapter marker.
                    pass

            if definition.input_schema:
                errors = validate_tool_input(definition.input_schema, input_data)
                if errors:
                    return ToolResult.error(f"Input validation failed: {errors}")
            def invoke_handler() -> ToolResult:
                if hasattr(invocation_handler, "execute"):
                    return invocation_handler.execute(ctx, input_data)
                if callable(invocation_handler):
                    return invocation_handler(ctx, input_data)
                return ToolResult.error(f"Tool '{tool_name}' has no executable handler")

            # Read handlers can be isolated in a worker and returned when the
            # deadline expires.  A live write is kept synchronous: returning
            # while an unkillable Python thread may still mutate a provider is
            # unsafe.  Provider clients receive the same deadline and must
            # abort their HTTP attempt; custom live handlers need equivalent
            # cooperative cancellation before being approved.
            if definition.is_read_tool:
                executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ad-agent-tool")
                future = executor.submit(invoke_handler)
                try:
                    result = future.result(timeout=max(tool_deadline - time.monotonic(), 0.001))
                except FutureTimeoutError:
                    return timeout_result()
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
            else:
                result = invoke_handler()
            if time.monotonic() > tool_deadline:
                return timeout_result()
            return self._apply_read_data_boundary(tool_name, result)
        finally:
            if ctx:
                if previous_deadline is None:
                    ctx.metadata.pop("tool_deadline", None)
                else:
                    ctx.metadata["tool_deadline"] = previous_deadline
                ctx.metadata.pop("cancel_event", None)

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
        return protected_field_paths(value, cls.PROTECTED_INPUT_FIELDS, path, limit=100)

    @classmethod
    def _validate_protected_input(cls, value: Any) -> list[str]:
        paths = cls._protected_field_paths(value)
        return paths[:10]

    @classmethod
    def _validate_tool_input_redline(cls, value: Any) -> list[str]:
        """Validate credentials everywhere and account config inside updates.

        ``account_id``/``customer_id`` are valid top-level selectors, so they
        cannot be globally rejected. They become protected configuration once
        nested below an ``updates`` payload. Keeping this check in the Runtime
        execution seam also protects custom Skill handlers and batch plans.
        """
        paths = cls._validate_protected_input(value)

        def visit(node: Any, path: str = "") -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    key_text = str(key)
                    current = f"{path}.{key_text}" if path else key_text
                    if normalize_field_name(key_text) in {"updates", "update"}:
                        paths.extend(protected_update_paths(child, current))
                    else:
                        visit(child, current)
            elif isinstance(node, (list, tuple)):
                for index, child in enumerate(node):
                    visit(child, f"{path}[{index}]")

        visit(value)
        return list(dict.fromkeys(paths))[:10]

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
        existing = self._session_manager.get_approval(expected["plan_fingerprint"])
        if existing:
            expected = {**expected, "expires_at": str(existing.get("expires_at", ""))}
            return expected
        if create:
            expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
            self._session_manager.create_approval(
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
        return self._session_manager.validate_approval(
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

    def _normalize_read_result_evidence(
        self, tool_def: Any, result: ToolResult
    ) -> ToolResult:
        """Normalize read evidence at the Runtime result boundary.

        The underlying Handler contract remains source-compatible for direct
        callers.  Results that enter the public turn aggregation path always
        carry an explicit evidence status; an omitted status is ``unknown``
        and can never be inferred as live data.
        """
        if not result or not result.success or not tool_def.is_read_tool:
            return result
        data = result.data if isinstance(result.data, dict) else {}
        if result.simulated or data.get("simulated") is True:
            if data.get("data_status") == "offline_mock":
                return result
            data = dict(data)
            data["data_status"] = "offline_mock"
            data.setdefault("simulated", True)
            result.data = data
            return result
        if data.get("data_status"):
            return result
        data = dict(data)
        data["data_status"] = "unknown"
        result.data = data
        return result
    
    def auto_load_skills(self, skills_root: str, credentials: dict = None) -> int:
        """
        自动加载 skills 目录下的所有 Skills。
        
        策略：
        1. 按标准 Agent Skill 约定发现所有包含 SKILL.md 的目录（可在根目录或任意层级）
        2. 业务上下文 Skill 只作为策略上下文，不注册执行工具
        3. 有受控插件的 Skill 通过统一 Runtime 注册工具
        4. 没有插件但能按包约定发现 Capability 的渠道 Skill，加载该 Capability
        5. 其他 Skill 只保留为自然语言上下文，不会因文件名或 workflow.yaml 变成工具
        
        Args:
            skills_root: Skills 根目录路径
            credentials: API 凭证配置
            
        Returns:
            成功加载的 Skill 数量
        """
        loaded_count = 0
        # Reuse credentials previously installed through set_credentials()
        # when callers do not repeat them during Skill discovery. Passing an
        # explicit empty mapping still means intentionally no provider creds.
        credentials = self._credentials if credentials is None else credentials
        credentials = credentials or {}
        # 保存凭证配置
        if credentials:
            self._credentials = copy.deepcopy(credentials)

        # Keep automatic discovery on the same canonical SkillLoader used by
        # normal Runtime initialization. This publishes aliases and expert
        # context from the user's root as well; the executable plugin or
        # Capability is still the only source of Tools below.
        self.skill_loader.add_root(skills_root)
        self.skill_loader.load_all()
        
        # SkillLoader is the single source of truth for standard directory
        # discovery.  Do not infer behavior from a parent folder name: a
        # packaged Skill can be mounted at the root or nested arbitrarily.
        # Only scan the root explicitly requested by this call.  The Runtime
        # may also have its built-in Skill root registered; including it here
        # would make a caller's temporary/managed root unexpectedly register
        # all built-in Capabilities a second time.
        for skill_dir in self.skill_loader.iter_skill_dirs([skills_root]):
            try:
                    # SkillLoader owns SKILL.md parsing, standard frontmatter,
                    # duplicate detection and malformed-package isolation.
                    # Runtime consumes the validated package instead of
                    # maintaining a second YAML parser for the same contract.
                    loaded_skill = self.skill_loader.load_skill_dir(skill_dir)
                    if loaded_skill is None or bool(getattr(loaded_skill, "context_only", False)):
                        continue
                    platform = loaded_skill.platform

                    # Loading SKILL.md supplies bounded expert context. It
                    # does not register routes or executable workflow steps.

                    # Executable extensions take precedence over declarative
                    # Skill metadata.  A plugin is still
                    # subject to the same registry, schema, account and write
                    # gates as built-in capabilities.
                    api_client = None
                    provider_credentials = self._credentials_for_platform(
                        platform, credentials
                    )
                    if provider_credentials:
                        try:
                            from ..api_clients.factory import create_platform_client
                            api_client = create_platform_client(
                                platform, provider_credentials
                            )
                        except Exception as e:
                            logger.debug(f"创建 {platform} API Client 失败: {e}")
                    plugin_skill = self._load_skill_plugin(skill_dir, api_client)
                    if plugin_skill is not None:
                        before_tool_count = len(self.registry.list_all())
                        registered = self.register_skill(
                            plugin_skill, platform, api_client
                        )
                        if not registered:
                            logger.warning(
                                "⚠️ Skill plugin '%s' 未注册任何可执行工具",
                                plugin_skill.name,
                            )
                            continue
                        loaded_count += 1
                        logger.info(
                            f"✅ 自动加载 Skill plugin: {plugin_skill.name} ({platform}, "
                            f"{len(self.registry.list_all()) - before_tool_count} executable tools)"
                        )
                        continue
                    
                    # Channel capability discovery is based on package
                    # convention, not on a parent directory name or a
                    # Markdown table. Context-only Skills remain
                    # context-only because their frontmatter is handled by
                    # SkillContract as ``context_only`` and never reaches
                    # this loop.
                    try:
                        from ..capabilities.factory import create_capability
                        canonical = self._canonical_platform(platform)
                        capability = self._discover_capability(canonical, api_client)
                        if capability is None:
                            capability = create_capability(canonical, api_client)
                        before_tool_count = len(self.registry.list_all())
                        self.register_capability(capability)
                        registered_count = len(self.registry.list_all()) - before_tool_count
                        if registered_count <= 0:
                            logger.warning(
                                "⚠️ Capability '%s' 未注册任何可执行工具",
                                canonical,
                            )
                            continue
                        loaded_count += 1
                        logger.info(
                            "✅ 自动加载 Capability: %s (%s, %s executable tools)",
                            platform,
                            platform,
                            registered_count,
                        )
                    except ValueError:
                        # A normal advisory Skill may have no executable
                        # Capability. That is expected and must not make a
                        # package layout convention mandatory.
                        logger.debug("未找到平台 Capability: %s", platform)
            except Exception as e:
                logger.warning(f"⚠️ 解析 Skill {skill_dir.name}/SKILL.md 失败: {e}")
        
        logger.info(f"✅ 自动加载完成，共加载 {loaded_count} 个 Skills")
        return loaded_count
    
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

    @staticmethod
    def _principal_accounts(
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> Optional[set[str]]:
        """Return the trusted principal's account scope, or ``None`` if absent."""
        if account_scope is None:
            return None
        normalized = AgentRuntime._canonical_platform(platform)
        aliases = {normalized, platform}
        accounts: set[str] = set()
        for key in aliases:
            values = account_scope.get(key, ()) if hasattr(account_scope, "get") else ()
            if isinstance(values, (str, bytes)):
                values = (values,)
            accounts.update(normalize_account_id(value) for value in (values or ()))
        return {value for value in accounts if value}

    def _validate_account_with_principal(
        self,
        platform: str,
        account_id: str,
        is_write: bool,
        account_scope: Optional[Mapping[str, Any]],
    ) -> tuple[bool, str]:
        """Apply both configured test-account and trusted principal scopes."""
        if account_scope is not None:
            principal_accounts = self._principal_accounts(platform, account_scope)
            if not principal_accounts or normalize_account_id(account_id) not in principal_accounts:
                return False, f"账户 {account_id or '<empty>'} 不在当前身份的授权范围内"
        return self._validate_account_for_tool(platform, account_id, is_write)

    def _available_accounts_for_request(
        self,
        platform: str,
        account_scope: Optional[Mapping[str, Any]],
    ) -> list[str]:
        configured = self.whitelist_validator.get_allowed_accounts(platform)
        principal_accounts = self._principal_accounts(platform, account_scope)
        if principal_accounts is None:
            return list(configured)
        return [
            account for account in configured
            if normalize_account_id(account) in principal_accounts
        ]

    def _simulate_write(self, tool_def: Any, input_data: dict, platform: str) -> ToolResult:
        """生成本地模拟结果，保证 dry-run 不触发任何平台 API。"""
        key = self.registry.generate_idempotency_key(tool_def.name, input_data, "dry-run") \
            if hasattr(self.registry, "generate_idempotency_key") else uuid.uuid4().hex[:16]
        name = input_data.get("name") or input_data.get("campaign_name") or f"dry_run_{key}"
        resource_type = getattr(tool_def, "resource_type", None) or "resource"
        resource_key = self._resource_id_field_for_tool(tool_def)
        parent_type = getattr(tool_def, "parent_resource_type", None)
        parent_field = self._parent_resource_id_field_for_tool(tool_def)
        parent_id = input_data.get(parent_field) if parent_field else None

        action = str(getattr(tool_def, "action", "") or "").lower()
        is_update = action in {"update", "pause", "resume", "enable", "disable"}
        is_delete = action == "delete"
        resource_id = input_data.get(resource_key) or f"dry_{platform}_{key}"
        operation = "delete" if is_delete else ("update" if is_update else "create")
        data = {
            "mode": ExecutionMode.DRY_RUN.value,
            "simulated": True,
            "live_support": bool(getattr(tool_def, "live_support", False)),
            "operation": operation,
            resource_key: resource_id,
            "resource_id_field": resource_key,
            "parent_resource_type": parent_type,
            "parent_resource_id_field": parent_field,
            "parent_resource_id": (
                str(parent_id) if parent_id not in (None, "") else None
            ),
            "name": name,
            "status": (
                "SIMULATED_DELETED" if is_delete
                else ("SIMULATED_UPDATED" if is_update else "SIMULATED_DRAFT")
            ),
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
    def _resource_id_field(resource_type: str) -> str:
        # Kept as a compatibility helper for callers that need a neutral
        # result key. Provider/Skill Tools must declare the actual wire field
        # through ``resource_id_field``; Core must not turn a logical resource
        # type into a provider field name.
        return "resource_id"

    @classmethod
    def _resource_id_field_for_tool(cls, tool_def: Any) -> str:
        """Resolve the provider resource ID from the Tool contract.

        A provider with a different wire name publishes
        ``resource_id_field`` on its Tool and does not require a Runtime
        change. A schema marker is accepted for custom Skill tools, but there
        is deliberately no resource-type-to-field lookup here.
        """
        declared = str(getattr(tool_def, "resource_id_field", "") or "").strip()
        if declared:
            return declared
        schema = getattr(tool_def, "input_schema", None)
        properties = getattr(schema, "properties", {}) if schema else {}
        if isinstance(properties, dict):
            marked = [
                str(name) for name, spec in properties.items()
                if isinstance(spec, dict)
                and (spec.get("resource_id") or spec.get("x-resource-id"))
            ]
            if len(marked) == 1:
                return marked[0]
        return "resource_id"

    @staticmethod
    def _parent_resource_id_field_for_tool(tool_def: Any) -> Optional[str]:
        """Resolve a Tool's parent ID field without provider branching.

        ``parent_resource_id_field`` is authoritative.  The schema marker is
        useful for plugin Tools that want to keep metadata close to their
        input contract; conventional logical names remain a compatibility
        fallback for older Tools.
        """
        declared = str(
            getattr(tool_def, "parent_resource_id_field", "") or ""
        ).strip()
        if declared:
            return declared

        schema = getattr(tool_def, "input_schema", None)
        properties = getattr(schema, "properties", {}) if schema else {}
        if isinstance(properties, dict):
            marked = [
                str(name) for name, spec in properties.items()
                if isinstance(spec, dict)
                and (spec.get("parent_resource_id") or spec.get("x-parent-resource-id"))
            ]
            if len(marked) == 1:
                return marked[0]

        parent_type = str(getattr(tool_def, "parent_resource_type", "") or "")
        normalized_parent = re.sub(r"[^a-z0-9]+", "_", parent_type.lower()).strip("_")
        candidates = [f"{normalized_parent}_id"] if normalized_parent else []
        if isinstance(properties, dict):
            for candidate in candidates:
                if candidate in properties:
                    return candidate
        return None

    @classmethod
    def _parent_resource_id_for_tool(
        cls, tool_def: Any, input_data: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        field = cls._parent_resource_id_field_for_tool(tool_def)
        value = (input_data or {}).get(field) if field else None
        return str(value) if value not in (None, "") else None

    @classmethod
    def _build_resource_results(cls, results: list[dict]) -> list[dict]:
        """Normalize write results without exposing provider credentials."""
        resource_items: list[ResourceResult] = []
        id_index: dict[tuple[str, str, str], int] = {}
        sequence = 0
        for item in results or []:
            tool_name = str(item.get("tool") or "")
            if not tool_name or not item.get("resource_type"):
                continue
            # Only resource-mutating results belong in this model.  A future
            # custom Tool may use a different name, so the result metadata is
            # also accepted as an explicit signal.
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            if not item.get("account_id") and not data and not item.get("error"):
                continue
            sequence += 1
            resource_type = str(item["resource_type"])
            id_field = str(item.get("resource_id_field") or cls._resource_id_field(resource_type))
            input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
            raw_id = data.get(id_field) or input_data.get(id_field) or item.get(id_field)
            if raw_id in (None, ""):
                raw_id = input_data.get("resource_id") or data.get("resource_id")
            raw_id = str(raw_id) if raw_id not in (None, "") else None
            simulated = bool(data.get("simulated") or item.get("simulated"))
            execution_status = str(data.get("execution_status") or "").lower()
            if item.get("skipped") or data.get("skipped"):
                status = "skipped"
            elif execution_status == "unsupported":
                status = "unsupported"
            elif execution_status in {"unknown", "timed_out", "transport_unknown"}:
                status = "unknown"
            elif item.get("needs_confirmation"):
                status = "awaiting_confirmation"
            elif item.get("success") and simulated:
                status = "planned"
            elif item.get("success"):
                status = "succeeded"
            else:
                status = "failed"

            parent_type = item.get("parent_resource_type") or data.get("parent_resource_type")
            parent_id = item.get("parent_resource_id") or data.get("parent_resource_id")
            if parent_id in (None, ""):
                # External consumers may provide a normalized result without
                # the top-level parent ID.  Only use the declared metadata
                # when available; do not guess from the provider name.
                parent_field = item.get("parent_resource_id_field")
                parent_id = input_data.get(parent_field) if parent_field else None
            parent_id = str(parent_id) if parent_id not in (None, "") else None
            normalized_platform = cls._canonical_platform(str(item.get("platform") or ""))
            parent_sequence = None
            if parent_id and parent_type:
                parent_sequence = id_index.get(
                    (normalized_platform, str(parent_type), parent_id)
                )
            local_id = raw_id if simulated else None
            provider_id = raw_id if raw_id and not simulated else None
            logical_id = str(
                data.get("logical_resource_id") or local_id or provider_id
                or input_data.get(id_field) or ""
            ) or None
            normalized = ResourceResult(
                sequence=sequence,
                platform=normalized_platform,
                resource_type=resource_type,
                tool_name=tool_name,
                status=status,
                parent_resource_type=(str(parent_type) if parent_type else None),
                account_id=(str(item.get("account_id")) if item.get("account_id") is not None else None),
                parent_sequence=parent_sequence,
                parent_resource_id=parent_id,
                provider_resource_id=provider_id,
                logical_resource_id=logical_id,
                local_resource_id=local_id,
                error=item.get("error"),
                simulated=simulated,
            )
            resource_items.append(normalized)
            if raw_id:
                id_index[(normalized_platform, resource_type, raw_id)] = sequence
        return [item.to_dict() for item in resource_items]

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
            "token", "secret", "api_key", "private_key", "private_key_id",
            "service_account", "sa_email", "developer_key", "credential", "authorization",
            "bc_id", "bcid", "partner_id", "partnerid", "perter_id", "perterid", "developer_token",
            "mcc", "login_customer_id", "logincustomerid",
            "manager_customer_id", "managercustomerid", "client_id", "clientid",
        )
        if isinstance(value, dict):
            return {
                k: (
                    AgentRuntime._redact_for_persistence(v)
                    if str(k).lower() in {"selection_token", "selection_tokens"}
                    else "<redacted>"
                    if any(part in str(k).lower() for part in sensitive)
                    else AgentRuntime._redact_for_persistence(v)
                )
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
                r"(?is)(?P<prefix>['\"]?(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id)['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                r"(?is)(?P<prefix>['\"]?authorization['\"]?\s*[:=]\s*)['\"][^'\"]*['\"]",
                # Unquoted key/value forms used by logs and CLI snippets.
                r"(?i)(?P<prefix>\b(?:access|refresh|developer)[_-]?token\s*[:=]\s*)[^\s,;}]+",
                r"(?is)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)-----BEGIN.*?-----END[^\r\n]*-----",
                r"(?i)(?P<prefix>\bprivate[_-]?key\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\bclient[_-]?secret\s*[:=]\s*)[^\s,;}]+",
                r"(?i)(?P<prefix>\b(?:bc[_-]?id|partner[_-]?id|perter[_-]?id|mcc|login[_-]?customer[_-]?id|manager[_-]?customer[_-]?id|client[_-]?id|authorization)\s*[:=]\s*)[^\s,;}]+",
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
        register_items: bool = True,
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
                "replay_policy": "explicit_operator_confirmation",
                "raw_input": self._redact_for_persistence(intent.raw_input),
            },
        )
        self._session_manager.heartbeat_workflow(
            workflow_id,
            self._workflow_lease_owner,
            self.workflow_stale_after_seconds,
        )
        # Register every write item before the first handler can run. A
        # feature that expands one Tool into multiple resource items can opt
        # out and create its own item-level checkpoints through the same
        # persistence service.
        if register_items:
            sequence = 0
            sequence_by_resource: dict[tuple[str, str], int] = {}
            for platform, tools in tool_plan.items():
                for tool in tools:
                    if not tool.is_write_tool:
                        continue
                    sequence += 1
                    actual_platform = self._canonical_platform(platform)
                    parent_sequence = None
                    parent_type = getattr(tool, "parent_resource_type", None)
                    if parent_type:
                        parent_sequence = sequence_by_resource.get(
                            (actual_platform, parent_type)
                        )
                    planned_account = self.account_resolver.resolve(
                        intent,
                        platform,
                        [tool],
                        session.ctx.account_id if len(intent.platforms) == 1 else None,
                    )
                    self._session_manager.record_workflow_item(
                        workflow_id=workflow_id,
                        sequence=sequence,
                        platform=actual_platform,
                        tool_name=tool.name,
                        status="planned",
                        input_data={},
                        account_id=planned_account,
                        resource_type=getattr(tool, "resource_type", None),
                        parent_resource_type=parent_type,
                        parent_sequence=parent_sequence,
                    )
                    sequence_by_resource[(actual_platform, tool.resource_type)] = sequence
        return workflow_id

    def _heartbeat_workflow(self, workflow_id: Optional[str]) -> bool:
        """Refresh the active workflow lease before another side effect."""
        if not workflow_id or not self._session_manager:
            return True
        return self._session_manager.heartbeat_workflow(
            workflow_id,
            self._workflow_lease_owner,
            self.workflow_stale_after_seconds,
        )

    def _finish_workflow(
        self,
        workflow_id: Optional[str],
        tool_plan: dict[str, list[Any]],
        results: list[dict],
        workflow_inputs: dict[int, dict],
        planning_errors: Optional[list[str]] = None,
    ) -> None:
        """Persist item-level state and record when a live chain needs review."""
        if not workflow_id or not self._session_manager:
            return
        planning_errors = list(planning_errors or [])
        write_tools = {
            tool.name for tools in tool_plan.values() for tool in tools
            if tool.is_write_tool
        }
        sequence_by_tool: dict[str, int] = {}
        definition_by_tool: dict[str, Any] = {}
        sequence = 0
        for platform, tools in tool_plan.items():
            for tool in tools:
                if tool.is_write_tool:
                    sequence += 1
                    sequence_by_tool[tool.name] = sequence
                    definition_by_tool[tool.name] = tool
        item_sequences = []
        successful_sequences = []
        failed_sequences = []
        unsupported_sequences = []
        unknown_sequences = []
        result_occurrences: dict[str, int] = {}
        for item in results:
            name = str(item.get("tool") or "")
            if name in write_tools:
                result_occurrences[name] = result_occurrences.get(name, 0) + 1
        seen_occurrences: dict[str, int] = {}
        sequence_by_resource_id: dict[tuple[str, str, str], int] = {}
        for index, item in enumerate(results):
            if item.get("tool") not in write_tools:
                continue
            # A batch-level planning error is not an executable workflow item.
            # Do not assign it a provider Tool's sequence: doing so can
            # overwrite a real item from another platform.
            if item.get("batch_planning_error"):
                continue
            tool_name = str(item.get("tool") or "")
            seen_occurrences[tool_name] = seen_occurrences.get(tool_name, 0) + 1
            explicit_sequence = item.get("workflow_sequence")
            if explicit_sequence not in (None, ""):
                try:
                    item_sequence = int(explicit_sequence)
                except (TypeError, ValueError):
                    item_sequence = None
            else:
                item_sequence = (
                    seen_occurrences[tool_name]
                    if result_occurrences.get(tool_name, 0) > 1
                    else sequence_by_tool.get(tool_name)
                )
            if item_sequence is None:
                continue
            item_sequences.append(item_sequence)
            skipped = bool(item.get("skipped"))
            if skipped:
                status = "skipped"
            elif isinstance(item.get("data"), dict) and item["data"].get("execution_status") == "unsupported":
                status = "unsupported"
                unsupported_sequences.append(item_sequence)
            elif isinstance(item.get("data"), dict) and item["data"].get("execution_status") in {
                "unknown", "timed_out", "transport_unknown",
            }:
                status = "unknown"
                unknown_sequences.append(item_sequence)
            elif item.get("needs_confirmation"):
                status = "awaiting_confirmation"
            elif item.get("success"):
                status = "succeeded"
                successful_sequences.append(item_sequence)
            else:
                status = "failed"
                failed_sequences.append(item_sequence)
            definition = definition_by_tool.get(tool_name)
            output_data = self._redact_for_persistence(item.get("data"))
            input_data = self._redact_for_persistence(workflow_inputs.get(index, {}))
            resource_type = getattr(definition, "resource_type", None)
            resource_id_field = str(
                item.get("resource_id_field")
                or self._resource_id_field_for_tool(definition)
            )
            output_object = item.get("data") if isinstance(item.get("data"), dict) else {}
            raw_resource_id = output_object.get(resource_id_field)
            if raw_resource_id in (None, ""):
                raw_resource_id = input_data.get(resource_id_field)
            parent_type = (
                item.get("parent_resource_type")
                or output_object.get("parent_resource_type")
                or getattr(definition, "parent_resource_type", None)
            )
            parent_field = str(
                item.get("parent_resource_id_field")
                or output_object.get("parent_resource_id_field")
                or self._parent_resource_id_field_for_tool(definition)
                or ""
            ) or None
            parent_resource_id = (
                item.get("parent_resource_id")
                or output_object.get("parent_resource_id")
                or (input_data.get(parent_field) if parent_field else None)
            )
            actual_platform = self._canonical_platform(str(item.get("platform") or ""))
            account_id = item.get("account_id") or output_object.get("account_id")
            if account_id in (None, ""):
                for account_key in ("account_id", "advertiser_id", "customer_id"):
                    if input_data.get(account_key) not in (None, ""):
                        account_id = input_data[account_key]
                        break
            parent_sequence = sequence_by_resource_id.get(
                (actual_platform, str(parent_type or ""), str(parent_resource_id))
            ) if parent_resource_id not in (None, "") and parent_type else None
            simulated = bool(output_object.get("simulated") or item.get("simulated"))
            provider_resource_id = (
                str(raw_resource_id) if raw_resource_id not in (None, "") and not simulated else None
            )
            local_resource_id = (
                str(raw_resource_id) if raw_resource_id not in (None, "") and simulated else None
            )
            self._session_manager.record_workflow_item(
                workflow_id=workflow_id,
                sequence=item_sequence,
                platform=actual_platform,
                tool_name=str(item.get("tool") or ""),
                status=status,
                input_data=input_data,
                output_data=output_data,
                error=item.get("error"),
                resource_type=resource_type,
                parent_resource_type=(str(parent_type) if parent_type else None),
                parent_sequence=parent_sequence,
                parent_resource_id=(str(parent_resource_id) if parent_resource_id not in (None, "") else None),
                provider_resource_id=provider_resource_id,
                logical_resource_id=local_resource_id or provider_resource_id,
                account_id=(str(account_id) if account_id not in (None, "") else None),
            )
            if raw_resource_id not in (None, ""):
                sequence_by_resource_id[
                    (actual_platform, str(resource_type or ""), str(raw_resource_id))
                ] = item_sequence

        persisted = self._session_manager.get_workflow(workflow_id) or {}
        pending_items = [
            item for item in persisted.get("items", [])
            if item.get("status") in {"planned", "running"}
        ]
        # A process can exit before a later tool produces a result. Never
        # close such a workflow as succeeded merely because the results list
        # contains no explicit failure; leave it recoverable instead.
        if pending_items:
            status = "recovery_required" if self.execution_mode == ExecutionMode.LIVE.value else "blocked"
            compensation_required = False
        elif unknown_sequences:
            status = "recovery_required"
            compensation_required = False
        elif failed_sequences and successful_sequences and self.execution_mode == ExecutionMode.LIVE.value:
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
        elif planning_errors:
            # A batch can contain valid dry-run items and unsupported or
            # malformed platform entries. The workflow is not wholly
            # successful in that case; surface the partial plan as blocked.
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
                "planning_error_count": len(planning_errors),
                "compensation_required": compensation_required,
                "compensation_policy": "manual_review_required",
            },
        )

    def _resolve_readback_definition(self, write_tool: str):
        """Find the read Tool matching a write Tool's resource metadata."""
        try:
            write_definition, _handler = self._get_registered_tool(write_tool)
        except KeyError:
            return None
        platform = self._canonical_platform(write_definition.platform)
        declared_readback = str(
            getattr(write_definition, "readback_tool", "") or ""
        ).strip()
        if declared_readback:
            try:
                candidate, _handler = self._get_registered_tool(declared_readback)
            except KeyError:
                return None
            if not candidate.is_read_tool:
                return None
            if self._canonical_platform(candidate.platform) != platform:
                return None
            if candidate.action != "get" or candidate.resource_type != write_definition.resource_type:
                return None
            if candidate.parent_resource_type != write_definition.parent_resource_type:
                return None
            return candidate

        candidates = []
        for definition in self.registry.list_all():
            if not definition.is_read_tool:
                continue
            if self._canonical_platform(definition.platform) != platform:
                continue
            if definition.action != "get" or definition.resource_type != write_definition.resource_type:
                continue
            if definition.parent_resource_type != write_definition.parent_resource_type:
                continue
            candidates.append(definition)
        # A name/order based tie-breaker would make a provider upgrade
        # silently reconcile against the wrong endpoint. Ambiguity is a
        # provider contract problem and must remain visible to recovery.
        return candidates[0] if len(candidates) == 1 else None

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
        principal: Optional[RequestPrincipal] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Execute one turn while serializing turns for the same session.

        SessionContext, credentials and protected state are mutable.  Without
        this boundary two concurrent requests for one session can interleave
        account context, tool outputs and confirmation state.
        """
        self.assert_llm_ready()
        lock = self._get_session_lock(session_id or "__new_session__")
        effective_user_id = principal.user_id if principal is not None else user_id
        effective_permissions = (
            principal.permissions if principal is not None else self._granted_permissions
        )
        effective_account_scope = (
            principal.account_scope if principal is not None else None
        )
        with lock:
            return self._run_unlocked(
                user_input=user_input,
                session_id=session_id,
                user_id=effective_user_id,
                account_id=account_id,
                credentials=credentials,
                platform_params=platform_params,
                confirmed=confirmed,
                confirmation_payload=confirmation_payload,
                granted_permissions=effective_permissions,
                account_scope=effective_account_scope,
                tenant_id=(
                    principal.tenant_id
                    if principal is not None
                    else (tenant_id or "default")
                ),
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
        granted_permissions: Optional[set[str] | frozenset[str]] = None,
        account_scope: Optional[Mapping[str, Any]] = None,
        tenant_id: str = "default",
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
        session = self._ensure_session(
            session_id, user_id, account_id, credentials, tenant_id=tenant_id
        )
        turn_deadline = time.monotonic() + self.turn_timeout_seconds
        session.ctx.metadata["turn_deadline"] = turn_deadline
        session.ctx.metadata["tenant_id"] = str(tenant_id or "default")
        effective_permissions = (
            self._granted_permissions
            if granted_permissions is None
            else frozenset(granted_permissions)
        )
        
        # Step 2: 解析用户意图
        # Give an injected LLM the bounded Skill/tool context before it emits
        # an intent.  The post-parse IntentRouter remains authoritative, so
        # this context can improve recognition but cannot grant execution.
        try:
            skill_context = self._build_skill_context(
                safe_user_input, self.registry.list_all(), None, tenant_id
            )
            skill_context["prior_tool_results"] = self._build_prior_tool_results_context(session)
            session.ctx.metadata["skill_context"] = skill_context
        except Exception as exc:
            logger.debug("构建 Skill 解析上下文失败: %s", exc)
        intent = self.intent_parser.parse(safe_user_input, session.ctx)
        # Refresh advisory context with the parsed intent.  This changes only
        # the model-facing explanation/context; IntentRouter remains the sole
        # authority for the executable plan below.
        try:
            skill_context = self._build_skill_context(
                safe_user_input,
                self.registry.list_all(),
                intent.intent_type,
                tenant_id,
            )
            skill_context["prior_tool_results"] = self._build_prior_tool_results_context(session)
            session.ctx.metadata["skill_context"] = skill_context
        except Exception as exc:
            logger.debug("构建意图级 Skill/知识上下文失败: %s", exc)
        
        # 如果提供了 platform_params（来自确认请求），合并到意图中
        if platform_params:
            protected_paths = self._validate_tool_input_redline(platform_params)
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

        policy_errors = self._validate_policies(intent)
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

        # Step 3: discover Tools from their self-described action/resource
        # metadata. Skills provide expert context and SOP; the Runtime orders
        # the returned Tool plan from provider-owned resource metadata.
        tool_plan = self.intent_router.route(intent, self.registry)
        execution_groups = list(tool_plan.items())
        routed_tools = [
            tool for _platform, tools in execution_groups for tool in tools
        ]
        tool_selection = self.tool_selector.optimize_for_llm(
            safe_user_input, intent, routed_tools
        )
        feature = self._feature_for_intent(intent)

        parameter_errors = self.input_builder.validate_platform_parameter_contract(
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

        # Cross-channel creation is preflighted as one provider-neutral plan.
        # This must happen before workflow creation or any provider Tool is
        # invoked, otherwise one channel could be committed/planned before a
        # later channel reveals a missing objective, app, targeting or asset.
        creation_preflight = None
        if (
            feature is not None
            and callable(getattr(feature, "preflight_creation", None))
            and callable(getattr(feature, "handles_creation_preflight", None))
            and feature.handles_creation_preflight(intent)
        ):
            creation_preflight = feature.preflight_creation(
                self,
                intent,
                tool_plan,
                session,
                account_id,
                account_scope,
                effective_permissions,
            )
            if not creation_preflight.ready:
                preflight_results = feature.preflight_results(creation_preflight)
                preflight_reply = getattr(feature, "preflight_failure_reply", None)
                reply = (
                    preflight_reply(intent, creation_preflight)
                    if callable(preflight_reply)
                    else "跨渠道创建 preflight 未通过；已停止所有渠道的创建。"
                )
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
                        "knowledge": tool_selection.get("knowledge", []),
                    },
                    "results": preflight_results,
                    "resource_results": [],
                    "workflow_id": None,
                    **(
                        feature.preflight_payload(creation_preflight)
                        if callable(getattr(feature, "preflight_payload", None))
                        else {"preflight": creation_preflight.to_dict()}
                    ),
                    "reply": reply,
                    "needs_confirmation": False,
                    "confirmation_payload": None,
                    "policy_errors": list(creation_preflight.errors),
                }
        
        # Batch management is a first-class planning operation.  It expands
        # IDs into independent items while retaining the normal whitelist and
        # workflow audit boundaries; no provider Handler is called here.
        if feature is not None and callable(
            getattr(feature, "is_batch_intent", None)
        ) and feature.is_batch_intent(intent):
            workflow_id = self._start_workflow(
                session,
                intent,
                tool_plan,
                register_items=not feature.is_batch_intent(intent),
            )
            return feature.run_batch_plan(
                self,
                safe_user_input, session, turn_id, intent, tool_plan,
                account_id, workflow_id,
                account_scope=account_scope,
                granted_permissions=effective_permissions,
            )

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
                    "knowledge": tool_selection.get("knowledge", []),
                },
                "results": [],
                "reply": self.response_renderer.render_chat(safe_user_input),
                "needs_confirmation": False,
                "confirmation_payload": None,
            }
        
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
        workflow_sequence = 0

        tool_call_count = 0
        for platform, tools in execution_groups:
            # 转换平台名称
            actual_platform = self._canonical_platform(platform)

            # 每个平台使用自己的账户（不跨平台共享）。没有显式账户时，
            # 只允许从配置的测试白名单中自动选择。
            per_platform_account = self.account_resolver.resolve(
                intent, platform, tools, account_id
            )
            if not per_platform_account:
                test_accounts = self._available_accounts_for_request(
                    actual_platform, account_scope
                )
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
                allowed, error_msg = self._validate_account_with_principal(
                    actual_platform, per_platform_account, platform_has_write,
                    account_scope,
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
                self._heartbeat_workflow(workflow_id)
                if workflow_id and tool_def.is_write_tool:
                    workflow_sequence += 1
                    self._session_manager.record_workflow_item(
                        workflow_id=workflow_id,
                        sequence=workflow_sequence,
                        platform=actual_platform,
                        tool_name=tool_def.name,
                        status="running",
                        input_data={},
                        account_id=per_platform_account,
                        parent_resource_type=getattr(tool_def, "parent_resource_type", None),
                    )
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
                permission_error = self._check_tool_permissions(
                    tool_def, effective_permissions
                )
                if permission_error:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {},
                        "error": permission_error,
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
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
                tool_input = self.input_builder.build(
                    tool_def, intent, platform, session.ctx
                )
                if workflow_id and tool_def.is_write_tool:
                    self._session_manager.record_workflow_item(
                        workflow_id=workflow_id,
                        sequence=workflow_sequence,
                        platform=actual_platform,
                        tool_name=tool_def.name,
                        status="running",
                        input_data=self._redact_for_persistence(tool_input),
                        account_id=per_platform_account,
                        parent_resource_type=getattr(tool_def, "parent_resource_type", None),
                    )

                protected_paths = self._validate_tool_input_redline(tool_input)
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

                selection_errors = tool_input.pop("_selection_errors", None)
                if selection_errors:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "data": {"execution_status": "invalid_parameter_selection"},
                        "error": "参数选择凭证无效：" + "; ".join(selection_errors),
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue
                
                # 检查必需参数是否齐全，不齐全则询问用户
                missing_params = tool_input.pop("_missing_params", None)
                if missing_params:
                    lookup_tools = self.input_builder.lookup_tools_for_fields(
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
                    not self.allow_live_writes
                    or not tool_def.live_support
                    or tool_def.name not in self._live_approved_tools
                ):
                    if not self.allow_live_writes:
                        reason = "Runtime 全局 allow_live_writes 未开启"
                    elif not tool_def.live_support:
                        reason = "该 Tool 当前仅支持 dry-run"
                    else:
                        reason = "该 Tool 未加入 live 执行批准清单"
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"{tool_def.name} 当前禁止 live 执行：{reason}",
                        "needs_confirmation": False,
                    })
                    chain_blocked = True
                    chain_blocker = tool_def.name
                    session.ctx.account_id = original_account
                    continue

                if (
                    tool_def.is_write_tool
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and self.write_guard is None
                ):
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": "live 写操作必须配置 WriteGuard；已拒绝执行",
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

                result = self._normalize_read_result_evidence(tool_def, result)
                result = self.input_builder.decorate_lookup_result(
                    tool_def, result, session.ctx, actual_platform
                )
                result = self._enforce_result_limit(result, tool_def)
                if self._is_uncertain_provider_failure(tool_def, result):
                    # A transport/temporary error does not prove that the
                    # provider rejected the write. Persist an explicit
                    # unknown outcome so workflow recovery and reconciliation
                    # do not depend on parsing the human-readable error.
                    result.data = {
                        **(result.data if isinstance(result.data, dict) else {}),
                        "execution_status": "unknown",
                    }
                self._heartbeat_workflow(workflow_id)

                resource_type = getattr(tool_def, "resource_type", None)
                resource_id_field = self._resource_id_field_for_tool(tool_def)
                parent_type = getattr(tool_def, "parent_resource_type", None)
                parent_field = self._parent_resource_id_field_for_tool(tool_def)
                parent_id = tool_input.get(parent_field) if parent_field else None
                # Keep hierarchy metadata next to the provider result. This
                # is especially important for live adapters whose response
                # only contains the newly created object's ID.
                if resource_type and isinstance(result.data, dict):
                    result.data = {
                        **result.data,
                        "resource_type": resource_type,
                        "resource_id_field": resource_id_field,
                        "parent_resource_type": parent_type,
                        "parent_resource_id_field": parent_field,
                        "parent_resource_id": (
                            str(parent_id) if parent_id not in (None, "") else None
                        ),
                    }

                result_index = len(results)
                safe_result_data = self._redact_for_persistence(result.data)
                safe_result_error = self._redact_for_persistence(result.error)
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "resource_type": resource_type,
                    "resource_id_field": resource_id_field,
                    "parent_resource_type": parent_type,
                    "parent_resource_id_field": parent_field,
                    "parent_resource_id": (
                        str(parent_id) if parent_id not in (None, "") else None
                    ),
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
                            self._session_manager.consume_approval(
                                expected_confirmation["plan_fingerprint"],
                                expected_confirmation["confirmation_token"],
                            )
                elif (
                    (not result.success or result.requires_confirmation)
                    and self.execution_mode == ExecutionMode.LIVE.value
                    and tool_def.is_write_tool
                    and self.write_guard
                    and hasattr(self.write_guard, "release_write")
                    and not self._is_uncertain_provider_failure(tool_def, result)
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
        if feature is not None and callable(
            getattr(feature, "collect_metrics", None)
        ):
            feature.collect_metrics(
                self,
                intent, tool_plan, results, session, turn_id, request_clients,
                account_scope=account_scope,
                granted_permissions=effective_permissions,
            )
        self._finish_workflow(workflow_id, tool_plan, results, workflow_inputs)
        resource_results = self._build_resource_results(results)

        analysis: dict[str, Any] = {}
        if feature is not None and callable(getattr(feature, "analyze", None)):
            analysis = feature.analyze(intent, results)
        reply = self.response_renderer.render(
            intent, results, needs_confirmation, analysis=analysis
        )
        
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
                "knowledge": tool_selection.get("knowledge", []),
            },
            "results": results,
            "resource_results": resource_results,
            "workflow_id": workflow_id,
            **(
                feature.preflight_payload(creation_preflight)
                if creation_preflight is not None
                and callable(getattr(feature, "preflight_payload", None))
                else (
                    {"preflight": creation_preflight.to_dict()}
                    if creation_preflight is not None
                    else {}
                )
            ),
            **(analysis if isinstance(analysis, dict) else {}),
            "reply": reply,
            "needs_confirmation": needs_confirmation,
            "confirmation_payload": confirmation_payload,
        }
    
# ─── Session 管理 ──────────────────────────────────────────
    
    def _ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
        tenant_id: str = "default",
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
            persisted_tenant = str(persisted_metadata.get("tenant_id", "default"))
            if persisted and persisted_tenant != str(tenant_id or "default"):
                raise PermissionError("session belongs to a different tenant")
            ctx = ToolContext(
                session_id=session_id,
                user_id=user_id,
                account_id=account_id or (persisted or {}).get("account_id"),
                credentials=self._freeze_credentials(copy.deepcopy(credentials or {})),
            )
            session = SessionContext(session_id, ctx)
            ctx.metadata["tenant_id"] = str(tenant_id or "default")
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
                        "tenant_id": str(tenant_id or "default"),
                    },
                )
        session = self._sessions[session_id]
        if session.ctx.user_id != user_id:
            raise PermissionError("session belongs to a different user")
        if str(session.ctx.metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
            raise PermissionError("session belongs to a different tenant")
        if account_id and session.ctx.account_id and str(account_id) != str(session.ctx.account_id):
            raise PermissionError("session belongs to a different account")
        if credentials:
            session.ctx.credentials = self._freeze_credentials(copy.deepcopy(credentials))
        return session
    
    def get_workflow(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Read a durable workflow while enforcing its owning user boundary."""
        if not self._session_manager:
            return None
        workflow = self._session_manager.get_workflow(workflow_id)
        if not workflow:
            return None
        if user_id is not None or tenant_id is not None:
            session = self._session_manager.get_session(workflow.get("session_id")) or {}
            if user_id is not None and str(session.get("user_id")) != str(user_id):
                raise PermissionError("workflow belongs to a different user")
            if tenant_id is not None:
                try:
                    metadata = json.loads(session.get("metadata") or "{}")
                except (TypeError, ValueError):
                    metadata = {}
                if str(metadata.get("tenant_id", "default")) != str(tenant_id or "default"):
                    raise PermissionError("workflow belongs to a different tenant")
        return workflow

    def get_workflow_resume_plan(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Return a safe replay plan without executing any provider operation.

        Recovery is deliberately an explicit two-step protocol.  This method
        only exposes the durable items that still need action; a future worker
        must call the normal Runtime path with a fresh approval and current
        principal instead of replaying handlers directly from SQLite.
        """
        workflow = self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        if workflow.get("status") == "running" and self._is_stale_workflow(workflow):
            self._session_manager.recover_stale_workflow(
                workflow_id,
                self.workflow_stale_after_seconds,
                {
                    "recovery_reason": "stale_running_workflow",
                    "recovery_detected_at": datetime.now().isoformat(),
                },
            )
            workflow = self.get_workflow(
                workflow_id, user_id=user_id, tenant_id=tenant_id
            ) or workflow
        resumable = {"failed", "partially_failed", "recovery_required", "blocked"}
        if workflow.get("status") not in resumable:
            return {
                "workflow_id": workflow_id,
                "status": workflow.get("status"),
                "resumable": False,
                "requires_fresh_confirmation": False,
                "items": [],
            }
        pending = [
            item for item in workflow.get("items", [])
            if item.get("status") not in {"succeeded", "unsupported"}
        ]
        session_record = (
            self._session_manager.get_session(workflow.get("session_id"))
            if self._session_manager else None
        ) or {}
        session_account_id = str(session_record.get("account_id") or "")

        def item_account_id(item: Mapping[str, Any]) -> Optional[str]:
            account_id = item.get("account_id")
            if account_id not in (None, ""):
                return str(account_id)
            input_data = item.get("input_data")
            if isinstance(input_data, Mapping):
                for key in ("account_id", "advertiser_id", "customer_id"):
                    value = input_data.get(key)
                    if value not in (None, ""):
                        return str(value)
            return session_account_id or None

        definitions = {
            definition.name: definition
            for definition in self.registry.list_all()
        }

        def item_definition_value(
            item: Mapping[str, Any], field: str,
        ) -> Optional[str]:
            value = item.get(field)
            if value not in (None, ""):
                return str(value)
            definition = definitions.get(str(item.get("tool_name") or ""))
            value = getattr(definition, field, None) if definition else None
            return str(value) if value not in (None, "") else None

        return {
            "workflow_id": workflow_id,
            "status": workflow.get("status"),
            "resumable": bool(pending),
            "requires_fresh_confirmation": workflow.get("execution_mode") == ExecutionMode.LIVE.value,
            "replay_policy": "explicit_operator_confirmation",
            "items": [
                {
                    "sequence": item.get("sequence"),
                    "platform": self._canonical_platform(str(item.get("platform") or "")),
                    "account_id": item_account_id(item),
                    "tool_name": item.get("tool_name"),
                    "resource_type": item_definition_value(item, "resource_type"),
                    "parent_resource_type": item_definition_value(
                        item, "parent_resource_type"
                    ),
                    "parent_resource_id": item.get("parent_resource_id"),
                    "status": item.get("status"),
                    "input_data": self._redact_for_persistence(item.get("input_data") or {}),
                    "error": self._redact_for_persistence(item.get("error")),
                }
                for item in pending
            ],
        }

    def _is_stale_workflow(self, workflow: Mapping[str, Any]) -> bool:
        """Treat a running workflow as recoverable only after its lease age."""
        try:
            updated_at = datetime.fromisoformat(str(workflow.get("updated_at")))
            age = (datetime.now() - updated_at).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return False
        return age >= self.workflow_stale_after_seconds

    def list_resumable_workflows(
        self, user_id: Optional[str] = None, tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List failed or stale-running workflows within an optional tenant."""
        if not self._session_manager:
            return []
        workflows = self._session_manager.list_resumable_workflows(
            user_id=user_id,
            limit=limit,
            include_stale_running=True,
            stale_after_seconds=self.workflow_stale_after_seconds,
        )
        if tenant_id is None:
            return workflows
        filtered = []
        for workflow in workflows:
            session = self._session_manager.get_session(workflow.get("session_id")) or {}
            try:
                metadata = json.loads(session.get("metadata") or "{}")
            except (TypeError, ValueError):
                metadata = {}
            if str(metadata.get("tenant_id", "default")) == str(tenant_id):
                filtered.append(workflow)
        return filtered

    def reconcile_workflow(
        self,
        workflow_id: str,
        observations: list[dict] | dict[int, dict],
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Apply provider-verified observations to a durable workflow.

        No provider is contacted here.  Every observation must explicitly set
        ``verified=true`` so an untrusted status guess cannot mark a failed
        live write as successful.  Unknown outcomes remain recovery-required.
        """
        workflow = self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        if isinstance(observations, dict):
            entries = [dict(value, sequence=key) for key, value in observations.items()]
        else:
            entries = list(observations or [])
        if not entries:
            raise ValueError("reconciliation requires at least one observation")
        known_sequences = {
            int(item.get("sequence"))
            for item in workflow.get("items", [])
            if item.get("sequence") is not None
        }
        current_statuses = {
            int(item.get("sequence")): str(item.get("status"))
            for item in workflow.get("items", [])
            if item.get("sequence") is not None
        }
        allowed_item_transitions = {
            "failed": {"failed", "succeeded", "unknown"},
            "unknown": {"unknown", "succeeded", "failed"},
            "awaiting_confirmation": {"awaiting_confirmation", "succeeded", "failed", "unknown"},
            "running": {"running", "succeeded", "failed", "unknown"},
            "planned": {"planned", "awaiting_confirmation", "running", "succeeded", "failed", "unknown"},
            "succeeded": {"succeeded"},
            "unsupported": {"unsupported"},
            "skipped": {"skipped"},
        }
        seen_sequences: set[int] = set()
        for observation in entries:
            if not isinstance(observation, dict) or observation.get("verified") is not True:
                raise ValueError("each reconciliation observation must set verified=true")
            status = str(observation.get("status", "unknown"))
            if status not in {"succeeded", "failed", "unknown"}:
                raise ValueError("reconciliation status must be succeeded, failed or unknown")
            if observation.get("sequence") is None:
                raise ValueError("reconciliation observation requires sequence")
            try:
                sequence = int(observation["sequence"])
            except (TypeError, ValueError):
                raise ValueError("reconciliation sequence must be an integer")
            if sequence not in known_sequences:
                raise ValueError("reconciliation sequence does not belong to workflow")
            if sequence in seen_sequences:
                raise ValueError("reconciliation sequence must be unique")
            current_status = current_statuses[sequence]
            if status not in allowed_item_transitions.get(current_status, set()):
                raise ValueError(
                    f"cannot reconcile workflow item {sequence} from {current_status} to {status}"
                )
            seen_sequences.add(sequence)
        for observation in entries:
            sequence = int(observation["sequence"])
            status = str(observation.get("status", "unknown"))
            updated_item = self._session_manager.update_workflow_item(
                workflow_id,
                sequence,
                status,
                output_data=self._redact_for_persistence(observation.get("output_data")),
                error=self._redact_for_persistence(observation.get("error")),
            )
            if not updated_item:
                raise ValueError(f"workflow item {sequence} could not be updated")

        updated = self._session_manager.get_workflow(workflow_id)
        items = updated.get("items", []) if updated else []
        statuses = [str(item.get("status")) for item in items]
        succeeded = [item for item in items if item.get("status") == "succeeded"]
        failed = [item for item in items if item.get("status") == "failed"]
        if any(status == "unknown" for status in statuses):
            workflow_status = "recovery_required"
        elif failed and succeeded:
            self._session_manager.mark_workflow_items_for_compensation(
                workflow_id,
                [int(item["sequence"]) for item in succeeded],
            )
            workflow_status = "partially_failed"
        elif failed:
            workflow_status = "failed"
        elif statuses and all(status in {"succeeded", "unsupported"} for status in statuses):
            workflow_status = "succeeded"
        else:
            workflow_status = "recovery_required"
        self._session_manager.update_workflow(
            workflow_id,
            workflow_status,
            {
                "last_reconciled_by": str(user_id or "operator"),
                "reconciliation_verified": True,
            },
        )
        return self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        ) or {}

    def reconcile_workflow_from_provider(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        credentials: Optional[dict] = None,
        principal: Optional[RequestPrincipal] = None,
    ) -> dict:
        """Resolve pending items through provider-owned read-back adapters.

        This method never replays a write. A reconciler can only invoke a
        registered read tool through the Runtime, and its observation is
        applied by the same verified state-transition path as externally
        supplied observations.
        """
        if not self._session_manager:
            raise RuntimeError("provider reconciliation requires persistence")
        effective_user_id = principal.user_id if principal is not None else user_id
        effective_tenant_id = principal.tenant_id if principal is not None else tenant_id
        permissions = (
            principal.permissions if principal is not None else self._granted_permissions
        )
        permissions = frozenset(permissions or ())
        if "ads.reconcile" not in permissions and "ads.write" not in permissions:
            raise PermissionError("provider reconciliation requires ads.reconcile or ads.write")
        if "ads.read" not in permissions and "ads.write" not in permissions:
            raise PermissionError("provider reconciliation requires ads.read")

        workflow = self.get_workflow(
            workflow_id,
            user_id=effective_user_id,
            tenant_id=effective_tenant_id,
        )
        if not workflow:
            raise KeyError("workflow not found")
        if not self._session_manager.claim_workflow_recovery(
            workflow_id,
            self._workflow_lease_owner,
            self.workflow_stale_after_seconds,
            self.workflow_stale_after_seconds,
        ):
            raise RuntimeError("workflow is already being recovered or is still active")
        workflow = self.get_workflow(
            workflow_id,
            user_id=effective_user_id,
            tenant_id=effective_tenant_id,
        ) or workflow
        session_record = self._session_manager.get_session(workflow.get("session_id")) or {}
        request_clients = self._build_request_clients(credentials)
        account_scope = principal.account_scope if principal is not None else None
        observations: list[dict[str, Any]] = []
        pending_statuses = {
            "planned", "running", "awaiting_confirmation", "failed", "unknown",
        }

        for item in workflow.get("items", []):
            if str(item.get("status")) not in pending_statuses:
                continue
            platform = self._canonical_platform(item.get("platform") or "")
            input_data = item.get("input_data") if isinstance(item.get("input_data"), dict) else {}
            account_id = None
            for account_key in ("account_id", "advertiser_id", "customer_id"):
                if input_data.get(account_key):
                    account_id = str(input_data[account_key])
                    break
            account_id = account_id or str(session_record.get("account_id") or "")
            allowed, account_error = self._validate_account_with_principal(
                platform, account_id, False, account_scope
            )
            if not allowed:
                observations.append({
                    "sequence": item.get("sequence"),
                    "status": "unknown",
                    "verified": True,
                    "error": f"read-back account boundary rejected: {account_error}",
                    "source": "runtime_account_boundary",
                })
                continue

            reconciler = self._provider_reconcilers.get(platform) or ToolReadbackReconciler(platform)

            ctx = ToolContext(
                session_id=str(workflow.get("session_id") or ""),
                user_id=str(effective_user_id or session_record.get("user_id") or ""),
                account_id=account_id,
                credentials=self._freeze_credentials(credentials or {}),
                metadata={
                    "tenant_id": str(effective_tenant_id or "default"),
                    "reconciliation": True,
                },
            )

            def execute_read(read_tool: str, read_input: dict[str, Any]) -> ToolResult:
                definition, _handler = self._get_registered_tool(read_tool)
                if not definition.is_read_tool:
                    return ToolResult.error("reconciliation callback only permits read tools")
                permission_error = self._check_tool_permissions(definition, permissions)
                if permission_error:
                    return ToolResult.error(permission_error)
                return self._execute_tool(ctx, read_tool, read_input, request_clients)

            observation = reconciler.reconcile(
                ReconciliationContext(
                    workflow=workflow,
                    item=item,
                    tool_context=ctx,
                    execute_read=execute_read,
                    resolve_read_tool=self._resolve_readback_definition,
                    resolve_tool=lambda tool_name: self._get_registered_tool(tool_name)[0]
                    if tool_name else None,
                )
            )
            if not isinstance(observation, ReconciliationObservation):
                raise TypeError("ProviderReconciler must return ReconciliationObservation")
            if int(observation.sequence) != int(item.get("sequence")):
                raise ValueError("ProviderReconciler returned a mismatched workflow sequence")
            if not observation.verified:
                raise ValueError("ProviderReconciler must return verified observations")
            payload = dict(observation.output_data or {})
            payload["_reconciliation"] = {
                "source": observation.source,
                "observed_at": observation.observed_at,
                "provider_resource_id": observation.provider_resource_id,
            }
            observations.append({
                "sequence": observation.sequence,
                "status": observation.status,
                "verified": True,
                "output_data": payload,
                "error": observation.error,
                "source": observation.source,
            })

        if not observations:
            self._session_manager.release_workflow_lease(
                workflow_id, self._workflow_lease_owner
            )
            raise ValueError("workflow has no pending items eligible for provider reconciliation")
        reconciled = self.reconcile_workflow(
            workflow_id,
            observations,
            user_id=effective_user_id,
            tenant_id=effective_tenant_id,
        )
        self._session_manager.release_workflow_lease(
            workflow_id, self._workflow_lease_owner
        )
        return reconciled

    def cancel_workflow(
        self, workflow_id: str, user_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """Cancel a non-terminal workflow without contacting a provider."""
        workflow = self.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
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
        keys = [
            "campaign_id", "ad_set_id", "adset_id", "ad_group_id", "adgroup_id",
            "creative_id", "io_id", "line_item_id", "ad_id",
        ]
        # Plugin resources may use a provider-specific identifier. Runtime
        # annotates it from the registered Tool contract; accept only a plain
        # identifier-shaped key so arbitrary result data cannot become shared
        # execution state.
        declared = result.data.get("resource_id_field") if isinstance(result.data, dict) else None
        if (
            isinstance(declared, str)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*_id", declared)
            and declared not in keys
        ):
            keys.append(declared)
        for key in keys:
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
