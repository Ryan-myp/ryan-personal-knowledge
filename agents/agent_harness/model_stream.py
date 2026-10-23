"""Bounded stream assembly independent of providers and Run lifecycle."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Callable, Mapping

from .messages import ModelTurn
from .model_limits import ModelOutputLimitError, model_output_chars

logger = logging.getLogger(__name__)


def consume_model_stream(
    iterator: Any,
    *,
    max_chars: int,
    max_chunks: int,
    delta_chars: int,
    parse_calls: Callable[..., Any],
    check: Callable[[], None],
    emit_delta: Callable[[str], None],
    emit_reasoning: Callable[[str], None] | None = None,
) -> ModelTurn:
    parts: list[str] = []
    calls = []
    final: ModelTurn | None = None
    used = 0
    failed = False
    try:
        for index, chunk in enumerate(iterator):
            check()
            if index >= max_chunks:
                raise ModelOutputLimitError()
            if isinstance(chunk, ModelTurn):
                if model_output_chars(chunk) > max_chars:
                    raise ModelOutputLimitError()
                final = chunk
                continue
            delta, reasoning_delta, chunk_calls = _stream_chunk(
                chunk, parse_calls,
            )
            used += model_output_chars(ModelTurn(content=delta, tool_calls=chunk_calls))
            if used > max_chars:
                raise ModelOutputLimitError()
            calls.extend(chunk_calls)
            if reasoning_delta and emit_reasoning is not None:
                for offset in range(0, len(reasoning_delta), delta_chars):
                    check()
                    emit_reasoning(
                        reasoning_delta[offset:offset + delta_chars],
                    )
            if not delta:
                continue
            parts.append(delta)
            for offset in range(0, len(delta), delta_chars):
                check()
                emit_delta(delta[offset:offset + delta_chars])
        check()
        return _final_turn(final, parts, calls, max_chars)
    except BaseException:
        failed = True
        raise
    finally:
        _close_stream(iterator, failed)


def _final_turn(final: Any, parts: list[str], calls: list[Any], max_chars: int) -> ModelTurn:
    if final is None:
        final = ModelTurn(content="".join(parts), tool_calls=tuple(calls))
    elif parts or calls:
        final = replace(
            final,
            content="".join(parts) if parts else final.content,
            tool_calls=tuple(final.tool_calls or calls),
        )
    if model_output_chars(final) > max_chars:
        raise ModelOutputLimitError()
    return final


def _close_stream(iterator: Any, failed: bool) -> None:
    close = getattr(iterator, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception as error:
        # Provider cleanup must not replace an existing timeout or cancellation.
        if not failed:
            raise
        logger.warning("Model stream cleanup failed: %s", type(error).__name__)


def _stream_chunk(
    chunk: Any,
    parse_calls: Callable[..., Any],
) -> tuple[str, str, Any]:
    if isinstance(chunk, str):
        return chunk, "", ()
    if isinstance(chunk, Mapping):
        reasoning_delta = chunk.get(
            "reasoning_delta",
            chunk.get("reasoning", ""),
        )
        delta = chunk.get("delta", chunk.get("content", ""))
        return (
            str(delta) if delta is not None else "",
            str(reasoning_delta) if reasoning_delta is not None else "",
            parse_calls(chunk.get("tool_calls") or ()),
        )
    return "", "", ()
