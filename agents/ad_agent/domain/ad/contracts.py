"""Advertising-domain contracts built on top of the generic Agent Core.

These models describe the advertising application's provider coverage and
resource hierarchy.  They intentionally do not belong to ``core``: a generic
Agent can execute a resource graph without knowing what an ad resource is.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ...core.interfaces import ToolSourceRuntime


class AdFormatCoverage(Enum):
    """Evidence level for an advertising format contract."""

    SUPPORTED_DRY_RUN = "supported_dry_run"
    PARTIAL_DRY_RUN = "partial_dry_run"
    DECLARED_ONLY = "declared_only"
    PLANNED = "planned"


@dataclass
class AdToolSourceRuntime(ToolSourceRuntime):
    """Advertising extension data returned by an ad Tool Source."""

    ad_format_catalogs: list[dict[str, Any]] = None
    creation_blueprints: list[Any] = None

    def __post_init__(self) -> None:
        self.ad_format_catalogs = list(self.ad_format_catalogs or [])
        self.creation_blueprints = list(self.creation_blueprints or [])


RESOURCE_RESULT_STATUSES = frozenset({
    "planned", "running", "succeeded", "failed", "skipped", "unknown",
    "unsupported", "awaiting_confirmation",
})


@dataclass(frozen=True)
class ResourceRef:
    """Advertising resource identity within a provider account hierarchy."""

    platform: str
    account_id: str
    resource_type: str
    resource_id: str

    def __post_init__(self) -> None:
        values = {
            "platform": str(self.platform or "").strip().lower(),
            "account_id": str(self.account_id or "").strip(),
            "resource_type": str(self.resource_type or "").strip().lower(),
            "resource_id": str(self.resource_id or "").strip(),
        }
        if not all(values.values()):
            raise ValueError(
                "ResourceRef requires platform, account_id, resource_type and resource_id"
            )
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, str]:
        return {
            "platform": self.platform,
            "account_id": self.account_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
        }


@dataclass
class ResourceResult:
    """Item-level result for one advertising resource operation."""

    sequence: int
    platform: str
    resource_type: str
    tool_name: str
    status: str
    parent_resource_type: Optional[str] = None
    account_id: Optional[str] = None
    parent_sequence: Optional[int] = None
    parent_resource_id: Optional[str] = None
    provider_resource_id: Optional[str] = None
    logical_resource_id: Optional[str] = None
    local_resource_id: Optional[str] = None
    error: Optional[str] = None
    simulated: bool = False

    def __post_init__(self) -> None:
        if self.status not in RESOURCE_RESULT_STATUSES:
            raise ValueError(f"Unsupported resource result status: {self.status}")

    @property
    def resource_ref(self) -> Optional[ResourceRef]:
        resource_id = (
            self.provider_resource_id
            or self.logical_resource_id
            or self.local_resource_id
        )
        if not resource_id or not self.account_id:
            return None
        return ResourceRef(
            platform=self.platform,
            account_id=self.account_id,
            resource_type=self.resource_type,
            resource_id=resource_id,
        )

    @property
    def parent_ref(self) -> Optional[ResourceRef]:
        if not self.parent_resource_id or not self.account_id or not self.parent_resource_type:
            return None
        return ResourceRef(
            platform=self.platform,
            account_id=self.account_id,
            resource_type=self.parent_resource_type,
            resource_id=self.parent_resource_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "platform": self.platform,
            "resource_type": self.resource_type,
            "parent_resource_type": self.parent_resource_type,
            "tool": self.tool_name,
            "status": self.status,
            "account_id": self.account_id,
            "parent_sequence": self.parent_sequence,
            "parent_resource_id": self.parent_resource_id,
            "provider_resource_id": self.provider_resource_id,
            "logical_resource_id": self.logical_resource_id,
            "local_resource_id": self.local_resource_id,
            "resource_ref": self.resource_ref.to_dict() if self.resource_ref else None,
            "parent_ref": self.parent_ref.to_dict() if self.parent_ref else None,
            "error": self.error,
            "simulated": self.simulated,
        }


__all__ = [
    "AdFormatCoverage",
    "AdToolSourceRuntime",
    "RESOURCE_RESULT_STATUSES",
    "ResourceRef",
    "ResourceResult",
]
