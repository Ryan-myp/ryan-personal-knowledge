# 广告平台统一数据模型设计

> **领域**: 广告投放 / 跨平台数据架构
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: data-model, cross-platform, google-ads, meta-ads, tiktok-ads, dv360, etl
> **更新时间**: 2026-08-14
> **类型**: deep-dive/data-architecture

---

## 一、为什么需要统一数据模型？

### 1.1 问题陈述

```
现状：四个平台各自为政

Google Ads:
├── 维度：Campaign, AdGroup, Keyword, Ad, Asset
├── 指标：Impressions, Clicks, Cost, Conversions, ConversionValue
├── 时间粒度：Hourly / Daily
└── API 格式：Protobuf / JSON

Meta Ads:
├── 维度：Campaign, AdSet, Ad, Creative, Insigh
├── 指标：Impressions, Clicks, Spend, Results, ResultRate
├── 时间粒度：Daily
└── API 格式：REST JSON

TikTok Ads:
├── 维度：Campaign, AdGroup, Ad, Creative, Audience
├── 指标：Impressions, Clicks, Cost, Conversions, Roas
├── 时间粒度：Daily
└── API 格式：REST JSON

DV360:
├── 维度：AdGroup, Creative, Flight, LineItem, IO
├── 指标：Impressions, Clicks, Cost, Viewability, BrandSafety
├── 时间粒度：Real-time / Daily
└── API 格式：REST JSON
```

**痛点：**
- 每个平台的字段名不同（Cost vs Spend vs Cost）
- 指标单位不统一（有些用分，有些用元）
- 时间格式不一致（UTC vs 本地时区）
- 无法跨平台对比分析
- 难以建立统一的优化决策

### 1.2 统一模型的价值

```
价值 1: 跨平台对比分析
├── 同一商品在 Google 和 Meta 的 ROAS 对比
├── 同一受众在不同平台的 CPA 对比
└── 同一创意在不同平台的 CTR 对比

价值 2: 统一预算分配
├── 基于统一指标（ROAS/CPA）做跨平台预算调整
├── 实时或近实时的预算再分配
└── 消除平台间的数据延迟差异

价值 3: 跨平台归因
├── 统一用户旅程重建
├── 统一的 Shapley Value 计算
└── 一致的归因结果

价值 4: 自动化决策
├── 统一的 Agent 输入
├── 统一的优化建议输出
└── 自动化的 API 调用
```

---

## 二、核心实体模型

### 2.1 统一实体定义

