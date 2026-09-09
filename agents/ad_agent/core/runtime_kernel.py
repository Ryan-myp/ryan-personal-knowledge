"""Business-neutral execution kernel for one Agent turn.

The kernel owns only transport and concurrency concerns:

* normalize the trusted principal/request context;
* serialize turns for one session inside a process;
* acquire and heartbeat a durable session lease across instances;
* install a request-scoped execution mode;
* delegate the actual turn to an application-provided executor.

It deliberately knows nothing about application domains, external systems, Skills,
Tools, workflows, or UI.  An application Runtime composes this kernel
with its own turn executor and policy services.
"""

from __future__ import annotations

import threading
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping, Optional, Protocol


class RuntimeSessionBusyError(RuntimeError):
    """Another Runtime instance currently owns the mutable session lease."""


class RuntimeSessionLeaseLostError(RuntimeError):
    """The durable owner lease was lost while a turn was running."""


class SessionLeaseStore(Protocol):
    """Minimal persistence port required by the generic kernel."""

    def acquire_session_lease(
        self, session_id: str, owner: str, lease_seconds: float,
    ) -> bool: ...

    def heartbeat_session_lease(
        self, session_id: str, owner: str, lease_seconds: float,
    ) -> bool: ...

    def release_session_lease(self, session_id: str, owner: str) -> bool: ...


@dataclass(frozen=True)
class TurnRequest:
    """Immutable input passed from an embedding boundary into the kernel.

    ``context`` is intentionally opaque to the kernel.  An embedding may put
    domain request data in it (for example tenant or integration parameters),
    but the generic execution shell must not name or interpret those fields.
    Keeping that envelope here also makes the boundary usable by a non-ad
    application without adding another Runtime-specific request type.
    """

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
                # The durable owner remains authoritative. A failed heartbeat
                # must not make the application believe it still owns a lease.
                # A transient backend error is not proof of lease loss, but the
                # heartbeat loop exits so the caller can fail closed at the
                # turn boundary instead of continuing indefinitely.
                self._lost.set()
                return

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    @property
    def lost_event(self) -> threading.Event:
        """Event exposed to the application executor for fail-closed handling."""
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
        if self._acquired:
            release = getattr(self.store, "release_session_lease", None)
            if callable(release):
                try:
                    release(self.session_id, self.owner)
                except Exception:
                    # The lease is bounded and will expire server-side. Never
                    # mask an application result with a best-effort cleanup
                    # failure (especially after an external side effect).
                    pass
        self._thread = None
        self._acquired = False


class AgentRuntimeKernel:
    """Reusable, application-neutral shell around a turn executor."""

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
        # The embedding owns the lock objects, while the kernel owns the
        # reference count used to retire locks that are no longer used. This
        # keeps a long-lived multi-tenant process from retaining one RLock per
        # conversation forever.
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
        """Drop an idle per-session lock without removing a replacement lock."""
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
            # Allocate an ID before locking. A fixed sentinel for all new
            # sessions accidentally serialized unrelated first turns.
            session_id = str(request.session_id or self._new_session_id())
            lock = self._get_session_lock(session_id)
            try:
                with lock:
                    normalized = request.with_effective_identity(
                        session_id=session_id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                    )
                    self.ensure_session(
                        normalized,
                    )
                    with SessionLease(
                        self.session_manager,
                        session_id,
                        self.lease_owner,
                        self.lease_seconds,
                        busy_error=self.busy_error,
                    ) as lease:
                        if self.refresh_session is not None:
                            # Re-load after the durable lease is acquired. This
                            # prevents a warm process-local cache from overwriting
                            # a newer session state committed by another instance.
                            self.refresh_session(
                                normalized,
                            )
                        normalized = replace(
                            normalized, lease_lost_event=lease.lost_event,
                        )
                        lease.assert_owned()
                        result = self.execute_unlocked(normalized)
                        # Never discard a completed application result merely
                        # because the lease was lost: the turn may already have
                        # produced an external side effect. Attach a generic
                        # signal so the application/task layer can surface it as
                        # uncertain and require reconciliation instead of retrying
                        # blindly.
                        if lease.lost and isinstance(result, dict):
                            result = dict(result)
                            signals = dict(result.get("runtime_signals") or {})
                            signals["session_lease_lost"] = True
                            result["runtime_signals"] = signals
                        return result
            finally:
                self._release_session_lock(session_id, lock)
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
    "RuntimeSessionLeaseLostError",
    "SessionLeaseStore",
    "SessionLease",
    "TurnRequest",
]
