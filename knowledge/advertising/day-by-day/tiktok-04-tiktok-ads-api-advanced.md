# TikTok Marketing API — 高级用法深度指南

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级 — API 高级用法全覆盖

---

## 第一部分: 认证体系与OAuth2

### 1.1 TikTok 认证架构

```
TikTok Marketing API 认证采用 OAuth2.0 标准流程:

┌──────────────────────────────────────────────────────────────┐
│              TikTok 认证流程                                    │
│                                                              │
│  1. 创建 TikTok Business Account                              │
│  ├── 注册 TikTok For Business                                  │
│  ├── 创建 Business Center (商务中心)                           │
│  ├── 创建 Marketing API App                                    │
│  └─ 获得 App Key + App Secret                                  │
│                                                              │
│  2. 授权流程 (Authorization Code Flow)                         │
│  ────────────────────────────────────────────────────────────  │
│  ├── 重定向到 TikTok 授权页面                                   │
│  │   https://www.tiktok.com/v1/authorize/                     │
│  │   ?client_key={app_key}                                    │
│  │   &redirect_uri={redirect_uri}                             │
│  │   &response_type=code                                      │
│  │   &scope={permissions}                                     │
│  │   &state={random_state}                                    │
│  │                                                           │
│  ├── 用户授权后返回 authorization_code                         │
│  │   {redirect_uri}?code={auth_code}&state={state}           │
│  │                                                           │
│  └─ 用 code 换取 access_token                                  │
│      POST https://open.tiktokapis.com/v2/oauth/token/        │
│      body:                                                     │
│      {                                                          │
│        "client_key": "{app_key}",                              │
│        "client_secret": "{app_secret}",                        │
│        "grant_type": "authorization_code",                     │
│        "code": "{auth_code}",                                  │
│        "redirect_uri": "{redirect_uri}"                        │
│      }                                                         │
│                                                              │
│  3. Token 类型                                                │
│  ├── Access Token: 短期有效 (默认 1 小时, 可延长到 365 天)      │
│  ├── Refresh Token: 长期有效 (用于刷新 access_token)            │
│  └─ User Access Token: 用户级访问令牌                          │
│                                                              │
│  4. 长期 Token 获取                                            │
│  ├── 请求 access_token 时添加 expire_in=31536000               │
│  │   // 365 天                                                │
│  ├── 或使用 refresh_token 刷新                                  │
│  └─ POST /v2/oauth/token/                                    │
│      body:                                                     │
│      {                                                          │
│        "grant_type": "refresh_token",                          │
│        "refresh_token": "{refresh_token}",                     │
│        "client_key": "{app_key}",                              │
│        "client_secret": "{app_secret}"                         │
│      }                                                         │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 权限范围 (Scopes)

```
TikTok API 权限范围:

广告管理:
├─ user.info.basic: 用户基本信息 (必需)
├─ user.info.profile: 用户个人资料
├─ ad.read: 读取广告数据
├─ ad.write: 创建/修改广告
├─ campaign.read: 读取广告系列
├─ campaign.write: 创建/修改广告系列
├─ adgroup.read: 读取广告组
├─ adgroup.write: 创建/修改广告组
├─ creative.read: 读取创意
├─ creative.write: 创建/修改创意
├─ pixel.read: 读取 Pixel
├─ pixel.write: 创建/修改 Pixel
├─ conversion.read: 读取转化
├─ conversion.write: 创建/修改转化
├─ product.read: 读取商品
├─ product.write: 创建/修改商品
├─ product_feed.read: 读取商品 Feed
├─ product_feed.write: 创建/修改商品 Feed
├─ custom_audience.read: 读取自定义受众
├─ custom_audience.write: 创建/修改自定义受众
├─ insights.read: 读取洞察数据
└─ insights.write: 写入洞察数据

最佳实践:
├─ 最小权限: 只请求需要的
├─ 区分读写权限
├─ 定期审计权限
└─ 及时撤销不需要的权限
```

---

## 第二部分: 核心端点深度使用

### 2.1 Campaign 管理

```
Campaign API 操作:

1. 创建广告系列:

