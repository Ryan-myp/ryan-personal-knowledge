---
skill:
  name: meta-marketing-api
  version: "2.0"
  description: "Meta Marketing API 专家 Skill - 支持 Campaign/AdSet/Ad 全层级管理、智能出价、定向优化、报表分析"
  platform: meta
  author: "Ryan"
  expertise_level: "expert"
  last_updated: "2026-08-24"

---

# Meta Marketing API 专家 Skill

## 概述

Meta Marketing API 专家级 Skill，支持：
- Campaign/AdSet/Ad 全层级管理
- 智能出价策略优化
- 精准定向设置
- 创意素材管理
- 实时报表分析

## 专家工具 (Tools)

### 1. Campaign 管理

#### meta_create_campaign
- **描述**: 创建广告系列（Campaign）
- **参数**:
  - campaign_name: 广告系列名称
  - objective: 投放目标 (OUTCOME_TRAFFIC/CONVERSIONS/LEADS/SALES/ENGAGEMENT)
  - budget: 每日预算
  - special_ad_categories: 特殊广告类别
- **专家提示**: 
  - 电商类选择 OUTCOME_SALES
  - 线索收集选择 OUTCOME_LEADS
  - 品牌曝光选择 OUTCOME_REACH

#### meta_update_campaign
- **描述**: 更新广告系列状态/预算
- **参数**: campaign_id, status, budget

#### meta_pause_campaign
- **描述**: 暂停广告系列

#### meta_resume_campaign
- **描述**: 恢复广告系列

### 2. Ad Set 管理

#### meta_create_adset
- **描述**: 创建广告组（Ad Set）
- **参数**:
  - campaign_id: 广告系列 ID
  - optimization_goal: 优化目标 (LINK_CLICKS/CONVERSIONS/REACH/IMPRESSIONS)
  - targeting: 定向参数
  - bid_amount: 出价金额
  - daily_budget: 每日预算
- **专家提示**:
  - 新 Campaign 建议先设较低的 bid_amount 测试
  - 使用 automatic_auction 可让 Meta 自动竞价

#### meta_update_adset
- **描述**: 更新广告组参数

#### meta_pause_adset
- **描述**: 暂停广告组

### 3. Ad 管理

#### meta_create_ad
- **描述**: 创建广告创意（Ad）
- **参数**:
  - adset_id: 广告组 ID
  - creative_id: 创意素材 ID
  - body: 广告文案
  - title: 广告标题
  - url_tags: UTM 参数

#### meta_create_carousel_ad
- **描述**: 创建轮播广告

### 4. 定向优化

#### meta_get_audience_insights
- **描述**: 获取受众洞察数据
- **参数**: audience_id

#### meta_create_custom_audience
- **描述**: 创建自定义受众

#### meta_create_lookalike_audience
- **描述**: 创建相似受众

### 5. 智能出价

#### meta_optimize_bidding
- **描述**: 智能出价优化建议
- **参数**:
  - campaign_id: 广告系列 ID
  - strategy: 出价策略 (LOWEST_COST/TARGET_COST/CAP)
  - target_cost: 目标成本（可选）
- **专家提示**:
  - 新广告组建议先用 LOWEST_COST 积累数据
  - 数据充足后可切换到 TARGET_COST 控制成本

#### meta_get_bid_recommendations
- **描述**: 获取出价推荐

### 6. 报表分析

#### meta_get_campaign_report
- **描述**: 获取 Campaign 报表
- **参数**:
  - campaign_id: 广告系列 ID
  - date_range: 日期范围
  - breakdowns: 维度拆分

#### meta_get_creative_report
- **描述**: 获取创意报表

### 7. 预算优化

#### meta_allocate_budget
- **描述**: 跨 Campaign 预算智能分配
- **参数**:
  - campaign_ids: 广告系列列表
  - total_budget: 总预算
  - optimization_goal: 优化目标

## 专家知识 (Expert Knowledge)

### 出价策略指南
详见 [expert/bidding_strategies.md](expert/bidding_strategies.md)

### 定向优化指南
详见 [expert/targeting_guide.md](expert/targeting_guide.md)

### 创意素材最佳实践
详见 [expert/creative_best_practices.md](expert/creative_best_practices.md)

## 常见场景

### 场景 1: 电商销售转化
```yaml
objective: OUTCOME_SALES
optimization_goal: CONVERSIONS
bidding_strategy: TARGET_COST
target_cost: 50  # 目标 CPA
audience: 
  - custom_audience: 网站访客 30 天
  - lookalike: 1% 相似受众
```

### 场景 2: App 安装
```yaml
objective: OUTCOME_APP_INSTALLS
optimization_goal: INSTANTS
bidding_strategy: LOWEST_COST
targeting:
  age_min: 18
  age_max: 35
  interests: ["Mobile Apps", "Gaming"]
```

### 场景 3: 线索收集
```yaml
objective: OUTCOME_LEADS
optimization_goal: LEADS
bidding_strategy: TARGET_COST
lead_form:
  form_type: immediate
  questions: ["name", "phone", "email"]
```

## 专家知识 (Expert Knowledge)

### 广告类型指南
详见 [expert/ad_types.md](expert/ad_types.md)

### 定向优化指南
详见 [expert/targeting.md](expert/targeting.md)

## 专家知识 (Expert Knowledge)

### 广告类型指南
详见 [expert/ad_types.md](expert/ad_types.md)

### 定向优化指南
详见 [expert/targeting.md](expert/targeting.md)

## 工具列表

| 工具名 | 描述 | 风险等级 |
|--------|------|----------|
| meta_create_campaign | 创建广告系列 | MEDIUM |
| meta_update_campaign | 更新广告系列 | LOW |
| meta_pause_campaign | 暂停广告系列 | LOW |
| meta_resume_campaign | 恢复广告系列 | LOW |
| meta_create_adset | 创建广告组 | MEDIUM |
| meta_update_adset | 更新广告组 | LOW |
| meta_pause_adset | 暂停广告组 | LOW |
| meta_create_ad | 创建广告 | MEDIUM |
| meta_create_carousel_ad | 创建轮播广告 | MEDIUM |
| meta_optimize_bidding | 智能出价优化 | MEDIUM |
| meta_get_bid_recommendations | 获取出价推荐 | LOW |
| meta_get_campaign_report | 获取 Campaign 报表 | LOW |
| meta_get_creative_report | 获取创意报表 | LOW |
| meta_allocate_budget | 预算智能分配 | MEDIUM |
| meta_create_custom_audience | 创建自定义受众 | MEDIUM |
| meta_create_lookalike_audience | 创建相似受众 | MEDIUM |
