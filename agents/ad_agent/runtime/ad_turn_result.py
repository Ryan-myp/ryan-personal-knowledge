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
