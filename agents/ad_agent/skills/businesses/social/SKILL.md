---
business:
  name: social
  version: "1.0.0"
  description: "社交媒体广告投放 Skill - 专注于品牌曝光、用户互动"
  allowed_channels:
    - meta
    - google
    - tiktok
  disallowed_channels:
    - dv360
  allowed_campaign_types:
    - BRAND_AWARENESS
    - ENGAGEMENT
    - TRAFFIC
    - VIDEO_VIEW
  business_rules:
    min_budget: 200
    max_budget: 200000
    focus_metrics:
      - CPM
      - Reach
      - Engagement
      - Video_View_Rate
    default_objective: "BRAND_AWARENESS"
---

# 社交媒体业务 Skill

## 可用渠道

| 渠道 | 状态 | 说明 |
|------|------|------|
| Meta | ✅ 可用 | Facebook/Instagram 品牌广告 |
| Google | ✅ 可用 | YouTube/Display 品牌广告 |
| TikTok | ✅ 可用 | Spark Ads、品牌挑战赛 |
| DV360 | ❌ 不可用 | 社交业务暂不支持 |

## 业务规则

- **预算范围**: ¥200 - ¥200,000
- **核心指标**: CPM、Reach、Engagement、Video_View_Rate
- **默认目标**: BRAND_AWARENESS（品牌认知）

## 常用场景

### 场景 1: 品牌曝光
```yaml
objective: BRAND_AWARENESS
campaign_types:
  - VIDEO_VIEW    # YouTube 视频广告
  - DISPLAY       # Google Display
channels:
  - google
  - meta
```

### 场景 2: 用户互动
```yaml
objective: ENGAGEMENT
campaign_types:
  - POST_ENGAGEMENT  # Facebook 帖子互动
  - VIDEO_VIEW       # TikTok 视频观看
channels:
  - meta
  - tiktok
```

### 场景 3: 社交裂变
```yaml
objective: VIRAL_CAMPAIGN
campaign_types:
  - SPARK_AD         # TikTok Spark Ads
  - UGC_CAMPAIGN     # 用户生成内容
channels:
  - tiktok
  - meta
```

## 工具发现

本业务 Skill 不维护固定 Tool 名称。运行时会根据当前已注册的渠道
Tool Source、广告类型目录和 Tool Schema 动态选择可用的 Campaign、下级资源、
报表和素材能力；若某个广告类型只有 `declared_only` 或 `partial_dry_run`，
必须在计划中明确提示缺口。

## 注意

- 禁止使用 DV360 渠道
- 预算低于 ¥200 将被拒绝
- 建议先测试 TikTok Spark Ads，再扩展 Meta/Google
