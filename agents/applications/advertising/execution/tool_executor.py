"""Provider-neutral execution boundary for registered advertising Tools."""

from __future__ import annotations
from contextvars import copy_context

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Optional

from agents.agent_harness.core.features import RuntimeExecutionServices
from agents.agent_harness.core.interfaces import ToolDefinition, ToolError, ToolResult
from agents.agent_harness.core.tool_registry import validate_tool_input


class _CancellationBridge:
    """Expose Run/task cancellation while retaining a local timeout signal."""

    def __init__(self, *signals: Any) -> None:
        self._signals = tuple(signal for signal in signals if signal is not None)
        self._local = threading.Event()

    def is_set(self) -> bool:
        return self._local.is_set() or any(
            bool(signal.is_set())
            for signal in self._signals
            if callable(getattr(signal, "is_set", None))
        )

    def wait(self, timeout: Optional[float] = None) -> bool:
        if self.is_set():
            return True
        if timeout is None:
            while not self.is_set():
                time.sleep(0.01)
            return True
        deadline = time.monotonic() + max(0.0, float(timeout))
        while not self.is_set() and time.monotonic() < deadline:
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        return self.is_set()

    def set(self) -> None:
        self._local.set()


@dataclass
class _ToolInvocation:
    ctx: Any
    definition: ToolDefinition
    handler: Any
    input_data: dict[str, Any]
    request_clients: Optional[dict[str, Any]]
    deadline: float
    cancel_event: _CancellationBridge

    @property
    def tool_name(self) -> str:
        return self.definition.name


def classify_error(error: Exception, tool: ToolDefinition) -> ToolError:
    """Map execution failures to stable retry and reconciliation semantics."""
    category = str(
        getattr(error, "error_category", None)
        or getattr(error, "category", None)
        or ""
    ).lower()
    categorized = _classify_category_error(error, tool, category)
    if categorized:
        return categorized
    return _classify_status_error(error, tool, _status_code(error))


def _classify_category_error(
    error: Exception, tool: ToolDefinition, category: str
) -> Optional[ToolError]:
    error_name = type(error).__name__
    message = str(error)
    is_timeout = isinstance(error, (TimeoutError, FutureTimeoutError)) or category in {
        "timeout", "deadline",
    }
    is_auth = error_name == "AuthError" or category in {"auth", "authentication"}
    is_rate_limit = error_name == "RateLimitError" or category in {
        "rate_limit", "ratelimit",
    }
    is_temporary = error_name == "TemporaryError" or category in {
        "temporary", "transient", "transport",
    }
    if is_timeout:
        if tool.is_write_tool:
            return ToolError(
                "provider_result_unknown", "PROVIDER_RESULT_UNKNOWN", message,
                "Reconcile provider state before any retry",
            )
        return ToolError("retriable", "TIMEOUT", message, "Retry automatically")
    if is_auth:
        return ToolError(
            "non_retriable", "AUTH_EXPIRED", message,
            "Refresh credentials through trusted configuration",
        )
    if is_rate_limit:
        return ToolError("retriable", "RATE_LIMIT", message, "Retry with backoff")
    if not is_temporary:
        return None
    if tool.is_write_tool:
        return ToolError(
            "provider_result_unknown", "PROVIDER_RESULT_UNKNOWN", message,
            "Reconcile provider state before any retry",
        )
    return ToolError(
        "retriable", "PROVIDER_TEMPORARY_ERROR", message, "Retry with backoff"
    )


def _status_code(error: Exception) -> int:
    status_code = getattr(error, "status_code", None)
    try:
        return int(status_code or 0)
    except (TypeError, ValueError):
        return 0


def _classify_status_error(
    error: Exception, tool: ToolDefinition, status_code: int
) -> ToolError:
    if status_code >= 500:
        if tool.is_write_tool:
            return ToolError(
                "provider_result_unknown", "PROVIDER_RESULT_UNKNOWN", str(error),
                "Reconcile provider state before any retry",
            )
        return ToolError(
            "retriable", "PROVIDER_5XX", str(error), "Retry with backoff"
        )
    if isinstance(error, (ValueError, TypeError, PermissionError)):
        return ToolError(
            "non_retriable", "INVALID_REQUEST", str(error), "Fix the request"
        )
    return ToolError(
        "non_retriable", "TOOL_EXECUTION_ERROR", str(error), "Inspect the error"
    )


