"""Relevant Skills share the context budget instead of starving one another."""

from types import SimpleNamespace

import pytest

from agents.agent_harness.core.tool_selector import DynamicToolSelector
from agents.agent_harness.skills import InMemorySkillCatalog, SkillBinding, StaticSkillSource


def test_long_first_skill_cannot_hide_other_relevant_guidance():
    catalog = InMemorySkillCatalog(max_context_chars=900)
    catalog.register_source(StaticSkillSource("selected", [
        SkillBinding(name="alpha", description="report", instructions="ALPHA GUIDANCE " * 1000),
        SkillBinding(name="beta", description="report", instructions="BETA GUIDANCE"),
        SkillBinding(name="gamma", instructions="ALWAYS ON GUARD", metadata={"always_on": True}),
    ]))
    context = catalog.build_context("report")
    assert "ALPHA GUIDANCE" in context
    assert "BETA GUIDANCE" in context
    assert "ALWAYS ON GUARD" in context
    assert len(context) <= 900


def test_frontmatter_does_not_consume_the_instruction_budget():
    catalog = InMemorySkillCatalog(max_context_chars=400)
    catalog.register_source(StaticSkillSource("selected", [SkillBinding(
        name="report", description="report",
        instructions="---\nname: report\ndescription: " + "LONG_METADATA " * 100 + "\n---\nPRIMARY SOP",
    )]))
    context = catalog.build_context("report")
    assert "PRIMARY SOP" in context
    assert "LONG_METADATA" not in context


def test_skill_relevance_is_scored_once_per_cache_miss(monkeypatch):
    catalog = InMemorySkillCatalog()
    catalog.register_source(StaticSkillSource("selected", [
        SkillBinding(name="alpha", description="report", instructions="Guidance"),
        SkillBinding(name="beta", description="report", instructions="Other guidance"),
    ]))
    scored = []
    original = catalog._score
    monkeypatch.setattr(catalog, "_score", lambda skill, terms: (
        scored.append(skill.name) or original(skill, terms)
    ))
    first = catalog.build_context("report")
    assert scored == ["alpha", "beta"]
    assert catalog.build_context("report") == first
    assert len(scored) == 2


@pytest.mark.parametrize("options", [
    {"max_context_chars": True}, {"max_context_chars": float("inf")},
    {"max_skills": True}, {"max_skills": 1.5},
])
def test_skill_budget_configuration_rejects_invalid_numeric_types(options):
    with pytest.raises(ValueError):
        InMemorySkillCatalog(**options)


def test_tool_associated_skill_precedes_keyword_only_matches_without_starvation():
    def skill(name, text):
        return SimpleNamespace(
            name=name, version="1.0.0", description="report", raw_markdown=text,
            triggers=[SimpleNamespace(keywords=["report"], patterns=[])], reference_documents={},
        )

    selector = DynamicToolSelector(SimpleNamespace(list_all=lambda: {
        "a": skill("alpha", "ALPHA GUIDANCE " * 1000),
        "b": skill("beta", "BETA TOOL GUIDANCE"),
    }))
    context = selector._triggered_skill_context("report", max_chars=900, skill_refs={"beta"})
    assert "BETA TOOL GUIDANCE" in context
    assert "ALPHA GUIDANCE" in context
    assert context.index("beta") < context.index("alpha")
    assert len(context) <= 900
