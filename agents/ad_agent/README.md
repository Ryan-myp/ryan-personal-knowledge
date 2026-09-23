# ad-agent - 多渠道广告投放 Agent

基于单 Agent + 多 Skills 架构的广告投放助手，支持 Meta、Google Ads、TikTok Ads、DV360 四大广告平台。当前默认是安全 `dry_run`：写操作可解析、校验和编排，但不会调用线上写 API。

## 架构特点

- **标准 Agent Harness**：单 Agent 通过 Skills、Tool Contract、Policy 和 Tool Executor 工作
- **API 客户端**：封装真实 API 请求、重试、限流和错误分类；live 能力须逐平台验证
- **持久化层**：通过 `PersistenceBackend` 抽象存储会话、工具调用、Campaign 状态、Agent Memory、Task、Outbox 和 Run Event；默认 SQLite 适合单进程，MySQL/InnoDB 可通过连接配置启用多实例共享状态
- **结构化日志**：JSON 格式，便于 log aggregation
- **模型驱动**：生产入口必须配置 LLM；离线 fixture 仅用于显式测试和评测，不是产品降级路径
- **Planner 执行闭环**：每回合由 LLM 解析当前请求和受限 Skill/Tool 上下文，Runtime 依据注册元数据生成确定性计划并执行；业务策略、跨渠道流程和响应展示通过 Skill-owned Policy/Feature/Renderer 扩展；后续回合可读取最近脱敏 Tool 结果继续补参或决策
- **LLM 结果闭环**：执行完成后，LLM 可基于脱敏的工具结果、知识引用和分析结果生成最终回答；输出协议、dry-run 事实和失败事实经过校验，异常时回退到确定性 Renderer
- **安全边界**：写操作必须由当前请求明确提供目标账户、命中配置的测试账户白名单；live 还必须显式确认
- **可扩展**：Tool 可以来自本地 Handler、SDK/HTTP Connector 或 MCP；新增集成不需要修改 Runtime、Router 或中心渠道表
- **业务扩展**：大多数业务只需新增标准 Skill；需要新外部动作时发布 Tool Source/Executor，广告渠道的 Provider Module 只是具体实现
- **跨 Agent 复用**：广告 Skills 可作为标准 Markdown Skill Source 导出，广告 Tools 可转换为通用 Tool Source，能够接入其他 Agent；其他业务也按同一方式接入本 Harness
- **广告创建蓝图**：广告 Provider Module 可提供版本化 JSON Blueprint，描述广告创建字段级联；Runtime 只做通用注册、校验和确定性状态计算，不执行 Blueprint 中的代码
- **统一插件内核**：Tool Source、Feature、Renderer、受信任 Skill 扩展和托管 Skill 上下文统一发布 Plugin Manifest、版本、依赖和生命周期；托管 Skill 始终是不可执行的 advisory Plugin
- **通用可观测性**：广告 Runtime 将安全 Run Trace 接入 Harness `MetricsSink`；默认指标只记录生命周期、Tool 调用计数和耗时，不保存 Prompt、参数、结果或凭证
- **动态平台识别**：解析器从已注册 Tool/Skill 发布 namespace 和自然语言别名，不维护固定四渠道路由表
- **版本兼容**：Tool 声明 Provider API 版本；版本差异由渠道 Client 自己的 adapter 处理，Runtime 不增加渠道分支
- **开发契约**：后续模块遵循 [`AGENT.md`](./AGENT.md)；仓库安全与操作约束见 [`AGENTS.md`](./AGENTS.md)

## 支持的广告平台

| 平台 | Skill | API 客户端 | 工具数量 |
|------|-------|-----------|---------|
| Meta | meta-marketing-api-expert | meta_client.py | 78（账户、Business Manager、Page/Pixel 详情/列表、Image/Video Asset 上传与列表、Custom Conversion CRUD、Lead Form 与 Lead 列表/详情、Audience/Lookalike Audience CRUD、Catalog/Product Set CRUD、层级资源、Traffic/Conversion/Lead/Engagement/Catalog/Messaging Ads、报表与生命周期接口） |
| Google Ads | google-ads-api-expert | google_ads_client.py | 103（层级资源完整 CRUD、CampaignBudget、CampaignCriterion 定向、Conversion Action 生命周期、Conversion Goal、User List 生命周期与 Customer Match 哈希数据上传、BiddingStrategy 生命周期与优化参数、可复用文本/图片/YouTube/HTML5 Asset 创建/移除、Campaign/Asset Group Asset 关联、Search Ad、Responsive Display Ad、Video Ad、Demand Gen、Hotel、Local、Smart、Travel、关键词完整生命周期、Product Group、PMax、Experiment 读写与生命周期、Experiment Arm 查询、报表与生命周期接口） |
| TikTok | tiktok-ads-api-expert | tiktok_client.py | 90（账户列表/详情、层级资源、Ad Group 定向更新、Lead/App/Spark/Product Sales 广告、Creative/Video/Image/Catalog/Product Set 列表与详情、Identity 列表/详情、Creative Portfolio 创建/查询/预览、图片/视频 Asset Library、受众 CRUD、官方定向参考数据、Pixel 生命周期、Pixel 事件、报表与生命周期接口） |
| DV360 | dv360-expert | dv360_client.py | 31（Advertiser、Campaign 查询、IO、Line Item、Creative、定向与异步报表接口） |
| **合计** |  |  | **302** |

> 302 是当前四个 Tool Source 已注册的业务 Tool 数量，不是 Meta、Google Ads、TikTok 或 DV360 官方 API 的完整接口总量。各渠道包的 `_surface_data.py` 同时维护实现 Surface 和 `OFFICIAL_INVENTORY` 官方能力基线；后者必须带 endpoint/Provider operation、API version、官方来源和状态，并明确是否为完整清单。新增官方接口时，应在对应渠道 Client 增加固定方法，在 Tool Source 增加 Tool Schema/adapter，再由 Surface、官方清单审计和契约快照阻止漏注册或漂移。Meta 图片/视频素材当前提供 HTTPS URL 上传与列表，未伪造删除或任意文件上传；DV360 Campaign 创建当前明确为 planned，不会暴露一个无 Client 适配器的假 Tool。

能力完整度要以审计报告为准，而不是 Tool 数量。运行：

```bash
make ad-agent-audit
```

