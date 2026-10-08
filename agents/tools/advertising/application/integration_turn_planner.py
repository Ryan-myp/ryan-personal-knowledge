"""Provider-neutral planning helpers for the advertising Harness adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from agents.agent_harness import (
    ToolArgumentBinding,
    ToolCall,
)
from agents.agent_harness.core.execution_plan import ExecutionPlan


@dataclass(frozen=True)
class AdvertisingTurnPlan:
    """The application planning result consumed by the generic Agent loop."""

    calls: tuple[ToolCall, ...]
    tool_plan: Mapping[str, tuple[str, ...]]
    execution_plan: ExecutionPlan


@dataclass(frozen=True)
class AdvertisingRoutingResult:
    """Resolved intent and Tool directory before argument planning."""

    intent: Any
    routed: Mapping[str, list[Any]]
    policy_errors: tuple[str, ...] = ()


class AdvertisingTurnPlanner:
    """Keep Tool-call planning mechanics outside the model adapter."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def route(
        self,
        intent: Any,
        user_input: str,
        session_context: Any,
    ) -> AdvertisingRoutingResult:
        """Resolve an intent against the live Tool catalog and app policies."""
        self.owner._load_required_skills(intent.namespaces)
        routed = self.owner.intent_router.route(intent, self.owner.registry)
        errors = tuple(self.owner._validate_policies(intent) or ())
        if errors:
            return AdvertisingRoutingResult(intent, routed, errors)

        repair = getattr(self.owner.intent_parser, "repair_for_routing", None)
        for _attempt in range(2):
            requested = {
                self.owner._canonical_platform(item)
                for item in (getattr(intent, "namespaces", []) or [])
            }
            actual = {
                self.owner._canonical_platform(item) for item in routed
            }
            if routed and (not requested or actual == requested):
                break
            if not callable(repair):
                break
            repaired = repair(user_input, session_context, intent)
            if repaired is None:
                break
            intent = repaired
            self.owner._load_required_skills(intent.namespaces)
            routed = self.owner.intent_router.route(intent, self.owner.registry)
            errors = tuple(self.owner._validate_policies(intent) or ())
            if errors:
                break
        return AdvertisingRoutingResult(intent, routed, errors)

    def merge_platform_params(
        self,
        intent: Any,
        platform_params: Mapping[str, Any],
    ) -> Any:
        """Merge trusted request-scoped values into parsed intent data."""
        merged = dict(getattr(intent, "scoped_parameters", {}) or {})
        for platform, values in platform_params.items():
            canonical = self.owner._resolve_platform_identifier(platform)
            target = next(
                (
                    existing
                    for existing in merged
                    if self.owner._resolve_platform_identifier(existing) == canonical
                ),
                canonical or str(platform),
            )
            if (
                isinstance(values, Mapping)
                and isinstance(merged.get(target), Mapping)
            ):
                merged[target] = {**dict(merged[target]), **dict(values)}
            else:
                merged[target] = (
                    dict(values) if isinstance(values, Mapping) else values
                )
        intent.scoped_parameters = merged
        if len(platform_params) > 1:
            known = {
                self.owner._canonical_platform(item)
                for item in (getattr(intent, "namespaces", []) or [])
            }
            for platform in platform_params:
                canonical = self.owner._resolve_platform_identifier(str(platform))
                if canonical not in known:
                    intent.namespaces.append(canonical)
                    known.add(canonical)
        return intent

    def build_tool_calls(
        self,
        routed: Mapping[str, list[Any]],
        intent: Any,
        session_context: Any,
    ) -> list[ToolCall]:
        """Build validated provider-neutral Tool Calls from routed definitions."""
        calls: list[ToolCall] = []
        for tools in routed.values():
            for definition in tools:
                arguments = self.owner.input_builder.build(
                    definition,
                    intent,
                    definition.namespace,
                    session_context,
                )
                scoped = getattr(intent, "scoped_parameters", {}) or {}
                platform_values = self._scoped_values_for(
                    scoped,
                    str(definition.namespace),
                )
                if isinstance(platform_values, Mapping):
                    properties = getattr(
                        getattr(definition, "input_schema", None),
                        "properties",
                        {},
                    ) or {}
                    for field in (
                        getattr(definition, "scope_fields", ()) or (
                            "account_id",
                            "ad_account_id",
                            "advertiser_id",
                            "customer_id",
                        )
                    ):
                        if (
                            field in properties
                            and platform_values.get(field) not in (None, "")
                        ):
                            arguments[field] = platform_values[field]
                resolver = getattr(self.owner, "account_resolver", None)
                resolve_account = getattr(resolver, "resolve", None)
                if callable(resolve_account):
                    properties = getattr(
                        getattr(definition, "input_schema", None),
                        "properties",
                        {},
                    ) or {}
                    scope_fields = tuple(
                        getattr(definition, "scope_fields", ()) or (
                            "account_id",
                            "ad_account_id",
                            "advertiser_id",
                            "customer_id",
                        )
                    )
                    resolved_account = resolve_account(
                        intent,
                        str(definition.namespace),
                        [definition],
                        getattr(session_context, "account_id", None),
                        allow_automatic_account=not bool(
                            getattr(definition, "is_write_tool", False)
                        ),
                    )
                    multi_namespace = len({
                        self.owner._canonical_platform(namespace)
                        for namespace in (getattr(intent, "namespaces", []) or [])
                    }) > 1
                    for field in scope_fields:
                        if field not in properties:
                            continue
                        explicit_scoped = (
                            isinstance(platform_values, Mapping)
                            and platform_values.get(field) not in (None, "")
                        )
                        if resolved_account not in (None, "") and (
                            arguments.get(field) in (None, "")
                            or (multi_namespace and not explicit_scoped)
                        ):
                            arguments[field] = str(resolved_account)
                        elif multi_namespace and not explicit_scoped:
                            # Do not let InputBuilder's session fallback leak
                            # a different namespace's account into this call.
                            arguments.pop(field, None)
                for key in (
                    "_missing_params",
                    "_unknown_params",
                    "_selection_errors",
                ):
                    arguments.pop(key, None)
                calls.append(ToolCall(
                    id=f"call-{len(calls) + 1}",
                    name=definition.name,
                    arguments=arguments,
                ))
        return calls

    def build_plan(
        self,
        routed: Mapping[str, list[Any]],
        intent: Any,
        session_context: Any,
    ) -> AdvertisingTurnPlan:
        """Return one immutable plan contract for the current routed intent."""
        calls = tuple(self.build_tool_calls(routed, intent, session_context))
        tool_plan = {
            str(platform): tuple(item.name for item in definitions)
            for platform, definitions in routed.items()
        }
        execution_plan = ExecutionPlan.from_tool_plan(
            intent,
            routed,
            canonicalize=self.owner._canonical_platform,
        )
        calls = self._bind_plan_dependencies(calls, execution_plan, routed)
        return AdvertisingTurnPlan(
            calls=calls,
            tool_plan=tool_plan,
            execution_plan=execution_plan,
        )

    @staticmethod
    def _bind_plan_dependencies(
        calls: tuple[ToolCall, ...],
        execution_plan: ExecutionPlan,
        routed: Mapping[str, list[Any]],
    ) -> tuple[ToolCall, ...]:
        """Translate resource edges into Harness dependencies and input bindings."""
        definitions = [
            definition
            for platform_tools in routed.values()
            for definition in platform_tools
        ]
        if len(calls) != len(execution_plan.nodes) or len(calls) != len(definitions):
            raise ValueError("Tool plan and execution plan are inconsistent")
        call_ids = {
            node.node_id: call.id
            for node, call in zip(execution_plan.nodes, calls)
        }
        node_by_id = {node.node_id: node for node in execution_plan.nodes}
        call_by_id = {
            node.node_id: call
            for node, call in zip(execution_plan.nodes, calls)
        }
        definition_by_id = {
            node.node_id: definition
            for node, definition in zip(execution_plan.nodes, definitions)
        }
        bound: list[ToolCall] = []
        for node, call in zip(execution_plan.nodes, calls):
            dependencies = tuple(
                call_ids[item] for item in node.depends_on
            )
            child_definition = definition_by_id[node.node_id]
            target_field = str(
                getattr(child_definition, "parent_resource_id_field", "") or ""
            )
            bindings: list[ToolArgumentBinding] = []
            if target_field and not call.arguments.get(target_field):
                for dependency_id in node.depends_on:
                    parent_node = node_by_id[dependency_id]
                    parent_definition = definition_by_id[dependency_id]
                    if (
                        parent_node.resource_type != node.parent_resource_type
                    ):
                        continue
                    source_field = str(
                        getattr(parent_definition, "resource_id_field", "") or ""
                    )
                    if source_field:
                        bindings.append(ToolArgumentBinding(
                            target_field=target_field,
                            source_call_id=call_by_id[dependency_id].id,
                            source_path=f"data.{source_field}",
                        ))
                    break
            bound.append(replace(
                call,
                depends_on=dependencies,
                argument_bindings=tuple(bindings),
            ))
        return tuple(bound)

    def _scoped_values_for(
        self,
        scoped: Any,
        namespace: str,
    ) -> Mapping[str, Any] | None:
        if not isinstance(scoped, Mapping):
            return None
        target = self.owner._resolve_platform_identifier(namespace)
        for key, values in scoped.items():
            if self.owner._resolve_platform_identifier(str(key)) == target:
                return values if isinstance(values, Mapping) else None
        return None


__all__ = [
    "AdvertisingRoutingResult",
    "AdvertisingTurnPlan",
    "AdvertisingTurnPlanner",
]
