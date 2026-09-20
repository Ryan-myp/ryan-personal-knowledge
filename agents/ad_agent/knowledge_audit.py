"""Repository-level quality audit for the Markdown LLM Wiki.

The runtime provider intentionally stays read-only and small.  This module
contains the broader maintenance checks that are useful in CI and during
content reviews: metadata contracts, object-directory alignment, provenance,
wikilinks, retrieval-case references and platform coverage.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .domain.ad.knowledge import (
    WIKI_LAYERS,
    WIKI_OBJECT_TYPES,
    WIKI_STATUSES,
    parse_frontmatter,
)


WIKI_DIR_TYPES = {
    "raw": "raw",
    "entities": "entity",
    "concepts": "concept",
    "comparisons": "comparison",
    "queries": "query",
    "platforms": "concept",
    "business": "concept",
    "expertise": "concept",
    "dynamic": "concept",
}
REQUIRED_FIELDS = {
    "id",
    "title",
    "layer",
    "knowledge_type",
    "platform",
    "source_ref",
    "version",
    "confidence",
    "updated_at",
    "status",
}
SOURCE_KINDS = {"official", "code", "internal", "user", "inferred"}
AUTHORITIES = {"official", "repository", "operator", "llm"}
EVIDENCE_LEVELS = {"verified", "reviewed", "provisional"}
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class KnowledgeAuditIssue:
    severity: str
    code: str
    message: str
    path: str = ""
    document_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class _Page:
    path: Path
    relative_path: str
    metadata: Mapping[str, Any]
    body: str
    is_control: bool

    @property
    def document_id(self) -> str:
        return str(self.metadata.get("id") or "")

    @property
    def title(self) -> str:
        return str(self.metadata.get("title") or "")

    @property
    def status(self) -> str:
        return str(self.metadata.get("status") or "published").lower()

    @property
    def wiki_type(self) -> str:
        explicit = str(
            self.metadata.get("wiki_type") or self.metadata.get("page_type") or ""
        ).strip().lower()
        if explicit:
            return explicit
        return WIKI_DIR_TYPES.get(self.path.parts[-2], "concept")


def _is_control(relative_path: Path) -> bool:
    return (
        relative_path.name == "README.md"
        or relative_path.name in {
            "ARCHITECTURE.md",
            "SCHEMA.md",
            "UPGRADE_SUMMARY.md",
            "USAGE_GUIDE.md",
            "QUALITY_STANDARD.md",
            "index.md",
            "log.md",
        }
    )


def _load_pages(root: Path) -> list[_Page]:
    pages: list[_Page] = []
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            pages.append(
                _Page(path, relative.as_posix(), {}, "", _is_control(relative))
            )
            continue
        metadata, body = parse_frontmatter(raw)
        pages.append(
            _Page(path, relative.as_posix(), metadata, body, _is_control(relative))
        )
    return pages


def _issue(
    severity: str,
    code: str,
    message: str,
    page: _Page | None = None,
) -> KnowledgeAuditIssue:
    return KnowledgeAuditIssue(
        severity=severity,
        code=code,
        message=message,
        path=page.relative_path if page else "",
        document_id=page.document_id if page else "",
    )


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip().strip('"').strip("'")
    if not DATE_RE.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def infer_source_kind(source_ref: str, source: str = "") -> str:
    """Infer a conservative source class for legacy pages without metadata."""
    ref = str(source_ref or "").strip().lower()
    owner = str(source or "").strip().lower()
    if ref.startswith(("http://", "https://")):
        return "official"
    if any(marker in ref for marker in ("tools/providers/", "api_clients/", "skill", "_surface_data")):
        return "code"
    if ref.startswith(("raw://", "upload://", "managed://")) or "user" in owner:
        return "user"
    if ref:
        return "internal"
    return "inferred"


def _normalise_link(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _coverage(pages: Iterable[_Page]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for page in pages:
        if page.is_control or page.wiki_type == "raw" or page.status != "published":
            continue
        platform = str(page.metadata.get("platform") or "all").strip().lower()
        knowledge_type = str(
            page.metadata.get("knowledge_type") or "general"
        ).strip().lower()
        result[platform][knowledge_type] += 1
    return {platform: dict(values) for platform, values in result.items()}


def audit_knowledge_base(
    root: str | Path,
    *,
    cases_path: str | Path | None = None,
    today: date | None = None,
    stale_days: int = 180,
) -> dict[str, Any]:
    """Return a JSON-serialisable audit report for a Wiki directory."""
    base = Path(root).resolve()
    pages = _load_pages(base)
    issues: list[KnowledgeAuditIssue] = []
    content_pages = [page for page in pages if not page.is_control]
    published_pages = [
        page
        for page in content_pages
        if page.status == "published" and page.wiki_type != "raw"
    ]
    ids: dict[str, list[_Page]] = defaultdict(list)
    titles: dict[str, list[_Page]] = defaultdict(list)
    known_ids: set[str] = set()
    known_titles: set[str] = set()
    known_stems: set[str] = set()

    for page in content_pages:
        metadata = page.metadata
        if not metadata:
            issues.append(_issue("error", "frontmatter_missing", "页面缺少 frontmatter", page))
            continue
        if page.document_id:
            ids[page.document_id].append(page)
            known_ids.add(page.document_id)
        if page.title:
            titles[_normalise_link(page.title)].append(page)
            known_titles.add(_normalise_link(page.title))
        known_stems.add(_normalise_link(page.path.stem))
        if page.wiki_type not in WIKI_OBJECT_TYPES:
            issues.append(_issue("error", "invalid_wiki_type", f"wiki_type 不合法: {page.wiki_type}", page))
        if page.wiki_type == "system":
            issues.append(_issue("error", "system_page_in_content", "system 页面应使用根目录维护文件，不应作为知识页", page))

        if page.wiki_type == "raw":
            if page.status not in {"draft", "published"}:
                issues.append(_issue("error", "invalid_raw_status", "raw 页面状态不合法", page))
            continue

        missing = sorted(field for field in REQUIRED_FIELDS if not str(metadata.get(field) or "").strip())
        for field in missing:
            issues.append(_issue("error", "required_field_missing", f"缺少必填字段: {field}", page))
        layer = str(metadata.get("layer") or "").strip().lower()
        if layer and layer not in WIKI_LAYERS:
            issues.append(_issue("error", "invalid_layer", f"layer 不合法: {layer}", page))
        status = page.status
        if status not in WIKI_STATUSES:
            issues.append(_issue("error", "invalid_status", f"status 不合法: {status}", page))
        version = str(metadata.get("version") or "").strip().strip('"').strip("'")
        if version and not SEMVER_RE.fullmatch(version):
            issues.append(_issue("error", "invalid_version", f"version 不是 semver: {version}", page))
        try:
            confidence = float(metadata.get("confidence"))
        except (TypeError, ValueError):
            confidence = None
        if confidence is None or not 0 <= confidence <= 1:
            issues.append(_issue("error", "invalid_confidence", "confidence 必须在 0 到 1 之间", page))
        updated = _parse_date(metadata.get("updated_at") or metadata.get("updated"))
        if not updated:
            issues.append(_issue("error", "invalid_updated_at", "updated_at 必须是 YYYY-MM-DD", page))
        elif today and (today - updated).days > stale_days:
            issues.append(_issue("warning", "stale_document", f"文档已超过 {stale_days} 天未更新", page))

        expected_type = WIKI_DIR_TYPES.get(page.path.parts[0])
        if expected_type and page.wiki_type != expected_type:
            issues.append(_issue(
                "error",
                "directory_type_mismatch",
                f"目录 {page.path.parts[0]} 期望 wiki_type={expected_type}，实际为 {page.wiki_type}",
                page,
            ))

        source_ref = str(metadata.get("source_ref") or "").strip()
        if source_ref == page.relative_path or source_ref.endswith(page.relative_path):
            issues.append(_issue(
                "warning",
                "self_referential_source",
                "source_ref 指向当前页面自身，不能证明外部来源",
                page,
            ))
        if not metadata.get("source_kind"):
            issues.append(_issue(
                "warning",
                "source_kind_missing",
                f"建议补充 source_kind（推断值: {infer_source_kind(source_ref, metadata.get('source', ''))}）",
                page,
            ))
        if not metadata.get("authority"):
            issues.append(_issue("warning", "authority_missing", "建议补充 authority", page))
        if not metadata.get("evidence_level"):
            issues.append(_issue("warning", "evidence_level_missing", "建议补充 evidence_level", page))
        elif str(metadata["evidence_level"]).strip().lower() not in EVIDENCE_LEVELS:
            issues.append(_issue("error", "invalid_evidence_level", "evidence_level 不合法", page))
        if not metadata.get("last_verified_at"):
            issues.append(_issue("warning", "last_verified_at_missing", "建议补充 last_verified_at", page))

    for document_id, matches in ids.items():
        if len(matches) > 1:
            for page in matches:
                issues.append(_issue("error", "duplicate_id", f"重复 document id: {document_id}", page))
    for normalised_title, matches in titles.items():
        if len(matches) > 1:
            for page in matches:
                issues.append(_issue("warning", "duplicate_title", f"重复标题: {normalised_title}", page))

    link_count: Counter[str] = Counter()
    for page in published_pages:
        for raw_target in WIKILINK_RE.findall(page.body):
            target = _normalise_link(raw_target)
            if target in known_ids or target in known_titles or target in known_stems:
                link_count[target] += 1
            else:
                issues.append(_issue("error", "broken_wikilink", f"找不到 wikilink 目标: [[{raw_target}]]", page))

    for page in published_pages:
        if page.wiki_type in {"entity", "comparison", "query"}:
            key_candidates = {
                _normalise_link(page.document_id),
                _normalise_link(page.title),
                _normalise_link(page.path.stem),
            }
            if not any(link_count.get(candidate) for candidate in key_candidates):
                issues.append(_issue("warning", "orphan_page", "页面没有被其他已发布页面链接或引用", page))

    case_stats = {
        "total": 0,
        "invalid_expected_ids": 0,
        "queries_with_expected_hit": 0,
        "negative_cases": 0,
        "negative_failures": 0,
    }
    if cases_path:
        try:
            cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            issues.append(KnowledgeAuditIssue("error", "cases_unreadable", f"无法读取检索案例: {exc}"))
            cases = []
        if not isinstance(cases, list):
            issues.append(KnowledgeAuditIssue("error", "cases_invalid", "检索案例必须是数组"))
            cases = []
        for case in cases:
            case_stats["total"] += 1
            if not isinstance(case, Mapping):
                issues.append(KnowledgeAuditIssue("error", "case_invalid", "检索案例必须是对象"))
                continue
            expected = case.get("expected") or []
            missing_expected = [str(item) for item in expected if str(item) not in known_ids]
            if missing_expected:
                case_stats["invalid_expected_ids"] += len(missing_expected)
                issues.append(KnowledgeAuditIssue(
                    "error",
                    "case_expected_id_missing",
                    f"检索案例引用不存在的 document id: {', '.join(missing_expected)}",
                ))
            if isinstance(case.get("query"), str):
                try:
                    from .domain.ad.knowledge import MarkdownWikiKnowledgeProvider

                    results = MarkdownWikiKnowledgeProvider(base).query(
                        case["query"], limit=3
                    )
                except (OSError, RuntimeError, TypeError, ValueError):
                    results = []
                result_ids = {result.document_id for result in results}
                if result_ids.intersection(str(item) for item in expected):
                    case_stats["queries_with_expected_hit"] += 1
                is_negative = bool(
                    case.get("expect_empty")
                    or case.get("forbidden_platforms")
                    or case.get("forbidden_wiki_types")
                    or case.get("forbidden_statuses")
                )
                if is_negative:
                    case_stats["negative_cases"] += 1
                    if case.get("expect_empty") and results:
                        case_stats["negative_failures"] += 1
                    forbidden_platforms = {
                        str(item).strip().lower()
                        for item in case.get("forbidden_platforms", [])
                    }
                    forbidden_wiki_types = {
                        str(item).strip().lower()
                        for item in case.get("forbidden_wiki_types", [])
                    }
                    forbidden_statuses = {
                        str(item).strip().lower()
                        for item in case.get("forbidden_statuses", [])
                    }
                    if any(result.platform in forbidden_platforms for result in results):
                        case_stats["negative_failures"] += 1
                    if any(result.wiki_type in forbidden_wiki_types for result in results):
                        case_stats["negative_failures"] += 1
                    if any(result.status in forbidden_statuses for result in results):
                        case_stats["negative_failures"] += 1

    coverage = _coverage(content_pages)
    required_platforms = {"google-ads", "meta", "tiktok", "dv360"}
    required_types = {"hierarchy", "workflow", "error_pattern"}
    for platform in sorted(required_platforms):
        platform_types = set(coverage.get(platform, {}))
        missing_types = sorted(required_types - platform_types)
        if missing_types:
            issues.append(KnowledgeAuditIssue(
                "warning",
                "platform_coverage_gap",
                f"{platform} 缺少知识类型: {', '.join(missing_types)}",
            ))

    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "root": str(base),
        "pages": len(content_pages),
        "published_pages": len(published_pages),
        "ids": len(known_ids),
        "issues": [issue.to_dict() for issue in issues],
        "errors": len(errors),
        "warnings": len(warnings),
        "coverage": coverage,
        "cases": case_stats,
    }
