# ad-agent 架构设计 v2.0

> 实现状态以同目录 `README.md` 与 `PROGRESS.md` 为准。本文件描述分层边界；当前已补充统一 Tool/Skill 契约、动态参数选择凭证、workflow checkpoint/lease/recovery 和 `PersistenceBackend` 抽象。Harness Engineering 的完成度与剩余缺口见 `README.md` 的“Harness Engineering 评估”。

## 一、整体架构概览

当前所有可扩展对象都向统一 PluginRegistry 发布生命周期元数据：

```text
PluginManifest
  -> PluginRegistry (register/load/activate/deactivate/unregister)
  -> Skill / Tool Source+Executor / Feature / Policy / Renderer / Evaluator
  -> Runtime 通用安全与执行门禁
```

PluginRegistry 是 Harness 的扩展控制面，不是第二个 Tool Router。它负责唯一 ID、版本、
依赖、来源、可信级别和状态；Provider 请求仍只能从注册的 Tool 进入。当前
内置目录 discovery 直接接入该注册表，托管 Skill 只登记为不可执行的租户级
上下文插件。

Tool Source/Skill 的注册、卸载、Parser catalog 刷新和 ownership index 更新由 Runtime
生命周期锁串行化；卸载采用快照回滚，避免刷新失败后留下半套 Tool、参数目录或 Plugin
状态。请求执行路径不持有该锁，因此生命周期一致性不会把普通对话串行化。

插件包管理控制面与进程内注册表分离：`PluginPackageManager` 通过
`PersistenceBackend` 保存租户级的不可变包快照和当前 release pointer，支持版本选择、
回滚、停用和卸载。用户上传或管理 API 激活只改变部署候选状态，不会自动 import 包内
文件；只有受信任部署宿主在完成审核后，才能把可执行包绑定为 Runtime 的贡献对象，
并可用 `PluginLoader.upgrade()` 在进程内升级失败时恢复旧贡献对象。
这样既保留“一切皆插件”的统一生命周期模型，也避免把用户数据包误当成可执行扩展。

### 0. 通用 Agent Harness

通用 Harness 与广告应用分开维护，目录边界如下：

```text
agents/agent_harness/
  Agent                 transcript + model/tool loop
  AgentApplication       standard Skills + Tools assembly
  AgentRuntime           Run facade and Tool Source ownership
  Runtime Kernel         identity, session lock, lease, mode
  TurnPipeline           application stage composition
  ToolCatalog             definitions + trusted executors
  RunStore                durable Run/event port

agents/ad_agent/
  Skills / domain policy / Tool Sources / persistence
  AdvertisingModelAdapter  model-to-ToolCall adapter
  AdvertisingToolExecutor provider Tool executor adapter
```

`Agent` 是默认的通用执行循环：一个 user message 可以产生多个 model turn，
每个 turn 可以执行零个或多个 Tool，再把 Tool result 放回 transcript 继续下一轮。
它提供稳定事件顺序、并行/串行 Tool 策略、取消、最大回合数和
`before_tool_call`/`after_tool_call` hooks。业务应用可以直接使用它，也可以选择
`TurnPipeline` 表达更强的领域阶段；这两者都通过同一个通用 `AgentRuntime` 和 Run identity
进入系统。

广告 Provider 适配器只负责发布 Tool Source。通用 Harness 不依赖任何 Provider
抽象，也不要求 MCP；本地函数、SDK/HTTP adapter 和 MCP `tools/list` 都只需要
转换成 `ToolBinding`。

业务接入统一采用：

```text
Agent Harness Registry
  ├── Skill Source             SKILL.md / references / assets
  ├── Tool Source              local / SDK / HTTP / MCP
  └── Policy Hooks             before/after Tool、权限、审批与输出策略
           ↓
    AgentApplication + AgentRuntime
```

广告只是其中一组 Skills、Tools 和 Provider adapters。广告侧 `AdvertisingComposition`
负责安全和 Workflow 的应用编排；它不向
`agents/agent_harness` 反向提供类型或路由规则。其他 Agent 可以直接注册广告
`SkillSource` 和 `ToolSource`，也可以只取广告知识而不加载广告执行器。

