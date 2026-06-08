#!/usr/bin/env python3
"""
LLM Summarizer — 自动化 LLM 摘要生成

通过 hermes CLI 调用 LLM 生成：
1. 文章摘要（ingest 时）
2. 综合回答（query 时）

不依赖外部 API key，使用 Hermes Agent 内置的 LLM。
"""

import subprocess
import re
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM 响应"""
    success: bool
    content: str
    error: str = ""
    tokens: int = 0


HERMES_CMD = os.path.expanduser("~/.local/bin/hermes")
# 备选路径
if not os.path.exists(HERMES_CMD):
    HERMES_CMD = os.path.expanduser("~/.hermes/venv/bin/hermes")
if not os.path.exists(HERMES_CMD):
    HERMES_CMD = "hermes"  # 最后尝试 PATH


def call_hermes(prompt: str, system_prompt: str = "", timeout: int = 120) -> LLMResponse:
    """
    通过 hermes CLI 调用 LLM
    
    使用 hermes chat -Q -q "prompt" 执行静默查询
    """
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    
    # 限制输入长度，避免超出 token 限制
    if len(full_prompt) > 50000:
        full_prompt = full_prompt[:50000] + "\n...(内容过长，已截断)"
    
    try:
        result = subprocess.run(
            [HERMES_CMD, "chat", "-Q", "-q", full_prompt],
            capture_output=True, text=True, timeout=timeout,
            cwd=Path.home()
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return LLMResponse(success=True, content=result.stdout.strip())
        else:
            return LLMResponse(
                success=False,
                content="",
                error=result.stderr[:500] or "无输出"
            )
    except subprocess.TimeoutExpired:
        return LLMResponse(success=False, content="", error="超时")
    except FileNotFoundError:
        return LLMResponse(success=False, content="", error=f"hermes CLI 未找到: {HERMES_CMD}")
    except Exception as e:
        return LLMResponse(success=False, content="", error=str(e)[:500])


# ──────────────────────────────────────────────
# 1. Ingest 摘要 — 文章 → entity/concept 页面
# ──────────────────────────────────────────────

INGEST_SUMMARY_PROMPT = """你是一个知识库维护助手。请将以下文章提炼为 wiki 实体/概念页面。

要求：
1. 标题：提取核心主题，简洁准确
2. 概述：3-5 句话概括核心内容
3. 要点：列出 3-8 个关键要点（每条 1-2 句）
4. 相关概念：列出 2-5 个相关的概念/实体（用 [[双括号]] 格式）
5. 保持客观、准确，不要添加原文没有的信息

只输出提炼后的内容，不要输出任何解释文字。"""


def summarize_for_entity(source_content: str, source_title: str) -> Optional[str]:
    """将原始文章提炼为 entity 页面内容"""
    system_prompt = "你是一个技术知识库编辑。你的任务是将原始资料提炼为结构化 wiki 页面。只输出页面内容，不输出其他文字。"
    
    prompt = f"""文章标题: {source_title}

原文内容:
{source_content}

请提炼为 entity/concept wiki 页面:"""
    
    response = call_hermes(prompt, system_prompt, timeout=180)
    
    if response.success:
        # 清理输出：去掉可能的 markdown 代码块包裹
        content = response.content
        if content.startswith('```'):
            content = re.sub(r'^```(?:markdown)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        return content
    return None


def summarize_for_concept(source_content: str, source_title: str) -> Optional[str]:
    """将原始文章提炼为 concept 页面内容"""
    system_prompt = "你是一个技术知识库编辑。你的任务是将原始资料提炼为结构化 wiki 页面。只输出页面内容，不输出其他文字。"
    
    prompt = f"""主题: {source_title}

原文内容:
{source_content}

