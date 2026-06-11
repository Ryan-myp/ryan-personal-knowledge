# Meta Graph API — 高级用法深度指南

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级 — API 高级用法全覆盖

---

## 第一部分: 认证体系与权限模型

### 1.1 Meta 认证流程

```
Meta 广告 API 认证采用 OAuth2 + Access Token 机制:

┌──────────────────────────────────────────────────────────────┐
│              Meta 认证流程                                     │
│                                                              │
│  1. App (开发者应用)                                          │
│  ├── 创建 Meta for Developers App                            │
│  ├── 获取 App ID + App Secret                                │
│  └─ 添加 products: instagram, whatsapp, marketing             │
│                                                              │
│  2. User Access Token (用户令牌)                               │
│  ├── 用户授权登录                                            │
│  ├── 选择广告账户权限                                         │
│  └─ 获取 user_access_token                                   │
│                                                              │
│  3. Page Access Token / Ad Account Access Token               │
│  ├── 从用户令牌转换为广告账户令牌                               │
│  ├── 授权范围: read_analytics, manage_ads, public_profile     │
│  └─ 有效期: 60 天 (长期有效需交换为长期令牌)                    │
│                                                              │
│  4. Long-Lived Token (长期令牌)                                 │
│  ├── 用户令牌交换为 60 天                                     │
│  ├── 广告账户令牌交换为 60 天                                  │
│  └─ 通过 token.refresh 刷新到 2 年                           │
│                                                              │
│  5. Business Account Token                                    │
│  ├── Business Manager 级别令牌                                │
│  ├── 可管理多个广告账户                                       │
│  └─ 适合: 代理/服务商                                         │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 权限范围 (Permission Scopes)

```
Meta API 权限范围:

广告相关:
├─ ads_management: 管理广告账户
├─ ads_read: 读取广告数据
├─ read_insights: 读取洞察数据
├─ manage_pages: 管理页面
├─ pages_show_list: 查看页面列表
├─ public_profile: 公开资料
├─ email: 用户邮箱
├─ phone: 用户电话
├─ instagram_basic: Instagram 基础数据
├─ instagram_content_publish: Instagram 发布内容
├─ instagram_manage_comments: 管理 Instagram 评论
├─ instagram_manage_insights: Instagram 洞察
└─ instagram_manage_messages: Instagram 消息

Pixel/转化:
├─ events_management: 管理转化事件
├─ pixel_management: 管理 Pixel
└─ pixel_read: 读取 Pixel 数据

Catalog:
├─ catalog_management: 管理商品目录
└─ catalog_read: 读取商品目录

Business Manager:
├─ business_management: 管理业务
└─ pages_manage_ads: 管理页面广告

最佳实践:
├─ 最小权限原则 (只申请需要的)
├─ 区分测试令牌和生产令牌
├─ 定期轮换令牌
└─ 安全存储 (不硬编码)
```

### 1.3 认证代码实现

```python
import requests

class MetaAPIAuth:
    """
    Meta API 认证管理
    """
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.session = requests.Session()
    
    def get_user_access_token(self, authorization_code: str,
                               redirect_uri: str) -> dict:
        """
        通过授权码获取用户访问令牌
        
        POST /oauth/access_token
        """
        url = "https://graph.facebook.com/v20.0/oauth/access_token"
        params = {
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'redirect_uri': redirect_uri,
            'code': authorization_code,
        }
        response = requests.get(url, params=params)
        return response.json()
    
    def get_long_lived_token(self, short_lived_token: str) -> str:
        """
        将短期令牌交换为长期令牌 (60天)
        
        GET /oauth/access_token
        """
        url = "https://graph.facebook.com/v20.0/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'fb_exchange_token': short_lived_token,
        }
        response = requests.get(url, params=params)
        data = response.json()
        return data['access_token']
    
    def exchange_for_ad_account_token(self, user_token: str,
                                       ad_account_id: str) -> str:
        """
        将用户令牌转换为广告账户令牌
        
        GET /v20.0/{ad_account_id}
        """
        url = f"https://graph.facebook.com/v20.0/{ad_account_id}"
        params = {
            'fields': 'access_token',
            'access_token': user_token,
        }
        response = requests.get(url, params=params)
        data = response.json()
        return data.get('access_token', user_token)
    
    def refresh_token(self, long_lived_token: str) -> str:
        """
        刷新令牌到 2 年有效期
        
        需要用户重新授权一次后, 令牌可刷新为 2 年
        """
        url = f"https://graph.facebook.com/v20.0/me"
        params = {
            'fields': 'access_token',
            'access_token': long_lived_token,
        }
        response = requests.get(url, params=params)
        data = response.json()
        return data.get('access_token', long_lived_token)
