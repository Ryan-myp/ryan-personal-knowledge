"""
core/interfaces.py - 核心接口定义

借鉴 DAP Agent internal/core/interfaces.go
所有接口定义在这里，业务模块只依赖接口，不依赖具体实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, runtime_checkable

from .security import sha256_json
from .context import ContextQuery


# ─── 核心数据类型 ───────────────────────────────────────────────

class RiskLevel(Enum):
    """工具风险等级"""
    LOW = "low"           # 只读查询
    MEDIUM = "medium"     # 低风险写入
    HIGH = "high"         # 高风险写入
    CRITICAL = "critical" # 不可逆操作

class ToolEffect(Enum):
    """工具效果分类"""
    READ = "read"           # 纯读操作
    WRITE = "write"         # 写操作
    EXTERNAL_WRITE = "external_write"  # 外部系统写入

class ReplayPolicy(Enum):
    """重放策略"""
    SAFE = "safe"           # 可安全重放
    UNSAFE = "unsafe"       # 不可重放


class ExecutionMode(Enum):
    """Runtime 执行模式。

    dry_run 是默认模式：可以生成并校验写入计划，但绝不调用外部写 API。
    live 仅供后续人工指定测试账户时使用。
    """
    DRY_RUN = "dry_run"
    LIVE = "live"


# ─── Tool 定义 ──────────────────────────────────────────────────

@dataclass
class ToolSchema:
    """工具输入 Schema（简化版 JSON Schema）"""
    type: str = "object"
    required: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    # An execution adapter can be stricter than the fields needed to build a
    # dry-run plan. Keep these requirements separate so dry-run remains useful
    # while live execution can fail before reaching an external system.
    capability_required: list[str] = field(default_factory=list)
    capability_any_of: list[list[str]] = field(default_factory=list)
    # Some external operations require exactly one source variant (for example
    # a local file, URL, or existing asset ID). Keep this distinct from
    # ``capability_any_of``, which only guarantees that at least one is present.
    capability_exactly_one_of: list[list[str]] = field(default_factory=list)
    # Rules that cannot be represented by a flat ``required``/``enum`` pair.
    # The shape intentionally stays JSON-serializable because it is also
    # exposed to UI/LLM callers through /tools.
    conditional_rules: list[dict[str, Any]] = field(default_factory=list)
    # Tool inputs are closed by default. An extension payload can explicitly
    # opt into open-ended fields at the field level (for example a targeting
    # object), but an undeclared top-level argument must never disappear
    # silently before execution.
    additional_properties: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the public, JSON-compatible tool contract."""
        contract = {
            "type": self.type,
            "required": list(self.required),
            "properties": self.properties,
            "capability_required": list(self.capability_required),
            "capability_any_of": [list(group) for group in self.capability_any_of],
            "conditional_rules": self.conditional_rules,
            "additional_properties": self.additional_properties,
            "additionalProperties": self.additional_properties,
        }
        if self.capability_exactly_one_of:
            contract["capability_exactly_one_of"] = [
                list(group) for group in self.capability_exactly_one_of
            ]
        return contract

