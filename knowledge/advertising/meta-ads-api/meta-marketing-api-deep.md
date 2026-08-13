# Meta Marketing API 深度解析

> **领域**: 广告投放 / Meta Ads
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: meta, facebook, instagram, marketing-api, campaigns, pixel, caapi
> **更新时间**: 2026-08-14
> **类型**: api-guide/production

---

## 📌 Meta Marketing API 概览

### 1. API 架构

```
┌─────────────────────────────────────────────────────┐
│            Meta Marketing API Architecture           │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Client Application                                 │
│  ├── OAuth 2.0 Authentication                       │
│  ├── SDK (PHP/Python/Node.js)                      │
│  └── REST API (HTTPS)                              │
│         │                                            │
│         ▼                                            │
│  Meta Marketing API                                 │
│  ├── Ad Account (广告账户)                         │
│  ├── Campaign (广告系列)                            │
│  ├── Ad Set (广告组)                                │
│  ├── Ad (广告创意)                                  │
│  └── Event (转化事件)                               │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 2. 核心端点

```python
# 官方 SDK 安装
pip install facebook_business

# 初始化 SDK
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.ad import Ad

# 配置凭证
FacebookAdsApi.init(
    app_id='YOUR_APP_ID',
    app_secret='YOUR_APP_SECRET',
    access_token='YOUR_ACCESS_TOKEN'
)
```

---

## 🔥 核心功能实现

### 1. 创建广告系列

```python
def create_campaign(account, campaign_name):
    """创建广告投放系列"""
    campaign = account.create_campaign(
        name=campaign_name,
        objective='SALES',  # 销售目标
        status=Campaign.Status.paused
    )
    
    campaign.remote_create()
    return campaign
```

### 2. 创建广告组

```python
def create_ad_set(campaign, ad_set_name, budget):
    """创建广告组"""
    ad_set = campaign.create_ad_set(
        name=ad_set_name,
        targeting={
            'geo_locations': {
                'countries': ['US', 'CA']
            },
            'ages': {'min': 18, 'max': 65}
        },
        daily_budget=budget,
        optimization_goal='LINK_CLICKS',
        bidding_strategy='LOWEST_COST_WITHOUT_CAP'
    )
    
    ad_set.remote_create()
    return ad_set
```

### 3. 创建广告创意

```python
def create_ad(ad_set, creative_title, creative_body, link_url):
    """创建广告创意"""
    ad = ad_set.create_ad(
        name='Summer Sale Ad',
        creative={
            'body': creative_body,
            'title': creative_title,
            'link_url': link_url,
            'object_store_url': 'https://your-store.com/product'
        },
        status=Ad.Status.paused
    )
    
    ad.remote_create()
    return ad
```

---

## 💡 生产实践要点

### 1. Pixel 事件追踪

```python
from facebook_business.adaccounts import AdAccount
from facebook_business.ads import AdsInsights

def track_pixel_event(pixel_id, event_name, event_data):
    """追踪 Pixel 事件"""
    pixel = Pixel(pixel_id)
    
    event = pixel.create_event(
        event_name=event_name,
        event_time=int(time.time()),
        action_source='website',
        event_source_url='https://your-site.com/checkout',
        custom_data={
            'content_ids': ['product_123'],
            'content_type': 'product',
            'value': 99.99,
            'currency': 'USD'
        },
        extinfo=['fb1']
    )
    
    event.remote_create()
```

### 2. CAPI（Conversion API）实现

```python
from facebook_business.adaccounts import AdAccount
from facebook_business.ads import AdsInsights

def send_capi_event(user_email, user_phone, event_name, event_data):
    """通过 CAPI 发送转化事件"""
    account = AdAccount('act_123456789')
    
    events = [
        {
            'event_name': event_name,
            'event_time': int(time.time()),
            'action_source': 'website',
            'user_data': {
                'email': [hash_email(user_email)],
                'phone': [hash_phone(user_phone)],
                'city': 'New York',
                'country': 'US'
            },
            'custom_data': event_data,
            'event_source_url': 'https://your-site.com/thank-you'
        }
    ]
    
    response = account.call_api(
        '/events',
        method='POST',
        params={
            'data': json.dumps(events),
            'access_token': get_access_token()
        }
    )
    
    return response
```

### 3. 批量创建与更新

```python
def batch_create_ads(account, ad_creatives):
    """批量创建广告"""
    batch = account.new_batch()
    
    for creative in ad_creatives:
        ad = account.create_ad(
            name=creative['name'],
            creative={
                'title': creative['title'],
                'body': creative['body'],
                'link_url': creative['url']
            },
            campaign_id=creative['campaign_id'],
            adset_id=creative['adset_id']
        )
        batch.add(ad)
    
    response = batch.execute()
    return response
```

---

## 📊 API 配额与限制

| 操作类型 | 每日配额 | 每应用限制 |
|---------|---------|-----------|
| Read 请求 | 200,000 | 200/min |
| Write 请求 | 100,000 | 100/min |
| 报表查询 | 100,000 | 100/min |
| 事件发送 | 无限制 | 根据负载 |

**最佳实践：**
1. 使用 Batch API 批量操作
2. 缓存访问令牌，定期刷新
3. 实现指数退避重试机制
4. 监控应用额度使用情况

---

## 🎓 面试高频问题

**Q: Pixel 和 CAPI 有什么区别？**
A: 三级区别：
1. **数据来源**: Pixel（浏览器）vs CAPI（服务器）
2. **准确性**: CAPI 更准确，不受浏览器限制
3. **iOS 14+**: CAPI 是必需方案

**Q: 如何处理 iOS 14+ 的隐私限制？**
A: 四级方案：
1. **CAPI 优先**: 服务器端事件追踪
2. **聚合事件测量**: 启用 Aggregated Event Measurement
3. **事件优先级**: 设置事件匹配优先级
4. **域名验证**: 完成域名所有权验证

---

## 📚 参考资源

- **官方文档**: https://developers.facebook.com/docs/marketing-apis/
- **SDK 仓库**: https://github.com/facebook/facebook-python-business-sdk
- **Pixel 文档**: https://developers.facebook.com/docs/facebook-pixel/

---

*本解析从 Meta Marketing API 出发，结合生产实践经验，提供独家洞察。*
