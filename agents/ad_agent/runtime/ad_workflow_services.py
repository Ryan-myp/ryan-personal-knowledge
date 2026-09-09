"""Workflow recovery and provider read-back application services.

Recovery owns durable state transitions and invokes only registered read Tools
through the Runtime security boundary. It never replays a write handler.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from ..domain.ad.auth import RequestPrincipal
from ..core.interfaces import (
    ReconciliationContext,
    ReconciliationObservation,
    ToolContext,
    ToolResult,
    ExecutionMode,
)
from .reconciliation import ToolReadbackReconciler

logger = logging.getLogger(__name__)


class AdWorkflowServices:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def get_workflow(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Read a durable workflow while enforcing its owning user boundary."""
        if not self.runtime._session_manager:
            return None
        workflow = self.runtime._session_manager.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if workflow:
            return workflow
        # Preserve the public distinction between “not found” and an
        # authenticated caller crossing an owner boundary, but compare only
        # normalized columns—not metadata copies.
        if user_id is not None or tenant_id is not None:
            existing = self.runtime._session_manager.get_workflow(workflow_id)
            if existing:
                if user_id is not None:
                    session = self.runtime._session_manager.get_session(
                        existing.get("session_id")
                    ) or {}
                    if str(session.get("user_id") or "") != str(user_id):
                        raise PermissionError("workflow belongs to a different user")
                if tenant_id is not None and str(existing.get("tenant_id") or "default") != str(tenant_id or "default"):
                    raise PermissionError("workflow belongs to a different tenant")
        return None

    def get_workflow_resume_plan(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Return a safe replay plan without executing any provider operation.

        Recovery is deliberately an explicit two-step protocol.  This method
        only exposes the durable items that still need action; a future worker
        must call the normal Runtime path with a fresh approval and current
        principal instead of replaying handlers directly from SQLite.
        """
        workflow = self.runtime.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        if workflow.get("status") == "running" and self.runtime._is_stale_workflow(workflow):
            self.runtime._session_manager.recover_stale_workflow(
                workflow_id,
                self.runtime.workflow_stale_after_seconds,
                {
                    "recovery_reason": "stale_running_workflow",
                    "recovery_detected_at": datetime.now().isoformat(),
                },
            )
            workflow = self.runtime.get_workflow(
                workflow_id, user_id=user_id, tenant_id=tenant_id
            ) or workflow
        resumable = {"failed", "partially_failed", "recovery_required", "blocked"}
        if workflow.get("status") not in resumable:
            return {
                "workflow_id": workflow_id,
                "status": workflow.get("status"),
                "resumable": False,
                "requires_fresh_confirmation": False,
                "items": [],
            }
        pending = [
            item for item in workflow.get("items", [])
            if item.get("status") not in {"succeeded", "unsupported"}
        ]
        session_record = (
            self.runtime._session_manager.get_session(workflow.get("session_id"))
            if self.runtime._session_manager else None
        ) or {}
        session_account_id = str(session_record.get("account_id") or "")

        def item_account_id(item: Mapping[str, Any]) -> Optional[str]:
            account_id = item.get("account_id")
            if account_id not in (None, ""):
                return str(account_id)
            input_data = item.get("input_data")
            if isinstance(input_data, Mapping):
                for key in ("account_id", "advertiser_id", "customer_id"):
                    value = input_data.get(key)
                    if value not in (None, ""):
                        return str(value)
            return session_account_id or None

        definitions = {
            definition.name: definition
            for definition in self.runtime.registry.list_all()
        }

        def item_definition_value(
            item: Mapping[str, Any], field: str,
        ) -> Optional[str]:
            value = item.get(field)
            if value not in (None, ""):
                return str(value)
            definition = definitions.get(str(item.get("tool_name") or ""))
            value = getattr(definition, field, None) if definition else None
            return str(value) if value not in (None, "") else None

        return {
            "workflow_id": workflow_id,
            "status": workflow.get("status"),
            "resumable": bool(pending),
            "requires_fresh_confirmation": workflow.get("execution_mode") == ExecutionMode.LIVE.value,
            "replay_policy": "explicit_operator_confirmation",
            "items": [
                {
                    "sequence": item.get("sequence"),
                    "platform": self.runtime._canonical_platform(str(item.get("platform") or "")),
                    "account_id": item_account_id(item),
                    "tool_name": item.get("tool_name"),
                    "resource_type": item_definition_value(item, "resource_type"),
                    "parent_resource_type": item_definition_value(
                        item, "parent_resource_type"
                    ),
                    "parent_resource_id": item.get("parent_resource_id"),
                    "status": item.get("status"),
                    "input_data": self.runtime._redact_for_persistence(item.get("input_data") or {}),
                    "error": self.runtime._redact_for_persistence(item.get("error")),
                }
                for item in pending
            ],
        }

    def _is_stale_workflow(self, workflow: Mapping[str, Any]) -> bool:
        """Treat a running workflow as recoverable only after its lease age."""
        try:
            updated_at = datetime.fromisoformat(str(workflow.get("updated_at")))
            age = (datetime.now() - updated_at).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return False
        return age >= self.runtime.workflow_stale_after_seconds

    def list_resumable_workflows(
        self, user_id: Optional[str] = None, tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List failed or stale-running workflows within an optional tenant."""
        if not self.runtime._session_manager:
            return []
        workflows = self.runtime._session_manager.list_resumable_workflows(
            user_id=user_id,
            limit=limit,
            include_stale_running=True,
            stale_after_seconds=self.runtime.workflow_stale_after_seconds,
            tenant_id=tenant_id,
        )
        return workflows

    def reconcile_workflow(
        self,
        workflow_id: str,
        observations: list[dict] | dict[int, dict],
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Apply provider-verified observations to a durable workflow.

        No provider is contacted here.  Every observation must explicitly set
        ``verified=true`` so an untrusted status guess cannot mark a failed
        live write as successful.  Unknown outcomes remain recovery-required.
        """
        workflow = self.runtime.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        if isinstance(observations, dict):
            entries = [dict(value, sequence=key) for key, value in observations.items()]
        else:
            entries = list(observations or [])
        if not entries:
            raise ValueError("reconciliation requires at least one observation")
        known_sequences = {
            int(item.get("sequence"))
            for item in workflow.get("items", [])
            if item.get("sequence") is not None
        }
        current_statuses = {
            int(item.get("sequence")): str(item.get("status"))
            for item in workflow.get("items", [])
            if item.get("sequence") is not None
        }
        allowed_item_transitions = {
            "failed": {"failed", "succeeded", "unknown"},
            "unknown": {"unknown", "succeeded", "failed"},
            "awaiting_confirmation": {"awaiting_confirmation", "succeeded", "failed", "unknown"},
            "running": {"running", "succeeded", "failed", "unknown"},
            "planned": {"planned", "awaiting_confirmation", "running", "succeeded", "failed", "unknown"},
            "succeeded": {"succeeded"},
            "unsupported": {"unsupported"},
            "skipped": {"skipped"},
        }
        seen_sequences: set[int] = set()
        for observation in entries:
            if not isinstance(observation, dict) or observation.get("verified") is not True:
                raise ValueError("each reconciliation observation must set verified=true")
            status = str(observation.get("status", "unknown"))
            if status not in {"succeeded", "failed", "unknown"}:
                raise ValueError("reconciliation status must be succeeded, failed or unknown")
            if observation.get("sequence") is None:
                raise ValueError("reconciliation observation requires sequence")
            try:
                sequence = int(observation["sequence"])
            except (TypeError, ValueError):
                raise ValueError("reconciliation sequence must be an integer")
            if sequence not in known_sequences:
                raise ValueError("reconciliation sequence does not belong to workflow")
            if sequence in seen_sequences:
                raise ValueError("reconciliation sequence must be unique")
            current_status = current_statuses[sequence]
            if status not in allowed_item_transitions.get(current_status, set()):
                raise ValueError(
                    f"cannot reconcile workflow item {sequence} from {current_status} to {status}"
                )
            seen_sequences.add(sequence)
        for observation in entries:
            sequence = int(observation["sequence"])
            status = str(observation.get("status", "unknown"))
            updated_item = self.runtime._session_manager.update_workflow_item(
                workflow_id,
                sequence,
                status,
                output_data=self.runtime._redact_for_persistence(observation.get("output_data")),
                error=self.runtime._redact_for_persistence(observation.get("error")),
            )
            if not updated_item:
                raise ValueError(f"workflow item {sequence} could not be updated")

        updated = self.runtime._session_manager.get_workflow(workflow_id)
        items = updated.get("items", []) if updated else []
        statuses = [str(item.get("status")) for item in items]
        succeeded = [item for item in items if item.get("status") == "succeeded"]
        failed = [item for item in items if item.get("status") == "failed"]
        if any(status == "unknown" for status in statuses):
            workflow_status = "recovery_required"
        elif failed and succeeded:
            self.runtime._session_manager.mark_workflow_items_for_compensation(
                workflow_id,
                [int(item["sequence"]) for item in succeeded],
            )
            workflow_status = "partially_failed"
        elif failed:
            workflow_status = "failed"
        elif statuses and all(status in {"succeeded", "unsupported"} for status in statuses):
            workflow_status = "succeeded"
        else:
            workflow_status = "recovery_required"
        self.runtime._session_manager.update_workflow(
            workflow_id,
            workflow_status,
            {
                "last_reconciled_by": str(user_id or "operator"),
                "reconciliation_verified": True,
            },
        )
        return self.runtime.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        ) or {}

    def reconcile_workflow_from_provider(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        credentials: Optional[dict] = None,
        principal: Optional[RequestPrincipal] = None,
    ) -> dict:
        """Resolve pending items through provider-owned read-back adapters.

        This method never replays a write. A reconciler can only invoke a
        registered read tool through the Runtime, and its observation is
        applied by the same verified state-transition path as externally
        supplied observations.
        """
        if not self.runtime._session_manager:
            raise RuntimeError("provider reconciliation requires persistence")
        effective_user_id = principal.user_id if principal is not None else user_id
        effective_tenant_id = principal.tenant_id if principal is not None else tenant_id
        permissions = (
            principal.permissions if principal is not None else self.runtime._granted_permissions
        )
        permissions = frozenset(permissions or ())
        if "ads.reconcile" not in permissions and "ads.write" not in permissions:
            raise PermissionError("provider reconciliation requires ads.reconcile or ads.write")
        if "ads.read" not in permissions and "ads.write" not in permissions:
            raise PermissionError("provider reconciliation requires ads.read")

        workflow = self.runtime.get_workflow(
            workflow_id,
            user_id=effective_user_id,
            tenant_id=effective_tenant_id,
        )
        if not workflow:
            raise KeyError("workflow not found")
        if not self.runtime._session_manager.claim_workflow_recovery(
            workflow_id,
            self.runtime._workflow_lease_owner,
            self.runtime.workflow_stale_after_seconds,
            self.runtime.workflow_stale_after_seconds,
        ):
            raise RuntimeError("workflow is already being recovered or is still active")
        try:
            workflow = self.runtime.get_workflow(
                workflow_id,
                user_id=effective_user_id,
                tenant_id=effective_tenant_id,
            ) or workflow
            session_record = self.runtime._session_manager.get_session(workflow.get("session_id")) or {}
            request_clients = self.runtime._build_request_clients(credentials)
            account_scope = principal.account_scope if principal is not None else None
            observations: list[dict[str, Any]] = []
            pending_statuses = {
                "planned", "running", "awaiting_confirmation", "failed", "unknown",
            }

            for item in workflow.get("items", []):
                if str(item.get("status")) not in pending_statuses:
                    continue
                platform = self.runtime._canonical_platform(item.get("platform") or "")
                input_data = item.get("input_data") if isinstance(item.get("input_data"), dict) else {}
                account_id = None
                for account_key in self.runtime.account_resolver.ACCOUNT_FIELDS:
                    if input_data.get(account_key):
                        account_id = str(input_data[account_key])
                        break
                account_id = account_id or str(session_record.get("account_id") or "")
                allowed, account_error = self.runtime._validate_account_with_principal(
                    platform, account_id, False, account_scope
                )
                if not allowed:
                    observations.append({
                        "sequence": item.get("sequence"),
                        "status": "unknown",
                        "verified": True,
                        "error": f"read-back account boundary rejected: {account_error}",
                        "source": "runtime_account_boundary",
                    })
                    continue

                reconciler = self.runtime._provider_reconcilers.get(platform) or ToolReadbackReconciler(platform)

                ctx = ToolContext(
                    session_id=str(workflow.get("session_id") or ""),
                    user_id=str(effective_user_id or session_record.get("user_id") or ""),
                    account_id=account_id,
                    credentials=self.runtime._freeze_credentials(credentials or {}),
                    metadata={
                        "tenant_id": str(effective_tenant_id or "default"),
                        "reconciliation": True,
                    },
                )

                def execute_read(read_tool: str, read_input: dict[str, Any]) -> ToolResult:
                    definition, _handler = self.runtime._get_registered_tool(read_tool)
                    if not definition.is_read_tool:
                        return ToolResult.error("reconciliation callback only permits read tools")
                    permission_error = self.runtime._check_tool_permissions(definition, permissions)
                    if permission_error:
                        return ToolResult.error(permission_error)
                    return self.runtime.tool_executor.execute(
                        ctx, read_tool, read_input, request_clients
                    )

                observation = reconciler.reconcile(
                    ReconciliationContext(
                        workflow=workflow,
                        item=item,
                        tool_context=ctx,
                        execute_read=execute_read,
                        resolve_read_tool=self.runtime._resolve_readback_definition,
                    )
                )
                if not isinstance(observation, ReconciliationObservation):
                    raise TypeError("ProviderReconciler must return ReconciliationObservation")
                if int(observation.sequence) != int(item.get("sequence")):
                    raise ValueError("ProviderReconciler returned a mismatched workflow sequence")
                if not observation.verified:
                    raise ValueError("ProviderReconciler must return verified observations")
                payload = dict(observation.output_data or {})
                payload["_reconciliation"] = {
                    "source": observation.source,
                    "observed_at": observation.observed_at,
                    "provider_resource_id": observation.provider_resource_id,
                }
                observations.append({
                    "sequence": observation.sequence,
                    "status": observation.status,
                    "verified": True,
                    "output_data": payload,
                    "error": observation.error,
                    "source": observation.source,
                })

            if not observations:
                raise ValueError("workflow has no pending items eligible for provider reconciliation")
            reconciled = self.runtime.reconcile_workflow(
                workflow_id,
                observations,
                user_id=effective_user_id,
                tenant_id=effective_tenant_id,
            )
            return reconciled
        finally:
            self.runtime._session_manager.release_workflow_lease(
                workflow_id, self.runtime._workflow_lease_owner
            )

    def cancel_workflow(
        self, workflow_id: str, user_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """Cancel a non-terminal workflow without contacting a provider."""
        workflow = self.runtime.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            return False
        return self.runtime._session_manager.update_workflow(
            workflow_id, "cancelled", {"cancelled_by": str(user_id)}
        )
