"""External-system- and business-neutral policy extension contracts.

Policies constrain an Agent turn without becoming a second router or
execution engine.  A business Skill can implement this contract to filter
namespaces and validate domain rules; AgentRuntime only invokes the generic
methods and never knows the policy's business vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from .namespace import normalize_namespace


@dataclass(frozen=True)
class PolicyContext:
    """Namespace policy context used by selectors and extensions."""

    name: str = ""
    allowed_namespaces: tuple[str, ...] = ()
    denied_namespaces: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)

    def is_namespace_allowed(self, namespace: str) -> bool:
        normalized = normalize_namespace(namespace)
        denied = {
            normalize_namespace(value) for value in self.denied_namespaces
        }
        allowed = {
            normalize_namespace(value) for value in self.allowed_namespaces
        }
        return normalized not in denied and (
            not allowed or normalized in allowed
        )

    def filter_namespaces(self, namespaces: Sequence[str]) -> list[str]:
        return [
            namespace for namespace in namespaces
            if self.is_namespace_allowed(namespace)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "allowed_namespaces": list(self.allowed_namespaces),
            "denied_namespaces": list(self.denied_namespaces),
            "attributes": dict(self.attributes),
        }


class RuntimePolicy(Protocol):
    """Optional policy supplied by a Skill or embedding application."""

    name: str

    def filter_namespaces(self, namespaces: Sequence[str]) -> list[str]:
        """Return the subset of requested namespaces allowed by this policy."""

    def validate_intent(self, intent: Any) -> list[str]:
        """Return blocking policy errors for a parsed intent."""

    def context_metadata(self) -> dict[str, Any]:
        """Return bounded, non-secret metadata for model context."""


def apply_policies(
    policies: Sequence[RuntimePolicy],
    namespaces: Sequence[str],
) -> list[str]:
    """Apply all policy namespace filters in declaration order."""
    result = list(namespaces)
    for policy in policies:
        filter_namespaces = getattr(policy, "filter_namespaces", None)
        if callable(filter_namespaces):
            result = list(filter_namespaces(result))
    return result


def validate_policies(
    policies: Sequence[RuntimePolicy],
    intent: Any,
) -> list[str]:
    """Collect deterministic policy errors without interpreting their fields."""
    errors: list[str] = []
    for policy in policies:
        validate_intent = getattr(policy, "validate_intent", None)
        if not callable(validate_intent):
            continue
        errors.extend(str(error) for error in (validate_intent(intent) or []) if error)
    return list(dict.fromkeys(errors))


def policy_metadata(policies: Sequence[RuntimePolicy]) -> dict[str, Any]:
    """Build bounded model-facing metadata from policy-owned declarations."""
    result: dict[str, Any] = {}
    for policy in policies:
        metadata = getattr(policy, "context_metadata", None)
        if not callable(metadata):
            continue
        value = metadata()
        if isinstance(value, dict):
            result.update(value)
    return result
