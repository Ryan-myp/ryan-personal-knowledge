"""Generic six-layer Agent Platform contracts and composition entry point.

The package is intentionally business-neutral.  It composes the reusable
Agent Harness, while product applications contribute their own definitions,
Skills, Tools, data adapters and integrations.
"""

__version__ = "0.1.0"

from .architecture import PlatformArchitecture, PlatformLayer
from .definitions import AgentDefinition, ScenarioDefinition
from .platform import AgentPlatform
from .runtime import (
    DataLayer,
    InfrastructureLayer,
    IntegrationLayer,
    PlatformApplication,
    PlatformDependencies,
)

__all__ = [
    "AgentDefinition",
    "AgentPlatform",
    "DataLayer",
    "InfrastructureLayer",
    "IntegrationLayer",
    "PlatformArchitecture",
    "PlatformApplication",
    "PlatformDependencies",
    "PlatformLayer",
    "ScenarioDefinition",
    "__version__",
]
