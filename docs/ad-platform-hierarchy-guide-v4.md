# 广告平台层级结构完整指南 v4.0

> 更新时间: 2026-08-20  
> 覆盖平台: Google Ads / Meta Marketing API / TikTok Ads / DV360  
> 版本: v4.0（简洁清晰版）

---

## 📋 目录

1. [Google Ads 层级结构](#1-google-ads-层级结构)
   - 1.1 搜索广告 (Search Ads)
   - 1.2 性能最大化广告 (PMax)
   - 1.3 购物广告 (Shopping Ads)
   - 1.4 视频广告 (Video Ads)
   - 1.5 展示广告 (Display Ads)
   - 1.6 应用安装广告 (App Ads)
2. [Meta Marketing API 层级结构](#2-meta-marketing-api-层级结构)
   - 2.1 流量广告
   - 2.2 转化广告
   - 2.3 潜在客户广告
   - 2.4 互动广告
   - 2.5 商品广告
   - 2.6 消息广告
3. [TikTok Ads 层级结构](#3-tiktok-ads-层级结构)
   - 3.1 产品销售广告
   - 3.2 Spark Ads
   - 3.3 线索收集广告
   - 3.4 应用推广广告
   - 3.5 品牌广告
4. [DV360 层级结构](#4-dv360-层级结构)
5. [平台对比速查表](#5-平台对比速查表)
6. [附录：快速创建 API 示例](#附录快速创建-api-示例)

---

## 1. Google Ads 层级结构

### 1.1 搜索广告 (Search Ads)

#### 层级结构

```
Customer (客户)
└── Campaign (广告系列)
    ├── Budgets (预算)
    ├── Dates (投放时间)
    ├── Campaign Criteria (定向)
    └── Ad Group (广告组)
        ├── Keywords (关键词)
        ├── Ads (广告)
        │   ├── Headlines (标题)
        │   ├── Descriptions (描述)
        │   ├── URLs (落地页)
        │   └── Assets (附加信息)
        └── Negative Keywords (否定关键词)
```

#### 各层级字段说明

**Customer（客户）**

| 字段 | 说明 |
|------|------|
| `customer_id` | 客户 ID，如 1234567890 |
| `descriptive_name` | 账户描述名称 |
| `currency_code` | 货币代码 (USD/CNY等) |

**Campaign（广告系列）**

| 字段 | 说明 |
|------|------|
| `campaign_id` | 广告系列 ID |
| `name` | 名称 |
| `status` | ENABLED / PAUSED / REMOVED |
| `advertising_channel_type` | SEARCH / SHOPPING / VIDEO / DISPLAY |
| `bidding_strategy` | 出价策略资源名 |
| `campaign_budget` | 预算资源名 |
| `start_date` | 开始日期 |
| `end_date` | 结束日期 |

**Ad Group（广告组）**

| 字段 | 说明 |
|------|------|
| `ad_group_id` | 广告组 ID |
| `name` | 名称 |
| `status` | ENABLED / PAUSED / REMOVED |
| `cpc_bid_micros` | CPC 出价（微单位） |
| `bidding_strategy_override` | 出价策略覆盖 |

**Keywords（关键词）**

| 字段 | 说明 |
|------|------|
| `keyword.text` | 关键词文本 |
| `keyword.match_type` | BROAD / PHRASE / EXACT |
| `cpc_bid_micros` | 关键词出价 |

#### 支持的广告附加信息 (Extensions)

| 类型 | 字段 | 说明 | 可点击 | 数量限制 |
|------|------|------|--------|----------|
| Sitelink | `sitelink_callout_text` | 附加链接文本（最多4个） | ❌ | 最多 15 个 |
| Callout | `callout_text` | 补充说明文本（最多10个） | ❌ | 最多 10 个 |
| Structured Snippet | `values` | 结构化摘要（标题+值列表） | ❌ | 最多 5 个 |
| Call | `phone_number` | 拨打电话 | ✅ | 最多 5 个 |
| Message | `phone_number`, `message_text` | 发送短信 | ✅ | 最多 5 个 |
| Location | `business_name`, `place_id` | 商家位置 | ✅ | 最多 10 个 |
| Affiliate Location | `seller_member_id`, `place_ids` | 经销商定位 | ✅ | 最多 20 个 |
| Price | `title`, `price`, `currency_code` | 价格信息 | ✅ | 最多 8 个 |
| App | `app_id`, `description` | 应用下载 | ✅ | 最多 1 个 |
| Promotion | `promotion_text`, `offer_code` | 促销活动 | ✅ | 最多 8 个 |

#### 展示位置 (Placements)

| 类型 | 说明 | 位置 |
|------|------|------|
| Google Search | 搜索结果页 | 主要位置 |
| Google Search Partners | 合作伙伴网站 | 搜索扩展 |

---

### 1.2 性能最大化广告 (PMax)

#### 层级结构

```
Campaign (Performance Max)
├── advertising_channel_type: MAX
├── campaign_goal_setting:
│   ├── sales_campaign_goal_setting
│   └── lead_campaign_goal_setting
├── bidding_strategy:
│   ├── type: TARGET_ROAS / MAXIMIZE_CONVERSIONS
│   └── target_roas_percentage: 500 (=5x ROAS)
├── asset_group (资产组):
│   ├── name: "Product A - Electronics"
│   ├── status: ENABLED
│   ├── audience_signals:
│   │   └── custom_segments: ["In-Market - Electronics"]
│   ├── product_selection:
│   │   └── product_group:
│   │       ├── product_type_1: {"values": ["Electronics"]}
│   │       ├── product_type_2: {"values": ["Phones"]}
│   │       ├── brand: {"values": ["Apple", "Samsung"]}
│   │       └── custom_label_0: {"values": ["bestseller"]}
│   ├── assets:
│   │   ├── headlines: ["Buy Now", "Best Deals"]
│   │   ├── images: [{"media_file": "image_1.jpg"}]
│   │   └── videos: [{"media_file": "video_1.mp4"}]
│   └── final_url_suffix: "?source=pmax"
└── resource_name: customers/xxx/campaigns/yyy
```

#### Asset 类型说明

| Asset 类型 | 说明 | 数量限制 |
|-----------|------|----------|
| Headline | 标题（必填） | 最多 30 个 |
| Description | 描述 | 最多 30 个 |
| Image | 图片 | 最多 20 个 |
| Logo | Logo | 最多 5 个 |
| Video | 视频 | 最多 20 个 |
| CTA Text | 行动号召文本 | 最多 5 个 |
| Call Out | 推广亮点 | 最多 8 个 |
| Sitelink | 附加链接 | 最多 8 个 |
| Product Feed Link | 产品 feed 链接 | 1 个 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Search | 搜索结果页 |
| Google Display Network | 展示广告网络 |
| YouTube | 视频广告 |
| Gmail | 邮件广告 |
| Google Maps | 地图广告 |
| Shopping Tabs | 购物标签页 |

---

### 1.3 购物广告 (Shopping Ads)

#### 层级结构

```
Campaign (Shopping)
├── advertising_channel_type: SHOPPING
├── shopping_setting:
│   ├── merchant_id: 商家 ID
│   ├── sales_country: 销售国家
│   └── marketing_language: 营销语言
├── product_promotion_link:
│   └── promotion_id: 促销 ID
├── Ad Group
│   └── product_group:
│       ├── all_products: {}  (全部产品)
│       ├── product_type_1: {"values": ["Electronics"]}
│       ├── product_type_2: {"values": ["Phones"]}
│       ├── brand: {"values": ["Apple"]}
│       └── condition: {"values": ["NEW"]}
└── Ads (Responsive Shopping Ad)
    └── product_group 可多层嵌套细分
```

#### Product Group 真实字段

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `product_type_1` | 产品类型层级 1 | Electronics |
| `product_type_2` | 产品类型层级 2 | Phones |
| `product_type_3` | 产品类型层级 3 | Smartphones |
| `product_type_4` | 产品类型层级 4 | iPhone |
| `product_type_5` | 产品类型层级 5 | iPhone 15 |
| `brand` | 品牌 | Apple |
| `category` | Google 分类 | Phones & Accessories |
| `condition` | 新旧程度 | NEW / USED |
| `custom_label_0` | 自定义标签 0 | bestseller |
| `custom_label_1` | 自定义标签 1 | clearance |
| `custom_label_2` | 自定义标签 2 | seasonal |
| `custom_label_3` | 自定义标签 3 | premium |
| `custom_label_4` | 自定义标签 4 | new_arrival |

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

---

### 1.4 视频广告 (Video Ads)

#### 层级结构

```
Campaign (Video)
├── advertising_channel_type: VIDEO
├── video_campaign_setting:
│   └── video_brand_safety_subject: 品牌安全主题
├── Ad Group
│   ├── video_ad:
│   │   ├── headline: 标题
│   │   ├── description: 描述
│   │   ├── advertising_image: 广告图片
│   │   └── final_urls: 落地页 URL
│   └── video:
│       ├── video_id: YouTube 视频 ID
│       └── tracking_url: 追踪 URL
└── Targeting:
    ├── audience_segment: 受众细分
    └── placement: YouTube 频道/视频
```

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 |
|------|------|
| Call | 拨打电话 |
| Location | 商家位置 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| YouTube | 视频播放前/中/后 |
| YouTube Search | 搜索结果视频 |
| YouTube Channels | 指定频道 |
| YouTube Videos | 指定视频 |

---

### 1.5 展示广告 (Display Ads)

#### 层级结构

```
Campaign (Display)
├── advertising_channel_type: DISPLAY
├── settings:
│   └── target_cpm_bid_micros: 目标 CPM 出价
├── Ad Group
│   └── Responsive Display Ad:
│       ├── headlines: 标题列表
│       ├── descriptions: 描述列表
│       ├── logos: Logo 图片
│       ├── marketing_images: 营销图片
│       ├── videos: 视频
│       └── final_urls: 落地页 URL
└── Audience:
    ├── custom_audience: 自定义受众
    └── similar_audience: 相似受众
```

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 |
|------|------|
| Sitelink | 附加链接 |
| Callout | 推广亮点 |
| Structured Snippet | 结构化摘要 |
| Image | 图片扩展 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Display Network | 展示广告网络 |
| YouTube | 视频展示 |
| Gmail | 邮件广告 |
| Google Search | 搜索扩展位 |

---

### 1.6 应用安装广告 (App Ads)

#### 层级结构

```
Campaign (App)
├── advertising_channel_type: APP
├── app_settings:
│   └── app_id: 应用 ID (iOS/Android)
├── Ad Group
│   └── App Campaign:
│       ├── app_title: 应用标题
│       ├── app_url: 应用链接
│       ├── headlines: 标题
│       ├── descriptions: 描述
│       └── images: 图片
└── Bidding:
    └── strategy: TARGET_CPA / MAXIMIZE_CONVERSIONS
```

#### 支持的广告附加信息 (Extensions)

| 类型 | 说明 |
|------|------|
| App | 应用下载 |
| Call | 拨打电话 |
| Location | 商家位置 |

#### 展示位置 (Placements)

| 类型 | 说明 |
|------|------|
| Google Play Store | 应用商店 |
| App Search | 应用搜索 |
| YouTube | 视频展示 |
| Display Network | 展示网络 |

---

## 2. Meta Marketing API 层级结构

### 2.1 流量广告 (Traffic Ads)

#### 层级结构

```
Business Manager (企业号)
└── Ad Account (广告账户)
    └── Campaign (广告系列)
        ├── objective: TRAFFIC / CONVERSIONS / BRAND_AWARENESS
        ├── special_ad_categories: 特殊广告类别
        ├── daily_budget / lifetime_budget: 预算
        ├── start_time / end_time: 投放时间
        └── Ad Set (广告组)
            ├── optimization_goal: 优化目标
            ├── bid_amount: 出价
            ├── targeting: 定向配置
            │   ├── geo_locations: 地理位置
            │   ├── age: 年龄
            │   ├── genders: 性别
            │   └── interests: 兴趣
            ├── placements: 广告位
            │   ├── facebook.feed: Facebook 信息流
            │   ├── instagram.feed: Instagram 信息流
            │   ├── facebook.search: Facebook 搜索
            │   └── instagram.search: Instagram 搜索
            └── Ads (广告)
                ├── creative: 创意
                │   ├── image_hash: 图片哈希
                │   ├── call_to_action: 行动号召
                │   └── object_store_url: 商品目录 URL
                └── preview: 预览链接
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 信息流 |
| Instagram Feed | Instagram 信息流 |
| Facebook Search | Facebook 搜索 |
| Instagram Search | Instagram 搜索 |
| Facebook Right Column | Facebook 右侧栏 |
| Instagram Explore | Instagram 探索页 |
| Facebook Stories | Facebook 动态 |
| Instagram Stories | Instagram 动态 |
| Facebook Reels | Facebook Reels |
| Instagram Reels | Instagram Reels |
| Messenger Story | Messenger 动态 |
| Audience Network | 受众网络 |

---

### 2.2 转化广告 (Conversion Ads)

#### 层级结构

```
Campaign (转化广告)
├── objective: CONVERSIONS
├── conversion_set_id: 转化集 ID
├── Ad Set
│   ├── optimization_goal: LINK_CLICKS / OFFSITE_CONVERSIONS
│   ├── pixel: Pixel ID
│   └── CAPI: Conversion API 配置
└── Ads
    └── Dynamic Creative: 动态创意
        ├── previews[]: 预览列表
        └── suggested_variables: 建议变量
```

#### 广告位 (Placements)

同 2.1 流量广告

---

### 2.3 潜在客户广告 (Lead Ads)

#### 层级结构

```
Campaign (线索收集)
├── objective: LEAD_GENERATION
├── Ad Set
│   └── lead_ads_config:
│       ├── client_form: 客户端表单
│       │   ├── account_mode: BUSINESS_MANAGEMENT / ADVANCED
│       │   ├── is_personalized: 是否个性化
│       │   └── form_content: 表单内容
│       └── privacy_disclosure: 隐私披露
└── Lead Form (原生表单)
    └── fields: 表单字段
        ├── name: 姓名
        ├── email: 邮箱
        └── phone: 电话
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Feed | Facebook 信息流 |
| Instagram Feed | Instagram 信息流 |
| Facebook Stories | Facebook 动态 |
| Instagram Stories | Instagram 动态 |

---

### 2.4 互动广告 (Engagement Ads)

#### 层级结构

```
Campaign (互动广告)
├── objective: ENGAGEMENT
├── special_ad_categories: 特殊广告类别
└── Ad Set
    └── engagement_type:
        ├── LIKE: Facebook 点赞
        ├── MESSAGE: Messenger 消息
        ├── WHATSAPP: WhatsApp 消息
        └── CALL: 拨打电话
```

#### 广告位 (Placements)

同 2.1 流量广告

---

### 2.5 商品广告 (Catalog Ads)

#### 层级结构

```
Campaign (商品广告)
├── objective: CONVERSIONS
├── catalog_id: 商品目录 ID
├── Ad Set
│   └── dynamic_ad_syntax:
│       ├── product_set_id: 商品组 ID
│       ├── ad_format: CAROUSEL / COLLECTION
│       └── headline: 标题模板
└── Ads
    └── Catalog Product: 商品素材
        └── product_data:
            ├── id: 商品 ID
            ├── title: 商品标题
            ├── description: 商品描述
            ├── price: 价格
            └── image_url: 商品图片
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| Facebook Shop | Facebook 商店 |
| Instagram Shop | Instagram 商店 |
| Marketplace | 市场 |
| Facebook Feed | Facebook 信息流 |
| Instagram Feed | Instagram 信息流 |

---

### 2.6 消息广告 (Messaging Ads)

#### 层级结构

```
Campaign (消息广告)
├── objective: MESSAGING
├── messaging_apps: [WHATSAPP, MESSENGER]
└── Ad Set
    └── destination:
        ├── whatsapp_number: WhatsApp 号码
        └── messenger_page_id: Messenger 页面 ID
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| Messenger Inbox | Messenger 收件箱 |
| Messenger Chat | Messenger 聊天 |
| WhatsApp | WhatsApp |
| Instagram Direct | Instagram 私信 |

---

## 3. TikTok Ads 层级结构

### 3.1 产品销售广告 (Product Sales)

#### 层级结构

```
Advertiser (广告主)
└── Campaign (广告系列)
    ├── campaign_id: 广告系列 ID
    ├── campaign_name: 名称
    ├── status: ENABLED / PAUSED / DISABLED
    ├── objective_type: PRODUCT_SALES / LEAD_GENERATION / APP_PROMOTION
    ├── daily_budget: 日预算（分）
    ├── budget_mode: DAY / LIFETIME
    ├── promotion_type: STANDARD / SPARK
    └── Ad Group (广告组)
        ├── adgroup_id: 广告组 ID
        ├── adgroup_name: 名称
        ├── status: ENABLED / PAUSED / DISABLED
        ├── bid_type: AUTO_BID / MANUAL_BID
        ├── bid_amount: 出价金额
        ├── targeting: 受众定向
        │   ├── geo_locations: 地理位置
        │   ├── age: 年龄
        │   ├── gender: 性别
        │   └── interests: 兴趣
        └── Ads (广告)
            ├── ad_id: 广告 ID
            ├── name: 名称
            ├── promoted_type: VIDEO / IMAGE
            └── spark_info: Spark Ads 配置
                ├── video_id: 视频 ID
                └── authorization_status: 授权状态
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok Feed | TikTok 信息流 |
| TikTok Search | TikTok 搜索 |
| TikTok Hadith | TikTok 话题页 |
| TikTok Live | TikTok 直播 |
| TikTok Post | TikTok 帖子页 |
| TikTok Profile | TikTok 个人主页 |

---

### 3.2 Spark Ads (达人原生广告)

#### 层级结构

```
Campaign
├── promotion_type: PROMOTION_TYPE_SPARK
└── spark_info:
    ├── source_type: POST / PROFILE / HASHTAG
    ├── author_id: 达人 ID
    ├── post_id: 帖子 ID
    └── video_id: 视频 ID
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok Feed | 原生信息流 |
| TikTok Search | 搜索结果 |
| TikTok Profile | 达人主页 |

---

### 3.3 线索收集广告 (Lead Generation)

#### 层级结构

```
Campaign
├── objective_type: LEAD_GENERATION
└── lead_form:
    ├── name: 表单名称
    ├── question_list: 问题列表
    │   └── questions:
    │       ├── text: 问题文本
    │       └── type: SHORT_ANSWER / DROPDOWN / CHECKBOX
    └── privacy_policy: 隐私政策 URL
```

#### 广告位 (Placements)

同 3.1 产品销售广告

---

### 3.4 应用推广广告 (App Promotion)

#### 层级结构

```
Campaign
├── objective_type: APP_PROMOTION
└── app_target:
    ├── platform: iOS / ANDROID
    ├── app_id: 应用 ID
    └── deep_link: 深度链接
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| TikTok Feed | 信息流 |
| TikTok Search | 搜索 |
| App Store | 应用商店跳转 |
| Google Play | 应用商店跳转 |

---

### 3.5 品牌广告 (Brand Ads)

#### 层级结构

```
Campaign
├── objective_type: BRAND_AWARENESS
└── brand_kpi:
    ├── brand_lift_study: 品牌提升研究
    └── reach_frequency: 触达频次
```

#### 广告位 (Placements)

| 类型 | 说明 |
|------|------|
| TopView | 开屏广告 |
| Brand Takeover | 品牌 takeover |
| Branded Effects | 品牌滤镜 |
| Branded Hashtag | 品牌话题挑战 |

---

## 4. DV360 层级结构

### 4.1 完整层级架构

```
Partner (合作伙伴)
└── Buyer (广告买家)
    ├── buyer_id: 买家 ID
    └── Campaign (广告系列)
        ├── campaign_id: 系列 ID
        ├── name: 名称
        ├── status: ACTIVE / PAUSED / ENDED
        ├── start_date: 开始日期
        ├── end_date: 结束日期
        └── budget: 预算
    └── Insertion Order (IO / 广告订购单)
        ├── io_id: IO ID
        ├── name: 名称
        ├── status: DRAFT / APPROVING / ACTIVE / PAUSED / ENDED
        ├── budget.total_amount_micros: 总预算（微单位）
        ├── billing_event: CPM / CPC / CPD / CPV
        ├── creative_set_id: 关联创意集
        └── approval_status: PENDING / APPROVED / REJECTED
        └── Line Item (LI / 行项目)
            ├── li_id: 行项目 ID
            ├── name: 名称
            ├── status: ACTIVE / PAUSED / ENDED
            ├── type: PROGRAMMATIC_AGENCY / PROGRAMMATIC_DIRECT / REMARKETING / HOSTED
            ├── budget.total_amount_micros: 预算金额
            ├── billing_event: 计费方式
            ├── bid_amount_micros: 出价金额
            ├── impression_cap: 展示上限
            ├── click_cap: 点击上限
            └── targeting: 定向配置
                ├── audience_segment: 受众细分
                ├── placement.values: 投放位 URL/APP ID
                ├── device_type: DESKTOP / SMARTPHONE / TABLET / ALL
                ├── creative_type: BANNER / VIDEO / NATIVE / HTML5
                └── geo_location.country_codes: 国家代码
            └── Creative Set (创意集)
                └── Creative (创意)
                    ├── creative_id: 创意 ID
                    ├── name: 名称
                    ├── type: BANNER / VIDEO / NATIVE / HTML5
                    ├── file_url: 创意文件 URL
                    ├── dimensions.width: 宽度
                    ├── dimensions.height: 高度
                    └── click_through_url: 点击跳转 URL
```

### 4.2 核心概念说明

#### 层级关系

| 层级 | 说明 |
|------|------|
| Partner | 合作伙伴/媒体方 |
| Buyer | 广告买家/DSP 代理商 |
| Campaign | 广告系列 |
| Flight | 航班期（DV360 特有） |
| Creative Set | 创意集 |
| Creative | 创意素材 |

### 4.3 Line Item 类型说明

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| PROGRAMMATIC_AGENCY | 通过 DSP 进行程序化竞价购买 | 需要多 DSP 聚合、自动化优化 |
| PROGRAMMATIC_DIRECT | 程序化直采（PMP/PI） | 优先购买优质媒体库存 |
| REMARKETING | ремаркетинг投放 | 针对已访问过网站的用户再触达 |
| HOSTED | 托管广告（非程序化） | 直接购买固定位置、固定时间段广告 |

### 4.4 广告位类型

| 类型 | 说明 |
|------|------|
| PMP (Private Marketplace) | 私有交易市场 |
| PI (Programmatic Guaranteed) | 程序化保证购买 |
| Open Auction | 公开竞价 |
| Video | 视频广告位 |
| CTV | 智能电视广告位 |
| Mobile | 移动端广告位 |
| Audio | 音频广告位 |
| DOOH | 数字户外广告位 |

---

## 5. 平台对比速查表

### 5.1 层级结构对比

| 层级 | Google Ads | Meta | TikTok | DV360 |
|------|------------|------|--------|-------|
| **顶级** | Customer ID | Business Manager | Business Center | Partner |
| **第二层** | Campaign Budget | Ad Account | Advertiser | Buyer |
| **第三层** | Campaign | Campaign | Campaign | Flight |
| **第四层** | Ad Group | Ad Set | Ad Group | Creative Set |
| **第五层** | Ad + Keywords/Product Group | Ad + Creative | Ad + Spark Info | Creative |
| **特殊** | Campaign Criteria | Pixel/CAPI | targeting | bid_strategy |

### 5.2 广告类型对比

| 广告类型 | Google Ads | Meta | TikTok | DV360 |
|---------|------------|------|--------|-------|
| 搜索广告 | ✅ Search | ❌ | ❌ | ✅ (搜索显示) |
| 购物广告 | ✅ Shopping + PMax | ✅ Catalog | ✅ Shop | ✅ |
| 视频广告 | ✅ YouTube | ✅ Video | ✅ In-Feed | ✅ |
| 展示广告 | ✅ Display | ✅ Display | ❌ | ✅ |
| Spark Ads | ❌ | ❌ | ✅ 独家 | ❌ |
| 应用安装 | ✅ App | ✅ App | ✅ App | ✅ |
| 消息广告 | ❌ | ✅ 独家 | ❌ | ❌ |
| 线索收集 | ✅ Lead Form | ✅ Instant Form | ✅ Lead Form | ✅ |
| TopView | ❌ | ❌ | ✅ 独家 | ❌ |

### 5.3 核心差异总结

| 平台 | 优势 | 特点 | 适用场景 |
|------|------|------|----------|
| **Google Ads** | 搜索意图驱动、PMax 全渠道自动化、Shopping 独立管理 | Keywords 为核心、Bidding Strategy 丰富、Product Group | 意图明确、转化导向的广告活动 |
| **Meta Marketing API** | 受众定向最灵活、Pixel+CAPI 双轨追踪、消息广告独占 | 兴趣/行为驱动、Instant Form 便捷、Dynamic Ads | 品牌认知、社交互动、精准人群触达 |
| **TikTok Ads** | Spark Ads 原生感强、年轻用户群体、TopView 强曝光 | 视频原生、内容驱动、达人授权机制 | 品牌曝光、年轻人群、电商带货 |
| **DV360** | RTB 实时竞价、跨媒体聚合、程序化购买效率最高 | 支持 DSP 聚合、CDP/DMP 接入、第三方数据 | 大规模程序化购买、跨平台投放、数据驱动优化 |

---

## 附录：快速创建 API 示例

### Google Ads - 创建 Campaign

```python
from google.ads.googleads.client import GoogleAdsClient

# 初始化客户端
client = GoogleAdsClient.load_from_storage('googleads.yaml')

# 创建服务
campaign_service = client.get_service("CampaignService")

# 构建 Campaign 对象
campaign = client.get_type("Campaign")
campaign.name = "Summer 2026 Brand Campaign"
campaign.advertising_channel_type = client.get_type(
    "AdvertisingChannelType"
).SEARCH

# 创建预算
budget = client.get_type("Budget")
budget.resource_name = f"customers/{customer_id}/budgets/{budget_id}"

campaign.budget = budget.resource_name
campaign.status = client.get_type("CampaignStatus").ENABLED

# 发送请求
operation = client.get_type("CampaignOperation")
operation.create.CopyFrom(campaign)
response = campaign_service.mutate_campaigns(
    request=f"customers/{customer_id}",
    operations=[operation]
)
print(f"Created campaign: {response.results[0].resource_name}")
```

---

### Meta - 创建 Campaign

```python
import facebook_business
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.campaign import Campaign

# 初始化
FacebookAdsApi.init(access_token='your_access_token')

# 创建 Campaign
campaign = Campaign(parent_id='act_your_ad_account_id')
campaign[Campaign.Field.name] = 'Summer 2026 Campaign'
campaign[Campaign.Field.objective] = 'TRAFFIC'
campaign[Campaign.Field.special_ad_categories] = []
campaign[Campaign.Field.status] = Campaign.Status.paused

campaign.validate()
campaign.create()
print(f'Campaign ID: {campaign[id]}')
```

---

### TikTok - 创建 Campaign

```python
import requests

# API 端点
url = "https://api-t2.tiktok.com/plus/open/api/v2/ad/group/"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your_access_token"
}

# 创建广告组
payload = {
    "adgroup_name": "Summer Sale",
    "campaign_id": campaign_id,
    "bid_type": "AUTO_BID",
    "bid_amount": 500,  # 5.00 USD
    "daily_budget": 10000,  # 100.00 USD
    "status": "ENABLED"
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

---

### DV360 - 创建 Line Item

```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage('googleads.yaml')

# 创建 Line Item
li = client.get_type("LineItem")
li.name = "Summer Sale - Banner Ads"
li.flight_start_time = "2026-07-01"
li.flight_end_time = "2026-08-31"
li.type = client.get_type("LineItemType").PROGRAMMATIC_AGENCY

# 设置预算
li.total_local_impact_amount_micros = 100000000  # $100

# 发送请求
operation = client.get_type("LineItemOperation")
operation.create.CopyFrom(li)
response = line_item_service.mutate_line_items(
    request=f"customers/{customer_id}",
    operations=[operation]
)
print(f"Created Line Item: {response.results[0].resource_name}")
```

---

## 文档版本信息

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-08-19 | 初始版本 |
| v2.0 | 2026-08-20 | 按广告类型详细拆解 |
| v3.0 | 2026-08-20 | 补充 Extensions 和广告位 |
| v4.0 | 2026-08-20 | 简洁清晰版，修复所有格式问题 |

---

**作者**: Ryan  
**联系方式**: 如有疑问请联系
