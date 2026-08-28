# 用户 Skill 管理与评测

业务 Skill 是建立在 Google Ads、Meta、TikTok、DV360 基础 Capability/Tool
之上的编排和专家知识层。用户可以通过管理 API 创建不可变版本、编辑新版本、
触发评测并发布通过的版本。

## Skill 目录格式

按照标准 Agent Skills 目录保存完整快照：

```text
my-campaign-skill/
├── SKILL.md             # 必需：身份、自然语言规则和 SOP
├── scripts/              # 可选：Skill 自带脚本/辅助文件
├── references/           # 可选：详细参考资料
├── assets/               # 可选：模板、示例素材等
└── evals/                # 可选：skill-up 评测配置和 cases
```

`SKILL.md` 负责自然语言指导；`scripts/`、`references/`、`assets/` 等文件会
随版本保存。用户 Skill 不会通过 `tools.py` 或其他文件向广告 Runtime 注入
可执行 Provider Tool。广告读写只能走已经注册的 Capability/Tool，并继续经过
权限、账户白名单、dry-run、确认、幂等和审计保护。

当前版本管理 API 使用 JSON 提交完整文件快照。文本文件直接传字符串，二进制
文件传：

```json
{"encoding":"base64","content":"..."}
```

## 生命周期

```text
编辑/上传目录
      ↓
创建 draft 版本（校验 SKILL.md、路径、大小和版本号）
      ↓
skill-up 评测（可选，但发布前建议通过）
      ↓
发布一个版本（同一租户/Skill 只有一个 published）
      ↓
Runtime 加载为 advisory context
```

发布新版本会把旧版本标记为 `archived`，历史版本仍可查看和复测。带有
`evals/eval.yaml` 的版本必须先通过 skill-up；未配置评测文件的纯上下文 Skill
仍可直接发布。Runtime
进程只加载当前服务租户的已发布版本，避免把一个租户的业务规则带到另一个
租户的会话中；多租户部署应为每个租户隔离 Runtime context。

## API

- `GET /skills`：列出当前身份租户的 Skill 版本
- `POST /skills/{name}/versions`：创建 draft 版本
- `GET /skills/{name}/versions`：列出版本
- `GET /skills/{name}/versions/{version}`：读取完整目录快照
- `POST /skills/{name}/versions/{version}/evaluate`：异步触发 skill-up
- `GET /skills/evaluations/{run_id}`：查询评测状态和报告
- `POST /skills/{name}/versions/{version}/publish`：发布并激活版本

接口要求显式的 `skills.read`、`skills.write`、`skills.evaluate` 权限；请求体
里的 `user_id` 不参与身份判断，租户来自认证后的 `RequestPrincipal`。

## skill-up

需要评测自然语言 Skill 时，在目录中提供：

```text
evals/eval.yaml
evals/cases/*.yaml
```

平台只接受内置 `codex`、`claude_code`、`qodercli`、`qwen_code`、平台托管的
`claude_sdk`，以及平台托管的 `ad-agent-runtime` Engine。`claude_sdk` 使用可选
的 Anthropic Python SDK 评估自然语言 Skill；它读取 Skill 文本、声明的只读
workspace 文件和可信 Tool 描述，但不执行广告 Tool、不连接 MCP，也不接收
Google、Meta、TikTok、DV360 凭证。后者使用仓库固定适配器验证 Skill 与广告底座
Tool 的 dry-run 路由；用户只能提供 cases，不能提供 Engine 命令。平台拒绝
用户自定义 Custom Engine、MCP Server 和 Judge Script。评测在版本快照的隔离
工作目录执行，结果写入版本和 evaluation run；没有 `evals/eval.yaml` 的版本
不能从管理 API 发起 skill-up 评测。

使用 Claude SDK 时先安装 `ad-agent[claude]`，并在服务评测进程配置
`ANTHROPIC_API_KEY`（或 `AD_AGENT_CLAUDE_API_KEY`）。`engine.kwargs` 只支持
`max_tokens`、`file_paths` 和上下文长度上限等非敏感参数；用户不能配置 SDK
执行命令。

仓库内已有的 `agents/ad_agent/evals/skill-up/` 是 Runtime/Capability 集成
回归套件，与用户 Skill 的自然语言评测分开：前者验证路由、Tool 合约、dry-run
和红线保护，后者验证用户 Skill 对 Agent 输出的增量效果。