```protobuf
// 统一广告实体模型 (Protobuf 3)
syntax = "proto3";
package ad_platform.unified;

// ========== 枚举定义 ==========

enum Platform {
  PLATFORM_UNSPECIFIED = 0;
  PLATFORM_GOOGLE = 1;
  PLATFORM_META = 2;
  PLATFORM_TIKTOK = 3;
  PLATFORM_DV360 = 4;
}

enum CampaignStatus {
  STATUS_UNSPECIFIED = 0;
  STATUS_ACTIVE = 1;
  STATUS_PAUSED = 2;
  STATUS_DRAFT = 3;
  STATUS_ENDED = 4;
  STATUS_REMOVED = 5;
}

enum BiddingStrategy {
  BID_STRATEGY_UNSPECIFIED = 0;
  BID_MANUAL_CPC = 1;
  BID_TARGET_CPA = 2;
  BID_TARGET_ROAS = 3;
  BID_MAX_CONVERSIONS = 4;
  BID_TARGET_CPIM = 5;
  BID_TARGET_CPV = 6;
  BID_AUTOMATIC = 7;
  BID_ADVANTAGE_PLUS = 8;
}

enum CampaignType {
  CAMPAIGN_TYPE_UNSPECIFIED = 0;
  CAMPAIGN_SEARCH = 1;
  CAMPAIGN_DISPLAY = 2;
  CAMPAIGN_VIDEO = 3;
  CAMPAIGN_SHOPPING = 4;
  CAMPAIGN_APP = 5;
  CAMPAIGN_BRAND = 6;
  CAMPAIGN_LEAD = 7;
  CAMPAIGN_TRAFFIC = 8;
  CAMPAIGN_LOCAL = 9;
}

// ========== 核心实体 ==========

// 统一广告账户
message UnifiedAccount {
  string account_id = 1;           // 内部唯一 ID
  Platform platform = 2;           // 平台
  string platform_account_id = 3;  // 平台原始 ID
  string account_name = 4;         // 账户名称
  string currency = 5;             // ISO 4217 货币代码
  string timezone = 6;             // IANA timezone
  string country_code = 7;         // ISO 3166
  string industry = 8;             // 行业类别
  string contact_email = 9;        // 联系人
  repeated string tags = 10;       // 标签
  string created_at = 11;          // 创建时间 (RFC3339)
  string updated_at = 12;          // 更新时间 (RFC3339)
}

// 统一广告系列
message UnifiedCampaign {
  string campaign_id = 1;          // 内部唯一 ID
  string platform_campaign_id = 2; // 平台原始 ID
  UnifiedAccount account = 3;      // 所属账户
  string name = 4;                 // 系列名称
  CampaignType type = 5;           // 系列类型
  CampaignStatus status = 6;       // 状态
  BiddingStrategy bidding_strategy = 7; // 出价策略
  
  // 预算
  double daily_budget = 8;         // 日预算 (平台货币单位)
  double lifetime_budget = 9;      // 总预算
  string budget_currency = 10;     // 预算货币
  
  // 排期
  string start_date = 11;          // 开始日期 (YYYY-MM-DD)
  string end_date = 12;            // 结束日期
  repeated TimeWindow schedule = 13; // 投放时段
  
  // 定向
  repeated string geo_targets = 14;       // 地理定向 (ISO 3166)
  repeated string age_ranges = 15;        // 年龄范围
  repeated string genders = 16;           // 性别
  repeated string interest_segments = 17; // 兴趣细分
  repeated string custom_audiences = 18;  // 自定义受众
  
  // 元数据
  repeated string tags = 19;
  string created_at = 20;
  string updated_at = 21;
}

// 统一指标（时间序列）
message UnifiedMetrics {
  string metric_id = 1;
  string campaign_id = 2;              // 关联 campaign
  string date = 3;                     // YYYY-MM-DD
  Platform platform = 4;
  
  // 曝光
  int64 impressions = 5;
  double cpm = 6;                      // Cost per thousand impressions
  
  // 点击
  int64 clicks = 7;
  double ctr = 8;                      // Click-through rate
  
  // 花费
  double spend = 9;                    // 已花费金额 (已转换为 USD)
  double spend_local = 10;             // 原始货币花费
  
  // 转化
  int64 conversions = 11;
  double conv_rate = 12;               // Conversion rate
  double cpa = 13;                     // Cost per acquisition
  double roas = 14;                    // Return on ad spend
  
  // 视频相关
  int64 video_views = 15;
  double vtr = 16;                     // Video view rate
  double average_watch_time = 17;      // 平均观看时长(秒)
  
  // 品牌安全
  double viewability_rate = 18;        // 可见率
  int32 brand_safety_score = 19;       // 品牌安全评分 (1-100)
  
  // 元数据
  string created_at = 20;
}

// 统一时间窗口
message TimeWindow {
  string day_of_week = 1;   // MON/TUE/WED/THU/FRI/SAT/SUN
  int32 start_hour = 2;     // 0-23
  int32 end_hour = 3;       // 0-23
}

// 统一用户旅程
message UserJourney {
  string journey_id = 1;     // 用户旅程唯一 ID
  string user_id = 2;        // 匿名化用户 ID
  repeated TouchPoint touches = 3; // 触达序列
  double total_conversions = 4;  // 总转化数
  double total_value = 5;      // 总转化价值 (USD)
  string first_touch_date = 6;  // 首次触达日期
  string last_touch_date = 7;   // 最后触达日期
  int32 touch_count = 8;       // 总触达次数
}

// 单次触达
message TouchPoint {
  Platform platform = 1;
  string touch_id = 2;
  string creative_id = 3;
  string placement = 4;         // 具体位置
  int64 timestamp = 5;          // Unix timestamp
  bool is_view = 6;             // 是否为 view-through
  bool is_click = 7;            // 是否为 click-through
  double attribution_weight = 8; // 归因权重
}
```

### 2.2 字段映射表

