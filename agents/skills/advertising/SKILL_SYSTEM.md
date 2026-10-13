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

`practices/` 用于广告类型和渠道之外的可复用工作方法，例如创意策略与诊断。它们
补充而不复制渠道 Skill、知识 Wiki 或 Tool contract；references 按请求相关性限量
加载。没有对应注册 Tool 时，Skill 只能给出分析、草案或待查询项，不能暗示已取数、
抓取外部素材、修改广告或执行自动化。

## 已吸收的营销方法

| 本地来源 | 系统落点 | 不导入的部分 |
|---|---|---|
| `ad-creative` 2.10.0 | `practices/creative-strategy` 与 Wiki 的创意路线图、Hook 漏斗诊断 | 生成素材的外部服务、抓取/上传脚本和特定平台规格副本 |
| `ads` 2.4.6 | Wiki 的审计证据状态与覆盖率，以及 `practices/account-diagnostics` 的通用审计、Google Search Terms/转化和 Meta Insights 解读 | 未注册报表能力对应的审计项、外部抓取流程和固定表现阈值 |
| `ab-testing` 2.0.1 | `practices/experimentation-design`、Wiki 的实验方法；触发后按需加载实验设计 reference | 上游固定样本量表、统计计算器或自动平台实验执行 |
| `attribution` 1.1.4 | `practices/measurement-attribution`、Wiki 的归因/增量方法；触发后按需加载对账 reference | 未接入数据源时声称运行 GA4、CRM、MTA 或 MMM |
| `analytics` 2.0.3 | `practices/measurement-instrumentation`、Wiki 的测量数据契约；触发后按需加载事件契约 reference | GA4/GTM/Pixel/CAPI 配置代码、外部集成和未注册的实施 Tool |

这些是本机读取到的来源包版本，用于追踪本次蒸馏输入，不代表远端最新版本或 Runtime
插件版本。来源包中与已发布广告 Wiki 重合的基础内容不重复导入。上游 Skill 只作为
知识来源；上表对应的项目内 Skill 均为独立 advisory 包，由广告 Scenario 的标准目录
Source 自动发现。其 `SKILL.md`、references 和 provenance 可进入受限上下文，但不会被
当作可执行扩展，也不增加 Tool、凭证或账户权限；所有查询和变更仍须通过当前注册 Tool
与 Harness 门禁。

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
