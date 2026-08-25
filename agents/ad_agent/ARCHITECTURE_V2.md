# ad-agent 架构设计 v2.0

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
│  │ - LLM/P规则      │  │ - 多平台支持    │  │ - 42 tools               │    │
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
│  │ 12 tools    │  │ 12 tools    │  │ 11 tools    │  │ 7 tools          │  │
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
    - intent_type: create_campaign | boost_post | download_report
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

### 2. IntentRouter (意图路由器)
```python
# 位置: core/intent.py
class SimpleIntentRouter:
    """根据意图类型路由到对应工具"""
    
    DEFAULT_INTENT_TOOLS = {
        "create_campaign": {
            "meta": ["meta_create_campaign", "meta_create_ad_set", "meta_create_ad"],
            "google": ["google_create_campaign", "google_create_ad_group", "google_create_ad"],
            "tiktok": ["tiktok_create_campaign", "tiktok_create_ad_group", "tiktok_create_ad"],
            "dv360": ["dv360_create_campaign", "dv360_create_io", "dv360_create_line_item"],
        },
        "download_report": {
            "meta": ["meta_get_campaign_report"],
            "google": ["google_get_campaign_report"],
            "tiktok": ["tiktok_get_campaign_report"],
            "dv360": ["dv360_get_line_item_report"],
        },
        "list_campaigns": {
            "meta": ["meta_list_campaigns"],
            "google": ["google_list_campaigns"],
            "tiktok": ["tiktok_list_campaigns"],
        }
    }
```

### 3. ToolRegistry (工具注册中心)
```python
# 位置: core/tool_registry.py
class SimpleToolRegistry:
    """工具注册与执行中心"""
    
    def register(self, capability: CapabilityModule):
        """注册平台能力模块"""
        for tool_def in capability.tool_definitions:
            self._tools[tool_def.name] = tool_def
            self._handlers[tool_def.name] = capability.get_handler(tool_def.name)
    
    def execute(self, session_ctx: ToolContext, tool_name: str, tool_input: dict) -> ToolResult:
        """执行工具调用"""
        handler = self._handlers.get(tool_name)
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
                # ... 12 tools total
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
    # 12 tools: list/get campaign/adgroup/ad + report

class TikTokCapability(BaseCapability):
    """TikTok Business API 能力"""
    # 11 tools: list/get campaign/adgroup/ad + report

class DV360Capability(BaseCapability):
    """DV360 API 能力 (Mock)"""
    # 7 tools: list/get campaign/io/line_item + report
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

## 三、工具清单 (42 Tools)

| 平台 | 工具数量 | 工具列表 |
|------|---------|---------|
| **Meta** | 12 | meta_list_campaigns, meta_list_accounts, meta_boost_post,<br>meta_get_campaign, meta_get_adset, meta_get_ad,<br>meta_list_ad_sets, meta_list_ads,<br>meta_create_campaign, meta_create_ad_set, meta_create_ad,<br>meta_get_campaign_report |
| **Google Ads** | 12 | google_list_campaigns,<br>google_get_campaign, google_list_ad_groups, google_get_ad_group,<br>google_list_ads, google_get_ad,<br>google_list_asset_groups, google_get_asset_group,<br>google_create_campaign, google_create_ad_group, google_create_ad,<br>google_get_campaign_report |
| **TikTok** | 11 | tiktok_list_campaigns, tiktok_list_adgroups, tiktok_list_ads,<br>tiktok_get_campaign, tiktok_get_adgroup, tiktok_get_ad,<br>tiktok_spark_ads_create,<br>tiktok_create_campaign, tiktok_create_ad_group, tiktok_create_ad,<br>tiktok_get_campaign_report |
| **DV360** | 7 | dv360_list_advertisers, dv360_list_campaigns, dv360_get_campaign,<br>dv360_create_campaign, dv360_create_io, dv360_create_line_item,<br>dv360_get_line_item_report |

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

## 五、安全机制

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
# 所有写操作都需要二次确认
if tool_def.is_write_tool and not request.confirmed:
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
| `runtime/runtime.py` | 680 | Agent 主循环、Session 管理、工具执行 |
| `core/intent.py` | 533 | 意图解析、路由逻辑 |
| `core/tool_registry.py` | 150 | 工具注册与执行 |
| `capabilities/base.py` | 227 | 能力模块基类 |
| `capabilities/meta_capability.py` | 26K | Meta 渠道实现 |
| `capabilities/platform_capabilities.py` | 50K | Google/TikTok/DV360 渠道实现 |
| `api_clients/base.py` | 280 | API 客户端基类 |
| `api_clients/meta_client.py` | 19K | Meta API 实现 |
| `api_clients/google_ads_client.py` | 20K | Google Ads API 实现 |
| `api_clients/tiktok_client.py` | 27K | TikTok API 实现 |
| `api_clients/dv360_client.py` | 16K | DV360 API 实现 |
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
│   ├── meta/SKILL.md        # Meta Marketing API (10 tools)
│   ├── google-ads/SKILL.md  # Google Ads API (10 tools)
│   ├── tiktok/SKILL.md      # TikTok Ads API (9 tools)
│   └── dv360/SKILL.md       # DV360 API (9 tools)
├── businesses/               # 业务层 Skill（业务规则）
│   ├── ecommerce/SKILL.md   # 电商业务
│   ├── app/SKILL.md         # App 推广业务
│   └── social/SKILL.md      # 社交媒体业务
└── cross-channel/            # 跨渠道 Skill
    └── SKILL.md              # 跨渠道管理工具
```

### 2. Skill 加载流程

```python
# api_server.py 初始化
runtime_skill_loader = RuntimeSkillLoader()
runtime_skill_loader.add_root(str(skills_root / "channels"))
runtime_skill_loader.add_root(str(skills_root / "businesses"))
runtime_skill_loader.add_root(str(skills_root / "cross-channel"))
runtime_skills = runtime_skill_loader.load_all()

# 输出: ✅ 已加载 4 个 Skills: ['google-ads-api', 'meta-marketing-api', 'dv360-api', 'tiktok-ads-api']
```

### 3. Skill 解析逻辑

`SkillContract` 类支持多种 SKILL.md 格式：

1. **Frontmatter 解析**：
   - 嵌套格式: `skill: {name: ..., description: ..., platform: ...}`
   - 直接格式: `name: ..., description: ...`

2. **工具定义提取**：
   - `### Tool: tool_name` 格式
   - Markdown 表格格式: `| Tool | 功能 | 参数 |`

### 4. Skills vs Capabilities

| 概念 | 说明 | 数量 |
|------|------|------|
| **Skills** | SKILL.md 定义的能力集合 | 4 个 Channel Skills |
| **Capabilities** | Python 实现的渠道能力模块 | 4 个 (Meta/Google/TikTok/DV360) |
| **Tools** | 具体可执行的工具函数 | 42 个 |

**关系**：
- Skills 是声明式定义（SKILL.md）
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

## 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `new_list_campaigns` | 列出广告系列 | account_id, limit |
| `new_create_campaign` | 创建广告系列 | account_id, name, budget |
