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
    # Self-description used by the planner.  A Tool declares what it acts on;
    # the Runtime can then discover the right Tool without a central
    # intent->tool table.  The defaults intentionally support existing Tools:
    # ``__post_init__`` derives metadata from the conventional tool name and
    # traits when a provider has not filled it explicitly.
    action: str = ""
    resource_type: str = ""
    parent_resource_type: Optional[str] = None
    intent_types: list[str] = field(default_factory=list)
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
        self.action, self.resource_type = self._derive_resource_metadata(
            self.action, self.resource_type
        )
        if not self.parent_resource_type:
            self.parent_resource_type = {
                "ad_set": "campaign", "ad_group": "campaign", "io": "campaign",
                "line_item": "io", "asset_group": "campaign",
                # Provider-specific parent relationships must be declared by
                # the Capability.  The generic fallback keeps existing
                # non-Meta providers usable without making the core platform
                # aware; Meta's Ad Tool declares ``ad_set`` explicitly.
                "ad": "ad_group",
            }.get(self.resource_type)
        if self.parent_resource_type:
            self.parent_resource_type = self._normalize_resource(
                self.parent_resource_type
            )
        self.intent_types = list(dict.fromkeys(str(item) for item in self.intent_types))
        if not self.intent_types:
            self.intent_types = self._derive_intents()

    @staticmethod
    def _normalize_resource(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
        aliases = {
            "adset": "ad_set", "ad_group": "ad_group", "adgroup": "ad_group",
            "lineitem": "line_item", "assetgroup": "asset_group",
            "audiences": "audience", "creatives": "creative",
            "videos": "video", "images": "image", "locations": "location",
            "devices": "device", "catalogs": "catalog",
        }
        return aliases.get(normalized, normalized)

    def _derive_resource_metadata(self, action: str, resource: str) -> tuple[str, str]:
        name = self.name.lower().replace("-", "_")
        tokens = name.split("_")
        known_actions = (
            "create", "list", "get", "update", "delete", "pause", "resume",
            "enable", "disable", "boost", "report", "export", "download",
            "estimate", "validate", "auth", "track", "send", "run",
        )
        derived_action = str(action or "").lower()
        if not derived_action and "spark" in tokens:
            derived_action = "boost"
        if not derived_action:
            if "report" in tokens or name.endswith("_export_report") or name.endswith("_download_report"):
                derived_action = "report"
            elif name.endswith("_create"):
                derived_action = "create"
        if not derived_action:
            for token in tokens:
                if token in known_actions:
                    derived_action = token
                    break
            if not derived_action and "spark" in tokens:
                derived_action = "boost"
        normalized_resource = self._normalize_resource(resource)
        if not normalized_resource:
            patterns = (
                ("line_item", "line_item"), ("asset_group", "asset_group"),
                ("ad_set", "ad_set"), ("adset", "ad_set"),
                ("ad_group", "ad_group"), ("adgroup", "ad_group"),
                ("campaign", "campaign"), ("creative", "creative"),
                ("audience", "audience"), ("conversion", "conversion"),
                ("keywords", "keyword"), ("keyword", "keyword"),
                ("location", "location"), ("device", "device"),
                ("catalog", "catalog"), ("app", "app"), ("video", "video"),
                ("image", "image"), ("brand_safety", "brand_safety"),
                ("post", "post"), ("flight", "flight"), ("io", "io"),
                ("advertiser", "advertiser"), ("report", "report"),
                ("ads", "ad"),
            )
            for marker, value in patterns:
                if marker in name:
                    normalized_resource = value
                    break
            if not normalized_resource:
                for token in reversed(tokens):
                    if token not in known_actions and token not in {"meta", "google", "ads", "tiktok", "dv360", "spark"}:
                        normalized_resource = self._normalize_resource(token)
                        break
        return derived_action or "custom", normalized_resource or "resource"

    def _derive_intents(self) -> list[str]:
        action = self.action
        resource = self.resource_type
        if resource == "post" or action == "boost":
            return ["boost_post"]
        if action in {"report", "export", "download"} or resource == "report":
            return ["download_report"]
        if action == "create":
            return {
                "campaign": ["create_campaign"],
                "ad_set": ["create_campaign"], "ad_group": ["create_campaign"],
                "ad": ["create_campaign"], "io": ["create_campaign"],
                "line_item": ["create_campaign"],
                "asset_group": ["create_asset_group"],
                "creative": ["create_creative"],
            }.get(resource, [])
        if action in {"pause", "disable"} and resource == "campaign":
            return ["pause_campaign", "cross_channel_batch_pause"]
        if action in {"resume", "enable"} and resource == "campaign":
            return ["resume_campaign", "cross_channel_batch_resume"]
        if action == "update":
            return {
                "campaign": ["update_campaign", "pause_campaign", "resume_campaign", "cross_channel_batch_pause", "cross_channel_batch_resume", "cross_channel_batch_update_budget"],
                "ad_set": ["update_adset"], "ad_group": ["update_adgroup"],
                "ad": ["update_ad"], "io": ["update_io"],
                "line_item": ["update_line_item"],
                "asset_group": ["update_asset_group"],
            }.get(resource, [])
        if action == "list":
            return {
                "campaign": ["list_campaigns", "cross_channel_overview", "cross_channel_compare", "cross_channel_performance_insights", "cross_channel_optimize_budget", "cross_channel_export_report"],
                "ad_set": ["list_adsets", "list_adgroups"],
                "ad_group": ["list_adgroups"], "ad": ["list_ads"],
                "audience": ["list_audiences"], "io": ["list_ios"],
                "line_item": ["list_line_items"], "asset_group": ["list_asset_groups"],
                "creative": ["list_creatives"],
                "video": ["list_videos"], "image": ["list_images"],
                "keyword": ["list_keywords"], "conversion": ["list_conversions"],
                "location": ["list_locations"], "device": ["list_devices"],
                "catalog": ["list_catalogs"], "app": ["list_apps"],
                "brand_safety": ["list_brand_safety"], "advertiser": ["list_advertisers"],
            }.get(resource, [])
        if action == "get":
            return {
                "campaign": ["get_campaign"], "io": ["get_io"],
                "line_item": ["get_line_item"], "asset_group": ["get_asset_group"],
                "ad_set": ["get_adset"], "ad_group": ["get_adgroup"],
                "ad": ["get_ad"],
            }.get(resource, [])
        return []

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
            "name": self.name, "skill": self.skill, "platform": self.platform,
            "description": self.description, "action": self.action,
            "resource_type": self.resource_type,
            "parent_resource_type": self.parent_resource_type,
            "intent_types": list(self.intent_types), "risk_level": self.risk_level.value,
            "effect_class": self.effect_class.value, "replay_policy": self.replay_policy.value,
            "traits": list(self.traits), "live_support": self.live_support,
            "required_permissions": list(self.required_permissions),
            "input_schema": self.input_schema.to_dict() if self.input_schema else None,
        }


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


