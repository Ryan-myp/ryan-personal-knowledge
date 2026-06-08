"""LLM Wiki 引擎 — 编译式知识管理系统"""

from .ingest import ingest, WikiContext, WikiPage
from .query import query, wiki_search, archive_query_result
from .lint import lint

__all__ = ['ingest', 'query', 'wiki_search', 'archive_query_result', 'lint', 'WikiContext', 'WikiPage']
