# ad-agent 专属开发约束

## Python 解释器约束

Agent 运行时、测试、评测、审计和知识库维护脚本统一使用 Python 3.13。请从仓库根目录
使用 `make ad-agent-*`，或使用 `./scripts/ad-agent-python` 包装器；不要直接调用系统
`python`/`python3`。包装器会在真正导入 Agent 代码前拒绝错误版本，`.python-version`
则为 pyenv/asdf 等本地工具提供默认版本提示。

## 不可改变的模型

本模块采用“单 Agent + 多 Skills + Tools”：

```text
用户请求
  -> 通用 Agent Harness Runtime / Run Kernel
  -> TurnPipeline
  -> IntentParser
  -> Skill 上下文与 Tool metadata
  -> ToolSelector / policy gates
  -> Tool Registry
  -> Local Handler / SDK-HTTP Connector / MCP Client
```

Skill 描述如何理解和编排业务；Tool 描述一个可校验、可授权、可审计的动作；Executor 负责具体实现。广告项目中的 Tool Source 只是 Provider Module 兼容实现，不是通用 Runtime 必需层。

通用 Run Kernel 统一负责 `run_id`、`turn_id`、身份规范化、Session 并发、租约、
执行模式和取消/租约丢失信号。应用只向 Harness 注入通用 Turn Handler；广告不再
拥有自己的 Pipeline、Stages 或第二套回合状态机。

- 业务 Skill 不得直接 import `api_clients/`、持有渠道凭证或自己发 HTTP 请求。
- `runtime/` 不得为单个业务流程硬编码 Google、Meta、TikTok 或 DV360 的分支。
- `core/` 只依赖统一的 Tool/Executor 契约；渠道特有字段、枚举和条件规则放在对应 Tool schema。
- 所有可部署扩展必须通过 `core.plugins.PluginManifest` 和 `PluginRegistry` 声明唯一 ID、版本、贡献类型、依赖、来源和可信级别；Tool Source、Feature、Renderer、受信任 Skill 扩展与托管 Skill 不得各自定义一套生命周期。
- 可部署插件包使用根目录 `plugin.manifest.json`；Loader 必须校验文件清单、摘要和可选签名，禁止仅凭 `entrypoint` 自动导入。托管 Skill 不要求该文件，也不能借此获得代码执行权限。
- `user_skills/` 和管理上传的 Skill 只能提供上下文；不能借助 `tools.py`、`scripts/` 或 `workflow.yaml` 绕过 registry。
- LLM Parser 的意图目录由 Registry 中已注册 Tool 的 `intent_types`、description、action 和 resource 元数据生成；新增自定义意图必须随 Tool 声明，禁止在中心 Parser 增加意图分支。

## 新增能力的落点

新增渠道接口时，按以下顺序落点：

1. 在对应 Provider Module/Connector 包中增加 Tool 定义和固定 Executor；方法名不能由用户输入决定。
2. 补齐输入 schema、枚举/条件依赖、权限、effect、风险、重放策略、超时、输出上限、契约版本和 Provider API 版本。
3. 在必要时扩展 `api_clients/<provider>/` 的版本化适配器；升级 API 时保留兼容 contract 或明确升级 contract version。
4. 通过 Tool Source/Registry 注册；广告内置渠道可以继续由 Tool Source factory 兼容发现，不在上层 Skill 或 Router 新增渠道硬编码引用。
5. 补充 provider payload、权限/账户范围、dry-run、幂等、失败恢复和审计测试，并运行 `scripts/audit_provider_tools.py`。

新增业务流程时，优先写标准 Skill 目录：根 `SKILL.md` 使用自然语言描述 SOP，复杂知识放 `references/`，资源放 `assets/`，辅助脚本仅作为包内容保存。只有确实需要新的可执行动作时才新增 Tool/Tool Source。

## Tool 与参数规则

- Tool schema 是参数目录的事实来源；不能在业务代码中复制一份渠道枚举。
- 动态参数通过受控 lookup Tool/parameter catalog 提供；静态枚举直接写入 Provider Tool schema，并保留来源和版本信息。
- Tool 执行必须经过 Runtime 的 schema、principal、权限、账户白名单、执行模式、live gate、确认、幂等和审计检查。
- 任何 write Tool 默认只能生成 dry-run 计划；没有测试账号白名单和显式授权不得 live。
- 永远不把 token、`bc_id`、`partner_id`/`perter_id`、`mcc`、client secret 等放进 Tool input、Skill 内容、模型上下文或错误信息。

## 用户 Skill 管理与评测

- 管理 API 接受完整标准 Skill 目录快照，保留 `SKILL.md`、`references/`、`scripts/`、`assets/`、`evals/` 等文件并做路径、大小、编码和 digest 校验。
- 版本发布只激活不可变快照；Runtime 加载的是 advisory context，不会将用户包转换成 Tool。
- 托管 Skill 只能登记为不可执行的 advisory Plugin；只有经过部署审核的 trusted source Plugin 才能携带生命周期对象，且其 Tool 仍必须经过 Runtime 的统一执行门禁。
- Skill-up 的 `ad-agent-runtime` Engine 测试真实 Runtime/Tool Source dry-run 路由。
- `claude_sdk` Engine 使用 Anthropic Python SDK 测试自然语言 Skill 效果。它可以读取 Skill 文本、受控只读文件和可信 Tool 描述，但不执行 Tool、不连接 MCP、不接收广告凭证。
- Skill-up adapter 由平台生成，用户只能选择受控 Engine 和参数；不得把任意命令、judge script 或环境变量变成管理 API 能力。

## 持久化、并发和后续模块

- SQLite 当前按单进程部署；新模块只依赖 `persistence/interfaces.py` 和 store service，不把 SQL 类型泄露到 Runtime/HTTP/Skill 层。
- 进程内 registry、Skill metadata、Provider client 应复用；请求中避免重复初始化和无界 Prompt 拼接。
- 对批量操作设置明确上限、超时和并发策略；外部 Provider 限流必须在 client/tool_source 边界处理。
- 观察性先沿用已有结构化审计/结果字段并预留 trace/metrics 接口，后续接入时不能改变 Tool 契约和安全 gate。
- 长任务必须通过通用 `TaskExecutor` 排队；worker 只能重新进入 Runtime 的统一执行
  链路，禁止直接读取任务 payload 后调用 Provider Handler。任务状态、lease、幂等和
  取消必须经过 `PersistenceBackend`；暂停/取消只控制本地任务，不声称已回滚外部状态。

## 修改完成前检查

```bash
make ad-agent-check
git diff --check
```

涉及 Skill-up 时再运行 `agents/ad_agent/evals/skill-up/run.sh`；涉及 API/存储时必须覆盖租户隔离、版本不可变性和失败恢复测试。
