"""Capability configuration context."""

from __future__ import annotations

from typing import Any

from ..core.interfaces import ToolRegistry


class CapabilityContextWrapper:
    """Small adapter passed to Capability.configure()."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.config: dict[str, Any] = {}