```

---

## 第二部分: 核心端点深度使用

### 2.1 Campaign 管理

```
Campaign CRUD 操作:

1. 创建广告系列:

POST /v20.0/{ad_account_id}/campaigns
{
    "name": "My Campaign",
    "objective": "CONVERSIONS",
    "status": "PAUSED",
    "special_ad_categories": ["NONE"],  // 必需字段
    "promoted_object": {
        "objective": "OFF_SITE_CONVERSIONS"
    },
    "budget_reuse_type": "CAMPAIGN",
    "daily_budget": 5000,  // 分
    "campaign_group_id": null,
    "optimization_goal": "LINK_CLICKS"
}

2. 更新广告系列:

POST /v20.0/{campaign_id}
{
    "name": "Updated Campaign Name",
    "status": "ACTIVE",
    "daily_budget": 6000
}

3. 删除广告系列:

DELETE /v20.0/{campaign_id}

4. 获取广告系列:

GET /v20.0/{campaign_id}
?fields=id,name,status,objective,daily_budget,budget_reuse_type,
     campaign_group_id,created_time,updated_time,
     insights.{impressions,clicks,conversions,cost}
```

### 2.2 Ad Set 管理

```
Ad Set 配置要点:

1. 创建广告组:

POST /v20.0/{ad_account_id}/adsets
{
    "name": "My Ad Set",
    "campaign_id": "{campaign_id}",
    "status": "PAUSED",
    "billing_event": "IMPRESSIONS",
    "optimization_goal": "LINK_CLICKS",
    "bid_amount": 100,  // 分 (可选, Lowest Cost 时不用)
    "bid_constraints": {
        "cost_per_goal_goal": 500
    },
    "targeting": {
        "geo_locations": {
            "countries": ["US", "CA"],
            "regions": [{"id": 1001}],  // 区域 ID
            "cities": [
                {
                    "name": "New York",
                    "country_code": "US",
                    "regions": [{"key": "1001"}],
                    "zip_codes": ["10001", "10002"]
                }
            ]
        },
        "age_min": 25,
        "age_max": 45,
        "genders": [1],  // 1=Female, 2=Male
        "interests": [
            {"name": "E-commerce", "id": "600"},
            {"name": "Online shopping", "id": "600"}
        ],
        "custom_audiences": [
            {"id": "{custom_audience_id}"}
        ],
        "exclusions": {
            "custom_audiences": [
                {"id": "{excluded_audience_id}"}
            ]
        }
    },
    "daily_budget": 5000,
    "start_time": "2026-06-10T00:00:00+0000",
    "end_time": "2026-07-10T00:00:00+0000",
    "schedule": [
        {
            "start_hour": 8,
            "end_hour": 22,
            "days": [1, 2, 3, 4, 5, 6, 7]  // Sun-Sat
        }
    ],
    "placemenements": ["facebook_feed", "instagram_feed"],
    "promoted_object": {
        "object_id": "{pixel_id}",
        "custom_event_type": "PURCHASE"
    },
    "conversion_spec_id": "{conversion_spec_id}"
}

2. 定位高级用法:

- 动态区域 (Dynamic Radius):
  "geo_locations": {
    "dynamic_zones": [
      {
        "key": "zone1",
        "geo_locations": {
          "countries": ["US"],
          "distance_in_meters": 16093  // 10 英里
        }
      }
    ]
  }

- 精细定位 (Detailed Targeting Expansion):
  "targeting_spec": {
    "publisher_platforms": ["facebook", "instagram"],
    "platforms": ["facebook"],
    "geo_locations": {...},
    "age_min": 18,
    "age_max": 65,
    "genders": [2],
    "use_new_app_integrations_targeting": true
  }

- 自定义受众组合:
  "custom_audiences": [
    {"id": "{list_audience}", "operator": "INTERSECT"},
    {"id": "{lookalike_audience}", "operator": "INTERSECT"}
  ]
  // INTERSECT: 交集, UNION: 并集, EXCLUDE: 排除
```

### 2.3 Ad 管理

```
Ad 创建完整示例:

1. 单图广告:

POST /v20.0/{ad_account_id}/ads
{
    "name": "My Ad",
    "run_status": "PAUSED",
    "campaign_id": "{campaign_id}",
    "adset_id": "{adset_id}",
    "creative": {
        "body": "Check out our amazing products!",
        "object_id": "{image_object_id}",
        "title": "Shop Now",
        "description": "Best deals of the season",
        "call_to_action": {
            "type": "SHOP_NOW",
            "value": {
                "link": "https://example.com/shop"
            }
        }
    },
    "preview_ad_format": "FEED",
    "tracking_urls": [
        {"type": "CLICK_THROUGH", "url": "https://tracking.com"}
    ]
}

