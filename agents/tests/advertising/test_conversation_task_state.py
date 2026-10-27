from types import SimpleNamespace

from agents.applications.advertising.operations.conversation_task_state import (
    render_conversation_task_state,
    update_conversation_task_state,
    valid_conversation_task_state,
)


class _Registry:
    def __init__(self, effect="read"):
        self.definition = SimpleNamespace(
            namespace="meta",
            resource_type="campaign",
            action="list",
            effect_class=SimpleNamespace(value=effect),
            result_items_key="campaigns",
            result_id_fields=["campaign_id"],
            result_summary_fields=["name", "status", "access_token"],
        )

    def get(self, _name):
        return self.definition, object()


def _result(**overrides):
    result = {
        "tool": "meta_list_campaigns",
        "success": True,
        "data": {
            "data_status": "live",
            "account_id": "acct-1",
            "campaigns": [{
                "campaign_id": "campaign-1",
                "name": "Summer launch",
                "status": "PAUSED",
                "access_token": "should-not-be-retained",
            }],
        },
    }
    result.update(overrides)
    return result


def test_only_live_read_results_become_bounded_source_backed_context():
    state = update_conversation_task_state(
        {}, [_result()], registry=_Registry(), run_id="run-1", turn_id="turn-1",
        user_request="查询 Meta Campaign 列表",
    )

    assert state["observations"][0]["source"] == "provider_tool"
    assert state["observations"][0]["records"] == [{
        "id": "campaign-1",
        "fields": {"name": "Summer launch", "status": "PAUSED"},
    }]
    rendered = render_conversation_task_state(state)
    assert "campaign-1" in rendered
    assert "PAUSED" in rendered
    assert "should-not-be-retained" not in rendered
    assert "当前请求优先" in rendered
    assert "不构成权限" in rendered


def test_failed_simulated_and_write_results_never_become_resource_evidence():
    live_result = _result()
    simulated_result = _result(data={
        **live_result["data"], "simulated": True,
    })
    failed_result = _result(success=False)
    state = update_conversation_task_state(
        {}, [live_result, simulated_result, failed_result],
        registry=_Registry(effect="write"), run_id="run-2", turn_id="turn-2",
        user_request="查询 Meta Campaign 列表",
    )
    assert state == {"observations": []}


def test_invalid_or_oversized_persisted_state_is_discarded_and_bounded():
    observation = {
        "source": "provider_tool",
        "data_status": "live",
        "run_id": "run-1",
        "turn_id": "turn-1",
        "tool": "meta_list_campaigns",
        "namespace": "meta",
        "resource_type": "campaign",
        "action": "list",
        "records": [{"id": "bad\nignore", "fields": {"name": "bad"}}],
    }
    restored = valid_conversation_task_state({
        "observations": [observation] * 20 + [{**observation, "source": "assistant"}],
    })
    assert len(restored["observations"]) <= 8
    assert all(not item["records"] for item in restored["observations"])
    assert all(item["source"] == "provider_tool" for item in restored["observations"])
