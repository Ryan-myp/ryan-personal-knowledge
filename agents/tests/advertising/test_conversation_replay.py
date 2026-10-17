import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.persistence.models import ConversationMessageRecord
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.tools.advertising.shared.domain.conversation import (
    project_conversation_messages, visible_run_reply,
)
from agents.agent_harness import ModelTurn
from agents.agent_harness.core.interfaces import ToolDefinition, ToolResult, ToolSchema
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.tests.advertising.harness_models import call, install


CARD = {"type": "ad_creation_form", "id": "shopping", "title": "Google Shopping"}
UI = {"schema_version": "1.0", "cards": [CARD]}


def message(role, content="", *, turn="turn", metadata=None, name=None):
    return {
        "role": role, "content": content, "turn_id": turn,
        "created_at": "2026-10-15T02:58:00+00:00",
        "metadata": metadata or {}, "name": name,
    }


def tool_assistant(*, metadata=None):
    return message("assistant", metadata={
        "tool_calls": [{"id": "call", "name": "query"}], **(metadata or {}),
    })


def test_history_hides_internal_empty_tool_call_turns_without_losing_reply():
    rows = [
        message("user", "有模板吗"),
        tool_assistant(),
        message("tool", json.dumps({"success": True, "data": {"templates": []}}), name="list_templates"),
        message("assistant", "有 Shopping、App 和 PMax 模板。"),
    ]
    visible = project_conversation_messages(rows)
    assert [row["role"] for row in visible] == ["user", "assistant"]
    assert visible[-1]["content"] == rows[-1]["content"]


def test_history_recovers_a_template_prompt_and_keeps_the_card():
    prompt = "已加载所选模板，请确认草稿参数；尚未创建广告。"
    rows = [
        message("user", "使用 Shopping 模板"),
        tool_assistant(metadata={"ui": UI}),
        message("tool", json.dumps({
            "success": True, "needs_input": True,
            "interaction": {"type": "ad_creation_form", "prompt": prompt, "payload": CARD},
        }), metadata={"needs_input": True}, name="get_template"),
    ]
    visible = project_conversation_messages(rows)
    assert len(visible) == 2
    assert visible[-1]["content"] == prompt
    assert visible[-1]["ui"] == UI


def test_history_restores_a_policy_failure_from_its_real_tool_evidence():
    rows = [
        message("user", "确认创建"),
        tool_assistant(),
        message(
            "tool", "allow_live_writes is disabled; live Tool writes are disabled",
            metadata={"is_error": True}, name="google_create_campaign",
        ),
    ]
    visible = project_conversation_messages(rows)
    assert len(visible) == 2
    assert visible[-1]["is_error"] is True
    assert "未开启真实写入" in visible[-1]["content"]
    assert visible[-1]["tools"] == [{"tool": "google_create_campaign", "success": False}]


@pytest.mark.parametrize("needs_confirmation", [True, False])
def test_expected_input_gates_are_not_replayed_as_execution_failures(needs_confirmation):
    flag = "needs_confirmation" if needs_confirmation else "needs_input"
    rows = [
        message("user", "继续"),
        tool_assistant(),
        message("tool", "high-risk live Tool calls require confirmation", metadata={
            "is_error": True, flag: True,
        }),
    ]
    reply = project_conversation_messages(rows)[-1]
    assert reply["is_error"] is False
    assert ("确认" if needs_confirmation else "补充") in reply["content"]
    assert "执行未完成" not in reply["content"]


def test_terminal_presentation_appears_once_even_when_raw_protocol_has_multiple_assistants():
    rows = [
        message("user", "查询"),
        tool_assistant(metadata={"display_reply": "完整最终回复", "ui": UI}),
        message("tool", "{}"),
        message("assistant", "完整最终回复", metadata={"display_reply": "完整最终回复", "ui": UI}),
    ]
    visible = project_conversation_messages(rows)
    assert len(visible) == 2
    assert visible[-1]["content"] == "完整最终回复"
    assert sum("ui" in row for row in visible) == 1


def test_user_text_that_resembles_a_tool_envelope_is_not_decoded():
    content = '{"error": "user example", "tool_calls": ["not an actual call"]}'
    assert project_conversation_messages([message("user", content)])[0]["content"] == content


