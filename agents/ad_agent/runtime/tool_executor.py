"""Generic Tool execution engine.

Authorization and workflow planning happen outside this class. This class
only executes a selected, already-registered Tool through the RuntimeServices
port, enforcing request deadlines and provider-client isolation.
"""

from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Optional

from ..core.interfaces import ToolResult
from ..core.tool_registry import validate_tool_input
from ..core.features import RuntimeServices


class ToolExecutor:
    """Execute one registered Tool after the caller's policy gates."""

    def __init__(self, services: RuntimeServices):
        self.services = services
        # A timed-out Python handler cannot be force-killed safely. Bound the
        # number of such lingering invocations so repeated provider/network
        # stalls cannot create an unbounded number of background threads.
        self._in_flight_capacity = threading.BoundedSemaphore(64)

    def execute(
        self,
        ctx: Any,
        tool_name: str,
        input_data: dict[str, Any],
        request_clients: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        definition, handler = self.services.get_registered_tool(tool_name)
        task_cancel_event = (
            ctx.metadata.get("task_cancel_event") if ctx else None
        )
        if task_cancel_event is not None and task_cancel_event.is_set():
            return ToolResult(
                success=False,
                data={"execution_status": "cancelled"},
                error="异步任务已请求取消；未执行工具",
            )
        protected_paths = self.services.security.validate_input_redline(input_data)
        if protected_paths:
            return ToolResult.error(
                "请求包含禁止传入的凭证/账户配置字段："
                + ", ".join(protected_paths)
            )

        if definition.is_write_tool and self.services.execution_mode == "live":
            platform = self.services.canonical_platform(definition.platform)
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

        turn_deadline = ctx.metadata.get("turn_deadline") if ctx else None
        now = time.monotonic()
        deadline = now + float(getattr(definition, "timeout_seconds", 30.0))
        if turn_deadline is not None:
            deadline = min(deadline, float(turn_deadline))
        if deadline <= now:
            return ToolResult(
                success=False,
                data={"execution_status": "timed_out"},
                error=f"工具 {tool_name} 在执行前已超过 timeout_seconds",
            )

        previous_deadline = ctx.metadata.get("tool_deadline") if ctx else None
        cancel_event = threading.Event()
        if ctx:
            ctx.metadata["tool_deadline"] = deadline
            ctx.metadata["cancel_event"] = cancel_event

        def timeout_result() -> ToolResult:
            cancel_event.set()
            is_uncertain_write = bool(definition.is_write_tool)
            status = "unknown" if is_uncertain_write else "timed_out"
            data = {
                "execution_status": status,
                "timeout": True,
            }
            if is_uncertain_write:
                data.update({
                    "requires_reconciliation": True,
                    "provider_state": "unknown",
                })
            return ToolResult(
                success=False,
                data=data,
                error=(
                    f"工具 {tool_name} 执行超过限制（最多 "
                    f"{float(getattr(definition, 'timeout_seconds', 30.0)):.3g} 秒）"
                    + (
                        "；这是外部写操作，结果未知，必须先进行状态核对，不能直接重试"
                        if is_uncertain_write else ""
                    )
                ),
            )

        def prepare_handler(source_handler: Any, source_client: Any = None):
            if source_client is None:
                return source_handler, False
            client_type = type(source_client)
            timeout_setter = getattr(client_type, "set_request_timeout", None)
            timeout_attribute = "request_timeout" in getattr(source_client, "__dict__", {})
            expected = str(
                getattr(definition, "provider_api_version", "") or ""
            ).strip()
            client_state = getattr(source_client, "__dict__", {})
            actual_value = (
                client_state.get("api_version")
                if isinstance(client_state, dict) else None
            )
            if actual_value in (None, ""):
                actual_value = getattr(type(source_client), "api_version", "")
            actual = str(actual_value or "").strip()
            needs_version_marker = bool(expected and actual and expected != actual)
            if (
                not callable(timeout_setter)
                and not timeout_attribute
                and not needs_version_marker
            ):
                return source_handler, False
            try:
                isolated_handler = copy.copy(source_handler)
                isolated_client = copy.copy(source_client)
            except Exception as exc:
                if expected and actual and expected != actual:
                    raise RuntimeError(
                        f"{tool_name} 的 Provider Client 不支持请求级隔离，"
                        "无法安全使用版本 adapter"
                    ) from exc
                if not callable(timeout_setter) and not timeout_attribute:
                    return source_handler, False
                raise RuntimeError(
                    f"{tool_name} 的 Provider Client 无法创建请求级隔离副本"
                ) from exc
            remaining = max(deadline - time.monotonic(), 0.001)
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
            expected = str(
                getattr(definition, "provider_api_version", "") or ""
            ).strip()
            if not expected or client is None:
                return None
            checker = getattr(type(client), "supports_tool_api_version", None)
            if callable(checker):
                compatible = bool(checker(client, expected))
            else:
                client_state = getattr(client, "__dict__", {})
                actual_value = (
                    client_state.get("api_version")
                    if isinstance(client_state, dict) else None
                )
                if actual_value in (None, ""):
                    actual_value = getattr(type(client), "api_version", "")
                compatible = not actual_value or str(actual_value) == expected
            if compatible:
                return None
            client_state = getattr(client, "__dict__", {})
            actual_value = (
                client_state.get("api_version")
                if isinstance(client_state, dict) else None
            )
            if actual_value in (None, ""):
                actual_value = getattr(type(client), "api_version", "")
            supported = getattr(type(client), "SUPPORTED_API_VERSIONS", ()) or ()
            return (
                f"{tool_name} 要求 Provider API {expected}，当前 Client 为 "
                f"{actual_value or 'unknown'}；支持版本: {list(supported)}。"
                "请升级 Client 或提供版本 adapter"
            )

        if (
            definition.is_read_tool
            and not self.services.offline_mode
            and hasattr(handler, "client")
            and getattr(handler, "client", None) is None
        ):
            return ToolResult.error(
                f"{tool_name} 没有配置 Provider Client；当前未启用 offline_mode，"
                "不会返回模拟查询数据"
            )

        try:
            if not request_clients:
                invocation_handler, isolated = prepare_handler(
                    handler, getattr(handler, "client", None)
                )
            else:
                client = request_clients.get(
                    self.services.canonical_platform(definition.platform)
                )
                if client is None or not hasattr(handler, "client"):
                    invocation_handler, isolated = handler, False
                else:
                    invocation_handler, isolated = prepare_handler(handler, client)

            active_client = getattr(invocation_handler, "client", None)
            version_error = provider_version_error(active_client)
            if version_error:
                return ToolResult.error(version_error)
            if active_client is not None and isolated:
                try:
                    active_client.requested_tool_api_version = str(
                        getattr(definition, "provider_api_version", "") or ""
                    ) or None
                except Exception:
                    pass

            errors = validate_tool_input(
                definition.input_schema, input_data
            ) if definition.input_schema else []
            if errors:
                return ToolResult.error(f"Input validation failed: {errors}")

            def invoke() -> ToolResult:
                if task_cancel_event is not None and task_cancel_event.is_set():
                    return ToolResult(
                        success=False,
                        data={"execution_status": "cancelled"},
                        error="异步任务已请求取消；未执行工具",
                    )
                if hasattr(invocation_handler, "execute"):
                    return invocation_handler.execute(ctx, input_data)
                if callable(invocation_handler):
                    return invocation_handler(ctx, input_data)
                return ToolResult.error(
                    f"Tool '{tool_name}' has no executable handler"
                )

            # Both read and write handlers run behind the same cooperative
            # deadline. A Python thread cannot be force-killed; when a write
            # exceeds the deadline ``timeout_result`` deliberately reports an
            # unknown provider state so recovery/reconciliation can decide the
            # next action instead of treating it as safely retryable.
            if not self._in_flight_capacity.acquire(blocking=False):
                return ToolResult(
                    success=False,
                    data={"execution_status": "capacity_exceeded"},
                    error="当前工具执行资源已达到上限，请稍后重试",
                )
            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="ad-agent-tool"
            )
            try:
                future = executor.submit(invoke)
            except Exception:
                self._in_flight_capacity.release()
                executor.shutdown(wait=False, cancel_futures=True)
                raise

            # Release only when the actual handler thread exits. Releasing in
            # the timeout path would allow every timed-out call to create one
            # more thread while the old provider call is still running.
            future.add_done_callback(lambda _future: self._in_flight_capacity.release())
            try:
                result = future.result(
                    timeout=max(deadline - time.monotonic(), 0.001)
                )
            except FutureTimeoutError:
                return timeout_result()
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            if not isinstance(result, ToolResult):
                # A Capability implementation must return the common result
                # contract. Fail closed here so an arbitrary handler return
                # value cannot be mistaken for successful provider evidence.
                result = ToolResult.error(
                    f"工具 {tool_name} 返回了无效结果；必须返回 ToolResult"
                )
            if time.monotonic() > deadline:
                return timeout_result()
            result = self.services.security.enforce_result_limit(result, definition)
            return self.services.security.apply_read_data_boundary(
                tool_name, result
            )
        finally:
            if ctx:
                if previous_deadline is None:
                    ctx.metadata.pop("tool_deadline", None)
                else:
                    ctx.metadata["tool_deadline"] = previous_deadline
                ctx.metadata.pop("cancel_event", None)
