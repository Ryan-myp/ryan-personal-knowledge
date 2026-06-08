#!/usr/bin/env python3
"""
Ryan 个人知识库搜索引擎 — 轻量级搜索/查询入口

复用 biz-delivery 框架的核心能力：
- smart_routing.py 的意图识别逻辑
- rrf_fusion.py 的多维度融合（文件内容、文件名、标签、目录路径）
- query_cache.py 的查询缓存

用法:
    python3 query_knowledge.py "我想看 Redis 相关的书"
    python3 query_knowledge.py "怎么集成 agentmemory"
    python3 query_knowledge.py "对比 agentmemory 的三种方案"
"""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────
# 1. 意图识别 (复用 biz-delivery smart_routing.py)
# ──────────────────────────────────────────────

INTENT_PATTERNS = {
    "query": ["查询", "查看", "获取", "查找", "检索", "显示", "query", "search", "get", "list", "想找", "想看", "想看", "想要", "推荐", "想"],
    "question": ["什么", "如何", "怎么", "为什么", "吗", "what", "how", "why", "where"],
    "explain": ["解释", "说明", "原理", "机制", "explain", "describe", "how it works"],
    "compare": ["对比", "比较", "区别", "差异", "compare", "diff", "difference"],
    "debug": ["排障", "错误", "问题", "失败", "bug", "error", "fix", "troubleshoot"],
    "create": ["创建", "新建", "添加", "新增", "生成", "构建"],
    "update": ["修改", "更新", "变更", "调整", "编辑", "更改"],
    "optimize": ["优化", "性能", "效率", "optimize", "performance"],
    "review": ["评审", "审核", "检查", "review", "audit"],
    "migrate": ["迁移", "升级", "转换", "migrate", "upgrade"],
}

INTENT_TO_SCOPE_WEIGHTS = {
    "query": {"file_content": 0.8, "file_name": 0.5, "tags": 0.7, "directory_path": 0.6},
    "question": {"file_content": 0.8, "file_name": 0.4, "tags": 0.6, "directory_path": 0.5},
    "explain": {"file_content": 0.9, "file_name": 0.3, "tags": 0.7, "directory_path": 0.5},
    "compare": {"file_content": 0.7, "file_name": 0.5, "tags": 0.8, "directory_path": 0.6},
    "debug": {"file_content": 0.9, "file_name": 0.4, "tags": 0.8, "directory_path": 0.5},
    "create": {"file_content": 0.7, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5},
    "update": {"file_content": 0.7, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5},
    "optimize": {"file_content": 0.8, "file_name": 0.4, "tags": 0.7, "directory_path": 0.5},
    "review": {"file_content": 0.7, "file_name": 0.5, "tags": 0.7, "directory_path": 0.5},
    "migrate": {"file_content": 0.7, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5},
}

# 默认（unknown 意图）
DEFAULT_SCOPE_WEIGHTS = {"file_content": 0.8, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5}


def extract_intent(query: str) -> Tuple[str, float]:
    """从查询文本中提取意图和置信度"""
    query_lower = query.lower()
    scores = {}

    for intent, patterns in INTENT_PATTERNS.items():
        score = sum(1 for pattern in patterns if pattern.lower() in query_lower)
        if score > 0:
            avg_pattern_len = sum(len(p) for p in patterns) / len(patterns)
            normalized_score = score / len(patterns) * (avg_pattern_len / 10)
            scores[intent] = min(normalized_score, 1.0)

    if not scores:
        return ("unknown", 0.0)

    max_intent = max(scores, key=scores.get)
    return (max_intent, scores[max_intent])


def get_scope_weights(intent: str) -> Dict[str, float]:
    """获取意图对应的多维度权重"""
    return INTENT_TO_SCOPE_WEIGHTS.get(intent, DEFAULT_SCOPE_WEIGHTS)


# ──────────────────────────────────────────────
# 2. 知识库索引器（提取 .md 文件的关键词/标签/分类）
# ──────────────────────────────────────────────

TAG_PATTERN = re.compile(r'#[-\w\u4e00-\u9fff]+')
HEADING_PATTERN = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)
FOOTER_PATTERN = re.compile(r'^\*\*.*?\*\*.*?:\s*(.+)$', re.MULTILINE)


def extract_frontmatter_tags(md_content: str) -> List[str]:
    """从 YAML frontmatter 中提取 tags"""
    tags = []
    match = re.search(r'^---\n(.*?)\n---', md_content, re.DOTALL)
    if match:
        fm_text = match.group(1)
        fm_tags = re.findall(r'tags?\s*:\s*(.+)', fm_text, re.IGNORECASE)
        for tag_line in fm_tags:
            # 支持 #tag1 #tag2 格式
            tags.extend(TAG_PATTERN.findall(tag_line))
    return tags


def extract_md_tags(md_content: str) -> List[str]:
    """从 Markdown 正文中提取 #tag"""
    return TAG_PATTERN.findall(md_content)


def extract_headings(md_content: str) -> List[str]:
    """提取所有标题"""
    return HEADING_PATTERN.findall(md_content)


