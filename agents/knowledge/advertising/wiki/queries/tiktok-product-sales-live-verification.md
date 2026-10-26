---
schema_version: "1"
id: tiktok-product-sales-live-verification
title: TikTok Product Sales 测试账号逐层验收与商品选择失败
layer: platform
wiki_type: query
knowledge_type: test_account_e2e
category: campaign_operations
subcategory: product-sales-verification
platform: tiktok
source: 仓库内 TikTok Product Sales 测试账号验收记录
source_ref: agents/docs/advertising/campaign-validation-20261026.md
source_kind: code
authority: repository
evidence_level: reviewed
last_verified_at: "2026-10-26"
version: "1.0.0"
confidence: 0.95
updated_at: "2026-10-26"
tags: [tiktok, product-sales, product-set, catalog, live-e2e, recovery]
status: published
---

# TikTok Product Sales 本轮通过到哪一层？

截至 2026-10-26，测试账号已用 live `/chat` 在暂停状态创建 Campaign
`1880083317565154` 和 Ad Group `1880083336090337`，并完成改名与独立回读。
**Ad 没有创建成功**，不能把父级通过说成 Product Sales 完整模板通过。

第一次 Ad 尝试因 BC_AUTH_TT 帖子与 Identity 不匹配被拒；换已核验的
CUSTOMIZED_USER 与暂停测试追踪参数后，Provider 返回
`Invalid product selection`。当前关联 Catalog 的 Product Set
只读列表为 0。这是该测试账号的观测，不代表 TikTok Product Sales
普遍不可用，也不代表无需核实其他商品选择前置条件。

## 如何恢复

1. 先从 `provider_live_e2e_memory.json` 和观察账本读取最新父级 ID、
   模板摘要、失败状态；再独立查询 Campaign/Ad Group 状态与账户归属。
2. 由测试账号所有者提供有效商品选择，使用已注册只读 Tool 核验
   Catalog / Product Set 和所需权限；不在此验收范围内创建或修改 Catalog。
3. 消除未知写入状态后，仅续建缺失的 `DISABLE` Ad 并回读其父级、
   投放状态和 Provider 结果；绝不重放整张创建卡。
4. 如果商品资源仍无效，报告阻塞和所需输入，不把 dry-run、LLM 文字
   或父级成功冒充完整三层 E2E。

原始 HTTP 与 Run 事件只保留在本机 ignored 的 `outputs/`；本页是
脱敏摘要，具体参数以当前模板和 Tool schema 为准。
