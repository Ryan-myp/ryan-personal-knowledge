---
skill:
  name: tiktok-ads-api
  version: "2.0"
  description: "TikTok Ads API 专家 Skill - 支持 Campaign/AdGroup/Ad 全层级管理、Spark Ads、Pixel 追踪、报表分析"
  platform: tiktok
  author: "Ryan"
  expertise_level: "expert"
  last_updated: "2026-08-24"

---

# TikTok Ads API 专家 Skill

## 概述

TikTok Ads API 专家级 Skill，支持：
- Campaign/AdGroup/Ad 全层级管理
- Spark Ads（原生内容投放）
- Pixel 追踪事件配置
- 智能出价策略
- 实时报表分析

## 专家工具 (Tools)

### 1. Campaign 管理

#### tiktok_create_campaign
- **描述**: 创建广告系列
- **参数**:
  - campaign_name: 广告系列名称
  - campaign_type: 投放类型 (SALE/LEAD/GAME_INSTALL/APPLINK)
  - budget: 每日预算
  - promotion_type: 推广类型
- **专家提示**:
  - SALE 适合电商转化
  - LEAD 适合线索收集
  - APPLINK 适合 App 安装

#### tiktok_update_campaign
- **描述**: 更新广告系列

#### tiktok_pause_campaign
- **描述**: 暂停广告系列

#### tiktok_resume_campaign
- **描述**: 恢复广告系列

### 2. Ad Group 管理

#### tiktok_create_ad_group
- **描述**: 创建广告组
- **参数**:
  - campaign_id: 广告系列 ID
  - ad_group_name: 广告组名称
  - bid_type: 竞价类型 (AUTO/OPTIMIZE_GOAL)
  - targeting: 定向参数
  - optimization_event: 优化事件
- **专家提示**:
  - 建议每个 AdGroup 预算不低于 $50
  - 测试期使用 AUTO 竞价积累经验

#### tiktok_update_ad_group
- **描述**: 更新广告组

#### tiktok_pause_ad_group
- **描述**: 暂停广告组

### 3. Ad 管理

#### tiktok_create_ad
- **描述**: 创建广告创意
- **参数**:
  - ad_group_id: 广告组 ID
  - ad_name: 广告名称
  - promotion_type: 推广类型
  - tracking_url: 追踪链接

#### tiktok_create_spark_ad
- **描述**: 创建 Spark Ads（原生内容投放）
- **参数**:
  - ad_group_id: 广告组 ID
  - post_id: TikTok 帖子 ID
  - advertiser_id: 广告主 ID

### 4. 定向优化

#### tiktok_get_audience_suggestions
- **描述**: 获取受众推荐
- **参数**:
  - category: 行业分类
  - target_audience: 目标受众描述

#### tiktok_create_custom_audience
- **描述**: 创建自定义受众

#### tiktok_create_lookalike_audience
- **描述**: 创建相似受众

### 5. 智能出价

#### tiktok_optimize_bidding
- **描述**: 智能出价优化
- **参数**:
  - campaign_id: 广告系列 ID
  - strategy: 出价策略 (LOWEST_COST/TARGET_COST)
  - target_cost: 目标成本

#### tiktok_get_bid_recommendations
- **描述**: 获取出价推荐

### 6. Pixel 追踪

#### tiktok_create_pixel
- **描述**: 创建 Pixel
- **参数**:
  - pixel_name: Pixel 名称
  - pixel_code: Pixel 代码

#### tiktok_track_conversion
- **描述**: 追踪转化事件
- **参数**:
  - pixel_id: Pixel ID
  - event_type: 事件类型
  - event_value: 事件价值

### 7. 报表分析

#### tiktok_get_campaign_report
- **描述**: 获取 Campaign 报表
- **参数**:
  - campaign_id: 广告系列 ID
  - date_range: 日期范围
  - columns: 报表字段

#### tiktok_get_ad_group_report
- **描述**: 获取广告组报表

## 专家知识 (Expert Knowledge)

### 出价策略指南
详见 [expert/bidding_strategies.md](expert/bidding_strategies.md)

### 定向优化指南
详见 [expert/targeting_guide.md](expert/targeting_guide.md)

### Spark Ads 最佳实践
详见 [expert/spark_ads_guide.md](expert/spark_ads_guide.md)

## 常见场景

### 场景 1: 电商带货
```yaml
campaign_type: SALE
budget: 100
optimization_event: PURCHASE
targeting:
  age_min: 18
  age_max: 35
  interests: ["Shopping", "Fashion"]
```

### 场景 2: App 安装
```yaml
campaign_type: GAME_INSTALL
budget: 200
optimization_event: INSTALL
targeting:
  interests: ["Mobile Games", "Casual Games"]
```

### 场景 3: 线索收集
```yaml
campaign_type: LEAD
budget: 80
optimization_event: LEAD_FORM_SUBMIT
targeting:
  age_min: 25
  age_max: 45
  interests: ["Finance", "Insurance"]
```

## 专家知识 (Expert Knowledge)

### 广告类型指南
详见 [expert/ad_types.md](expert/ad_types.md)

## 专家知识 (Expert Knowledge)

### 广告类型指南
详见 [expert/ad_types.md](expert/ad_types.md)

## 工具列表

| 工具名 | 描述 | 风险等级 |
|--------|------|----------|
| tiktok_create_campaign | 创建广告系列 | MEDIUM |
| tiktok_update_campaign | 更新广告系列 | LOW |
| tiktok_pause_campaign | 暂停广告系列 | LOW |
| tiktok_resume_campaign | 恢复广告系列 | LOW |
| tiktok_create_ad_group | 创建广告组 | MEDIUM |
| tiktok_update_ad_group | 更新广告组 | LOW |
| tiktok_pause_ad_group | 暂停广告组 | LOW |
| tiktok_create_ad | 创建广告 | MEDIUM |
| tiktok_create_spark_ad | 创建 Spark Ads | MEDIUM |
| tiktok_optimize_bidding | 智能出价优化 | MEDIUM |
| tiktok_get_bid_recommendations | 获取出价推荐 | LOW |
| tiktok_get_campaign_report | 获取 Campaign 报表 | LOW |
| tiktok_get_ad_group_report | 获取广告组报表 | LOW |
| tiktok_create_pixel | 创建 Pixel | LOW |
| tiktok_track_conversion | 追踪转化事件 | LOW |
| tiktok_create_custom_audience | 创建自定义受众 | MEDIUM |
| tiktok_create_lookalike_audience | 创建相似受众 | MEDIUM |
