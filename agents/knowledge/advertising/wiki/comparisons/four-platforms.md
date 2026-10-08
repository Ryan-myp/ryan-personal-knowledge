---
schema_version: "1"
id: four-platform-comparison
title: Google、Meta、TikTok 与 DV360 对比
layer: business
wiki_type: comparison
knowledge_type: general
platform: all
source: 四个平台官方文档与当前 Tool Source 元数据
source_ref: business/four-platform-ad-agent-handbook.md
source_kind: internal
authority: repository
evidence_level: reviewed
last_verified_at: "2026-09-17"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-17"
tags: [comparison, google-ads, meta, tiktok, dv360, hierarchy, measurement]
status: published
---

# Google、Meta、TikTok 与 DV360 对比

四个平台都可以抽象为“账户 -> 活动 -> 投放单元 -> 广告/创意 ->
测量与报表”，但对象名称、预算位置、目标枚举、归因口径和 API 能力
不同。这个页面只提供选择和导航，不把一个平台的字段复制到另一个平台。

| 平台 | 主要投放层级 | 典型强项 | 优先核对 |
|---|---|---|---|
| Google Ads | Campaign -> Ad Group -> Ad/Asset | 搜索意图、商品和跨库存自动化 | Customer、转化动作、GAQL 和预算 |
| Meta | Campaign -> Ad Set -> Ad | 社交内容、探索和再营销 | ODAX 目标、事件去重、学习期和 Page |
| TikTok | Campaign -> Ad Group -> Ad | 短视频创意迭代和内容分发 | 事件质量、素材供给、Spark 授权 |
| DV360 | Partner/Advertiser -> IO -> Line Item | 程序化采购、Deal 和品牌安全 | 资源范围、采购资格、异步报表 |

进一步阅读：

- [[四大广告平台 Agent 专业知识总览]]
- [[四平台广告层级对照与账户设计]]
- [[Google Ads]]
- [[Meta Ads]]
- [[TikTok Ads]]
- [[Display & Video 360]]
