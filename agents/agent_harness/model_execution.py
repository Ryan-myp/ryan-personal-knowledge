"""Bounded model execution, streaming, retries, fallback and Run token budgets."""

from __future__ import annotations

import threading
from contextvars import copy_context
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Optional, Sequence, TYPE_CHECKING

from .messages import AgentMessage, ModelTurn, ToolCall
from .runtime_kernel import TurnRequest

if TYPE_CHECKING:
    from .agent import AgentState


class ModelTimeoutError(TimeoutError):
    """The provider exceeded the configured deadline."""


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
    timeout_seconds: float | None = None
    max_inflight: int = 32
    max_retries: int = 0
    retry_delay_seconds: float = 0.0
    max_stream_delta_chars: int = 4096
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None

    def __post_init__(self) -> None:
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
    ) -> Any:
        if not self._model_slots.acquire(blocking=False):
            raise ModelCapacityError("model execution capacity exhausted")
        if self.options.timeout_seconds is None:
            try:
                return invoke()
            finally:
                self._model_slots.release()
        executor = None
        try:
            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="agent-model"
            )
            future = executor.submit(copy_context().run, invoke)
        except (RuntimeError, OSError, MemoryError):
            self._model_slots.release()
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)
            raise
        future.add_done_callback(lambda _completed: self._model_slots.release())
        try:
            return future.result(timeout=self.options.timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            raise ModelTimeoutError("model provider timed out") from error
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
    ) -> ModelTurn:
        stream = getattr(provider, "stream", None)
        if not callable(stream):
            return self.invoke(
                lambda: (
                    provider.complete(messages, tools, request)
                    if callable(getattr(provider, "complete", None))
                    else provider(messages, tools, request)
                ),
            )
        # Consume the iterator inside the bounded worker. A timeout around
        # only ``stream(...)`` is insufficient because most providers return
        # a lazy iterator whose next chunk can block indefinitely.
        return self.invoke(
            lambda: self._consume_stream(
                stream(messages, tools, request),
                request,
                abort_event,
            ),
        )

    def _consume_stream(
        self,
        iterator: Any,
        request: TurnRequest,
        abort_event: Optional[threading.Event] = None,
    ) -> ModelTurn:
        parts: list[str] = []
        final: Optional[ModelTurn] = None
        calls: list[ToolCall] = []
        for chunk in iterator:
            self.assert_not_interrupted(request, abort_event)
            if isinstance(chunk, ModelTurn):
                final = chunk
                if chunk.tool_calls:
                    calls.extend(chunk.tool_calls)
                continue
            if isinstance(chunk, str):
                delta = chunk
            elif isinstance(chunk, Mapping):
                delta = chunk.get("delta", chunk.get("content", ""))
                calls.extend(self._stream_calls(chunk.get("tool_calls") or ()))
            else:
                delta = ""
            if delta not in (None, ""):
                safe_delta = str(delta)[: self.options.max_stream_delta_chars]
                parts.append(safe_delta)
                self.emit(
                    "model_delta",
                    request,
                    delta=safe_delta,
                )
        if final is None:
            final = ModelTurn(
                content="".join(parts),
                tool_calls=tuple(calls),
            )
        elif parts:
            final = replace(
                final,
                content="".join(parts),
                tool_calls=tuple(final.tool_calls or calls),
            )
        return final

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
            )
            if streaming
            else self.invoke(
                lambda: (
                    provider.complete(messages, tools, request)
                    if callable(getattr(provider, "complete", None))
                    else provider(messages, tools, request)
                ),
            )
        )
        self.assert_not_interrupted(request, abort_event)
        return self.normalize(value)

    def complete(
        self,
        request: TurnRequest,
        state: AgentState,
        abort_event: Optional[threading.Event] = None,
    ) -> ModelTurn:
        messages, tools, model_request = self.prepare(request, state)
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
                or self.options.timeout_seconds is not None
                or len(providers) > 1
            ),
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
        provider_name = self._provider_name(provider)
        if invocation.lifecycle_events:
            self.emit(
                "model_start",
                request,
                provider=provider_name,
                provider_index=invocation.provider_index,
                attempt=attempt + 1,
            )
        try:
            model_turn = self._call_provider(
                provider,
                invocation.messages,
                invocation.tools,
                invocation.model_request,
                invocation.abort_event,
            )
        except Exception as error:
            raise _ModelInvocationFailure(
                error, self._retryable_model_error(error)
            ) from error
        self._record_usage(request, invocation.state, model_turn)
        if invocation.lifecycle_events:
            self.emit(
                "model_end",
                request,
                provider=provider_name,
                provider_index=invocation.provider_index,
                usage=dict(model_turn.usage),
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
                self.emit(
                    "model_error",
                    invocation.request,
                    provider=self._provider_name(provider),
                    provider_index=invocation.provider_index,
                    error_type=type(error).__name__,
                    retryable=retryable,
                )
                if not retryable or attempt == self.options.max_retries:
                    raise
                self.emit(
                    "model_retry",
                    invocation.request,
                    attempt=attempt + 1,
                    provider=self._provider_name(provider),
                    error_type=type(error).__name__,
                )
                time.sleep(self.options.retry_delay_seconds)
        raise RuntimeError("model retry loop exhausted")

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