@dataclass
class ToolDefinition:
    """
    工具定义 - 对应 Go 的 core.ToolDefinition
    
    每个 Tool 属于一个由扩展声明的 namespace，便于路由和权限控制。
    """
    name: str                              # 工具名称，全局唯一
    skill: str                             # 所属 Skill 名称
    namespace: str                          # Publisher namespace
    description: str                       # 工具描述（给 LLM 使用）
    input_schema: ToolSchema               # 输入参数 Schema
    # Self-description used by the planner. A Tool declares what it acts on;
    # the Runtime can then discover the right Tool without a central
    # intent->tool table. These are required Capability/Skill-owned contract
    # fields; Core never derives them from a tool name.
    action: str = ""
    resource_type: str = ""
    parent_resource_type: Optional[str] = None
    intent_types: list[str] = field(default_factory=list)
    # Natural-language aliases are owned by the Tool/Skill publisher. Core
    # may use them for constrained offline parsing, but never invents a
    # integration or business vocabulary of its own.
    intent_aliases: list[str] = field(default_factory=list)
    # Optional advisory Skill bindings published by the Tool owner. These
    # bindings narrow which managed Skill packages are loaded as context; they
    # never grant execution permission and never turn a Skill into a Tool.
    skill_refs: list[str] = field(default_factory=list)
    # Publisher-owned routing predicates. A Tool can publish a conditional
    # creation-chain membership without adding an integration branch to Router.
    # Each rule is JSON-serializable and is evaluated against ParsedIntent and
    # the namespace's structured parameters.
    activation_rules: list[dict[str, Any]] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW  # 风险等级
    effect_class: ToolEffect = ToolEffect.READ  # 效果分类
    # Unsafe is the default for writes.  A ToolDefinition constructed by a
    # newly added Capability/Skill must not accidentally become replayable
    # just because its author omitted this field.
    replay_policy: Optional[ReplayPolicy] = None  # 重放策略
    traits: list[str] = field(default_factory=list)  # 额外特性标记
    # Whether a live adapter is implemented and approved for this tool.  A
    # false value still permits dry-run planning, but prevents a misleading
    # live confirmation/execution path.
    # Live writes are opt-in. A newly added Tool that forgets to declare a
    # verified external adapter remains dry-run-only by default.
    # Read tools are live by default; write tools must opt in explicitly.
    live_support: Optional[bool] = None
    # Operational contract used by the Runtime before a handler is invoked.
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1_000_000
    required_permissions: list[str] = field(default_factory=list)
    # Publisher-owned scope metadata. The Core treats scope as opaque; an
    # application adapter decides how to resolve and authorize it.
    scope_type: Optional[str] = None
    scope_fields: list[str] = field(default_factory=list)
    scope_required: bool = False
    # A live effect may require an application-specific permission. Keeping it
    # on the Tool contract prevents the generic Runtime from inventing a
    # domain permission such as ``ads.write``.
    live_permission: Optional[str] = None
    # External systems do not agree on identifier spelling. Keep wire names on the Tool
    # contract so Runtime can persist and connect resources without knowing a
    # integration hierarchy. Mutating Tools must declare the identity they
    # create or address; Runtime never derives it from resource_type.
    resource_id_field: Optional[str] = None
    parent_resource_id_field: Optional[str] = None
    # Optional explicit read-back edge for an uncertain write.  The Runtime
    # validates and invokes this read Tool, but never derives its name from
    # the write Tool name. This is especially important when an integration has
    # multiple get variants for the same logical resource.
    readback_tool: Optional[str] = None
    # If the remote system accepts a caller-supplied idempotency field, the
    # Tool publisher may declare it. Runtime treats this as contract metadata;
    # it never invents a remote field or uses an internal request ID as a
    # remote resource identifier.
    idempotency_key_field: Optional[str] = None
    # Version metadata is descriptive contract data, not routing logic. An
    # integration can publish a new adapter contract while keeping the stable
    # Tool name; Runtime and Router do not need an integration-specific
    # edit for that upgrade.
    contract_version: str = "1"
    integration_api_version: Optional[str] = None
    # Result-shape metadata is owned by the Tool publisher.  Cross-feature
    # extensions can consume a normalized resource result without guessing a
    # integration result key or identifier spelling from its Tool name.
    result_items_key: Optional[str] = None
    result_id_fields: list[str] = field(default_factory=list)
    related_resource_type: Optional[str] = None
    related_resource_id_fields: list[str] = field(default_factory=list)
    # Immutable fingerprint of the public input contract.  It is calculated
    # from ToolSchema rather than vendor/channel names, so Registry and
    # approval code can detect schema drift without a central router.
    contract_hash: str = ""

    def __post_init__(self) -> None:
        from .namespace import normalize_namespace

        self.namespace = normalize_namespace(self.namespace)
        if not self.namespace:
            raise ValueError(f"Tool '{self.name}' requires a non-empty namespace")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        self.scope_type = str(self.scope_type or "").strip() or None
        self.scope_fields = list(dict.fromkeys(
            str(item).strip() for item in (self.scope_fields or [])
            if str(item).strip()
        ))
        self.scope_required = bool(self.scope_required)
        self.live_permission = (
            str(self.live_permission).strip()
            if self.live_permission is not None and str(self.live_permission).strip()
            else None
        )
        self.contract_version = str(self.contract_version or "1")
        if self.integration_api_version is not None:
            self.integration_api_version = str(self.integration_api_version)
        calculated_contract_hash = sha256_json(
            self.input_schema.to_dict() if self.input_schema else None
        )
        if self.contract_hash and str(self.contract_hash) != calculated_contract_hash:
            raise ValueError(
                f"Tool '{self.name}' contract_hash does not match input_schema"
            )
        self.contract_hash = calculated_contract_hash
        if self.live_support is None:
            self.live_support = not self.is_write_tool
        if self.replay_policy is None:
            self.replay_policy = (
                ReplayPolicy.UNSAFE if self.is_write_tool else ReplayPolicy.SAFE
            )
        elif isinstance(self.replay_policy, str):
            try:
                self.replay_policy = ReplayPolicy(self.replay_policy.lower())
            except ValueError as exc:
                raise ValueError(
                    f"Unsupported replay_policy: {self.replay_policy}"
                ) from exc
        if self.is_write_tool and self.replay_policy != ReplayPolicy.UNSAFE:
            raise ValueError("write tools must use ReplayPolicy.UNSAFE")
        self.action = str(self.action or "").strip().lower()
        self.resource_type = self._normalize_resource(self.resource_type)
        if self.parent_resource_type:
            self.parent_resource_type = self._normalize_resource(
                self.parent_resource_type
            )
        if self.readback_tool is not None:
            self.readback_tool = str(self.readback_tool).strip() or None
        if self.idempotency_key_field is not None:
            self.idempotency_key_field = str(self.idempotency_key_field).strip() or None
        if self.result_items_key is not None:
            self.result_items_key = str(self.result_items_key).strip() or None
        self.result_id_fields = list(dict.fromkeys(
            str(item).strip() for item in self.result_id_fields if str(item).strip()
        ))
        if self.related_resource_type:
            self.related_resource_type = self._normalize_resource(
                self.related_resource_type
            )
        self.related_resource_id_fields = list(dict.fromkeys(
            str(item).strip()
            for item in self.related_resource_id_fields if str(item).strip()
        ))
        self.intent_types = list(dict.fromkeys(str(item) for item in self.intent_types))
        self.intent_aliases = list(dict.fromkeys(
            str(item).strip() for item in self.intent_aliases if str(item).strip()
        ))
        self.skill_refs = list(dict.fromkeys(
            str(item).strip() for item in self.skill_refs if str(item).strip()
        ))

    def routing_metadata_errors(self) -> list[str]:
        """Return missing self-description fields without Core inference.

        Construction remains permissive for low-level registry/unit-test
        fixtures. Capability and Skill registration boundaries call this
        method and fail closed before exposing an incomplete executable Tool.
        """
        errors = []
        if not self.action:
            errors.append("action")
        if not self.resource_type:
            errors.append("resource_type")
        if not self.intent_types:
            errors.append("intent_types")
        if self.action in {"create", "update", "delete", "pause", "resume", "enable", "disable"} and not self.resource_id_field:
            errors.append("resource_id_field")
        if self.parent_resource_type and not self.parent_resource_id_field:
            errors.append("parent_resource_id_field")
        return errors

    @staticmethod
    def _normalize_resource(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")

    def add_intents(self, intents: list[str] | tuple[str, ...] | set[str]) -> None:
        self.intent_types = list(dict.fromkeys(self.intent_types + [str(item) for item in intents]))

    @property
    def is_write_tool(self) -> bool:
        return self.effect_class in (ToolEffect.WRITE, ToolEffect.EXTERNAL_WRITE)

    @property
    def is_read_tool(self) -> bool:
        return self.effect_class == ToolEffect.READ

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "skill": self.skill, "namespace": self.namespace,
            "description": self.description, "action": self.action,
            "resource_type": self.resource_type,
            "parent_resource_type": self.parent_resource_type,
            "intent_types": list(self.intent_types),
            "intent_aliases": list(self.intent_aliases),
            "skill_refs": list(self.skill_refs),
            "activation_rules": [dict(rule) for rule in self.activation_rules],
            "risk_level": self.risk_level.value,
            "effect_class": self.effect_class.value, "replay_policy": self.replay_policy.value,
            "traits": list(self.traits), "live_support": self.live_support,
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "required_permissions": list(self.required_permissions),
            "scope_type": self.scope_type,
            "scope_fields": list(self.scope_fields),
            "scope_required": self.scope_required,
            "live_permission": self.live_permission,
            "resource_id_field": self.resource_id_field,
            "parent_resource_id_field": self.parent_resource_id_field,
            "readback_tool": self.readback_tool,
            "idempotency_key_field": self.idempotency_key_field,
            "contract_version": self.contract_version,
            "integration_api_version": self.integration_api_version,
            "result_items_key": self.result_items_key,
            "result_id_fields": list(self.result_id_fields),
            "related_resource_type": self.related_resource_type,
            "related_resource_id_fields": list(self.related_resource_id_fields),
            "contract_hash": self.contract_hash,
            "input_schema": self.input_schema.to_dict() if self.input_schema else None,
        }


