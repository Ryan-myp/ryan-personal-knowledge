"""Provider client binding and guarded Tool access for advertising."""

from __future__ import annotations

import copy
import logging
from typing import Any, Mapping, Optional

from agents.agent_harness.core.interfaces import ToolContext, ToolResult
from .provider_bindings import ProviderBindings

logger = logging.getLogger(__name__)


class AdProviderRuntimeServicesMixin:
    def set_credentials(self, credentials: dict) -> None:
        """Set in-process credentials without expanding account scope."""
        previous_platforms = {
            self._canonical_platform(str(platform))
            for platform in self._credentials
        }
        self._credentials = copy.deepcopy(credentials or {})
        self._refresh_provider_clients(
            previous_platforms,
            replace_bound_clients=True,
        )

    def _refresh_provider_clients(
        self,
        previous_platforms: set[str],
        *,
        replace_bound_clients: bool = False,
    ) -> None:
        """Replace bound clients after a credential rotation without a new Tool registry."""
        clients: dict[str, Any] = {}
        for tool_def in self.registry.list_all():
            try:
                _, handler = self._get_registered_tool(tool_def.name)
            except KeyError:
                continue
            if not hasattr(handler, "client"):
                continue
            if (
                not replace_bound_clients
                and getattr(handler, "client", None) is not None
            ):
                continue
            platform = self._canonical_platform(tool_def.namespace)
            if (
                platform not in previous_platforms
                and not self._credentials_for_platform(platform)
                and getattr(handler, "client", None) is None
            ):
                continue
            if platform not in clients:
                clients[platform] = (
                    self._get_api_client(platform)
                    if self._credentials_for_platform(platform)
                    else None
                )
            handler.client = clients[platform]

    def _get_api_client(self, platform: str):
        if not self._credentials:
            return None
        credentials = self._credentials_for_platform(platform)
        if not credentials:
            return None
        try:
            return self.provider_bindings.create_client(platform, credentials)
        except Exception as exc:
            logger.debug("创建 %s API Client 失败: %s", platform, exc)
            return None

    def _credentials_for_platform(
        self,
        platform: str,
        credentials: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        source = credentials if credentials is not None else self._credentials
        if not isinstance(source, Mapping):
            return {}
        wanted = self._resolve_platform_identifier(platform)
        for key, value in source.items():
            if (
                self._resolve_platform_identifier(str(key)) == wanted
                and isinstance(value, dict)
            ):
                return copy.deepcopy(value)
        return {}

    @staticmethod
    def _discover_tool_source(platform: str, api_client: Any = None) -> Any:
        return ProviderBindings.discover_tool_source(platform, api_client)

    def _build_request_clients(
        self, credentials: Optional[dict]
    ) -> dict[str, Any]:
        """Build request-scoped clients without mutating shared handlers."""
        if not credentials:
            return {}
        clients: dict[str, Any] = {}
        for raw_platform in credentials:
            platform = self._resolve_platform_identifier(str(raw_platform))
            provider_credentials = self._credentials_for_platform(platform, credentials)
            if not provider_credentials:
                continue
            try:
                client = self.provider_bindings.create_client(
                    platform, provider_credentials
                )
                if client is not None:
                    clients[platform] = client
            except Exception as exc:
                logger.warning("创建请求级 %s client 失败: %s", platform, exc)
        return clients

    def _execute_registered_tool(
        self, ctx: ToolContext, tool_name: str, input_data: dict
    ) -> ToolResult:
        execute = getattr(self.registry, "execute_authorized", None)
        if callable(execute):
            return execute(
                ctx, tool_name, input_data,
                _execution_token=self._registry_execution_token,
            )
        return self.registry.execute(ctx, tool_name, input_data)

    def _get_registered_tool(self, tool_name: str):
        getter = getattr(self.registry, "get_authorized", None)
        if callable(getter):
            return getter(tool_name, self._registry_execution_token)
        return self.registry.get(tool_name)


__all__ = ["AdProviderRuntimeServicesMixin"]
