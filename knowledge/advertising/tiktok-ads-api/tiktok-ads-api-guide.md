# TikTok Ads Manager API 完整指南

> **领域**: 广告投放 / TikTok Ads
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: tiktok, ads-api, spark-ads, pixel, conversion-api
> **更新时间**: 2026-08-14
> **类型**: api-guide/production

---

## 📌 TikTok Ads API 概览

### 1. API 架构

```
┌─────────────────────────────────────────────────────┐
│             TikTok Ads API Architecture              │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Client Application                                 │
│  ├── OAuth 2.0 Authentication                       │
│  ├── Python SDK                                      │
│  └── REST API (HTTPS)                              │
│         │                                            │
│         ▼                                            │
│  TikTok Marketing API                               │
│  ├── Ad Account (广告账户)                         │
│  ├── Campaign (广告系列)                            │
│  ├── Ad Group (广告组)                               │
│  ├── Ad (广告创意)                                  │
│  └── Event (转化事件)                               │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 2. 核心端点

```python
# 官方 SDK 安装
pip install tiktok-api

# 初始化客户端
from tiktokads.business.sdk import Client
from tiktokads.business.services import *

# 配置凭证
client = Client(
    access_token='YOUR_ACCESS_TOKEN',
    app_key='YOUR_APP_KEY',
    app_secret='YOUR_APP_SECRET'
)
```

---

## 🔥 核心功能实现

### 1. 创建广告系列

```python
def create_campaign(client, account_id, campaign_name):
    """创建广告系列"""
    from tiktokads.business.objects import Campaign
    
    campaign = Campaign(
        {
            Campaign.field_account_id: account_id,
            Campaign.field_name: campaign_name,
            Campaign.field_promotion_type: PromotionType.SALES,
            Campaign.field_daily_budget: 100000000,  # 100 USD (micros)
            Campaign.field_bid_type: BidType.AUTO_BID,
            Campaign.field_status: Status.PAUSED
        }
    )
    
    campaign.remote_create()
    return campaign
```

### 2. 创建广告组

```python
def create_ad_group(client, account_id, campaign_id, ad_group_name):
    """创建广告组"""
    from tiktokads.business.objects import AdGroup
    
    ad_group = AdGroup(
        {
            AdGroup.field_account_id: account_id,
            AdGroup.field_campaign_id: campaign_id,
            AdGroup.field_name: ad_group_name,
            AdGroup.field_bid_amount: 5000000,  # $0.05
            AdGroup.field_optimization_goal: OptimizationGoal.LINK_CLICKS,
            AdGroup.field_targeting: {
                'geo_locations': [{'country': 'US'}],
                'age_min': 18,
                'age_max': 65
            },
            AdGroup.field_status: Status.PAUSED
        }
    )
    
    ad_group.remote_create()
    return ad_group
```

### 3. 创建广告创意

```python
def create_ad(client, account_id, ad_group_id, ad_name):
    """创建广告创意"""
    from tiktokads.business.objects import Ad
    
    ad = Ad(
        {
            Ad.field_account_id: account_id,
            Ad.field_ad_group_id: ad_group_id,
            Ad.field_name: ad_name,
            Ad.field_tracking_url: 'https://your-site.com/track',
            Ad.field_status: Status.PAUSED
        }
    )
    
    ad.remote_create()
    return ad
```

---

## 💡 生产实践要点

### 1. Spark Ads（达人广告）

```python
def create_spark_ad(client, account_id, ad_group_id, video_id, creator_id):
    """创建 Spark Ads（使用 TikTok 原生视频）"""
    from tiktokads.business.objects import Ad
    
    ad = Ad(
        {
            Ad.field_account_id: account_id,
            Ad.field_ad_group_id: ad_group_id,
            Ad.field_name: f"Spark Ad - {creator_id}",
            Ad.field_spark_content_source: SparkContentSource.POST,
            Ad.field_spark_content_source_id: video_id,
            Ad.field_post_id: video_id,
            Ad.field_creator_id: creator_id,
            Ad.field_status: Status.PAUSED
        }
    )
    
    ad.remote_create()
    return ad
```

### 2. Pixel 事件追踪

```python
def track_pixel_event(client, pixel_id, event_name, event_data):
    """追踪 Pixel 事件"""
    from tiktokads.business.objects import PixelEvent
    
    event = PixelEvent(
        {
            PixelEvent.field_pixel_id: pixel_id,
            PixelEvent.field_event_name: event_name,
            PixelEvent.field_event_time: int(time.time()),
            PixelEvent.field_event_source_url: 'https://your-site.com/checkout',
            PixelEvent.field_custom_data: {
                'value': 99.99,
                'currency': 'USD',
                'content_ids': ['product_123']
            }
        }
    )
    
    event.remote_create()
```

### 3. Conversion API 实现

```python
def send_conversion_event(client, pixel_id, user_email, user_phone):
    """通过 Conversion API 发送事件"""
    from tikttikads.business.objects import ConversionEvent
    
    event = ConversionEvent(
        {
            ConversionEvent.field_pixel_id: pixel_id,
            ConversionEvent.field_event_name: 'PageView',
            ConversionEvent.field_event_time: int(time.time()),
            ConversionEvent.field_user_data: {
                'em': [hash_email(user_email)],
                'ph': [hash_phone(user_phone)]
            },
            ConversionEvent.field_custom_data: {
                'content_category': 'product'
            }
        }
    )
    
    event.remote_create()
```

---

## 📊 API 配额与限制

| 操作类型 | 每日配额 | 每应用限制 |
|---------|---------|-----------|
| Read 请求 | 100,000 | 100/min |
| Write 请求 | 50,000 | 50/min |
| 报表查询 | 100,000 | 100/min |
| 事件发送 | 无限制 | 根据负载 |

**最佳实践：**
1. 使用批量创建 API
2. 缓存访问令牌
3. 实现速率限制处理
4. 监控 API 使用情况

---

## 🎓 面试高频问题

**Q: TikTok Ads API 和 Facebook Marketing API 有什么区别？**
A: 三级区别：
1. **认证**: TikTok 使用 App Key/Secret，Meta 使用 OAuth
2. **创意**: TikTok 支持 Spark Ads，Meta 支持 Instant Experience
3. **追踪**: TikTok Pixel 更简化，Meta Pixel 更灵活

**Q: Spark Ads 的优势是什么？**
A: 四级优势：
1. **原生体验**: 使用创作者原生内容
2. **信任度高**: 用户更信任创作者内容
3. **成本低**: 无需制作广告素材
4. **效果好**: 点击率通常更高

---

## 📚 参考资源

- **官方文档**: https://business-api.tiktok.com/portal/docs
- **SDK 仓库**: https://github.com/TikTokAPI/tiktok-ads-python-sdk
- **示例代码**: https://github.com/TikTokAPI/tiktok-ads-python-sdk/tree/master/examples

---

*本指南从 TikTok Ads API 出发，结合生产实践经验，提供独家洞察。*
