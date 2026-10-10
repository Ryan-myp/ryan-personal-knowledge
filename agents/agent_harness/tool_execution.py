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

from .messages import AgentMessage, ToolCall
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
        tool_timeout_seconds: float | None = None,
        tool_max_retries: int = 0,
        tool_retry_delay_seconds: float = 0.0,
        tool_circuit: Optional[ToolCircuitBreaker] = None,
        max_tool_result_chars: int = 32_000,
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
    def _tool_cancellation_mode(cls, definition: Any) -> str:
        value = str(
            cls._tool_value(definition, "cancellation_mode", "cooperative")
            or "cooperative"
        ).strip().lower()
        return value if value in TOOL_CANCELLATION_MODES else "cooperative"

    @classmethod
    def _tool_is_write(cls, definition: Any) -> bool:
        effect = cls._tool_value(
            definition,
            "effect_class",
            cls._tool_value(definition, "effect", "read"),
        )
        effect = getattr(effect, "value", effect)
        return str(effect or "").strip().lower() in {"write", "external_write"}

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

        max_paths = 1 if self.max_tool_result_chars < 512 else 8
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
                    if self.tool_timeout_seconds is None:
                        output = execute(context, dict(call.arguments))
                    else:
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
                            output = future.result(
                                timeout=self.tool_timeout_seconds
                            )
                        except FutureTimeoutError as error:
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
                for key in (
                    "needs_input", "needs_confirmation", "confirmation_payload",
                    "interaction", "runtime_signals", "recovery_required",
                    "success", "effect_state", "data", "execution_status",
                ):
                    if key in decision:
                        result[key] = (
                            self._bound_tool_value(decision[key])
                            if key == "interaction"
                            else decision[key]
                        )
                return result
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
            result = {
                "tool_call_id": call.id,
                "name": call.name,
                "content": self._bound_tool_value(safe_output),
                "is_error": bool(
                    isinstance(safe_output, Mapping)
                    and safe_output.get("success") is False
                    and not uncertain_effect
                ),
                "terminate": False,
                "retry_count": retry_count,
            }
            if isinstance(safe_output, Mapping):
                for key in (
                    "needs_input", "needs_confirmation", "confirmation_payload",
                    "requires_confirmation", "interaction", "card_payload",
                    "runtime_signals", "recovery_required", "success",
                    "effect_state", "data", "execution_status",
                ):
                    if key in safe_output:
                        result[key] = (
                            self._bound_tool_value(safe_output[key])
                            if key in {"data", "interaction", "card_payload"}
                            else safe_output[key]
                        )
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
            cancellation_mode = self._tool_cancellation_mode(
                getattr(binding, "definition", None),
            )
            interrupted = self.interrupt_reason(request)
            if interrupted == "cancelled":
                result["cancelled"] = True
                result["terminate"] = True
                if cancellation_mode != "interruptible" and self._tool_is_write(
                    getattr(binding, "definition", None),
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

    def execute_tools(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        calls: Sequence[ToolCall],
        state: Any,
        read_cache: ToolReadCache | None = None,
        write_cache: ToolWriteReplayCache | None = None,
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
        pending = list(calls)
        completed: dict[str, dict[str, Any]] = {}
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
                else:
                    runnable.append(call)
            resolved_calls: list[ToolCall] = []
            batch_read_cache = read_cache or ToolReadCache()
            binding_errors: dict[str, dict[str, Any]] = {}
            for call in runnable:
                resolved, error = self._resolve_argument_bindings(
                    call, completed,
                )
                if error:
                    binding_errors[str(call.id)] = {
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": "Tool dependency argument could not be resolved",
                        "is_error": True,
                        "terminate": False,
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
        return [results[str(call.id)] for call in calls]

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
