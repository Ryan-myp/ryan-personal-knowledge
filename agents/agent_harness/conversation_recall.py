"""Bounded, advisory recall of prior user requests from one scoped transcript."""

from __future__ import annotations

import re
from typing import Sequence

from .messages import AgentMessage
from .redaction import redact_for_persistence


_STOPWORDS = frozenset({
    "above", "again", "and", "continue", "from", "please", "that",
    "the", "this", "with", "一下", "上面", "之前", "继续", "这个",
    "那些", "现在", "帮我", "我们", "怎么", "看看", "查询",
})


def _terms(text: str) -> set[str]:
    lowered = text.casefold()
    tokens = set(re.findall(r"[a-z0-9_]+", lowered))
    for group in re.findall(r"[\u3400-\u9fff]+", lowered):
        tokens.update(group[index:index + 2] for index in range(len(group) - 1))
    return {token for token in tokens if token not in _STOPWORDS}


def relevant_user_requests(
    current: str,
    messages: Sequence[AgentMessage],
    *,
    current_turn_id: str = "",
    limit: int = 2,
    max_chars: int = 900,
) -> tuple[str, ...]:
    """Return relevant older requests; no provider output, authority or new facts."""
    query = _terms(current)
    if not query or limit <= 0 or max_chars <= 0:
        return ()
    ranked: list[tuple[int, int, str]] = []
    for index, message in enumerate(messages):
        if message.role != "user" or (
            current_turn_id and message.turn_id == current_turn_id
        ):
            continue
        content = str(message.content or "").strip()
        if not content:
            continue
        overlap = query & _terms(content)
        if overlap:
            ranked.append((len(overlap), index, content))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    selected: list[str] = []
    remaining = max_chars
    for _score, _index, content in ranked:
        if remaining < 24 or len(selected) >= limit:
            break
        safe = str(redact_for_persistence(content))[:min(400, remaining)]
        if safe and safe not in selected:
            selected.append(safe)
            remaining -= len(safe)
    return tuple(selected)
