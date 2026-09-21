"""The stable layer vocabulary for the Agent Platform."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlatformLayer(str, Enum):
    """The six primary layers shown by the platform architecture."""

    APPLICATION_SCENARIOS = "application_scenarios"
    AGENTS = "agents"
    CORE = "core"
    DATA = "data"
    INTEGRATIONS = "integrations"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class PlatformArchitecture:
    """Declarative architecture metadata used by docs, catalogs and tooling."""

    layers: tuple[PlatformLayer, ...] = tuple(PlatformLayer)
    cross_cutting: tuple[str, ...] = (
        "agent_market",
        "governance_operations",
        "security",
        "observability",
    )

    def __post_init__(self) -> None:
        if self.layers != tuple(PlatformLayer):
            raise ValueError("the platform must expose the standard six layers")
        if len(set(self.cross_cutting)) != len(self.cross_cutting):
            raise ValueError("cross-cutting concerns must be unique")

    def layer_names(self) -> tuple[str, ...]:
        return tuple(layer.value for layer in self.layers)


__all__ = ["PlatformArchitecture", "PlatformLayer"]