报告分别输出 `api surface`（代码实现覆盖）和 `official inventory`（已登记官方基线覆盖）。
当前官方清单是 `scoped_not_exhaustive`，因此报告中的比例只能用于当前基线治理；要宣称
某渠道完整，必须先把该渠道官方资源/动作清单补齐，并为每项补 operation-specific source
或 Provider E2E 证据。当前实现默认 `dry_run_only`，即使出现在 `covered` 里也不代表已验证
live。

### 广告类型覆盖边界

广告系列层级、下级资源和具体素材格式按
[`docs/ad-platform-hierarchy-guide-v5.md`](/Users/yanping.ma/ryan-personal-knowledge/docs/ad-platform-hierarchy-guide-v5.md)
建立渠道自有目录，并通过 `GET /ad-formats` 对外提供。当前目录覆盖：

- Google Ads：Search、Performance Max、Shopping、Video、Display、App，以及 RSA、PMax Asset Group、Product Group、Video/Display 子格式。
- Meta：Traffic、Conversion、Lead、Engagement、Catalog、Messaging，以及图文、视频、Instant Form、Dynamic Product、Click-to-Message 子格式。
- TikTok：Product Sales、Spark、Lead Generation、App Promotion、Brand，以及 Shop、Instant Form、TopView、Brand Takeover 子格式；Lead Instant Form 与 App Install 已有专用 dry-run contract。
- DV360：暂保留已有基础 Tool Source，详细广告类型目录和专用 payload 暂缓建设。

目录中的 `supported_dry_run` 表示已有专用 payload contract，`partial_dry_run` 表示层级或部分字段可规划，`declared_only` 只表示已纳入能力地图，不能当作可执行或已验证的 live 能力。所有写操作当前仍为 dry-run。

广告创建蓝图通过 `GET /creation-blueprints` 提供给向导，前端提交当前草稿到
`POST /creation-blueprints/{blueprint_id}/evaluate` 获取字段可见性、必填状态和受影响
字段；也可以通过 `POST /creation-blueprints/resolve` 按 Blueprint 声明的 selector
解析入口。两个接口都是本地元数据计算，不会调用广告渠道 API。Meta 按 objective 选择
流量、转化、潜客或目录销售；TikTok 按 objective 选择 App、流量、潜客或商品销售；
Google Ads 按广告系列类型选择 Search、Display、Video、App、Shopping 或 Performance
Max。每个 Blueprint 仍只引用同一渠道已注册的 Tool schema，动态 lookup 继续按 dry-run
边界等待后续受控接入。

## 安装

```bash
make ad-agent-install
```

## 快速开始

本项目统一使用 Python 3.13。请从仓库根目录执行 Make 命令，或使用
scripts/ad-agent-python；不要直接使用 macOS 系统的 python3。包装器会在启动前校验
解释器版本，避免 3.9/3.11 环境导入代码时出现难以定位的语法错误。

常用命令：

    make ad-agent-python-version
    make ad-agent-run
    make ad-agent-check

```python
import os

from ad_agent import AdvertisingComposition, create_meta_tool_source, create_google_tool_source
from ad_agent.core.llm_client import create_llm_client
from ad_agent.persistence.store import AdAgentStore

# 初始化（LLM 驱动、默认 dry-run，带持久化）
store = AdAgentStore("ad_agent.db")
runtime = AdvertisingComposition(
    persistence_store=store,
    require_llm=True,
    llm_client=create_llm_client(
        model=os.environ["LLM_MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL"),
    ),
)

# 广告 Tool Source（写操作仍只生成 dry-run 计划）
runtime.register_tool_source(create_meta_tool_source())
runtime.register_tool_source(create_google_tool_source())

# 通用 Harness 入口也可以直接注册 Tool 或 MCP/HTTP Tool Source：
# runtime.register_tool(tool_definition, executor)
# runtime.register_tool_source(source)

# 运行对话
result = runtime.run(
    user_input="帮我投放Meta和Google广告，预算100元/天",
    user_id="user_001",
)

print(result["reply"])
```

`AdvertisingComposition` 默认要求已注入 LLM；不会在模型不可用时自动切换为规则解析。
只有测试或明确的离线工具才可以显式传入 `require_llm=False`，并且这不代表产品运行模式。

### Markdown LLM Wiki 与 Agent Memory

知识库采用 Karpathy 风格的 Markdown-first LLM Wiki：`index.md` 做导航，`log.md`
记录变更，`raw/` 保存来源，`entities/`、`concepts/`、`comparisons/` 和 `queries/`
表达知识对象；现有 `platforms/`、`business/`、`expertise/` 作为概念页的稳定领域存储继续兼容。
知识文件使用 [`knowledge_base/SCHEMA.md`](./knowledge_base/SCHEMA.md) 的 frontmatter
描述来源、版本、置信度和状态。除了仓库内置文档外，用户还可以通过
`POST /knowledge/documents` 保存租户隔离的 Markdown 文档，使用
`POST /knowledge/documents/{document_id}/publish` 显式发布，并通过
`GET /knowledge/documents` 管理当前租户文档。修改使用新的语义化版本，保留旧快照，
与 Skills 管理采用相同的“不可变版本 + 显式发布”思路。知识写入需要 `knowledge.write`
权限，检索仍需要 `ads.read`；草稿和废弃文档不会进入召回。

推荐的新文档流程是 `POST /knowledge/raw`：服务先按
`tenant_id + sha256` 去重，写入不可变 raw source，再排入受控的
`knowledge.ingest` durable task。worker 只允许调用结构化 `LLM.call_json`，根据当前已发布
Wiki 目录生成 entity/concept/comparison/query draft，并记录
`source_ref=raw://...`、`derived_from`、`raw_sha256` 和 `wikilinks`。LLM 不能指定文件路径、
执行代码或直接发布页面；人工审核后仍需调用原有的
`POST /knowledge/documents/{document_id}/publish`。Runtime 检索只读取已发布派生页，不会直接读取 raw source。
同一个 source 由 Store 原子地从 `received/failed` 领取到 `ingesting`，并记录
`ingest_attempts`、任务 ID、开始和完成时间；并发重复任务只有一个能领取。失败会保留
安全错误摘要并允许重试，`draft_ready` source 默认不可再次 ingest，避免重复生成派生页面。
如果 worker 在 `ingesting` 阶段中断，过期 claim 会被 recovery 标记为 `failed`，
下一次任务可以安全重试。

