# ad-agent 生产级完成报告

## 项目概述

**ad-agent** 是一个基于单 Agent + 多 Skills 架构的通用广告投放自动化工具，支持 Meta、Google Ads、TikTok Ads、DV360 四大广告平台。

## 架构特点

### 1. 单 Agent + 多 Skills
- 通过 IntentRouter 自动识别用户意图并路由到对应平台的 Capability
- 每个平台是一个独立的 CapabilityModule，可独立扩展
- 新增平台只需添加新 Capability，无需修改 Core 层

### 2. 生产级 API 客户端
- **重试机制**: 指数退避重试（可配置最大重试次数和延迟）
- **限流器**: 令牌桶算法，防止超出 API 配额
- **错误分类**: AuthError, RateLimitError, TemporaryError, APIError
- **真实 API 集成**: 基于官方文档实现，非模拟数据

### 3. 持久化层
- SQLite 存储会话、工具调用历史、Campaign 状态
- 跨会话恢复 Campaign 上下文
- 线程安全（RLock 保护）

### 4. 结构化日志
- JSON 格式化输出，便于 log aggregation
- 支持文件输出和 stdout
- 上下文感知（工具名、平台、耗时）

### 5. Mock 模式
- 无需 API 凭证即可测试和演示
- 一键切换到真实 API 模式

## 目录结构

```
ad_agent/
├── __init__.py              # 包入口，导出公共 API
├── README.md                # 项目文档
├── requirements.txt         # 依赖列表
├── setup.py                 # 打包配置
├── .gitignore               # Git 忽略规则
│
├── core/                    # 核心层（不依赖业务）
│   ├── interfaces.py        # 接口定义（ToolDefinition, ToolResult 等）
│   ├── tool_registry.py     # 工具注册表
│   └── intent.py            # 意图解析与路由
│
├── runtime/                 # 运行时
│   ├── runtime.py           # AgentRuntime 主循环
│   └── skill.py             # Skill 加载器
│
├── capabilities/            # 业务能力层
│   ├── base.py              # Capability 基类
│   ├── meta_capability.py   # Meta 广告能力
│   └── platform_capabilities.py  # Google/TikTok/DV360 能力
│
├── api_clients/             # API 客户端层
│   ├── base.py              # 基类（重试/限流/错误分类）
│   ├── meta_client.py       # Meta Marketing API
│   ├── google_ads_client.py # Google Ads API
│   ├── tiktok_client.py     # TikTok Business API
│   └── dv360_client.py      # DV360 API（纯 Python JWT 签名）
│
├── persistence/             # 持久化层
│   ├── store.py             # SQLite 存储
│   └── session_manager.py   # 会话管理器
│
├── logger/                  # 日志系统
│   └── __init__.py          # JSON 格式化器
│
├── user_skills/             # 用户层 Skill
│   └── orchestrator.py      # 跨平台编排 Skill
│
└── tests/                   # 测试
    └── test_ad_agent.py     # 单元测试（26 个用例全通过）
```

## 快速开始

### 安装
```bash
pip install -r requirements.txt
```

### Mock 模式（无需凭证）
```python
from ad_agent import AgentRuntime, create_meta_capability, create_google_capability

runtime = AgentRuntime()
runtime.register_capability(create_meta_capability())
runtime.register_capability(create_google_capability())

result = runtime.run(
    user_input="帮我投放Meta和Google广告，预算100元/天",
    user_id="user_001",
)
print(result["reply"])
```

### 真实 API 模式
```python
import json
from ad_agent import AgentRuntime
from ad_agent.api_clients.meta_client import MetaAPIClient
from ad_agent.capabilities.meta_capability import MetaCapability

# 加载凭证
with open("credentials.json") as f:
    credentials = json.load(f)

# 创建真实 API 客户端
api_client = MetaAPIClient(credentials)
capability = MetaCapability(api_client=api_client)  # 传入真实客户端

runtime = AgentRuntime()
runtime.register_capability(capability)
```

## 测试覆盖

```bash
python -m pytest agents/ad_agent/tests/ -v
```

测试结果：
- 26 passed in 0.06s
- 覆盖：持久化层、API 客户端初始化、Capability 注册、Runtime 集成

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

## 生产级特性清单

| 特性 | 状态 | 说明 |
|------|------|------|
| 重试机制 | ✅ | 指数退避，可配置 |
| 限流器 | ✅ | 令牌桶算法 |
| 错误分类 | ✅ | Auth/RateLimit/Temporary/API |
| 持久化 | ✅ | SQLite，跨会话恢复 |
| 结构化日志 | ✅ | JSON 格式 |
| Mock 模式 | ✅ | 无需凭证测试 |
| WriteGuard | ✅ | 写操作需确认 |
| 单元测试 | ✅ | 26 个用例 |
| 多平台支持 | ✅ | Meta/Google/TikTok/DV360 |
| 可扩展性 | ✅ | 新增平台只需 Capability |

## 与 DAP Agent 对标

| DAP Agent (Go) | ad-agent (Python) | 说明 |
|----------------|-------------------|------|
| Core Engine | AgentRuntime | 主循环入口 |
| SkillLoader | SkillLoader | Skill 加载 |
| ToolRegistry | ToolRegistry | 工具注册表 |
| IntentRouter | SimpleIntentRouter | 意图路由 |
| CapabilityModule | BaseCapability | 能力模块基类 |
| WriteGuard | WriteGuard | 写入保护 |
| - | SQLite Persistence | 持久化层（新增） |
| - | JSON Logger | 结构化日志（新增） |

## 下一步计划

1. **更多测试**: 增加到 60%+ 覆盖率
2. **真实 API 测试**: 使用测试账户验证各平台 API
3. **更多平台**: YouTube Ads、LinkedIn Ads
4. **异步支持**: 使用 asyncio 提高并发性能
5. **Web UI**: 提供 Web 界面管理 Campaign

## 2026-08-26 Google Ads 工具修复

### 问题
- Google Ads 工具执行时报错 "client not configured or customer_id missing"
- 根因：`_get_api_client` 和 `auto_load_skills` 未正确处理平台别名映射（`google-ads` vs `google`）

### 修复
1. **添加 `_credentials` 属性**：在 `AgentRuntime.__init__` 中添加
2. **实现 `set_credentials` 方法**：支持外部设置凭证
3. **修复 `_get_api_client`**：支持平台别名映射（`google-ads` → `google`）
4. **修复 `auto_load_skills`**：使用正确的 credentials key
5. **修复 `_find_skill_by_platform`**：正确查找和加载 Skill

### 测试结果
- ✅ Meta: 25 campaigns 正常返回
- ✅ TikTok: 20 campaigns 正常返回  
- ✅ Google Ads: 工具执行成功（账户无 campaign 返回空）
- ⚠️ DV360: JWT PEM 密钥格式错误（待修复）

### 安全
- 使用 `git filter-branch` 清除历史提交中的敏感凭证
- config.yaml 改为环境变量模板
- 添加 .env.example 说明所需环境变量
