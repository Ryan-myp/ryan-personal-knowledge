---
schema_version: "1"
id: dv360-constraints-and-workflows
title: DV360 预算、定向、创意与投放工作流
layer: platform
knowledge_type: constraint
platform: dv360
source: Display & Video 360 API 官方文档 + 当前 Tool Source schema
source_ref: "https://developers.google.com/display-video/api/concepts/targeting"
version: "1.0.0"
confidence: 0.88
updated_at: "2026-09-08"
tags: [dv360, budget, flight, targeting, brand-safety, creative, workflow]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-09-08"
---

# DV360 预算、定向、创意与投放工作流

## Preflight 顺序

```text
Partner / Advertiser scope
  -> Campaign / IO / Line Item parent
  -> flight、预算、计费/出价和采购类型
  -> targeting option lookup + assignment diff
  -> creative format、关联和审核状态
  -> schema + permission + dry-run
  -> confirmation + live write
  -> readback + delivery/report check
```

预算和日期可能由 IO 与 Line Item 分担。用户说“改预算”时，先确认改变 IO 总预算、Line Item 预算、日预算还是媒体成本上限；同时检查起止时间、时区、已消耗金额和剩余可交付量。不能把 IO 的预算直接覆盖成 Line Item 的预算。

## 定向 assignment

定向类型与选项是独立资源。先读取当前 assignment，再计算新增、保留和删除差异；选项 ID 必须来自正确的 advertiser/partner 范围。Geo、device、environment、audience、inventory、brand safety 和频控可能有组合限制，无法证明兼容时停在 dry-run，不假设平台自动处理。

## 创意生命周期

```text
asset uploaded -> creative definition -> associated to Line Item -> review pending -> approved/rejected -> eligible -> delivery
```

尺寸、时长、格式、媒体引用、点击/落地页、追踪和 advertiser 归属要先校验。审核 pending 不是失败，rejected 不是网络错误；拒审只生成修订与重新审核计划，不通过重复创建绕过政策。

## 故障恢复

异步报告和长任务要记录 definition、run/result 关联、状态、轮询次数、超时和错误摘要。未知写入状态先 readback；参数、权限、父级、定向组合和创意审核问题停止重试。所有写操作默认 dry-run，并经过 live 权限、确认、幂等和审计。
