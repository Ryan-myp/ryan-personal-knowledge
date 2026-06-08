#!/usr/bin/env python3
"""
LLM Wiki — Ingest 流程
新源摄入 → 提取实体/概念 → 更新/创建页面 → 维护 wikilinks → 更新 index.md + log.md

参考：Karpathy LLM Wiki 模式
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
"""

import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field


# ──────────────────────────────────────────────
# 1. 文件操作工具
# ──────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
TAG_RE = re.compile(r'#([\w\u4e00-\u9fff][\w\u4e00-\u9fff_-]*)')


def read_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def read_frontmatter(content: str) -> Dict[str, Any]:
    """从 markdown 提取 frontmatter"""
    m = FRONTMATTER_RE.search(content)
    if not m:
        return {}
    try:
        fm = json.loads(m.group(1))
        fm.pop('type', None)  # type 不在 fm 里返回
        return fm
    except json.JSONDecodeError:
        return {}


def extract_frontmatter(content: str) -> Dict[str, Any]:
    """提取完整 frontmatter（含 type）"""
    m = FRONTMATTER_RE.search(content)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def build_frontmatter(data: Dict[str, Any]) -> str:
    """构建 frontmatter 字符串"""
    lines = ['---']
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f'{k}: [{", ".join(v)}]')
        else:
            lines.append(f'{k}: {v}')
    lines.append('---')
    return '\n'.join(lines)


def extract_body(content: str) -> str:
    """提取 frontmatter 之后的正文"""
    m = FRONTMATTER_RE.search(content)
    if m:
        return content[m.end():].lstrip('\n')
    return content


def extract_headings(content: str) -> List[str]:
    return re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)


def extract_wikilinks(content: str) -> List[str]:
    """提取 [[wikilink]]"""
    return [l for l in WIKILINK_RE.findall(content) if not l.startswith('#') and not l.startswith('!')]


def extract_tags(content: str) -> List[str]:
    """提取 #tag"""
    return list(set(TAG_RE.findall(content)))


# ──────────────────────────────────────────────
# 2. Wiki 索引结构
# ──────────────────────────────────────────────

@dataclass
class WikiPage:
    """Wiki 页面"""
    path: Path
    title: str
    page_type: str  # entity | concept | comparison | query | summary
    tags: List[str]
    headings: List[str]
    wikilinks: List[str]
    content: str
    body: str
    created: str = ""
    updated: str = ""

    @classmethod
    def from_file(cls, path: Path) -> Optional['WikiPage']:
        content = read_file(path)
        if not content:
            return None
        fm = extract_frontmatter(content)
        body = extract_body(content)
        return cls(
            path=path,
            title=fm.get('title', path.stem),
            page_type=fm.get('type', 'summary'),
            tags=fm.get('tags', extract_tags(content)),
            headings=extract_headings(content),
            wikilinks=extract_wikilinks(content),
            content=content,
            body=body,
            created=fm.get('created', ''),
            updated=fm.get('updated', ''),
        )


@dataclass
class WikiContext:
    """Wiki 上下文 — 所有页面的索引"""
    wiki_root: Path
    pages: Dict[Path, WikiPage] = field(default_factory=dict)
    log_entries: List[str] = field(default_factory=list)

    def load_all(self):
        """加载所有 wiki 页面"""
        for subdir in ['entities', 'concepts', 'queries', 'comparisons']:
            dir_path = self.wiki_root / subdir
            if dir_path.exists():
                for md_file in dir_path.glob('*.md'):
                    page = WikiPage.from_file(md_file)
                    if page:
                        self.pages[md_file] = page

    def get_all_titles(self) -> Set[str]:
        return {p.title.lower() for p in self.pages.values()}

    def get_entities(self) -> Dict[Path, WikiPage]:
        return {p: page for p, page in self.pages.items() if page.page_type == 'entity'}

    def get_concepts(self) -> Dict[Path, WikiPage]:
        return {p: page for p, page in self.pages.items() if page.page_type == 'concept'}

    def get_pages_by_tag(self, tag: str) -> List[Path]:
        return [p for p, pg in self.pages.items() if tag in pg.tags]

    def update_index(self):
        """重建 index.md"""
        lines = ['# Wiki Index\n']
        lines.append(f'> Last updated: {self.log_entries[-1][:10] if self.log_entries else "N/A"}\n')

        sections = {
            'Entities': [],
            'Concepts': [],
            'Comparisons': [],
            'Queries': [],
        }

        for path, page in sorted(self.pages.items()):
            entry = f'- [[{page.title}]] — {page.headings[0] if page.headings else page.title}'
            if page.page_type in sections:
                sections[page.page_type].append(entry)

        for section_name, entries in sections.items():
            if entries:
                lines.append(f'\n## {section_name}\n')
                lines.extend(sorted(entries))

        index_path = self.wiki_root / 'index.md'
        write_file(index_path, '\n'.join(lines))

    def append_log(self, action: str, subject: str, files_changed: List[str] = None):
        """追加操作日志"""
        date = self.log_entries[-1][:10] if self.log_entries else "N/A"
        entry = f'## [{date}] {action} | {subject}'
        if files_changed:
            entry += f'\n- Files: {", ".join(files_changed)}'
        self.log_entries.append(entry)

        log_path = self.wiki_root / 'log.md'
        log_content = read_file(log_path) or '# Wiki Log\n\n'
        write_file(log_path, log_content + '\n' + entry + '\n')


# ──────────────────────────────────────────────
# 3. Ingest 流程
# ──────────────────────────────────────────────

