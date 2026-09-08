# LLM Wiki 知识库升级总结

## v2.0.0 · 2026-09-08

本次升级把四渠道知识从零散的层级/约束示例，扩展为可用于广告规划、执行前检查、运行中优化和归因复盘的专业知识包。运行时读取 `knowledge_base/**/*.md`，旧 JSON 文件仅保留作历史兼容材料，不参与 Wiki 检索。

## 新增内容

| 范围 | 新增主题 |
|---|---|
| Google Ads | Search、Shopping/PMax、Video/App 的目标选择；Campaign/AdGroup/Ad/Keyword/Asset 关系；出价预算；转化、增强型转化、离线回传、GAQL、报表、配额与故障诊断 |
| Meta Ads | Business/Ad Account/Campaign/Ad Set/Ad；ODAX 目标；预算、特殊广告类别、受众、Catalog；Pixel/CAPI 去重、事件质量、Insights breakdown、异步报表和素材疲劳 |
| TikTok Ads | Advertiser/Campaign/Ad Group/Ad；普通素材、Spark、Smart+、Commerce、Lead/App；Events API 身份与去重、归因、报表维度、预算诊断和创意优化 |
| DV360 | Partner/Advertiser/Campaign/IO/Line Item；Deal/竞价和采购模型；Targeting Assignment；Floodlight 归因；Creative 审核生命周期；异步 Report 与交付优化 |
| 跨平台业务 | 四平台专业总览、层级对照、行业打法、预算出价、受众策略、创意测试、数据契约、证据驱动诊断、归因与增量评估 |
| 经验方法 | 全链路诊断树、实验卡片、学习期管理、放量阶梯与安全执行边界 |

## 知识质量策略

1. **平台事实与运营建议分开**：层级、资源依赖和字段边界参考官方文档与当前 Capability；策略文档表达判断框架，不把经验写成保证。
2. **动态能力不硬编码**：objective、placement、targeting option、report fields、规格和可写范围以当前账户、地区、API 版本与 Registry Tool schema 为准。
3. **完整链路而非指标清单**：每个专题同时覆盖目标、资源、约束、工作流、指标、诊断、失败恢复和回查。
4. **避免虚假精确**：不使用没有账户/样本/时间窗口背景的固定 benchmark；建议用当前账户历史、实验或后端业务结果建立基线。
5. **安全可执行**：知识库是 advisory context；写操作默认 dry-run，live 需要权限、白名单、确认、幂等和审计。

## 现有正式文档

截至 2026-09-08，运行时可加载 64 个业务 Markdown 文档：Google 13 个、Meta/TikTok/DV360 各 11 个，跨平台业务 14 个，经验方法 4 个。新增四平台 Canonical Runbook、四平台专业总览、转化数据契约、事件去重、分段报表、Deal/Floodlight、边际预算、证据驱动诊断和异步失败恢复专题。Wiki 维护文档不进入业务检索；完整导航见 [`index.md`](index.md)。

本轮同时加入 `QUALITY_STANDARD.md`、24 条检索评测 case 和 `ad-agent-knowledge-check`，把来源、可执行性、检索命中、跨平台误召回和治理要求变成可重复验收项。

## 检索与维护

- 文档按标题章节切块，使用 SQLite FTS5 + BM25 风格排序，标题、章节和标签会加权；不接入 Embedding 或向量数据库。
- SQLite 不支持 FTS5 时使用受限词法检索回退；这不改变文档格式和发布流程。
- 只有 `status: published` 的文档会进入内置检索；每篇文档必须有稳定 `id`、版本、来源、置信度和更新时间。
- 平台 API 或政策变化时，新增语义化版本并记录变更来源、受影响平台、字段/Tool 契约、迁移与回滚方式。