POST /open_api/v3/ad/group/campaign/create/
{
    "access_token": "{token}",
    "request_body": {
        "campaign": {
            "name": "Summer Sale Campaign",
            "objective": "CONVERSION",  // 目标
            "budget_period": "DAILY",   // 预算周期: DAILY/TOTAL
            "budget_amount": 500000000, // 分 (500 美元)
            "campaign_group_id": "",    // 广告系列分组
            "promoted_object": {
                "objective": "OFF_SITE_CONVERSIONS",  // 推广目标
                "website_tracker_ids": [
                    "{pixel_id}"
                ]
            },
            "optimization_goal": "CONVERSION",  // 优化目标
            "conversion_id": "{conversion_spec_id}",  // 转化规格
            "bid_setting": {
                "auto_bid": "OFF",    // OFF=手动, ON=自动
                "cost_type": "OCPM", // OCPM/OCPA/OPTC/CPM/CPC
                "max_cost": 10000,   // 分 (100 美元, OCPA 用)
                "effective_pacing": "STANDARD" // STANDARD/ACCELERATED
            },
            "start_time": "2026-06-10T00:00:00+08:00",
            "end_time": "2026-07-10T00:00:00+08:00",
            "daily_budget": 500000000, // 分
            "schedule_type": "START_AND_END_DATE",
            "ad_serving_effective_pacing": "STANDARD",
            "special_ad_categories": "NONE", // NONE/CREDIT/HOUSING/EMPLOYMENT
            "is_mweb": false,
            "promoted_type": "WEB"
        }
    }
}

2. 更新广告系列:

POST /open_api/v3/ad/group/campaign/update/
{
    "access_token": "{token}",
    "request_body": {
        "campaign_id": "{campaign_id}",
        "campaign": {
            "name": "Updated Campaign",
            "status": "PAUSED"  // ENABLED/DISABLED/PAUSED
        }
    }
}

3. 获取广告系列:

GET /open_api/v3/ad/group/campaign/get/?
  access_token={token}&
  campaign_ids={id1},{id2}

4. 广告系列分页:

GET /open_api/v3/ad/group/campaign/get/?
  access_token={token}&
  page=1&
  page_size=50
// page: 页码 (从 1 开始)
// page_size: 每页数量 (默认 50, 最大 50)
```

### 2.2 Ad Group 管理

```
Ad Group API 操作:

1. 创建广告组:

POST /open_api/v3/ad/group/create/
{
    "access_token": "{token}",
    "request_body": {
        "ad_group": {
            "name": "Target Audience US",
            "campaign_id": "{campaign_id}",
            "daily_budget": 50000000, // 分 (500 美元)
            "start_time": "2026-06-10T00:00:00+08:00",
            "end_time": "2026-07-10T00:00:00+08:00",
            "promoted_object": {
                "objective": "OFF_SITE_CONVERSIONS",
                "type": "WEB",
                "website_tracker_ids": ["{pixel_id}"]
            },
            "optimization_goal": "CONVERSION",
            "conversion_id": "{conversion_spec_id}",
            "bid_setting": {
                "auto_bid": "OFF",
                "cost_type": "OCPM",
                "max_cost": 50000, // 500 美元
                "effective_pacing": "STANDARD"
            },
            "targeting": {
                "gender": 1,  // 0=ALL, 1=FEMALE, 2=MALE
                "age_min": 18,
                "age_max": 65,
                "countries": ["US", "CA"],
                "regions": [],
                "cities": [],
                "platforms": ["TikTok"],  // TikTok/YouTube/Others
                "languages": ["EN"],
                "exclude_purposes": ["PURCHASE"],
                "gender_type": "ALL",
                "age_ranges": ["18-20", "21-24", "25-34"],
                "interests": [
                    {
                        "type": "INTEREST",
                        "id": "{interest_id}",
                        "name": "Shopping"
                    }
                ],
                "behaviors": [],
                "demographics": [],
                "custom_audiences": [
                    {
                        "id": "{custom_audience_id}",
                        "name": "My Retargeting List"
                    }
                ],
                "exclude_custom_audiences": [],
                "location_type": "ALL",
                "radius": 10,
                "store_type": "ALL",
                "store_id": "",
                "placement_type": "ALL",
                "placement_value": "",
                "connection_type": "ALL",
                "device_brand": "ALL",
                "device_model": "ALL",
                "os": "ALL",
                "os_version": "ALL"
            },
            "pacing": "STANDARD",  // STANDARD/ACCELERATED
            "frequency_capping": {
                "frequency_type": "AD_GROUP",  // AD/CAMPAIGN/AD_GROUP
                "frequency_duration": 7,  // 天数
                "frequency_max": 5  // 最大展示次数
            },
            "delivery_pool": "GLOBAL",  // GLOBAL/ADVANCED
            "delivery_adjustment_status": "ENABLE",  // ENABLE/DISABLE
            "effective_pacing": "STANDARD"
        }
    }
}

