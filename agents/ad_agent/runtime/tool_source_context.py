"""Tool Source configuration context."""

from __future__ import annotations

from typing import Any

from ..core.interfaces import ToolRegistry


class ToolSourceContextWrapper:
    """Small adapter passed to Tool Source configure()."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.config: dict[str, Any] = {}
