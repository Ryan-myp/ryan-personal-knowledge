"""Public application-neutral Agent Runtime facade."""

from __future__ import annotations

import threading
import uuid
from contextvars import ContextVar
from dataclasses import replace
from typing import Any, Optional

from .ports import RuntimePorts
from .results import RunResult
from .run_store import RunStore, run_start_payload
from .skills import SkillSource
from .runtime_kernel import (
    AgentRuntimeKernel,
    RuntimeSessionBusyError,
    TurnRequest,
)
from .tool_sources import StaticToolSource, ToolBinding, ToolSource
from .turn_pipeline import TurnPipeline


class AgentRuntime:
    """Run lifecycle plus Tool Source ownership for any application."""

    def __init__(
        self,
        *,
        ports: Optional[RuntimePorts] = None,
        pipeline: Optional[TurnPipeline] = None,
        agent: Any = None,
        tool_registry: Any = None,
        skill_catalog: Any = None,
        on_tool_catalog_changed: Optional[callable] = None,
        run_store: Optional[RunStore] = None,
        session_manager: Any = None,
        session_locks: Optional[dict[str, threading.RLock]] = None,
        session_locks_guard: Optional[threading.RLock] = None,
        lease_owner: str = "agent-runtime",
        lease_seconds: float = 300.0,
        mode_context: Optional[ContextVar[Optional[str]]] = None,
        validate_mode: Optional[callable] = None,
        resolve_mode: Optional[callable] = None,
        assert_ready: Optional[callable] = None,
        ensure_session: Optional[callable] = None,
        refresh_session: Optional[callable] = None,
        busy_error: type[Exception] = RuntimeSessionBusyError,
    ) -> None:
        if pipeline is not None and agent is not None:
            raise ValueError("provide either pipeline or agent, not both")
        pipeline = pipeline or agent
        if ports is None:
            if pipeline is None:
                raise TypeError("Agent Runtime requires ports and pipeline")
            ports = RuntimePorts(
                session_manager=session_manager,
                session_locks=session_locks or {},
                session_locks_guard=session_locks_guard or threading.RLock(),
                lease_owner=lease_owner,
                lease_seconds=lease_seconds,
                mode_context=mode_context or ContextVar(
                    "agent_harness_execution_mode", default=None,
                ),
                validate_mode=validate_mode or (lambda value: value or "dry_run"),
                resolve_mode=resolve_mode or (
                    lambda _tenant, _user, _requested: "dry_run"
                ),
                assert_ready=assert_ready or (lambda: None),
                ensure_session=ensure_session or (lambda _request: None),
                refresh_session=refresh_session,
                busy_error=busy_error,
            )
        if pipeline is None or not callable(getattr(pipeline, "execute", None)):
            raise TypeError("pipeline must expose execute(request)")
        self._closed = False
        self.pipeline = pipeline
        self.turn_pipeline = pipeline
        self._executor = pipeline
        self.tool_registry = tool_registry
        self.skill_catalog = skill_catalog
        self._on_tool_catalog_changed = on_tool_catalog_changed
        self.run_store = run_store
        self._kernel = AgentRuntimeKernel(
            session_manager=ports.session_manager,
            session_locks=ports.session_locks,
            session_locks_guard=ports.session_locks_guard,
            lease_owner=ports.lease_owner,
            lease_seconds=ports.lease_seconds,
            mode_context=ports.mode_context,
            validate_mode=ports.validate_mode,
            resolve_mode=ports.resolve_mode,
            assert_ready=ports.assert_ready,
            ensure_session=ports.ensure_session,
            refresh_session=ports.refresh_session,
            execute_unlocked=self._execute_pipeline,
            busy_error=ports.busy_error,
        )

    @property
    def closed(self) -> bool:
        return self._closed

    def run(self, request: TurnRequest) -> Any:
        if self._closed:
            raise RuntimeError("Agent Runtime is closed")
        request = replace(
            request,
            run_id=str(request.run_id or uuid.uuid4()),
            turn_id=str(request.turn_id or uuid.uuid4()),
        )
        result = self._kernel.run(request)
        if isinstance(result, dict):
            result = dict(result)
            result.setdefault("run_id", request.run_id)
            result.setdefault("turn_id", request.turn_id)
        return result

    def _execute_pipeline(self, request: TurnRequest) -> Any:
        store = self.run_store
        if store is None:
            return self.pipeline.execute(request)

        store.start_run(**run_start_payload(request))
        original_callback = request.event_callback

        def observe(event: dict[str, Any]) -> None:
            try:
                store.append_event(str(request.run_id), dict(event))
            except Exception:
                # Durable event repair is an implementation concern of the
                # bound RunStore. A transient observer failure must not turn
                # an already-running model/provider operation into a failure.
                pass
            if callable(original_callback):
                try:
                    original_callback(event)
                except Exception:
                    pass

        request = replace(request, event_callback=observe)
        try:
            result = self.pipeline.execute(request)
        except Exception as error:
            store.finish_run(
                str(request.run_id),
                status="failed",
                metadata={"error_type": type(error).__name__},
            )
            raise
        normalized = RunResult.from_payload(result)
        result_metadata = (
            dict(result.get("run_metadata") or {})
            if isinstance(result, dict)
            and isinstance(result.get("run_metadata"), dict)
            else {}
        )
        try:
            store.finish_run(
                str(request.run_id),
                status=normalized.status.value,
                metadata={
                    "effect_state": normalized.effect_state,
                    "recovery_required": normalized.recovery_required,
                    **result_metadata,
                },
            )
        except Exception:
            # The Run remains recoverable from its last durable event. Do not
            # replace a valid provider result with a persistence observer error.
            pass
        return result

    def register_tool(
        self, definition: Any, executor: Any, *, source_id: str = "local",
    ) -> None:
        if self.tool_registry is None:
            raise RuntimeError("Agent Runtime has no Tool Registry")
        name = (
            definition.get("name")
            if isinstance(definition, dict)
            else getattr(definition, "name", "tool")
        )
        self.register_tool_source(StaticToolSource(
            f"{source_id}:{name}",
            [ToolBinding(definition, executor)],
        ))

    def register_tool_source(self, source: ToolSource) -> list[str]:
        if self.tool_registry is None:
            raise RuntimeError("Agent Runtime has no Tool Registry")
        names = self.tool_registry.register_source(source)
        try:
            if callable(self._on_tool_catalog_changed):
                self._on_tool_catalog_changed()
        except Exception:
            # Registry mutation and parser/catalog refresh form one public
            # lifecycle operation. Roll back the source when the application
            # cannot publish its new catalog snapshot.
            unregister = getattr(self.tool_registry, "unregister_source", None)
            if callable(unregister):
                unregister(getattr(source, "source_id", ""))
            raise
        return names

    def unregister_tool_source(self, source_id: str) -> list[str]:
        if self.tool_registry is None:
            raise RuntimeError("Agent Runtime has no Tool Registry")
        names = self.tool_registry.unregister_source(source_id)
        if names and callable(self._on_tool_catalog_changed):
            self._on_tool_catalog_changed()
        return names

    def list_tools(self) -> list[Any]:
        if self.tool_registry is None:
            return []
        return self.tool_registry.list_all()

    def register_skill_source(self, source: SkillSource) -> list[str]:
        if self.skill_catalog is None:
            raise RuntimeError("Agent Runtime has no Skill Catalog")
        return self.skill_catalog.register_source(source)

    def unregister_skill_source(self, source_id: str) -> list[str]:
        if self.skill_catalog is None:
            raise RuntimeError("Agent Runtime has no Skill Catalog")
        unregister = getattr(self.skill_catalog, "unregister_source", None)
        if not callable(unregister):
            raise TypeError("Skill Catalog does not support source removal")
        return unregister(source_id)

    def list_skills(self) -> list[Any]:
        if self.skill_catalog is None:
            return []
        list_skills = getattr(self.skill_catalog, "list_skills", None)
        return list_skills() if callable(list_skills) else []

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._executor, "close", None)
        if callable(close):
            close()

__all__ = ["AgentRuntime"]
