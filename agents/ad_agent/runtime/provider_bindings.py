"""Provider binding boundary used by the application composition root.

The Agent Core never imports a Provider client or a channel package. This
adapter is the only runtime-side seam allowed to resolve a platform-owned
Tool Source/client from a deployment registry. Replacing it is sufficient for
an embedding that discovers Tool Sources from a package, service registry or
dependency-injection container.
"""

from __future__ import annotations

from typing import Any


class ProviderBindings:
    """Late-bound provider factories kept outside AgentRuntime."""

    @staticmethod
    def normalize_namespace(namespace: str) -> str:
        from ..tools.providers.source_factory import normalize_namespace

        return normalize_namespace(namespace)

    @staticmethod
    def create_client(platform: str, credentials: dict[str, Any]) -> Any:
        from ..api_clients.factory import create_platform_client

        return create_platform_client(platform, credentials)

    @staticmethod
    def discover_tool_source(platform: str, api_client: Any = None) -> Any:
        from ..tools.providers.source_factory import discover_tool_source_factory

        factory = discover_tool_source_factory(platform)
        return factory(api_client) if callable(factory) else None

    @staticmethod
    def create_tool_source(platform: str, api_client: Any = None) -> Any:
        from ..tools.providers.source_factory import create_tool_source

        return create_tool_source(platform, api_client)


__all__ = ["ProviderBindings"]