2. 视频广告:

POST /v8.0/{ad_account_id}/ads
{
    "name": "Video Ad",
    "run_status": "PAUSED",
    "campaign_id": "{campaign_id}",
    "adset_id": "{adset_id}",
    "creative": {
        "title": "Product Demo",
        "message": "See how it works",
        "object_story_id": "{object_story_id}",
        "call_to_action": {
            "type": "LEARN_MORE"
        }
    }
}

3. 轮播广告:

POST /v20.0/{ad_account_id}/ads
{
    "name": "Carousel Ad",
    "run_status": "PAUSED",
    "campaign_id": "{campaign_id}",
    "adset_id": "{adset_id}",
    "creative": {
        "title": "Our Products",
        "call_to_action": {
            "type": "SHOP_NOW"
        },
        "child_assets": [
            {
                "name": "Card 1",
                "description": "Product 1",
                "image_url": "https://...",
                "link": "https://.../product1"
            },
            {
                "name": "Card 2",
                "description": "Product 2",
                "image_url": "https://...",
                "link": "https://.../product2"
            }
        ]
    }
}

4. 动态商品广告:

POST /v20.0/{ad_account_id}/ads
{
    "name": "Dynamic Product Ad",
    "run_status": "PAUSED",
    "campaign_id": "{campaign_id}",
    "adset_id": "{adset_id}",
    "creative": {
        "object_story_spec": {
            "page_id": "{page_id}",
            "link_data": {
                "image_hash": "{image_hash}",
                "call_to_action": {
                    "type": "SHOP_NOW",
                    "value": {
                        "link": "https://example.com"
                    }
                },
                "description": "Shop our latest collection",
                "title": "New Arrivals",
                "messenger_extension": false,
                "target_id": "{catalog_product_id}"
            }
        }
    }
}
```

---

## 第三部分: Insights 与数据分析

### 3.1 Insights 查询

```
获取洞察数据:

GET /v20.0/{ad_account_id}/insights
?fields=
  campaign.name,
  adset.name,
  ad.name,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions,
  metrics.cost_per_total_action,
  metrics.cost_per_purchase,
  metrics.thruplays,
  metrics.unique_thruplays,
  metrics.cpm,
  metrics.cpc,
  metrics.ctr
&time_range={
  "since": "2026-05-01",
  "until": "2026-06-01"
}
&breakdowns=
  platform_position,
  gender,
  age,
  country,
  region,
  city,
  device_platform,
  date_start
&limit=100

高级 Insights:

1. 自定义时间范围:
   &time_range={
     "since": "2026-01-01",
     "until": "2026-06-01",
     "count": 30
   }
   // count: 返回多少天的数据

2. 增量分析:
   ?insights=
     campaign.{impressions,clicks,conversions},
     insights.{
       impressions,
       clicks,
       conversions,
       cost_per_total_action,
       purchase_roas
     }

3. 按广告系列分组:
   ?groupby=campaign,adset,ad

4. 排序:
   ?sort=metric_name:desc
   // metric_name: 指标名
   // desc/asc: 排序方向
```

### 3.2 常用指标

```
Meta Insights 核心指标:

展示/点击:
├─ impressions: 总展示
├─ reach: 触达人数
├─ frequency: 平均频次
├─ clicks: 总点击
├─ link_clicks: 链接点击
├─ unique_link_clicks: 唯一链接点击
├─ cpc: 平均 CPC
├─ cpm: 平均 CPM
└─ cpp: 平均 CPP (每次购买)

转化:
├─ conversions: 总转化
├─ purchase_roas: 广告投资回报率
├─ cost_per_purchase: 每次购买成本
├─ cost_per_thruplay: 每次完整观看成本
├─ cost_per_action: 每次行动成本
└─ cost_per_total_action: 每次总行动成本

视频:
├─ video_avg_time_watched: 平均观看时长
├─ video_avg_time_watched_actions: 视频观看行动
├─ video_avg_time_watched_pooled_0p00: 0-3s 观看
├─ video_avg_time_watched_pooled_0p25: 25% 观看
├─ video_avg_time_watched_pooled_0p50: 50% 观看
├─ video_avg_time_watched_pooled_0p75: 75% 观看
├─ video_avg_time_watched_pooled_1p00: 100% 观看
├─ thruplays: 完整播放 (15s 或完整)
├─ unique_thruplays: 唯一完整播放
└─ video_avg_time_watched_actions: 视频观看行动数

