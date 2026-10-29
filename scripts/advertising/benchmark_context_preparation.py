"""离线测量工具元数据评分和长任务结果压缩，不创建客户端或调用 Provider。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agents.agent_harness.core import tool_selection
from agents.agent_harness.evidence_compaction import compact_read_messages
from agents.agent_harness.messages import AgentMessage
from agents.agent_harness.model_limits import model_message_chars


def _score_all(definitions: list, query: set) -> list[int]:
    return [tool_selection._relevance_score(query, item) for item in definitions]


def _sample(operation, samples: int = 20):
    times = []
    result = None
    for _ in range(samples):
        start = time.perf_counter()
        result = operation()
        times.append((time.perf_counter() - start) * 1000)
    return result, round(median(times), 3)


def _metadata_benchmark(definitions: list) -> dict:
    query = tool_selection._terms("查询最近七天 campaign 数据 report budget")
    def uncached(value):
        return frozenset(tool_selection._terms(value))

    with patch.object(tool_selection, "_metadata_terms", new=uncached):
        baseline, baseline_ms = _sample(lambda: _score_all(definitions, query))
    tool_selection._cached_metadata_terms.cache_clear()
    _score_all(definitions, query)
    current, current_ms = _sample(lambda: _score_all(definitions, query))
    if baseline != current:
        raise AssertionError("metadata cache changed relevance scores")
    return {
        "scope": "scoring_all_registered_contracts_not_full_selection_or_model_latency",
        "tools": len(definitions), "samples_per_path": 20,
        "uncached_p50_ms": baseline_ms, "cached_p50_ms": current_ms,
        "scores_identical": True,
        "cache": tool_selection._cached_metadata_terms.cache_info()._asdict(),
    }


def _compaction_benchmark() -> dict:
    definition = {"name": "records", "effect_class": "read", "result_items_key": "items",
                  "result_id_fields": ["id"], "result_summary_fields": ["status"]}
    messages = [AgentMessage.user("分析所有已返回的数据，保持资源状态不变")]
    for index in range(8):
        call_id = f"page-{index}"
        messages.extend([
            AgentMessage.assistant("", metadata={"tool_calls": [
                {"id": call_id, "name": "records", "arguments": {"page": index}},
            ]}),
            AgentMessage.tool({"success": True, "data": {
                "items": [{"id": f"{index}-{row}", "status": "PAUSED", "text": "x" * 800}
                          for row in range(20)],
                "query_summary": {"returned_count": 20, "scope": "returned_page"},
            }}, tool_call_id=call_id, name="records"),
        ])
    before = sum(map(model_message_chars, messages))
    result, duration = _sample(lambda: compact_read_messages(
        messages, (definition,), max_chars=32_000, message_size=model_message_chars,
    ))
    after = sum(map(model_message_chars, result))
    preserved = [m.message_id for m in result] == [m.message_id for m in messages]
    if after > 32_000 or not preserved:
        raise AssertionError("compaction exceeded budget or removed call messages")
    return {
        "mode": "synthetic_read_results", "samples": 20, "p50_ms": duration,
        "before_message_chars": before, "after_message_chars": after,
        "message_char_budget": 32_000, "message_identity_preserved": preserved,
        "raw_message_chars_after": sum(map(model_message_chars, messages)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    snapshot_path = ROOT / "agents/tools/advertising/contracts/builtin_tools.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    definitions = [tool for group in snapshot["platforms"].values() for tool in group["tools"]]
    report = {"schema_version": "context-preparation-benchmark/v1", "provider_calls": 0,
              "model_calls": 0, "metadata_scoring": _metadata_benchmark(definitions),
              "read_compaction": _compaction_benchmark()}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
