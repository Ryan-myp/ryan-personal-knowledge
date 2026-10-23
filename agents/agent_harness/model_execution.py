"""Bounded model execution, streaming, retries, fallback and Run token budgets."""

from __future__ import annotations

import math
import re
import threading
import uuid
from contextvars import copy_context
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Optional, Sequence, TYPE_CHECKING

from .messages import AgentMessage, ModelTurn, ToolCall
from .model_limits import (
    DEFAULT_MODEL_OUTPUT_CHARS, DEFAULT_STREAM_CHUNKS,
    ModelOutputLimitError, ModelTimeoutError,
    model_input_chars, model_output_chars, positive_integer,
)
from .model_stream import consume_model_stream
from .core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS
from .runtime_kernel import TurnRequest

if TYPE_CHECKING:
    from .agent import AgentState


class ModelCapacityError(RuntimeError):
    """All model slots are occupied, including timed-out calls."""


class ModelBudgetExceededError(RuntimeError):
    """The provider returned usage beyond the configured Run budget."""


class ModelUnavailableError(RuntimeError):
    """No model adapter is configured."""


class _ModelInvocationFailure(RuntimeError):
    def __init__(self, error: Exception, retryable: bool) -> None:
        super().__init__(type(error).__name__)
        self.error = error
        self.retryable = retryable