2. 定向高级用法:

- 动态半径定位:
  "targeting": {
    "countries": ["US"],
    "radius": 10,
    "location_type": "DYNAMIC_ZONE",
    "dynamic_zones": [
      {
        "name": "New York Zone",
        "lat": 40.7128,
        "lng": -74.0060,
        "radius": 10
      }
    ]
  }

- 排除定向:
  "targeting": {
    "exclude_custom_audiences": ["{exclude_id}"],
    "exclude_interests": [
      {
        "type": "INTEREST",
        "id": "{exclude_interest_id}"
      }
    ]
  }

- 设备定向:
  "targeting": {
    "device_brand": "ALL",  // ALL/Apple/Android
    "device_model": "ALL",  // 具体型号
    "os": "ALL",  // ALL/iOS/Android
    "os_version": "ALL",
    "connection_type": "ALL"  // ALL/WIFI/4G/5G
  }
```

### 2.3 Ad (广告) 管理

```
Ad API 操作:

1. 创建视频广告:

POST /open_api/v3/ad/create/
{
    "access_token": "{token}",
    "request_body": {
        "ad": {
            "name": "Summer Video Ad",
            "adgroup_id": "{adgroup_id}",
            "run_status": "PAUSED",  // ENABLED/DISABLED/PAUSED
            "review_status": "PENDING",  // 审核状态
            "creative": {
                "creative_type": "VIDEO",  // VIDEO/IMAGE/CAROUSEL
                "video": {
                    "video_id": "{video_id}",
                    "video_name": "Summer Video"
                },
                "primary_text": "Shop our summer collection!",
                "headline": "Up to 50% off",
                "description": "Limited time offer",
                "call_to_action": {
                    "type": "SHOP_NOW",  // APPLY_NOW/BOOK_NOW/INSTALL/LEARN_MORE/SHOP_NOW/SIGN_UP/USE_APP/VIEW_OFFER
                    "value": {
                        "link": "https://example.com/shop",
                        "mweb_link": "https://m.example.com/shop"
                    }
                },
                "text_type": "ENGAGE",  // ENGAGE/SELL
                "image_type": "NONE",
                "image_id": "",
                "image_urls": [],
                "product_set_id": "",
                "product_item_ids": [],
                "messenger_extension": false,
                "messenger_extension_setup": {
                    "has_messenger_extension": false
                },
                "object_type": "WEB",
                "tracking_url": [
                    {
                        "type": "CLICK_THROUGH",
                        "url": "https://tracking.com"
                    }
                ]
            }
        }
    }
}

2. 创建图片广告:

POST /open_api/v3/ad/create/
{
    "access_token": "{token}",
    "request_body": {
        "ad": {
            "name": "Image Ad",
            "adgroup_id": "{adgroup_id}",
            "run_status": "PAUSED",
            "creative": {
                "creative_type": "IMAGE",
                "image": {
                    "image_url": "https://example.com/image.jpg",
                    "image_type": "RATIO_16_9"  // RATIO_16_9/RATIO_1_1/RATIO_4_5/RATIO_9_16
                },
                "primary_text": "Check out our products!",
                "headline": "New Arrivals",
                "description": "Shop now",
                "call_to_action": {
                    "type": "SHOP_NOW",
                    "value": {
                        "link": "https://example.com"
                    }
                }
            }
        }
    }
}

3. 创建轮播广告:

