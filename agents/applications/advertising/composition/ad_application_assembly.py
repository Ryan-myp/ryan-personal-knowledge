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
import re
from contextvars import ContextVar
from typing import Any, Callable, Mapping, Optional

from agents.agent_harness import (
    InMemorySkillCatalog,
    RuntimePorts,
    TurnRequest,
)
from agents.agent_harness.core.tool_selection import ToolSelector
from agents.agent_harness.core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS
from agents.agent_platform import (
    AgentPlatform,
    PlatformDependencies,
)
from agents.agent_platform.runtime import DataLayer, InfrastructureLayer, IntegrationLayer
from agents.agent_platform.tools import (
    knowledge_search_tool_source,
    readonly_recipe_tool_source,
    scheduling_tool_source,
)
from agents.agent_platform.tools.clarification import clarification_tool_source
from agents.agent_harness.core.plugins import PluginKind
from agents.agent_harness.core.memory import MemoryManager
from agents.scenarios.advertising import (
    advertising_agent_definition,
    advertising_scenario_definition,
)
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.tools.advertising.shared.domain.security import ACCOUNT_SCOPE_FIELDS
from agents.tools.advertising.shared.budget_analysis import (
    cross_channel_budget_analysis_tool_source,
)
from agents.applications.advertising.persistence.models import (
    ScheduledTaskRecord,
    ScheduledTaskRunRecord,
)
from agents.applications.advertising.creation.template_tool_service import (
    pending_template_input_tool,
)
from agents.applications.advertising.persistence.session_manager import SessionManager
from agents.applications.advertising.persistence.adapters import (
    PersistenceTranscriptStore,
)
from ..execution.account_context import AccountResolver
from ..operations.ad_conversation_services import AdConversationServices
from ..operations.ad_persistence_services import AdPersistenceServices
from ..operations.ad_session_services import AdSessionServices
from ..operations.ad_task_services import AdTaskServices
from ..integrations.integration import (
    AdvertisingContextProvider,
    AdvertisingToolCatalog,
    registered_advertising_tool_sources,
)
from ..execution.ad_tool_policy_factory import AdvertisingToolPolicyFactory
from ..operations.ad_workflow_services import AdWorkflowServices
from ..execution.input_builder import ToolInputBuilder
from agents.agent_platform.infrastructure.durable import OutboxPublisher
from ..operations.scheduling_service import SchedulingService
from ..execution.security import RuntimeSecurity
from ..operations.services import AdRuntimeServices
from agents.agent_platform.infrastructure.durable import RuntimeSupervisor
from ..execution.tool_executor import ToolExecutor
from ..operations.workflow import WorkflowCoordinator
from .ad_application_components import (
    AdApplicationAssemblyOptions,
    AdApplicationComponents,
    AdApplicationServiceGraph,
    AdRunStoreAdapter,
)

logger = logging.getLogger(__name__)

MAX_RELEVANT_TOOLS_PER_TURN = 32
_MULTI_ACCOUNT_REFERENCE = re.compile(
    r"(?:这\s*(?:几个|些)|所有|每(?:个|一个)|各(?:个)?)"
    r"(?:测试|广告)?(?:账号|账户|渠道|平台)"
    r"|(?:他们|它们|这些|上述|以上)"
    r"|\b(?:these|all|each|every|both|multiple|the following)"
    r"\s+(?:(?:test|ad)\s+)?(?:accounts?|channels?|platforms?)\b",
    re.IGNORECASE,
)