`core.knowledge.KnowledgeProvider` 统一提供确定性的标题/标签/正文词法检索，不接入
向量库。知识库搜索会先展示 LLM 生成的业务摘要，再展示带 Markdown 格式的内容摘录
和来源；LLM 暂不可用时使用确定性摘要，不影响文档检索。用户提交的文档不能包含凭证
字段，也不能创建 Tool 或改变权限。
知识服务依赖窄化的 `KnowledgeStorePort`，不会把完整广告持久化后端暴露给 Wiki；
历史 Markdown 页可用 `scripts/normalize_knowledge_metadata.py --write` 补齐 provenance
字段，该工具只改 frontmatter，不改正文、版本或发布状态。

Memory 与 Wiki、Session、Tool Audit 分离。只有显式的“记住/保存”请求才会创建长期
Memory；Runtime 仅在同一 `tenant_id + user_id` 范围内做有界召回，Memory 不能创建
Tool、权限、账户范围或凭证。SQLite 的 `memories` 表通过 `PersistenceBackend` 访问，
未来替换 MySQL/PostgreSQL 不需要修改 Runtime。

## 使用真实 API（仅测试账号）

```python
import json

# 加载凭证
with open("credentials.json") as f:
    credentials = json.load(f)

# 传入真实客户端；Runtime 仍默认为 dry-run
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.tools.providers.meta import create_meta_tool_source

api_client = MetaAPIClient(credentials["meta"])
provider_tools = create_meta_tool_source(api_client)

runtime.register_tool_source(
    advertising_tool_source(
        provider_tools,
        source_id="provider:meta",
    )
)
```

切换到 `execution_mode="live"` 前，必须确认 `agents/ad_agent/config.yaml` 中已配置目标测试账号白名单，并先取得当前写入计划返回的 `confirmation_payload`，随后以同一 payload 调用 `runtime.run(..., confirmed=True, confirmation_payload=payload)`。HTTP API 会拒绝缺少该 payload 的确认请求。HTTP 的执行模式按租户和用户隔离，单回合也可以通过 `execution_mode` 覆盖；不要通过凭证内容自动扩大白名单，凭证只保存在进程内，不写入 SQLite。写操作（创建、更新、删除、暂停/恢复及批量写）即使白名单只有一个账户，也必须在当前请求中显式传入目标账户；单账户自动兜底只适用于只读查询，避免误选广告主。

当前所有 Campaign/下级资源创建默认只生成 dry-run 计划；DV360 IO/Line Item 更新、Google PMax Asset Group 以及部分下级资源更新没有经过验证的 live adapter，live 会明确返回不支持。DV360 Campaign 创建尚未建设，API Surface 会将其标为 planned，Runtime 不会路由到不可执行的假 Tool。读取请求在没有 Provider Client 时默认 fail-closed，只有显式 `offline_mode=True` 才会返回离线 fixture。

页面顶部的“执行模式”面板可以切换当前 principal 的 `dry_run` / `live` 模式；该选择不修改
`config.yaml`，而是按 tenant/user 通过 `PersistenceBackend` 持久化，重启服务后仍保持。
切换面板只需要当前身份拥有 `ads.plan`，并将模式按 tenant/user 隔离持久化；这一步不会授予
写权限，也不会调用广告平台 API。实际 live 写操作仍必须同时满足 `ads.write`、
`AD_AGENT_ENABLE_LIVE=1`、`allow_live_writes: true`、非只读配置、显式账户、测试白名单、
Tool 批准清单和当前计划的二次确认信息。若这些条件未满足，模式可以显示为 live，但写 Tool
会在统一 Runtime 执行门禁处被拒绝，并记录原因。

### 异步任务与身份、权限和恢复边界

长耗时 Agent 回合可通过 `POST /tasks` 脱离 HTTP 请求线程，使用 `GET /tasks/{id}` 查询，
并通过 `/pause`、`/resume` 和 `DELETE` 控制本地调度。任务输入只允许已注册的
`agent.turn` 数据契约；不接受凭证、confirmation token、回调或脚本。worker 会重新进入
Runtime 的完整 LLM/Skill/Tool/权限/账户/dry-run/审计链路，不能直接调用 Provider Handler。
任务状态的暂停/取消不代表外部广告平台状态已回滚；运行中的底层网络调用只能 cooperative
cancel，超时或进程中断则进入 recovery_required，等待显式恢复/回查。

这里要区分两条队列：`tasks` 是 Agent 执行队列，负责让 worker 重新进入统一
`Runtime.run()`；`outbox_events` 是事务后的事件投递队列，负责向 SSE/Webhook/指标等
sink 投递已落库事件，不能用 Outbox 代替 Task 执行。任务和 Outbox 都是持久化记录，
各实例通过 lease/数据库 claim 竞争消费；因此服务重启后会重新扫描 `queued` Task，
而已进入 Provider 操作但租约过期的 Task/Run 会进入 `recovery_required`，不会盲目重放写操作。

身份、权限和恢复边界

HTTP 请求不会信任 JSON/query 中的 `user_id`。服务端应通过已认证的 API Gateway
配置 `AD_AGENT_API_KEY_PRINCIPALS`，把 API key 映射为 `user_id`、`tenant_id`、
`permissions` 和 `account_scope`；单 API key 部署则使用配置的 service principal。
Runtime 会将身份账户范围与 `config.yaml` 的测试账户白名单取交集。默认权限只有
`ads.read`、`ads.plan`，live 写入还必须显式授予 `ads.write`，并同时满足 live 开关、
工具白名单和 confirmation payload。

Workflow 的 `/workflows/{id}/resume-plan` 只返回待恢复 item，不会自动重放；
`/workflows/{id}/reconcile` 只接受带 `verified=true` 的 Provider 观测。
`/workflows/{id}/reconcile/provider` 会通过渠道注册的只读回查 Tool 解析 pending/unknown item，仍不会重放写操作。
Provider timeout、连接错误、限流和 5xx 等无法确认最终结果的写入会标记为 `unknown`，保留
幂等 reservation 并进入 `recovery_required`，避免恢复流程绕过原有审批和幂等门禁。HTTP
reconcile 还需要显式 `ads.reconcile`（或 `ads.write`）权限；`verified` 不是权限，
而是恢复 worker 对观测来源完成校验后的声明。

部署探针使用 `GET /health` 做进程存活检查，使用 `GET /readyz` 做请求就绪检查。后者会
检查 Runtime、必需的 LLM、Tool Registry、持久化后端和已启用的 durable worker 是否已就绪，
不会调用 Provider，也不会
返回凭证；ASGI 生命周期结束时会关闭 Runtime-owned TaskExecutor，避免热重载留下后台任务。