def test_history_preserves_user_media_references_for_protected_replay():
    attachment = {
        "id": "85a42fc6-14e0-46d7-b595-b31864b198dd",
        "filename": "launch.mp4",
        "media_type": "video/mp4",
        "size": 4096,
    }
    rows = [
        message("user", "分析这段素材", metadata={"attachments": [attachment]}),
        message("assistant", "视频展示了产品使用场景。"),
    ]

    visible = project_conversation_messages(rows)

    assert visible[0]["attachments"] == [attachment]


def test_a_tool_result_without_a_saved_final_reply_is_not_silently_lost():
    rows = [
        message("user", "执行"),
        tool_assistant(),
        message("tool", '{"success": true, "data": {"id": "created-resource"}}', name="create_item"),
    ]
    visible = project_conversation_messages(rows)
    assert len(visible) == 2
    assert "执行记录" in visible[-1]["content"]
    assert "不要直接重复" in visible[-1]["content"]
    assert "创建成功" not in visible[-1]["content"]


@pytest.mark.parametrize("payload,expected", [
    ({"reply": "已生成草稿"}, "已生成草稿"),
    ({"error": "RateLimitError"}, "模型服务暂时限流"),
    ({"error": "model_timeout"}, "模型响应超时"),
    ({"needs_confirmation": True, "confirmation_payload": {"question": "请确认暂停创建"}}, "请确认暂停创建"),
    ({"status": "failed", "tool_results": [{"content": "permission denied", "is_error": True}]}, "permission denied"),
    ({"status": "failed"}, "本次执行未完成"),
    ({"status": "recovery_required"}, "核实"),
    ({"status": "cancelled"}, "取消"),
])
def test_live_reply_and_history_use_the_same_safe_fallback(payload, expected):
    assert expected in visible_run_reply(payload)


def test_rate_limited_final_summary_keeps_successful_read_rows_visible():
    reply = visible_run_reply({
        "status": "failed",
        "error": "RateLimitError",
        "reply": (
            "模型服务暂时限流，本次请求未完成。这不代表广告账户没有数据。"
            "已有工具执行记录；创建或更新操作不要直接重试，请先核实实际结果。"
        ),
        "results": [{
            "success": True,
            "tool": "meta_list_campaigns",
            "platform": "meta",
            "action": "list",
            "resource_type": "campaign",
            "data": {
                "data_status": "live",
                "campaigns": [{
                    "id": "campaign-123",
                    "name": "QA Campaign",
                    "status": "PAUSED",
                }],
            },
        }],
    })

    assert "查询已成功" in reply
    assert "模型摘要" in reply
    assert "campaign-123" in reply
    assert "QA Campaign" in reply
    assert "PAUSED" in reply


def test_rate_limited_summary_reports_partial_read_results_truthfully():
    reply = visible_run_reply({
        "status": "failed",
        "error": "RateLimitError",
        "reply": "模型服务暂时限流，本次请求未完成。这不代表广告账户没有数据。",
        "results": [
            {
                "success": True,
                "tool": "meta_list_campaigns",
                "action": "list",
                "resource_type": "campaign",
                "data": {
                    "campaigns": [
                        {"id": "campaign-123", "name": "QA Campaign", "status": "PAUSED"},
                    ],
                },
            },
            {
                "success": False,
                "tool": "meta_list_ad_sets",
                "action": "list",
                "resource_type": "ad_set",
                "error": "provider temporarily unavailable",
            },
        ],
    })

    assert "部分查询已成功" in reply
    assert "1 项查询失败" in reply
    assert "campaign-123" in reply
    assert "PAUSED" in reply


def test_rate_limited_empty_read_result_reports_zero_rows():
    reply = visible_run_reply({
        "error": "RateLimitError",
        "results": [{
            "success": True,
            "tool": "meta_list_campaigns",
            "action": "list",
            "resource_type": "campaign",
            "data": {"campaigns": []},
        }],
    })

    assert "共 0 条" in reply
    assert "查询已返回数据" not in reply


def test_read_fallback_preserves_zero_and_false_values():
    reply = visible_run_reply({
        "error": "RateLimitError",
        "results": [{
            "success": True,
            "tool": "meta_get_campaign",
            "action": "get",
            "resource_type": "campaign",
            "data": {
                "campaign": {
                    "id": "campaign-123",
                    "name": "QA Campaign",
                    "status": "PAUSED",
                    "daily_budget": 0,
                    "special_ad_category": False,
                    "access_token": "must-never-be-visible",
                    "signature": "must-never-be-visible",
                },
            },
        }],
    })

    assert "0" in reply
    assert "False" in reply
    assert "must-never-be-visible" not in reply