# ─── 执行结果 ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ToolError:
    """Structured, application-neutral error classification.

    ``ToolResult.error`` remains a human-readable string for API consumers;
    callers that need recovery semantics should use ``error_detail``.
    """

    category: str
    code: str
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class WriteReservation:
    """Binding returned by a write guard until an external result is known."""

    idempotency_key: str
    request_hash: str
    tool_name: str
    scope_key: str


class ToolResult:
    """工具执行结果 - 使用普通类避免 dataclass 字段/方法名冲突"""
    
    def __init__(
        self,
        success: bool,
        data: dict[str, Any] = None,
        error: Optional[str] = None,
        requires_confirmation: bool = False,
        card_payload: Optional[dict] = None,
        simulated: bool = False,
        error_detail: Optional[ToolError] = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.error_detail = error_detail
        self.requires_confirmation = requires_confirmation
        self.card_payload = card_payload
        self.simulated = simulated
    
    @classmethod
    def ok(cls, data: dict[str, Any]) -> "ToolResult":
        return cls(success=True, data=data)
    
    @classmethod
    def error(
        cls, message: str, *, detail: Optional[ToolError] = None,
    ) -> "ToolResult":
        return cls(success=False, error=message, error_detail=detail)
    
    @classmethod
    def needs_confirmation(cls, card_payload: dict) -> "ToolResult":
        return cls(success=True, requires_confirmation=True, card_payload=card_payload)

    @classmethod
    def dry_run(cls, data: dict[str, Any]) -> "ToolResult":
        """返回未触发外部 API 的模拟执行结果。"""
        return cls(success=True, data=data, simulated=True)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_detail": (
                self.error_detail.to_dict() if self.error_detail else None
            ),
            "requires_confirmation": self.requires_confirmation,
            "card_payload": self.card_payload,
            "simulated": self.simulated,
        }


