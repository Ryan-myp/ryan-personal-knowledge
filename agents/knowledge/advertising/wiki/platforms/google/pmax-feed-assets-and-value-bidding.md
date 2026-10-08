---
schema_version: "1"
id: google-pmax-feed-assets-and-value-bidding
title: Google PMax 商品源、资产组与价值出价方法
layer: platform
knowledge_type: best_practice
category: optimization
subcategory: pmax-feed-assets-and-value-bidding
platform: google-ads
source: Google Ads API 与 Google Ads 官方文档
source_ref: "https://developers.google.com/google-ads/api/docs/performance-max/overview"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-09-08"
tags: [google-ads, pmax, performance-max, merchant-center, asset-group, value-bidding]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# Google PMax 商品源、资产组与价值出价方法

PMax 是跨库存的自动化 Campaign 类型，商品源、资产组、素材质量、转化信号、预算和价值目标共同影响交付。资产组不是简单的广告组替代物，商品、受众信号和素材承接必须与落地页和业务目标一致。

## 排查顺序

1. 确认 Campaign 类型、状态、预算、目标、账户时区和转化目标。
2. 检查 Merchant Center 商品源、商品批准状态、价格/库存、落地页和政策限制。
3. 检查 Asset Group 的最终 URL、文本/图片/视频资产、资产批准状态和主题分组。
4. 检查转化动作是否去重、延迟是否稳定、primary/secondary 口径是否清楚。
5. 再看展示、花费、价值、搜索分类/洞察、商品级表现和素材组合，不用单一 CTR 判断。

## 资产组设计

资产组应围绕清晰的商品或受众主题组织，让素材、页面和商品信息形成一致承诺。过度拆分会稀释学习信号，完全混合又会让预算和结果难以解释。新增资产前记录原有资产、主题、页面、商品范围和审核状态；替换素材后留出稳定观察窗口。

## 价值出价前提

价值优化需要可靠的转化价值、稳定的货币口径、合理的退款/取消处理和足够的成熟数据。目标 ROAS 过紧可能限制花费，目标过松可能牺牲利润；在信号不足时，先修事件质量和价值分布，不用虚假的 micro conversion 充量。价值是预测和归因的组合结果，要与真实订单 cohort 分开标记。

## 异常决策表

| 现象 | 先查 | 处理边界 |
|---|---|---|
| 不花费 | 商品批准、预算、资格、资产和目标 | 修交付前不调 ROAS |
| 花费有但转化少 | 转化目标、页面、事件延迟和价值 | 先确认信号不是丢失 |
| ROAS 高但规模小 | 目标过紧、库存容量、价值分布 | 小幅放宽并设护栏 |
| 商品点击好但购买差 | 价格、库存、页面、运费和承诺 | 不把点击当业务成功 |
| 改素材后波动 | 学习扰动、资产审核和流量混合 | 固定窗口复盘 |

## API 与安全执行

读取时用最小字段和有界日期范围，按 Campaign、Asset Group、Asset、Product/Listing 相关资源分层确认。变更先生成 dry-run 对比，列出父资源、字段掩码、资产影响、预算/目标变化和回退条件；不能用知识文档替代当前 Tool schema 的字段和权限校验。

## 官方参考

- [Performance Max overview](https://developers.google.com/google-ads/api/docs/performance-max/overview)
- [Asset groups](https://developers.google.com/google-ads/api/docs/performance-max/asset-groups)
- [Value-based bidding](https://support.google.com/google-ads/answer/2471188)