请提炼为 concept wiki 页面:"""
    
    response = call_hermes(prompt, system_prompt, timeout=180)
    
    if response.success:
        content = response.content
        if content.startswith('```'):
            content = re.sub(r'^```(?:markdown)?\n', '', content)
            content = re.sub(r'\n```$', '', content)
        return content
    return None


def auto_ingest(wiki_path: str, source_path: str) -> Dict[str, Any]:
    """
    自动 ingest 流程（LLM 增强版）：
    1. 读原始文件
    2. LLM 提炼内容
    3. 创建/更新 wiki 页面
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from ingest import (
        WikiContext, WikiPage, read_file, write_file,
        extract_frontmatter, extract_body, extract_tags,
        extract_headings, extract_wikilinks, classify_source,
        find_relevant_pages, create_page, build_frontmatter,
        extract_key_concepts
    )
    
    wiki = WikiContext(Path(wiki_path))
    wiki.load_all()
    
    source_file = Path(source_path)
    content = source_file.read_text(encoding='utf-8')
    
    # 清理 frontmatter 只留正文
    body = extract_body(content)
    raw_frontmatter = extract_frontmatter(content)
    
    # 调用 LLM 提炼
    page_type = classify_source(body, source_file)
    title = source_file.stem.title().replace('-', ' ')
    
    summary = summarize_for_entity(body, title)
    if not summary:
        # LLM 失败，回退到原始内容
        summary = body
    
    # 提取标签和概念
    tags = raw_frontmatter.get('tags', []) or extract_tags(body)
    headings = extract_headings(body)
    concepts = extract_key_concepts(body)
    related = find_relevant_pages(concepts, wiki)
    wikilinks = [p.name.replace('.md', '') for p in related[:5]]
    
    # 创建页面
    created_path = create_page(wiki, page_type, title, tags, headings, summary, wikilinks)
    
    # 更新 index
    wiki.update_index()
    wiki.append_log('ingest', title, [str(created_path.relative_to(wiki.wiki_root.parent))])
    
    return {
        'page_type': page_type,
        'title': title,
        'path': str(created_path),
        'wikilinks': wikilinks,
        'llm_used': True,
    }


# ──────────────────────────────────────────────
# 2. Query 综合 — 搜索 → LLM 综合回答
# ──────────────────────────────────────────────

QUERY_SUMMARIZE_PROMPT = """你是一个知识库问答助手。根据以下 wiki 页面信息，综合生成一个准确的回答。

要求：
1. 直接回答问题，不要输出搜索过程
2. 引用来源：在关键论据后标注 [[页面标题]]
3. 如果多个页面有冲突信息，指出差异
4. 如果信息不足以回答，诚实说明
5. 保持结构清晰，使用列表/表格等格式"""


def synthesize_answer_from_pages(question: str, search_results: List[Dict]) -> Optional[str]:
    """
    综合多个 wiki 页面生成回答
    """
    if not search_results:
        return None
    
    # 构建上下文
    pages_context = ""
    for i, r in enumerate(search_results, 1):
        path = Path(r.get('path', ''))
        if path.exists():
            content = read_file(path) or ""
            body = extract_body(content)
            pages_context += f"\n--- 页面 {i}: {r['title']} ({r.get('path', '')}) ---\n{body[:3000]}\n"
    
    system_prompt = "你是一个技术知识库问答助手。根据提供的 wiki 页面内容回答问题。"
    
    prompt = f"""问题: {question}

以下是相关 wiki 页面内容:
{pages_context}

请综合这些页面内容，给出一个准确的回答。"""
    
    response = call_hermes(prompt, system_prompt, timeout=180)
    
    if response.success:
        return response.content
    return None


def enhanced_query(wiki_path: str, question: str) -> Dict[str, Any]:
    """增强版 wiki 查询 — LLM 综合回答"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from query import wiki_search, extract_body, read_file
    from ingest import WikiContext, read_file as rf, extract_body as eb
    wiki_context = WikiContext(Path(wiki_path))
    wiki_context.load_all()
    
    # 搜索
    search_result = wiki_search(question, wiki_context, top_k=5)
    
    # LLM 综合
    answer = None
    if search_result['results']:
        answer = synthesize_answer_from_pages(question, search_result['results'])
    
    result = {
        'query': question,
        'search': search_result,
        'llm_answer': answer,
    }
    
    return result


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python summarizer.py ingest <wiki_path> <source_path>")
        print("  python summarizer.py query <wiki_path> <question>")
        print("  python summarizer.py summarize <text> --type entity|concept")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'ingest':
        wiki_path = sys.argv[2]
        source_path = sys.argv[3] if len(sys.argv) > 3 else '.'
        result = auto_ingest(wiki_path, source_path)
        print(f"✅ {result['title']} ({result['page_type']})")
        print(f"   Path: {result['path']}")
        print(f"   Wikilinks: {result['wikilinks']}")
    
    elif cmd == 'query':
        wiki_path = sys.argv[2]
        question = ' '.join(sys.argv[3:])
        result = enhanced_query(wiki_path, question)
        print(f"🔍 {question}\n")
        for r in result['search']['results']:
            print(f"  [{r['title']}] ({r['type']}) score={r['rrf_score']}")
        if result['llm_answer']:
            print(f"\n### 综合回答\n\n{result['llm_answer']}")
    
    elif cmd == 'summarize':
        text = ' '.join(sys.argv[2:])
        stype = 'entity'
        if '--type' in sys.argv:
            idx = sys.argv.index('--type')
            stype = sys.argv[idx + 1]
        
        summary = summarize_for_entity(text, "Summary")
        print(summary or "LLM 调用失败")
    
    else:
        print(f"Unknown command: {cmd}")
