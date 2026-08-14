---
name: ad-platform-api-expert
description: "广告平台 API 专家技能 — Google Ads / Meta / TikTok / DV360 Marketing API 深度解析（v4.0）"
version: 4.0.0
author: ryan
tags: [advertising, api, google-ads, meta-ads, tiktok-ads, dv360, expert, cross-platform]
---

# 广告平台 API 专家技能 v4.0

> 四大主流广告平台 API 的深度解析与实战指南 — 1,637 个 API 方法 + 262 篇深度文档

## 平台覆盖

### Google Ads API (407 个方法)
- **核心能力**：Campaign 管理、AdGroup、Keywords、Bidding、Reports
- **数据流**：Marketing API + Google Analytics + BigQuery + Streaming Mutate
- **关键概念**：PMax（Performance Max）、GMX（General Merchandise eXperience）、Smart Bidding
- **API 版本**：v16+（REST + gRPC）
- **新增能力**：Streaming Mutate 批量操作、PMax 暗箱解析、GMX 商品级优化

### Meta Marketing API (728 个方法)
- **核心能力**：Ad Account、Campaign、Ad Set、Creative、Insights
- **数据流**：Events API + CAPI（Conversions API）+ GraphQL
- **关键概念**：Advantage+ 家族、CAVE 模型、Instagram Shopping、WhatsApp Business
- **API 版本**：v18+
- **新增能力**：Instagram 商业全链路、WhatsApp Business API、Messenger 机器人、CAPI 生产部署

### TikTok Marketing API (324 个方法)
- **核心能力**：Ad Account、Campaign、Ad Group、Creative、Pixel
- **关键概念**：Spark Ads、In-Feed、TopView、直播带货、达人合作
- **独特能力**：短视频创意优化、Spark Ads 原生推广、直播电商闭环
- **API 版本**：v202401+
- **新增能力**：直播带货全流程、推荐算法解析、创意自动化

### DV360 API (178 个方法)
- **核心能力**：IO/LineItem/Creative/Targeting/Reporting
- **关键概念**：PG/PMP/PD 交易类型、Bid Surge、品牌安全、Floodlight
- **适用场景**：大型企业、程序化购买、品牌安全、跨媒体投放
- **新增能力**：媒体购买全流程、预算优化、竞价策略、定向系统、报表分析

## 知识库规模 (v4.0)

```
总文档数:   262+ Markdown 文档（广告业务领域）
总行数:     133,239+ 行
API 方法:   1,637 个（Google 407 + Meta 728 + TikTok 324 + DV360 178）
官方文档:   5 篇（platform-docs/）
深度文档:   257 篇
day-by-day: 25+ 篇学习笔记
```

### 新增强度文档 (v4.0)

| 平台 | 新增文档 |
|------|---------|
| **跨平台** | 战略选型指南、归因模型、统一数据模型、出价 Agent、创意系统 |
| **Google Ads** | PMax 暗箱解析、Streaming Mutate 生产指南 |
| **Meta Ads** | Advantage+ 完整体系、CAPI 生产部署、Instagram Graph API、WhatsApp Cloud API、Messenger 机器人 |
| **TikTok Ads** | 直播带货完整指南 |
| **DV360** | 媒体购买、竞价策略、预算优化、定向系统、报表分析（进行中） |

## 知识库引用

### 跨平台整合
| 主题 | 文档路径 |
|------|---------|
| 平台战略选型 | `knowledge/advertising/ad-cross-platform-strategy-deep.md` |
| 跨平台归因 | `knowledge/advertising/ad-cross-platform-attribution-deep.md` |
| 统一数据模型 | `knowledge/advertising/ad-platform-data-model-deep.md` |
| 统一出价框架 | `knowledge/advertising/ad-unified-bidding-framework-deep.md` |
| 创意管理系统 | `knowledge/advertising/ad-unified-creative-system-deep.md` |

### Google Ads
| 主题 | 文档路径 |
|------|---------|
| 架构 | `knowledge/advertising/google-ads/google-ads-architecture-deep.md` |
| API 生产指南 | `knowledge/advertising/google-ads-api/google-ads-api-production-guide.md` |
| PMax 暗箱 | `knowledge/advertising/google-ads/google-ads-pmax-dark-matter-deep.md` |
| Streaming Mutate | `knowledge/advertising/google-ads-api/google-ads-streaming-mutate-deep.md` |

### Meta Ads
| 主题 | 文档路径 |
|------|---------|
| 架构 | `knowledge/advertising/meta-ads/meta-ads-architecture-deep.md` |
| Advantage+ | `knowledge/advertising/meta-ads/meta-ads-advantage-plus-full-deep.md` |
| CAPI 生产 | `knowledge/advertising/meta-ads-capi-prod-guide.md` |
| Instagram API | `knowledge/advertising/meta-ads-api/meta-instagram-graph-api-deep.md` |
| WhatsApp API | `knowledge/advertising/meta-ads-api/meta-whatsapp-cloud-api-deep.md` |
| Messenger | `knowledge/advertising/meta-ads/meta-ads-messenger-bot-deep.md` |

