# Ad Agent 系统开发契约

本文是 `agents/ad_agent` 的产品级架构与开发指导，约束后续模块如何扩展。
仓库级操作规则仍以同目录的 `AGENTS.md` 为准；两者冲突时，以用户明确需求和
`AGENTS.md` 的安全约束为准。

## 1. 产品定义

这是一个由 LLM 驱动的单 Agent 广告管理系统，不是四个渠道 Agent 的集合：

```text
用户请求
  -> 一个 Agent / LLM
  -> Skill 上下文、SOP 和业务策略
  -> Tool metadata 选择与参数计划
  -> Runtime policy gates
  -> Provider Capability Tool
  -> Provider API Client
```

- Agent 负责理解、拆解、询问缺失信息、编排和总结。
- Skill 负责自然语言知识、业务流程、渠道规则、前置条件和安全提示。
- Tool 是一个有明确输入/输出、权限、风险、重放、超时和资源层级的可执行动作。
- Capability 是渠道拥有的 Tool 注册和 Provider 适配边界。
- Client 负责认证后的请求、版本适配、限流、重试、错误分类和 payload 转换。
- Runtime/Core 只实现通用规划、校验、授权、dry-run、幂等和恢复，
  不为某个渠道或业务流程增加分支。

Runtime 不承载业务流程实现。可选业务扩展通过通用接口自动发现：

- `RuntimePolicy`：由业务 Skill 提供渠道过滤、预算/类型等策略；
- `RuntimeFeature`：由需要二阶段查询、批量计划或复杂编排的 Skill/Feature 提供；
- `ResponseRenderer`：由应用层提供结果展示。
- `ExecutionPlan` / `WorkflowCoordinator`：分别负责不可变计划描述和持久化执行状态，
  不把业务流程实现塞回 Runtime。
- `TaskExecutor`：负责长回合的持久化排队、受控并发、lease 心跳、取消和恢复；任务
  worker 只重新进入 Agent Runtime，不直接调用 Provider Handler。暂停/取消是本地
  调度语义，不代表外部广告平台已回滚。
- `RuntimeServices` / `ToolExecutor` / `RuntimeSecurity`：分别提供 Feature 端口、
  Tool 执行和安全边界实现。
- `PluginRegistry`：统一管理扩展的 Manifest、版本、依赖和生命周期；Capability、
  Feature、Renderer、受信任 Skill 扩展和托管 Skill 上下文都通过它登记。它不执行
  Provider 请求，也不替代 ToolRegistry 的权限、账户、dry-run 和审计门禁。
- 最终回答经过 `ResponseSynthesizer`/`ResponseRenderer` 边界：LLM 只能基于脱敏的
  用户输入、已执行结果、知识引用和分析结果回答，不能在最终回答阶段调用 Tool 或
  改变执行状态；LLM 输出异常时必须回退到 Renderer。

Runtime 只调用这些接口，不识别 `ecommerce`、`app`、`cross-channel` 等业务名称。

`ToolInputBuilder` 只能按 Tool Schema 的字段名、`input_aliases`、`intent_field`、
`intent_aliases` 和 `intent_map` 组装输入；不得在 Runtime/Builder 中新增
`budget`、`objective`、`campaign` 等业务字段的专门分支。资源 ID 只能通过
Tool 的 `resource_id_field` 进入会话保护状态。

## 2. Skill 边界

Skill 必须使用标准目录格式，至少包含 `SKILL.md`，也可以包含：

```text
skill-name/
├── SKILL.md       # 必需：身份、知识、SOP 和安全边界
├── references/    # 可选：详细文档、字段说明和示例
├── scripts/       # 可选：随包保存的辅助材料，不由 Runtime 自动执行
├── assets/        # 可选：模板、图片和其他资源
└── evals/         # 可选：skill-up 数据文件和验收用例
```

`SKILL.md` 使用自然语言描述流程；frontmatter 只声明身份、版本、平台别名、可选的
解析展示标识和非执行触发上下文。平台别名由渠道 Skill 元数据自动发现，不需要在
Core 或 Router 中维护渠道表。Markdown 表格、`workflow.yaml`、`scripts/` 或 `assets/`
都不能自动变成 Tool，也不能绕过 Registry、权限和 Runtime gate。

用户上传的 Skill 作为 advisory context 保存和版本化。它可以指导 Agent 组合
已有 Tools，但不能携带凭证、自动导入 Python、注册任意 HTTP 动作或改变账户白名单。
多租户 HTTP 请求在进入 Agent 前只激活认证 Principal 对应租户的已发布版本；该激活
按不可变物化快照幂等跳过，Provider Tool Registry 仍不按租户动态变更。
带 `evals/eval.yaml` 的版本发布前必须通过受控 Skill-up Engine；用户不能提供
自定义命令、judge script、MCP server 或环境注入。