class _ToolInvocationRunner:
    """Resolve request-scoped Provider state and execute one bounded call."""

    def __init__(
        self,
        services: RuntimeExecutionServices,
        capacity_provider: Callable[[], threading.BoundedSemaphore],
    ) -> None:
        self.services = services
        self.capacity_provider = capacity_provider

    def execute(self, invocation: _ToolInvocation) -> ToolResult:
        handler, isolated = self._resolve_handler(invocation)
        client = getattr(handler, "client", None)
        version_error = self._provider_version_error(invocation, client)
        if version_error:
            return ToolResult.error(version_error)
        marker_error = self._set_tool_api_version(invocation, client, isolated)
        if marker_error:
            return marker_error
        validation_error = self._validate_input(invocation)
        if validation_error:
            return validation_error
        return self._run_handler(invocation, handler)

    def _resolve_handler(self, invocation: _ToolInvocation) -> tuple[Any, bool]:
        handler = invocation.handler
        clients = invocation.request_clients
        if not clients:
            client = getattr(handler, "client", None)
        else:
            platform = self.services.normalize_namespace(
                invocation.definition.namespace
            )
            client = clients.get(platform)
            if client is None or not hasattr(handler, "client"):
                return handler, False
        if client is None:
            return handler, False
        return self._prepare_handler(invocation, handler, client)

    def _prepare_handler(
        self, invocation: _ToolInvocation, handler: Any, client: Any
    ) -> tuple[Any, bool]:
        client_type = type(client)
        timeout_setter = getattr(client_type, "set_request_timeout", None)
        timeout_attribute = "request_timeout" in getattr(client, "__dict__", {})
        expected = str(
            getattr(invocation.definition, "integration_api_version", "") or ""
        ).strip()
        client_state = getattr(client, "__dict__", {})
        actual_value = client_state.get("api_version") if isinstance(client_state, dict) else None
        if actual_value in (None, ""):
            actual_value = getattr(client_type, "api_version", "")
        actual = str(actual_value or "").strip()
        needs_version_marker = bool(expected and actual and expected != actual)
        if not callable(timeout_setter) and not timeout_attribute and not needs_version_marker:
            return handler, False
        try:
            isolated_handler = copy.copy(handler)
            isolated_client = copy.copy(client)
        except Exception as exc:
            if needs_version_marker:
                raise RuntimeError(
                    f"{invocation.tool_name} 的 Provider Client 不支持请求级隔离，"
                    "无法安全使用版本 adapter"
                ) from exc
            if not callable(timeout_setter) and not timeout_attribute:
                return handler, False
            raise RuntimeError(
                f"{invocation.tool_name} 的 Provider Client 无法创建请求级隔离副本"
            ) from exc
        self._apply_request_budget(invocation, isolated_client)
        isolated_handler.client = isolated_client
        return isolated_handler, True

    @staticmethod
    def _apply_request_budget(invocation: _ToolInvocation, client: Any) -> None:
        remaining = max(invocation.deadline - time.monotonic(), 0.001)
        budget_setter = getattr(client, "set_request_budget", None)
        if callable(budget_setter):
            budget_setter(remaining)
            return
        timeout_setter = getattr(client, "set_request_timeout", None)
        if callable(timeout_setter):
            timeout_setter(remaining)
        elif hasattr(client, "request_timeout"):
            client.request_timeout = remaining

    def _provider_version_error(
        self, invocation: _ToolInvocation, client: Any
    ) -> Optional[str]:
        expected = str(
            getattr(invocation.definition, "integration_api_version", "") or ""
        ).strip()
        if not expected or client is None:
            return None
        client_type = type(client)
        checker = getattr(client_type, "supports_tool_api_version", None)
        if callable(checker):
            compatible = bool(checker(client, expected))
        else:
            client_state = getattr(client, "__dict__", {})
            actual_value = (
                client_state.get("api_version")
                if isinstance(client_state, dict) else None
            )
            if actual_value in (None, ""):
                actual_value = getattr(client_type, "api_version", "")
            compatible = not actual_value or str(actual_value) == expected
        if compatible:
            return None
        client_state = getattr(client, "__dict__", {})
        actual_value = client_state.get("api_version") if isinstance(client_state, dict) else None
        if actual_value in (None, ""):
            actual_value = getattr(client_type, "api_version", "")
        supported = getattr(client_type, "SUPPORTED_API_VERSIONS", ()) or ()
        return (
            f"{invocation.tool_name} 要求 Provider API {expected}，当前 Client 为 "
            f"{actual_value or 'unknown'}；支持版本: {list(supported)}。"
            "请升级 Client 或提供版本 adapter"
        )

    def _set_tool_api_version(
        self, invocation: _ToolInvocation, client: Any, isolated: bool
    ) -> Optional[ToolResult]:
        if client is None or not isolated:
            return None
        version = str(
            getattr(invocation.definition, "integration_api_version", "") or ""
        ) or None
        try:
            client.requested_tool_api_version = version
        except Exception as exc:
            safe_error = self.services.redact(str(exc))
            return self.services.security.sanitize_result(
                ToolResult.error(
                    f"工具 {invocation.tool_name} 无法应用 Provider API 版本 "
                    f"{version}：{safe_error}",
                    detail=classify_error(exc, invocation.definition),
                )
            )
        return None

    @staticmethod
    def _validate_input(invocation: _ToolInvocation) -> Optional[ToolResult]:
        schema = invocation.definition.input_schema
        errors = validate_tool_input(schema, invocation.input_data) if schema else []
        if errors:
            return ToolResult.error(f"Input validation failed: {errors}")
        return None

    def _run_handler(
        self, invocation: _ToolInvocation, handler: Any
    ) -> ToolResult:
        capacity = self.capacity_provider()
        if not capacity.acquire(blocking=False):
            return ToolResult(
                success=False,
                data={"execution_status": "capacity_exceeded"},
                error="当前工具执行资源已达到上限，请稍后重试",
            )
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ad-agent-tool")
        try:
            future = executor.submit(copy_context().run, self._invoke_handler, invocation, handler)
        except RuntimeError:
            capacity.release()
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        future.add_done_callback(lambda _future: capacity.release())
        try:
            result = future.result(
                timeout=max(invocation.deadline - time.monotonic(), 0.001)
            )
        except FutureTimeoutError:
            return self._timeout_result(invocation)
        except Exception as exc:
            return self._handler_error(invocation, exc)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return self._normalize_result(invocation, result)

    @staticmethod
    def _invoke_handler(invocation: _ToolInvocation, handler: Any) -> ToolResult:
        if invocation.cancel_event.is_set():
            return ToolResult(
                success=False,
                data={"execution_status": "cancelled"},
                error="异步任务已请求取消；未执行工具",
            )
        if hasattr(handler, "execute"):
            return handler.execute(invocation.ctx, invocation.input_data)
        if callable(handler):
            return handler(invocation.ctx, invocation.input_data)
        return ToolResult.error(
            f"Tool '{invocation.tool_name}' has no executable handler"
        )

    def _timeout_result(self, invocation: _ToolInvocation) -> ToolResult:
        invocation.cancel_event.set()
        uncertain_write = invocation.definition.is_write_tool
        status = "unknown" if uncertain_write else "timed_out"
        data = {"execution_status": status, "timeout": True}
        if uncertain_write:
            data.update({"requires_reconciliation": True, "effect_state": "unknown"})
        max_seconds = float(
            getattr(invocation.definition, "timeout_seconds", 30.0)
        )
        uncertainty = (
            "；这是外部写操作，结果未知，必须先进行状态核对，不能直接重试"
            if uncertain_write else ""
        )
        return ToolResult(
            success=False,
            data=data,
            error=(
                f"工具 {invocation.tool_name} 执行超过限制（最多 "
                f"{max_seconds:.3g} 秒）{uncertainty}"
            ),
            error_detail=classify_error(
                TimeoutError(f"tool {invocation.tool_name} exceeded deadline"),
                invocation.definition,
            ),
        )

    def _handler_error(
        self, invocation: _ToolInvocation, error: Exception
    ) -> ToolResult:
        safe_error = self.services.redact(str(error))
        detail = classify_error(error, invocation.definition)
        return self.services.security.sanitize_result(
            ToolResult.error(
                f"工具 {invocation.tool_name} 执行失败：{safe_error}", detail=detail
            )
        )

    def _normalize_result(
        self, invocation: _ToolInvocation, result: Any
    ) -> ToolResult:
        if not isinstance(result, ToolResult):
            return ToolResult.error(
                f"工具 {invocation.tool_name} 返回了无效结果；必须返回 ToolResult"
            )
        if time.monotonic() > invocation.deadline:
            return self._timeout_result(invocation)
        result = self.services.security.sanitize_result(result)
        result = self.services.security.enforce_result_limit(
            result, invocation.definition
        )
        return self.services.security.apply_read_data_boundary(
            invocation.tool_name, result
        )


