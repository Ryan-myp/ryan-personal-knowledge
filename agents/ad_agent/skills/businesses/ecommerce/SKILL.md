---
business:
  name: ecommerce
  version: "1.0.0"
  description: "电商平台广告投放 Skill - 专注于商品推广、销售转化"
  allowed_channels:
    - meta
    - google
  disallowed_channels:
    - tiktok
    - dv360
  allowed_campaign_types:
    - SHOPPING
    - SEARCH
    - DISPLAY
    - MAX
  business_rules:
    min_budget: 100
    max_budget: 100000
    focus_metrics:
      - ROAS
      - CPA
      - CVR
    default_objective: "SALES"
---

# 电商业务 Skill

## 可用渠道

| 渠道 | 状态 | 说明 |
|------|------|------|
| Meta | ✅ 可用 | Facebook/Instagram 商品推广 |
| Google | ✅ 可用 | Shopping/Search/PMax 广告 |
| TikTok | ❌ 不可用 | 电商业务暂不支持 |
| DV360 | ❌ 不可用 | 电商业务暂不支持 |

## 业务规则

- **预算范围**: ¥100 - ¥100,000
- **核心指标**: ROAS、CPA、CVR
- **默认目标**: SALES（销售转化）

## 常用场景

### 场景 1: 新品上市
```yaml
objective: SALES
campaign_types:
  - SHOPPING  # Google Shopping
  - SEARCH    # 搜索品牌词
channels:
  - google
  - meta
```

### 场景 2: 大促投放
```yaml
objective: SALES
budget_multiplier: 2.0  # 预算翻倍
channels:
  - google
  - meta
```

### 场景 3: 再营销
```yaml
objective: RETARGETING
audience:
  - cart_abandoners_30d
  - purchasers_90d
channels:
  - meta
  - google
```

## 工具发现

本业务 Skill 不维护固定 Tool 名称。运行时会根据当前已注册的渠道
Capability、广告类型目录和 Tool Schema 动态选择 Shopping、PMax、Catalog、
Campaign 下级资源及报表能力；未达到完整 dry-run 的类型必须在计划中标明缺口。

## 注意

- 禁止使用 TikTok/DV360 渠道
- 预算低于 ¥100 将被拒绝
- 建议先测试 Google Shopping，再扩展 Meta
