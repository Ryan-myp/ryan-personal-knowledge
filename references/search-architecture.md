# 搜索引擎架构决策 — knowledge-search + wiki-engine 双引擎

> 标签: `#知识库搜索` `#RRF融合` `#wiki-engine` `#search-architecture`

---

## 核心决策

知识库搜索采用**双引擎互补**架构，两个引擎都走同一个 biz-delivery 核心（smart_routing + rrf_fusion + query_cache）。

| | knowledge-search | wiki-engine |
|---|---|---|
| **搜什么** | knowledge/ 原始 .md 文件 | wiki/ 结构化页面 |
| **优势** | 覆盖全，不依赖结构化 | 有语义链接、entity 概念 |
| **劣势** | 纯文本匹配 | 依赖 ingested |
| **触发** | 自动检测 wikilinks 启用 Wiki 增强 | 始终使用结构化搜索 |

---

## 搜索路径 1: knowledge-search（RRF 融合搜索原始 .md 文件）

```bash
cd ~/ryan-personal-knowledge
python3 knowledge-search/query_knowledge.py "Redis 持久化" --rebuild
```

**4路搜索 + RRF 融合：**
1. `file_content` — 文件内容全文搜索
2. `file_name` — 文件名匹配
3. `tags` — frontmatter tags 匹配
4. `directory_path` — 目录路径匹配

**RRF 融合：**
```
Score(item) = Σ 1 / (rank_i + 60)
```

**Wiki 增强模式：** 当检测到文档中有 `[[wikilink]]` 格式时，自动启用 entity_pages boost。

---

## 搜索路径 2: wiki-engine（结构化 Wiki 搜索）

```bash
cd ~/biz-delivery
python3 wiki-engine/query.py ~/ryan-personal-knowledge/knowledge "关键词"
```

**核心能力：**
- `frontmatter` — 文档元数据 tags
- `wikilinks` — 文档间语义链接图遍历
- `entity_pages` — 实体页面 boost
- `cross_reference` — 跨文档引用追踪

**Ingest 流程：**
```
kb_to_wiki.py:
  knowledge/*.md (原始)
    → frontmatter 提取
    → wikilinks 解析
    → 生成 wiki/*.md (结构化)
    → entity_pages 构建
```

---

## kb_to_wiki 自动同步

**Post-commit hook（.git/hooks/post-commit）：**
- 触发条件：commit 包含 `knowledge/` 变更
- 行为：执行 `kb_to_wiki.py --execute`
- 非 `knowledge/` 变更静默跳过
- ingest 失败不影响 commit

**手动执行：**
```bash
python3 kb_to_wiki.py --execute --kb-dir knowledge --wiki-dir wiki-engine/wiki
```

---

## 搜索 + LLM 综合回答

```bash
python3 knowledge-search/query_knowledge_answer.py "Kafka Rebalance 流程"
```

流程：
1. knowledge-search 召回 Top-K 文档
2. LLM 综合回答 + 引用来源

---

## Pitfalls

- knowledge-search 是 biz-delivery 的 **thin wrapper**，import scripts 用相对 import
- biz-delivery 的 scripts 需 sys.path 指向 biz-delivery root
- biz-delivery 的 extract_intent 对短中文查询置信度低，knowledge-search 保留自己的 get_scope_weights() 覆盖
- 目录名必须用下划线（knowledge_search/ wiki_engine/）
- rg --json 输出格式：data.path.text / data.lines.text / data.lines.line_number / data.submatches

---

*基于 biz-delivery/wiki-engine 和 knowledge-search 实际使用经验整理*
