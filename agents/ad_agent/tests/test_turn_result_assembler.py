"""Focused tests for the provider-neutral turn result boundary."""

from types import SimpleNamespace

from agents.ad_agent.integration_result_assembler import AdvertisingResultAssembler


def test_export_application_state_only_contains_public_run_data():
    assembler = AdvertisingResultAssembler(SimpleNamespace())
    state = {
        "intent": SimpleNamespace(to_dict=lambda: {"intent_type": "list"}),
        "calls": [SimpleNamespace(to_dict=lambda: {"name": "list_accounts"})],
        "last_reply": "done",
        "credentials": {"access_token": "must-not-escape"},
        "session": object(),
    }

    result = assembler.export_application_state(state)

    assert result == {
        "last_reply": "done",
        "intent": {"intent_type": "list"},
        "calls": [{"name": "list_accounts"}],
    }
    assert "credentials" not in result
    assert "session" not in result


def test_tool_plan_names_groups_only_named_results():
    assembler = AdvertisingResultAssembler(SimpleNamespace())

    result = assembler.tool_plan_names([
        {"tool": "meta_list_accounts", "platform": "meta"},
        {"tool": "tiktok_list_accounts", "platform": "tiktok"},
        {"tool": "", "platform": "meta"},
        {"tool": "missing-platform"},
    ])

    assert result == {
        "meta": ["meta_list_accounts"],
        "tiktok": ["tiktok_list_accounts"],
    }


def test_prune_completed_keeps_newest_bounded_results():
    assembler = AdvertisingResultAssembler(SimpleNamespace(), max_completed=2)
    assembler.completed.update({"run-1": {}, "run-2": {}, "run-3": {}})

    assembler.prune_completed()

    assert list(assembler.completed) == ["run-2", "run-3"]