class ToolExecutor:
    """Apply request gates, then delegate one call to the bounded executor."""

    def __init__(self, services: RuntimeExecutionServices):
        self.services = services
        self._in_flight_capacity = threading.BoundedSemaphore(64)
        self._runner = _ToolInvocationRunner(
            services, lambda: self._in_flight_capacity
        )

    def execute(
        self,
        ctx: Any,
        tool_name: str,
        input_data: dict[str, Any],
        request_clients: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        invocation = self._prepare_invocation(ctx, tool_name, input_data, request_clients)
        if isinstance(invocation, ToolResult):
            return invocation
        previous_deadline = ctx.metadata.get("tool_deadline") if ctx else None
        if ctx:
            ctx.metadata["tool_deadline"] = invocation.deadline
            ctx.metadata["cancel_event"] = invocation.cancel_event
        try:
            return self._runner.execute(invocation)
        finally:
            self._restore_context(ctx, previous_deadline)

    def _prepare_invocation(
        self,
        ctx: Any,
        tool_name: str,
        input_data: dict[str, Any],
        request_clients: Optional[dict[str, Any]],
    ) -> _ToolInvocation | ToolResult:
        definition, handler = self.services.get_registered_tool(tool_name)
        metadata = ctx.metadata if ctx else {}
        task_cancel = metadata.get("task_cancel_event")
        run_cancel = metadata.get("cancellation_event")
        cancelled = self._is_cancelled(task_cancel, run_cancel)
        if cancelled:
            return ToolResult(
                success=False,
                data={"execution_status": "cancelled"},
                error="异步任务已请求取消；未执行工具",
            )
        protected_paths = self.services.security.validate_input_redline(input_data)
        if protected_paths:
            return ToolResult.error(
                "请求包含禁止传入的凭证/账户配置字段：" + ", ".join(protected_paths)
            )
        preflight = self._preflight_error(
            ctx, definition, handler, tool_name, request_clients
        )
        if preflight:
            return preflight
        deadline, error = self._deadline(ctx, definition, tool_name)
        if error:
            return error
        return _ToolInvocation(
            ctx=ctx,
            definition=definition,
            handler=handler,
            input_data=input_data,
            request_clients=request_clients,
            deadline=deadline,
            cancel_event=_CancellationBridge(task_cancel, run_cancel),
        )

    @staticmethod
    def _is_cancelled(*signals: Any) -> bool:
        return any(
            signal is not None and signal.is_set()
            for signal in signals
            if callable(getattr(signal, "is_set", None))
        )

    def _preflight_error(
        self,
        ctx: Any,
        definition: ToolDefinition,
        handler: Any,
        tool_name: str,
        request_clients: Optional[dict[str, Any]],
    ) -> Optional[ToolResult]:
        write_error = self._live_write_error(
            ctx, definition, handler, tool_name, request_clients
        )
        if write_error:
            return write_error
        return self._read_client_error(ctx, definition, handler, tool_name, request_clients)

    def _live_write_error(
        self,
        ctx: Any,
        definition: ToolDefinition,
        handler: Any,
        tool_name: str,
        request_clients: Optional[dict[str, Any]],
    ) -> Optional[ToolResult]:
        mode = str((ctx.metadata if ctx else {}).get(
            "execution_mode", self.services.execution_mode,
        ))
        if not definition.is_write_tool or mode != "live":
            return None
        platform = self.services.normalize_namespace(definition.namespace)
        request_client = (request_clients or {}).get(platform)
        has_client = hasattr(handler, "client")
        handler_client = getattr(handler, "client", None) if has_client else None
        if not has_client:
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
        return None

    def _read_client_error(
        self,
        ctx: Any,
        definition: ToolDefinition,
        handler: Any,
        tool_name: str,
        request_clients: Optional[dict[str, Any]],
    ) -> Optional[ToolResult]:
        platform = self.services.normalize_namespace(definition.namespace)
        has_request_client = bool(
            isinstance(request_clients, dict) and request_clients.get(platform) is not None
        )
        if (
            definition.is_read_tool
            and not self.services.offline_mode
            and hasattr(handler, "client")
            and getattr(handler, "client", None) is None
            and not has_request_client
        ):
            return ToolResult.error(
                f"{tool_name} 没有配置 Provider Client；当前未启用 offline_mode，"
                "不会返回模拟查询数据"
            )
        return None

    @staticmethod
    def _deadline(
        ctx: Any, definition: ToolDefinition, tool_name: str
    ) -> tuple[float, Optional[ToolResult]]:
        metadata = ctx.metadata if ctx else {}
        now = time.monotonic()
        deadline = now + float(getattr(definition, "timeout_seconds", 30.0))
        turn_deadline = metadata.get("turn_deadline")
        if turn_deadline is not None:
            deadline = min(deadline, float(turn_deadline))
        if deadline <= now:
            return deadline, ToolResult(
                success=False,
                data={"execution_status": "timed_out"},
                error=f"工具 {tool_name} 在执行前已超过 timeout_seconds",
            )
        return deadline, None

    @staticmethod
    def _restore_context(ctx: Any, previous_deadline: Optional[float]) -> None:
        if not ctx:
            return
        if previous_deadline is None:
            ctx.metadata.pop("tool_deadline", None)
        else:
            ctx.metadata["tool_deadline"] = previous_deadline
        ctx.metadata.pop("cancel_event", None)
