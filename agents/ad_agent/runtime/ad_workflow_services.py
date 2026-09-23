"""Durable workflow inspection and verified state reconciliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from ..core.interfaces import ExecutionMode
from .ad_workflow_provider_reconciliation import ProviderWorkflowReconciliationMixin


class AdWorkflowServices(ProviderWorkflowReconciliationMixin):
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def get_workflow(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Read a durable workflow while enforcing its owner boundary."""
        if not self.runtime._session_manager:
            return None
        workflow = self.runtime._session_manager.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if workflow:
            return workflow
        if user_id is not None or tenant_id is not None:
            existing = self.runtime._session_manager.get_workflow(workflow_id)
            if existing:
                if user_id is not None:
                    session = self.runtime._session_manager.get_session(
                        existing.get("session_id")
                    ) or {}
                    if str(session.get("user_id") or "") != str(user_id):
                        raise PermissionError("workflow belongs to a different user")
                if tenant_id is not None and str(
                    existing.get("tenant_id") or "default"
                ) != str(tenant_id or "default"):
                    raise PermissionError("workflow belongs to a different tenant")
        return None

    def get_workflow_resume_plan(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Return a safe replay plan without executing provider operations."""
        workflow = self.runtime.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        if (
            workflow.get("status") == "running"
            and self.runtime._is_stale_workflow(workflow)
        ):
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
            "requires_fresh_confirmation": (
                workflow.get("execution_mode") == ExecutionMode.LIVE.value
            ),
            "replay_policy": "explicit_operator_confirmation",
            "items": [
                {
                    "sequence": item.get("sequence"),
                    "platform": self.runtime._canonical_platform(
                        str(item.get("platform") or "")
                    ),
                    "account_id": item_account_id(item),
                    "tool_name": item.get("tool_name"),
                    "resource_type": item_definition_value(item, "resource_type"),
                    "parent_resource_type": item_definition_value(
                        item, "parent_resource_type"
                    ),
                    "parent_resource_id": item.get("parent_resource_id"),
                    "status": item.get("status"),
                    "input_data": self.runtime._redact_for_persistence(
                        item.get("input_data") or {}
                    ),
                    "error": self.runtime._redact_for_persistence(
                        item.get("error")
                    ),
                }
                for item in pending
            ],
        }

    def _is_stale_workflow(self, workflow: Mapping[str, Any]) -> bool:
        try:
            updated_at = datetime.fromisoformat(str(workflow.get("updated_at")))
            age = (datetime.now() - updated_at).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return False
        return age >= self.runtime.workflow_stale_after_seconds

    def list_resumable_workflows(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        if not self.runtime._session_manager:
            return []
        return self.runtime._session_manager.list_resumable_workflows(
            user_id=user_id,
            limit=limit,
            include_stale_running=True,
            stale_after_seconds=self.runtime.workflow_stale_after_seconds,
            tenant_id=tenant_id,
        )

    def reconcile_workflow(
        self,
        workflow_id: str,
        observations: list[dict] | dict[int, dict],
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> dict:
        """Apply provider-verified observations to durable workflow state."""
        workflow = self.runtime.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            raise KeyError("workflow not found")
        entries = (
            [dict(value, sequence=key) for key, value in observations.items()]
            if isinstance(observations, dict)
            else list(observations or [])
        )
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
            "awaiting_confirmation": {
                "awaiting_confirmation", "succeeded", "failed", "unknown",
            },
            "running": {"running", "succeeded", "failed", "unknown"},
            "planned": {
                "planned", "awaiting_confirmation", "running",
                "succeeded", "failed", "unknown",
            },
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
                raise ValueError(
                    "reconciliation status must be succeeded, failed or unknown"
                )
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
                    f"cannot reconcile workflow item {sequence} "
                    f"from {current_status} to {status}"
                )
            seen_sequences.add(sequence)
        for observation in entries:
            sequence = int(observation["sequence"])
            updated_item = self.runtime._session_manager.update_workflow_item(
                workflow_id,
                sequence,
                str(observation.get("status", "unknown")),
                output_data=self.runtime._redact_for_persistence(
                    observation.get("output_data")
                ),
                error=self.runtime._redact_for_persistence(
                    observation.get("error")
                ),
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
        elif statuses and all(
            status in {"succeeded", "unsupported"} for status in statuses
        ):
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

    def cancel_workflow(
        self, workflow_id: str, user_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        workflow = self.runtime.get_workflow(
            workflow_id, user_id=user_id, tenant_id=tenant_id
        )
        if not workflow:
            return False
        return self.runtime._session_manager.update_workflow(
            workflow_id, "cancelled", {"cancelled_by": str(user_id)}
        )


__all__ = ["AdWorkflowServices"]
