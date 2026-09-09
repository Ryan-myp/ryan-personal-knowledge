"""Small helpers for provider-owned API method Tools.

Provider capabilities own the endpoint catalog.  This module only removes the
repetitive, provider-neutral plumbing needed to turn a fixed client method
into a ToolDefinition.  It never accepts a method name from user input.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from ..core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolSchema,
)
from .base import ProviderMethodHandler


ArgumentBuilder = Callable[[Any, dict[str, Any]], tuple[tuple[Any, ...], dict[str, Any]]]


def account_from(ctx: Any, data: dict[str, Any], *fields: str) -> str:
    """Resolve a provider account from Runtime context, then tool input."""
    if getattr(ctx, "account_id", None):
        return str(ctx.account_id)
    for field in fields:
        value = data.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def value_from(data: dict[str, Any], field: str, default: Any = None) -> Any:
    value = data.get(field)
    return default if value is None else value


def method_tool(
    *,
    namespace: str,
    skill: str,
    name: str,
    description: str,
    method_name: str,
    result_key: str,
    properties: dict[str, Any],
    argument_builder: ArgumentBuilder,
    required: Optional[Iterable[str]] = None,
    action: str = "",
    resource_type: str = "",
    parent_resource_type: Optional[str] = None,
    resource_id_field: Optional[str] = None,
    parent_resource_id_field: Optional[str] = None,
    intent_types: Optional[Iterable[str]] = None,
    intent_aliases: Optional[Iterable[str]] = None,
    activation_rules: Optional[Iterable[dict[str, Any]]] = None,
    traits: Optional[Iterable[str]] = None,
    write: bool = False,
    live_support: Optional[bool] = None,
    capability_required: Optional[Iterable[str]] = None,
    capability_any_of: Optional[Iterable[Iterable[str]]] = None,
    capability_exactly_one_of: Optional[Iterable[Iterable[str]]] = None,
    conditional_rules: Optional[Iterable[dict[str, Any]]] = None,
    additional_properties: bool = False,
    contract_version: str = "1",
    integration_api_version: Optional[str] = None,
    result_items_key: Optional[str] = None,
    result_id_fields: Optional[Iterable[str]] = None,
    related_resource_type: Optional[str] = None,
    related_resource_id_fields: Optional[Iterable[str]] = None,
    timeout_seconds: float = 30.0,
    max_output_bytes: int = 1_000_000,
    required_permissions: Optional[Iterable[str]] = None,
    readback_tool: Optional[str] = None,
) -> tuple[ToolDefinition, ProviderMethodHandler]:
    """Build one provider-owned Tool and its fixed method handler."""
    effect = ToolEffect.WRITE if write else ToolEffect.READ
    if live_support is None:
        live_support = False if write else True
    definition = ToolDefinition(
        name=name,
        skill=skill,
        namespace=namespace,
        description=description,
        input_schema=ToolSchema(
            required=list(required or []),
            properties=dict(properties),
            capability_required=list(capability_required or []),
            capability_any_of=[list(group) for group in (capability_any_of or [])],
            capability_exactly_one_of=[
                list(group) for group in (capability_exactly_one_of or [])
            ],
            conditional_rules=[dict(rule) for rule in (conditional_rules or [])],
            additional_properties=bool(additional_properties),
        ),
        action=action,
        resource_type=resource_type,
        parent_resource_type=parent_resource_type,
        resource_id_field=resource_id_field,
        parent_resource_id_field=parent_resource_id_field,
        intent_types=list(intent_types or []),
        intent_aliases=list(intent_aliases or []),
        activation_rules=[dict(rule) for rule in (activation_rules or [])],
        risk_level=RiskLevel.MEDIUM if write else RiskLevel.LOW,
        effect_class=effect,
        replay_policy=ReplayPolicy.UNSAFE if write else ReplayPolicy.SAFE,
        traits=list(traits) if traits is not None else (["write"] if write else ["read"]),
        live_support=live_support,
        contract_version=contract_version,
        integration_api_version=integration_api_version,
        result_items_key=result_items_key,
        result_id_fields=list(result_id_fields or []),
        related_resource_type=related_resource_type,
        related_resource_id_fields=list(related_resource_id_fields or []),
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        required_permissions=list(required_permissions or []),
        readback_tool=readback_tool,
    )
    handler = ProviderMethodHandler(
        None,
        method_name,
        result_key,
        argument_builder,
        write=write,
    )
    return definition, handler


def bind_provider_method(
    tool: tuple[ToolDefinition, ProviderMethodHandler], client: Any
) -> tuple[ToolDefinition, ProviderMethodHandler]:
    """Bind a capability's injected client without rebuilding its contract."""
    definition, handler = tool
    handler.client = client
    return definition, handler
