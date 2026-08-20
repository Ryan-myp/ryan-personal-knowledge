# 广告平台层级结构完整指南 v2.0

> 更新时间: 2026-08-20  
> 覆盖平台: Google Ads / Meta Marketing API / TikTok Ads / DV360  
> 版本: v2.0（按广告类型详细拆解）

---

## 📋 目录

1. [Google Ads 层级结构](#1-google-ads-层级结构)
   - 1.1 搜索广告（Search Ads）
   - 1.2 性能最大化广告（Performance Max）
   - 1.3 购物广告（Shopping Ads）
   - 1.4 视频广告（Video Ads）
   - 1.5 展示广告（Display Ads）
   - 1.6 应用安装广告（App Ads）
2. [Meta Marketing API 层级结构](#2-meta-marketing-api-层级结构)
   - 2.1 流量广告（Traffic Ads）
   - 2.2 转化广告（Conversion Ads）
   - 2.3 潜在客户广告（Lead Ads）
   - 2.4 互动广告（Engagement Ads）
   - 2.5 商品广告（Catalog/Sales Ads）
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
┌─────────────────────────────────────────────────────────────────────┐
│                         Google Ads Account                          │
│                    (Customer ID / MCC)                              │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    Campaign Budget                            │ │
│  │         (Budget ID, Amount, Sharing Settings)                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                         Campaign                              │ │
│  │  • Name                                                     │ │
│  │  • Advertising Channel Type (SEARCH/SHOPPING/VIDEO/DISPLAY) │ │
│  │  • Status                                                   │ │
│  │  • Bidding Strategy                                         │ │
│  │  • Settings (Targeting, Networks, etc.)                     │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                        Ad Group                               │ │
│  │  • Name                                                     │ │
│  │  • Status                                                   │ │
│  │  • CPC Bid                                                  │ │
│  │  • Bidding Strategy Override                                │ │
│  │  • Target CPA / ROAS                                        │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│              ┌───────────────┼───────────────┐                     │
│              ▼               ▼               ▼                     │
│    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│    │   Ad        │   │  Keyword    │   │  Asset      │           │
│    │  (Creative) │   │ (Criterion) │   │  Group      │           │
│    └─────────────┘   └─────────────┘   └─────────────┘           │
│                              │                                     │
│                              ▼                                     │
│                    ┌─────────────────┐                           │
│                    │  Sitelink Ext.  │                           │
│                    │  Callout Ext.   │                           │
│                    │  Structured Snip│                           │
│                    │  Call Ext.      │                           │
│                    └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 1.1 搜索广告（Search Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Search Campaign                                        │
│  ├── advertising_channel_type: SEARCH                              │
│  ├── status: ENABLED / PAUSED                                      │
│  ├── bidding_strategy: "resource_names/bidding_strategies/xxx"    │
│  │   ├── type: MANUAL_CPC / TARGET_CPA / MAXIMIZE_CONVERSIONS     │
│  ├── campaign_budget: "resource_names/campaign_budgets/xxx"       │
│  │   ├── amount_micros: 10000000 (=$100)                          │
│  ├── settings:                                                     │
│  │   ├── targeting_setting:                                       │
│  │   │   ├── target_restrictions: [Geographic]                    │
│  │   │   └── selection_mode: MUST_INCLUDE_ALL_TARGETS             │
│  │   ├── network_setting:                                         │
│  │   │   ├── target_google_search: true                          │
│  │   │   ├── target_search_partners: false                       │
│  │   │   ├── target_network: false                                │
│  │   └── geo_target_type: LOCAL_OR_PRESENT                        │
│  └── resource_name: customers/xxx/campaigns/yyy                    │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Group: Electronics Products                                    │
│  ├── campaign: "resource_names/campaigns/yyy"                     │
│  ├── name: "Electronics - Summer Sale"                            │
│  ├── status: ENABLED / PAUSED                                     │
│  ├── cpc_bid_micros: 250000 (=$0.25)                             │
│  ├── bidding_strategy_override: "resource_names/bidding_strategies/zzz"
│  └── resource_name: customers/xxx/adGroups/aaa                    │
├─────────────────────────────────────────────────────────────────────┤
│  Keywords (Ad Group Criteria):                                    │
│  ├── criterion:                                                   │
│  │   ├── text: "running shoes"                                    │
│  │   └── match_type: PHRASE                                       │
│  ├── cpc_bid_micros: 300000                                       │
│  └── resource_name: customers/xxx/adGroupCriterions/bbb           │
│                                                                     │
│  Negative Keywords:                                               │
│  ├── criterion:                                                   │
│  │   ├── text: "free"                                             │
│  │   └── match_type: EXACT                                        │
│  └── negative: true                                               │
├─────────────────────────────────────────────────────────────────────┤
│  Ads (Responsive Search Ad):                                     │
│  ├── ad_group: "resource_names/adGroups/aaa"                      │
│  ├── name: "Running Shoes - Summer Sale"                          │
│  ├── status: ENABLED                                              │
│  ├── type: RESPONSIVE_SEARCH_AD                                   │
│  ├── final_urls: ["https://example.com/shoes"]                   │
│  ├── info:                                                        │
│  │   ├── headlines:                                               │
│  │   │   ├── text: "Buy Running Shoes"                           │
│  │   │   ├── text: "Summer Sale 50% Off"                         │
│  │   │   └── prominence: 0 (recommended)                         │
│  │   ├── descriptions:                                            │
│  │   │   ├── text: "Best running shoes for summer"               │
│  │   │   └── text: "Free shipping on orders over $50"            │
│  │   └── path1: "summer-sale"                                     │
│  │   └── path2: "running-shoes"                                   │
│  └── resource_name: customers/xxx/ads/ccc                         │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Extensions:                                                    │
│  ├── Sitelink Extensions:                                          │
│  │   ├── link_text: "Shop Men's"                                 │
│ │   ├── link_url: "https://example.com/men"                      │
│  │   └── sitelink_type: CALLOUT                                   │
│  ├── Callout Extensions:                                           │
│  │   └── text: "Free Shipping"                                    │
│  ├── Call Extensions:                                              │
│  │   └── phone_number: "+1234567890"                              │
│  └── Structured Snippet Extensions:                                │
│      ├── header: "Brands"                                         │
│      └── values: ["Nike", "Adidas", "Puma"]                       │
└─────────────────────────────────────────────────────────────────────┘
```

**搜索广告关键配置**:

| 配置项 | 字段名 | 可选值 | 说明 |
|--------|--------|--------|------|
| 渠道类型 | `advertising_channel_type` | SEARCH | 搜索广告 |
| 出价策略 | `bidding_strategy.type` | MANUAL_CPC/TARGET_CPA/MAXIMIZE_CONVERSIONS/TARGET_ROAS | 智能出价 |
| 预算 | `campaign_budget.amount_micros` | Integer | 微单位，1,000,000 = $1 |
| 关键词匹配 | `keyword.match_type` | BROAD/PHRASE/EXACT | 匹配方式 |
| 广告类型 | `ad.type` | RESPONSIVE_SEARCH_AD/TEXT_AD | 响应式搜索广告 |
| 最终URL | `ad.final_urls` | String[] | 落地页链接 |
| 标题数量 | `ad.info.headlines[]` | 15个 | 建议10-15个 |
| 描述数量 | `ad.info.descriptions[]` | 5个 | 建议4-5个 |

---

### 1.2 性能最大化广告（Performance Max）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Performance Max Campaign                               │
│  ├── advertising_channel_type: MAX                                │
│  ├── status: ENABLED / PAUSED                                     │
│  ├── campaign_goal_setting:                                       │
│  │   ├── sales_campaign_goal_setting:                             │
│  │   │   ├── goal_type: "SALES_GOAL_TYPE_ECOMMERCE"              │
│  │   │   └── ecommerce_checkout_progress: 0.5                    │
│  │   └── lead_campaign_goal_setting:                              │
│  │       └── generate_leads_campaign_goal_setting:                │
│  │           └── lead_form: { ... }                               │
│  ├── bidding_strategy:                                             │
│  │   ├── type: MAXIMIZE_CONVERSIONS / TARGET_ROAS                 │
│  │   ├── target_cpa_micros: 5000000 (=$5)                        │
│  │   └── target_roas_percentage: 400 (=4x ROAS)                   │
│  ├── campaign_budget: "resource_names/campaign_budgets/xxx"       │
│  ├── settings:                                                     │
│  │   ├── location_extension_setting: { enabled: true }            │
│  │   └── audience_signals:                                        │
│  │       ├── custom_segments:                                     │
│  │       │   ├── name: "In-Market - Apparel"                      │
│  │       │   └── membership_reason: "SEO"                         │
│  │       └── customer_match_user_list:                            │
│  │           └── user_list_id: "123456789"                        │
│  ├── asset_group:                                                  │
│  │   ├── name: "Summer Collection"                                │
│  │   ├── status: ENABLED                                        │
│  │   ├── audience_signal:                                         │
│  │   │   └── custom_segments: ["In-Market - Apparel"]            │
│  │   ├── assets:                                                  │
│  │   │   ├── headline: ["Buy Now", "Summer Sale", "50% Off"]     │
│  │   │   ├── description: ["Best prices", "Limited time only"]   │
│  │   │   ├── image: [{"media_file": "image_url_1"}, ...]         │
│  │   │   ├── logo: [{"media_file": "logo_url"}]                  │
│  │   │   └── video: [{"media_file": "video_url"}]                │
│  │   └── final_url_suffix: "?source=pmax"                         │
│  └── resource_name: customers/xxx/campaigns/yyy                    │
└─────────────────────────────────────────────────────────────────────┘
```

**PMax 关键配置**:

| 配置项 | 字段名 | 说明 |
|--------|--------|------|
| 渠道类型 | `advertising_channel_type: MAX` | 性能最大化 |
| 资产组 | `asset_group` | 至少1个，建议2-5个 |
| 受众信号 | `audience_signals` | 建议信号，非强制 |
| 标题 | `assets.headline` | 建议10-15个 |
| 图片 | `assets.image` | 建议5-10个 |
| 视频 | `assets.video` | 建议1-5个 |
| Logo | `assets.logo` | 建议3-5个 |
| 最终URL后缀 | `final_url_suffix` | UTM参数追加 |

---

### 1.3 购物广告（Shopping Ads）层级详解

#### 1.3.1 完整层级架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Google Ads Account                          │
│                    (Merchant Center 关联)                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Campaign Budget (预算)                            │
│  • campaign_budget.resource_name                                   │
│  • amount_micros: 10000000 (=$100)                                 │
│  • explicit_cycle: false (日预算)                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Campaign (广告系列)                          │
│  • advertising_channel_type: SHOPPING                              │
│  • status: ENABLED / PAUSED                                        │
│  • campaign_budget: resource_name                                  │
│  • bidding_strategy: resource_name                                 │
│  • settings.shopping_setting:                                       │
│      ├── merchant_id: 12345678                                     │
│      ├── sales_country: "US"                                       │
│      ├── priority: 0 (0-100)                                       │
│      └── exclude_offline_store_locations: false                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Ad Group (广告组)                             │
│  • campaign: resource_name                                         │
│  • name: "Electronics Products"                                    │
│  • status: ENABLED / PAUSED                                        │
│  • resource_name: customers/xxx/adGroups/aaa                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Product Group / Listing Group (产品分组)            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ALL_PRODUCTS (根节点 - 所有商品)                             │   │
│  │  • ad_group_criterion.type: PRODUCT_GROUP                    │   │
│  │  • all_products: {}                                          │   │
│  │  • cpc_bid_micros: 50000 (=$0.50) - 默认出价                │   │
│  │                                                              │   │
│  │  ├── Product Type 1 = "Electronics"  ← 细分                  │   │
│  │  │   • product_type_1.values: ["Electronics"]               │   │
│  │  │                                                          │   │
│  │  │   ├── Product Type 2 = "Phones"    ← 再细分              │   │
│  │  │   │   • product_type_2.values: ["Phones"]                │   │
│  │  │   │                                                      │   │
│  │  │   │   ├── Brand = "Apple"         ← 叶节点               │   │
│  │  │   │   │   • brand.values: ["Apple"]                      │   │
│  │  │   │   │   • cpc_bid_micros: 100000 (=$1.00)  ← 出价     │   │
│  │  │   │   │                                                  │   │
│  │  │   │   ├── Brand = "Samsung"       ← 叶节点               │   │
│  │  │   │   │   • brand.values: ["Samsung"]                    │   │
│  │  │   │   │   • cpc_bid_micros: 80000 (=$0.80)              │   │
│  │  │   │   └── ...                                            │   │
│  │  │   │                                                      │   │
│  │  │   └── Condition = NEW / USED ← 另一分支                  │   │
│  │  │       • condition.condition_type: NEW                    │   │
│  │  │       • condition.condition_values: ["NEW"]              │   │
│  │  │       • cpc_bid_micros: 70000 (=$0.70)                   │   │
│  │  │                                                          │   │
│  │  ├── Custom Label 0 = "bestseller"   ← 另一细分              │   │
│  │  │   • custom_label_0.values: ["bestseller"]                │   │
│  │  │   • cpc_bid_micros: 150000 (=$1.50)                     │   │
│  │  │                                                          │   │
│  │  ├── Category = "Electronics > Phones"  ← 另一分支           │   │
│  │  │   • category.values: ["4167", "4168"]                   │   │
│  │  │   • cpc_bid_micros: 90000 (=$0.90)                      │   │
│  │  │                                                          │   │
│  │  ├── Gender = "MALE" / "FEMALE"     ← 另一分支              │   │
│  │  │   • gender.values: ["MALE", "FEMALE"]                    │   │
│  │  │   • cpc_bid_micros: 60000 (=$0.60)                      │   │
│  │  │                                                          │   │
│  │  ├── Age Group = "ADULT" / "TEEN"    ← 另一分支              │   │
│  │  │   • age_group.values: ["ADULT"]                          │   │
│  │  │   • cpc_bid_micros: 50000 (=$0.50)                      │   │
│  │  │                                                          │   │
│  │  ├── Color = "Red" / "Blue" / "Black" ← 另一分支             │   │
│  │  │   • color.values: ["Red", "Blue", "Black"]               │   │
│  │  │   • cpc_bid_micros: 55000 (=$0.55)                      │   │
│  │  │                                                          │   │
│  │  └── Size = "S" / "M" / "L" / "XL"  ← 另一分支              │   │
│  │      • size.values: ["S", "M", "L", "XL"]                   │   │
│  │      • cpc_bid_micros: 50000 (=$0.50)                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

#### 1.3.2 Product Group 层级规则

| 规则 | 说明 |
|------|------|
| **根节点** | `ALL_PRODUCTS` 必须存在，是产品分组的根节点 |
| **叶节点出价** | 只有叶节点可以设置 `cpc_bid_micros` |
| **非叶节点** | 仅用于细分，不能设置出价 |
| **嵌套深度** | 最多支持 10 层嵌套细分 |
| **互斥性** | 每个细分维度只能使用一次 |

#### 1.3.3 Product Group 细分维度详解

```python
# 产品分组 (Product Group) 细分维度
product_group = {
    # 根节点 - 所有商品
    "all_products": {},  # 可设置默认 CPC Bid
    
    # 细分维度 1: 产品子类 (Product Type)
    # 来自 Merchant Center 的产品分类，最多 5 层
    "product_type_1": {
        "values": ["Electronics", "Clothing", "Home & Garden"]
    },
    "product_type_2": {
        "values": ["Phones", "Laptops", "Tablets"]
    },
    "product_type_3": {"values": ["Smartphones"]},
    "product_type_4": {"values": ["iPhone"]},
    "product_type_5": {"values": []},  # 空表示不细分
    
    # 细分维度 2: 商品条件
    "condition": {
        "condition_type": "NEW",  # NEW / USED / REFURBISHED
        "values": ["NEW", "REFURBISHED"]
    },
    
    # 细分维度 3: 自定义标签 (最多 5 个)
    # 来自 Merchant Center 的自定义标签，用于业务分组
    "custom_label_0": {"values": ["bestseller", "clearance", "new_arrival"]},
    "custom_label_1": {"values": ["premium", "budget"]},
    "custom_label_2": {"values": ["seasonal", "year_round"]},
    "custom_label_3": {"values": []},
    "custom_label_4": {"values": []},
    
    # 细分维度 4: Google 商品分类
    # 来自 Google 的商品品类树
    "category": {"values": ["4167", "4168"]},  # 品类 ID
    
    # 细分维度 5: 性别
    "gender": {"values": ["MALE", "FEMALE", "UNISEX"]},
    
    # 细分维度 6: 年龄组
    "age_group": {"values": ["ADULT", "CHILD", "TEEN", "BABY"]},
    
    # 细分维度 7: 颜色
    "color": {"values": ["Red", "Blue", "Black", "White"]},
    
    # 细分维度 8: 尺寸
    "size": {"values": ["S", "M", "L", "XL", "XXL"]},
    
    # 细分维度 9: 品牌
    "brand": {"values": ["Apple", "Samsung", "Google"]},
    
    # 细分维度 10: 广告标签
    "ad_group_criterion": {
        "cpc_bid_micros": 50000,  # $0.50
        "bid_modifier": 1.2  # 出价调整系数
    }
}
```

#### 1.3.4 购物广告 API 字段速查

| 层级 | 字段名 | 说明 |
|------|--------|------|
| Campaign | `advertising_channel_type` | SHOPPING |
| Campaign | `settings.shopping_setting.merchant_id` | Merchant Center ID |
| Campaign | `settings.shopping_setting.sales_country` | 销售国家 (ISO 代码) |
| Campaign | `settings.shopping_setting.priority` | 优先级 (0-100) |
| Campaign | `settings.shopping_setting.store_sales_mode` | 本地库存广告模式 |
| Ad Group | `name` | 广告组名称 |
| Ad Group Criterion | `type` | PRODUCT_GROUP |
| Ad Group Criterion | `all_products` | 根节点配置 |
| Ad Group Criterion | `product_type_1~5` | 产品子类细分 |
| Ad Group Criterion | `condition` | 商品条件 (NEW/USED) |
| Ad Group Criterion | `custom_label_0~4` | 自定义标签细分 |
| Ad Group Criterion | `category` | Google 品类细分 |
| Ad Group Criterion | `gender` | 性别细分 |
| Ad Group Criterion | `age_group` | 年龄细分 |
| Ad Group Criterion | `color` | 颜色细分 |
| Ad Group Criterion | `size` | 尺寸细分 |
| Ad Group Criterion | `brand` | 品牌细分 |
| Ad Group Criterion | `cpc_bid_micros` | CPC 出价 (微单位) |
| Ad Group Criterion | `bid_modifier` | 出价调整系数 |

#### 1.3.5 Listing Group vs Product Group

| 术语 | 说明 |
|------|------|
| **Product Group** | API 中使用的术语，指产品分组 |
| **Listing Group** | 控制台 UI 中的术语，与 Product Group 同义 |
| **Ad Group Criterion** | API 中层级，包含 Product Group 配置 |

```
Google Ads API 结构:
Customer → Campaign → Ad Group → AdGroupCriterion (Product Group)

Google Ads UI 结构:
广告系列 → 广告组 → 产品分组 (Listing Group)
```

**Product Group 创建示例 (Python)**:
```python
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.enums import MatchTypeEnum

# 创建 Product Group (Listing Group)
product_group = {
    "ad_group": f"customers/{customer_id}/adGroups/{ad_group_id}",
    "type": "PRODUCT_GROUP",
    "product_group": {
        "all_products": {},  # 根节点
        "cpc_bid_micros": 50000,  # $0.50 默认出价
    }
}

# 创建细分 Product Group
sub_product_group = {
    "ad_group": f"customers/{customer_id}/adGroups/{ad_group_id}",
    "type": "PRODUCT_GROUP",
    "product_group": {
        "product_type_1": {
            "values": ["Electronics"]
        },
        "cpc_bid_micros": 100000,  # $1.00
    }
}

# 创建叶节点 Product Group
leaf_product_group = {
    "ad_group": f"customers/{customer_id}/adGroups/{ad_group_id}",
    "type": "PRODUCT_GROUP",
    "product_group": {
        "brand": {
            "values": ["Apple"]
        },
        "cpc_bid_micros": 150000,  # $1.50
    }
}
```

---

### 1.4 视频广告（Video Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Video Campaign                                          │
│  ├── advertising_channel_type: VIDEO                                │
│  ├── status: ENABLED / PAUSED                                      │
│  ├── bidding_strategy:                                              │
│  │   ├── type: MAXIMIZE_VIDEO_QUERIES / TARGET_CPA                 │
│  │   └── target_cpa_micros: 200000 (=$0.20)                       │
│  ├── campaign_budget: "resource_names/campaign_budgets/xxx"       │
│  ├── settings:                                                      │
│  │   └── video_setting:                                             │
│  │       ├── video_series: "My Campaign"                           │
│  │       └── preferred_content_base: ALL_CONTENT                  │
│  └── resource_name: customers/xxx/campaigns/yyy                    │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Group: Product Showcase                                        │
│  ├── campaign: "resource_names/campaigns/yyy"                     │
│  ├── name: "Product Showcase"                                     │
│  ├── status: ENABLED                                              │
│  ├── advertising_position: PREFERRED                                │
│  ├── content_filter_settings:                                     │
│  │   └── exclusion_criteria: []                                   │
│  └── resource_name: customers/xxx/adGroups/aaa                    │
│                                                                     │
│  Targeting:                                                        │
│  ├── audiences:                                                   │
│  │   └── remarketing_setting:                                     │
│  │       └── list_remarketing_setting:                            │
│  │           └── user_lists: ["123456789"]                        │
│  ├── topics:                                                      │
│  │   └── topic_constants: ["encyclopedia/2157"]                   │
│  └── placements:                                                  │
│      └── video_playback_audiences:                                │
│          └── audience_type: GENERAL_AUDIENCE                      │
├─────────────────────────────────────────────────────────────────────┤
│  Ads:                                                              │
│  ├── TrueView in-stream Ad:                                        │
│  │   ├── name: "Product Demo Video"                               │
│  │   ├── type: TRUEVIEW_IN_STREAM                                 │
│  │   ├── video:                                                   │
│  │   │   └── video_id: "dQw4w9WgXcQ"                             │
│  │   ├── call_to_action_video_action:                             │
│  │   │   └── link_destination_url: "https://example.com"          │
│  │   └── resource_name: customers/xxx/ads/ccc                     │
│  │                                                                   │
│  ├── Non-skippable in-stream (Bumper):                             │
│  │   ├── type: BUMPER_AD                                          │
│  │   └── video: { video_id: "..." }                               │
│  │                                                                   │
│  └── Outstream Ad:                                                 │
│      ├── type: OUTSTREAM                                          │
│      └── creative_sound_setting: ALLOWED                          │
└─────────────────────────────────────────────────────────────────────┘
```

**视频广告关键配置**:

| 配置项 | 字段名 | 可选值 |
|--------|--------|--------|
| 渠道类型 | `advertising_channel_type: VIDEO` | 视频广告 |
| 出价策略 | `bidding_strategy.type` | MAXIMIZE_VIDEO_QUERIES/TARGET_CPA |
| 广告类型 | `ad.type` | TRUEVIEW_IN_STREAM/BUMPER_AD/OUTSTREAM |
| 视频ID | `ad.video.video_id` | YouTube视频ID |
| 创意声音 | `creative_sound_setting` | ALLOWED/DISALLOWED |

---

### 1.5 展示广告（Display Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Display Campaign                                        │
│  ├── advertising_channel_type: DISPLAY                              │
│  ├── status: ENABLED / PAUSED                                      │
│  ├── bidding_strategy:                                              │
│  │   ├── type: MAXIMIZE_CLICKS / TARGET_CPM / ECPM_BIDDING        │
│  │   └── target_cpm_micros: 500000 (=$0.50)                       │
│  ├── campaign_budget: "resource_names/campaign_budgets/xxx"       │
│  ├── settings:                                                      │
│  │   └── visualization_setting:                                   │
│  │       └── display_campaign_setting:                            │
│  │           └── adaptive_choice_mode: DISPLAY_ONLY               │
│  └── resource_name: customers/xxx/campaigns/yyy                    │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Group: Retargeting                                             │
│  ├── campaign: "resource_names/campaigns/yyy"                     │
│  ├── name: "Retargeting - Summer"                                 │
│  ├── status: ENABLED                                              │
│  ├── display_setting:                                              │
│  │   └── adaptive_choice_mode: DISPLAY_ONLY                       │
│  └── resource_name: customers/xxx/adGroups/aaa                    │
│                                                                     │
│  Targeting:                                                        │
│  ├── audiences:                                                   │
│  │   └── custom_segments: ["In-Market - Apparel"]                 │
│  ├── placements:                                                  │
│  │   └── targeted_placement: ["example.com"]                      │
│  └── topic_bidding:                                               │
│      └── bid_modifier: 1.5                                        │
├─────────────────────────────────────────────────────────────────────┤
│  Ads (Responsive Display Ad):                                      │
│  ├── name: "Summer Collection Banner"                              │
│  ├── type: RESPONSIVE_DISPLAY_AD                                  │
│  ├── final_urls: ["https://example.com"]                          │
│  ├── info:                                                        │
│  │   ├── headlines: ["Summer Sale"]                               │
│  │   ├── descriptions: ["Up to 50% off"]                          │
│  │   ├── long_headline: "Summer Collection 2026"                  │
│  │   └── aspect_ratios: LOGO_ONLY / SQUARE / LANDING_PAGE         │
│  ├── images:                                                      │
│  │   └── media_file: "https://example.com/image.jpg"              │
│  ├── logo_images:                                                 │
│  │   └── media_file: "https://example.com/logo.png"               │
│  └── resource_name: customers/xxx/ads/ccc                         │
└─────────────────────────────────────────────────────────────────────┘
```

**展示广告关键配置**:

| 配置项 | 字段名 | 可选值 |
|--------|--------|--------|
| 渠道类型 | `advertising_channel_type: DISPLAY` | 展示广告 |
| 出价策略 | `bidding_strategy.type` | MAXIMIZE_CLICKS/TARGET_CPM/ECPM_BIDDING |
| 广告类型 | `ad.type` | RESPONSIVE_DISPLAY_AD |
| 图片 | `ad.images[].media_file` | PNG/JPG，建议1200x628 |
| Logo | `ad.logo_images[].media_file` | 建议120x120 |
| 长标题 | `ad.info.long_headline` | 最多30字符 |

---

### 1.6 应用安装广告（App Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: App Campaign                                            │
│  ├── advertising_channel_type: APP                                  │
│  ├── status: ENABLED / PAUSED                                      │
│  ├── bidding_strategy:                                              │
│  │   ├── type: MAXIMIZE_INSTALLS / TARGET_CPI                     │
│  │   └── target_cpi_micros: 200000 (=$0.20)                       │
│  ├── campaign_budget: "resource_names/campaign_budgets/xxx"       │
│  ├── settings:                                                      │
│  │   └── app_setting:                                               │
│  │       ├── app_id: "com.example.app"                            │
│  │       ├── app_store: GOOGLE_PLAY / APP_STORE                   │
│  │       └── url_custom_parameters:                                 │
│  │           └── additional_parameters: "?source=gad"             │
│  └── resource_name: customers/xxx/campaigns/yyy                    │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Group: App Install                                              │
│  ├── campaign: "resource_names/campaigns/yyy"                     │
│  ├── name: "App Install - New Users"                              │
│  ├── status: ENABLED                                              │
│  └── resource_name: customers/xxx/adGroups/aaa                    │
│                                                                     │
│  Targeting:                                                        │
│  ├── languages: ["en", "es"]                                      │
│  ├── locations: [{"text_unit": "GEO_LOCATION", "target_type": "PRESENT"}]
│  └── excludes:                                                    │
│      └── app_targeting:                                           │
│          └── exclude_apps: ["com Competitor.app"]                 │
├─────────────────────────────────────────────────────────────────────┤
│  Ads:                                                              │
│  ├── App Preview Video Ad:                                         │
│  │   ├── name: "App Preview Video"                                │
│  │   ├── type: APP_PREVIEW_VIDEO                                  │
│  │   └── app_preview_video_asset:                                 │
│  │       └── youtube_video_id: "dQw4w9WgXcQ"                      │
│  │                                                                   │
│  ├── Image Ad:                                                     │
│  │   ├── name: "App Banner"                                       │
│  │   ├── type: RESPONSIVE_APP_AD                                  │
│  │   └── info: {                                                   │
│  │       ├── headlines: ["Download Now"],                          │
│  │       ├── descriptions: ["Best app for productivity"],          │
│  │       └── images: [{"media_file": "https://..."}]              │
│  │   }                                                            │
│  │                                                                   │
│  └── Text Ad:                                                      │
│      ├── name: "App Text Ad"                                      │
│      ├── type: APP_TEXT_AD                                        │
│      └── info: {                                                   │
│          ├── text1: "Download App",                               │
│          └── text2: "Free & Easy to Use"                          │
│      }                                                            │
└─────────────────────────────────────────────────────────────────────┘
```

**应用广告关键配置**:

| 配置项 | 字段名 | 可选值 |
|--------|--------|--------|
| 渠道类型 | `advertising_channel_type: APP` | 应用广告 |
| App ID | `app_setting.app_id` | com.example.app |
| App Store | `app_setting.app_store` | GOOGLE_PLAY / APP_STORE |
| 出价策略 | `bidding_strategy.type` | MAXIMIZE_INSTALLS / TARGET_CPI |
| 广告类型 | `ad.type` | APP_PREVIEW_VIDEO / RESPONSIVE_APP_AD / APP_TEXT_AD |


---

## 2. Meta Marketing API 层级结构

### 通用层级架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Ad Account                                  │
│                    (Act ID: 2806375919473667)                       │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    Business Manager                            │ │
│  │         (Business ID: 1472239313020616)                        │ │
│  │         Pages / Pixels / Catalogs / Products                   │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                         Campaign                               │ │
│  │  • Name                                                      │ │
│  │  • Objective (SALES/LEADS/TRAFFIC/ENGAGEMENT)                │ │
│  │  • Status (ACTIVE/PAUSED/ARCHIVED)                           │ │
│  │  • Special Ad Categories (NONE/HOUSING/EMPLOYMENT/CREDET)    │ │
│  │  • Daily/Lifetime Budget                                     │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                          Ad Set                                │ │
│  │  • Name                                                      │ │
│  │  • Status                                                    │ │
│  │  • Optimization Guide (CONVERSIONS/LINK_CLICKS/...)          │ │
│  │  • Targeting (Location/Age/Gender/Interests/Behaviors)       │ │
│  │  • Placements (Facebook/Instagram/audience Network)          │ │
│  │  • Budget & Schedule                                         │ │
│  │  • Tracking URLs                                             │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                              │                                     │
│                              ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                            Ad                                  │ │
│  │  • Name                                                      │ │
│  │  • Status                                                    │ │
│  │  • Creative (Image/Video/Carousel/Collection)                │ │
│  │  • Body/Title/Description/CTA                                │ │
│  │  • Tracking URLs                                             │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.1 流量广告（Traffic Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Traffic Campaign                                        │
│  ├── name: "Traffic - Website Visits"                              │
│  ├── status: ACTIVE / PAUSED / DELETED / ARCHIVED                  │
│  ├── objective: TRAFFIC                                            │
│  ├── special_ad_categories: ['NONE']                              │
│  │   ├── 'NONE' - 无特殊类别                                         │
│  │   ├── 'HOUSING' - 住房广告                                         │
│  │   ├── 'EMPLOYMENT' - 就业广告                                     │
│  │   └── 'CREDIT' - 信用广告                                         │
│  ├── daily_budget: 10000  # $100 (单位: 美分)                        │
│  ├── lifetime_budget: null  # 不设总预算                              │
│  ├── promotional_materials: []                                      │
│  └── id: "23851447981100250"                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Set: Traffic - Website                                         │
│  ├── campaign_id: "23851447981100250"                              │
│  ├── name: "Website Traffic - Retargeting"                         │
│  ├── status: ACTIVE / PAUSED / DELETED                             │
│  ├── optimization_guide: LINK_CLICKS  # 优化链接点击                 │
│  ├── billing_event: LINK_CLICKS                                    │
│  ├── promotional_materials: []                                      │
│  ├── targeting:                                                     │
│  │   ├── location_ids: [211671]  # United States                   │
│  │   ├── locations:                                                 │
│  │   │   ├── dynamic: false                                        │
│  │   │   └── values: [{                                           │
│  │   │       ├── key: "location_id",                               │
│  │   │       ├── value: {                                          │
│  │   │           ├── city: "New York",                             │
│  │   │           ├── longitude: -74.0060,                          │
│  │   │           ├── latitude: 40.7128,                            │
│  │   │           ├── radius: 25,  # 25公里                         │
│  │   │           ├── units: "km"                                   │
│  │   │       },                                                    │
│  │   │       └── price: {                                          │
│  │   │           ├── min: 18,                                      │
│  │   │           └── max: 65                                       │
│  │   │       }                                                     │
│  │   │   }]                                                         │
│  │   ├── age_min: 18                                              │
│  │   ├── age_max: 65                                              │
│  │   ├── gender: 1  # 1=MALE, 2=FEMALE, 3=ALL                     │
│  │   ├── niche_audience_deals_enabled: false                      │
│  │   ├── publisher_platforms: ["FACEBOOK", "INSTAGRAM"]            │
│  │   ├── partner_audience_exclusions: []                          │
│  │   └── apps: []                                                  │
│  ├── placement_group:                                               │
│  │   ├── facebook_placements: ["FEED", "STORIES", "REELS"]        │
│  │   ├── instagram_placements: ["FEED", "STORIES", "REELS"]       │
│  │   ├── audience_network_placements: ["audience_network_feed"]   │
│  │   └── facebook_feeds: ["feed", "pages"]                        │
│  ├── daily_budget: 5000  # $50                                     │
│  ├── start_time: "2026-08-20T08:00:00+00:00"                       │
│  ├── stop_time: "2026-09-20T08:00:00+00:00"                        │
│  ├── tracking_urls:                                                 │
│  │   └── standard: "https://example.com/track"                     │
│  ├── url_custom_parameters:                                         │
│  │   └── additional_parameters: "?source=fb&campaign=traffic"      │
│  └── id: "120250788391650251"                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Ad: Summer Traffic Campaign                                       │
│  ├── adset_id: "120250788391650251"                                │
│  ├── name: "Summer Sale - Link Clicks"                             │
│  ├── status: ACTIVE / PAUSED / DELETED                             │
│  ├── body: "Check out our summer collection! Up to 50% off."       │
│  ├── page_id: "123456789"                                          │
│  ├── object_story_spec:                                             │
│  │   ├── link_data: {                                              │
│  │   │   ├── image_hash: "abc123",                                │
│  │   │   ├── call_to_action: {                                    │
│  │   │   │   ├── type: "LEARN_MORE",                              │
│  │   │   │   └── value: {                                         │
│  │   │   │       └── link: "https://example.com/summer-sale"      │
│  │   │   │   }                                                     │
│  │   │   └   └── },                                                │
│  │   │   ├── title: "Summer Sale - Up to 50% Off"                  │
│  │   │   ├── description: "Best deals of the season"               │
│  │   │   └── message: "Shop now and save big!"                     │
│  │   └── }                                                         │
│  ├── creative:                                                      │
│  │   └── story_media_id: "creative_123"                            │
│  └── id: "120250788392070251"                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.2 转化广告（Conversion Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Conversion Campaign                                     │
│  ├── name: "Sales - Purchase"                                      │
│  ├── status: ACTIVE                                               │
│  ├── objective: SALES                                             │
│  ├── special_ad_categories: ['NONE']                              │
│  ├── daily_budget: 50000  # $500                                   │
│  ├── conversion_api_integration_setting:                            │
│  │   └── integration: CAPI_ONLY                                   │
│  └── id: "23851447981100251"                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Set: Purchase Conversion                                       │
│  ├── campaign_id: "23851447981100251"                              │
│  ├── name: "Purchase - High Value"                                 │
│  ├── status: ACTIVE                                               │
│  ├── optimization_guide: CONVERSIONS                               │
│  ├── billing_event: IMPRESSION                                      │
│  ├── attribution_spec: "1d_click"  # 1天点击归因                    │
│  ├── targeting:                                                     │
│  │   ├── location_ids: [211671]                                   │
│  │   ├── age_min: 25                                              │
│  │   ├── age_max: 45                                              │
│  │   ├── gender: 3                                                │
│  │   ├── interests: [                                               │
│  │   │   { "id": "6003109334935", "name": "Shopping" },            │
│  │   │   { "id": "6003109334936", "name": "Online shopping" }      │
│  │   │ ]                                                           │
│  │   ├── behaviors: [                                               │
│  │   │   { "id": "6003109334937", "name": "Engaged Shoppers" }     │
│  │   │ ]                                                           │
│  │   └── custom_audiences: ["956683664786094"]                    │
│  ├── pixel_id: "1234567890"                                        │
│  ├── fb_pixel_id: "1234567890"                                     │
│  ├── conversion_customizations: [                                  │
│  │   {                                                           │
│  │       "aggregation_type": "EVENT_LEVEL",                        │
│  │       "value": 1.0                                              │
│  │   }                                                            │
│  │ ]                                                              │
│  ├── multi_quality_spec:                                           │
│  │   ├── quality_evaluate_setting: OPTIMIZATION_GOAL              │
│  │   ├── quality_bucket_evaluate_setting: LOWEST_COST             │
│  │   └── minimum_quality_ranking: 7                                │
│  ├── daily_budget: 20000  # $200                                   │
│  └── id: "120250788391840251"                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Ad: Product Purchase                                              │
│  ├── adset_id: "120250788391840251"                                │
│  ├── name: "Product A - Purchase"                                 │
│  ├── status: ACTIVE                                               │
│  ├── run_time: {                                                   │
│  │   "end_time": "2026-09-20T08:00:00+00:00"                      │
│  │ }                                                               │
│  ├── body: "Get yours today!"                                     │
│  ├── object_story_spec:                                             │
│  │   ├── page_profile: "123456789"                               │
│  │   ├── link_data: {                                              │
│  │   │   ├── call_to_action: {                                   │
│  │   │   │   └── type: "CHECK_OUT"                               │
│  │   │   └── },                                                   │
│  │   │   └── title: "Product A - Buy Now"                        │
│  │   └── }                                                         │
│  └── id: "120250788392070252"                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.3 潜在客户广告（Lead Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Lead Generation Campaign                                │
│  ├── name: "Lead Gen - Consultation"                               │
│  ├── status: ACTIVE                                               │
│  ├── objective: LEADS                                             │
│  ├── special_ad_categories: ['NONE']                              │
│  ├── daily_budget: 30000  # $300                                   │
│  └── id: "23851447981100252"                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Set: Lead Form                                                 │
│  ├── campaign_id: "23851447981100252"                              │
│  ├── name: "Consultation Request"                                  │
│  ├── status: ACTIVE                                               │
│  ├── optimization_guide: LEAD                                     │
│  ├── billing_event: LEAD                                          │
│  ├── target_cost: 500  # $5 per lead (单位: 美分)                    │
│  ├── daily_budget: 10000  # $100                                   │
│  ├── instant_form_id: "instant_form_123"                          │
│  ├── quick_format_lead_form:                                        │
│  │   ├── title: "Get a Free Quote"                                │
│  │   ├── privacy_policy_url: "https://example.com/privacy"        │
│  │   └── thank_you_id: "thank_you_123"                            │
│  └── id: "120250788391650252"                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Instant Form (广告组内联):                                         │
│  ├── id: "instant_form_123"                                       │
│  ├── title: "Get Your Free Quote"                                 │
│  ├── privacy_policy_url: "https://example.com/privacy"            │
│  ├── invite_transform_url: ""                                     │
│  ├── post_form_share_content: {}                                  │
│  ├── lead_quality_threshold: "EXPERIENCED"                        │
│  ├── questions: [                                                  │
│  │   {                                                           │
│  │       "question_text": "What is your full name?",              │
│  │       "field_type": "FULL_NAME",                               │
│  │       "is_required": true                                      │
│  │   },                                                          │
│  │   {                                                           │
│  │       "question_text": "Email Address",                        │
│  │       "field_type": "EMAIL",                                   │
│  │       "is_required": true                                      │
│  │   },                                                          │
│  │   {                                                           │
│  │       "question_text": "Phone Number",                         │
│  │       "field_type": "PHONE",                                   │
│  │       "is_required": true                                      │
│  │   },                                                          │
│  │   {                                                           │
│  │       "question_text": "What service are you interested in?",  │
│  │       "field_type": "DROPDOWN",                                │
│  │       "options": ["Consultation", "Demo", "Quote"],             │
│  │       "is_required": true                                      │
│  │   }                                                            │
│  │ ]                                                              │
│  ├── dynamic_form_config:                                           │
│  │   ├── dynamic_questions: []                                   │
│  │   └── dynamic_answers: {}                                      │
│  └── lead_param: {                                                 │
│      └── encrypted_id: "xxxxx"                                    │
│  }                                                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Ad: Lead Generation                                               │
│  ├── adset_id: "120250788391650252"                                │
│  ├── name: "Lead Gen Ad"                                          │
│  ├── status: ACTIVE                                               │
│  ├── body: "Fill out the form to get a free consultation!"        │
│  ├── object_story_spec:                                             │
│  │   └── link_data: {                                              │
│  │       └── call_to_action: {                                   │
│  │           └── type: "GENERATE_LEAD"                            │
│  │       }                                                         │
│  │   └── }                                                         │
│  └── id: "120250788392070253"                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.4 互动广告（Engagement Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Engagement Campaign                                     │
│  ├── name: "Post Engagement"                                       │
│  ├── status: ACTIVE                                               │
│  ├── objective: ENGAGEMENT                                        │
│  ├── special_ad_categories: ['NONE']                              │
│  ├── daily_budget: 15000  # $150                                   │
│  └── id: "23851447981100253"                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Set: Post Engagement                                           │
│  ├── campaign_id: "23851447981100253"                              │
│  ├── name: "Facebook Post Engagement"                              │
│  ├── status: ACTIVE                                               │
│  ├── optimization_guide: POST_ENGAGEMENT                           │
│  ├── billing_event: POST_ENGAGEMENT                                │
│  ├── target_cost: 200  # $2 per engagement                         │
│  ├── daily_budget: 5000  # $50                                     │
│  ├── promoted_object:                                               │
│  │   ├── page_id: "123456789"                                     │
│  │   └── post_id: "123456789_987654321"                           │
│  └── id: "120250788391650253"                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Ad: Engagement Ad                                                 │
│  ├── adset_id: "120250788391650253"                                │
│  ├── name: "Engagement Post"                                      │
│  ├── status: ACTIVE                                               │
│  ├── run_time: {                                                   │
│  │   └── end_time: "2026-09-20T08:00:00+00:00"                    │
│  │ }                                                               │
│  └── id: "120250788392070254"                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.5 商品广告（Catalog/Sales Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Catalog Sales Campaign                                  │
│  ├── name: "Product Catalog Sales"                                  │
│  ├── status: ACTIVE                                               │
│  ├── objective: SALES                                             │
│  ├── special_ad_categories: ['NONE']                              │
│  ├── catalog_id: "catalog_123"                                     │
│  ├── daily_budget: 100000  # $1000                                 │
│  └── id: "23851447981100254"                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Set: Dynamic Product Ads                                       │
│  ├── campaign_id: "23851447981100254"                              │
│  ├── name: "Dynamic Products - Retargeting"                        │
│  ├── status: ACTIVE                                               │
│  ├── optimization_guide: CONVERSIONS                               │
│  ├── billing_event: IMPRESSION                                     │
│  ├── target_cost: 500  # $5 per conversion                         │
│  ├── catalog_ad_type: DYNAMIC_PRODUCT_ADS                          │
│  ├── product_set_id: "product_set_123"                             │
│  ├── daily_budget: 50000  # $500                                   │
│  └── id: "120250788391650254"                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Product Set (商品集):                                               │
│  ├── id: "product_set_123"                                         │
│  ├── name: "Electronics Products"                                  │
│  ├── filter:                                                        │
│  │   └── conditions: [                                             │
│  │       {                                                        │
│  │           "field": "product_type",                             │
│  │           "operator": "EQUAL",                                 │
│  │           "value": "Electronics"                                │
│  │       }                                                         │
│  │   ]                                                             │
│  ├── default_filter:                                                │
│  │   └── all_products: true                                       │
│  └── include_product_ids: []                                      │
│                                                                     │
│  Catalog (商品目录):                                                 │
│  ├── id: "catalog_123"                                             │
│  ├── name: "Main Product Catalog"                                  │
│  ├── country: "US"                                                 │
│  ├── language: "en"                                                │
│  ├── currency: "USD"                                               │
│  ├── products_count: 1500                                          │
│  └── product_count_total: 1500                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Ads: Dynamic Ads                                                  │
│  ├── carousel_ad_type: CAROUSEL                                     │
│  ├── carousel_format_style: PRODUCT_CARD                            │
│  ├── adset_id: "120250788391650254"                                │
│  ├── name: "Dynamic Carousel"                                      │
│  ├── status: ACTIVE                                               │
│  ├── creative:                                                      │
│  │   └── product_card_style:                                      │
│  │       └── images: ["product_1.jpg", "product_2.jpg"]            │
│  └── id: "120250788392070255"                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 2.6 消息广告（Messaging Ads）层级详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  Campaign: Messaging Campaign                                      │
│  ├── name: "WhatsApp Messages"                                     │
│  ├── status: ACTIVE                                               │
│  ├── objective: MESSAGES                                          │
│  ├── special_ad_categories: ['NONE']                              │
│  ├── daily_budget: 20000  # $200                                   │
│  └── id: "23851447981100255"                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Ad Set: WhatsApp Messages                                         │
│  ├── campaign_id: "23851447981100255"                              │
│  ├── name: "WhatsApp - Customer Support"                           │
│  ├── status: ACTIVE                                               │
│  ├── optimization_guide: MESSAGES                                  │
│  ├── billing_event: MESSAGE_REPLY                                  │
│  ├── messaging_app_setting:                                        │
│  │   ├── whatsapp_number: "+1234567890"                           │
│  │   ├── instagram_direct_message_setting:                        │
│  │   │   └── instagram_business_id: "123456789"                   │
│  │   └── messenger_setting:                                        │
│  │       └── welcome_message: "Hello! How can we help?"           │
│  ├── target_cost: 100  # $1 per message                            │
│  ├── daily_budget: 10000  # $100                                   │
│  └── id: "120250788391650255"                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Ad: WhatsApp Message                                              │
│  ├── adset_id: "120250788391650255"                                │
│  ├── name: "WhatsApp Promo"                                       │
│  ├── status: ACTIVE                                               │
│  ├── run_time: {                                                   │
│  │   └── end_time: "2026-09-20T08:00:00+00:00"                    │
│  │ }                                                               │
│  └── id: "120250788392070256"                                      │
└─────────────────────────────────────────────────────────────────────┘
```

