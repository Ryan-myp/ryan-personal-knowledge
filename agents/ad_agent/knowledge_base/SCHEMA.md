# LLM Wiki 文档规范

本目录采用 Markdown-first 的 LLM Wiki 方式：文档是人和模型共同阅读的知识源，`index.md` 负责导航，`log.md` 记录变更。知识文件不包含可执行代码，也不通过 `workflow.yaml` 驱动流程。目录组织兼容 Karpathy 风格，同时保留广告 Agent 已稳定使用的领域目录，避免一次性搬家破坏来源引用。

## 目录层级

```text
knowledge_base/
├── index.md
├── log.md
├── raw/                         # 不可变来源；仅供 ingest/provenance
├── entities/                    # 平台、产品等稳定实体
├── concepts/                    # 逻辑概念层说明
├── comparisons/                 # 跨平台/方案对比
├── queries/                     # 可复用问答归档
├── platforms/<platform>/
├── business/
├── expertise/
└── dynamic/
```

`platforms/`、`business/`、`expertise/` 是现有概念页的领域存储目录；它们在逻辑上属于 `concepts/`，不要求立即物理迁移。目录表达主题，正文表达规则、例子、边界和证据。每个知识文件可以包含标准 frontmatter；没有 frontmatter 的历史文档会按路径和文件名推导元数据，但新文档必须显式声明。

## Karpathy 对象类型

`wiki_type` 表示页面在 Wiki 中扮演的角色：

| `wiki_type` | 作用 | Runtime 默认 |
|---|---|---|
| `raw` | 原始文章、论文、代码片段和未经审核的来源 | 不加载 |
| `entity` | 平台、产品、人物等稳定对象的身份和导航页 | 加载 |
| `concept` | 已提炼的主题、规则、流程和方法 | 加载 |
| `comparison` | 多平台或多方案对比 | 加载 |
| `query` | 经过筛选、可复用的问答结论 | 加载 |
| `system` | schema、索引、日志和维护说明 | 不加载 |

未声明 `wiki_type` 的历史页面按路径确定性推导：`platforms/`、`business/`、
`expertise/` 为 `concept`。这只影响导航和治理，不改变平台过滤与 Tool 权限边界。

## 标准 frontmatter

```yaml
schema_version: "1"
id: unique-stable-id
title: Human readable title
layer: platform | business | experience | dynamic
knowledge_type: hierarchy | constraint | parameter | workflow | best_practice | error_pattern | case_study | tip | general | bidding_strategy | targeting_strategy | creative_guide | business_strategy
platform: google | meta | tiktok | dv360 | all
source: source owner or authority
source_ref: path, URL, ticket or document reference
version: semantic document version
confidence: 0.0-1.0
updated_at: YYYY-MM-DD
tags: [search, terms]
status: draft | published | deprecated
wiki_type: raw | entity | concept | comparison | query
source_kind: official | code | internal | user | inferred
authority: official | repository | operator | llm
evidence_level: verified | reviewed | provisional
last_verified_at: YYYY-MM-DD
derived_from: raw source or parent document ID
raw_sha256: immutable raw-source digest
wikilinks: ["[[Related page title]]"]
```

`id`、`title`、`layer`、`knowledge_type`、`platform`、`source_ref`、`version`、`confidence`、`updated_at`、`status` 和新页面的 `wiki_type` 是发布前必须具备的事实元数据。`source` 用于展示来源，不能替代 `source_ref`。

`source_ref` 指向原始 URL、仓库文件、工单或测试证据；实体/概念/对比/问答页
必须能回溯到一个或多个来源。`raw/` 的来源文件不直接注入 Runtime，必须先经过
提炼、审核和发布。

`source_kind`、`authority`、`evidence_level` 和 `last_verified_at` 是来源治理字段。
历史页面如果缺少这些字段，Provider 会按 `source_ref` 做保守推断，但新页面应显式填写。
`official` 只表示来源来自平台官方材料，不表示当前账户一定支持该能力；
`code` 表示当前仓库或 Tool Source 事实；`internal` 表示内部经验；`user` 表示用户上传
材料；`inferred` 表示尚未完成来源确认。`verified`、`reviewed` 和 `provisional` 不等同
于模型置信度，发布审核不能用 `confidence` 替代证据等级。

## 租户上传与自动 ingest

HTTP 上传也遵循同一层次：

