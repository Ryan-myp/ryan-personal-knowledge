"""
capabilities/base.py - 平台 Capability 基类

所有广告平台 Capability 都继承此类。
提供标准化的工具注册、意图映射、写入保护等能力。

借鉴 DAP Agent internal/capabilities/tiktok/runtime/module.go
"""

import hashlib
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Optional

from ..core.interfaces import (
    ToolContext, ToolResult, ToolDefinition, ToolHandler,
    CapabilityModule, CapabilityContext, CapabilityRuntime,
    WriteGuard, RiskLevel, ToolEffect
)
from ..core.tool_registry import SimpleToolRegistry


PROTECTED_UPDATE_FIELDS = frozenset({
    "token", "accesstoken", "refreshtoken", "developertoken", "clientid",
    "clientsecret", "apikey", "appsecret", "secretkey", "privatekey",
    "privatekeyid", "serviceaccount", "serviceaccountemail", "saemail",
    "developerkey", "bcid", "partnerid", "mcc",
    "authorization", "credential", "credentials", "perterid",
})


def protected_update_paths(value: Any, path: str = "") -> list[str]:
    """Find red-line configuration fields in a provider update payload."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            normalized = "".join(char for char in key_text.lower() if char.isalnum())
            current = f"{path}.{key_text}" if path else key_text
            if normalized in PROTECTED_UPDATE_FIELDS:
                found.append(current)
            else:
                found.extend(protected_update_paths(item, current))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(protected_update_paths(item, f"{path}[{index}]"))
    return found[:10]


class BaseCapability(CapabilityModule, ABC):
    """
    平台 Capability 基类。
    
    子类只需实现：
    1. platform_name: 平台名称（meta/google/tiktok/dv360）
    2. register_tools(): 注册该平台的原子工具

    Skill 以自然语言提供业务流程和跨渠道 SOP；Capability 只注册原子 Tool
    及其参数/Provider 适配。标准编排由 Runtime 根据 Tool 元数据发现，
    Capability 不维护中心意图路由或 workflow 配置。
    
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
        
        # Workflow policy belongs to the Skill contract. Capability only
        # registers executable tools and its provider-independent write guard.
        write_guard = self._build_write_guard()
        return CapabilityRuntime(write_guard=write_guard)
    
    def _register_platform_tools(self, registry: SimpleToolRegistry) -> None:
        """子类实现：将平台工具注册到 Registry"""
        tools = self.register_tools()
        for defn, handler in tools:
            # Built-in capabilities must participate in the same authorization
            # contract as dynamically loaded Skills.  ``ads.plan`` is the
            # baseline grant for dry-run writes; Runtime adds ``ads.write``
            # only when a live write is attempted.  A capability may provide a
            # more specific permission list and is never overwritten here.
            if not defn.required_permissions:
                defn.required_permissions = [
                    "ads.plan" if defn.is_write_tool else "ads.read"
                ]
            registry.register(defn, handler)
    
    @abstractmethod
    def register_tools(self) -> list[tuple[ToolDefinition, ToolHandler]]:
        """
        注册平台工具。
        
        Returns:
            [(ToolDefinition, ToolHandler), ...]
        """
        pass
    
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
    
    def __init__(self, max_retries: int = 3, store=None):
        self._executed: dict[str, datetime] = {}
        self._reserved: dict[str, datetime] = {}
        self._max_retries = max_retries
        self._store = store
        self._lock = threading.RLock()

    def bind_store(self, store) -> None:
        """Attach the Runtime's SQLite store without changing the API."""
        self._store = store
    
    def reserve_write(
        self,
        ctx: ToolContext,
        tool_def: ToolDefinition,
        input_data: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """检查是否允许写入"""
        # 生成幂等键
        key = self._generate_key(tool_def.name, input_data, ctx.user_id)
        
        # Check executed and in-flight reservations atomically.  The previous
        # check-then-mark sequence allowed concurrent requests to pass the
        # guard before either one recorded completion.
        with self._lock:
            now = datetime.now()
            last_run = self._executed.get(key) or self._reserved.get(key)
            if last_run:
                elapsed = (now - last_run).total_seconds()
                if elapsed < 300:  # 5-minute window
                    return False, f"Duplicate write detected for '{tool_def.name}' (last run {elapsed:.0f}s ago)"
            if self._store is not None and not self._store.reserve_write(key, 300):
                return False, f"Duplicate write detected for '{tool_def.name}' (persistent reservation)"
            self._reserved[key] = now

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
        with self._lock:
            self._reserved.pop(key, None)
            self._executed[key] = datetime.now()
            if self._store is not None:
                self._store.mark_write_executed(key)

    def release_write(self, tool_name: str, input_data: dict, user_id: str) -> None:
        """Release a reservation after a failed/non-executed write."""
        key = self._generate_key(tool_name, input_data, user_id)
        with self._lock:
            self._reserved.pop(key, None)
            if self._store is not None:
                self._store.release_write(key)


class CampaignUpdateHandler(ToolHandler):
    """统一的 Campaign/下级资源更新适配器。

    Runtime 的 dry-run 会在到达 Handler 前截断写请求；此 Handler 只负责
    后续人工启用 live 模式后的已知平台方法，不会自行改变凭证或账户元数据。
    """

    def __init__(
        self,
        api_client=None,
        resource_type: str = "campaign",
        update_adapter: Optional[Callable[..., Any]] = None,
        resource_id_field: Optional[str] = None,
        parent_resource_id_field: Optional[str] = None,
    ):
        self.client = api_client
        self.resource_type = resource_type
        self.update_adapter = update_adapter
        self.resource_id_field = resource_id_field or f"{resource_type}_id"
        self.parent_resource_id_field = parent_resource_id_field

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if not self.client:
            return ToolResult.error("API client not configured")
        updates = input_data.get("updates", {})
        if not isinstance(updates, dict) or not updates:
            return ToolResult.error("updates must be a non-empty object")
        protected = protected_update_paths(updates)
        if protected:
            return ToolResult.error(
                "Protected credential/account fields cannot be modified: "
                + ", ".join(protected)
            )

        try:
            resource_id = input_data.get(self.resource_id_field)
            if not resource_id:
                return ToolResult.error(f"{self.resource_type}_id is required")
            parent_id = (
                input_data.get(self.parent_resource_id_field)
                if self.parent_resource_id_field else None
            )
            if self.update_adapter is None:
                # A custom provider can expose this uniform seam and avoid
                # writing an adapter at all.  Provider-specific signatures
                # belong in the Capability that registered the Tool.
                method = getattr(self.client, "update_resource", None)
                if not callable(method):
                    return ToolResult.error(
                        f"{self.resource_type} update adapter is unavailable"
                    )
                value = method(
                    self.resource_type, ctx.account_id, resource_id, parent_id, updates
                )
            else:
                value = self.update_adapter(
                    self.client, ctx, self.resource_type, resource_id, parent_id, updates
                )
            return ToolResult.ok({"resource_id": resource_id, "result": value})
        except Exception as exc:
            return ToolResult.error(f"Failed to update {self.resource_type}: {exc}")
