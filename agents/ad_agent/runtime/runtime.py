"""Public runtime entry points.

The reusable execution shell lives in :mod:`agents.ad_agent.core.runtime_kernel`.
Advertising composition is intentionally kept in :mod:`ad_runtime`; this module
is only the stable package boundary used by the HTTP/CLI adapters.
"""

from __future__ import annotations

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
# Generic embedders should depend on core.runtime_kernel.AgentRuntimeKernel.
AgentRuntime = AdAgentRuntime

__all__ = [
    "AgentRuntime",
    "AdAgentRuntime",
    "AccountWhitelistValidator",
    "SessionBusyError",
    "SessionContext",
]
