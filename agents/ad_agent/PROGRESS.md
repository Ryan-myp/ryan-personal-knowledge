# ad-agent 当前实现状态

> 本文件记录当前源码状态，不代表所有平台 live API 能力已达到生产可用。默认执行模式为 `dry_run`；真实测试只允许使用 `config.yaml` 中的测试账户白名单，且不能修改线上凭证或账户元数据。下方历史记录仅供追溯，不能作为当前 live 成功证据。

## 当前契约（2026-08-28）

- 单 Agent + 多 Skills + Tools；平台 Capability 是可执行注册表的来源，当前共 129 个工具：Meta 28、Google Ads 27、TikTok 42、DV360 32。Capability 和按约定命名的 Provider Client 均自动发现，不依赖中心渠道/工具配置表；每个 Capability 还提供 Provider 方法覆盖率发布门禁。
- 所有 Campaign 及下级资源创建/更新默认 dry-run；当前不会因工具已注册就调用真实写 API。
- live 仅允许配置白名单账户，且 API 确认必须携带与当前 `session_id + account_id + tool + normalized input + idempotency key` 绑定的 `confirmation_payload`。
- 白名单只有一个账户时允许兼容性自动选择；多账户配置必须由调用方显式指定目标账户。
- 创建工具已支持参数目录：固定枚举/数组元素/条件依赖进入 ToolSchema，TikTok App 与地域等动态字段关联现有 lookup 工具，`/tools` 返回完整 Schema。
- `access_token`、`refresh_token`、`developer_token`、`client_id`、`client_secret`、`private_key`、`bc_id`、`partner_id`、`mcc` 等字段禁止出现在工具 payload/updates 中；凭证不写入 SQLite。
- 无 Provider Client 的读取默认 fail-closed；离线 fixture 仅在显式 `offline_mode=True` 下可用。
- Workflow 有持久化 heartbeat/lease：活跃任务刷新 lease，恢复 worker 只能原子 claim
  过期或非终态任务；当前 SQLite 仍按单进程部署，多实例需换共享 backend。
- Provider timeout、连接错误、限流或 5xx 等不确定写结果会进入 `unknown` /
  `recovery_required`，并保留 pending 幂等 reservation，等待只读回查后再决定状态。
- Provider live lookup 可为动态字段签发短时 selection token；创建请求提交
  `selection_tokens` 后会校验 user/session/account/tool/field/source 绑定，live 不接受未经 lookup 证明的裸动态 ID。
- Contract validator 将内置工具数量作为 minimum baseline；新增 Skill/Tool 不需要修改
  中央计数，但仍必须通过统一 schema、权限、重放策略和红线字段校验。
- 广告类型目录已按 `docs/ad-platform-hierarchy-guide-v5.md` 拆分为广告系列家族和具体
  子格式：Google Search/PMax/Shopping/Video/Display/App，Meta Traffic/Conversion/
  Lead/Engagement/Catalog/Messaging，TikTok Product Sales/Spark/Lead/App/Brand。
  `supported_dry_run`、`partial_dry_run`、`declared_only` 分别表达专用契约、部分契约和
  仅纳入能力地图；DV360 详细广告类型建设暂缓。
- `scripts/validate_contracts.py` 支持生成和校验版本化契约快照：
  `contracts/builtin_tools.json`；它用于审查已有 Tool 的 Schema/元数据漂移，
  不参与 Runtime 路由或渠道配置。
- `scripts/audit_capabilities.py` 按 Capability 包约定生成 action/resource 矩阵和创建链
  缺口报告；它是 release gate，不是 Runtime 的第二套渠道注册表。
- 每个渠道 Capability 包另有 `api_surface.py`，声明已实现与计划中的官方资源操作；审计会
  检查已实现项是否同时存在 Client 方法、覆盖映射和 executable Tool，并把计划项显式列为
  后续建设缺口。

## 项目概述

**ad-agent** 是一个基于单 Agent + 多 Skills 架构的通用广告投放自动化工具，支持 Meta、Google Ads、TikTok Ads、DV360 四大广告平台。

## 架构特点

### 1. 单 Agent + 多 Skills
- 通过 IntentRouter 自动识别用户意图并路由到对应平台的 Capability
- 每个平台是一个独立的 CapabilityModule，可独立扩展
- 新增平台只需按约定添加渠道 Capability（以及可选的同名 API Client）；无需修改 Core、Runtime、Router 或 CLI 中心列表

