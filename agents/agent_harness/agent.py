"""Stateful, application-neutral Agent loop.

The loop owns transcript state, model turns, Tool preflight/execution and
event ordering. Applications inject a model adapter, Tool catalog and policy
hooks; the loop never knows a provider, channel or business workflow.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence

from .messages import AgentMessage, ModelTurn, ToolCall
from .results import RunResult, RunStatus
from .runtime_kernel import TurnRequest
from .tool_catalog import ToolCatalog


class ModelAdapter(Protocol):
    def complete(
        self,
        messages: Sequence[AgentMessage],
        tools: Sequence[Any],
        request: TurnRequest,
    ) -> Any:
        ...


@dataclass(frozen=True)
class ToolCallContext:
    request: TurnRequest
    assistant_message: AgentMessage
    tool_call: ToolCall
    state: "AgentState"


@dataclass
class AgentState:
    messages: list[AgentMessage] = field(default_factory=list)
    is_running: bool = False
    error_message: str | None = None

    def snapshot(self) -> list[AgentMessage]:
        return list(self.messages)


class Agent:
    """A reusable stateful model/tool loop similar to a small agent core."""

    def __init__(
        self,
        *,
        model: ModelAdapter | Callable[..., Any],
        tool_catalog: Optional[ToolCatalog] = None,
        system_prompt: str = "",
        max_turns: int = 12,
        tool_execution: str = "parallel",
        max_parallel_tools: int = 8,
        before_tool_call: Optional[Callable[[ToolCallContext], Any]] = None,
        after_tool_call: Optional[Callable[[ToolCallContext, Any], Any]] = None,
        should_stop_after_turn: Optional[Callable[[AgentState], bool]] = None,
        event_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        if max_turns <= 0:
            raise ValueError("max_turns must be positive")
        if tool_execution not in {"sequential", "parallel"}:
            raise ValueError("tool_execution must be sequential or parallel")
        if max_parallel_tools <= 0:
            raise ValueError("max_parallel_tools must be positive")
        self.model = model
        self.tool_catalog = tool_catalog
        self.max_turns = int(max_turns)
        self.tool_execution = tool_execution
        self.max_parallel_tools = int(max_parallel_tools)
        self.before_tool_call = before_tool_call
        self.after_tool_call = after_tool_call
        self.should_stop_after_turn = should_stop_after_turn
        self.event_callback = event_callback
        self.state = AgentState(
            messages=[AgentMessage.system(system_prompt)] if system_prompt else []
        )
        self._lock = threading.RLock()
        self._abort_event = threading.Event()
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._sequence = 0

    def reset(self) -> None:
        with self._lock:
            if self.state.is_running:
                raise RuntimeError("Agent is already running")
            system_messages = [
                item for item in self.state.messages if item.role == "system"
            ]
            self.state = AgentState(messages=system_messages)
            self._abort_event.clear()

    def subscribe(
        self, callback: Callable[[dict[str, Any]], None],
    ) -> Callable[[], None]:
        if not callable(callback):
            raise TypeError("Agent subscriber must be callable")
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe

    def abort(self) -> None:
        """Request cooperative cancellation at the next loop boundary."""
        self._abort_event.set()

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
            cancellation_event=self._abort_event,
        ))

    def _emit(self, event_type: str, request: TurnRequest, **payload: Any) -> None:
        self._sequence += 1
        event = {
            "type": event_type,
            "run_id": str(request.run_id or ""),
            "turn_id": str(request.turn_id or ""),
            "seq": self._sequence,
        }
        event.update(payload)
        callbacks = []
        for callback in (
            self.event_callback,
            request.event_callback,
            *self._subscribers,
        ):
            if callable(callback) and callback not in callbacks:
                callbacks.append(callback)
        for callback in callbacks:
            try:
                callback(event)
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
            )
        raise TypeError("model must return ModelTurn, mapping, or string")

    def _call_model(self, request: TurnRequest) -> ModelTurn:
        tools = self.tool_catalog.list_tools() if self.tool_catalog else []
        complete = getattr(self.model, "complete", None)
        if callable(complete):
            value = complete(self.state.snapshot(), tools, request)
        elif callable(self.model):
            value = self.model(self.state.snapshot(), tools, request)
        else:
            raise TypeError("model must be callable or expose complete()")
        return self._normalize_turn(value)

    def _execute_one(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        call: ToolCall,
    ) -> dict[str, Any]:
        context = ToolCallContext(
            request=request,
            assistant_message=assistant,
            tool_call=call,
            state=self.state,
        )
        if callable(self.before_tool_call):
            decision = self.before_tool_call(context)
            if isinstance(decision, Mapping) and decision.get("block"):
                result = {
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": str(decision.get("reason") or "tool call blocked"),
                    "is_error": True,
                    "terminate": bool(decision.get("terminate")),
                }
                return result
        try:
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
            result = {
                "tool_call_id": call.id,
                "name": call.name,
                "content": output,
                "is_error": False,
                "terminate": False,
            }
        except Exception as error:
            result = {
                "tool_call_id": call.id,
                "name": call.name,
                "content": str(error),
                "is_error": True,
                "terminate": False,
            }
        if callable(self.after_tool_call):
            override = self.after_tool_call(context, result)
            if isinstance(override, Mapping):
                result = {**result, **dict(override)}
        return result

    def _execute_tools(
        self,
        request: TurnRequest,
        assistant: AgentMessage,
        calls: Sequence[ToolCall],
    ) -> list[dict[str, Any]]:
        if self.tool_execution == "sequential" or len(calls) <= 1:
            return [
                self._execute_emitting(request, assistant, call)
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
                pool.submit(self._execute_one, request, assistant, call)
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
        self, request: TurnRequest, assistant: AgentMessage, call: ToolCall,
    ) -> dict[str, Any]:
        self._emit(
            "tool_execution_start",
            request,
            tool_call_id=call.id,
            tool_name=call.name,
            arguments=dict(call.arguments),
        )
        result = self._execute_one(request, assistant, call)
        self._emit_tool_end(request, call, result)
        return result

    def run(self, request: TurnRequest) -> RunResult:
        with self._lock:
            if self.state.is_running:
                raise RuntimeError("Agent is already running")
            self.state.is_running = True
            self.state.error_message = None
        try:
            self._sequence = 0
            self._emit("agent_start", request)
            self._emit("turn_start", request, turn_index=0)
            user_message = AgentMessage.user(
                request.user_input,
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
            )
            self.state.messages.append(user_message)
            self._emit("message_end", request, message=user_message.to_dict())
            tool_results: list[dict[str, Any]] = []
            last_reply = ""
            for turn_index in range(self.max_turns):
                cancelled = self._abort_event.is_set() or (
                    request.cancellation_event is not None
                    and request.cancellation_event.is_set()
                )
                if cancelled:
                    result = RunResult(
                        run_id=str(request.run_id or ""),
                        turn_id=str(request.turn_id or ""),
                        status=RunStatus.CANCELLED,
                        data={"messages": [item.to_dict() for item in self.state.messages]},
                    )
                    self._emit("agent_end", request, status=result.status.value)
                    return result
                if turn_index > 0:
                    self._emit("turn_start", request, turn_index=turn_index)
                tool_results = []
                model_turn = self._call_model(request)
                assistant = AgentMessage.assistant(
                    model_turn.content,
                    run_id=str(request.run_id or ""),
                    turn_id=str(request.turn_id or ""),
                    metadata={"stop_reason": model_turn.stop_reason},
                )
                self.state.messages.append(assistant)
                last_reply = str(model_turn.content or "")
                self._emit("message_end", request, message=assistant.to_dict())
                if model_turn.tool_calls:
                    tool_results = self._execute_tools(
                        request, assistant, model_turn.tool_calls,
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
                            },
                        )
                        self.state.messages.append(tool_message)
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
                    or (
                        callable(self.should_stop_after_turn)
                        and self.should_stop_after_turn(self.state)
                    )
                ):
                    result = RunResult(
                        run_id=str(request.run_id or ""),
                        turn_id=str(request.turn_id or ""),
                        status=RunStatus.SUCCEEDED,
                        reply=last_reply,
                        data={
                            "messages": [
                                item.to_dict() for item in self.state.messages
                            ],
                            "tool_results": tool_results,
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
                    "messages": [item.to_dict() for item in self.state.messages],
                    "tool_results": tool_results,
                    "error": "maximum agent turns exceeded",
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        except Exception as error:
            self.state.error_message = type(error).__name__
            result = RunResult(
                run_id=str(request.run_id or ""),
                turn_id=str(request.turn_id or ""),
                status=RunStatus.FAILED,
                data={
                    "messages": [item.to_dict() for item in self.state.messages],
                    "error": type(error).__name__,
                },
            )
            self._emit("agent_end", request, status=result.status.value)
            return result
        finally:
            self.state.is_running = False
            self._abort_event.clear()

    def execute(self, request: TurnRequest) -> RunResult:
        """TurnPipeline-compatible alias for embedding the Agent in Runtime."""
        return self.run(request)


__all__ = ["Agent", "AgentState", "ModelAdapter", "ToolCallContext"]
