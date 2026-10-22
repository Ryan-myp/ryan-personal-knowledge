import pytest

from agents.agent_platform.evals.model_metrics import ModelMetrics


def test_metrics_retain_numeric_counts_without_prompt_content_or_credentials():
    metrics = ModelMetrics()
    metrics({
        "type": "model_start", "model_call_id": "one",
        "message_chars": 1200, "message_count": 5, "tool_count": 8,
        "prepare_duration_ms": 7, "api_key": "PRIVATE",
    })
    metrics({"type": "model_end", "model_call_id": "one", "duration_ms": 100})
    metrics({"type": "model_start", "model_call_id": "two", "message_chars": 1500})
    metrics({"type": "model_error", "model_call_id": "two", "duration_ms": 50})
    report = metrics.snapshot()
    assert report["attempts"] == 2
    assert report["completed"] == 1
    assert report["failed"] == 1
    assert report["duration_ms"] == 150
    assert report["message_chars_total"] == 2700
    assert report["message_chars_peak"] == 1500
    assert report["prepare_duration_ms"] == 7
    assert "PRIVATE" not in str(report)


@pytest.mark.parametrize("value", ["100", True, float("nan"), float("inf"), -4, {}])
def test_metrics_ignore_malformed_numbers(value):
    metrics = ModelMetrics()
    metrics({"type": "model_start", "model_call_id": "one", "message_chars": value})
    metrics({"type": "model_end", "model_call_id": "one", "duration_ms": value})
    assert metrics.snapshot()["duration_ms"] == 0
    assert metrics.snapshot()["message_chars_total"] == 0


def test_metrics_are_bounded_and_ignore_duplicates_and_unmatched_completion():
    metrics = ModelMetrics(max_attempts=2)
    for index in range(4):
        metrics({"type": "model_start", "model_call_id": str(index), "message_chars": 10})
        metrics({"type": "model_start", "model_call_id": str(index), "message_chars": 10})
        metrics({"type": "model_end", "model_call_id": str(index), "duration_ms": 5})
        metrics({"type": "model_end", "model_call_id": str(index), "duration_ms": 5})
    report = metrics.snapshot()
    assert report["attempts"] == report["completed"] == 2
    assert report["duration_ms"] == 10
    assert report["truncated"] is True
