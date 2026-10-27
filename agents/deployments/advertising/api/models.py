"""Pydantic request models for the advertising HTTP API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field
from agents.agent_platform.evals.regression import RegressionAssertions
from agents.agent_harness.core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS


class AccountSelectionResponse(BaseModel):
    type: Literal["account_selection"]
    turn_id: str = Field(min_length=1, max_length=200)
    tool_name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=200)


class ChatRequest(BaseModel):
    user_input: str = Field(default="", max_length=12_000)
    session_id: Optional[str] = None
    user_id: str = Field(default="web_user", min_length=1, max_length=200)
    account_id: str = Field(default="", max_length=200)
    interaction_response: Optional[AccountSelectionResponse] = None
    media_ids: list[str] = Field(default_factory=list, max_length=5)
    confirmed: bool = False
    confirmation_payload: Optional[dict] = None
    platform_params: Optional[dict] = None
    creation_blueprint_id: Optional[str] = Field(default=None, max_length=200)
    creation_blueprint_version: Optional[str] = Field(default=None, max_length=32)
    creation_template_id: Optional[str] = Field(default=None, max_length=240)
    execution_mode: Optional[Literal["dry_run", "live"]] = None
    tool_allowlist: Optional[list[str]] = Field(default=None, max_length=128)


class ChatCancelRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)


class ExecutionModeRequest(BaseModel):
    mode: str = Field(min_length=1, max_length=16)


class SessionDeleteRequest(BaseModel):
    session_ids: list[str] = Field(min_length=1, max_length=50)


class SessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=32)


class ConversationFeedbackRequest(BaseModel):
    rating: Literal["positive", "negative"]
    reason: Optional[str] = Field(default=None, max_length=1000)


class ConversationFeedbackReviewRequest(BaseModel):
    review_status: Literal["candidate", "dismissed"]
    expected_behavior: str = Field(default="", max_length=2000)
    assertions: RegressionAssertions = Field(default_factory=RegressionAssertions)


class TaskSubmitRequest(BaseModel):
    kind: str = Field(default="agent.turn", min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=200)


class TaskRecoveryRequest(BaseModel):
    recovery_reference: str = Field(min_length=1, max_length=255)
    provider_verified: bool = False


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=12_000)
    cron_expression: str = Field(min_length=9, max_length=120)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    session_id: Optional[str] = Field(default=None, max_length=200)
    account_id: Optional[str] = Field(default=None, max_length=200)
    platform_params: Optional[dict] = None


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    prompt: Optional[str] = Field(default=None, min_length=1, max_length=12_000)
    cron_expression: Optional[str] = Field(
        default=None, min_length=9, max_length=120,
    )
    timezone: Optional[str] = Field(default=None, min_length=1, max_length=80)


class MemoryWriteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    kind: str = Field(default="semantic", min_length=1, max_length=32)
    session_id: Optional[str] = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=20)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    memory_key: Optional[str] = Field(default=None, max_length=120)


class KnowledgeDocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=60_000)
    platform: str = Field(default="all", max_length=64)
    layer: str = Field(default="business", max_length=32)
    knowledge_type: str = Field(default="general", max_length=64)
    source: str = Field(default="user", max_length=200)
    source_ref: str = Field(default="", max_length=500)
    version: str = Field(default="1.0.0", max_length=80)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    wiki_type: str = Field(default="concept", max_length=32)
    derived_from: str = Field(default="", max_length=200)
    raw_sha256: str = Field(default="", max_length=128)
    wikilinks: list[str] = Field(default_factory=list, max_length=30)


class RawKnowledgeUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=120_000)
    media_type: str = Field(default="text/markdown", max_length=100)
    source_ref: str = Field(default="", max_length=500)


class CreationTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    provider: str = Field(default="", max_length=64)
    blueprint_id: str = Field(min_length=1, max_length=200)
    blueprint_version: Optional[str] = Field(default=None, max_length=80)
    ad_format: str = Field(default="", max_length=100)
    scope_type: Literal["general", "account", "region"] = "general"
    account_id: str = Field(default="", max_length=200)
    region: str = Field(default="", max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=20)
    values: dict[str, object] = Field(default_factory=dict)
    status: Literal["active", "inactive", "archived"] = "active"
    is_default: bool = False


class CreationTemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    blueprint_id: Optional[str] = Field(default=None, max_length=200)
    blueprint_version: Optional[str] = Field(default=None, max_length=80)
    provider: Optional[str] = Field(default=None, max_length=64)
    ad_format: Optional[str] = Field(default=None, max_length=100)
    scope_type: Optional[Literal["general", "account", "region"]] = None
    account_id: Optional[str] = Field(default=None, max_length=200)
    region: Optional[str] = Field(default=None, max_length=120)
    tags: Optional[list[str]] = Field(default=None, max_length=20)
    values: Optional[dict[str, object]] = None
    status: Optional[Literal["active", "inactive", "archived"]] = None
    is_default: Optional[bool] = None


class CreationTemplateDuplicateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)


class PluginPackageRequest(BaseModel):
    manifest: dict[str, object]
    files: dict[str, object]


class MCPServerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    endpoint: str = Field(min_length=10, max_length=2048)
    transport: Literal["streamable_http"] = "streamable_http"
    auth_type: Literal["none", "bearer", "api_key"] = "none"
    credential_ref: Optional[str] = Field(default=None, max_length=128)
    auth_header: str = Field(default="", max_length=64)
    timeout_seconds: float = Field(
        default=DEFAULT_EXECUTION_TIMEOUT_SECONDS, ge=1.0,
        le=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    )


class MCPServerPatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    endpoint: Optional[str] = Field(default=None, min_length=10, max_length=2048)
    transport: Optional[Literal["streamable_http"]] = None
    auth_type: Optional[Literal["none", "bearer", "api_key"]] = None
    credential_ref: Optional[str] = Field(default=None, max_length=128)
    auth_header: Optional[str] = Field(default=None, max_length=64)
    timeout_seconds: Optional[float] = Field(
        default=None, ge=1.0, le=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    )


class MCPValidationRequest(BaseModel):
    checks: list[Literal[
        "all", "configuration", "connectivity", "tool_schema", "policy"
    ]] = Field(default_factory=lambda: ["all"], max_length=5)


class MCPToolTestRequest(BaseModel):
    input: dict = Field(default_factory=dict)
    account_id: Optional[str] = Field(default=None, max_length=200)


class MCPToolMetadataPatchRequest(BaseModel):
    intent_types: Optional[list[str]] = Field(default=None, max_length=32)
    intent_aliases: Optional[list[str]] = Field(default=None, max_length=32)
    skill_refs: Optional[list[str]] = Field(default=None, max_length=32)
    action: Optional[str] = Field(default=None, min_length=1, max_length=64)
    resource_type: Optional[str] = Field(default=None, min_length=1, max_length=191)
    resource_id_field: Optional[str] = Field(default=None, max_length=128)
    readback_tool: Optional[str] = Field(default=None, max_length=128)
    idempotency_key_field: Optional[str] = Field(default=None, max_length=128)
    required_permissions: Optional[list[str]] = Field(default=None, max_length=16)
    traits: Optional[list[str]] = Field(default=None, max_length=32)
    trusted_read: Optional[bool] = None
    live_write_enabled: Optional[bool] = None


class BlueprintEvaluationRequest(BaseModel):
    values: dict[str, object] = Field(default_factory=dict)
    previous_values: Optional[dict[str, object]] = None
    changed_fields: Optional[list[str]] = None
    version: Optional[str] = Field(None, max_length=80)


class BlueprintResolveRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    selector_values: dict[str, object] = Field(default_factory=dict)
    values: dict[str, object] = Field(default_factory=dict)
    version: Optional[str] = Field(None, max_length=80)


class CreationImportPreviewRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    attachment_id: str = Field(min_length=1, max_length=128)
    blueprint_id: str = Field(min_length=1, max_length=200)
    version: Optional[str] = Field(default=None, max_length=80)
    sheet_name: Optional[str] = Field(default=None, max_length=120)
    column_mapping: dict[str, str] = Field(default_factory=dict, max_length=80)


class SkillVersionRequest(BaseModel):
    version: str = Field(min_length=5, max_length=80)
    files: dict[str, object]


class ChatStreamRequest(BaseModel):
    user_input: str = Field(default="", max_length=12_000)
    session_id: Optional[str] = None
    user_id: str = Field(default="web_user", min_length=1, max_length=200)
    account_id: str = Field(default="", max_length=200)
    interaction_response: Optional[AccountSelectionResponse] = None
    media_ids: list[str] = Field(default_factory=list, max_length=5)
    confirmed: bool = False
    confirmation_payload: Optional[dict] = None
    platform_params: Optional[dict] = None
    creation_blueprint_id: Optional[str] = Field(default=None, max_length=200)
    creation_blueprint_version: Optional[str] = Field(default=None, max_length=32)
    creation_template_id: Optional[str] = Field(default=None, max_length=240)
    execution_mode: Optional[Literal["dry_run", "live"]] = None
    tool_allowlist: Optional[list[str]] = Field(default=None, max_length=128)


class WorkflowReconcileRequest(BaseModel):
    observations: object


__all__ = [
    "BlueprintEvaluationRequest",
    "BlueprintResolveRequest",
    "ChatCancelRequest",
    "ChatRequest",
    "ChatStreamRequest",
    "ConversationFeedbackRequest",
    "ConversationFeedbackReviewRequest",
    "CreationImportPreviewRequest",
    "CreationTemplateDuplicateRequest",
    "CreationTemplateRequest",
    "CreationTemplateUpdateRequest",
    "ExecutionModeRequest",
    "KnowledgeDocumentRequest",
    "MCPServerPatchRequest",
    "MCPServerRequest",
    "MCPToolMetadataPatchRequest",
    "MCPToolTestRequest",
    "MCPValidationRequest",
    "MemoryWriteRequest",
    "PluginPackageRequest",
    "RawKnowledgeUploadRequest",
    "ScheduleCreateRequest",
    "ScheduleUpdateRequest",
    "SessionDeleteRequest",
    "SessionRenameRequest",
    "SkillVersionRequest",
    "TaskRecoveryRequest",
    "TaskSubmitRequest",
    "WorkflowReconcileRequest",
]
