# ad-agent - 多渠道广告投放 Agent

基于单 Agent + 多 Skills 架构的通用广告投放自动化工具，支持 Meta、Google Ads、TikTok Ads、DV360 四大广告平台。

## 架构特点

- **单 Agent + 多 Skills**：通过意图路由自动分发到对应平台的 Capability
- **生产级 API 客户端**：真实 API 集成 + 指数退避重试 + 限流器
- **持久化层**：SQLite 存储会话、工具调用、Campaign 状态
- **结构化日志**：JSON 格式，便于 log aggregation
- **Mock 模式**：无需凭证即可测试/演示
- **WriteGuard**：写操作需人工确认
- **可扩展**：新增平台只需添加新 Capability

## 支持的广告平台

| 平台 | Skill | API 客户端 | 工具数量 |
|------|-------|-----------|---------|
| Meta | meta-marketing-api-expert | meta_client.py | 6 |
| Google Ads | google-ads-api-expert | google_ads_client.py | 4 |
| TikTok | tiktok-ads-expert | tiktok_client.py | 5 |
| DV360 | dv360-expert | dv360_client.py | 4 |

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```python
from ad_agent import AgentRuntime, create_meta_capability, create_google_capability
from ad_agent.persistence.store import AdAgentStore

# 初始化（带持久化）
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

## 使用真实 API

```python
import json

# 加载凭证
with open("credentials.json") as f:
    credentials = json.load(f)

# 创建真实 API 客户端
from ad_agent.api_clients.meta_client import MetaAPIClient
from ad_agent.capabilities.meta_capability import MetaCapability

api_client = MetaAPIClient(credentials)
capability = MetaCapability(api_client=api_client)  # 传入真实客户端

runtime.register_capability(capability)
```

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
│   ├── meta_capability.py   # Meta 广告能力
│   └── platform_capabilities.py  # Google/TikTok/DV360 能力
├── api_clients/
│   ├── base.py              # 客户端基类（重试/限流）
│   ├── meta_client.py       # Meta Marketing API
│   ├── google_ads_client.py # Google Ads API
│   ├── tiktok_client.py     # TikTok Business API
│   └── dv360_client.py      # DV360 API
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

只需三步：

```python
# 1. 创建 API 客户端
class NewPlatformClient(BasePlatformClient):
    def _do_request(self, method, url, **kwargs): ...

# 2. 创建 Capability
class NewPlatformCapability(BaseCapability):
    platform_name = "new_platform"
    
    def register_tools(self):
        return [
            (ToolDefinition(...), NewHandler()),
            ...
        ]
    
    def _get_campaign_tool_sequence(self):
        return ["new_create_campaign", "new_create_ad_group", ...]

# 3. 注册到 Runtime
runtime.register_capability(NewPlatformCapability(api_client))
```

## 许可证

MIT