POST /open_api/v3/ad/create/
{
    "access_token": "{token}",
    "request_body": {
        "ad": {
            "name": "Carousel Ad",
            "adgroup_id": "{adgroup_id}",
            "run_status": "PAUSED",
            "creative": {
                "creative_type": "CAROUSEL",
                "carousel_cards": [
                    {
                        "image_url": "https://example.com/card1.jpg",
                        "title": "Product 1",
                        "description": "Description 1",
                        "link": "https://example.com/product1"
                    },
                    {
                        "image_url": "https://example.com/card2.jpg",
                        "title": "Product 2",
                        "description": "Description 2",
                        "link": "https://example.com/product2"
                    }
                ],
                "primary_text": "Our Products",
                "call_to_action": {
                    "type": "SHOP_NOW",
                    "value": {
                        "link": "https://example.com"
                    }
                }
            }
        }
    }
}
```

---

## 第三部分: 创意管理

### 3.1 Creative API

```
创意管理 API:

1. 上传视频创意:

POST /open_api/v3/creative/video/upload/
{
    "access_token": "{token}",
    "request_body": {
        "video": {
            "name": "New Video",
            "video_file": {  // 通过 multipart/form-data 上传
                "file_name": "video.mp4",
                "file_data": "base64_encoded_data"
            },
            "video_type": "VIDEO",  // VIDEO/THUMBNAIL
            "description": "Video description",
            "cover_image_url": "https://example.com/cover.jpg"
        }
    }
}

2. 上传图片创意:

POST /open_api/v3/creative/image/upload/
{
    "access_token": "{token}",
    "request_body": {
        "image": {
            "name": "New Image",
            "image_file": {
                "file_name": "image.jpg",
                "file_data": "base64_encoded_data"
            }
        }
    }
}

3. 获取创意列表:

GET /open_api/v3/creative/get/?
  access_token={token}&
  creative_ids={id1},{id2}&
  creative_types=VIDEO,IMAGE

4. 创意分页:

GET /open_api/v3/creative/get/?
  access_token={token}&
  page=1&
  page_size=50
```

### 3.2 Spark Ads API

```
Spark Ads 通过 Creative API 创建:

POST /open_api/v3/ad/create/
{
    "access_token": "{token}",
    "request_body": {
        "ad": {
            "name": "Spark Ad",
            "adgroup_id": "{adgroup_id}",
            "run_status": "PAUSED",
            "creative": {
                "creative_type": "SPARK",  // 特殊类型
                "spark_id": "{organic_video_id}",  // 有机视频 ID
                "primary_text": "Check out this!",
                "headline": "Amazing Product",
                "call_to_action": {
                    "type": "SHOP_NOW",
                    "value": {
                        "link": "https://example.com"
                    }
                }
            }
        }
    }
}

获取 Spark Ads 信息:

GET /open_api/v3/creative/spark/get/?
  access_token={token}&
  spark_ids={organic_video_id}
```

---

## 第四部分: 转化追踪 API

### 4.1 Pixel 管理

```
Pixel API 操作:

1. 创建 Pixel:

POST /open_api/v3/pixel/create/
{
    "access_token": "{token}",
    "request_body": {
        "name": "My Website Pixel",
        "object_type": "WEBSITE",
        "tracking_url": "https://tracking.example.com"
    }
}

2. 获取 Pixel 信息:

GET /open_api/v3/pixel/get/?
  access_token={token}&
  pixel_ids={pixel_id}

3. 更新 Pixel:

POST /open_api/v3/pixel/update/
{
    "access_token": "{token}",
    "request_body": {
        "pixel_id": "{pixel_id}",
        "name": "Updated Pixel Name"
    }
}
```

### 4.2 Conversion API

```
转化 API 操作:

1. 创建自定义转化:

POST /open_api/v3/conversion/create/
{
    "access_token": "{token}",
    "request_body": {
        "name": "Purchase Event",
        "status": "ACTIVE",
        "object_type": "WEBSITE",
        "conversion_type": "PURCHASE",
        "pixel_ids": ["{pixel_id}"],
        "event_matching_options": {
            "em": ["hashed_email@example.com"],
            "ph": ["hashed_phone"],
            "external_id": "user_123"
        },
        "default_landing_url": "https://example.com/thank-you",
        "url_custom_parameters": ["_event_id", "_fbp"]
    }
}

