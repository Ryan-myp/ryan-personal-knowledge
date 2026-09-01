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
knowledge_type: hierarchy | constraint | parameter | workflow | best_practice | error_pattern | case_study | tip | general
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

## Runtime 使用边界

- Runtime 只通过 `KnowledgeProvider` 读取已发布 Markdown 文档。
- 当前检索是确定性的词法检索，包含标题、标签、正文、平台和知识类型过滤；不接入向量库。
- 结果只注入有界 excerpt，并携带 citation、版本和来源。
- 知识只提供业务上下文，不创建 Tool、权限、凭证或执行路径。
- Provider 的 Tool schema 才是参数校验的权威来源，Wiki 不能替代 Tool schema。

## 编辑与发布

文档修改应创建新的版本并更新 `log.md`。草稿不会被 Runtime 检索；删除或废弃文档应保留变更记录和来源说明。
