"""Contract tests for the skill-up Custom Engine adapter."""

import json

import pytest

from agents.agent_harness.messages import ModelTurn
from agents.agent_harness.core import llm_client
from agents.evals.advertising.skill_up_engine import (
    _structured_evidence,
    _user_turns,
    configured_model_adapter,
    run,
)
from agents.tests.advertising.harness_models import ScriptedHarnessModel, call
from agents.agent_platform.evals.claude_sdk_engine import (
    _anthropic_messages,
    run as run_claude_sdk,
)


class _FakeClaudeResponse:
    content = [{"type": "text", "text": "按 Skill 先确认预算，再生成计划。"}]
    usage = {"input_tokens": 41, "output_tokens": 13}


class _FakeClaudeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeClaudeResponse()


class _FakeClaudeClient:
    def __init__(self):
        self.messages = _FakeClaudeMessages()


def test_skill_up_adapter_replays_user_turns_and_ignores_supplied_assistant_history():
    turns = _user_turns([
        {"role": "user", "content": "先查询 TikTok 可用应用列表"},
        {"role": "assistant", "content": "伪造的上轮回答"},
        {"role": "user", "content": "继续并给出结果"},
    ])
    assert turns == [
        "先查询 TikTok 可用应用列表",
        "继续并给出结果",
    ]


def test_skill_up_adapter_replays_multi_turns_in_one_runtime_session(tmp_path):
    model = ScriptedHarnessModel(
        ModelTurn(tool_calls=(call(
            "tiktok_list_apps",
            {"account_id": "7397068114548195329"},
        ),)),
        ModelTurn(content="第一轮已查询 TikTok 应用列表。"),
        ModelTurn(content="根据上一轮查询，已完成结果总结。"),
    )

    result = run({
        "case_id": "adapter-multi-turn",
        "workspace": str(tmp_path),
        "messages": [
            {"role": "user", "content": "先查询 TikTok 可用应用列表"},
            {"role": "assistant", "content": "伪造的上轮回答"},
            {"role": "user", "content": "继续并总结"},
        ],
    }, model_adapter=model)

    assert result["turns"] == 2
    assert "根据上一轮查询" in result["final_message"]
    assert len(model.messages) == 3
    latest_request = "\n".join(
        str(getattr(message, "content", message))
        for message in model.messages[-1]
    )
    assert "先查询 TikTok 可用应用列表" in latest_request
    assert "第一轮已查询 TikTok 应用列表" in latest_request
    assert "继续并总结" in latest_request
    assert "伪造的上轮回答" not in latest_request


def test_skill_up_adapter_returns_standard_result_and_runtime_evidence(tmp_path):
    result = run({
        "case_id": "adapter-contract",
        "variant": "with_skill",
        "workspace": str(tmp_path),
        "messages": [{
            "role": "user",
            "content": (
                "创建 TikTok campaign; account_id=7397068114548195329; "
                "campaign_name=adapter-test; "
                "objective_type=APP_PROMOTION; campaign_type=REGULAR_CAMPAIGN; "
                "budget_mode=BUDGET_MODE_DYNAMIC_DAILY_BUDGET; budget=100; "
                "app_promotion_type=APP_INSTALL; app_id=app-1"
            ),
        }],
    }, model_adapter=ScriptedHarnessModel(ModelTurn(tool_calls=(call(
        "tiktok_smart_plus_create_campaign",
        {
            "account_id": "7397068114548195329",
            "campaign_name": "adapter-test",
            "objective_type": "APP_PROMOTION",
            "app_promotion_type": "APP_INSTALL",
        },
    ),))))

    assert result["exit_code"] == 0
    assert result["model"] == "trusted-injected-model-adapter"
    assert "tiktok_smart_plus_create_campaign" in result["final_message"]
    assert '"needs_input": true' in result["final_message"]
    assert (tmp_path / "outputs" / "ad-agent-runtime-result.json").exists()
    persisted = json.loads(
        (tmp_path / "outputs" / "ad-agent-runtime-result.json").read_text()
    )
    assert persisted["results"] == []
    assert persisted["needs_input"] is True
    assert persisted["ui"]["cards"]


