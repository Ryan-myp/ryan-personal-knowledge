# LLM Wiki 知识库升级总结

## v2.2.0 · 2026-09-18

- 增加租户 raw source 存储：正文、media type、来源引用和 SHA-256 持久化，按租户去重且正文不可变。
- 增加 `POST /knowledge/raw`、raw 状态查询和 `knowledge.ingest` durable task。
- 增加结构化 LLM ingest contract：只接受受限 JSON，生成页面前先完整校验，产物默认是 draft。
- 派生页保留 `source_ref`、`derived_from`、`raw_sha256`、`wikilinks` 和 `wiki_type`，Runtime 只检索已发布页面。
- SQLite schema version 提升到 19；MySQL 适配器增加对应迁移。

## v2.3.0 · 2026-09-20

- raw source ingest 增加 Store 原子 claim，防止同一 source 被并发 worker 重复处理。
- 增加 `ingest_attempts`、`ingest_started_at`、`ingest_finished_at`，失败 source 可安全重试，`draft_ready` 默认幂等拒绝。
- 增加 stale ingest recovery，worker 中断后的过期 claim 会回到 `failed`，允许下一次任务重试。
- SQLite/MySQL schema version 提升到 20；Plugin lifecycle 增加 Runtime 级串行化和卸载失败快照回滚。

## v2.1.0 · 2026-09-17

本次升级把现有广告 Agent Wiki 对齐到 Karpathy 风格的知识对象模型，同时不搬动已经被 Skill、来源引用和 Runtime 使用的领域路径。

### 结构与运行时

- 增加 `raw/`、`entities/`、`concepts/`、`comparisons/` 和 `queries/`。
- 增加四个平台实体页与跨平台对比页；`platforms/`、`business/`、`expertise/` 继续作为概念页的稳定存储。
- 增加 `wiki_type` 元数据；`raw` 与 `system` 默认不进入 Runtime。
- Runtime 继续只通过 `MarkdownWikiKnowledgeProvider` 读取已发布文档，不创建 Tool、不执行知识文件。
- `wiki-engine/` 只保留为通用 ingest/query/lint 兼容工具，并与 YAML frontmatter 和标准对象类型对齐。

### 验收

- 运行时加载 69 个发布文档，元数据校验通过。
- 知识质量：Hit@3=1.000、MRR=0.958、跨平台泄漏=0。
- Agent 全量测试：810 passed。

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

1. **平台事实与运营建议分开**：层级、资源依赖和字段边界参考官方文档与当前 Tool Source；策略文档表达判断框架，不把经验写成保证。
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
