"""Public application API for the advertising composition."""

from __future__ import annotations

import threading
from typing import Any, Iterable, Optional

from ..core.execution_trace import ExecutionEventCallback
from ..core.interfaces import (
    ExecutionMode,
    ToolDefinition,
)
from ..core.memory import MemoryManager
from ..core.policy import RuntimePolicy
from ..domain.ad.auth import RequestPrincipal
from ..persistence.interfaces import PersistenceBackend
from .ad_runtime_controls import AdvertisingRuntimeControls
from .skill import Skill


class AdApplicationFacadeMixin:
    """Stable public controls and request entrypoint for the application."""

    @staticmethod
    def _validate_execution_mode(execution_mode: str) -> str:
        return AdvertisingRuntimeControls.validate_execution_mode(execution_mode)

    @property
    def execution_mode(self) -> str:
        return self._controls_service().execution_mode

    @execution_mode.setter
    def execution_mode(self, value: str) -> None:
        self._controls_service().execution_mode = value

    def set_execution_mode(
        self,
        execution_mode: str,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        return self._controls_service().set_execution_mode(
            execution_mode,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def get_execution_mode(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        return self._controls_service().get_execution_mode(tenant_id, user_id)

    def set_policies(self, policies: Optional[Iterable[RuntimePolicy]]) -> None:
        """Replace Skill-owned policies without interpreting their vocabulary."""
        self.policies = list(policies or [])
        setter = getattr(self.tool_selector, "set_policies", None)
        if callable(setter):
            setter(self.policies)

    def register_tool(
        self,
        definition: ToolDefinition,
        executor: Any,
        *,
        source_id: str = "local",
    ) -> None:
        return self._catalog_service().register_tool(
            definition,
            executor,
            source_id=source_id,
        )

    def register_tool_source(self, source: Any) -> list[str]:
        return self._catalog_service().register_tool_source(source)

    def unregister_tool_source(self, source_id: str) -> list[str]:
        return self._catalog_service().unregister_tool_source(source_id)

    @property
    def persistence_store(self) -> Optional[PersistenceBackend]:
        """Expose the persistence abstraction to management services."""
        return self._session_manager.store if self._session_manager else None

    @property
    def platform_application(self) -> Any:
        """Expose the single generic PlatformApplication entrypoint."""
        return self._platform_application

    @property
    def session_manager(self) -> Any:
        """Expose the application persistence/session port."""
        return self._session_manager

    @property
    def sessions(self) -> dict[str, Any]:
        """Expose the bounded in-process session cache to application services."""
        return self._sessions

    @property
    def redact_for_persistence(self) -> Any:
        """Expose the configured application redaction boundary."""
        return self._redact_for_persistence

    def close(self, wait: bool = False) -> None:
        return self._controls_service().close(wait=wait)

    def get_readiness(self) -> dict[str, Any]:
        return self._controls_service().readiness()

    @property
    def memory_manager(self) -> Optional[MemoryManager]:
        return self._controls_service().memory_manager

    def set_auto_memory_capture_enabled(self, enabled: bool) -> None:
        return self._controls_service().set_auto_memory_capture_enabled(enabled)

    def list_plugins(self, tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
        return self._lifecycle_service().list_plugins(tenant_id)

    def load_managed_skill(self, skill_dir: str, tenant_id: str = "default") -> bool:
        return self._lifecycle_service().load_managed_skill(
            skill_dir,
            tenant_id=tenant_id,
        )

    def unload_managed_skill(self, skill_name: str, tenant_id: str = "default") -> bool:
        return self._lifecycle_service().unload_managed_skill(
            skill_name,
            tenant_id=tenant_id,
        )

    def get_managed_skills(self, tenant_id: Optional[str] = None) -> dict[str, Skill]:
        return self._lifecycle_service().get_managed_skills(tenant_id)

    def inject_llm(self, llm_client: Any) -> None:
        return self._controls_service().inject_llm(llm_client)

    def assert_llm_ready(self) -> None:
        return self._controls_service().assert_llm_ready()

    def enable_read_only_mode(self) -> None:
        return self._controls_service().enable_read_only_mode()

    def run(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
        credentials: dict = None,
        platform_params: dict = None,
        confirmed: bool = False,
        confirmation_payload: Optional[dict] = None,
        creation_blueprint_id: Optional[str] = None,
        creation_blueprint_version: Optional[str] = None,
        creation_template_id: Optional[str] = None,
        principal: Optional[RequestPrincipal] = None,
        tenant_id: Optional[str] = None,
        cancellation_event: Optional[threading.Event] = None,
        event_callback: Optional[ExecutionEventCallback] = None,
        execution_mode: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict:
        return self._run_service().run(
            user_input=user_input,
            session_id=session_id,
            user_id=user_id,
            account_id=account_id,
            credentials=credentials,
            platform_params=platform_params,
            confirmed=confirmed,
            confirmation_payload=confirmation_payload,
            creation_blueprint_id=creation_blueprint_id,
            creation_blueprint_version=creation_blueprint_version,
            creation_template_id=creation_template_id,
            principal=principal,
            tenant_id=tenant_id,
            cancellation_event=cancellation_event,
            event_callback=event_callback,
            execution_mode=execution_mode,
            task_id=task_id,
        )


__all__ = ["AdApplicationFacadeMixin"]
