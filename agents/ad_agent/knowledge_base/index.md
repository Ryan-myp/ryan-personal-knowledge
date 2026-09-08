# LLM Wiki 索引

> **版本**: v2.0.0
> **更新时间**: 2026-09-08
> **定位**: 为单 Agent 提供可检索、可引用、不可执行的广告业务上下文

## 知识地图

本知识库围绕 Google Ads、Meta Ads、TikTok Ads、DV360 四个平台，覆盖“理解对象 → 设计投放 → 执行前校验 → 运行中优化 → 归因复盘”的完整链路。

```text
平台层：层级 / 目标 / 参数约束 / 创建工作流 / 平台优化 / 报表诊断
业务层：行业打法 / 预算出价 / 受众定向 / 创意测试 / 归因增量
经验层：诊断决策树 / 实验设计 / 错误模式 / 最佳实践 / 案例与数据
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
├── ARCHITECTURE.md
├── SCHEMA.md
├── QUALITY_STANDARD.md
├── USAGE_GUIDE.md
└── log.md
```

## 按问题检索

| 用户问题 | 优先知识 |
|---|---|
| “这个平台的层级和父子关系是什么？” | `cross-platform-hierarchy` + 对应平台 `hierarchy` |
| “怎么创建/修改广告？” | 对应平台 `constraints-and-workflows` + 当前 Tool schema |
| “预算/出价怎么设？” | `bidding-and-budget` + 对应平台优化文档 |
| “素材、受众怎么测？” | `creative-testing` + `targeting-and-audiences` |
| “数据为什么异常？” | `optimization-diagnostic-framework` + 对应平台 measurement 文档 |
| “平台数据能不能代表真实增量？” | `measurement-and-attribution` + `experimentation-and-learning` |
| “四个平台整体怎么设计和排查？” | `four-platform-ad-agent-handbook` + 对应平台 Canonical Runbook |
| “这个操作系统支持吗？” | 先查当前 Registry/Capability，不以知识文档代替能力审计 |

## 重要边界

- Wiki 是 advisory context，不注册 Tool、不调用 Provider、不保存凭证、不执行上传包中的脚本。
- 平台枚举、字段组合、动态 ID、权限和 live 能力以当前 Registry Tool schema 为最终事实来源。
- 新增知识会被 SQLite FTS5/BM25 索引；不依赖 Embedding 或向量数据库。若 FTS5 不可用，Runtime 自动使用受限的词法检索回退。
- 报告必须携带平台、账户/资源层级、日期时区、归因窗口、币种、来源和数据延迟；跨平台指标默认不可直接横比。
- 涉及写入时默认 dry-run；live 必须通过账户范围、权限、测试白名单、显式确认、幂等和审计。

## 当前统计

截至 2026-09-08，Runtime 实际加载 **64 个业务 Markdown 文档**：

| 范围 | 文档数 | 覆盖 |
|---|---:|---|
| Google | 13 | 层级、约束、Search/PMax、Campaign/Search Runbook、价值出价、转化、GAQL、报表、策略优化、配额与版本 |
| Meta | 11 | 层级目标、预算定向、Campaign/Ad Set Runbook、ODAX、Catalog/Lead、Pixel/CAPI、事件质量、Insights、权限与版本 |
| TikTok | 11 | 层级目标、Campaign/Ad Group Runbook、Smart+/Spark、素材、App/Commerce、Events API、事件归因、报表、限流与排障 |
| DV360 | 11 | 购买层级、IO/Line Item Runbook、Deal/竞价、Floodlight、采购质量、报告诊断、创意审批、异步恢复 |
| 跨平台业务 | 14 | 四平台总览、层级、行业、预算节奏、边际效率、受众、创意、数据契约、证据驱动诊断、归因、电商、App/游戏、B2B、渠道组合 |
| 经验方法 | 4 | 诊断、实验、最佳实践、错误模式 |

平台专题文档当前已从“示例条目”升级为“资源模型 + 数据契约 + 决策框架 + 诊断路径 + API 执行边界”。固定数值、策略枚举和规格仍需按账户、地区、接口版本与平台政策复核。

`ARCHITECTURE.md`、`SCHEMA.md`、`QUALITY_STANDARD.md`、`UPGRADE_SUMMARY.md`、`USAGE_GUIDE.md`、`index.md` 和 `log.md` 是维护文档，不进入 Agent 业务检索和前端知识目录；它们只用于解释知识库自身如何维护。

## 版本与维护

- 文档使用标准 frontmatter，只有 `status: published` 的文档进入 Runtime 检索。
- 平台 API、政策、字段和能力变化时，新增语义化版本文档或更新版本号，并在 `log.md` 记录来源和影响范围。
- 运营经验不能伪装成官方事实；经验文档需要标记适用条件、置信度、样本范围和失效条件。
- 文档更新后应运行 Markdown 元数据校验、知识库检索 smoke test、相关测试、能力审计和 `git diff --check`。
