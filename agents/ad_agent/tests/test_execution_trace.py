"""Execution trace contract tests; these never call a provider API."""

from agents.ad_agent.core.execution_plan import ExecutionPlan, PlanNode
from agents.ad_agent.core.execution_trace import ExecutionTrace


def test_trace_is_ordered_and_uses_plan_node_identity():
    events = []
    plan = ExecutionPlan(
        schema_version="1.0",
        intent_type="list_campaigns",
        nodes=(PlanNode("node-0001", 1, "meta", "meta.list_campaigns", "list", "campaign"),),
    )
    trace = ExecutionTrace(events.append, turn_id="turn-1")

    trace.start()
    trace.bind_plan(plan)
    node = trace.node_for("meta", "meta.list_campaigns")
    trace.node_status(node, "running")
    trace.node_status(node, "succeeded", safe_metadata={"duration_ms": 2.5})
    trace.done()

    assert [event["type"] for event in events] == [
        "start", "plan", "node_started", "node_status", "done"
    ]
    assert [event["seq"] for event in events] == [1, 2, 3, 4, 5]
    assert events[2]["node_id"] == "node-0001"
    assert events[3]["status"] == "succeeded"
    assert events[3]["safe_metadata"]["duration_ms"] >= 0


def test_trace_does_not_copy_credentials_or_raw_exception_text():
    events = []
    trace = ExecutionTrace(events.append, turn_id="turn-2")
    trace._emit(
        "node_status",
        status="failed",
        safe_metadata={
            "reason": "provider_error",
            "access_token": "should-not-appear",
            "raw": "client_secret=should-not-appear",
        },
    )

    payload = str(events[0])
    assert "should-not-appear" not in payload
    assert "access_token" not in payload