可部署插件包使用根目录 `plugin.manifest.json` 作为声明入口。Loader 校验包内相对路径、
大小/数量上限、逐文件 SHA-256、确定性 package digest 和可选 HMAC 签名，但不自动导入
入口代码。只有受信任部署宿主可以把已审核源码贡献绑定到可执行 Manifest；托管 Skill
包不需要该文件，也不会因为包含 `tools.py`、`scripts/` 或其他代码文件而获得执行权限。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Web UI (FastAPI + HTML)                          │
│                    http://127.0.0.1:8765/                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │  聊天界面    │  │  确认卡片    │  │  工具状态    │  │  平台信息面板    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼ POST /chat
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API Server (FastAPI)                                │
│   • 请求解析 (ChatRequest)                                                   │
│   • 确认逻辑处理                                                              │
│   • 错误处理与日志                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Agent Runtime (核心引擎)                               │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │ IntentParser    │  │ IntentRouter    │  │ ToolRegistry             │    │
│  │ 意图解析         │→│ 路由分发         │→ │ 工具注册/执行            │    │
│  │ - LLM 结构化解析    │ │ - 发现式路由   │  │ 297 tools              │    │
│  │ - 上下文反馈         │ │ - 确定性执行   │  │ - 受控 Runtime gates     │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘    │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │ WhitelistValidator│ │ SessionManager  │  │ Persistence Store       │    │
│  │ 账户白名单验证    │  │ 会话管理        │  │ PersistenceBackend       │    │
│  │ - 防止误操作     │  │ - 上下文传递    │  │ - 会话历史               │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 Tool Sources / Provider Modules 层                          │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Meta        │  │ Google Ads  │  │ TikTok      │  │ DV360            │  │
│  │ Local/SDK   │  │ MCP Source │  │ Provider    │  │ Feature Source   │  │
│  │ 78 tools    │  │ 103 tools   │  │ 90 tools    │  │ 31 tools         │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API Clients 层 (客户端实现)                          │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Meta        │  │ Google Ads  │  │ TikTok      │  │ DV360            │  │
│  │ Client      │  │ Client      │  │ Client      │  │ Client           │  │
│  │ - OAuth     │  │ - REST API  │  │ - Access-T  │  │ - JWT Auth       │  │
│  │ - RateLimit │  │ - GAQL      │  │ - v1.3 API  │  │ - ServiceAccount │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 二、核心组件详解

### 1. IntentParser (意图解析器)
```python
# 位置: core/intent.py
class LLMIntentParser:
    """LLM 解析；生产 Runtime 不降级为规则解析。"""
    PARSE_PROMPT_TEMPLATE = """
    你是广告投放专家助手。请分析用户的投放需求：
    - intent_type: create/update/pause/resume/delete/cross-channel | boost_post | download_report
    - platforms: 当前 Runtime 已注册的平台标识列表
    - objective: sales | leads | traffic | brand
    - platform_params: 各平台具体参数
    """

    def parse(self, text: str, context: ToolContext) -> ParsedIntent:
        # 平台集合、Skill aliases 和 Tool Schema 均来自当前注册对象；
        # Router 不维护 Meta/Google/TikTok/DV360 的中心路由表。
        ...
```

### 2. IntentRouter (发现式意图路由器)
```python
# 位置: core/intent.py
class SimpleIntentRouter:
    """按 ToolDefinition 的 action/resource_type/intent_types 发现工具"""
```

`SKILL.md` 只提供自然语言专家知识、SOP、适用边界和安全注意事项，
不承担可执行 DSL。Tool Source/plugin 注册可执行 Tool，并在
`ToolDefinition` 中声明 `action`、`resource_type`、`parent_resource_type`
及可选 `intent_types`。涉及层级创建的 Tool 还应声明
`resource_id_field` 与 `parent_resource_id_field`，把各平台的 ID 拼写差异
留在 Provider Module/Connector 内。Runtime 根据父子资源层级排序创建链，并统一执行
权限、账户、dry-run、审批、幂等与恢复。执行顺序属于 LLM 规划和 Runtime/Harness
的受控执行记录，不由用户 Skill 文件中的 DSL 决定。

Runtime 本身不承载业务流程。业务策略通过 `RuntimePolicy` 注入，复杂业务编排通过
按约定自动发现的 `RuntimeFeature` 注入，结果展示通过 `ResponseRenderer` 注入。
因此大多数业务流程只需要新增标准 Skill 和已有 Tools；需要新外部动作时增加
Tool，只有复杂的二阶段、批量或聚合流程才增加 Skill-owned Feature。

当前已实现：业务策略、跨渠道流程、回复渲染、输入组装、动态参数选择、Provider
兼容归一化和账户上下文解析已经迁出 Runtime，分别由 Policy、Feature、Renderer、
`ToolInputBuilder`/parameter service 和 `AccountResolver` 承担。