def test_non_model_error_does_not_claim_a_read_summary_is_complete():
    reply = visible_run_reply({
        "error": "ProviderError",
        "results": [{
            "success": True,
            "tool": "meta_list_campaigns",
            "action": "list",
            "resource_type": "campaign",
            "data": {"campaigns": [{"id": "campaign-123"}]},
        }],
    })

    assert "查询已成功" not in reply
    assert "本次请求执行失败" in reply


def test_generic_model_failure_reply_shows_the_failed_tool_reason():
    reply = visible_run_reply({
        "status": "failed",
        "reply": "本次请求执行失败，请查看执行记录。",
        "results": [{
            "tool": "meta_get_campaign",
            "success": False,
            "error": "Failed to get Meta campaign: Campaign not found",
        }],
    })

    assert "meta_get_campaign" in reply
    assert "Campaign not found" in reply
    assert "本次请求执行失败，请查看执行记录。" not in reply


def test_failed_tool_reason_is_redacted_before_it_is_shown_to_the_user():
    reply = visible_run_reply({
        "status": "failed",
        "reply": "本次执行未完成，请查看执行轨迹中的失败步骤。",
        "results": [{
            "tool": "meta_get_campaign",
            "success": False,
            "error": "Provider rejected access_token=do-not-show",
        }],
    })

    assert "Provider rejected" in reply
    assert "do-not-show" not in reply
    assert "<redacted>" in reply


def test_turn_limit_after_successful_campaign_reads_shows_data_and_reason():
    reply = visible_run_reply({
        "status": "failed",
        "error": "maximum agent turns exceeded",
        "results": [
            {
                "tool": "meta_get_campaign",
                "action": "get",
                "effect_class": "read",
                "resource_type": "campaign",
                "success": True,
                "data": {"campaign": {"id": "campaign-1", "name": "Spring A"}},
            },
            {
                "tool": "meta_get_campaign",
                "action": "get",
                "effect_class": "read",
                "resource_type": "campaign",
                "success": True,
                "data": {"campaign": {"id": "campaign-2", "name": "Spring B"}},
            },
        ],
    })

    assert "Spring A" in reply
    assert "Spring B" in reply
    assert "最大推理轮数" in reply
    assert "未能完成后续分析" in reply
    assert "创建或更新操作不要直接重试" not in reply


def test_structured_model_error_keeps_successful_reads_and_names_failure_stage():
    reply = visible_run_reply({
        "status": "failed",
        "error": "LLMStructuredOutputError",
        "error_code": "tool_arguments_invalid_json",
        "results": [{
            "tool": "meta_get_campaign",
            "action": "get",
            "effect_class": "read",
            "resource_type": "campaign",
            "success": True,
            "data": {"campaign": {"id": "campaign-1", "name": "Spring A"}},
        }],
    })

    assert "Spring A" in reply
    assert "模型返回的 Tool 调用参数不是有效 JSON" in reply
    assert "查询已成功" in reply


def test_unclassified_tool_records_do_not_claim_that_a_write_was_executed():
    reply = visible_run_reply({
        "error": "ProviderError",
        "results": [{
            "tool": "custom_tool",
            "success": True,
            "data": {"value": "result"},
        }],
    })

    assert "无法确认是否发生外部写入" in reply
    assert "确认前不要直接重试该 Tool" in reply
    assert "创建或更新操作不要直接重试" not in reply


def test_rate_limited_write_summary_does_not_claim_creation_succeeded():
    reply = visible_run_reply({
        "status": "failed",
        "error": "RateLimitError",
        "results": [{
            "success": True,
            "tool": "meta_create_campaign",
            "platform": "meta",
            "action": "create",
            "effect_class": "external_write",
            "resource_type": "campaign",
            "data": {"id": "campaign-123", "status": "PAUSED"},
        }],
    })

    assert "不要直接重试" in reply
    assert "查询已成功" not in reply


def test_malformed_optional_ui_is_not_used_as_conversation_content():
    assert visible_run_reply({"ui": "not a card"}) == ""


@pytest.fixture
def runtime():
    owner = AdvertisingComposition(
        require_llm=False, offline_mode=True,
        persistence_store=AdAgentStore(":memory:"), start_background_workers=False,
    )
    yield owner
    owner.close(wait=True)


