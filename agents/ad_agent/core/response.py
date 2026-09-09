"""Generic response rendering contract for Agent Runtime."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol
from .agent_profile import AgentProfile


class ResponseRenderer(Protocol):
    """Render a turn result without participating in execution or routing."""

    renderer_name: str

    def render(
        self,
        intent: Any,
        results: list[dict[str, Any]],
        needs_confirmation: bool,
        analysis: dict[str, Any] | None = None,
    ) -> str:
        ...

    def render_chat(self, user_input: str) -> str:
        ...


class ResponseSynthesizer(Protocol):
    """Model-backed final-answer boundary, separate from execution."""

    def synthesize(
        self,
        llm: Any,
        *,
        user_input: str,
        intent: Any,
        results: list[dict[str, Any]],
        knowledge: list[dict[str, Any]] | None,
        analysis: dict[str, Any] | None,
        fallback_reply: str,
        needs_confirmation: bool = False,
        memory: list[dict[str, Any]] | None = None,
    ) -> str | None:
        ...


class LLMResponseSynthesizer:
    """Produce a grounded user answer from already-executed local results.

    The model receives result data only; it cannot call tools from this
    boundary.  A failed/invalid synthesis returns ``None`` so the application
    renderer remains the deterministic safety fallback.
    """

    _SECRET_RE = re.compile(
        r"(?i)(?:access[_ -]?token|refresh[_ -]?token|developer[_ -]?token|"
        r"client[_ -]?(?:secret|id)|app[_ -]?secret|private[_ -]?key|"
        r"authorization|password|credentials?|bc[_ -]?id|mcc|partner[_ -]?id)"
        r"\s*[:=]\s*[^\s,;]+"
    )
    STABLE_SYSTEM_PROMPT = (
        "[STABLE] 你是一个严谨、可审计的 Agent 回复助手。"
        "只基于已提供的用户问题、意图、知识引用、受控 Memory 和已执行结果回答；"
        "不调用工具、不编造平台数据、不改变执行状态。"
        "优先使用用户使用的语言并保留关键数量、状态和时间范围。"
    )

    def __init__(self, profile: AgentProfile | None = None):
        self.profile = profile or AgentProfile()
        self.stable_system_prompt = (
            self.STABLE_SYSTEM_PROMPT + "\n\n" + self.profile.prompt_block()
        )

    @classmethod
    def _safe_payload(cls, value: Any, max_chars: int = 12000) -> str:
        try:
            encoded = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            encoded = str(value)
        return cls._SECRET_RE.sub("<redacted>", encoded)[:max_chars]

    @staticmethod
    def _valid_answer(answer: str, results: list[dict[str, Any]], fallback: str) -> bool:
        text = str(answer or "").strip()
        if not text or len(text) > 4000:
            return False
        # A misconfigured/mock model may return the intent JSON again instead
        # of a user-facing answer. Never expose that internal protocol.
        if text.startswith("{") and '"intent_type"' in text:
            return False
        # A model must not turn an all-failed execution into a success claim.
        if results and not any(bool(item.get("success")) for item in results):
            success_words = ("已成功", "成功完成", "操作完成", "已经完成")
            if any(word in text for word in success_words):
                return False
        simulated = any(
            isinstance(item.get("data"), dict)
            and item["data"].get("simulated")
            for item in results
        )
        if simulated and not any(marker in text.lower() for marker in ("dry-run", "模拟", "预览", "尚未修改")):
            return False
        if "access_token" in text.lower() or "refresh_token" in text.lower():
            return False
        # Internal execution vocabulary belongs in the trace/audit view, not
        # in the operator's answer. Reject it so the deterministic renderer
        # can provide a business-facing fallback when the model ignores this
        # presentation contract.
        internal_terms = (
            "dry-run", "runtime", "tool", "provider client", "platform_params", "api",
            "intent_type", "schema", "线上写 api", "api client",
        )
        if any(term in text.lower() for term in internal_terms):
            return False
        return True

    def synthesize(
        self,
        llm: Any,
        *,
        user_input: str,
        intent: Any,
        results: list[dict[str, Any]],
        knowledge: list[dict[str, Any]] | None,
        analysis: dict[str, Any] | None,
        fallback_reply: str,
        needs_confirmation: bool = False,
        memory: list[dict[str, Any]] | None = None,
    ) -> str | None:
        if llm is None or needs_confirmation:
            return None
        context_prompt = (
            "[CONTEXT] 当前请求与可引用依据：\n"
            f"用户问题：{str(user_input)[:4000]}\n"
            f"意图：{self._safe_payload(getattr(intent, 'to_dict', lambda: intent)())[:2000]}\n"
            f"知识引用：{self._safe_payload(knowledge or [], 5000)}"
        )
        volatile_prompt = (
            "[VOLATILE] 本轮执行数据与呈现约束：\n"
            f"已执行结果：{self._safe_payload(results)}\n"
            f"受控 Memory：{self._safe_payload(memory or [], 3000)}\n"
            f"分析结果：{self._safe_payload(analysis or {}, 5000)}\n"
            f"兜底答案：{str(fallback_reply)[:4000]}\n\n"
            "禁止出现 Runtime、Tool、schema、intent、Provider、dry-run、API 等开发术语。"
            "预览类操作请说‘已生成预览，尚未修改广告账户’；查询失败要说明现状和下一步。"
        )
        try:
            answer = llm.call([
                {"role": "system", "content": self.stable_system_prompt},
                {"role": "system", "content": context_prompt},
                {"role": "system", "content": volatile_prompt},
                {"role": "user", "content": "请根据以上 Stable、Context、Volatile 内容生成最终用户答复。"},
            ])
        except Exception:
            return None
        return str(answer).strip() if self._valid_answer(answer, results, fallback_reply) else None
