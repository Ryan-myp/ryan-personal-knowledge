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


@dataclass
class ConversationMessageRecord:
    """One durable, sanitized user/assistant message in a session."""

    message_id: str
    session_id: str
    turn_id: str
    role: str
    content: str
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> "ConversationMessageRecord":
        if isinstance(row, dict):
            data = dict(row)
        else:
            columns = ["message_id", "session_id", "turn_id", "role", "content", "created_at"]
            data = dict(zip(columns, row))
        return cls(**data)


@dataclass
class KnowledgeDocumentRecord:
    """A tenant-scoped, versioned Markdown Wiki document snapshot."""

    document_id: str
    tenant_id: str
    title: str
    content: str
    platform: str = "all"
    layer: str = "business"
    knowledge_type: str = "general"
    source: str = "user"
    source_ref: str = ""
    version: str = "1.0.0"
    confidence: float = 0.8
    tags: list[str] = field(default_factory=list)
    status: str = "draft"
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    published_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["tags"] = list(self.tags or [])
        return value

    @classmethod
    def from_row(cls, row: Any) -> "KnowledgeDocumentRecord":
        data = dict(row) if isinstance(row, dict) else dict(row)
        tags = data.get("tags")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags or "[]")
            except (TypeError, ValueError):
                tags = []
        data["tags"] = tags if isinstance(tags, list) else []
        return cls(**data)


@dataclass
class TaskRecord:
    """Durable, backend-neutral record for one asynchronous Agent task.

    ``payload`` and ``metadata`` are already sanitized by the trusted
    submission boundary.  In particular, this record never carries provider
    credentials or executable callbacks; a worker resolves ``kind`` only
    against handlers registered by the embedding Runtime.
    """

    task_id: str
    tenant_id: str
    user_id: str
    kind: str
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    idempotency_key: str | None = None
    workflow_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    lease_owner: str | None = None
    lease_expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        # Return copies so an API caller cannot mutate an in-memory record.
        value["payload"] = json.loads(json.dumps(self.payload or {}))
        value["result"] = (
            json.loads(json.dumps(self.result))
            if self.result is not None else None
        )
        value["metadata"] = json.loads(json.dumps(self.metadata or {}))
        return value

    @classmethod
    def from_row(cls, row: Any) -> "TaskRecord":
        if isinstance(row, dict):
            data = dict(row)
        else:
            columns = [
                "task_id", "tenant_id", "user_id", "kind", "status", "payload",
                "result", "error", "idempotency_key", "workflow_id", "metadata",
                "created_at", "updated_at", "started_at", "finished_at",
                "lease_owner", "lease_expires_at",
            ]
            data = dict(zip(columns, row))
        for key, default in (
            ("payload", {}), ("result", None), ("metadata", {}),
        ):
            value = data.get(key)
            if isinstance(value, str):
                try:
                    data[key] = json.loads(value or "null")
                except (TypeError, ValueError):
                    data[key] = default
            elif value is None and default == {}:
                data[key] = {}
        return cls(**data)