运行监控入口位于页面顶部“系统运维”菜单中的“运行监控”，后端接口为
`GET /monitoring/overview`，沿用当前 API Key 与 `ads.read` 权限。它返回当前 principal
范围内的 Durable Task 队列、Task/Workflow/Session lease、Run/Workflow recovery、Outbox
投递、Tool 调用成功率/平均延迟，以及当前进程 worker/consumer 状态；页面每 15 秒刷新一次。
共享 MySQL 部署中，队列和租约统计来自同一份 InnoDB 状态，当前实例卡片只代表本机进程，
不把 Outbox 误当成 Agent 执行队列。

Workflow 在执行前预登记 write item，并通过 upsert checkpoint 更新状态；Task、Outbox、
Workflow 和 Session 都通过 `PersistenceBackend` 的租约/claim 边界协调。SQLite 的进程级
实证只用于验证契约，SQLite 仍明确限制为单进程部署；配置
`AD_AGENT_DATABASE_URL=mysql+pymysql://...`
后使用 MySQL/InnoDB 的事务、`FOR UPDATE SKIP LOCKED` 和跨实例 Session lease，
Runtime、Skill、Tool、Tool Source 代码无需修改。运行中的 workflow 会 heartbeat，恢复 worker
通过持久化 lease 原子 claim，避免把新鲜任务误判为可恢复或被多个 worker 同时接管。

Outbox 投递采用有界重试（默认 10 次）；超过上限的事件进入 `dead_letter`，不会无限占用
投递轮询，并会在运行监控的告警中显示。这里仍然是 at-least-once 投递语义，外部 sink
必须按 `event_id` 做幂等处理。

当任务已经进入 `recovery_required` 时，HTTP 只能通过
`POST /tasks/{task_id}/recover` 显式提交 `provider_verified=true`、回查记录
`recovery_reference` 以及 `ads.reconcile`（或 `ads.write`）权限；接口随后重新进入统一的
`agent.turn` 队列，不会绕过 Runtime 的 Skill、Tool、账户、确认和审计门禁。事件落库失败会
进入 `execution_event_repairs` 补偿队列，避免一次短暂数据库异常让前端永久丢失 Run Event。
Worker 注册与心跳则写入 `worker_instances`，运行监控可区分共享队列状态和当前进程状态。

仓库提供进程级可靠性实证：

```bash
make ad-agent-reliability-evidence
```

它会启动独立进程，验证 Session lease 互斥、Task 单次 claim、两个 Worker 竞争同一
`agent.turn`，以及 Worker 崩溃后进入 `recovery_required`、经过显式回查引用后才能重新
排队。报告只保存状态、计数和脱敏摘要，不调用 Provider。该报告证明的是共享持久化契约和
Runtime 边界，不等同于已经完成生产集群部署、MySQL 压测、跨可用区故障演练或 Provider
live 验证；`release_readiness` 会将 `reliability_evidence` 与
`production_deployment_attested` 分开记录。

### 存储后端与部署切换

默认配置保持 SQLite：

```bash
AD_AGENT_DB_PATH=/path/to/ad_agent.db
```

多实例部署只需要改为：

```bash
AD_AGENT_DB_BACKEND=mysql
AD_AGENT_DATABASE_URL='mysql+pymysql://user:password@db-host:3306/ad_agent?charset=utf8mb4'
AD_AGENT_DB_POOL_SIZE=5
AD_AGENT_DB_MAX_OVERFLOW=10
```

MySQL schema 使用 InnoDB，启动时执行版本化 schema baseline；任务抢占、Outbox 抢占、
幂等键、Session lease 和 Run Event replay 使用同一个后端契约。SQLite 与 MySQL 的差异
只存在于 `persistence/`，HTTP、Runtime 和 Provider Tool Source 不直接写 SQL。

动态 Skill 可以提供 `skill.manifest.json`，其中包含插件文件 SHA-256；生产环境可
通过 `AD_AGENT_REQUIRE_SKILL_MANIFEST=1` 和 `AD_AGENT_SKILL_MANIFEST_KEY` 要求签名。

### 创建参数与枚举

创建工具的输入契约由 `ToolSchema` 暴露：固定枚举放在字段的 `enum`，例如 TikTok 的 `objective_type`、`promotion_type`、`billing_event`、`bid_type`、`placement_type` 和 `deep_bid_type`；App、地域等动态值则通过字段上的 `lookup_tool` 指向 `tiktok_list_apps` / `tiktok_list_locations` 等查询工具。字段之间的依赖放在 `conditional_rules`，例如 `APP_ANDROID` 必须同时提供 `app_id`、`operating_systems`、`deep_bid_type`，且计费事件为 `OCPM`。

`SimpleToolRegistry` 在执行前统一校验类型、固定枚举、数组元素和条件依赖；`/tools` 返回完整 `input_schema`，因此前端或 LLM 可以据此渲染参数选择器。动态 Provider 选项不会被伪造为静态枚举：dry-run 使用已知契约，live 再由 Provider contract 和真实查询结果收口。

Provider live lookup 返回的动态选项会附带短时 `selection_token`。创建请求在对应工具的
`selection_tokens[field]` 中提交它，Runtime 会校验 token 的签名、有效期、用户、会话、账户、字段、目标工具和来源查询工具；因此 live 不能直接伪造 App/地域 ID。多实例部署时应通过
`AD_AGENT_SELECTION_TOKEN_KEY` 配置所有实例共享的签名密钥。

动态字段的 `lookup_tool` 在 Skill 注册时还会被检查：来源工具必须已注册、属于同一渠道且是只读工具。没有 Provider Client 时，live 写入会 fail-closed，不会把 Handler 的离线 fixture 当成线上成功。

表单或前端需要实时加载账户相关参数时，调用 `GET /parameter-options/resolve`，
传入 `platform`、`field`、`tool_name`、`account_id` 和可选 `session_id`；认证主体
由 `X-API-Key` 对应的 principal 提供，接口不会信任 query/body 中的用户身份。该接口
只解析动态 lookup，固定枚举仍使用 `GET /parameter-options`。

### Harness Engineering 评估

