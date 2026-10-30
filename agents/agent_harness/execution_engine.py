"""Replaceable reasoning loops over a platform-owned, revocable Run session.

Engines are reviewed deployment code, never uploaded Skill code. Only the host
owns requests, executors, checkpoints and terminal RunResult construction.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextvars import copy_context
from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Generator, Mapping, Protocol, Sequence

from .core.plugins import PluginManifest, PluginRegistry
from .messages import ModelTurn, ToolCall
from .model_limits import ModelTimeoutError
from .redaction import redact_for_persistence
from .results import RunResult
from .tool_schema_projection import model_tool_payload


@dataclass(frozen=True)
class EngineSnapshot:
    """Bounded advisory input; contains no principal, executable or credentials."""
    messages: tuple[Mapping[str, Any], ...]
    tools: tuple[Mapping[str, Any], ...]
    input_media: tuple[Any, ...] = ()
    tool_choice: str | None = None


class ExecutionEngine(Protocol):
    manifest: PluginManifest

    def run(self, session: EngineSession) -> None:
        """Drive reasoning until finish() or a host-enforced terminal outcome."""
        ...


@dataclass
class EngineStep:
    """Private host continuation. Never supplied to an engine adapter."""
    prepare: Callable[[], EngineSnapshot]
    complete_native: Callable[[], ModelTurn]
    validate: Callable[[ModelTurn], None]
    emit_text: Callable[[str], None]
    check_interrupted: Callable[[], None]
    tool_results: Sequence[Mapping[str, Any]] = ()


class EngineStopped(RuntimeError):
    """The host stopped the Run; adapters must stop their SDK loop as well."""


class EngineProtocolError(RuntimeError):
    """An engine returned without a final answer or violated its contract."""


class EngineSession:
    """A serialized capability scoped to one Run, revoked when that Run ends."""

    def __init__(self, steps: Generator[EngineStep, ModelTurn, RunResult]) -> None:
        self._steps = steps
        self._context = copy_context()
        self._lock = threading.RLock()
        self._step: EngineStep | None = None
        self._snapshot: EngineSnapshot | None = None
        self._result: RunResult | None = None
        self._closed = False
        self._advance(lambda: next(self._steps))

    @property
    def done(self) -> bool:
        return self._result is not None

    def _active(self) -> EngineStep:
        if self._closed or self.done or self._step is None:
            raise EngineStopped("Run session is no longer active")
        return self._step

    def check_cancelled(self) -> None:
        # No lock here: a cancellation check must not wait for an in-flight Tool.
        self._active().check_interrupted()

    def snapshot(self) -> EngineSnapshot:
        with self._lock:
            step = self._active()
            step.check_interrupted()
            if self._snapshot is None:
                self._snapshot = self._context.run(step.prepare)
            return deepcopy(self._snapshot)

    def _advance(self, operation: Callable[[], EngineStep]) -> None:
        try:
            self._step = self._context.run(operation)
            self._snapshot = None
        except StopIteration as stopped:
            if not isinstance(stopped.value, RunResult):
                raise EngineProtocolError("host did not return RunResult")
            self._result = stopped.value
            self._step = None

    def _submit(self, turn: ModelTurn) -> list[dict[str, Any]]:
        with self._lock:
            step = self._active()
            self.snapshot()  # Refresh discovery/allowlist and bounded context first.
            self._context.run(step.validate, turn)
            self._advance(lambda: self._steps.send(deepcopy(turn)))
            if self.done:
                raise EngineStopped("host reached a terminal outcome")
            return deepcopy(list(self._active().tool_results))

    def call_tools(self, calls: Sequence[ToolCall]) -> list[dict[str, Any]]:
        if not calls or any(not isinstance(call, ToolCall) for call in calls):
            raise EngineProtocolError("call_tools requires non-empty ToolCall objects")
        return self._submit(ModelTurn(tool_calls=tuple(calls)))

    def finish(self, reply: str, *, usage: Mapping[str, Any] | None = None) -> None:
        if not isinstance(reply, str):
            raise EngineProtocolError("final reply must be text")
        try:
            self._submit(ModelTurn(content=reply, usage=dict(usage or {})))
        except EngineStopped:
            if not self.done:
                raise

    def emit_text(self, delta: str) -> None:
        """Publish answer text, not SDK-internal traces or hidden reasoning."""
        with self._lock:
            step = self._active()
            self.snapshot()
            self._context.run(step.emit_text, delta)

    def _native_turn(self) -> None:
        with self._lock:
            turn = self._context.run(self._active().complete_native)
            self._advance(lambda: self._steps.send(turn))

    def fail(self, error: Exception) -> None:
        with self._lock:
            if not self.done:
                self._advance(lambda: self._steps.throw(error))

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._context.run(self._steps.close)

    def result(self) -> RunResult:
        if self._result is None:
            raise EngineProtocolError("engine returned without finishing the Run")
        return self._result


class NativeExecutionEngine:
    manifest = PluginManifest(
        plugin_id="harness.native-engine", version="1.0.0", kinds=("engine",),
        trusted=True, executable=True, description="内置模型与工具决策循环",
    )

    def run(self, session: EngineSession) -> None:
        while not session.done:
            session._native_turn()


class _EngineLifecycle:
    def __init__(self, engine: ExecutionEngine) -> None:
        self.engine = engine

    def deactivate(self, registry: PluginRegistry) -> None:
        close = getattr(self.engine, "close", None)
        if callable(close):
            close()


def register_engine(engine: ExecutionEngine, registry: PluginRegistry) -> None:
    manifest = getattr(engine, "manifest", None)
    if not isinstance(manifest, PluginManifest):
        raise TypeError("engine must declare a PluginManifest")
    if not manifest.trusted or not manifest.executable or "engine" not in manifest.kinds:
        raise ValueError("engine must be a trusted executable engine plugin")
    if not callable(getattr(engine, "run", None)):
        raise TypeError("engine must expose run(session)")
    registry.register(manifest, contribution=engine, lifecycle=_EngineLifecycle(engine))
    registry.activate(manifest.plugin_id)


def snapshot_from_inputs(inputs: tuple[Any, Any, Any]) -> EngineSnapshot:
    messages, tools, request = inputs
    descriptions = []
    for definition in tools:
        payload = model_tool_payload(definition)["function"]
        descriptions.append({
            "name": payload["name"], "description": payload["description"],
            "input_schema": payload["parameters"],
        })
    return EngineSnapshot(
        messages=tuple(redact_for_persistence([message.to_dict() for message in messages])),
        tools=tuple(redact_for_persistence(descriptions)),
        input_media=tuple(request.input_media), tool_choice=request.initial_tool_choice,
    )


def _invoke_engine(engine: ExecutionEngine, session: EngineSession) -> None:
    try:
        engine.run(session)
    except EngineStopped:
        if not session.done:
            raise


def drive_engine(engine: ExecutionEngine, session: EngineSession) -> RunResult:
    """Native path; no additional model loop or Run lifecycle is introduced."""
    try:
        if not session.done:
            _invoke_engine(engine, session)
        if not session.done:
            session.fail(EngineProtocolError("engine returned without finish"))
    except Exception as error:
        # Plugin/provider exceptions vary. Re-enter the host error boundary so
        # it persists a safe failure and retains already completed Tool results.
        session.fail(error)
    finally:
        session.close()
    return session.result()


def drive_external_engine(
    engine: ExecutionEngine, session: EngineSession, *, timeout: float,
    cancellation: threading.Event, slots: threading.BoundedSemaphore,
) -> RunResult:
    """Bound SDK waits and revoke late callbacks without replaying any effects."""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-engine")
    acquired = slots.acquire(blocking=False)
    future = None
    try:
        if not acquired:
            raise EngineProtocolError("engine execution capacity exhausted")
        if session.done:
            return session.result()
        future = pool.submit(copy_context().run, _invoke_engine, engine, session)
        future.add_done_callback(lambda _future: slots.release())
        deadline = time.monotonic() + timeout
        while True:
            if not session.done:
                session.check_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ModelTimeoutError("engine execution timed out")
            try:
                future.result(timeout=min(0.1, remaining))
                break
            except FutureTimeout:
                if future.done():
                    raise
        if not session.done:
            raise EngineProtocolError("engine returned without finish")
    except Exception as error:
        # Revoke SDK callbacks before handing any unknown exception to the
        # host. Never retry the whole engine after a possibly completed effect.
        cancellation.set()
        session.fail(error)
    finally:
        if acquired and future is None:
            slots.release()
        session.close()
        pool.shutdown(wait=False, cancel_futures=True)
    return session.result()