### TikTok Ads
| 主题 | 文档路径 |
|------|---------|
| 架构 | `knowledge/advertising/tiktok-ads/tiktok-ads-architecture-deep.md` |
| 营销 API | `knowledge/advertising/tiktok-ads/tiktok-ads-marketing-api-deep.md` |
| 直播带货 | `knowledge/advertising/tiktok-ads/tiktok-ads-live-commerce-deep.md` |

### DV360
| 主题 | 文档路径 |
|------|---------|
| 架构 | `knowledge/advertising/dv360/dv360-architecture-deep.md` |
| 营销 API | `knowledge/advertising/dv360/dv360-marketing-api-deep.md` |
| 媒体购买 | `knowledge/advertising/dv360/dv360-media-buying-deep.md` |
| 竞价策略 | `knowledge/advertising/dv360/dv360-bidding-strategy-deep.md` |

## 脚本工具

### 广告平台统一 API 客户端
```bash
# 统一调用脚本
python3 scripts/ad_platform_api.py --platform google --action list_campaigns

# 查询脚本
python3 scripts/ad_platform_query_client.py --platform meta --query insights

# 全量查询
python3 scripts/ad_platform_all_query_client.py
```

### 知识库搜索
```bash
cd knowledge-search
python3 query_knowledge.py "Google PMax 优化策略"
python3 query_knowledge.py "DV360 竞价策略对比"
python3 query_knowledge.py "跨平台归因模型"
```

### 官方文档接入
```bash
python3 scripts/platform_docs_scraper.py --all --mode hybrid
```

## 使用场景

### 场景 1: 选择广告平台
1. 确定目标 → 查看 `ad-cross-platform-strategy-deep.md`
2. 预算评估 → 根据预算门槛选择平台组合
3. 行业适配 → 参考各行业最佳实践矩阵
4. 架构设计 → 参考统一数据模型文档

### 场景 2: API 集成开发
1. 平台认证 → 查看对应平台的 API 生产指南
2. 方法查找 → 参考 `scripts/api_coverage_report.md`
3. 代码实现 → 参考各平台 SKILL.md
4. 错误处理 → 参考 troubleshooting 文档

### 场景 3: 跨平台优化决策
1. 数据汇总 → 使用统一数据模型
2. 归因分析 → 参考跨平台归因文档
3. 预算分配 → 参考统一出价框架
4. 执行调整 → 通过 API 脚本执行

## 关键对比

| 维度 | Google Ads | Meta | TikTok | DV360 |
|------|-----------|------|--------|-------|
| 数据精度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| API 稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 创意灵活性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 自动化程度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 适用场景 | 搜索+购物 | 社交+内容 | 短视频+直播 | 大型品牌 |
| API 方法数 | 407 | 728 | 324 | 178 |
| 深度文档 | 16 | 15 | 14 | 11 |

## 自测题

<details>
<summary>Q1: Google PMax 和 GMX 有什么区别？</summary>

**答案**：
- **PMax** (Performance Max)：Google 的全自动智能投放，覆盖 Search、Display、YouTube、Gmail、Maps
- **GMX** (General Merchandise eXperience)：PMax 的电商升级版，专门针对商品推广，集成 Merchant Center 数据
- **关键区别**：GMX 有商品级优化，PMax 是 campaign 级别

</details>

<details>
<summary>Q2: Meta CAVE 模型是什么？如何用于广告优化？</summary>

**答案**：
CAVE = Creative + Audience + Value + Efficiency
- **Creative**：广告素材效果
- **Audience**：目标受众精准度
- **Value**：用户生命周期价值
- **Efficiency**：投放效率
Advantage+ 利用 CAVE 进行自动优化，比传统人工投放效率高 20-30%

</details>

<details>
<summary>Q3: TikTok Spark Ads 和普通 Ads 有什么区别？</summary>

**答案**：
- **Spark Ads**：推广已有的有机视频（可以是达人内容），保留原生互动数据
- **普通 Ads**：从 0 创建的纯广告视频
- **优势**：Spark Ads 可以利用已验证的内容，降低创意成本，提高转化率

</details>

<details>
<summary>Q4: DV360 的 PG 和 PMP 核心区别是什么？</summary>

**答案**：
- **PG (Programmatic Guaranteed)**：100% 展示量保证，固定价格，适合品牌大额投放
- **PMP (Private Market Place)**：不保证展示量，有限竞争，适合获取优质库存
- **核心区别**：PG 是"买断"，PMP 是"优先购买权"

</details>

<details>
<summary>Q5: 跨平台归因为什么推荐使用 Shapley Value？</summary>

**答案**：
- 公平性：考虑所有可能的平台组合排列
- 科学性：基于合作博弈论，数学上最公平
- 适应性：可以处理任意数量的平台和 touchpoint
- 对比：时间衰减过于简单，Last Click 偏向最后一个触点

</details>

---

*本文档 v4.0 版本，于 2026-08-14 全面升级。*