当前核心 Harness 已具备：受限 Tool/Skill 契约、统一 Runtime 执行入口、Skill-owned Policy/Feature 扩展、权限/账户白名单、dry-run、显式确认、持久化幂等、workflow checkpoint/lease/recovery、Provider 回查入口、LLM 输出后的二次 schema 校验，以及下一回合可用的脱敏 Tool 结果上下文。另有 `scripts/audit_provider_tools.py`、`scripts/validate_contracts.py` 和 `contracts/builtin_tools.json` 提供 API Surface、版本化契约快照、Provider 方法覆盖率和 drift gate。跨渠道批量状态保持为 `ACTIVE/PAUSED` 中性值，最终字段和值由所选 Tool 的 Provider Schema 映射。结论是“核心骨架符合，尚未达到生产闭环”，不能把当前 302 个工具数或单元测试通过当成 Provider live 已验证。

#### 发布就绪门禁与证据分层

现在使用统一的 readiness 报告把四层证据分开，避免把 Tool 数量或本地模拟结果当成线上能力：

| 层级 | 证明什么 | 本地是否可运行 |
|------|----------|----------------|
| `code_contract` | Tool Source、Tool schema、权限、版本和 snapshot 一致 | 是 |
| `dry_run` | Runtime → Tool → Tool Source → Client 的本地调用链和 Skill-up case | 是 |
| `provider_e2e` | 指定渠道测试账户上的逐接口真实读写证据 | 否（需受控环境） |
| `live_verified` | 经过 live fuse、白名单、确认和审计的逐接口证据 | 否（需批准环境） |

本地默认门禁：

```bash
./scripts/ad-agent-python agents/ad_agent/scripts/release_readiness.py --profile local
```

本地 Provider contract harness 使用记录型 Client，不产生任何外部请求：

```bash
./scripts/ad-agent-python agents/ad_agent/scripts/provider_contract_harness.py
```

`release` profile 会要求后两层证据；在尚未接入受控 Provider E2E 证据前，失败是预期的，不能通过改 Tool 数量或把本地 stub 标成 live 来绕过：

```bash
./scripts/ad-agent-python agents/ad_agent/scripts/release_readiness.py --profile release
```

门禁规则位于 [`contracts/readiness_policy.json`](./contracts/readiness_policy.json)，Provider 本地场景位于 [`contracts/provider_contract_scenarios.json`](./contracts/provider_contract_scenarios.json)。新增渠道时只需新增自己的 Tool Source、Tool 和对应的本地场景证据；Runtime/中心 Router 不增加渠道分支。

当前已增加统一 `PluginRegistry`：所有内置 Tool Source、Runtime Feature、Response Renderer、受信任可执行 Skill 和租户托管 Skill 都登记为带 `PluginManifest` 的扩展，并提供依赖排序、版本约束、启停/卸载和安全快照；`GET /plugins` 只返回 Manifest 与生命周期元数据。这个阶段完成的是插件内核和声明式接入，不代表已经支持任意第三方代码热加载。
Runtime 对 Tool Source/Skill 的注册、卸载和派生索引刷新使用同一把生命周期锁；
执行请求仍可并发，但不会在注册中途观察到半套 Tool 或 Skill ownership 状态。卸载失败时
会回滚 Registry、参数目录、Blueprint、SkillLoader、格式目录和 Parser catalog。

插件包可以使用根目录 `plugin.manifest.json` 描述 `PluginManifest`、文件 SHA-256、整体
`package_digest` 和可选 HMAC 签名。`PluginLoader.load_package()` 只验证声明和文件完整性，
不会导入 `entrypoint` 或执行包文件；可执行插件必须由受信任部署宿主绑定已审核的源码
贡献对象。管理端上传的标准 Skill 不要求该文件，仍然只是不可执行的 advisory context。

管理端还支持 `POST /plugins/packages/archive` 导入标准 ZIP，并提供版本级 `health` 检查；
健康检查只验证摘要、声明一致性和租户内依赖，不进行代码探针。

可用 `./scripts/ad-agent-python agents/ad_agent/scripts/audit_provider_tools.py` 做无网络能力审计；它按
Tool Source 包约定自动发现渠道，输出 action/resource 矩阵和创建链，不是 Runtime 的第二套
渠道注册表。

创建参数还可用 `./scripts/ad-agent-python agents/ad_agent/scripts/audit_creation_contracts.py --strict-guided`
做发布前审计。它会逐字段报告 `enum` 固定选项、`lookup` 动态查询、`manual_entry` 人工
录入、`upload` 素材上传、`context` 账户/父级上下文、`inherited` 级联继承、`free_text`
自由输入和 `structured` 结构化输入，并检查资源字段是否缺少受控来源、Lookup 是否为同
渠道只读 Tool，以及 Blueprint 展开后的必填字段是否完整。新增 Provider 字段不需要修改
Runtime；只要补齐自身 Tool Schema/Lookup/Blueprint，审计即可自动发现缺口。对于没有子
字段 Schema、只能退化成 JSON 的对象参数，审计还会单独列出结构化引导缺口，并标记它是否
出现在现有 Blueprint 中，避免把高级 Provider Payload 误呈现为完整表单。

插件生命周期可通过 Runtime SDK 或 `GET /plugins` 检查；注册表不会绕过 ToolRegistry 的
Schema、权限、账户、dry-run、确认、幂等和审计门禁。后续仍需补可信插件的
沙箱/独立进程和生产级运行时探针。受信任部署宿主的 `PluginLoader.upgrade()` 已提供
进程内升级失败自动恢复旧贡献对象的契约。插件控制面已提供
`/plugins/packages`：按租户保存不可变的 Manifest + 完整文件快照，支持版本发布指针、
回滚（重新激活旧版本）、停用和卸载。这个 API 只做校验和控制面状态变更，不会导入
`entrypoint`、执行 `tools.py`，也不会向 Runtime 注册 Provider Tool；可执行插件仍需
受信任部署宿主绑定已审核的源码贡献对象。

### Runtime 边界结论

广告 `AdvertisingComposition` 是应用组合根：它把广告 Skill、Provider Module、Feature、
Policy、Renderer 和持久化端口装配成一个可运行应用。它不是通用 Core，也不应继续增加
通用队列、租约或 Provider 分支。通用执行壳是 `agents/agent_harness/`，队列/Outbox/
Schedule 生命周期由 `runtime/supervisor.py` 管理；新增广告业务应优先落到 Skill、Tool、
Tool Source/Executor 或独立 Feature。

当前装配图已经收敛到 `runtime/ad_application_assembly.py`：`AdvertisingComposition` 负责广告应用
配置、能力注册入口和稳定门面，`AdApplicationAssembly` 负责把 `PersistenceBackend`、通用
`AgentRuntimeKernel`、Tool 执行器、Schedule/Task/Outbox worker 与广告应用服务接起来。
Assembly 只做依赖连接，不根据渠道或业务流程分支；新的简单能力仍应通过 Skill + Tool/MCP
Tool 扩展，只有需要可信执行代码、特殊恢复或新的应用控制面的能力才新增 Provider Module/Feature。

