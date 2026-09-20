from agents.agent_harness import (
    AgentApplication,
    AgentMessage,
    InMemorySkillCatalog,
    SkillBinding,
    StaticSkillSource,
    ToolBinding,
    StaticToolSource,
)
from agents.ad_agent.integration import advertising_skill_source


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
    assert "meta" in names
    assert "cross-channel" in names
