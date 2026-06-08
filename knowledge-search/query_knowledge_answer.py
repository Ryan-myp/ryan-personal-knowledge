#!/usr/bin/env python3
"""
知识库搜索引擎 — 带 LLM 综合回答的版本

增强版 query_knowledge.py：
1. 先搜索知识库 → 找到相关文档
2. 如果找到结果 → 用 LLM 综合生成带图示的回答
3. 如果没有结果 → 返回原始搜索结果列表

用法:
    python3 query_knowledge_answer.py "Kafka Rebalance 流程"
    python3 query_knowledge_answer.py "讲下 Redis 的持久化机制"
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ──────────────────────────────────────────────
# 导入原始搜索模块（复用所有搜索逻辑）
# ──────────────────────────────────────────────
KB_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(KB_ROOT / "knowledge-search"))

from query_knowledge import (
    build_index,
    run_pipeline_enhanced,
    run_pipeline,
    load_config,
    QueryCache,
    format_result,
    extract_intent,
    get_scope_weights,
    extract_wikilinks,
)


# ──────────────────────────────────────────────
# LLM 调用（通过 hermes CLI）
# ──────────────────────────────────────────────

def call_llm(prompt: str, max_tokens: int = 4000) -> Optional[str]:
    """通过 hermes CLI 调用 LLM 生成综合回答"""
    system_prompt = """你是一个技术知识助手。你的任务是根据用户提供的搜索结果（来自知识库的文档片段），生成一份清晰、深入、图文并茂的技术解答。

要求：
1. 结构清晰：分章节讲解，先概念后细节
2. 图文结合：适当使用 ASCII 图示、表格、代码块帮助理解
3. 深度足够：一次性给到有基础的人能看懂的粒度
4. 如果有相关概念，用 [[wikilink]] 格式标注
5. 使用中文回答，技术术语保留英文
6. 如果知识库内容不足以回答，诚实地说明局限性

只输出回答内容，不要加"根据搜索结果"之类的套话。"""

    try:
        result = subprocess.run(
            ["hermes", "chat", "-q", prompt, "--max-turns", "1", "--toolsets", "file", "-Q"],
            capture_output=True, text=True,
            timeout=180,
            cwd=str(KB_ROOT),
            env={**dict(__import__('os').environ), 'HERMES_SYSTEM_PROMPT': system_prompt},
        )
        # 解析输出：hermes -Q 模式只返回最终回答 + session info
        # 回答在 ╭─ ⚕ Hermes ─────────── 和 ╰──────────────────────╯ 之间
        output = result.stdout
        # 尝试从 hermes 输出框中提取回答
        start = output.find("╭─")
        end = output.rfind("╰")
        if start != -1 and end != -1 and end > start:
            # 提取框内的内容
            box_content = output[start:end]
            # 去除框线和分隔符
            lines = box_content.split('\n')
            answer_lines = []
            for line in lines:
                clean = line.replace('│', '').strip()
                if clean and clean != '─' * len(clean):
                    answer_lines.append(clean)
            answer = '\n'.join(answer_lines).strip()
            if answer:
                return answer

        # 降级：如果没有找到框，尝试直接返回 stdout
        if output.strip():
            # 去掉 banner 和 session info
            lines = output.strip().split('\n')
            # 过滤掉特殊行
            clean_lines = [l for l in lines if l.strip() and '──' not in l and '⚕' not in l and '╭' not in l and '╰' not in l and 'Iteration' not in l and 'Resume' not in l and 'Session:' not in l and 'Duration:' not in l and 'Messages:' not in l]
            answer = '\n'.join(clean_lines).strip()
            if answer:
                return answer

        print(f"  [WARN] LLM 返回空输出", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print("  [WARN] LLM 调用超时", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("  [WARN] hermes CLI 未找到，跳过 LLM 回答", file=sys.stderr)
        return None


def generate_answer(query: str, search_results: List[Dict], search_intent: str, search_confidence: float) -> Optional[str]:
    """基于搜索结果生成 LLM 综合回答"""
    if not search_results:
        return None

    # 提取文档内容（限制总长度，避免 prompt 太长）
    context_parts = []
    total_chars = 0
    MAX_CHARS = 12000  # 留给 LLM 的最大上下文

    for i, doc in enumerate(search_results[:5], 1):  # 最多取 Top 5
        content = doc.get("full_content", "")
        file_path = doc.get("file_path", "")
        tags = " ".join(doc.get("tags", []))

        # 截断到合理长度
        if len(content) > 3000:
            content = content[:3000] + "\n...[内容截断]"

        context_parts.append(
            f"--- 文档 {i}: {doc.get('file_name', '')} ---\n"
            f"标签: {tags}\n"
            f"内容:\n{content}"
        )

        total_chars += len(content)
        if total_chars >= MAX_CHARS:
            break

    context = "\n\n".join(context_parts)

    prompt = f"""以下是从知识库中搜索到的相关文档：