def classify_source(source_content: str, source_path: Path) -> str:
    """判断新源属于哪个类别"""
    content_lower = source_content.lower()
    source_name = source_path.name.lower()

    # 简单启发式分类
    entity_keywords = ['person', 'product', 'service', 'tool', 'platform', 'api', '公司', '产品', '服务', '工具']
    concept_keywords = ['concept', 'method', 'pattern', '架构', '原理', '模式', '概念', '方法']

    for kw in entity_keywords:
        if kw in content_lower or kw in source_name:
            return 'entity'

    for kw in concept_keywords:
        if kw in content_lower:
            return 'concept'

    return 'concept'  # 默认


def extract_key_concepts(source_content: str) -> List[str]:
    """从内容中提取关键概念（用于 wikilinks）"""
    tags = extract_tags(source_content)
    headings = extract_headings(source_content)

    concepts = set()
    for h in headings[:10]:  # 前 10 个 heading
        if len(h) > 2 and len(h) < 50:
            concepts.add(h.strip())

    for tag in tags:
        concepts.add(tag)

    return list(concepts)


def find_relevant_pages(concepts: List[str], wiki: WikiContext) -> List[Path]:
    """找到最相关的现有页面（用于建立 wikilinks）"""
    scored = []
    titles = wiki.get_all_titles()

    for concept in concepts:
        concept_lower = concept.lower()
        for path, page in wiki.pages.items():
            page_text = f"{page.title} {' '.join(page.tags)} {' '.join(page.headings)}".lower()
            if concept_lower in page_text or any(cw in page_text for cw in concept_lower.split() if len(cw) > 2):
                scored.append((path, 1.0))
            elif any(page.title.lower().startswith(cw) for cw in concept_lower.split() if len(cw) > 2):
                scored.append((path, 0.5))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:5]]


def create_page(wiki: WikiContext, page_type: str, title: str, tags: List[str],
                headings: List[str], body: str, wikilinks: List[str], existing_path: Path = None) -> Path:
    """创建或更新页面"""
    today = wiki.log_entries[-1][:10] if wiki.log_entries else "N/A"

    if existing_path:
        # 更新现有页面 — 追加内容
        content = read_file(existing_path) or ''
        fm = extract_frontmatter(content)
        if not fm.get('title'):
            fm['title'] = title
        fm['tags'] = list(set(fm.get('tags', []) + tags))
        fm['updated'] = today

        existing_links = extract_wikilinks(content)
        all_links = list(dict.fromkeys(existing_links + wikilinks))

        body_clean = extract_body(body) if body.startswith('---\n') else body

        # 追加 wikilinks
        link_content = '\n\n'.join(f'- [[{l}]]' for l in all_links[:5])
        new_body = body_clean.rstrip() + ('\n\n### 相关页面\n' + link_content if all_links else '')

        new_content = build_frontmatter(fm) + '\n\n' + new_body
        write_file(existing_path, new_content)
        return existing_path
    else:
        # 创建新页面
        fm = {
            'title': title,
            'created': today,
            'updated': today,
            'type': page_type,
            'tags': tags if tags else ['默认'],
        }

        # 清理正文中的双重 frontmatter
        body_clean = extract_body(body) if body.startswith('---\n') else body

        # 自动添加 wikilinks
        link_content = '\n\n'.join(f'- [[{l}]]' for l in wikilinks[:5])
        if link_content:
            body_clean = body_clean.rstrip() + '\n\n### 相关页面\n' + link_content

        content = build_frontmatter(fm) + '\n\n' + body_clean
        subdir = {'entity': 'entities', 'concept': 'concepts', 'comparison': 'comparisons',
                  'query': 'queries', 'summary': ''}.get(page_type, 'concepts')
        safe_title = title.lower().replace(' ', '-').replace('/', '-').replace('（', '(').replace('）', ')')
        path = wiki.wiki_root / subdir / f'{safe_title}.md'
        write_file(path, content)
        return path


def ingest(wiki_path: str, source_path: str, force: bool = False) -> Dict[str, Any]:
    """
    执行 ingest 流程：
    1. 读新源
    2. 提取概念
    3. 找到相关页面
    4. 创建/更新页面 + wikilinks
    5. 更新 index.md + log.md
    """
    wiki = WikiContext(Path(wiki_path))
    wiki.load_all()

    source_file = Path(source_path)
    content = source_file.read_text(encoding='utf-8')

    page_type = classify_source(content, source_file)
    concepts = extract_key_concepts(content)
    tags = extract_tags(content)
    headings = extract_headings(content)
    related_pages = find_relevant_pages(concepts, wiki)

    # 创建或更新页面
    existing_path = None
    if related_pages:
        # 尝试匹配已有页面
        for rp in related_pages:
            pg = wiki.pages.get(rp)
            if pg and pg.page_type == page_type:
                existing_path = rp
                break

    wikilinks = [p.name.replace('.md', '') for p in related_pages[:5]]
    page_title = source_file.stem.title().replace('-', ' ')

    created_path = create_page(wiki, page_type, page_title, tags, headings, content, wikilinks, existing_path)

    # 更新 index
    wiki.update_index()
    wiki.append_log('ingest', page_title, [str(created_path.relative_to(wiki.wiki_root.parent))])

    result = {
        'page_type': page_type,
        'title': page_title,
        'path': str(created_path),
        'wikilinks_added': wikilinks,
        'related_pages': [str(p.relative_to(wiki.wiki_root.parent)) for p in related_pages],
    }

    print(f"✅ Ingested: {page_title} ({page_type})")
    print(f"   Path: {created_path}")
    print(f"   Wikilinks: {wikilinks}")

    return result


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python ingest.py <wiki_path> <source_path> [--force]")
        sys.exit(1)

    wiki_path = sys.argv[1]
    source_path = sys.argv[2]
    force = '--force' in sys.argv

    ingest(wiki_path, source_path, force)
