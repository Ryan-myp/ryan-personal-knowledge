"""Contract tests for the skill-up Custom Engine adapter."""

import json

import pytest

from agents.agent_harness.messages import ModelTurn
from agents.evals.advertising.skill_up_engine import (
    _runtime_prompt,
    _structured_evidence,
    run,
)
from agents.tests.advertising.harness_models import ScriptedHarnessModel, call
from agents.evals.advertising.claude_sdk_engine import (
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


def test_skill_up_adapter_preserves_multi_turn_context_in_fallback_prompt():
    prompt = _runtime_prompt([
        {"role": "user", "content": "先查询 TikTok 可用应用列表"},
        {"role": "assistant", "content": "我准备查询"},
        {"role": "user", "content": "继续并给出结果"},
    ])
    assert "[user]" in prompt
    assert "[assistant]" in prompt
    assert "TikTok" in prompt


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


def test_runtime_skill_up_fails_closed_when_no_model_is_configured(tmp_path):
    with pytest.raises(RuntimeError, match="LLM client is required"):
        run({
            "case_id": "model-required",
            "workspace": str(tmp_path),
            "messages": [{"role": "user", "content": "查询 TikTok 应用"}],
        })


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
        "tiktok_smart_plus_create_campaign",
        {
            "account_id": "7397068114548195329",
            "campaign_name": "skill-up-app",
            "objective_type": "APP_PROMOTION",
            "app_promotion_type": "APP_INSTALL",
        },
    ),))))

    evidence = result["metadata"]["runtime_result"]
    assert evidence["intent"]["intent_type"] == "create_smart_plus_campaign"
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
        if item["path"] == "campaign.app_id"
    )
    assert app_id["state"] == "missing"
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
    monkeypatch.setenv("AD_AGENT_SKILLS_ROOT", str(skill_root))
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
