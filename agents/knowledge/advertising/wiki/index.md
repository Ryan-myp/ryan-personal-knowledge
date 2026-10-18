# LLM Wiki 索引

> **版本**: v2.6.0
> **更新时间**: 2026-10-18
> **定位**: 为单 Agent 提供可检索、可引用、不可执行的广告业务上下文

## 知识地图

本知识库围绕 Google Ads、Meta Ads、TikTok Ads、DV360 四个平台，覆盖“理解对象 → 设计投放 → 执行前校验 → 运行中优化 → 归因复盘”的完整链路。

```text
raw：原始来源、论文、代码片段和未经审核的材料
entities：Google Ads / Meta Ads / TikTok Ads / DV360 等稳定实体，含中文概览与知识导航
concepts：平台规则、业务方法、经验与诊断知识
comparisons：跨平台对象模型、测量和策略对比
queries：经过筛选、可复用的问答归档
```

## 目录

```text
knowledge_base/
├── platforms/
│   ├── google/      # Campaign、Search/PMax、转化、GAQL、优化、配额
│   ├── meta/        # Campaign/Ad Set/Ad、ODAX、Catalog、CAPI、Insights
│   ├── tiktok/      # Campaign/Ad Group/Ad、Spark、Smart+、事件、报表
│   └── dv360/       # Partner/Advertiser、IO/Line Item、Deal、Floodlight、报告
├── business/
│   ├── cross-platform-hierarchy.md
│   ├── industry-playbooks.md
│   ├── bidding-and-budget.md
│   ├── targeting-and-audiences.md
│   ├── creative-testing.md
│   ├── measurement-and-attribution.md
│   ├── measurement-data-contracts-and-incrementality.md
│   ├── budget-pacing-and-marginal-efficiency.md
│   ├── evidence-driven-performance-diagnosis.md
│   ├── four-platform-ad-agent-handbook.md
│   ├── ecommerce-growth-playbook.md
│   ├── app-game-growth-playbook.md
│   ├── b2b-lead-generation-playbook.md
│   └── unit-economics-and-channel-mix.md
├── expertise/
│   ├── optimization-diagnostic-framework.md
│   ├── experimentation-and-learning.md
│   ├── best-practices.md
│   └── error-patterns.md
├── raw/                         # 来源层，不进入 Runtime
├── entities/                    # Karpathy entity pages
├── concepts/                    # Karpathy concept map
├── comparisons/                 # Karpathy comparison pages
├── queries/                     # 可复用问答归档
├── ARCHITECTURE.md
├── SCHEMA.md
├── QUALITY_STANDARD.md
├── USAGE_GUIDE.md
└── log.md
```

## 按问题检索

| 用户问题 | 优先知识 |
|---|---|
| “介绍一下某个广告平台/讲讲基础知识” | 对应 `entities/` 概览页，再按其知识入口深入专题 |
| “这个平台的层级和父子关系是什么？” | `cross-platform-hierarchy` + 对应平台 `hierarchy` |
| “Meta 的广告目标应该怎么选，Catalog Sales/私信属于哪一层？” | `queries/meta-objective-selection` + Meta `hierarchy-and-objectives` |
| “怎么创建/修改广告？” | 对应平台 `constraints-and-workflows` + 当前 Tool schema |
| “预算/出价怎么设？” | `bidding-and-budget` + 对应平台优化文档 |
| “素材、受众怎么测？” | `creative-testing` + `targeting-and-audiences` |
| “下一批创意应该做什么，如何按证据和产能排优先级？” | `creative-testing` + `agents/skills/advertising/practices/creative-strategy/` |
| “如何设计广告 A/B 实验、规划样本并解释结果？” | `expertise/experimentation-and-learning` + `agents/skills/advertising/practices/experimentation-design/` |
| “数据为什么异常？” | `optimization-diagnostic-framework` + 对应平台 measurement 文档 |
| “账户审计覆盖不完整，健康分应该怎么算？” | `evidence-driven-performance-diagnosis` |
| “Google 搜索词/转化报表或 Meta Insights 数据可信吗，指标如何解读？” | `agents/skills/advertising/practices/account-diagnostics/` + 对应平台 measurement/reporting 文档 |
| “广告平台、分析系统和 CRM 的转化为什么对不上，是否代表增量？” | `measurement-and-attribution` + `measurement-data-contracts-and-incrementality` + `agents/skills/advertising/practices/measurement-attribution/` |
| “需要埋哪些转化事件、如何定义和验收追踪？” | `measurement-data-contracts-and-incrementality` + `agents/skills/advertising/practices/measurement-instrumentation/` + 对应渠道事件文档 |
| “四个平台整体怎么设计和排查？” | `four-platform-ad-agent-handbook` + 对应平台 Canonical Runbook |
| “这个操作系统支持吗？” | 先查当前 Registry/Tool Source，不以知识文档代替能力审计 |
| “测试账号某种广告类型上次真实创建到哪一步，失败怎么恢复？” | `concepts/provider-live-e2e-memory` + `agents/tools/advertising/contracts/provider_live_e2e_memory.json` |

