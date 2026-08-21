# 广告平台层级结构完整指南 v4.0

> 更新时间: 2025-07-25  
> 版本: v4.0（基于官方 API 文档整理）
> 数据来源: 
> - [Google Ads API](https://developers.google.com/google-ads/api/docs/start)
> - [Meta Marketing API](https://developers.facebook.com/docs/marketing-apis/)
> - [TikTok Business API](https://developers.tiktok.com/doc/ads-api-overview)
> - [DV360 API](https://developers.google.com/display-video/api/guides)

---

## 目录

1. [Google Ads 层级结构](#1-google-ads-层级结构)
   - 1.1 搜索广告（Search Ads）
   - 1.2 性能最大化广告（Performance Max）
   - 1.3 购物广告（Shopping Ads）
   - 1.4 视频广告（Video Ads）
   - 1.5 展示广告（Display Ads）
   - 1.6 应用广告（App Ads）
2. [Meta Marketing API 层级结构](#2-meta-marketing-api-层级结构)
   - 2.1 流量广告（Traffic Ads）
   - 2.2 转化广告（Conversion Ads）
   - 2.3 线索广告（Lead Ads）
   - 2.4 互动广告（Engagement Ads）
   - 2.5 商品广告（Catalog Ads）
   - 2.6 消息广告（Messaging Ads）
3. [TikTok Ads 层级结构](#3-tiktok-ads-层级结构)
   - 3.1 产品销售广告（Product Sales）
   - 3.2 Spark Ads（达人原生广告）
   - 3.3 线索收集广告（Lead Generation）
   - 3.4 应用推广广告（App Promotion）
   - 3.5 品牌广告（Brand Ads）
4. [DV360 层级结构](#4-dv360-层级结构)
5. [平台对比速查表](#5-平台对比速查表)

---

## 1. Google Ads 层级结构

### 通用层级架构

```
Customer (账户)
├── Campaign Budget (预算)
│   ├── amount_micros: 10000000 (=$100)
│   └── delivery_method: STANDARD / DAILY
├── Campaign (广告系列)
│   ├── advertising_channel_type: SEARCH/SHOPPING/VIDEO/DISPLAY/APP/MAX
│   ├── status: ENABLED / PAUSED / REMOVED
│   ├── bidding_strategy: resource_name
│   ├── campaign_budget: resource_name
│   └── settings:
│       ├── targeting_setting
│       ├── network_setting
│       └── shopping_setting (仅 Shopping)
├── Ad Group (广告组)
│   ├── name
│   ├── status
│   ├── cpc_bid_micros
│   └── bidding_strategy_override (可选)
├── Ad Group Criterion (广告组限定条件)
│   ├── Keywords (关键词)
│   ├── Product Groups (产品分组，仅 Shopping/PMax)
│   └── Negative Criteria (否定限定)
└── Ads (广告创意)
    ├── Responsive Search Ad
    ├── Expanded Text Ad
    └── Asset Group (PMax 专用)
```

**官方文档来源**: 
- [Campaign Service](https://developers.google.com/google-ads/api/docs/campaigns/overview)
- [AdvertisingChannelTypeEnum](https://developers.google.com/google-ads/api/reference/rest/v18/enums/AdvertisingChannelType)

---

### 1.1 搜索广告（Search Ads）

#### 层级结构

```
Campaign (Search)
├── advertising_channel_type: SEARCH
├── status: ENABLED
├── campaign_budget: resource_name
├── bidding_strategy: MANUAL_CPC / TARGET_CPA / MAXIMIZE_CONVERSIONS
├── settings:
│   ├── targeting_setting:
│   │   └── target_restrictions: [GEOGRAPHIC]
│   └── network_setting:
│       ├── target_google_search: true
│       ├── target_search_partners: false
│       └── target_network: false
└── resource_name: customers/{customer_id}/campaigns/{campaign_id}
    │
    ├── Ad Group
    │   ├── name: "Electronics Products"
    │   ├── status: ENABLED
    │   ├── cpc_bid_micros: 250000 (=$0.25)
    │   └── resource_name: customers/{customer_id}/adGroups/{ad_group_id}
    │       │
    │       ├── Keywords (Ad Group Criteria)
    │       │   ├── criterion.text: "running shoes"
    │       │   ├── criterion.match_type: PHRASE
    │       │   └── cpc_bid_micros: 300000
    │       │
    │       └── Negative Keywords
    │           └── criterion.text: "free"
    │
    └── Ads (Responsive Search Ad)
        ├── ad_group: resource_name
        ├── name: "Running Shoes - Summer Sale"
        ├── status: ENABLED
        ├── type: RESPONSIVE_SEARCH_AD
        ├── info:
        │   ├── headlines: [
        │   │   {text: "Buy Running Shoes", prominence: 0},
        │   │   {text: "Summer Sale 50% Off", prominence: 0}
        │   │ ]
        │   └── descriptions: [
        │       {text: "Best running shoes for summer"},
        │       {text: "Free shipping on orders over $50"}
        │     ]
        └── final_urls: ["https://example.com/shoes"]
```

#### 支持的广告附加信息 (Extensions)

| 类型 | 字段 | 数量限制 | 官方文档 |
|------|------|----------|----------|
| Sitelink | `SitelinkExtensionSetting` | 最多 15 个 | [Sitelink](https://developers.google.com/google-ads/api/docs/campaigns/sitelink-extensions) |
| Callout | `CalloutExtensionSetting` | 最多 10 个 | [Callout](https://developers.google.com/google-ads/api/docs/campaigns/callout-extensions) |
| Structured Snippet | `StructuredSnippetExtensionSetting` | 最多 5 个 | [Snippet](https://developers.google.com/google-ads/api/docs/campaigns/structured-snippet-extensions) |
| Call | `CallExtensionSetting` | 1 个 | [Call](https://developers.google.com/google-ads/api/docs/campaigns/call-extensions) |
| Message | `MessageExtensionSetting` | 1 个 | [Message](https://developers.google.com/google-ads/api/docs/campaigns/message-extensions) |
| Location | `LocationExtensionSetting` | 1 个 | [Location](https://developers.google.com/google-ads/api/docs/campaigns/location-extensions) |
| Price | `PriceExtensionSetting` | 最多 8 个 | [Price](https://developers.google.com/google-ads/api/docs/campaigns/price-extensions) |
| Promotion | `PromotionExtensionSetting` | 2 个 | [Promotion](https://developers.google.com/google-ads/api/docs/campaigns/promotion-extensions) |
| App | `AppExtensionSetting` | 1 个 | [App](https://developers.google.com/google-ads/api/docs/campaigns/app-extensions) |
| Affiliate Location | `AffiliateLocationExtensionSetting` | 最多 8 个 | [Affiliate](https://developers.google.com/google-ads/api/docs/campaigns/affiliate-location-extensions) |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Search | 搜索结果页 |
| Google Search Partners | 搜索合作伙伴网站 |
| Google Shopping | 购物标签页 |
| Google Play | 应用商店 |

**官方文档来源**: [Search Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/search-campaigns)

---

### 1.2 性能最大化广告（Performance Max）

#### 层级结构

```
Campaign (Performance Max)
├── advertising_channel_type: MAX
├── status: ENABLED
├── campaign_goal_setting:
│   ├── sales_campaign_goal_setting:
│   │   ├── goal_type: SALES_GOAL_TYPE_ECOMMERCE
│   │   └── ecommerce_checkout_progress: 0.5
│   └── lead_campaign_goal_setting:
│       └── generate_leads_campaign_goal_setting: { ... }
├── bidding_strategy: MAXIMIZE_CONVERSIONS / TARGET_ROAS
├── audience_signals:
│   └── custom_segments: ["In-Market - Apparel"]
├── asset_group:
│   ├── name: "Summer Collection"
│   ├── status: ENABLED
│   ├── products:
│   │   └── listing_group:
│   │       ├── all_products: {}
│   │       └── product_type_1: {values: ["Electronics"]}
│   ├── assets:
│   │   ├── headlines: ["Buy Now", "Summer Sale"]
│   │   ├── descriptions: ["Best prices", "Limited time"]
│   │   ├── images: [{media_file: "image_url"}]
│   │   ├── logos: [{media_file: "logo_url"}]
│   │   └── videos: [{media_file: "video_url"}]
│   └── final_url_suffix: "?source=pmax"
└── resource_name: customers/{customer_id}/campaigns/{campaign_id}
```

#### Asset 类型（PMax 专用）

| 类型 | 说明 | 建议数量 | 官方文档 |
|------|------|----------|----------|
| Headline | 标题 | 10-15 个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Description | 描述 | 4-5 个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Image | 图片 | 5-10 个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Logo | Logo | 3-5 个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Video | 视频 | 1-5 个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| CTA Text | 行动号召文本 | 1 个 | [CTA](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Call Out | 补充说明 | 10 个 | [Callouts](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Sitelink | 附加链接 | 15 个 | [Sitelinks](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Product Feed Link | 产品Feed链接 | 1 个 | [Product Feed](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#product-feed) |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Search | 搜索广告 |
| Google Shopping | 购物广告 |
| YouTube | 视频广告 |
| Gmail | 邮件广告 |
| Google Display Network | 展示广告 |
| Google Maps | 地图广告 |

**官方文档来源**: [Performance Max Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/performance-max)

---

### 1.3 购物广告（Shopping Ads）

#### 层级结构

```
Campaign (Shopping)
├── advertising_channel_type: SHOPPING
├── status: ENABLED
├── campaign_budget: resource_name
├── bidding_strategy: MANUAL_CPC / MAXIMIZE_CONVERSIONS_VALUE
├── settings:
│   └── shopping_setting:
│       ├── merchant_id: 12345678
│       ├── sales_country: "US"
│       ├── marketing_language: "EN"
│       ├── priority: 0 (0-100)
│       └── exclude_offline_store_locations: false
├── product_promotion_link:
│   └── promotion_id: 促销 ID
└── resource_name: customers/{customer_id}/campaigns/{campaign_id}
    │
    └── Ad Group
        ├── name: "Electronics Products"
        ├── status: ENABLED
        └── resource_name: customers/{customer_id}/adGroups/{ad_group_id}
            │
            └── Product Group (Listing Group)
                ├── all_products: {}  (全部产品)
                ├── product_type_1: {values: ["Electronics"]}
                ├── product_type_2: {values: ["Phones"]}
                ├── brand: {values: ["Apple"]}
                └── condition: {values: ["NEW"]}
                (product_group 可多层嵌套细分)
```

#### Product Group 真实字段

| 字段 | 说明 | 示例值 | 官方文档 |
|------|------|--------|----------|
| `all_products` | 根节点，包含所有产品 | `{}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_1` | 产品子类 1 | `{"values": ["Electronics"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_2` | 产品子类 2 | `{"values": ["Phones"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_3` | 产品子类 3 | `{"values": ["Smartphones"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_4` | 产品子类 4 | - | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_5` | 产品子类 5 | - | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_0` | 自定义标签 0 | `{"values": ["bestseller"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_1` | 自定义标签 1 | `{"values": ["clearance"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_2` | 自定义标签 2 | `{"values": ["seasonal"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_3` | 自定义标签 3 | `{"values": ["premium"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_4` | 自定义标签 4 | `{"values": ["new_arrival"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `brand` | 品牌 | `{"values": ["Apple", "Samsung"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `category` | Google 品类 | `{"values": ["4167", "4168"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `condition` | 商品条件 | `{"values": ["NEW", "USED"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |

**注意**: 以下字段**不存在**于 Google Ads API Product Group：
- ~~`gender.values`~~
- ~~`age_group.values`~~
- ~~`color.values`~~
- ~~`size.values`~~

这些是 Merchant Center 产品数据中的字段，不是 Product Group 的筛选条件。

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 | 数量限制 |
|------|------|----------|
| Sitelink | 附加链接文本 | 最多 15 个 |
| Callout | 补充说明文本 | 最多 10 个 |
| Structured Snippet | 结构化摘要 | 最多 5 个 |
| Price | 价格信息 | 最多 8 个 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Shopping | 购物标签页 |
| Google Search | 搜索结果中的购物结果 |
| Google Shopping Tab | 专属购物频道 |
| Google Partner Sites | 合作伙伴网站 |

**官方文档来源**: [Shopping Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/shopping)

---

### 1.4 视频广告（Video Ads）

#### 层级结构

```
Campaign (Video)
├── advertising_channel_type: VIDEO
├── status: ENABLED
├── campaign_budget: resource_name
├── bidding_strategy: MAXIMIZE_CONVERSIONS / TARGET_CPM
├── settings:
│   └── video_setting:
│       ├── smart_performance: false
│       └── video_ad_format_preference: [TRUE_VIEW_IN_STREAM, NON_TRUE_VIEW_IN_STREAM]
└── resource_name: customers/{customer_id}/campaigns/{campaign_id}
    │
    └── Ad Group
        ├── name: "YouTube Campaign"
        ├── status: ENABLED
        ├── cpc_bid_micros: 500000 (=$0.50)
        │
        ├── Ad (Video Ad)
        │   ├── type: VIDEO
        │   ├── video:
        │   │   └── video_id: "dQw4w9WgXcQ" (YouTube 视频 ID)
        │   └── final_urls: ["https://example.com"]
        │
        └── Customer SEO (可选)
            └── audience_expansion: true
```

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 | 数量限制 |
|------|------|----------|
| Call | 电话扩展 | 1 个 |
| Location | 位置扩展 | 1 个 |
| Callout | 补充说明 | 10 个 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| YouTube | 视频播放页 |
| YouTube Search | YouTube 搜索 |
| YouTube Homepage | YouTube 首页 |
| YouTube Mobile | 移动端 |
| Google Video Partners | 视频合作伙伴网络 |

**官方文档来源**: [Video Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/video-campaigns)

---

### 1.5 展示广告（Display Ads）

#### 层级结构

```
Campaign (Display)
├── advertising_channel_type: DISPLAY
├── status: ENABLED
├── campaign_budget: resource_name
├── bidding_strategy: TARGET_CPM / MAXIMIZE_CONVERSIONS
├── settings:
│   ├── targeting_setting:
│   │   └── geo_target_type: LOCAL_OR_PRESENT
│   └── network_setting:
│       └── target_content_network: false
└── resource_name: customers/{customer_id}/campaigns/{campaign_id}
    │
    └── Ad Group
        ├── name: "Retargeting"
        ├── status: ENABLED
        ├── cpm_bid_micros: 200000 (=$0.20)
        │
        ├── Audience (受众)
        │   └── inference_label: {label: "Lifestyle & Fashion"}
        │
        └── Ad (Responsive Display Ad)
            ├── type: RESPONSIVE_DISPLAY_AD
            ├── name: "Summer Sale"
            ├── status: ENABLED
            ├── info:
            │   ├── headlines: ["Summer Sale", "Up to 50% Off"]
            │   ├── descriptions: ["Shop now", "Limited time"]
            │   ├── logos: [{media_file: "logo.png"}]
            │   ├── marketing_images: [{media_file: "image.jpg"}]
            │   └── business_name: "My Store"
            └── final_urls: ["https://example.com"]
```

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 | 数量限制 |
|------|------|----------|
| Callout | 补充说明 | 10 个 |
| Structured Snippet | 结构化摘要 | 5 个 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Display Network | 展示广告网络 |
| Contextual Placements | 上下文定位 |
| Placements | 指定网站/应用 |
| Topics | 主题定位 |
| Affinity Audiences | 亲和受众 |
| In-Market Audiences | 购买意向受众 |

**官方文档来源**: [Display Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/display-campaigns)

---

### 1.6 应用广告（App Ads）

#### 层级结构

```
Campaign (App)
├── advertising_channel_type: APP
├── status: ENABLED
├── campaign_budget: resource_name
├── bidding_strategy: TARGET_CPA / MAXIMIZE_CONVERSIONS
├── settings:
│   └── app_setting:
│       └── app_id: "com.example.app" (Google Play 包名)
└── resource_name: customers/{customer_id}/campaigns/{campaign_id}
    │
    └── Ad Group
        ├── name: "App Install"
        ├── status: ENABLED
        │
        ├── Ad (App Ad)
        │   ├── type: APP_AD
        │   ├── app_ad:
        │   │   ├── app_id: "com.example.app"
        │   │   ├── tracking_url: "https://example.com/tracking"
        │   │   └── url_custom_parameters: {ua: "app"}
        │   └── info:
        │       ├── headlines: ["Install Our App"]
        │       ├── descriptions: ["Download now"]
        │       └── marketing_images: [{media_file: "image.jpg"}]
        │
        └── Assets (资产组)
            ├── headlines: ["Install Now", "Get the App"]
            ├── descriptions: ["Best app for..."]
            ├── images: [{media_file: "image.jpg"}]
            └── videos: [{media_file: "video.mp4"}]
```

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 | 数量限制 |
|------|------|----------|
| App | 应用安装 | 1 个 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Play Store | 应用商店 |
| YouTube | 视频广告 |
| Google Search | 搜索广告 |
| Google Network of Partners | 合作伙伴网络 |
| Other Apps | 其他应用 |
| Other Websites | 其他网站 |

**官方文档来源**: [App Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/app-campaigns)

---

## 2. Meta Marketing API 层级结构

### 通用层级架构

```
Business Manager (业务管理器)
└── Ad Account (广告账户) act_{account_id}
    ├── Campaign (广告系列)
    │   ├── objective: OUTCOME_LEADS / OUTCOME_CONVERSIONS / OUTCOME_SALES / OUTCOME_AWARENESS
    │   ├── status: ACTIVE / PAUSED / DELETED
    │   ├── daily_budget: 10000 (单位: 分)
    │   └── special_ad_categories: [] (必需，无特殊分类设为空数组)
    ├── Ad Set (广告组)
    │   ├── name
    │   ├── status
    │   ├── budget_remaining
    │   ├── targetting:
    │   │   ├── geo_locations: {countries: ["US"]}
    │   │   ├── age_min: 18
    │   │   ├── age_max: 65
    │   │   ├── interests: [{name: "Marketing"}]
    │   │   └── behaviors: [{name: "Digital activity"}]
    │   └── placement: FEED / STORIES / RIGHT_COLUMN / INSTAGRAM_FEED
    └── Ad (广告)
        ├── name
        ├── status
        ├── creative:
        │   ├── object_story_spec:
        │   │   ├── page_id: 页面 ID
        │   │   └── link_data:
        │   │       ├── call_to_action: {type: "LEARN_MORE"}
        │   │       └── message: "Learn more about..."
        │   └── image_hash: 图片哈希
        └── run_status: ACTIVE
```

**官方文档来源**: [Campaign Objectives](https://developers.facebook.com/docs/marketing-apis/campaign-objective-overview)

---

### 2.1 流量广告（Traffic Ads）

#### 层级结构

```
Campaign (Traffic)
├── objective: OUTCOME_TRAFFIC (流量)
├── status: ACTIVE
├── daily_budget: 5000 (=$50)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Traffic Campaign"
        ├── optimization_goal: LINK_CLICKS (链接点击)
        ├── targeting:
        │   ├── geo_locations: {countries: ["US"]}
        │   └── interests: [{name: "Technology"}]
        └── placements: [FEED, STORIES]
            │
            └── Ad
                ├── name: "Traffic Ad"
                ├── creative:
                │   ├── link_data:
                │   │   ├── message: "Check out our latest article"
                │   │   └── call_to_action: {type: "LEARN_MORE"}
                │   └── image_hash: "abc123"
                └── run_status: ACTIVE
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 动态 |
| Instagram Feed | Instagram 动态 |
| Stories | 快拍 |
| Right Column | 右侧栏 |
| Marketplace | 市场 |

**官方文档来源**: [Traffic Campaigns](https://developers.facebook.com/docs/marketing-apis/optimization-goals)

---

### 2.2 转化广告（Conversion Ads）

#### 层级结构

```
Campaign (Conversion)
├── objective: OUTCOME_CONVERSIONS (转化)
├── status: ACTIVE
├── daily_budget: 10000 (=$100)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Conversion Campaign"
        ├── optimization_goal: CONVERSIONS (转化)
        ├── conversion_specs: [{external_event_id: "product_view"}]
        ├── targeting:
        │   └── geo_locations: {countries: ["US", "CA"]}
        └── placements: [FEED, INSTAGRAM_FEED]
            │
            └── Ad
                ├── name: "Conversion Ad"
                ├── creative:
                │   └── link_data:
                │       ├── message: "Shop now and save"
                │       └── call_to_action: {type: "SHOP_NOW"}
                └── run_status: ACTIVE
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 动态 |
| Instagram Feed | Instagram 动态 |
| Stories | 快拍 |
| Reels | Reels |

**官方文档来源**: [Conversion Campaigns](https://developers.facebook.com/docs/marketing-apis/campaign-objective-overview)

---

### 2.3 线索广告（Lead Ads）

#### 层级结构

```
Campaign (Lead Generation)
├── objective: OUTCOME_LEADS (线索)
├── status: ACTIVE
├── daily_budget: 8000 (=$80)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Lead Generation Campaign"
        ├── optimization_goal: LEADS (线索)
        ├── lead_gen_config:
        │   ├── form_id: "123456789" (表单 ID)
        │   └── dynamic_form_config: { ... }
        ├── targeting:
        │   └── geo_locations: {countries: ["US"]}
        └── placements: [FEED, STORIES]
            │
            └── Ad
                ├── name: "Lead Gen Ad"
                ├── creative:
                │   └── lead_gen:
                │       ├── page_id: 页面 ID
                │       └── config: { ... }
                └── run_status: ACTIVE
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 动态 |
| Instagram Feed | Instagram 动态 |
| Stories | 快拍 |
| Messenger | Messenger |

**官方文档来源**: [Lead Ads](https://developers.facebook.com/docs/marketing-apis/lead-forms)

---

### 2.4 互动广告（Engagement Ads）

#### 层级结构

```
Campaign (Engagement)
├── objective: OUTCOME_ENGAGEMENT (互动)
├── status: ACTIVE
├── daily_budget: 3000 (=$30)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Engagement Campaign"
        ├── optimization_goal: POST_ENGAGEMENT (帖子互动)
        ├── targeting:
        │   └── geo_locations: {countries: ["US"]}
        └── placements: [FEED, STORIES]
            │
            └── Ad
                ├── name: "Engagement Ad"
                ├── creative:
                │   └── link_data:
                │       └── call_to_action: {type: "LIKE_PAGE"}
                └── run_status: ACTIVE
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 动态 |
| Instagram Feed | Instagram 动态 |
| Stories | 快拍 |

**官方文档来源**: [Engagement Campaigns](https://developers.facebook.com/docs/marketing-apis/campaign-objective-overview)

---

### 2.5 商品广告（Catalog Ads）

#### 层级结构

```
Campaign (Catalog Sales)
├── objective: OUTCOME_SALES (销售)
├── status: ACTIVE
├── daily_budget: 15000 (=$150)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Catalog Campaign"
        ├── optimization_goal: CONVERSIONS (转化)
        ├── catalog_id: "123456789" (商品目录 ID)
        ├── targeting:
        │   └── geo_locations: {countries: ["US"]}
        └── placements: [FEED, INSTAGRAM_FEED]
            │
            └── Ad
                ├── name: "Catalog Ad"
                ├── creative:
                │   ├── catalog_product_set_id: "123"
                │   └── ad_style: CAROUSEL (轮播)
                └── run_status: ACTIVE
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 动态 |
| Instagram Feed | Instagram 动态 |
| Stories | 快拍 |
| Reels | Reels |

**官方文档来源**: [Catalog Ads](https://developers.facebook.com/docs/marketing-apis/catalog-ads)

---

### 2.6 消息广告（Messaging Ads）

#### 层级结构

```
Campaign (Messaging)
├── objective: OUTCOME_MESSAGES (消息)
├── status: ACTIVE
├── daily_budget: 5000 (=$50)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Messaging Campaign"
        ├── optimization_goal: MESSAGES (消息)
        ├── messaging_apps: ["MESSENGER", "WHATSAPP"]
        ├── targeting:
        │   └── geo_locations: {countries: ["US"]}
        └── placements: [FEED, STORIES]
            │
            └── Ad
                ├── name: "Messaging Ad"
                ├── creative:
                │   └── link_data:
                │       └── call_to_action: {type: "SEND_MESSAGE"}
                └── run_status: ACTIVE
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 动态 |
| Instagram Feed | Instagram 动态 |
| Messenger | Messenger |
| WhatsApp | WhatsApp |

**官方文档来源**: [Messaging Campaigns](https://developers.facebook.com/docs/marketing-apis/messaging-apps)

---

## 3. TikTok Ads 层级结构

### 通用层级架构

```
Business Center (业务中心)
└── Ad Account (广告账户) ad_id
    ├── Campaign (广告系列)
    │   ├── objective: PRODUCT_SALES / LEAD_GENERATION / APP_INSTALLS / BRAND_AWARENESS
    │   ├── status: ENABLED / DISABLED
    │   ├── daily_budget: 1000 (单位: 分)
    │   └── budget_total: 10000
    ├── Ad Group (广告组)
    │   ├── name
    │   ├── status
    │   ├── bid_type: AUTO_BID / MANUAL_BID
    │   ├── bid_value: 100
    │   ├── targeting:
    │   │   ├── age_min: 18
    │   │   ├── age_max: 65
    │   │   ├── genders: [1, 2] (1=女, 2=男)
    │   │   └── placements: [TikTok]
    │   └── creative_setting: {video_id: "xxx"}
    └── Ad (广告)
        └── creative:
            ├── video: {video_id: "xxx"}
            └── image: [{url: "image_url"}]
```

**官方文档来源**: [Campaign API](https://developers.tiktok.com/doc/ads-api-campaign)

---

### 3.1 产品销售广告（Product Sales）

#### 层级结构

```
Campaign (Product Sales)
├── objective: PRODUCT_SALES
├── status: ENABLED
├── daily_budget: 5000 (=$50)
└── budget_total: 10000
    │
    └── Ad Group
        ├── name: "Product Sales"
        ├── bid_type: AUTO_BID
        ├── bid_value: 100
        ├── targeting:
        │   ├── age_min: 18
        │   ├── age_max: 45
        │   ├── genders: [1, 2]
        │   └── placements: [TikTok]
        └── creative_setting:
            └── video_id: "video_123"
            │
            └── Ad
                ├── creative:
                │   └── video: {video_id: "video_123"}
                └── promote_object:
                    └── website: "https://example.com"
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok | TikTok Feed |
| TikTok Fullscreen | 全屏视频 |
| TikTok Brand Takeover | 品牌 takeover |

**官方文档来源**: [Product Sales](https://developers.tiktok.com/doc/ads-api-campaign)

---

### 3.2 Spark Ads（达人原生广告）

#### 层级结构

```
Campaign (Spark Ads)
├── objective: PRODUCT_SALES
├── status: ENABLED
├── daily_budget: 5000
└── budget_total: 10000
    │
    └── Ad Group
        ├── name: "Spark Ads"
        ├── bid_type: AUTO_BID
        ├── spark_post_id: "post_123" (达人帖子 ID)
        └── creative_setting:
            └── spark_ad_info: {post_id: "post_123"}
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok Feed | TikTok 动态 |
| TikTok Search | TikTok 搜索 |

**官方文档来源**: [Spark Ads](https://developers.tiktok.com/doc/ads-api-spark)

---

### 3.3 线索收集广告（Lead Generation）

#### 层级结构

```
Campaign (Lead Generation)
├── objective: LEAD_GENERATION
├── status: ENABLED
├── daily_budget: 3000
└── budget_total: 5000
    │
    └── Ad Group
        ├── name: "Lead Gen"
        ├── bid_type: AUTO_BID
        ├── form_id: "form_123" (表单 ID)
        └── creative_setting:
            └── video_id: "video_456"
            │
            └── Ad
                └── promote_object:
                    └── lead_form: {form_id: "form_123"}
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok Feed | TikTok 动态 |

**官方文档来源**: [Lead Generation](https://developers.tiktok.com/doc/ads-api-lead-generation)

---

### 3.4 应用推广广告（App Promotion）

#### 层级结构

```
Campaign (App Promotion)
├── objective: APP_INSTALLS
├── status: ENABLED
├── daily_budget: 8000
└── budget_total: 15000
    │
    └── Ad Group
        ├── name: "App Install"
        ├── bid_type: AUTO_BID
        └── creative_setting:
            └── video_id: "video_789"
            │
            └── Ad
                └── promote_object:
                    └── app_install: {app_id: "com.example.app"}
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok Feed | TikTok 动态 |
| TikTok Search | TikTok 搜索 |

**官方文档来源**: [App Promotion](https://developers.tiktok.com/doc/ads-api-app-promotion)

---

### 3.5 品牌广告（Brand Ads）

#### 层级结构

```
Campaign (Brand Awareness)
├── objective: BRAND_AWARENESS
├── status: ENABLED
├── daily_budget: 20000
└── budget_total: 50000
    │
    └── Ad Group
        ├── name: "Brand Campaign"
        ├── bid_type: CPM
        ├── bid_value: 500
        └── creative_setting:
            └── video_id: "video_brand"
            │
            └── Ad
                └── creative:
                    └── video: {video_id: "video_brand"}
```

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok Fullscreen | 全屏视频 |
| TikTok Brand Takeover | 品牌 takeover |
| TikTok Feed | TikTok 动态 |

**官方文档来源**: [Brand Awareness](https://developers.tiktok.com/doc/ads-api-brand-awareness)

---

## 4. DV360 层级结构

### 通用层级架构

```
Partner (MCN/代理商)
└── Advertiser (广告主)
    ├── Insertion Order (IO) - 类似 Campaign
    │   ├── name: IO 名称
    │   ├── status: ACTIVE / INACTIVE / ARCHIVED
    │   ├── start_time: 开始时间
    │   ├── end_time: 结束时间
    │   └── funding_source: PARTNER / ADVERTISER
    │       │
    │       ├── Line Item (行项目) - 广告投放单元
    │       │   ├── name: 行项目名称
    │       │   ├── status: ACTIVE / PAUSED / COMPLETED / REJECTED
    │       │   ├── type: VIDEO / DISPLAY / AUDIO / CTV
    │       │   ├── funding_bundle_id: 资金包 ID
    │       │   ├── goal:
    │       │   │   └── goal_type: IMPRESSIONS / CONVERSIONS / VIEWABILITY
    │       │   └── targeting:
    │       │       ├── inventory_source: YOUTUBE / GAM / EXTERNAL
    │       │       ├── geo_targeting: {countries: ["US"]}
    │       │       └── creative_type_filtering: [VIDEO, DISPLAY]
    │       │           │
    │       │           └── Creative (创意素材)
    │       │               ├── name: 创意名称
    │       │               ├── status: ACTIVE / ARCHIVED
    │       │               ├── type: VIDEO / IMAGE / HTML / NATIVE
    │       │               └── media_file: 媒体文件 URL
    │       │
    │       └── Custom Channel (可选)
    │           └── reported_custom_channel
    │
    └── Reported Custom Channel (RCCH) - 报表自定义渠道
```

**官方文档来源**: [DV360 API](https://developers.google.com/display-video/api/guides)

---

### 4.1 视频广告（Video Ads）

#### 层级结构

```
Line Item (Video)
├── type: VIDEO
├── status: ACTIVE
├── funding_bundle_id: bundle_123
├── goal:
│   └── goal_type: IMPRESSIONS
├── targeting:
│   ├── inventory_source: YOUTUBE
│   ├── geo_targeting: {countries: ["US"]}
│   └── creative_type_filtering: [VIDEO]
└── Creatives:
    ├── Video Creative
    │   ├── name: "Video Ad"
    │   ├── type: VIDEO
    │   └── media_file: "video_url"
    └── Skippable In-Stream
        ├── type: SKIPPABLE_IN_STREAM
        └── video_id: "youtube_video_id"
```

---

### 4.2 展示广告（Display Ads）

#### 层级结构

```
Line Item (Display)
├── type: DISPLAY
├── status: ACTIVE
├── funding_bundle_id: bundle_456
├── goal:
│   └── goal_type: IMPRESSIONS
├── targeting:
│   ├── inventory_source: GAM / EXTERNAL
│   └── creative_type_filtering: [DISPLAY]
└── Creatives:
    ├── Image Creative
    │   ├── name: "Banner Ad"
    │   ├── type: IMAGE
    │   └── media_file: "image_url"
    └── HTML Creative
        ├── name: "Rich Media"
        │   └── type: HTML
        └── html: "<html>...</html>"
```

---

### 4.3 音频广告（Audio Ads）

#### 层级结构

```
Line Item (Audio)
├── type: AUDIO
├── status: ACTIVE
├── funding_bundle_id: bundle_789
├── goal:
│   └── goal_type: IMPRESSIONS
├── targeting:
│   ├── inventory_source: YOUTUBE
│   └── creative_type_filtering: [AUDIO]
└── Creatives:
    └── Audio Creative
        ├── name: "Audio Ad"
        ├── type: AUDIO
        └── media_file: "audio_url"
```

---

### 4.4 广告位类型

| 类型 | 说明 | 官方文档 |
|------|------|----------|
| PMP (Private Marketplace) | 私人 marketplace | [Inventory Source](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/inventorysources) |
| PI (Programmatic Guaranteed) | 程序化保量 | [Inventory Source](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/inventorysources) |
| Open Auction | 公开竞价 | [Inventory Source](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/inventorysources) |
| Video | 视频广告 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| CTV | 连接电视 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| Mobile | 移动广告 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| Audio | 音频广告 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| DOOH | 数字户外 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |

---

## 5. 平台对比速查表

| 功能 | Google Ads | Meta | TikTok | DV360 |
|------|-----------|------|--------|-------|
| **账户层级** | Customer | Business Manager | Business Center | Partner |
| **预算层级** | Campaign Budget | Campaign | Campaign | IO |
| **广告系列** | Campaign | Campaign | Campaign | Line Item |
| **广告组** | Ad Group | Ad Set | Ad Group | Creative |
| **广告** | Ad | Ad | Ad | Creative |
| **出价策略** | MANUAL_CPC/TARGET_CPA/MAXIMIZE_CONVERSIONS/TARGET_ROAS | CPM/CPC/CPV/OCPM | AUTO_BID/MANUAL_BID | CPM/CPV |
| **目标类型** | SEARCH/SHOPPING/VIDEO/DISPLAY/APP/MAX | OUTCOME_LEADS/CONVERSIONS/SALES/AWARENESS | PRODUCT_SALES/LEAD_GENERATION/APP_INSTALLS/BRAND_AWARENESS | VIDEO/DISPLAY/AUDIO |
| **创意素材** | Responsive Search Ad | Link/Video/Image | Video/Image | Video/Image/HTML |
| **定向方式** | Keywords/Audience/Location | Interests/Behaviors/Lookalike | Interests/Behaviors/Placement | Interests/Placement/Geo |

---

## 官方文档来源汇总

| 平台 | 文档链接 |
|------|----------|
| Google Ads API | https://developers.google.com/google-ads/api/docs/start |
| Meta Marketing API | https://developers.facebook.com/docs/marketing-apis/ |
| TikTok Business API | https://developers.tiktok.com/doc/ads-api-overview |
| DV360 API | https://developers.google.com/display-video/api/guides |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v4.0 | 2025-07-25 | 基于官方 API 文档重写，移除虚构字段 |
| v3.0 | 2025-08-15 | 按广告类型组织，添加 Extensions/Placements |
| v2.0 | 2026-08-20 | 详细层级拆解 |
| v1.0 | 2025-08-10 | 初始版本 |
