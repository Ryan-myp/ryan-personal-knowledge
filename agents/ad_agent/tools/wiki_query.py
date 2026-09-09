"""Compatibility facade for the canonical Markdown LLM Wiki provider.

New code should inject/use the application ``KnowledgeProvider`` contract.
These small helpers remain for CLI and existing callers, but they do not load
or search a second knowledge index.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.ad_agent.domain.ad.knowledge import (
    KnowledgeDocument,
    MarkdownWikiKnowledgeProvider,
)


@dataclass
class WikiEntry:
    """Legacy-shaped view over one canonical ``KnowledgeDocument``."""

    entry_id: str
    platform: str
    knowledge_type: str
    content: Dict[str, Any]
    source: str
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    score: float = 0.0


def _entry(document: KnowledgeDocument) -> WikiEntry:
    return WikiEntry(
        entry_id=document.document_id,
        platform=document.platform,
        knowledge_type=document.knowledge_type,
        content={
            "title": document.title or document.topic,
            "raw_content": document.excerpt,
            "source_file": document.source_ref,
            "layer": document.layer,
            "version": document.version,
            "updated_at": document.updated_at,
            "citation": document.citation,
        },
        source=document.source,
        tags=list(document.tags),
        created_at=document.updated_at,
        score=document.score,
    )


class MarkdownWikiLoader:
    """Legacy loader API backed by ``MarkdownWikiKnowledgeProvider``."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self.provider = MarkdownWikiKnowledgeProvider(self.base_path)

    @property
    def entries(self) -> Dict[str, WikiEntry]:
        return {
            document.document_id: _entry(document)
            for document in self.provider.documents
        }

    def search(
        self,
        query: str,
        platforms: List[str] = None,
        knowledge_types: List[str] = None,
        limit: int = 10,
    ) -> List[WikiEntry]:
        return [
            _entry(document)
            for document in self.provider.query(
                query or "",
                platforms=platforms,
                knowledge_types=knowledge_types,
                limit=limit,
            )
        ]

    def get_by_type(self, knowledge_type: str, platform: str = None) -> List[WikiEntry]:
        return self.search(
            "",
            platforms=[platform] if platform else None,
            knowledge_types=[knowledge_type],
            limit=max(1, len(self.provider.documents)),
        )

    def get_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {"total": 0, "by_platform": {}, "by_type": {}, "by_layer": {}}
        for document in self.provider.documents:
            if document.status != "published":
                continue
            stats["total"] += 1
            for key, value in (
                ("by_platform", document.platform),
                ("by_type", document.knowledge_type),
                ("by_layer", document.layer),
            ):
                stats[key][value] = stats[key].get(value, 0) + 1
        return stats

    def validate(self) -> list[dict[str, Any]]:
        return self.provider.validate()


_wiki_instances: dict[str, MarkdownWikiLoader] = {}


def get_wiki_loader(base_path: str = None) -> MarkdownWikiLoader:
    path = Path(base_path or Path(__file__).parent.parent / "knowledge_base").resolve()
    key = str(path)
    if key not in _wiki_instances:
        _wiki_instances[key] = MarkdownWikiLoader(key)
    return _wiki_instances[key]


class WikiQueryTool:
    """Read-only Wiki facade for CLI and compatibility callers."""

    def __init__(self, base_path: str = None):
        self.loader = get_wiki_loader(base_path)

    def search(
        self,
        query: str,
        platforms: List[str] = None,
        knowledge_types: List[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "entry_id": result.entry_id,
                "platform": result.platform,
                "knowledge_type": result.knowledge_type,
                "content": result.content,
                "source": result.source,
                "tags": result.tags,
                "score": result.score,
                "citation": result.content.get("citation", {}),
            }
            for result in self.loader.search(query, platforms, knowledge_types, limit)
        ]

    def get_best_practices(
        self, platform: str = None, business_type: str = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        query = business_type or ""
        return [
            result.content
            for result in self.loader.search(
                query,
                platforms=[platform] if platform else None,
                knowledge_types=["best_practice"],
                limit=limit,
            )
        ]

    def get_error_solutions(
        self, error_code: str, platform: str = None, limit: int = 10
    ) -> List[str]:
        results = self.loader.search(
            error_code,
            platforms=[platform] if platform else None,
            knowledge_types=["error_pattern"],
            limit=limit,
        )
        solutions = []
        for result in results:
            content = str(result.content.get("raw_content", ""))
            match = re.search(r"解决方案[：:]\s*(.*)", content, re.DOTALL)
            if match:
                solutions.append(match.group(1).strip())
        return solutions[:limit] if limit else solutions

    def get_workflow(self, platform: str, workflow_type: str = None) -> Dict[str, Any]:
        results = self.loader.search(
            workflow_type or "",
            platforms=None if not platform or str(platform).lower() == "all" else [platform],
            knowledge_types=["workflow"],
            limit=max(1, len(self.loader.provider.documents)),
        )
        return {"platform": platform or "all", "workflows": [result.content for result in results]}

    def get_stats(self) -> Dict[str, Any]:
        return self.loader.get_stats()


def wiki_search(
    query: str, platforms: List[str] = None, knowledge_types: List[str] = None, limit: int = 10
) -> List[Dict[str, Any]]:
    return WikiQueryTool().search(query, platforms, knowledge_types, limit)


def wiki_get_best_practices(
    platform: str = None, business_type: str = None, limit: int = 10
) -> List[Dict[str, Any]]:
    return WikiQueryTool().get_best_practices(platform, business_type, limit)


def wiki_get_errors(error_code: str, platform: str = None, limit: int = 10) -> List[str]:
    return WikiQueryTool().get_error_solutions(error_code, platform, limit)


def wiki_get_workflow(platform: str, workflow_type: str = None) -> Dict[str, Any]:
    return WikiQueryTool().get_workflow(platform, workflow_type)


def main() -> None:
    parser = argparse.ArgumentParser(description="Markdown LLM Wiki 查询工具")
    parser.add_argument("--action", "-a", required=True, choices=["search", "best_practices", "errors", "workflow", "stats"])
    parser.add_argument("--query", "-q", default=None)
    parser.add_argument("--platform", "-p", default=None)
    parser.add_argument("--error", "-e", default=None)
    parser.add_argument("--workflow-type", "-w", default=None)
    parser.add_argument("--limit", "-n", type=int, default=10)
    args = parser.parse_args()
    tool = WikiQueryTool()
    if args.action == "search":
        result = tool.search(args.query or "", [args.platform] if args.platform and args.platform != "all" else None, limit=args.limit)
    elif args.action == "best_practices":
        result = tool.get_best_practices(args.platform, limit=args.limit)
    elif args.action == "errors":
        result = tool.get_error_solutions(args.error or args.query or "", limit=args.limit)
    elif args.action == "workflow":
        result = tool.get_workflow(args.platform or "all", args.workflow_type)
    else:
        result = tool.get_stats()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
