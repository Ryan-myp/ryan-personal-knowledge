"""Conversation title generation shared by the Agent Runtime and storage views."""

from __future__ import annotations

import json
import re
from typing import Any


class ConversationTitleGenerator:
    """Create short, user-facing conversation titles.

    The model is advisory here: it never routes a request or executes a Tool.
    A deterministic fallback keeps history usable when a model response is
    unavailable or violates the small title contract.
    """

    MAX_TITLE_CHARS = 32

    @classmethod
    def fallback_title(cls, user_input: str) -> str:
        text = re.sub(r"\s+", " ", str(user_input or "")).strip()
        text = re.sub(r"^(?:请帮我|帮我|麻烦你|麻烦|我想要|我想|我需要|能否|可以帮我)\s*", "", text)
        text = text.strip(" ，,：:。.!！?？")
        text = re.split(r"[。.!！?？;；\n]", text, maxsplit=1)[0].strip()
        if not text:
            return "新对话"
        action_match = re.match(
            r"^(查询|查看|获取|列出|分析|创建|搭建|优化|更新|删除|暂停|恢复|检查|比较|导出)\s*(.+)$",
            text,
        )
        if action_match:
            subject, action = action_match.group(2).strip(), action_match.group(1)
            subject = re.sub(r"^(?:一下|下|一下的|下的)\s*", "", subject)
            subject = re.sub(r"\b\d{6,}\b", "", subject)
            subject = re.sub(r"\s+下(?:的)?\s+", " ", subject)
            subject = re.sub(r"\s+", " ", subject).strip(" ，,：:")
            if not subject:
                return action
            text = f"{subject} · {action}"
        if len(text) > cls.MAX_TITLE_CHARS:
            return text[: cls.MAX_TITLE_CHARS - 1].rstrip() + "…"
        return text

    @classmethod
    def _extract_title(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            decoded = json.loads(text)
            if isinstance(decoded, dict):
                text = str(decoded.get("title") or "")
            elif isinstance(decoded, str):
                text = decoded
        except (TypeError, ValueError):
            pass
        text = re.sub(r"^```(?:json|text)?\s*|\s*```$", "", text, flags=re.I).strip()
        text = text.splitlines()[0].strip(" \t\"'`#")
        text = re.sub(r"^(?:标题|title)\s*[:：]\s*", "", text, flags=re.I)
        text = re.sub(r"\s+", " ", text).strip(" \t\"'`#")
        return text

    @classmethod
    def _valid_title(cls, title: str, source: str) -> bool:
        if len(title) < 2 or len(title) > cls.MAX_TITLE_CHARS:
            return False
        if title == source or title.lower() == source.lower():
            return False
        if title.startswith("{") or title.startswith("["):
            return False
        if any(term in title.lower() for term in ("intent_type", "platform_params", "provider client")):
            return False
        return True

    def generate(self, user_input: str, llm: Any = None) -> tuple[str, str]:
        source = re.sub(r"\s+", " ", str(user_input or "")).strip()
        fallback = self.fallback_title(source)
        if llm is None or not source:
            return fallback, "fallback"
        prompt = (
            "请把下面的广告业务请求总结成一个简短、易识别的历史对话标题。"
            "标题要体现主要平台、对象或任务，控制在 8-24 个中文字符或 6 个英文单词内。"
            "不要复述整句请求，不要加入序号、引号、Markdown 或开发术语。"
            "只返回 JSON，例如 {\"title\":\"广告资源报表\"}。\n\n"
            f"用户请求：{source[:2000]}"
        )
        try:
            response = llm.call([
                {"role": "system", "content": "你是对话历史标题摘要助手，只生成标题 JSON。"},
                {"role": "user", "content": prompt},
            ])
            title = self._extract_title(response)
        except Exception:
            return fallback, "fallback"
        if self._valid_title(title, source):
            return title, "llm"
        return fallback, "fallback"
