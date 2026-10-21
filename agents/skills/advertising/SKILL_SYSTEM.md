# ad-agent Skills 系统架构

## 设计原则

1. **Skill 独立** - 每个渠道有独立的 SKILL.md，提供自然语言专家知识、SOP 和安全边界
2. **Tool Source 扩展** - 渠道 Tool Source/plugin 提供可执行 Tool、Provider schema 和 adapter
3. **Runtime Harness** - 统一负责路由、权限、dry-run、确认、幂等、恢复和审计
4. **跨渠道编排** - 通过 Skill 的业务流程意图和统一资源模型管理多平台 Campaign

## Skill 目录结构

```
skills/
├── SKILL_SYSTEM.md        # 本文件：系统架构说明
├── channels/              # 渠道 Skill：只放专家上下文与 SOP
│   ├── meta/SKILL.md
│   ├── tiktok/SKILL.md
│   ├── google-ads/SKILL.md
│   └── dv360/SKILL.md
├── businesses/             # 业务 Skill：业务规则与适用渠道
│   └── <business>/SKILL.md
├── practices/              # 横切工作方法：策略、诊断、实验等 advisory Skills
│   └── <practice>/SKILL.md
└── cross-channel/          # 跨渠道 Skill：业务 SOP 与统一模型说明
    └── SKILL.md

# 可执行能力不放在上面的 Markdown 目录中：
tools/providers/<platform>/provider.py  # 渠道 Tool Source + ToolDefinition
api_clients/<platform>_client.py        # 可选 Provider Client
skills/<name>/tools.py                  # 仅受信任源码扩展，不属于上传 Skill
```

## Skill 定义格式

每个 Skill 的 SKILL.md 包含身份元数据、自然语言知识、流程说明和安全边界。
它不是 Tool 注册表，也不应通过 Markdown 标题、表格或 YAML 清单直接产生可执行能力。
每个可执行 Tool 必须由 Tool Source/plugin 以结构化 `ToolDefinition` 和 Handler 注册，
这样 schema、权限、Provider adapter 和 Harness 门禁可以被 Runtime 统一验证。

Skill 包遵循标准目录约定：至少包含 `SKILL.md`，也可以包含 `references/`、`scripts/`、
`assets/`、`evals/` 和其他包文件。`SKILL.md` 以自然语言提供专家知识、SOP 和安全
边界；LLM 负责理解这些上下文并提出工具计划，Runtime + Tool metadata + Harness
负责把计划落实为受控执行。上述目录内容由管理系统保存、版本化和评测，但不会被
Runtime 自动导入或执行；`workflow.yaml` 不是上传、编辑或执行入口。只有仓库内经
验证的源码扩展才可以提供 Tool，用户上传的同名文件不会被当作插件加载。

SKILL.md 的 frontmatter 只建议声明 Skill 身份和版本等元数据；专家知识、流程和
安全边界使用自然语言 Markdown 编写。渠道 Tool、参数 schema 和 handler 不写入
SKILL.md，而由对应 Tool Source 在 Registry 中注册。

`practices/` 用于渠道之外可复用的增长与工作方法，例如创意策略、诊断、SEO、GEO 和
增长组合。它们补充而不复制渠道 Skill、知识 Wiki 或 Tool contract；references 按请求
相关性限量加载。没有对应注册 Tool 时，Skill 只能给出分析、草案或待查询项，不能暗示
已取数、抓取外部素材、修改广告/网站或执行自动化。

## 已吸收的营销方法

| 本地来源 | 系统落点 | 不导入的部分 |
|---|---|---|
| 本项目广告 Wiki 与已验证的知识问答模式 | `practices/knowledge-explainer` 的结论优先、层级解释、场景分支和证据边界 | 不复制 Wiki 中的平台事实；不增加 Tool、账户查询或执行权限 |
| `ad-creative` 2.10.0 | `practices/creative-strategy` 与 Wiki 的创意路线图、Hook 漏斗诊断 | 生成素材的外部服务、抓取/上传脚本和特定平台规格副本 |
| `ads` 2.4.6；上游 `operating-check` 参考（2026-10-18） | `practices/account-diagnostics` 的通用审计、Google Search Terms/转化、Meta Insights 解读和日/周 HOLD/FIX/TEST/INVESTIGATE 运营检查 | 未注册报表能力对应的审计项、外部抓取流程和固定表现阈值 |
| `ab-testing` 2.0.1 | `practices/experimentation-design`、Wiki 的实验方法；触发后按需加载实验设计 reference | 上游固定样本量表、统计计算器或自动平台实验执行 |
| `attribution` 1.1.4 | `practices/measurement-attribution`、Wiki 的归因/增量方法；触发后按需加载对账 reference | 未接入数据源时声称运行 GA4、CRM、MTA 或 MMM |
| `analytics` 2.0.3 | `practices/measurement-instrumentation`、Wiki 的测量数据契约和转化信号排障；触发后按需加载事件契约与 conversion QA runbook | GA4/GTM/Pixel/CAPI 配置代码、外部集成和未注册的实施 Tool |
| `aso` 2.0.2 | `practices/app-growth`：商店页与广告主张匹配、经官方只读 Tool 查询公开 iOS 商店元数据、页面审查和安装后 cohort 诊断 | 商店抓取、App Store Connect/Google Play Console 私有数据或修改、把公开评分当作广告/下载/留存表现 |
| `marketing-loops` 1.4.0 | `practices/ad-growth-operations`：检查频率与动作条件分离、循环契约、跨运行去重需求、失败停止和人工审批 | 将通用定时任务包装成第二套 Runtime、自动调预算/暂停/轮换或跨运行状态能力 |
| Marketplace `copywriting`、`paid-ads`、`ad-creative`、`marketing-psychology` | `practices/ad-copywriting` 的广告文案 brief、主张证据、变体设计与伦理说服约束 | 虚构产品主张/社会证明、操纵性紧迫感、未经验证的平台规格和素材发布 |
| Marketplace `page-cro`、`copywriting`、`paid-ads` | `practices/paid-landing-page-review` 的付费流量消息匹配、页面证据审查与可验证测试 | 未授权网页抓取、分析系统接入、页面修改及无来源的转化提升承诺 |
| Anthropic `data-visualization`、`validate-data`；Hermes `grounded-citations` | `practices/data-visualization` 与 `web-research` 的数据粒度检查、来源映射、缺失值边界和图表自检 | 上游脚本、来源账本、连接器和可执行流程；搜索摘要不能替代网页正文或结构化数据 |
| Google Search Central SEO Starter Guide、AI features 文档；OpenAI crawler 文档 | `practices/seo-growth` 的自然搜索诊断、`generative-search-visibility` 的 AI 搜索测量、`growth-strategy` 的渠道组合决策；`public-site-quality` Tool 提供单页 PageSpeed/Lighthouse 读取 | 排名/引用保证、未经官方确认的 GEO 配方、整站自动爬取、GSC 私有数据读取或网站改写权限 |

