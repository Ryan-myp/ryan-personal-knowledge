#!/usr/bin/env python3
"""
Ryan 个人知识库搜索引擎 — thin wrapper over biz-delivery

复用 biz-delivery 框架的核心能力：
- scripts.smart_routing 的意图识别逻辑
- scripts.rrf_fusion 的多维度融合（文件内容、文件名、标签、目录路径）
- scripts.query_cache 的查询缓存

用法:
    python3 query_knowledge.py "我想看 Redis 相关的书"
    python3 query_knowledge.py "怎么集成 agentmemory"
    python3 query_knowledge.py "对比 agentmemory 的三种方案"
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────
# Import biz-delivery core modules
# ──────────────────────────────────────────────

_BD_SCRIPTS = Path.home() / "biz-delivery" / "scripts"
if str(_BD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_BD_SCRIPTS.parent))

from scripts.smart_routing import extract_intent, INTENT_PATTERNS
from scripts.query_cache import QueryCache
from scripts.rrf_fusion import rrf_ranks

# ──────────────────────────────────────────────
# Knowledge-search specific: KB index & search
# ──────────────────────────────────────────────

TAG_PATTERN = re.compile(r'#[-\w\u4e00-\u9fff]+')
HEADING_PATTERN = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)
WIKILINK_PATTERN = re.compile(r'\[\[([^\]]+)\]\]')
WIKI_ENTITIES = {"entity", "concept", "comparison", "query", "summary", "article"}
ENTRIES_PENALTY = 0.7
DEFAULT_SCOPE_WEIGHTS = {
    "file_content": 0.8, "file_name": 0.5,
    "tags": 0.6, "directory_path": 0.5,
}

# Intent → scope weight overrides (knowledge-search specific)
INTENT_TO_SCOPE_WEIGHTS = {
    "query":       {"file_content": 0.8, "file_name": 0.5, "tags": 0.7, "directory_path": 0.6},
    "question":    {"file_content": 0.8, "file_name": 0.4, "tags": 0.6, "directory_path": 0.5},
    "explain":     {"file_content": 0.9, "file_name": 0.3, "tags": 0.7, "directory_path": 0.5},
    "compare":     {"file_content": 0.7, "file_name": 0.5, "tags": 0.8, "directory_path": 0.6},
    "debug":       {"file_content": 0.9, "file_name": 0.4, "tags": 0.8, "directory_path": 0.5},
    "create":      {"file_content": 0.7, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5},
    "update":      {"file_content": 0.7, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5},
    "optimize":    {"file_content": 0.8, "file_name": 0.4, "tags": 0.7, "directory_path": 0.5},
    "review":      {"file_content": 0.7, "file_name": 0.5, "tags": 0.7, "directory_path": 0.5},
    "migrate":     {"file_content": 0.7, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5},
}


def get_scope_weights(intent: str) -> Dict[str, float]:
    """获取意图对应的多维度权重"""
    return INTENT_TO_SCOPE_WEIGHTS.get(intent, DEFAULT_SCOPE_WEIGHTS)


# ──────────────────────────────────────────────
# KB Indexing
# ──────────────────────────────────────────────

def extract_keywords(md_content: str, file_path: Path) -> Dict[str, Any]:
    """提取文件的结构化信息"""
    frontmatter_tags = []
    fm_match = re.search(r'^---\n(.*?)\n---', md_content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        fm_tags = re.findall(r'tags?\s*:\s*(.+)', fm_text, re.IGNORECASE)
        for tag_line in fm_tags:
            frontmatter_tags.extend(TAG_PATTERN.findall(tag_line))

    body_tags = TAG_PATTERN.findall(md_content)
    all_tags = list(dict.fromkeys(frontmatter_tags + body_tags))
    headings = HEADING_PATTERN.findall(md_content)
    directory = file_path.parent.name
    parent_dir = file_path.parent.parent.name if file_path.parent.parent.name != file_path.parent.name else ""
    is_entry = file_path.name in {"SKILL.md", "README.md"}

    return {
        "file_path": str(file_path),
        "file_name": file_path.name,
        "directory": directory,
        "parent_dir": parent_dir,
        "tags": all_tags,
        "headings": headings,
        "content_preview": md_content[:500],
        "full_content": md_content,
        "word_count": len(md_content.split()),
        "is_entry_file": is_entry,
        "wikilinks": [],
        "frontmatter_type": "",
        "created": "",
    }


def build_index(kb_root: Path) -> List[Dict]:
    """扫描所有 .md 文件，构建知识库索引"""
    docs = []
    exclude_dirs = {"knowledge-search", ".git"}

    for md_file in sorted(kb_root.rglob("*.md")):
        rel = md_file.relative_to(kb_root)
        parts = rel.parts
        if any(p in exclude_dirs for p in parts):
            continue
        if "ryan-personal-knowledge" in parts and parts.index("ryan-personal-knowledge") > 0:
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
            doc = extract_keywords(content, md_file)
            if doc["word_count"] > 0:
                docs.append(doc)
        except Exception as e:
            print(f"  [WARN] 跳过 {md_file}: {e}")

    return docs


# ──────────────────────────────────────────────
# Multi-path search (knowledge-search specific)
# ──────────────────────────────────────────────

def search_file_content(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """按文件内容搜索"""
    query_terms = set(re.findall(r'[\w\u4e00-\u9fff]+', query.lower()))
    if not query_terms:
        return []

    scored = []
    for doc in docs:
        content_lower = doc["full_content"].lower()
        matched = sum(1 for term in query_terms if term in content_lower)
        if matched > 0:
            tf = matched / len(query_terms)
            length_factor = min(1.0, 2000 / max(doc.get("word_count", 1), 1))
            score = tf * length_factor
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def search_file_name(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """按文件名/标题搜索"""
    query_lower = query.lower()
    scored = []
    for doc in docs:
        text_to_check = doc["file_name"].lower()
        for h in doc.get("headings", []):
            text_to_check += " " + h.lower()

        if query_lower in text_to_check:
            score = 1.0
        else:
            query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))
            text_words = set(re.findall(r'[\w\u4e00-\u9fff]+', text_to_check))
            if query_words and text_words:
                overlap = len(query_words & text_words)
                score = overlap / len(query_words)
            else:
                continue

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def search_tags(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """按标签搜索"""
    query_lower = query.lower()
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))
    if not query_words:
        return []

    scored = []
    for doc in docs:
        tags = [t.lower().lstrip('#') for t in doc.get("tags", [])]
        matched_tags = set()
        for tag in tags:
            for qw in query_words:
                if qw in tag or tag in qw:
                    matched_tags.add(tag)

        if matched_tags:
            score = len(matched_tags) / len(query_words)
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def search_directory(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """按目录路径搜索"""
    query_lower = query.lower()
    scored = []
    for doc in docs:
        text_to_check = f"{doc['directory']} {doc['parent_dir']}".lower()
        if query_lower in text_to_check:
            score = 1.0
        else:
            query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))
            text_words = set(re.findall(r'[\w\u4e00-\u9fff]+', text_to_check))
            if query_words and text_words:
                overlap = len(query_words & text_words)
                score = overlap / max(len(query_words), 1)
            else:
                continue

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


# ──────────────────────────────────────────────
# LLM Wiki enhanced search
# ──────────────────────────────────────────────

def extract_wikilinks(content: str) -> List[str]:
    """提取文件中的 [[wikilink]] 语法"""
    links = WIKILINK_PATTERN.findall(content)
    return [l for l in links if not l.startswith('#') and not l.startswith('!')]


def extract_frontmatter_type(frontmatter: Dict) -> Optional[str]:
    """从 frontmatter 提取页面类型"""
    return frontmatter.get("type", "").lower()


def search_wikilinks(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """[[wikilinks]] 搜索 — 通过链接关系找到相关页面"""
    query_lower = query.lower()
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))
    if not query_words:
        return []

    scored = []
    for doc in docs:
        wikilinks = doc.get("wikilinks", [])
        if not wikilinks:
            continue

        matched_links = set()
        for link in wikilinks:
            link_clean = link.lower().lstrip('#')
            for qw in query_words:
                if qw in link_clean or link_clean in qw:
                    matched_links.add(link)

        if matched_links:
            score = len(matched_links) / len(query_words) * 1.5
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def search_entity_pages(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """Entity 页面优先 — frontmatter type=entity/concept 的页面排前面"""
    query_lower = query.lower()
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))
    if not query_words:
        return []

    scored = []
    for doc in docs:
        page_type = doc.get("frontmatter_type", "")
        if page_type in ("entity", "concept"):
            content = doc.get("full_content", "").lower()
            headings = " ".join(doc.get("headings", [])).lower()
            search_text = content + " " + headings
            word_hits = sum(1 for w in query_words if w in search_text)
            if word_hits > 0:
                base_score = word_hits / len(query_words) * 1.3
                scored.append((base_score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def search_cross_reference(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """Cross-reference 搜索 — 通过 wikilinks 找到被其他相关页面引用的页面"""
    seed_docs = search_file_content(query, docs, top_k=5)
    if not seed_docs:
        return []

    seed_links = set()
    for doc in seed_docs:
        seed_links.update(doc.get("wikilinks", []))

    scored = []
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query.lower()))

    seed_titles = set(d["file_name"].lower().replace(".md", "") for d in seed_docs)
    for doc in docs:
        if doc["file_path"] in [d["file_path"] for d in seed_docs]:
            continue

        doc_links = doc.get("wikilinks", [])
        cross_hits = 0
        for link in doc_links:
            link_clean = link.lower().replace("knowledge/", "").replace("/", "-").lstrip('#')
            for seed_title in seed_titles:
                if seed_title in link_clean or link_clean in seed_title:
                    cross_hits += 1

        if cross_hits > 0:
            score = cross_hits / len(query_words) * 0.8
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def extract_wikilinks_and_frontmatter(docs: List[Dict]) -> List[Dict]:
    """增强文档索引：提取 wikilinks 和 frontmatter 类型"""
    FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)

    for doc in docs:
        content = doc["full_content"]
        doc["wikilinks"] = extract_wikilinks(content)

        fm_match = FRONTMATTER_RE.search(content)
        fm_content = fm_match.group(1) if fm_match else ""
        try:
            fm = json.loads(fm_content)
            doc["frontmatter_type"] = extract_frontmatter_type(fm)
            fm_tags = fm.get("tags", [])
            if fm_tags:
                existing_tags = set(doc.get("tags", []))
                doc["tags"] = list(existing_tags | set(fm_tags))
        except json.JSONDecodeError:
            doc["frontmatter_type"] = ""

    return docs


# ──────────────────────────────────────────────
# Search pipeline
# ──────────────────────────────────────────────

def _run_pipeline(query: str, docs: List[Dict], config: dict, cache: QueryCache,
                   enhanced: bool = False) -> Dict[str, Any]:
    """通用搜索管线"""
    intent, confidence = extract_intent(query)
    scope_weights = get_scope_weights(intent)

    # 查询类型映射
    query_type_map = {
        "file_content": search_file_content,
        "file_name": search_file_name,
        "tags": search_tags,
        "directory_path": search_directory,
        "wikilinks": search_wikilinks,
        "entity_pages": search_entity_pages,
        "cross_reference": search_cross_reference,
    }

    top_k = config["fusion"]["top_k"]

    # 构建路径列表
    paths_to_use = list(config["fusion"]["paths"])
    if enhanced:
        has_wikilinks_any = any(doc.get("wikilinks") for doc in docs)
        has_entity_pages = any(doc.get("frontmatter_type") in WIKI_ENTITIES for doc in docs)
        if has_wikilinks_any:
            paths_to_use.append({"name": "wikilinks", "weight": 0.1})
            paths_to_use.append({"name": "cross_reference", "weight": 0.08})
        if has_entity_pages:
            paths_to_use.append({"name": "entity_pages", "weight": 0.15})

    # 执行多路查询 + RRF 融合
    candidates = []
    source_metadata = []
    path_weights = []
    path_results_cache = {}

    for path_cfg in paths_to_use:
        path_name = path_cfg["name"]
        weight = path_cfg.get("weight", 1.0)
        intent_w = scope_weights.get(path_name, 0.5)
        effective_weight = weight * intent_w * (0.5 + 0.5 * confidence)

        search_fn = query_type_map.get(path_name)
        if search_fn:
            results = search_fn(query, docs, top_k)
            candidates.append(results)
            source_metadata.append({
                "path": path_name,
                "weight": round(effective_weight, 3),
                "count": len(results),
            })
            path_weights.append(effective_weight)
            path_results_cache[path_name] = results

    # RRF 融合
    fused = rrf_ranks(candidates, k=config["fusion"]["rrf_k"]) if candidates else []

    # 计算最终得分
    results = []
    for doc in fused:
        total_score = 0.0
        source_scores = []
        for i, path_cfg in enumerate(paths_to_use):
            path_name = path_cfg["name"]
            weight = path_cfg.get("weight", 1.0) * scope_weights.get(path_name, 0.5) * (0.5 + 0.5 * confidence)

            if path_name in path_results_cache:
                path_results = path_results_cache[path_name]
                for j, r in enumerate(path_results):
                    if r["file_path"] == doc["file_path"]:
                        rrf_contrib = weight * (1.0 / (60 + j + 1))
                        total_score += rrf_contrib
                        source_scores.append((path_name, round(rrf_contrib, 6)))
                        break

        results.append({
            **doc,
            "rrf_score": round(total_score, 6),
            "source_scores": source_scores,
            "intent": intent,
            "confidence": round(confidence, 3),
        })

    # 入口文件惩罚
    for r in results:
        if r.get("is_entry_file", False):
            r["rrf_score"] *= ENTRIES_PENALTY
            r["source_scores"] = [(k, round(v * ENTRIES_PENALTY, 6)) for k, v in r["source_scores"]]

    results.sort(key=lambda x: x["rrf_score"], reverse=True)
    top_results = results[:top_k]

    return {
        "query": query,
        "intent": intent,
        "confidence": round(confidence, 3),
        "scope_weights": scope_weights,
        "paths": source_metadata,
        "results": top_results,
        "total_results": len(results),
        "retrieved_from": "fresh",
    }


def run_pipeline(query: str, docs: List[Dict], config: dict, cache: QueryCache) -> Dict[str, Any]:
    """标准搜索管线"""
    params = f"k={config['fusion']['top_k']}"

    if cache:
        cached = cache.get(query, params)
        if cached:
            cached["retrieved_from"] = "cache"
            return cached

    result = _run_pipeline(query, docs, config, cache, enhanced=False)

    if cache:
        cache.set(query, params, result)

    return result


def run_pipeline_enhanced(query: str, docs: List[Dict], config: dict, cache: QueryCache) -> Dict[str, Any]:
    """增强搜索管线（LLM Wiki 模式）"""
    docs = extract_wikilinks_and_frontmatter(docs)
    params = f"enhanced=k={config['fusion']['top_k']}"

    if cache:
        cached = cache.get(query, params)
        if cached:
            cached["retrieved_from"] = "cache"
            return cached

    result = _run_pipeline(query, docs, config, cache, enhanced=True)
    result["wiki_enhanced"] = any(doc.get("wikilinks") for doc in docs)

    if cache:
        cache.set(query, params, result)

    return result


# ──────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────

def format_result(result: Dict[str, Any]) -> str:
    """格式化输出搜索结果"""
    intent_emoji = {
        "query": "🔍", "question": "❓", "explain": "💡",
        "compare": "⚖️", "debug": "🐛", "create": "🆕",
        "update": "🔄", "optimize": "⚡", "review": "👀",
        "migrate": "🚀", "unknown": "📝",
    }

    lines = []
    emoji = intent_emoji.get(result["intent"], "📝")

    lines.append(f"\n{'='*60}")
    lines.append(f"{emoji} 搜索结果")
    lines.append(f"{'='*60}")
    lines.append(f"📋 查询: \"{result['query']}\"")
    lines.append(f"🎯 意图: {result['intent']} (置信度: {result['confidence']:.3f})")
    lines.append(f"📊 结果: 找到 {result['total_results']} 个匹配文件")
    lines.append(f"⚡ 来源: {'缓存命中' if result.get('retrieved_from') == 'cache' else '实时搜索'}")
    if result.get('wiki_enhanced'):
        lines.append(f"🔗 Wiki 增强: 已启用")
    lines.append("")

    if result["paths"]:
        lines.append("📌 多路查询详情:")
        for path_info in result["paths"]:
            lines.append(f"   [{path_info['path']}] 权重={path_info['weight']} | 命中={path_info['count']}条")
        lines.append("")

    if not result["results"]:
        lines.append("😔 未找到相关结果，请尝试其他关键词。")
        lines.append(f"{'='*60}\n")
        return "\n".join(lines)

    lines.append(f"{'─'*60}")
    lines.append(f"📚 推荐结果 (Top {len(result['results'])}):")
    lines.append(f"{'─'*60}")

    for i, doc in enumerate(result["results"], 1):
        lines.append(f"\n  {i}. [{doc['rrf_score']:.6f}] {doc['file_name']}")
        lines.append(f"     📂 路径: {doc['file_path']}")
        lines.append(f"     📁 目录: {doc['parent_dir']}/{doc['directory']}" if doc.get('parent_dir') else f"     📁 目录: {doc['directory']}")

        if doc.get("tags"):
            tag_str = ", ".join(doc["tags"][:5])
            lines.append(f"     🏷️  标签: {tag_str}")

        preview = doc.get("content_preview", "")
        clean_preview = re.sub(r'[#*_\-\[\]]', '', preview)[:200].strip()
        if clean_preview:
            lines.append(f"     📄 摘要: {clean_preview}...")

        if doc.get("source_scores"):
            score_parts = [f"{sn}={sv}" for sn, sv in doc["source_scores"]]
            lines.append(f"     🔬 来源得分: {', '.join(score_parts)}")

    lines.append(f"\n{'='*60}\n")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# CLI Entry point
# ──────────────────────────────────────────────

def load_config(profile_path: Path) -> dict:
    """加载配置文件"""
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    parser = argparse.ArgumentParser(description="Ryan 个人知识库搜索引擎")
    parser.add_argument("query", help="搜索查询语句")
    parser.add_argument("--profile", default=None, help="配置文件路径")
    parser.add_argument("--index", default=None, help="索引文件路径（缓存用）")
    parser.add_argument("--clear-cache", action="store_true", help="清除缓存")
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    parser.add_argument("--verbose", action="store_true", help="显示详细信息")
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

    # 构建/加载索引
    index_path = script_dir / ".cache" / "index.json"

    if args.rebuild or not index_path.exists():
        print("📦 正在构建知识库索引...")
        docs = build_index(kb_root)
        print(f"   索引了 {len(docs)} 个 Markdown 文件")

        serializable_docs = []
        for doc in docs:
            sdoc = {k: v for k, v in doc.items() if k != "full_content"}
            serializable_docs.append(sdoc)

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(serializable_docs, f, ensure_ascii=False, indent=2)
    else:
        with open(index_path, "r", encoding="utf-8") as f:
            partial_docs = json.load(f)

        docs = []
        for sdoc in partial_docs:
            try:
                full_path = sdoc["file_path"]
                content = Path(full_path).read_text(encoding="utf-8")
                doc = {**sdoc, "full_content": content}
                docs.append(doc)
            except Exception:
                docs.append(sdoc)

    # 索引统计
    all_tags = set()
    for doc in docs:
        all_tags.update(doc.get("tags", []))
    print(f"📖 知识库统计: {len(docs)} 文件, {len(all_tags)} 标签")

    if not args.query:
        parser.print_help()
        return

    print(f"\n🔍 正在搜索: \"{args.query}\"")

    try:
        # 自动检测是否需要 Wiki 增强
        has_wiki_structure = any(
            re.search(r'^---\n.*type:\s*(entity|concept)', doc["full_content"], re.DOTALL)
            for doc in docs
        )
        has_wikilinks = any(extract_wikilinks(doc.get("full_content", "")) for doc in docs)

        if has_wiki_structure or has_wikilinks or args.wiki:
            print(f"  🔗 LLM Wiki 模式: wikilinks={has_wikilinks}, entities={has_wiki_structure}")
            result = run_pipeline_enhanced(args.query, docs, config, cache)
        else:
            result = run_pipeline(args.query, docs, config, cache)
    except Exception as e:
        print(f"❌ 搜索出错: {e}")
        import traceback
        traceback.print_exc()
        return

    print(format_result(result))


if __name__ == "__main__":
    main()
