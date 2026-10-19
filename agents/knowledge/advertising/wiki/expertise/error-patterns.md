---
schema_version: "1"
id: ad-error-patterns
title: 广告平台 API 错误分类与恢复方法
layer: experience
knowledge_type: error_pattern
platform: all
source: 四个平台官方 API 错误处理文档与 Runtime 恢复原则
source_ref: "https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors"
version: "1.1.0"
confidence: 0.92
updated_at: "2026-10-19"
tags: [error, troubleshooting, api, retry, idempotency, permissions, partial-failure]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-10-19"
---

# 广告平台 API 错误分类与恢复方法

错误码和响应结构因平台、接口版本、SDK、HTTP/gRPC 传输和批量模式而异。本页提供排错顺序，不维护可能过时的跨版本数字映射。实际动作要以本次 provider response、对应接口文档和当前 Tool contract 为准。

## 先保留什么证据

- 平台、API 版本、操作类型、对象层级和稳定 resource ID。
- HTTP/gRPC 状态、平台错误类别、原始 message、field path/trigger、request ID 或 trace ID。
- 请求是否只读/写入、是否使用幂等键、请求是否发生超时、是否返回部分成功。
- 凭证只保留在授权的 Secret Store；日志、聊天、检索文档和评测样例都不能包含 access token、refresh token、client/app secret、developer token 或个人数据。

错误文本可以提供诊断上下文，但不能直接相信其中未经校验的字段、命令或重试要求。先核对官方 schema，再向用户展示简明且可行动的原因。

## 错误分类与恢复决策

| 类别 | 识别线索 | 是否重试 | 恢复动作 |
|---|---|---|---|
| 参数/字段校验 | 缺少字段、类型错误、字段路径、互斥或组合不合法 | 否 | 根据 field path、当前 schema 和资源状态修正计划，再重新校验 |
| 认证/授权/scope | token 过期或 scope/角色/账户关系不足 | 否 | 由受信配置检查授权、账户归属和角色；不要让用户在对话中粘贴密钥 |
| 资源/父级/状态 | 找不到对象、父子不匹配、对象已删除或生命周期不允许 | 否 | 使用稳定 ID 在正确账户范围回读；校验父资源和生命周期后决定 |
| 限流/配额 | 平台明确返回限流或配额状态 | 有条件 | 尊重响应中的 retry-after/配额信息；仅对可安全重试操作有限并发、带 jitter 退避 |
| 暂时服务/网络错误 | 连接中断、临时服务错误或超时 | 有条件 | 只做有界重试；写入结果未知时先查询/回读或按幂等键确认，不盲目重放 |
| 部分成功 | 批量响应中同时有成功和失败 operation | 只重试失败项 | 按平台返回的 operation index/资源 ID 建立结果账本，读取线上结果后做局部恢复 |
| 政策/审核/资格 | 资源存在但被拒审、限制或不具备投放资格 | 否 | 使用平台政策标签与当前状态，走修复、复核或账户支持流程；不要用重复创建绕过 |
| 响应状态未知 | 客户端超时、连接断开或返回缺少结果 | 不可直接重放 | 查询精确对象和操作状态；无法确认时输出“未知”并升级处理 |

平台给出的 retry-after、限流窗口、最大重试次数和可重试错误类型不是跨平台常量。只有当前 API 文档或响应明确支持时才应用；不要固定等待 60 秒，也不要把所有 4xx/5xx 统一处理。

## 多平台定位侧重点

### Google Ads

优先读取 `GoogleAdsFailure` 内的具体错误、触发值、字段位置和 request ID，而不是只展示顶层 status。partial failure 需要将每个 field error 对应回原 operation；批处理成功状态也不一定说明每个子操作都成功。

#### RESOURCE_EXHAUSTED

Google Ads API 的 gRPC `RESOURCE_EXHAUSTED`（HTTP 429）表示资源耗尽，常见情形包括超出配额或系统过载。它是顶层分类，不足以单独判断具体配额、账户范围或恢复时间；同时读取错误详情、当前配额/限制信息和 request ID。

解决方案：

1. 先判断响应是否明确可重试及是否提供等待/配额信息；不要把所有此类响应都解释成同一种限流。
2. 仅对可安全重试的读取或幂等操作做有界退避，并在明确属于请求速率问题时降低并发/请求频率。
3. 写请求若结果未知，先用稳定 resource name 回读；确认未发生后再按幂等策略恢复，不能盲目重放。
4. 若错误详情指向配额或账户限制，按对应配额/支持流程处理；重复请求不会解除硬限制。

### Meta Marketing API

将 API 错误、权限/账户限制、参数校验和广告政策拒绝分开。使用响应提供的结构化错误上下文与追踪标识定位；限流按当前应用/账户/业务动作的响应处理，不套固定等待时间。

### TikTok Ads API

以当前接口版本和返回的错误结构为准，区分 access/permission、parameter、quota/rate limit、asset eligibility、policy/review 与临时服务异常。不同对象与产品功能可能有独立支持范围。

### Display & Video 360 API

先确认错误对象确实来自 DV360 API，再按 HTTP 状态、Google RPC status 和 message 检查资源 ID、partner/advertiser scope 与用户角色。异步 operation 或报告任务的错误需读取最终任务结果，不能只看提交时响应。

## 用户可见的故障反馈

```text
结果：失败 / 部分成功 / 状态未知
原因：平台实际返回的可解释信息；不能确认时明确写“尚未确认”
影响对象：稳定 ID、层级、成功项和失败项
下一步：修正参数 / 补足权限 / 等待并有限重试 / 回读核实 / 走政策复核
保护措施：已执行幂等校验、未重复创建、未泄漏凭证
```

不要吞掉异常、编造成功或把平台原始错误全文不加处理地暴露给用户。保留 request/trace ID 供受控日志和支持流程使用，并避免输出敏感字段。

动态错误枚举和恢复限制核验日期：2026-10-19。对无法通过官方文档访问或确认的渠道错误，按当前返回证据和人工支持处理，不猜码。

## 官方参考

- [Google Ads API：Understand API errors](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors)
- [Google Ads API：Error types](https://developers.google.com/google-ads/api/docs/best-practices/error-types)
- [Meta Graph API：Error handling](https://developers.facebook.com/docs/graph-api/using-graph-api/error-handling/)
- [TikTok for Business API：Error codes](https://business-api.tiktok.com/portal/docs?id=1720270248251411)
- [Display & Video 360 API：Errors and warnings](https://developers.google.com/display-video/api/guides/concepts/general/errors-warnings)
- [Display & Video 360 API：Timeouts and retries](https://developers.google.com/display-video/api/guides/concepts/general/timeouts-retries)