### 2.1 Plugin 边界

Plugin 是比 Skill 更宽的扩展协议，不等同于“上传任意代码即可执行”。每个 Plugin
必须有 `PluginManifest`，声明唯一 ID、语义化版本、Plugin API 版本、贡献类型、依赖、
权限、来源和是否可执行。当前内置源码扩展可以贡献 Capability/Tool Provider、Feature、
Renderer 或受信任 Skill；管理端上传的 Skill 只能登记为 tenant-scoped advisory Plugin，
不会导入其 `tools.py`/`scripts/`，也不会获得生命周期执行钩子。

`PluginRegistry` 提供 `register → load → activate → deactivate → unregister` 生命周期，
按依赖拓扑激活，并阻止版本不满足、依赖环和仍有活动依赖者的卸载。插件生命周期只
管理扩展状态；Tool 的执行仍必须经过 Runtime 的统一安全链路。

可部署插件包的根目录可以包含 `plugin.manifest.json`。该文件中的 `manifest` 对应
`PluginManifest`，`files` 保存除自身外所有文件的 SHA-256，`package_digest` 保存确定性
整体摘要，必要时用 `signature_algorithm: hmac-sha256` 和部署密钥签名。`PluginLoader`
只做解析和完整性校验，不根据 `entrypoint` 自动 import；只有受信任部署宿主在完成审核
后，才可以绑定源码贡献对象。用户 Skill 上传仍走 ManagedSkillManager 的 advisory
路径，不要求这个文件，也不会因为包里存在 `tools.py` 就执行它。

可信插件 Manifest 声明的 `permissions` 还必须由部署宿主通过 `PluginLoader` 显式批准；
未提供批准集合时按 fail-closed 处理。用户/管理 API 不能伪造这项部署批准。

## 3. 扩展规则

### 3.0 Plugin SDK 约定

新增可部署扩展优先提供自己的 Manifest 和受信任贡献对象，再由宿主适配到统一注册表；
不要在 Runtime 里新增按插件名分支。当前目录约定 discovery 仍保留作为兼容 Loader，
但所有已发现对象都会发布到 `runtime.plugin_registry`，可通过 `GET /plugins` 查看安全
的生命周期元数据。后续 Plugin SDK 将把目录 discovery 逐步收敛为 Manifest/entrypoint
解析，并补沙箱和跨进程热升级；当前 `PluginLoader.upgrade()` 已覆盖受信任对象的进程内
升级失败恢复，用户上传包仍不可执行。

### 3.1 新增业务流程

如果流程只是在已有原子能力之上重新编排，新增或修改标准 Skill 目录即可：
知识放 `SKILL.md`/`references/`，验收用例放 `evals/`。不要在 Runtime 中添加
渠道判断，不要复制一份 Tool 清单，不要用 `workflow.yaml` 建第二套执行引擎。

大多数业务扩展的落点是：

```text
已有 Tools + 新 Skill（自然语言 SOP / 约束 / evals）
```

只有流程包含跨回合状态机、二阶段数据采集、批量展开或专用结果聚合时，才增加
Skill-owned `RuntimeFeature`；Feature 通过 Runtime 的通用扩展上下文工作，仍不需要
修改 Runtime 主循环。新增外部 API 动作时，才增加 Provider Client + Capability Tool。

### 3.1.1 Wiki 与 Memory

共享广告知识可以写入仓库 `knowledge_base/` 的 Markdown LLM Wiki，也可以由有权限的
用户通过知识库管理 API 保存为租户隔离的 Markdown 文档快照；两者都必须遵循
`SCHEMA.md` frontmatter。Runtime 只通过 `KnowledgeProvider` 读取已发布文档；不得在
Skill、Tool 或 Runtime 中自行扫描文件、维护第二套 Wiki 索引或引入 `workflow.yaml`。
当前知识检索是确定性的词法检索，不接入向量库；检索结果必须有界并带来源、版本和
引用信息。用户知识文档默认是草稿，必须显式发布后才进入检索和 Agent 上下文；修改
应递增版本并保留旧快照，不覆盖既有文档。