# ─── 上下文 ─────────────────────────────────────────────────────

@dataclass(init=False)
class ToolContext:
    """Opaque execution context shared with a Tool handler."""
    session_id: str
    user_id: str
    scope: dict[str, Any]
    credentials: dict[str, Any]
    protected_state: dict[str, Any]
    messages: list[dict]
    metadata: dict[str, Any]

    def __init__(
        self,
        session_id: str,
        user_id: str,
        scope: Optional[Mapping[str, Any]] = None,
        credentials: Optional[Mapping[str, Any]] = None,
        protected_state: Optional[Mapping[str, Any]] = None,
        messages: Optional[list[dict]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        **extensions: Any,
    ) -> None:
        """Create a context with an opaque application scope.

        The Core stores scope values without naming their vocabulary.  An
        embedding may expose a convenience value through the extension map
        (for example a workspace selector) without adding it to this contract.
        """
        self.session_id = str(session_id)
        self.user_id = str(user_id)
        self.scope = dict(scope or {}) if isinstance(scope, Mapping) else {}
        self.scope.update(extensions)
        self.credentials = dict(credentials or {})
        self.protected_state = dict(protected_state or {})
        self.messages = list(messages or [])
        self.metadata = dict(metadata or {})

    def __getattr__(self, name: str) -> Any:
        scope = self.__dict__.get("scope", {})
        if name in scope:
            return scope[name]
        raise AttributeError(name)
    
    def get_protected(self, key: str, default=None) -> Any:
        """获取跨 Tool 共享的受保护状态"""
        return self.protected_state.get(key, default)
    
    def set_protected(self, key: str, value: Any) -> None:
        """设置跨 Tool 共享的状态"""
        self.protected_state[key] = value


@dataclass(frozen=True)
class ReconciliationObservation:
    """An external read-back result for one durable workflow item."""

    sequence: int
    status: str
    verified: bool
    source: str
    observed_at: str
    output_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    external_resource_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "sequence": int(self.sequence),
            "status": self.status,
            "verified": bool(self.verified),
            "source": self.source,
            "observed_at": self.observed_at,
            "output_data": self.output_data,
            "error": self.error,
        }
        if self.external_resource_id:
            result["external_resource_id"] = self.external_resource_id
        return result


