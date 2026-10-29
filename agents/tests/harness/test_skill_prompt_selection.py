from types import SimpleNamespace

from agents.agent_harness.skills import (
    InMemorySkillCatalog, MarkdownSkillSource, SkillBinding, StaticSkillSource,
)


def test_shared_reference_words_do_not_load_every_skill():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("skills", [
        SkillBinding(name=f"specialty-{i}", instructions="UNRELATED " * 1000,
                     reference_documents={"references/notes.md": "支持查询，各种能力说明。"})
        for i in range(8)
    ]))
    assert catalog.build_context("支持哪些能力") == ""


def test_specific_reference_terms_can_still_discover_a_skill():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("skills", [
        SkillBinding(name="research", instructions="RESEARCH SOP",
                     reference_documents={"references/notes.md": "quasar photometry"}),
        SkillBinding(name="billing", instructions="UNRELATED"),
    ]))
    assert "RESEARCH SOP" in catalog.build_context("quasar photometry")


def test_strong_topic_does_not_pull_in_weak_generic_matches():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("skills", [
        SkillBinding(name="specific", description="alpha beta gamma delta", instructions="PRIMARY " * 3000),
        SkillBinding(name="generic", description="alpha", instructions="UNRELATED"),
    ]))
    context = catalog.build_context("alpha beta gamma delta")
    assert "PRIMARY" in context
    assert "UNRELATED" not in context
    assert len(context) <= 4000


def test_tool_bindings_precede_lexical_matches_but_cannot_cross_source_scope():
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("allowed", [
        SkillBinding(name="linked", instructions="BOUND SOP"),
        SkillBinding(name="other", description="query", instructions="OTHER SOP"),
    ]))
    catalog.register_source(StaticSkillSource("private", [
        SkillBinding(name="secret", instructions="PRIVATE SOP"),
    ]))
    tools = [SimpleNamespace(skill_refs=["linked", "secret"], skill="")]
    context = catalog.build_tool_context("query", tools, source_ids=["allowed"])
    assert "BOUND SOP" in context and "PRIVATE SOP" not in context
    assert context.index("BOUND SOP") < context.index("OTHER SOP")
    assert "BOUND SOP" not in catalog.build_context("query", source_ids=["allowed"])
    assert catalog.build_tool_context("query", tools, source_ids=[]) == ""


def test_always_on_guidance_cannot_be_starved_by_topical_candidates():
    catalog = InMemorySkillCatalog(max_skills=2)
    catalog.register_source(StaticSkillSource("skills", [
        SkillBinding(name="policy", instructions="ALWAYS", metadata={"always_on": True}),
        *[SkillBinding(name=f"topic-{i}", description="report", instructions="TOPIC") for i in range(5)],
    ]))
    assert "ALWAYS" in catalog.build_context("report")


def test_package_trigger_keeps_complementary_guidance_beside_named_topic(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        '---\nname: diagnostics\ndescription: Audit supporting evidence\n'
        'triggers:\n  - [search coverage, 搜索覆盖率]\naliases: [reconciliation]\n'
        '---\nDIAGNOSTIC SOP', encoding="utf-8",
    )
    catalog = InMemorySkillCatalog()
    catalog.register_source(MarkdownSkillSource.from_directory(tmp_path))
    catalog.register_source(StaticSkillSource("channel", [
        SkillBinding(name="alpha", description="Alpha campaign report", instructions="CHANNEL SOP"),
    ]))
    context = catalog.build_context("alpha campaign report 搜索覆盖率")
    assert "CHANNEL SOP" in context and "DIAGNOSTIC SOP" in context
    assert "DIAGNOSTIC SOP" in catalog.build_context("reconciliation")
    assert "DIAGNOSTIC SOP" not in catalog.build_context("unreconciliationable")