暂留的工程缺口：

- 当前监控页提供持久化运行态聚合和 Tool 审计摘要；通用 Harness 已提供
  `MetricsSink`、`TraceSink`、`AlertSink`、`CredentialProvider`、`QuotaProvider` 端口，
  Runtime readiness 也会输出 `DeploymentHealth`。生产部署仍需注入具体 exporter/告警适配器，
  并把 `queue depth`、lease expiry、recovery count、Provider latency 等指标接入统一平台。
- Plugin 包控制面已支持租户隔离、版本不可变、摘要校验、依赖激活门禁和发布回滚；
  已支持标准 ZIP 导入和不执行代码的完整性/依赖健康检查；仍待补可信插件的沙箱/独立
  进程、签名来源策略的部署配置和生产级运行时探针。
- MySQL/InnoDB backend 已提供连接配置、版本化 schema、共享事务、幂等 reservation、Task/Outbox claim、Session/Workflow lease 和 principal execution-mode preference；仍需在正式部署前补压测、死锁重试策略和生产级指标告警。
- Provider schema 目前以代码契约为准，已接入本地版本化快照和代码契约 drift gate；尚未接入 Provider API schema 拉取和真实测试账户 E2E。动态组合约束仍需按渠道逐项补齐。
- 部分 workflow 只标记 `compensation_required` 并转人工复核，尚无经过 Provider 验证的自动补偿执行器；这属于刻意的安全降级，不是已完成能力。
- live 还需要凭证轮换/授权中心、合作方级配额策略，以及 Provider 调用级别的真正可中断
  能力；当前异步 worker 已支持任务级 cooperative cancellation，但无法强制终止一个
  已进入底层网络调用的线程。ToolExecutor 已对这类超时中的后台调用设置有界容量，
  防止连续网络阻塞造成线程无界增长；容量耗尽时会明确返回资源繁忙，不伪装成 Provider
  结果。
- 当前四个 Client 已提供版本元数据和 adapter 接口，Tool Source 注册与能力审计会校验 Client、Tool Source、Tool 三者的 Provider contract；每个平台目前仍只声明一个实际支持版本。升级时仍需要在渠道 Client 增加真实新版本、请求/响应 adapter、Provider contract 回归和测试账户 E2E，不能只修改 Tool 上的版本字符串。

因此下一阶段应优先做“Provider schema 对照 + 测试账户 E2E”，再逐个把工具加入 `live_approved_tools`，而不是一次性开放全部渠道写入。代码契约漂移可先通过以下 release gate：

```bash
./scripts/ad-agent-python agents/ad_agent/scripts/validate_contracts.py --check-snapshot agents/ad_agent/contracts/builtin_tools.json
```

更新操作同样使用渠道拥有的嵌套 Schema：Meta、Google Ads、TikTok、DV360 的 `updates` 只允许当前适配器声明的字段，未知字段会在计划阶段报错，不会静默丢弃或带入 live 请求。缺少带 `lookup_tool` 的动态字段时，返回结果中的 `confirmation_payload.lookup_tools` 会告诉调用方应先调用哪个查询工具。通用目标（sales/leads/traffic/brand）由各 Skill 的字段元数据映射为 Provider 枚举，不由 Runtime 维护一张不可扩展的渠道表。

dry-run 结果中的 `provider_validation` 会单独标记 Provider 必填字段是否齐全：计划可以先生成，但 `ready: false` 时不能视为可直接 live 执行。

### Provider 接口扩展与版本升级

新增接口的最小闭环是：

1. 在渠道自己的 `api_clients/<provider>_client.py` 增加固定、可测试的方法；不要把用户输入的方法名直接转发到 HTTP。
2. 在渠道自己的 `tools/providers/<provider>/provider.py` 用 `method_tool()` 或显式 `ToolDefinition` 暴露 Schema、枚举、条件依赖、权限、超时和资源层级。
3. 需要账户 App、地域、事件等运行时选项时，增加同渠道只读 lookup Tool，并在字段上声明 `lookup_tool`。
4. 对可能需要结果回查的写 Tool，声明 `resource_id_field`、`parent_resource_id_field` 和可选 `readback_tool`；Runtime 不从 Tool 名称或资源类型猜 ID/回查接口。
5. 运行 `audit_provider_tools.py`、`validate_contracts.py` 和 Provider 回归测试，确认接口已注册、契约稳定且创建链没有断点。

Provider API 升级时，保持稳定的 Tool 名称和业务输入契约，在渠道 Client 中增加
`SUPPORTED_API_VERSIONS` 与 `VERSION_ADAPTERS[旧版本]`，并通过
`version_contract()` 校验实际版本、兼容版本和 adapter 是否完整，由 adapter 改写请求和
响应；Runtime 只做版本兼容检查，不需要新增渠道分支。若新旧版本语义无法安全转换，则
让该 Tool 暂时返回版本不兼容并保持 dry-run，避免静默发送错误 payload。

Google Ads 当前使用 REST Client 而不是可选的 `google-ads` SDK。Client 会根据
`access_token` 的过期时间复用进程内缓存；缓存过期或只读请求收到 401 时，使用
`refresh_token + client_id + client_secret` 调用 Google OAuth token endpoint，
刷新后重试当前只读请求。刷新锁按进程生效，写请求不会因为 401 自动重放；多实例部署
需要在各实例分别配置凭证并由部署层管理共享的 OAuth 凭证。

凭证文件格式：
```json
{
  "meta": {
    "access_token": "EAABs..."
  },
  "tiktok": {
    "access_token": "7012345678901234567"
  },
  "google": {},
  "dv360": {
    "service_account_email": "sa@project.iam.gserviceaccount.com",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\n..."
  }
}
```

## 架构设计

仓库整体六层 Agent 中台架构见
[`docs/agent-platform-architecture.md`](../../docs/agent-platform-architecture.md)。
广告在其中属于应用场景层，复用单一通用 Agent；通用 Run/Session/Tool/Skill 执行能力由
[`agents/agent_harness`](../agent_harness/) 与
[`agents/agent_platform`](../agent_platform/) 提供。

