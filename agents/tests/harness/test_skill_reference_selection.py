"""Skill references are selected by request relevance, not directory order."""

from types import SimpleNamespace

from agents.agent_harness.core.tool_selector import (
    DynamicToolSelector,
    select_reference_excerpts,
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
                "Attribution discrepancies and conversion drop diagnosis."
            ),
        },
    )
    loader = SimpleNamespace(list_all=lambda: {"tiktok": skill})
    selector = DynamicToolSelector(loader)

    context = selector._triggered_skill_context("排查转化归因下降问题")

    assert "references/attribution.md" in context
    assert "references/billing.md" not in context