这些是本机读取到的来源包版本，用于追踪本次蒸馏输入，不代表远端最新版本或 Runtime
插件版本。来源包中与已发布广告 Wiki 重合的基础内容不重复导入。上游 Skill 只作为
知识来源；上表对应的项目内 Skill 均为独立 advisory 包，由广告 Scenario 的标准目录
Source 自动发现。其 `SKILL.md`、references 和 provenance 可进入受限上下文，但不会被
当作可执行扩展，也不增加 Tool、凭证或账户权限；所有查询和变更仍须通过当前注册 Tool
与 Harness 门禁。

2026-10-18 对照 Skills Marketplace 的 `paid-ads`、`copywriting`、`page-cro`、
`ad-creative` 和 `marketing-psychology` 条目后，保留三项非重复增量：账户运营决策
检查、广告文案/证据 brief、付费流量落地页审查。Marketplace 的通用文案与 CRO 方法
被改写为广告场景；未注册的网页抓取、分析、第三方平台或写操作能力不会随 Skill 引入。

2026-10-19 复核本机 `customer-research`、`marketing-plan`、`marketing-loops`、`aso`、
`onboarding`、`signup`、`paywalls`、`churn-prevention`、`revops` 和 `launch`：
客户语言采样已覆盖在创意策略；CRO/分析/归因/实验已有专门 practice；整套营销计划、
发布、订阅和销售流程不适合作为广告 Agent 的新 Tool 权限。新增 ASO/App 漏斗分析与安全
广告运营循环两个 advisory Skills。循环可以使用当前通用 Scheduler 登记只读复盘，但跨运行
业务去重、GA4/CRM/MMP/商店数据、创意生成与自动预算/暂停仍需独立 Tool/Data 能力及授权。

2026-10-21 根据 Anthropic `knowledge-work-plugins` 的数据校验/可视化方法和 Hermes
`grounded-citations` 的来源映射方法，新增有证据的数据可视化 Skill，并强化联网检索 Skill。
其重点是让每项结论和图表观测对应本轮可见来源；不引入网页正文抓取、天气 API、来源账本、
外部脚本或新执行权限。上游许可证分别为 Apache-2.0 与 MIT；方法来源详见该 Skill 的
`ATTRIBUTION.md`。

2026-10-21 增补非付费增长方向：增长策略先定位漏斗瓶颈，再比较自然搜索、GEO、内容、
付费、ASO、CRO、推荐/合作、产品驱动和生命周期路径；SEO 与 GEO 是独立 advisory Skills，
不会与广告关键词规划或付费落地页审查混为一谈。新增 Google PageSpeed Insights 单页只读
Tool：可尝试无 key 低频调用，也支持通过 `GOOGLE_PAGESPEED_API_KEY` 配置受限 API key；
匿名配额可能被限流，不能承诺免 key 稳定可用。Search Console 数据需 OAuth 及属性权限，
IndexNow 则是站点所有者主动提交 URL 的写操作而非效果/收录保证，二者当前未接入。详见新
Skills 的官方来源与边界。

## 跨渠道 Campaign 管理

跨渠道 Skill 提供业务层流程和统一口径；真正的查询/计划/执行能力仍来自已注册的
平台 Tool Source 和 Tool：

1. **Campaign 总览** - 统一查看各平台 Campaign 状态
2. **预算分配** - 跨平台预算智能分配
3. **性能对比** - 对比各平台 ROI/CPA
4. **批量操作** - 一键启停多个平台 Campaign

## 扩展新渠道

按以下边界扩展：

1. 创建 `skills/channels/{channel}/SKILL.md`，描述专家知识、SOP 和安全边界
2. 创建 `tools/providers/{channel}/provider.py`，导出约定的 Tool Source factory
3. 按需创建 `api_clients/{channel}_client.py` 或 Skill plugin
4. 让 Runtime 自动发现；Tool 仍需通过统一 Registry、schema 和 Harness 安全门禁
