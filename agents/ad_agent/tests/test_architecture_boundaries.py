"""Architecture boundary tests for the single-Agent extension model."""

from agents.ad_agent.core.interfaces import ParsedIntent
from agents.ad_agent.core.tool_selector import DynamicToolSelector
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.skills.businesses.policy import BusinessSkillPolicy


def test_runtime_discovers_domain_features_without_a_central_workflow_table():
    runtime = AgentRuntime(require_llm=False)

    assert "cross-channel" in {
        feature.feature_name for feature in runtime.features
    }
    assert not hasattr(runtime, "business_context")
    assert not hasattr(runtime, "load_business_context")
    assert not hasattr(DynamicToolSelector(), "business_context")


def test_business_skill_policy_is_loaded_and_enforced_outside_runtime(tmp_path):
    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "businesses" / "app"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "business:\n"
        "  name: app\n"
        "  allowed_channels: [google]\n"
        "  allowed_campaign_types: [APP]\n"
        "  business_rules:\n"
        "    min_budget: 50\n"
        "    max_budget: 50000\n"
        "---\n\n# App policy\n",
        encoding="utf-8",
    )

    policy = BusinessSkillPolicy.from_skill_file("app", str(skills_root))
    intent = ParsedIntent(
        intent_type="create_campaign",
        raw_input="create",
        platforms=["tiktok"],
        campaign_type="APP",
        budget=100,
    )

    errors = policy.validate_intent(intent)
    assert errors
    assert "不允许使用 tiktok" in errors[0]

    runtime = AgentRuntime(require_llm=False, policies=[policy])
    assert runtime._validate_policies(intent) == errors
