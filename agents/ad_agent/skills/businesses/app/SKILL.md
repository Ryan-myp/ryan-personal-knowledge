---
business:
  name: app
  version: "1.0"
  description: "App 推广投放 Skill - 专注于应用安装、激活、留存"
  allowed_channels:
    - google
  disallowed_channels:
    - meta
    - tiktok
    - dv360
  allowed_campaign_types:
    - APP_INSTALL
    - APP_engagement
  business_rules:
    min_budget: 50
    max_budget: 50000
    focus_metrics:
      - CPI
      - Retention
      - LTV
    default_objective: "APP_INSTALL"
---

# App 业务 Skill

## 可用渠道

| 渠道 | 状态 | 说明 |
|------|------|------|
| Google | ✅ 可用 | App Campaign (UAC) |
| Meta | ❌ 不可用 | App 业务暂不支持 |
| TikTok | ❌ 不可用 | App 业务暂不支持 |
| DV360 | ❌ 不可用 | App 业务暂不支持 |

## 业务规则

- **预算范围**: ¥50 - ¥50,000
- **核心指标**: CPI、Retention、LTV
- **默认目标**: APP_INSTALL（应用安装）

## 常用场景

### 场景 1: 新 App 上线
```yaml
objective: APP_INSTALL
campaign_type: APP_install
channels:
  - google
```

### 场景 2: 应用激活
```yaml
objective: APP_engagement
event: "app_open"
channels:
  - google
```

### 场景 3: 留存优化
```yaml
objective: RETENTION
retention_days: 7
channels:
  - google
```

## 工具列表

App 业务可用的工具（从渠道层过滤）：

### Google App Campaign
- google_create_campaign (APP)
- google_create_ad_group
- google_optimize_bidding
- google_get_campaign_report

## 注意

- 只支持 Google App Campaign
- 建议优先测试 Google，验证留存后再考虑其他平台