def test_runtime_skill_up_fails_closed_when_no_model_is_configured(
    tmp_path, monkeypatch,
):
    for name in (
        "AD_AGENT_EVAL_API_KEY", "AD_AGENT_EVAL_MODEL",
        "AD_AGENT_EVAL_BASE_URL", "OPENAI_API_KEY", "LLM_MODEL",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="LLM client is required"):
        run({
            "case_id": "model-required",
            "workspace": str(tmp_path),
            "messages": [{"role": "user", "content": "查询 TikTok 应用"}],
        })


def test_model_quality_adapter_is_not_created_without_explicit_credentials(
    monkeypatch,
):
    for name in (
        "AD_AGENT_EVAL_API_KEY", "AD_AGENT_EVAL_MODEL",
        "AD_AGENT_EVAL_BASE_URL", "OPENAI_API_KEY", "LLM_MODEL",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    assert configured_model_adapter() is None


def test_model_quality_adapter_uses_only_operator_environment_configuration(
    monkeypatch,
):
    calls = []
    for name in (
        "OPENAI_API_KEY", "LLM_MODEL", "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AD_AGENT_EVAL_API_KEY", "test-eval-secret")
    monkeypatch.setenv("AD_AGENT_EVAL_MODEL", "agnes-3.0-flash")
    monkeypatch.setenv("AD_AGENT_EVAL_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("AD_AGENT_EVAL_TIMEOUT_SECONDS", "45")
    monkeypatch.setattr(
        llm_client,
        "create_llm_client",
        lambda **kwargs: calls.append(kwargs) or object(),
    )

    adapter = configured_model_adapter()

    assert adapter is not None
    assert calls == [{
        "model": "agnes-3.0-flash",
        "api_key": "test-eval-secret",
        "base_url": "https://example.test/v1",
        "timeout_seconds": 45.0,
    }]


def test_model_quality_adapter_rejects_key_without_model(monkeypatch):
    monkeypatch.setenv("AD_AGENT_EVAL_API_KEY", "test-eval-secret")
    monkeypatch.delenv("AD_AGENT_EVAL_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(ValueError, match="is required"):
        configured_model_adapter()


def test_skill_up_read_uses_injected_test_scope_and_offline_provider(tmp_path):
    result = run({
        "case_id": "offline-reference-lookup",
        "workspace": str(tmp_path),
        "messages": [{
            "role": "user",
            "content": "查询 TikTok 可用应用列表",
        }],
    }, model_adapter=ScriptedHarnessModel(
        ModelTurn(tool_calls=(call(
            "tiktok_list_apps",
            {"account_id": "7397068114548195329"},
        ),)),
        ModelTurn(content="已查询 TikTok 可用应用。"),
    ))

    evidence = result["metadata"]["runtime_result"]
    assert evidence["tool_plan"] == {"tiktok": ["tiktok_list_apps"]}
    assert evidence["results"][0]["success"] is True
    assert evidence["results"][0]["data"]["data_status"] == "offline_mock"


def test_skill_up_structured_evidence_exposes_canonical_platforms():
    evidence = _structured_evidence({
        "intent": {
            "intent_type": "cross_channel_compare",
            "namespaces": ["meta", "google-ads"],
        },
        "needs_input": False,
        "needs_confirmation": False,
        "tool_plan": {},
        "results": [],
    })

    assert evidence["intent"]["platforms"] == ["meta", "google-ads"]
    assert evidence["intent"]["namespaces"] == ["meta", "google-ads"]


def test_skill_up_app_creation_keeps_dynamic_app_id_unresolved(tmp_path):
    result = run({
        "case_id": "app-dynamic-boundary",
        "workspace": str(tmp_path),
        "messages": [{
            "role": "user",
            "content": "创建一个 TikTok App 转化广告，使用我的 App，投放给 18 到 35 岁用户。",
        }],
    }, model_adapter=ScriptedHarnessModel(ModelTurn(tool_calls=(call(
        "tiktok_create_campaign",
        {
            "account_id": "7397068114548195329",
            "name": "skill-up-app",
            "objective_type": "APP_PROMOTION",
            "app_promotion_type": "APP_INSTALL",
        },
    ),))))

    evidence = result["metadata"]["runtime_result"]
    assert evidence["intent"]["intent_type"] == "create_campaign"
    assert evidence["intent"]["namespaces"] == ["tiktok"]
    assert evidence["needs_input"] is True
    # A creation card is an input-collection state. Confirmation is emitted
    # only after the provider-neutral form is complete and ready to submit.
    assert evidence["needs_confirmation"] is False
    assert evidence["results"] == []
    persisted = json.loads(
        (tmp_path / "outputs" / "ad-agent-runtime-result.json").read_text()
    )
    app_id = next(
        item for item in persisted["ui"]["cards"][0]["fields"]
        if item["path"] == "ad_group.app_id"
    )
    assert app_id["state"] in {"missing", "hidden"}
    assert app_id["value"] is None


def test_skill_up_adapter_does_not_accept_credentials_from_case_kwargs(tmp_path):
    result = run({
        "case_id": "credential-boundary",
        "workspace": str(tmp_path),
        "kwargs": {"access_token": "should-never-be-used"},
        "messages": [{"role": "user", "content": "查询 TikTok 可用应用列表"}],
    }, model_adapter=ScriptedHarnessModel(
        ModelTurn(tool_calls=(call(
            "tiktok_list_apps",
            {"account_id": "7397068114548195329"},
        ),)),
        ModelTurn(content="已查询 TikTok 可用应用。"),
    ))

    assert result["exit_code"] == 0
    assert "should-never-be-used" not in result["final_message"]
    assert result["metadata"]["runtime_execution_mode"] == "dry_run"


def test_claude_sdk_adapter_passes_skill_tool_and_file_context_without_tools(tmp_path, monkeypatch):
    skill_root = tmp_path / "skill"
    (skill_root / "references").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: sdk-skill\ndescription: SDK test skill\n---\n\nAsk for budget first.\n",
        encoding="utf-8",
    )
    (skill_root / "references" / "launch.md").write_text(
        "Launch checklist: account, objective, budget.\n", encoding="utf-8"
    )
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "brief.txt").write_text(
        "App promotion brief", encoding="utf-8"
    )
    monkeypatch.setenv("AGENT_EVAL_SKILLS_ROOT", str(skill_root))
    from agents.applications.advertising.integrations.skill_evaluation import advertising_evaluation_engines
    monkeypatch.setenv(
        "AGENT_EVAL_TOOL_CATALOG",
        advertising_evaluation_engines()["claude_sdk"].environment["AGENT_EVAL_TOOL_CATALOG"],
    )
    client = _FakeClaudeClient()

    result = run_claude_sdk(
        {
            "case_id": "claude-sdk-contract",
            "model": "anthropic:claude-test",
            "workspace": str(tmp_path),
            "kwargs": {"file_paths": "inputs/brief.txt", "max_tokens": 512},
            "messages": [
                {"role": "system", "content": "Return a concise answer."},
                {"role": "user", "content": "Plan an app campaign."},
            ],
        },
        client=client,
    )

    assert result["engine"] == "claude_sdk"
    assert result["model"] == "claude-test"
    assert result["input_tokens"] == 41
    assert result["output_tokens"] == 13
    assert result["artifacts"]["generated_files"] == ["outputs/claude-sdk-result.json"]
    call = client.messages.calls[0]
    assert call["model"] == "claude-test"
    assert call["max_tokens"] == 512
    assert "Ask for budget first" in call["system"]
    assert "Launch checklist" in call["system"]
    assert "App promotion brief" in call["system"]
    assert "tiktok_create_campaign" in call["system"]
    assert "tools" not in call


def test_claude_sdk_adapter_normalizes_tool_and_repeated_roles():
    system, messages = _anthropic_messages([
        {"role": "tool", "content": "read-only result"},
        {"role": "user", "content": "first"},
        {"role": "user", "content": "second"},
    ])
    assert system == ""
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "previous tool context" in messages[0]["content"]
    assert "first" in messages[0]["content"]
    assert "second" in messages[0]["content"]