def extract_keywords(md_content: str, file_path: Path) -> Dict[str, Any]:
    """提取文件的结构化信息"""
    frontmatter_tags = extract_frontmatter_tags(md_content)
    body_tags = extract_md_tags(md_content)
    all_tags = list(dict.fromkeys(frontmatter_tags + body_tags))  # 去重保留顺序
    headings = extract_headings(md_content)
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
        "content_preview": md_content[:500],  # 前500字符用于搜索
        "full_content": md_content,
        "word_count": len(md_content.split()),
        "is_entry_file": is_entry,  # 入口文件标记（SKILL.md, README.md）
        "created": "",
    }


# ──────────────────────────────────────────────
# 3. 多路查询引擎（复用 rrf_fusion.py 思路）
# ──────────────────────────────────────────────

RRF_K = 60


def search_file_content(query: str, docs: List[Dict], top_k: int = 10) -> List[Dict]:
    """按文件内容搜索 — BM25 简化版（TF * log(N/df) 近似）"""
    query_terms = set(re.findall(r'[\w\u4e00-\u9fff]+', query.lower()))
    if not query_terms:
        return []

    scored = []
    for doc in docs:
        content_lower = doc["full_content"].lower()
        # 计算关键词命中
        matched = 0
        for term in query_terms:
            # 中文单字匹配 + 英文词匹配
            if term in content_lower:
                matched += 1
            else:
                # 对英文做单词边界匹配
                if re.search(r'\b' + re.escape(term) + r'\b', content_lower):
                    matched += 1

        if matched > 0:
            # 简化 TF 计算
            tf = matched / len(query_terms)
            # 内容长度惩罚
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
        # 也检查 headings
        for h in doc.get("headings", []):
            text_to_check += " " + h.lower()

        if query_lower in text_to_check:
            # 完全包含
            score = 1.0
        else:
            # 部分词匹配
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
    scored = []
    for doc in docs:
        tags = [t.lower().lstrip('#') for t in doc.get("tags", [])]
        query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query_lower))
        if not query_words:
            continue

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
# 4. RRF 融合
# ──────────────────────────────────────────────

def rrf_ranks(candidates: List[List[Dict]], k: int = RRF_K) -> List[Dict]:
    """Reciprocal Rank Fusion 融合多个排序结果"""
    rank_scores: Dict[str, Dict[str, Any]] = {}

    for result_list in candidates:
        for rank, item in enumerate(result_list):
            item_id = item["file_path"]
            if item_id not in rank_scores:
                rank_scores[item_id] = {
                    "score": 0.0,
                    "item": item,
                    "sources": [],
                }
            rank_scores[item_id]["score"] += 1.0 / (k + rank + 1)
            if len(result_list) > 0:
                rank_scores[item_id]["sources"].append(f"path_{rank + 1}")

    # 排序
    ranked = sorted(
        rank_scores.values(),
        key=lambda x: x["score"],
        reverse=True,
    )

    return [r["item"] for r in ranked]


# ──────────────────────────────────────────────
# 5. 查询缓存（复用 biz-delivery query_cache.py 思路）
# ──────────────────────────────────────────────

class QueryCache:
    """轻量级文件缓存，支持 TTL"""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 3600):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, query: str, params: str) -> str:
        key_str = f"{query}:{params}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, query: str, params: str) -> Optional[dict]:
        key = self._get_cache_key(query, params)
        path = self._get_cache_path(key)

        if not path.exists():
            return None

        mtime = path.stat().st_mtime
        if time.time() - mtime > self.ttl_seconds:
            path.unlink()
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, query: str, params: str, data: dict):
        key = self._get_cache_key(query, params)
        path = self._get_cache_path(key)
        data["cached_at"] = time.time()
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ──────────────────────────────────────────────
# 6. 核心搜索流程
# ──────────────────────────────────────────────

def build_index(kb_root: Path) -> List[Dict]:
    """扫描所有 .md 文件，构建知识库索引"""
    docs = []
    # 排除 knowledge-search 自身目录
    exclude_dirs = {"knowledge-search", ".git"}

    for md_file in sorted(kb_root.rglob("*.md")):
        # 排除子目录中的重复（如 ryan-personal-knowledge/ryan-personal-knowledge/）
        rel = md_file.relative_to(kb_root)
        parts = rel.parts
        if any(p in exclude_dirs for p in parts):
            continue
        # 避免递归嵌套
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


