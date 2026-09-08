---
schema_version: "1"
id: google-search-keyword-operations
title: Google Search 关键词、广告相关性与查询优化
layer: platform
knowledge_type: workflow
platform: google-ads
source: Google Ads Search 官方文档 + Google Ads 运营 Skill
source_ref: https://developers.google.com/google-ads/api/docs/campaigns/organize
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [google, search, keyword, match-type, search-terms, negative-keyword, ad-rank, quality]
status: published
---

# Google Search 关键词、广告相关性与查询优化

## 结构设计

Search 的基本单元是 `Campaign → AdGroup → Keyword/Ad`。Campaign 划分预算、地域、语言、网络和目标；AdGroup 聚合同一搜索意图；Keyword 表达可触发的需求；Ad 负责承诺与落地页。不要为了追求颗粒度把每个词拆成一个 AdGroup，也不要把品牌词、竞品词、通用词和不同落地页混在同一个学习单元。

推荐按以下意图拆分：

| 意图 | 典型处理 | 观察重点 |
|---|---|---|
| 品牌 | 独立 Campaign 或明确标签 | 品牌保护、增量与自然流量重叠 |
| 高意向品类 | 按产品/服务和页面拆 AdGroup | 搜索词质量、CVR、CPA |
| 问题/教育 | 独立漏斗或较低价值事件 | 内容承接和后续线索质量 |
| 竞品 | 单独风险与政策检查 | 搜索量、相关性、品牌限制 |
| 低意向泛词 | 先小额探索 | 点击质量和否定词速度 |

## 匹配与搜索词

匹配类型是触发控制与扩量程度的选择，不是关键词质量的替代品。上线后必须定期查看 search terms：将高价值新查询纳入结构，把无关意图加入否定词，确认否定词不会误伤核心词或其他 Campaign。广泛匹配若与智能出价配合，应先确保转化动作、价值和否定规则稳定，并用 Experiment 或受控预算验证。

## 广告与落地页相关性

每个 AdGroup 至少应有清晰的意图主题、相匹配的 RSA 资产和对应页面。诊断“点击多、转化低”时按顺序看：搜索词是否带来真实需求 → 广告是否兑现承诺 → 页面是否首屏可用且速度稳定 → 表单/支付是否正常 → 转化事件是否准确。不要仅通过提高 CPC 解决相关性问题。

## Ad Rank 的运营理解

曝光与位置受竞价、广告质量、相关性、资产、落地页、竞争和上下文影响。`lost IS (budget)` 与 `lost IS (rank)` 是不同问题：前者要评估预算/分配，后者先改善相关性、资产和出价策略。Quality Score 类诊断指标是方向信号，不应当被当作最终业务 KPI。

## 日常检查清单

1. 账户与 Campaign 状态、预算、地域、时区和排期。
2. 搜索词增量、否定词冲突、关键词状态和匹配类型。
3. CTR、CPC、impression share、lost IS 的预算/排名拆解。
4. Ad 资产批准状态、相关性、页面承诺和追踪参数。
5. 转化数量、转化延迟、primary/secondary 与 CRM/订单质量。
6. 变更后按固定窗口复盘，不同时修改关键词、页面和出价。

## 当前执行边界

当前项目已覆盖 Keyword、AdGroup、Ad、Campaign Criterion、报告和 Experiment 等部分 Tool。关键词/定向候选、账户 ID、动态状态和字段组合仍需走当前 Registry lookup/schema；知识文档不能直接创建或修改资源。
