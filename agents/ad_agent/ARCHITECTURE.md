# ad-agent 架构设计

## 分层架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         业务层 (Businesses)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  ecommerce   │  │     app      │  │    social    │              │
│  │  (电商业务)   │  │  (App推广)    │  │  (社交业务)   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                        │
│         └─────────────────┴─────────────────┘                        │
│                     声明可用渠道 + 业务规则                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       渠道层 (Channels)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │     meta     │  │  google-ads  │  │    tiktok    │              │
│  │   (Meta API)  │  │  (Google Ads) │  │  (TikTok API) │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐                                                  │
│  │    dv360     │  (DV360 API)                                     │
│  └──────────────┘                                                  │
│                     通用 API 能力 + 工具实现                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    动态工具选择器 (ToolSelector)                     │
│  • 根据业务上下文过滤可用渠道                                        │
│  • 根据意图类型筛选相关工具                                          │
│  • 注入平台专家知识                                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LLM 调用                                      │
│  • 精简的工具列表（按意图筛选，当前 Capability 共 143 个）             │
│  • 平台专家知识摘要                                                  │
│  • 业务规则上下文                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
skills/
├── channels/               # 渠道层（通用 API 能力）
│   ├── meta/              # Meta Marketing API
│   │   └── SKILL.md       # 自然语言知识、SOP、安全边界
│   ├── google-ads/        # Google Ads API
│   │   └── SKILL.md       # 自然语言知识、SOP、安全边界
│   ├── tiktok/            # TikTok Business API
│   │   └── SKILL.md       # 自然语言知识、SOP、安全边界
│   └── dv360/             # DV360 API
│       └── SKILL.md       # 自然语言知识、SOP、安全边界
│
├── businesses/             # 业务层（特定业务规则）
│   ├── README.md          # 业务层设计说明
│   ├── ecommerce/         # 电商业务
│   │   └── SKILL.md       # Meta + Google, 预算 ¥100-¥100,000
│   ├── app/               # App 推广业务
│   │   └── SKILL.md       # Google only, 预算 ¥50-¥50,000
│   └── social/            # 社交媒体业务
│       └── SKILL.md       # Meta + Google + TikTok, 预算 ¥200-¥200,000
│
└── cross-channel/          # 跨渠道设计说明；当前由 Runtime 聚合器提供可执行摘要
    └── SKILL.md
```

## 核心设计原则

### 0. Skill、Capability 和参数契约的边界

`SKILL.md` 是自然语言上下文：描述平台知识、SOP、适用范围和安全边界；它不是
Tool 注册表，也不执行代码。Capability/plugin 才提供 `ToolDefinition`、Handler
和 Provider Client。每个 Tool 自己声明 action、资源层级、输入 Schema、固定枚举
以及可选的 `lookup_tool`。

固定枚举由 `/parameter-options` 暴露；App、地域、转化事件等账户相关值由
`/parameter-options/resolve` 调用对应的只读 lookup Tool 获取。Resolver 复用权限、
账户白名单和超时边界，并可返回绑定用户/会话/账户的短期 selection token。

标准 Skill 只需要自然语言 SOP。流程由 LLM 根据 Skill 上下文提出计划，再由
Runtime、Tool metadata 和 Harness 负责工具选择、顺序、权限、账户、dry-run、确认、
幂等和恢复检查。`workflow.yaml` 不是 Skill 的上传、编辑或执行入口；Skill 包中的
其他文件可以被保存和管理，但不会因此获得执行能力。

### 1. 业务 Skill 不直接引用渠道 Skill
```python
# ❌ 错误：业务直接 import 渠道
from channels.meta import MetaTools

# ✅ 正确：通过 BusinessContext 声明
business_context = BusinessContext(
    business_name="ecommerce",
    allowed_channels=["meta", "google"],
)
```

### 2. 业务规则配置化
```yaml
# ecommerce/SKILL.md
business:
  allowed_channels: [meta, google]
  disallowed_channels: [tiktok, dv360]
  allowed_campaign_types: [SHOPPING, SEARCH, DISPLAY]
  business_rules:
    min_budget: 100
    max_budget: 100000
    focus_metrics: [ROAS, CPA, CVR]
```

### 3. 动态工具过滤
```python
# ToolSelector 自动过滤
selector.set_business_context("ecommerce", business_context)
result = selector.optimize_for_llm(user_input, intent, all_tools)
# result['selected_tools'] 只包含 meta + google 的工具
```

## 工具选择流程

```
用户请求: "帮我创建 Google Shopping Campaign"
    │
    ▼
IntentParser 解析
    │
    ├─ intent_type: "create_campaign"
    ├─ platforms: ["google"]
    └─ objective: "sales"
    │
    ▼
BusinessContext 检查
    │
    ├─ business: "ecommerce"
    ├─ allowed_channels: ["meta", "google"]
    └─ google 在允许列表中 ✅
    │
    ▼
ToolSelector 筛选
    │
    ├─ 从当前已注册工具中筛选
    ├─ 只保留 google 平台工具
    ├─ 根据 intent_type="create_campaign" 筛选
    │   ├─ 关键词: ["create", "add", "new"]
    │   └─ 匹配工具:
    │       ├─ google_create_campaign ✅
    │       ├─ google_create_ad_group ✅
    │       └─ ...（按 Capability 实际注册工具决定）
    │
    ▼
最终结果: 匹配工具 + 专家知识
```

## 扩展指南

### 新增渠道或 Tool

新增渠道只需提供约定目录下的 Capability factory（以及可选的 Provider Client）和
渠道 Skill；新增 Tool 只需在所属 Capability/plugin 中注册自描述的 ToolDefinition。
不需要修改中心 Router、Runtime 平台列表或跨渠道映射表。既有渠道也遵循同一注册、
Schema、权限、账户边界和参数透传契约。

### 新增业务（3 步）

```bash
# 步骤 1: 创建业务目录
mkdir -p agents/ad_agent/skills/businesses/new-business

# 步骤 2: 编写 SKILL.md
cat > agents/ad_agent/skills/businesses/new-business/SKILL.md << 'EOF'
---
business:
  name: new-business
  allowed_channels: [meta, google]
  business_rules:
    min_budget: 100
    max_budget: 50000
---
# 新业务 Skill
...
