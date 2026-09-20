"""Application-neutral resource scope contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class ResourceScope:
    """One resolved resource boundary used by policy and audit layers."""

    scope_type: str
    scope_id: str
    namespace: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        scope_type = str(self.scope_type or "").strip()
        scope_id = str(self.scope_id or "").strip()
        if not scope_type:
            raise ValueError("scope_type must not be empty")
        if not scope_id:
            raise ValueError("scope_id must not be empty")
        object.__setattr__(self, "scope_type", scope_type)
        object.__setattr__(self, "scope_id", scope_id)
        object.__setattr__(self, "namespace", str(self.namespace or "").strip())
        object.__setattr__(self, "source", str(self.source or "").strip())

    def to_dict(self) -> dict[str, str]:
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "namespace": self.namespace,
            "source": self.source,
        }


class ScopeResolver(Protocol):
    """Resolve an application resource scope without authorizing it."""

    def resolve_scope(
        self,
        request: Any,
        tools: Sequence[Any],
        fallback: Any = None,
    ) -> ResourceScope | None:
        ...


class ScopePolicy(Protocol):
    """Authorize an already-resolved scope at the application boundary."""

    def validate_scope(
        self,
        scope: ResourceScope,
        *,
        principal: Any = None,
        tool: Any = None,
        effect: Any = None,
    ) -> tuple[bool, str]:
        ...


__all__ = ["ResourceScope", "ScopePolicy", "ScopeResolver"]
