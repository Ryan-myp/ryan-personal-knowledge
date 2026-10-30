"""Bounded transcripts and scope-checked durable checkpoints for one Agent."""

from __future__ import annotations

from dataclasses import replace
import math
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
        if not isinstance(payloads, Sequence) or isinstance(payloads, (str, bytes, bytearray)):
            raise TranscriptPersistenceError("transcript messages must be a list")
        messages = list(self._system_messages)
        for payload in payloads:
            message = self.message_from_payload(payload)
            if message is None:
                raise TranscriptPersistenceError("transcript contains an invalid message")
            if message.role != "system":
                messages.append(message)
        staged = replace(state, messages=messages)
        self._trim_completed_turns(staged)
        state.messages = staged.messages

    @staticmethod
    def message_from_payload(value: Any) -> Optional[AgentMessage]:
        if isinstance(value, AgentMessage):
            value = vars(value)
        if not isinstance(value, Mapping):
            return None
        role = str(value.get("role") or "user")
        if role not in {"system", "user", "assistant", "tool"}:
            return None
        metadata = value.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TranscriptPersistenceError("transcript message metadata must be an object")
        timestamp = AgentStatePersistence._message_timestamp(value.get("timestamp"))
        return AgentMessage(
            role=role,
            content=value.get("content", ""),
            message_id=str(value.get("message_id") or ""),
            run_id=str(value.get("run_id") or ""),
            turn_id=str(value.get("turn_id") or ""),
            tool_call_id=value.get("tool_call_id"),
            name=value.get("name"),
            metadata=dict(metadata or {}),
            timestamp=timestamp,
        )

    @staticmethod
    def _message_timestamp(value: Any) -> float:
        if value is None:
            return time.time()
        try:
            timestamp = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise TranscriptPersistenceError("transcript timestamp is invalid") from error
        if isinstance(value, bool) or not math.isfinite(timestamp) or timestamp < 0:
            raise TranscriptPersistenceError("transcript timestamp must be finite and non-negative")
        return timestamp

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

    def load_user_history(self, request: TurnRequest) -> tuple[AgentMessage, ...]:
        loader = getattr(self.transcript_store, "load_user_history", None)
        if not callable(loader) or not request.session_id:
            return ()
        try:
            loaded = self._store_operation(
                loader, "user history load failed", str(request.session_id),
                tenant_id=str(request.tenant_id or "default"),
                user_id=str(request.user_id or "anonymous"),
                limit=128,
            )
            messages = tuple(
                message for value in loaded[:128]
                if (message := self.message_from_payload(value)) is not None
                and message.role == "user"
                and message.turn_id != request.turn_id
            )
            self._emit("conversation_recall_loaded", request, count=len(messages))
            return messages
        except Exception as error:
            self._emit(
                "conversation_recall_error", request,
                error_type=type(error.__cause__ or error).__name__,
            )
            return ()

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
        self._trim_completed_turns(state)
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

    def over_budget(self, messages: Sequence[AgentMessage]) -> bool:
        return len(messages) > self.max_transcript_messages or sum(
            len(str(item.content)) for item in messages
        ) > self.max_transcript_chars

    def _trim_completed_turns(self, state: AgentState) -> None:
        system = [item for item in state.messages if item.role == "system"]
        history = [item for item in state.messages if item.role != "system"]
        starts = [index for index, item in enumerate(history) if item.role == "user"]
        keep_from = starts[0] if starts else len(history)
        total_chars = sum(len(str(item.content)) for item in [*system, *history[keep_from:]])
        for next_start in starts[1:]:
            if len(system) + len(history) - keep_from <= self.max_transcript_messages and (
                total_chars <= self.max_transcript_chars
            ):
                break
            total_chars -= sum(len(str(item.content)) for item in history[keep_from:next_start])
            keep_from = next_start
        # Keep an oversized current group intact until the next model admission
        # check. The whole executed batch must reach durable storage first;
        # dropping its user message would lose the goal and orphan Tool calls.
        state.messages = system + history[keep_from:]

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
            saved = self._store_operation(
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
            if saved is False:
                raise TranscriptPersistenceError("checkpoint save was not accepted")
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
                error_type=type(error.__cause__ or error).__name__,
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
        saved_usage = self._checkpoint_usage(checkpoint.get("usage", state.usage))
        self._restore_messages(state, checkpoint.get("messages", ()))
        state.usage = saved_usage
        self._emit(
            "checkpoint_resumed",
            request,
            source_run_id=checkpoint_id,
            turn_index=checkpoint.get("turn_index"),
        )
        return checkpoint_id

    @staticmethod
    def _checkpoint_usage(value: Any) -> dict[str, int]:
        if not isinstance(value, Mapping):
            raise TranscriptPersistenceError("checkpoint usage must be an object")
        if any(isinstance(item, float) and not math.isfinite(item) for item in value.values()):
            raise TranscriptPersistenceError("checkpoint usage must be finite")
        return {
            str(key): max(0, int(item)) for key, item in value.items()
            if isinstance(item, (int, float)) and not isinstance(item, bool)
        }

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
