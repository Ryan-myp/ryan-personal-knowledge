"""
tools/providers/provider_base.py - 平台 Tool Source 基类

所有广告平台 Tool Source 都继承此类。
提供标准化的工具注册、意图映射、写入保护等能力。

借鉴 DAP Agent internal/tools/providers/tiktok/runtime/module.go
"""

import hashlib
import importlib
import inspect
import threading
import copy
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Optional

from ...core.interfaces import (
    ToolContext, ToolResult, ToolDefinition, ToolHandler,
    ToolSourceModule, ToolSourceContext,
    WriteGuard, WriteReservation, RiskLevel, ToolEffect
)
from agents.agent_harness import StaticToolSource, ToolBinding
from ...core.tool_registry import SimpleToolRegistry
from ...domain.ad.security import protected_update_paths
from ...domain.ad.contracts import AdToolSourceRuntime


def call_with_optional_page_size(
    method: Callable,
    *args: Any,
    limit: Any = None,
    parameter_names: tuple[str, ...] = ("limit", "page_size"),
) -> Any:
    """Pass paging to adapters that advertise it, preserving old adapters.

    Provider clients are intentionally replaceable.  A read-only handler must
    not force every test/custom client to grow a paging keyword just because
    the built-in adapter exposes one.  Signature inspection also avoids a
    broad ``TypeError`` retry that could accidentally duplicate a call when
    the provider method itself raises a TypeError.
    """
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        return method(*args)
    # ``**kwargs`` alone is not evidence that an adapter consumes paging;
    # permissive test doubles commonly expose every method that way. Only an
    # explicitly named parameter opts into the additional argument.
    name = next((candidate for candidate in parameter_names if candidate in parameters), None)
    if name is None or limit is None:
        return method(*args)
    return method(*args, **{name: limit})


def resource_was_created_in_current_run(
    ctx: ToolContext, resource_type: str, resource_id: Any
) -> bool:
    """Return whether a parent resource was created earlier in this run.

    Provider ownership lookups are deliberately retained for caller-supplied
    IDs.  A just-created parent can, however, be absent from an eventually
    consistent account listing for a short period.  Runtime records only
    successful live creates in this bounded, per-turn map, allowing a
    hierarchy chain to continue without weakening cross-account checks.
    """
    if ctx is None or not resource_type or resource_id in (None, ""):
        return False
    created = (getattr(ctx, "metadata", {}) or {}).get(
        "runtime_created_resource_ids", {}
    )
    if not isinstance(created, dict):
        return False
    values = created.get(str(resource_type), ())
    if isinstance(values, (str, bytes)):
        values = (values,)
    return str(resource_id) in {str(value) for value in (values or ())}


def apply_lookup_contracts(
    tools: list[tuple[ToolDefinition, ToolHandler]],
    contracts: dict[str, dict[str, dict[str, Any]]],
) -> list[tuple[ToolDefinition, ToolHandler]]:
    """Attach provider-owned lookup metadata to registered Tool schemas.

    ``contracts`` lives beside a provider Tool Source and is deliberately
    keyed by Tool/schema paths.  The shared Runtime only consumes the
    resulting declarative metadata; it never infers a lookup endpoint from a
        field name.  ``*`` applies a contract to every Tool in that Tool Source,
    which keeps a newly exposed operation covered without duplicating dozens
    of identical field declarations.
    """
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    for scope in ("*",):
        for path, metadata in (contracts.get(scope) or {}).items():
            merged[f"*.{path}"] = copy.deepcopy(metadata)
    for tool_name, fields in contracts.items():
        if tool_name == "*":
            continue
        for path, metadata in (fields or {}).items():
            merged[f"{tool_name}.{path}"] = copy.deepcopy(metadata)

    def schema_paths(properties: Any, prefix: str = "") -> list[tuple[str, dict[str, Any]]]:
        """Flatten object properties, including nested provider settings."""
        result: list[tuple[str, dict[str, Any]]] = []
        if not isinstance(properties, dict):
            return result
        for name, schema in properties.items():
            if not isinstance(schema, dict):
                continue
            path = f"{prefix}.{name}" if prefix else str(name)
            result.append((path, schema))
            if schema.get("type") == "object":
                result.extend(schema_paths(schema.get("properties"), path))
            item_schema = schema.get("items")
            if isinstance(item_schema, dict) and item_schema.get("type") == "object":
                result.extend(schema_paths(item_schema.get("properties"), f"{path}[]"))
        return result

    for definition, _handler in tools:
        properties = getattr(definition.input_schema, "properties", {}) or {}
        for path, target in schema_paths(properties):
            leaf = path.rsplit(".", 1)[-1].replace("[]", "")
            for key, metadata in merged.items():
                if key.startswith("*"):
                    contract_path = key[2:] if key.startswith("*.") else key
                    matches = path == contract_path or (
                        "." not in contract_path and leaf == contract_path
                    )
                else:
                    tool_name, contract_path = key.split(".", 1)
                    matches = (
                        definition.name == tool_name
                        and (path == contract_path or (
                            "." not in contract_path and leaf == contract_path
                        ))
                    )
                if matches:
                    target.update(copy.deepcopy(metadata))
    return tools