`ExecutionPlan` 是模型意图进入执行层后的通用计划对象，`WorkflowCoordinator` 是
计划状态的持久化协调对象；两者都不包含渠道枚举、业务规则或 Provider Client。
`RuntimeServices` 是 Feature 与 Runtime 之间的正式端口，`ToolExecutor` 和
`RuntimeSecurity` 分别承载 Tool 执行和安全边界；Runtime 主类只组合这些组件。
Wiki 管理和 raw ingest 使用 `KnowledgeStorePort`，Memory 使用独立的 `MemoryStore`，
Task/Outbox/Schedule 使用各自的 durable port；`PersistenceBackend` 只作为应用组合根的
聚合存储端口，业务服务不再必须依赖整套后端接口。

Runtime 外壳进一步分为三层：`agents/agent_harness/runtime_kernel.py` 保留最小的请求、
Session 并发、租约和 `run_id`/`turn_id` 生命周期；
`agents/agent_harness/turn_pipeline.py` 定义通用回合阶段、
阶段元数据、终止和错误语义；
`agents/agent_harness/agent_runtime.py` 的 `AgentRuntime` 通过注入 `TurnPipeline` 提供可嵌入的
通用门面。应用 pipeline 消费 Kernel 注入的 Run identity，并将持久化、审计和响应关联到
同一 `run_id`/`turn_id`，不得在 pipeline 内覆盖。广告侧 `AdvertisingComposition` 只负责组装
领域服务。广告通过 `AgentPlatform.create_application()` 装配标准 Harness Agent；
`AdvertisingModelAdapter` 只负责把广告场景的模型输入转换为通用 `ModelTurn`，
不创建自己的 Pipeline、Stages 或回合状态机。广告安全、账户、Blueprint、
Workflow 和 Provider 细节属于场景的 Tool/数据适配，不得形成第二套 Runtime 或
Tool 门禁。工具选择同样拆开：
`core/tool_selection.py` 的 `ToolSelector` 只消费 Tool metadata 和 ParsedIntent，
`PromptRenderer` 只生成有界模型上下文；`DynamicToolSelector` 负责组合
Skill、Wiki 和租户上下文，但不能执行 Tool 或授予权限。

`agents/agent_platform/tools/policy.py` 的 `ToolExecutionPolicy` 负责把 Tool、Effect、Scope、执行模式、
权限、live 批准和 WriteGuard 状态转换成 `PolicyDecision`。dry-run 可以通过规划门槛，
live 必须通过额外门槛；确认 token 的生成、绑定和消费仍留在应用安全层，Core 不认识
任何 UI 确认格式。

参数选择也遵循同一边界：固定 Provider 枚举由 Tool Schema 的 `enum` 自动生成
catalog；账户相关的 App、地域、转化事件等由字段上的 `lookup_tool` 声明，
`GET /parameter-options/resolve` 才会执行对应的只读查询。查询结果中的短期
selection token 绑定用户、租户、会话、账户、目标 Tool、字段和来源 Tool，不能
跨上下文复用。新增参数只改所属 Provider Module/Connector 的 Schema/adapter，不改 Runtime 的
渠道分支；既有 Meta、Google、TikTok、DV360 创建适配器也必须保持 Schema 到
Provider payload 的显式透传。

更新操作同样遵循该边界：共享 `CampaignUpdateHandler` 只处理输入安全校验和
统一调用协议，Meta/Google/TikTok 的资源级 API 签名由各自 Provider Module adapter
负责；新增 Provider 可提供自己的 adapter，或实现统一的 `update_resource` 接口。

### 3. ToolRegistry (工具注册中心)
```python
# 位置: core/tool_registry.py
class SimpleToolRegistry:
    """工具注册与执行中心"""
    
    def register(self, tool_def: ToolDefinition, handler: ToolHandler):
        """注册一个 Tool Source/Executor 提供的可执行 Tool"""
        self._tools[tool_def.name] = (tool_def, handler)
    
    def execute(self, session_ctx: ToolContext, tool_name: str, tool_input: dict) -> ToolResult:
        """执行工具调用"""
        definition, handler = self._tools.get(tool_name, (None, None))
        if handler:
            return handler.execute(session_ctx, tool_input)
        return ToolResult(success=False, error="Handler not found")
```