互动:
├─ actions: 行动列表
├─ action_values: 行动价值
├─ post_engagements: 帖子互动
├─ page_engagements: 页面互动
├─ social_actions_likes: 点赞
├─ comments: 评论
├─ shares: 分享
└─ saves: 收藏

品牌:
├─ brand_lift: 品牌提升
├─ brand_search_lift: 品牌搜索提升
├─ ad_recall_rate: 广告回忆率
└─ ad_recallers: 广告回忆人数
```

---

## 第四部分: 批量操作 (Batch API)

### 4.1 Batch API 详解

```
Batch API 允许在一次 HTTP 请求中执行多个操作:

POST /v20.0/{business_id}?batch=[
  {
    "name": "create_campaign",
    "method": "POST",
    "relative_url": "{ad_account_id}/campaigns",
    "body": "name=Birthday Campaign&objective=SALES&status=PAUSED&special_ad_categories=NONE",
    "headers": {
      "Authorization": "Bearer {access_token}"
    }
  },
  {
    "name": "create_adset_1",
    "method": "POST",
    "relative_url": "{ad_account_id}/adsets",
    "body": "name=Ad Set 1&campaign_id={result=create_campaign:$.id}&status=PAUSED&billing_event=IMPRESSIONS&optimization_goal=LINK_CLICKS&daily_budget=5000",
    "headers": {
      "Authorization": "Bearer {access_token}"
    }
  },
  {
    "name": "create_adset_2",
    "method": "POST",
    "relative_url": "{ad_account_id}/adsets",
    "body": "name=Ad Set 2&campaign_id={result=create_campaign:$.id}&status=PAUSED&billing_event=IMPRESSIONS&optimization_goal=LINK_CLICKS&daily_budget=5000",
    "headers": {
      "Authorization": "Bearer {access_token}"
    }
  },
  {
    "name": "get_insights",
    "method": "GET",
    "relative_url": "{ad_account_id}/insights?fields=metrics.impressions,metrics.clicks&time_range={%27since%27:%272026-01-01%27,%27until%27:%272026-06-01%27}",
    "headers": {
      "Authorization": "Bearer {access_token}"
    }
  }
]

Batch API 特性:
├─ 最大批量: 40 个操作
├─ 操作间依赖: {result=name:$.field_path} 引用前一步结果
├─ 原子性: 所有操作要么全成功, 要么全失败
├─ 响应: 每个操作独立返回状态码和响应体
└─ 速率限制: 按批次计算 (每 600s 5000 次)

Python 实现:
```python
import requests
import json

def execute_batch(ad_account_id: str, access_token: str,
                  operations: list) -> dict:
    """
    执行 Meta Batch API 操作
    
    参数:
    ├── ad_account_id: 广告账户 ID
    ├── access_token: 访问令牌
    └── operations: 操作列表
    
    返回:
    └── 批量操作结果
    """
    url = f"https://graph.facebook.com/v20.0/{ad_account_id}"
    
    batch = []
    for op in operations:
        batch.append({
            "name": op["name"],
            "method": op["method"],
            "relative_url": op["relative_url"].format(
                ad_account_id=ad_account_id
            ),
            "body": op.get("body", ""),
        })
    
    params = {
        "batch": json.dumps(batch),
        "access_token": access_token,
    }
    
    response = requests.post(url, params=params)
    return response.json()

# 使用示例
operations = [
    {
        "name": "create_campaign",
        "method": "POST",
        "relative_url": "{ad_account_id}/campaigns",
        "body": "name=Test Campaign&status=PAUSED&objective=CONVERSIONS&special_ad_categories=NONE",
    },
    {
        "name": "create_adset",
        "method": "POST",
        "relative_url": "{ad_account_id}/adsets",
        "body": "name=Test Ad Set&campaign_id={result=create_campaign:$.id}&status=PAUSED&billing_event=IMPRESSIONS&optimization_goal=LINK_CLICKS&daily_budget=5000&targeting={%27geo_locations%27:{%27countries%27:[%27US%27]}%7D",
    },
]

result = execute_batch("act_123456", "EAAB...", operations)
print(json.dumps(result, indent=2))
```

### 4.2 异步操作