class BaseProviderToolSource(ToolSourceModule, ABC):
    """
    平台 Tool Source 基类。
    
    子类只需实现：
    1. platform_name: 平台名称（meta/google/tiktok/dv360）
    2. register_tools(): 注册该平台的原子工具

    Skill 以自然语言提供业务流程和跨渠道 SOP；Tool Source 只注册原子 Tool
    及其参数/Provider 适配。标准编排由 Runtime 根据 Tool 元数据发现，
    Tool Source 不维护中心意图路由或 workflow 配置。
    
    不实现的部分由基类提供默认行为。
    """
    
    # 平台名称（子类必须覆盖）
    platform_name: str = ""
    tool_source_version: str = "1.0.0"
    integration_api_version: str = ""
    
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
    
    def configure(self, context: ToolSourceContext) -> AdToolSourceRuntime:
        """
        配置并返回 ToolSourceRuntime。
        
        对应 DAP Agent ToolSourceModule.Configure() 模式：
        1. 读取业务依赖
        2. 创建工具处理器
        3. 注册到 Registry
        4. 返回 ToolSourceRuntime
        """
        # Step 1: 注册平台工具
        self._register_platform_tools(context.registry)
        
        # Workflow policy belongs to the Skill contract. Tool Source only
        # registers executable tools and its provider-independent write guard.
        write_guard = self._build_write_guard()
        return AdToolSourceRuntime(
            write_guard=write_guard,
            ad_format_catalogs=self.get_ad_format_catalog(),
            creation_blueprints=self.get_creation_blueprints(),
        )

    def get_creation_blueprints(self) -> list[Any]:
        """Return provider-owned declarative creation blueprints.

        The default keeps existing/custom Tool Sources independently usable. A
        provider may load JSON blueprints beside its Tool Source package; the
        shared Runtime only validates and indexes them.
        """
        return []

    def get_ad_format_catalog(self) -> list[dict[str, Any]]:
        """Return provider-owned format coverage metadata.

        A provider may extend this without changing Runtime.  The default is
        empty so custom Tool Sources can adopt the contract incrementally.
        """
        return []

    def get_provider_version_contract(self) -> dict[str, Any]:
        """Expose the Client-owned version contract for audits and tooling."""
        client_class = getattr(self, "provider_client_class", None)
        version_contract = getattr(client_class, "version_contract", None)
        if callable(version_contract):
            contract = dict(version_contract())
        else:
            contract = {
                "api_version": str(getattr(client_class, "API_VERSION", "") or ""),
                "supported_api_versions": list(
                    getattr(client_class, "SUPPORTED_API_VERSIONS", ()) or ()
                ),
                "adapter_versions": sorted(
                    str(version)
                    for version in (getattr(client_class, "VERSION_ADAPTERS", {}) or {})
                ),
                "issues": [],
            }
        contract["tool_source_api_version"] = str(self.integration_api_version or "")
        return contract

    def get_api_surface(self) -> list[dict[str, Any]]:
        """Return this provider package's declarative API surface."""
        module_name = f"{type(self).__module__.rsplit('.', 1)[0]}.api_surface"
        try:
            module = importlib.import_module(module_name)
        except (ImportError, AttributeError):
            return []
        entries = getattr(module, "API_SURFACE", []) or []
        return [dict(entry) for entry in entries if isinstance(entry, dict)]

    def _validate_provider_version_contract(
        self,
        definitions: list[tuple[ToolDefinition, ToolHandler]],
    ) -> list[str]:
        """Validate Tool Source, Client and Tool version declarations together."""
        client_class = getattr(self, "provider_client_class", None)
        contract = self.get_provider_version_contract()
            # A local/provider-agnostic Tool Source may not have a Client at all.
        # Do not force it to invent a provider version contract.
        if client_class is None:
            return []
        errors = list(contract.get("issues", []))
        supported = set(str(item).strip() for item in contract.get("supported_api_versions", []))
        adapters = set(str(item).strip() for item in contract.get("adapter_versions", []))
        compatible = supported | adapters
        tool_source_version = str(self.integration_api_version or "").strip()
        client_name = getattr(client_class, "__name__", type(client_class).__name__)
        if tool_source_version and not compatible:
            errors.append(
                f"Tool Source integration_api_version {tool_source_version!r} cannot be verified; "
                f"Client {client_name} publishes no supported API versions"
            )
        elif tool_source_version and tool_source_version not in compatible:
            errors.append(
                f"Tool Source integration_api_version {tool_source_version!r} is not supported by "
                f"Client {client_name}: "
                f"{sorted(compatible)}"
            )

        bound_client = getattr(self, "_api_client", None)
        # Test doubles and replaceable clients may implement permissive
        # ``__getattr__``.  Only trust an instance-owned value here; an
        # arbitrary callable returned for ``api_version`` is not metadata.
        bound_state = getattr(bound_client, "__dict__", {})
        bound_value = (
            bound_state.get("api_version")
            if isinstance(bound_state, dict)
            else None
        )
        bound_actual = str(
            bound_value or getattr(client_class, "API_VERSION", "") or ""
        ).strip()
        for definition, _handler in definitions:
            declared = str(
                getattr(definition, "integration_api_version", "")
                or tool_source_version
                or contract.get("api_version", "")
                or ""
            ).strip()
            if not declared or not compatible:
                continue
            if declared not in compatible:
                errors.append(
                    f"Tool {definition.name} integration_api_version {declared!r} is not supported by "
                    f"Client {sorted(compatible)}"
                )
            elif bound_actual and bound_actual != declared and declared not in adapters:
                errors.append(
                    f"Tool {definition.name} requires {declared!r}, but bound Client uses "
                    f"{bound_actual!r} without an adapter"
                )
        return list(dict.fromkeys(errors))
    
    def _register_platform_tools(self, registry: SimpleToolRegistry) -> None:
        """子类实现：将平台工具注册到 Registry"""
        tools = self.register_tools()
        version_errors = self._validate_provider_version_contract(tools)
        if version_errors:
            raise ValueError(
                f"{self.platform_name} Provider API version contract invalid: "
                + "; ".join(version_errors)
            )
        provider_contract = self.get_provider_version_contract()
        client_version = str(provider_contract.get("api_version") or "").strip()
        bound_client = getattr(self, "_api_client", None)
        bound_state = getattr(bound_client, "__dict__", {})
        bound_client_version = (
            str(bound_state.get("api_version") or "").strip()
            if isinstance(bound_state, dict)
            else ""
        )
        bindings: list[ToolBinding] = []
        for defn, handler in tools:
            metadata_errors = defn.routing_metadata_errors()
            if metadata_errors:
                raise ValueError(
                    f"{self.platform_name} Tool {defn.name} is missing explicit routing metadata: "
                    + ", ".join(metadata_errors)
                )
            if not defn.integration_api_version:
                # An absent version is a valid extension state: a custom
                # Tool Source may expose a provider-agnostic/local Tool or a
                # client that has not published version metadata yet. Do not
                # turn that absence into the literal version ``unknown``;
                # Runtime would then treat it as a concrete contract and
                # reject every real client whose version is known.
                provided_version = (
                    bound_client_version
                    or getattr(self, "integration_api_version", "")
                    or client_version
                )
                if provided_version:
                    defn.integration_api_version = str(provided_version)
            # Tool Source version is deliberately attached at registration
            # time, so a provider can publish a new Tool contract without a
            # Runtime/Router change.
            if defn.contract_version == "1" and self.tool_source_version:
                defn.contract_version = str(self.tool_source_version)
            # Built-in Tool Sources must participate in the same authorization
            # contract as dynamically loaded Skills.  ``ads.plan`` is the
            # baseline grant for dry-run writes; Runtime adds ``ads.write``
            # only when a live write is attempted.  A tool_source may provide a
            # more specific permission list and is never overwritten here.
            if not defn.required_permissions:
                defn.required_permissions = [
                    "ads.plan" if defn.is_write_tool else "ads.read"
                ]
            bindings.append(ToolBinding(defn, handler))
        if bindings:
            registry.register_source(
                StaticToolSource(
                    f"provider-module:{self.platform_name}",
                    bindings,
                )
            )
    
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
        self._reservations: dict[str, WriteReservation] = {}

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
        allowed, reason, _reservation = self.reserve_write_record(
            ctx, tool_def, input_data
        )
        return allowed, reason

    def reserve_write_record(
        self,
        ctx: ToolContext,
        tool_def: ToolDefinition,
        input_data: dict[str, Any],
    ) -> tuple[bool, Optional[str], Optional[WriteReservation]]:
        """Reserve and return a request-bound reservation for Runtime."""
        key = self._generate_key(tool_def.name, input_data, ctx.user_id)
        from ...domain.ad.security import request_hash, sha256_json
        reservation = WriteReservation(
            idempotency_key=key,
            request_hash=request_hash(
                tool_def.namespace, ctx.account_id, tool_def.name,
                sha256_json(input_data),
            ),
            tool_name=tool_def.name,
            scope_key=str(ctx.account_id or ""),
        )
        
        # Check executed and in-flight reservations atomically.  The previous
        # check-then-mark sequence allowed concurrent requests to pass the
        # guard before either one recorded completion.
        with self._lock:
            now = datetime.now()
            last_run = self._executed.get(key) or self._reserved.get(key)
            if last_run:
                elapsed = (now - last_run).total_seconds()
                if elapsed < 300:  # 5-minute window
                    return False, f"Duplicate write detected for '{tool_def.name}' (last run {elapsed:.0f}s ago)", None
            if self._store is not None and not self._store.reserve_write(
                key, 300, reservation.request_hash
            ):
                return False, f"Duplicate write detected for '{tool_def.name}' (persistent reservation)", None
            self._reserved[key] = now
            self._reservations[key] = reservation

        return True, None, reservation
    
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
            self._reservations.pop(key, None)
            if self._store is not None:
                self._store.release_write(key)

    def finalize(self, reservation: WriteReservation, result: ToolResult) -> None:
        """Bind the provider result to the exact reservation/request hash."""
        with self._lock:
            current = self._reservations.get(reservation.idempotency_key)
            if current != reservation:
                return
            if result.success and not result.simulated:
                self._reserved.pop(reservation.idempotency_key, None)
                self._reservations.pop(reservation.idempotency_key, None)
                self._executed[reservation.idempotency_key] = datetime.now()
                if self._store is not None:
                    self._store.mark_write_executed(
                        reservation.idempotency_key, reservation.request_hash
                    )
            elif getattr(result, "data", {}).get("execution_status") in {
                "unknown", "timed_out", "transport_unknown",
            }:
                # Keep the durable reservation until reconciliation or an
                # explicit operator decision; retrying could duplicate a write.
                return
            else:
                self._reserved.pop(reservation.idempotency_key, None)
                self._reservations.pop(reservation.idempotency_key, None)
                if self._store is not None:
                    self._store.release_write(
                        reservation.idempotency_key, reservation.request_hash
                    )


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
            # belong in the Tool Source that registered the Tool.
                method = getattr(self.client, "update_resource", None)
                if not callable(method):
                    return ToolResult.error(
                        f"{self.resource_type} update adapter is unavailable"
                    )
                value = method(
                    self.resource_type, ctx.account_id, resource_id, parent_id, updates
                )
            else:
                adapter = self.update_adapter
                # Provider update adapters may expose the same explicit live
            # switch as create adapters.  Inspect the fixed Tool Source
                # callback signature instead of passing Runtime state through
                # user-controlled input or assuming every custom adapter has
                # the new keyword.
                try:
                    adapter_parameters = inspect.signature(adapter).parameters
                except (TypeError, ValueError):
                    adapter_parameters = {}
                adapter_kwargs = {}
                if "live" in adapter_parameters:
                    adapter_kwargs["live"] = (
                        str(getattr(ctx, "metadata", {}).get("execution_mode", "dry_run"))
                        == "live"
                    )
                value = adapter(
                    self.client, ctx, self.resource_type, resource_id, parent_id,
                    updates, **adapter_kwargs
                )
            return ToolResult.ok({"resource_id": resource_id, "result": value})
        except Exception as exc:
            return ToolResult.error(f"Failed to update {self.resource_type}: {exc}")


