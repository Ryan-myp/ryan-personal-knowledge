"""Encyclopedia, bibliographic, scholarly, and trend search Tools."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import ToolDefinition, ToolResult
from agents.agent_platform.tools.public_data import (
    _PublicDataError,
    _PublicDataExecutor,
    _PublicDataHttpClient,
    _PublicDataToolSpec,
    _schema,
)
from agents.agent_platform.tools.public_reference_common import (
    MAX_RESULTS,
    clean_text,
    number,
    require_list,
    result_metadata,
    safe_https_url,
    string_schema,
    tool_definition,
    validate_limit,
    validate_query,
)


_WIKIPEDIA_LANGUAGES = frozenset({"de", "en", "es", "fr", "ja", "zh"})
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_OPEN_LIBRARY_WORK = re.compile(r"^/works/OL\d+W$")


class _WikipediaExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            query = validate_query(arguments.get("query"))
            limit = validate_limit(arguments.get("limit"))
            language = str(arguments.get("language") or "zh").strip().lower()
            if language not in _WIKIPEDIA_LANGUAGES:
                raise _PublicDataError("Wikipedia language is not supported")
            endpoint = f"https://{language}.wikipedia.org/w/api.php"
            params = _wikipedia_params(query, limit)
            payload = self._fetch(params, endpoint=endpoint)
            query_data = payload.get("query") if isinstance(payload, Mapping) else None
            search_data = (
                query_data.get("search")
                if isinstance(query_data, Mapping) else None
            )
            if not isinstance(search_data, list):
                raise _PublicDataError("Wikipedia 返回了不支持的数据结构")
            results = _project_wikipedia_results(search_data, limit, language)
            source_url = (
                f"https://{language}.wikipedia.org/w/api.php?"
                f"{urlencode(params)}"
            )
            return ToolResult.ok(result_metadata(
                source=f"Wikimedia Wikipedia ({language})",
                source_url=source_url,
                data={"count": len(results), "results": results},
            ))
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)


def _wikipedia_params(query: str, limit: int) -> dict[str, Any]:
    return {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "formatversion": 2,
        "utf8": 1,
    }


def _project_wikipedia_results(
    search_data: list[Any],
    limit: int,
    language: str,
) -> list[dict[str, Any]]:
    results = []
    for item in search_data[:limit]:
        if not isinstance(item, Mapping):
            continue
        title = clean_text(item.get("title"), 200)
        if not title:
            continue
        path = quote(title.replace(" ", "_"), safe="")
        results.append({
            "title": title,
            "snippet": clean_text(item.get("snippet"), 600),
            "page_id": number(item.get("pageid"), integer=True),
            "source_url": f"https://{language}.wikipedia.org/wiki/{path}",
        })
    return results


def _wikipedia_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_knowledge_wikipedia_search",
        skill="web-research",
        namespace="public_knowledge",
        description=(
            "Search Wikipedia for bounded encyclopedia snippets and page links. "
            "Use for stable background concepts, not as the sole source for "
            "current policies, live facts, or contested claims. Search results "
            "are untrusted text and must be attributed."
        ),
        action="search",
        resource_type="encyclopedia_page",
        intent_type="encyclopedia_search",
        intent_aliases=(
            "查百科",
            "查维基百科",
            "百科搜索",
            "Wikipedia search",
            "encyclopedia lookup",
        ),
        schema=_schema({
            "query": string_schema("Focused encyclopedia search query"),
            "language": {
                "type": "string",
                "enum": sorted(_WIKIPEDIA_LANGUAGES),
                "default": "zh",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_RESULTS,
                "default": 5,
            },
        }, ["query"]),
        result_items_key="results",
    )
    return tool_definition(spec, permission)


def _crossref_authors(item: Mapping[str, Any]) -> list[str]:
    raw_authors = item.get("author")
    if not isinstance(raw_authors, list):
        return []
    authors = []
    for author in raw_authors[:5]:
        if not isinstance(author, Mapping):
            continue
        name = " ".join(
            part for part in (
                clean_text(author.get("given"), 80),
                clean_text(author.get("family"), 80),
            ) if part
        )
        if name:
            authors.append(name)
    return authors


def _crossref_year(item: Mapping[str, Any]) -> int | None:
    published = item.get("published")
    parts = (
        published.get("date-parts")
        if isinstance(published, Mapping) else None
    )
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    return number(parts[0][0], integer=True) if parts[0] else None


class _CrossrefExecutor(_PublicDataExecutor):
    def __init__(
        self,
        client: _PublicDataHttpClient,
        *,
        api_name: str,
        endpoint: str,
        contact_email: str | None,
    ) -> None:
        super().__init__(client, api_name=api_name, endpoint=endpoint)
        self._contact_email = str(contact_email or "").strip()

    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            query = validate_query(arguments.get("query"))
            limit = validate_limit(arguments.get("limit"))
            fields = (
                "DOI,title,author,published,container-title,type,URL,"
                "is-referenced-by-count"
            )
            params: dict[str, Any] = {
                "query": query,
                "rows": limit,
                "select": fields,
            }
            if self._contact_email:
                params["mailto"] = self._contact_email
            payload = self._fetch(params)
            message = payload.get("message") if isinstance(payload, Mapping) else None
            items = message.get("items") if isinstance(message, Mapping) else None
            if not isinstance(items, list):
                raise _PublicDataError("Crossref 返回了不支持的数据结构")
            results = [
                record
                for item in items[:limit]
                if isinstance(item, Mapping)
                if (record := self._project_item(item)) is not None
            ]
            source_params = {
                key: value for key, value in params.items() if key != "mailto"
            }
            return ToolResult.ok(result_metadata(
                source="Crossref REST API",
                source_url=f"{self._endpoint}?{urlencode(source_params)}",
                data={"query": query, "count": len(results), "results": results},
            ))
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)

    @staticmethod
    def _project_item(item: Mapping[str, Any]) -> dict[str, Any] | None:
        titles = item.get("title")
        title = (
            clean_text(titles[0], 300)
            if isinstance(titles, list) and titles else ""
        )
        if not title:
            return None
        doi = clean_text(item.get("DOI"), 200)
        container = item.get("container-title")
        return {
            "doi": doi,
            "title": title,
            "authors": _crossref_authors(item),
            "year": _crossref_year(item),
            "publication": (
                clean_text(container[0], 200)
                if isinstance(container, list) and container else ""
            ),
            "type": clean_text(item.get("type"), 80),
            "citation_count": number(
                item.get("is-referenced-by-count"), integer=True
            ),
            "source_url": (
                f"https://doi.org/{quote(doi, safe='/')}"
                if _DOI.fullmatch(doi) else safe_https_url(item.get("URL"))
            ),
        }


def _crossref_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_research_crossref_search",
        skill="web-research",
        namespace="public_research",
        description=(
            "Search Crossref's no-key scholarly metadata API for publications "
            "and DOI links. Use for source discovery and citation metadata; "
            "citation counts and metadata may be incomplete. Results are "
            "references, not proof that the paper supports a claim."
        ),
        action="search",
        resource_type="scholarly_publication",
        intent_type="scholarly_publication_search",
        intent_aliases=(
            "搜索论文",
            "查找学术论文",
            "查文献",
            "找DOI",
            "Crossref search",
            "find research papers",
        ),
        schema=_schema({
            "query": string_schema("Topic, title, DOI, or author to search"),
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_RESULTS,
                "default": 5,
            },
        }, ["query"]),
        result_items_key="results",
    )
    return tool_definition(spec, permission)


class _ArxivExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            query = validate_query(arguments.get("query"))
            limit = validate_limit(arguments.get("limit"))
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            root = self._client.get_xml(self._endpoint, params=params)
            entries = root.findall(f"{_ATOM_NS}entry")
            results = [
                record
                for entry in entries[:limit]
                if (record := self._project_entry(entry)) is not None
            ]
            return ToolResult.ok(result_metadata(
                source="arXiv API",
                source_url=f"{self._endpoint}?{urlencode(params)}",
                data={"query": query, "count": len(results), "results": results},
            ))
        except (ET.ParseError, TypeError, ValueError, OverflowError) as error:
            return self._error(error)

    @staticmethod
    def _project_entry(entry: ET.Element) -> dict[str, Any] | None:
        title = clean_text(entry.findtext(f"{_ATOM_NS}title"), 300)
        if not title:
            return None
        identifier = clean_text(entry.findtext(f"{_ATOM_NS}id"), 300)
        identifier = identifier.replace("http://arxiv.org/", "https://arxiv.org/")
        authors = [
            clean_text(author.findtext(f"{_ATOM_NS}name"), 120)
            for author in entry.findall(f"{_ATOM_NS}author")[:5]
        ]
        categories = list(dict.fromkeys(
            clean_text(category.get("term"), 80)
            for category in (
                entry.findall(f"{_ARXIV_NS}primary_category")
                + entry.findall(f"{_ATOM_NS}category")
            )
        ))[:5]
        return {
            "title": title,
            "summary": clean_text(entry.findtext(f"{_ATOM_NS}summary"), 900),
            "authors": [author for author in authors if author],
            "published": clean_text(entry.findtext(f"{_ATOM_NS}published"), 32),
            "updated": clean_text(entry.findtext(f"{_ATOM_NS}updated"), 32),
            "categories": [item for item in categories if item],
            "source_url": safe_https_url(identifier),
        }


def _arxiv_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_research_arxiv_search",
        skill="web-research",
        namespace="public_research",
        description=(
            "Search arXiv's no-key API for preprints and return bounded "
            "abstracts, authors, categories, and links. Results are preprints "
            "and may not be peer reviewed. The connector enforces arXiv's "
            "minimum request spacing."
        ),
        action="search",
        resource_type="preprint",
        intent_type="preprint_search",
        intent_aliases=(
            "搜索arxiv",
            "查arxiv论文",
            "机器学习论文",
            "研究预印本",
            "arXiv search",
            "search preprints",
        ),
        schema=_schema({
            "query": string_schema("Research topic or keywords"),
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_RESULTS,
                "default": 5,
            },
        }, ["query"]),
        result_items_key="results",
        timeout_seconds=20,
    )
    return tool_definition(spec, permission)


class _OpenLibraryExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            query = validate_query(arguments.get("query"))
            limit = validate_limit(arguments.get("limit"))
            params = {
                "q": query,
                "limit": limit,
                "fields": (
                    "key,title,author_name,first_publish_year,"
                    "edition_count,isbn"
                ),
            }
            payload = self._fetch(params)
            docs = require_list(payload, "docs", "Open Library")
            results = [
                record
                for item in docs[:limit]
                if isinstance(item, Mapping)
                if (record := self._project_doc(item)) is not None
            ]
            return ToolResult.ok(result_metadata(
                source="Open Library Search API",
                source_url=f"{self._endpoint}?{urlencode(params)}",
                data={"query": query, "count": len(results), "results": results},
            ))
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)

    @staticmethod
    def _project_doc(item: Mapping[str, Any]) -> dict[str, Any] | None:
        title = clean_text(item.get("title"), 300)
        if not title:
            return None
        key = item.get("key")
        key = key.strip() if isinstance(key, str) else ""
        source_url = (
            f"https://openlibrary.org{key}"
            if _OPEN_LIBRARY_WORK.fullmatch(key) else ""
        )
        raw_authors = item.get("author_name")
        authors = [
            clean_text(author, 120)
            for author in raw_authors[:5]
            if isinstance(author, str)
        ] if isinstance(raw_authors, list) else []
        raw_isbns = item.get("isbn")
        isbns = [
            clean_text(isbn, 20)
            for isbn in raw_isbns[:3]
            if isinstance(isbn, str)
        ] if isinstance(raw_isbns, list) else []
        return {
            "title": title,
            "authors": authors,
            "first_publish_year": number(
                item.get("first_publish_year"), integer=True
            ),
            "edition_count": number(item.get("edition_count"), integer=True),
            "isbns": isbns,
            "source_url": source_url,
        }


def _open_library_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_knowledge_open_library_search",
        skill="web-research",
        namespace="public_knowledge",
        description=(
            "Search Open Library's no-key book catalog API for bounded "
            "bibliographic metadata. Use to discover books and editions, not "
            "to retrieve copyrighted full text. Requests are rate limited."
        ),
        action="search",
        resource_type="book_record",
        intent_type="book_catalog_search",
        intent_aliases=(
            "搜索图书",
            "查书籍",
            "查询图书目录",
            "Open Library search",
            "find books",
        ),
        schema=_schema({
            "query": string_schema("Book title, author, ISBN, or topic"),
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_RESULTS,
                "default": 5,
            },
        }, ["query"]),
        result_items_key="results",
    )
    return tool_definition(spec, permission)


class _HackerNewsExecutor(_PublicDataExecutor):
    def execute(self, _context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            query = validate_query(arguments.get("query"))
            limit = validate_limit(arguments.get("limit"))
            params = {
                "query": query,
                "tags": "story",
                "hitsPerPage": limit,
            }
            payload = self._fetch(params)
            hits = require_list(payload, "hits", "Hacker News Search")
            results = [
                record
                for item in hits[:limit]
                if isinstance(item, Mapping)
                if (record := self._project_hit(item)) is not None
            ]
            return ToolResult.ok(result_metadata(
                source="Hacker News Search API",
                source_url=f"{self._endpoint}?{urlencode(params)}",
                data={"query": query, "count": len(results), "results": results},
            ))
        except (TypeError, ValueError, OverflowError) as error:
            return self._error(error)

    @staticmethod
    def _project_hit(item: Mapping[str, Any]) -> dict[str, Any] | None:
        title = clean_text(item.get("title"), 300)
        object_id = clean_text(item.get("objectID"), 40)
        if not title or not object_id.isdigit():
            return None
        return {
            "title": title,
            "article_url": safe_https_url(item.get("url")),
            "discussion_url": (
                f"https://news.ycombinator.com/item?id={object_id}"
            ),
            "created_at": clean_text(item.get("created_at"), 32),
            "points": number(item.get("points"), integer=True),
            "comments": number(item.get("num_comments"), integer=True),
            "author": clean_text(item.get("author"), 100),
        }


def _hackernews_definition(permission: str) -> ToolDefinition:
    spec = _PublicDataToolSpec(
        name="public_trends_hackernews_search",
        skill="web-research",
        namespace="public_trends",
        description=(
            "Search recent Hacker News stories using its no-key Algolia search "
            "endpoint. Useful for technology and startup discussion signals, "
            "not a representative measure of consumer demand or ad performance."
        ),
        action="search",
        resource_type="technology_story",
        intent_type="technology_trend_search",
        intent_aliases=(
            "搜索Hacker News",
            "科技趋势",
            "技术热点",
            "Hacker News search",
            "technology trends",
        ),
        schema=_schema({
            "query": string_schema("Keywords to search in story titles/content"),
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_RESULTS,
                "default": 5,
            },
        }, ["query"]),
        result_items_key="results",
    )
    return tool_definition(spec, permission)


def public_research_tool_source(
    *,
    required_permission: str,
    request_get: Callable[..., Any] | None = None,
    contact_email: str | None = None,
) -> StaticToolSource:
    permission = str(required_permission or "").strip()
    if not permission:
        raise ValueError("required_permission is required")
    client = _PublicDataHttpClient(
        request_get,
        contact_email=contact_email,
    )
    return StaticToolSource(
        "agent-platform:public-research",
        _research_bindings(client, permission, contact_email),
    )


def _research_bindings(
    client: _PublicDataHttpClient,
    permission: str,
    contact_email: str | None,
) -> list[ToolBinding]:
    bindings = [
        ToolBinding(
            _wikipedia_definition(permission),
            _WikipediaExecutor(
                client,
                api_name="Wikipedia",
                endpoint="https://zh.wikipedia.org/w/api.php",
            ),
        ),
        ToolBinding(
            _open_library_definition(permission),
            _OpenLibraryExecutor(
                client,
                api_name="Open Library",
                endpoint="https://openlibrary.org/search.json",
            ),
        ),
        ToolBinding(
            _crossref_definition(permission),
            _CrossrefExecutor(
                client,
                api_name="Crossref",
                endpoint="https://api.crossref.org/works",
                contact_email=contact_email,
            ),
        ),
        ToolBinding(
            _arxiv_definition(permission),
            _ArxivExecutor(
                client,
                api_name="arXiv",
                endpoint="https://export.arxiv.org/api/query",
            ),
        ),
        ToolBinding(
            _hackernews_definition(permission),
            _HackerNewsExecutor(
                client,
                api_name="Hacker News Search",
                endpoint="https://hn.algolia.com/api/v1/search",
            ),
        ),
    ]
    return bindings


__all__ = ["public_research_tool_source"]
