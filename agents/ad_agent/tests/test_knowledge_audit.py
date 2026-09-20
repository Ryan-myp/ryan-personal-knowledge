from datetime import date

from agents.ad_agent.knowledge_audit import audit_knowledge_base, infer_source_kind
from agents.ad_agent.scripts.normalize_knowledge_metadata import _normalise_page


def _page(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_audit_reports_contract_provenance_links_and_case_drift(tmp_path):
    _page(
        tmp_path,
        "entities/meta.md",
        """---
id: meta-entity
title: Meta Ads
layer: platform
knowledge_type: hierarchy
platform: meta
source_ref: https://example.invalid/meta
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-18"
status: published
wiki_type: entity
---
# Meta Ads

实体页。
""",
    )
    _page(
        tmp_path,
        "concepts/guide.md",
        """---
id: guide
title: Guide
layer: business
knowledge_type: workflow
platform: all
source_ref: concepts/guide.md
version: "1.0.0"
confidence: 0.8
updated_at: "2026-09-18"
status: published
wiki_type: concept
---
# Guide

See [[Meta Ads]] and [[Missing Page]].
""",
    )
    _page(
        tmp_path,
        "concepts/duplicate.md",
        """---
id: meta-entity
title: Duplicate
layer: business
knowledge_type: workflow
platform: all
source_ref: https://example.invalid/duplicate
version: "1.0.0"
confidence: 0.8
updated_at: "2026-09-18"
status: published
wiki_type: concept
---
# Duplicate

重复 ID。
""",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        '[{"query": "meta", "expected": ["missing-id"]}]',
        encoding="utf-8",
    )

    report = audit_knowledge_base(
        tmp_path,
        cases_path=cases,
        today=date(2026, 9, 18),
    )
    codes = {item["code"] for item in report["issues"]}

    assert report["errors"] >= 3
    assert "duplicate_id" in codes
    assert "broken_wikilink" in codes
    assert "self_referential_source" in codes or "self_referential_source" in {
        item["code"] for item in report["issues"]
    }
    assert "case_expected_id_missing" in codes
    assert "source_kind_missing" in codes


def test_audit_infers_legacy_source_kind_without_overclaiming():
    assert infer_source_kind("https://developers.google.com/google-ads/api") == "official"
    assert infer_source_kind("agents/ad_agent/capabilities/google/tool.py") == "code"
    assert infer_source_kind("agents/ad_agent/knowledge_base/page.md") == "internal"
    assert infer_source_kind("") == "inferred"


def test_metadata_normalizer_only_updates_provenance_fields(tmp_path):
    root = tmp_path / "knowledge"
    path = root / "business" / "guide.md"
    path.parent.mkdir(parents=True)
    original = """---
id: guide
title: Guide
layer: business
knowledge_type: workflow
platform: all
source: internal operating notes
source_ref: business/guide.md
version: "1.0.0"
confidence: 0.8
updated_at: "2026-09-18"
status: published
---
# Guide

正文不能被 normalizer 改写。
"""
    path.write_text(original, encoding="utf-8")

    updated, fields = _normalise_page(
        path, root, today="2026-09-20"
    )

    assert set(fields) == {
        "source_ref", "source_kind", "authority",
        "evidence_level", "last_verified_at",
    }
    assert "正文不能被 normalizer 改写。" in updated
    assert "source_ref: \"internal://ad-agent/playbook/guide\"" in updated
    assert 'source_kind: "internal"' in updated
    assert 'authority: "operator"' in updated
    assert 'evidence_level: "provisional"' in updated
    assert 'last_verified_at: "2026-09-18"' in updated
