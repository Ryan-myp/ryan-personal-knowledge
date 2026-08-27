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
from typing import Any, Optional

from ..core.interfaces import (
    ToolContext, ToolResult, ToolDefinition, ToolHandler,
    CapabilityModule, CapabilityContext, CapabilityRuntime,
    WriteGuard, RiskLevel, ToolEffect
)
from ..core.tool_registry import SimpleToolRegistry


PROTECTED_UPDATE_FIELDS = frozenset({
    "token", "accesstoken", "refreshtoken", "developertoken", "clientid",
    "clientsecret", "privatekey", "bcid", "partnerid", "mcc",
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
        intent_mappings = self._build_intent_mappings(context.registry)
        
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
    
    def _build_intent_mappings(self, registry: Optional[SimpleToolRegistry] = None) -> dict[str, dict[str, list[str]]]:
        """
        构建意图 → 平台工具映射。
        
        默认实现：为常见意图类型提供标准工具序列。
        子类可覆盖以提供平台特定映射。
        """
        available = {
            tool.name for tool in registry.list_by_platform(self.platform_name)
        } if registry else set()

        def existing(names: list[str]) -> list[str]:
            # Only publish routes for tools that this Capability actually
            # registered.  This turns capability configuration into an
            # executable contract instead of a documentation-only hint.
            return [name for name in names if not available or name in available]

        prefix = self.platform_name
        if prefix == "google-ads":
            prefix = "google"

        mappings: dict[str, dict[str, list[str]]] = {}

        def add(intent_type: str, names: list[str]) -> None:
            names = existing(names)
            if names:
                mappings.setdefault(intent_type, {})[self.platform_name] = names

        add("create_campaign", self._get_campaign_tool_sequence())
        add("create_asset_group", [f"{prefix}_create_asset_group"])
        add("boost_post", self._get_boost_tool_sequence() or [
            f"{prefix}_boost_post" if self.platform_name == "meta"
            else "tiktok_spark_ads_create" if self.platform_name == "tiktok"
            else "",
        ])
        add("download_report", self._get_report_tool_sequence())
        add("list_campaigns", [f"{prefix}_list_campaigns"])
        add("get_campaign", [f"{prefix}_get_campaign"])
        add("update_campaign", [f"{prefix}_update_campaign"])
        add("pause_campaign", [f"{prefix}_update_campaign"])
        add("resume_campaign", [f"{prefix}_update_campaign"])

        child_tools = {
            "meta": ("list_adgroups", "meta_list_ad_sets"),
            "google-ads": ("list_adgroups", "google_list_ad_groups"),
            "tiktok": ("list_adgroups", "tiktok_list_adgroups"),
        }
        if self.platform_name in child_tools:
            add(child_tools[self.platform_name][0], [child_tools[self.platform_name][1]])
        if self.platform_name == "meta":
            add("list_adsets", ["meta_list_ad_sets"])
            add("update_adset", ["meta_update_adset"])
        elif self.platform_name == "google-ads":
            add("update_adgroup", ["google_update_ad_group"])
            add("update_adset", ["google_update_ad_group"])
        elif self.platform_name == "tiktok":
            add("update_adgroup", ["tiktok_update_adgroup"])
            add("update_adset", ["tiktok_update_adgroup"])

        add("list_ads", [f"{prefix}_list_ads"])
        add("update_ad", [f"{prefix}_update_ad"])
        add("list_audiences", [f"{prefix}_list_audiences"])
        if self.platform_name == "google-ads":
            add("list_keywords", ["google_list_keywords"])
        if self.platform_name == "tiktok":
            add("list_creatives", ["tiktok_list_creatives"])
            add("list_videos", ["tiktok_list_videos"])
            add("list_images", ["tiktok_list_images"])
            add("list_conversions", ["tiktok_list_conversions"])
            add("list_locations", ["tiktok_list_locations"])
            add("list_devices", ["tiktok_list_devices"])
            add("list_catalogs", ["tiktok_list_catalogs"])
            add("list_apps", ["tiktok_list_apps"])
            add("list_brand_safety", ["tiktok_list_brand_safety"])
        if self.platform_name == "meta":
            add("create_creative", ["meta_create_creative"])
        if self.platform_name == "dv360":
            add("list_ios", ["dv360_list_ios"])
            add("get_io", ["dv360_get_io"])
            add("list_line_items", ["dv360_list_line_items"])
            add("get_line_item", ["dv360_get_line_item"])
            add("update_io", ["dv360_update_io"])
            add("update_line_item", ["dv360_update_line_item"])
        if self.platform_name == "google-ads":
            add("update_asset_group", ["google_update_asset_group"])
        return mappings
    
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

    def __init__(self, api_client=None, resource_type: str = "campaign"):
        self.client = api_client
        self.resource_type = resource_type

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
            account_id = ctx.account_id
            if self.client.platform == "meta":
                resource_id = input_data.get(f"{self.resource_type}_id") or input_data.get("adset_id")
                method_name = {
                    "campaign": "update_campaign",
                    "adset": "update_adset",
                    "ad": "update_ad",
                }.get(self.resource_type)
                method = getattr(self.client, method_name, None) if method_name else None
                if not method or not resource_id:
                    return ToolResult.error(f"Meta {self.resource_type} update adapter is unavailable")
                # A Graph object can be addressed directly by ID even when it
                # belongs to another account visible to the same token.  Do
                # not treat the Runtime's selected account as proof of object
                # ownership.
                from ..api_clients.meta_client import MetaAPIClient
                if isinstance(self.client, MetaAPIClient) and not self.client.resource_belongs_to_account(
                    account_id, self.resource_type, resource_id
                ):
                    return ToolResult.error(
                        f"Meta {self.resource_type} {resource_id} does not belong to account {account_id}"
                    )
                return ToolResult.ok({"resource_id": resource_id, "result": method(resource_id, updates)})

            # The runtime/registry uses ``google-ads`` while the REST client
            # normalizes its internal platform name to ``google``. Accept
            # both forms so a verified campaign update is not rejected by
            # the adapter itself.
            if self.client.platform in ("google", "google-ads"):
                resource_id = input_data.get(f"{self.resource_type}_id") or input_data.get("ad_group_id")
                if self.resource_type != "campaign" or not resource_id:
                    return ToolResult.error(f"Google {self.resource_type} update adapter is unavailable")
                method = getattr(type(self.client), "for_customer", None)
                client = method(self.client, account_id) if method and account_id else self.client
                if client is self.client and account_id and hasattr(self.client, "customer_id"):
                    self.client.customer_id = account_id
                return ToolResult.ok({"resource_id": resource_id, "result": client.update_campaign(resource_id, updates)})

            if self.client.platform == "tiktok":
                if self.resource_type == "campaign":
                    resource_id = input_data.get("campaign_id")
                    method = self.client.update_campaign
                    args = (account_id, resource_id, updates)
                elif self.resource_type == "adgroup":
                    resource_id = input_data.get("adgroup_id")
                    method = self.client.update_adgroup
                    args = (account_id, input_data.get("campaign_id"), resource_id, updates)
                else:
                    return ToolResult.error(f"TikTok {self.resource_type} update adapter is unavailable")
                if not resource_id:
                    return ToolResult.error(f"TikTok {self.resource_type}_id is required")
                return ToolResult.ok({"resource_id": resource_id, "result": method(*args)})

            return ToolResult.error(f"{self.client.platform} {self.resource_type} update adapter is unavailable")
        except Exception as exc:
            return ToolResult.error(f"Failed to update {self.resource_type}: {exc}")
