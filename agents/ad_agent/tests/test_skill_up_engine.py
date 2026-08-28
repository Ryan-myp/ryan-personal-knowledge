"""Contract tests for the skill-up Custom Engine adapter."""

import json

from agents.ad_agent.evals.skill_up_engine import run


def test_skill_up_adapter_returns_standard_result_and_runtime_evidence(tmp_path):
    result = run({
        "case_id": "adapter-contract",
        "variant": "with_skill",
        "workspace": str(tmp_path),
        "messages": [{
            "role": "user",
            "content": (
                "创建 TikTok campaign; name=adapter-test; "
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
