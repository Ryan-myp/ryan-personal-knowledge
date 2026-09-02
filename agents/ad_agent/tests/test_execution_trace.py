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


def test_trace_snapshot_is_available_without_an_observer():
    trace = ExecutionTrace(turn_id="turn-snapshot")

    trace.start()
    trace.stage_status("intent", "Intent 识别", "running", safe_input={"request": "查询报表"})
    trace.stage_status("intent", "Intent 识别", "succeeded", safe_output={"intent_type": "report"})
    trace.done("succeeded")

    snapshot = trace.snapshot()
    assert snapshot["turn_id"] == "turn-snapshot"
    assert snapshot["status"] == "succeeded"
    assert [event["type"] for event in snapshot["events"]] == [
        "start", "stage_started", "stage_status", "done"
    ]


def test_trace_emits_real_lifecycle_stages_and_keeps_plan_metadata():
    events = []
    plan = ExecutionPlan(
        schema_version="1.0",
        intent_type="list_campaigns",
        nodes=(PlanNode("node-0001", 1, "google", "google.list_campaigns", "list", "campaign"),),
    )
    trace = ExecutionTrace(events.append, turn_id="turn-3")

    trace.start()
    trace.stage_status("intent", "Intent 识别", "running", subtitle="理解用户目标")
    trace.stage_status("intent", "Intent 识别", "succeeded", subtitle="已识别")
    trace.bind_plan(plan)
    trace.stage_status("reply", "回复生成", "running")
    trace.stage_status("reply", "回复生成", "succeeded")
    trace.done()

    assert [event["type"] for event in events] == [
        "start", "stage_started", "stage_status", "plan",
        "stage_started", "stage_status", "done",
    ]
    assert events[1]["node_id"] == "stage:intent"
    assert events[1]["kind"] == "stage"
    assert events[3]["execution_plan"]["nodes"][0]["tool"] == "google.list_campaigns"
    assert events[3]["execution_plan"]["nodes"][0]["platform"] == "google"


def test_trace_registers_feature_discovered_tool_before_status_events():
    events = []
    trace = ExecutionTrace(events.append, turn_id="turn-4")
    trace.bind_plan(
        ExecutionPlan(
            schema_version="1.0",
            intent_type="cross_channel_compare",
            nodes=(PlanNode("node-0001", 1, "meta", "meta.list_campaigns", "list", "campaign"),),
        )
    )

    node = trace.register_dynamic_node(
        "meta", "meta.get_campaign_report", action="report", resource_type="report"
    )
    trace.node_status(node, "running")

    assert events[-2]["type"] == "node_discovered"
    assert events[-2]["tool"] == "meta.get_campaign_report"
    assert node["depends_on"] == ["node-0001"]
    assert events[-1]["node_id"] == node["node_id"]


def test_trace_emits_formatted_safe_input_and_output_without_credentials():
    events = []
    trace = ExecutionTrace(events.append, turn_id="turn-5")
    trace.bind_plan(
        ExecutionPlan(
            schema_version="1.0",
            intent_type="list_campaigns",
            nodes=(PlanNode("node-0001", 1, "google", "google.list_campaigns", "list", "campaign"),),
        )
    )
    node = trace.node_for("google", "google.list_campaigns")

    trace.node_status(
        node,
        "running",
        safe_input={"customer_id": "123", "nested": {"access_token": "secret"}},
    )
    trace.node_status(
        node,
        "succeeded",
        safe_output={
            "success": True,
            "rows": [{"name": "Campaign 1", "clicks": 12}],
            "client_secret": "secret",
        },
    )

    started, finished = events[-2:]
    assert started["safe_input"]["customer_id"] == "123"
    assert "access_token" not in str(started["safe_input"])
    assert finished["safe_output"]["success"] is True
    assert "secret" not in str(finished["safe_output"])
    assert "client_secret" not in str(finished["safe_output"])
