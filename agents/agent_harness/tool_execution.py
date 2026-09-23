"""Application-neutral Tool execution coordinator.

The Agent loop owns model turns and transcript state.  This module owns the
bounded Tool execution concerns: dependency batches, policy hooks, timeouts,
retries, circuit breaking, cancellation and model-facing output limits.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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

    def _bound_tool_value(self, value: Any) -> Any:
        if isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(
                    value, ensure_ascii=False, sort_keys=True, default=str,
                )
            except (TypeError, ValueError):
                text = str(value)
        if len(text) <= self.max_tool_result_chars:
            return value
        marker = "\n...[tool output truncated]"
        limit = max(0, self.max_tool_result_chars - len(marker))
        return text[:limit] + marker

    def _invoke_tool(
        self,
        binding: Any,
        context: ToolCallContext,
        call: ToolCall,
        definition: Any,
    ) -> tuple[Any, int]:
        execute = getattr(binding.executor, "execute", None)
        if not callable(execute):
            execute = binding.executor if callable(binding.executor) else None
        if not callable(execute):
            raise TypeError(f"Tool '{call.name}' has no executor")
        max_retries = self.tool_max_retries if self._tool_replay_safe(definition) else 0
        retry_count = 0
        for attempt in range(max_retries + 1):
            self.assert_not_interrupted(context.request)
            try:
                if self.tool_timeout_seconds is None:
                    output = execute(context, dict(call.arguments))
                else:
                    pool = ThreadPoolExecutor(
                        max_workers=1, thread_name_prefix="agent-tool-call",
                    )
                    future: Future[Any] = pool.submit(
                        execute, context, dict(call.arguments),
                    )
                    try:
                        output = future.result(timeout=self.tool_timeout_seconds)
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

    def execute_one(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        call: ToolCall,
        state: Any,
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
                    "runtime_signals", "recovery_required", "success",
                    "effect_state", "data", "execution_status",
                ):
                    if key in decision:
                        result[key] = decision[key]
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
            output, retry_count = self._invoke_tool(
                binding, context, call, definition,
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
                    "runtime_signals", "recovery_required", "success",
                    "effect_state", "data", "execution_status",
                ):
                    if key in safe_output:
                        result[key] = (
                            self._bound_tool_value(safe_output[key])
                            if key == "data"
                            else safe_output[key]
                        )
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

    def execute_tools(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        calls: Sequence[ToolCall],
        state: Any,
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
                failed = [
                    completed[str(dep)] for dep in call.depends_on
                    if completed[str(dep)].get("is_error")
                ]
                if failed:
                    result = {
                        "tool_call_id": str(call.id),
                        "name": call.name,
                        "content": "dependency failed; Tool was not executed",
                        "is_error": True,
                        "terminate": False,
                        "runtime_signals": {"tool_dependency_failed": True},
                    }
                    completed[str(call.id)] = result
                    results[str(call.id)] = result
                else:
                    runnable.append(call)
            for call in runnable:
                self.emit(
                    "tool_execution_start",
                    request,
                    tool_call_id=call.id,
                    tool_name=call.name,
                    arguments=dict(call.arguments),
                )
            if self.tool_execution == "sequential" or len(runnable) <= 1:
                batch = [
                    self.execute_one(request, assistant, call, state)
                    for call in runnable
                ]
            else:
                pool = ThreadPoolExecutor(
                    max_workers=min(self.max_parallel_tools, len(runnable)),
                    thread_name_prefix="agent-tool",
                )
                futures = [
                    pool.submit(
                        self.execute_one, request, assistant, call, state,
                    )
                    for call in runnable
                ]
                try:
                    batch = [future.result() for future in futures]
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)
            for call, result in zip(runnable, batch):
                self._emit_tool_end(request, call, result)
                completed[str(call.id)] = result
                results[str(call.id)] = result
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
]
