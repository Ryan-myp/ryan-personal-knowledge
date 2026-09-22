"""Small contracts shared by the advertising application boundary."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional


class SessionBusyError(RuntimeError):
    """Another application instance currently owns the mutable session lease."""


execution_mode_context: ContextVar[Optional[str]] = ContextVar(
    "ad_agent_execution_mode",
    default=None,
)


__all__ = ["SessionBusyError", "execution_mode_context"]
