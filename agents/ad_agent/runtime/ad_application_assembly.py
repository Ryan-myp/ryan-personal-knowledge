"""Composition of the advertising application's Runtime dependencies.

``AdvertisingComposition`` is the public application facade, not the place where
every infrastructure object should be constructed.  This module owns the
application composition graph and returns explicit components to the facade.

The assembly is the advertising scenario's composition root. It contributes
Skills, Tools, data adapters and lifecycle resources to the generic Runtime;
the Harness owns the only Run/Session/Turn entry point.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from agents.agent_harness import (
    AgentRuntime,
    InMemorySkillCatalog,
    RuntimePorts,
    ToolCall,
    ToolCallContext,
    TurnRequest,
)
from agents.agent_platform import (
    AgentDefinition,
    AgentPlatform,
    PlatformApplication,
    PlatformDependencies,
    ScenarioDefinition,
)
from agents.agent_platform.tools.policy import ToolExecutionPolicy
from agents.agent_platform.runtime import DataLayer, InfrastructureLayer, IntegrationLayer
from ..core.memory import MemoryManager
from ..agent_definition import advertising_agent_definition
from ..domain.ad.auth import RequestPrincipal
from ..domain.ad.security import ACCOUNT_SCOPE_FIELDS
from ..persistence.interfaces import PersistenceBackend
from ..persistence.models import ScheduledTaskRecord
from ..persistence.session_manager import SessionManager
from ..persistence.adapters import (
    PersistenceIdempotencyStore,
    PersistenceTranscriptStore,
)
from .account_context import AccountResolver
from .ad_conversation_services import AdConversationServices
from .ad_persistence_services import AdPersistenceServices
from .ad_session_services import AdSessionServices
from .ad_task_services import AdTaskServices
from ..integration import (
    AdvertisingContextProvider,
    AdvertisingModelAdapter,
    AdvertisingToolCatalog,
)
from .ad_workflow_services import AdWorkflowServices
from .input_builder import ToolInputBuilder
from .outbox import OutboxPublisher
from .scheduling_service import SchedulingService
from .security import RuntimeSecurity
from .services import AdRuntimeServices
from .supervisor import RuntimeSupervisor
from .tool_executor import ToolExecutor
from .workflow import WorkflowCoordinator

logger = logging.getLogger(__name__)


class AdRunStoreAdapter:
    """Expose the advertising persistence API through the generic RunStore port."""

    def __init__(self, session_manager: SessionManager, runtime: Any) -> None:
        self.session_manager = session_manager
        self.runtime = runtime

    def start_run(self, **payload: Any) -> Any:
        from ..persistence.models import ExecutionRunRecord

        now = datetime.now(timezone.utc).isoformat()
        return self.session_manager.create_execution_run(
            ExecutionRunRecord(
                run_id=str(payload.get("run_id") or ""),
                session_id=str(payload.get("session_id") or ""),
                turn_id=str(payload.get("turn_id") or ""),
                user_id=str(payload.get("user_id") or "anonymous"),
                tenant_id=str(payload.get("tenant_id") or "default"),
                execution_mode=str(
                    payload.get("execution_mode")
                    or getattr(self.runtime, "execution_mode", "dry_run")
                ),
                task_id=(
                    str(payload["task_id"]) if payload.get("task_id") else None
                ),
                metadata={"effect_state": "unknown"},
                created_at=now,
                updated_at=now,
            )
        )

    def append_event(self, run_id: str, event: dict[str, Any]) -> bool:
        try:
            accepted = self.session_manager.append_execution_run_event(
                str(run_id), dict(event),
            )
        except Exception:
            accepted = False
        if accepted:
            return True
        enqueue = getattr(
            self.runtime._persistence_store,
            "enqueue_execution_event_repair",
            None,
        )
        if callable(enqueue):
            enqueue(str(run_id), dict(event))
        return False

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        current = self.session_manager.get_execution_run(str(run_id))
        current_metadata = getattr(current, "metadata", {}) if current else {}
        merged = {
            **(current_metadata if isinstance(current_metadata, dict) else {}),
            **dict(metadata or {}),
        }
        return bool(self.session_manager.update_execution_run(
            str(run_id),
            status=str(status),
            metadata=merged,
        ))

    def save_checkpoint(
        self, run_id: str, checkpoint: Mapping[str, Any],
    ) -> bool:
        current = self.session_manager.get_execution_run(str(run_id))
        metadata = getattr(current, "metadata", {}) if current else {}
        merged = dict(metadata) if isinstance(metadata, dict) else {}
        merged["checkpoint"] = dict(checkpoint)
        return bool(self.session_manager.update_execution_run(
            str(run_id), metadata=merged,
        ))

    def load_checkpoint(self, run_id: str) -> Optional[Mapping[str, Any]]:
        current = self.session_manager.get_execution_run(str(run_id))
        metadata = getattr(current, "metadata", {}) if current else {}
        checkpoint = (
            metadata.get("checkpoint")
            if isinstance(metadata, dict) else None
        )
        return dict(checkpoint) if isinstance(checkpoint, Mapping) else None

    def clear_checkpoint(self, run_id: str) -> bool:
        current = self.session_manager.get_execution_run(str(run_id))
        metadata = getattr(current, "metadata", {}) if current else {}
        merged = dict(metadata) if isinstance(metadata, dict) else {}
        merged.pop("checkpoint", None)
        return bool(self.session_manager.update_execution_run(
            str(run_id), metadata=merged,
        ))


@dataclass(frozen=True)
class AdApplicationAssemblyOptions:
    """Infrastructure options supplied by the application boundary.

    Domain settings such as Skill roots, Tool definitions and provider
    clients are initialized by ``AdvertisingComposition`` before this assembly runs.
    Only lifecycle/queue options belong here, which keeps the composition
    graph explicit and makes it possible to replace SQLite with MySQL through
    the same persistence port.
    """

    persistence_store: Optional[PersistenceBackend]
    outbox_delivery: Optional[Callable[[Any], None]]
    outbox_poll_interval: float
    outbox_max_attempts: int
    max_task_workers: int
    max_task_queue: int
    task_timeout_seconds: float
    task_lease_seconds: float
    task_queue_poll_interval: float
    start_background_workers: bool


@dataclass(frozen=True)
class AdApplicationComponents:
    """Fully wired application services returned by the assembly.

    Keeping these as one typed value prevents the facade constructor from
    silently growing another group of partially initialized attributes.
    ``install`` is the only mutation step and is intentionally kept at the
    application boundary.
    """

    persistence_store: Optional[PersistenceBackend]
    session_manager: Optional[SessionManager]
    memory_manager: Optional[MemoryManager]
    outbox: Optional[OutboxPublisher]
    services: AdRuntimeServices
    input_builder: ToolInputBuilder
    account_resolver: AccountResolver
    workflow: WorkflowCoordinator
    security: RuntimeSecurity
    scheduling_service: SchedulingService
    persistence_services: AdPersistenceServices
    conversation_services: AdConversationServices
    session_services: AdSessionServices
    workflow_services: AdWorkflowServices
    task_services: AdTaskServices
    runtime_kernel: AgentRuntime
    platform_application: PlatformApplication
    tool_executor: ToolExecutor
    supervisor: RuntimeSupervisor
    start_background_workers: bool

    def install(self, runtime: Any) -> None:
        """Install the graph on the application facade in one bounded step."""
        values = {
            "_persistence_store": self.persistence_store,
            "_session_manager": self.session_manager,
            "_memory_manager": self.memory_manager,
            "outbox": self.outbox,
            "services": self.services,
            "input_builder": self.input_builder,
            "account_resolver": self.account_resolver,
            "workflow": self.workflow,
            "security": self.security,
            "scheduling_service": self.scheduling_service,
            "persistence_services": self.persistence_services,
            "conversation_services": self.conversation_services,
            "session_services": self.session_services,
            "workflow_services": self.workflow_services,
            "task_services": self.task_services,
            "_runtime_kernel": self.runtime_kernel,
            "_platform_application": self.platform_application,
            "tool_executor": self.tool_executor,
            "supervisor": self.supervisor,
        }
        for name, value in values.items():
            setattr(runtime, name, value)
        runtime.outbox_consumer = self.supervisor.outbox_consumer
        runtime.event_repair_consumer = self.supervisor.event_repair_consumer
        runtime.task_executor = self.supervisor.task_executor
        runtime.scheduler = self.supervisor.scheduler
        if self.start_background_workers:
            self.supervisor.start()


class AdApplicationAssembly:
    """Build the advertising application graph over generic runtime ports."""

    @classmethod
    def compose(
        cls,
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        *,
        mode_context: ContextVar[Optional[str]],
        busy_error: type[Exception],
    ) -> AdApplicationComponents:
        store = options.persistence_store
        session_manager: Optional[SessionManager] = None
        memory_manager: Optional[MemoryManager] = None
        if store is not None:
            session_manager = SessionManager(store)
            recover_runs = getattr(session_manager, "recover_stale_execution_runs", None)
            if callable(recover_runs):
                try:
                    recovered_runs = recover_runs(runtime.workflow_stale_after_seconds)
                    if recovered_runs:
                        logger.warning(
                            "marked %s stale Agent runs for recovery", recovered_runs
                        )
                except Exception:
                    logger.exception("failed to recover stale Agent runs")
            if all(
                callable(getattr(store, method, None))
                for method in ("save_memory", "search_memories", "delete_memory")
            ):
                # Reuse the SessionManager-owned policy/cache instance so
                # Runtime recall and management/API recall share one bounded
                # cache and one automatic-capture switch per process.
                memory_manager = session_manager.memory_manager
                memory_manager.set_auto_capture_enabled(
                    bool(getattr(runtime, "auto_memory_capture_enabled", True))
                )
            if runtime.write_guard and hasattr(runtime.write_guard, "bind_store"):
                runtime.write_guard.bind_store(store)

        outbox = OutboxPublisher(session_manager) if session_manager else None
        services = AdRuntimeServices(runtime)
        input_builder = ToolInputBuilder(
            services,
            scope_field_names=ACCOUNT_SCOPE_FIELDS,
            scope_value_resolver=lambda context: getattr(context, "account_id", None),
        )
        account_resolver = AccountResolver(services)
        workflow = WorkflowCoordinator(
            services,
            outbox=outbox,
            item_scope_resolver=runtime._resolve_workflow_item_scope,
            result_scope_resolver=runtime._resolve_workflow_result_scope,
        )
        security = RuntimeSecurity(runtime)
        scheduling_service = SchedulingService(
            store=store,
            submit_task=runtime.submit_task,
            session_context=lambda session_id: runtime._sessions.get(str(session_id or "")),
            preflight=runtime.preflight_scheduled_prompt,
            redact=runtime._redact_for_persistence,
            validate_input=security.validate_input_redline,
            max_prompt_chars=runtime.max_user_input_chars,
            schedule_record_factory=ScheduledTaskRecord,
            task_kind="agent.turn",
            principal_from_metadata=lambda claims: RequestPrincipal.from_claims(claims),
            default_principal=lambda user, tenant: RequestPrincipal(
                user_id=user,
                tenant_id=tenant,
                permissions=runtime._granted_permissions,
            ),
        )
        services.bind_scheduling(scheduling_service)

        persistence_services = AdPersistenceServices(runtime)
        conversation_services = AdConversationServices(runtime)
        session_services = AdSessionServices(runtime)
        workflow_services = AdWorkflowServices(runtime)
        task_services = AdTaskServices(runtime)
        run_store = (
            AdRunStoreAdapter(session_manager, runtime)
            if session_manager is not None else None
        )
        def policy_scope_check(
            tool: Any, request: TurnRequest, arguments: Mapping[str, Any],
        ) -> Optional[tuple[str, str]]:
            """Inject the advertising account boundary into generic policy."""
            protected = runtime.security.validate_input_redline(arguments)
            if protected:
                return (
                    "protected_input",
                    "请求包含禁止传入的凭证/账户配置字段："
                    + ", ".join(protected),
                )
            platform = runtime._canonical_platform(
                str(getattr(tool, "namespace", "") or "")
            )
            if (
                str(getattr(request, "execution_mode", "") or "").lower() == "live"
                and bool(getattr(tool, "is_write_tool", False))
                and runtime.write_guard is None
            ):
                return (
                    "write_guard_missing",
                    "live 写操作必须配置 WriteGuard；已拒绝执行",
                )
            scoped_account = None
            if isinstance(request.context, Mapping):
                platform_params = request.context.get("platform_params")
                if isinstance(platform_params, Mapping):
                    for key, values in platform_params.items():
                        if (
                            runtime._resolve_platform_identifier(str(key))
                            == runtime._resolve_platform_identifier(platform)
                            and isinstance(values, Mapping)
                        ):
                            for field in (
                                getattr(tool, "scope_fields", ()) or (
                                    "account_id", "ad_account_id",
                                    "advertiser_id", "customer_id",
                                )
                            ):
                                if values.get(field) not in (None, ""):
                                    scoped_account = values[field]
                                    break
                        if scoped_account not in (None, ""):
                            break
            intent_namespaces = (
                request.context.get("_agent_intent_namespaces", ())
                if isinstance(request.context, Mapping) else ()
            )
            if not intent_namespaces and isinstance(request.context, Mapping):
                platform_params = request.context.get("platform_params")
                intent_namespaces = (
                    list(platform_params.keys())
                    if isinstance(platform_params, Mapping) else []
                )
            multiple_namespaces = len({
                runtime._canonical_platform(namespace)
                for namespace in (intent_namespaces or ())
            }) > 1
            scope_fields = tuple(
                getattr(tool, "scope_fields", ()) or (
                    "account_id", "ad_account_id",
                    "advertiser_id", "customer_id",
                )
            )
            account = (
                scoped_account
                or (
                    None
                    if multiple_namespaces
                    else (
                        request.context.get("account_id")
                        if isinstance(request.context, Mapping) else None
                    )
                )
                or next(
                    (
                        arguments.get(field)
                        for field in scope_fields
                        if arguments.get(field) not in (None, "")
                    ),
                    None,
                )
            )
            if not account and (
                bool(getattr(tool, "is_write_tool", False))
                or runtime.enforce_account_scope
            ):
                if bool(getattr(tool, "is_write_tool", False)):
                    return "confirmation_required", "请求缺少受控账户范围，请先提供账户并确认"
                return "scope_required", "请求缺少受控账户范围"
            principal = getattr(request, "principal", None)
            account_scope = getattr(principal, "account_scope", None)
            if account_scope is not None and account:
                allowed, message = runtime._validate_account_with_principal(
                    platform,
                    str(account),
                    bool(getattr(tool, "is_write_tool", False)),
                    account_scope,
                )
                if not allowed:
                    return "scope_denied", str(message)
            elif account and (
                bool(getattr(tool, "is_write_tool", False))
                or runtime.enforce_account_scope
            ):
                allowed, message = runtime._validate_account_for_tool(
                    platform,
                    str(account),
                    bool(getattr(tool, "is_write_tool", False)),
                )
                if not allowed:
                    return "scope_denied", str(message)
            if (
                str(getattr(request, "execution_mode", "") or "").lower() == "live"
                and bool(getattr(tool, "is_write_tool", False))
                and isinstance(request.context, Mapping)
                and request.context.get("confirmed")
            ):
                provided = request.context.get("confirmation_payload")
                if not isinstance(provided, Mapping):
                    return (
                        "confirmation_required",
                        "confirmed=true 必须携带当前计划的 confirmation_payload",
                    )
                context = ToolCallContext(
                    request=request,
                    assistant_message=None,
                    tool_call=ToolCall(
                        id="policy-confirmation",
                        name=str(getattr(tool, "name", "") or ""),
                        arguments=dict(arguments),
                    ),
                    state=None,
                    tool_definition=tool,
                )
                expected = confirmation_builder(context, tool, arguments)
                if not runtime.security.confirmation_matches(provided, expected or {}):
                    return (
                        "confirmation_mismatch",
                        "确认信息与当前写入计划不匹配，已拒绝执行",
                    )
                approval_ok, approval_error = (
                    runtime.security.validate_confirmation_record(expected, provided)
                )
                if not approval_ok:
                    return (
                        "confirmation_invalid",
                        f"确认记录无效：{approval_error}",
                    )
            return None

        def confirmation_builder(
            context: Any,
            tool: Any,
            arguments: Mapping[str, Any],
        ) -> Mapping[str, Any] | None:
            """Create the application approval binding without owning Run state."""
            request = context.request
            request_context = (
                request.context if isinstance(request.context, Mapping) else {}
            )
            intent_namespaces = request_context.get(
                "_agent_intent_namespaces", ()
            )
            if not intent_namespaces:
                platform_params = request_context.get("platform_params")
                intent_namespaces = (
                    list(platform_params.keys())
                    if isinstance(platform_params, Mapping) else []
                )
            multiple_namespaces = len({
                runtime._canonical_platform(namespace)
                for namespace in (intent_namespaces or ())
            }) > 1
            scope_fields = tuple(
                getattr(tool, "scope_fields", ()) or (
                    "account_id", "ad_account_id",
                    "advertiser_id", "customer_id",
                )
            )
            account = (
                (
                    None
                    if multiple_namespaces
                    else request_context.get("account_id")
                )
                or next(
                    (
                        arguments.get(field)
                        for field in scope_fields
                        if arguments.get(field) not in (None, "")
                    ),
                    None,
                )
            )
            if account in (None, ""):
                return {
                    "type": "ask_account",
                    "platform": str(getattr(tool, "namespace", "") or ""),
                    "question": "请提供要操作的广告账户 ID。",
                }
            related_tools = [
                candidate for candidate in runtime.registry.list_all()
                if (
                    getattr(candidate, "is_write_tool", False)
                    and runtime._canonical_platform(
                        str(getattr(candidate, "namespace", "") or "")
                    ) == runtime._canonical_platform(
                        str(getattr(tool, "namespace", "") or "")
                    )
                    and set(getattr(candidate, "intent_types", ()) or ())
                    & set(getattr(tool, "intent_types", ()) or ())
                )
            ]
            is_chain = (
                bool(getattr(tool, "action", "") == "create")
                and any(
                    getattr(candidate, "parent_resource_type", None)
                    for candidate in related_tools
                )
            )
            if is_chain:
                incoming = request_context.get("confirmation_payload")
                if (
                    bool(request_context.get("confirmed"))
                    and isinstance(incoming, Mapping)
                    and incoming.get("type") == "confirm_write_plan"
                ):
                    return dict(incoming)
                expected = security.confirmation_chain_plan(
                    str(request.session_id or ""),
                    str(request.user_id or "anonymous"),
                    str(account),
                    str(getattr(tool, "namespace", "") or ""),
                    related_tools,
                    dict(arguments),
                    preview={"tools": [candidate.name for candidate in related_tools]},
                )
                confirmed = bool(request_context.get("confirmed"))
                return security.prepare_confirmation(
                    expected,
                    create=not confirmed,
                )
            expected = security.confirmation_plan(
                str(request.session_id or ""),
                str(request.user_id or "anonymous"),
                str(account),
                tool,
                dict(arguments),
                preview={"tool": str(getattr(tool, "name", "") or ""), "input": dict(arguments)},
            )
            expected["type"] = "confirm_write"
            confirmed = bool(request_context.get("confirmed"))
            return security.prepare_confirmation(
                expected,
                create=not confirmed,
            )

        tool_policy = ToolExecutionPolicy(
            permissions=frozenset(runtime._granted_permissions),
            allow_live_writes=bool(runtime.allow_live_writes),
            # Keep the policy connected to the trusted deployment-owned
            # approval set. Tool Sources may be registered, verified or
            # approved after the composition root has been built; copying
            # this set here would leave the live gate stale.
            live_approved_tools=runtime._live_approved_tools,
            # The concrete WriteGuard is supplied by the selected Tool Source
            # before a live call. The dynamic scope check below remains the
            # source of truth for this application-owned resource.
            write_guard_configured=True,
            require_confirmation_for_writes=True,
            before_check=policy_scope_check,
            confirmation_builder=confirmation_builder,
            live_approved_tools_provider=lambda: runtime._live_approved_tools,
            require_audit=True,
            idempotency_store=(
                PersistenceIdempotencyStore(store) if store is not None else None
            ),
        )
        ports = RuntimePorts(
            session_manager=session_manager,
            session_locks=runtime._session_locks,
            session_locks_guard=runtime._session_locks_guard,
            lease_owner=runtime._session_lease_owner,
            lease_seconds=runtime.session_lease_seconds,
            mode_context=mode_context,
            validate_mode=runtime._validate_execution_mode,
            resolve_mode=lambda tenant, user, _requested: runtime.get_execution_mode(
                tenant, user
            ),
            assert_ready=runtime.assert_llm_ready,
            ensure_session=runtime._ensure_kernel_session,
            refresh_session=runtime._refresh_kernel_session,
            busy_error=busy_error,
        )
        tool_executor = ToolExecutor(services)
        supervisor = RuntimeSupervisor(
            store=store,
            outbox_delivery=options.outbox_delivery or runtime._default_outbox_delivery,
            scheduled_submitter=runtime._submit_scheduled_task,
            task_handlers={
                "agent.turn": runtime._execute_agent_task,
                "knowledge.ingest": runtime._execute_knowledge_ingest_task,
            },
            redact=runtime._redact_for_persistence,
            max_task_workers=options.max_task_workers,
            max_task_queue=options.max_task_queue,
            task_timeout_seconds=options.task_timeout_seconds,
            task_lease_seconds=options.task_lease_seconds,
            task_queue_poll_interval=options.task_queue_poll_interval,
            outbox_poll_interval=options.outbox_poll_interval,
            outbox_max_attempts=options.outbox_max_attempts,
            # Start only after ``AdApplicationComponents.install`` has published
            # every callback target on the facade. This prevents a recovered
            # task/schedule from racing a partially initialized application.
            start_background_workers=False,
            create_background_workers=options.start_background_workers,
        )
        platform = AgentPlatform()
        platform.register_agent(advertising_agent_definition())
        platform.register_scenario(ScenarioDefinition(
            scenario_id="advertising",
            agent_id=platform.agent_id,
            display_name="Advertising",
        ))
        context_provider = AdvertisingContextProvider(runtime)
        platform_application = platform.create_application(
            "advertising",
            model=AdvertisingModelAdapter(runtime),
            dependencies=PlatformDependencies(
                data=DataLayer(
                    knowledge_store=runtime.knowledge_provider,
                    memory_store=memory_manager,
                    session_store=session_manager,
                    run_store=run_store,
                ),
                integrations=IntegrationLayer(registry=runtime.registry),
                infrastructure=InfrastructureLayer(
                    resources=(supervisor,) if options.start_background_workers else (),
                ),
            ),
            options={
                "ports": ports,
                "tool_catalog": AdvertisingToolCatalog(runtime),
                "skill_catalog": InMemorySkillCatalog(),
                "tool_policy": tool_policy,
                "context_provider": context_provider,
                "input_sanitizer": runtime._redact_for_persistence,
                "run_store": run_store,
                "checkpoint_store": run_store,
                "transcript_store": (
                    PersistenceTranscriptStore(store) if store is not None else None
                ),
                "metrics": getattr(runtime, "metrics", None),
                "max_turns": max(4, int(runtime.max_tool_calls) + 2),
                "tool_execution": "sequential",
            },
        )
        runtime_kernel = platform_application.runtime
        return AdApplicationComponents(
            persistence_store=store,
            session_manager=session_manager,
            memory_manager=memory_manager,
            outbox=outbox,
            services=services,
            input_builder=input_builder,
            account_resolver=account_resolver,
            workflow=workflow,
            security=security,
            scheduling_service=scheduling_service,
            persistence_services=persistence_services,
            conversation_services=conversation_services,
            session_services=session_services,
            workflow_services=workflow_services,
            task_services=task_services,
            runtime_kernel=runtime_kernel,
            platform_application=platform_application,
            tool_executor=tool_executor,
            supervisor=supervisor,
            start_background_workers=options.start_background_workers,
        )


__all__ = [
    "AdApplicationAssembly",
    "AdApplicationAssemblyOptions",
    "AdApplicationComponents",
    "AdRunStoreAdapter",
]
