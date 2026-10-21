---
schema_version: "1"
id: google-keyword-planning-and-search-intent
title: Google Ads 关键词规划与搜索意图研究
layer: platform
wiki_type: concept
knowledge_type: workflow
platform: google-ads
source: Google Ads API 官方 Keyword Planning 文档与项目内 Google Ads Tool contract
source_ref: "https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas"
source_kind: official
authority: official
evidence_level: reviewed
last_verified_at: "2026-10-21"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-10-21"
tags: [google-ads, keyword-planner, keyword-research, search-intent, search-volume]
status: published
---

# Google Ads 关键词规划与搜索意图研究

## 能力范围

Google Ads Keyword Planning API 的 `GenerateKeywordIdeas` 可以使用关键词种子，或关键词加 URL 种子，返回候选词及历史指标。当前项目暴露的 `google_generate_keyword_ideas` 是只读查询：最多 20 个关键词种子，可选 URL、最多 10 个 Geo Target、语言、网络、分页 token 和有界结果数。它不创建关键词，也不创建 Campaign。

请求账户来自当前 Runtime 的可信账户上下文；关键词建议 API 使用 Google Ads OAuth 的 `adwords` scope。实际调用仍受 Google Ads 账户权限、开发者 Token、API 配额和服务端 Tool policy 约束。未配置客户端时 Runtime 只能返回 offline 标记，不能称为实时 Keyword Planner 结果。

## 指标如何读

| 字段 | 含义与限制 |
|---|---|
| `text` | Google 返回的规范化候选词；可能聚合 close variants，不一定等同于一个原样搜索查询。 |
| `average_monthly_searches` | 历史平均搜索量，不是未来点击、展示或转化预测。 |
| `competition` / `competition_index` | Google Ads 历史广告竞争信号；不代表 SEO 自然排名难度，也不代表当前竞价强度。 |
| `low_top_of_page_bid_micros` / `high_top_of_page_bid_micros` | 页面顶部出价历史区间，以账户货币的 micros 表示；可读金额换算需除以 1,000,000，并注明币种未知时不要换算。 |
| `next_page_token` | 有更多结果时继续翻页。分页请求必须保持其他种子与定向条件不变；只看第一页不能宣称结果完整。 |

没有传 Geo Target 或语言时，结果可能跨多个地理区域或语言。对单一市场的规划应明确传入适用的官方 `geoTargetConstants/{id}` 与 `languageConstants/{id}`。网络设置也需要记录，避免把 Google Search 与 Search Partners 数据混为同一范围。

## 建议的研究闭环

```text
业务目标与目标市场
  -> 关键词/可选 URL 种子
  -> Keyword Planner 历史建议
  -> 搜索意图与语义聚类
  -> 落地页、广告承诺和转化目标匹配
  -> 账户真实搜索词与转化数据验证
  -> 仅在单独确认后提出关键词写入计划
```

按信息型、比较型、交易型、品牌/导航型和商品属性聚类；优先保留与落地页和商业价值相符的主题。对 Search campaign 的最终决策应同时检查真实搜索词、匹配方式、否定关键词和转化质量。Keyword Planner 建议不能替代账户报告或业务转化数据。

## 能力边界

- Historical metrics 不是 `GenerateKeywordForecastMetrics` 预测结果。
- 建议列表不证明关键词已在账户投放、符合政策、具备资格或能获得流量。
- 关键词添加、更新、删除和否定关键词管理仍属于独立写操作，必须经过当前 Runtime 权限、账户范围、执行模式、确认、幂等与审计门禁。
- Merchant Center 商品表现、GA4 站内行为、自然搜索趋势和竞品广告数据不由此 Tool 提供。

## 官方依据

- [Generate keyword ideas](https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas)
- [GenerateKeywordIdeas v24 API reference](https://developers.google.com/google-ads/api/reference/rpc/v24/KeywordPlanIdeaService/GenerateKeywordIdeas)
