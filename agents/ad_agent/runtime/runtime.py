"""Public runtime entry points.

 The reusable execution shell lives in :mod:`agents.agent_harness`.
Advertising composition is intentionally kept in :mod:`ad_runtime`; this module
is only the stable package boundary used by the HTTP/CLI adapters.
"""

from __future__ import annotations

from agents.agent_harness import AgentRuntime as GenericAgentRuntime
from .ad_runtime import (
    AdAgentRuntime,
    AccountWhitelistValidator,
    SessionBusyError,
    SessionContext,
    _EXECUTION_MODE_CACHE_MAX_ENTRIES,
    _EXECUTION_MODE_CACHE_TTL_SECONDS,
    time,
)

# The application package exposes AgentRuntime at its application boundary.
# Generic embedders should depend on agents.agent_harness.AgentRuntime.
AgentRuntime = AdAgentRuntime

__all__ = [
    "AgentRuntime",
    "AdAgentRuntime",
    "GenericAgentRuntime",
    "AccountWhitelistValidator",
    "SessionBusyError",
    "SessionContext",
]