Memory 不等同于会话历史、工具审计或 Campaign 状态。跨会话记忆必须通过
`MemoryManager`/`MemoryStore`，并同时受 `tenant_id`、`user_id` 隔离。默认只接受用户
显式记忆请求；不得把原始 Tool payload、凭证、账户配置或未脱敏异常写入 Memory。
Memory 只能作为受限上下文辅助 LLM，不能成为 Tool、权限或账户范围的来源。

### 3.2 新增 Provider API 能力

如果确实需要新的外部动作，按以下顺序在渠道包内完成最小闭环：

1. 在 `api_clients/<provider>_client.py` 增加固定方法；方法名和 endpoint 不能来自用户输入。
2. 在 `capabilities/<provider>/capability.py` 增加 Tool Schema、handler/adapter、
   资源层级、`intent_types`、权限、风险、重放、超时和输出上限。
3. 静态选项放在渠道 Tool schema；账户、App、地域、事件等动态值增加同渠道只读
   lookup Tool，并通过 `lookup_tool`/selection token 关联，不在 Core 写渠道枚举。Provider
   字段兼容别名由 Tool schema 的 `input_aliases` 声明；Core 只做标点无关的通用归一化，
   不维护 `adset_id`、`adgroup_id` 等渠道字段别名表。
4. 在该渠道 `api_surface.py` 标记 implemented 或 planned，并增加 Provider payload、
   schema、权限、dry-run、失败恢复和账户隔离测试。
5. 在该渠道 `_surface_data.py` 的 `OFFICIAL_INVENTORY` 登记官方资源/动作、endpoint
   或 Provider operation、API version、官方 source URL 和当前状态。这个清单是覆盖
   基线，不得写成“官方完整接口总数”；范围不完整时必须声明
   `completeness: scoped_not_exhaustive`。
6. 运行能力审计、契约快照和全量测试后再提交。新增渠道不需要修改 Runtime、Router
   或中心渠道表。

审计必须同时看三条链：

```text
官方能力基线 OFFICIAL_INVENTORY
  -> 当前实现 API_SURFACE
  -> Client method -> Capability Tool -> Runtime
```

`API_SURFACE.status=implemented` 只表示已有代码契约；`execution_status=dry_run_only`
表示尚未通过测试账户 E2E，不能当成 live 能力。官方清单里的 planned 项和报告里的
`gaps_entries` 必须继续可见，不能用增加一个宽泛 Tool 把缺口隐藏掉。

### 3.3 API 版本升级

保持稳定的 Tool 名称和业务输入契约，在渠道 Client 内通过
`version_contract()` 声明实际版本、完整兼容版本列表和请求/响应 adapter；Capability
注册与 `audit_capabilities.py` 会校验 Client、Capability、Tool 三者一致。每次升级都要
补 provider-owned adapter 回归测试和指定测试账户 E2E；不能只修改 `/tools` 返回的版本
字符串。若语义不能安全转换，新版本必须先保持 dry-run 或返回版本不兼容，禁止静默发送
未知 payload。

Google REST Client 的 OAuth access token 必须带过期管理：优先复用未过期 token，
按 refresh-token/client 作用域复用进程内缓存，过期或只读请求收到 401 时自动刷新并
重试一次；写请求禁止因认证失败自动重放。刷新失败必须返回认证错误，不能退回离线
数据或关键词解析。

### 3.4 广告创建 Blueprint

广告创建的级联参数使用 Provider Capability 拥有的声明式 JSON Blueprint，不能把这类
机器可读规则塞进 Skill 的 `references/` 作为唯一事实来源，也不要求用户编写
`workflow.yaml`：

```text
capabilities/<provider>/blueprints/<ad-format>.v<major>.json
```

Blueprint 只描述广告类型、资源层级、Tool Schema 字段引用、可见/必填条件、动态选项
来源以及父字段变化后的 `reset`/`revalidate`/`preserve`/`ask` 影响。它不能包含脚本、
表达式执行、Provider client、MCP、凭证或 HTTP 请求。通用 `BlueprintRegistry` 在
Capability 注册时校验配置，并由 `BlueprintCascadeEngine` 确定性计算字段状态；最终
参数仍必须经过注册 Tool 的 schema、权限、账户和 dry-run/live gate。

Skill 的 `SKILL.md`/`references/` 继续负责自然语言 SOP、业务解释和用户沟通。Blueprint
中的 `tool_ref` 只能引用同一 Capability 已注册的 Tool，静态枚举复用 Tool Schema，
动态值复用只读 lookup Tool。Blueprint 版本不可变，用户保存的 Preset/Template 绑定
具体 Blueprint 版本，升级必须显式预览和迁移，不能静默改变旧模板。