## 重要边界

- Wiki 是 advisory context，不注册 Tool、不调用 Provider、不保存凭证、不执行上传包中的脚本。
- 平台枚举、字段组合、动态 ID、权限和 live 能力以当前 Registry Tool schema 为最终事实来源。
- 新增知识会被 SQLite FTS5/BM25 索引；不依赖 Embedding 或向量数据库。若 FTS5 不可用，Runtime 自动使用受限的词法检索回退。
- 报告必须携带平台、账户/资源层级、日期时区、归因窗口、币种、来源和数据延迟；跨平台指标默认不可直接横比。
- 涉及写入时默认 dry-run；live 必须通过账户范围、权限、测试白名单、显式确认、幂等和审计。

## 当前统计

截至 2026-10-18，Runtime 实际加载 **71 个发布 Markdown 文档**：

| 范围 | 文档数 | 覆盖 |
|---|---:|---|
| Google | 14 | 1 个实体页 + 13 篇平台规则、Search/PMax、Campaign/Search Runbook、转化、GAQL、报表与优化 |
| Meta | 13 | 1 个实体页 + 11 篇平台规则 + 1 篇目标选择 Query，覆盖 ODAX、Catalog/Lead、Pixel/CAPI、Insights 与优化 |
| TikTok | 12 | 1 个实体页 + 11 篇平台规则、Smart+/Spark、Commerce、事件、报表与素材 |
| DV360 | 12 | 1 个实体页 + 11 篇平台规则、IO/Line Item、Deal、Floodlight、报告与恢复 |
| 跨平台业务 | 14 | 四平台总览、层级、行业、预算节奏、边际效率、受众、创意、数据契约、证据驱动诊断、归因、电商、App/游戏、B2B、渠道组合 |
| 经验方法 | 4 | 诊断、实验、最佳实践、错误模式 |
| 对比页 | 1 | 四个平台的对象、强项和优先核对项 |
| 概念页 | 1 | Provider live E2E 的测试记忆与恢复规则 |

平台专题文档当前已从“示例条目”升级为“资源模型 + 数据契约 + 决策框架 + 诊断路径 + API 执行边界”。跨平台创意知识新增了证据驱动路线图、探索/扩量状态、制作产能和 Hook 到业务结果的诊断；审计知识区分健康度与证据覆盖率；实验与归因知识明确统计结论和因果边界；Google 报表知识补充搜索词可见性、转化动作粒度、日期口径和模拟数据边界。实体页只负责导航，不复制平台规则；固定数值、策略枚举和规格仍需按账户、地区、接口版本与平台政策复核。

四个平台的实体页提供中文概览、核心对象职责和专题入口，适合回答“讲讲某渠道/基础知识”这类宽问题；遇到具体决策、字段、策略和排障时，继续引用对应专题，而不是把实体页当作完整事实来源。纯链接参考章节不参与知识片段排名，但文章级来源仍随检索结果返回。

`ARCHITECTURE.md`、`SCHEMA.md`、`QUALITY_STANDARD.md`、`UPGRADE_SUMMARY.md`、`USAGE_GUIDE.md`、`index.md` 和 `log.md` 是维护文档，不进入 Agent 业务检索和前端知识目录；它们只用于解释知识库自身如何维护。

## 版本与维护

- 文档使用标准 frontmatter，只有 `status: published` 的文档进入 Runtime 检索。
- 平台 API、政策、字段和能力变化时，新增语义化版本文档或更新版本号，并在 `log.md` 记录来源和影响范围。
- 运营经验不能伪装成官方事实；经验文档需要标记适用条件、置信度、样本范围和失效条件。
- 文档更新后应运行 Markdown 元数据校验、全库审计、知识库检索 smoke test、相关测试、能力审计和 `git diff --check`。
- 全库审计会检查目录对象类型、来源证据、断链、孤立页、案例 ID 漂移和平台覆盖；
  结果中的 warning 是历史治理待办，error 才阻断质量门。
