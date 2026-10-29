"""Newest Tool evidence remains complete and bounded across follow-up turns."""

import json
from types import SimpleNamespace

from agents.agent_harness.core.interfaces import ToolContext, ToolResult
from agents.agent_harness.redaction import redact_for_persistence
from agents.applications.advertising.operations.session_context import SessionContext
from agents.applications.advertising.run.ad_runtime_context import AdvertisingRuntimeContext


def test_prior_results_favor_latest_evidence_and_remain_valid_json():
    runtime = SimpleNamespace(_redact_for_persistence=redact_for_persistence)
    service = AdvertisingRuntimeContext(runtime)
    session = SessionContext("s", ToolContext("s", "u"))
    for index in range(8):
        session.save_result(f"read_{index}", ToolResult.ok({
            "id": f"resource-{index}", "payload": "正文\"\\" * 5000,
        }))
    window = service.prior_tool_results(session, max_chars=2600)
    assert window.startswith("[read_7] ")
    assert "resource-7" in window
    assert len(window) <= 2600
    for line in window.splitlines():
        payload = json.loads(line.split("] ", 1)[1])
        assert payload["success"] is True
        assert payload["output_truncated"] is True


def test_repeated_tool_result_is_moved_to_the_most_recent_position():
    session = SessionContext("s", ToolContext("s", "u"))
    session.save_result("read_first", ToolResult.ok({"id": "old"}))
    session.save_result("read_second", ToolResult.ok({"id": "second"}))
    session.save_result("read_first", ToolResult.ok({"id": "new"}))
    runtime = SimpleNamespace(_redact_for_persistence=redact_for_persistence)
    window = AdvertisingRuntimeContext(runtime).prior_tool_results(session, max_results=1)
    assert window.startswith("[read_first] ")
    assert '"new"' in window


def test_no_evidence_is_exposed_for_zero_or_negative_window_limits():
    session = SimpleNamespace(tool_results={"read": ToolResult.ok({"id": "x"})})
    runtime = SimpleNamespace(_redact_for_persistence=redact_for_persistence)
    service = AdvertisingRuntimeContext(runtime)
    for options in ({"max_results": 0}, {"max_results": -1}, {"max_chars": 0}):
        assert service.prior_tool_results(session, **options) == ""


def test_prior_results_redact_secrets_without_mutating_retained_data():
    result = ToolResult.ok({"id": "x", "client_secret": "PRIVATE"})
    session = SimpleNamespace(tool_results={"read": result})
    runtime = SimpleNamespace(_redact_for_persistence=redact_for_persistence)
    window = AdvertisingRuntimeContext(runtime).prior_tool_results(session)
    assert "PRIVATE" not in window
    assert result.data["client_secret"] == "PRIVATE"
