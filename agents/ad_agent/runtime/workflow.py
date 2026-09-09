"""Workflow coordination outside the Agent Runtime main loop."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Optional

from ..core.features import RuntimeExecutionServices
from ..core.execution_plan import ExecutionPlan


class WorkflowCoordinator:
    """Persist generic plan checkpoints and workflow state transitions."""

    def __init__(
        self,
        services: RuntimeExecutionServices,
        outbox: Any = None,
        item_scope_resolver: Optional[Callable[..., Optional[str]]] = None,
        result_scope_resolver: Optional[Callable[..., Optional[str]]] = None,
    ):
        self.services = services
        self.outbox = outbox
        # Resource scope is application-owned.  The generic coordinator only
        # persists the opaque value returned by this callback and never knows
        # whether an application calls it an account, workspace, project, or
        # something else.
        self.item_scope_resolver = item_scope_resolver
        self.result_scope_resolver = result_scope_resolver

    def start(
        self,
        session: Any,
        intent: Any,
        tool_plan: dict[str, list[Any]],
        register_items: bool = True,
        execution_plan: Optional[ExecutionPlan] = None,
    ) -> Optional[str]:
        store = self.services.session_manager
        if not store:
            return None
        if not any(
            tool.is_write_tool
            for tools in tool_plan.values()
            for tool in tools
        ):
            return None
        workflow_id = str(uuid.uuid4())
        workflow_metadata = {
            "platforms": list(intent.platforms),
            "dry_run": self.services.is_dry_run(),
            "execution_plan": (
                execution_plan.to_dict()
                if execution_plan is not None else None
            ),
            "compensation_policy": "manual_review_required",
            "replay_policy": "explicit_operator_confirmation",
            "raw_input": self.services.redact(intent.raw_input),
        }
        store.create_workflow(
            workflow_id,
            session.session_id,
            intent.intent_type,
            self.services.execution_mode,
            status="running",
            metadata=workflow_metadata,
            # Workflow state and its durable event must commit together. The
            # backend owns this transaction; a process-level publisher is
            # only a delivery mechanism and cannot sit between the two writes.
            emit_outbox=True,
        )
        store.heartbeat_workflow(
            workflow_id,
            self.services.workflow_lease_owner(),
            self.services.workflow_stale_after_seconds(),
        )
        if register_items:
            sequence = 0
            sequence_by_resource: dict[tuple[str, str], int] = {}
            for platform, tools in tool_plan.items():
                for tool in tools:
                    if not tool.is_write_tool:
                        continue
                    sequence += 1
                    actual_platform = self.services.normalize_namespace(platform)
                    parent_type = getattr(tool, "parent_resource_type", None)
                    parent_sequence = (
                        sequence_by_resource.get((actual_platform, parent_type))
                        if parent_type else None
                    )
                    scope_value = (
                        self.item_scope_resolver(
                            intent, platform, [tool], session,
                        )
                        if self.item_scope_resolver is not None else None
                    )
                    store.record_workflow_item(
                        workflow_id=workflow_id,
                        sequence=sequence,
                        platform=actual_platform,
                        tool_name=tool.name,
                        status="planned",
                        input_data={},
                        # The application persistence adapter maps this
                        # opaque scope to its storage representation.
                        scope=scope_value,
                        resource_type=getattr(tool, "resource_type", None),
                        parent_resource_type=parent_type,
                        parent_sequence=parent_sequence,
                    )
                    sequence_by_resource[(
                        actual_platform,
                        str(getattr(tool, "resource_type", "") or ""),
                    )] = sequence
        return workflow_id

    def heartbeat(self, workflow_id: Optional[str]) -> bool:
        if not workflow_id or not self.services.session_manager:
            return True
        return self.services.session_manager.heartbeat_workflow(
            workflow_id,
            self.services.workflow_lease_owner(),
            self.services.workflow_stale_after_seconds(),
        )

    def finish(
        self,
        workflow_id: Optional[str],
        tool_plan: dict[str, list[Any]],
        results: list[dict],
        workflow_inputs: dict[int, dict],
        planning_errors: Optional[list[str]] = None,
        *,
        intent: Any = None,
        session: Any = None,
    ) -> None:
        store = self.services.session_manager
        if not workflow_id or not store:
            return
        planning_errors = list(planning_errors or [])
        write_tools = {
            tool.name
            for tools in tool_plan.values()
            for tool in tools
            if tool.is_write_tool
        }
        sequence_by_tool: dict[str, int] = {}
        definition_by_tool: dict[str, Any] = {}
        sequence = 0
        for tools in tool_plan.values():
            for tool in tools:
                if tool.is_write_tool:
                    sequence += 1
                    sequence_by_tool[tool.name] = sequence
                    definition_by_tool[tool.name] = tool

        item_sequences: list[int] = []
        successful_sequences: list[int] = []
        failed_sequences: list[int] = []
        unsupported_sequences: list[int] = []
        unknown_sequences: list[int] = []
        retriable_sequences: list[int] = []
        occurrences: dict[str, int] = {}
        for item in results:
            name = str(item.get("tool") or "")
            if name in write_tools:
                occurrences[name] = occurrences.get(name, 0) + 1
        seen: dict[str, int] = {}
        resource_sequences: dict[tuple[str, str, str], int] = {}

        for index, item in enumerate(results):
            tool_name = item.get("tool")
            if tool_name not in write_tools or item.get("batch_planning_error"):
                continue
            tool_name = str(tool_name)
            seen[tool_name] = seen.get(tool_name, 0) + 1
            explicit = item.get("workflow_sequence")
            if explicit not in (None, ""):
                try:
                    item_sequence = int(explicit)
                except (TypeError, ValueError):
                    item_sequence = None
            else:
                item_sequence = (
                    seen[tool_name]
                    if occurrences.get(tool_name, 0) > 1
                    else sequence_by_tool.get(tool_name)
                )
            if item_sequence is None:
                continue
            item_sequences.append(item_sequence)
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            error_detail = item.get("error_detail") if isinstance(item.get("error_detail"), dict) else {}
            error_category = str(error_detail.get("category") or "")
            if item.get("skipped"):
                status = "skipped"
            elif data.get("execution_status") == "unsupported":
                status = "unsupported"
                unsupported_sequences.append(item_sequence)
            elif error_category == "provider_result_unknown" or data.get("execution_status") in {
                "unknown", "timed_out", "transport_unknown",
            }:
                status = "unknown"
                unknown_sequences.append(item_sequence)
            elif error_category == "retriable":
                status = "failed"
                failed_sequences.append(item_sequence)
                retriable_sequences.append(item_sequence)
            elif item.get("needs_confirmation"):
                status = "awaiting_confirmation"
            elif item.get("success"):
                status = "succeeded"
                successful_sequences.append(item_sequence)
            else:
                status = "failed"
                failed_sequences.append(item_sequence)

            definition = definition_by_tool.get(tool_name)
            output_data = self.services.redact(data)
            input_data = self.services.redact(workflow_inputs.get(index, {}))
            resource_type = getattr(definition, "resource_type", None)
            resource_id_field = str(
                item.get("resource_id_field")
                or self.services.resource_id_field(definition)
                or ""
            )
            raw_resource_id = data.get(resource_id_field)
            if raw_resource_id in (None, ""):
                raw_resource_id = input_data.get(resource_id_field)
            parent_type = (
                item.get("parent_resource_type")
                or data.get("parent_resource_type")
                or getattr(definition, "parent_resource_type", None)
            )
            parent_field = (
                item.get("parent_resource_id_field")
                or data.get("parent_resource_id_field")
                or self.services.parent_resource_id_field(definition)
            )
            parent_resource_id = (
                item.get("parent_resource_id")
                or data.get("parent_resource_id")
                or (input_data.get(parent_field) if parent_field else None)
            )
            actual_platform = self.services.normalize_namespace(
                str(item.get("platform") or "")
            )
            scope_value = (
                self.result_scope_resolver(
                    intent, actual_platform, [definition] if definition else [],
                    session, item, input_data, data,
                )
                if self.result_scope_resolver is not None else None
            )
            parent_sequence = (
                resource_sequences.get((
                    actual_platform,
                    str(parent_type or ""),
                    str(parent_resource_id),
                ))
                if parent_resource_id not in (None, "") and parent_type
                else None
            )
            simulated = bool(data.get("simulated") or item.get("simulated"))
            provider_resource_id = (
                str(raw_resource_id)
                if raw_resource_id not in (None, "") and not simulated
                else None
            )
            local_resource_id = (
                str(raw_resource_id)
                if raw_resource_id not in (None, "") and simulated
                else None
            )
            store.record_workflow_item(
                workflow_id=workflow_id,
                sequence=item_sequence,
                platform=actual_platform,
                tool_name=tool_name,
                status=status,
                input_data=input_data,
                output_data=output_data,
                error=item.get("error"),
                resource_type=resource_type,
                parent_resource_type=(
                    str(parent_type) if parent_type else None
                ),
                parent_sequence=parent_sequence,
                parent_resource_id=(
                    str(parent_resource_id)
                    if parent_resource_id not in (None, "") else None
                ),
                provider_resource_id=provider_resource_id,
                logical_resource_id=local_resource_id or provider_resource_id,
                scope=(
                    str(scope_value) if scope_value not in (None, "") else None
                ),
            )
            if raw_resource_id not in (None, ""):
                resource_sequences[(
                    actual_platform,
                    str(resource_type or ""),
                    str(raw_resource_id),
                )] = item_sequence

        persisted = store.get_workflow(workflow_id) or {}
        pending = [
            item for item in persisted.get("items", [])
            if item.get("status") in {"planned", "running"}
        ]
        if pending:
            status = (
                "recovery_required"
                if self.services.execution_mode == "live" else "blocked"
            )
            compensation_required = False
        elif unknown_sequences:
            status = "recovery_required"
            compensation_required = False
        elif (
            failed_sequences and successful_sequences
            and self.services.execution_mode == "live"
        ):
            store.mark_workflow_items_for_compensation(
                workflow_id, successful_sequences
            )
            status = "partially_failed"
            compensation_required = True
        elif failed_sequences:
            status = "blocked" if self.services.is_dry_run() else "failed"
            compensation_required = False
        elif unsupported_sequences or planning_errors:
            status = "blocked"
            compensation_required = False
        elif any(
            item.get("needs_confirmation")
            for item in results if item.get("tool") in write_tools
        ):
            status = "awaiting_confirmation"
            compensation_required = False
        else:
            status = (
                "planned" if self.services.is_dry_run() else "succeeded"
            )
            compensation_required = False
        workflow_metadata = {
            "write_item_count": len(item_sequences),
            "successful_items": len(successful_sequences),
            "failed_items": len(failed_sequences),
            "retriable_items": retriable_sequences,
            "planning_error_count": len(planning_errors),
            "compensation_required": compensation_required,
            "compensation_policy": "manual_review_required",
        }
        store.update_workflow(
            workflow_id,
            status,
            workflow_metadata,
            # Keep the state transition and workflow.updated event in one
            # persistence transaction for restart-safe delivery.
            emit_outbox=True,
        )