def _select_blueprint_tools(
    runtime: Any,
    context: Mapping[str, Any],
    tools: Any,
    *,
    include_lookups: bool = False,
) -> Optional[list[Any]]:
    blueprint_id = str(context.get("creation_blueprint_id") or "").strip()
    if not blueprint_id:
        return None
    version = context.get("creation_blueprint_version") or None
    blueprint = runtime.creation_blueprints.get(blueprint_id, version)
    if blueprint is None and not context.get("creation_template_id"):
        blueprint = runtime.creation_blueprints.get(blueprint_id)
    if blueprint is None:
        return []

    available = {
        str(getattr(tool, "name", "") or ""): tool
        for tool in tools
        if getattr(tool, "name", None)
    }
    selected = []
    for name in blueprint.tools:
        tool = available.get(str(name))
        if (
            tool is None
            or str(getattr(tool, "action", "")).lower() != "create"
            or runtime._canonical_platform(
                str(getattr(tool, "namespace", "") or "")
            ) != runtime._canonical_platform(blueprint.provider)
        ):
            return []
        selected.append(tool)
    if include_lookups:
        selection = runtime.input_builder.parameter_selection
        lookup_names = {
            lookup
            for tool in selected
            for field, schema in selection.iter_schema_fields(tool.input_schema.properties)
            if field.split(".", 1)[0] not in {
                tool.parent_resource_id_field, tool.resource_id_field,
                *(tool.related_resource_id_fields or ()),
            }
            if (lookup := selection.lookup_tool_for_field(schema))
        }
        lookup_names.update(
            str(field["lookup_tool"])
            for field in blueprint.fields if field.get("lookup_tool")
        )
        for name in sorted(lookup_names):
            lookup = available.get(name)
            if (
                lookup is not None and lookup.is_read_tool
                and runtime._canonical_platform(lookup.namespace)
                == runtime._canonical_platform(blueprint.provider)
            ):
                selected.append(lookup)
    selected = list({tool.name: tool for tool in selected}.values())
    return selected[:MAX_RELEVANT_TOOLS_PER_TURN]


def _filter_unapproved_live_write_tools(
    runtime: Any,
    request: TurnRequest,
    tools: Any,
) -> list[Any]:
    """Hide external writes that the active live policy cannot execute.

    Model-visible Tools and executable Tools must use the same write boundary.
    Otherwise the selector can offer an unapproved legacy Tool and the model
    only discovers the mismatch when the policy rejects the call.
    """
    items = list(tools or ())
    if str(getattr(request, "execution_mode", "") or "").lower() != "live":
        return items
    approved = set(getattr(runtime, "_live_approved_tools", ()) or ())
    visible: list[Any] = []
    for tool in items:
        if not bool(getattr(tool, "is_write_tool", False)):
            visible.append(tool)
            continue
        effect = getattr(tool, "effect_class", "")
        effect = str(getattr(effect, "value", effect) or "").lower()
        if effect == "internal_write":
            visible.append(tool)
            continue
        name = str(getattr(tool, "name", "") or "")
        if name and name in approved:
            visible.append(tool)
    return visible


def _creation_blueprint_request_error(
    runtime: Any,
    context: Mapping[str, Any],
) -> Optional[str]:
    blueprint_id = str(context.get("creation_blueprint_id") or "").strip()
    if not blueprint_id:
        return None
    version = context.get("creation_blueprint_version") or None
    blueprint = runtime.creation_blueprints.get(blueprint_id, version)
    if blueprint is None and not context.get("creation_template_id"):
        blueprint = runtime.creation_blueprints.get(blueprint_id)
    if blueprint is None:
        return (
            None if context.get("creation_template_id")
            else "广告创建蓝图不存在或版本不可用，请重新选择创建类型。"
        )
    for name in blueprint.tools:
        try:
            definition, _handler = runtime.registry.get(str(name))
        except (KeyError, LookupError):
            return "广告创建蓝图依赖的 Tool 暂不可用，请稍后重试。"
        if (
            str(getattr(definition, "action", "")).lower() != "create"
            or runtime._canonical_platform(
                str(getattr(definition, "namespace", "") or "")
            ) != runtime._canonical_platform(blueprint.provider)
        ):
            return "广告创建蓝图的 Tool 契约与当前注册能力不一致。"
    return None


