---
name: ad-platform-api-expert
description: "广告平台 API 专家技能 — Google Ads / Meta / TikTok / DV360 Marketing API 深度解析"
version: 1.0.0
author: ryan
tags: [advertising, api, google-ads, meta-ads, tiktok-ads, dv360, expert]
---

# 广告平台 API 专家技能

> 四大主流广告平台 API 的深度解析与实战指南

## 平台覆盖

### Google Ads API
- **核心能力**：Campaign 管理、AdGroup、Keywords、Bidding、Reports
- **数据流**：Marketing API + Google Analytics + BigQuery
- **关键概念**：PMax（Performance Max）、GMX（General Merchandise eXperience）
- **API 版本**：v15+（REST + gRPC）

### Meta Marketing API
- **核心能力**：Ad Account、Campaign、Ad Set、Creative、Insights
- **数据流**：Events API + CAPI（Conversions API）
- **关键概念**：Advantage+、CAVE 模型、Attribution Window
- **API 版本**：v17+

### TikTok Marketing API
- **核心能力**：Ad Account、Campaign、Ad Group、Creative、Pixel
- **关键概念**：Spark Ads、In-Feed、TopView
- **独特能力**：短视频创意优化、达人合作 API
- **API 版本**：v202401+

### DV360 (Google Marketing Platform)
- **核心能力**：Display & Video 360、Search Ads 360、Campaign Manager
- **关键概念**：Bid Surge、Automated Rules、Cross-Channel Attribution
- **适用场景**：大型企业、程序化购买、品牌安全

## 知识库引用

| 平台 | 核心文档 |
|------|---------|
| Google Ads | `knowledge/advertising/google-ads/google-ads-architecture-deep.md` |
| Google Ads API | `knowledge/advertising/day-by-day/google-01-google-ads-api-principles.md` |
| Google Ads 进阶 | `knowledge/advertising/day-by-day/google-06-google-ads-api-advanced.md` |
| Meta Ads | `knowledge/advertising/meta-ads/meta-ads-architecture-deep.md` |
| Meta API | `knowledge/advertising/day-by-day/meta-01-meta-ads-api-principles.md` |
| Meta 进阶 | `knowledge/advertising/day-by-day/meta-05-meta-ads-api-advanced.md` |
| TikTok Ads | `knowledge/advertising/tiktok-ads/tiktok-ads-architecture-deep.md` |
| TikTok API | `knowledge/advertising/day-by-day/tiktok-01-tiktok-ads-api-principles.md` |
| DV360 | `knowledge/advertising/dv360/dv360-architecture-deep.md` |
| DV360 API | `knowledge/advertising/dv360/dv360-marketing-api-deep.md` |

## 使用场景

### 场景 1: 选择广告平台 API
1. 确定目标受众 → Google（搜索意图）、Meta（社交兴趣）、TikTok（年轻群体）
2. 查看对应平台的架构文档
3. 参考 API 原则文档了解核心设计

### 场景 2: 排查 API 问题
1. 查看 `knowledge/advertising/knowledge-query-pitfalls.md` 了解常见坑
2. 查看各平台的 troubleshooting 文档
3. 使用验证脚本测试 API 连接

### 场景 3: 设计 API 集成方案
1. 参考 `knowledge/advertising/day-by-day/google-01-google-ads-api-principles.md`
2. 参考 `knowledge/advertising/day-by-day/meta-01-meta-ads-api-principles.md`
3. 参考 `knowledge/advertising/capi-deep-dive.md` 了解转化追踪

## 关键对比

| 维度 | Google Ads | Meta | TikTok | DV360 |
|------|-----------|------|--------|-------|
| 数据精度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| API 稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 创意灵活性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 自动化程度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 适用场景 | 搜索+购物 | 社交+内容 | 短视频 | 大型品牌 |

## 自测题

<details>
<summary>Q1: Google PMax 和 GMX 有什么区别？</summary>

**答案**：
- **PMax** (Performance Max)：Google 的全自动智能投放，覆盖 Search、Display、YouTube、Gmail、Maps
- **GMX** (General Merchandise eXperience)：PMax 的电商升级版，专门针对商品推广，集成 Merchant Center 数据
- **关键区别**：GMX 有商品级优化，PMax 是 campaign 级别

</details>

<details>
<summary>Q2: Meta CAVЕ 模型是什么？如何用于广告优化？</summary>

**答案**：
CAVE = Creative + Audience + Value + Efficiency
- **Creative**：广告素材效果
- **Audience**：目标受众精准度
- **Value**：用户生命周期价值
- **Efficiency**：投放效率
Advantage+ 利用 CAVЕ 进行自动优化，比传统人工投放效率高 20-30%

</details>

<details>
<summary>Q3: TikTok Spark Ads 和普通 Ads 有什么区别？</summary>

**答案**：
- **Spark Ads**：推广已有的有机视频（可以是达人内容），保留原生互动数据
- **普通 Ads**：从 0 创建的纯广告视频
- **优势**：Spark Ads 可以利用已验证的内容，降低创意成本，提高转化率

</details>
