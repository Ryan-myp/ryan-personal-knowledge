# LLM Wiki 更新日志

## 2026-09-20

- 为历史页面补齐 `source_kind`、`authority`、`evidence_level`、`last_verified_at`，
  并将自引用 `source_ref` 改为可追溯的 repository/internal provenance；正文和发布状态未改动。
- raw ingest 增加原子 claim、attempt 记录和 stale recovery；Runtime Skill lifecycle 增加
  串行化与失败回滚。

## 2026-09-18

### 全库治理与来源证据升级

- ✅ 增加全库审计：frontmatter、重复 ID、目录对象类型、来源自引用、断链、孤立页、检索案例 ID 和平台覆盖。
- ✅ 增加 `source_kind`、`authority`、`evidence_level`、`last_verified_at` 的兼容读取和 citation 输出。
- ✅ 修正检索评测中漂移的文档 ID，避免用不存在的旧 ID 误判召回质量。
- ✅ `ad-agent-knowledge-check` 现在同时执行检索质量门和全库审计。

## 2026-09-17

### Karpathy 对象层兼容升级

- ✅ 增加 `raw/`、`entities/`、`concepts/`、`comparisons/` 和 `queries/` 对象目录。
- ✅ 增加四个平台实体页和一个跨平台对比页；原有 `platforms/`、`business/`、`expertise/` 路径保持兼容。
- ✅ `MarkdownWikiKnowledgeProvider` 增加 `wiki_type`、对象类型过滤、重复 ID/状态/置信度/来源校验。
- ✅ Runtime 默认跳过 `raw/`、`system` 和导航 README，避免原始资料或维护说明进入模型上下文。
- ✅ 统一 `wiki-engine` 的 YAML frontmatter、递归目录加载、日期写入和标准对象类型识别。
- ✅ 知识库运行时文档增至 69 篇；知识质量门禁 Hit@3=1.000、MRR=0.958、跨平台泄漏为 0。

## 2026-09-08

### 四渠道专业知识扩充

- ✅ 新增 Google Ads 策略/优化、转化/GAQL/诊断知识。
- ✅ 新增 Meta 的账户层级、ODAX 目标、预算/定向约束、Catalog、Pixel/CAPI、Insights 与创意优化知识。
- ✅ 新增 TikTok 的 Campaign/Ad Group/Ad、Smart+/Spark、Commerce、事件、报表和素材测试知识。
- ✅ 新增 DV360 的 Partner/Advertiser、Campaign/IO/Line Item、Targeting Assignment、Creative 审批和异步报告知识。
- ✅ 新增跨平台层级对照、行业打法、预算出价、受众定向、创意测试、归因增量、诊断决策树和实验设计。
- ✅ 更新索引与使用说明，明确 Markdown + SQLite FTS5/BM25 是当前唯一运行时知识源；旧 JSON 仅作历史兼容备份。
- ✅ 隔离 Wiki 索引、日志、架构和规范文档，清理旧 JSON 目录，避免维护信息混入业务知识目录。
- ✅ 新增电商利润、App/游戏 LTV、B2B CRM 线索、渠道组合与边际效率四篇深度行业知识。
- ✅ 深化四个平台的测量、报表与优化知识：Google 转化/增强型转化/GAQL，Meta CAPI 去重/Insights，TikTok Events API/归因/报表，DV360 Floodlight/Deal/竞价。
- ✅ 运行时业务 Markdown 增至 58 篇；平台知识统一补充资源模型、数据契约、诊断顺序、失败恢复和 API 安全边界。
- ✅ 新增跨平台《证据驱动诊断与决策卡》，统一数据成熟度、指标口径、假设验证、放量阶梯、置信度和 Agent 输出格式。
- ✅ 新增《四大广告平台 Agent 专业知识总览》，串联统一对象模型、四平台差异、生命周期、测量归因、优化决策、诊断卡和标准输出结构。
- ✅ 新增四平台 Canonical Runbook、知识质量标准和 24 条检索评测 case；新增 `ad-agent-knowledge-check`，支持发布前检查文档门禁与 Hit@3/MRR/跨平台泄漏。

### 内容边界

- 所有平台动态枚举、资源 ID、权限和可执行能力仍以当前 Provider Capability/Tool schema 为准。
- 文档不承载凭证、原始 PII、MCP、Provider client 或执行脚本。
- 文档中的优化建议是方法论，不承诺固定结果或跨账户通用 benchmark。

## 2026-08-26

### 架构升级

- ✅ 迁移到 Karpathy LLM Wiki 标准架构
- ✅ 知识库从 JSON 格式改为 Markdown 格式
- ✅ 新增索引文件 index.md
- ✅ 新增日志文件 log.md

### 知识库内容

- 平台层: Google/Meta/TikTok/DV360 层级结构、工作流、约束规则
- 经验层: 最佳实践、错误模式、案例研究
- 业务层: 出价策略、定向策略、素材指南

## 2026-08-14

### 初始版本

- 创建 Google Ads 知识库
- 创建 Meta Marketing API 知识库
- 创建 TikTok Ads 知识库
- 创建 DV360 知识库