2. 获取转化列表:

GET /open_api/v3/conversion/get/?
  access_token={token}&
  conversion_ids={conversion_id}

3. 发送转化事件 (Server-Side):

POST /open_api/v3/conversion/log/
{
    "access_token": "{token}",
    "request_body": {
        "conversion_id": "{conversion_id}",
        "external_conversion_id": "order_123",
        "event_time": 1717929600,
        "event_name": "PURCHASE",
        "event_source_url": "https://example.com",
        "user_data": {
            "em": ["hashed_email@example.com"],
            "ph": ["hashed_phone"],
            "external_id": "user_123"
        },
        "custom_data": {
            "value": 100.00,
            "currency": "USD",
            "content_ids": ["product_123"],
            "num_items": 2
        }
    }
}
```

### 4.3 标准事件

```
TikTok 标准转化事件:

┌──────────────────────────────────────────────────────────────┐
│              TikTok 标准事件                                    │
│                                                              │
│  电商:                                                        │
│  ├── ADD_TO_CART — 加入购物车                                  │
│  ├── ADD_TO_WISHLIST — 加入愿望单                              │
│  ├── CHECKOUT_START — 开始结算                                  │
│  ├── PURCHASE — 购买                                          │
│  ├── PRODUCT_VIEWED — 查看产品                                  │
│  └── SEARCH — 搜索                                            │
│                                                              │
│  注册/线索:                                                    │
│  ├── COMPLETE_REGISTRATION — 完成注册                           │
│  ├── SUBSCRIBE — 订阅                                          │
│  ├── LEAD — 线索                                              │
│  └── APPLICATION_SUBMITTED — 提交申请                           │
│                                                              │
│  应用:                                                        │
│  ├── APP_INSTALL — 应用安装                                     │
│  ├── APP_OPEN — 打开应用                                        │
│  ├── GAME_STARTED — 开始游戏                                    │
│  ├── LEVEL_ACHIEVED — 达成关卡                                  │
│  └── AD_VIEWED — 观看广告                                     │
│                                                              │
│  内容:                                                        │
│  ├── CONTENT_VIEWED — 查看内容                                  │
│  ├── VIDEO_VIEWED — 观看视频                                    │
│  ├── TIME_SPENT — 使用时间                                      │
│  └── BOOKING_COMPLETED — 完成预订                               │
│                                                              │
│  自定义:                                                       │
│  └── CUSTOM_EVENT — 自定义事件                                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 第五部分: 商品 Feed 管理

### 5.1 Product Feed API

```
商品 Feed 管理:

1. 创建商品目录:

POST /open_api/v3/product_feed/create/
{
    "access_token": "{token}",
    "request_body": {
        "name": "Summer Products",
        "country": "US",
        "currency": "USD",
        "feed_type": "PRODUCT",
        "scheduled_feed_update": {
            "frequency": "DAILY",  // DAILY/ONCE/ON_DEMAND
            "time": "02:00"
        }
    }
}

2. 更新商品:

POST /open_api/v3/product/update/
{
    "access_token": "{token}",
    "request_body": {
        "id": "product_123",
        "title": "Summer Dress",
        "description": "Beautiful summer dress",
        "link": "https://example.com/summer-dress",
        "image_link": "https://example.com/dress.jpg",
        "price": "49.99",
        "currency": "USD",
        "availability": "in_stock",  // in_stock/out_of_stock/preorder
        "condition": "new",  // new/used/refurbished
        "brand": "MyBrand",
        "category": "Clothing",
        "gender": "female",
        "age_group": "adult",
        "size": "M",
        "color": "red",
        "item_group_id": "dress_group_1",
        "custom_label_0": "bestseller"
    }
}

3. 批量上传商品:

POST /open_api/v3/product/batch_create/
{
    "access_token": "{token}",
    "request_body": {
        "items": [
            {
                "id": "product_1",
                "title": "Product 1",
                "link": "https://.../1",
                "image_link": "https://.../1.jpg",
                "price": "29.99",
                "currency": "USD",
                "availability": "in_stock"
            },
            {
                "id": "product_2",
                "title": "Product 2",
                "link": "https://.../2",
                "image_link": "https://.../2.jpg",
                "price": "39.99",
                "currency": "USD",
                "availability": "in_stock"
            }
        ]
    }
}
```

