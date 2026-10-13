"""Skill references are selected by request relevance, not directory order."""

from types import SimpleNamespace

from agents.agent_harness.core.tool_selector import (
    DynamicToolSelector,
    select_reference_excerpts,
)
from agents.agent_harness.skills import (
    InMemorySkillCatalog,
    MarkdownSkillSource,
)


def test_reference_selection_prefers_relevant_chinese_document():
    references = {
        "references/audience.md": "Audience setup and demographic targeting.",
        "references/conversion.md": (
            "TikTok pixel events, conversion tracking, attribution window, "
            "and diagnosing campaign conversion drops."
        ),
        "references/billing.md": "Billing profile and invoice settings.",
    }

    selected = select_reference_excerpts(
        "分析 TikTok pixel 转化追踪问题",
        references,
        max_documents=1,
        max_chars=600,
    )

    assert "references/conversion.md" in selected
    assert "references/audience.md" not in selected
    assert "references/billing.md" not in selected


def test_reference_selection_is_bounded_and_skips_unmatched_documents():
    references = {
        "references/a.md": "Audience targeting and demographics.",
        "references/b.md": "Billing invoices and account balance.",
    }

    assert select_reference_excerpts(
        "完全无关的检索词",
        references,
        max_documents=2,
        max_chars=80,
    ) == ""
    assert len(select_reference_excerpts(
        "audience targeting",
        references,
        max_documents=2,
        max_chars=80,
    )) <= 80


def test_triggered_skill_context_uses_relevant_reference_instead_of_first_file():
    skill = SimpleNamespace(
        name="conversion-expert",
        description="Guidance for diagnosing conversion attribution drops.",
        triggers=[SimpleNamespace(keywords=["转化"], patterns=[])],
        raw_markdown="Diagnose pixel attribution discrepancies and conversion drops.",
        reference_documents={
            "references/billing.md": "Billing profile and invoice settings.",
            "references/attribution.md": (
                "转化归因 attribution discrepancies and conversion drop diagnosis."
            ),
        },
    )
    loader = SimpleNamespace(list_all=lambda: {"tiktok": skill})
    selector = DynamicToolSelector(loader)

    context = selector._triggered_skill_context("排查转化归因下降问题")

    assert "references/attribution.md" in context
    assert "references/billing.md" not in context


def test_skill_reference_selection_does_not_let_skill_body_dilute_request_relevance():
    skill = SimpleNamespace(
        name="creative-strategy",
        description="Plan evidence-led creative roadmaps and production priorities.",
        triggers=[SimpleNamespace(keywords=["创意路线图"], patterns=[])],
        raw_markdown=(
            "Creative strategy includes hooks, funnel diagnostics, video formats, "
            "and many other topics not asked about in this request."
        ),
        reference_documents={
            "references/creative-roadmap.md": (
                "Prioritize concepts by evidence and production capacity."
            ),
            "references/hook-diagnosis.md": (
                "Diagnose thumb-stop, video hooks, hold rate, CTR, and conversion."
            ),
        },
    )
    selector = DynamicToolSelector(
        SimpleNamespace(list_all=lambda: {"creative-strategy": skill})
    )

    context = selector._triggered_skill_context(
        "制定创意路线图，按账户证据安排 production capacity"
    )

    assert "references/creative-roadmap.md" in context
    assert "references/hook-diagnosis.md" not in context


def test_skill_description_does_not_select_unrelated_provider_reference():
    skill = SimpleNamespace(
        name="account-diagnostics",
        description="Ad account report diagnostics and performance guidance.",
        triggers=[SimpleNamespace(keywords=["广告账户做审计"], patterns=[])],
        raw_markdown="Use current evidence and label unknowns.",
        reference_documents={
            "references/google-report-interpretation.md": (
                "GOOGLE_SPECIFIC_MARKER Search terms and conversion reporting."
            ),
        },
    )
    selector = DynamicToolSelector(
        SimpleNamespace(list_all=lambda: {"account-diagnostics": skill})
    )

    context = selector._triggered_skill_context("对 Meta 广告账户做审计")

    assert "[skill guidance: account-diagnostics]" in context
    assert "GOOGLE_SPECIFIC_MARKER" not in context


def test_generic_audit_terms_do_not_select_provider_specific_reference():
    selected = select_reference_excerpts(
        "Meta account audit Pass Fail Unknown evidence coverage",
        {
            "references/google-report-interpretation.md": (
                "Google Ads report coverage and account evidence may be Unknown."
            ),
        },
        max_documents=1,
        max_chars=600,
    )

    assert selected == ""


def test_markdown_skill_source_loads_advisory_text_references_only(tmp_path):
    skill_dir = tmp_path / "creative-strategy"
    references_dir = skill_dir / "references"
    scripts_dir = skill_dir / "scripts"
    assets_dir = skill_dir / "assets"
    references_dir.mkdir(parents=True)
    scripts_dir.mkdir()
    assets_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: creative-strategy\n"
        "description: Plan evidence-based advertising creative.\n"
        "version: 1.0.0\n---\n\n# Creative strategy\n",
        encoding="utf-8",
    )
    (references_dir / "roadmap.md").write_text(
        "Rank concepts by evidence and production capacity.",
        encoding="utf-8",
    )
    (references_dir / "thumbnail.png").write_bytes(b"not prompt text")
    (scripts_dir / "publish.py").write_text(
        "raise RuntimeError('scripts must never be loaded')",
        encoding="utf-8",
    )
    (assets_dir / "notes.md").write_text(
        "Assets outside references are not Skill guidance.",
        encoding="utf-8",
    )

    binding = MarkdownSkillSource.from_directory(skill_dir).list_skills()[0]

    assert binding.name == "creative-strategy"
    assert binding.reference_documents == {
        "references/roadmap.md":
            "Rank concepts by evidence and production capacity."
    }


def test_skill_catalog_injects_only_relevant_references_within_context_limit(
    tmp_path,
):
    skill_dir = tmp_path / "creative-strategy"
    references_dir = skill_dir / "references"
    references_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: creative-strategy\n"
        "description: Plan advertising creative roadmaps.\n"
        "version: 1.0.0\n---\n\n"
        "# Creative strategy\n"
        "Use evidence to choose which creative concepts to test.\n",
        encoding="utf-8",
    )
    (references_dir / "roadmap.md").write_text(
        "## Evidence-ranked concepts\n\n"
        "Prioritize concepts using account results, customer language, "
        "and organic signals. Check production capacity before scheduling.",
        encoding="utf-8",
    )
    (references_dir / "billing.md").write_text(
        "Billing profile, payment method, invoices, and account balance.",
        encoding="utf-8",
    )
    catalog = InMemorySkillCatalog(max_context_chars=1_000, max_skills=1)
    catalog.register_source(MarkdownSkillSource.from_directory(skill_dir))

    context = catalog.build_context(
        "创意路线图 evidence-ranked concepts production capacity"
    )

    assert len(context) <= 1_000
    assert "references/roadmap.md" in context
    assert "account results" in context
    assert "references/billing.md" not in context