### 4. Tool Sources 与 Provider Modules
```python
# 位置: tools/providers/
class MetaProviderModule(BaseProviderToolSource):
    """广告应用中的 Meta Provider Module 兼容实现"""
    def __init__(self, api_client: MetaAPIClient):
        super().__init__(
            platform="meta",
            tool_definitions=[
                ToolDefinition(name="meta_list_campaigns", ...),
                ToolDefinition(name="meta_get_campaign_report", ...),
                # ... 16 tools total
            ]
        )
    
    def get_handler(self, tool_name: str) -> BaseHandler:
        handlers = {
            "meta_list_campaigns": MetaListCampaignsHandler(self.api_client),
            "meta_get_campaign_report": MetaGetReportRealHandler(self.api_client),
            # ...
        }
        return handlers.get(tool_name)

class GoogleAdsProviderModule(BaseProviderToolSource):
    """Google Ads Provider Module 兼容实现"""
    # 18 tools: list/get/create campaign/adgroup/ad + keywords/report/update

class TikTokProviderModule(BaseProviderToolSource):
    """TikTok Provider Module 兼容实现"""
    # 18 tools: list/get/create campaign/adgroup/ad + media/report/update

class DV360ProviderModule(BaseProviderToolSource):
    """DV360 Provider Module 兼容实现"""
    # 14 tools: list/get campaign/advertiser/io/line_item + report/update
```

### 5. API Clients (客户端实现)
```python
# 位置: api_clients/
class BaseAPIClient:
    """API 客户端基类"""
    BASE_URL: str = ""
    
    def __init__(self, credentials: dict):
        self.access_token = credentials.get('access_token', '')
        self.rate_limiter = TokenBucketRateLimiter(...)
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        # 限流检查
        self.rate_limiter.acquire()
        # 构建请求头
        headers = self._build_headers()
        # 发送请求
        resp = requests.request(method, url, headers=headers, ...)
        return {'status_code': resp.status_code, 'data': resp.json()}

class MetaAPIClient(BaseAPIClient):
    """Meta Marketing API 客户端"""
    BASE_URL = "https://graph.facebook.com/v18.0"
    
    def list_campaigns(self, account_id: str) -> list:
        url = f"{self.BASE_URL}/{account_id}/campaigns"
        params = {'access_token': self.access_token, 'fields': 'id,name,status'}
        resp = self._do_request('GET', url, params=params)
        return resp.get('data', [])

class GoogleAdsAPIClient(BaseAPIClient):
    """Google Ads API 客户端"""
    BASE_URL = "https://googleads.googleapis.com/v24"
    
    def _search(self, query: str) -> dict:
        """执行 GAQL 查询"""
        url = f"{self.BASE_URL}/customers/{self.login_customer_id}:googleAds:search"
        data = {'query': query}
        return self._do_request('POST', url, data=data)
    
    def list_campaigns(self, customer_id: str = None) -> list:
        query = "SELECT campaign.id, campaign.name FROM campaign LIMIT 100"
        result = self._search(query)
        # 解析嵌套结构
        results = result.get('data', {}).get('results', [])
        return [r.get('campaign', {}) for r in results]

class TikTokAPIClient(BaseAPIClient):
    """TikTok Business API 客户端"""
    BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"
    
    def list_campaigns(self, advertiser_id: str) -> list:
        url = f"{self.BASE_URL}/campaign/get/"
        headers = {'Access-Token': self.access_token}
        data = {'advertiser_id': advertiser_id, 'page_size': 20}
        resp = self._do_request('POST', url, headers=headers, data=data)
        # TikTok 响应结构: {code, message, data: {list: [...]}}
        return resp.get('data', {}).get('list', [])
```

## 三、工具清单（当前广告 Provider Modules 共 297 个 Tool）