class ProviderMethodHandler(ToolHandler):
    """Expose one fixed provider-client method as a safe Tool handler.

    The method name and argument builder are owned by the Tool Source, never by
    user input.  This keeps the extension surface small when a provider adds a
    read/reference/management endpoint, while preserving the Runtime's
    standard ``client`` isolation, timeout and live-write gates.
    """

    def __init__(
        self,
        api_client: Any,
        method_name: str,
        result_key: str,
        argument_builder: Callable[[ToolContext, dict[str, Any]], tuple[tuple, dict]],
        *,
        write: bool = False,
        offline_value: Any = None,
    ):
        self.client = api_client
        self.method_name = str(method_name)
        self.result_key = str(result_key)
        self.argument_builder = argument_builder
        self.write = bool(write)
        self.offline_value = offline_value
        # Provider Tool Sources may resolve an account-scoped client view
        # without making Runtime know provider-specific client semantics.
        self.client_resolver: Optional[Callable[[ToolContext, dict[str, Any]], Any]] = None

    def execute(self, ctx: ToolContext, input_data: dict) -> ToolResult:
        if self.client is None:
            if self.write:
                return ToolResult.error("API client not configured")
            return ToolResult.ok({
                self.result_key: self.offline_value if self.offline_value is not None else [],
                "account_id": getattr(ctx, "account_id", None),
                "data_status": "offline_no_client",
                "simulated": True,
            })
        try:
            client = self.client
            if self.client_resolver is not None:
                client = self.client_resolver(ctx, input_data)
            method = getattr(client, self.method_name, None)
            if not callable(method):
                return ToolResult.error(
                    f"Provider method {self.method_name} is unavailable"
                )
            args, kwargs = self.argument_builder(ctx, input_data)
            # Provider adapters may expose a deliberate ``live`` switch for
            # multi-step mutations. Inject it only when the fixed method
            # explicitly declares the parameter; arbitrary Tools never
            # receive Runtime state through user-controlled kwargs.
            try:
                method_parameters = inspect.signature(method).parameters
            except (TypeError, ValueError):
                method_parameters = {}
            if "live" in method_parameters and "live" not in kwargs:
                kwargs["live"] = (
                    str(getattr(ctx, "metadata", {}).get("execution_mode", "dry_run"))
                    == "live"
                )
            value = method(*args, **kwargs)
            data = {
                self.result_key: value,
                "data_status": "live",
            }
            if getattr(ctx, "account_id", None):
                data["account_id"] = ctx.account_id
            return ToolResult.ok(data)
        except Exception as exc:
            return ToolResult.error(
                f"Failed to call provider method {self.method_name}: {exc}"
            )
