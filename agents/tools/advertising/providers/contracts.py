"""Advertising Provider installation metadata, not a second Tool Source protocol.

The application uses these local contracts to configure accounts, blueprints
and client lifecycle. Executable contributions use Harness ToolBinding/ToolSource.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agents.agent_harness.core.interfaces import ToolRegistry, WriteGuard


class ProviderModule(ABC):
    @abstractmethod
    def configure(
        self, context: "ProviderInstallationContext"
    ) -> "ProviderInstallation":
        raise NotImplementedError


@dataclass
class ProviderInstallationContext:
    registry: ToolRegistry
    config: dict[str, Any] = field(default_factory=dict)
    session_store: Any = None


@dataclass
class ProviderInstallation:
    write_guard: WriteGuard | None = None
    background_tasks: list[dict] = field(default_factory=list)
    parameter_catalogs: list[Any] = field(default_factory=list)
