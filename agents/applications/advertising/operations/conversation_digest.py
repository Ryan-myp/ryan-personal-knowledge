"""Bounded, source-aware compaction for older conversation requests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from agents.agent_harness.redaction import redact_for_persistence

_MAX_DIGEST_CHARS = 2400
_MAX_REQUESTS = 12
_MAX_REQUEST_CHARS = 360
_USER_PREFIXES = ("- 用户：", "- 用户:")


def compact_conversation_digest(
    previous: Any,
    user_requests: Iterable[Any] = (),
    *,
    redactor: Callable[[Any], Any] = redact_for_persistence,
) -> str:
    """Keep recent, unique user requests; never promote assistant output."""
    requests = _read_user_requests(previous)
    requests.extend(user_requests)
    unique: list[str] = []
    seen: set[str] = set()
    for request in requests:
        content = redactor(request)
        content = " ".join(str(content or "").split())
        if len(content) > _MAX_REQUEST_CHARS:
            content = content[:220] + "…[中间内容已折叠]…" + content[-110:]
        key = content.casefold()
        if not content:
            continue
        if key in seen:
            unique = [item for item in unique if item.casefold() != key]
        else:
            seen.add(key)
        unique.append(content)

    unique = unique[-_MAX_REQUESTS:]
    digest = "\n".join(f"- 用户：{request}" for request in unique)
    while unique and len(digest) > _MAX_DIGEST_CHARS:
        unique.pop(0)
        digest = "\n".join(f"- 用户：{request}" for request in unique)
    return digest


def _read_user_requests(value: Any) -> list[str]:
    previous = str(value or "")[-_MAX_DIGEST_CHARS * 4:]
    requests = []
    for line in previous.splitlines():
        normalized = line.strip()
        prefix = next(
            (item for item in _USER_PREFIXES if normalized.startswith(item)),
            None,
        )
        if prefix:
            requests.append(normalized[len(prefix):])
    return requests


__all__ = ["compact_conversation_digest"]
