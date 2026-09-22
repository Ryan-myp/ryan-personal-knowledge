"""Stateful, application-neutral Agent loop.

The loop owns transcript state, model turns, Tool preflight/execution and
event ordering. Applications inject a model adapter, Tool catalog and policy
hooks; the loop never knows a provider, channel or business workflow.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from dataclasses import replace
import json
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence

from .context import ContextProvider, context_prompt
from .messages import AgentMessage, ModelTurn, ToolCall
from .persistence import TranscriptStore
from .redaction import redact_for_persistence
from .results import RunResult, RunStatus
from .runtime_kernel import TurnRequest
from .skills import SkillCatalog
from .tool_catalog import ToolCatalog


class ModelAdapter(Protocol):
    def complete(
        self,
        messages: Sequence[AgentMessage],
        tools: Sequence[Any],
        request: TurnRequest,
    ) -> Any:
        ...


class StreamingModelAdapter(ModelAdapter, Protocol):
    """Optional provider contract for incremental model output."""

    def stream(
        self,
        messages: Sequence[AgentMessage],
        tools: Sequence[Any],
        request: TurnRequest,
    ) -> Any:
        ...


class ModelTimeoutError(TimeoutError):
    """The provider did not produce a result within the configured deadline."""


class ModelBudgetExceededError(RuntimeError):
    """The provider returned usage beyond the configured Run budget."""


class TranscriptPersistenceError(RuntimeError):
    """The durable transcript could not be loaded or appended safely."""


class AgentCancelledError(RuntimeError):
    """The current Agent Run was cooperatively cancelled."""


class AgentLeaseLostError(RuntimeError):
    """The current Agent Run lost its durable Runtime session lease."""


@dataclass(frozen=True)
class ToolCallContext:
    request: TurnRequest
    assistant_message: AgentMessage
    tool_call: ToolCall
    state: "AgentState"
    tool_definition: Any = None


@dataclass
class AgentState:
    messages: list[AgentMessage] = field(default_factory=list)
    is_running: bool = False
    error_message: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    hydrated: bool = False
    last_used_at: float = field(default_factory=time.monotonic)

    def snapshot(self) -> list[AgentMessage]:
        return list(self.messages)


class Agent:
    """A reusable stateful model/tool loop similar to a small agent core."""

    def __init__(
        self,
        *,
        model: ModelAdapter | Callable[..., Any],
        tool_catalog: Optional[ToolCatalog] = None,
        skill_catalog: Optional[SkillCatalog] = None,
        system_prompt: str = "",
        max_turns: int = 12,
        tool_execution: str = "parallel",
        max_parallel_tools: int = 8,
        max_tools: int = 128,
        tool_selector: Optional[
            Callable[[TurnRequest, Sequence[Any]], Sequence[Any]]
        ] = None,
        before_tool_call: Optional[Callable[[ToolCallContext], Any]] = None,
        after_tool_call: Optional[Callable[[ToolCallContext, Any], Any]] = None,
        should_stop_after_turn: Optional[Callable[[AgentState], bool]] = None,
        event_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        context_provider: Optional[ContextProvider] = None,
        input_sanitizer: Optional[Callable[[Any], Any]] = None,
        model_max_retries: int = 0,
        model_retry_delay_seconds: float = 0.0,
        max_transcript_messages: int = 200,
        max_transcript_chars: int = 100_000,
        transcript_store: Optional[TranscriptStore] = None,
        session_ttl_seconds: float = 3600.0,
        max_sessions: int = 1000,
        model_timeout_seconds: float | None = None,
        model_fallbacks: Sequence[Any] = (),
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        max_total_tokens: int | None = None,
        max_stream_delta_chars: int = 4096,
        max_tool_result_chars: int = 32_000,
    ) -> None:
        if max_turns <= 0:
            raise ValueError("max_turns must be positive")
        if tool_execution not in {"sequential", "parallel"}:
            raise ValueError("tool_execution must be sequential or parallel")
        if max_parallel_tools <= 0:
            raise ValueError("max_parallel_tools must be positive")
        if max_tools <= 0:
            raise ValueError("max_tools must be positive")
        if model_max_retries < 0:
            raise ValueError("model_max_retries must be non-negative")
        if model_retry_delay_seconds < 0:
            raise ValueError("model_retry_delay_seconds must be non-negative")
        if max_transcript_messages < 2:
            raise ValueError("max_transcript_messages must be at least 2")
        if max_transcript_chars <= 0:
            raise ValueError("max_transcript_chars must be positive")
        if session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds must be positive")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be positive")
        if model_timeout_seconds is not None and model_timeout_seconds <= 0:
            raise ValueError("model_timeout_seconds must be positive")
        for name, value in (
            ("max_input_tokens", max_input_tokens),
            ("max_output_tokens", max_output_tokens),
            ("max_total_tokens", max_total_tokens),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")
        if max_stream_delta_chars <= 0:
            raise ValueError("max_stream_delta_chars must be positive")
        if max_tool_result_chars <= 0:
            raise ValueError("max_tool_result_chars must be positive")
        self.model = model
        self.tool_catalog = tool_catalog
        self.skill_catalog = skill_catalog
        self._system_prompt = str(system_prompt or "")
        self.max_turns = int(max_turns)
        self.tool_execution = tool_execution
        self.max_parallel_tools = int(max_parallel_tools)
        self.max_tools = int(max_tools)
        self.tool_selector = tool_selector
        self.model_max_retries = int(model_max_retries)
        self.model_retry_delay_seconds = float(model_retry_delay_seconds)
        self.max_transcript_messages = int(max_transcript_messages)
        self.max_transcript_chars = int(max_transcript_chars)
        self.transcript_store = transcript_store
        self.session_ttl_seconds = float(session_ttl_seconds)
        self.max_sessions = int(max_sessions)
        self.model_timeout_seconds = (
            float(model_timeout_seconds)
            if model_timeout_seconds is not None else None
        )
        self.model_fallbacks = tuple(model_fallbacks or ())
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_total_tokens = max_total_tokens
        self.max_stream_delta_chars = int(max_stream_delta_chars)
        self.max_tool_result_chars = int(max_tool_result_chars)
        self.before_tool_call = before_tool_call
        self.after_tool_call = after_tool_call
        self.should_stop_after_turn = should_stop_after_turn
        self.event_callback = event_callback
        self.context_provider = context_provider
        self.input_sanitizer = input_sanitizer
        self._system_messages = (
            [AgentMessage.system(system_prompt)] if system_prompt else []
        )
        self._session_states: dict[str, AgentState] = {}
        self._session_locks: dict[str, threading.RLock] = {}
        self._session_guard = threading.RLock()
        self._abort_events: dict[str, threading.Event] = {}
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._subscriber_guard = threading.RLock()
        self._event_guard = threading.RLock()
        self._event_sequences: dict[str, int] = {}

    @staticmethod
    def _session_key(
        session_id: str | None,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> str:
        return "\x1f".join((
            str(tenant_id or "default"),
            str(user_id or "anonymous"),
            str(session_id or "__default__"),
        ))

    def _state_for(
        self,
        session_id: str | None,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> AgentState:
        key = self._session_key(session_id, user_id, tenant_id)
        with self._session_guard:
            self._evict_sessions_locked()
            return self._session_states.setdefault(
                key,
                AgentState(messages=list(self._system_messages)),
            )

    def _lock_for(
        self,
        session_id: str | None,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> threading.RLock:
        key = self._session_key(session_id, user_id, tenant_id)
        with self._session_guard:
            return self._session_locks.setdefault(key, threading.RLock())

    def _abort_event_for(
        self,
        session_id: str | None,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> threading.Event:
        key = self._session_key(session_id, user_id, tenant_id)
        with self._session_guard:
            return self._abort_events.setdefault(key, threading.Event())

    @property
    def system_prompt(self) -> str:
        """Return the immutable prompt used to seed a fresh transcript."""
        return self._system_prompt

    @property
    def state(self) -> AgentState:
        """Return the default-session state for interactive callers."""
        return self._state_for(None)

    def _evict_sessions_locked(self) -> None:
        now = time.monotonic()
        expired = [
            key for key, state in self._session_states.items()
            if not state.is_running
            and now - state.last_used_at >= self.session_ttl_seconds
        ]
        for key in expired:
            self._session_states.pop(key, None)
            self._session_locks.pop(key, None)
            self._abort_events.pop(key, None)
        if len(self._session_states) <= self.max_sessions:
            return
        candidates = sorted(
            (
                (state.last_used_at, key)
                for key, state in self._session_states.items()
                if not state.is_running
            ),
        )
        for _timestamp, key in candidates:
            if len(self._session_states) <= self.max_sessions:
                break
            self._session_states.pop(key, None)
            self._session_locks.pop(key, None)
            self._abort_events.pop(key, None)

    def reset(
        self,
        session_id: str | None = None,
        *,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> None:
        state = self._state_for(session_id, user_id, tenant_id)
        with self._lock_for(session_id, user_id, tenant_id):
            if state.is_running:
                raise RuntimeError("Agent is already running")
            if self.transcript_store is not None and session_id:
                clear = getattr(self.transcript_store, "clear", None)
                if callable(clear):
                    try:
                        clear(
                            str(session_id),
                            tenant_id=str(tenant_id or "default"),
                            user_id=str(user_id or "anonymous"),
                        )
                    except Exception as error:
                        raise TranscriptPersistenceError(
                            "transcript clear failed",
                        ) from error
            state.messages = list(self._system_messages)
            state.error_message = None
            state.usage = {}
            state.hydrated = False
            self._abort_event_for(session_id, user_id, tenant_id).clear()

    def forget_session(
        self,
        session_id: str,
        *,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> None:
        """Drop one in-memory session after its durable record was deleted."""
        key = self._session_key(session_id, user_id, tenant_id)
        with self._session_guard:
            state = self._session_states.get(key)
            if state is not None and state.is_running:
                raise RuntimeError("Agent session is already running")
            self._session_states.pop(key, None)
            self._session_locks.pop(key, None)
            self._abort_events.pop(key, None)

    def subscribe(
        self, callback: Callable[[dict[str, Any]], None],
    ) -> Callable[[], None]:
        if not callable(callback):
            raise TypeError("Agent subscriber must be callable")
        with self._subscriber_guard:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._subscriber_guard:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def abort(self, session_id: str | None = None) -> None:
        """Request cooperative cancellation for one session."""
        self._abort_event_for(session_id).set()

    def prompt(
        self,
        user_input: str,
        *,
        session_id: str | None = None,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> RunResult:
        """Convenience API for interactive callers that do not need an envelope."""
        return self.run(TurnRequest(
            user_input=str(user_input),
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            cancellation_event=self._abort_event_for(session_id, user_id, tenant_id),
        ))

    def _emit(self, event_type: str, request: TurnRequest, **payload: Any) -> None:
        run_key = str(request.run_id or "")
        with self._event_guard:
            sequence = self._event_sequences.get(run_key, 0) + 1
            self._event_sequences[run_key] = sequence
            event = {
                "type": event_type,
                "run_id": run_key,
                "turn_id": str(request.turn_id or ""),
                "seq": sequence,
            }
            event.update(payload)
        with self._subscriber_guard:
            subscribers = tuple(self._subscribers)
        callbacks = []
        for callback in (self.event_callback, request.event_callback, *subscribers):
            if callable(callback) and callback not in callbacks:
                callbacks.append(callback)
        for callback in callbacks:
            try:
                callback(redact_for_persistence(event))
            except Exception:
                # Event consumers are observers; a broken stream must not
                # corrupt the transcript or turn result.
                continue

    @staticmethod
    def _normalize_turn(value: Any) -> ModelTurn:
        if isinstance(value, ModelTurn):
            return value
        if isinstance(value, str):
            return ModelTurn(content=value)
        if isinstance(value, Mapping):
            calls = []
            for item in value.get("tool_calls") or ():
                if isinstance(item, ToolCall):
                    calls.append(item)
                    continue
                if isinstance(item, Mapping):
                    calls.append(ToolCall(
                        id=str(item.get("id") or item.get("tool_call_id") or ""),
                        name=str(item.get("name") or ""),
                        arguments=dict(item.get("arguments") or item.get("args") or {}),
                    ))
            return ModelTurn(
                content=value.get("content", value.get("reply", "")),
                tool_calls=tuple(calls),
                stop_reason=str(value.get("stop_reason") or "stop"),
                usage=dict(value.get("usage") or {}),
                context_updates=dict(value.get("context_updates") or {}),
            )
        raise TypeError("model must return ModelTurn, mapping, or string")

    def _notify_model_run_end(
        self,
        request: TurnRequest,
        model_turn: ModelTurn,
        tool_results: Sequence[Mapping[str, Any]],
        state: AgentState,
    ) -> None:
        """Allow a model adapter to shape application results at Run end."""
        callback = getattr(self.model, "on_run_end", None)
        if not callable(callback):
            return
        try:
            callback(
                request,
                model_turn,
                tuple(dict(item) for item in tool_results),
                state,
            )
        except Exception:
            # Application result shaping cannot break the generic lifecycle.
            return

    def _model_inputs(
        self, request: TurnRequest, state: AgentState,
    ) -> tuple[list[Any], list[Any], TurnRequest]:
        tools = self.tool_catalog.list_tools() if self.tool_catalog else []
        if callable(self.tool_selector):
            tools = list(self.tool_selector(request, tuple(tools)))
        tools = list(tools[:self.max_tools])
        messages = state.snapshot()
        model_request = request
        if self.context_provider is not None:
            build_context = getattr(self.context_provider, "build_context", None)
            if not callable(build_context):
                raise TypeError("context_provider must expose build_context()")
            value = build_context(request, messages)
            if isinstance(value, Mapping):
                context = dict(request.context or {})
                context["agent_context"] = dict(value)
                model_request = replace(request, context=context)
                prompt = context_prompt(value)
                if prompt:
                    messages = [
                        AgentMessage.system(
                            prompt,
                            run_id=str(request.run_id or ""),
                            turn_id=str(request.turn_id or ""),
                            metadata={"context_type": "provider"},
                        ),
                        *messages,
                    ]
        if self.skill_catalog is not None:
            skill_context = self.skill_catalog.build_context(request.user_input)
            if skill_context:
                messages = [
                    AgentMessage.system(
                        skill_context,
                        run_id=str(request.run_id or ""),
                        turn_id=str(request.turn_id or ""),
                        metadata={"context_type": "skills"},
                    ),
                    *messages,
                ]
        context = dict(model_request.context or {})
        if self.model_timeout_seconds is not None:
            context["model_timeout_seconds"] = self.model_timeout_seconds
        for name, value in (
            ("max_input_tokens", self.max_input_tokens),
            ("max_output_tokens", self.max_output_tokens),
            ("max_total_tokens", self.max_total_tokens),
        ):
            if value is not None:
                context[name] = value
        if context != dict(model_request.context or {}):
            model_request = replace(model_request, context=context)
        return messages, tools, model_request

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

    def _invoke_with_timeout(
        self,
        invoke: Callable[[], Any],
    ) -> Any:
        if self.model_timeout_seconds is None:
            return invoke()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-model")
        future = executor.submit(invoke)
        try:
            return future.result(timeout=self.model_timeout_seconds)
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
            return self._invoke_with_timeout(
                lambda: (
                    provider.complete(messages, tools, request)
                    if callable(getattr(provider, "complete", None))
                    else provider(messages, tools, request)
                ),
            )
        # Consume the iterator inside the bounded worker. A timeout around
        # only ``stream(...)`` is insufficient because most providers return
        # a lazy iterator whose next chunk can block indefinitely.
        return self._invoke_with_timeout(
            lambda: self._consume_stream(
                stream(messages, tools, request), request, abort_event,
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
            self._assert_not_interrupted(request, abort_event)
            if isinstance(chunk, ModelTurn):
                final = chunk
                if chunk.tool_calls:
                    calls.extend(chunk.tool_calls)
                continue
            if isinstance(chunk, str):
                delta = chunk
            elif isinstance(chunk, Mapping):
                delta = chunk.get("delta", chunk.get("content", ""))
                for item in chunk.get("tool_calls") or ():
                    if isinstance(item, ToolCall):
                        calls.append(item)
                    elif isinstance(item, Mapping):
                        calls.append(ToolCall(
                            id=str(item.get("id") or item.get("tool_call_id") or ""),
                            name=str(item.get("name") or ""),
                            arguments=dict(item.get("arguments") or item.get("args") or {}),
                        ))
            else:
                delta = ""
            if delta not in (None, ""):
                safe_delta = str(delta)[:self.max_stream_delta_chars]
                parts.append(safe_delta)
                self._emit(
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
    def _interrupt_reason(
        request: TurnRequest,
        abort_event: Optional[threading.Event] = None,
    ) -> Optional[str]:
        lease_lost = request.lease_lost_event
        if lease_lost is not None and lease_lost.is_set():
            return "session_lease_lost"
        cancelled = request.cancellation_event
        if (abort_event is not None and abort_event.is_set()) or (
            cancelled is not None and cancelled.is_set()
        ):
            return "cancelled"
        return None

    def _assert_not_interrupted(
        self,
        request: TurnRequest,
        abort_event: Optional[threading.Event] = None,
    ) -> None:
        reason = self._interrupt_reason(request, abort_event)
        if reason == "session_lease_lost":
            raise AgentLeaseLostError(
                "durable session lease was lost while the Run was active",
            )
        if reason == "cancelled":
            raise AgentCancelledError("Agent Run was cancelled")

    @staticmethod
    def _interrupted_result(
        request: TurnRequest,
        state: AgentState,
        *,
        reason: str,
    ) -> RunResult:
        if reason == "session_lease_lost":
            return RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.RECOVERY_REQUIRED,
                recovery_required=True,
                runtime_signals={"session_lease_lost": True},
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "error": "session_lease_lost",
                    "usage": dict(state.usage),
                },
            )
        return RunResult(
            run_id=str(request.run_id or ""),
            turn_id=str(request.turn_id or ""),
            status=RunStatus.CANCELLED,
            runtime_signals={"cancelled": True},
            data={
                "messages": [item.to_dict() for item in state.messages],
                "error": "cancelled",
                "usage": dict(state.usage),
            },
        )

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
                provider, messages, tools, request, abort_event,
            )
            if streaming else self._invoke_with_timeout(
                lambda: (
                    provider.complete(messages, tools, request)
                    if callable(getattr(provider, "complete", None))
                    else provider(messages, tools, request)
                ),
            )
        )
        self._assert_not_interrupted(request, abort_event)
        return self._normalize_turn(value)

    def _call_model(
        self,
        request: TurnRequest,
        state: AgentState,
        abort_event: Optional[threading.Event] = None,
    ) -> ModelTurn:
        messages, tools, model_request = self._model_inputs(request, state)
        providers = (self.model, *self.model_fallbacks)
        last_error: Optional[Exception] = None
        for provider_index, provider in enumerate(providers):
            complete = getattr(provider, "complete", None)
            stream = getattr(provider, "stream", None)
            if not callable(complete) and not callable(stream) and not callable(provider):
                raise TypeError("model must be callable or expose complete()/stream()")
            provider_name = self._provider_name(provider)
            for attempt in range(self.model_max_retries + 1):
                emit_model_lifecycle = bool(
                    request.streaming
                    or self.model_timeout_seconds is not None
                    or self.model_fallbacks
                )
                if emit_model_lifecycle:
                    self._emit(
                        "model_start",
                        request,
                        provider=provider_name,
                        provider_index=provider_index,
                        attempt=attempt + 1,
                    )
                try:
                    value = self._call_provider(
                        provider, messages, tools, model_request, abort_event,
                    )
                    model_turn = self._normalize_turn(value)
                    self._record_usage(request, state, model_turn)
                    if emit_model_lifecycle:
                        self._emit(
                            "model_end",
                            request,
                            provider=provider_name,
                            provider_index=provider_index,
                            usage=dict(model_turn.usage),
                        )
                    return model_turn
                except ModelBudgetExceededError:
                    raise
                except Exception as error:
                    last_error = error
                    retryable = self._retryable_model_error(error)
                    self._emit(
                        "model_error",
                        request,
                        provider=provider_name,
                        provider_index=provider_index,
                        error_type=type(error).__name__,
                        retryable=retryable,
                    )
                    if retryable and attempt < self.model_max_retries:
                        self._emit(
                            "model_retry",
                            request,
                            attempt=attempt + 1,
                            provider=provider_name,
                            error_type=type(error).__name__,
                        )
                        if self.model_retry_delay_seconds:
                            time.sleep(self.model_retry_delay_seconds)
                        continue
                    if (
                        retryable
                        and provider_index < len(providers) - 1
                    ):
                        self._emit(
                            "model_fallback",
                            request,
                            from_provider=provider_name,
                            to_provider=self._provider_name(providers[provider_index + 1]),
                            error_type=type(error).__name__,
                        )
                        break
                    raise
        raise last_error or RuntimeError("model call failed")

    @staticmethod
    def _usage_number(usage: Mapping[str, Any], *names: str) -> int:
        for name in names:
            value = usage.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return max(0, int(value))
        return 0

    def _record_usage(
        self, request: TurnRequest, state: AgentState, model_turn: ModelTurn,
    ) -> None:
        usage = model_turn.usage if isinstance(model_turn.usage, Mapping) else {}
        input_tokens = self._usage_number(
            usage, "input_tokens", "prompt_tokens", "input",
        )
        output_tokens = self._usage_number(
            usage, "output_tokens", "completion_tokens", "output",
        )
        total_tokens = self._usage_number(usage, "total_tokens", "total")
        if not total_tokens:
            total_tokens = input_tokens + output_tokens
        for key, value in (
            ("input_tokens", input_tokens),
            ("output_tokens", output_tokens),
            ("total_tokens", total_tokens),
            ("model_calls", 1),
        ):
            state.usage[key] = int(state.usage.get(key, 0)) + int(value)
        if usage or any(
            limit is not None for limit in (
                self.max_input_tokens,
                self.max_output_tokens,
                self.max_total_tokens,
            )
        ):
            self._emit("model_usage", request, usage=dict(state.usage))
        limits = (
            ("input_tokens", self.max_input_tokens),
            ("output_tokens", self.max_output_tokens),
            ("total_tokens", self.max_total_tokens),
        )
        exceeded = [
            name for name, limit in limits
            if limit is not None and state.usage.get(name, 0) > limit
        ]
        if exceeded:
            raise ModelBudgetExceededError(
                "model token budget exceeded: " + ", ".join(exceeded),
            )

    @staticmethod
    def _message_from_payload(value: Any) -> Optional[AgentMessage]:
        if isinstance(value, AgentMessage):
            return value
        if not isinstance(value, Mapping):
            return None
        role = str(value.get("role") or "user")
        if role not in {"system", "user", "assistant", "tool"}:
            return None
        return AgentMessage(
            role=role,
            content=value.get("content", ""),
            message_id=str(value.get("message_id") or ""),
            run_id=str(value.get("run_id") or ""),
            turn_id=str(value.get("turn_id") or ""),
            tool_call_id=value.get("tool_call_id"),
            name=value.get("name"),
            metadata=dict(value.get("metadata") or {}),
            timestamp=float(value.get("timestamp") or time.time()),
        )

    def _hydrate_state(
        self, request: TurnRequest, state: AgentState,
    ) -> None:
        if state.hydrated:
            return
        if self.transcript_store is not None and request.session_id:
            try:
                loaded = self.transcript_store.load(
                    str(request.session_id),
                    tenant_id=str(request.tenant_id or "default"),
                    user_id=str(request.user_id or "anonymous"),
                    limit=self.max_transcript_messages,
                )
            except Exception as error:
                raise TranscriptPersistenceError(
                    "transcript load failed",
                ) from error
            restored = [
                message for item in loaded
                if (message := self._message_from_payload(item)) is not None
                and message.role != "system"
            ]
            state.messages = list(self._system_messages)
            for message in restored:
                self._append_message(state, message, persist=False)
        state.hydrated = True

    def _append_message(
        self,
        state: AgentState,
        message: AgentMessage,
        *,
        request: Optional[TurnRequest] = None,
        persist: bool = True,
    ) -> None:
        """Keep durable transcript state bounded while retaining system context."""
        state.messages.append(message)
        system_messages = [
            item for item in state.messages if item.role == "system"
        ]
        non_system = [
            item for item in state.messages if item.role != "system"
        ]
        while (
            len(system_messages) + len(non_system)
            > self.max_transcript_messages
            and non_system
        ):
            non_system.pop(0)
        while (
            sum(len(str(item.content)) for item in system_messages + non_system)
            > self.max_transcript_chars
            and non_system
        ):
            non_system.pop(0)
        state.messages = system_messages + non_system
        if (
            persist
            and request is not None
            and self.transcript_store is not None
            and request.session_id
        ):
            safe_message = self._message_from_payload(
                redact_for_persistence(message.to_dict()),
            )
            if safe_message is None:
                raise RuntimeError("transcript message could not be serialized")
            try:
                self.transcript_store.append(
                    str(request.session_id),
                    [safe_message],
                    tenant_id=str(request.tenant_id or "default"),
                    user_id=str(request.user_id or "anonymous"),
                )
            except Exception as error:
                raise TranscriptPersistenceError(
                    "transcript append failed",
                ) from error

    def _execute_one(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        call: ToolCall,
        state: AgentState,
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
                if self.tool_catalog is None:
                    raise KeyError(f"Tool '{call.name}' not found")
                binding = self.tool_catalog.get_binding(call.name)
            execute = getattr(binding.executor, "execute", None)
            if callable(execute):
                output = execute(context, dict(call.arguments))
            elif callable(binding.executor):
                output = binding.executor(context, dict(call.arguments))
            else:
                raise TypeError(f"Tool '{call.name}' has no executor")
            safe_output = redact_for_persistence(output)
            result = {
                "tool_call_id": call.id,
                "name": call.name,
                "content": self._bound_tool_value(safe_output),
                "is_error": False,
                "terminate": False,
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
        except Exception as error:
            result = {
                "tool_call_id": call.id,
                "name": call.name,
                "content": redact_for_persistence(str(error)),
                "is_error": True,
                "terminate": False,
            }
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

    def _bound_tool_value(self, value: Any) -> Any:
        """Keep model-facing Tool content bounded without dropping status data."""
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

    def _execute_tools(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        calls: Sequence[ToolCall],
        state: AgentState,
    ) -> list[dict[str, Any]]:
        if self.tool_execution == "sequential" or len(calls) <= 1:
            return [
                self._execute_emitting(request, assistant, call, state)
                for call in calls
            ]
        for call in calls:
            self._emit(
                "tool_execution_start",
                request,
                tool_call_id=call.id,
                tool_name=call.name,
                arguments=dict(call.arguments),
            )
        with ThreadPoolExecutor(
            max_workers=min(self.max_parallel_tools, len(calls)),
            thread_name_prefix="agent-tool",
        ) as pool:
            futures = [
                pool.submit(self._execute_one, request, assistant, call, state)
                for call in calls
            ]
            results = []
            for call, future in zip(calls, futures):
                result = future.result()
                self._emit_tool_end(request, call, result)
                results.append(result)
            return results

    def _emit_tool_end(
        self, request: TurnRequest, call: ToolCall, result: Mapping[str, Any],
    ) -> None:
        self._emit(
            "tool_execution_end",
            request,
            tool_call_id=call.id,
            tool_name=call.name,
            result=dict(result),
            is_error=bool(result.get("is_error")),
        )

    def _execute_emitting(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        call: ToolCall,
        state: AgentState,
    ) -> dict[str, Any]:
        self._emit(
            "tool_execution_start",
            request,
            tool_call_id=call.id,
            tool_name=call.name,
            arguments=dict(call.arguments),
        )
        result = self._execute_one(request, assistant, call, state)
        self._emit_tool_end(request, call, result)
        return result

    def run(self, request: TurnRequest) -> RunResult:
        state = self._state_for(
            request.session_id, request.user_id, request.tenant_id,
        )
        session_lock = self._lock_for(
            request.session_id, request.user_id, request.tenant_id,
        )
        abort_event = self._abort_event_for(
            request.session_id, request.user_id, request.tenant_id,
        )
        with session_lock:
            if state.is_running:
                raise RuntimeError("Agent is already running")
            state.is_running = True
            state.error_message = None
            # Usage budgets are Run-scoped. Transcript state survives across
            # prompts, but a previous prompt must not consume this prompt's
            # model budget.
            state.usage = {}
            state.last_used_at = time.monotonic()
        try:
            self._hydrate_state(request, state)
            self._emit("agent_start", request)
            self._emit("turn_start", request, turn_index=0)
            user_message = AgentMessage.user(
                self.input_sanitizer(request.user_input)
                if callable(self.input_sanitizer)
                else request.user_input,
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
            )
            self._append_message(state, user_message, request=request)
            self._emit("message_end", request, message=user_message.to_dict())
            tool_results: list[dict[str, Any]] = []
            last_reply = ""
            for turn_index in range(self.max_turns):
                interrupt_reason = self._interrupt_reason(request, abort_event)
                if interrupt_reason is not None:
                    result = self._interrupted_result(
                        request, state, reason=interrupt_reason,
                    )
                    self._emit("agent_end", request, status=result.status.value)
                    return result
                if turn_index > 0:
                    self._emit("turn_start", request, turn_index=turn_index)
                tool_results = []
                model_turn = self._call_model(request, state, abort_event)
                if model_turn.context_updates and isinstance(request.context, dict):
                    request.context.update(dict(model_turn.context_updates))
                assistant = AgentMessage.assistant(
                    model_turn.content,
                    run_id=str(request.run_id or ""),
                    turn_id=str(request.turn_id or ""),
                    metadata={
                        "stop_reason": model_turn.stop_reason,
                        "tool_calls": [
                            call.to_dict() for call in model_turn.tool_calls
                        ],
                    },
                )
                self._append_message(state, assistant, request=request)
                last_reply = str(model_turn.content or "")
                self._emit("message_end", request, message=assistant.to_dict())
                if model_turn.tool_calls:
                    tool_results = self._execute_tools(
                        request, assistant, model_turn.tool_calls, state,
                    )
                    for result in tool_results:
                        tool_message = AgentMessage.tool(
                            result.get("content"),
                            tool_call_id=str(result.get("tool_call_id") or ""),
                            name=str(result.get("name") or ""),
                            run_id=str(request.run_id or ""),
                            turn_id=str(request.turn_id or ""),
                            metadata={
                                "is_error": bool(result.get("is_error")),
                                **{
                                    key: result[key]
                                    for key in (
                                        "needs_input",
                                        "needs_confirmation",
                                        "confirmation_payload",
                                    )
                                    if key in result
                                },
                            },
                        )
                        self._append_message(state, tool_message, request=request)
                        self._emit(
                            "message_end",
                            request,
                            message=tool_message.to_dict(),
                        )
                self._emit(
                    "turn_end",
                    request,
                    turn_index=turn_index,
                    tool_results=tool_results,
                )
                if (
                    not model_turn.tool_calls
                    or all(bool(item.get("terminate")) for item in tool_results)
                    or any(bool(item.get("recovery_required")) for item in tool_results)
                    or (
                        callable(self.should_stop_after_turn)
                        and self.should_stop_after_turn(state)
                    )
                ):
                    self._notify_model_run_end(
                        request, model_turn, tool_results, state,
                    )
                    awaiting_input = (
                        model_turn.stop_reason in {
                            "awaiting_input", "awaiting_confirmation", "needs_input",
                        }
                        or any(
                            bool(item.get("needs_input") or item.get("needs_confirmation"))
                            for item in tool_results
                        )
                    )
                    tool_recovery = any(
                        bool(item.get("recovery_required"))
                        or bool(
                            isinstance(item.get("runtime_signals"), Mapping)
                            and item["runtime_signals"].get("audit_error")
                        )
                        for item in tool_results
                    )
                    terminal_status = (
                        RunStatus.RECOVERY_REQUIRED
                        if tool_recovery
                        else RunStatus.FAILED
                        if model_turn.stop_reason in {"error", "policy_blocked"}
                        else RunStatus.AWAITING_INPUT
                        if awaiting_input
                        else RunStatus.SUCCEEDED
                    )
                    result = RunResult(
                        run_id=str(request.run_id or ""),
                        turn_id=str(request.turn_id or ""),
                        status=terminal_status,
                        reply=last_reply,
                        needs_input=awaiting_input,
                        recovery_required=tool_recovery,
                        runtime_signals={
                            key: value
                            for item in tool_results
                            if isinstance(item.get("runtime_signals"), Mapping)
                            for key, value in item["runtime_signals"].items()
                        },
                        data={
                            "messages": [
                                item.to_dict() for item in state.messages
                            ],
                            "tool_results": tool_results,
                            "needs_input": awaiting_input,
                            "usage": dict(state.usage),
                        },
                    )
                    self._emit("agent_end", request, status=result.status.value)
                    return result
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                reply=last_reply,
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "tool_results": tool_results,
                    "error": "maximum agent turns exceeded",
                    "usage": dict(state.usage),
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except TranscriptPersistenceError as error:
            state.error_message = type(error).__name__
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.RECOVERY_REQUIRED,
                recovery_required=True,
                runtime_signals={
                    "transcript_store_error": True,
                    "transcript_error_type": type(error).__name__,
                },
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "error": "transcript_persistence_failed",
                    "usage": dict(state.usage),
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except ModelBudgetExceededError as error:
            state.error_message = type(error).__name__
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                runtime_signals={
                    "budget_exceeded": True,
                    "budget_error": str(error),
                },
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "error": "model_token_budget_exceeded",
                    "usage": dict(state.usage),
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except ModelTimeoutError as error:
            state.error_message = type(error).__name__
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                runtime_signals={
                    "model_timeout": True,
                    "model_error_type": type(error).__name__,
                },
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "error": "model_timeout",
                    "usage": dict(state.usage),
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except AgentLeaseLostError:
            result = self._interrupted_result(
                request, state, reason="session_lease_lost",
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except AgentCancelledError:
            result = self._interrupted_result(
                request, state, reason="cancelled",
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except Exception as error:
            state.error_message = type(error).__name__
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "error": type(error).__name__,
                    "usage": dict(state.usage),
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        finally:
            state.is_running = False
            abort_event.clear()
            with self._event_guard:
                self._event_sequences.pop(str(request.run_id or ""), None)

    def execute(self, request: TurnRequest) -> RunResult:
        """Execute one Run through the shared TurnPipeline contract."""
        return self.run(request)


__all__ = [
    "Agent",
    "AgentState",
    "ModelAdapter",
    "StreamingModelAdapter",
    "ToolCallContext",
    "ModelTimeoutError",
    "ModelBudgetExceededError",
    "TranscriptPersistenceError",
    "AgentCancelledError",
    "AgentLeaseLostError",
]
