"""Application-neutral Run Kernel for one Agent turn."""

from __future__ import annotations

import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping, Optional, Protocol


SUPPORTED_EXECUTION_MODES = frozenset({"dry_run", "live"})


def validate_execution_mode(
    value: Optional[str], *, default: str = "dry_run",
) -> str:
    """Normalize the provider-neutral execution mode vocabulary."""
    mode = str(value or default).strip().lower()
    if mode not in SUPPORTED_EXECUTION_MODES:
        raise ValueError(f"unsupported execution mode: {value}")
    return mode


class RuntimeSessionBusyError(RuntimeError):
    """Another Runtime instance currently owns the mutable session lease."""


class RuntimeSessionLeaseLostError(RuntimeError):
    """The durable owner lease was lost while a turn was running."""


class _AnyEvent:
    """Read-only event view that is set when any source event is set."""

    def __init__(self, *events: Optional[threading.Event]) -> None:
        self._events = tuple(event for event in events if event is not None)

    def is_set(self) -> bool:
        return any(event.is_set() for event in self._events)

    def wait(self, timeout: Optional[float] = None) -> bool:
        if self.is_set():
            return True
        if timeout is None:
            while not self.is_set():
                time.sleep(0.01)
            return True
        deadline = time.monotonic() + max(0.0, float(timeout))
        while not self.is_set() and time.monotonic() < deadline:
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        return self.is_set()


class SessionLeaseStore(Protocol):
    def acquire_session_lease(
        self, session_id: str, owner: str, lease_seconds: float,
    ) -> bool: ...

    def heartbeat_session_lease(
        self, session_id: str, owner: str, lease_seconds: float,
    ) -> bool: ...

    def release_session_lease(self, session_id: str, owner: str) -> bool: ...


@dataclass(frozen=True)
class TurnRequest:
    """Opaque request envelope passed from an application boundary."""

    user_input: str
    session_id: Optional[str] = None
    user_id: str = "anonymous"
    tenant_id: str = "default"
    context: Mapping[str, Any] = field(default_factory=dict)
    principal: Any = None
    cancellation_event: Optional[threading.Event] = None
    lease_lost_event: Optional[threading.Event] = None
    event_callback: Optional[Callable[[dict[str, Any]], None]] = None
    execution_mode: Optional[str] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    turn_id: Optional[str] = None
    streaming: bool = False

    def with_effective_identity(
        self, *, session_id: str, user_id: str, tenant_id: str,
    ) -> "TurnRequest":
        return replace(
            self,
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )


class SessionLease:
    """Cross-instance lease adapter with bounded heartbeat lifecycle."""

    def __init__(
        self,
        store: Optional[SessionLeaseStore],
        session_id: str,
        owner: str,
        lease_seconds: float,
        *,
        busy_error: type[Exception] = RuntimeSessionBusyError,
    ) -> None:
        self.store = store
        self.session_id = str(session_id)
        self.owner = str(owner)
        self.lease_seconds = float(lease_seconds)
        self.busy_error = busy_error
        self._acquired = False
        self._lost = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self) -> "SessionLease":
        acquire = getattr(self.store, "acquire_session_lease", None)
        release = getattr(self.store, "release_session_lease", None)
        if not callable(acquire) or not callable(release):
            return self
        if not acquire(self.session_id, self.owner, self.lease_seconds):
            raise self.busy_error(
                "session is busy on another Agent instance; retry shortly"
            )
        self._acquired = True
        heartbeat = getattr(self.store, "heartbeat_session_lease", None)
        if callable(heartbeat):
            self._thread = threading.Thread(
                target=self._heartbeat,
                name="agent-session-heartbeat",
                daemon=True,
            )
            self._thread.start()
        return self

    def _heartbeat(self) -> None:
        interval = min(max(self.lease_seconds / 3.0, 1.0), 10.0)
        heartbeat = getattr(self.store, "heartbeat_session_lease", None)
        while not self._stop.wait(interval):
            try:
                if not heartbeat(
                    self.session_id, self.owner, self.lease_seconds
                ):
                    self._lost.set()
                    return
            except Exception:
                self._lost.set()
                return

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    @property
    def lost_event(self) -> threading.Event:
        return self._lost

    def assert_owned(self) -> None:
        if self.lost:
            raise RuntimeSessionLeaseLostError(
                "durable session lease was lost while the turn was running"
            )

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.2)
        release_error: Optional[Exception] = None
        if self._acquired:
            release = getattr(self.store, "release_session_lease", None)
            if callable(release):
                try:
                    released = release(self.session_id, self.owner)
                    if released is False:
                        raise RuntimeError("session lease release rejected")
                except Exception as error:
                    if _exc is not None and hasattr(_exc, "add_note"):
                        _exc.add_note(
                            "session lease release failed: "
                            f"{type(error).__name__}"
                        )
                    elif _exc is None:
                        release_error = error
        self._thread = None
        self._acquired = False
        if release_error is not None:
            raise release_error


