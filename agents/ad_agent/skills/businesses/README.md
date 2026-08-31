# 业务层 Skill 设计

## 核心原则

1. **业务 Skill 不直接引用渠道 Skill**
   - 业务 Skill 通过 `allowed_channels` 声明可用渠道
   - 业务 Skill 通过 `business_rules` 定义投放规则
   - 运行时由 ToolSelector 根据业务上下文过滤工具

2. **每个业务有独立的投放策略**
   - 电商业务：关注转化、ROAS
   - App 业务：关注安装、留存
   - 社交业务：关注互动、曝光

3. **业务规则可配置**
   - 允许的渠道列表
   - 允许的广告类型
   - 预算范围限制
   - 定向规则

## 目录结构

```
skills/
├── channels/               # 渠道层（通用 API 能力）
│   ├── meta/              # Meta API
│   ├── google-ads/        # Google Ads API
│   ├── tiktok/            # TikTok API
│   └── dv360/             # DV360 API
│
├── businesses/             # 业务层（特定业务规则）
│   ├── ecommerce/         # 电商业务（Meta + Google）
│   ├── app/               # App 业务（Google）
│   └── social/            # 社交业务（Meta + Google + TikTok）
│
└── cross-channel/          # 跨渠道管理（通用）
```

## 业务 Skill 示例

### ecommerce (电商业务)
```yaml
business:
  name: ecommerce
  description: "电商平台广告投放"
  allowed_channels: [meta, google]  # 只允许 Meta 和 Google
  allowed_campaign_types: [SHOPPING, SEARCH, DISPLAY, MAX]
  business_rules:
    min_budget: 100
    max_budget: 100000
    focus_metrics: [ROAS, CPA, CVR]
```

### app (App 业务)
```yaml
business:
  name: app
  description: "App 推广投放"
  allowed_channels: [google]  # 只用 Google
  allowed_campaign_types: [APP_INSTALL, APP_engagement]
  business_rules:
    min_budget: 50
    max_budget: 50000
    focus_metrics: [CPI, Retention, LTV]
```

### social (社交业务)
```yaml
business:
  name: social
  description: "社交媒体广告投放"
  allowed_channels: [meta, google, tiktok]
  allowed_campaign_types: [BRAND_AWARENESS, ENGAGEMENT, TRAFFIC]
  business_rules:
    min_budget: 200
    max_budget: 200000
    focus_metrics: [CPM, Reach, Engagement]
```

## 工具选择流程

```
用户请求 (业务: ecommerce)
    │
    ▼
BusinessSkillPolicy 解析
    │
    ├─ allowed_channels: [meta, google]
    ├─ allowed_campaign_types: [SHOPPING, SEARCH]
    └─ policy rules: {...}
    │
    ▼
RuntimePolicy + ToolSelector 过滤
    │
    ├─ 从当前已注册工具中筛选
    ├─ 只保留 meta + google 平台的工具
    ├─ 只保留 SHOPPING/SEARCH 相关工具
    └─ 最终: ~15 个工具
    │
    ▼
LLM 收到精简上下文
```

## 扩展新业务（3 步）

### 步骤 1：创建业务 SKILL.md
```bash
mkdir -p agents/ad_agent/skills/businesses/new-business
```

### 步骤 2：配置业务规则
```yaml
business:
  name: new-business
  allowed_channels: [meta, google]
  business_rules:
    min_budget: 100
    max_budget: 50000
```

### 步骤 3：自动生效
```bash
# 无需修改其他代码，自动加载
python agents/ad_agent/api_server.py
```

## 与渠道层的关系

```
业务层 (Businesses)
    │
    ├─ 声明 allowed_channels
    ├─ 声明 business_rules
    └─ 不直接调用渠道 API
    
    │
    ▼
渠道层 (Channels)
    ├─ 提供通用 API 能力
    ├─ 工具实现
    └─ 专家知识
    
    │
    ▼
ToolSelector 动态选择
    ├─ 根据业务上下文过滤工具
    └─ 只返回业务可用的工具
```

## 关键设计

1. **解耦**: 业务 Skill 不 import 渠道 Skill
2. **声明式**: 业务通过 YAML 声明可用渠道
3. **动态过滤**: ToolSelector 运行时过滤工具
4. **可扩展**: 新业务只需添加 SKILL.md