---

## 第六部分: 洞察数据 (Insights)

### 6.1 Insights API

```
获取洞察数据:

GET /open_api/v3/report/insights/?
  access_token={token}&
  page=1&
  page_size=50&
  report_spec=[
    {
      "report_action": "GET",
      "granularity": "DAY",  // REALTIME/DAY/HOUR/WEEK/MONTH
      "aggregation": "ALL",  // ALL/DAY/HOUR/WEEK/MONTH
      "metrics": [
        "VIDEO_3S_PLAYS",
        "VIDEO_AVG_TIME_WATCHED",
        "CLICKS",
        "IMPRESSIONS",
        "SPEND",
        "PURCHASES",
        "PURCHASE_VALUE",
        "CPM",
        "CPC",
        "CTR",
        "CPA",
        "ROAS"
      ],
      "date_preset": "LAST_7_DAYS",  // TODAY/YESTERDAY/LAST_7_DAYS/LAST_30_DAYS/THIS_MONTH/LAST_MONTH/LIFETIME
      "time_range": {
        "since": "2026-05-01",
        "until": "2026-06-01"
      },
      "filters": [
        {
          "field": "campaign_status",
          "operator": "EQUALS",  // EQUALS/NOT_EQUALS/CONTAINS/NOT_CONTAINS
          "values": ["ENABLED"]
        },
        {
          "field": "country",
          "operator": "CONTAINS",
          "values": ["US"]
        }
      ],
      "breakdowns": [
        "AGE",
        "GENDER",
        "COUNTRY",
        "PLATFORM",
        "AGE_RANGE",
        "DEVICE_OS"
      ],
      "sorts": [
        {
          "field": "SPEND",
          "order": "DESC"  // ASC/DESC
        }
      ]
    }
  ]

高级用法:

1. 实时报告:
   "granularity": "REALTIME",
   "aggregation": "ALL"

2. 按多个维度细分:
   "breakdowns": ["AGE", "GENDER", "COUNTRY"]

3. 排序:
   "sorts": [{"field": "SPEND", "order": "DESC"}]
```

---

## 第七部分: 错误处理与速率限制

### 7.1 错误码

```
TikTok API 错误码:

┌──────────────────────────────────────────────────────────────┐
│              TikTok API 错误码                                 │
│                                                              │
│  认证错误:                                                   │
│  ├── 1000: Invalid access token                              │
│  ├── 1001: Token expired                                    │
│  ├── 1002: Token revoked                                    │
│  └─ 1003: Insufficient permission                            │
│                                                              │
│  验证错误:                                                   │
│  ├── 2000: Invalid parameter                                 │
│  ├── 2001: Required parameter missing                        │
│  ├── 2002: Invalid value for parameter                       │
│  └─ 2003: Invalid request body                               │
│                                                              │
│  业务错误:                                                   │
│  ├── 3000: Ad not found                                      │
│  ├── 3001: Campaign not found                                │
│  ├── 3002: Ad group not found                                │
│  ├── 3003: Creative not found                                │
│  ├── 3004: Pixel not found                                   │
│  ├── 3005: Conversion not found                              │
│  └─ 3006: Product not found                                  │
│                                                              │
│  配额/限制:                                                  │
│  ├── 4000: Rate limit exceeded                               │
│  ├── 4001: Daily limit exceeded                              │
│  └─ 4002: Monthly limit exceeded                             │
│                                                              │
│  审核错误:                                                   │
│  ├── 5000: Ad rejected by review                              │
│  ├── 5001: Creative rejected                                 │
│  └─ 5002: Policy violation                                    │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 速率限制

```
TikTok API 速率限制:

