"""Bounded transcripts and scope-checked durable checkpoints for one Agent."""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping, Optional, Sequence, TYPE_CHECKING

from .messages import AgentMessage
from .persistence import TranscriptStore
from .redaction import redact_for_persistence
from .runtime_kernel import TurnRequest

if TYPE_CHECKING:
    from .agent import AgentState


class TranscriptPersistenceError(RuntimeError):
    """The durable transcript could not be read or changed safely."""


class AgentStatePersistence:
    def __init__(
        self,
        *,
        transcript_store: Optional[TranscriptStore],
        checkpoint_store: Any,
        system_messages: Sequence[AgentMessage],
        max_messages: int,
        max_chars: int,
        emit: Callable[..., None],
    ) -> None:
        self.transcript_store = transcript_store
        self.checkpoint_store = checkpoint_store
        self._system_messages = tuple(system_messages)
        self.max_transcript_messages = max_messages
        self.max_transcript_chars = max_chars
        self._emit = emit

    @staticmethod
    def _store_operation(
        operation: Callable[..., Any], error_message: str, *args: Any, **kwargs: Any
    ) -> Any:
        try:
            return operation(*args, **kwargs)
        except Exception as error:
            raise TranscriptPersistenceError(error_message) from error

    def _restore_messages(self, state: AgentState, payloads: Sequence[Any]) -> None:
        state.messages = list(self._system_messages)
        for payload in payloads:
            message = self.message_from_payload(payload)
            if message is not None and message.role != "system":
                self.append_message(state, message, persist=False)

    @staticmethod
    def message_from_payload(value: Any) -> Optional[AgentMessage]:
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

    def hydrate(
        self,
        request: TurnRequest,
        state: AgentState,
    ) -> None:
        if state.hydrated:
            return
        if self.transcript_store is not None and request.session_id:
            loaded = self._store_operation(
                self.transcript_store.load,
                "transcript load failed",
                str(request.session_id),
                tenant_id=str(request.tenant_id or "default"),
                user_id=str(request.user_id or "anonymous"),
                limit=self.max_transcript_messages,
            )
            self._restore_messages(state, loaded)
        state.hydrated = True

    def append_message(
        self,
        state: AgentState,
        message: AgentMessage,
        *,
        request: Optional[TurnRequest] = None,
        persist: bool = True,
    ) -> None:
        """Keep durable transcript state bounded while retaining system context."""
        state.messages.append(message)
        system_messages = [item for item in state.messages if item.role == "system"]
        non_system = [item for item in state.messages if item.role != "system"]
        keep_from = max(
            0,
            len(system_messages) + len(non_system) - self.max_transcript_messages,
        )
        total_chars = sum(
            len(str(item.content)) for item in system_messages + non_system[keep_from:]
        )
        while total_chars > self.max_transcript_chars and keep_from < len(non_system):
            total_chars -= len(str(non_system[keep_from].content))
            keep_from += 1
        state.messages = system_messages + non_system[keep_from:]
        if (
            persist
            and request is not None
            and self.transcript_store is not None
            and request.session_id
        ):
            safe_message = self.message_from_payload(
                redact_for_persistence(message.to_dict()),
            )
            if safe_message is None:
                raise RuntimeError("transcript message could not be serialized")
            self._store_operation(
                self.transcript_store.append,
                "transcript append failed",
                str(request.session_id),
                [safe_message],
                tenant_id=str(request.tenant_id or "default"),
                user_id=str(request.user_id or "anonymous"),
            )

    def save_checkpoint(
        self,
        request: TurnRequest,
        state: AgentState,
        *,
        turn_index: int,
        tool_results: Sequence[Mapping[str, Any]],
    ) -> bool:
        save = getattr(self.checkpoint_store, "save_checkpoint", None)
        if not callable(save):
            return True
        try:
            self._store_operation(
                save,
                "checkpoint save failed",
                str(request.run_id or ""),
                {
                    "run_id": str(request.run_id or ""),
                    "turn_id": str(request.turn_id or ""),
                    "session_id": str(request.session_id or ""),
                    "tenant_id": str(request.tenant_id or "default"),
                    "user_id": str(request.user_id or "anonymous"),
                    "turn_index": int(turn_index),
                    "messages": [
                        redact_for_persistence(item.to_dict())
                        for item in state.messages
                    ],
                    "tool_results": redact_for_persistence(
                        [dict(item) for item in tool_results],
                    ),
                    "usage": dict(state.usage),
                    "saved_at": time.time(),
                },
            )
            self._emit(
                "checkpoint_saved",
                request,
                turn_index=int(turn_index),
            )
            return True
        except TranscriptPersistenceError as error:
            self._emit(
                "checkpoint_error",
                request,
                error_type=type(error.__cause__).__name__,
            )
            return False

    def clear_checkpoint(self, request: TurnRequest) -> None:
        self.clear_checkpoint_id(str(request.run_id or ""), request)

    def clear_checkpoint_id(
        self,
        checkpoint_id: str,
        request: TurnRequest,
    ) -> None:
        clear = getattr(self.checkpoint_store, "clear_checkpoint", None)
        if not callable(clear):
            return
        try:
            self._store_operation(
                clear, "checkpoint clear failed", str(checkpoint_id or "")
            )
            self._emit("checkpoint_cleared", request)
        except TranscriptPersistenceError as error:
            self._emit(
                "checkpoint_error",
                request,
                phase="clear",
                error_type=type(error.__cause__).__name__,
            )

    def restore_checkpoint(
        self,
        request: TurnRequest,
        state: AgentState,
    ) -> str | None:
        context = request.context
        if not isinstance(context, Mapping) or not context.get(
            "resume_from_checkpoint"
        ):
            return None
        checkpoint_id = str(
            context.get("resume_run_id") or request.run_id or ""
        ).strip()
        load = getattr(self.checkpoint_store, "load_checkpoint", None)
        if not checkpoint_id or not callable(load):
            raise TranscriptPersistenceError("checkpoint restoration is not available")
        try:
            checkpoint = self._store_operation(
                load, "checkpoint load failed", checkpoint_id
            )
        except TranscriptPersistenceError as error:
            self._emit(
                "checkpoint_error",
                request,
                phase="load",
                error_type=type(error.__cause__).__name__,
            )
            raise
        if not isinstance(checkpoint, Mapping):
            raise TranscriptPersistenceError("checkpoint is missing or invalid")
        self._validate_checkpoint_scope(checkpoint, request)
        self._restore_messages(state, checkpoint.get("messages") or ())
        saved_usage = checkpoint.get("usage")
        if isinstance(saved_usage, Mapping):
            state.usage = {
                str(key): max(0, int(value))
                for key, value in saved_usage.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
        self._emit(
            "checkpoint_resumed",
            request,
            source_run_id=checkpoint_id,
            turn_index=checkpoint.get("turn_index"),
        )
        return checkpoint_id

    @staticmethod
    def _validate_checkpoint_scope(
        checkpoint: Mapping[str, Any], request: TurnRequest
    ) -> None:
        expected_scope = {
            "tenant_id": str(request.tenant_id or "default"),
            "user_id": str(request.user_id or "anonymous"),
            "session_id": str(request.session_id or ""),
        }
        if any(
            str(checkpoint.get(field, "")) != value
            for field, value in expected_scope.items()
        ):
            raise PermissionError("checkpoint scope does not match the current request")