可直接打开交互式架构图：[`docs/ad_agent_architecture.html`](../../docs/ad_agent_architecture.html)。
图中标注了单 Agent、多 Skills、Tool Registry、Tool Sources/Executors，以及异步 Task、Outbox、Run Event、恢复和后续 MySQL 演进关系。

Runtime Harness 分为四个可组合部分：`agents/agent_harness/runtime_kernel.py` 负责最底层的请求身份规范化、
Session 并发/租约、执行模式和 Run identity；`agents/agent_harness/agent.py`
提供维护 transcript 的通用 model→Tool→model loop；`agents/agent_harness/turn_pipeline.py`
提供通用 Turn Handler 适配契约；`agents/agent_harness/agent_runtime.py`
通用 Harness 提供可嵌入的 `agents.agent_harness.AgentRuntime` 门面；
`agents/agent_harness/tool_catalog.py`
提供不依赖广告域的 Tool catalog。任意应用都通过同一个 Harness Agent 或
Turn Handler 执行，不再创建业务 Pipeline。

广告的 `runtime/ad_application.py` 是场景组合根，负责把广告 Skills、Tools、Provider
Modules、数据适配和基础设施资源注入唯一的平台应用。广告不再拥有自己的 Pipeline、
Stages 或回合状态机；`runtime/ad_application_assembly.py` 只提供一个符合 Harness
契约的 Turn Handler。`runtime/runtime.py` 仅作为稳定导出入口。Generic Runtime
通过 opaque `TurnRequest.context` 与场景交换领域数据，因此新增业务 Skill/Tool
不需要把账户、渠道或业务流程分支写回 Core。

工具选择也分成两个层次：`core/tool_selection.py` 的 `ToolSelector` 只读取 Tool
publisher metadata 和解析后的 intent，`PromptRenderer` 只负责生成有界的模型上下文；
`core/tool_selector.py` 的 `DynamicToolSelector` 负责知识库、Skill 和租户上下文的
组合与筛选，不承担 Tool 执行、权限授予或业务路由。

执行策略由 `agents/agent_platform/tools/policy.py` 的
`ToolExecutionPolicy` 统一计算。它把 Tool 声明的
权限、Scope、Effect、live 能力、批准清单和 WriteGuard 状态转换成不可变的
`PolicyDecision`；dry-run 规划和 live 执行因此使用同一份契约但拥有不同门槛。
确认卡片和确认 token 仍由应用安全服务生成/消费，ToolExecutionPolicy 不解析 UI payload，
避免把展示协议带回 Core。

```
┌─────────────────────────────────────────────────────────────┐
│                        AdvertisingComposition                         │
│   ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │
│   │ IntentParser │  │IntentRouter │  │   ToolRegistry     │   │
│   │ (LLM)        │  │ (多平台)    │  │   (工具注册表)      │   │
│   └─────────────┘  └─────────────┘  └───────────────────┘   │
│                             │                                │
│   ┌─────────────────────────┼─────────────────────────────┐  │
│   │                   ToolSourceLayer                     │  │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│   │  │ Meta     │ │ Google   │ │ TikTok   │ │ DV360    │ │  │
│   │  │ Cap      │ │ Cap      │ │ Cap      │ │ Cap      │ │  │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │  │
│   └───────────────────────────────────────────────────────┘  │
│                            │                                  │
│   ┌────────────────────────┼───────────────────────────────┐ │
│   │                  API Clients Layer                      │ │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│   │  │ Meta     │ │ Google   │ │ TikTok   │ │ DV360    │ │ │
│   │  │ Client   │ │ Client   │ │ Client   │ │ Client   │ │ │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│   └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Persistence Layer                        │
│   ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │
│   │   Sessions  │  │ Tool Calls  │  │ Campaign State    │   │
│   │  (SQLite)   │  │  (SQLite)   │  │   (SQLite)        │   │
│   └─────────────┘  └─────────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
ad_agent/
├── __init__.py              # 包入口
├── core/
│   ├── agent_runtime.py     # Agent Harness Runtime 导出
│   ├── runtime_kernel.py    # 请求/会话/租约生命周期内核
│   ├── interfaces.py        # 核心接口定义
│   ├── tool_selection.py    # 通用 Tool 选择与 Prompt 渲染
│   ├── tool_selector.py     # Skill/知识上下文兼容适配层
│   ├── policy_engine.py     # 平台 ToolExecutionPolicy 的广告导出
│   ├── tool_registry.py     # 工具注册表与来源生命周期
│   ├── tool_sources.py      # ToolBinding/ToolSource/Executor 契约
│   ├── turn_pipeline.py     # 通用回合阶段与终止/错误语义
│   └── intent.py            # 意图解析与路由
├── runtime/
│   ├── runtime.py           # 稳定公共导出入口（不承载主循环）
│   ├── ad_application.py    # 广告应用组合根
│   ├── ad_application_assembly.py # AgentPlatform 场景装配
│   ├── task_executor.py     # 通用异步 Task 队列与租约
│   ├── scheduler.py         # 通用定时任务调度
│   ├── supervisor.py        # 后台 worker 生命周期
│   └── skill.py             # Skill 加载
├── tools/providers/
│   ├── base.py              # 能力基类
│   ├── factory.py           # 按包约定发现 Tool Source
│   └── <platform>/provider.py  # 渠道能力包
├── api_clients/
│   ├── base.py              # 客户端基类（重试/限流）
│   └── <platform>_client.py # 按约定可选的 Provider Client
├── persistence/
│   ├── store.py             # SQLite 单进程 backend
│   ├── mysql_store.py       # MySQL/InnoDB backend
│   ├── factory.py           # 按环境选择 backend
│   └── session_manager.py   # 会话管理器
├── logging/
│   └── __init__.py          # 结构化日志
├── user_skills/
│   └── README.md             # 标准用户 Skill 的边界说明
└── tests/
    ├── test_ad_agent.py      # 核心回归测试
    └── ...                   # Harness、契约与 Provider 回归测试
```

HTTP 入口的声明层和安全边界位于 `agents/ad_agent/api/`：

```text
api/
├── models.py       # 所有 HTTP 输入契约
└── security.py     # API key -> trusted Principal、权限与脱敏边界
```

模型适配器的规划和结果边界位于同级：

```text
integration.py                  # Harness turn bridge
integration_turn_planner.py     # 参数合并、Tool Call、依赖补全
integration_result_assembler.py # Tool 结果、业务分析、回复与 application_data
```

通用 Harness 位于同级的 `agents/agent_harness/`，不依赖 `ad_agent`：

