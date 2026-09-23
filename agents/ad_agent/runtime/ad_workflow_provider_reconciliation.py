"""Provider read-back reconciliation for durable advertising workflows."""

from __future__ import annotations

from typing import Any, Optional

from ..domain.ad.auth import RequestPrincipal
from ..core.interfaces import (
    ReconciliationContext,
    ReconciliationObservation,
    ToolContext,
    ToolResult,
)
from .reconciliation import ToolReadbackReconciler


class ProviderWorkflowReconciliationMixin:
    def reconcile_workflow_from_provider(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        credentials: Optional[dict] = None,
        principal: Optional[RequestPrincipal] = None,
    ) -> dict:
        """Resolve pending items through registered provider read Tools."""
        if not self.runtime._session_manager:
            raise RuntimeError("provider reconciliation requires persistence")
        effective_user_id = principal.user_id if principal is not None else user_id
        effective_tenant_id = principal.tenant_id if principal is not None else tenant_id
        permissions = (
            principal.permissions
            if principal is not None
            else self.runtime._granted_permissions
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
            session_record = (
                self.runtime._session_manager.get_session(
                    workflow.get("session_id")
                ) or {}
            )
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
                input_data = (
                    item.get("input_data")
                    if isinstance(item.get("input_data"), dict) else {}
                )
                account_id = next(
                    (
                        str(input_data[key])
                        for key in self.runtime.account_resolver.ACCOUNT_FIELDS
                        if input_data.get(key)
                    ),
                    None,
                )
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

                reconciler = (
                    self.runtime._effect_reconcilers.get(platform)
                    or ToolReadbackReconciler(platform)
                )
                ctx = ToolContext(
                    session_id=str(workflow.get("session_id") or ""),
                    user_id=str(
                        effective_user_id
                        or session_record.get("user_id")
                        or ""
                    ),
                    account_id=account_id,
                    credentials=self.runtime._freeze_credentials(credentials or {}),
                    metadata={
                        "tenant_id": str(effective_tenant_id or "default"),
                        "reconciliation": True,
                    },
                )

                def execute_read(
                    read_tool: str, read_input: dict[str, Any]
                ) -> ToolResult:
                    definition, _handler = self.runtime._get_registered_tool(read_tool)
                    if not definition.is_read_tool:
                        return ToolResult.error(
                            "reconciliation callback only permits read tools"
                        )
                    permission_error = self.runtime._check_tool_permissions(
                        definition, permissions
                    )
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
                    raise TypeError(
                        "EffectReconciler must return ReconciliationObservation"
                    )
                if int(observation.sequence) != int(item.get("sequence")):
                    raise ValueError(
                        "EffectReconciler returned a mismatched workflow sequence"
                    )
                if not observation.verified:
                    raise ValueError(
                        "EffectReconciler must return verified observations"
                    )
                payload = dict(observation.output_data or {})
                payload["_reconciliation"] = {
                    "source": observation.source,
                    "observed_at": observation.observed_at,
                    "provider_resource_id": observation.external_resource_id,
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
                raise ValueError(
                    "workflow has no pending items eligible for provider reconciliation"
                )
            return self.runtime.reconcile_workflow(
                workflow_id,
                observations,
                user_id=effective_user_id,
                tenant_id=effective_tenant_id,
            )
        finally:
            self.runtime._session_manager.release_workflow_lease(
                workflow_id, self.runtime._workflow_lease_owner
            )


__all__ = ["ProviderWorkflowReconciliationMixin"]
