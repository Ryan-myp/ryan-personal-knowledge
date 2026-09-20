"""Application result aggregation and response finalization.

Planning and Tool execution are intentionally upstream of this service. This
module only joins normalized results, Feature-owned analysis and the response
renderer, then closes workflow/turn persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

class AdTurnResultService:
    """Finalize one completed application turn without selecting Tools."""

    def complete(
        self,
        *,
        runtime: Any,
        feature: Any,
        intent: Any,
        tool_plan: dict[str, list[Any]],
        results: list[dict[str, Any]],
        session: Any,
        turn_id: str,
        request_clients: Mapping[str, Any],
        account_scope: Optional[Mapping[str, Any]],
        effective_permissions: Any,
        workflow_id: Optional[str],
        workflow_inputs: dict[int, dict[str, Any]],
        trace: Any,
        creation_ui: dict[str, Any],
        safe_user_input: str,
        needs_confirmation: bool,
        confirmation_payload: Optional[dict[str, Any]],
        confirmed: bool,
        creation_preflight: Any,
        recalled_memories: list[dict[str, Any]],
        memory_updates: list[dict[str, Any]],
        tool_selection: dict[str, Any],
        execution_plan: Any,
        session_id: str,
        run_id: str,
        finalize_run: Any,
    ) -> dict[str, Any]:
        # Cross-channel comparison is a two-phase read workflow: first list
        # campaigns, then collect campaign-scoped report rows.
        analysis_owner = getattr(feature, "handles_analysis", None) if feature is not None else None
        analysis_stage_active = bool(
            feature is not None
            and callable(analysis_owner)
            and analysis_owner(intent)
        )
        if analysis_stage_active:
            trace.stage_status(
                "analysis",
                "结果分析",
                "running",
                subtitle="整理工具结果并提取业务信息",
                safe_metadata={"phase": "result_analysis"},
                safe_input={"result_count": len(results)},
            )
        if feature is not None and callable(
            getattr(feature, "collect_metrics", None)
        ):
            feature.collect_metrics(
                runtime.services,
                intent, tool_plan, results, session, turn_id, request_clients,
                account_scope=account_scope,
                granted_permissions=effective_permissions,
                execution_trace=trace,
            )
        runtime.workflow.finish(
            workflow_id, tool_plan, results, workflow_inputs,
            intent=intent, session=session,
        )
        resource_results = runtime._build_resource_results(results)

        analysis: dict[str, Any] = {}
        if feature is not None and callable(getattr(feature, "analyze", None)):
            analysis = feature.analyze(intent, results)
        if analysis_stage_active:
            trace.stage_status(
                "analysis",
                "结果分析",
                "succeeded",
                subtitle="结果已整理完成",
                safe_metadata={"result_count": len(results)},
                safe_input={"result_count": len(results)},
                safe_output={
                    "result_count": len(results),
                    "analysis_available": bool(analysis),
                    "summary": runtime._redact_for_persistence(analysis or {}),
                },
            )
        trace.stage_status(
            "reply",
            "回复生成",
            "running",
            subtitle="生成面向业务人员的结果说明",
            safe_metadata={"phase": "response_rendering"},
            safe_input={
                "result_count": len(results),
                "needs_confirmation": needs_confirmation,
            },
        )
        if creation_ui.get("needs_input") and not any(
            isinstance(item.get("confirmation_payload"), dict)
            and item["confirmation_payload"].get("type") == "ask_account"
            for item in results
        ):
            reply, response_source = runtime.creation_ui_reply(creation_ui, safe_user_input), "creation_card"
        else:
            reply, response_source = runtime._render_response(
                safe_user_input,
                intent,
                results,
                needs_confirmation,
                analysis=analysis,
                session=session,
            )
        trace.stage_status(
            "reply",
            "回复生成",
            "succeeded",
            subtitle="已生成本轮回复",
            safe_metadata={"response_source": response_source},
            safe_output={
                "response_source": response_source,
                "available": True,
                "preview": runtime._redact_for_persistence(reply),
            },
        )
        trace.reply(needs_confirmation=needs_confirmation)
        has_failure = any(
            not item.get("success", False) and not item.get("skipped", False)
            for item in results
        )
        trace.done(
            "awaiting_confirmation" if needs_confirmation else "failed" if has_failure else "succeeded",
            safe_metadata={"tool_count": len(results)},
        )

        # Only promote high-value live write outcomes to episodic memory.
        # Ordinary reads and dry-run previews must not pollute long-term
        # memory. The MemoryManager owns the allowlist, sanitization, TTL and
        # idempotency policy; this service only supplies a bounded summary.
        memory_manager = getattr(runtime, "_memory_manager", None)
        if memory_manager and runtime.execution_mode == "live":
            tool_by_name = {
                tool.name: tool
                for tools in tool_plan.values()
                for tool in tools
            }
            write_results = [
                item for item in results
                if bool(getattr(tool_by_name.get(item.get("tool")), "is_write_tool", False))
            ]
            successful_writes = [
                item for item in write_results if bool(item.get("success"))
            ]
            failed_writes = [
                item for item in write_results
                if not item.get("success") and not item.get("skipped")
            ]
            unknown_writes = [
                item for item in write_results
                if str((item.get("data") or {}).get("execution_status") or "").lower()
                in {"unknown", "timed_out", "transport_unknown"}
            ]
            event_type = None
            outcome = None
            if unknown_writes:
                event_type, outcome = "recovery_required", "unknown"
            elif confirmed and successful_writes:
                event_type, outcome = "confirmation_completed", "succeeded"
            elif successful_writes:
                event_type, outcome = "operation_succeeded", "succeeded"
            elif failed_writes:
                event_type, outcome = "operation_failed", "failed"
            if event_type:
                platforms = sorted({
                    str(item.get("platform") or "").strip().lower()
                    for item in write_results
                    if str(item.get("platform") or "").strip()
                })
                try:
                    episode = memory_manager.remember_runtime_event(
                        f"本次操作包含 {len(write_results)} 个写入步骤，"
                        f"成功 {len(successful_writes)} 个，失败 {len(failed_writes)} 个。",
                        tenant_id=str(session.ctx.metadata.get("tenant_id") or "default"),
                        user_id=str(session.ctx.user_id or "anonymous"),
                        session_id=str(session.session_id),
                        event_type=event_type,
                        dedupe_key=f"{session.session_id}:{turn_id}:{event_type}",
                        outcome=outcome,
                        tags=[f"channel:{platform}" for platform in platforms],
                    )
                    if episode is not None:
                        memory_updates.append(episode.to_context_dict())
                except Exception:
                    # Memory is advisory; never turn a completed provider
                    # operation into a user-visible failure.
                    pass

        # Step 6: 记录消息历史
        runtime.persist_conversation_turn(
            session, turn_id, safe_user_input, reply,
            execution_trace=trace, ui=creation_ui,
        )
        finalize_run(
            "awaiting_confirmation"
            if needs_confirmation else "failed" if has_failure else "succeeded",
            {"tool_count": len(results)},
        )

        return {
            "session_id": session_id,
            "run_id": run_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "tool_selection": {
                "tool_count": tool_selection["tool_count"],
                "tools": [tool.name for tool in tool_selection["selected_tools"]],
                "platforms": tool_selection["namespaces"],
                "context": tool_selection["context"],
                "tool_prompt": tool_selection["tool_prompt"],
                "expert_knowledge": tool_selection["expert_knowledge"],
                "knowledge": tool_selection.get("knowledge", []),
            },
            "memory": recalled_memories,
            "memory_updates": memory_updates,
            "response_source": response_source,
            "execution_plan": execution_plan.to_dict(),
            "results": results,
            "resource_results": resource_results,
            "workflow_id": workflow_id,
            **(
                feature.preflight_payload(creation_preflight)
                if creation_preflight is not None
                and callable(getattr(feature, "preflight_payload", None))
                else (
                    {"preflight": creation_preflight.to_dict()}
                    if creation_preflight is not None
                    else {}
                )
            ),
            **(analysis if isinstance(analysis, dict) else {}),
            "reply": reply,
            "needs_confirmation": needs_confirmation,
            "confirmation_payload": confirmation_payload,
            "ui": creation_ui,
        }


__all__ = ["AdTurnResultService"]
