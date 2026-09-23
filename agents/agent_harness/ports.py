"""Application ports required by the reusable Agent Harness."""

from __future__ import annotations

import threading
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from .runtime_kernel import RuntimeSessionBusyError, TurnRequest


class SessionLockProvider(Protocol):
    """Provide the one in-process lock used by the stateful Agent loop."""

    def __call__(self, request: TurnRequest) -> Any:
        ...


@dataclass(frozen=True)
class RuntimePorts:
    """Infrastructure callbacks kept outside the generic Runtime object."""

    session_manager: Any
    session_locks: dict[str, threading.RLock]
    session_locks_guard: threading.RLock
    lease_owner: str
    lease_seconds: float
    mode_context: ContextVar[Optional[str]]
    validate_mode: Callable[[str], str]
    resolve_mode: Callable[[str, str, Optional[str]], str]
    assert_ready: Callable[[], None]
    ensure_session: Callable[[TurnRequest], Any]
    refresh_session: Optional[Callable[[TurnRequest], Any]] = None
    session_lock_provider: Optional[SessionLockProvider] = None
    busy_error: type[Exception] = RuntimeSessionBusyError

    def __post_init__(self) -> None:
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if not callable(self.validate_mode):
            raise TypeError("validate_mode must be callable")
        if not callable(self.resolve_mode):
            raise TypeError("resolve_mode must be callable")
        if not callable(self.assert_ready):
            raise TypeError("assert_ready must be callable")
        if not callable(self.ensure_session):
            raise TypeError("ensure_session must be callable")
        if (
            self.session_lock_provider is not None
            and not callable(self.session_lock_provider)
        ):
            raise TypeError("session_lock_provider must be callable")
