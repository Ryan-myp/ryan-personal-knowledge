"""
core/interfaces.py - 核心接口定义

借鉴 DAP Agent internal/core/interfaces.go
所有接口定义在这里，业务模块只依赖接口，不依赖具体实现。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional


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
    EXTERNAL_WRITE = "external_write"  # 外部平台写入

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
    # Provider contracts can be stricter than the fields needed to build a
    # dry-run plan.  Keep these requirements separate so dry-run remains useful
    # while live execution can fail before reaching a provider.
    provider_required: list[str] = field(default_factory=list)
    provider_any_of: list[list[str]] = field(default_factory=list)
    # Rules that cannot be represented by a flat ``required``/``enum`` pair.
    # The shape intentionally stays JSON-serializable because it is also
    # exposed to UI/LLM callers through /tools.
    conditional_rules: list[dict[str, Any]] = field(default_factory=list)
    # Tool inputs are closed by default.  A provider payload can explicitly
    # opt into open-ended fields at the field level (for example a targeting
    # object), but an undeclared top-level argument must never disappear
    # silently before execution.
    additional_properties: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the public, JSON-compatible tool contract."""
        return {
            "type": self.type,
            "required": list(self.required),
            "properties": self.properties,
            "provider_required": list(self.provider_required),
            "provider_any_of": [list(group) for group in self.provider_any_of],
            "conditional_rules": self.conditional_rules,
            "additional_properties": self.additional_properties,
        }

@dataclass
class ToolDefinition:
    """
    工具定义 - 对应 Go 的 core.ToolDefinition
    
    每个 Tool 必须属于某个 Skill 和 Platform，便于路由和权限控制。
    """
    name: str                              # 工具名称，全局唯一
    skill: str                             # 所属 Skill 名称
    platform: str                          # 所属平台（meta/google/tiktok/dv360）
    description: str                       # 工具描述（给 LLM 使用）
    input_schema: ToolSchema               # 输入参数 Schema
    risk_level: RiskLevel = RiskLevel.LOW  # 风险等级
    effect_class: ToolEffect = ToolEffect.READ  # 效果分类
    replay_policy: ReplayPolicy = ReplayPolicy.SAFE  # 重放策略
    traits: list[str] = field(default_factory=list)  # 额外特性标记
    # Whether a live adapter is implemented and approved for this tool.  A
    # false value still permits dry-run planning, but prevents a misleading
    # live confirmation/execution path.
    live_support: bool = True
    # Operational contract used by the Runtime before a handler is invoked.
    # These defaults keep existing Skills source-compatible while making the
    # limits visible to /tools and future policy implementations.
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1_000_000
    required_permissions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")

    @property
    def is_write_tool(self) -> bool:
        return self.effect_class in (ToolEffect.WRITE, ToolEffect.EXTERNAL_WRITE)

    @property
    def is_read_tool(self) -> bool:
        return self.effect_class == ToolEffect.READ


# ─── 执行结果 ───────────────────────────────────────────────────

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
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.requires_confirmation = requires_confirmation
        self.card_payload = card_payload
        self.simulated = simulated
    
    @classmethod
    def ok(cls, data: dict[str, Any]) -> "ToolResult":
        return cls(success=True, data=data)
    
    @classmethod
    def error(cls, message: str) -> "ToolResult":
        return cls(success=False, error=message)
    
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
            "requires_confirmation": self.requires_confirmation,
            "card_payload": self.card_payload,
            "simulated": self.simulated,
        }


# ─── 上下文 ─────────────────────────────────────────────────────

@dataclass
class ToolContext:
    """
    工具执行上下文 - 对应 Go 的 core.ToolContext
    
    包含执行所需的所有元信息，不绑定具体实现。
    """
    session_id: str
    user_id: str
    account_id: Optional[str] = None       # 当前广告账户 ID
    credentials: dict[str, Any] = field(default_factory=dict)  # 平台凭证（内存中，不持久化）
    protected_state: dict[str, Any] = field(default_factory=dict)  # 受保护状态（跨 Tool 调用保持）
    messages: list[dict] = field(default_factory=list)           # 对话历史
    metadata: dict[str, Any] = field(default_factory=dict)       # 扩展元数据
    
    def get_protected(self, key: str, default=None) -> Any:
        """获取跨 Tool 共享的受保护状态"""
        return self.protected_state.get(key, default)
    
    def set_protected(self, key: str, value: Any) -> None:
        """设置跨 Tool 共享的状态"""
        self.protected_state[key] = value


@dataclass(frozen=True)
class ReconciliationObservation:
    """A provider read-back result for one durable workflow item."""

    sequence: int
    status: str
    verified: bool
    source: str
    observed_at: str
    output_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    provider_resource_id: Optional[str] = None

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
        if self.provider_resource_id:
            result["provider_resource_id"] = self.provider_resource_id
        return result


@dataclass
class ReconciliationContext:
    """Safe callback surface exposed to a ProviderReconciler.

    A reconciler may perform only a read-tool call through Runtime. It does
    not receive a registry handler or a write-capable callback.
    """

    workflow: Mapping[str, Any]
    item: Mapping[str, Any]
    tool_context: ToolContext
    execute_read: Callable[[str, dict[str, Any]], ToolResult]


class ProviderReconciler(ABC):
    """Provider-owned adapter for resolving an uncertain write outcome."""

    @abstractmethod
    def reconcile(self, context: ReconciliationContext) -> ReconciliationObservation:
        """Read the provider and return a verified item observation."""
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