@dataclass(frozen=True)
class ModelExecutionOptions:
    timeout_seconds: float | None = DEFAULT_EXECUTION_TIMEOUT_SECONDS
    max_inflight: int = 32
    max_retries: int = 0
    retry_delay_seconds: float = 0.0
    max_stream_delta_chars: int = 4096
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_model_output_chars: int = DEFAULT_MODEL_OUTPUT_CHARS
    max_stream_chunks: int = DEFAULT_STREAM_CHUNKS

    def __post_init__(self) -> None:
        for name in ("max_model_output_chars", "max_stream_chunks"):
            positive_integer(name, getattr(self, name))
        for name in ("max_inflight", "max_stream_delta_chars"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "timeout_seconds",
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_retries < 0 or self.retry_delay_seconds < 0:
            raise ValueError("model retry bounds must be non-negative")
        if (
            self.timeout_seconds is not None
            and not math.isfinite(self.timeout_seconds)
        ) or not math.isfinite(self.retry_delay_seconds):
            raise ValueError("model time bounds must be finite")


@dataclass
class _ModelInvocation:
    request: TurnRequest
    model_request: TurnRequest
    state: AgentState
    messages: Sequence[AgentMessage]
    tools: Sequence[Any]
    abort_event: threading.Event | None
    lifecycle_events: bool
    provider_index: int = 0
    deadline: float | None = None
    stream_output_started: bool = False
    attempt_started_at: float | None = None
    model_call_id: str = ""
    prepare_duration_ms: float = 0.0
    input_chars: int = 0


class ModelExecutionCoordinator:
    """Execute model adapters without owning Run or transcript lifecycle."""

    def __init__(
        self,
        *,
        options: ModelExecutionOptions,
        providers: Callable[[], Sequence[Any]],
        prepare: Callable[..., Any],
        normalize: Callable[[Any], ModelTurn],
        emit: Callable[..., None],
        assert_not_interrupted: Callable[..., None],
    ) -> None:
        self.options = options
        self.providers = providers
        self.prepare = prepare
        self.normalize = normalize
        self.emit = emit
        self.assert_not_interrupted = assert_not_interrupted
        self._model_slots = threading.BoundedSemaphore(options.max_inflight)

    @staticmethod
    def _provider_name(provider: Any) -> str:
        return str(
            getattr(provider, "model_name", None)
            or getattr(provider, "name", None)
            or provider.__class__.__name__
        )

    @staticmethod
    def _retryable_model_error(error: Exception) -> bool:
        if isinstance(error, (TimeoutError, ConnectionError, FutureTimeoutError)):
            return True
        status = getattr(error, "status_code", None)
        if isinstance(status, int) and (status == 429 or status >= 500):
            return True
        name = type(error).__name__.lower()
        return any(token in name for token in ("timeout", "ratelimit", "transient"))

    def invoke(
        self,
        invoke: Callable[[], Any],
        *,
        timeout_seconds: float | None = None,
        interrupt_check: Optional[Callable[[], None]] = None,
    ) -> Any:
        timeout = self.options.timeout_seconds if timeout_seconds is None else timeout_seconds
        if timeout is not None and timeout <= 0:
            raise ModelTimeoutError("model execution budget exhausted")
        if not self._model_slots.acquire(blocking=False):
            raise ModelCapacityError("model execution capacity exhausted")
        if timeout is None and interrupt_check is None:
            try:
                return invoke()
            finally:
                self._model_slots.release()
        executor = None
        admitted: Future[bool] = Future()

        def admitted_invoke() -> Any:
            return invoke() if admitted.result() else None

        try:
            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="agent-model"
            )
            future = executor.submit(copy_context().run, admitted_invoke)
        except BaseException:
            # submit() can enqueue work before thread creation fails.
            admitted.set_result(False)
            self._model_slots.release()
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)
            raise
        future.add_done_callback(lambda _completed: self._model_slots.release())
        admitted.set_result(True)
        deadline = time.monotonic() + timeout if timeout is not None else None
        try:
            while True:
                if interrupt_check is not None:
                    interrupt_check()
                remaining = (
                    deadline - time.monotonic()
                    if deadline is not None else None
                )
                if remaining is not None and remaining <= 0:
                    future.cancel()
                    raise ModelTimeoutError("model provider timed out")
                wait_seconds = (
                    min(0.1, remaining)
                    if remaining is not None
                    else 0.1
                )
                try:
                    return future.result(timeout=wait_seconds)
                except FutureTimeoutError as error:
                    if future.done():
                        raise
                    if interrupt_check is not None:
                        interrupt_check()
                    if deadline is not None and time.monotonic() >= deadline:
                        future.cancel()
                        raise ModelTimeoutError(
                            "model provider timed out"
                        ) from error
        finally:
            # A provider that ignores cancellation may continue in its own
            # thread, but the Run never waits unboundedly for it.
            executor.shutdown(wait=False, cancel_futures=True)

    def _stream_model(
        self,
        provider: Any,
        messages: Sequence[AgentMessage],
        tools: Sequence[Any],
        request: TurnRequest,
        abort_event: Optional[threading.Event] = None,
        timeout_seconds: float | None = None,
        on_output: Optional[Callable[[], None]] = None,
    ) -> ModelTurn:
        stream = getattr(provider, "stream", None)
        interrupt_check = lambda: self.assert_not_interrupted(
            request, abort_event,
        )
        if not callable(stream):
            return self.invoke(
                lambda: (
                    provider.complete(messages, tools, request)
                    if callable(getattr(provider, "complete", None))
                    else provider(messages, tools, request)
                ),
                timeout_seconds=timeout_seconds,
                interrupt_check=interrupt_check,
            )
        # Consume the iterator inside the bounded worker. A timeout around
        # only ``stream(...)`` is insufficient because most providers return
        # a lazy iterator whose next chunk can block indefinitely.
        stopped = threading.Event()
        timeout = self.options.timeout_seconds if timeout_seconds is None else timeout_seconds
        deadline = time.monotonic() + timeout if timeout is not None else None

        def check_stream() -> None:
            if stopped.is_set() or (deadline is not None and time.monotonic() >= deadline):
                raise ModelTimeoutError("model stream invocation has ended")
            interrupt_check()

        def consume() -> ModelTurn:
            check_stream()
            return self._consume_stream(
                stream(messages, tools, request), request, abort_event,
                on_output, check_stream,
            )

        try:
            return self.invoke(
                consume, timeout_seconds=timeout_seconds,
                interrupt_check=interrupt_check,
            )
        finally:
            stopped.set()

    def _consume_stream(
        self,
        iterator: Any,
        request: TurnRequest,
        abort_event: Optional[threading.Event] = None,
        on_output: Optional[Callable[[], None]] = None,
        interrupt_check: Optional[Callable[[], None]] = None,
    ) -> ModelTurn:
        def emit_delta(delta: str) -> None:
            if on_output is not None:
                on_output()
            self.emit("model_delta", request, delta=delta)

        def emit_reasoning(delta: str) -> None:
            if on_output is not None:
                on_output()
            self.emit("model_reasoning_delta", request, delta=delta)

        return consume_model_stream(
            iterator,
            max_chars=self.options.max_model_output_chars,
            max_chunks=self.options.max_stream_chunks,
            delta_chars=self.options.max_stream_delta_chars,
            parse_calls=self._stream_calls,
            check=interrupt_check or (
                lambda: self.assert_not_interrupted(request, abort_event)
            ),
            emit_delta=emit_delta,
            emit_reasoning=emit_reasoning,
        )

    @staticmethod
    def _stream_calls(items: Sequence[Any]) -> list[ToolCall]:
        calls = []
        for item in items:
            if isinstance(item, ToolCall):
                calls.append(item)
            elif isinstance(item, Mapping):
                calls.append(
                    ToolCall(
                        id=str(item.get("id") or item.get("tool_call_id") or ""),
                        name=str(item.get("name") or ""),
                        arguments=dict(item.get("arguments") or item.get("args") or {}),
                        depends_on=tuple(item.get("depends_on") or ()),
                        argument_bindings=tuple(item.get("argument_bindings") or ()),
                    )
                )
        return calls

    def _call_provider(
        self,
        provider: Any,
        messages: Sequence[AgentMessage],
        tools: Sequence[Any],
        request: TurnRequest,
        abort_event: Optional[threading.Event] = None,
        timeout_seconds: float | None = None,
        on_output: Optional[Callable[[], None]] = None,
    ) -> ModelTurn:
        streaming = bool(
            request.streaming
            or (
                isinstance(request.context, Mapping)
                and request.context.get("streaming")
            )
        )
        value = (
            self._stream_model(
                provider,
                messages,
                tools,
                request,
                abort_event,
                timeout_seconds,
                on_output,
            )
            if streaming
            else self.invoke(
                lambda: (
                    provider.complete(messages, tools, request)
                    if callable(getattr(provider, "complete", None))
                    else provider(messages, tools, request)
                ),
                timeout_seconds=timeout_seconds,
                interrupt_check=lambda: self.assert_not_interrupted(
                    request, abort_event,
                ),
            )
        )
        self.assert_not_interrupted(request, abort_event)
        turn = self.normalize(value)
        if model_output_chars(turn) > self.options.max_model_output_chars:
            raise ModelOutputLimitError()
        return turn

    def complete(
        self,
        request: TurnRequest,
        state: AgentState,
        abort_event: Optional[threading.Event] = None,
    ) -> ModelTurn:
        deadline = (
            time.monotonic() + self.options.timeout_seconds
            if self.options.timeout_seconds is not None else None
        )
        prepared_at = time.monotonic()
        messages, tools, model_request = self.prepare(request, state)
        prepare_duration_ms = round((time.monotonic() - prepared_at) * 1000, 2)
        providers = tuple(
            provider for provider in self.providers() if provider is not None
        )
        if not providers:
            raise ModelUnavailableError("No model adapter is configured")
        invocation = _ModelInvocation(
            request=request,
            model_request=model_request,
            state=state,
            messages=messages,
            tools=tools,
            abort_event=abort_event,
            lifecycle_events=bool(
                request.streaming
                or callable(request.event_callback)
                or self.options.timeout_seconds is not None
                or len(providers) > 1
            ),
            deadline=deadline,
            prepare_duration_ms=prepare_duration_ms,
            input_chars=model_input_chars(messages, tools),
        )
        for provider_index, provider in enumerate(providers):
            complete = getattr(provider, "complete", None)
            stream = getattr(provider, "stream", None)
            if (
                not callable(complete)
                and not callable(stream)
                and not callable(provider)
            ):
                raise TypeError("model must be callable or expose complete()/stream()")
            invocation.provider_index = provider_index
            try:
                return self._call_with_retries(provider, invocation)
            except _ModelInvocationFailure as failure:
                if not failure.retryable or provider_index == len(providers) - 1:
                    raise failure.error
                self.emit(
                    "model_fallback",
                    request,
                    from_provider=self._provider_name(provider),
                    to_provider=self._provider_name(providers[provider_index + 1]),
                    error_type=type(failure.error).__name__,
                )
        raise RuntimeError("model call failed")

    def _attempt(
        self, provider: Any, invocation: _ModelInvocation, attempt: int
    ) -> ModelTurn:
        request = invocation.request
        remaining = (
            invocation.deadline - time.monotonic()
            if invocation.deadline is not None else None
        )
        if remaining is not None and remaining <= 0:
            raise _ModelInvocationFailure(
                ModelTimeoutError("model execution budget exhausted"), False,
            )
        model_request = invocation.model_request
        if remaining is not None:
            model_request = replace(model_request, context={
                **dict(model_request.context or {}),
                "model_timeout_seconds": remaining,
                "_harness_model_deadline": invocation.deadline,
            })
        invocation.stream_output_started = False
        invocation.attempt_started_at = time.monotonic()
        invocation.model_call_id = uuid.uuid4().hex

        def mark_stream_output() -> None:
            invocation.stream_output_started = True

        provider_name = self._provider_name(provider)
        if invocation.lifecycle_events:
            self.emit(
                "model_start",
                request,
                model_call_id=invocation.model_call_id,
                provider=provider_name,
                provider_index=invocation.provider_index,
                attempt=attempt + 1,
                message_count=len(invocation.messages),
                message_chars=sum(
                    len(str(message.content or "")) for message in invocation.messages
                ),
                tool_count=len(invocation.tools),
                input_chars=invocation.input_chars,
                prepare_duration_ms=(
                    invocation.prepare_duration_ms
                    if attempt == 0 and invocation.provider_index == 0
                    else 0.0
                ),
            )
        try:
            model_turn = self._call_provider(
                provider,
                invocation.messages,
                invocation.tools,
                model_request,
                invocation.abort_event,
                remaining,
                mark_stream_output,
            )
        except Exception as error:
            self.assert_not_interrupted(request, invocation.abort_event)
            raise _ModelInvocationFailure(
                error, self._retryable_model_error(error)
                and not invocation.stream_output_started,
            ) from error
        self._record_usage(request, invocation.state, model_turn)
        if invocation.lifecycle_events:
            self.emit(
                "model_end",
                request,
                model_call_id=invocation.model_call_id,
                provider=provider_name,
                provider_index=invocation.provider_index,
                usage=dict(model_turn.usage),
                tool_call_count=len(model_turn.tool_calls or ()),
                has_content=bool(str(model_turn.content or "").strip()),
                duration_ms=round(
                    (
                        time.monotonic()
                        - (invocation.attempt_started_at or time.monotonic())
                    ) * 1000,
                    2,
                ),
            )
        return model_turn

    def _call_with_retries(
        self, provider: Any, invocation: _ModelInvocation
    ) -> ModelTurn:
        for attempt in range(self.options.max_retries + 1):
            self.assert_not_interrupted(invocation.request, invocation.abort_event)
            try:
                return self._attempt(provider, invocation, attempt)
            except _ModelInvocationFailure as failure:
                error, retryable = failure.error, failure.retryable
                error_event = {
                    "model_call_id": invocation.model_call_id,
                    "provider": self._provider_name(provider),
                    "provider_index": invocation.provider_index,
                    "error_type": type(error).__name__,
                    "retryable": retryable,
                    "duration_ms": round(
                        (
                            time.monotonic()
                            - (invocation.attempt_started_at or time.monotonic())
                        ) * 1000,
                        2,
                    ),
                    "attempt": attempt + 1,
                }
                safe_reason_code = getattr(error, "safe_reason_code", None)
                if (
                    isinstance(safe_reason_code, str)
                    and re.fullmatch(r"[a-z0-9_]{1,64}", safe_reason_code)
                ):
                    error_event["error_code"] = safe_reason_code
                self.emit("model_error", invocation.request, **error_event)
                if not retryable or attempt == self.options.max_retries:
                    raise
                delay = self._retry_delay(error, attempt)
                self.emit(
                    "model_retry",
                    invocation.request,
                    attempt=attempt + 1,
                    provider=self._provider_name(provider),
                    error_type=type(error).__name__,
                    retry_delay_seconds=delay,
                )
                self._wait_for_retry(invocation, delay)
        raise RuntimeError("model retry loop exhausted")

    def _retry_delay(self, error: Exception, attempt: int) -> float:
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", {}) or {}
        hint = headers.get("retry-after") or headers.get("Retry-After")
        if hint is not None:
            try:
                seconds = float(hint)
            except (TypeError, ValueError):
                seconds = -1
            if math.isfinite(seconds) and seconds >= 0:
                return min(seconds, 60.0)
        return min(self.options.retry_delay_seconds * (2 ** attempt), 60.0)

    def _wait_for_retry(self, invocation: _ModelInvocation, delay: float) -> None:
        until = time.monotonic() + delay
        while time.monotonic() < until:
            self.assert_not_interrupted(invocation.request, invocation.abort_event)
            remaining = (
                invocation.deadline - time.monotonic()
                if invocation.deadline is not None else float("inf")
            )
            if remaining <= 0:
                raise _ModelInvocationFailure(
                    ModelTimeoutError("model execution budget exhausted"), False,
                )
            time.sleep(min(0.1, remaining, until - time.monotonic()))

    @staticmethod
    def _usage_number(usage: Mapping[str, Any], *names: str) -> int:
        for name in names:
            value = usage.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return max(0, int(value))
        return 0

    @classmethod
    def _usage_counters(cls, usage: Mapping[str, Any]) -> tuple[tuple[str, int], ...]:
        input_tokens = cls._usage_number(
            usage,
            "input_tokens",
            "prompt_tokens",
            "input",
        )
        output_tokens = cls._usage_number(
            usage,
            "output_tokens",
            "completion_tokens",
            "output",
        )
        total_tokens = cls._usage_number(usage, "total_tokens", "total")
        if not total_tokens:
            total_tokens = input_tokens + output_tokens
        cache_read_tokens = cls._usage_number(
            usage,
            "cache_read_input_tokens",
            "cached_input_tokens",
            "cache_read_tokens",
        )
        cache_write_tokens = cls._usage_number(
            usage,
            "cache_write_input_tokens",
            "cache_creation_input_tokens",
        )
        llm_requests = cls._usage_number(
            usage,
            "llm_requests",
            "api_requests",
        )
        if not llm_requests and (input_tokens or output_tokens):
            llm_requests = 1
        return (
            ("input_tokens", input_tokens),
            ("output_tokens", output_tokens),
            ("total_tokens", total_tokens),
            ("cache_read_input_tokens", cache_read_tokens),
            ("cache_write_input_tokens", cache_write_tokens),
            ("llm_requests", llm_requests),
            ("adapter_turns", 1),
        )

    def _record_usage(
        self, request: TurnRequest, state: AgentState, model_turn: ModelTurn
    ) -> None:
        usage = model_turn.usage if isinstance(model_turn.usage, Mapping) else {}
        for key, value in self._usage_counters(usage):
            state.usage[key] = int(state.usage.get(key, 0)) + int(value)
        if usage or any(
            limit is not None
            for limit in (
                self.options.max_input_tokens,
                self.options.max_output_tokens,
                self.options.max_total_tokens,
            )
        ):
            self.emit("model_usage", request, usage=dict(state.usage))
        limits = (
            ("input_tokens", self.options.max_input_tokens),
            ("output_tokens", self.options.max_output_tokens),
            ("total_tokens", self.options.max_total_tokens),
        )
        exceeded = [
            name
            for name, limit in limits
            if limit is not None and state.usage.get(name, 0) > limit
        ]
        if exceeded:
            raise ModelBudgetExceededError(
                "model token budget exceeded: " + ", ".join(exceeded),
            )
