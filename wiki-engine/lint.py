#!/usr/bin/env python3
"""
LLM Wiki — Lint 流程
定期检查：断链 / 孤儿 / 过时 / 矛盾 / tag 规范 / 页面大小

参考：Karpathy LLM Wiki 模式
"""

from pathlib import Path
from typing import Any, Dict, List
from collections import defaultdict

try:
    from .ingest import (
        WikiContext, WikiPage, read_file, write_file,
        extract_wikilinks, FRONTMATTER_RE, extract_frontmatter
    )
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from ingest import (
        WikiContext, WikiPage, read_file, write_file,
        extract_wikilinks, FRONTMATTER_RE, extract_frontmatter
    )


# ──────────────────────────────────────────────
# 1. 断链检测
# ──────────────────────────────────────────────

def check_broken_links(wiki: WikiContext) -> List[Dict[str, Any]]:
    """检查所有断链"""
    broken = []
    page_titles = {p.title.lower() for p in wiki.pages.values()}

    for path, page in wiki.pages.items():
        for link in page.wikilinks:
            link_title = link.lower().lstrip('#')
            # 匹配方式 1: 精确标题匹配
            if link_title not in page_titles:
                # 尝试文件名匹配
                link_clean = link_title.replace('-', ' ').replace('_', ' ')
                found = False
                for other_title in page_titles:
                    if link_clean in other_title or other_title in link_clean:
                        found = True
                        break
                if not found:
                    broken.append({
                        'from': str(path.relative_to(wiki.wiki_root.parent)),
                        'link': link,
                        'reason': 'no_page',
                    })

    return broken


# ──────────────────────────────────────────────
# 2. 孤儿页面检测
# ──────────────────────────────────────────────

def check_orphan_pages(wiki: WikiContext) -> List[Dict[str, Any]]:
    """检查没有被其他页面引用的页面"""
    inbound = defaultdict(int)
    page_titles = {p.title.lower() for p in wiki.pages.values()}

    for path, page in wiki.pages.items():
        for link in page.wikilinks:
            link_title = link.lower().lstrip('#')
            for other_path, other_page in wiki.pages.items():
                if other_path == path:
                    continue
                if other_page.title.lower() == link_title or link_title in other_page.title.lower():
                    inbound[other_path] += 1

    orphans = []
    for path, page in wiki.pages.items():
        if inbound[path] == 0 and page.path != wiki.wiki_root / 'index.md':
            orphans.append({
                'path': str(path.relative_to(wiki.wiki_root.parent)),
                'title': page.title,
                'type': page.page_type,
            })

    return orphans


# ──────────────────────────────────────────────
# 3. 过时内容检测
# ──────────────────────────────────────────────

def check_stale_content(wiki: WikiContext, days_threshold: int = 90) -> List[Dict[str, Any]]:
    """检查超过阈值未更新的页面"""
    stale = []
    from datetime import datetime, timedelta

    now = datetime.now()

    for path, page in wiki.pages.items():
        if page.updated:
            try:
                updated_date = datetime.strptime(page.updated, '%Y-%m-%d')
                days_since = (now - updated_date).days
                if days_since > days_threshold:
                    stale.append({
                        'path': str(path.relative_to(wiki.wiki_root.parent)),
                        'title': page.title,
                        'days_since_updated': days_since,
                    })
            except ValueError:
                pass

    return stale


# ──────────────────────────────────────────────
# 4. 页面大小检测
# ──────────────────────────────────────────────

def check_page_sizes(wiki: WikiContext, max_lines: int = 200) -> List[Dict[str, Any]]:
    """检查过大的页面"""
    large = []

    for path, page in wiki.pages.items():
        lines = page.body.count('\n') + 1
        if lines > max_lines:
            large.append({
                'path': str(path.relative_to(wiki.wiki_root.parent)),
                'title': page.title,
                'lines': lines,
            })

    return large


# ──────────────────────────────────────────────
# 5. 完整 Lint 报告
# ──────────────────────────────────────────────

def lint(wiki_path: str, strict: bool = False) -> Dict[str, Any]:
    """执行完整 lint 审计"""
    wiki = WikiContext(Path(wiki_path))
    wiki.load_all()

    report = {
        'total_pages': len(wiki.pages),
        'broken_links': check_broken_links(wiki),
        'orphan_pages': check_orphan_pages(wiki),
        'stale_content': check_stale_content(wiki),
        'large_pages': check_page_sizes(wiki),
    }

    # 统计
    report['severity'] = {
        'critical': len(report['broken_links']),  # 断链是致命错误
        'warning': len(report['orphan_pages']) + len(report['stale_content']),
        'info': len(report['large_pages']),
    }

    report['summary'] = (
        f"共 {report['total_pages']} 个页面\n"
        f"🔴 断链: {len(report['broken_links'])}\n"
        f"🟡 孤儿: {len(report['orphan_pages'])}\n"
        f"🟡 过时: {len(report['stale_content'])}\n"
        f"🔵 过大: {len(report['large_pages'])}"
    )

    return report


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    wiki_path = sys.argv[1] if len(sys.argv) > 1 else '.'
    report = lint(wiki_path)
    print(report['summary'])
    if report['broken_links']:
        print(f"\n断链页面 ({len(report['broken_links'])}):\n")
        for bl in report['broken_links']:
            print(f"  {bl['from']} → [[{bl['link']}]] (原因: {bl['reason']})")
    if report['orphan_pages']:
        print(f"\n孤儿页面 ({len(report['orphan_pages'])}):\n")
        for op in report['orphan_pages']:
            print(f"  {op['path']} — {op['title']} ({op['type']})")
    if report['stale_content']:
        print(f"\n过时内容 ({len(report['stale_content'])}):\n")
        for sc in report['stale_content']:
            print(f"  {sc['path']} — {sc['title']} (已 {sc['days_since_updated']} 天未更新)")
    if report['large_pages']:
        print(f"\n过大页面 ({len(report['large_pages'])}):\n")
        for lp in report['large_pages']:
            print(f"  {lp['path']} — {lp['title']} ({lp['lines']} 行)")
