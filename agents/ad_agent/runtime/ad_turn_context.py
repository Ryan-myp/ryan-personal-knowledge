"""Context preparation for one advertising Agent turn.

Memory and Skill context are advisory inputs to intent parsing.  Keeping this
work here makes the turn engine an orchestrator instead of a context store,
and gives future context implementations a single application boundary.
The service never selects or executes a Tool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AdTurnContext:
    """Bounded context produced for the current turn."""

    recalled_memories: list[dict[str, Any]] = field(default_factory=list)
    memory_updates: list[dict[str, Any]] = field(default_factory=list)
    memory_context: str = ""


class AdTurnContextService:
    """Build and refresh the application-owned advisory turn context."""

    def prepare(
        self,
        *,
        runtime: Any,
        session: Any,
        session_id: str,
        user_id: str,
        tenant_id: str,
        safe_user_input: str,
        trace: Any,
    ) -> AdTurnContext:
        context = AdTurnContext()
        memory_manager = runtime._memory_manager
        if memory_manager:
            try:
                for candidate in memory_manager.extract_candidates(safe_user_input):
                    record = memory_manager.remember(
                        candidate["content"],
                        tenant_id=tenant_id,
                        user_id=user_id,
                        # Long-lived memory is user-scoped rather than tied to
                        # the current conversation session.
                        session_id=None,
                        kind=candidate.get("kind", "semantic"),
                        source=candidate.get("source", "auto_preference"),
                        importance=candidate.get("importance", 0.7),
                        confidence=candidate.get("confidence", 0.86),
                        memory_key=candidate.get("memory_key"),
                    )
                    context.memory_updates.append(record.to_context_dict())
                session.ctx.metadata["memory_updates"] = context.memory_updates[-20:]
                (
                    context.recalled_memories,
                    context.memory_context,
                ) = memory_manager.build_context(
                    safe_user_input,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception:
                # Memory is an advisory enhancement. A storage/index failure
                # must never block intent parsing or Tool policy.
                logger.debug("构建 Memory 上下文失败", exc_info=True)

        trace.stage_status(
            "context",
            "上下文构建",
            "running",
            subtitle="加载有限的 Skill、工具、记忆与会话状态",
            safe_metadata={"phase": "context_build"},
            safe_input={
                "request": safe_user_input,
                "request_length": len(safe_user_input),
            },
        )
        try:
            self._store_skill_context(
                runtime=runtime,
                session=session,
                safe_user_input=safe_user_input,
                intent_type=None,
                tenant_id=tenant_id,
                context=context,
            )
        except Exception as exc:
            logger.debug("构建 Skill 解析上下文失败", exc_info=True)
            trace.stage_status(
                "context",
                "上下文构建",
                "failed",
                subtitle="上下文加载失败，继续使用最小上下文",
                safe_metadata={"error_type": type(exc).__name__},
            )
        else:
            trace.stage_status(
                "context",
                "上下文构建",
                "succeeded",
                subtitle="已完成有限上下文组装",
                safe_metadata={
                    "phase": "context_build",
                    "memory_count": len(context.recalled_memories),
                    "has_conversation_digest": bool(
                        session.ctx.metadata.get("conversation_digest")
                    ),
                },
            )
        return context

    def enrich(
        self,
        *,
        runtime: Any,
        session: Any,
        safe_user_input: str,
        intent: Any,
        tenant_id: str,
        context: AdTurnContext,
        trace: Any,
    ) -> None:
        """Replace only the model-facing Skill slice after intent parsing."""
        trace.stage_status(
            "context_enrichment",
            "意图上下文补充",
            "running",
            subtitle="根据已识别目标收敛可用知识",
            safe_metadata={"phase": "context_enrichment"},
        )
        try:
            self._store_skill_context(
                runtime=runtime,
                session=session,
                safe_user_input=safe_user_input,
                intent_type=getattr(intent, "intent_type", None),
                tenant_id=tenant_id,
                context=context,
            )
        except Exception as exc:
            logger.debug("构建意图级 Skill/知识上下文失败", exc_info=True)
            trace.stage_status(
                "context_enrichment",
                "意图上下文补充",
                "failed",
                subtitle="补充上下文失败，保留前一阶段上下文",
                safe_metadata={"error_type": type(exc).__name__},
            )
        else:
            trace.stage_status(
                "context_enrichment",
                "意图上下文补充",
                "succeeded",
                subtitle="已按意图收敛上下文",
                safe_metadata={
                    "phase": "context_enrichment",
                    "intent_type": getattr(intent, "intent_type", ""),
                },
            )

    @staticmethod
    def _store_skill_context(
        *,
        runtime: Any,
        session: Any,
        safe_user_input: str,
        intent_type: str | None,
        tenant_id: str,
        context: AdTurnContext,
    ) -> None:
        skill_context = runtime._build_skill_context(
            safe_user_input,
            runtime.registry.list_all(),
            intent_type,
            tenant_id,
        )
        skill_context["prior_tool_results"] = runtime._build_prior_tool_results_context(
            session
        )
        skill_context["memory"] = context.recalled_memories
        skill_context["memory_context"] = context.memory_context
        skill_context["conversation_digest"] = session.ctx.metadata.get(
            "conversation_digest", ""
        )
        session.ctx.metadata["skill_context"] = skill_context


__all__ = ["AdTurnContext", "AdTurnContextService"]