```
对于大数据操作 (超过 Batch 限制):

1. 使用 /{ad_account_id}/campaigns 的异步模式:

POST /v20.0/{ad_account_id}/campaigns
{
    "name": "Asynchronous Campaign",
    "objective": "CONVERSIONS",
    "status": "PAUSED",
    "special_ad_categories": "NONE",
    "campaign_group_id": "{campaign_group_id}",
    "use_new_campaign_setup": true
}

2. 监控异步操作状态:

GET /v20.0/{operation_id}
?fields=status,errors

3. 批量删除:
   
   DELETE /v20.0/{ad_account_id}/ads?ids={ad_id_1},{ad_id_2},...,{ad_id_N}
   // 最多 50 个 ID 一次

4. 使用 GraphQL (替代 Batch):
   
   POST /v20.0/me?
     query=query {
       adaccount(id: "act_123456") {
         campaigns(limit: 100) {
           data {
             id
             name
             status
           }
         }
         adsets(limit: 100) {
           data {
             id
             name
             status
           }
         }
       }
     }
```

---

## 第五部分: 错误处理

### 5.1 Meta API 错误类型

```
Meta API 错误码:

┌──────────────────────────────────────────────────────────────┐
│              Meta API 错误分类                                 │
│                                                              │
│  认证错误:                                                   │
│  ├── 190: Invalid access token                              │
│  ├── 102: Application session invalid                        │
│  ├── 368: The app has been removed                            │
│  └─ 200: Permissions error                                   │
│                                                              │
│  速率限制:                                                   │
│  ├── 4: API call limit exceeded                              │
│  ├── 17: User query limit reached                            │
│  ├── 32: Page query limit reached                            │
│  ├── 800: Business query limit exceeded                      │
│  └─ 803: Throttled by application                             │
│                                                              │
│  验证错误:                                                   │
│  ├── 100: Invalid parameter                                 │
│  ├── 101: Parameter missing                                  │
│  ├── 200: Permissions error                                  │
│  └─ 201: Unsupported update operation                        │
│                                                              │
│  资源错误:                                                   │
│  ├── 105: Invalid object                                    │
│  ├── 107: User query failed due to down time                │
│  ├── 195: Object is not found                                │
│  └─ 2500: App request limit reached                          │
│                                                              │
│  业务错误:                                                   │
│  ├── 750: Action blocked by policy                            │
│  ├── 1363031: Ad account disabled                             │
│  └─ 1363022: Ad account limit reached                         │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 错误处理策略

```python
import time
import logging

logger = logging.getLogger(__name__)

class MetaAPIError(Exception):
    """Meta API 自定义异常"""
    def __init__(self, error_code: int, error_message: str,
                 error_subcode: int = None):
        self.error_code = error_code
        self.error_message = error_message
        self.error_subcode = error_subcode
        super().__init__(f"Error {error_code}: {error_message}")

RATE_LIMIT_ERRORS = {4, 17, 32, 800, 803}

def safe_graph_request(url: str, params: dict = None,
                        max_retries: int = 3,
                        base_delay: float = 1.0) -> dict:
    """
    安全的 Graph API 请求 (带重试)
    """
    import requests
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # 检查 API 错误
            if 'error' in data:
                error = data['error']
                error_code = error.get('code', 0)
                error_msg = error.get('message', '')
                
                if error_code in RATE_LIMIT_ERRORS:
                    # 速率限制, 指数退避
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                elif error_code in [190, 102, 368]:
                    # 认证错误, 不重试
                    logger.error(f"Auth error: {error_msg}")
                    raise MetaAPIError(error_code, error_msg)
                else:
                    # 其他错误, 不重试
                    logger.error(f"API error: {error_msg}")
                    raise MetaAPIError(error_code, error_msg)
            
            return data
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Network error. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise
    
    raise Exception(f"Failed after {max_retries} retries")

# 使用示例
result = safe_graph_request(
    "https://graph.facebook.com/v20.0/act_123456/insights",
    params={
        "fields": "metrics.impressions,metrics.clicks,metrics.conversions",
        "time_range": '{"since":"2026-01-01","until":"2026-06-01"}',
    },
    max_retries=3,
)
```

---

## 第六部分: 性能优化

### 6.1 查询优化

```
Graph API 性能优化:

1. 字段选择:
   ├── 只请求需要的字段 (fields=...)
   ├── 避免使用 * (通配符)
   └─ 使用字段组 (metrics/insights/breakdowns)

2. 分页:
   ├── 使用 limit 控制每页数量
   ├── 使用 after/before 游标
   └─ 避免递归调用 (使用 batch 替代)

3. 并发:
   ├── 并行请求不同资源
   ├── 使用 Connection Pool
   └─ 注意速率限制 (5000 req/600s)

4. 缓存:
   ├── 缓存高频数据 (广告系列/广告组)
   ├── 缓存变更检测 (updated_time)
   └─ 使用 ETag (If-None-Match)

5. 连接复用:
   ├── 使用 requests.Session()
   ├── HTTP/2 支持
   └─ 超时设置 (connect: 5s, read: 30s)

