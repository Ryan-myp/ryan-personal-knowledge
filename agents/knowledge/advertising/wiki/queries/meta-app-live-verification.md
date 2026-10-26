---
schema_version: "1"
id: meta-app-live-verification
title: Meta App Promotion 测试账号模板与逐层验收边界
layer: platform
wiki_type: query
knowledge_type: test_account_e2e
category: campaign_operations
subcategory: app-promotion-verification
platform: meta
source: 仓库内 Meta App Promotion 测试账号验收记录
source_ref: agents/docs/advertising/campaign-validation-20261026.md
source_kind: code
authority: repository
evidence_level: reviewed
last_verified_at: "2026-10-26"
version: "1.0.0"
confidence: 0.95
updated_at: "2026-10-26"
tags: [meta, app-promotion, template, live-e2e, readback, recovery]
status: published
---

# Meta App Promotion 原生一键 live 模板通过了吗？

截至 2026-10-26，当前内置模板参数已通过三层 dry-run；
测试账号的 Campaign、Ad Set、Ad 均已通过受控 live 工具分层创建、
改名和独立回读。**原生一键 live 模板链仍未完整通过**：
第一次请求在 Tool-call 生成阶段超时且未发现写入；对账后重试，
Campaign 创建成功，驱动再次提交整卡触发重复写门禁。

子级随后在既有暂停 Campaign 下逐层续建，不能把“分层创建成功”
说成“原生一键成功”。Ad 配置 `PAUSED`，但 Provider 回读的
`effective_status=IN_PROCESS`；不要把这两种状态混为一谈。

## 下次如何验证

1. 从 `provider_live_e2e_memory.json` 读取最新资源 ID、模板摘要和
   observation，并用当前账户只读查询父子归属、配置/有效状态。
2. 已创建任一层时只恢复缺失子级；超时或未知效果先按名称/ID 对账，
   不盲重试、不覆盖已存在的 Campaign。
3. 原生一键链仍需在明确授权且完成部分写保护检查后单独验收；
   dry-run、分步 Tool 和历史资源不可替代该结论。

三个渠道删除 Tool 仍未开启 live；本页不表示 Meta 删除已通过。
本页只记录受控测试账号的证据边界，实际参数以当前 Tool schema 为准。