### 2. API 客户端封装
- **重试机制**: 指数退避重试（可配置最大重试次数和延迟）
- **限流器**: 令牌桶算法，防止超出 API 配额
- **错误分类**: AuthError, RateLimitError, TemporaryError, APIError
- **真实 API 集成**: 已提供平台客户端和 Handler，但 live 能力需逐工具验证

### 3. 持久化层
- SQLite 存储会话、工具调用历史、Campaign 状态
- 跨会话恢复 Campaign 上下文
- 线程安全（RLock 保护）

### 4. 结构化日志
- JSON 格式化输出，便于 log aggregation
- 支持文件输出和 stdout
- 上下文感知（工具名、平台、耗时）

### 5. Dry-run 模式
- 无需调用线上写 API 即可测试参数、路由和层级编排
- live 只允许显式指定测试账号并确认

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
│   ├── factory.py           # 按包约定发现 Capability
│   └── <platform>/capability.py
│
├── api_clients/             # API 客户端层
│   ├── base.py              # 基类（重试/限流/错误分类）
│   ├── meta_client.py       # Meta Marketing API
│   ├── google_ads_client.py # Google Ads API
│   ├── tiktok_client.py     # TikTok Business API
│   └── <platform>_client.py # 按约定可选的 Provider Client
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
    ├── test_ad_agent.py      # 核心回归测试
    └── ...                   # Harness、契约与四渠道回归测试
```

## 快速开始

### 安装
```bash
pip install -r requirements.txt
```

### 离线契约评测模式（无需凭证）
```python
from ad_agent import AgentRuntime, create_meta_capability, create_google_capability

# 仅用于显式离线测试/评测；产品 Runtime 默认必须配置 LLM。
runtime = AgentRuntime(require_llm=False, offline_mode=True)
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
import os
from ad_agent import AgentRuntime
from ad_agent.core.llm_client import create_llm_client
from ad_agent.api_clients.meta_client import MetaAPIClient
from ad_agent.capabilities.meta import create_meta_capability

# 加载凭证
with open("credentials.json") as f:
    credentials = json.load(f)

# 创建真实 API 客户端；Runtime 仍默认为 dry-run
api_client = MetaAPIClient(credentials["meta"])
capability = create_meta_capability(api_client)

# 生产入口仍需注入 LLM；真实 API 客户端只负责渠道调用，写操作仍默认为 dry-run。
runtime = AgentRuntime(
    llm_client=create_llm_client(model=os.environ["LLM_MODEL"], api_key=os.environ["OPENAI_API_KEY"]),
    require_llm=True,
)
runtime.register_capability(capability)
```

## 测试覆盖

```bash
python -m pytest agents/ad_agent/tests/ -v
```

测试结果：
- 当前 `agents/ad_agent/tests/`：290 passed（本轮完整回归；另有 1 条本机依赖弃用 warning）
- 覆盖：工具注册、Schema 校验、白名单、dry-run 不调用 Client、跨平台账户、层级 ID 传递、live 确认、持久化和 Runtime 集成

## 扩展新平台

新增渠道只需按包约定提供自己的实现；不需要修改中心 Router、Runtime 或 CLI：

```python
# 1. 创建 API 客户端（可选）
# agents/ad_agent/api_clients/new_platform_client.py
class NewPlatformClient(BasePlatformClient):
    def _do_request(self, method, url, **kwargs): ...

# 工厂名：create_new_platform_client(credentials)

# 2. 创建 Capability
# agents/ad_agent/capabilities/new_platform/capability.py
class NewPlatformCapability(BaseCapability):
    platform_name = "new_platform"
    
    def register_tools(self):
        return [
            (ToolDefinition(...), NewHandler()),
            ...
        ]
    
    # ToolDefinition 自描述 action/resource_type/parent_resource_type，
    # 不需要修改中心 Router

