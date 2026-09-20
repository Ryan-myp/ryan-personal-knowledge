"""Reusable Runtime facade over the business-neutral execution kernel."""

from __future__ import annotations

import threading
from contextvars import ContextVar
from typing import Any, Callable, Optional

from .runtime_kernel import (
    AgentRuntimeKernel,
    RuntimeSessionBusyError,
    TurnRequest,
)
from .interfaces import ToolDefinition, ToolRegistry
from .tool_sources import StaticToolSource, ToolBinding, ToolSource
from .turn_pipeline import TurnPipeline


class GenericAgentRuntime:
    """Embeddable Runtime shell for applications with their own TurnPipeline.

    The shell owns request/session lifecycle and delegates domain behavior to
    the injected pipeline. ``execute_turn`` remains only as a migration adapter
    for older embeddings. The shell intentionally exposes no application
    concepts, external clients, Skill loaders, or persistence details.
    """

    def __init__(
        self,
        *,
        session_manager: Any,
        session_locks: dict[str, threading.RLock],
        session_locks_guard: threading.RLock,
        lease_owner: str,
        lease_seconds: float,
        mode_context: ContextVar[Optional[str]],
        validate_mode: Callable[[str], str],
        resolve_mode: Callable[[str, str, Optional[str]], str],
        assert_ready: Callable[[], None],
        ensure_session: Callable[[TurnRequest], Any],
        execute_turn: Optional[Callable[[TurnRequest], Any]] = None,
        turn_pipeline: Optional[TurnPipeline] = None,
        tool_registry: Optional[ToolRegistry] = None,
        on_tool_catalog_changed: Optional[Callable[[], None]] = None,
        refresh_session: Optional[Callable[[TurnRequest], Any]] = None,
        busy_error: type[Exception] = RuntimeSessionBusyError,
    ) -> None:
        if execute_turn is not None and turn_pipeline is not None:
            raise ValueError("provide either execute_turn or turn_pipeline, not both")
        if execute_turn is None and turn_pipeline is None:
            raise ValueError("Generic Agent Runtime requires a turn pipeline")
        self._closed = False
        self.turn_pipeline = turn_pipeline
        self._executor = turn_pipeline or execute_turn
        self.tool_registry = tool_registry
        self._on_tool_catalog_changed = on_tool_catalog_changed
        self._kernel = AgentRuntimeKernel(
            session_manager=session_manager,
            session_locks=session_locks,
            session_locks_guard=session_locks_guard,
            lease_owner=lease_owner,
            lease_seconds=lease_seconds,
            mode_context=mode_context,
            validate_mode=validate_mode,
            resolve_mode=resolve_mode,
            assert_ready=assert_ready,
            ensure_session=ensure_session,
            refresh_session=refresh_session,
            execute_unlocked=self._execute_turn,
            busy_error=busy_error,
        )

    @property
    def closed(self) -> bool:
        return self._closed

    def run(self, request: TurnRequest) -> Any:
        if self._closed:
            raise RuntimeError("Agent Runtime is closed")
        return self._kernel.run(request)

    def _execute_turn(self, request: TurnRequest) -> Any:
        """Execute the injected generic pipeline after Kernel gates."""
        pipeline = self.turn_pipeline
        if pipeline is not None:
            return pipeline.execute(request)
        # ``execute_turn`` is retained as a source-compatible adapter for
        # existing applications while they migrate to TurnPipeline.
        if self._executor is None:
            raise RuntimeError("Generic Agent Runtime has no turn executor")
        return self._executor(request)

    def register_tool(
        self,
        definition: ToolDefinition,
        executor: Any,
        *,
        source_id: str = "local",
    ) -> None:
        """Register one Tool without requiring an application Capability."""
        if self.tool_registry is None:
            raise RuntimeError("Generic Agent Runtime has no Tool Registry")
        source = StaticToolSource(
            f"{source_id}:{definition.name}",
            [ToolBinding(definition, executor)],
        )
        self.tool_registry.register_source(source)
        callback = self._on_tool_catalog_changed
        if callable(callback):
            callback()

    def register_tool_source(self, source: ToolSource) -> list[str]:
        """Register a local/SDK/HTTP/MCP source through one generic seam."""
        if self.tool_registry is None:
            raise RuntimeError("Generic Agent Runtime has no Tool Registry")
        names = self.tool_registry.register_source(source)
        callback = self._on_tool_catalog_changed
        if callable(callback):
            callback()
        return names

    def unregister_tool_source(self, source_id: str) -> list[str]:
        """Unload all Tools published by one source."""
        if self.tool_registry is None:
            raise RuntimeError("Generic Agent Runtime has no Tool Registry")
        names = self.tool_registry.unregister_source(source_id)
        if names and callable(self._on_tool_catalog_changed):
            self._on_tool_catalog_changed()
        return names

    def list_tools(self) -> list[ToolDefinition]:
        """Return the current generic Tool catalog."""
        if self.tool_registry is None:
            return []
        return self.tool_registry.list_all()

    def close(self) -> None:
        """Close optional application-owned executor resources once."""
        if self._closed:
            return
        self._closed = True
        close = getattr(self._executor, "close", None)
        if callable(close):
            close()


__all__ = ["GenericAgentRuntime"]