```text
agents/agent_harness/
├── agent.py             # Stateful Agent loop、transcript、Tool turns
├── messages.py         # AgentMessage、ModelTurn、ToolCall
├── tool_catalog.py      # 通用 Tool catalog
├── tool_sources.py     # Tool Source/Binding/Executor 端口
├── agent_runtime.py    # Run facade，可注入 Agent 或 TurnPipeline
├── runtime_kernel.py   # identity/session/lease/mode
├── turn_pipeline.py    # 可组合应用阶段
├── run_store.py        # durable Run port
└── results.py          # RunResult/RunStatus
```

广告侧 `AdvertisingComposition` 负责现有广告安全策略、账户范围、Workflow 和 Provider
恢复逻辑，但不是通用 Harness。新业务应使用
`agents.agent_harness.AgentApplication`，通过 `SkillSource + ToolSource` 接入。
广告侧也提供 `advertising_skill_source()` 和 `advertising_tool_source()`，用于把
广告知识和原子工具接入其他 Agent。

## 扩展新平台

新增渠道只需按包约定提供自己的实现，不需要修改中心 Router、Runtime 或平台列表：

```python
# 1. 创建 API 客户端（可选）
#    agents/ad_agent/api_clients/new_network_client.py
class NewPlatformClient(BasePlatformClient):
    def _do_request(self, method, url, **kwargs): ...

# 工厂名按约定自动发现：create_new_network_client(credentials)

# 2. 创建只发布 Tool 的 Provider adapter
#    agents/ad_agent/tools/providers/new_network/tools.py
class NewPlatformTools:
    platform_name = "new_platform"
    
    def register_tools(self):
        return [
            (ToolDefinition(...), NewHandler()),
            ...
        ]
    
    # ToolDefinition 自描述 action/resource_type/parent_resource_type；
    # 层级 Tool 另外声明 resource_id_field/parent_resource_id_field；
    # 需要异常写入回查时声明 readback_tool；
    # 不需要修改中心 Router 或 Runtime 的渠道分支

# 3. 通过普通 ToolSource 注册，也可以直接接入其他 Agent
runtime.register_tool_source(
    advertising_tool_source(
        NewPlatformTools(api_client),
        source_id="provider:new_platform",
    )
)
```

如果渠道通过 `skills/channels/<name>/SKILL.md` 自动加载，广告应用可以发现同名
Provider Module 并注入按渠道创建的 Client；没有 Client 时仍可安全生成 dry-run 计划。
只有需要补充专家知识、SOP 或安全边界时才修改 `SKILL.md`。可执行能力必须通过
受注册和审计的 Tool Source/Executor 扩展，用户上传 Skill 中的 `tools.py`、`scripts/`
或其他代码文件不会被 Runtime 导入或执行。受控外部 MCP 只通过 MCP Client
归一化为普通 Tool，并继续经过 Runtime 的权限、scope、dry-run/live、确认、幂等和审计门禁。

LLM 结果规范化会读取当前已注册的平台集合。新增渠道的自然语言别名可以由其
平台标识自动获得（例如 `snapchat-ads` / `snapchat ads`）；若需要中文或品牌别名，
直接在渠道 Skill 的 frontmatter `aliases` 中声明即可，平台身份解析会自动发现，
不需要修改 Core、中心 Router 或渠道表。平台显示别名由 Skill frontmatter 声明，只有
注册到当前 Runtime 的 Skill/Tool Source 才会进入解析与执行上下文。
Skill 包遵循标准目录约定：至少包含 `SKILL.md`，可包含 `references/`、`scripts/`、
`assets/`、`evals/` 和其他包文件。管理系统负责保存、版本化和评测这些文件；
`scripts/`、`assets/`、`evals/` 及 `workflow.yaml` 都不是 Runtime 的自动执行入口。

## 扩展 Skill + Tools

新增业务流程优先放在独立的标准 Skill 目录，不需要修改 Runtime 的核心路由。目录
至少包含 `SKILL.md`，可包含 `references/`、`scripts/`、`assets/`、`evals/` 和其他
包文件；这些文件只作为管理、版本和评测对象。只有仓库内受信任的源码扩展，才可在
`tools.py` 或 `tools/__init__.py` 中导出可执行 Tool：

```python
def create_skill(api_client=None):
    return MySkill(api_client)
```

返回的 Skill 需要实现 `get_tools()`、`get_tool_handler(tool_name)`。每个 Tool
应在自己的 `ToolDefinition` 中声明元数据；标准意图无需额外映射，自定义意图
可使用 `intent_types=["my_intent"]`。Runtime 会自动发现受信任源码扩展，注册声明的
工具；没有可执行 Handler 的声明不会被注册，也不会因为 Skill 文档存在而伪造执行能力。
所有扩展工具继续经过 schema 校验、账户白名单、dry-run/live gate、红线字段检查和审计。

内置四渠道的 Provider 实现仍位于 `tools/providers/` 和 `api_clients/`，Skill plugin
只负责扩展工具编排和 Handler；默认模式不会触发线上写 API。

## 使用 skill-up 评测

仓库提供了一个 `skill-up` Custom Engine 适配器，直接调用生产
`AdvertisingComposition`，并将 Runtime 的结构化结果转换为 `SessionResult`。评测默认
使用内存 SQLite、dry-run、offline fixtures 和测试账户白名单，不会调用真实
Provider 写接口。

```bash
agents/ad_agent/evals/skill-up/run.sh
```

详细说明、case 范围和直接调用方式见
`agents/ad_agent/evals/skill-up/README.md`。新增 Runtime 场景只需在该目录
增加 `cases/*.yaml`；新增自然语言 Skill 评测可以使用 skill-up 的内置 Engine
或平台托管的 `claude_sdk`。后者使用 Anthropic Python SDK，读取标准 Skill
目录、受控只读文件和可信 Tool 描述，但不执行广告 Tool、不连接 MCP，也不接收
渠道凭证；不能把 Runtime Custom Engine 结果误当作通用模型能力评测。

## 用户 Skill 管理

业务 Skill 可以按标准 Agent Skills 目录上传和版本化，目录不只包含
`SKILL.md`，也可以包含 `scripts/`、`references/`、`assets/` 和 `evals/`。
管理、发布和评测接口及安全边界见
[`SKILLS_MANAGEMENT.md`](SKILLS_MANAGEMENT.md)。用户 Skill 只提供自然语言
上下文；广告执行仍只能通过已注册的 Tool，并经过 Runtime 统一门禁。

## 许可证

MIT