# 工厂名：create_new_platform_capability(api_client)
```

将 `SKILL.md` 放入 `skills/channels/<platform>/` 后，Runtime/CLI 会自动发现渠道
Capability。`SKILL.md` 仍只负责自然语言知识、SOP 和安全边界；只有渠道确实需要
补充使用指导时才修改它。

## 生产级特性清单

| 特性 | 状态 | 说明 |
|------|------|------|
| 重试机制 | ✅ | 指数退避，可配置 |
| 限流器 | ✅ | 令牌桶算法 |
| 错误分类 | ✅ | Auth/RateLimit/Temporary/API |
| 持久化 | ✅ | SQLite，跨会话恢复 |
| 结构化日志 | ✅ | JSON 格式 |
| Dry-run 模式 | ✅ | 无需调用线上写 API 即可测试 |
| WriteGuard | ✅ | 持久化幂等、显式确认、unknown 结果保留 reservation、workflow lease/claim 已接入 |
| 单元测试 | ✅ | `agents/ad_agent/tests/` 全量 245 个用例 |
| 多平台支持 | ✅ | Meta/Google/TikTok/DV360 |
| 可扩展性 | ✅ | Capability 与 Provider Client 按包约定自动发现，无需修改中心 Router/Runtime |

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

## 修复记录 - 2026-08-26

### Google Ads API 端点修复
- **问题**: 所有 Google Ads API 请求返回 404
- **原因**: URL 端点格式错误，使用了  而不是 
- **修复**: 
  -  第 530 行
  - 从  改为 

### Credentials 路径修复
- **问题**: API 服务启动时无法加载凭证
- **原因**:  中 credentials 路径计算错误
- **修复**: 
  -  第 50 行
  - 从  改为 

### 平台别名映射修复
- **问题**:  返回 None
- **原因**: credentials 中 key 是 ，不是 
- **修复**: 
  -  第 148-153 行
  - 添加平台别名映射逻辑

### 测试结果
- ✅ Google Ads: API 正常工作（账户无 campaign 返回空）
- ✅ Meta: 正常
- ✅ TikTok: 正常
- ⚠️ DV360: JWT PEM 密钥格式错误（待修复）


## 2026-08-26 Google Ads API 端点修复

### 问题
- Google Ads API 所有请求返回 404
- 原因：URL 端点格式错误，使用了 `:search` 而不是 `/googleAds:search`

### 修复
1. **`agents/ad_agent/api_clients/google_ads_client.py`**
   - 第 530 行：从 `/customers/{id}:search` 改为 `/customers/{id}/googleAds:search`

2. **`agents/ad_agent/api_server.py`**
   - 第 50 行：修复 credentials 路径，从 `parent.parent` 改为 `parent.parent.parent`
   - 添加 JSON 凭证文件加载逻辑

3. **`agents/ad_agent/runtime/runtime.py`**
   - 第 148-153 行：添加平台别名映射（`google-ads` → `google`）

### 测试结果
- ✅ Google Ads: API 正常工作
- ✅ Meta: 正常
- ✅ TikTok: 正常
- ⚠️ DV360: JWT PEM 密钥格式错误（待修复）

## 2026-08-26 测试账户更新

### 正确的测试账户 ID
- **Meta**: `2806375919473667`
- **Google Ads**: `9055507554`
- **TikTok**: `7397068114548195329`
- **DV360**: `5110831`

### 测试结果
| 平台 | 状态 | Campaigns |
|------|------|-----------|
| Google Ads | ✅ | 0 |
| Meta | ✅ | 25 |
| TikTok | ✅ | 20 |
| DV360 | ⚠️ | JWT PEM 密钥格式错误 |

### DV360 JWT 问题
- 原因：`config/dv360_service_account.json` 中的 `private_key` 字段包含转义的 `\n` 而不是实际换行符
- 状态：已修复私钥格式，需要重新测试

## 2026-08-26 最终测试结果

### 测试账户
- **Meta**: `2806375919473667`
- **Google Ads**: `9055507554`
- **TikTok**: `7397068114548195329`
- **DV360**: `5110831`

### 测试结果
| 平台 | 状态 | Campaigns | 说明 |
|------|------|-----------|------|
| Google Ads | ✅ | 0 | 账户无 campaign |
| Meta | ✅ | 25 | 正常返回 |
| TikTok | ✅ | 20 | 正常返回 |
| DV360 | ✅ | 0 | 账户无 campaign |

### 修复内容
1. **Google Ads API 端点** - 从 `:search` 改为 `/googleAds:search`
2. **Credentials 路径** - 修复 `api_server.py` 中的路径计算
3. **平台别名映射** - 添加 `google-ads` → `google` 映射
4. **DV360 私钥** - 将私钥从 `dv360_service_account.json` 合并到 `ad_platform_credentials.json`

## 2026-08-26 Google Ads Campaign 查询修复

### 问题
- Google Ads API 返回 0 campaigns，但 UI 显示有 campaign 数据
- 根因：URL 中使用了 login_customer_id (MCC) 而非 customer_id

### 修复
1. **google_ads_client.py:530**
   - 从 `/customers/{login_customer_id}/googleAds:search`
   - 改为 `/customers/{customer_id}/googleAds:search`

2. **capabilities/google/campaigns.py:GoogleListCampaignsHandler**
   - 在执行时使用 `ctx.account_id` 更新 client 的 customer_id

### 测试结果
- ✅ 查询成功返回 100 campaigns
- ✅ 包含用户截图中的 campaign: App promotion-App-2 (ID: 22078331406)


### 5. Google Ads Campaign 查询修复
- **文件**: agents/ad_agent/api_clients/google_ads_client.py
- **修改 1**: `_search` 方法使用 `customer_id` 而非 `login_customer_id`
  - 错误: `/customers/{login_customer_id}/googleAds:search`
  - 正确: `/customers/{customer_id}/googleAds:search`
- **修改 2**: 添加 `_ensure_valid_token` 方法，自动刷新过期的 access_token
- **文件**: agents/ad_agent/capabilities/google/campaigns.py
- **修改**: `GoogleListCampaignsHandler.execute` 使用 `ctx.account_id` 更新 client 的 customer_id

### 测试结果
```bash
# Google Ads 测试账户: 9055507554
curl -X POST http://localhost:8765/chat \
  -d '{"user_input": "列出 Google Ads campaigns", "account_id": "9055507554"}'
