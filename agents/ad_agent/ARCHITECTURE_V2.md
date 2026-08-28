# ad-agent 架构设计 v2.0

> 实现状态以同目录 `README.md` 与 `PROGRESS.md` 为准。本文件描述分层边界；当前已补充统一 Tool/Skill 契约、动态参数选择凭证、workflow checkpoint/lease/recovery 和 `PersistenceBackend` 抽象。Harness Engineering 的完成度与剩余缺口见 `README.md` 的“Harness Engineering 评估”。

## 一、整体架构概览

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
│  │ - LLM/P规则      │  │ - 多平台支持    │  │ - 72 tools               │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘    │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │ WhitelistValidator│ │ SessionManager  │  │ Persistence Store       │    │
│  │ 账户白名单验证    │  │ 会话管理        │  │ SQLite 持久化            │    │
│  │ - 防止误操作     │  │ - 上下文传递    │  │ - 会话历史               │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Capabilities 层 (渠道能力)                          │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Meta        │  │ Google Ads  │  │ TikTok      │  │ DV360            │  │
│  │ Capability  │  │ Capability  │  │ Capability  │  │ Capability       │  │
│  │ 16 tools    │  │ 18 tools    │  │ 24 tools    │  │ 14 tools         │  │
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
    """基于 LLM 的意图解析"""
    PARSE_PROMPT_TEMPLATE = """
    你是广告投放专家助手。请分析用户的投放需求：
    - intent_type: create/update/pause/resume/cross-channel | boost_post | download_report
    - platforms: ["meta", "google", "tiktok", "dv360"]
    - objective: sales | leads | traffic | brand
    - platform_params: 各平台具体参数
    """

class SimpleIntentParser:
    """基于规则的轻量级解析（默认）"""
    def _detect_intent(self, text: str) -> str:
        # 报表查询
        if any(kw in text for kw in ["报表", "report", "下载", "查看数据"]):
            return "download_report"
        # 创建广告
        if any(kw in text for kw in ["投放", "创建广告", "创建", "promote"]):
            return "create_campaign"
        # 列表查询
        if any(kw in text for kw in ["列表", "list", "查询"]):
            return "list_campaigns"
```

### 2. IntentRouter (发现式意图路由器)
```python
# 位置: core/intent.py
class SimpleIntentRouter:
    """按 ToolDefinition 的 action/resource_type/intent_types 发现工具"""
```

`SKILL.md` 只提供自然语言专家知识、SOP、适用边界和安全注意事项，
不承担可执行 DSL。Capability/plugin 注册可执行 Tool，并在
`ToolDefinition` 中声明 `action`、`resource_type`、`parent_resource_type`
及可选 `intent_types`。Runtime 根据父子资源层级排序创建链，并统一执行
权限、账户、dry-run、审批、幂等与恢复。严格 DAG 只作为特殊扩展点，不是
每个 Skill 的必填配置。

### 3. ToolRegistry (工具注册中心)
```python
# 位置: core/tool_registry.py
class SimpleToolRegistry:
    """工具注册与执行中心"""
    
    def register(self, tool_def: ToolDefinition, handler: ToolHandler):
        """注册一个 Capability/plugin 提供的可执行 Tool"""
        self._tools[tool_def.name] = (tool_def, handler)
    
    def execute(self, session_ctx: ToolContext, tool_name: str, tool_input: dict) -> ToolResult:
        """执行工具调用"""
        definition, handler = self._tools.get(tool_name, (None, None))
        if handler:
            return handler.execute(session_ctx, tool_input)
        return ToolResult(success=False, error="Handler not found")
```

### 4. Capabilities (渠道能力层)
```python
# 位置: capabilities/
class MetaCapability(BaseCapability):
    """Meta Marketing API 能力"""
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

class GoogleAdsCapability(BaseCapability):
    """Google Ads API 能力"""
    # 18 tools: list/get/create campaign/adgroup/ad + keywords/report/update

class TikTokCapability(BaseCapability):
    """TikTok Business API 能力"""
    # 18 tools: list/get/create campaign/adgroup/ad + media/report/update

class DV360Capability(BaseCapability):
    """DV360 API 能力 (Mock)"""
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

## 三、工具清单（当前 Capability 共 72 个工具）