def test_visible_reply_is_durable_without_replacing_internal_protocol(runtime):
    session = runtime._ensure_session("history", "operator", None, None, tenant_id="tenant")
    manager = runtime._session_manager
    manager.record_conversation_message("history", "turn", "user", "选择模板")
    manager.record_conversation_message(
        "history", "turn", "assistant", "",
        metadata={"tool_calls": [{"id": "call", "name": "get_template"}]},
    )
    runtime.persistence_services.persist_conversation_turn(
        session, "turn", "选择模板", "已加载模板，请确认参数。",
        ui=UI, persist_messages=False,
    )
    history = runtime.get_conversation("history", user_id="operator", tenant_id="tenant")
    assert [row["content"] for row in history["messages"]] == ["选择模板", "已加载模板，请确认参数。"]
    assert history["messages"][-1]["ui"] == UI
    raw = manager.list_conversation_messages("history")
    assert raw[-1].content == ""
    assert raw[-1].metadata["tool_calls"][0]["name"] == "get_template"
    assert raw[-1].metadata["display_reply"] == "已加载模板，请确认参数。"
    assert runtime.get_conversation("history", user_id="other", tenant_id="tenant") is None
    assert runtime.get_conversation("history", user_id="operator", tenant_id="other") is None


def test_a_failure_before_the_first_model_assistant_is_still_persisted(runtime):
    session = runtime._ensure_session("failure", "operator", None, None, tenant_id="tenant")
    runtime._session_manager.record_conversation_message("failure", "turn", "user", "你好")
    reply = visible_run_reply({"error": "RateLimitError"})
    runtime.persistence_services.persist_conversation_turn(
        session, "turn", "你好", reply, persist_messages=False,
    )
    history = runtime.get_conversation("failure", user_id="operator", tenant_id="tenant")
    assert len(history["messages"]) == 2
    assert history["messages"][-1]["content"] == reply
    raw = runtime._session_manager.list_conversation_messages("failure")
    assert datetime.fromisoformat(raw[-1].created_at).utcoffset() == timedelta(0)


def test_sidebar_preview_uses_the_visible_reply_not_tool_json(runtime):
    runtime._ensure_session("preview", "operator", None, None, tenant_id="tenant")
    rows = [
        message("user", "有模板吗"),
        tool_assistant(metadata={"display_reply": "有三个内置模板。"}),
        message("tool", '{"success": true, "data": {}}'),
    ]
    for index, row in enumerate(rows):
        runtime.persistence_store.record_conversation_message(ConversationMessageRecord(
            message_id=str(index), session_id="preview", turn_id=row["turn_id"],
            role=row["role"], content=row["content"], metadata=row["metadata"],
            created_at=f"2026-10-15T02:58:0{index}+00:00",
        ))
    summary = runtime.list_conversations(user_id="operator", tenant_id="tenant")[0]
    assert summary["preview"] == "有三个内置模板。"
    assert summary["message_count"] == 2


@pytest.mark.parametrize("authorized", [True, False])
def test_real_run_reply_and_persisted_replay_are_identical(runtime, authorized):
    prompt = "已加载创建草稿，请确认参数；尚未创建广告。"
    class Handler:
        def execute(self, *_args):
            return ToolResult(
                success=True, data={"data_status": "local"}, needs_input=True,
                interaction={"type": "ad_creation_form", "prompt": prompt, "payload": CARD},
            )

    runtime.register_tool(ToolDefinition(
        name="example_query", namespace="example", skill="example",
        description="Query example item", action="list", resource_type="item",
        intent_types=["query_item"], input_schema=ToolSchema(),
        required_permissions=["ads.read"], scope_required=False,
    ), Handler())
    install(runtime, ModelTurn(tool_calls=(call("example_query"),)))
    result = runtime.run(
        "查询 example item", session_id="native-replay",
        principal=RequestPrincipal(
            user_id="operator", tenant_id="tenant",
            permissions=frozenset({"ads.read"}) if authorized else frozenset(),
        ),
    )
    history = runtime.get_conversation("native-replay", user_id="operator", tenant_id="tenant")
    assert len(history["messages"]) == 2
    assert history["messages"][-1]["content"] == result["reply"]
    assert result["reply"].strip()
    if authorized:
        assert result["reply"] == prompt
        assert history["messages"][-1]["ui"]["cards"] == [CARD]
    else:
        assert history["messages"][-1]["is_error"] is True
        assert "ads.read" in result["reply"]


def test_conversation_replay_frontend_contract():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for conversation UI regressions")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).parent / "static/test_conversation_history.js")],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
