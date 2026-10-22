"""Background task completion must follow evidence, not Python truthiness."""

import time

import pytest

from agents.agent_platform.infrastructure.durable import TaskExecutor, task_outcome_status
from agents.applications.advertising.persistence.store import AdAgentStore


@pytest.mark.parametrize("payload, expected", [
    ({"task_status": "succeeded", "effect_state": "unknown"}, "recovery_required"),
    ({"status": "succeeded", "error": "failed"}, "failed"),
    ({"task_status": "succeeded", "status": "failed"}, "failed"),
    ({"status": "succeeded", "results": [{"success": False}]}, "failed"),
    ({"status": "succeeded", "results": [{"success": True}, {"success": False}]}, "partially_failed"),
    ({"status": "succeeded", "results": [{"success": True, "effect_state": "unknown"}]}, "recovery_required"),
    ({"task_status": "succeeded", "needs_input": True}, "awaiting_input"),
    ({"needs_input": True, "status": "failed"}, "failed"),
    ({"status": "awaiting_input", "tool_results": [
        {"is_error": True, "needs_input": True},
    ]}, "awaiting_input"),
])
def test_task_status_cannot_hide_stronger_failure_evidence(payload, expected):
    assert task_outcome_status(payload) == expected


@pytest.mark.parametrize("payload", [
    {"success": "false"}, {"success": 1}, {"recovery_required": "false"},
    {"needs_input": None}, {"needs_confirmation": []},
    {"status": "queued"}, {"task_status": "not-a-terminal-state"},
    {"runtime_signals": "not-an-object"}, {"results": [{"success": "false"}]},
    {"results": ["not-an-outcome"]},
    {"effect_state": []},
])
def test_malformed_task_control_fields_are_not_coerced_to_success(payload):
    from agents.agent_platform.infrastructure.durable.task_executor import TaskOutcomeContractError

    with pytest.raises(TaskOutcomeContractError):
        task_outcome_status(payload)


@pytest.mark.parametrize("outcome", [
    {"success": "false", "detail": "untrusted"},
    {"runtime_signals": "untrusted"},
])
def test_invalid_handler_outcome_is_durable_recovery_required_not_success(outcome):
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store, max_workers=1, max_queue=0)
    executor.register_handler("bad", lambda _: outcome)
    try:
        task, _ = executor.submit("bad", {}, tenant_id="tenant", user_id="user")
        deadline = time.monotonic() + 2
        final = executor.get(task.task_id)
        while time.monotonic() < deadline and final.status in {"queued", "running"}:
            time.sleep(0.01)
            final = executor.get(task.task_id)
        assert final.status == "recovery_required"
        assert final.metadata["task_output_invalid"] is True
        assert final.metadata["effect_state"] == "unknown"
        assert "untrusted" not in final.error
        assert final.error
    finally:
        executor.shutdown(wait=True)
        store.close()


def test_truncated_handler_output_cannot_become_a_successful_task():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store)
    try:
        result = executor._safe_result({"status": "failed", "body": "x" * 2_000_100})
        assert result["truncated"]
        assert task_outcome_status(result) == "recovery_required"
    finally:
        executor.shutdown(wait=True)
        store.close()


def test_cancellation_cannot_hide_a_handler_reported_unknown_effect():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store, max_workers=1, max_queue=0)

    def handler(context):
        context.cancel_event.set()
        return {"status": "recovery_required", "effect_state": "unknown", "reply": "核对结果"}

    executor.register_handler("unknown", handler)
    try:
        task, _ = executor.submit("unknown", {}, tenant_id="tenant", user_id="user")
        deadline = time.monotonic() + 2
        final = executor.get(task.task_id)
        while time.monotonic() < deadline and final.status in {"queued", "running"}:
            time.sleep(0.01)
            final = executor.get(task.task_id)
        assert final.status == "recovery_required"
        assert final.result["effect_state"] == "unknown"
        assert final.error
    finally:
        executor.shutdown(wait=True)
        store.close()


@pytest.mark.parametrize("status", ["failed", "recovery_required", "awaiting_input"])
def test_canonical_run_result_is_not_stringified_into_an_opaque_success(status):
    from agents.agent_harness import RunResult, RunStatus

    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store)
    result = RunResult(status=RunStatus(status), reply="typed result")
    try:
        assert task_outcome_status(result) == status
        retained = executor._safe_result(result)
        assert isinstance(retained, dict)
        assert task_outcome_status(retained) == status
    finally:
        executor.shutdown(wait=True)
        store.close()


def test_generic_task_executor_redacts_results_and_errors_by_default():
    store = AdAgentStore(":memory:")
    executor = TaskExecutor(store)
    try:
        retained = executor._safe_result({
            "success": True,
            "access_token": "fixture-only",
            "detail": "api_key=fixture-only",
            "input_tokens": 12,
            "selection_token": "signed-selection",
        })
        assert retained["access_token"] == "<redacted>"
        assert "fixture-only" not in str(retained)
        assert retained["input_tokens"] == 12
        assert retained["selection_token"] == "signed-selection"
        assert "fixture-only" not in executor._safe_error(RuntimeError("api_key=fixture-only"))
    finally:
        executor.shutdown(wait=True)
        store.close()