| 平台 | 工具数量 | 工具列表 |
|------|---------|---------|
| **Meta** | 78 | 账户、Business Manager、Page/Pixel 详情/列表、Image/Video Asset 上传与列表、Custom Conversion CRUD、Lead Form 与 Lead 列表/详情、Audience/Lookalike Audience CRUD、查询/创建 Campaign、Ad Set、Ad、Lead Ads、Catalog Ads、Creative；商品目录/商品集；受众；Boost；生命周期；报表 |
| **Google Ads** | 103 | 查询/创建/删除 Campaign、CampaignBudget、CampaignCriterion 定向、Conversion Action/Conversion Goal 生命周期、Feed/FeedItem 列表/详情/生命周期、User List 生命周期与 Customer Match 哈希数据上传、BiddingStrategy 生命周期与优化参数、可复用文本/图片/YouTube/HTML5 Asset 创建/移除、Campaign/Asset Group Asset 关联、出价策略查询、Ad Group/Ad 完整 CRUD、关键词完整生命周期、Search Ad、Responsive Display Ad、Video Ad、Demand Gen、Hotel、Local、Smart、Travel、Product Group、PMax Asset Group、Experiment 读写与 schedule/end/graduate/promote 生命周期、Experiment Arm 查询、报表 |
| **TikTok** | 85 | 账户列表/详情、查询/创建 Campaign、Ad Group、Ad；Creative/Video/Image/Catalog/Product Set 列表与详情；Lead/App/Spark/Product Sales 广告；Identity 列表/详情、Creative Portfolio 创建/查询/预览；图片/视频 Asset Library 上传；上下文地域、转化、设备、目录、应用、品牌安全查询；Pixel 生命周期与事件；Spark Ads；受众 CRUD；生命周期；报表 |
| **DV360** | 31 | 查询 Advertiser/Campaign/IO/Line Item/Creative；创建/更新/删除 Creative；定向目录与 Line Item 定向绑定；删除/激活/暂停 IO/Line Item；异步报表；IO/Line Item/Campaign 更新工具；Campaign 创建暂缓 |

## 四、核心数据流

```
用户输入 → IntentParser → ParsedIntent → IntentRouter → ToolPlan
                                              │
                                              ▼
                                         ToolRegistry.execute()
                                              │
                                              ▼
                                         ToolSourceHandler
                                              │
                                              ▼
                                         APIClient.request()
                                              │
                                              ▼
                                         外部 API (Meta/Google/TikTok/DV360)
                                              │
                                              ▼
                                         ToolResult → SessionManager.save()
                                              │
                                              ▼
                                         返回给用户 (JSON/HTML)
```

每回合的 LLM 负责理解请求并提出结构化 Planner 输入；`IntentRouter` 只读取当前
ToolDefinition 的自描述元数据，Runtime 再执行 schema、权限、账户、dry-run、确认和
幂等校验。工具结果不会直接变成下一次执行指令，而是以限量、脱敏的
`prior_tool_results` 上下文反馈给后续 LLM 回合，用于补参和连续对话。这是单 Agent 的
模型规划闭环，不引入第二套 `workflow.yaml` 执行引擎。

### Provider 接口与版本演进

当前 297 个 Tool 是四个广告 Provider Module 对其已实现 Client 方法的覆盖基线，不等于四个
官方 Marketing API 的全量接口。新增接口由渠道包自己完成 Client 方法、Tool Schema、
参数目录/lookup 和 payload adapter，再通过 `audit_provider_tools.py` 与契约快照进入
发布门禁。

`ToolDefinition.provider_api_version` 是 Tool 与 Provider Client 之间的版本契约。
`BasePlatformClient` 负责检查 `SUPPORTED_API_VERSIONS`，并把请求/响应交给渠道 Client
拥有的 `VERSION_ADAPTERS`。因此版本升级不需要修改 Runtime 或 IntentRouter；只需增加
渠道 Client 的版本支持、adapter 和对应回归。如果字段语义不能兼容，必须 fail-closed，
保留 dry-run，不得静默发送未经验证的 Provider payload。

### Provider 能力完整度审计

每个渠道包维护两份互补的 provider-owned 声明：

| 声明 | 含义 | 能否代表官方全量 |
|---|---|---|
| `API_SURFACE` | 已落到 Client/Provider Module/Tool 的代码实现，以及 planned 缺口 | 不能 |
| `OFFICIAL_INVENTORY` | 有官方文档来源的资源/动作基线、endpoint/operation 和实现状态 | 只有 `completeness` 明确完整时才可以 |

审计先验证 `OFFICIAL_INVENTORY -> API_SURFACE`，再验证原有的
`API_SURFACE -> Client -> Tool`。因此同一条报告会同时回答“我们写了什么”和“登记的
官方能力还有什么没写”。目前各渠道基线均标记 `scoped_not_exhaustive`，这是诚实的覆盖率
口径，不把 269 个 Tool 或某个渠道的 Tool 数量冒充 Provider 全部接口。官方文档只支持
资源级结论、但还没有 operation-specific source 或测试账户证据时，执行状态仍保持
`dry_run_only`。

## 五、安全机制与执行模式

默认 `execution_mode=dry_run`。所有写工具在 dry-run 中只由 Runtime 生成本地模拟 ID，不进入 Handler/API Client；live 写入必须同时满足测试账户白名单和 `confirmed=True`。HTTP 模式按租户和用户隔离，单回合可以显式覆盖，但不会修改其他请求；读操作可按平台账户查询，但生产环境仍应由调用方限制账户范围。