| 平台 | 工具数量 | 工具列表 |
|------|---------|---------|
| **Meta** | 16 | 查询/创建 Campaign、Ad Set、Ad、Creative；受众；Boost；更新 Campaign/Ad Set/Ad；报表 |
| **Google Ads** | 18 | 查询/创建 Campaign、Ad Group、Ad、关键词、PMax Asset Group；报表；更新工具 |
| **TikTok** | 24 | 查询/创建 Campaign、Ad Group、Ad；Creative/视频/图片素材；转化、地域、设备、目录、应用、品牌安全查询；Spark Ads；受众；报表；更新工具 |
| **DV360** | 14 | 查询 Advertiser/Campaign/IO/Line Item；创建 IO/Line Item；报表；更新工具（live 部分未适配） |

## 四、核心数据流

```
用户输入 → IntentParser → ParsedIntent → IntentRouter → ToolPlan
                                              │
                                              ▼
                                         ToolRegistry.execute()
                                              │
                                              ▼
                                         CapabilityHandler
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

## 五、安全机制与执行模式

默认 `execution_mode=dry_run`。所有写工具在 dry-run 中只由 Runtime 生成本地模拟 ID，不进入 Handler/API Client；live 写入必须同时满足测试账户白名单和 `confirmed=True`。读操作可按平台账户查询，但生产环境仍应由调用方限制账户范围。

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

### 2. AdAgentStore (SQLite)
```python
class AdAgentStore:
    """数据存储层"""
    
    # 表结构
    CREATE TABLE sessions (...)
    CREATE TABLE turns (...)
    CREATE TABLE tool_calls (...)
    CREATE TABLE campaigns (...)  # 同步 Campaign 状态
```

## 七、关键文件索引

| 文件 | 行数 | 职责 |
|------|------|------|
| `runtime/runtime.py` | 当前源码 | Agent 主循环、Session 管理、执行模式与安全边界 |
| `core/intent.py` | 533 | 意图解析、路由逻辑 |
| `core/tool_registry.py` | 150 | 工具注册与执行 |
| `capabilities/base.py` | 227 | 能力模块基类 |
| `capabilities/meta/capability.py` | 当前源码 | Meta 渠道 Capability |
| `capabilities/google/capability.py` | 当前源码 | Google Ads 渠道 Capability |
| `capabilities/tiktok/capability.py` | 当前源码 | TikTok 渠道 Capability |
| `capabilities/dv360/capability.py` | 当前源码 | DV360 渠道 Capability |
| `capabilities/factory.py` | 当前源码 | 按包约定发现 Capability |
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
```python
# 1. 创建 API Client
class NewPlatformClient(BaseAPIClient):
    BASE_URL = "https://api.newplatform.com"

# 2. 创建 Capability
class NewPlatformCapability(BaseCapability):
    def __init__(self, api_client: NewPlatformClient):
        super().__init__(
            platform="new_platform",
            tool_definitions=[...]
        )

# 3. 注册到 Runtime
runtime.register_capability(NewPlatformCapability(api_client))
```

### 新增业务场景
```python
# 1. 定义业务规则
business_rules = {
    "allowed_channels": ["meta", "google"],
    "min_budget": 100,
    "max_budget": 100000,
}

# 2. 注入到 ToolSelector
selector.set_business_context("ecommerce", business_rules)
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
# api_server.py 初始化
runtime = AgentRuntime()
runtime.auto_load_skills(str(skills_root), credentials)

# 输出: ✅ 已加载 4 个 Skills: ['google-ads-api', 'meta-marketing-api', 'dv360-api', 'tiktok-ads-api']
```

### 3. Skill 解析逻辑

`SkillContract` 类支持多种 SKILL.md frontmatter 格式：

1. **Frontmatter 解析**：
   - 嵌套格式: `skill: {name: ..., description: ..., platform: ...}`
   - 直接格式: `name: ..., description: ...`

2. **执行能力发现**：SKILL.md 不提取 Tool 定义；渠道 Capability 或 Skill plugin
   提供 `ToolDefinition` 与 Handler，Runtime 只注册真实存在的 executable Tool。

### 4. Skills vs Capabilities

| 概念 | 说明 | 数量 |
|------|------|------|
| **Skills** | SKILL.md 提供的上下文、SOP 和安全边界 | 4 个 Channel Skills |
| **Capabilities** | Python 实现的渠道能力模块 | 4 个 (Meta/Google/TikTok/DV360) |
| **Tools** | Capability/plugin 提供的具体可执行工具 | 72 个基线工具 |

**关系**：
- Skills 是自然语言上下文（SKILL.md）
- Capabilities 是命令式实现（Python 类）
- Tools 是实际执行的函数

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

# Capability 按约定导出 create_new_platform_capability(api_client=None)
# Client 按约定导出 create_new_platform_client(credentials)（可选）
# Runtime/CLI 自动发现，无需修改中心列表
