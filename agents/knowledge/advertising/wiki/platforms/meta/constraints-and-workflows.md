---
schema_version: "1"
id: meta-ads-constraints-and-workflows
title: Meta Ads 预算、定向与创建工作流
layer: platform
knowledge_type: constraint
platform: meta
source: Meta Marketing API 与 Meta Advertising Standards 官方资料
source_ref: "https://storage.googleapis.com/understanding_meta_advertising_standards/Understanding_Meta_Advertising_Standards.pdf"
version: "1.1.0"
confidence: 0.88
updated_at: "2026-10-19"
tags: [meta, budget, targeting, optimization, special-ad-category, workflow, review, rejection, appeal]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-10-19"
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

### 拒登和账户限制

- 在 Ads Manager 当前状态/Delivery 信息中定位具体对象，读取广告被拒原因；分别检查文案、图片/视频、CTA、目标页和广告所引用的 Page、Instagram identity、商品或表单。
- 若内容确有问题，修复对应素材或落地页，再按平台要求重新审核；若判定疑似错误，带上对应政策点和事实证据，通过 Meta 当前 Business Support / Account Quality 支持入口查看复核选项。
- 单条广告拒绝与 Ad Account、Page 或 Business 资产限制范围不同。先确认被限制主体与关联资产，不能只重建单条广告，也不能以换账户、换身份绕开审核。
- Meta 的支持入口与界面文案会变化；提交前检查当前界面是否提供复核，以及申诉对象、状态和范围。
- 状态解除后重新检查父级、预算、排期、素材关联和实际交付；“审核通过”本身不证明已投放。

该排查顺序与素材/目的地检查参考 Meta 官方 Advertising Standards 培训资料；具体资格和支持入口以账户当前界面为准。
