"""Stateful, application-neutral Agent loop.

The loop owns transcript state, model turns, Tool preflight/execution and
event ordering. Applications inject a model adapter, Tool catalog and policy
hooks; the loop never knows a provider, channel or business workflow.
"""

from __future__ import annotations

import re
import sys
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from dataclasses import replace
import uuid
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence

from .context import ContextProvider, context_prompt
from .evidence_compaction import compact_read_messages
from .conversation_recall import (
    has_recall_terms, is_contextual_followup, relevant_user_requests,
)
from .core.agent_profile import CORE_AGENT_SYSTEM_PROMPT
from .core.conversation_selection import (
    catalog_selection_input,
    clarification_context,
    clarification_origin,
    pending_input_interaction,
)
from .core.security import canonical_json
from .messages import AgentMessage, ModelTurn, ToolArgumentBinding, ToolCall
from .model_execution import (
    ModelExecutionCoordinator,
    ModelExecutionOptions,
    ModelTimeoutError,
    ModelCapacityError,
    ModelBudgetExceededError,
    ModelUnavailableError,
)
from .model_limits import (
    DEFAULT_MODEL_INPUT_CHARS, DEFAULT_MODEL_OUTPUT_CHARS, DEFAULT_STREAM_CHUNKS,
    ModelInputLimitError, ModelLimitError, bound_model_messages, model_input_chars,
    positive_integer,
)
from .persistence import TranscriptStore
from .state_persistence import AgentStatePersistence, TranscriptPersistenceError
from .redaction import redact_for_persistence
from .reliability import ToolCircuitBreaker
from .results import RunResult, RunStatus, tool_outcome_status
from .core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS
from .runtime_kernel import CancellationEventGroup, TurnRequest
from .skills import SkillCatalog
from .tool_catalog import ToolCatalog
from .tool_discovery import (
    DISCOVERY_GUIDANCE, RunToolDiscovery, active_tool_discovery, is_discovery_tool,
)
from .tool_execution import (
    ToolCallContext,
    ToolExecutionCoordinator,
    ToolReadCache,
    ToolWriteReplayCache,
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


def _missing_clarification_context(
    request: TurnRequest,
    transcript: Sequence[AgentMessage],
    bounded: Sequence[AgentMessage],
) -> tuple[str, ...]:
    context = clarification_context(
        request.user_input, request.turn_id, transcript,
    )
    if not context:
        return ()
    existing = "\n".join(
        str(message.content or "")
        for message in bounded if message.role == "user"
    )
    return () if all(item in existing for item in context) else context


class AgentCancelledError(RuntimeError):
    """The current Agent Run was cooperatively cancelled."""


class AgentLeaseLostError(RuntimeError):
    """The current Agent Run lost its durable Runtime session lease."""


_MODEL_SNAPSHOT_UNSET = object()


@dataclass
class AgentState:
    messages: list[AgentMessage] = field(default_factory=list)
    is_running: bool = False
    error_message: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    hydrated: bool = False
    historical_turn_id: str = ""
    historical_requests: tuple[AgentMessage, ...] = ()
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
        model_timeout_seconds: float | None = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        max_inflight_model_invocations: int = 32,
        model_fallbacks: Sequence[Any] = (),
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        max_total_tokens: int | None = None,
        max_model_input_chars: int = DEFAULT_MODEL_INPUT_CHARS,
        max_model_output_chars: int = DEFAULT_MODEL_OUTPUT_CHARS,
        max_stream_chunks: int = DEFAULT_STREAM_CHUNKS,
        max_stream_delta_chars: int = 4096,
        max_tool_result_chars: int = 32_000,
        max_interaction_chars: int = 256_000,
        tool_timeout_seconds: float | None = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
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
        if tool_execution not in {"sequential", "parallel", "parallel_reads"}:
            raise ValueError("unsupported tool execution strategy")
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
        if max_interaction_chars <= 0:
            raise ValueError("max_interaction_chars must be positive")
        if tool_timeout_seconds is not None and tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        if tool_max_retries < 0:
            raise ValueError("tool_max_retries must be non-negative")
        if tool_retry_delay_seconds < 0:
            raise ValueError("tool_retry_delay_seconds must be non-negative")
        self.model = model
        self._run_model_snapshot: ContextVar[Any] = ContextVar(
            f"agent_run_model_snapshot_{id(self)}",
            default=_MODEL_SNAPSHOT_UNSET,
        )
        self.tool_catalog = tool_catalog
        self.skill_catalog = skill_catalog
        application_prompt = str(system_prompt or "").strip()
        self._system_prompt = "\n\n".join(
            part for part in (
                CORE_AGENT_SYSTEM_PROMPT.strip(),
                application_prompt,
            )
            if part
        )
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
        self.max_model_input_chars = positive_integer("max_model_input_chars", max_model_input_chars)
        self.max_model_output_chars = positive_integer("max_model_output_chars", max_model_output_chars)
        self.max_stream_chunks = positive_integer("max_stream_chunks", max_stream_chunks)
        self.max_stream_delta_chars = int(max_stream_delta_chars)
        self.max_tool_result_chars = int(max_tool_result_chars)
        self.max_interaction_chars = int(max_interaction_chars)
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
        # Stable policy is added to model inputs per turn, never stored as
        # conversation history or counted against the transcript window.
        self._system_messages: tuple[AgentMessage, ...] = ()
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
                max_model_output_chars=self.max_model_output_chars,
                max_stream_chunks=self.max_stream_chunks,
            ),
            providers=self._model_providers_for_current_run,
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
            max_interaction_chars=self.max_interaction_chars,
        )

    def _model_for_current_run(self) -> Any:
        snapshot = self._run_model_snapshot.get()
        return self.model if snapshot is _MODEL_SNAPSHOT_UNSET else snapshot

    def _model_providers_for_current_run(self) -> tuple[Any, ...]:
        return (self._model_for_current_run(), *self.model_fallbacks)

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
                AgentState(),
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
        """Return the immutable policy prompt supplied to every model turn."""
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
            state.messages = []
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

    def abort(
        self,
        session_id: str | None = None,
        *,
        user_id: str = "anonymous",
        tenant_id: str = "default",
    ) -> bool:
        """Request cancellation only for an active, identity-scoped session."""
        key = self._session_key(session_id, user_id, tenant_id)
        with self._session_guard:
            state = self._session_states.get(key)
            event = self._abort_events.get(key)
            if state is None or event is None or not state.is_running:
                return False
            event.set()
            return True

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
        callback = getattr(self._model_for_current_run(), "on_run_end", None)
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
    def _non_retriable_error_reply(
        tool_results: Sequence[Mapping[str, Any]],
        fallback: str,
    ) -> str:
        for item in tool_results:
            signals = item.get("runtime_signals")
            if not (
                isinstance(signals, Mapping)
                and signals.get("non_retriable_tool_error")
            ):
                continue
            content = item.get("content")
            if isinstance(content, Mapping):
                error = str(content.get("error") or "").strip()
                if error:
                    return error
            elif isinstance(content, str) and content.strip():
                return content.strip()
        return str(fallback or "")

    @staticmethod
    def _terminate_repeated_schema_repairs(
        tool_calls: Sequence[ToolCall],
        tool_results: Sequence[dict[str, Any]],
        attempted_signatures: set[str],
    ) -> None:
        """Allow one model correction for an identical extra-field error."""
        calls_by_id = {
            str(call.id or ""): call for call in tool_calls if str(call.id or "")
        }
        for result in tool_results:
            signals = result.get("runtime_signals")
            if not (
                isinstance(signals, Mapping)
                and signals.get("tool_input_repairable")
            ):
                continue
            call = calls_by_id.get(str(result.get("tool_call_id") or ""))
            signature = canonical_json({
                "tool": str(call.name if call else result.get("name") or ""),
                "arguments": dict(call.arguments) if call else {},
                "reason": str(result.get("content") or "") if call is None else "",
            })
            if signature not in attempted_signatures:
                attempted_signatures.add(signature)
                continue

            result["terminate"] = True
            updated_signals = dict(signals)
            updated_signals.pop("tool_input_repairable", None)
            updated_signals["non_retriable_tool_error"] = True
            updated_signals["schema_repair_retry_exhausted"] = True
            result["runtime_signals"] = updated_signals

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
        callback = getattr(self._model_for_current_run(), "on_run_cleanup", None)
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
                self._emit(
                    "context_cleanup_error", request,
                    error_type=type(sys.exception()).__name__,
                )

    def _model_inputs(
        self,
        request: TurnRequest,
        state: AgentState,
    ) -> tuple[list[Any], list[Any], TurnRequest]:
        transcript = state.snapshot()
        if len(transcript) > self.max_transcript_messages:
            raise ModelInputLimitError()
        definitions = self.tool_catalog.list_tools() if self.tool_catalog else []
        if self._state_io.over_budget(transcript):
            transcript = compact_read_messages(
                transcript, definitions, max_chars=self.max_transcript_chars,
                message_size=lambda message: len(str(message.content)),
            )
            if self._state_io.over_budget(transcript):
                raise ModelInputLimitError()
        tools, require_tool_call = self._tools_for_turn(
            request, transcript, state=state,
        )
        context_messages, model_request = self._context_messages_for_turn(
            request, transcript, tools=tools,
        )
        if any(is_discovery_tool(tool) for tool in tools):
            context_messages.append(AgentMessage.system(DISCOVERY_GUIDANCE))
        if (
            require_tool_call
            and model_request.initial_tool_choice in (None, "auto")
        ):
            model_request = replace(
                model_request,
                initial_tool_choice="required",
            )
        messages = [
            AgentMessage.system(self._system_prompt),
            *(
                message for message in transcript
                if message.role == "system"
            ),
            *context_messages,
            *(
                message for message in transcript
                if message.role != "system"
            ),
        ]
        if not any(
            message.role == "user" and message.turn_id == request.turn_id
            for message in transcript
        ):
            raise ModelInputLimitError()
        bounded = bound_model_messages(
            messages, tools, max_chars=self.max_model_input_chars,
            evidence_definitions=definitions,
        )
        self._emit_evidence_compaction(request, state.snapshot(), bounded)
        bounded = self._add_recalled_context(
            request, state, transcript, bounded, tools,
        )
        removed_count = len({
            message.message_id for message in messages
        } - {
            message.message_id for message in bounded
        })
        if removed_count:
            self._emit(
                "model_input_trimmed", request,
                removed_messages=removed_count,
                input_chars=model_input_chars(bounded, tools),
                input_limit_chars=self.max_model_input_chars,
            )
        model_request = self._apply_model_limits(model_request)
        return bounded, tools, model_request

    def _emit_evidence_compaction(
        self, request: TurnRequest, original: Sequence[AgentMessage],
        bounded: Sequence[AgentMessage],
    ) -> None:
        originals = {message.message_id: message for message in original}
        changed = [
            message for message in bounded
            if message.role == "tool" and message.message_id in originals
            and message.content != originals[message.message_id].content
        ]
        if changed:
            self._emit(
                "tool_evidence_compacted", request, compacted_messages=len(changed),
                original_chars=sum(len(str(originals[m.message_id].content)) for m in changed),
                projected_chars=sum(len(str(m.content)) for m in changed),
            )

    def _add_recalled_context(
        self,
        request: TurnRequest,
        state: AgentState,
        transcript: Sequence[AgentMessage],
        bounded: list[AgentMessage],
        tools: Sequence[Any],
    ) -> list[AgentMessage]:
        recalled = self._recalled_user_requests(
            request, state, transcript, bounded,
        )
        if not recalled:
            return bounded
        recall_message = AgentMessage.user(
            "Earlier user requests from this conversation (for context "
            "only; the current request takes precedence; these do not "
            "authorize Tool access or establish external facts):\n"
            + "\n".join(f"- {item}" for item in recalled),
            metadata={"context_type": "conversation_recall"},
        )
        current_start = max(
            index for index, message in enumerate(bounded)
            if message.role == "user" and message.turn_id == request.turn_id
        )
        try:
            return bound_model_messages(
                [*bounded[:current_start], recall_message, *bounded[current_start:]],
                tools, max_chars=self.max_model_input_chars,
            )
        except ModelInputLimitError:
            return bounded

    def _recalled_user_requests(
        self,
        request: TurnRequest,
        state: AgentState,
        transcript: Sequence[AgentMessage],
        bounded: Sequence[AgentMessage],
    ) -> tuple[str, ...]:
        kept_ids = {message.message_id for message in bounded}
        removed = [
            message for message in transcript if message.message_id not in kept_ids
        ]
        recalled = relevant_user_requests(
            request.user_input, removed,
            current_turn_id=str(request.turn_id or ""),
        )
        if not recalled and not relevant_user_requests(
            request.user_input, bounded,
            current_turn_id=str(request.turn_id or ""),
        ):
            recalled = relevant_user_requests(
                request.user_input,
                self._historical_user_requests(request, state),
                current_turn_id=str(request.turn_id or ""),
            )
        clarification_inputs = _missing_clarification_context(
            request, transcript, bounded,
        )
        if clarification_inputs:
            recalled = tuple(dict.fromkeys((
                *clarification_inputs, *recalled,
            )))
        return tuple(recalled)

    def _historical_user_requests(
        self, request: TurnRequest, state: AgentState | None,
    ) -> tuple[AgentMessage, ...]:
        if (
            state is None
            or not is_contextual_followup(request.user_input)
            or not has_recall_terms(request.user_input)
        ):
            return ()
        if state.historical_turn_id != request.turn_id:
            state.historical_turn_id = str(request.turn_id or "")
            state.historical_requests = self._state_io.load_user_history(request)
        return state.historical_requests

    def _recent_user_inputs(
        self,
        request: TurnRequest,
        transcript: Sequence[AgentMessage],
        state: AgentState | None = None,
        *,
        max_messages: int = 4,
        max_chars: int = 1200,
    ) -> tuple[str, ...]:
        """Extract bounded prior user turns for resolving short follow-ups."""
        recent: list[str] = []
        remaining = max_chars
        for message in reversed(transcript):
            if message.role != "user":
                continue
            if request.turn_id and message.turn_id == request.turn_id:
                continue
            content = str(message.content or "").strip()
            if not content:
                continue
            content = content[-remaining:]
            if content:
                recent.append(content)
                remaining -= len(content)
            if len(recent) >= max_messages or remaining <= 0:
                break
        recent.reverse()
        if len(recent) >= max_messages or (
            state is not None and len(transcript) >= self.max_transcript_messages
        ):
            tail = recent[-(max_messages - 1):] if max_messages > 1 else []
            anchor_budget = min(400, max_chars - sum(map(len, tail)))
            relevant = relevant_user_requests(
                request.user_input, transcript,
                current_turn_id=str(request.turn_id or ""),
                limit=1,
                max_chars=anchor_budget,
            ) if anchor_budget >= 24 else ()
            if not relevant and anchor_budget >= 24:
                relevant = relevant_user_requests(
                    request.user_input,
                    self._historical_user_requests(request, state),
                    current_turn_id=str(request.turn_id or ""),
                    limit=1,
                    max_chars=anchor_budget,
                )
            if relevant and relevant[0] not in recent and max_messages > 1:
                # The selector reads at most four previous requests. Preserve
                # one topical anchor across short unrelated interjections.
                recent = [relevant[0], *tail]
        return tuple(recent)

    @staticmethod
    def _prior_turn_tool_names(
        request: TurnRequest,
        transcript: Sequence[AgentMessage],
        *,
        limit: int = 8,
    ) -> tuple[str, ...]:
        """Return registered Tool names invoked in the immediately prior turn.

        This is routing context only. The receiving selector must resolve every
        name against the current registry and reapply current policy before a
        Tool can reach the model.
        """
        prior_user_turn = next((
            message.turn_id
            for message in reversed(transcript)
            if message.role == "user"
            and message.turn_id != str(request.turn_id or "")
        ), None)
        if prior_user_turn is None:
            return ()
        names: list[str] = []
        seen: set[str] = set()
        for message in reversed(transcript):
            if message.role != "tool" or message.turn_id != prior_user_turn:
                continue
            name = str(message.name or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
            if len(names) >= limit:
                break
        return tuple(names)

    def _tool_selection_request(
        self,
        request: TurnRequest,
        transcript: Sequence[AgentMessage],
        tools: Sequence[Any],
        state: AgentState | None = None,
    ) -> tuple[TurnRequest, str]:
        selection_context = dict(request.context or {})
        recent_inputs = self._recent_user_inputs(request, transcript, state)
        if recent_inputs:
            selection_context["_agent_tool_selection_context"] = recent_inputs
        prior_tool_names = self._prior_turn_tool_names(request, transcript)
        if prior_tool_names:
            selection_context["_agent_prior_tool_names"] = prior_tool_names
        pending = pending_input_interaction(
            request.turn_id, transcript, choice=request.user_input.strip(),
            response=selection_context.get("_agent_interaction_response"),
        )
        if pending:
            selection_context["_agent_pending_interaction"] = pending
        origin = clarification_origin(
            request.user_input, request.turn_id, transcript,
        )
        clarification_inputs = clarification_context(
            request.user_input, request.turn_id, transcript,
        ) if origin else ()
        if clarification_inputs:
            selection_context["_agent_tool_selection_context"] = clarification_inputs
            selection_context["_agent_clarification_followup"] = True
        catalog_selection, target_name = catalog_selection_input(
            request.user_input, request.turn_id, transcript, tools,
        )
        selection_input = (
            catalog_selection or (
                f"{origin}\n{request.user_input}" if origin else request.user_input
            )
        )
        if catalog_selection:
            selection_context["_agent_tool_choice_required"] = True
        return (
            replace(request, user_input=selection_input, context=selection_context),
            target_name,
        )

    @staticmethod
    def _restrict_to_catalog_target(
        tools: Sequence[Any],
        target_name: str,
    ) -> list[Any]:
        if not target_name:
            return list(tools)
        return [
            tool for tool in tools
            if Agent._tool_name(tool) == target_name
        ]

    def _tools_for_turn(
        self,
        request: TurnRequest,
        transcript: Sequence[AgentMessage] = (),
        *,
        state: AgentState | None = None,
    ) -> tuple[list[Any], bool]:
        tools = self.tool_catalog.list_tools() if self.tool_catalog else []
        catalog_tools = tuple(tools)
        # Discovery is a control capability, not a competing business intent.
        tools = [tool for tool in tools if not is_discovery_tool(tool)]
        require_tool_call = False
        if callable(self.tool_selector):
            selection_request, catalog_target_name = self._tool_selection_request(
                request, transcript, tools, state,
            )
            selection_context = selection_request.context
            tools = list(self.tool_selector(selection_request, tuple(tools)))
            tools = self._restrict_to_catalog_target(tools, catalog_target_name)
            require_tool_call = bool(
                selection_context.pop("_agent_tool_choice_required", False)
            )
            require_tool_call = require_tool_call and not any(
                message.role == "assistant"
                and message.turn_id == request.turn_id
                for message in transcript
            )
            selection_context.pop("_agent_tool_selection_context", None)
            selection_context.pop("_agent_prior_tool_names", None)
            selection_context.pop("_agent_clarification_followup", None)
            selection_context.pop("_agent_pending_interaction", None)
            selection_context.pop("_agent_interaction_response", None)
            if isinstance(request.context, dict):
                request.context.update({
                    key: value
                    for key, value in selection_context.items()
                })
        if request.tool_allowlist is not None:
            allowed = set(request.tool_allowlist)
            tools = [tool for tool in tools if self._tool_name(tool) in allowed]
        discovery = active_tool_discovery.get()
        if discovery is not None:
            tools = discovery.select(tools, catalog_tools)
        tools = list(tools[: self.max_tools])
        require_tool_call = require_tool_call and bool(tools)
        if isinstance(request.context, dict):
            request.context["_harness_visible_tool_names"] = tuple(
                name for name in (self._tool_name(tool) for tool in tools) if name
            )

        return tools, require_tool_call

    def _context_messages_for_turn(
        self,
        request: TurnRequest,
        transcript: Sequence[AgentMessage],
        *,
        tools: Sequence[Any] = (),
    ) -> tuple[list[AgentMessage], TurnRequest]:
        context_messages: list[AgentMessage] = []
        model_request = request
        if self.context_provider is not None:
            build_tool_context = getattr(self.context_provider, "build_tool_context", None)
            build_context = getattr(self.context_provider, "build_context", None)
            if not callable(build_context) and not callable(build_tool_context):
                raise TypeError("context_provider must expose build_context()")
            started = time.monotonic()
            try:
                value = (
                    build_tool_context(request, transcript, tools)
                    if callable(build_tool_context) else build_context(request, transcript)
                )
            finally:
                self._emit(
                    "runtime_phase", request, phase="context_build",
                    duration_ms=round((time.monotonic() - started) * 1000, 3),
                )
            if isinstance(value, Mapping):
                context = dict(request.context or {})
                context["agent_context"] = dict(value)
                model_request = replace(request, context=context)
                prompt = redact_for_persistence(context_prompt(value))
                if prompt:
                    context_messages.append(
                        AgentMessage.system(
                            prompt,
                            run_id=str(request.run_id or ""),
                            turn_id=str(request.turn_id or ""),
                            metadata={"context_type": "provider"},
                        )
                    )
        if self.skill_catalog is not None:
            source_ids = None
            if isinstance(request.context, Mapping):
                configured_sources = request.context.get("skill_source_ids")
                if isinstance(configured_sources, (list, tuple, set, frozenset)):
                    source_ids = tuple(str(item) for item in configured_sources)
            build_tool_context = getattr(self.skill_catalog, "build_tool_context", None)
            if callable(build_tool_context):
                skill_context = build_tool_context(request.user_input, tools, source_ids=source_ids)
            else:
                skill_context = self.skill_catalog.build_context(
                    request.user_input, source_ids=source_ids,
                )
            skill_context = redact_for_persistence(skill_context)
            if skill_context:
                context_messages.append(
                    AgentMessage.system(
                        skill_context,
                        run_id=str(request.run_id or ""),
                        turn_id=str(request.turn_id or ""),
                        metadata={"context_type": "skills"},
                    )
                )
        return context_messages, model_request

    def _apply_model_limits(self, model_request: TurnRequest) -> TurnRequest:
        context = dict(model_request.context or {})
        if self.model_timeout_seconds is not None:
            context["model_timeout_seconds"] = self.model_timeout_seconds
        for name, value in (
            ("max_model_input_chars", self.max_model_input_chars),
            ("max_model_output_chars", self.max_model_output_chars),
            ("max_input_tokens", self.max_input_tokens),
            ("max_output_tokens", self.max_output_tokens),
            ("max_total_tokens", self.max_total_tokens),
        ):
            if value is not None:
                context[name] = value
        context = redact_for_persistence(context)
        if context != dict(model_request.context or {}):
            model_request = replace(model_request, context=context)
        return model_request

    @staticmethod
    def _tool_name(tool: Any) -> str:
        if isinstance(tool, Mapping):
            return str(tool.get("name") or "").strip()
        return str(getattr(tool, "name", "") or "").strip()

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

    def _interrupted_result(
        self,
        request: TurnRequest,
        state: AgentState,
        *,
        reason: str,
        tool_results: Sequence[Mapping[str, Any]],
        tool_call_count: int,
    ) -> RunResult:
        signals = {
            key: value for item in tool_results
            if isinstance(item.get("runtime_signals"), Mapping)
            for key, value in item["runtime_signals"].items()
        }
        recovery = reason == "session_lease_lost" or any(
            item.get("recovery_required")
            or item.get("effect_state") in {"unknown", "recovery_required"}
            for item in tool_results
        ) or bool(signals.get("audit_error"))
        return RunResult(
            run_id=str(request.run_id or ""),
            turn_id=str(request.turn_id or ""),
            status=RunStatus.RECOVERY_REQUIRED if recovery else RunStatus.CANCELLED,
            recovery_required=recovery,
            effect_state="unknown" if recovery else "none",
            runtime_signals={**signals, reason: True},
            data={
                "messages": [item.to_dict() for item in state.messages],
                "error": reason,
                "tool_results": list(tool_results),
                "tool_call_count": tool_call_count,
                "tool_call_limit": self.max_tool_calls_per_run,
                "usage": dict(state.usage),
            },
            interactions=self._run_interactions(tool_results),
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
        request = replace(
            request,
            cancellation_event=CancellationEventGroup(
                request.cancellation_event,
                abort_event,
            ),
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
        tool_call_count = 0
        run_read_cache = ToolReadCache()
        run_write_cache = ToolWriteReplayCache()
        run_resource_history: list[Mapping[str, Any]] = []
        schema_repair_attempts: set[str] = set()
        model_snapshot_token = self._run_model_snapshot.set(self.model)
        discovery = RunToolDiscovery(request, self.tool_catalog, self.max_tools)
        discovery_token = active_tool_discovery.set(discovery)
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
            interaction = (
                request.context.get("_agent_interaction_response")
                if isinstance(request.context, Mapping) else None
            )
            origin = (
                {
                    "turn_id": interaction["turn_id"],
                    "tool_name": interaction["tool_name"],
                }
                if isinstance(interaction, Mapping)
                and all(
                    isinstance(interaction.get(key), str)
                    and 0 < len(interaction[key]) <= 200
                    for key in ("turn_id", "tool_name")
                )
                else None
            )
            user_message = AgentMessage.user(
                self.input_sanitizer(request.user_input)
                if callable(self.input_sanitizer)
                else request.user_input,
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                metadata={
                    **({"interaction_origin": origin} if origin else {}),
                    **({"attachments": [
                        media.to_metadata() for media in request.input_media
                    ]} if request.input_media else {}),
                },
            )
            if len(str(user_message.content)) > min(
                self.max_transcript_chars, self.max_model_input_chars,
            ):
                raise ModelInputLimitError()
            self._state_io.append_message(state, user_message, request=request)
            self._emit("message_end", request, message=user_message.to_dict())
            tool_results: list[dict[str, Any]] = []
            last_reply = ""
            application_data: Mapping[str, Any] = {}
            for turn_index in range(self.max_turns):
                interrupt_reason = self._interrupt_reason(request, abort_event)
                if interrupt_reason is not None:
                    result = self._interrupted_result(
                        request,
                        state,
                        reason=interrupt_reason,
                        tool_results=all_tool_results,
                        tool_call_count=tool_call_count,
                    )
                    self._emit("agent_end", request, status=result.status.value)
                    return result
                if turn_index > 0:
                    self._emit("turn_start", request, turn_index=turn_index)
                tool_results = []
                model_request = (
                    replace(request, initial_tool_choice=None)
                    if turn_index > 0 and request.initial_tool_choice
                    else request
                )
                model_turn = self._models.complete(
                    model_request, state, abort_event,
                )
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
                            read_cache=run_read_cache,
                            write_cache=run_write_cache,
                            resource_history=run_resource_history,
                        )
                        tool_call_count += requested_count
                    self._terminate_repeated_schema_repairs(
                        model_turn.tool_calls,
                        tool_results,
                        schema_repair_attempts,
                    )
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
                                        "interaction",
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
                non_retriable_tool_failure = any(
                    bool(signals.get("non_retriable_tool_error"))
                    for item in tool_results
                    if isinstance((signals := item.get("runtime_signals")), Mapping)
                )
                if (
                    not model_turn.tool_calls
                    or any(
                        bool(item.get("needs_input") or item.get("needs_confirmation"))
                        for item in tool_results
                    )
                    or non_retriable_tool_failure
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
                        for item in all_tool_results
                        if isinstance(item.get("runtime_signals"), Mapping)
                        for key, value in item["runtime_signals"].items()
                    }
                    if model_turn.stop_reason == "required_tool_failed":
                        runtime_signals["required_tool_call_failed"] = True
                    if not checkpoint_ok:
                        runtime_signals["checkpoint_error"] = True
                    terminal_status = (
                        RunStatus.RECOVERY_REQUIRED
                        if not checkpoint_ok or tool_recovery
                        else RunStatus.CANCELLED
                        if tool_cancelled
                        else RunStatus.FAILED
                        if tool_budget_exceeded
                        or model_turn.stop_reason in {
                            "error",
                            "policy_blocked",
                            "required_tool_failed",
                        }
                        or non_retriable_tool_failure
                        or any(
                            isinstance(item.get("runtime_signals"), Mapping)
                            and item["runtime_signals"].get(
                                "tool_allowlist_violation"
                            )
                            for item in tool_results
                        )
                        else RunStatus.AWAITING_INPUT
                        if awaiting_input
                        else tool_outcome_status(all_tool_results)
                    )
                    terminal_reply = (
                        "Run Tool-call budget exceeded; the rejected batch was not executed."
                        if tool_budget_exceeded
                        else self._awaiting_input_reply(tool_results, last_reply)
                        if awaiting_input
                        else last_reply
                    )
                    missing_final_reply = (
                        not awaiting_input
                        and not model_turn.tool_calls
                        and not last_reply.strip()
                    )
                    if missing_final_reply:
                        if terminal_status == RunStatus.SUCCEEDED:
                            terminal_status = RunStatus.FAILED
                        terminal_reply = (
                            "本回合已有工具执行记录，但模型没有生成最终文字说明。"
                            "请先核实执行状态后再决定是否重试。"
                            if all_tool_results
                            else "模型本回合没有生成文字回复，也没有执行工具操作。"
                            "请重试，或换一种问法。"
                        )
                    if non_retriable_tool_failure:
                        terminal_reply = self._non_retriable_error_reply(
                            tool_results,
                            terminal_reply,
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
        except ModelLimitError as error:
            state.error_message = type(error).__name__
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                reply=error.public_reply,
                runtime_signals={error.safe_reason_code: True},
                data={
                    "messages": [item.to_dict() for item in state.messages],
                    "error": error.safe_reason_code,
                    "tool_results": list(all_tool_results),
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
                tool_results=all_tool_results,
                tool_call_count=tool_call_count,
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except AgentCancelledError:
            result = self._interrupted_result(
                request,
                state,
                reason="cancelled",
                tool_results=all_tool_results,
                tool_call_count=tool_call_count,
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except Exception as error:
            state.error_message = type(error).__name__
            error_code = getattr(error, "safe_reason_code", None)
            failure_data = {
                "messages": [item.to_dict() for item in state.messages],
                "error": type(error).__name__,
                "tool_results": list(all_tool_results),
                "usage": dict(state.usage),
            }
            if (
                isinstance(error_code, str)
                and re.fullmatch(r"[a-z0-9_]{1,64}", error_code)
            ):
                failure_data["error_code"] = error_code
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                data=failure_data,
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        finally:
            state.historical_turn_id = ""
            state.historical_requests = ()
            with session_lock:
                with self._session_guard:
                    state.is_running = False
                    key = self._session_key(
                        request.session_id,
                        request.user_id,
                        request.tenant_id,
                    )
                    if self._abort_events.get(key) is abort_event:
                        self._abort_events.pop(key, None)
            with self._event_guard:
                self._event_sequences.pop(str(request.run_id or ""), None)
            self._notify_model_run_cleanup(request, state)
            self._notify_context_cleanup(request, state)
            self._run_model_snapshot.reset(model_snapshot_token)
            discovery.close()
            active_tool_discovery.reset(discovery_token)

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