@dataclass
class ReconciliationContext:
    """Safe callback surface exposed to an EffectReconciler.

    A reconciler may perform only a read-tool call through Runtime. It does
    not receive a registry handler or a write-capable callback.
    """

    workflow: Mapping[str, Any]
    item: Mapping[str, Any]
    tool_context: ToolContext
    execute_read: Callable[[str, dict[str, Any]], ToolResult]
    # Optional Runtime-owned metadata lookup. Effect reconcilers can use it
    # to discover the matching read Tool without a shared integration table.
    resolve_read_tool: Optional[Callable[[str], Any]] = None


class EffectReconciler(ABC):
    """Extension-owned adapter for resolving an uncertain external effect."""

    @abstractmethod
    def reconcile(self, context: ReconciliationContext) -> ReconciliationObservation:
        """Read the external system and return a verified item observation."""
        pass


@dataclass
class ChatMessage:
    """对话消息"""
    role: str          # "user" | "assistant" | "tool" | "system"
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    internal: bool = False  # 系统内部消息


# ─── 核心接口 ───────────────────────────────────────────────────

class ToolHandler(ABC):
    """
    工具处理器接口 - 对应 Go 的 core.ToolHandler
    
    业务实现此接口来定义工具的具体行为。
    """
    @abstractmethod
    def execute(self, ctx: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        """执行工具，返回结果"""
        pass


@runtime_checkable
class ToolCatalog(Protocol):
    """Read-only catalog surface used by parsers and routers.

    Routing needs definitions only. Keeping this port separate from the
    executable registry prevents a parser/router implementation from gaining
    access to handlers, registration, or direct execution merely because it
    needs to discover a Tool.
    """

    def list_by_namespace(self, namespace: str) -> list[ToolDefinition]:
        """Return the active Tool definitions in one namespace."""
        ...


class ToolRegistry(ABC):
    """
    工具注册表接口 - 对应 Go 的 core.ToolRegistry
    
    所有工具的统一注册和执行入口。
    """
    @abstractmethod
    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """注册一个工具"""
        pass

    def register_binding(self, binding: "ToolBinding") -> None:
        """Register a Tool contract and its application-neutral executor."""
        self.register(binding.definition, binding.executor)

    def register_source(self, source: "ToolSource") -> list[str]:
        """Register a complete source snapshot as one lifecycle operation."""
        raise NotImplementedError

    @abstractmethod
    def get(self, name: str) -> tuple[ToolDefinition, ToolHandler]:
        """获取工具定义和处理器"""
        pass

    @abstractmethod
    def list_by_namespace(self, namespace: str) -> list[ToolDefinition]:
        """列出某 namespace 的所有工具"""
        pass

    @abstractmethod
    def list_by_skill(self, skill_name: str) -> list[ToolDefinition]:
        """列出某 Skill 所有工具"""
        pass

    @abstractmethod
    def unregister(self, tool_name: str) -> None:
        """从注册表中移除工具"""
        pass

    def unregister_source(self, source_id: str) -> list[str]:
        """Remove all Tools owned by one source."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, ctx: ToolContext, tool_name: str, input_data: dict[str, Any]) -> ToolResult:
        """执行工具"""
        pass


class KnowledgeSource(Protocol):
    """Read-only advisory context source used by the generic selector."""

    def query_context(self, query: ContextQuery) -> Sequence[Any]:
        """Return records for the application-neutral query contract."""
        ...

    def query(
        self,
        query: str,
        *,
        namespaces: Optional[Sequence[str]] = None,
        intent_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 4,
        max_excerpt_chars: int = 1200,
    ) -> Sequence[Any]:
        """Return bounded context records for the requested namespaces."""
        ...


class Skill(ABC):
    """
    Skill 接口 - 对应 Go 的 core.Skill
    
    一个 Skill 是一组相关工具的集合，有明确的 namespace 边界和能力描述。
    """
    @property
    def name(self) -> str:
        """Skill 名称"""
        raise NotImplementedError("Subclasses must implement 'name'")

    @property
    def namespace(self) -> str:
        """所属 namespace"""
        raise NotImplementedError("Subclasses must implement 'namespace'")

    @property
    def namespace_aliases(self) -> list[str]:
        """Natural-language namespace aliases published by this Skill."""
        return []

    @property
    def description(self) -> str:
        """Skill 描述（给 LLM 使用）"""
        raise NotImplementedError("Subclasses must implement 'description'")

    def get_tools(self) -> list[ToolDefinition]:
        """返回此 Skill 注册的所有工具定义"""
        raise NotImplementedError("Subclasses must implement 'get_tools'")

    def get_tool_handler(self, tool_name: str) -> Optional[ToolHandler]:
        """返回指定工具的执行器"""
        raise NotImplementedError("Subclasses must implement 'get_tool_handler'")

class CapabilityModule(ABC):
    """
    能力模块接口 - 对应 Go 的 internal/capabilities/contract/runtime.go
    
    业务模块通过此接口向运行时声明自己的能力和扩展点。
    这是 DAP 架构的核心抽象：业务不直接操作 Runtime，而是通过接口注入能力。
    """
    @abstractmethod
    def configure(self, context: "CapabilityContext") -> "CapabilityRuntime":
        """
        配置并返回能力运行时。
        
        职责：
        1. 读取扩展依赖（如凭证、配置）
        2. 创建工具处理器
        3. 向注册表注册工具
        4. 返回 CapabilityRuntime 生命周期声明
        """
        pass


@dataclass
class CapabilityContext:
    """Capability 配置上下文"""
    registry: ToolRegistry
    config: dict[str, Any] = field(default_factory=dict)
    session_store: Optional[Any] = None  # 会话存储（可选）


@dataclass
class CapabilityRuntime:
    """
    能力运行时声明 - 对应 Go 的 CapabilityRuntime
    
    业务模块向 Runtime 提交的能力生命周期声明。

    流程和路由归 Skill 所有；Capability 只提供原子 Tool、输入契约
    以及必要的运行时扩展点。
    """
    # 写入前保护钩子（可选）
    write_guard: Optional["WriteGuard"] = None

    # 后台任务（可选）
    background_tasks: list[dict] = field(default_factory=list)

    # Skill-owned parameter catalogs.  A catalog may expose static enums or
    # a dynamic lookup descriptor without making the shared Runtime know a
    # integration field names.
    parameter_catalogs: list[Any] = field(default_factory=list)

class WriteGuard(ABC):
    """
    写入保护接口 - 对应 Go 的 core.WriteExecutionGuard
    
    在真正调用外部 API 之前，检查是否允许写入。
    可以检查幂等性、资源冲突、作用域绑定等。
    """
    @abstractmethod
    def reserve_write(
        self,
        ctx: ToolContext,
        tool_def: ToolDefinition,
        input_data: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        返回 (是否允许, 拒绝原因)
        """
        pass

    def finalize(
        self, reservation: WriteReservation, result: ToolResult,
    ) -> None:
        """Finalize a reservation after the external outcome is known."""
        return None


# ─── Intent 相关 ────────────────────────────────────────────────

@dataclass(init=False)
class ParsedIntent:
    """Application-neutral intent envelope.

    The Core parser and router need only an intent name, a raw request, target
    namespaces and opaque publisher-owned values.  Domain fields must live in
    ``attributes`` (intent-level values) or ``scoped_parameters`` (values
    belonging to a registered namespace/Tool schema).  This prevents Core
    from accumulating one field per application workflow or control-plane
    feature.

    ``**extensions`` is intentionally data-only.  It lets a Skill/Feature
    publish a structured value without changing this class, while the
    application can still access it through ``intent.attributes``.
    ``scoped_parameters`` and dynamic attribute access remain generic
    structural extension points; neither contains a domain map.
    """
    intent_type: str
    raw_input: str
    namespaces: list[str]
    attributes: dict[str, Any]
    parameters: dict[str, Any]
    scoped_parameters: dict[str, dict[str, Any]]
    metadata: dict[str, Any]

    def __init__(
        self,
        intent_type: str,
        raw_input: str,
        namespaces: list[str] | tuple[str, ...] | None,
        *,
        attributes: Optional[Mapping[str, Any]] = None,
        parameters: Optional[Mapping[str, Any]] = None,
        scoped_parameters: Optional[Mapping[str, Mapping[str, Any]]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        **extensions: Any,
    ) -> None:
        self.intent_type = str(intent_type or "chat")
        self.raw_input = str(raw_input or "")
        self.namespaces = [str(item) for item in (namespaces or []) if str(item).strip()]
        self.attributes = dict(attributes or {})
        # Top-level extension values are folded into the generic envelope.
        # No Core field-name allowlist is needed because these values are not
        # executable; Tool schemas remain the only executable input contract.
        self.attributes.update(extensions)
        self.parameters = dict(parameters or {})
        selected = scoped_parameters
        self.scoped_parameters = {
            str(namespace): dict(values or {})
            for namespace, values in (selected or {}).items()
            if isinstance(values, Mapping)
        }
        self.metadata = dict(metadata or {})

    def __getattr__(self, name: str) -> Any:
        """Allow application extensions to be read without Core field maps."""
        attributes = self.__dict__.get("attributes", {})
        if name in attributes:
            return attributes[name]
        # An extension is optional by definition.  Returning ``None`` keeps
        # ``getattr(intent, name, None)`` useful for application-owned fields
        # without adding a Core-owned vocabulary or field registry.
        return None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "intent_type": self.intent_type,
            "raw_input": self.raw_input,
            "namespaces": list(self.namespaces),
            "attributes": dict(self.attributes),
            "parameters": dict(self.parameters),
            "scoped_parameters": {
                key: dict(value) for key, value in self.scoped_parameters.items()
            },
            "metadata": dict(self.metadata),
        }
        # Flat extension keys are useful to declarative activation rules and
        # preserve a simple JSON shape for application renderers.  The set is
        # owned by the publisher, not by Core.
        result.update(self.attributes)
        return result


class IntentParser(ABC):
    """
    意图解析器接口
    
    将自然语言输入转换为标准化的 ParsedIntent。
    生产 Runtime 使用 LLM；测试或显式嵌入场景可以注入自定义解析器。
    """
    @abstractmethod
    def parse(self, user_input: str, context: ToolContext) -> ParsedIntent:
        pass

    def register_tool_definitions(
        self, definitions: list[ToolDefinition] | tuple[ToolDefinition, ...]
    ) -> None:
        """Receive the current Tool catalog for model-backed intent parsing."""
        return None

    def refresh_tool_catalog(
        self, definitions: list[ToolDefinition] | tuple[ToolDefinition, ...]
    ) -> None:
        """Replace the parser's discoverable Tool catalog after a lifecycle change."""
        self.register_tool_definitions(definitions)

    def register_namespace_aliases(
        self, namespace: str, aliases: list[str] | set[str]
    ) -> None:
        """Publish Skill-owned display aliases for parser context."""
        return None

    def register_intent_descriptors(
        self, descriptors: Mapping[str, Mapping[str, Any]]
    ) -> None:
        """Publish Feature-owned language descriptors."""
        return None

    def extract_parameters(
        self, user_input: str, namespaces: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Extract only explicitly declared parameters for a continuation turn."""
        return {}

    def repair_for_routing(
        self, user_input: str, context: ToolContext, previous: ParsedIntent
    ) -> Optional[ParsedIntent]:
        """Optionally repair a model result against the active Tool catalog."""
        return None

    def model_client(self) -> Any:
        """Return the injected model client, if this parser uses one."""
        return None


class IntentRouter(ABC):
    """
    意图路由器接口 - 对应 Go 的 PlanningRouter / TurnRouter
    
    根据解析后的意图，查找各 namespace 需要调用的工具。
    """
    @abstractmethod
    def route(self, intent: ParsedIntent, registry: ToolCatalog) -> dict[str, list[ToolDefinition]]:
        """
        返回：{namespace: [ToolDefinition, ...]}
        例如：{"namespace-a": [tool_a, tool_b], "namespace-b": [...]}
        """
        pass