class AgentRuntimeKernel:
    """Reusable transport, identity and concurrency shell."""

    def __init__(
        self,
        *,
        session_manager: Optional[SessionLeaseStore],
        session_locks: dict[str, threading.RLock],
        session_locks_guard: threading.RLock,
        lease_owner: str,
        lease_seconds: float,
        mode_context: ContextVar[Optional[str]],
        validate_mode: Callable[[str], str],
        resolve_mode: Callable[[str, str, Optional[str]], str],
        assert_ready: Callable[[], None],
        ensure_session: Callable[[TurnRequest], Any],
        refresh_session: Optional[Callable[[TurnRequest], Any]] = None,
        execute_unlocked: Callable[[TurnRequest], Any],
        busy_error: type[Exception] = RuntimeSessionBusyError,
    ) -> None:
        self.session_manager = session_manager
        self.session_locks = session_locks
        self.session_locks_guard = session_locks_guard
        self.lease_owner = str(lease_owner)
        self.lease_seconds = float(lease_seconds)
        self.mode_context = mode_context
        self.validate_mode = validate_mode
        self.resolve_mode = resolve_mode
        self.assert_ready = assert_ready
        self.ensure_session = ensure_session
        self.refresh_session = refresh_session
        self.execute_unlocked = execute_unlocked
        self.busy_error = busy_error
        self._session_lock_refs: dict[str, int] = {}

    def _get_session_lock(self, session_id: str) -> threading.RLock:
        with self.session_locks_guard:
            key = str(session_id)
            lock = self.session_locks.setdefault(key, threading.RLock())
            self._session_lock_refs[key] = self._session_lock_refs.get(key, 0) + 1
            return lock

    def _release_session_lock(
        self, session_id: str, lock: threading.RLock,
    ) -> None:
        key = str(session_id)
        with self.session_locks_guard:
            refs = self._session_lock_refs.get(key, 0) - 1
            if refs > 0:
                self._session_lock_refs[key] = refs
                return
            self._session_lock_refs.pop(key, None)
            if self.session_locks.get(key) is lock:
                self.session_locks.pop(key, None)

    @staticmethod
    def _identity(request: TurnRequest) -> tuple[str, str]:
        principal = request.principal
        user_id = str(
            getattr(principal, "user_id", None) or request.user_id or "anonymous"
        )
        tenant_id = str(
            getattr(principal, "tenant_id", None)
            or request.tenant_id
            or "default"
        )
        return user_id, tenant_id

    def run(self, request: TurnRequest) -> Any:
        self.assert_ready()
        request = replace(
            request,
            run_id=str(request.run_id or uuid.uuid4()),
            turn_id=str(request.turn_id or uuid.uuid4()),
        )
        user_id, tenant_id = self._identity(request)
        requested_mode = (
            self.validate_mode(request.execution_mode)
            if request.execution_mode is not None
            else self.resolve_mode(tenant_id, user_id, None)
        )
        token = self.mode_context.set(requested_mode)
        try:
            request = replace(request, execution_mode=requested_mode)
            session_id = str(request.session_id or uuid.uuid4())
            lock = self._get_session_lock(session_id)
            try:
                with lock:
                    normalized = request.with_effective_identity(
                        session_id=session_id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                    )
                    self.ensure_session(normalized)
                    with SessionLease(
                        self.session_manager,
                        session_id,
                        self.lease_owner,
                        self.lease_seconds,
                        busy_error=self.busy_error,
                    ) as lease:
                        if self.refresh_session is not None:
                            self.refresh_session(normalized)
                        normalized = replace(
                            normalized,
                            lease_lost_event=_AnyEvent(
                                normalized.lease_lost_event,
                                lease.lost_event,
                            ),
                        )
                        lease.assert_owned()
                        result = self.execute_unlocked(normalized)
                        if lease.lost:
                            signals = {"session_lease_lost": True}
                            if isinstance(result, dict):
                                result = dict(result)
                                result["recovery_required"] = True
                                result["runtime_signals"] = {
                                    **dict(result.get("runtime_signals") or {}),
                                    **signals,
                                }
                            else:
                                try:
                                    from .results import RunResult, RunStatus

                                    if isinstance(result, RunResult):
                                        result = replace(
                                            result,
                                            status=RunStatus.RECOVERY_REQUIRED,
                                            recovery_required=True,
                                            runtime_signals={
                                                **dict(result.runtime_signals),
                                                **signals,
                                            },
                                        )
                                    else:
                                        result = {
                                            "value": result,
                                            "recovery_required": True,
                                            "runtime_signals": signals,
                                        }
                                except (ImportError, TypeError):
                                    result = {
                                        "value": result,
                                        "recovery_required": True,
                                        "runtime_signals": signals,
                                    }
                        return result
            finally:
                self._release_session_lock(session_id, lock)
        finally:
            self.mode_context.reset(token)


__all__ = [
    "AgentRuntimeKernel",
    "RuntimeSessionBusyError",
    "RuntimeSessionLeaseLostError",
    "SessionLeaseStore",
    "SessionLease",
    "SUPPORTED_EXECUTION_MODES",
    "TurnRequest",
    "validate_execution_mode",
]
