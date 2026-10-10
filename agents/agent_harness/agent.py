"""Stateful, application-neutral Agent loop.

The loop owns transcript state, model turns, Tool preflight/execution and
event ordering. Applications inject a model adapter, Tool catalog and policy
hooks; the loop never knows a provider, channel or business workflow.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from dataclasses import replace
import uuid
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence

from .context import ContextProvider, context_prompt
from .messages import AgentMessage, ModelTurn, ToolArgumentBinding, ToolCall
from .model_execution import (
    ModelExecutionCoordinator,
    ModelExecutionOptions,
    ModelTimeoutError,
    ModelCapacityError,
    ModelBudgetExceededError,
    ModelUnavailableError,
)
from .persistence import TranscriptStore
from .state_persistence import AgentStatePersistence, TranscriptPersistenceError
from .redaction import redact_for_persistence
from .reliability import ToolCircuitBreaker
from .results import RunResult, RunStatus
from .runtime_kernel import TurnRequest
from .skills import SkillCatalog
from .tool_catalog import ToolCatalog
from .tool_execution import (
    ToolCallContext,
    ToolExecutionCoordinator,
)


class ModelAdapter(Protocol):
    def complete(
        self,
        messages: Sequence[AgentMessage],
        tools: Sequence[Any],
        request: TurnRequest,
    ) -> Any: ...


class StreamingModelAdapter(ModelAdapter, Protocol):
    """Optional provider contract for incremental model output."""

    def stream(
        self,
        messages: Sequence[AgentMessage],
        tools: Sequence[Any],
        request: TurnRequest,
    ) -> Any: ...


class AgentCancelledError(RuntimeError):
    """The current Agent Run was cooperatively cancelled."""


class AgentLeaseLostError(RuntimeError):
    """The current Agent Run lost its durable Runtime session lease."""


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
        max_tool_calls_per_run: int = 64,
        max_parallel_tools: int = 8,
        max_inflight_tool_invocations: int = 64,
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
        request_validator: Optional[Callable[[TurnRequest], Optional[str]]] = None,
        model_max_retries: int = 0,
        model_retry_delay_seconds: float = 0.0,
        max_transcript_messages: int = 200,
        max_transcript_chars: int = 100_000,
        transcript_store: Optional[TranscriptStore] = None,
        session_ttl_seconds: float = 3600.0,
        max_sessions: int = 1000,
        model_timeout_seconds: float | None = None,
        max_inflight_model_invocations: int = 32,
        model_fallbacks: Sequence[Any] = (),
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        max_total_tokens: int | None = None,
        max_stream_delta_chars: int = 4096,
        max_tool_result_chars: int = 32_000,
        tool_timeout_seconds: float | None = None,
        tool_max_retries: int = 0,
        tool_retry_delay_seconds: float = 0.0,
        tool_circuit_failure_threshold: int = 5,
        tool_circuit_reset_seconds: float = 30.0,
        checkpoint_store: Any = None,
    ) -> None:
        if max_turns <= 0:
            raise ValueError("max_turns must be positive")
        if max_tool_calls_per_run <= 0:
            raise ValueError("max_tool_calls_per_run must be positive")
        if tool_execution not in {"sequential", "parallel"}:
            raise ValueError("tool_execution must be sequential or parallel")
        if max_parallel_tools <= 0:
            raise ValueError("max_parallel_tools must be positive")
        if max_inflight_tool_invocations <= 0:
            raise ValueError("max_inflight_tool_invocations must be positive")
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
        if max_inflight_model_invocations <= 0:
            raise ValueError("max_inflight_model_invocations must be positive")
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
        if tool_timeout_seconds is not None and tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        if tool_max_retries < 0:
            raise ValueError("tool_max_retries must be non-negative")
        if tool_retry_delay_seconds < 0:
            raise ValueError("tool_retry_delay_seconds must be non-negative")
        self.model = model
        self.tool_catalog = tool_catalog
        self.skill_catalog = skill_catalog
        self._system_prompt = str(system_prompt or "")
        self.max_turns = int(max_turns)
        self.max_tool_calls_per_run = int(max_tool_calls_per_run)
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
            float(model_timeout_seconds) if model_timeout_seconds is not None else None
        )
        self.model_fallbacks = tuple(model_fallbacks or ())
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_total_tokens = max_total_tokens
        self.max_stream_delta_chars = int(max_stream_delta_chars)
        self.max_tool_result_chars = int(max_tool_result_chars)
        self.tool_timeout_seconds = (
            float(tool_timeout_seconds) if tool_timeout_seconds is not None else None
        )
        self.tool_max_retries = int(tool_max_retries)
        self.tool_retry_delay_seconds = float(tool_retry_delay_seconds)
        self._tool_circuit = ToolCircuitBreaker(
            failure_threshold=tool_circuit_failure_threshold,
            reset_seconds=tool_circuit_reset_seconds,
        )
        self.checkpoint_store = checkpoint_store
        self.before_tool_call = before_tool_call
        self.after_tool_call = after_tool_call
        self.should_stop_after_turn = should_stop_after_turn
        self.event_callback = event_callback
        self.context_provider = context_provider
        self.input_sanitizer = input_sanitizer
        self.request_validator = request_validator
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
        self._state_io = AgentStatePersistence(
            transcript_store=self.transcript_store,
            checkpoint_store=self.checkpoint_store,
            system_messages=self._system_messages,
            max_messages=self.max_transcript_messages,
            max_chars=self.max_transcript_chars,
            emit=self._emit,
        )
        self._models = ModelExecutionCoordinator(
            options=ModelExecutionOptions(
                timeout_seconds=self.model_timeout_seconds,
                max_inflight=int(max_inflight_model_invocations),
                max_retries=self.model_max_retries,
                retry_delay_seconds=self.model_retry_delay_seconds,
                max_stream_delta_chars=self.max_stream_delta_chars,
                max_input_tokens=self.max_input_tokens,
                max_output_tokens=self.max_output_tokens,
                max_total_tokens=self.max_total_tokens,
            ),
            providers=lambda: (self.model, *self.model_fallbacks),
            prepare=self._model_inputs,
            normalize=self._normalize_turn,
            emit=self._emit,
            assert_not_interrupted=self._assert_not_interrupted,
        )
        self._tool_executor = ToolExecutionCoordinator(
            tool_catalog=self.tool_catalog,
            emit=self._emit,
            interrupt_reason=lambda request: self._interrupt_reason(request),
            assert_not_interrupted=lambda request: self._assert_not_interrupted(
                request
            ),
            before_tool_call=self.before_tool_call,
            after_tool_call=self.after_tool_call,
            tool_execution=self.tool_execution,
            max_parallel_tools=self.max_parallel_tools,
            max_inflight_tool_invocations=max_inflight_tool_invocations,
            tool_timeout_seconds=self.tool_timeout_seconds,
            tool_max_retries=self.tool_max_retries,
            tool_retry_delay_seconds=self.tool_retry_delay_seconds,
            tool_circuit=self._tool_circuit,
            max_tool_result_chars=self.max_tool_result_chars,
        )

    @staticmethod
    def _session_key(
        session_id: str | None,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> str:
        return "\x1f".join(
            (
                str(tenant_id or "default"),
                str(user_id or "anonymous"),
                str(session_id or "__default__"),
            )
        )

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

    def session_lock(self, request: TurnRequest) -> threading.RLock:
        """Return the Agent state lock used by the Runtime Kernel."""
        return self._lock_for(
            request.session_id,
            request.user_id,
            request.tenant_id,
        )

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
            key
            for key, state in self._session_states.items()
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
        self,
        callback: Callable[[dict[str, Any]], None],
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
        return self.run(
            TurnRequest(
                user_input=str(user_input),
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
                cancellation_event=self._abort_event_for(
                    session_id, user_id, tenant_id
                ),
            )
        )

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
                    calls.append(
                        ToolCall(
                            id=str(item.get("id") or item.get("tool_call_id") or ""),
                            name=str(item.get("name") or ""),
                            arguments=dict(
                                item.get("arguments") or item.get("args") or {}
                            ),
                            depends_on=tuple(item.get("depends_on") or ()),
                            argument_bindings=tuple(
                                ToolArgumentBinding(**binding)
                                for binding in item.get("argument_bindings") or ()
                                if isinstance(binding, Mapping)
                            ),
                        )
                    )
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
    ) -> Mapping[str, Any]:
        """Allow a model adapter to shape application results at Run end."""
        callback = getattr(self.model, "on_run_end", None)
        if not callable(callback):
            return {}
        try:
            result = callback(
                request,
                model_turn,
                tuple(dict(item) for item in tool_results),
                state,
            )
            return dict(result) if isinstance(result, Mapping) else {}
        except Exception:
            # Application result shaping cannot break the generic lifecycle.
            return {}

    @staticmethod
    def _awaiting_input_reply(
        tool_results: Sequence[Mapping[str, Any]],
        fallback: str,
    ) -> str:
        """Prefer the trusted gate prompt over an empty model Tool-call turn."""
        for item in tool_results:
            if not (item.get("needs_input") or item.get("needs_confirmation")):
                continue
            payload = item.get("confirmation_payload")
            if isinstance(payload, Mapping):
                question = str(payload.get("question") or "").strip()
                if question:
                    return question
            interaction = item.get("interaction")
            if isinstance(interaction, Mapping):
                question = str(
                    interaction.get("question") or interaction.get("prompt") or ""
                ).strip()
                if question:
                    return question
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return str(fallback or "")

    @staticmethod
    def _run_interactions(
        tool_results: Sequence[Mapping[str, Any]],
    ) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            dict(interaction)
            for item in tool_results
            if isinstance(item, Mapping)
            and isinstance((interaction := item.get("interaction")), Mapping)
        )

    def _notify_model_run_cleanup(
        self,
        request: TurnRequest,
        state: AgentState,
    ) -> None:
        """Release adapter-owned state after every Run, including failures."""
        callback = getattr(self.model, "on_run_cleanup", None)
        if callable(callback):
            try:
                callback(request, state)
            except Exception:
                # Adapter cleanup is best effort and must not replace the Run
                # result or hide the original failure.
                return

    def _notify_context_cleanup(
        self,
        request: TurnRequest,
        state: AgentState,
    ) -> None:
        """Release context-provider state after every Run."""
        callback = getattr(self.context_provider, "cleanup", None)
        if callable(callback):
            try:
                callback(request, state)
            except Exception:
                return

    def _model_inputs(
        self,
        request: TurnRequest,
        state: AgentState,
    ) -> tuple[list[Any], list[Any], TurnRequest]:
        tools = self.tool_catalog.list_tools() if self.tool_catalog else []
        if callable(self.tool_selector):
            tools = list(self.tool_selector(request, tuple(tools)))
        tools = list(tools[: self.max_tools])
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
            source_ids = None
            if isinstance(request.context, Mapping):
                configured_sources = request.context.get("skill_source_ids")
                if isinstance(configured_sources, (list, tuple, set, frozenset)):
                    source_ids = tuple(str(item) for item in configured_sources)
            skill_context = self.skill_catalog.build_context(
                request.user_input,
                source_ids=source_ids,
            )
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
        context = redact_for_persistence(context)
        if context != dict(model_request.context or {}):
            model_request = replace(model_request, context=context)
        return messages, tools, model_request

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

    def run(self, request: TurnRequest) -> RunResult:
        if not isinstance(request.context, Mapping):
            raise TypeError("TurnRequest.context must be a mapping")
        request = replace(
            request,
            run_id=str(request.run_id or uuid.uuid4()),
            turn_id=str(request.turn_id or uuid.uuid4()),
            context=dict(request.context),
        )
        state = self._state_for(
            request.session_id,
            request.user_id,
            request.tenant_id,
        )
        session_lock = self._lock_for(
            request.session_id,
            request.user_id,
            request.tenant_id,
        )
        abort_event = self._abort_event_for(
            request.session_id,
            request.user_id,
            request.tenant_id,
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
        checkpoint_source_id: str | None = None
        all_tool_results: list[dict[str, Any]] = []
        try:
            self._state_io.hydrate(request, state)
            checkpoint_source_id = self._state_io.restore_checkpoint(request, state)
            self._emit("agent_start", request)
            self._emit("turn_start", request, turn_index=0)
            if callable(self.request_validator):
                validation_error = self.request_validator(request)
                if validation_error:
                    if not isinstance(validation_error, str):
                        raise TypeError(
                            "request_validator must return a string or None"
                        )
                    self._emit(
                        "turn_end",
                        request,
                        turn_index=0,
                        tool_results=[],
                        status="failed",
                        reason="request_validation",
                    )
                    result = RunResult(
                        run_id=str(request.run_id or ""),
                        turn_id=str(request.turn_id or ""),
                        status=RunStatus.FAILED,
                        reply=validation_error,
                        data={
                            "request_validation_error": validation_error,
                            "tool_results": [],
                            "needs_input": False,
                            "usage": dict(state.usage),
                        },
                    )
                    self._emit("agent_end", request, status=result.status.value)
                    return result
            user_message = AgentMessage.user(
                self.input_sanitizer(request.user_input)
                if callable(self.input_sanitizer)
                else request.user_input,
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
            )
            self._state_io.append_message(state, user_message, request=request)
            self._emit("message_end", request, message=user_message.to_dict())
            tool_results: list[dict[str, Any]] = []
            tool_call_count = 0
            last_reply = ""
            application_data: Mapping[str, Any] = {}
            for turn_index in range(self.max_turns):
                interrupt_reason = self._interrupt_reason(request, abort_event)
                if interrupt_reason is not None:
                    result = self._interrupted_result(
                        request,
                        state,
                        reason=interrupt_reason,
                    )
                    self._emit("agent_end", request, status=result.status.value)
                    return result
                if turn_index > 0:
                    self._emit("turn_start", request, turn_index=turn_index)
                tool_results = []
                model_turn = self._models.complete(request, state, abort_event)
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
                self._state_io.append_message(state, assistant, request=request)
                last_reply = str(model_turn.content or "")
                self._emit("message_end", request, message=assistant.to_dict())
                tool_budget_exceeded = False
                if model_turn.tool_calls:
                    requested_count = len(model_turn.tool_calls)
                    if tool_call_count + requested_count > self.max_tool_calls_per_run:
                        tool_budget_exceeded = True
                        self._emit(
                            "tool_call_budget_exceeded",
                            request,
                            accepted_count=tool_call_count,
                            requested_count=requested_count,
                            limit=self.max_tool_calls_per_run,
                        )
                        tool_results = [
                            {
                                "tool_call_id": str(call.id),
                                "name": call.name,
                                "content": (
                                    "Run Tool-call budget exceeded; this batch "
                                    "was rejected before execution."
                                ),
                                "is_error": True,
                                "terminate": True,
                                "runtime_signals": {
                                    "tool_call_budget_exceeded": True,
                                },
                            }
                            for call in model_turn.tool_calls
                        ]
                    else:
                        tool_results = self._tool_executor.execute_tools(
                            request,
                            assistant,
                            model_turn.tool_calls,
                            state,
                        )
                        tool_call_count += requested_count
                    all_tool_results.extend(tool_results)
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
                        self._state_io.append_message(
                            state, tool_message, request=request
                        )
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
                checkpoint_ok = self._state_io.save_checkpoint(
                    request,
                    state,
                    turn_index=turn_index,
                    tool_results=tool_results,
                )
                if (
                    not model_turn.tool_calls
                    or any(
                        bool(item.get("needs_input") or item.get("needs_confirmation"))
                        for item in tool_results
                    )
                    or all(bool(item.get("terminate")) for item in tool_results)
                    or any(bool(item.get("recovery_required")) for item in tool_results)
                    or tool_budget_exceeded
                    or (
                        callable(self.should_stop_after_turn)
                        and self.should_stop_after_turn(state)
                    )
                ):
                    application_data = self._notify_model_run_end(
                        request,
                        model_turn,
                        tool_results,
                        state,
                    )
                    awaiting_input = model_turn.stop_reason in {
                        "awaiting_input",
                        "awaiting_confirmation",
                        "needs_input",
                    } or any(
                        bool(item.get("needs_input") or item.get("needs_confirmation"))
                        for item in tool_results
                    )
                    tool_recovery = any(
                        bool(item.get("recovery_required"))
                        or bool(
                            isinstance(item.get("runtime_signals"), Mapping)
                            and item["runtime_signals"].get("audit_error")
                        )
                        for item in tool_results
                    )
                    tool_cancelled = any(
                        bool(item.get("cancelled")) for item in tool_results
                    )
                    runtime_signals = {
                        key: value
                        for item in tool_results
                        if isinstance(item.get("runtime_signals"), Mapping)
                        for key, value in item["runtime_signals"].items()
                    }
                    if not checkpoint_ok:
                        runtime_signals["checkpoint_error"] = True
                    terminal_status = (
                        RunStatus.RECOVERY_REQUIRED
                        if not checkpoint_ok or tool_recovery
                        else RunStatus.CANCELLED
                        if tool_cancelled
                        else RunStatus.FAILED
                        if tool_budget_exceeded
                        else RunStatus.FAILED
                        if model_turn.stop_reason in {"error", "policy_blocked"}
                        else RunStatus.AWAITING_INPUT
                        if awaiting_input
                        else RunStatus.SUCCEEDED
                    )
                    terminal_reply = (
                        "Run Tool-call budget exceeded; the rejected batch was not executed."
                        if tool_budget_exceeded
                        else self._awaiting_input_reply(tool_results, last_reply)
                        if awaiting_input
                        else last_reply
                    )
                    result = RunResult(
                        run_id=str(request.run_id or ""),
                        turn_id=str(request.turn_id or ""),
                        status=terminal_status,
                        reply=terminal_reply,
                        needs_input=awaiting_input,
                        effect_state="unknown" if tool_recovery else "none",
                        recovery_required=tool_recovery or not checkpoint_ok,
                        runtime_signals=runtime_signals,
                        data={
                            "messages": [item.to_dict() for item in state.messages],
                            "tool_results": list(all_tool_results),
                            "tool_call_count": tool_call_count,
                            "tool_call_limit": self.max_tool_calls_per_run,
                            "tool_call_budget_exceeded": tool_budget_exceeded,
                            "needs_input": awaiting_input,
                            "usage": dict(state.usage),
                        },
                        application_data=application_data,
                        interactions=self._run_interactions(all_tool_results),
                    )
                    if result.status not in {
                        RunStatus.RECOVERY_REQUIRED,
                        RunStatus.CANCELLED,
                    }:
                        self._state_io.clear_checkpoint(request)
                        if checkpoint_source_id and checkpoint_source_id != str(
                            request.run_id or ""
                        ):
                            self._state_io.clear_checkpoint_id(
                                checkpoint_source_id,
                                request,
                            )
                    self._emit("agent_end", request, status=result.status.value)
                    return result
            application_data = self._notify_model_run_end(
                request,
                model_turn,
                tool_results,
                state,
            )
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                reply=last_reply,
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "tool_results": list(all_tool_results),
                    "tool_call_count": tool_call_count,
                    "tool_call_limit": self.max_tool_calls_per_run,
                    "error": "maximum agent turns exceeded",
                    "usage": dict(state.usage),
                },
                application_data=application_data,
                interactions=self._run_interactions(all_tool_results),
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
        except ModelUnavailableError:
            state.error_message = "ModelUnavailableError"
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                reply="此 Run 未配置模型服务，无法理解或执行请求。",
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "error": "model_not_configured",
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
                    "tool_results": list(all_tool_results),
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
                    "tool_results": list(all_tool_results),
                    "usage": dict(state.usage),
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except AgentLeaseLostError:
            result = self._interrupted_result(
                request,
                state,
                reason="session_lease_lost",
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except AgentCancelledError:
            result = self._interrupted_result(
                request,
                state,
                reason="cancelled",
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
                    "tool_results": list(all_tool_results),
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
            self._notify_model_run_cleanup(request, state)
            self._notify_context_cleanup(request, state)

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