### 1. 账户白名单
```python
# config.yaml
allowed_accounts:
  meta: ['act_2806375919473667']
  google: ['9055507554']
  tiktok: ['7397068114548195329']
  dv360: ['5110831']
```

### 2. WriteGuard (写操作保护)
```python
# live 写操作需要显式确认；dry-run 不触发线上写 API
if execution_mode == "live" and tool_def.is_write_tool and not request.confirmed:
    return {
        "needs_confirmation": True,
        "confirmation_payload": {
            "type": "ask_params",
            "tool": tool_def.name,
            "missing": missing_params,
            "question": "..."
        }
    }
```

### 3. 凭证管理
```python
# 凭证文件被 .gitignore 排除
config/ad_platform_credentials.json  # ❌ 不提交
config/dv360_service_account.json    # ❌ 不提交
config.yaml                          # ✅ 只包含脱敏配置
```

## 六、持久化层

### 1. SessionManager
```python
class SessionManager:
    """会话管理器"""
    
    def create_session(self, user_id: str, account_id: str = None) -> Session:
        """创建新会话"""
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
    
    def save_turn(self, session_id: str, turn_data: dict):
        """保存对话轮次"""
```

### 2. PersistenceBackend（SQLite 默认 / MySQL 可配置）
```python
class AdAgentStore:
    """SQLite 单进程数据存储层"""
    
    # 表结构
    CREATE TABLE sessions (...)
    CREATE TABLE turns (...)
    CREATE TABLE tool_calls (...)
CREATE TABLE campaigns (...)  # 同步 Campaign 状态
```

生产多实例通过 `AD_AGENT_DATABASE_URL=mysql+pymysql://...` 选择
`persistence.mysql_store.MySQLStore`。它复用同一份领域 Store 契约，使用 InnoDB、事务、
任务/Outbox 的行锁 claim、Session/Workflow lease 和 Run Event replay；Runtime 不包含
SQLite/MySQL 分支。`tasks` 是 Agent 执行队列，`outbox_events` 是事件投递队列，二者都
必须保持幂等消费和明确的恢复状态。MySQL 的 claim transaction 对死锁和 lock wait
timeout 做有界的整事务重试；任务、定时任务和 Outbox 的确认/回写都要求当前 owner，
并且控制面修改在数据库中带 tenant/user scope 原子执行，避免“先查询再修改”的
TOCTOU 越权窗口。SQLite 仍只适合单进程，生产多机必须使用共享 InnoDB 和统一的
租约/令牌配置。

### 3. Markdown LLM Wiki

知识库是独立的只读上下文源，不是执行引擎：

```text
Markdown Wiki (index/log/主题文档)
        ↓ KnowledgeProvider
确定性词法检索（标题 + 标签 + 正文 + 平台/类型过滤）
        ↓ 有界 excerpt + citation
Intent Parser / Skill 上下文
```

当前实现不依赖向量数据库。`core.knowledge.MarkdownWikiKnowledgeProvider` 是唯一
Runtime Provider；CLI 和 Tool 都直接使用这个 Provider，不维护第二套文档加载和索引逻辑。
文档元数据规范见
[`knowledge_base/SCHEMA.md`](./knowledge_base/SCHEMA.md)。

### 4. Agent Memory

Memory 与 Wiki、Session 和 Tool Audit 的边界如下：

| 数据 | 作用 | 是否自动成为长期记忆 |
|---|---|---|
| SessionContext | 当前对话和跨 Tool 临时引用 | 否 |
| Tool Audit | 调用审计和恢复证据 | 否 |
| Markdown Wiki | 团队共享的稳定知识 | 否 |
| MemoryRecord | 用户/租户明确保存的事实和经验 | 仅显式写入 |

`MemoryManager` 提供写入、召回和删除策略，`MemoryStore` 是后端接口，当前由
`AdAgentStore`/`MySQLStore` 的 `memories` 表实现。召回先做租户/用户/会话范围过滤，再做
确定性词法排序；过期记录和删除墓碑不返回。召回内容只作为受限 LLM 上下文，不能改变
Tool Registry、权限、账户范围或执行计划。

## 七、关键文件索引