class AdApplicationAssembly:
    """Build the advertising application graph over generic runtime ports."""

    @staticmethod
    def _multi_account_context_namespaces(
        runtime: Any,
        selector: ToolSelector,
        request: TurnRequest,
        tools: Any,
    ) -> tuple[str, ...]:
        """Resolve plural account references from trusted principal scope."""
        text = str(getattr(request, "user_input", "") or "")
        principal = getattr(request, "principal", None)
        scope = getattr(principal, "account_scope", None)
        if (
            not isinstance(scope, Mapping)
            or not scope
            or not _MULTI_ACCOUNT_REFERENCE.search(text)
            or not selector.is_read_only_request(text, tools)
        ):
            return ()

        registered = set(selector.registered_namespaces(tools))
        account_provider = getattr(
            runtime, "_available_accounts_for_request", None,
        )
        namespaces: set[str] = set()
        for raw_namespace, accounts in scope.items():
            if isinstance(accounts, (str, bytes)) or not accounts:
                continue
            namespace = runtime._canonical_platform(str(raw_namespace))
            if namespace not in registered:
                continue
            authorized_accounts = (
                account_provider(namespace, scope)
                if callable(account_provider)
                else accounts
            )
            if authorized_accounts:
                namespaces.add(namespace)
        return tuple(sorted(namespaces))

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
        session_manager, memory_manager = cls._create_session_manager(runtime, store)
        outbox = OutboxPublisher(session_manager) if session_manager else None
        services = cls._build_service_graph(
            runtime, store, session_manager, outbox,
        )
        ports = cls._build_runtime_ports(
            runtime, session_manager, mode_context, busy_error,
        )
        supervisor = cls._build_supervisor(runtime, options, store)
        platform_application = cls._build_platform_application(
            runtime, options, services, session_manager, memory_manager, ports,
            supervisor,
        )
        return AdApplicationComponents(
            persistence_store=store,
            session_manager=session_manager,
            memory_manager=memory_manager,
            outbox=services.outbox,
            services=services.services,
            input_builder=services.input_builder,
            account_resolver=services.account_resolver,
            workflow=services.workflow,
            security=services.security,
            scheduling_service=services.scheduling_service,
            persistence_services=services.persistence_services,
            conversation_services=services.conversation_services,
            session_services=services.session_services,
            workflow_services=services.workflow_services,
            task_services=services.task_services,
            runtime_kernel=platform_application.runtime,
            platform_application=platform_application,
            tool_executor=services.tool_executor,
            supervisor=supervisor,
            start_background_workers=options.start_background_workers,
        )

    @staticmethod
    def _create_session_manager(
        runtime: Any,
        store: Any,
    ) -> tuple[Optional[SessionManager], Optional[MemoryManager]]:
        if store is None:
            return None, None
        session_manager = SessionManager(store)
        recover_runs = getattr(session_manager, "recover_stale_execution_runs", None)
        if callable(recover_runs):
            recovered_runs = recover_runs(runtime.workflow_stale_after_seconds)
            if recovered_runs:
                logger.warning(
                    "marked %s stale Agent runs for recovery", recovered_runs,
                )
        memory_manager = None
        memory_methods = ("save_memory", "search_memories", "delete_memory")
        if all(callable(getattr(store, method, None)) for method in memory_methods):
            memory_manager = session_manager.memory_manager
            memory_manager.set_auto_capture_enabled(
                bool(getattr(runtime, "auto_memory_capture_enabled", True))
            )
        if runtime.write_guard and hasattr(runtime.write_guard, "bind_store"):
            runtime.write_guard.bind_store(store)
        return session_manager, memory_manager

    @staticmethod
    def _build_service_graph(
        runtime: Any,
        store: Any,
        session_manager: Optional[SessionManager],
        outbox: Optional[OutboxPublisher],
    ) -> AdApplicationServiceGraph:
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
        scheduling_service = AdApplicationAssembly._build_scheduling_service(
            runtime, store, security,
        )
        services.bind_scheduling(scheduling_service)
        for source, description in (
            (
                clarification_tool_source(required_permission="ads.read"),
                "Side-effect-free structured clarification Tool",
            ),
            (
                knowledge_search_tool_source(
                    runtime.knowledge_provider,
                    required_permission="ads.read",
                ),
                "Built-in read-only knowledge search Tool",
            ),
            (
                readonly_recipe_tool_source(required_permission="ads.read"),
                "Built-in declarative read-only JSON transform Tool",
            ),
            (
                cross_channel_budget_analysis_tool_source(),
                "Built-in read-only cross-channel budget analysis Tool",
            ),
        ):
            runtime.registry.register_source(source)
            runtime._register_builtin_plugin(
                source.source_id,
                source,
                (PluginKind.TOOL_SOURCE.value,),
                description=description,
            )
        if store is not None and not runtime._read_only_mode:
            runtime.registry.register_source(scheduling_tool_source(
                lambda **kwargs: runtime.create_schedule(**kwargs),
                required_permission="ads.plan",
                run_schedule_now=lambda schedule_id, user_id, tenant_id: (
                    runtime.run_schedule_now(
                        schedule_id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                    )
                ),
            ))
        return AdApplicationServiceGraph(
            outbox=outbox,
            services=services,
            input_builder=input_builder,
            account_resolver=account_resolver,
            workflow=workflow,
            security=security,
            scheduling_service=scheduling_service,
            persistence_services=AdPersistenceServices(runtime),
            conversation_services=AdConversationServices(runtime),
            session_services=AdSessionServices(runtime),
            workflow_services=AdWorkflowServices(runtime),
            task_services=AdTaskServices(runtime),
            run_store=(
                AdRunStoreAdapter(session_manager, store)
                if session_manager is not None else None
            ),
            tool_policy=AdvertisingToolPolicyFactory(runtime).build(store),
            tool_executor=ToolExecutor(services),
        )

    @staticmethod
    def _build_scheduling_service(
        runtime: Any,
        store: Any,
        security: RuntimeSecurity,
    ) -> SchedulingService:
        return SchedulingService(
            store=store,
            submit_task=runtime.submit_task,
            redact=runtime._redact_for_persistence,
            validate_input=security.validate_input_redline,
            max_prompt_chars=runtime.max_user_input_chars,
            schedule_record_factory=ScheduledTaskRecord,
            schedule_run_record_factory=ScheduledTaskRunRecord,
            task_kind="agent.turn",
            principal_from_metadata=lambda claims: RequestPrincipal.from_claims(claims),
            default_principal=lambda user, tenant: RequestPrincipal(
                user_id=user,
                tenant_id=tenant,
                permissions=runtime._granted_permissions,
            ),
        )

    @staticmethod
    def _build_runtime_ports(
        runtime: Any,
        session_manager: Optional[SessionManager],
        mode_context: ContextVar[Optional[str]],
        busy_error: type[Exception],
    ) -> RuntimePorts:
        return RuntimePorts(
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

    @staticmethod
    def _build_supervisor(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        store: Any,
    ) -> RuntimeSupervisor:
        return RuntimeSupervisor(
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
            start_background_workers=False,
            create_background_workers=options.start_background_workers,
        )

    @staticmethod
    def _build_platform_application(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        services: AdApplicationServiceGraph,
        session_manager: Optional[SessionManager],
        memory_manager: Optional[MemoryManager],
        ports: RuntimePorts,
        supervisor: RuntimeSupervisor,
    ) -> Any:
        platform = AgentPlatform()
        platform.register_agent(advertising_agent_definition())
        platform.register_scenario(
            advertising_scenario_definition(agent_id=platform.agent_id)
        )
        return platform.create_application(
            "advertising",
            model=runtime._llm,
            dependencies=AdApplicationAssembly._platform_dependencies(
                runtime, options, services, session_manager, memory_manager,
                supervisor,
            ),
            options=AdApplicationAssembly._platform_options(
                runtime, options, services, ports,
            ),
        )

    @staticmethod
    def _platform_dependencies(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        services: AdApplicationServiceGraph,
        session_manager: Optional[SessionManager],
        memory_manager: Optional[MemoryManager],
        supervisor: RuntimeSupervisor,
    ) -> PlatformDependencies:
        resources = (supervisor,) if options.start_background_workers else ()
        return PlatformDependencies(
            data=DataLayer(
                knowledge_store=runtime.knowledge_provider,
                memory_store=memory_manager,
                session_store=session_manager,
                run_store=services.run_store,
            ),
            integrations=IntegrationLayer(
                tool_sources=registered_advertising_tool_sources(runtime),
                registry=runtime.registry,
            ),
            infrastructure=InfrastructureLayer(resources=resources),
        )

    @staticmethod
    def _platform_options(
        runtime: Any,
        options: AdApplicationAssemblyOptions,
        services: AdApplicationServiceGraph,
        ports: RuntimePorts,
    ) -> dict[str, Any]:
        return {
            "ports": ports,
            "tool_catalog": AdvertisingToolCatalog(runtime),
            "tool_selector": AdApplicationAssembly._tool_selector(
                runtime,
                ToolSelector(policies=getattr(runtime, "policies", ())),
            ),
            "skill_catalog": InMemorySkillCatalog(),
            "tool_policy": services.tool_policy,
            "context_provider": AdvertisingContextProvider(runtime),
            "input_sanitizer": runtime._redact_for_persistence,
            "request_validator": AdApplicationAssembly._request_validator(
                runtime, services.security,
            ),
            "run_store": services.run_store,
            "checkpoint_store": services.run_store,
            "transcript_store": (
                PersistenceTranscriptStore(options.persistence_store)
                if options.persistence_store is not None else None
            ),
            "metrics": getattr(runtime, "metrics", None),
            "max_turns": max(4, int(runtime.max_tool_calls) + 2),
            "max_tool_calls_per_run": int(runtime.max_tool_calls),
            "tool_execution": "parallel_reads",
            "max_parallel_tools": runtime.max_parallel_tools,
            "max_inflight_tool_invocations": runtime.max_inflight_tool_invocations,
            "model_timeout_seconds": getattr(
                runtime, "turn_timeout_seconds", DEFAULT_EXECUTION_TIMEOUT_SECONDS,
            ),
            "tool_timeout_seconds": getattr(
                runtime, "turn_timeout_seconds", DEFAULT_EXECUTION_TIMEOUT_SECONDS,
            ),
            "tool_max_retries": 0,
        }

    @staticmethod
    def _authorized_account_namespace(
        runtime: Any,
        request: TurnRequest,
        tools: Any,
    ) -> Optional[str]:
        context = request.context if isinstance(request.context, Mapping) else {}
        account = context.get("account_id")
        scope = getattr(request.principal, "account_scope", None)
        if scope is None:
            return None
        namespaces = {
            runtime._canonical_platform(str(getattr(tool, "namespace", "") or ""))
            for tool in tools
            if getattr(tool, "namespace", None)
        }
        if account not in (None, ""):
            candidates = {namespace: account for namespace in namespaces}
        else:
            remembered = context.get("_agent_read_account_scopes")
            if not isinstance(remembered, Mapping) or not remembered:
                sessions = getattr(runtime, "_sessions", {})
                session = sessions.get(str(request.session_id or ""))
                metadata = getattr(getattr(session, "ctx", None), "metadata", {})
                remembered = metadata.get("read_account_scopes", {})
            candidates = remembered if isinstance(remembered, Mapping) else {}
        matches = [
            namespace for namespace in namespaces
            if candidates.get(namespace) not in (None, "")
            and runtime._validate_account_with_principal(
                namespace, str(candidates[namespace]), False, scope,
            )[0]
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _account_option_allowed(
        runtime: Any, tool: Any, account_id: str,
        interaction: Any, scope: Any,
    ) -> bool:
        namespace = str(getattr(tool, "namespace", "") or "")
        if scope is None or not runtime._validate_account_with_principal(
            namespace, account_id, False, scope,
        )[0]:
            return False
        if interaction is None:
            return account_id in runtime._available_accounts_for_request(
                namespace, scope,
            )
        if not isinstance(interaction, Mapping) or (
            interaction.get("type") != "account_selection"
        ):
            return False
        payload = interaction.get("payload")
        if not isinstance(payload, Mapping):
            return False
        options = payload.get("account_options")
        return (
            payload.get("tool") == tool.name
            and runtime._canonical_platform(str(payload.get("namespace") or ""))
            == runtime._canonical_platform(namespace)
            and isinstance(options, list)
            and any(
                isinstance(option, Mapping)
                and str(option.get("value") or "") == account_id
                for option in options[:20]
            )
        )

    @staticmethod
    def _resume_account_read(
        runtime: Any, request: TurnRequest, tools: Any,
    ) -> Any | None:
        context = request.context if isinstance(request.context, Mapping) else {}
        pending = context.get("_agent_pending_interaction")
        if not isinstance(pending, Mapping) or not pending.get("source_input"):
            return None
        account_id = str(context.get("account_id") or "").strip()
        response = context.get("_agent_interaction_response")
        if not account_id:
            return None
        if response is not None:
            if not isinstance(response, Mapping) or any((
                response.get("type") != "account_selection",
                response.get("turn_id") != pending.get("turn_id"),
                response.get("tool_name") != pending.get("tool_name"),
                response.get("value") != account_id,
            )):
                return None
        elif request.user_input.strip() != f"使用账户 {account_id} 继续":
            # Older clients have no structured selection; retain their exact
            # command without interpreting a new question as a continuation.
            return None
        tool = next((
            tool for tool in tools
            if getattr(tool, "name", None) == pending.get("tool_name")
            and getattr(tool, "is_read_tool", False)
        ), None)
        if tool is None:
            return None
        scope = getattr(request.principal, "account_scope", None)
        if not AdApplicationAssembly._account_option_allowed(
            runtime, tool, account_id, pending.get("interaction"), scope,
        ):
            return None
        return tool

    @staticmethod
    def _scope_account_directory(
        selector: ToolSelector, user_input: str, selected: list[Any],
    ) -> list[Any]:
        """Account selection is a prerequisite, not a second read target."""
        account_lists = [
            tool for tool in selected
            if getattr(tool, "action", None) == "list"
            and getattr(tool, "resource_type", None) == "account"
        ]
        if not account_lists or not selector.has_explicit_resource_target(
            user_input,
            [
                tool for tool in selected
                if getattr(tool, "resource_type", None) != "account"
            ],
        ):
            return selected
        text = user_input.casefold()
        explicit = {
            tool.name for tool in account_lists
            if any(
                len(str(alias).strip()) >= 3
                and str(alias).strip().casefold() in text
                for alias in getattr(tool, "intent_aliases", ()) or ()
            )
        }
        return [
            tool for tool in selected
            if tool not in account_lists or tool.name in explicit
        ]

    @staticmethod
    def _tool_selector(
        runtime: Any,
        selector: ToolSelector,
    ) -> Callable[[TurnRequest, Any], list[Any]]:
        def select_tools(request: TurnRequest, tools: Any) -> list[Any]:
            request_context = (
                request.context if isinstance(request.context, Mapping) else {}
            )
            preview = pending_template_input_tool(runtime, request, tools)
            resume = AdApplicationAssembly._resume_account_read(
                runtime, request, tools,
            )
            if preview is not None:
                selected = [preview]
            elif resume is not None:
                selected = [resume]
                request_context["_agent_tool_choice_required"] = True
            else:
                selected = _select_blueprint_tools(
                    runtime, request_context, tools,
                    include_lookups=str(request.execution_mode or "dry_run") == "live",
                )
            allow_clarification = selected is None
            if selected is None:
                conversation_context = tuple(
                    request_context.get("_agent_tool_selection_context", ()) or ()
                )
                sessions = getattr(runtime, "sessions", None)
                get_session = getattr(sessions, "get", None)
                session_id = str(getattr(request, "session_id", "") or "")
                session = (
                    get_session(session_id)
                    if callable(get_session) and session_id else None
                )
                metadata = getattr(
                    getattr(session, "ctx", None), "metadata", {},
                )
                task_state = (
                    metadata.get("conversation_task_state", {})
                    if isinstance(metadata, Mapping) else {}
                )
                observations = (
                    task_state.get("observations", [])
                    if isinstance(task_state, Mapping) else []
                )
                prior_requests = [
                    str(item.get("user_request") or "").strip()
                    for item in observations[-4:]
                    if isinstance(item, Mapping) and item.get("user_request")
                ] if isinstance(observations, list) else []
                if prior_requests:
                    conversation_context = (*conversation_context, *prior_requests)
                contextual_namespaces = (
                    AdApplicationAssembly._multi_account_context_namespaces(
                        runtime, selector, request, tools,
                    )
                )
                account_namespace = AdApplicationAssembly._authorized_account_namespace(
                    runtime, request, tools,
                )
                if account_namespace:
                    conversation_context = (*conversation_context, account_namespace)
                registry = getattr(runtime, "registry", None)
                list_registered = getattr(registry, "list_all", None)
                registered_tools = (
                    list_registered() if callable(list_registered) else tools
                )
                blocked_resource_target = (
                    selector.is_read_only_request(
                        request.user_input, tools,
                    )
                    and selector.has_declared_resource_target(
                        request.user_input, registered_tools,
                    )
                    and not selector.has_declared_resource_target(
                        request.user_input, tools,
                    )
                    and not selector.explicitly_requests_discovery(
                        request.user_input, tools,
                    )
                )
                selected = [] if blocked_resource_target else (
                    selector.select_relevant(
                        request.user_input,
                        tools,
                        limit=MAX_RELEVANT_TOOLS_PER_TURN,
                        conversation_context=conversation_context,
                        contextual_namespaces=contextual_namespaces,
                    )
                )
                selected = AdApplicationAssembly._scope_account_directory(
                    selector, request.user_input, selected,
                )
                attached_read_required = False
                if not blocked_resource_target:
                    media_types = {
                        str(getattr(media, "media_type", "") or "")
                        for media in getattr(request, "input_media", ()) or ()
                    }
                    compatible = [
                        tool for tool in tools
                        if any(
                            f"accepts_media:{media_type}"
                            in (getattr(tool, "traits", ()) or ())
                            for media_type in media_types
                        )
                    ]
                    attached_read_required = bool(compatible) and all(
                        tool in compatible
                        or "semantic_discovery" in (getattr(tool, "traits", ()) or ())
                        for tool in selected
                    )
                    if (
                        attached_read_required
                        and not selector.explicitly_requests_discovery(
                            request.user_input, tools,
                        )
                    ):
                        selected = compatible
                    selected = list({
                        tool.name: tool for tool in (
                            *compatible, *selected,
                        )
                    }.values())[:MAX_RELEVANT_TOOLS_PER_TURN]
                if selected and (
                    attached_read_required
                    or selector.requires_tool_call(
                        request.user_input,
                        selected,
                        conversation_context=conversation_context,
                    )
                ):
                    request_context["_agent_tool_choice_required"] = True
            selected = _filter_unapproved_live_write_tools(
                runtime, request, selected,
            )
            if isinstance(request.context, dict):
                request.context["_agent_local_catalog"] = bool(selected) and all(
                    bool(getattr(item, "is_read_tool", False))
                    and {"local", "catalog"} <= set(getattr(item, "traits", ()) or ())
                    for item in selected
                )
                request.context["_agent_tool_namespaces"] = list(dict.fromkeys(
                    str(getattr(item, "namespace", "") or "")
                    for item in selected
                    if getattr(item, "namespace", None)
                ))
            if (
                not allow_clarification or not selected
                or selector.is_read_only_request(request.user_input, selected)
                or all(
                    "semantic_discovery" in (getattr(tool, "traits", ()) or ())
                    for tool in selected
                )
            ):
                return selected
            clarifications = [
                tool for tool in tools
                if "clarification" in (getattr(tool, "traits", ()) or ())
            ]
            return list({
                tool.name: tool for tool in (
                    *clarifications,
                    *selected[:max(0, MAX_RELEVANT_TOOLS_PER_TURN - len(clarifications))],
                )
            }.values())
        return select_tools

    @staticmethod
    def _request_validator(
        runtime: Any,
        security: RuntimeSecurity,
    ) -> Callable[[TurnRequest], str | None]:
        def validate_request(request: TurnRequest) -> str | None:
            context = request.context if isinstance(request.context, Mapping) else {}
            blueprint_error = _creation_blueprint_request_error(runtime, context)
            if blueprint_error:
                return blueprint_error
            platform_params = context.get("platform_params")
            limit_error = runtime._validate_request_limits(
                request.user_input, platform_params,
            )
            if limit_error:
                return limit_error
            protected_fields = security.validate_input_redline(platform_params)
            if protected_fields:
                return (
                    "请求包含禁止传入的凭证/账户配置字段："
                    + ", ".join(protected_fields)
                )
            text_fields = security.validate_text_redline(request.user_input)
            if text_fields:
                return (
                    "请求包含禁止传入的凭证字段："
                    + ", ".join(text_fields)
                )
            return None
        return validate_request



__all__ = [
    "AdApplicationAssembly",
]
