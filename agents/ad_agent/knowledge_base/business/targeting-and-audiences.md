---
schema_version: "1"
id: cross-platform-targeting-and-audiences
title: 跨平台受众、定向与增量策略
layer: business
knowledge_type: targeting_strategy
platform: all
source: 四平台定向官方文档 + 隐私安全投放方法论
source_ref: agents/ad_agent/knowledge_base/business/targeting-and-audiences.md
version: "1.0.0"
confidence: 0.82
updated_at: "2026-09-08"
tags: [targeting, audience, broad, lookalike, remarketing, exclusion, incrementality]
status: published
---

# 跨平台受众、定向与增量策略

## 受众分层

```text
冷启动：broad / contextual / interest / behavior
探索扩量：lookalike / modeled / platform expansion
再营销：site/app engaged、商品浏览、加购、线索未成交
价值分层：高 LTV、复购、已成交、流失/排除
```

平台受众对象的 ID、生命周期、匹配率和可用时间不同。名称不能替代动态 lookup，不能把一个平台的 audience ID 复制到另一个平台，也不能把上传成功描述为立即可投放。

## 定向选择原则

- 冷启动先保留一个足够宽且事件清晰的探索单元，再用受众切片验证假设。
- 再营销要设排除：已购买用户、已提交线索、当前客户或不符合服务地域者，避免浪费与重复计数。
- Lookalike/类似受众的种子质量通常比数量更重要；按价值或合格事件建种子，记录窗口和来源。
- 特殊广告类别、隐私政策、地区法律和平台策略可能限制年龄、性别、地域、兴趣或匹配方式。
- 受众越窄不代表越精准；以交付、转化质量、边际成本和增量结果共同判断。

## 重叠与增量

用受众覆盖、频次、竞价成本和排除逻辑识别重叠。对品牌词、再营销和高意向人群，平台归因可能高估本来就会转化的人；关键预算应使用 holdout、geo test、转换提升或其他可审计实验估计增量，不能只看 last-click。

## 数据治理

第一方数据上传前明确授权、用途、保留周期和哈希边界；不要在 Skill、Prompt、日志、知识库或工具结果中保留原始邮箱、电话或用户明细。用户列表、CAPI、Pixel 和平台 Audience 的成功状态要分为上传、匹配、可用、进入投放和归因可见。

## 受众评估卡

每个受众都记录来源、构建窗口、事件定义、排除条件、市场、预计规模、同意状态、刷新频率和失效条件。评价顺序是：

1. **资格**：平台和地区允许使用，规模与隐私门槛满足。
2. **可交付**：有足够库存，频次和重叠没有造成异常集中。
3. **效率**：在同一归因窗口下比较边际 CPA/ROAS 和有效率。
4. **增量**：品牌词、再营销和高意向人群优先使用 holdout/geo 等设计。
5. **长期价值**：按 cohort 看付费、复购、留存、退款和毛利。

受众变小先查事件延迟、匹配、同意、刷新和排除逻辑；受众变大先查质量、重复和隐私边界。不能把受众规模或平台匹配率直接当作增量规模。
