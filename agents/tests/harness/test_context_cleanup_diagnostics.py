"""Cleanup failures stay observable without leaking provider error text."""

from types import SimpleNamespace

from agents.agent_harness import AgentApplication


def test_cleanup_failure_reports_type_without_erasing_success_or_leaking_text():
    events = []

    def fail_cleanup(*_):
        raise RuntimeError("private-context-material")

    app = AgentApplication.create(
        model=lambda *_: "done", event_callback=events.append,
        context_provider=SimpleNamespace(build_context=lambda *_: {}, cleanup=fail_cleanup),
    )
    try:
        result = app.prompt("hello")
        assert result.status.value == "succeeded"
        event = next(item for item in events if item["type"] == "context_cleanup_error")
        assert event["error_type"] == "RuntimeError"
        assert event["run_id"] == result.run_id
        assert "private-context-material" not in str(events)
    finally:
        app.close()
