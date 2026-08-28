# ad-agent - 多渠道广告投放 Agent

基于单 Agent + 多 Skills 架构的广告投放助手，支持 Meta、Google Ads、TikTok Ads、DV360 四大广告平台。当前默认是安全 `dry_run`：写操作可解析、校验和编排，但不会调用线上写 API。

## 架构特点

- **单 Agent + 多 Skills**：通过意图路由自动分发到对应平台的 Capability
- **API 客户端**：封装真实 API 请求、重试、限流和错误分类；live 能力须逐平台验证
- **持久化层**：SQLite 存储会话、工具调用、Campaign 状态
- **结构化日志**：JSON 格式，便于 log aggregation
- **离线演示**：无凭证时部分查询 Handler 返回 mock 数据；这些数据不代表线上结果
- **安全边界**：写操作必须命中配置的测试账户白名单；live 还必须显式确认
- **可扩展**：渠道包按约定自动发现；新增平台不需要修改 Runtime、Router 或中心渠道表

## 支持的广告平台

| 平台 | Skill | API 客户端 | 工具数量 |
|------|-------|-----------|---------|
| Meta | meta-marketing-api-expert | meta_client.py | 16（含 Creative dry-run） |
| Google Ads | google-ads-api-expert | google_ads_client.py | 18（含关键词与 PMax Asset Group dry-run/update plan） |
| TikTok | tiktok-ads-expert | tiktok_client.py | 24（含 Creative/视频/图片素材及参考数据查询） |
| DV360 | dv360-expert | dv360_client.py | 14（含 IO/Line Item 查询；Campaign-level report 未支持） |
| **合计** |  |  | **72** |

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```python
from ad_agent import AgentRuntime, create_meta_capability, create_google_capability
from ad_agent.persistence.store import AdAgentStore

# 初始化（默认 dry-run，带持久化）
store = AdAgentStore("ad_agent.db")
runtime = AgentRuntime(persistence_store=store)

# 注册 Capability（Mock 模式，无需 API 凭证）
runtime.register_capability(create_meta_capability())
runtime.register_capability(create_google_capability())

# 运行对话
result = runtime.run(
    user_input="帮我投放Meta和Google广告，预算100元/天",
    user_id="user_001",
)

print(result["reply"])
```

## 使用真实 API（仅测试账号）

```python
import json

# 加载凭证
with open("credentials.json") as f:
    credentials = json.load(f)

# 传入真实客户端；Runtime 仍默认为 dry-run
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.capabilities.meta import create_meta_capability

api_client = MetaAPIClient(credentials["meta"])
capability = create_meta_capability(api_client)

runtime.register_capability(capability)
```

切换到 `execution_mode="live"` 前，必须确认 `agents/ad_agent/config.yaml` 中已配置目标测试账号白名单，并先取得当前写入计划返回的 `confirmation_payload`，随后以同一 payload 调用 `runtime.run(..., confirmed=True, confirmation_payload=payload)`。HTTP API 会拒绝缺少该 payload 的确认请求。不要通过凭证内容自动扩大白名单；凭证只保存在进程内，不写入 SQLite。白名单只有一个账户时允许兼容性自动选择；配置多个账户后必须显式传入目标账户，避免误选。

当前所有 Campaign/下级资源创建默认只生成 dry-run 计划；DV360 Campaign/IO/Line Item 更新、Google PMax Asset Group 以及部分下级资源更新没有经过验证的 live adapter，live 会明确返回不支持。读取请求在没有 Provider Client 时默认 fail-closed，只有显式 `offline_mode=True` 才会返回离线 fixture。

### 身份、权限和恢复边界

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

Workflow 在执行前预登记 write item，并通过 upsert checkpoint 更新状态；当前 SQLite
实现由 `PersistenceBackend` 接口隔离，后续可替换 MySQL/PostgreSQL backend，不需要改 Runtime。
当前 SQLite 连接由进程内锁保护，部署边界按单进程处理；多进程/多实例共享状态应在接入
MySQL 等后端并补齐租约/并发控制后开启。运行中的 workflow 会 heartbeat，恢复 worker
通过持久化 lease 原子 claim，避免把新鲜任务误判为可恢复或被多个 worker 同时接管。

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

当前核心 Harness 已具备：受限 Tool/Skill 契约、统一 Runtime 执行入口、权限/账户白名单、dry-run、显式确认、持久化幂等、workflow checkpoint/lease/recovery、Provider 回查入口，以及 LLM 输出后的二次 schema 校验。结论是“核心骨架符合，尚未达到生产闭环”，不能把当前 72 个工具数或单元测试通过当成 Provider live 已验证。

暂留的工程缺口：

- 观察性只保留接入入口，尚未接入 trace、指标、告警和审计检索。
- SQLite 当前按单进程使用；未来 MySQL/PostgreSQL backend 需要实现同一接口的共享事务、幂等 reservation 和 lease 原子语义，并补多实例并发测试。
- Provider schema 目前是代码契约，尚未接入版本化 API schema 拉取、漂移检测和真实测试账户 E2E；动态组合约束仍需按渠道逐项补齐。
- 部分 workflow 只标记 `compensation_required` 并转人工复核，尚无经过 Provider 验证的自动补偿执行器；这属于刻意的安全降级，不是已完成能力。
- live 还需要凭证轮换/授权中心、合作方级配额策略，以及可中断的异步执行 worker。

