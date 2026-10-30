"""Task success includes intermediate turns, not just a plausible last reply."""

import pytest

from scripts.advertising.run_conversation_regressions import RegressionCase, run_suite


def task_case(**overrides):
    return RegressionCase.model_validate({
        "id": "task", "history": ["只读账户 A", "改查账户 B"], "input": "总结",
        "assertions": {"reply_contains": ["完成"]},
        "checkpoints": [{"turn": 2, "assertions": {
            "tool_arguments": [{"tool": "read", "equals": {"account_id": "B"}}],
        }}],
        "task_forbidden_tools": ["write"], **overrides,
    })


def evidence():
    from agents.agent_platform.evals.execution_evidence import argument_fingerprints
    return {"reply": "完成", "turn_evidence": [
        {"reply": "已记住", "results": []},
        {"reply": "已查到", "results": [{"tool": "read", "success": True,
         "argument_fingerprints": argument_fingerprints({"account_id": "B"})}]},
        {"reply": "完成", "results": []},
    ]}


def grade(response):
    return run_suite([task_case()], lambda _: response, mode="fixture_contract")


def test_task_gate_checks_intermediate_parameters_and_all_turn_prohibitions():
    assert grade(evidence())["passed"] == 1
    wrong = evidence()
    wrong["turn_evidence"][1]["results"][0]["argument_fingerprints"] = {}
    assert grade(wrong)["failed"] == 1
    unsafe = evidence()
    unsafe["turn_evidence"][0]["results"] = [{"tool": "write", "success": False}]
    report = grade(unsafe)
    assert report["failed"] == 1
    assert "turn:1:forbidden_tool:write" in report["cases"][0]["failures"]


@pytest.mark.parametrize("rows", [None, [], [{"reply": "完成"}]])
def test_missing_turn_evidence_cannot_pass(rows):
    assert grade({"reply": "完成", "turn_evidence": rows})["error"] == 1


def test_checkpoint_bounds_and_long_conversation_input_budget():
    assert len(task_case(history=["继续核对约束"] * 49).history) == 49
    for changes in (
        {"history": ["继续"] * 50},
        {"history": ["x" * 4000] * 49},
        {"checkpoints": [{"turn": 4, "assertions": {"reply_nonempty": True}}]},
        {"checkpoints": [{"turn": 1, "assertions": {}}]},
    ):
        with pytest.raises(ValueError):
            task_case(**changes)


def test_task_evidence_does_not_leak_replies_to_summary():
    response = evidence()
    response["turn_evidence"][0]["reply"] = "PRIVATE USER DETAIL"
    assert "PRIVATE" not in str(grade(response))


def test_skill_up_keeps_per_turn_results_for_long_tasks(tmp_path):
    from agents.evals.advertising.skill_up_engine import run
    from agents.tests.advertising.harness_models import ScriptedHarnessModel
    from agents.agent_harness.messages import ModelTurn

    model = ScriptedHarnessModel(*(ModelTurn(content="仅讨论方案，未执行。") for _ in range(30)))
    result = run({"case_id": "long-task", "workspace": str(tmp_path), "messages": [
        {"role": "user", "content": "只讨论方案，不查询账户。"} for _ in range(30)
    ]}, model_adapter=model)
    turns = result["metadata"]["runtime_result"]["turn_evidence"]
    assert len(turns) == 30
    assert all(turn["phase_metrics"]["runs"] == 1 for turn in turns)
    assert all(turn["model_metrics"]["attempts"] == 1 for turn in turns)
    assert result["metadata"]["runtime_result"]["phase_metrics"]["runs"] == 30


def test_fifty_turn_compaction_restores_latest_constraints_without_old_budget():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.applications.advertising.persistence.store import AdAgentStore
    from agents.applications.advertising.operations.conversation_state import render_conversation_state

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store,
        features=[], start_background_workers=False)
    try:
        session = runtime._ensure_session("long-session", "owner", None, {}, tenant_id="tenant")
        for index in range(50):
            text = f"只讨论素材测试的方法，第{index}轮，不查询账户。"
            if index == 0: text = "Meta campaign 预算必须是100"
            if index == 10: text = "Meta campaign 创建状态必须保持 paused"
            if index == 30: text = "将 Meta campaign 预算改为80"
            runtime.persist_conversation_turn(session, f"turn-{index}", text, "仅讨论，未执行")
        fresh = AdvertisingComposition(require_llm=False, persistence_store=store,
            features=[], start_background_workers=False)
        try:
            restored = fresh._ensure_session("long-session", "owner", None, {}, tenant_id="tenant")
            state = render_conversation_state(restored.ctx.metadata["conversation_state"],
                                               "继续 Meta campaign 的预算和创建状态")
            assert "80" in state and "paused" in state
            assert "100" not in state
            assert restored.ctx.metadata["conversation_turn_count"] == 50
        finally:
            fresh.close(wait=True)
    finally:
        runtime.close(wait=True)
        store.close()
