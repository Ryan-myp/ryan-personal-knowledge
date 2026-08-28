"""Persistence-neutral records used by the ad-agent domain.

These records deliberately contain no SQLite, SQL, or backend-specific
concerns.  A backend is responsible for serialising them; Runtime and
SessionManager should only depend on this module and ``PersistenceBackend``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CampaignRecord:
    """A provider Campaign snapshot scoped to one advertising account."""

    id: str
    platform: str
    campaign_id: str
    name: str
    status: str
    objective: str | None = None
    budget_daily: float | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    account_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["metadata"] = json.dumps(value["metadata"] or {})
        return value

    @classmethod
    def from_row(cls, row: Any) -> "CampaignRecord":
        if isinstance(row, dict):
            data = dict(row)
        else:
            columns = [
                "id", "platform", "campaign_id", "name", "status",
                "objective", "budget_daily", "created_at", "updated_at",
                "metadata", "account_id",
            ]
            data = dict(zip(columns, row))
        metadata = data.get("metadata")
        if isinstance(metadata, str):
            try:
                data["metadata"] = json.loads(metadata or "{}")
            except (TypeError, ValueError):
                data["metadata"] = {}
        elif not isinstance(metadata, dict):
            data["metadata"] = {}
        return cls(**data)


@dataclass
class ToolCallRecord:
    """An execution audit record without provider credentials."""

    id: str
    session_id: str
    turn_id: str
    tool_name: str
    platform: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None = None
    success: bool = True
    error: str | None = None
    started_at: str = ""
    ended_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["input_data"] = json.dumps(value["input_data"] or {})
        value["output_data"] = (
            json.dumps(value["output_data"])
            if value["output_data"] is not None else None
        )
        return value

    @classmethod
    def from_row(cls, row: Any) -> "ToolCallRecord":
        if isinstance(row, dict):
            data = dict(row)
        else:
            columns = [
                "id", "session_id", "turn_id", "tool_name", "platform",
                "input_data", "output_data", "success", "error",
                "started_at", "ended_at",
            ]
            data = dict(zip(columns, row))
        for key in ("input_data", "output_data"):
            value = data.get(key)
            if isinstance(value, str):
                try:
                    data[key] = json.loads(value)
                except (TypeError, ValueError):
                    data[key] = {} if key == "input_data" else None
            elif key == "input_data" and not isinstance(value, dict):
                data[key] = {}
        return cls(**data)