```
平台字段 → 统一模型字段映射：

Google Ads:
├── campaign.name → UnifiedCampaign.name
├── campaign.id → UnifiedCampaign.platform_campaign_id
├── campaign.status → UnifiedCampaign.status
├── advertising_channel_type → UnifiedCampaign.type
├── bidding_strategy → UnifiedCampaign.bidding_strategy
├── daily_budget.micros → UnifiedCampaign.daily_budget (÷1,000,000)
├── geo_target_constant → UnifiedCampaign.geo_targets
├── metrics.impressions → UnifiedMetrics.impressions
├── metrics.clicks → UnifiedMetrics.clicks
├── metrics.costMicros → UnifiedMetrics.spend_local (÷1,000,000)
├── metrics.conversions → UnifiedMetrics.conversions
└── metrics.averageCpc → UnifiedMetrics.cpc

Meta Ads:
├── name → UnifiedCampaign.name
├── id → UnifiedCampaign.platform_campaign_id (去除 act_ 前缀)
├── effective_status → UnifiedCampaign.status
├── promotion_type → UnifiedCampaign.type
├── targeting → UnifiedCampaign.geo_targets + interest_segments
├── daily_budget → UnifiedCampaign.daily_budget
├── insights → UnifiedMetrics.*
└── actions → UnifiedMetrics.conversions (按 action_type 过滤)

TikTok Ads:
├── campaign_name → UnifiedCampaign.name
├── campaign_id → UnifiedCampaign.platform_campaign_id
├── campaign_status → UnifiedCampaign.status
├── campaign_ad_type → UnifiedCampaign.type
├── daily_budget → UnifiedCampaign.daily_budget
├── campaign_geo_targeting → UnifiedCampaign.geo_targets
├── campaign_audience_targeting → UnifiedCampaign.interest_segments
├── stats → UnifiedMetrics.*
└── conversion_stats → UnifiedMetrics.conversions

DV360:
├── displayName → UnifiedCampaign.name
├── id → UnifiedCampaign.platform_campaign_id
├── status → UnifiedCampaign.status
├── type → UnifiedCampaign.type
├── flightStartDateMillis → UnifiedCampaign.start_date
├── flightEndDateMillis → UnifiedCampaign.end_date
├── budget → UnifiedCampaign.daily_budget
├── targetedGeoIds → UnifiedCampaign.geo_targets
└── impressionStats → UnifiedMetrics.*
```

---

## 三、ETL 管道设计

### 3.1 管道架构

```
                    ┌──────────────────────────────────────┐
                    │         Google BigQuery               │
                    │     unified_data.staging_*            │
                    └──────────────┬───────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│  Google Ads   │         │   Meta Ads    │         │  TikTok Ads   │
│   Connector   │         │   Connector   │         │   Connector   │
│               │         │               │         │               │
│ • Official    │         │ • Graph API   │         │ • Marketing   │
│   Python SDK  │         │ • Batch       │         │   API         │
│ • 8h 同步     │         │ • 12h 同步    │         │ • 12h 同步    │
└───────┬───────┘         └───────┬───────┘         └───────┬───────┘
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  ▼
                    ┌──────────────────────────┐
                    │    DV360 Connector       │
                    │                          │
                    │ • Display Video API      │
                    │ • 24h 同步               │
                    └────────────┬─────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │   Data Transformation    │
                    │   (dbt / Go pipeline)    │
                    │                          │
                    │ 1. 字段标准化            │
                    │ 2. 货币转换 (USD)        │
                    │ 3. 时区统一 (UTC)        │
                    │ 4. 去重与合并            │
                    │ 5. 质量检查              │
                    └────────────┬─────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │   unified_data.dim_*     │
                    │   unified_data.fact_*    │
                    │   (生产数据层)            │
                    └──────────────────────────┘
```

### 3.2 Go 实现示例

```go
package etl

import (
    "context"
    "time"
    "github.com/googleapis/google-cloud-go/bigquery"
)

// PlatformConnector 平台连接器接口
type PlatformConnector interface {
    GetCampaigns(ctx context.Context, since time.Time) ([]Campaign, error)
    GetMetrics(ctx context.Context, campaignIDs []string, since time.Time) ([]Metrics, error)
    Platform() string
}

// UnifiedPipeline 统一数据管道
type UnifiedPipeline struct {
    connectors []PlatformConnector
    bqClient   *bigquery.Client
    projectID  string
}

// Run 执行 ETL 同步
func (p *UnifiedPipeline) Run(ctx context.Context) error {
    since := time.Now().Add(-24 * time.Hour)
    
    for _, conn := range p.connectors {
        // 1. 获取 Campaigns
        campaigns, err := conn.GetCampaigns(ctx, since)
        if err != nil {
            return fmt.Errorf("failed to get %s campaigns: %w", conn.Platform(), err)
        }
        
        // 2. 标准化并写入 staging
        for _, c := range campaigns {
            unified := p.standardizeCampaign(c, conn.Platform())
            if err := p.writeToStaging(ctx, "campaigns", unified); err != nil {
                return err
            }
        }
        
        // 3. 获取 Metrics
        campaignIDs := extractIDs(campaigns)
        metrics, err := conn.GetMetrics(ctx, campaignIDs, since)
        if err != nil {
            return fmt.Errorf("failed to get %s metrics: %w", conn.Platform(), err)
        }
        
        // 4. 标准化指标
        for _, m := range metrics {
            unified := p.standardizeMetrics(m, conn.Platform())
            if err := p.writeToStaging(ctx, "metrics", unified); err != nil {
                return err
            }
        }
    }
    
    // 5. 运行 dbt 转换
    return p.runTransformations(ctx)
}

// standardizeCurrency 统一货币为 USD
func (p *UnifiedPipeline) standardizeCurrency(amount float64, currency string) float64 {
    rates := map[string]float64{
        "USD": 1.0,
        "EUR": 1.08,
        "GBP": 1.27,
        "CNY": 0.14,
        "JPY": 0.0067,
    }
    rate := rates[currency]
    if rate == 0 {
        rate = 1.0 // 默认 USD
    }
    return amount * rate
}
```

