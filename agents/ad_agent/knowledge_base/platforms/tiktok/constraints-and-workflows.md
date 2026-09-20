---
schema_version: "1"
id: tiktok-ads-constraints-and-workflows
title: TikTok Ads 预算、定向与素材创建工作流
layer: platform
knowledge_type: constraint
platform: tiktok
source: TikTok Ads API 官方文档 + 当前 Capability schema
source_ref: "https://business-api.tiktok.com/portal/docs?id=1739385842588674"
version: "1.0.0"
confidence: 0.88
updated_at: "2026-09-08"
tags: [tiktok, budget, targeting, placement, spark-ads, catalog, workflow]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
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

## Commerce 与 Lead

- Product Sales 先验证 `catalog_id`、`product_set_id`、商品状态、落地页和商品选择；名字不能替代 ID。
- Lead 需要确认表单/页面、隐私政策、线索事件和回传范围；当前 Ads API 不支持的 Instant Page 管理不能伪造 CRUD。
- App 需要 app_id、操作系统、商店或深链、事件和归因来源；安装成功不代表应用内价值事件已稳定回传。

## 变更与失败恢复

写入默认 dry-run。超时或未知状态先 readback，已存在则核对或 update，不能重复 create。对限流和暂态网络错误做有界退避；参数、权限、资产不存在、政策拒审和账号资格错误要停止重试并返回具体缺口。
