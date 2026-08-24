---
skill:
  name: google-ads-api
  version: "2.0"
  description: "Google Ads API 专家 Skill - 支持 Campaign/AdGroup/Ad 全层级管理、PMax、Shopping、搜索广告"
  platform: google
  author: "Ryan"
  expertise_level: "expert"
  last_updated: "2026-08-24"

---

# Google Ads API 专家 Skill

## 概述

Google Ads API 专家级 Skill，支持：
- Campaign/AdGroup/Ad 全层级管理
- Performance Max (PMax) 智能投放
- Shopping 商品广告
- Search/Display/Video/Discovery 全类型广告
- 智能出价策略
- GA4 数据整合

## 专家工具 (Tools)

### 1. Campaign 管理

#### google_create_campaign
- **描述**: 创建广告系列
- **参数**:
  - campaign_name: 广告系列名称
  - advertising_channel_type: 渠道类型 (SEARCH/SHOPPING/VIDEO/DISPLAY/APP/MAX)
  - bidding_strategy: 出价策略
  - daily_budget: 每日预算
- **专家提示**:
  - SEARCH 适合关键词定向
  - SHOPPING 适合商品推广
  - MAX 适合全渠道智能投放

#### google_update_campaign
- **描述**: 更新广告系列

#### google_pause_campaign
- **描述**: 暂停广告系列

#### google_resume_campaign
- **描述**: 恢复广告系列

### 2. Ad Group 管理

#### google_create_ad_group
- **描述**: 创建广告组
- **参数**:
  - campaign_id: 广告系列 ID
  - ad_group_name: 广告组名称
  - cpc_bid: CPC 出价
  - status: 状态

#### google_update_ad_group
- **描述**: 更新广告组

### 3. Ad 管理

#### google_create_search_ad
- **描述**: 创建搜索广告
- **参数**:
  - ad_group_id: 广告组 ID
  - headline: 标题
  - description: 描述
  - final_urls: 最终 URL

#### google_create_shopping_ad
- **描述**: 创建商品广告

#### google_create_video_ad
- **描述**: 创建视频广告

#### google_create_pmax_asset_group
- **描述**: 创建 PMax Asset Group
- **参数**:
  - campaign_id: 广告系列 ID
  - asset_group_name: 资产组名称
  - headlines: 标题列表
  - descriptions: 描述列表
  - images: 图片 URL 列表
  - videos: 视频 URL 列表
  - final_url: 最终 URL

### 4. 关键词管理

#### google_add_keywords
- **描述**: 添加关键词
- **参数**:
  - ad_group_id: 广告组 ID
  - keywords: 关键词列表
  - match_type: 匹配类型 (BROAD/PHRASE/EXACT)

#### google_remove_keywords
- **描述**: 移除关键词

#### google_get_keyword_suggestions
- **描述**: 获取关键词建议

### 5. 智能出价

#### google_optimize_bidding
- **描述**: 智能出价优化
- **参数**:
  - campaign_id: 广告系列 ID
  - strategy: 出价策略 (TARGET_CPA/TARGET_ROAS/MAXIMIZE_CONVERSIONS)
  - target_cpa: 目标 CPA
  - target_roas: 目标 ROAS

#### google_get_bid_recommendations
- **描述**: 获取出价推荐

### 6. 报表分析

#### google_get_campaign_report
- **描述**: 获取 Campaign 报表
- **参数**:
  - campaign_id: 广告系列 ID
  - date_range: 日期范围
  - columns: 报表字段
  - gaql: GAQL 查询语句

#### google_get_keyword_report
- **描述**: 获取关键词报表

#### google_get_audience_report
- **描述**: 获取受众报表

### 7. PMax 专用

#### google_get_pmax_asset_performance
- **描述**: 获取 PMax 资产表现
- **参数**:
  - campaign_id: 广告系列 ID
  - asset_group_id: 资产组 ID

#### google_optimize_pmax_assets
- **描述**: PMax 资产优化建议

## 专家知识 (Expert Knowledge)

### 出价策略指南
详见 [expert/bidding_strategies.md](expert/bidding_strategies.md)

### PMax 最佳实践
详见 [expert/pmax_guide.md](expert/pmax_guide.md)

### 关键词策略指南
详见 [expert/keyword_strategies.md](expert/keyword_strategies.md)

## 常见场景

### 场景 1: 搜索广告
```yaml
campaign_type: SEARCH
bidding_strategy: MAXIMIZE_CONVERSIONS
daily_budget: 200
ad_groups:
  - keywords: ["running shoes", "nike shoes"]
    match_type: EXACT
```

### 场景 2: Shopping 广告
```yaml
campaign_type: SHOPPING
bidding_strategy: TARGET_ROAS
target_roas: 400
product_group:
  type: UNIT
  children:
    - type: ALL
      bid_modifier: 1.2
```

### 场景 3: PMax 智能投放
```yaml
campaign_type: MAX
bidding_strategy: TARGET_ROAS
target_roas: 350
asset_groups:
  - name: 夏季促销
    headlines: ["夏季新品", "限时优惠"]
    images: ["https://..."]
    videos: ["https://..."]
```

## 专家知识 (Expert Knowledge)

### 广告类型指南
详见 [expert/ad_types.md](expert/ad_types.md)

### 出价策略指南
详见 [expert/bidding.md](expert/bidding.md)

### 定向优化指南
详见 [expert/targeting.md](expert/targeting.md)

## 专家知识 (Expert Knowledge)

### 广告类型指南
详见 [expert/ad_types.md](expert/ad_types.md)

### 出价策略指南
详见 [expert/bidding.md](expert/bidding.md)

### 定向优化指南
详见 [expert/targeting.md](expert/targeting.md)

## 工具列表

| 工具名 | 描述 | 风险等级 |
|--------|------|----------|
| google_create_campaign | 创建广告系列 | MEDIUM |
| google_update_campaign | 更新广告系列 | LOW |
| google_pause_campaign | 暂停广告系列 | LOW |
| google_resume_campaign | 恢复广告系列 | LOW |
| google_create_ad_group | 创建广告组 | MEDIUM |
| google_update_ad_group | 更新广告组 | LOW |
| google_create_search_ad | 创建搜索广告 | MEDIUM |
| google_create_shopping_ad | 创建商品广告 | MEDIUM |
| google_create_video_ad | 创建视频广告 | MEDIUM |
| google_create_pmax_asset_group | 创建 PMax 资产组 | MEDIUM |
| google_add_keywords | 添加关键词 | MEDIUM |
| google_remove_keywords | 移除关键词 | LOW |
| google_get_keyword_suggestions | 获取关键词建议 | LOW |
| google_optimize_bidding | 智能出价优化 | MEDIUM |
| google_get_bid_recommendations | 获取出价推荐 | LOW |
| google_get_campaign_report | 获取 Campaign 报表 | LOW |
| google_get_keyword_report | 获取关键词报表 | LOW |
| google_get_pmax_asset_performance | 获取 PMax 资产表现 | LOW |
| google_optimize_pmax_assets | PMax 资产优化建议 | LOW |
