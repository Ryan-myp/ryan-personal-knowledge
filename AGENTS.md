# Agent 开发约束

本仓库的广告 Agent 是一个新建的单 Agent 平台。后续模块必须在既有边界内演进，不能通过复制一套独立 Agent、渠道 Router 或旧式流程来解决局部需求。

## 总体架构

```text
单 Agent Runtime
  ├── Skills：自然语言规则、业务 SOP、上下文与流程指导
  ├── Tools：结构化、可校验、可审计的能力入口
  └── Capabilities：渠道 API 的可信实现与 Tool 注册
```

- `SKILL.md` 是 Skill 的自然语言入口，不是 Tool 注册表，也不承担凭证或执行权限。
- 广告 API 的唯一执行底座是已注册的 Capability/Tool。任何 Skill、LLM 或管理上传包都不能直接调用 Provider client。
- 新功能优先通过新增或扩展 Skill、Tool、Capability 完成；不要在中心 Router 中增加渠道名、业务流程或参数大分支。
- 渠道差异放在 Provider Capability、Tool schema 和 API client 边界；上层业务依赖 Tool 的 intent、resource、schema 和 traits，不硬编码渠道实现。
- 观察性当前只保留接口和结构化字段，不在本阶段阻塞功能交付。

## Skill 约束

用户 Skill 必须按标准 Agent Skills 目录保存，至少包含根目录 `SKILL.md`；可以包含 `references/`、`scripts/`、`assets/`、`evals/` 以及其他标准包文件。除 `SKILL.md` 外的文件必须按用途加载，不能假设只有两个文件。

- Skill 流程、SOP、触发条件和输出要求用自然语言写在 `SKILL.md` 与 references 中。
- 不要求用户提供 `workflow.yaml`；已有 workflow 支持仅是内部兼容能力，不能把它设为上传或编辑的必填项。
- 用户上传 Skill 是上下文数据。服务可以保存、版本化、发布和评测，但不能 import、执行其中的 `scripts/`，也不能从中注册 Provider Tool。
- Skill 版本不可变；修改必须创建新语义化版本，发布前通过校验和适用的评测。

## 安全与执行

- 默认 `dry_run`。真实写操作必须同时通过显式 live 开关、测试账号白名单、权限、确认、幂等和审计链路。
- 禁止在日志、结果、Prompt、评测产物和异常中泄露 `access_token`、`refresh_token`、`client_secret`、`app_secret`、`private_key`、`developer_token`、`bc_id`、`partner_id`、`perter_id`、`mcc` 或等价凭证字段。
- 请求体中的 `user_id` 不是认证身份；身份、租户、权限和账户范围必须来自可信 principal/configuration。
- 任何新 Tool 都必须有闭合 schema、权限、风险等级、effect、replay/idempotency 和超时/输出上限声明。
- 不得给上传 Skill、评测 case 或任意自定义 Engine 开放 MCP、Provider 凭证或未审核的可执行命令。

## 存储与性能

- 当前 SQLite 只支持单进程部署；所有持久化必须通过 store/interface 抽象，不能在业务代码中散落 SQL 或绑定 SQLite 特性，便于未来切换 MySQL 等后端。
- Runtime、Capability 和 Tool registry 应在进程启动时初始化并复用；请求路径不得重复扫描、注册全部渠道或创建不必要的客户端。
- 扩展时保持 Provider client 连接复用、schema 元数据缓存、有限上下文和有界并发；不要用无上限的全量 Skill/Tool 文档注入 Prompt。

## 评测与交付

- Runtime/Capability dry-run 场景使用 `agents/ad_agent/evals/skill-up/skill_up_engine.py`。
- 通用自然语言 Skill 效果可以使用平台托管的 `claude_sdk` Engine 或 skill-up 内置 Engine；Claude SDK 适配器只提供 Skill、Tool 描述和只读文件上下文，不执行广告 Tool。
- 评测配置必须是声明式、可审计、可复现的；用户包不能自定义执行命令、MCP server 或 judge script。
- 代码变更至少运行编译、相关单测、全量 Agent 测试、能力审计和 `git diff --check`；Provider contract 变化必须补充回归用例。
- 变更说明要交代影响的接口/契约、失败恢复、权限边界、迁移/回滚方式以及是否需要后续观察性接入。

详细的广告 Agent 专属规则见 [`agents/ad_agent/AGENTS.md`](agents/ad_agent/AGENTS.md)。