┌──────────────────────────────────────────────────────────────┐
│              速率限制规则                                       │
│                                                              │
│  限制类型:                                                   │
│  ├── Requests per second: 100 次/秒 (API Key 级别)           │
│  ├── Requests per day: 100,000 次/天                         │
│  ├── Mutates per 100 seconds: 100 次/100秒                   │
│  └─ 每个 API 端点可能有独立的限制                              │
│                                                              │
│  响应头:                                                   │
│  ├── X-RateLimit-Limit: 限制次数                              │
│  ├── X-RateLimit-Remaining: 剩余次数                          │
│  └─ X-RateLimit-Reset: 重置时间 (Unix Timestamp)             │
│                                                              │
│  处理:                                                       │
│  ├── 监控响应头                                              │
│  ├── 指数退避                                                │
│  └─ 批量操作减少请求                                          │
└──────────────────────────────────────────────────────────────┘
```

### 7.3 错误处理代码

```python
import time
import logging
import requests

logger = logging.getLogger(__name__)

class TikTokAPIError(Exception):
    """TikTok API 异常"""
    def __init__(self, error_code: int, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"Error {error_code}: {error_message}")

RATE_LIMIT_ERRORS = {4000, 4001, 4002}

def safe_tiktok_request(url: str, data: dict,
                        access_token: str,
                        max_retries: int = 3,
                        base_delay: float = 1.0) -> dict:
    """
    安全的 TikTok API 请求
    
    参数:
    ├── url: API 端点
    ├── data: 请求数据
    ├── access_token: 访问令牌
    ├── max_retries: 最大重试次数
    └── base_delay: 基础延迟 (秒)
    
    返回:
    └── 响应数据
    """
    for attempt in range(max_retries):
        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}',
            }
            
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            
            # 检查业务错误
            if 'code' in result and 'message' in result:
                error_code = result['code']
                error_msg = result['message']
                
                if error_code in RATE_LIMIT_ERRORS:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    # 非速率限制错误, 不重试
                    logger.error(f"API error: {error_msg}")
                    raise TikTokAPIError(error_code, error_msg)
            
            return result
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Network error. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise
    
    raise Exception(f"Failed after {max_retries} retries")

# 使用示例
result = safe_tiktok_request(
    "https://open.tiktokapis.com/v2/ad/group/stats/",
    data={
        "access_token": "{token}",
        "request_body": {
            "granularity": "DAY",
            "date_preset": "LAST_7_DAYS",
            "metrics": ["IMPRESSIONS", "CLICKS", "SPEND"],
        }
    },
    access_token="EAAB...",
)
```

---

## 第八部分: 最佳实践

```
TikTok Marketing API 最佳实践:

1. 认证管理:
   ├── 使用长期 Token (365 天)
   ├── 安全存储 credentials
   ├── 使用 refresh_token 保持有效
   └─ 区分测试/生产环境

2. 请求优化:
   ├── 只请求需要的字段
   ├── 使用分页 (page/page_size)
   ├── 使用 report_spec 批量获取
   └─ 连接复用

3. 错误处理:
   ├── 监控速率限制 (4000/4001/4002)
   ├── 指数退避
   ├── 日志所有错误
   └─ 告警设置

4. 数据同步:
   ├── 增量同步 (updated_time)
   ├── 全量同步 (定期)
   └─ 变更检测

5. 性能:
   ├── 并行请求不同资源
   ├── 连接池
   ├── 超时设置 (connect: 5s, read: 30s)
   └─ 监控 API 延迟
```

---

*今天花 90 分钟：深入掌握 TikTok Marketing API 高级用法*
*答不出自测题？回去重读对应章节。*

---

## 自测题

### 问题 1
TikTok API 的默认速率限制是多少？

<details>
<summary>查看答案</summary>

100 次/秒, 100,000 次/天 (API Key 级别)
</details>

### 问题 2
Spark Ads 在 Creative 中用什么类型标识？

<details>
<summary>查看答案</summary>

creative_type: "SPARK", 并指定 spark_id 为有机视频 ID
</details>

### 问题 3
TikTok API 的错误码中, 4000 代表什么？

<details>
<summary>查看答案</summary>

Rate limit exceeded (超出速率限制)
</details>

---

*今天花 90 分钟：深入掌握 TikTok Marketing API 高级用法*
*答不出自测题？回去重读对应章节。*
