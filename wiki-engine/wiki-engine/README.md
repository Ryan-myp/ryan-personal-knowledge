# LLM Wiki 引擎 — 编译式知识管理系统

> 基于 Karpathy LLM Wiki 模式的通用知识引擎，为 biz-delivery 提供持续演进的知识库能力。

## 核心思想

**LLM Wiki vs RAG：**
- RAG：每次查询从零检索碎片 → 每次都重新发现
- Wiki：知识被编译一次 → 持续迭代 → 查询时已有综合结论

> "The knowledge is compiled once and then kept current, not re-derived on every query."

## 架构 — 三层模型

```
wiki/
├── CLAUDE.md              # Schema：约定、结构规则、tag 体系
├── index.md               # 内容目录：所有页面的概述
├── log.md                 # 操作日志：append-only
├── raw/                   # Layer 1：不可变来源
│   └── articles/          # 文章、论文、代码片段
├── entities/              # Layer 2：实体页面（人/产品/技术）
├── concepts/              # Layer 2：概念/主题页面
├── queries/               # Layer 2：有价值的问答归档
├── comparisons/           # Layer 2：对比分析页面
└── _archive/              # 过期页面归档
```

## 核心流程

### 1. Ingest（新源摄入）
```
新源 → 读文件 → 提取实体/概念 → 更新/创建页面 → 加 wikilinks → 更新 index.md + log.md
```

### 2. Query（知识问答）
```
问题 → 读 index.md → 定位相关页面 → 读页面内容 → 综合回答 → 归档有价值的回答
```

### 3. Lint（定期审计）
```
扫描 → 找断链/孤儿/过时/矛盾 → 报告 + 自动修复建议
```

## 业务集成

biz-delivery 的 `query_evidence.py` 会调用 Wiki 引擎：
```
query_evidence → wiki_search(query) → entity_page → concept_page → file_content → RRF融合
```