---

## 四、统一查询接口

### 4.1 跨平台查询 DSL

```
跨平台统一查询语言（概念）：

SELECT
  platform,
  campaign_name,
  SUM(spend_usd) as total_spend,
  SUM(conversions) as total_conversions,
  SUM(spend_usd) / NULLIF(SUM(conversions), 0) as blended_cpa,
  SUM(conversion_value_usd) / SUM(spend_usd) as blended_roas
FROM unified_metrics
WHERE date BETWEEN '2025-01-01' AND '2025-01-31'
  AND status = 'ACTIVE'
GROUP BY platform, campaign_name
ORDER BY blended_roas DESC;

结果：
┌────────────┬───────────────────────┬──────────┬─────────────┬──────────┐
│ platform   │ campaign_name         │ spend    │ conversions │ roas     │
├────────────┼───────────────────────┼──────────┼─────────────┼──────────┤
│ GOOGLE     │ PMax - 夏季运动鞋      │ $12,500  │ 250         │ 4.2x     │
│ META       │ ASC - 鞋类再营销       │ $8,200   │ 164         │ 3.8x     │
│ TIKTOK     │ In-Feed - 品牌 awareness│ $5,000  │ 80          │ 2.1x     │
│ DV360      │ Brand Takeover - Q1   │ $15,000  │ 120         │ 1.8x     │
└────────────┴───────────────────────┴──────────┴─────────────┴──────────┘
```

### 4.2 统一 API 设计

```
Unified Ad Platform API (GraphQL):

query GetCrossPlatformPerformance($dateFrom: Date!, $dateTo: Date!) {
  crossPlatformPerformance(from: $dateFrom, to: $dateTo) {
    platform
    totalSpend { amount currency }
    totalImpressions
    totalClicks
    totalConversions
    blendedROAS
    blendedCPA
    topCampaigns {
      name
      spend
      conversions
      roas
    }
  }
}

mutation UpdateBudget($campaignId: ID!, $newBudget: Float!) {
  updateCampaignBudget(id: $campaignId, budget: $newBudget) {
    success
    previousBudget
    newBudget
    platform
  }
}
```

---

## 五、自测题

### Q1: 为什么统一数据模型中 spend 要统一转换为 USD？

<details>
<summary>点击查看答案</summary>

原因：
1. **跨平台比较**：不同平台使用不同货币，直接比较无意义
2. **预算分配**：统一货币便于计算各平台的预算占比
3. **ROAS 计算**：ROI = Revenue / Spend，分子分母必须同货币
4. **财务对账**：企业财务通常以 USD 为汇报货币

注意事项：
- 使用实时或 T-1 汇率
- 记录原始货币和金额
- 处理汇率波动对历史数据的影响
- 对于 EUR/CNY 等波动较大的货币，建议使用 T-1 汇率而非实时汇率
</details>

### Q2: 如何处理各平台的数据延迟差异？

<details>
<summary>点击查看答案</summary>

各平台数据延迟：
- Google: 通常实时，最慢 1 小时
- Meta: 通常 T+1（前一天完整）
- TikTok: T+1
- DV360: 实时到 T+1 不等

处理策略：
1. **统一延迟窗口**：只查询 T-2 及之前的数据（确保所有平台都有完整数据）
2. **增量更新**：T-1 数据各平台陆续到达，持续更新
3. **标记状态**：
   - `complete`: 数据完整，可用于分析
   - `pending`: 数据可能不完整，仅作参考
   - `realtime`: 实时数据，波动较大
4. **补数机制**：当平台数据更新时，自动重新计算受影响的时间段
</details>

---

## 六、总结

| 主题 | 核心要点 |
|------|---------|
| 统一模型 | 抽象出 Platform/Campaign/Metrics/Journey 四层实体 |
| 字段映射 | 建立 4 平台 → 统一模型的完整映射表 |
| ETL 管道 |  Connector 模式 + dbt 转换 + BigQuery 存储 |
| 货币统一 | 所有 spend 转换为 USD，记录原始值 |
| 延迟处理 | T-2 窗口策略 + 增量更新 + 状态标记 |
| 查询接口 | GraphQL 统一查询 + 写入接口 |

---

*本文档是跨平台数据架构的参考设计，建议根据实际业务需求调整。*