def run_pipeline(query: str, docs: List[Dict], config: dict, cache: QueryCache) -> Dict[str, Any]:
    """
    执行搜索管线：
    1. 意图识别 → 选择各路径权重
    2. 多路查询（内容/文件名/标签/目录）
    3. RRF 融合
    4. 返回排序结果
    """
    intent, confidence = extract_intent(query)
    scope_weights = get_scope_weights(intent)

    # 构建缓存 key 的参数字符串
    params = f"k={config['fusion']['top_k']}:{intent}"

    # 尝试从缓存获取
    if cache and config.get("cache", {}).get("enabled", True):
        cached = cache.get(query, params)
        if cached:
            cached["retrieved_from"] = "cache"
            return cached

    # 多路查询
    query_type_map = {
        "file_content": search_file_content,
        "file_name": search_file_name,
        "tags": search_tags,
        "directory_path": search_directory,
    }

    top_k = config["fusion"]["top_k"]
    candidates = []
    source_metadata = []
    path_weights = []
    path_results_cache = {}  # 缓存每路搜索结果，供 RRF 融合使用

    for path_cfg in config["fusion"]["paths"]:
        path_name = path_cfg["name"]
        weight = path_cfg.get("weight", 1.0)
        # 应用意图权重
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
            # 缓存 path_results 供后续 RRF 融合使用
            path_results_cache[path_name] = results

    # RRF 融合
    if candidates:
        fused = rrf_ranks(candidates, k=config["fusion"]["rrf_k"])
    else:
        fused = []

    # 计算最终得分并排序
    enhanced_results = []
    for rank, doc in enumerate(fused):
        # 多路径综合得分 — 用之前缓存的 path_results，不再重复搜索
        total_score = 0.0
        source_scores = []
        for i, path_cfg in enumerate(config["fusion"]["paths"]):
            path_name = path_cfg["name"]
            weight = path_cfg.get("weight", 1.0) * scope_weights.get(path_name, 0.5) * (0.5 + 0.5 * confidence)

            if path_name in path_results_cache:
                path_results = path_results_cache[path_name]
                for j, r in enumerate(path_results):
                    if r["file_path"] == doc["file_path"]:
                        rrf_contrib = weight * (1.0 / (RRF_K + j + 1))
                        total_score += rrf_contrib
                        source_scores.append((path_name, round(rrf_contrib, 6)))
                        break

        enhanced_results.append({
            **doc,
            "rrf_score": round(total_score, 6),
            "source_scores": source_scores,
            "intent": intent,
            "confidence": round(confidence, 3),
        })

    # 入口文件惩罚：SKILL.md / README.md 太通用，降低优先级
    ENTRIES_PENALTY = 0.7  # 入口文件得分乘以 0.7
    for r in enhanced_results:
        if r.get("is_entry_file", False):
            r["rrf_score"] *= ENTRIES_PENALTY
            r["source_scores"] = [(k, round(v * ENTRIES_PENALTY, 6)) for k, v in r["source_scores"]]

    enhanced_results.sort(key=lambda x: x["rrf_score"], reverse=True)
    top_results = enhanced_results[:top_k]

    result = {
        "query": query,
        "intent": intent,
        "confidence": round(confidence, 3),
        "scope_weights": scope_weights,
        "paths": source_metadata,
        "results": top_results,
        "total_results": len(enhanced_results),
        "retrieved_from": "fresh",
    }

    # 写入缓存
    if cache and config.get("cache", {}).get("enabled", True):
        cache.set(query, params, result)

    return result


def format_result(result: Dict[str, Any]) -> str:
    """格式化输出搜索结果"""
    intent_emoji = {
        "query": "🔍",
        "question": "❓",
        "explain": "💡",
        "compare": "⚖️",
        "debug": "🐛",
        "create": "🆕",
        "update": "🔄",
        "optimize": "⚡",
        "review": "👀",
        "migrate": "🚀",
        "unknown": "📝",
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

        # 内容摘要
        preview = doc.get("content_preview", "")
        # 清理 markdown 标记做摘要
        clean_preview = re.sub(r'[#*_\-\[\]]', '', preview)[:200].strip()
        if clean_preview:
            lines.append(f"     📄 摘要: {clean_preview}...")

        # 来源得分明细
        if doc.get("source_scores"):
            score_parts = [f"{sn}={sv}" for sn, sv in doc["source_scores"]]
            lines.append(f"     🔬 来源得分: {', '.join(score_parts)}")

    lines.append(f"\n{'='*60}\n")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# 7. 入口
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

    args = parser.parse_args()

    # 确定基准目录
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

        # 保存索引
        serializable_docs = []
        for doc in docs:
            sdoc = {k: v for k, v in doc.items() if k != "full_content"}
            serializable_docs.append(sdoc)

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(serializable_docs, f, ensure_ascii=False, indent=2)
    else:
        with open(index_path, "r", encoding="utf-8") as f:
            partial_docs = json.load(f)

        # 重新加载完整内容用于搜索
        docs = []
        for sdoc in partial_docs:
            try:
                full_path = sdoc["file_path"]
                content = Path(full_path).read_text(encoding="utf-8")
                doc = {**sdoc, "full_content": content}
                docs.append(doc)
            except Exception:
                docs.append(sdoc)

    # 显示索引统计
    all_tags = set()
    for doc in docs:
        all_tags.update(doc.get("tags", []))
    print(f"📖 知识库统计: {len(docs)} 文件, {len(all_tags)} 标签")

    if not args.query:
        parser.print_help()
        return

    # 执行搜索
    print(f"\n🔍 正在搜索: \"{args.query}\"")

    try:
        result = run_pipeline(args.query, docs, config, cache)
    except Exception as e:
        print(f"❌ 搜索出错: {e}")
        import traceback
        traceback.print_exc()
        return

    # 输出结果
    print(format_result(result))


if __name__ == "__main__":
    main()