1. `POST /knowledge/raw` 将文本、Markdown 或 JSON 原文写入 raw source。
2. Store 以 `tenant_id + sha256` 去重；filename、正文、media type、来源引用和 hash
   写入后不可修改，只允许更新 `received / ingesting / draft_ready / failed` 状态字段。
   `received/failed -> ingesting` 必须通过原子 claim 完成，并记录 attempt、任务 ID、
   开始时间和完成时间；`ingesting` 拒绝并发领取，`draft_ready` 默认不重复处理。
   超过 worker 超时的 `ingesting` claim 可被 recovery 标记为 `failed`，避免 source 永久卡死。
3. Runtime 通过通用 `TaskExecutor` 排队 `knowledge.ingest`，不在请求线程调用 LLM。
4. ingest 读取 raw 与当前已发布目录，要求 LLM 返回受限 JSON；所有页面先完整校验，
   再保存为 `draft`，并保留 `source_ref`、`derived_from`、`raw_sha256` 和 `wikilinks`。
5. 人工审核后显式发布；只有发布后的派生页才进入 `KnowledgeProvider`。

LLM 只能产生页面元数据和 Markdown 正文，不能返回目标路径、脚本、Tool、MCP、权限或
凭证。重复 hash 不会产生第二份 raw source，跨租户相同内容仍分别保存。

## 目录分类元数据

`category` 和 `subcategory` 用于把文件系统目录提升为稳定的知识导航树：

```yaml
category: measurement
subcategory: conversion-and-diagnostics
```

推荐的一级分类：

| category | 用途 |
|---|---|
| `platform_foundation` | 平台定位、账户、资源层级和基础对象 |
| `campaign_operations` | 目标、参数依赖、预算、创建与变更工作流 |
| `optimization` | 出价、交付、素材、放量与平台优化 |
| `measurement` | 转化、事件、报表、归因与数据质量 |
| `industry_playbooks` | 电商、App/游戏、B2B、Lead Gen 等行业打法 |
| `budget_bidding` | 跨平台预算、成本、价值和边际收益 |
| `audience_targeting` | 受众、定向、排除、重叠与增量 |
| `creative` | 创意策略、格式、测试与疲劳 |
| `diagnostics` | 故障、异常、排查和失败恢复 |
| `experimentation` | 实验设计、学习期、分流与放量 |
| `system` | 架构、规范、索引和维护说明 |

`subcategory` 是分类下的稳定主题 slug，不用于替代正文标题。历史文档没有显式分类时，Provider 会按 `platforms/<platform>`、`business`、`expertise` 路径和 `knowledge_type` 确定性推导，不会因为重命名标题改变平台边界。目录 API 返回 `documents` 兼容旧客户端，同时返回按平台/分类组织的 `tree`。

## Runtime 使用边界

- Runtime 只通过 `KnowledgeProvider` 读取已发布 Markdown 文档；它默认跳过
  `raw/`、`system` 页面和导航 README。
- 当前检索是确定性的稀疏检索：Markdown 按标题层级切成内存片段，使用 SQLite FTS5 做全文召回，再结合标题/章节/标签字段权重、中文双字词和 BM25 风格评分；不接入向量库。
- 结果只注入有界 excerpt，并携带 citation、版本和来源。
- 结果同时携带 `category/subcategory`，用于 UI 导航和按主题筛选；分类只是导航元数据，不授予执行权限。
- 知识只提供业务上下文，不创建 Tool、权限、凭证或执行路径。
- Provider 的 Tool schema 才是参数校验的权威来源，Wiki 不能替代 Tool schema。

## 关于向量检索

LLM Wiki 是知识组织和内容格式，不等于某一种检索引擎。它可以接向量检索，
也可以使用 BM25、全文检索或混合检索。当前 ad-agent 选择 Markdown 文件 + 进程内
稀疏索引，避免引入 Embedding 模型、向量数据库和额外运维依赖；如果 SQLite 构建不带
FTS5，会自动回退到进程内词法排序。未来若需要语义检索，
应通过 `KnowledgeProvider` 增加可替换实现，不改变 Wiki 文档格式和 Runtime 安全边界。

## 编辑与发布

文档修改应创建新的版本并更新 `log.md`。草稿不会被 Runtime 检索；删除或废弃文档应保留变更记录和来源说明。可复用问答才进入 `queries/`，一次性回答不自动写回知识库。

## 自动审计

```bash
./scripts/ad-agent-python agents/ad_agent/scripts/audit_knowledge_base.py
```

审计覆盖 frontmatter、重复 ID/标题、目录与 `wiki_type` 一致性、来源自引用、
过期页面、断开的 `[[wikilink]]`、孤立实体页、检索案例 ID 漂移和平台知识覆盖。
错误会阻断质量门；来源治理缺失和孤立页先作为 warning，便于渐进式补齐历史页面。
