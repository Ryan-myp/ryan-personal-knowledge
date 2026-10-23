from agents.agent_harness import (
    AgentApplication,
    AgentMessage,
    InMemorySkillCatalog,
    SkillBinding,
    StaticSkillSource,
    ToolBinding,
    StaticToolSource,
)
from agents.scenarios.advertising import advertising_skill_source


def test_a_non_ad_business_can_mount_its_own_skill_and_tool():
    seen = {}

    class Model:
        def complete(self, messages, tools, _request):
            seen["messages"] = messages
            seen["tools"] = tools
            return "done"

    application = AgentApplication.create(model=Model())
    application.register_skill_source(StaticSkillSource(
        "support",
        [SkillBinding(
            name="support",
            instructions="Answer support questions using the support policy.",
            description="Customer support",
        )],
    ))
    application.register_tool_source(StaticToolSource(
        "support-tools",
        [ToolBinding({"name": "lookup_ticket"}, lambda _ctx, _data: {"ok": True})],
    ))

    result = application.prompt("help with my support ticket")

    assert result.reply == "done"
    assert any(
        isinstance(message, AgentMessage)
        and message.role == "system"
        and "support policy" in str(message.content)
        for message in seen["messages"]
    )
    assert seen["tools"][0]["name"] == "lookup_ticket"


def test_skill_catalog_is_application_neutral_and_bounded():
    catalog = InMemorySkillCatalog(max_context_chars=80)
    catalog.register_source(StaticSkillSource(
        "docs",
        [SkillBinding(
            name="docs",
            instructions="A" * 500,
            description="documentation",
        )],
    ))

    context = catalog.build_context("documentation")

    assert len(context) <= 80
    assert "docs" in context


def test_advertising_skills_are_exportable_without_ad_runtime():
    source = advertising_skill_source()
    catalog = InMemorySkillCatalog(max_context_chars=2_000)

    names = catalog.register_source(source)

    assert names
    assert "meta-marketing-api-expert" in names
    assert "cross-channel-campaign-manager" in names
    assert "creative-strategy" in names
    assert "account-diagnostics" in names
    assert "experimentation-design" in names
    assert "measurement-attribution" in names
    assert "measurement-instrumentation" in names

    context = catalog.build_context(
        "设计广告创意路线图，按客户证据和账户表现安排 production tier"
    )

    assert "Skill: creative-strategy" in context
    assert "references/creative-roadmap.md" in context

    diagnostics_context = catalog.build_context(
        "Google Ads 搜索词报告可见点击覆盖率与缺失查询"
    )

    assert "Skill: account-diagnostics" in diagnostics_context
    assert "references/google-report-interpretation.md" in diagnostics_context

    experiment_context = catalog.build_context(
        "设计广告 A/B test hypothesis、MDE、power 和停止规则"
    )
    assert "Skill: experimentation-design" in experiment_context
    assert "references/test-design.md" in experiment_context

    attribution_context = catalog.build_context(
        "平台转化和业务结果差异，MTA MMM incrementality holdout"
    )
    assert "Skill: measurement-attribution" in attribution_context
    assert "references/attribution-and-incrementality.md" in attribution_context

    instrumentation_context = catalog.build_context(
        "广告 conversion event tracking plan、UTM、deduplication 和 PII 校验"
    )
    assert "Skill: measurement-instrumentation" in instrumentation_context
    assert "references/event-measurement-contract.md" in instrumentation_context


def test_harness_has_no_business_package_or_tool_source_runtime_concept():
    from pathlib import Path

    harness_readme = Path("agents/agent_harness/README.md").read_text(
        encoding="utf-8"
    )
    assert "application package" not in harness_readme
    assert "business package" not in harness_readme
    assert "Tool Source classes" not in harness_readme
    assert "ToolSource" in harness_readme
