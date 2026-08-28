---
skill:
  name: cross-channel-campaign-manager
  version: "1.0"
  description: "跨渠道 Campaign 管理器 - 统一管理 Google/Meta/TikTok/DV360 多平台投放"
  platform: cross-channel
  author: "Ryan"
  expertise_level: "expert"
  last_updated: "2026-08-24"

---

# 跨渠道 Campaign 管理 Skill

> 实现边界：本文件描述跨渠道业务流程、统一口径和安全 SOP，不是可执行 Tool 注册表。当前 Runtime 通过已注册的平台 Tool 完成查询，并在统一聚合器中处理 comparison、洞察、预算建议和 CSV 导出；缺失指标、多币种及离线数据会明确标记，不会用 mock 数据冒充线上数据。需要稳定多步顺序时，使用同目录的 `workflow.yaml` 声明依赖和映射；普通自然语言流程不需要结构化 workflow。

## 概述

跨渠道 Campaign 管理 Expert Skill，提供：
- 多平台 Campaign 统一视图
- 跨平台预算智能分配
- 性能对比分析
- 批量操作管理
- 统一报表汇总

## 能力意图与流程契约（不是 Tool 注册）

### 1. Campaign 总览

#### cross_channel_get_campaign_overview
- **描述**: 获取所有平台 Campaign 总览
- **参数**:
  - date_range: 日期范围
  - platforms: 平台列表 (可选，默认全部)
  - metrics: 需要显示的指标
- **返回**:
  ```json
  {
    "total_campaigns": 15,
    "total_spend": 50000,
    "total_impressions": 10000000,
    "platforms": {
      "meta": {"campaigns": 5, "spend": 20000, "impressions": 4000000},
      "tiktok": {"campaigns": 4, "spend": 15000, "impressions": 3000000},
      "google": {"campaigns": 4, "spend": 10000, "impressions": 2000000},
      "dv360": {"campaigns": 2, "spend": 5000, "impressions": 1000000}
    }
  }
  ```

#### cross_channel_get_platform_comparison
- **描述**: 各平台性能对比
- **参数**:
  - platforms: 平台列表
  - metrics: ["impressions", "clicks", "spend", "conversions", "ctr", "cpc", "cpm", "cvr"]

### 2. 预算分配

#### cross_channel_optimize_budget
- **描述**: 智能跨平台预算分配
- **参数**:
  - total_budget: 总预算
  - optimization_goal: 优化目标 (MAXIMIZE_ROAS/MINIMIZE_CPA/MAXIMIZE_CONVERSIONS)
  - constraints: 各平台预算上限/下限
- **返回**:
  ```json
  {
    "allocations": [
      {"platform": "meta", "budget": 25000, "expected_roi": 3.5},
      {"platform": "tiktok", "budget": 20000, "expected_roi": 2.8},
      {"platform": "google", "budget": 15000, "expected_roi": 4.2}
    ],
    "total_expected_roi": 3.4
  }
  ```

#### cross_channel_allocate_budget
- **描述**: 按比例分配预算
- **参数**:
  - total_budget: 总预算
  - ratios: 各平台分配比例 {"meta": 0.4, "tiktok": 0.3, "google": 0.3}

### 3. 批量操作

#### cross_channel_batch_pause
- **描述**: 批量暂停多平台 Campaign
- **参数**:
  - platform_campaigns: {"meta": ["id1", "id2"], "tiktok": ["id3"]}
  - reason: 暂停原因

#### cross_channel_batch_resume
- **描述**: 批量恢复多平台 Campaign

#### cross_channel_batch_update_budget
- **描述**: 批量更新各平台预算
- **参数**:
  - updates: [{"platform": "meta", "campaign_id": "xxx", "budget": 500}]

### 4. 统一报表

#### cross_channel_get_unified_report
- **描述**: 获取跨平台统一报表
- **参数**:
  - date_range: 日期范围
  - metrics: 需要展示的指标
  - breakdown_by: 拆分维度 ("platform" / "campaign" / "day")

#### cross_channel_export_report
- **描述**: 导出跨平台报表
- **参数**:
  - date_range: 日期范围
  - format: "csv" / "xlsx"

### 5. 性能诊断

#### cross_channel_get_performance_insights
- **描述**: 跨平台性能洞察
- **参数**:
  - date_range: 日期范围
  - threshold: 异常阈值

#### cross_channel_detect_anomalies
- **描述**: 检测投放异常
- **参数**:
  - date_range: 日期范围
  - metrics: ["cpm", "ctr", "cvr", "cpc"]

### 6. 渠道推荐

#### cross_channel_get_channel_recommendations
- **描述**: 获取渠道投放建议
- **参数**:
  - industry: 行业
  - objective: 投放目标
  - budget: 预算范围

## 专家知识 (Expert Knowledge)

### 跨渠道投放策略
详见 [expert/multi_channel_strategy.md](expert/multi_channel_strategy.md)

### 预算分配算法
详见 [expert/budget_allocation.md](expert/budget_allocation.md)

### 渠道协同效应
详见 [expert/channel_synergy.md](expert/channel_synergy.md)

## 常见场景

### 场景 1: 新品上市多平台投放
```yaml
objective: MAXIMIZE_REACH
budget: 100000
channels:
  meta:
    allocation: 0.4
    focus: "brand_awareness"
  tiktok:
    allocation: 0.3
    focus: "viral_content"
  google:
    allocation: 0.2
    focus: "search_capture"
  dv360:
    allocation: 0.1
    focus: "premium_inventory"
```

### 场景 2: 双11大促投放
```yaml
objective: MAXIMIZE_ROAS
budget: 500000
strategy: "aggressive_scaling"
channels:
  meta:
    budget_boost: 1.5
    targeting: "lookalike"
  tiktok:
    budget_boost: 2.0
    creative: "spark_ads"
  google:
    budget_boost: 1.2
    bidding: "target_roas"
```

### 场景 3: 预算优化调整
```yaml
action: "optimize_budget"
current_spend:
  meta: 30000
  tiktok: 20000
  google: 15000
optimization_goal: "minimize_cpa"
constraints:
  meta: {"min": 20000, "max": 40000}
  tiktok: {"min": 15000, "max": 30000}
  google: {"min": 10000, "max": 20000}
```

## 流程能力清单

| 能力意图 | 描述 | 风险等级 |
|--------|------|----------|
| cross_channel_get_campaign_overview | 获取 Campaign 总览 | LOW |
| cross_channel_get_platform_comparison | 平台性能对比 | LOW |
| cross_channel_optimize_budget | 智能预算分配 | MEDIUM |
| cross_channel_allocate_budget | 按比例分配预算 | MEDIUM |
| cross_channel_batch_pause | 批量暂停 Campaign | MEDIUM |
| cross_channel_batch_resume | 批量恢复 Campaign | LOW |
| cross_channel_batch_update_budget | 批量更新预算 | MEDIUM |
| cross_channel_get_unified_report | 获取统一报表 | LOW |
| cross_channel_export_report | 导出报表 | LOW |
| cross_channel_get_performance_insights | 性能洞察 | LOW |
| cross_channel_detect_anomalies | 检测异常 | LOW |
| cross_channel_get_channel_recommendations | 渠道推荐 | LOW |
