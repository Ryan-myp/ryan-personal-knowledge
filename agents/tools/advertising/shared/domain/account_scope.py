"""Account candidates shared by Tool authorization and Provider execution."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .security import ACCOUNT_SCOPE_FIELDS


def tool_account_fields(tool: Any) -> tuple[str, ...]:
    """Honor published scope fields, then use the advertising account aliases."""
    return tuple(getattr(tool, "scope_fields", ()) or ACCOUNT_SCOPE_FIELDS)


def tool_call_accounts(
    tool: Any,
    platform: str,
    arguments: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    normalize_namespace: Callable[[str], str],
) -> tuple[Any, Any]:
    """Resolve candidates without granting authority or selecting writes."""
    fields = tool_account_fields(tool)
    argument_account = next((
        arguments.get(field) for field in fields
        if arguments.get(field) not in (None, "")
    ), None)
    platform_params = context.get("platform_params")
    scoped_account = None
    if isinstance(platform_params, Mapping):
        scoped_account = next((
            values[field]
            for namespace, values in platform_params.items()
            if normalize_namespace(namespace) == normalize_namespace(platform)
            and isinstance(values, Mapping)
            for field in fields
            if values.get(field) not in (None, "")
        ), None)
    namespaces = (
        list(platform_params) if isinstance(platform_params, Mapping) and platform_params
        else context.get("_agent_tool_namespaces", ())
    )
    multiple_namespaces = len({
        normalize_namespace(namespace) for namespace in (namespaces or ())
    }) > 1
    request_account = scoped_account or (
        None if multiple_namespaces else context.get("account_id")
    )
    # History supplies a read candidate, never authority. An explicit new
    # argument wins, and every call must still pass current account policy.
    remembered = context.get("_agent_read_account_scopes")
    if (
        not request_account and not argument_account
        and bool(getattr(tool, "is_read_tool", False))
        and getattr(tool, "scope_required", None) is not False
        and isinstance(remembered, Mapping)
    ):
        request_account = remembered.get(normalize_namespace(platform))
    return request_account, argument_account
