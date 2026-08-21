# 广告平台层级结构完整指南 v5.0

> 更新时间: 2025-07-25  
> 版本: v5.0（v4.0 + 详细字段解释）
> 数据来源: 
> - [Google Ads API](https://developers.google.com/google-ads/api/docs/start)
> - [Meta Marketing API](https://developers.facebook.com/docs/marketing-apis/)
> - [TikTok Business API](https://developers.tiktok.com/doc/ads-api-overview)
> - [DV360 API](https://developers.google.com/display-video/api/guides)

---

## 目录

1. [Google Ads 层级结构](#1-google-ads-层级结构)
   - 1.1 搜索广告（Search Ads）
   - 1.2 效果最大化广告（Performance Max）
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
6. [字段解释汇总表](#6-字段解释汇总表)
7. [关键字段详解](#7-关键字段详解)
   - 7.1 Google Ads 关键字段详解
     - 7.1.1 出价策略 (Bidding Strategies)
     - 7.1.2 优化目标 (Optimization Goals)
     - 7.1.3 定向方式 (Targeting)
   - 7.2 Meta 关键字段详解
     - 7.2.1 出价策略 (Bidding Strategies)
     - 7.2.2 优化目标 (Optimization Goals)
     - 7.2.3 定向方式 (Targeting)
   - 7.3 TikTok Ads 关键字段详解
     - 7.3.1 出价策略 (Bidding Strategies)
     - 7.3.2 优化目标 (Optimization Goals)
     - 7.3.3 定向方式 (Targeting)
   - 7.4 DV360 关键字段详解
     - 7.4.1 出价策略 (Bidding Strategies)
     - 7.4.2 目标类型 (Goal Types)
     - 7.4.3 库存来源 (Inventory Sources)
     - 7.4.4 广告位类型 (Ad Formats)

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

**字段解释**:

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `advertising_channel_type` | enum | 广告渠道类型，决定广告形态 | `SEARCH` / `SHOPPING` / `VIDEO` / `DISPLAY` / `APP` / `MAX` |
| `status` | enum | 广告系列状态 | `ENABLED` / `PAUSED` / `REMOVED` |
| `bidding_strategy` | string | 出价策略资源名 | `customers/123/biddingStrategies/456` |
| `campaign_budget` | string | 预算资源名 | `customers/123/campaignBudgets/789` |
| `amount_micros` | int64 | 预算金额（微单位，1,000,000 = $1） | `10000000` |
| `delivery_method` | enum | 预算交付方式 | `STANDARD` / `DAILY` / `UNACCELERATED` |
| `cpc_bid_micros` | int64 | 手动CPC出价（微单位） | `250000` (= $0.25) |
| `resource_name` | string | 资源唯一标识符 | `customers/123/campaigns/456` |

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
    │   ├── cpc_bid_micros: 250000 (= $0.25)
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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `advertising_channel_type` | enum | 广告渠道类型 | `SEARCH` |
| `bidding_strategy` | enum | 出价策略类型 | `MANUAL_CPC` / `TARGET_CPA` / `MAXIMIZE_CONVERSIONS` / `TARGET_ROAS` |
| `target_google_search` | bool | 是否投放Google搜索 | `true` / `false` |
| `target_search_partners` | bool | 是否投放搜索合作伙伴 | `true` / `false` |
| `target_network` | bool | 是否投放展示网络 | `true` / `false` |
| `criterion.text` | string | 关键词文本 | `"running shoes"` |
| `criterion.match_type` | enum | 匹配类型 | `BROAD` / `PHRASE` / `EXACT` |
| `prominence` | int32 | 标题突出度（0=不突出，1=高突出） | `0` / `1` |
| `type` | enum | 广告类型 | `RESPONSIVE_SEARCH_AD` / `EXPANDED_TEXT_AD` |

#### 支持的广告附加信息 (Extensions)

| 类型 | 字段 | 数量限制 | 说明 | 官方文档 |
|------|------|----------|------|----------|
| Sitelink | `SitelinkExtensionSetting` | 最多15个 | 附加链接文本，引导用户到特定页面 | [Sitelink](https://developers.google.com/google-ads/api/docs/campaigns/sitelink-extensions) |
| Callout | `CalloutExtensionSetting` | 最多10个 | 补充说明文本（如"免费送货"） | [Callout](https://developers.google.com/google-ads/api/docs/campaigns/callout-extensions) |
| Structured Snippet | `StructuredSnippetExtensionSetting` | 最多5个 | 结构化摘要（如"品牌: Nike, Adidas"） | [Snippet](https://developers.google.com/google-ads/api/docs/campaigns/structured-snippet-extensions) |
| Call | `CallExtensionSetting` | 1个 | 电话扩展，显示联系电话 | [Call](https://developers.google.com/google-ads/api/docs/campaigns/call-extensions) |
| Message | `MessageExtensionSetting` | 1个 | 短信扩展，允许用户发短信 | [Message](https://developers.google.com/google-ads/api/docs/campaigns/message-extensions) |
| Location | `LocationExtensionSetting` | 1个 | 位置扩展，显示店铺地址 | [Location](https://developers.google.com/google-ads/api/docs/campaigns/location-extensions) |
| Price | `PriceExtensionSetting` | 最多8个 | 价格信息，展示产品价格 | [Price](https://developers.google.com/google-ads/api/docs/campaigns/price-extensions) |
| Promotion | `PromotionExtensionSetting` | 2个 | 促销活动信息 | [Promotion](https://developers.google.com/google-ads/api/docs/campaigns/promotion-extensions) |
| App | `AppExtensionSetting` | 1个 | 应用下载扩展 | [App](https://developers.google.com/google-ads/api/docs/campaigns/app-extensions) |
| Affiliate Location | `AffiliateLocationExtensionSetting` | 最多8个 | 经销商位置信息 | [Affiliate](https://developers.google.com/google-ads/api/docs/campaigns/affiliate-location-extensions) |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Search | 搜索结果页 |
| Google Search Partners | 搜索合作伙伴网站 |
| Google Shopping | 购物标签页 |
| Google Play | 应用商店 |

**官方文档来源**: [Search Campaigns](https://developers.google.com/google-ads/api/docs/campaigns/search-campaigns)

---

### 1.2 效果最大化广告（Performance Max）

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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `advertising_channel_type` | enum | 广告渠道类型 | `MAX` |
| `goal_type` | enum | 目标类型 | `SALES_GOAL_TYPE_ECOMMERCE` / `LEAD_GENERATION` |
| `ecommerce_checkout_progress` | double | 电商结账进度（0-1） | `0.5` |
| `bidding_strategy` | enum | 出价策略 | `MAXIMIZE_CONVERSIONS` / `TARGET_ROAS` |
| `custom_segments` | list | 自定义受众段 | `["In-Market - Apparel"]` |
| `final_url_suffix` | string | URL后缀（UTM参数） | `"?source=pmax"` |

#### Asset 类型说明

| Asset 类型 | 说明 | 建议数量 | 官方文档 |
|------------|------|----------|----------|
| Headline | 标题 | 10-15个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Description | 描述 | 4-5个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Image | 图片 | 5-10个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Logo | Logo | 3-5个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Video | 视频 | 1-5个 | [Assets](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| CTA Text | 行动号召文本 | 1个 | [CTA](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Call Out | 补充说明 | 10个 | [Callouts](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Sitelink | 附加链接 | 15个 | [Sitelinks](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#assets) |
| Product Feed Link | 产品Feed链接 | 1个 | [Product Feed](https://developers.google.com/google-ads/api/docs/campaigns/performance-max#product-feed) |

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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `advertising_channel_type` | enum | 广告渠道类型 | `SHOPPING` |
| `merchant_id` | int64 | 商家ID（Merchant Center） | `12345678` |
| `sales_country` | string | 销售国家代码 | `"US"` / `"CN"` / `"GB"` |
| `marketing_language` | string | 营销语言代码 | `"EN"` / `"ZH"` / `"JA"` |
| `priority` | int32 | 广告系列优先级（0-100） | `0` |
| `exclude_offline_store_locations` | bool | 是否排除线下门店 | `false` |
| `bidding_strategy` | enum | 出价策略 | `MANUAL_CPC` / `MAXIMIZE_CONVERSIONS_VALUE` |

#### Product Group 真实字段

| 字段 | 说明 | 示例值 | 官方文档 |
|------|------|--------|----------|
| `all_products` | 根节点，包含所有产品 | `{}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_1` | 产品子类1（Merchant Center定义） | `{"values": ["Electronics"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_2` | 产品子类2 | `{"values": ["Phones"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_3` | 产品子类3 | `{"values": ["Smartphones"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_4` | 产品子类4 | - | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `product_type_5` | 产品子类5 | - | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_0` | 自定义标签0 | `{"values": ["bestseller"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_1` | 自定义标签1 | `{"values": ["clearance"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_2` | 自定义标签2 | `{"values": ["seasonal"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_3` | 自定义标签3 | `{"values": ["premium"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `custom_label_4` | 自定义标签4 | `{"values": ["new_arrival"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `brand` | 品牌 | `{"values": ["Apple", "Samsung"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
| `category` | Google品类 | `{"values": ["4167", "4168"]}` | [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups) |
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
| Sitelink | 附加链接文本 | 最多15个 |
| Callout | 补充说明文本 | 最多10个 |
| Structured Snippet | 结构化摘要 | 最多5个 |
| Price | 价格信息 | 最多8个 |

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
        ├── cpc_bid_micros: 500000 (= $0.50)
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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `advertising_channel_type` | enum | 广告渠道类型 | `VIDEO` |
| `smart_performance` | bool | 是否启用智能优化 | `true` / `false` |
| `video_ad_format_preference` | list | 广告格式偏好 | `[TRUE_VIEW_IN_STREAM]` / `[NON_TRUE_VIEW_IN_STREAM]` |
| `video_id` | string | YouTube 视频ID | `"dQw4w9WgXcQ"` |

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 | 数量限制 |
|------|------|----------|
| Call | 电话扩展 | 1个 |
| Location | 位置扩展 | 1个 |
| Callout | 补充说明 | 10个 |

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
        ├── cpm_bid_micros: 200000 (= $0.20)
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
            │   ├── logos: [{media_file: "logo.png"]}
            │   ├── marketing_images: [{media_file: "image.jpg"]}
            │   └── business_name: "My Store"
            └── final_urls: ["https://example.com"]
```

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `advertising_channel_type` | enum | 广告渠道类型 | `DISPLAY` |
| `geo_target_type` | enum | 地理位置 targeting 类型 | `LOCAL_OR_PRESENT` / `PRESENCE` |
| `target_content_network` | bool | 是否投放内容网络 | `true` / `false` |
| `inference_label` | string | 推断标签（兴趣/受众） | `"Lifestyle & Fashion"` |
| `type` | enum | 广告类型 | `RESPONSIVE_DISPLAY_AD` / `ULTRA_FORMAT_AD` |

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 | 数量限制 |
|------|------|----------|
| Callout | 补充说明 | 10个 |
| Structured Snippet | 结构化摘要 | 5个 |

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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `advertising_channel_type` | enum | 广告渠道类型 | `APP` |
| `app_id` | string | 应用包名（Google Play） | `"com.example.app"` |
| `tracking_url` | string | 追踪URL | `"https://example.com/tracking"` |
| `url_custom_parameters` | map | URL自定义参数 | `{ua: "app"}` |
| `type` | enum | 广告类型 | `APP_AD` |

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 | 数量限制 |
|------|------|----------|
| App | 应用安装 | 1个 |

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
    │   ├── targeting:
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
├── daily_budget: 5000 (= $50)
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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告系列目标 | `OUTCOME_TRAFFIC` / `OUTCOME_CONVERSIONS` / `OUTCOME_SALES` / `OUTCOME_AWARENESS` |
| `status` | enum | 广告系列状态 | `ACTIVE` / `PAUSED` / `DELETED` |
| `daily_budget` | int | 每日预算（单位: 分） | `5000` (= $50) |
| `special_ad_categories` | list | 特殊广告分类（必需） | `[]` / `["HOUSING"，"EMPLOYMENT"，"CREDIT"]` |
| `optimization_goal` | enum | 优化目标 | `LINK_CLICKS` / `IMPRESSIONS` / `THRU_PLAY` |
| `placements` | list | 展示位置 | `["FEED"，"STORIES"，"RIGHT_COLUMN"，"INSTAGRAM_FEED"]` |
| `call_to_action.type` | enum | 行动号召类型 | `LEARN_MORE` / `SHOP_NOW` / `SIGN_UP` / `CONTACT_US` |

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
├── daily_budget: 10000 (= $100)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Conversion Campaign"
        ├── optimization_goal: CONVERSIONS (转化)
        ├── conversion_specs: [{external_event_id: "product_view"}]
        ├── targeting:
        │   └── geo_locations: {countries: ["US", "CA"]}
        └── placements: [FEED，INSTAGRAM_FEED]
            │
            └── Ad
                ├── name: "Conversion Ad"
                ├── creative:
                │   └── link_data:
                │       ├── message: "Shop now and save"
                │       └── call_to_action: {type: "SHOP_NOW"}
                └── run_status: ACTIVE
```

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告系列目标 | `OUTCOME_CONVERSIONS` |
| `conversion_specs` | list | 转化事件规范 | `[{external_event_id: "product_view"}]` |
| `optimization_goal` | enum | 优化目标 | `CONVERSIONS` |

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
├── daily_budget: 8000 (= $80)
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
        └── placements: [FEED，STORIES]
            │
            └── Ad
                ├── name: "Lead Gen Ad"
                ├── creative:
                │   └── lead_gen:
                │       ├── page_id: 页面 ID
                │       └── config: { ... }
                └── run_status: ACTIVE
```

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告系列目标 | `OUTCOME_LEADS` |
| `optimization_goal` | enum | 优化目标 | `LEADS` |
| `lead_gen_config.form_id` | string | 表单ID | `"123456789"` |
| `dynamic_form_config` | object | 动态表单配置 | `{...}` |

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
├── daily_budget: 3000 (= $30)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Engagement Campaign"
        ├── optimization_goal: POST_ENGAGEMENT (帖子互动)
        ├── targeting:
        │   └── geo_locations: {countries: ["US"]}
        └── placements: [FEED，STORIES]
            │
            └── Ad
                ├── name: "Engagement Ad"
                ├── creative:
                │   └── link_data:
                │       └── call_to_action: {type: "LIKE_PAGE"}
                └── run_status: ACTIVE
```

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告系列目标 | `OUTCOME_ENGAGEMENT` |
| `optimization_goal` | enum | 优化目标 | `POST_ENGAGEMENT` / `PAGE_LIKES` |
| `call_to_action.type` | enum | 行动号召类型 | `LIKE_PAGE` / `WATCH_VIDEO` |

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
├── daily_budget: 15000 (= $150)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Catalog Campaign"
        ├── optimization_goal: CONVERSIONS (转化)
        ├── catalog_id: "123456789" (商品目录 ID)
        ├── targeting:
        │   └── geo_locations: {countries: ["US"]}
        └── placements: [FEED，INSTAGRAM_FEED]
            │
            └── Ad
                ├── name: "Catalog Ad"
                ├── creative:
                │   ├── catalog_product_set_id: "123"
                │   └── ad_style: CAROUSEL (轮播)
                └── run_status: ACTIVE
```

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告系列目标 | `OUTCOME_SALES` |
| `catalog_id` | string | 商品目录ID | `"123456789"` |
| `catalog_product_set_id` | string | 商品集合ID | `"123"` |
| `ad_style` | enum | 广告样式 | `CAROUSEL` / `COLLAGE` / `PRODUCT_SET` |

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
├── daily_budget: 5000 (= $50)
└── special_ad_categories: []
    │
    └── Ad Set
        ├── name: "Messaging Campaign"
        ├── optimization_goal: MESSAGES (消息)
        ├── messaging_apps: ["MESSENGER"，"WHATSAPP"]
        ├── targeting:
        │   └── geo_locations: {countries: ["US"]}
        └── placements: [FEED，STORIES]
            │
            └── Ad
                ├── name: "Messaging Ad"
                ├── creative:
                │   └── link_data:
                │       └── call_to_action: {type: "SEND_MESSAGE"}
                └── run_status: ACTIVE
```

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告系列目标 | `OUTCOME_MESSAGES` |
| `optimization_goal` | enum | 优化目标 | `MESSAGES` |
| `messaging_apps` | list | 消息应用 | `["MESSENGER"，"WHATSAPP"]` |
| `call_to_action.type` | enum | 行动号召类型 | `SEND_MESSAGE` / `WHATSAPP` |

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
    │   │   ├── genders: [1, 2] (1=女，2=男)
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
├── daily_budget: 5000 (= $50)
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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告目标 | `PRODUCT_SALES` / `LEAD_GENERATION` / `APP_INSTALLS` / `BRAND_AWARENESS` |
| `status` | enum | 状态 | `ENABLED` / `DISABLED` |
| `daily_budget` | int | 每日预算（单位: 分） | `5000` (= $50) |
| `budget_total` | int | 总预算 | `10000` |
| `bid_type` | enum | 出价类型 | `AUTO_BID` / `MANUAL_BID` |
| `bid_value` | int | 出价金额（单位: 分） | `100` |
| `genders` | list | 性别 | `[1]` = 女，`[2]` = 男，`[1,2]` = 全部 |
| `placements` | list | 展示位置 | `["TikTok"]` |
| `video_id` | string | 视频ID | `"video_123"` |

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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `spark_post_id` | string | 达人帖子ID | `"post_123"` |
| `spark_ad_info.post_id` | string | Spark广告帖子ID | `"post_123"` |

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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告目标 | `LEAD_GENERATION` |
| `form_id` | string | 表单ID | `"form_123"` |
| `lead_form.form_id` | string | 线索表单ID | `"form_123"` |

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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告目标 | `APP_INSTALLS` |
| `app_install.app_id` | string | 应用ID | `"com.example.app"` |

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

#### 字段解释表

| 字段 | 类型 | 说明 | 可选值/示例 |
|------|------|------|-------------|
| `objective` | enum | 广告目标 | `BRAND_AWARENESS` |
| `bid_type` | enum | 出价类型 | `CPM` / `OCPM` |
| `bid_value` | int | 出价金额（单位: 分） | `500` |

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
    │       │       └── creative_type_filtering: [VIDEO，DISPLAY]
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
| PMP (Private Marketplace) | 私人 marketplace，邀请制 | [Inventory Source](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/inventorysources) |
| PI (Programmatic Guaranteed) | 程序化保量，固定价格 | [Inventory Source](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/inventorysources) |
| Open Auction | 公开竞价 | [Inventory Source](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/inventorysources) |
| Video | 视频广告 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| CTV | 连接电视 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| Mobile | 移动广告 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| Audio | 音频广告 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |
| DOOH | 数字户外 | [Line Item](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/lineItems) |

**官方文档来源**: [DV360 API](https://developers.google.com/display-video/api/guides)

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

## 6. 字段解释汇总表

### Google Ads 字段

| 字段 | 所属层级 | 类型 | 说明 | 必填 |
|------|---------|------|------|------|
| `advertising_channel_type` | Campaign | enum | 广告渠道类型 | ✅ |
| `status` | Campaign | enum | 广告系列状态 | ✅ |
| `bidding_strategy` | Campaign | string | 出价策略资源名 | ✅ |
| `campaign_budget` | Campaign | string | 预算资源名 | ✅ |
| `merchant_id` | Campaign | int64 | Merchant Center商家ID | ✅ (Shopping) |
| `sales_country` | Campaign | string | 销售国家代码 | ✅ (Shopping) |
| `app_id` | Campaign | string | 应用包名 | ✅ (App) |
| `name` | Ad Group | string | 广告组名称 | ✅ |
| `cpc_bid_micros` | Ad Group | int64 | 手动CPC出价（微单位） | ❌ |
| `criterion.text` | Keyword | string | 关键词文本 | ✅ |
| `criterion.match_type` | Keyword | enum | 匹配类型 | ✅ |
| `info.headlines` | Ad | list | 标题列表 | ✅ |
| `info.descriptions` | Ad | list | 描述列表 | ✅ |
| `final_urls` | Ad | list | 最终落地页URL | ✅ |
| `all_products` | Product Group | object | 全部产品根节点 | ✅ |
| `product_type_1` | Product Group | object | 产品子类1 | ❌ |
| `brand` | Product Group | object | 品牌 | ❌ |
| `condition` | Product Group | object | 商品条件 | ❌ |

### Meta 字段

| 字段 | 所属层级 | 类型 | 说明 | 必填 |
|------|---------|------|------|------|
| `objective` | Campaign | enum | 广告目标 | ✅ |
| `status` | Campaign | enum | 广告系列状态 | ✅ |
| `daily_budget` | Campaign | int | 每日预算（单位: 分） | ✅ |
| `special_ad_categories` | Campaign | list | 特殊广告分类 | ✅ |
| `optimization_goal` | Ad Set | enum | 优化目标 | ✅ |
| `targeting.geo_locations` | Ad Set | object | 地理位置定向 | ✅ |
| `placements` | Ad Set | list | 展示位置 | ✅ |
| `creative.object_story_spec` | Ad | object | 创意故事规范 | ✅ |
| `call_to_action.type` | Ad | enum | 行动号召类型 | ✅ |

### TikTok 字段

| 字段 | 所属层级 | 类型 | 说明 | 必填 |
|------|---------|------|------|------|
| `objective` | Campaign | enum | 广告目标 | ✅ |
| `status` | Campaign | enum | 状态 | ✅ |
| `daily_budget` | Campaign | int | 每日预算（单位: 分） | ✅ |
| `bid_type` | Ad Group | enum | 出价类型 | ✅ |
| `bid_value` | Ad Group | int | 出价金额（单位: 分） | ❌ |
| `targeting.age_min` | Ad Group | int | 最小年龄 | ❌ |
| `targeting.genders` | Ad Group | list | 性别 | ❌ |
| `video_id` | Creative | string | 视频ID | ✅ |

### DV360 字段

| 字段 | 所属层级 | 类型 | 说明 | 必填 |
|------|---------|------|------|------|
| `name` | IO | string | IO名称 | ✅ |
| `status` | IO | enum | 状态 | ✅ |
| `start_time` | IO | string | 开始时间 | ✅ |
| `end_time` | IO | string | 结束时间 | ✅ |
| `funding_source` | IO | enum | 资金来源 | ✅ |
| `type` | Line Item | enum | 广告类型 | ✅ |
| `goal.goal_type` | Line Item | enum | 目标类型 | ✅ |
| `inventory_source` | Line Item | enum | 库存来源 | ✅ |
| `media_file` | Creative | string | 媒体文件URL | ✅ |

---

## 7. 关键字段详解

本章详细解释各平台的**出价策略**、**优化目标**、**定向方式**等核心概念。

---

### 7.1 Google Ads 关键字段详解

#### 7.1.1 出价策略 (Bidding Strategies)

| 出价策略 | API 字段值 | 说明 | 适用场景 | 官方文档 |
|----------|-----------|------|----------|----------|
| **手动CPC** | `MANUAL_CPC` | 广告主手动设置每次点击最高出价，系统不会自动调整 | 对流量成本有严格控制时 | [Manual CPC](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/manual-cpc) |
| **目标CPA** | `TARGET_CPA` | 系统自动调整出价，力求在长期内达到广告主设定的每次转化成本目标 | 以转化为目标，希望控制单次转化成本 | [Target CPA](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/target-cpa) |
| **最大化转化** | `MAXIMIZE_CONVERSIONS` | 系统在给定预算下自动寻找尽可能多的转化，不限制单次转化成本 | 预算有限，希望获得最大转化量 | [Maximize Conversions](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/maximize-conversions) |
| **目标ROAS** | `TARGET_ROAS` | 系统自动调整出价，力求在长期内达到广告主设定的广告支出回报率目标 | 电商销售，关注ROI | [Target ROAS](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/target-roas) |
| **最大化转化价值** | `MAXIMIZE_CONVERSION_VALUE` | 系统在给定预算下自动寻找最大转化价值，不限制ROI | 预算有限，希望获得最大转化价值 | [Max Conv. Value](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/maximize-conversion-value) |
| **目标展示份额** | `TARGET_IMPRESSION_SHARE` | 系统自动调整出价，力求达到设定的搜索展示份额目标 | 品牌曝光，追求高展示份额 | [Target Impression Share](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/target-impression-share) |
| **目标CPC（增强）** | `ENHANCED_CPC` | 基于手动CPC，系统对高转化概率的点击自动提高出价 | 保留手动控制的同时提升转化 | [eCPC](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/enhanced-cpc) |
| **目标CPM** | `TARGET_CPM` | 按千次展示出价，系统自动调整以达到目标千次展示成本 | 品牌曝光型广告 | [Target CPM](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/target-cpm) |
| **目标CPV** | `TARGET_CPV` | 按观看出价，系统自动调整以达到目标每次观看成本 | 视频广告 | [Target CPV](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/target-cpv) |

**出价策略选择建议**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    出价策略选择决策树                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  你的目标是？                                                    │
│  ├── 转化（销售/线索）→ 看预算和转化数据                          │
│  │   ├── 预算充足，追求转化量 → MAXIMIZE_CONVERSIONS             │
│  │   ├── 控制单次转化成本 → TARGET_CPA                          │
│  │   └── 追求ROI → TARGET_ROAS / MAXIMIZE_CONVERSION_VALUE      │
│  │                                                               │
│  ├── 点击流量 → MANUAL_CPC / ENHANCED_CPC                       │
│  │                                                               │
│  ├── 品牌曝光 → TARGET_IMPRESSION_SHARE / TARGET_CPM            │
│  │                                                               │
│  └── 视频观看 → TARGET_CPV                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**官方文档来源**:
- [Bidding Strategies Overview](https://developers.google.com/google-ads/api/docs/campaigns/bidding-strategies/overview)
- [BiddingStrategyType Enum](https://developers.google.com/google-ads/api/reference/rest/v18/enums/BiddingStrategyType)

---

#### 7.1.2 优化目标 (Optimization Goals)

Google Ads 的优化目标与出价策略紧密相关，不同的广告类型支持不同的优化目标：

| 广告类型 | 支持的优化目标 | 说明 |
|----------|---------------|------|
| **搜索广告** | 转化、点击量、展示份额 | 主要优化关键词匹配后的转化或点击 |
| **Shopping/PMax** | 转化价值、转化率 | 主要优化商品销售额和转化率 |
| **视频广告** | 视频观看、展示、点击 | 主要优化视频观看次数或展示量 |
| **展示广告** | 展示、点击、转化 | 主要优化展示量和点击率 |
| **应用广告** | 安装、应用内转化 | 主要优化应用安装量和后续转化 |

**关键词匹配类型详解**:

| 匹配类型 | API 字段值 | 说明 | 示例 |
|----------|-----------|------|------|
| **广泛匹配** | `BROAD` | 广告可匹配与关键词含义相关的搜索词，包括同义词、相关搜索 | `running shoes` → 可能匹配 "jogging sneakers", "best running footwear" |
| **词组匹配** | `PHRASE` | 广告匹配包含关键词短语的搜索，词序不变，中间可插入其他词 | `"running shoes"` → 匹配 "buy running shoes online"，不匹配 "shoes for running" |
| **精确匹配** | `EXACT` | 广告仅匹配与关键词完全相同或非常接近的搜索词 | `[running shoes]` → 只匹配 "running shoes", "buy running shoes" |

**官方文档来源**: [Keyword Match Types](https://developers.google.com/google-ads/api/docs/campaigns/targeting/keywords)

---

#### 7.1.3 定向方式 (Targeting)

Google Ads 提供多种定向方式，帮助广告主精准触达目标受众：

##### 地理位置定向 (Geo Targeting)

| 字段 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| `targeting_setting.target_restrictions` | enum list | 地理位置定向类型 | `[GEOGRAPHIC]` |
| `geo_target_type` | enum | 地理 targeting 类型 | `LOCAL_OR_PRESENT` (当地或当前位置) / `PRESENCE` (仅当前位置) |

**官方文档来源**: [Geo Targeting](https://developers.google.com/google-ads/api/docs/campaigns/targeting/geo-targeting)

##### 关键词定向 (Keyword Targeting)

| 字段 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| `criterion.text` | string | 关键词文本 | `"running shoes"` |
| `criterion.match_type` | enum | 匹配类型 | `BROAD` / `PHRASE` / `EXACT` |

**官方文档来源**: [Keywords](https://developers.google.com/google-ads/api/docs/campaigns/targeting/keywords)

##### 受众定向 (Audience Targeting)

| 受众类型 | 说明 | 数据来源 |
|----------|------|----------|
| ** remarketing** | 针对网站/App 访问者的再营销 | Google Analytics / Google Ads 转化数据 |
| **In-Market Audiences** | 对特定产品类别有购买意向的用户 | Google 搜索行为和转化数据 |
| **Affinity Audiences** | 基于用户长期兴趣和习惯的受众 | Google 用户数据和行为分析 |
| **Detailed Demographics** | 详细的 demographics 特征 | 用户人口统计数据和生活方式 |
| **Custom Segments** | 自定义受众段 | 广告主上传的受众列表或自定义规则 |

**官方文档来源**: [Audiences](https://developers.google.com/google-ads/api/docs/campaigns/targeting/audiences)

##### 商品定向 (Product Targeting - Shopping/PMax)

| 字段 | 类型 | 说明 |
|------|------|------|
| `product_type_1~5` | object | 产品子类定向（Merchant Center 定义的5层产品类别） |
| `brand` | object | 品牌定向 |
| `category` | object | Google 品类定向 |
| `condition` | object | 商品条件（NEW/USED） |
| `custom_label_0~4` | object | 自定义标签定向（广告主自定义的5个标签） |

**官方文档来源**: [Product Group](https://developers.google.com/google-ads/api/docs/campaigns/shopping#product_groups)

---

### 7.2 Meta 关键字段详解

#### 7.2.1 出价策略 (Bidding Strategies)

| 出价策略 | API 字段值 | 说明 | 适用场景 |
|----------|-----------|------|----------|
| **自动出价** | `AUTO` | Facebook 自动优化出价以获取最佳结果 | 新手或希望 Facebook 自动管理出价 |
| **手动 CPC** | `CPC` | 广告主设置每次点击最高出价 | 控制单次点击成本 |
| **目标 CPA** | `CPA` | 系统自动调整出价以达到目标转化成本 | 追求稳定转化成本 |
| **目标 CPM** | `CPM` | 按千次展示出价 | 品牌曝光 |
| **OCPM** | `OCPM` | 优化千次展示，按转化出价 | 平衡展示和转化 |

**官方文档来源**: [Bidding](https://developers.facebook.com/docs/marketing-apis/bidding)

---

#### 7.2.2 优化目标 (Optimization Goals)

| 优化目标 | API 字段值 | 说明 | 适用场景 |
|----------|-----------|------|----------|
| **链接点击** | `LINK_CLICKS` | 优化用户点击广告链接 | 流量广告、内容推广 |
| **转化** | `CONVERSIONS` | 优化用户完成转化动作 | 销售、注册、下载 |
| **页面浏览** | `PAGE_VIEW` | 优化用户查看页面内容 | 品牌曝光、内容营销 |
| **消息发送** | `MESSAGES` | 优化用户发送消息 | Messenger/WhatsApp 营销 |
| **视频观看** | `THRU_PLAY` / `VIDEO_VIEWS` | 优化视频观看次数 | 视频广告、品牌宣传 |
| **互动** | `POST_ENGAGEMENT` | 优化帖子互动（点赞、评论、分享） | 内容互动 |
| **应用安装** | `APP_INSTALLS` | 优化应用安装 | 移动应用推广 |
| **潜在客户开发** | `LEADS` | 优化线索表单提交 | 销售线索收集 |

**官方文档来源**: [Optimization Goals](https://developers.facebook.com/docs/marketing-apis/optimization-goals)

---

#### 7.2.3 定向方式 (Targeting)

##### 地理位置定向

| 字段 | 类型 | 说明 |
|------|------|------|
| `geo_locations.countries` | list | 国家代码列表，如 `["US", "CA"]` |
| `geo_locations.radius` | object | 半径定向，包含城市和距离 |

**官方文档来源**: [Geo Targeting](https://developers.facebook.com/docs/marketing-apis/targeting#geolocations)

##### 兴趣定向 (Interests)

| 字段 | 类型 | 说明 |
|------|------|------|
| `interests` | list | 兴趣列表，如 `[{name: "Marketing"}]` |
| `interest_id` | int | 兴趣 ID |

**常见兴趣类别**:
- **购物行为**: Online Shopping, Fashion Accessories
- **兴趣爱好**: Photography, Travel, Fitness
- **行业相关**: Digital Marketing, E-commerce

**官方文档来源**: [Interest Targeting](https://developers.facebook.com/docs/marketing-apis/targeting#interests)

##### 行为定向 (Behaviors)

| 字段 | 类型 | 说明 |
|------|------|------|
| `behaviors` | list | 行为列表，如 `[{name: "Digital activity"}]` |
| `behavior_id` | int | 行为 ID |

**常见行为类别**:
- **数字行为**: Digital Actives, Facebook Access
- **购买行为**: Engaged Shoppers, Frequent Travelers
- **设备行为**: Android Device Users, iOS Device Users

**官方文档来源**: [Behavior Targeting](https://developers.facebook.com/docs/marketing-apis/targeting#behaviors)

##### 自定义受众 (Custom Audiences)

| 受众类型 | 说明 |
|----------|------|
| **Customer List** | 广告主上传的客户邮箱列表 |
| **Website Visitors** | 网站访问者（通过 Pixel 追踪） |
| **App Activity** | 应用活动用户 |
| **Engagement** | 与广告/内容互动过的用户 |
| **Instagram Followers** | Instagram 关注者 |

**官方文档来源**: [Custom Audiences](https://developers.facebook.com/docs/marketing-apis/audiences/custom-audiences)

##### 类似受众 (Lookalike Audiences)

| 字段 | 说明 |
|------|------|
| `lookalike_audiences` | 基于种子受众创建的相似人群 |
| `lookalike_spec` | 类似受众规格，包含种子受众 ID 和目标地区 |

**官方文档来源**: [Lookalike Audiences](https://developers.facebook.com/docs/marketing-apis/audiences/lookalike-audiences)

---

### 7.3 TikTok Ads 关键字段详解

#### 7.3.1 出价策略 (Bidding Strategies)

| 出价策略 | API 字段值 | 说明 | 适用场景 |
|----------|-----------|------|----------|
| **自动出价** | `AUTO_BID` | TikTok 自动优化出价以获取最佳效果 | 新手或希望系统自动管理 |
| **手动出价** | `MANUAL_BID` | 广告主手动设置最高出价 | 需要控制单次点击/转化成本 |
| **OCPM** | `OCPM` | 优化千次展示，按转化出价 | 追求转化效果 |
| **CPM** | `CPM` | 按千次展示出价 | 品牌曝光 |
| **CPV** | `CPV` | 按视频观看出价 | 视频广告 |

**官方文档来源**: [Bidding](https://developers.tiktok.com/doc/ads-api-bidding)

---

#### 7.3.2 优化目标 (Optimization Goals)

| 优化目标 | API 字段值 | 说明 | 适用场景 |
|----------|-----------|------|----------|
| **产品销售** | `PRODUCT_SALES` | 优化商品销售转化 | e-commerce 电商 |
| **线索收集** | `LEAD_GENERATION` | 优化表单提交 | 销售线索收集 |
| **应用安装** | `APP_INSTALLS` | 优化应用下载 | 移动应用推广 |
| **品牌认知** | `BRAND_AWARENESS` | 优化品牌曝光 | 品牌建设 |
| **流量引导** | `WEBSITE_TRAFFIC` | 优化网站点击 | 网站引流 |

**官方文档来源**: [Objectives](https://developers.tiktok.com/doc/ads-api-objective)

---

#### 7.3.3 定向方式 (Targeting)

##### 基础定向

| 字段 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| `age_min` | int | 最小年龄 | 13-65 |
| `age_max` | int | 最大年龄 | 13-65 |
| `genders` | list | 性别 | `[1]` = 女，`[2]` = 男，`[1,2]` = 全部 |

##### 兴趣定向

| 字段 | 类型 | 说明 |
|------|------|------|
| `interests` | list | 兴趣标签列表 |
| `interest_ids` | list | 兴趣 ID 列表 |

**常见兴趣类别**:
- **时尚美妆**: Fashion, Beauty, Cosmetics
- **科技数码**: Technology, Gadgets, Gaming
- **生活方式**: Food, Travel, Fitness

##### 行为定向

| 字段 | 类型 | 说明 |
|------|------|------|
| `behaviors` | list | 行为标签列表 |
| `behavior_ids` | list | 行为 ID 列表 |

**常见行为类别**:
- **购物行为**: Online Shoppers, Price Sensitive
- **内容消费**: Video Lovers, Music Fans

##### 自定义定向

| 字段 | 类型 | 说明 |
|------|------|------|
| `custom_audiences` | list | 自定义受众列表 |
| `exclusion_audiences` | list | 排除受众列表 |

**官方文档来源**: [Targeting](https://developers.tiktok.com/doc/ads-api-targeting)

---

### 7.4 DV360 关键字段详解

#### 7.4.1 出价策略 (Bidding Strategies)

| 出价策略 | API 字段值 | 说明 | 适用场景 |
|----------|-----------|------|----------|
| **CPM** | `CPM` | 按千次展示出价 | 品牌曝光、展示广告 |
| **vCPM** | `vCPM` | 按可见展示千次出价 | 强调可见性的品牌广告 |
| **CPV** | `CPV` | 按视频观看出价 | 视频广告 |
| **oCPM** | `oCPM` | 优化千次展示，按转化出价 | 平衡曝光和转化 |

**官方文档来源**: [Bidding](https://developers.google.com/display-video/api/guides/bidding)

---

#### 7.4.2 目标类型 (Goal Types)

| 目标类型 | API 字段值 | 说明 | 适用场景 |
|----------|-----------|------|----------|
| **展示** | `IMPRESSIONS` | 优化展示次数 | 品牌曝光 |
| **转化** | `CONVERSIONS` | 优化转化次数 | 效果广告 |
| **可见性** | `VIEWABILITY` | 优化可见展示比例 | 品牌安全 |
| **点击** | `CLICKS` | 优化点击次数 | 流量获取 |

**官方文档来源**: [Goals](https://developers.google.com/display-video/api/guides/goals)

---

#### 7.4.3 库存来源 (Inventory Sources)

| 库存来源 | API 字段值 | 说明 | 适用场景 |
|----------|-----------|------|----------|
| **YouTube** | `YOUTUBE` | YouTube 视频广告库存 | 视频品牌广告 |
| **GMA** | `GMA` | Google Marketing Ads（原 GAM） | 展示广告 |
| **External** | `EXTERNAL` | 外部需求方平台库存 | 跨平台投放 |

**官方文档来源**: [Inventory Sources](https://developers.google.com/display-video/api/reference/rest/v4/advertisers/inventorysources)

---

#### 7.4.4 广告位类型 (Ad Formats)

| 广告位类型 | 说明 | 适用场景 |
|------------|------|----------|
| **PMP (Private Marketplace)** | 私人 marketplace，邀请制拍卖 | 品牌安全、优质库存 |
| **PI (Programmatic Guaranteed)** | 程序化保量，固定价格购买 | 大品牌、高保量需求 |
| **Open Auction** | 公开竞价 | 追求最大覆盖范围 |
| **Video** | 视频广告位 | YouTube、CTV |
| **CTV** | 连接电视广告位 | 家庭大屏曝光 |
| **Mobile** | 移动广告位 | 移动端触达 |
| **Audio** | 音频广告位 | Spotify、Pandora |
| **DOOH** | 数字户外广告位 | 线下场景触达 |

**官方文档来源**: [Ad Formats](https://developers.google.com/display-video/api/guides/ad-formats)

---

## 版本历史

| 版本 | 日期 | 变更 |  |
|------|------|------|------|
| v5.1 | 2025-07-25 | 新增第7章：关键字段详解（出价策略、优化目标、定向方式） | ⭐ NEW |
| v5.0 | 2025-07-25 | 基于v4.0添加详细字段解释表 |  |
| v4.0 | 2025-07-25 | 基于官方API文档重写，移除虚构字段 |  |
| v3.0 | 2025-08-15 | 按广告类型组织，添加Extensions/Placements |  |
| v2.0 | 2026-08-20 | 详细层级拆解 |  |
| v1.0 | 2025-08-10 | 初始版本 |  |

| 版本 | 日期 | 变更 |
|------|------|------|
| v5.0 | 2025-07-25 | 基于v4.0添加详细字段解释表 |
| v4.0 | 2025-07-25 | 基于官方API文档重写，移除虚构字段 |
| v3.0 | 2025-08-15 | 按广告类型组织，添加Extensions/Placements |
| v2.0 | 2026-08-20 | 详细层级拆解 |
| v1.0 | 2025-08-10 | 初始版本 |
