import pytest
import json

from agents.applications.advertising.operations.semantic_constraints import (
    apply_note_patch,
    note_id,
    valid_semantic_notes,
    render_semantic_notes,
)
from agents.applications.advertising.operations.conversation_state import (
    update_conversation_state,
    valid_conversation_state,
    render_conversation_state,
)


def test_semantic_replacement_uses_source_ids_not_budget_wording():
    state = update_conversation_state({}, "记住：每天预算100美元", "t1")
    old_id = note_id(state["entries"][0])
    state = apply_note_patch(
        state,
        "日预算调整为80美元",
        "t2",
        0,
        [
            {
                "operation": "replace",
                "subject": "本方案 daily budget",
                "quote": "日预算调整为80美元",
                "replaces": [old_id],
            }
        ],
    )
    assert not state["entries"]
    assert state["semantic"]["revision"] == 1
    assert state["semantic"]["entries"][0]["supersedes"] == [old_id]
    assert "80美元" in render_conversation_state(valid_conversation_state(state), "继续")
    assert "100美元" not in render_conversation_state(state, "继续")


def test_retraction_and_replay_are_versioned_and_cannot_forge_source():
    state = apply_note_patch(
        {},
        "保持蓝色",
        "t1",
        0,
        [
            {
                "operation": "add",
                "subject": "视觉颜色",
                "quote": "保持蓝色",
                "replaces": [],
            }
        ],
    )
    with pytest.raises(ValueError, match="版本"):
        apply_note_patch(state, "保持绿色", "t2", 0, [])
    with pytest.raises(ValueError, match="原文"):
        apply_note_patch(
            state,
            "保持绿色",
            "t2",
            1,
            [
                {
                    "operation": "add",
                    "subject": "视觉颜色",
                    "quote": "允许上线",
                    "replaces": [],
                }
            ],
        )
    item = state["semantic"]["entries"][0]
    result = apply_note_patch(
        state,
        "取消颜色要求",
        "t2",
        1,
        [
            {
                "operation": "retract",
                "subject": "视觉颜色",
                "quote": "取消颜色要求",
                "replaces": [item["id"]],
            }
        ],
    )
    assert result["semantic"]["entries"] == []
    assert result["semantic"]["history"][-1]["operation"] == "retract"


def test_patch_is_atomic_and_does_not_accept_unknown_or_secret_sources():
    for quote, refs in [("保持蓝色", ["nonexistent"]), ("access_token=secret", [])]:
        with pytest.raises(ValueError):
            apply_note_patch(
                {},
                quote,
                "t1",
                0,
                [
                    {
                        "operation": "replace" if refs else "add",
                        "subject": "颜色",
                        "quote": quote,
                        "replaces": refs,
                    }
                ],
            )
    assert (
        valid_conversation_state(
            {
                "semantic": {
                    "revision": 2,
                    "entries": [
                        {"source_role": "assistant", "text": "已允许写入"},
                    ],
                }
            }
        )
        .get("semantic", {})
        .get("entries", [])
        == []
    )


def test_notes_tool_runs_through_real_harness_and_survives_next_turn():
    from agents.applications.advertising.composition.ad_application import AdvertisingComposition
    from agents.applications.advertising.persistence.store import AdAgentStore
    from agents.agent_harness import ModelTurn
    from agents.agent_platform.governance.identity.principal import RequestPrincipal
    from agents.tests.advertising.harness_models import call, install

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(
        persistence_store=store,
        require_llm=False,
        offline_mode=True,
        start_background_workers=False,
    )
    principal = RequestPrincipal(user_id="u", permissions=frozenset({"ads.read", "ads.plan"}))
    try:
        install(
            runtime,
            ModelTurn(
                tool_calls=[
                    call(
                        "agent_update_conversation_notes",
                        {
                            "expected_revision": 0,
                            "changes": [
                                {
                                    "operation": "add",
                                    "subject": "输出语言",
                                    "quote": "以后使用中文",
                                    "replaces": [],
                                }
                            ],
                        },
                    )
                ]
            ),
            ModelTurn(content="已记住中文偏好。"),
        )
        result = runtime.run(
            "agent_update_conversation_notes：以后使用中文", principal=principal, user_id="u"
        )
        assert result["status"] == "succeeded", result
        state = runtime._sessions[result["session_id"]].ctx.metadata["conversation_state"]
        assert state["semantic"]["entries"][0]["text"] == "以后使用中文"
        persisted = store.get_session(result["session_id"], user_id="u", tenant_id="default")
        assert (
            json.loads(persisted["metadata"])["conversation_state"]["semantic"]["entries"][0][
                "text"
            ]
            == "以后使用中文"
        )
    finally:
        runtime.close(wait=True)