6. 批量操作优先:
   ├── 单个 batch 最多 40 个操作
   ├── 减少 HTTP 请求次数
   └─ 利用操作间依赖
```

### 6.2 连接管理

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class MetaAPIClient:
    """
    优化的 Meta API 客户端
    """
    
    def __init__(self, access_token: str, timeout: int = 30):
        self.access_token = access_token
        self.timeout = timeout
        self.session = requests.Session()
        
        # 连接池
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
            ),
            pool_connections=10,
            pool_maxsize=20,
        )
        self.session.mount('https://', adapter)
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        })
    
    def get(self, endpoint: str, params: dict = None) -> dict:
        """GET 请求"""
        url = f"https://graph.facebook.com/v20.0/{endpoint}"
        response = self.session.get(
            url, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint: str, data: dict = None) -> dict:
        """POST 请求"""
        url = f"https://graph.facebook.com/v20.0/{endpoint}"
        response = self.session.post(
            url, json=data, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def batch(self, operations: list) -> list:
        """
        批量操作
        
        参数:
        └── operations: 操作列表
        
        返回:
        └── 操作结果列表
        """
        batch_params = {
            'batch': json.dumps(operations),
        }
        response = self.session.post(
            f"https://graph.facebook.com/v20.0/me",
            params=batch_params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
    
    def close(self):
        """关闭连接"""
        self.session.close()
```

---

## 第七部分: 最佳实践清单

```
Meta Graph API 最佳实践:

1. 认证:
   ├── 使用长期令牌 (60天/2年)
   ├── 安全存储 credentials
   ├── 区分测试/生产环境
   └─ 定期轮换

2. 请求优化:
   ├── 只请求需要的字段
   ├── 使用 batch 减少请求
   ├── 使用缓存
   └─ 连接复用 (Session)

3. 错误处理:
   ├── 监控速率限制错误 (4, 17, 32, 800)
   ├── 指数退避
   ├── 日志记录所有错误
   └─ 告警阈值设置

4. 数据同步:
   ├── 增量同步 (updated_time)
   ├── 全量同步 (定期)
   └─ 变更检测 (ETag)

5. 性能:
   ├── 并行请求不同资源
   ├── 连接池 (max_connections=20)
   ├── 超时设置 (connect: 5s, read: 30s)
   └─ 监控 API 延迟
```

---

### Meta Ads API 高级用法的 Go 实现

