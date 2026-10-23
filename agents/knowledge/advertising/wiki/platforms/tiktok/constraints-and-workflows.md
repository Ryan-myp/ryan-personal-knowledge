---
schema_version: "1"
id: tiktok-ads-constraints-and-workflows
title: TikTok Ads 预算、定向与素材创建工作流
layer: platform
knowledge_type: constraint
platform: tiktok
source: TikTok for Business 官方 Ads API 与审核帮助文档
source_ref: "https://ads.tiktok.com/resources/help/article/one-click-appeal-for-other-ad-types?lang=en"
version: "1.1.0"
confidence: 0.88
updated_at: "2026-10-19"
tags: [tiktok, budget, targeting, placement, spark-ads, catalog, workflow, review, rejection, appeal]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-10-19"
---

# TikTok Ads 预算、定向与素材创建工作流

## 标准创建顺序

```text
Advertiser scope
  -> Campaign objective / campaign type
  -> Ad Group promotion / budget / schedule / placement / targeting / bid
  -> media / identity / Pixel / app / catalog lookup
  -> Ad format + policy preflight
  -> dry-run + confirmation
  -> live create/update
  -> readback + audit
```

预算模式、排期、地域最低预算、优化目标、计费事件和出价之间有条件依赖。用户未说明币种、时区、开始时间、结束时间、地区和投放目标时，不要用默认值代替；`SCHEDULE_FROM_NOW` 与固定时间不是同一语义。

## 定向与版位

地域、语言、设备、操作系统、兴趣/行为、受众、版位、年龄和性别等字段可能来自动态目录。先通过当前账户/地区可用的 lookup 得到 ID，再校验组合；模型猜出的兴趣名称或区域编码不能直接写入 Ad Group。定向越窄不一定越好，先确认业务约束和可交付曝光，再决定 broad、兴趣或再营销。

## Spark Ads

Spark 是对原生 TikTok 内容的授权使用，不等同于上传普通视频。创建前确认 creator/identity 授权、item/post 引用、授权有效期、互动使用规则、advertiser 归属和 tracking。素材存在、授权有效、广告创建、审核通过和开始投放是不同状态；无授权时不能自动降级为普通视频来绕过阻塞。

## 商品销售与线索

- Product Sales 先验证 `catalog_id`、`product_set_id`、商品状态、落地页和商品选择；名字不能替代 ID。
- Lead 需要确认表单/页面、隐私政策、线索事件和回传范围；当前 Ads API 不支持的 Instant Page 管理不能伪造 CRUD。
- App 需要 app_id、操作系统、商店或深链、事件和归因来源；安装成功不代表应用内价值事件已稳定回传。

## 变更与失败恢复

写入默认 dry-run。超时或未知状态先 readback，已存在则核对或 update，不能重复 create。对限流和暂态网络错误做有界退避；参数、权限、资产不存在、政策拒审和账号资格错误要停止重试并返回具体缺口。

## 广告/广告组拒登与 One Click Appeal

- 从 Campaign 下的 Ad 或 Ad Group 读取平台拒登详情、政策说明与状态；同时核对该 Ad Group 中所有广告、素材、落地页和相关身份资产。
- 若确有问题，编辑具体内容并重新提交审核；只有怀疑误判且能说明证据时才申请复核。
- TikTok 当前 One Click Appeal 帮助文档说明：从 Ad 或 Ad Group 提交的复核可能覆盖整个 Ad Group；复核进行期间不能编辑该广告组或其广告。提交前必须确认整个组内容并保存当前版本。
- 同一文档说明，如果账户处于 suspended 状态，需先处理账户暂停状态，才能提交该流程的申诉。入口资格与当前账户状态可能不同，应以当下 UI 和官方说明为准。
- 审核通过后仍须回读 Campaign/Ad Group/Ad 状态、排期、预算、身份、事件和实际 delivery；不能把复核结果当作开始投放的证据。

## 官方审核参考

- [What to do if your ad or ad group was rejected](https://ads.tiktok.com/resources/help/article/what-to-do-if-your-ad-or-ad-group-was-rejected-on-tiktok)
- [One Click Appeal for Other Ad Types](https://ads.tiktok.com/resources/help/article/one-click-appeal-for-other-ad-types?lang=en)