查询: "{query}"
搜索意图: {search_intent}
置信度: {search_confidence:.3f}
找到 {len(search_results)} 个匹配文档

=== 相关知识内容 ===

{context}

请基于以上内容，生成一份关于 "{query}" 的详细技术解答。要求：
1. 综合所有文档的内容，给出结构化的解答
2. 适当使用 ASCII 图示、表格帮助理解
3. 深度足够，面向有技术基础的人
4. 如果有相关概念，用 [[wikilink]] 格式标注
5. 只使用上面提供的知识，不要编造
6. 中文回答，技术术语保留英文"""

    return call_llm(prompt, max_tokens=4000)


# ──────────────────────────────────────────────
# 核心流程
# ──────────────────────────────────────────────

def search_and_answer(query: str, kb_root: Path, config: dict, cache: QueryCache, use_wiki: bool = False) -> Dict[str, Any]:
    """搜索 + LLM 回答一体化流程"""

    # Step 1: 构建索引
    print("📦 正在构建知识库索引...")
    docs = build_index(kb_root)
    print(f"   索引了 {len(docs)} 个 Markdown 文件")

    all_tags = set()
    for doc in docs:
        all_tags.update(doc.get("tags", []))
    print(f"📖 知识库统计: {len(docs)} 文件, {len(all_tags)} 标签")

    # Step 2: 执行搜索
    print(f"\n🔍 正在搜索: \"{query}\"")

    has_wiki_structure = any(
        re.search(r'^---\n.*type:\s*(entity|concept)', doc["full_content"], re.DOTALL)
        for doc in docs
    )
    has_wikilinks = any(extract_wikilinks(doc.get("full_content", "")) for doc in docs)

    if has_wiki_structure or has_wikilinks or use_wiki:
        print(f"  🔗 LLM Wiki 模式: wikilinks={has_wikilinks}, entities={has_wiki_structure}")
        result = run_pipeline_enhanced(query, docs, config, cache)
    else:
        result = run_pipeline(query, docs, config, cache)

    # Step 3: 输出搜索结果列表
    print(format_result(result))

    # Step 4: 生成 LLM 综合回答
    intent = result.get("intent", "unknown")
    confidence = result.get("confidence", 0.0)
    top_results = result.get("results", [])

    if top_results:
        print("🤖 正在生成综合回答...")
        answer = generate_answer(query, top_results, intent, confidence)

        if answer:
            print("\n" + "=" * 60)
            print("📝 综合回答")
            print("=" * 60)
            print(answer)
            print("=" * 60)
        else:
            print("\n⚠️ LLM 未能生成综合回答，以上为搜索结果列表。")
    else:
        print("\n😔 未找到相关结果，无法生成回答。")

    return result


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="知识库搜索 + LLM 综合回答")
    parser.add_argument("query", help="搜索查询语句")
    parser.add_argument("--profile", default=None, help="配置文件路径")
    parser.add_argument("--clear-cache", action="store_true", help="清除缓存")
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    parser.add_argument("--wiki", action="store_true", help="强制启用 LLM Wiki 增强模式")

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    kb_root = script_dir.parent  # ryan-personal-knowledge

    # 加载配置
    if args.profile:
        config = load_config(Path(args.profile))
    else:
        default_profile = script_dir / "profiles" / "knowledge-search.json"
        config = load_config(default_profile)

    # 初始化缓存
    cache_dir = script_dir / ".cache"
    cache_dir.mkdir(exist_ok=True)
    cache = QueryCache(cache_dir, ttl_seconds=config.get("cache", {}).get("ttl_seconds", 3600))

    # 清除缓存
    if args.clear_cache:
        for f in cache_dir.glob("*.json"):
            f.unlink()
        print("✅ 缓存已清除")
        return

    # 执行搜索 + 回答
    search_and_answer(args.query, kb_root, config, cache, use_wiki=args.wiki)


if __name__ == "__main__":
    main()