class ToolRegistry(ABC):
    """
    工具注册表接口 - 对应 Go 的 core.ToolRegistry
    
    所有工具的统一注册和执行入口。
    """
    @abstractmethod
    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """注册一个工具"""
        pass

    @abstractmethod
    def get(self, name: str) -> tuple[ToolDefinition, ToolHandler]:
        """获取工具定义和处理器"""
        pass

    @abstractmethod
    def list_by_platform(self, platform: str) -> list[ToolDefinition]:
        """列出某平台所有工具"""
        pass

    @abstractmethod
    def list_by_skill(self, skill_name: str) -> list[ToolDefinition]:
        """列出某 Skill 所有工具"""
        pass

    @abstractmethod
    def unregister(self, tool_name: str) -> None:
        """从注册表中移除工具"""
        pass

    @abstractmethod
    def execute(self, ctx: ToolContext, tool_name: str, input_data: dict[str, Any]) -> ToolResult:
        """执行工具"""
        pass


class Skill(ABC):
    """
    Skill 接口 - 对应 Go 的 core.Skill
    
    一个 Skill 是一组相关工具的集合，有明确的平台边界和能力描述。
    """
    @property
    def name(self) -> str:
        """Skill 名称"""
        raise NotImplementedError("Subclasses must implement 'name'")

    @property
    def platform(self) -> str:
        """所属平台"""
        raise NotImplementedError("Subclasses must implement 'platform'")

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
        1. 读取业务依赖（如凭证、配置）
        2. 创建工具处理器
        3. 向注册表注册工具
        4. 声明跨 Skill 路由规则
        5. 返回 CapabilityRuntime
        """
        pass


@dataclass
class CapabilityContext:
    """Capability 配置上下文"""
    registry: ToolRegistry
    skills: dict[str, Skill] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    session_store: Optional[Any] = None  # 会话存储（可选）


@dataclass
class CapabilityRuntime:
    """
    能力运行时声明 - 对应 Go 的 CapabilityRuntime
    
    业务模块向 Runtime 提交的能力清单，包含：
    - 自定义 Skill（跨平台编排能力）
    - 意图路由规则
    - 写入保护钩子
    - 后台任务
    """
    # 跨平台编排 Skill（如 ad-campaign-orchestrator）
    orchestrator_skills: list[Skill] = field(default_factory=list)
    
    # 意图 → 平台工具映射（供 IntentRouter 使用）
    intent_to_tools: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    # 格式：{"create_campaign": {"meta": ["meta_create_campaign", ...], "google": [...]}}
    
    # 写入前保护钩子（可选）
    write_guard: Optional["WriteGuard"] = None
    
    # 意图解析规则（可选，覆盖默认 LLM 解析）
    intent_rules: Optional[dict] = None
    
    # 后台任务（可选）
    background_tasks: list[dict] = field(default_factory=list)

    # Skill-owned parameter catalogs.  A catalog may expose static enums or
    # a dynamic lookup descriptor without making the shared Runtime know a
    # provider's field names.
    parameter_catalogs: list[Any] = field(default_factory=list)


class WriteGuard(ABC):
    """
    写入保护接口 - 对应 Go 的 core.WriteExecutionGuard
    
    在真正调用外部 API 之前，检查是否允许写入。
    可以检查幂等性、资源冲突、账户绑定等。
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


# ─── Intent 相关 ────────────────────────────────────────────────

@dataclass
class ParsedIntent:
    """
    解析后的用户意图 - 对应 Go 的 ParsedIntent / WorkflowTurnInput
    
    User Skill 输出的标准化意图，由 IntentRouter 转换为平台工具调用计划。
    """
    intent_type: str                  # 意图类型，如 "create_campaign"
    raw_input: str                    # 原始用户输入
    platforms: list[str]              # 目标平台列表
    objective: Optional[str] = None   # 投放目标
    campaign_type: Optional[str] = None  # 平台/业务 Campaign 类型
    budget: Optional[float] = None    # 预算
    duration_days: Optional[int] = None
    date_range: Optional[Any] = None  # 报表查询日期范围
    creative_materials: list[dict] = field(default_factory=list)
    # 各平台需要的参数
    platform_params: dict[str, dict] = field(default_factory=dict)
    # 格式：{"meta": {"campaign_name": "...", ...}, "google": {...}}
    
    def to_dict(self) -> dict:
        return {
            "intent_type": self.intent_type,
            "platforms": self.platforms,
            "objective": self.objective,
            "campaign_type": self.campaign_type,
            "budget": self.budget,
            "duration_days": self.duration_days,
            "date_range": self.date_range,
            "creative_materials": self.creative_materials,
            "platform_params": self.platform_params,
        }


class IntentParser(ABC):
    """
    意图解析器接口
    
    将自然语言输入转换为标准化的 ParsedIntent。
    默认实现使用 LLM，也可以注入自定义规则解析器。
    """
    @abstractmethod
    def parse(self, user_input: str, context: ToolContext) -> ParsedIntent:
        pass


class IntentRouter(ABC):
    """
    意图路由器接口 - 对应 Go 的 PlanningRouter / TurnRouter
    
    根据解析后的意图，查找各平台需要调用的工具。
    """
    @abstractmethod
    def route(self, intent: ParsedIntent, registry: ToolRegistry) -> dict[str, list[ToolDefinition]]:
        """
        返回：{platform: [ToolDefinition, ...]}
        例如：{"meta": [meta_create_campaign, meta_create_ad_set, ...], "google": [...]}
        """
        pass
