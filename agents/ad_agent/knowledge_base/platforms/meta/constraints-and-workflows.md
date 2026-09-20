---
schema_version: "1"
id: meta-ads-constraints-and-workflows
title: Meta Ads 预算、定向与创建工作流
layer: platform
knowledge_type: constraint
platform: meta
source: Meta Marketing API 官方文档 + 当前 Tool Source schema
source_ref: "https://developers.facebook.com/docs/marketing-api/campaign-structure/creation"
version: "1.0.0"
confidence: 0.88
updated_at: "2026-09-08"
tags: [meta, budget, targeting, optimization, special-ad-category, workflow]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# Meta Ads 预算、定向与创建工作流

## 创建顺序

```text
Ad Account scope
  -> Campaign objective / special category
  -> Ad Set budget / schedule / optimization / bid
  -> targeting 与 exclusions
  -> Page/IG、Pixel、Catalog/Form、creative lookup
  -> schema + policy + permission preflight
  -> dry-run + confirmation
  -> live create/update
  -> readback + audit
```

不能因为用户说“建一个 Ad”就跳过父级。未知状态先 readback，不能盲目重复 create；批量创建要保存每个 Campaign、Ad Set、Ad 的父级和部分失败结果。

## 预算与出价

- 先确认预算放在 Campaign 还是 Ad Set、daily 还是 lifetime、币种、排期与总预算上限。
- 预算集中分配适合让系统在 Ad Set 间寻找机会；需要严格控制国家、漏斗或实验预算时保留 Ad Set 边界。
- Lowest cost、cost cap、bid cap 等策略不是同义词，分别代表系统探索程度与成本约束；目标过紧可能导致花费不足，目标过松可能损失效率。
- 优化事件必须在 Pixel/CAPI 真实稳定后再升级到更深层事件；事件数量不足时应先保证信号质量，不要用虚假的 micro conversion 凑数据量。

## 定向约束

Broad/Advantage+、兴趣、行为、地域、年龄、再营销和 Lookalike 是策略工具，不是越多越好。受众过度叠加会导致竞价内耗和报告难以解释；冷启动时可将一个探索单元与一个可控单元并行，而不是无限拆分。

特殊广告类别（如住房、就业、信贷等）会限制年龄、性别、地域半径或部分受众能力。涉及特殊类别必须先识别政策类别，再根据当前账户和接口返回的允许字段构建，不得通过换名称规避限制。

## 素材与审核

Ad Creative 的身份、媒体、文案、链接、CTA、目录和追踪组合要在 Ad 之前校验。上传成功、Creative 创建成功、Ad 创建成功、审核通过、开始投放是五个不同状态；拒审时保留平台原因和修订方向，不用重复创建绕过审核。