| 文件 | 行数 | 职责 |
|------|------|------|
| `agents/agent_harness/agent.py` | 当前源码 | Stateful transcript 与 model/Tool loop |
| `agents/agent_harness/messages.py` | 当前源码 | 通用消息、ModelTurn 和 ToolCall 合约 |
| `agents/agent_harness/tool_catalog.py` | 当前源码 | 通用 Tool catalog 与 source ownership |
| `agents/agent_harness/agent_runtime.py` | 当前源码 | 通用 Runtime 门面，可注入 Agent 或 TurnPipeline |
| `agents/agent_harness/turn_pipeline.py` | 当前源码 | 通用回合阶段、终止和错误处理契约 |
| `agents/agent_harness/runtime_kernel.py` | 当前源码 | 与业务无关的请求规范化、Session 并发、跨实例租约和执行委托 |
| `agents/agent_harness/run_store.py` | 当前源码 | 通用 Run 启动、事件和终态持久化端口 |
| `core/tool_selection.py` | 当前源码 | 业务无关的 Tool 选择和 Prompt 渲染 |
| `core/tool_selector.py` | 当前源码 | Skill/Wiki/租户上下文组合与筛选 |
| `agents/agent_platform/tools/policy.py` | 当前源码 | Tool/Scope/Effect/执行模式策略决策 |
| `runtime/runtime.py` | 30 | 稳定的广告应用公共导出入口，不承载主循环 |
| `runtime/ad_application.py` | 当前源码 | 广告应用组合根：组装 Skills、Tools、Tool Sources、业务服务和通用 Harness |
| `runtime/ad_application_assembly.py` | 当前源码 | 广告组合图与 `AdRunStoreAdapter` |
| `runtime/ad_application_assembly.py` | 当前源码 | 场景通过 `AgentPlatform` 装配标准 Harness |
| `integration.py` | 当前源码 | 广告 Tool Catalog、Model Adapter 和 Executor 适配 |
| `runtime/supervisor.py` | 当前源码 | 通用 Task、Scheduler、Outbox、Event Repair worker 生命周期；任务类型由应用组合根注入 |
| `runtime/services.py` | 当前源码 | RuntimeServices Feature 端口适配器 |
| `runtime/tool_executor.py` | 当前源码 | Tool 执行、超时与 Provider Client 隔离 |
| `runtime/security.py` | 当前源码 | 红线字段、确认、结果证据与不确定失败边界 |
| `runtime/workflow.py` | 当前源码 | Workflow checkpoint、lease 和状态协调 |
| `runtime/input_builder.py` | 当前源码 | Schema 驱动输入组装和动态参数选择 |
| `runtime/account_policy.py` | 当前源码 | 测试账户白名单校验 |
| `runtime/session_context.py` | 当前源码 | 会话与跨 Tool 状态 |
| `core/intent.py` | 533 | 意图解析、路由逻辑 |
| `core/tool_registry.py` | 150 | 工具注册与执行 |
| `tools/providers/provider_base.py` | 227 | Provider Tool Source 基类 |
| `tools/providers/meta/provider.py` | 当前源码 | Meta 渠道 Tool Source |
| `tools/providers/google/provider.py` | 当前源码 | Google Ads 渠道 Tool Source |
| `tools/providers/tiktok/provider.py` | 当前源码 | TikTok 渠道 Tool Source |
| `tools/providers/dv360/provider.py` | 当前源码 | DV360 渠道 Tool Source |
| `tools/providers/source_factory.py` | 当前源码 | 按包约定发现 Tool Source |
| `api_clients/base.py` | 280 | API 客户端基类 |
| `api_clients/meta_client.py` | 19K | Meta API 实现 |
| `api_clients/google_ads_client.py` | 20K | Google Ads API 实现 |
| `api_clients/tiktok_client.py` | 27K | TikTok API 实现 |
| `api_clients/dv360_client.py` | 16K | DV360 API 实现 |
| `api_clients/factory.py` | 当前源码 | 按包约定发现 Provider Client |
| `api_server.py` | 300 | FastAPI 服务 |
| `templates/chat.html` | ~1500 | Web UI |

## 八、扩展指南

### 新增平台

新增平台只需要发布 Tool Source、可选的 API Client 和 Skill。
Runtime、IntentRouter、工具选择器和跨渠道聚合入口都从已注册 Tool 的元数据发现平台，
不再维护一份四渠道列表。内置平台名称只作为现有 Skill 的自然语言别名示例。
```python
# 1. 创建 API Client
class NewPlatformClient(BaseAPIClient):
    BASE_URL = "https://api.newplatform.com"

# 2. 创建一个只发布 Tool 的 Provider adapter
class NewPlatformTools:
    def __init__(self, api_client: NewPlatformClient):
        self.api_client = api_client

    def register_tools(self):
        return [...]

# 3. 通过普通 ToolSource 注册
runtime.register_tool_source(
    advertising_tool_source(
        NewPlatformTools(api_client),
        source_id="provider:new_platform",
    )
)
```