Blueprint 可声明一个入口 `selector`（例如 Meta/TikTok 的 `objective`，或 Google Ads
的 `ad_format`），包含 selector 维度、读取字段、允许值和展示标签。Registry 只按这个
声明解析，不在 Runtime、Router 或上层业务中维护渠道分支；同一创意形式下也可以由
多个 objective Blueprint 并存。

## 4. 广告资源和跨渠道管理

跨渠道对象必须使用 `(platform, account_id, resource_type, resource_id)` 作为完整
身份，不能把不同渠道的数字 ID 互相复用。当前跨渠道 Campaign 批量管理支持暂停、
恢复、预算更新和删除的 dry-run 计划；每个动作均由目标渠道发布的 Campaign Tool
元数据驱动选择，不能在 Core 中写渠道分支。跨渠道操作先生成带逐项状态的本地计划，
再由每个渠道的 Capability 执行或回查；回查 Tool、资源 ID 字段和父资源字段必须来自
渠道 Tool 合约，Runtime 不从工具名推断；失败或不确定结果进入
`unknown`/`recovery_required`，不得把缺失指标填成 0，也不得把一个渠道的成功推断成
另一个渠道的成功。

广告创建优先覆盖完整层级和参数目录：Campaign、下级资源、定向、受众、素材、转化
目标和出价策略。固定枚举必须来自 Provider schema；动态参数必须先 lookup 或在
dry-run 中明确标记未解析。未完成的官方资源写入 API 进入 Surface 的 planned 清单，
不能以一个宽泛 Tool 冒充完整 CRUD。

## 5. 安全红线

- 默认执行模式是 `dry_run`；所有 Campaign 及下级资源写入先规划和校验，不真实调用。
- live 写入同时需要受控测试账户白名单、部署级 live fuse、Tool 白名单、权限和显式确认。
- 未经用户和部署配置明确指定，不得选用线上账户进行写测试。
- 永远不修改或接受为业务更新字段：`access_token`、`refresh_token`、
  `developer_token`、`client_id`、`client_secret`、`private_key`、`bc_id`、
  `partner_id`/`perter_id`、`mcc` 及同义字段。
- 凭证只存在进程内受控 Client；不进入 Skill、LLM 上下文、Tool payload、SQLite、
  错误信息、评测输入或评测报告。
- 读/写对象必须验证账户范围；Provider 对象 ID 不能仅凭格式或用户文本信任。
- 用户输入只能选择已注册 Tool，不能选择 method、endpoint、脚本或命令。

## 6. 性能和可靠性边界

复用进程内 Registry、Skill metadata、Provider Client 和 rate limiter；LLM 上下文只
注入与当前意图相关的有限 Tool。列表、报表和批量操作必须有 page size、最大页数、
调用上限、超时和输出字节上限。外部请求的重试、限流和错误分类放在 Client，跨渠道
并发和逐项状态放在 Runtime/Core。

SQLite 当前按单进程使用；所有持久化依赖必须经过 `PersistenceBackend`，不得把 SQL
泄露到 Skill、HTTP 或 Provider 层。未来换 MySQL/PostgreSQL 时，必须保持事务、幂等
reservation、workflow lease 和租户隔离语义。

长耗时 Agent 回合通过 `POST /tasks` 脱离 HTTP 请求线程，使用 `GET /tasks/{id}` 查询，
并通过 pause/resume/delete 控制本地任务状态。任务输入是闭合的数据契约，默认只允许
`agent.turn`；它不能携带凭证、confirmation token、回调、脚本或任意执行命令。任务
状态与 Workflow 状态保持关联但不复制 Workflow 的资源状态机：Workflow 继续负责广告
计划项审计和恢复，Task 只负责回合调度。SQLite 实现使用有限 worker/queue；跨进程部署
时只需替换 `PersistenceBackend`，不改变 Runtime 的任务契约。

观察性先保留 trace、metrics、告警和审计检索入口，不因为暂未接入而改变 Tool 契约
或安全 gate。

## 7. 提交前门禁

```bash
python3.13 -m compileall -q agents/ad_agent
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. \
  python3.13 -m pytest agents/ad_agent/tests -q
python3 agents/ad_agent/scripts/audit_capabilities.py
python3 agents/ad_agent/scripts/validate_contracts.py \
  --check-snapshot agents/ad_agent/contracts/builtin_tools.json
git diff --check
```

任何能力只有在 Client、Capability、Schema、Surface、测试和契约快照一致后，才算
“已接入”；只有经过指定测试账户的手动验证并加入 live 白名单后，才算“live 已验证”。