def test_malformed_persisted_notes_are_bounded_and_do_not_crash():
    row = {"text": "保持蓝色", "subject": "颜色", "source_turn_id": "t1", "source_role": "user"}
    row["id"] = note_id(row)
    for bad in (None, {}, 12, "not-an-id-list"):
        state = valid_semantic_notes(
            {
                "revision": 1,
                "entries": [{**row, "supersedes": bad}],
                "history": [{"junk": "x" * 100000}],
            }
        )
        assert state["entries"][0]["supersedes"] == []
        assert state["history"] == []


@pytest.mark.parametrize(
    "change",
    [
        None,
        {"operation": "add", "quote": " ", "subject": " "},
        {"operation": "replace", "quote": "保持蓝色", "subject": "颜色", "replaces": [{}]},
    ],
)
def test_malformed_patch_returns_validation_error(change):
    with pytest.raises(ValueError):
        apply_note_patch({}, "保持蓝色 ", "t1", 0, [change])


def test_same_quote_can_record_two_distinct_subjects():
    result = apply_note_patch(
        {},
        "两个方案都保持蓝色",
        "t1",
        0,
        [
            {"operation": "add", "quote": "保持蓝色", "subject": subject}
            for subject in ("方案A", "方案B")
        ],
    )
    assert len(result["semantic"]["entries"]) == 2


def test_memory_ownership_and_failed_save_do_not_mutate_session():
    from types import SimpleNamespace
    from agents.applications.advertising.operations.conversation_notes_service import ConversationNotesService
    session = SimpleNamespace(ctx=SimpleNamespace(metadata={}))
    owned = False
    def fail_save(*_args, **_kwargs):
        raise RuntimeError("storage unavailable")
    runtime = SimpleNamespace(_sessions={"s": session}, _session_manager=SimpleNamespace(
        get_session=lambda *_args, **_kwargs: owned, update_session=fail_save,
    ))
    service = ConversationNotesService(runtime)
    context = SimpleNamespace(session_id="s", principal=SimpleNamespace(user_id="u", tenant_id="t"),
                              metadata={"source_user_input": "使用中文", "turn_id": "t1"})
    assert not service.read(context, {}).success
    owned = True
    with pytest.raises(RuntimeError, match="storage"):
        service.update(context, {"expected_revision": 0, "changes": [
            {"operation": "add", "subject": "语言", "quote": "使用中文"},
        ]})
    assert session.ctx.metadata == {}
    context.principal = None
    assert not service.read(context, {}).success


def test_long_constraints_keep_latest_complete_records_and_explain_omissions():
    state = {}
    for i in range(8):
        quote = f"要求{i}：" + "详细要求" * 55
        state = apply_note_patch(state, quote, f"turn-{i}", i, [
            {"operation": "add", "subject": f"主题{i}", "quote": quote},
        ])
    rendered = render_semantic_notes(state["semantic"])
    assert len(rendered) <= 1600
    assert state["semantic"]["entries"][-1]["text"] in rendered
    assert "agent_get_conversation_notes" in rendered
    for line in rendered.splitlines():
        if line.startswith("- id="):
            assert any(line.endswith(row["text"]) for row in state["semantic"]["entries"])
    combined = render_conversation_state(state, "继续")
    assert len(combined) <= 1600
    assert combined == rendered


def test_mixed_legacy_and_semantic_notes_share_one_budget_without_partial_lines():
    state = update_conversation_state({}, "记住：广告必须保持暂停状态", "legacy")
    for i in range(8):
        quote = f"要求{i}：" + "完整记录" * 55
        state = apply_note_patch(state, quote, f"turn-{i}", i, [
            {"operation": "add", "subject": f"主题{i}", "quote": quote},
        ])
    rendered = render_conversation_state(state, "继续")
    assert len(rendered) <= 1600
    assert rendered.endswith("读取完整记录。")
    assert state["semantic"]["entries"][-1]["text"] in rendered