因此下一阶段应优先做“Provider contract fixture + schema drift check + 测试账户 E2E”，再逐个把工具加入 `live_approved_tools`，而不是一次性开放全部渠道写入。

更新操作同样使用渠道拥有的嵌套 Schema：Meta、Google Ads、TikTok、DV360 的 `updates` 只允许当前适配器声明的字段，未知字段会在计划阶段报错，不会静默丢弃或带入 live 请求。缺少带 `lookup_tool` 的动态字段时，返回结果中的 `confirmation_payload.lookup_tools` 会告诉调用方应先调用哪个查询工具。通用目标（sales/leads/traffic/brand）由各 Skill 的字段元数据映射为 Provider 枚举，不由 Runtime 维护一张不可扩展的渠道表。

dry-run 结果中的 `provider_validation` 会单独标记 Provider 必填字段是否齐全：计划可以先生成，但 `ready: false` 时不能视为可直接 live 执行。

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

```
┌─────────────────────────────────────────────────────────────┐
│                      User Skill (orchestrator)              │
│                    意图路由 + 编排协调                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        AgentRuntime                         │
│   ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │
│   │ IntentParser │  │IntentRouter │  │   ToolRegistry     │   │
│   │ (LLM/规则)   │  │ (多平台)    │  │   (工具注册表)      │   │
│   └─────────────┘  └─────────────┘  └───────────────────┘   │
│                             │                                │
│   ┌─────────────────────────┼─────────────────────────────┐  │
│   │                   CapabilityLayer                      │  │
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
│   ├── interfaces.py        # 核心接口定义
│   ├── tool_registry.py     # 工具注册表
│   └── intent.py            # 意图解析与路由
├── runtime/
│   ├── runtime.py           # 运行时编排
│   └── skill.py             # Skill 加载
├── capabilities/
│   ├── base.py              # 能力基类
│   ├── factory.py           # 按包约定发现 Capability
│   └── <platform>/capability.py  # 渠道能力包
├── api_clients/
│   ├── base.py              # 客户端基类（重试/限流）
│   └── <platform>_client.py # 按约定可选的 Provider Client
├── persistence/
│   ├── store.py             # SQLite 持久化
│   └── session_manager.py   # 会话管理器
├── logging/
│   └── __init__.py          # 结构化日志
├── user_skills/
│   └── orchestrator.py      # 用户层编排 Skill
└── tests/
    └── test_ad_agent.py     # 单元测试
```

## 扩展新平台

新增渠道只需按包约定提供自己的实现，不需要修改中心 Router、Runtime 或平台列表：

```python
# 1. 创建 API 客户端（可选）
#    agents/ad_agent/api_clients/new_network_client.py
class NewPlatformClient(BasePlatformClient):
    def _do_request(self, method, url, **kwargs): ...

# 工厂名按约定自动发现：create_new_network_client(credentials)

# 2. 创建 Capability
#    agents/ad_agent/capabilities/new_network/capability.py
class NewPlatformCapability(BaseCapability):
    platform_name = "new_platform"
    
    def register_tools(self):
        return [
            (ToolDefinition(...), NewHandler()),
            ...
        ]
    
    # ToolDefinition 自描述 action/resource_type/parent_resource_type，
    # 不需要修改中心 Router

# 工厂名按约定自动发现：create_new_network_capability(api_client)
```

如果渠道通过 `skills/channels/<name>/SKILL.md` 自动加载，Runtime 会发现同名
Capability 并注入按渠道创建的 Client；没有 Client 时仍可安全生成 dry-run 计划。
只有需要补充专家知识、SOP 或安全边界时才修改 `SKILL.md`。业务层和跨渠道 Skill
仍然可以通过自己的 `tools.py` 提供扩展 Tool。
需要严格的多步 SOP 时，可在 Skill 目录旁提供可选的 `workflow.yaml`；它只声明
Tool 之间的依赖和输入输出映射，不包含可执行代码，且普通渠道不要求配置它。

## 扩展 Skill + Tools

新增能力优先放在独立 Skill 目录，不需要修改 Runtime 的核心路由。目录至少包含
`SKILL.md`，并在 `tools.py` 或 `tools/__init__.py` 中导出：

```python
def create_skill(api_client=None):
    return MySkill(api_client)
```

返回的 Skill 需要实现 `get_tools()`、`get_tool_handler(tool_name)`。每个 Tool
应在自己的 `ToolDefinition` 中声明元数据；标准意图无需额外映射，自定义意图
可使用 `intent_types=["my_intent"]`。Runtime 会自动发现该目录，注册声明的
工具；没有可执行 Handler 的声明不会被注册，也不会因为 Skill 文档存在而伪造执行能力。
所有扩展工具继续经过 schema 校验、账户白名单、dry-run/live gate、红线字段检查和审计。

内置四渠道的 Provider 实现仍位于 `capabilities/` 和 `api_clients/`，Skill plugin
只负责扩展工具编排和 Handler；默认模式不会触发线上写 API。

## 许可证

MIT
