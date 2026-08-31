"""Architecture boundary tests for the single-Agent extension model."""

import pytest

from agents.ad_agent.core.execution_plan import ExecutionPlan, PlanNode
from agents.ad_agent.core.interfaces import (
    ParsedIntent, ToolDefinition, ToolSchema, ToolEffect,
)
from agents.ad_agent.core.tool_selector import DynamicToolSelector
from agents.ad_agent.runtime.runtime import AgentRuntime
from agents.ad_agent.skills.businesses.policy import BusinessSkillPolicy
from agents.ad_agent.runtime.account_policy import AccountWhitelistValidator
from agents.ad_agent.runtime.session_context import SessionContext


def test_runtime_discovers_domain_features_without_a_central_workflow_table():
    runtime = AgentRuntime(require_llm=False)

    assert "cross-channel" in {
        feature.feature_name for feature in runtime.features
    }
    assert not hasattr(runtime, "business_context")
    assert not hasattr(runtime, "load_business_context")
    assert not hasattr(runtime, "_build_tool_input")
    assert not hasattr(runtime, "_apply_selection_tokens")
    assert not hasattr(runtime, "_execute_tool")
    assert not hasattr(runtime, "_start_workflow")
    assert not hasattr(runtime, "_finish_workflow")
    assert not hasattr(runtime, "_validate_tool_input_redline")
    assert runtime.input_builder.services is runtime.services
    assert runtime.services.workflow_lease_owner() == runtime._workflow_lease_owner
    assert runtime.tool_executor.services is runtime.services
    assert runtime.security.runtime is runtime
    assert isinstance(runtime.workflow.services, type(runtime.services))
    assert AccountWhitelistValidator is not None
    assert SessionContext is not None
    assert "runtime._" not in (
        __import__(
            "pathlib"
        ).Path("agents/ad_agent/features/cross_channel.py").read_text(
            encoding="utf-8"
        )
    )
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


def test_execution_plan_is_provider_neutral_and_validates_dependencies():
    campaign = ToolDefinition(
        name="provider_create_campaign",
        skill="provider",
        platform="provider",
        description="create",
        input_schema=ToolSchema(),
        action="create",
        resource_type="campaign",
        effect_class=ToolEffect.WRITE,
    )
    child = ToolDefinition(
        name="provider_create_child",
        skill="provider",
        platform="provider",
        description="create child",
        input_schema=ToolSchema(),
        action="create",
        resource_type="child",
        parent_resource_type="campaign",
        effect_class=ToolEffect.WRITE,
    )
    plan = ExecutionPlan.from_tool_plan(
        ParsedIntent("create", "create", ["provider"]),
        {"provider": [campaign, child]},
    )

    assert plan.nodes[1].depends_on == (plan.nodes[0].node_id,)
    assert plan.to_dict()["schema_version"] == "1.0"
    assert all("credentials" not in node for node in plan.to_dict()["nodes"])

    cyclic = ExecutionPlan(
        schema_version="1.0",
        intent_type="cycle",
        nodes=(
            PlanNode("a", 1, "provider", "a", "create", "a", depends_on=("b",)),
            PlanNode("b", 2, "provider", "b", "create", "b", depends_on=("a",)),
        ),
    )
    with pytest.raises(ValueError, match="dependency cycle"):
        cyclic.validate()
