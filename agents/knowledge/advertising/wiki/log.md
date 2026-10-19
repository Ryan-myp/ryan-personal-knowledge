# LLM Wiki 更新日志

## 2026-10-19

- 新增全漏斗投放规划、转化信号/CRM 回传排障、商品目录/Feed 质量运营三篇跨平台实战知识，明确业务证据、平台动态能力和隐私边界。
- 新增 3 条检索回归用例覆盖规划、转化质量与商品目录；知识库文档总量更新为 74 篇。
- 修复模型以 Harmony 工具协议文本泄露的情况：识别截图中的工具协议、只允许一次受限重试，绝不将协议文本解析或执行。
- 对模型回复与历史回放移除 `<think>` 私密段；将上游工具路由 `40400 / invalid_user_id` 映射为安全、可操作的错误说明，不暴露原始协议。
- 保持知识检索 tenant scope 来自可信 Runtime principal；错误发生在外部模型服务的工具路由文本中时明确告知本地知识 Tool 未执行。

## 2026-10-18

- 四个平台实体页增加经项目内 Runbook 复核的中文概览与专题导航，明确平台原生能力和 Agent 当前 Tool 覆盖的边界；各实体页升级到 `1.1.0`。
- 检索切块跳过只含链接/URL 的参考或知识导航章节，避免宽泛渠道查询把链接列表当成知识正文；来源仍保留在结果 citation 元数据中。
- 增加四条自然语言渠道基础知识检索评测，检查首位实体页和参考章节泄漏；补充“讲下相关知识/介绍基础知识”触发回归，确保解释请求不把账户操作 Tool 暴露给模型。
- 根据 Meta“投放目标”对话整理一篇可复用 Query 页面，按业务结果区分六类 Objective，并澄清 Catalog Sales、Messages、Conversion 与 Ad Set 优化目标的层级。
- 对照 Meta 官方 Business 目标入口及官方 Marketing API SDK；动态可用组合仍要求按当前账户、API 版本和 Tool schema 验证。
- Meta Skill 增加目标讲解回答结构与固定阈值、能力清单边界。
- 新增 4 条 Meta 目标选择检索回归用例；运行前 Hit@3 从 1.000 降至 0.879，新增 Query 后复测。
- Wiki 运行时文档统计更新为 71 篇。

## 2026-10-13

- 将创意路线图、按探索/扩量状态规划、制作产能约束、Hook 漏斗诊断和复盘闭环
  蒸馏进 `creative-strategy` advisory Skill 与现有跨平台创意 Wiki；原有 channel Skill
  与 Tool schema 仍是格式/执行能力来源。
- 补全账户审计 Pass/Fail/Unknown/N/A、健康度与证据覆盖率分离，以及不完整来源不计零分的规则。
- 补充实验 MDE/统计功效、效应大小、重复查看和多重比较边界；补充平台归因、MTA、MMM
  与增量评估的适用边界。
- 增加创意路线图、审计覆盖率、实验统计边界和归因/增量问题的检索回归用例。
- 标明 `marketingskills` 等上游来源与许可；未复制集成脚本、资源文件或任何可执行入口。
- 增强 Google Ads 报表诊断：说明搜索词报告可能因隐私标准省略低活动查询，并要求用口径兼容的总点击量计算可见覆盖率；不将可见查询推算成完整搜索需求。
- 明确转化列语义、按转化动作分段后的行粒度和全零行省略，以及数据延迟和日期口径边界。
- 记录无 Provider client 返回的 simulated/offline 报表不是测试账户的真实证据；缺少可信来源时归为 Unknown。
- 新增 `account-diagnostics` advisory Skill，在 Skill 正文提供通用审计规则，并按请求加载 Google 报表解读 reference；不增加 Tool/API。
- 将本地 `ab-testing`、`attribution`、`analytics` 方法蒸馏为
  `experimentation-design`、`measurement-attribution`、`measurement-instrumentation`
  三个标准广告 advisory Skills；Scenario 自动发现、references 按请求加载，均不增加 Tool、
  外部集成或账户权限。
- 为三类测量 Skills 增加运行时召回、reference 选择、内置目录版本和零 Tool 权限回归测试；
  Wiki 索引补充问题路由，保留 Wiki 作为细节知识来源。
- 增加账户诊断 Skill 行为测试与 Google 报表知识检索回归用例。
- 扩展 `account-diagnostics` 到 Meta Insights，补充 Campaign/Ad Set/Ad 粒度、actions/action_values、数据完整性和归因解释；明确当前 Meta report Tools 尚未暴露 breakdown 与自定义 attribution-window 参数。
- 将 `account-diagnostics` 从 `1.0.0` 升至 `1.1.0`，新增 Meta 报表触发词、按需 reference 和真实 Tool 契约回归测试。

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

- 所有平台动态枚举、资源 ID、权限和可执行能力仍以当前 Provider Tool Source/Tool schema 为准。
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
