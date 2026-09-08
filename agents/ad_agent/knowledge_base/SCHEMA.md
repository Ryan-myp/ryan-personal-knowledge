# LLM Wiki 文档规范

本目录采用 Markdown-first 的 LLM Wiki 方式：文档是人和模型共同阅读的知识源，`index.md` 负责导航，`log.md` 记录变更。知识文件不包含可执行代码，也不通过 `workflow.yaml` 驱动流程。

## 目录层级

```text
knowledge_base/
├── index.md
├── log.md
├── platforms/<platform>/
├── business/
├── expertise/
└── dynamic/
```

目录表达主题，正文表达规则、例子、边界和证据。每个知识文件可以包含标准 frontmatter；没有 frontmatter 的历史文档会按路径和文件名推导元数据，但新文档必须显式声明。

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
```

`id`、`title`、`layer`、`knowledge_type`、`platform`、`source_ref`、`version`、`confidence`、`updated_at` 和 `status` 是发布前必须具备的事实元数据。`source` 用于展示来源，不能替代 `source_ref`。

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

- Runtime 只通过 `KnowledgeProvider` 读取已发布 Markdown 文档。
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

文档修改应创建新的版本并更新 `log.md`。草稿不会被 Runtime 检索；删除或废弃文档应保留变更记录和来源说明。
