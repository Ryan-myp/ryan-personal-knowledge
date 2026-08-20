# 三大广告平台层级结构完整指南

> 版本: v1.0  
> 更新时间: 2026-08-15  
> 覆盖平台: Google Ads、Meta Marketing API、TikTok Ads

---

## 📋 目录

1. [Google Ads 层级结构](#1-google-ads-层级结构)
2. [Meta Marketing API 层级结构](#2-meta-marketing-api-层级结构)
3. [TikTok Ads 层级结构](#3-tiktok-ads-层级结构)
4. [平台对比总结](#4-平台对比总结)
5. [API 字段参考](#5-api-字段参考)

---

## 1. Google Ads 层级结构

### 1.1 账户层级图

```
┌─────────────────────────────────────────────────────────────┐
│                    Google Ads Account                      │
│                    (MCC / 客户账户)                          │
│  - Customer ID: 2493002626                                  │
│  - 层级: MCC → 子账户 → Campaign                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Campaign（广告系列）                       │
│  - 命名规范: [渠道]-[目标]-[日期]-[版本]                     │
│  - 预算: Campaign Budget                                    │
│  - 出价策略: Target CPA / ROAS / Maximize Conversions       │
│  - 广告类型: Search / Display / Shopping / Video / PMax     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad Group（广告组）                         │
│  - 关键词/兴趣/受众分组                                     │
│  - 出价: CPC / CPV / eCPM                                   │
│  - 广告创意模板                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad（广告创意）                             │
│  - Responsive Search Ad（响应式搜索广告）                   │
│  - Expanded Text Ad（扩展文本广告）                         │
│  - Display Ad（展示广告）                                   │
│  - Video Ad（视频广告）                                     │
│  - Shopping Ad（购物广告）                                  │
│  - App Install Ad（应用安装广告）                           │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 广告类型详解

#### 搜索广告（Search Ads）
```
Campaign 目标类型:
├── SALES（销售）
├── LEADS（潜在客户）
├── WEBSITE_TRAFFIC（网站流量）
├── BRAND_AWARENESS（品牌认知）
└── PROMOTION（促销）

Ad Group 配置:
├── Keywords（关键词）
│   ├── Broad Match（广泛匹配）
│   ├── Phrase Match（词组匹配）
│   ├── Exact Match（精确匹配）
│   └── Negative Keywords（否定关键词）
├── Bidding（出价）
│   ├── Manual CPC
│   ├── Enhanced CPC
│   ├── Target CPA
│   └── Target ROAS
└── Ad Extensions（附加信息）
    ├── Sitelink Extensions
    ├── Callout Extensions
    ├── Structured Snippets
    └── Call Extensions
```

#### 性能最大化管理广告（Performance Max，PMax）
```
Campaign 配置:
├── Campaign Goal（活动目标）
│   ├── Sales（销售）
│   ├── Leads（潜在客户）
│   └── Website Traffic（网站流量）
├── Asset Groups（资产组）
│   ├── Headlines（标题）
│   ├── Descriptions（描述）
│   ├── Images（图片）
│   ├── Videos（视频）
│   ├── Logos（Logo）
│   └── Brand Assets（品牌资产）
├── Audience Signals（受众信号）
│   ├── Custom Segments
│   ├── Customer Lists
│   └── Interests & Categories
├── Final URL Expansion（最终 URL 扩展）
└── Location Options（地理位置选项）

注意: PMax 是 Google 的自动化广告形式
- 自动投放到所有 Google 广告格式
- 需要至少 1 个 Asset Group
- 建议准备 15+ 标题 + 5+ 图片
```

#### 购物广告（Shopping Ads）
```
Campaign 配置:
├── Shopping Campaign
│   ├── Standard Shopping（标准购物广告）
│   └── Smart Shopping（智能购物广告，已合并到 PMax）
├── Product Feed（产品 Feed）
│   ├── Google Merchant Center ID
│   ├── 产品数据源
│   └── 产品分组
├── Bidding（出价）
│   ├── Maximize Clicks
│   ├── Maximize Conversion Value
│   └── Target ROAS
└── Priority（优先级）
    ├── Standard
    └── High
```

#### 应用安装广告（App Install Ads）
```
Campaign 目标: APP_PROMOTION

App 配置:
├── App Store（应用商店）
│   ├── Apple App Store
│   ├── Google Play
│   └── App Store ID
├── Bidding（出价）
│   ├── Maximize Installs（最大化安装量）
│   ├── Target CPI（目标单次安装成本）
│   └── Maximize Conversions（最大化转化）
├── Conversion Actions（转化追踪）
│   ├── App Install
│   ├── In-app Action（应用内行为）
│   └── Retargeting（再营销）
└── Ad Creative（广告创意）
    ├── App Preview Video（应用预览视频）
    ├── Text Ads（文本广告）
    └── Image Ads（图片广告）
```

#### YouTube 视频广告（Video Ads）
```
Campaign 目标: VIDEO

广告格式:
├── Skippable In-Stream（可跳过插播广告）
├── Non-Skippable In-Stream（不可跳过插播广告）
├── Bumper Ads（6 秒非跳过广告）
├── Outstream Ads（外置广告）
├── Masthead（头版广告）
└── Shorts Ads（Shorts 广告）

出价策略:
├── View CPV（每次观看成本）
├── View CPM（千次展示成本）
├── Maximize Views（最大化观看）
└── Target CPA（目标单次转化成本）
```

#### 展示广告（Display Ads）
```
Campaign 目标: CUSTOM

广告组类型:
├── Demand Gen Campaign（需求生成广告）
├── Standard Display Campaign（标准展示广告）
└── Discovery Campaign（发现广告）

 placement 类型:
├── Placements（网站/App 定向）
├── Topics（主题定向）
├── Affinity Audiences（兴趣受众）
├── In-Market Audiences（购买意向受众）
└── Custom Intent Audiences（自定义意向受众）
```

### 1.3 Google Ads 字段速查

| 层级 | 字段 | 说明 |
|------|------|------|
| Campaign | `campaign_id` | 广告系列 ID |
| Campaign | `name` | 名称 |
| Campaign | `status` | ENABLED / PAUSED / REMOVED |
| Campaign | `advertising_channel_type` | SEARCH / DISPLAY / SHOPPING / VIDEO / MAX |
| Campaign | `campaign_budget` | 关联的预算资源名 |
| Campaign | `bidding_strategy` | 出价策略资源名 |
| Campaign | `settings` | 包含 location/currency/settings |
| Ad Group | `ad_group_id` | 广告组 ID |
| Ad Group | `name` | 名称 |
| Ad Group | `status` | ENABLED / PAUSED / REMOVED |
| Ad Group | `cpc_bid` | 手动 CPC 出价 |
| Ad Group | `ad_group_bidding_strategy` | 出价策略 |
| Ad | `ad_id` | 广告 ID |
| Ad | `name` | 名称 |
| Ad | `type` | RESPONSIVE_SEARCH_AD / TEXT_AD 等 |
| Ad | `status` | ENABLED / PAUSED / REMOVED |
| Keyword | `ad_group_criterion_id` | 关键词 ID |
| Keyword | `keyword_text` | 关键词文本 |
| Keyword | `match_type` | BROAD / PHRASE / EXACT |
| Keyword | `cpc_bid` | CPC 出价 |
| Budget | `budget_id` | 预算 ID |
| Budget | `amount_micros` | 金额（微单位） |

---

## 2. Meta Marketing API 层级结构

### 2.1 账户层级图

```
┌─────────────────────────────────────────────────────────────┐
│                    Ad Account（广告账户）                    │
│  - Ad Account ID: 2806375919473667                          │
│  - 权限范围: 广告投放、报表、受众、创意                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Campaign（广告系列）                       │
│  - 命名: [渠道]-[目标]-[日期]-[版本]                        │
│  - 目标类型（Objective）:                                   │
│    · LEADS（潜在客户）                                      │
│    · SALES（销售）                                          │
│    · ENGAGEMENT（互动）                                     │
│    · TRAFFIC（流量）                                        │
│    · BRAND_AWARENESS（品牌认知）                            │
│    · CONVERSIONS（转化）                                    │
│  - 预算类型: Daily Budget / Lifetime Budget                  │
│  - 特殊广告类别: NONE / HOUSING / EMPLOYMENT / CREDIT       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad Set（广告组）                           │
│  - 受众定向（Targeting）:                                    │
│    · Locations（地理位置）                                  │
│    · Age（年龄）                                            │
│    · Gender（性别）                                         │
│    · Interests（兴趣）                                      │
│    · Behaviors（行为）                                      │
│  - Placements（广告位）:                                    │
│    · Facebook Feed                                          │
│    · Instagram Feed                                         │
│    · Stories                                                │
│    · Reels                                                  │
│    · Marketplace                                            │
│    · Messenger                                              │
│    · Audience Network                                       │
│  - 预算与排期                                               │
│  - 优化与投放                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad（广告创意）                             │
│  - 格式:                                                     │
│    · Single Image（单张图片）                                │
│    · Carousel（轮播图）                                      │
│    · Video（视频）                                           │
│    · Collection（合集）                                      │
│    · Instant Experience（即时体验）                          │
│  - 创意资产:                                                 │
│    · Primary Text（主文本）                                  │
│    · Headline（标题）                                        │
│    · Description（描述）                                     │
│    · Image / Video                                          │
│    · CTA Button（行动按钮）                                  │
│  - Tracking URL（追踪链接）                                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 广告类型详解

#### 流量广告（Traffic Ads）
```
Campaign Objective: TRAFFIC

配置重点:
├── Optimizations: Link Clicks（链接点击）
├── Billing Event: Link Clicks
├── Targeting: 自定义受众
└── Placements: 手动选择广告位
```

#### 互动广告（Engagement Ads）
```
Campaign Objective: ENGAGEMENT

优化目标:
├── Post Engagement（帖子互动）
├── Message Messages（消息互动）
├── Event Responses（活动响应）
├── Lead Generation（线索收集）
└── Offer Claims（优惠领取）
```

#### 转化广告（Conversion Ads）
```
Campaign Objective: SALES / CONVERSIONS

配置重点:
├── Optimizations: Conversion（转化）
├── Pixel 事件追踪:
│   ├── Purchase（购买）
│   ├── AddToCart（加入购物车）
│   ├── InitiateCheckout（开始结账）
│   ├── ViewContent（查看内容）
│   └── AddToWishlist（添加到愿望清单）
├── CAPI（Conversion API）: 服务器端回传
└── 归因窗口: 7-day click / 1-day view
```

#### 品牌认知广告（Awareness Ads）
```
Campaign Objective: BRAND_AWARENESS / REACH

指标优化:
├── Brand Awareness（品牌认知）
├── Reach（触达）
└── Impressions（展示量）
```

#### 潜在客户广告（Lead Ads）
```
Campaign Objective: LEADS

表单配置:
├── Instant Form（即时表单）
│   ├── Form Type: Higher Intent / Standard
│   ├── Questions: 自定义问题
│   ├── Privacy Policy URL
│   └── CTA Button
├── CRM Integration（CRM 集成）
└── Follow-up Message（后续消息）
```

#### 商店广告（Catalog/Sales Ads）
```
Campaign Objective: SALES

产品目录:
├── Product Catalog（商品目录）
│   ├── Catalog ID
│   ├── Product Set
│   └── Product Feed
├── Ad Format: Carousel / Collection
├── Dynamic Ads（动态广告）
│   ├── Retargeting（再营销）
│   └── Prospecting（拓展新客）
└── Product Quantity: 1-10 个产品
```

#### 引流广告（Messaging Ads）
```
Campaign Objective: MESSAGES

消息平台:
├── WhatsApp（WhatsApp Business）
├── Messenger（Messenger）
├── Instagram Direct
└── SMS

消息模板:
├── Welcome Message（欢迎消息）
├── Quick Reply（快速回复）
├── CTA Button
└── Response Rule（响应规则）
```

### 2.3 Meta Ads 字段速查

| 层级 | 字段 | 说明 |
|------|------|------|
| Campaign | `id` | 广告系列 ID |
| Campaign | `name` | 名称 |
| Campaign | `status` | ACTIVE / PAUSED / DELETED / ARCHIVED |
| Campaign | `objective` | LEADS / SALES / TRAFFIC / ENGAGEMENT 等 |
| Campaign | `special_ad_categories` | ['NONE'] / HOUSING / EMPLOYMENT / CREDIT |
| Campaign | `daily_budget` | 日预算（美分） |
| Campaign | `lifetime_budget` | 总预算 |
| Ad Set | `id` | 广告组 ID |
| Ad Set | `name` | 名称 |
| Ad Set | `status` | ACTIVE / PAUSED / DELETED |
| Ad Set | `optimization_guide` | LINK_CLICKS / CONVERSIONS / QUALITY_RANKING 等 |
| Ad Set | `targeting` | 受众定向配置 |
| Ad Set | `placement_group` | 广告位配置 |
| Ad Set | `daily_budget` | 日预算 |
| Ad Set | `start_time` / `stop_time` | 排期 |
| Ad | `id` | 广告 ID |
| Ad | `name` | 名称 |
| Ad | `status` | ACTIVE / PAUSED / DELETED |
| Ad | `creative` | 创意对象引用 |
| Ad | `body` | 主文本 |
| Ad | `title` | 标题 |
| Ad | `description` | 描述 |
| Ad | `object_store_url` | 产品 URL |
| Creative | `object_id` | 创意对象 ID |
| Creative | `asset_feed_id` | 素材 Feed ID |
| Creative | `title` / `body` | 创意文案 |

---

## 3. TikTok Ads 层级结构

### 3.1 账户层级图

```
┌─────────────────────────────────────────────────────────────┐
│                    Business Center（商务中心）               │
│  - Partner ID: 4659631（示例）                               │
│  - 包含多个 Advertiser                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Advertiser（广告主）                       │
│  - Advertiser ID: 7397068114548195329                        │
│  - 预算管理                                                  │
│  - 账户状态: ACTIVE / SUSPENDED / PENDING                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Campaign（广告系列）                       │
│  - 命名规范: [类型]-[目标]-[日期]                            │
│  - 广告目标（Objective）:                                    │
│    · PRODUCT_SALES（产品销售）                               │
│    · LEAD_GENERATION（线索收集）                             │
│    · APP_PROMOTION（应用推广）                               │
│    · BRAND_AWARENESS（品牌认知）                             │
│    · TRAFFIC（流量）                                         │
│    · VIDEO_VIEWS（视频播放）                                 │
│    · CONVERSIONS（转化）                                     │
│  - 预算类型: Daily Budget / Campaign Budget                  │
│  - 预算模式: BUDGET_MODE_DAY / BUDGET_MODE_LIFETIME          │
│  - 排序: Low / Normal / High                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad Group（广告组）                         │
│  - 出价策略:                                                 │
│    · AUTO_BID（自动出价）                                    │
│    · MANUAL_BID（手动出价）                                  │
│  - 目标:                                                     │
│    · CPC（点击）                                             │
│    · IMPRESSION（展示）                                      │
│    · CONVERSION（转化）                                      │
│  - 定向配置:                                                 │
│    · Interest（兴趣）                                        │
│    · Behavior（行为）                                        │
│    · Demographics（人口统计）                                │
│    · Device（设备）                                          │
│  - 排期与预算                                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad（广告创意）                             │
│  - 格式:                                                     │
│    · Video（视频广告）                                       │
│    · Image（图片广告）                                       │
│    · Carousel（轮播广告）                                    │
│  - Spark Ads（达人原生广告）:                                │
│    · 使用达人原创视频                                        │
│    · 需授权视频 ID                                           │
│  - 落地页配置                                                │
│  - 追踪链接                                                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 广告类型详解

#### 效果广告（Performance Ads）
```
Campaign 目标:
├── PRODUCT_SALES（电商销售）
│   ├── 支持商品目录
│   ├── 智能出价
│   └── 归因分析
├── LEAD_GENERATION（线索收集）
│   ├── 即时表单（Instant Form）
│   └── CRM 集成
├── APP_INSTALL（应用安装）
│   ├── App Store 跳转
│   └── 深度链接
└── CONVERSIONS（转化追踪）
    ├── Pixel 事件
    └── CAPI 回传
```

#### Spark Ads（达人原生广告）
```
特殊配置:
├── spark_info（Spark 信息）
│   ├── video_id（视频 ID）
│   ├── creator_id（达人 ID）
│   └── authorization（授权状态）
├── 使用达人原创内容
├── 高原生感，转化效果好
└── 需达人授权后方可投放
```

#### 品牌广告（Brand Ads）
```
Campaign 目标:
├── BRAND_AWARENESS（品牌认知）
│   ├── TopView（开屏广告）
│   ├── Brand Takeover（品牌收购）
│   └── Hashtag Challenge（话题挑战）
├── VIDEO_VIEWS（视频播放）
│   ├── In-Feed Video（信息流视频）
│   └── Branded Effects（品牌特效）
└── TRAFFIC（流量）
    ├── Landing Page（落地页）
    └── App Download（应用下载）
```

#### 应用广告（App Ads）
```
配置项:
├── App Information（应用信息）
│   ├── App ID
│   ├── App Store URL
│   └── Deep Link
├── Bidding（出价）
│   ├── Cost Cap（成本上限）
│   ├── Auto Bid（自动出价）
│   └── Maximize Conversions（最大化转化）
├── Optimization（优化目标）
│   ├── App Install（应用安装）
│   ├── App Event（应用事件）
│   └── Retention（留存）
└── Creative（创意）
    ├── Video（视频）
    └── Image（图片）
```

#### 商品电商广告（Shop Ads）
```
配置项:
├── Product Set（商品集）
│   ├── 全店商品
│   ├── 分类商品
│   └── 精选商品
├── Catalog（商品目录）
│   ├── Product Feed ID
│   └── 同步设置
├── Ad Format（广告格式）
│   ├── Carousel（轮播）
│   └── Collection（合集）
└── Shop Presence（店铺展示）
    ├── Shop Name
    └── Shop Logo
```

### 3.3 TikTok Ads 字段速查

| 层级 | 字段 | 说明 |
|------|------|------|
| Campaign | `campaign_id` | 广告系列 ID |
| Campaign | `campaign_name` | 名称 |
| Campaign | `status` | ENABLED / PAUSED / DISABLED / ARCHIVED |
| Campaign | `objective_type` | PRODUCT_SALES / LEAD_GENERATION / APP_PROMOTION 等 |
| Campaign | `daily_budget` | 日预算（分） |
| Campaign | `budget_mode` | BUDGET_MODE_DAY / BUDGET_MODE_LIFETIME |
| Campaign | `promotion_type` | PROMOTION_TYPE_STANDARD / PROMOTION_TYPE_SPARK |
| Campaign | `start_time` / `end_time` | 排期 |
| Ad Group | `adgroup_id` | 广告组 ID |
| Ad Group | `adgroup_name` | 名称 |
| Ad Group | `status` | ENABLED / PAUSED / DISABLED |
| Ad Group | `bid_type` | AUTO_BID / MANUAL_BID |
| Ad Group | `bid_amount` | 出价金额 |
| Ad Group | `promoted_object` | 推广对象 |
| Ad Group | `targeting` | 受众定向配置 |
| Ad Group | `daily_budget` | 日预算 |
| Ad | `ad_id` | 广告 ID |
| Ad | `name` | 名称 |
| Ad | `status` | ENABLED / PAUSED / DISABLED |
| Ad | `promoted_type` | PROMOTED_TYPE_VIDEO / PROMOTED_TYPE_IMAGE |
| Ad | `spark_info` | Spark Ads 配置 |
| Spark | `video_id` | 视频 ID |
| Spark | `creator_id` | 达人 ID |
| Spark | `authorization_id` | 授权 ID |

---

## 4. 平台对比总结

### 4.1 层级结构对比

| 维度 | Google Ads | Meta Marketing API | TikTok Ads |
|------|------------|-------------------|------------|
| **顶层** | MCC Account | Ad Account | Business Center |
| **第二层** | Campaign | Campaign | Campaign |
| **第三层** | Ad Group | Ad Set | Ad Group |
| **第四层** | Ad + Keywords | Ad + Creative | Ad + Spark |
| **预算层级** | Campaign | Campaign/Ad Set | Campaign/Ad Group |
| **出价层级** | Campaign/Ad Group | Ad Set | Ad Group |
| **定向层级** | Campaign | Ad Set | Ad Group |
| **创意层级** | Ad | Ad | Ad |

### 4.2 广告类型对比

| 广告类型 | Google Ads | Meta | TikTok |
|---------|------------|------|--------|
| **搜索广告** | ✅ Search | ❌ | ❌ |
| **购物广告** | ✅ Shopping | ✅ Catalog | ✅ Shop |
| **视频广告** | ✅ YouTube | ✅ Video | ✅ In-Feed |
| **展示广告** | ✅ Display | ✅ Display | ❌ |
| **原生广告** | ❌ | ✅ Native | ❌ |
| **Spark Ads** | ❌ | ❌ | ✅ 达人原生 |
| **PMax 广告** | ✅ 全渠道 | ❌ | ❌ |
| **应用安装** | ✅ App | ✅ App | ✅ App |
| **消息广告** | ❌ | ✅ WhatsApp/Messenger | ❌ |
| **开屏广告** | ❌ | ❌ | ✅ TopView |

### 4.3 预算与出价对比

| 特性 | Google Ads | Meta | TikTok |
|------|------------|------|--------|
| **预算类型** | Daily / Lifetime | Daily / Lifetime | Daily / Lifetime |
| **出价方式** | Manual / Smart Bidding | Manual / Automated | Manual / Auto |
| **智能出价** | tCPA / tROAS / Max Conv | Optimization Goal | Cost Cap / Auto Bid |
| **预算单位** | Currency（自动转换） | 美分 | 分 |
| **预算下限** | $1+ | $1+ | 取决于货币 |

### 4.4 关键差异点

```
┌─────────────────────────────────────────────────────────────┐
│                      Google Ads                              │
│  • 搜索意图驱动（人找广告）                                   │
│  • PMax 自动化程度最高                                       │
│  • Shopping 广告独立管理                                      │
│  • Keywords 核心概念                                         │
├─────────────────────────────────────────────────────────────┤
│                      Meta Marketing API                      │
│  • 兴趣/行为驱动（广告找人）                                  │
│  • 受众定向最灵活                                            │
│  • Pixel + CAPI 双轨追踪                                     │
│  • 消息广告独占性（WhatsApp/Messenger）                       │
├─────────────────────────────────────────────────────────────┤
│                      TikTok Ads                              │
│  • 内容驱动（视频原生）                                       │
│  • Spark Ads 独特优势                                        │
│  • 年轻用户群体                                                │
│  • 短视频生态闭环                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. API 字段参考

### 5.1 状态值对照表

| 状态 | Google Ads | Meta | TikTok |
|------|------------|------|--------|
| **启用** | ENABLED | ACTIVE | ENABLED |
| **暂停** | PAUSED | PAUSED | PAUSED |
| **禁用** | - | - | DISABLED |
| **删除** | REMOVED | DELETED | ARCHIVED |
| **待审核** | PENDING_REVIEW | PENDING_REVIEW | PENDING_REVIEW |
| **受限** | LIMITED | LIMITED | SUSPENDED |

### 5.2 目标类型对照

| 目标 | Google Ads | Meta | TikTok |
|------|------------|------|--------|
| **销售** | SALES | SALES | PRODUCT_SALES |
| **线索** | LEADS | LEADS | LEAD_GENERATION |
| **流量** | WEBSITE_TRAFFIC | TRAFFIC | TRAFFIC |
| **互动** | - | ENGAGEMENT | ENGAGEMENT |
| **品牌** | BRAND_AWARENESS | BRAND_AWARENESS | BRAND_AWARENESS |
| **应用** | APP_PROMOTION | APP_PROMOTION | APP_PROMOTION |
| **视频播放** | VIDEO | VIDEO_VIEWS | VIDEO_VIEWS |

### 5.3 出价策略对照

| 策略 | Google Ads | Meta | TikTok |
|------|------------|------|--------|
| **手动 CPC** | MANUAL_CPC | MANUAL_CPC | MANUAL_BID |
| **目标 CPA** | TARGET_CPA | COST_PER_IMPRESSSION_OPTIMIZATION | - |
| **目标 ROAS** | TARGET_ROAS | - | - |
| **最大化转化** | MAXIMIZE_CONVERSIONS | AUTOMATED_COST_PER_CLICK | AUTO_BID |
| **成本上限** | - | - | COST_CAP |
| **自动出价** | SMART_TARGET_CPA | OPTIMIZATION_GOAL | AUTO_BID |

---

## 附录：快速创建命令参考

### Google Ads（Python）
```python
from google.ads.googleads.client import GoogleAdsClient

# 创建 Campaign
campaign = {
    "campaign.name": "Summer Sale 2026",
    "campaign.advertising_channel_type": "SEARCH",
    "campaign.status": "PAUSED",  # 先创建暂停
    "campaign.budget": "resource_names/campaign_budget/12345",
    "campaign.bidding_strategy": "resource_names/bidding_strategy/67890",
    "campaign.settings": {
        "targeting_setting": {
            "target_restrictions": [
                {"geographic_targeting_restriction": {"regions": ["regions/US"]}}
            ]
        }
    }
}

# 创建 Ad Group
ad_group = {
    "ad_group.campaign": "resource_names/campaign/123",
    "ad_group.name": "Summer Sale - Electronics",
    "ad_group.status": "PAUSED",
    "ad_group.cpc_bid_micros": 500000,  # $0.005
}
```

### Meta（Python）
```python
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad

# 创建 Campaign
campaign = AdAccount(act_acct_id).create_campaign(
    name='Summer Sale 2026',
    objective='SALES',
    special_ad_categories=['NONE'],
    status=Campaign.Status.paused
)

# 创建 Ad Set
ad_set = campaign.create_adset(
    name='Ad Set - Electronics',
    optimization_guide='CONVERSIONS',
    targeting={
        'locations': {'key': 'US'},
        'age_min': 18,
        'age_max': 65,
    },
    daily_budget=1000,  # 10 USD in cents
    status=AdSet.Status.paused
)

# 创建 Ad
ad = ad_set.create_ad(
    name='Ad - Product A',
    creative={
        'object_story_spec': {
            'page_id': page_id,
            'link_data': {
                'image_hash': image_hash,
                'call_to_action': {'type': 'LEARN_MORE'},
            }
        }
    },
    body='Check out our summer sale!',
    title='Summer Sale - Up to 50% Off',
    status=Ad.Status.paused
)
```

### TikTok（Python）
```python
import requests

# 获取 Access Token
headers = {
    'Access-Token': access_token,
    'Content-Type': 'application/json'
}

# 创建 Campaign
campaign_data = {
    'campaign_name': 'Summer Sale 2026',
    'objective_type': 'PRODUCT_SALES',
    'daily_budget': 5000,  # $50 in cents
    'budget_mode': 'BUDGET_MODE_DAY',
    'promotion_type': 'PROMOTION_TYPE_STANDARD',
    'status': 'PAUSED'
}
response = requests.post(
    'https://business-api.tiktok.com/open_api/v1.3/campaign/create/',
    headers=headers,
    json=campaign_data
)

# 创建 Ad Group
adgroup_data = {
    'adgroup_name': 'Electronics - Summer Sale',
    'campaign_id': campaign_id,
    'bid_type': 'MANUAL_BID',
    'bid_amount': 100,  # $1 CPC
    'promoted_object': {
        'objective_type': 'PRODUCT_SALES',
        'landing_url': 'https://example.com'
    },
    'status': 'PAUSED'
}
response = requests.post(
    'https://business-api.tiktok.com/open_api/v1.3/adgroup/create/',
    headers=headers,
    json=adgroup_data
)
```

---

**文档版本**: v1.0  
**创建日期**: 2026-08-15  
**作者**: Ryan