# ✅ Success: true, Campaigns: 100
# ✅ 包含 UI 中的 campaign: App promotion-App-2 (ID: 22078331406)
```

### 6. 渠道技能文件升级
- **问题**: `agents/ad_agent/skills/channels/` 下的技能文件过于简陋（38-78 行）
- **修复**: 将 `knowledge/skills/` 下的专家级内容整合到渠道技能中
- **新增**: 每个渠道创建 `expert/best_practices.md`，包含完整代码示例和最佳实践
- **结果**: 专家知识正确加载到 LLM 上下文

| 渠道 | 原行数 | 新行数 | 工具数 | 专家知识 |
|------|--------|--------|--------|----------|
| google-ads | 42 | 215 | 15 | ✅ 3750 chars |
| meta | 39 | 197 | 14 | ✅ 2630 chars |
| tiktok | 38 | 196 | 14 | ✅ 1830 chars |
| dv360 | 78 | 248 | 52 | ✅ 2229 chars |

### 8. Agent Skills 标准规范对齐
- **参考**: https://agentskills.io/home
- **核心要求**:
  - SKILL.md 必须包含 YAML frontmatter（必需字段：name, description, version, author, created, tags）
  - frontmatter 必须在文件最顶部，用 `---` 包裹
  - 内容结构建议：角色定位 + 核心能力 + 可用 Tools + 参考文档 + 最佳实践 + FAQ
- **当前状态**:
  - ✅ 4 个 Channel Skills 已符合标准格式
  - ✅ Service 正常运行，加载 39 个工具
  - ✅ 已修复 meta Skill tags 拼写错误

### 9. 修复 Google Ads 报表查询 bug
- **问题**: `get_campaign_report() got an unexpected keyword argument 'customer_id'`
- **原因**: Handler 调用签名与 Client 方法签名不匹配
- **修复**:
  - Handler 现在传递正确的参数: `campaign_ids`, `date_from`, `date_to`
  - Tool 定义更新: `campaign_ids` 改为可选，默认查前5个campaign
- **结果**: 报表查询功能恢复正常

### 10. 输出格式优化和流式思考
- **TikTok/Google Ads 列表美化**: Campaign 列表改为表格格式，显示关键字段
- **Google Ads 报表修复**: 添加 summary 汇总，改进展示格式
- **流式思考过程**: 
  - 新增 `/chat/stream` SSE 端点
  - 前端实时显示 💭 思考步骤
  - 工具执行状态实时反馈
  - 支持 Markdown 表格渲染

### 11. 修复 Google Ads 平台名称映射
- **问题**: 查询报表时报"需要确认账户ID"
- **原因**: Intent 使用 `google`，但工具注册为 `google-ads`，导致账户验证失败
- **修复**: 添加 `platform_name_map` 映射 `google` → `google-ads`
