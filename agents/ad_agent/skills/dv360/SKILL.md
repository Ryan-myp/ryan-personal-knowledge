---
skill:
  name: dv360-api
  version: "2.0"
  description: "DV360 API 专家 Skill - 支持 Display & Video 360 程序化广告投放管理"
  platform: dv360
  author: "Ryan"
  expertise_level: "expert"
  last_updated: "2026-08-24"

---

# DV360 API 专家 Skill

## 概述

DV360 API 专家级 Skill，支持：
- Flight/Line Item/Creative 全层级管理
- 程序化保证 (PG) 投放
- 程序化私有市场 (PMP)
- Open Auction 投放
- 自定义定向
- 创意素材管理

## 专家工具 (Tools)

### 1. Flight 管理

#### dv360_create_flight
- **描述**: 创建 Flight（广告航班）
- **参数**:
  - flight_name: Flight 名称
  - advertiser_id: 广告主 ID
  - start_date: 开始日期
  - end_date: 结束日期
  - delivery_type: 投放类型 (PMP/OPEN_AUCTION)
- **专家提示**:
  - PMP 适合私有市场采购
  - OPEN_AUCTION 适合公开市场竞价

#### dv360_update_flight
- **描述**: 更新 Flight

#### dv360_pause_flight
- **描述**: 暂停 Flight

#### dv360_resume_flight
- **描述**: 恢复 Flight

### 2. Line Item 管理

#### dv360_create_line_item
- **描述**: 创建 Line Item（插入订单行）
- **参数**:
  - flight_id: Flight ID
  - line_item_name: Line Item 名称
  - type: 类型 (GUARANTEED/NON_GUARANTEED)
  - bid_type: 竞价类型
  - budget: 预算
  - targeting: 定向参数
- **专家提示**:
  - GUARANTEED 适合保量采购
  - NON_GUARANTEED 适合动态竞价

#### dv360_update_line_item
- **描述**: 更新 Line Item

#### dv360_pause_line_item
- **描述**: 暂停 Line Item

#### dv360_resume_line_item
- **描述**: 恢复 Line Item

### 3. Creative 管理

#### dv360_upload_creative
- **描述**: 上传创意素材
- **参数**:
  - line_item_id: Line Item ID
  - creative_type: 创意类型 (DISPLAY/VIDEO/AUDIO)
  - creative_file: 文件路径
  - dimensions: 尺寸

#### dv360_create_display_creative
- **描述**: 创建展示广告创意

#### dv360_create_video_creative
- **描述**: 创建视频广告创意

### 4. 定向管理

#### dv360_set_targeting
- **描述**: 设置定向参数
- **参数**:
  - line_item_id: Line Item ID
  - geo_targeting: 地理定向
  - demographic_targeting: 人口统计定向
  - interest_targeting: 兴趣定向

#### dv360_get_targeting_suggestions
- **描述**: 获取定向建议

### 5. 出价策略

#### dv360_optimize_bidding
- **描述**: 智能出价优化
- **参数**:
  - line_item_id: Line Item ID
  - strategy: 出价策略
  - target_cpm: 目标 CPM

#### dv360_get_bid_recommendations
- **描述**: 获取出价推荐

### 6. 报表分析

#### dv360_get_flight_report
- **描述**: 获取 Flight 报表
- **参数**:
  - flight_id: Flight ID
  - date_range: 日期范围

#### dv360_get_line_item_report
- **描述**: 获取 Line Item 报表

#### dv360_get_creative_report
- **描述**: 获取创意报表

### 7. 广告位管理

#### dv360_list_inventory_sources
- **描述**: 列出库存源
- **参数**:
  - source_type: 来源类型

#### dv360_add_inventory_source
- **描述**: 添加库存源

## 专家知识 (Expert Knowledge)

### 投放策略指南
详见 [expert/delivery_strategies.md](expert/delivery_strategies.md)

### PMP 采购指南
详见 [expert/pmp_guide.md](expert/pmp_guide.md)

### 创意素材指南
详见 [expert/creative_guide.md](expert/creative_guide.md)

## 常见场景

### 场景 1: 品牌曝光 (PMP)
```yaml
flight_type: PMP
line_item_type: GUARANTEED
budget: 50000
targeting:
  inventory_sources: ["premium_publisher_1", "premium_publisher_2"]
  demographics:
    age_range: "18-45"
    gender: "ALL"
```

### 场景 2: 效果投放 (Open Auction)
```yaml
flight_type: OPEN_AUCTION
line_item_type: NON_GUARANTEED
bid_type: CPV
targeting:
  interests: ["Automotive", "Technology"]
  demographics:
    age_range: "25-54"
```

## 工具列表

| 工具名 | 描述 | 风险等级 |
|--------|------|----------|
| dv360_create_flight | 创建 Flight | MEDIUM |
| dv360_update_flight | 更新 Flight | LOW |
| dv360_pause_flight | 暂停 Flight | LOW |
| dv360_resume_flight | 恢复 Flight | LOW |
| dv360_create_line_item | 创建 Line Item | MEDIUM |
| dv360_update_line_item | 更新 Line Item | LOW |
| dv360_pause_line_item | 暂停 Line Item | LOW |
| dv360_resume_line_item | 恢复 Line Item | LOW |
| dv360_upload_creative | 上传创意素材 | MEDIUM |
| dv360_set_targeting | 设置定向 | MEDIUM |
| dv360_optimize_bidding | 智能出价优化 | MEDIUM |
| dv360_get_bid_recommendations | 获取出价推荐 | LOW |
| dv360_get_flight_report | 获取 Flight 报表 | LOW |
| dv360_get_line_item_report | 获取 Line Item 报表 | LOW |
| dv360_get_creative_report | 获取创意报表 | LOW |
| dv360_list_inventory_sources | 列出库存源 | LOW |
| dv360_add_inventory_source | 添加库存源 | MEDIUM |
