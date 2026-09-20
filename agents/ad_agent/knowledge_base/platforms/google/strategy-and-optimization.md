---
schema_version: "1"
id: google-ads-strategy-and-optimization
title: Google Ads 目标、出价与优化方法
layer: platform
knowledge_type: best_practice
platform: google-ads
source: Google Ads 官方文档 + Google Ads Tool Source/Skill
source_ref: "https://developers.google.com/google-ads/api/docs/campaigns/bidding/strategy"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [google, search, pmax, shopping, video, app, bidding, optimization]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# Google Ads 目标、出价与优化方法

## 平台定位

Google Ads 以搜索意图、商品目录、YouTube 内容和跨网络自动化为核心。Search 更适合承接已表达需求的用户，Shopping/PMax 更依赖商品数据与资产质量，Video/Demand Gen 更偏上层需求和再营销。选择 Campaign 类型前先回答：用户是否主动搜索、是否有 Merchant Center/商品源、是否有可用转化数据、素材是否适合视频，以及是否接受自动化扩量。

## 目标到策略的映射

| 业务目标 | 优先考虑 | 关键前提 |
|---|---|---|
| 高意向获客 | Search + 转化优化 | 转化动作定义、关键词与否定词、落地页 |
| 商品销售 | Shopping/PMax | Merchant Center、商品数据、purchase value |
| App 安装/应用内事件 | App Campaign | App ID、事件回传、平台与地区 |
| 视频触达/观看 | Video | YouTube 视频资产、CPM/CPV 语义 |
| 新客与再营销并行 | 分层 Campaign 或实验 | 第一方受众、排除规则、增量口径 |

不要把“最大化点击”当作长期转化策略，也不要在转化稀少时直接给出过窄的 tCPA/tROAS。出价策略必须与优化事件、转化价值、预算和数据量一起判断；具体可选枚举以当前 Tool schema 和账户类型为准。

## Search 优化闭环

1. 按意图而不是只按词面拆分 AdGroup：品牌、非品牌、竞品、问题型和高价值品类分别观察。
2. 用 search terms 识别真实查询，添加否定词并检查是否误伤高价值意图。
3. 观察 impression share、lost IS（budget/rank）、CTR、转化率、CPA 与搜索词质量。
4. 先修正相关性、广告资产、落地页和转化追踪，再调预算或出价。
5. 用小范围 Experiment 验证出价、广泛匹配、落地页或新资产，不同时改变多个变量。

## Shopping/PMax 优化闭环

- 先修复商品标题、属性、价格、库存、政策和 Merchant Center 诊断；商品源错误会伪装成投放问题。
- 用 asset group 表达产品线/受众/主题，并确保文字、图片、Logo、视频和最终 URL 彼此一致。
- 用 listing group/product group 做可解释的商品分层，保留高毛利、高库存或高复购商品的独立观测窗口。
- 同时看 spend、conversion value、ROAS、新客比例、品牌与非品牌贡献；不能只看平台归因 ROAS。
- 放量时优先逐步增加预算，或放宽过紧的目标；频繁大幅改目标会重新扰动学习。

## 通用调参原则

| 现象 | 先查什么 | 再做什么 |
|---|---|---|
| 花不出去 | 审核、预算、出价、定向、商品/素材资格 | 修复资格或逐项放宽限制 |
| 有点击无转化 | 搜索意图、落地页、事件触发、数据延迟 | 先校准漏斗，再调整出价 |
| CPA 上升 | 查询质量、竞争、转化率、目标是否过激 | 分层诊断，避免只降预算 |
| ROAS 下降 | 订单价值、品牌占比、商品组合、新老客 | 拆分价值与增量后再优化 |
| 波动大 | 数据量、归因窗口、改动频率、日期边界 | 固定观察窗口，建立变更日志 |

## 能力边界

当前项目已覆盖 Campaign、AdGroup、Ad、Keyword、Asset、Campaign Budget、Conversion Action、Audience、Bidding Strategy、Experiment、Feed、PMax Asset Group 和报告等部分能力；个别格式或字段仍需以 Registry Tool schema、账户资格与 dry-run 结果确认。知识文档不能替代 GAQL 字段兼容性校验，也不能把规划能力当作已上线执行能力。
