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

    _CONTEXT_LIMITS = {
        "tool_prompt": 6000,
        "expert_knowledge": 6000,
        "publisher_context": 3500,
        "knowledge": 6000,
        "memory_context": 2400,
        "prior_tool_results": 4000,
        "conversation_digest": 2400,
    }
    _MAX_MEMORY_RECORDS = 5
    _MAX_KNOWLEDGE_RECORDS = 8
    _AGGREGATE_CONTEXT_LIMIT = 20_000
    _CONTEXT_TRIM_PRIORITY = (
        "conversation_digest",
        "prior_tool_results",
        "memory_context",
        "publisher_context",
        "expert_knowledge",
        "tool_prompt",
    )

    @staticmethod
    def _bounded_text(value: Any, limit: int) -> tuple[str, bool]:
        text = str(value or "")
        return text[:limit], len(text) > limit

    @classmethod
    def _bounded_records(
        cls,
        records: Any,
        *,
        max_items: int,
        max_chars: int,
        item_excerpt_chars: int = 1200,
    ) -> tuple[list[dict[str, Any]], bool]:
        if not isinstance(records, list):
            return [], bool(records)
        bounded: list[dict[str, Any]] = []
        truncated = len(records) > max_items
        total_chars = 0
        for item in records[:max_items]:
            if not isinstance(item, dict):
                truncated = True
                continue
            value = dict(item)
            if "content" in value:
                content = str(value.get("content") or "")
                value["content"] = content[:item_excerpt_chars]
                truncated = truncated or len(content) > item_excerpt_chars
            if "excerpt" in value:
                excerpt = str(value.get("excerpt") or "")
                value["excerpt"] = excerpt[:item_excerpt_chars]
                truncated = truncated or len(excerpt) > item_excerpt_chars
            encoded_length = sum(len(str(part)) for part in value.values())
            if total_chars + encoded_length > max_chars:
                truncated = True
                break
            bounded.append(value)
            total_chars += encoded_length
        return bounded, truncated

    @classmethod
    def _enforce_aggregate_budget(
        cls,
        skill_context: dict[str, Any],
        truncated: dict[str, bool],
    ) -> int:
        """Trim lower-priority advisory fields to one total model budget."""
        fields = tuple(
            key for key in cls._CONTEXT_LIMITS
            if isinstance(skill_context.get(key), str)
        )
        total = sum(len(skill_context[key]) for key in fields)
        overflow = max(0, total - cls._AGGREGATE_CONTEXT_LIMIT)
        for key in cls._CONTEXT_TRIM_PRIORITY:
            if overflow <= 0:
                break
            value = str(skill_context.get(key) or "")
            if not value:
                continue
            trim = min(len(value), overflow)
            skill_context[key] = value[:len(value) - trim]
            truncated[key] = True
            overflow -= trim
        return sum(len(skill_context[key]) for key in fields)

    @staticmethod
    def _budget_snapshot(session: Any) -> dict[str, Any]:
        skill_context = session.ctx.metadata.get("skill_context", {})
        budget = skill_context.get("context_budget", {})
        if not isinstance(budget, dict):
            return {}
        return {
            "aggregate_limit": budget.get("aggregate_limit"),
            "aggregate_used": budget.get("aggregate_used"),
            "total_truncated": bool(budget.get("total_truncated")),
            "truncated_fields": sorted(
                str(key) for key in (budget.get("truncated") or {})
                if key
            ),
        }

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
                        session_id=(
                            session_id
                            if candidate.get("session_bound")
                            or candidate.get("kind") == "working"
                            else None
                        ),
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
                    "context_budget": self._budget_snapshot(session),
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
                    "context_budget": self._budget_snapshot(session),
                },
            )

    @classmethod
    def _store_skill_context(
        cls,
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
        if not isinstance(skill_context, dict):
            skill_context = {}
        budget = cls._CONTEXT_LIMITS
        truncated: dict[str, bool] = {}
        for key in ("tool_prompt", "expert_knowledge", "publisher_context"):
            value, was_truncated = cls._bounded_text(
                skill_context.get(key), budget[key]
            )
            skill_context[key] = value
            truncated[key] = was_truncated

        knowledge, knowledge_truncated = cls._bounded_records(
            skill_context.get("knowledge"),
            max_items=cls._MAX_KNOWLEDGE_RECORDS,
            max_chars=budget["knowledge"],
        )
        skill_context["knowledge"] = knowledge
        truncated["knowledge"] = knowledge_truncated

        prior_results, prior_truncated = cls._bounded_text(
            runtime._build_prior_tool_results_context(session),
            budget["prior_tool_results"],
        )
        memory, memory_truncated = cls._bounded_records(
            context.recalled_memories,
            max_items=cls._MAX_MEMORY_RECORDS,
            max_chars=2400,
        )
        memory_context, memory_context_truncated = cls._bounded_text(
            context.memory_context, budget["memory_context"]
        )
        digest, digest_truncated = cls._bounded_text(
            session.ctx.metadata.get("conversation_digest", ""),
            budget["conversation_digest"],
        )
        skill_context["prior_tool_results"] = prior_results
        skill_context["memory"] = memory
        skill_context["memory_context"] = memory_context
        skill_context["conversation_digest"] = digest
        truncated.update({
            "prior_tool_results": prior_truncated,
            "memory": memory_truncated,
            "memory_context": memory_context_truncated,
            "conversation_digest": digest_truncated,
        })
        aggregate_used = cls._enforce_aggregate_budget(skill_context, truncated)
        skill_context["context_budget"] = {
            "limits": dict(budget),
            "aggregate_limit": cls._AGGREGATE_CONTEXT_LIMIT,
            "aggregate_used": aggregate_used,
            "used": {
                key: (
                    len(value) if isinstance(value, str)
                    else len(value) if isinstance(value, list)
                    else 0
                )
                for key, value in skill_context.items()
                if key in budget
            },
            "truncated": {
                key: value for key, value in truncated.items() if value
            },
            "total_truncated": any(truncated.values()),
        }
        session.ctx.metadata["skill_context"] = skill_context


__all__ = ["AdTurnContext", "AdTurnContextService"]
