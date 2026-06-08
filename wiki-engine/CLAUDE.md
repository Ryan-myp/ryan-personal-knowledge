# LLM Wiki Schema

## 领域
通用业务交付知识库（biz-delivery + ad-ai-coding）

## 约定
- 文件名：小写 + 连字符，无空格
- 每个 wiki 页面以 YAML frontmatter 开头
- 用 `[[wikilinks]]` 链接页面（至少 2 个出站链接）
- 更新页面时更新 `updated` 日期
- 每个新页面必须加入 `index.md`
- 每次操作追加到 `log.md`

## Frontmatter
```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [技术, 架构, 广告, agent]
---
```

## Tag 体系
- 技术：技术, 架构, 数据库, 缓存, 并发, API
- 广告：广告, 竞价, 排序, RTB, 投放, 数据
- Agent：agent, skill, orchestration, rag
- 业务：prd, 评审, td, 测试, 流水线

## 页面阈值
- 创建页面：实体/概念在 2+ 来源中出现，或一个来源的核心主题
- 已有页面追加：新信息补充到现有页面
- 不要创建：仅提及一次的内容
- 拆分页面：超过 200 行 → 拆成子主题
- 归档页面：内容已被完全替代
