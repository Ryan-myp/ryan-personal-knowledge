"""Application-neutral context query contracts.

The Runtime uses this small value object to ask any advisory context source
for bounded records. Domain adapters may map ``filters`` to their own
metadata, but the Runtime does not need to know whether the source is a Wiki,
memory store, document index, or another context system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ContextQuery:
    """Immutable, bounded query passed to an advisory context source."""

    text: str
    namespaces: tuple[str, ...] = ()
    intent_type: str = ""
    filters: Mapping[str, Any] = field(default_factory=dict)
    tenant_id: str = "default"
    limit: int = 4
    max_excerpt_chars: int = 1200

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", str(self.text or "").strip()[:12_000])
        object.__setattr__(
            self,
            "namespaces",
            tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in (self.namespaces or ())
                    if str(item).strip()
                )
            ),
        )
        object.__setattr__(self, "intent_type", str(self.intent_type or "").strip())
        object.__setattr__(
            self,
            "tenant_id",
            str(self.tenant_id or "default").strip() or "default",
        )
        normalized_filters: dict[str, Any] = {}
        for key, value in (self.filters or {}).items():
            name = str(key).strip()
            if not name:
                continue
            if isinstance(value, (list, tuple, set, frozenset)):
                normalized_filters[name] = tuple(
                    str(item).strip() for item in value if str(item).strip()
                )
            else:
                normalized_filters[name] = value
        object.__setattr__(self, "filters", normalized_filters)
        object.__setattr__(self, "limit", max(0, min(int(self.limit), 100)))
        object.__setattr__(
            self,
            "max_excerpt_chars",
            max(0, min(int(self.max_excerpt_chars), 1800)),
        )


__all__ = ["ContextQuery"]
