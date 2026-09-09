"""Business-neutral execution kernel for one Agent turn.

The kernel owns only transport and concurrency concerns:

* normalize the trusted principal/request context;
* serialize turns for one session inside a process;
* acquire and heartbeat a durable session lease across instances;
* install a request-scoped execution mode;
* delegate the actual turn to an application-provided executor.

It deliberately knows nothing about advertising, Providers, Skills, Tools,
campaigns, schedules, or UI.  An application Runtime composes this kernel
with its own turn executor and policy services.
"""

from __future__ import annotations

import threading
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Optional


class RuntimeSessionBusyError(RuntimeError):
    """Another Runtime instance currently owns the mutable session lease."""


@dataclass(frozen=True)
class TurnRequest:
    """Immutable input passed from an embedding boundary into the kernel."""

    user_input: str
    session_id: Optional[str] = None
    user_id: str = "anonymous"
    tenant_id: str = "default"
    account_id: Optional[str] = None
    credentials: Optional[Mapping[str, Any]] = None
    platform_params: Optional[Mapping[str, Any]] = None
    confirmed: bool = False
    confirmation_payload: Optional[Mapping[str, Any]] = None
    creation_blueprint_id: Optional[str] = None
    creation_blueprint_version: Optional[str] = None
    principal: Any = None
    cancellation_event: Optional[threading.Event] = None
    event_callback: Optional[Callable[[dict[str, Any]], None]] = None
    execution_mode: Optional[str] = None
    task_id: Optional[str] = None

    def with_effective_identity(
        self, *, session_id: str, user_id: str, tenant_id: str,
    ) -> "TurnRequest":
        """Return the request after trusted identity/session normalization."""
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
        store: Any,
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
                    return
            except Exception:
                # The durable owner remains authoritative. A failed heartbeat
                # must not make the application believe it still owns a lease.
                return

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.2)
        if self._acquired:
            release = getattr(self.store, "release_session_lease", None)
            if callable(release):
                release(self.session_id, self.owner)
        self._thread = None
        self._acquired = False


class AgentRuntimeKernel:
    """Reusable, application-neutral shell around a turn executor."""

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
        ensure_session: Callable[..., Any],
        execute_unlocked: Callable[[TurnRequest], dict[str, Any]],
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
        self.execute_unlocked = execute_unlocked
        self.busy_error = busy_error

    def _get_session_lock(self, session_id: str) -> threading.RLock:
        with self.session_locks_guard:
            return self.session_locks.setdefault(str(session_id), threading.RLock())

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

    def run(self, request: TurnRequest) -> dict[str, Any]:
        """Run one request while enforcing generic session concurrency rules."""
        self.assert_ready()
        user_id, tenant_id = self._identity(request)
        requested_mode = (
            self.validate_mode(request.execution_mode)
            if request.execution_mode is not None
            else self.resolve_mode(tenant_id, user_id, None)
        )
        token = self.mode_context.set(requested_mode)
        try:
            requested_session = str(request.session_id or "__new_session__")
            lock = self._get_session_lock(requested_session)
            with lock:
                session_id = request.session_id or self._new_session_id()
                self.ensure_session(
                    session_id,
                    user_id,
                    request.account_id,
                    request.credentials,
                    tenant_id=tenant_id,
                )
                normalized = request.with_effective_identity(
                    session_id=session_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
                with SessionLease(
                    self.session_manager,
                    session_id,
                    self.lease_owner,
                    self.lease_seconds,
                    busy_error=self.busy_error,
                ):
                    return self.execute_unlocked(normalized)
        finally:
            self.mode_context.reset(token)

    @staticmethod
    def _new_session_id() -> str:
        # Kept behind a tiny method so an embedding can replace ID generation
        # in a subclass without changing the execution contract.
        import uuid

        return str(uuid.uuid4())


__all__ = [
    "AgentRuntimeKernel",
    "RuntimeSessionBusyError",
    "SessionLease",
    "TurnRequest",
]