RESOURCE_RESULT_STATUSES = frozenset({
    "planned", "running", "succeeded", "failed", "skipped", "unknown",
    "unsupported", "awaiting_confirmation",
})


@dataclass
class ResourceResult:
    """Uniform item-level result for campaign hierarchy operations.

    Provider adapters may return different identifier shapes, but callers
    should be able to consume one stable model for Campaign, Ad Set/Ad Group,
    Ad, IO, Line Item, Creative and Asset Group operations.  ``logical`` and
    ``local`` identifiers are safe planning identifiers; only
    ``provider_resource_id`` represents a confirmed provider object.
    """

    sequence: int
    platform: str
    resource_type: str
    tool_name: str
    status: str
    account_id: Optional[str] = None
    parent_sequence: Optional[int] = None
    parent_resource_id: Optional[str] = None
    provider_resource_id: Optional[str] = None
    logical_resource_id: Optional[str] = None
    local_resource_id: Optional[str] = None
    error: Optional[str] = None
    simulated: bool = False

    def __post_init__(self) -> None:
        if self.status not in RESOURCE_RESULT_STATUSES:
            raise ValueError(f"Unsupported resource result status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "platform": self.platform,
            "resource_type": self.resource_type,
            "tool": self.tool_name,
            "status": self.status,
            "account_id": self.account_id,
            "parent_sequence": self.parent_sequence,
            "parent_resource_id": self.parent_resource_id,
            "provider_resource_id": self.provider_resource_id,
            "logical_resource_id": self.logical_resource_id,
            "local_resource_id": self.local_resource_id,
            "error": self.error,
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
    # Optional Runtime-owned metadata lookup. Provider reconcilers can use it
    # to discover the matching read Tool without a shared provider table.
    resolve_read_tool: Optional[Callable[[str], Any]] = None


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

    def get_workflows(self) -> dict[str, "SkillWorkflow"]:
        """Optional special-case DAGs; normal routing does not require them."""
        return {}

    def get_workflow_mappings(self) -> dict[str, dict[str, list[str]]]:
        """Deprecated compatibility projection for external special cases."""
        return {
            name: workflow.tool_mapping()
            for name, workflow in self.get_workflows().items()
        }


@dataclass(frozen=True)
class SkillWorkflowStep:
    """One declarative step in a Skill workflow.

    A step names a Tool but never contains executable code.  ``when`` and
    ``depends_on`` are deterministic data used by Runtime/Router to build a
    bounded plan; authorization and side-effect policy remain Runtime-owned.
    """

    id: str
    tool: str
    platform: Optional[str] = None
    depends_on: tuple[str, ...] = ()
    when: Mapping[str, Any] = field(default_factory=dict)
    required_inputs: tuple[str, ...] = ()
    input_mapping: Mapping[str, str] = field(default_factory=dict)
    output_mapping: Mapping[str, str] = field(default_factory=dict)
    on_error: str = "stop"
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "platform": self.platform,
            "depends_on": list(self.depends_on),
            "when": dict(self.when),
            "required_inputs": list(self.required_inputs),
            "input_mapping": dict(self.input_mapping),
            "output_mapping": dict(self.output_mapping),
            "on_error": self.on_error,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass(frozen=True)
class SkillWorkflow:
    """A Skill-owned, data-only orchestration contract."""

    name: str
    steps: tuple[SkillWorkflowStep, ...] = ()
    description: str = ""

    @property
    def tools(self) -> list[str]:
        """Compatibility-free convenience projection for UI/context code."""
        return [step.tool for step in self.steps]

    @property
    def platforms(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for step in self.steps:
            if step.platform:
                result.setdefault(step.platform, []).append(step.tool)
        return result

    def tool_mapping(self) -> dict[str, list[str]]:
        if self.platforms:
            return self.platforms
        return {"": self.tools} if self.tools else {}

    def ordered_steps(self) -> list[SkillWorkflowStep]:
        """Return a stable topological order for Runtime execution.

        ``validation_errors`` checks that the graph is a DAG, but callers also
        need the graph order rather than the file order.  A declaration-order
        tie break keeps plans reproducible when two independent steps are
        ready at the same time.  The method is deliberately data-only: a
        workflow can select Tools, but it cannot execute Python or bypass the
        Runtime policy gates.
        """
        errors = self.validation_errors()
        if errors:
            raise ValueError("; ".join(errors))
        by_id = {step.id: step for step in self.steps}
        remaining = {step.id: set(step.depends_on) for step in self.steps}
        ordered: list[SkillWorkflowStep] = []
        while remaining:
            ready = [step.id for step in self.steps if step.id in remaining and not remaining[step.id]]
            if not ready:
                raise ValueError(f"workflow {self.name}: step dependencies contain a cycle")
            for step_id in ready:
                ordered.append(by_id[step_id])
                remaining.pop(step_id, None)
            for deps in remaining.values():
                deps.difference_update(ready)
        return ordered

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
        }

    def validation_errors(self) -> list[str]:
        """Validate deterministic workflow structure at Skill load time."""
        errors: list[str] = []
        step_ids = [step.id for step in self.steps]
        seen: set[str] = set()
        for step in self.steps:
            if not step.tool:
                errors.append(f"workflow {self.name}: step {step.id} has no tool")
            if step.id in seen:
                errors.append(f"workflow {self.name}: duplicate step id {step.id}")
            seen.add(step.id)
            if step.on_error not in {"stop", "continue", "skip_dependents"}:
                errors.append(
                    f"workflow {self.name}: step {step.id} has invalid on_error={step.on_error}"
                )
            for dependency in step.depends_on:
                if dependency not in step_ids:
                    errors.append(
                        f"workflow {self.name}: step {step.id} depends on unknown step {dependency}"
                    )

        # A workflow must be a DAG; otherwise a recovery worker could never
        # derive a deterministic next step.
        remaining = {step.id: set(step.depends_on) for step in self.steps}
        while remaining:
            ready = {step_id for step_id, deps in remaining.items() if not deps}
            if not ready:
                errors.append(f"workflow {self.name}: step dependencies contain a cycle")
                break
            for step_id in ready:
                remaining.pop(step_id, None)
            for deps in remaining.values():
                deps.difference_update(ready)
        return errors


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
        4. 返回 CapabilityRuntime 生命周期声明
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
    
    业务模块向 Runtime 提交的能力生命周期声明。

    流程和路由归 Skill 所有；Capability 只提供原子 Tool、Provider
    schema/lookup 以及必要的运行时扩展点。
    """
    # 写入前保护钩子（可选）
    write_guard: Optional["WriteGuard"] = None

    # 后台任务（可选）
    background_tasks: list[dict] = field(default_factory=list)

    # Skill-owned parameter catalogs.  A catalog may expose static enums or
    # a dynamic lookup descriptor without making the shared Runtime know a
    # provider's field names.
    parameter_catalogs: list[Any] = field(default_factory=list)

    @property
    def intent_to_tools(self) -> dict[str, dict[str, list[str]]]:
        """Deprecated compatibility view; routing is Tool metadata based."""
        return {}


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