```go
// Meta Ads API 高级用法: Insights、批量操作、缓存、重试
package metaadvanced

import (
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"sync"
	"time"
)

// ==================== 高级 Insights 查询 ====================

// InsightsQuery Builder 模式
type InsightsQuery struct {
	customerID string
	fields     []string
	metrics    []string
	timeRange  map[string]string
	filtering  []string
	breakdowns []string
	limit      int
	sortOrder  string
}

// NewInsightsQuery 创建查询构建器
func NewInsightsQuery(customerID string) *InsightsQuery {
	return &InsightsQuery{
		customerID: customerID,
		timeRange:  make(map[string]string),
		limit:      100,
	}
}

func (q *InsightsQuery) Fields(fields []string) *InsightsQuery {
	q.fields = fields
	return q
}

func (q *InsightsQuery) Metrics(metrics []string) *InsightsQuery {
	q.metrics = metrics
	return q
}

func (q *InsightsQuery) TimeRange(start, end string) *InsightsQuery {
	q.timeRange["start_date"] = start
	q.timeRange["end_date"] = end
	return q
}

func (q *InsightsQuery) Filter(field, op, value string) *InsightsQuery {
	q.filtering = append(q.filtering, fmt.Sprintf(`{"field":"%s","operator":"%s","value":["%s"]}`, field, op, value))
	return q
}

func (q *InsightsQuery) Breakdowns(breakdowns []string) *InsightsQuery {
	q.breakdowns = breakdowns
	return q
}

func (q *InsightsQuery) Limit(n int) *InsightsQuery {
	if n > 0 {
		q.limit = n
	}
	return q
}

// Build 构建最终查询参数
func (q *InsightsQuery) Build() map[string]string {
	params := make(map[string]string)
	params["access_token"] = "..."

	if len(q.fields) > 0 {
		params["fields"] = join(q.fields, ",")
	}
	if len(q.metrics) > 0 {
		params["metrics"] = join(q.metrics, ",")
	}
	if start, ok := q.timeRange["start_date"]; ok {
		params["time_range[start_date]"] = start
	}
	if end, ok := q.timeRange["end_date"]; ok {
		params["time_range[end_date]"] = end
	}
	if len(q.breakdowns) > 0 {
		params["breakdowns"] = join(q.breakdowns, ",")
	}
	params["limit"] = fmt.Sprintf("%d", q.limit)
	if q.sortOrder != "" {
		params["sort"] = q.sortOrder
	}
	return params
}

// ==================== 批量操作高级用法 ====================

// BatchOperation 批量操作管理器
type BatchOperation struct {
	operations []*BatchOp
	mu         sync.Mutex
}

type BatchOp struct {
	ID     string
	Method string
	Path   string
	Body   map[string]string
}

// AddCreateCampaign 添加创建广告系列的批量操作
func (b *BatchOperation) AddCreateCampaign(name, objective string, budget int64) string {
	id := fmt.Sprintf("create_campaign_%d", len(b.operations))
	b.mu.Lock()
	defer b.mu.Unlock()
	b.operations = append(b.operations, &BatchOp{
		ID:     id,
		Method: "POST",
		Path:   "/act_123/campaigns",
		Body: map[string]string{
			"name":       name,
			"objective":  objective,
			"daily_budget": fmt.Sprintf("%d", budget),
		},
	})
	return id
}

// AddCreateAdSet 添加创建广告组的批量操作
func (b *BatchOperation) AddCreateAdSet(campaignID string, name string, targetID int) string {
	id := fmt.Sprintf("create_adset_%d", len(b.operations))
	b.mu.Lock()
	defer b.mu.Unlock()
	b.operations = append(b.operations, &BatchOp{
		ID:     id,
		Method: "POST",
		Path:   "/act_123/adsets",
		Body: map[string]string{
			"name":       name,
			"campaign_id": fmt.Sprintf("[%s.id]", campaignID), // 引用上一步
		},
	})
	return id
}

// Execute 执行所有批量操作
func (b *BatchOperation) Execute(client *MetaClient) ([]BatchResponse, error) {
	b.mu.Lock()
	ops := make([]*BatchOp, len(b.operations))
	copy(ops, b.operations)
	b.mu.Unlock()

	if len(ops) == 0 {
		return nil, nil
	}

	// Meta 限制每批最多 50 个
	const maxPerBatch = 50
	results := make([]BatchResponse, 0)

	for i := 0; i < len(ops); i += maxPerBatch {
		end := i + maxPerBatch
		if end > len(ops) {
			end = len(ops)
		}
		chunk := ops[i:end]

		resp, err := client.PostForm("/batch", map[string]string{
			"requests": marshalBatch(chunk),
		})
		if err != nil {
			return results, err
		}

		var chunkResults []BatchResponse
		json.Unmarshal(resp, &chunkResults)
		results = append(results, chunkResults...)
	}

	return results, nil
}

// ==================== 指数退避重试 ====================

// RetryConfig 重试配置
type RetryConfig struct {
	MaxRetries     int
	BaseDelay      time.Duration
	MaxDelay       time.Duration
	RetryableCodes []int
}

// DefaultRetryConfig 默认重试配置
var DefaultRetryConfig = RetryConfig{
	MaxRetries: 3,
	BaseDelay:  time.Second,
	MaxDelay:   30 * time.Second,
	RetryableCodes: []int{429, 500, 503},
}

// ExponentialBackoffRetry 指数退避重试
func ExponentialBackoffRetry(fn func() ([]byte, error), config RetryConfig) ([]byte, error) {
	var lastErr error
	delay := config.BaseDelay

	for attempt := 0; attempt <= config.MaxRetries; attempt++ {
		data, err := fn()
		if err == nil {
			return data, nil
		}
		lastErr = err

		// 检查是否可重试
		if !isRetryable(err, config.RetryableCodes) {
			return nil, err
		}

		// 指数退避 + 抖动 (jitter)
		if attempt < config.MaxRetries {
			jitter := time.Duration(rand.Int63n(int64(delay)))
			totalDelay := delay + jitter
			if totalDelay > config.MaxDelay {
				totalDelay = config.MaxDelay
			}
			time.Sleep(totalDelay)
			delay = delay * 2
		}
	}

	return nil, fmt.Errorf("retry failed after %d attempts: %w", config.MaxRetries+1, lastErr)
}

func isRetryable(err error, codes []int) bool {
	// 简化：429 Rate Limited 和 5xx 服务端错误可重试
	for _, code := range codes {
		if code == 429 || code >= 500 {
			return true
		}
	}
	return false
}

// ==================== 本地缓存 ====================

// LocalCache 本地缓存 (LRU 风格简化版)
type LocalCache struct {
	items map[string]*cacheItem
	maxSize int
	mu    sync.RWMutex
}

type cacheItem struct {
	Value     []byte
	ExpiresAt time.Time
}

// NewLocalCache 创建缓存
func NewLocalCache(maxSize int) *LocalCache {
	if maxSize == 0 {
		maxSize = 1000
	}
	return &LocalCache{
		items:   make(map[string]*cacheItem),
		maxSize: maxSize,
	}
}

// Get 获取缓存
func (c *LocalCache) Get(key string) ([]byte, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	item, ok := c.items[key]
	if !ok {
		return nil, false
	}
	if time.Now().After(item.ExpiresAt) {
		delete(c.items, key)
		return nil, false
	}
	return item.Value, true
}

// Set 设置缓存
func (c *LocalCache) Set(key string, value []byte, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.items) >= c.maxSize {
		// 简单淘汰: 移除最旧的
		oldestKey := ""
		oldestTime := time.Now()
		for k, v := range c.items {
			if v.ExpiresAt.Before(oldestTime) {
				oldestKey = k
				oldestTime = v.ExpiresAt
			}
		}
		if oldestKey != "" {
			delete(c.items, oldestKey)
		}
	}
	c.items[key] = &cacheItem{
		Value:     value,
		ExpiresAt: time.Now().Add(ttl),
	}
}

// ==================== 速率限制器 (令牌桶) ====================

// TokenBucket 令牌桶限流器
type TokenBucket struct {
	tokens     float64
	maxTokens  float64
	refillRate float64 // tokens/second
	lastRefill time.Time
	mu         sync.Mutex
}

// NewTokenBucket 创建令牌桶
func NewTokenBucket(maxTokens float64, refillRate float64) *TokenBucket {
	return &TokenBucket{
		tokens:     maxTokens,
		maxTokens:  maxTokens,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

// TryConsume 尝试消费一个 token
func (tb *TokenBucket) TryConsume() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens = math.Min(tb.maxTokens, tb.tokens+elapsed*tb.refillRate)
	tb.lastRefill = now

	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}

// Wait 等待直到可以消费
func (tb *TokenBucket) Wait() {
	for !tb.TryConsume() {
		time.Sleep(100 * time.Millisecond)
	}
}

// ==================== 类型和工具 ====================

type BatchResponse struct {
	Status  int
	Body    json.RawMessage
	Headers map[string]string
}

type MetaClient struct{}
func (c *MetaClient) PostForm(path string, params map[string]string) ([]byte, error) {
	return []byte(`[]`), nil
}

func join(ss []string, sep string) string {
	s := ""
	for i, p := range ss {
		if i > 0 {
			s += sep
		}
		s += p
	}
	return s
}

func marshalBatch(ops []*BatchOp) string {
	b, _ := json.Marshal(ops)
	return string(b)
}

// 使用示例
func main() {
	// 1. Insights 查询
	query := NewInsightsQuery("act_123").
		Metrics([]string{"impressions", "clicks", "spend", "conversions", "cpa"}).
		TimeRange("2024-01-01", "2024-01-31").
		Breakdowns([]string{"platform", "device", "age", "gender"}).
		Limit(100).
		Build()
	fmt.Printf("Query params: %+v\n", query)

	// 2. 批量操作
	batch := &BatchOperation{}
	batch.AddCreateCampaign("Summer Sale", "OUTCOME_RESULTS", 5000)
	batch.AddCreateAdSet("create_campaign_0", "Prospecting", 0)
	results, _ := batch.Execute(&MetaClient{})
	fmt.Printf("Batch results: %d\n", len(results))

	// 3. 令牌桶限流
	bucket := NewTokenBucket(10, 10) // 10 tokens, 10/s
	for i := 0; i < 5; i++ {
		bucket.Wait()
		fmt.Printf("Request %d\n", i)
	}

	// 4. 缓存
	cache := NewLocalCache(100)
	cache.Set("campaign_123", []byte(`{"id":"123","name":"test"}`), 5*time.Minute)
	if data, ok := cache.Get("campaign_123"); ok {
		fmt.Printf("Cached: %s\n", data)
	}
}

---

## 自测题

### 问题 1
Meta API 批量操作每批最多多少个操作？

<details>
<summary>查看答案</summary>

40 个操作。超过需要多个 batch。
</details>

### 问题 2
速率限制错误代码有哪些？

<details>
<summary>查看答案</summary>

4, 17, 32, 800, 803
</details>

### 问题 3
Meta Batch API 的操作间依赖格式是什么？

<details>
<summary>查看答案</summary>

{result=operation_name:$.field_path}
例如: {result=create_campaign:$.id}
</details>

---

*今天花 90 分钟：深入掌握 Meta Graph API 高级用法*
*答不出自测题？回去重读对应章节。*