### 新增业务场景
```python
# 1. 定义业务规则
business_rules = {
    "allowed_channels": ["meta", "google"],
    "min_budget": 100,
    "max_budget": 100000,
}

# 2. 由业务 Skill 适配为通用 RuntimePolicy
policy = BusinessSkillPolicy.from_values(
    name="ecommerce",
    allowed_platforms=("meta", "google"),
    rules={"min_budget": 100, "max_budget": 100000},
)
runtime.set_policies([policy])
```

## 九、Skills 系统

### 1. Skills 目录结构

```
skills/
├── channels/                 # 渠道层 Skill（核心能力）
│   ├── meta/SKILL.md        # Meta 专家知识、SOP、安全边界
│   ├── google-ads/SKILL.md  # Google Ads 专家知识、SOP、安全边界
│   ├── tiktok/SKILL.md      # TikTok 专家知识、SOP、安全边界
│   └── dv360/SKILL.md       # DV360 专家知识、SOP、安全边界
├── businesses/               # 业务层 Skill（业务规则）
│   ├── ecommerce/SKILL.md   # 电商业务
│   ├── app/SKILL.md         # App 推广业务
│   └── social/SKILL.md      # 社交媒体业务
└── cross-channel/            # 跨渠道 Skill 上下文
    └── SKILL.md
```

### 2. Skill 加载流程

```python
# api_server.py 初始化（生产入口注入 LLM；离线评测才显式 require_llm=False）
runtime = AdvertisingComposition(llm_client=create_llm_client(...), require_llm=True)
runtime.auto_load_skills(
    str(skills_root), credentials,
    allow_executable_plugins=True,
    allow_provider_tool_discovery=True,
)

# 输出: ✅ 已加载当前 Skill 根目录下发现的 Skills
```

### 3. Skill 解析逻辑

`SkillContract` 类支持多种 SKILL.md frontmatter 格式：

自动发现默认只加载标准 Skill 文本和声明式资料。只有受信部署入口显式传入
`allow_executable_plugins=True, allow_provider_tool_discovery=True` 时，Runtime 才会导入
插件代码或发现内置渠道 Tool Source；管理端上传目录永远走 advisory-only 路径，不能把
`tools.py`、`scripts/` 或渠道 frontmatter 变成可执行能力。

1. **Frontmatter 解析**：
   - 嵌套格式: `skill: {name: ..., description: ..., platform: ...}`
   - 直接格式: `name: ..., description: ...`

2. **执行能力发现**：SKILL.md 不提取 Tool 定义；渠道 Tool Source 或 Skill plugin
   提供 `ToolDefinition` 与 Handler，Runtime 只注册真实存在的 executable Tool。

### 4. Skills vs Tool Sources

| 概念 | 说明 | 数量 |
|------|------|------|
| **Skills** | SKILL.md 提供的上下文、SOP 和安全边界 | 按已加载 Skill 动态发现（当前内置 4 个） |
| **Tool Sources** | 发布 Tool contract 与 executor 的来源，可是本地、SDK/HTTP 或 MCP | 按注册结果动态发现 |
| **Provider Modules** | 广告应用内部的渠道适配与兼容组装 | 当前内置 4 个，非通用 Runtime 必需层 |
| **Tools** | Registry 中的统一可执行契约 | 按注册结果动态统计（当前基线 297 个） |

**关系**：
- Skills 是自然语言上下文（SKILL.md）
- Tool Sources 发布 contract 和 executor
- Provider Modules 只是广告应用的适配实现
- Tools 是经过 Runtime 门禁的统一执行入口

### 5. 扩展新 Skill

```bash
# 1. 创建 Skill 目录
mkdir -p agents/ad_agent/skills/channels/new-platform

# 2. 编写 SKILL.md
cat > agents/ad_agent/skills/channels/new-platform/SKILL.md << 'EOF'
---
name: new-platform-api
description: New Platform API 专家技能
---

# New Platform API

## 创建流程与安全边界

这里描述参数含义、固定枚举、动态查询要求、流程和安全边界；不要用 Markdown
Tool 清单代替可执行注册。
EOF

# Tool Source 按约定导出 create_new_platform_tool_source(api_client=None)
# Client 按约定导出 create_new_platform_client(credentials)（可选）
# Runtime/CLI 自动发现，无需修改中心列表
