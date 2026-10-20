"""Application-neutral Tool execution coordinator.

The Agent loop owns model turns and transcript state.  This module owns the
bounded Tool execution concerns: dependency batches, policy hooks, timeouts,
retries, circuit breaking, cancellation and model-facing output limits.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextvars import copy_context
from typing import Any, Callable, Mapping, Optional, Sequence

from .core.interfaces import ToolResult
from .messages import AgentMessage, ToolCall
from .core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS
from .redaction import redact_for_persistence
from .reliability import ToolCircuitBreaker
from .runtime_kernel import TurnRequest


TOOL_CANCELLATION_MODES = frozenset({
    "cooperative",
    "interruptible",
    "not_interruptible",
})


class ToolCapacityError(RuntimeError):
    """The bounded Tool invocation pool has no free execution slot."""


class ToolReadCache:
    """Share bounded replay-safe read results within one Agent Run."""

    def __init__(self, max_entries: int = 256) -> None:
        self._initialize(max_entries=max_entries)

    def _initialize(
        self,
        *,
        max_entries: int,
        cache_result: Callable[[Any], bool] | None = None,
        retain_exceptions: bool = True,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._lock = threading.Lock()
        self._entries: dict[str, Future[tuple[Any, int]]] = {}
        self._max_entries = int(max_entries)
        self._cache_result = cache_result or (lambda _value: True)
        self._retain_exceptions = bool(retain_exceptions)

    def get_or_invoke(
        self,
        key: str,
        operation: Callable[[], tuple[Any, int]],
    ) -> tuple[tuple[Any, int], bool]:
        with self._lock:
            future = self._entries.get(key)
            owner = future is None
            if future is None:
                while len(self._entries) >= self._max_entries:
                    oldest_completed = next(
                        (
                            entry_key for entry_key, entry in self._entries.items()
                            if entry.done()
                        ),
                        None,
                    )
                    if oldest_completed is None:
                        break
                    self._entries.pop(oldest_completed, None)
                if len(self._entries) < self._max_entries:
                    future = Future()
                    self._entries[key] = future
                else:
                    owner = False
        if future is None:
            return operation(), False
        if owner:
            try:
                value = operation()
                future.set_result(value)
                if not self._cache_result(value):
                    with self._lock:
                        if self._entries.get(key) is future:
                            self._entries.pop(key, None)
            except BaseException as error:
                if not future.done():
                    future.set_exception(error)
                if not self._retain_exceptions:
                    with self._lock:
                        if self._entries.get(key) is future:
                            self._entries.pop(key, None)
                raise
        return future.result(), not owner

    def clear(self) -> None:
        """Discard prior reads after a possible side effect or failed read."""
        with self._lock:
            self._entries.clear()


class ToolWriteReplayCache(ToolReadCache):
    """Prevent identical writes from running twice inside one Agent Run."""

    def __init__(self, max_entries: int = 256) -> None:
        super()._initialize(
            max_entries=max_entries,
            retain_exceptions=True,
        )


class ToolCallContext:
    """Context passed to a trusted Tool policy hook or executor."""

    def __init__(
        self,
        *,
        request: TurnRequest,
        assistant_message: AgentMessage,
        tool_call: ToolCall,
        state: Any,
        tool_definition: Any = None,
    ) -> None:
        self.request = request
        self.assistant_message = assistant_message
        self.tool_call = tool_call
        self.state = state
        self.tool_definition = tool_definition


class ToolExecutionCoordinator:
    """Execute a model Tool plan without embedding business knowledge."""

    _TRUNCATION_PRIORITY = {
        "type": 0,
        "kind": 1,
        "question": 2,
        "prompt": 3,
        "needs_input": 4,
        "needs_confirmation": 5,
        "confirmation_payload": 6,
        "payload": 7,
        "success": 0,
        "error": 1,
        "data_status": 2,
        "execution_status": 3,
        "effect_state": 4,
        "requires_reconciliation": 5,
        "query_summary": 6,
        "total_count": 6,
        "total": 7,
        "count": 8,
        "has_more": 9,
        "next_page": 10,
        "page_info": 11,
        "data": 12,
    }

    def __init__(
        self,
        *,
        tool_catalog: Any,
        emit: Callable[..., None],
        interrupt_reason: Callable[[TurnRequest], Optional[str]],
        assert_not_interrupted: Callable[[TurnRequest], None],
        before_tool_call: Optional[Callable[[ToolCallContext], Any]] = None,
        after_tool_call: Optional[Callable[[ToolCallContext, Any], Any]] = None,
        tool_execution: str = "parallel",
        max_parallel_tools: int = 8,
        max_inflight_tool_invocations: int = 64,
        tool_timeout_seconds: float | None = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        tool_max_retries: int = 0,
        tool_retry_delay_seconds: float = 0.0,
        tool_circuit: Optional[ToolCircuitBreaker] = None,
        max_tool_result_chars: int = 32_000,
        max_interaction_chars: int = 256_000,
    ) -> None:
        if tool_execution not in {"sequential", "parallel"}:
            raise ValueError("tool_execution must be sequential or parallel")
        if max_parallel_tools <= 0:
            raise ValueError("max_parallel_tools must be positive")
        if max_inflight_tool_invocations <= 0:
            raise ValueError("max_inflight_tool_invocations must be positive")
        if tool_timeout_seconds is not None and tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        if tool_max_retries < 0:
            raise ValueError("tool_max_retries must be non-negative")
        if tool_retry_delay_seconds < 0:
            raise ValueError("tool_retry_delay_seconds must be non-negative")
        if max_tool_result_chars <= 0:
            raise ValueError("max_tool_result_chars must be positive")
        if max_interaction_chars <= 0:
            raise ValueError("max_interaction_chars must be positive")
        self.tool_catalog = tool_catalog
        self.emit = emit
        self.interrupt_reason = interrupt_reason
        self.assert_not_interrupted = assert_not_interrupted
        self.before_tool_call = before_tool_call
        self.after_tool_call = after_tool_call
        self.tool_execution = tool_execution
        self.max_parallel_tools = int(max_parallel_tools)
        self._inflight_tool_slots = threading.BoundedSemaphore(
            int(max_inflight_tool_invocations)
        )
        self.tool_timeout_seconds = tool_timeout_seconds
        self.tool_max_retries = int(tool_max_retries)
        self.tool_retry_delay_seconds = float(tool_retry_delay_seconds)
        self.tool_circuit = tool_circuit or ToolCircuitBreaker()
        self.max_tool_result_chars = int(max_tool_result_chars)
        self.max_interaction_chars = int(max_interaction_chars)

    @staticmethod
    def _tool_value(definition: Any, name: str, default: Any = None) -> Any:
        if isinstance(definition, Mapping):
            return definition.get(name, default)
        return getattr(definition, name, default)

    @classmethod
    def _tool_replay_safe(cls, definition: Any) -> bool:
        effect = cls._tool_value(
            definition,
            "effect_class",
            cls._tool_value(definition, "effect", None),
        )
        effect = getattr(effect, "value", effect)
        if str(effect or "").strip().lower() not in {"read", "none"}:
            return False
        replay = cls._tool_value(definition, "replay_policy", "")
        replay = getattr(replay, "value", replay)
        return str(replay).strip().lower() in {"", "safe", "idempotent"}

    def _call_replay_safe(self, call: ToolCall) -> bool:
        if self.tool_catalog is None:
            return False
        try:
            binding = self.tool_catalog.get_binding(call.name)
        except (KeyError, TypeError, AttributeError):
            return False
        return self._tool_replay_safe(getattr(binding, "definition", None))

    @classmethod
    def _tool_is_write(cls, definition: Any) -> bool:
        effect = cls._tool_value(
            definition,
            "effect_class",
            cls._tool_value(definition, "effect", "read"),
        )
        effect = getattr(effect, "value", effect)
        return str(effect or "").strip().lower() in {
            "write", "external_write", "internal_write",
        }

    @staticmethod
    def _serialized_tool_value(value: Any) -> str:
        try:
            return json.dumps(
                value, ensure_ascii=False, sort_keys=True, default=str,
            )
        except (TypeError, ValueError):
            return json.dumps(str(value), ensure_ascii=False)

    def _replay_cache_key(
        self,
        binding: Any,
        context: ToolCallContext,
        call: ToolCall,
    ) -> str:
        raw_arguments = dict(call.arguments)
        invocation_key: Any = raw_arguments
        key_builder = getattr(binding.executor, "replay_key", None)
        if callable(key_builder):
            try:
                candidate = key_builder(context, raw_arguments)
                if candidate is not None:
                    invocation_key = candidate
            except Exception as error:
                self.emit(
                    "tool_replay_key_error",
                    context.request,
                    tool_call_id=call.id,
                    tool_name=call.name,
                    error_type=type(error).__name__,
                )
        request = context.request
        identity = {
            "tool": call.name,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "execution_mode": request.execution_mode or "dry_run",
            "invocation": invocation_key,
        }
        serialized = self._serialized_tool_value(identity).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def _truncate_tool_text(self, value: str, budget: int) -> str:
        marker = "\n...[tool output truncated]"
        low, high = 0, len(value)
        best = ""
        while low <= high:
            middle = (low + high) // 2
            suffix = marker if middle < len(value) else ""
            candidate = value[:middle] + suffix
            if len(self._serialized_tool_value(candidate)) <= budget:
                best = candidate
                low = middle + 1
            else:
                high = middle - 1
        return best

    def _compact_tool_value(
        self,
        value: Any,
        budget: int,
        path: str,
    ) -> tuple[Any, list[str]]:
        if len(self._serialized_tool_value(value)) <= budget:
            return value, []
        if isinstance(value, str):
            return self._truncate_tool_text(value, budget), [path or "$"]
        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            truncated: list[str] = []
            current_size = 2
            keys = sorted(
                value,
                key=lambda key: (
                    self._TRUNCATION_PRIORITY.get(str(key).lower(), 100),
                    str(key).lower(),
                ),
            )
            for key in keys:
                field = str(key)
                field_path = f"{path}.{field}" if path else field
                key_size = len(self._serialized_tool_value(field))
                field_overhead = key_size + 2 + (2 if result else 0)
                child_budget = budget - current_size - field_overhead
                if child_budget < 2:
                    truncated.append(field_path)
                    continue
                child, child_truncated = self._compact_tool_value(
                    value[key], child_budget, field_path,
                )
                child_size = len(self._serialized_tool_value(child))
                if current_size + field_overhead + child_size > budget:
                    truncated.append(field_path)
                    continue
                result[field] = child
                current_size += field_overhead + child_size
                truncated.extend(child_truncated)
            return result, truncated
        if isinstance(value, (list, tuple)):
            result = []
            truncated: list[str] = []
            current_size = 2
            for index, child_value in enumerate(value):
                child_path = f"{path}[{index}]" if path else f"[{index}]"
                child_budget = budget - current_size - (2 if result else 0)
                if child_budget < 2:
                    truncated.append(path or "$")
                    break
                child, child_truncated = self._compact_tool_value(
                    child_value, child_budget, child_path,
                )
                child_size = len(self._serialized_tool_value(child))
                extra_size = child_size + (2 if result else 0)
                if current_size + extra_size > budget:
                    truncated.append(path or "$")
                    break
                result.append(child)
                current_size += extra_size
                truncated.extend(child_truncated)
            if len(result) < len(value) and (path or "$") not in truncated:
                truncated.append(path or "$")
            return result, truncated
        return self._truncate_tool_text(str(value), budget), [path or "$"]

    def _query_content(self, value: Any, definition: Any) -> Any:
        model_value = value
        data = value.get("data") if isinstance(value, Mapping) else None
        if (
            isinstance(data, Mapping)
            and isinstance(data.get("parameter_selections"), list)
        ):
            # Signed, target-specific proofs stay in the Tool result for the
            # caller; the model only needs the underlying candidate records.
            model_value = dict(value)
            model_data = dict(data)
            model_data.pop("parameter_selections", None)
            model_value["data"] = model_data
        collection = self._tool_value(definition, "result_items_key")
        data = model_value.get("data") if isinstance(model_value, Mapping) else None
        rows = data.get(collection) if isinstance(data, Mapping) and collection else None
        if not isinstance(rows, list) or self._tool_is_write(definition):
            return self._bound_tool_value(model_value)
        summary = {
            "collection": collection, "returned_count": len(rows),
            "context_count": len(rows), "context_truncated": False,
        }
        content = self._bound_tool_value({
            **model_value, "data": {"query_summary": summary, **data},
        })
        preview = content.get("data") if isinstance(content, Mapping) else None
        visible_summary = preview.get("query_summary") if isinstance(preview, Mapping) else None
        if isinstance(visible_summary, dict):
            visible_rows = preview.get(collection)
            visible_summary["context_count"] = len(visible_rows) if isinstance(visible_rows, list) else 0
            visible_summary["context_truncated"] = bool(content.get("output_truncated"))
        return content

    def _retained_tool_value(self, value: Any, definition: Any) -> Any:
        """Keep API evidence under the Tool contract, not the model budget."""
        limit = min(1_000_000, int(self._tool_value(
            definition, "max_output_bytes", 1_000_000,
        )))
        if limit < 2:
            raise ValueError("max_output_bytes must be at least two bytes")
        if len(self._serialized_tool_value(value).encode("utf-8")) <= limit:
            return value
        bounded, paths = self._compact_tool_value(value, max(2, limit // 4 - 64), "data")
        retained = dict(bounded) if isinstance(bounded, Mapping) else {"items": bounded}
        retained["output_truncated"] = True
        retained["truncated_fields"] = list(dict.fromkeys(paths))[:1]
        if len(self._serialized_tool_value(retained).encode("utf-8")) > limit:
            marker = {"output_truncated": True}
            return marker if len(self._serialized_tool_value(marker)) <= limit else {}
        return retained

    def _bound_tool_value(self, value: Any) -> Any:
        text = (
            value
            if isinstance(value, str)
            else self._serialized_tool_value(value)
        )
        if len(text) <= self.max_tool_result_chars:
            return value
        if isinstance(value, str):
            return self._truncate_tool_text(value, self.max_tool_result_chars)

        max_paths = min(8, max(1, self.max_tool_result_chars // 512))
        max_path_chars = 32 if self.max_tool_result_chars < 512 else 96
        marker_reserve = len(self._serialized_tool_value({
            "output_truncated": True,
            "truncated_fields": ["x" * max_path_chars] * max_paths,
        }))
        content_budget = max(2, self.max_tool_result_chars - marker_reserve)
        bounded, truncated = self._compact_tool_value(
            value, content_budget, "",
        )
        paths = list(dict.fromkeys(truncated))[:max_paths]
        paths = [path[:max_path_chars] for path in paths] or ["$"]
        if isinstance(bounded, Mapping):
            result = dict(bounded)
            result["output_truncated"] = True
            result["truncated_fields"] = paths
            return result
        if isinstance(value, (list, tuple)):
            return {
                "items": bounded,
                "output_truncated": True,
                "truncated_fields": paths,
            }
        return bounded

    def _bound_interaction_value(self, value: Any) -> tuple[Any, bool]:
        """Keep complete interaction contracts separate from model context limits."""
        if len(self._serialized_tool_value(value)) <= self.max_interaction_chars:
            return value, False
        return {
            "type": "interaction_error",
            "error_code": "interaction_payload_too_large",
            "max_chars": self.max_interaction_chars,
        }, True

    def _invoke_tool(
        self,
        binding: Any,
        context: ToolCallContext,
        call: ToolCall,
        definition: Any,
        batch_read_cache: ToolReadCache | None = None,
        write_cache: ToolWriteReplayCache | None = None,
    ) -> tuple[Any, int, str | None]:
        execute = getattr(binding.executor, "execute", None)
        if not callable(execute):
            execute = binding.executor if callable(binding.executor) else None
        if not callable(execute):
            raise TypeError(f"Tool '{call.name}' has no executor")
        max_retries = self.tool_max_retries if self._tool_replay_safe(definition) else 0

        def invoke() -> tuple[Any, int]:
            retry_count = 0
            for attempt in range(max_retries + 1):
                self.assert_not_interrupted(context.request)
                try:
                    if not self._inflight_tool_slots.acquire(blocking=False):
                        raise ToolCapacityError(
                            "Tool execution capacity exhausted"
                        )
                    pool = None
                    try:
                        pool = ThreadPoolExecutor(
                            max_workers=1,
                            thread_name_prefix="agent-tool-call",
                        )
                        future: Future[Any] = pool.submit(
                            copy_context().run,
                            execute,
                            context,
                            dict(call.arguments),
                        )
                    except Exception:
                        self._inflight_tool_slots.release()
                        if pool is not None:
                            pool.shutdown(wait=False, cancel_futures=True)
                        raise
                    future.add_done_callback(
                        lambda _completed: self._inflight_tool_slots.release()
                    )
                    try:
                        deadline = (
                            time.monotonic() + self.tool_timeout_seconds
                            if self.tool_timeout_seconds is not None else None
                        )
                        while True:
                            remaining = (
                                deadline - time.monotonic()
                                if deadline is not None else None
                            )
                            if remaining is not None and remaining <= 0:
                                future.cancel()
                                self.emit(
                                    "tool_timeout",
                                    context.request,
                                    tool_call_id=call.id,
                                    tool_name=call.name,
                                    timeout_seconds=self.tool_timeout_seconds,
                                )
                                raise TimeoutError(
                                    f"Tool '{call.name}' timed out"
                                )
                            wait_seconds = (
                                min(0.1, remaining)
                                if remaining is not None else 0.1
                            )
                            try:
                                output = future.result(timeout=wait_seconds)
                                break
                            except FutureTimeoutError as error:
                                if future.done():
                                    raise
                                interrupted = self.interrupt_reason(
                                    context.request,
                                )
                                if interrupted is not None:
                                    cancelled_before_start = future.cancel()
                                    unsafe_write = (
                                        interrupted in {
                                            "cancelled",
                                            "session_lease_lost",
                                        }
                                        and self._tool_is_write(definition)
                                        and not cancelled_before_start
                                    )
                                    output = {
                                        "success": False,
                                        "execution_status": interrupted,
                                        "cancelled": interrupted == "cancelled",
                                        "cancelled_before_execution": (
                                            cancelled_before_start
                                        ),
                                        "error": (
                                            "Run cancellation requested"
                                            if interrupted == "cancelled"
                                            else "Runtime session lease was lost"
                                        ),
                                        "effect_state": (
                                            "unknown" if unsafe_write else "none"
                                        ),
                                        "recovery_required": unsafe_write,
                                        "runtime_signals": {
                                            interrupted: True,
                                            **(
                                                {"effect_state": "unknown"}
                                                if unsafe_write else {}
                                            ),
                                        },
                                    }
                                    break
                                if (
                                    deadline is not None
                                    and time.monotonic() >= deadline
                                ):
                                    future.cancel()
                                    self.emit(
                                        "tool_timeout",
                                        context.request,
                                        tool_call_id=call.id,
                                        tool_name=call.name,
                                        timeout_seconds=self.tool_timeout_seconds,
                                    )
                                    raise TimeoutError(
                                        f"Tool '{call.name}' timed out"
                                    ) from error
                    finally:
                        pool.shutdown(wait=False, cancel_futures=True)
                    if isinstance(output, ToolResult):
                        output = output.to_dict()
                    return output, retry_count
                except Exception as error:
                    retryable = (
                        isinstance(
                            error,
                            (TimeoutError, FutureTimeoutError, ConnectionError),
                        )
                        or "transient" in type(error).__name__.lower()
                    )
                    if not retryable or attempt >= max_retries:
                        raise
                    retry_count += 1
                    self.emit(
                        "tool_retry",
                        context.request,
                        tool_call_id=call.id,
                        tool_name=call.name,
                        attempt=retry_count,
                        error_type=type(error).__name__,
                    )
                    if self.tool_retry_delay_seconds:
                        time.sleep(self.tool_retry_delay_seconds)
            raise RuntimeError("tool invocation loop exited unexpectedly")

        if self._tool_replay_safe(definition):
            if batch_read_cache is None:
                output, retry_count = invoke()
                return output, retry_count, None
            cache = batch_read_cache
            coalesced_kind = "read"
        elif self._tool_is_write(definition) and write_cache is not None:
            cache = write_cache
            coalesced_kind = "write"
        else:
            output, retry_count = invoke()
            return output, retry_count, None
        cache_key = self._replay_cache_key(binding, context, call)
        (output, retry_count), coalesced = cache.get_or_invoke(
            cache_key,
            invoke,
        )
        return output, retry_count, coalesced_kind if coalesced else None

    def execute_one(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        call: ToolCall,
        state: Any,
        batch_read_cache: ToolReadCache | None = None,
        write_cache: ToolWriteReplayCache | None = None,
    ) -> dict[str, Any]:
        binding = None
        if self.tool_catalog is not None:
            try:
                binding = self.tool_catalog.get_binding(call.name)
            except Exception:
                binding = None
        context = ToolCallContext(
            request=request,
            assistant_message=assistant,
            tool_call=call,
            state=state,
            tool_definition=getattr(binding, "definition", None),
        )
        interrupted = self.interrupt_reason(request)
        if interrupted is not None:
            return {
                "tool_call_id": call.id,
                "name": call.name,
                "content": interrupted,
                "is_error": True,
                "terminate": True,
                "cancelled": interrupted == "cancelled",
                "recovery_required": interrupted == "session_lease_lost",
                "effect_state": (
                    "unknown" if interrupted == "session_lease_lost" else "none"
                ),
                "runtime_signals": {interrupted: True},
            }
        if callable(self.before_tool_call):
            try:
                decision = self.before_tool_call(context)
            except Exception as error:
                return {
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": "Tool policy evaluation failed",
                    "is_error": True,
                    "terminate": True,
                    "recovery_required": True,
                    "effect_state": "unknown",
                    "runtime_signals": {
                        "tool_policy_error": True,
                        "tool_policy_error_type": type(error).__name__,
                    },
                }
            if isinstance(decision, Mapping) and decision.get("block"):
                result = {
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": str(decision.get("reason") or "tool call blocked"),
                    "is_error": True,
                    "terminate": bool(decision.get("terminate")),
                }
                interaction_too_large = False
                for key in (
                    "needs_input", "needs_confirmation", "confirmation_payload",
                    "interaction", "runtime_signals", "recovery_required",
                    "success", "effect_state", "data", "execution_status",
                ):
                    if key in decision:
                        if key == "interaction":
                            result[key], interaction_too_large = (
                                self._bound_interaction_value(decision[key])
                            )
                        else:
                            result[key] = decision[key]
                if interaction_too_large:
                    result.update({
                        "content": (
                            "Interactive payload exceeds the Runtime limit; "
                            "no partial interaction was returned."
                        ),
                        "terminate": True,
                        "needs_input": True,
                        "runtime_signals": {
                            **dict(result.get("runtime_signals") or {}),
                            "interaction_payload_too_large": True,
                        },
                    })
                return result
            call = context.tool_call
        try:
            if self.tool_catalog is None:
                raise KeyError(f"Tool '{call.name}' not found")
            if binding is None:
                binding = self.tool_catalog.get_binding(call.name)
            definition = getattr(binding, "definition", None)
            if not self.tool_circuit.allow(call.name):
                return {
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": "Tool temporarily unavailable",
                    "is_error": True,
                    "terminate": False,
                    "runtime_signals": {"tool_circuit_open": True},
                }
            output, retry_count, coalesced = self._invoke_tool(
                binding,
                context,
                call,
                definition,
                batch_read_cache,
                write_cache,
            )
            interrupted = self.interrupt_reason(request)
            if interrupted is None:
                self.tool_circuit.record_success(call.name)
            safe_output = redact_for_persistence(output)
            output_data = (
                safe_output.get("data")
                if isinstance(safe_output, Mapping)
                and isinstance(safe_output.get("data"), Mapping)
                else {}
            )
            uncertain_effect = (
                isinstance(safe_output, Mapping)
                and (
                    safe_output.get("effect_state") == "unknown"
                    or safe_output.get("execution_status") == "unknown"
                    or safe_output.get("requires_reconciliation") is True
                    or output_data.get("effect_state") == "unknown"
                    or output_data.get("execution_status") == "unknown"
                    or output_data.get("requires_reconciliation") is True
                )
            )
            error_detail = (
                safe_output.get("error_detail")
                if isinstance(safe_output, Mapping)
                else None
            )
            non_retriable_error = (
                isinstance(safe_output, Mapping)
                and safe_output.get("success") is False
                and isinstance(error_detail, Mapping)
                and str(error_detail.get("category") or "").strip().lower()
                == "non_retriable"
            )
            result = {
                "tool_call_id": call.id,
                "name": call.name,
                "content": self._query_content(safe_output, definition),
                "is_error": bool(
                    isinstance(safe_output, Mapping)
                    and safe_output.get("success") is False
                    and not uncertain_effect
                ),
                "terminate": non_retriable_error,
                "retry_count": retry_count,
            }
            if non_retriable_error:
                result["runtime_signals"] = {
                    "non_retriable_tool_error": True,
                }
            if isinstance(safe_output, Mapping):
                interaction_too_large = False
                for key in (
                    "needs_input", "needs_confirmation", "confirmation_payload",
                    "requires_confirmation", "interaction", "card_payload",
                    "runtime_signals", "recovery_required", "success",
                    "effect_state", "data", "execution_status",
                ):
                    if key in safe_output:
                        if key == "interaction":
                            result[key], interaction_too_large = (
                                self._bound_interaction_value(
                                    safe_output[key],
                                )
                            )
                        elif key in {"data", "card_payload"}:
                            result[key] = self._retained_tool_value(
                                safe_output[key], definition,
                            )
                        else:
                            result[key] = safe_output[key]
                if interaction_too_large:
                    result.update({
                        "content": (
                            "Interactive payload exceeds the Runtime limit; "
                            "no partial interaction was returned."
                        ),
                        "terminate": True,
                        "needs_input": True,
                        "runtime_signals": {
                            **dict(result.get("runtime_signals") or {}),
                            "interaction_payload_too_large": True,
                        },
                    })
                if result.get("requires_confirmation"):
                    result["needs_confirmation"] = True
            if coalesced == "read":
                result["runtime_signals"] = {
                    **dict(result.get("runtime_signals") or {}),
                    "duplicate_read_coalesced": True,
                }
            elif coalesced == "write":
                result["runtime_signals"] = {
                    **dict(result.get("runtime_signals") or {}),
                    "duplicate_write_coalesced": True,
                }
            if uncertain_effect:
                result.update({
                    "terminate": True,
                    "recovery_required": True,
                    "effect_state": "unknown",
                    "runtime_signals": {
                        **dict(result.get("runtime_signals") or {}),
                        "effect_state": "unknown",
                        "provider_effect_unknown": True,
                    },
                })
            if interrupted == "cancelled":
                result["cancelled"] = True
                result["terminate"] = True
                cancelled_before_execution = bool(
                    isinstance(safe_output, Mapping)
                    and safe_output.get("cancelled_before_execution")
                    and safe_output.get("effect_state") == "none"
                )
                if (
                    self._tool_is_write(getattr(binding, "definition", None))
                    and not cancelled_before_execution
                ):
                    result["recovery_required"] = True
                    result["effect_state"] = "unknown"
                    result["runtime_signals"] = {
                        "cancelled": True,
                        "effect_state": "unknown",
                    }
                else:
                    result["runtime_signals"] = {"cancelled": True}
            elif interrupted == "session_lease_lost":
                result.update({
                    "terminate": True,
                    "recovery_required": True,
                    "effect_state": "unknown",
                    "runtime_signals": {"session_lease_lost": True},
                })
        except Exception as error:
            if not isinstance(error, ToolCapacityError):
                self.tool_circuit.record_failure(call.name)
            effect_unknown = (
                self._tool_is_write(getattr(binding, "definition", None))
                and isinstance(error, (TimeoutError, FutureTimeoutError))
            )
            result = {
                "tool_call_id": call.id,
                "name": call.name,
                "content": redact_for_persistence(str(error)),
                "is_error": True,
                "terminate": False,
                "retry_count": 0,
            }
            if effect_unknown:
                result.update({
                    "recovery_required": True,
                    "effect_state": "unknown",
                    "runtime_signals": {
                        "tool_timeout": True,
                        "effect_state": "unknown",
                    },
                })
            elif isinstance(error, ToolCapacityError):
                result["runtime_signals"] = {"tool_capacity_exhausted": True}
        if callable(self.after_tool_call):
            try:
                override = self.after_tool_call(context, result)
            except Exception as error:
                return {
                    **result,
                    "content": "Tool post-execution policy failed",
                    "is_error": True,
                    "terminate": True,
                    "recovery_required": True,
                    "effect_state": "unknown",
                    "runtime_signals": {
                        **dict(result.get("runtime_signals") or {}),
                        "tool_policy_error": True,
                        "tool_policy_error_type": type(error).__name__,
                    },
                }
            if isinstance(override, Mapping):
                result = {**result, **dict(override)}
        return result

    def _emit_tool_end(
        self,
        request: TurnRequest,
        call: ToolCall,
        result: Mapping[str, Any],
    ) -> None:
        self.emit(
            "tool_execution_end",
            request,
            tool_call_id=call.id,
            tool_name=call.name,
            result=dict(result),
            is_error=bool(result.get("is_error")),
        )

    @staticmethod
    def _schema_properties(schema: Any) -> Mapping[str, Any]:
        if isinstance(schema, Mapping):
            properties = schema.get("properties")
        else:
            properties = getattr(schema, "properties", None)
        return properties if isinstance(properties, Mapping) else {}

    @classmethod
    def _declares_input_path(cls, definition: Any, path: str) -> bool:
        schema = cls._tool_value(definition, "input_schema", None)
        parts = path.split(".")
        for index, part in enumerate(parts):
            spec = cls._schema_properties(schema).get(part)
            if spec is None:
                return False
            if index < len(parts) - 1:
                schema = spec
        return True

    @staticmethod
    def _value_at_path(value: Any, path: str) -> Any:
        current = value
        for part in path.split("."):
            if not isinstance(current, Mapping) or part not in current:
                return None
            current = current[part]
        return current

    @staticmethod
    def _set_input_path(
        target: dict[str, Any], path: str, value: Any,
    ) -> None:
        parts = path.split(".")
        current = target
        for part in parts[:-1]:
            child = current.get(part)
            if not isinstance(child, Mapping):
                child = {}
            else:
                child = dict(child)
            current[part] = child
            current = child
        current[parts[-1]] = value

    @staticmethod
    def _resource_id_from_output(value: Any, field_name: str) -> Any:
        """Find one unambiguous value for a Tool-declared resource ID field."""
        pending = [value]
        identifiers: dict[str, Any] = {}
        visited = 0
        while pending and visited < 10_000:
            current = pending.pop()
            visited += 1
            if isinstance(current, Mapping):
                candidate = current.get(field_name)
                if (
                    isinstance(candidate, (str, int))
                    and not isinstance(candidate, bool)
                    and str(candidate).strip()
                ):
                    identifiers.setdefault(str(candidate), candidate)
                pending.extend(current.values())
            elif isinstance(current, (list, tuple)):
                pending.extend(current)
        if len(identifiers) != 1:
            return None
        return next(iter(identifiers.values()))

    @classmethod
    def _resource_scope_matches(
        cls,
        parent_call: ToolCall,
        parent_definition: Any,
        child_call: ToolCall,
        child_definition: Any,
    ) -> bool:
        parent_fields = {
            str(item).strip()
            for item in cls._tool_value(parent_definition, "scope_fields", ()) or ()
            if str(item).strip()
        }
        child_fields = {
            str(item).strip()
            for item in cls._tool_value(child_definition, "scope_fields", ()) or ()
            if str(item).strip()
        }
        shared_fields = parent_fields & child_fields
        if (parent_fields or child_fields) and not shared_fields:
            return False
        for field in shared_fields:
            parent_scope = cls._value_at_path(parent_call.arguments, field)
            child_scope = cls._value_at_path(child_call.arguments, field)
            if (
                parent_scope not in (None, "")
                and child_scope not in (None, "")
                and str(parent_scope) != str(child_scope)
            ):
                return False
        return True

    @classmethod
    def _tool_definitions_for_calls(
        cls, calls: Sequence[ToolCall], tool_catalog: Any
    ) -> dict[str, Any]:
        definitions: dict[str, Any] = {}
        for call in calls:
            try:
                binding = tool_catalog.get_binding(call.name)
            except (AttributeError, KeyError, TypeError):
                continue
            definitions[str(call.id)] = getattr(binding, "definition", None)
        return definitions

    @classmethod
    def _resource_producers(
        cls,
        calls: Sequence[ToolCall],
        definitions: Mapping[str, Any],
    ) -> dict[tuple[str, str], list[tuple[ToolCall, Any]]]:
        producers: dict[tuple[str, str], list[tuple[ToolCall, Any]]] = {}
        for call in calls:
            definition = definitions.get(str(call.id))
            contract = {
                key: str(cls._tool_value(definition, key, "") or "").strip().lower()
                for key in ("action", "namespace", "resource_type", "resource_id_field")
            }
            if (
                contract["action"] != "create"
                or not contract["namespace"]
                or not contract["resource_type"]
                or not contract["resource_id_field"]
            ):
                continue
            producers.setdefault(
                (contract["namespace"], contract["resource_type"]), []
            ).append(
                (call, definition)
            )
        return producers

    @classmethod
    def _has_required_resource_producer_inputs(
        cls,
        call: ToolCall,
        definition: Any,
    ) -> bool:
        schema = cls._tool_value(definition, "input_schema", None)
        required = cls._tool_value(schema, "required", ()) or ()
        parent_field = str(
            cls._tool_value(definition, "parent_resource_id_field", "") or ""
        ).strip()
        bound_fields = {
            str(item.target_field)
            for item in call.argument_bindings
            if str(getattr(item, "target_field", "") or "").strip()
        }
        for field in required:
            field = str(field).strip()
            if not field or field == parent_field or field in bound_fields:
                continue
            if cls._value_at_path(call.arguments, field) in (None, ""):
                return False
        return True

    @classmethod
    def _resource_candidates(
        cls,
        call: ToolCall,
        definition: Any,
        resource_type: str,
        producers: Mapping[tuple[str, str], Sequence[tuple[ToolCall, Any]]],
    ) -> tuple[list[tuple[ToolCall, Any]], str | None]:
        namespace = str(cls._tool_value(definition, "namespace", "") or "").strip().lower()
        candidates = [
            item for item in producers.get((namespace, resource_type), ())
            if item[0].id != call.id
        ]
        explicit = [item for item in candidates if item[0].id in set(call.depends_on)]
        if explicit:
            candidates = explicit
        scoped = [
            item for item in candidates
            if cls._resource_scope_matches(item[0], item[1], call, definition)
        ]
        if candidates and not scoped:
            return [], "scope_mismatch"
        return scoped, None

    @staticmethod
    def _add_call_dependency(call: ToolCall, dependency_id: str) -> ToolCall:
        return ToolCall(
            id=call.id,
            name=call.name,
            arguments=call.arguments,
            depends_on=tuple(dict.fromkeys((*call.depends_on, dependency_id))),
            argument_bindings=call.argument_bindings,
        )

    @classmethod
    def _bind_parent_resource(
        cls,
        call: ToolCall,
        definition: Any,
        producers: Mapping[tuple[str, str], Sequence[tuple[ToolCall, Any]]],
        historical_resource_ids: Mapping[str, Any] | None = None,
    ) -> tuple[ToolCall, tuple[str, str, str] | None, str | None, str | None]:
        if str(cls._tool_value(definition, "action", "") or "").lower() != "create":
            return call, None, None, None
        parent_type = str(
            cls._tool_value(definition, "parent_resource_type", "") or ""
        ).strip().lower()
        parent_field = str(
            cls._tool_value(definition, "parent_resource_id_field", "") or ""
        ).strip()
        if not parent_type or not parent_field:
            return call, None, None, None
        if not cls._declares_input_path(definition, parent_field):
            return call, None, None, "invalid_parent_contract"
        has_argument_binding = any(
            item.target_field == parent_field for item in call.argument_bindings
        )
        if has_argument_binding:
            return call, None, None, None

        has_value = cls._value_at_path(call.arguments, parent_field) not in (None, "")
        schema = cls._tool_value(definition, "input_schema", None)
        properties = cls._tool_value(schema, "properties", {}) or {}
        if has_value and parent_field in properties:
            from .core.interfaces import ToolSchema
            from .core.tool_registry import validate_tool_input
            has_value = not validate_tool_input(
                ToolSchema(properties={parent_field: properties[parent_field]}),
                {parent_field: cls._value_at_path(call.arguments, parent_field)},
            )
        if has_value:
            candidates, rejection = cls._resource_candidates(
                call, definition, parent_type, producers,
            )
            historical_ids = historical_resource_ids or {}
            historical_candidates = [
                item for item in candidates if item[0].id in historical_ids
            ]
            current_candidates = [
                item for item in candidates if item[0].id not in historical_ids
            ]
            if rejection or current_candidates or not historical_candidates:
                return call, None, None, None
            provided_value = str(cls._value_at_path(call.arguments, parent_field))
            if any(
                str(historical_ids[item[0].id]) == provided_value
                for item in historical_candidates
            ):
                return call, None, None, None
            if len(historical_candidates) > 1:
                return call, None, None, "ambiguous_parent"
            candidates = historical_candidates
        else:
            candidates, rejection = cls._resource_candidates(
                call, definition, parent_type, producers,
            )

        if rejection:
            return call, None, None, rejection
        if len(candidates) > 1:
            return call, None, None, "ambiguous_parent"
        if not candidates:
            return call, None, "missing_parent", None
        parent_call, parent_definition = candidates[0]
        source_field = str(
            cls._tool_value(parent_definition, "resource_id_field", "") or ""
        ).strip()
        if not source_field:
            return call, None, None, "invalid_parent_contract"
        return (
            cls._add_call_dependency(call, str(parent_call.id)),
            (parent_field, str(parent_call.id), source_field),
            None,
            None,
        )

    @classmethod
    def _related_resource_fields(cls, definition: Any) -> list[str]:
        if str(cls._tool_value(definition, "action", "") or "").lower() != "create":
            return []
        related_type = str(
            cls._tool_value(definition, "related_resource_type", "") or ""
        ).strip().lower()
        raw_fields = cls._tool_value(
            definition, "related_resource_id_fields", (),
        ) or ()
        if not related_type or not isinstance(raw_fields, (list, tuple, set)):
            return []
        return list(dict.fromkeys(
            str(item).strip() for item in raw_fields if str(item).strip()
        ))

    @classmethod
    def _bind_related_resource(
        cls,
        call: ToolCall,
        definition: Any,
        target_field: str,
        producers: Mapping[tuple[str, str], Sequence[tuple[ToolCall, Any]]],
    ) -> tuple[tuple[str, str, str] | None, str | None, str | None]:
        if not cls._declares_input_path(definition, target_field):
            return None, None, "invalid_parent_contract"
        related_type = str(
            cls._tool_value(definition, "related_resource_type", "") or ""
        ).strip().lower()
        candidates, rejection = cls._resource_candidates(
            call, definition, related_type, producers,
        )
        if rejection:
            return None, None, rejection
        if len(candidates) > 1:
            return None, None, "ambiguous_parent"
        if not candidates:
            return None, "missing_parent", None
        parent_call, parent_definition = candidates[0]
        source_field = str(
            cls._tool_value(parent_definition, "resource_id_field", "") or ""
        ).strip()
        if not source_field:
            return None, None, "invalid_parent_contract"
        return (
            (target_field, str(parent_call.id), source_field),
            str(parent_call.id),
            None,
        )

    @classmethod
    def _bind_related_resources(
        cls,
        calls: Sequence[ToolCall],
        definitions: Mapping[str, Any],
        producers: Mapping[tuple[str, str], Sequence[tuple[ToolCall, Any]]],
        resource_bindings: dict[str, list[tuple[str, str, str]]],
    ) -> tuple[dict[str, list[str]], dict[str, str], str | None]:
        dependencies: dict[str, list[str]] = {}
        unresolved: dict[str, str] = {}
        rejection = None
        for call in calls:
            definition = definitions.get(str(call.id))
            for target_field in cls._related_resource_fields(definition):
                already_bound = any(
                    item.target_field == target_field for item in call.argument_bindings
                ) or any(
                    item[0] == target_field
                    for item in resource_bindings.get(str(call.id), [])
                )
                if (
                    already_bound
                    or cls._value_at_path(call.arguments, target_field) not in (None, "")
                ):
                    continue
                binding, dependency, reason = cls._bind_related_resource(
                    call, definition, target_field, producers,
                )
                if binding:
                    resource_bindings.setdefault(str(call.id), []).append(binding)
                if binding and dependency:
                    dependencies.setdefault(str(call.id), []).append(dependency)
                elif dependency:
                    unresolved[str(call.id)] = dependency
                if reason:
                    rejection = reason
        return dependencies, unresolved, rejection

    @classmethod
    def _extend_resource_dependencies(
        cls, calls: Sequence[ToolCall], dependencies: Mapping[str, Sequence[str]]
    ) -> list[ToolCall]:
        updated = []
        for call in calls:
            for dependency_id in dependencies.get(str(call.id), ()):
                call = cls._add_call_dependency(call, dependency_id)
            updated.append(call)
        return updated

    @classmethod
    def _declared_resource_dependencies(
        cls,
        calls: Sequence[ToolCall],
        tool_catalog: Any,
        resource_history: Sequence[Mapping[str, Any]] = (),
    ) -> tuple[
        list[ToolCall],
        dict[str, list[tuple[str, str, str]]],
        dict[str, str],
        str | None,
    ]:
        """Bind child resource IDs using Tool-declared parent contracts."""
        definitions = cls._tool_definitions_for_calls(calls, tool_catalog)
        historical_calls = []
        historical_definitions = {}
        historical_resource_ids = {}
        for record in resource_history:
            if not isinstance(record, Mapping):
                continue
            history_id = record.get("history_id")
            tool_name = record.get("tool_name")
            arguments = record.get("arguments")
            if (
                not isinstance(history_id, str)
                or not history_id
                or not isinstance(tool_name, str)
                or not tool_name
                or not isinstance(arguments, Mapping)
                or not isinstance(record.get("data"), Mapping)
            ):
                continue
            try:
                binding = tool_catalog.get_binding(tool_name)
            except (AttributeError, KeyError, TypeError):
                continue
            definition = getattr(binding, "definition", None)
            if (
                str(cls._tool_value(definition, "action", "") or "").lower()
                != "create"
            ):
                continue
            historical_call = ToolCall(
                id=history_id,
                name=tool_name,
                arguments=dict(arguments),
            )
            historical_calls.append(historical_call)
            historical_definitions[history_id] = definition
            resource_id_field = str(record.get("resource_id_field") or "").strip()
            resource_id = record["data"].get(resource_id_field)
            if resource_id_field and resource_id not in (None, ""):
                historical_resource_ids[history_id] = resource_id
        definitions.update(historical_definitions)
        producers = cls._resource_producers(
            (
                *historical_calls,
                *(
                    call for call in calls
                    if cls._has_required_resource_producer_inputs(
                        call,
                        definitions.get(str(call.id)),
                    )
                ),
            ),
            definitions,
        )
        bound_calls: list[ToolCall] = []
        resource_bindings: dict[str, list[tuple[str, str, str]]] = {}
        unresolved: dict[str, str] = {}
        rejection = None
        for call in calls:
            updated, binding, missing, reason = cls._bind_parent_resource(
                call,
                definitions.get(str(call.id)),
                producers,
                historical_resource_ids,
            )
            bound_calls.append(updated)
            if binding:
                resource_bindings.setdefault(str(call.id), []).append(binding)
            if missing:
                unresolved[str(call.id)] = missing
            if reason:
                rejection = reason

        related_dependencies, related_unresolved, related_rejection = (
            cls._bind_related_resources(
                calls, definitions, producers, resource_bindings,
            )
        )
        unresolved.update(related_unresolved)
        rejection = related_rejection or rejection
        bound_calls = cls._extend_resource_dependencies(
            bound_calls, related_dependencies,
        )
        return (
            bound_calls,
            resource_bindings,
            unresolved,
            rejection,
        )

    def _remember_run_resources(
        self,
        calls: Sequence[ToolCall],
        results: Sequence[Mapping[str, Any]],
        resource_history: list[Mapping[str, Any]] | None,
    ) -> None:
        if resource_history is None:
            return
        for call, result in zip(calls, results):
            if (
                not isinstance(result, Mapping)
                or result.get("is_error")
                or result.get("recovery_required")
                or result.get("effect_state") == "unknown"
                or result.get("needs_input")
                or result.get("needs_confirmation")
            ):
                continue
            try:
                binding = self.tool_catalog.get_binding(call.name)
            except (AttributeError, KeyError, TypeError):
                continue
            definition = getattr(binding, "definition", None)
            if str(self._tool_value(definition, "action", "") or "").lower() != "create":
                continue
            resource_id_field = str(
                self._tool_value(definition, "resource_id_field", "") or ""
            ).strip()
            namespace = str(
                self._tool_value(definition, "namespace", "") or ""
            ).strip()
            resource_type = str(
                self._tool_value(definition, "resource_type", "") or ""
            ).strip()
            resource_id = self._resource_id_from_output(
                result.get("data"), resource_id_field,
            )
            if (
                not resource_id_field
                or not namespace
                or not resource_type
                or resource_id in (None, "")
            ):
                continue
            dedupe_key = (
                call.name,
                resource_id_field,
                str(resource_id),
            )
            existing = {
                (
                    str(item.get("tool_name") or ""),
                    str(item.get("resource_id_field") or ""),
                    str(item.get("data", {}).get(item.get("resource_id_field")) or ""),
                )
                for item in resource_history
                if isinstance(item, Mapping)
                and isinstance(item.get("data"), Mapping)
            }
            if dedupe_key in existing:
                continue
            scope_arguments = {}
            for field_name in (
                self._tool_value(definition, "scope_fields", ()) or ()
            ):
                value = self._value_at_path(call.arguments, str(field_name))
                if value not in (None, ""):
                    self._set_input_path(
                        scope_arguments, str(field_name), value,
                    )
            history_id = f"__run_resource_{len(resource_history)}"
            resource_history.append({
                "history_id": history_id,
                "tool_name": call.name,
                "arguments": scope_arguments,
                "resource_id_field": resource_id_field,
                "data": {resource_id_field: resource_id},
            })
        del resource_history[:-64]

    def _resolve_argument_bindings(
        self,
        call: ToolCall,
        completed: Mapping[str, Mapping[str, Any]],
    ) -> tuple[ToolCall | None, str | None]:
        if not call.argument_bindings:
            return call, None
        try:
            binding = self.tool_catalog.get_binding(call.name)
        except (AttributeError, KeyError, TypeError):
            return None, "target Tool contract is unavailable"
        definition = getattr(binding, "definition", None)
        arguments = dict(call.arguments)
        for reference in call.argument_bindings:
            if not self._declares_input_path(definition, reference.target_field):
                return None, "target input field is not declared by the Tool"
            source = completed.get(reference.source_call_id)
            if not isinstance(source, Mapping):
                return None, "dependency result is unavailable"
            value = self._value_at_path(
                source.get("content"), reference.source_path,
            )
            if value in (None, ""):
                return None, "dependency result did not contain the bound value"
            self._set_input_path(arguments, reference.target_field, value)
        return ToolCall(
            id=call.id,
            name=call.name,
            arguments=arguments,
            depends_on=call.depends_on,
            argument_bindings=call.argument_bindings,
        ), None

    def _resolve_resource_bindings(
        self,
        call: ToolCall,
        completed: Mapping[str, Mapping[str, Any]],
        bindings: Sequence[tuple[str, str, str]],
    ) -> tuple[ToolCall | None, str | None]:
        resolved, error = self._resolve_argument_bindings(call, completed)
        if error or resolved is None or not bindings:
            return resolved, error
        arguments = dict(resolved.arguments)
        for target_field, source_call_id, resource_id_field in bindings:
            source = completed.get(source_call_id)
            if not isinstance(source, Mapping):
                return None, "declared parent Tool result is unavailable"
            value = self._resource_id_from_output(
                source.get("data"), resource_id_field,
            )
            if value in (None, ""):
                return None, "declared parent Tool result did not contain one resource ID"
            self._set_input_path(arguments, target_field, value)
        return ToolCall(
            id=resolved.id,
            name=resolved.name,
            arguments=arguments,
            depends_on=resolved.depends_on,
            argument_bindings=resolved.argument_bindings,
        ), None

    def execute_tools(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        calls: Sequence[ToolCall],
        state: Any,
        read_cache: ToolReadCache | None = None,
        write_cache: ToolWriteReplayCache | None = None,
        resource_history: list[Mapping[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if not calls:
            return []
        by_id = {str(call.id): call for call in calls}
        if len(by_id) != len(calls):
            return [{
                "tool_call_id": str(call.id),
                "name": call.name,
                "content": "duplicate tool call id",
                "is_error": True,
                "terminate": True,
            } for call in calls]
        calls, resource_bindings, unresolved_dependencies, batch_rejection = (
            self._declared_resource_dependencies(
                calls,
                self.tool_catalog,
                resource_history or (),
            )
        )
        if batch_rejection:
            signal = {
                "scope_mismatch": "tool_resource_scope_mismatch",
                "ambiguous_parent": "tool_resource_dependency_ambiguous",
                "invalid_parent_contract": "tool_resource_dependency_contract_invalid",
            }[batch_rejection]
            content = {
                "scope_mismatch": (
                    "Tool batch rejected: declared parent and child resources "
                    "have different scopes; no Tool was executed."
                ),
                "ambiguous_parent": (
                    "Tool batch rejected: multiple declared parent resources "
                    "could supply a required input; no Tool was executed."
                ),
                "invalid_parent_contract": (
                    "Tool batch rejected: declared parent Tool has no resource "
                    "ID contract; no Tool was executed."
                ),
            }[batch_rejection]
            return [{
                "tool_call_id": str(call.id),
                "name": call.name,
                "content": content,
                "is_error": True,
                "terminate": True,
                "needs_input": True,
                "runtime_signals": {
                    signal: True,
                },
            } for call in calls]
        pending = list(calls)
        completed: dict[str, dict[str, Any]] = {
            str(record["history_id"]): {"data": record["data"]}
            for record in resource_history or ()
            if isinstance(record, Mapping)
            and isinstance(record.get("history_id"), str)
            and isinstance(record.get("data"), Mapping)
        }
        results: dict[str, dict[str, Any]] = {}
        context = request.context if isinstance(request.context, Mapping) else {}
        visible_names = context.get("_harness_visible_tool_names")
        allowed_names = (
            {str(name) for name in visible_names}
            if isinstance(visible_names, (list, tuple, set, frozenset))
            else None
        )
        if request.tool_allowlist is not None:
            explicit_names = set(request.tool_allowlist)
            allowed_names = (
                explicit_names
                if allowed_names is None
                else allowed_names & explicit_names
            )
        while pending:
            ready = [
                call for call in pending
                if all(str(dep) in completed for dep in call.depends_on)
            ]
            if not ready:
                return [{
                    "tool_call_id": str(call.id),
                    "name": call.name,
                    "content": "tool call dependency cycle or missing dependency",
                    "is_error": True,
                    "terminate": True,
                    "runtime_signals": {"tool_dependency_error": True},
                } for call in pending]
            runnable: list[ToolCall] = []
            for call in ready:
                if allowed_names is not None and call.name not in allowed_names:
                    result = {
                        "tool_call_id": str(call.id),
                        "name": call.name,
                        "content": (
                            "Tool was not available in the active Tool selection"
                        ),
                        "is_error": True,
                        "terminate": True,
                        "runtime_signals": {"tool_allowlist_violation": True},
                    }
                    completed[str(call.id)] = result
                    results[str(call.id)] = result
                    continue
                failed = [
                    completed[str(dep)] for dep in call.depends_on
                    if completed[str(dep)].get("is_error")
                ]
                if failed:
                    terminal_dependency = any(
                        item.get("terminate") for item in failed
                    )
                    result = {
                        "tool_call_id": str(call.id),
                        "name": call.name,
                        "content": "dependency failed; Tool was not executed",
                        "is_error": True,
                        "terminate": terminal_dependency,
                        "runtime_signals": {"tool_dependency_failed": True},
                    }
                    completed[str(call.id)] = result
                    results[str(call.id)] = result
                elif str(call.id) in unresolved_dependencies:
                    reason = unresolved_dependencies[str(call.id)]
                    result = {
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": (
                            "Required parent resource ID is missing; provide an "
                            "existing parent ID or include its create Tool."
                        ),
                        "is_error": True,
                        "terminate": False,
                        "needs_input": True,
                        "runtime_signals": {
                            f"tool_resource_dependency_{reason}": True,
                        },
                    }
                    completed[str(call.id)] = result
                    results[str(call.id)] = result
                else:
                    runnable.append(call)
            resolved_calls: list[ToolCall] = []
            batch_read_cache = read_cache or ToolReadCache()
            binding_errors: dict[str, dict[str, Any]] = {}
            for call in runnable:
                resolved, error = self._resolve_resource_bindings(
                    call,
                    completed,
                    resource_bindings.get(str(call.id), ()),
                )
                if error:
                    binding_errors[str(call.id)] = {
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": (
                            "Parent Tool completed without one concrete resource "
                            "ID; dependent Tool was not executed."
                        ),
                        "is_error": True,
                        "terminate": False,
                        "needs_input": True,
                        "runtime_signals": {
                            "tool_argument_binding_error": True,
                        },
                    }
                elif resolved is not None:
                    resolved_calls.append(resolved)
            for call in (*resolved_calls, *(
                item for item in runnable
                if str(item.id) in binding_errors
            )):
                self.emit(
                    "tool_execution_start",
                    request,
                    tool_call_id=call.id,
                    tool_name=call.name,
                    arguments=dict(call.arguments),
                )
            if self.tool_execution == "sequential" or len(resolved_calls) <= 1:
                batch = [
                    self.execute_one(
                        request,
                        assistant,
                        call,
                        state,
                        batch_read_cache,
                        write_cache,
                    )
                    for call in resolved_calls
                ]
            elif resolved_calls:
                pool = ThreadPoolExecutor(
                    max_workers=min(self.max_parallel_tools, len(resolved_calls)),
                    thread_name_prefix="agent-tool",
                )
                futures = [
                    pool.submit(
                        copy_context().run,
                        self.execute_one,
                        request,
                        assistant,
                        call,
                        state,
                        batch_read_cache,
                        write_cache,
                    )
                    for call in resolved_calls
                ]
                try:
                    batch = [future.result() for future in futures]
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)
            else:
                batch = []
            batch_by_id = {
                str(call.id): result
                for call, result in zip(resolved_calls, batch)
            }
            for call in runnable:
                result = binding_errors.get(str(call.id)) or batch_by_id.get(
                    str(call.id),
                )
                if result is None:
                    result = {
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": "Tool dependency argument could not be resolved",
                        "is_error": True,
                        "terminate": False,
                        "runtime_signals": {
                            "tool_argument_binding_error": True,
                        },
                    }
                self._emit_tool_end(request, call, result)
                completed[str(call.id)] = result
                results[str(call.id)] = result
            cache_invalidated = any(
                not self._call_replay_safe(call) for call in runnable
            ) or any(
                result.get("is_error")
                for result in batch_by_id.values()
            )
            if read_cache is not None and cache_invalidated:
                read_cache.clear()
            pending = [
                call for call in pending
                if str(call.id) not in completed
            ]
        ordered_results = [results[str(call.id)] for call in calls]
        self._remember_run_resources(calls, ordered_results, resource_history)
        return ordered_results

    def execute_emitting(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        call: ToolCall,
        state: Any,
    ) -> dict[str, Any]:
        self.emit(
            "tool_execution_start",
            request,
            tool_call_id=call.id,
            tool_name=call.name,
            arguments=dict(call.arguments),
        )
        result = self.execute_one(request, assistant, call, state)
        self._emit_tool_end(request, call, result)
        return result


__all__ = [
    "TOOL_CANCELLATION_MODES",
    "ToolCallContext",
    "ToolExecutionCoordinator",
    "ToolReadCache",
    "ToolWriteReplayCache",
]
