"""Contract tests for the skill-up Custom Engine adapter."""

import json

from agents.ad_agent.evals.skill_up_engine import _runtime_prompt, run
from agents.ad_agent.evals.claude_sdk_engine import (
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
                "name=adapter-test; "
                "objective_type=APP_PROMOTION; campaign_type=REGULAR_CAMPAIGN; "
                "budget_mode=BUDGET_MODE_DAY; daily_budget=100; "
                "app_promotion_type=APP_ACQUISITION"
            ),
        }],
    })

    assert result["exit_code"] == 0
    assert "tiktok_create_campaign" in result["final_message"]
    assert '"mode": "dry_run"' in result["final_message"]
    assert (tmp_path / "outputs" / "ad-agent-runtime-result.json").exists()
    persisted = json.loads(
        (tmp_path / "outputs" / "ad-agent-runtime-result.json").read_text()
    )
    assert persisted["results"][0]["data"]["simulated"] is True


def test_skill_up_adapter_does_not_accept_credentials_from_case_kwargs(tmp_path):
    result = run({
        "case_id": "credential-boundary",
        "workspace": str(tmp_path),
        "kwargs": {"access_token": "should-never-be-used"},
        "messages": [{"role": "user", "content": "查询 TikTok 可用应用列表"}],
    })

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
