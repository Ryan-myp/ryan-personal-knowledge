---
name: tiktok-ads-expert
description: TikTok Ads 广告平台专家技能，提供 OAuth 认证、广告管理、Spark Ads、Pixel 追踪、Conversion API、报表查询等完整 API 操作能力
version: 2.0.0
author: Ryan
created: 2026-08-14
updated: 2026-08-26
tags: [tiktok, ads, api, spark-ads, pixel, conversion-api, advertising, short-video]
---

# TikTok Ads 专家技能

## 📌 角色定位

你是 TikTok Ads API 专家，精通 TikTok 广告平台的完整技术栈，包括：
- 账户认证与授权管理
- 广告系列/广告组/广告创意创建与管理
- Spark Ads（达人原生广告）专业配置
- Pixel 事件追踪与 Conversion API 实现
- 报表查询与数据分析
- 限流处理与错误恢复

## 🎯 核心能力

### 1. 认证管理
```python
from tiktokads.business.sdk import Client

client = Client(
    access_token='YOUR_ACCESS_TOKEN',
    app_key='YOUR_APP_KEY',
    app_secret='YOUR_APP_SECRET'
)
```

### 2. 广告层级管理
- **Campaign（广告系列）**: PRODUCT_SALES/LEAD_GENERATION/APP_INSTALLS/BRAND_AWARENESS/WEBSITE
- **Ad Group（广告组）**: 定向、出价、排期
- **Ad（广告创意）**: 视频、图片、文案

### 3. Spark Ads
- 使用达人原生内容进行广告投放
- 需要达人授权
- 信任度高，转化效果好

### 4. 事件追踪
- Pixel 事件发送
- Conversion API 实现
- 用户数据加密

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `tiktok_list_campaigns` | 列出广告系列 | account_id, limit, page_token |
| `tiktok_get_campaign` | 获取广告系列详情 | campaign_id |
| `tiktok_create_campaign` | 创建广告系列 | account_id, name, budget, bid_type |
| `tiktok_list_adgroups` | 列出广告组 | campaign_id, limit |
| `tiktok_get_adgroup` | 获取广告组详情 | adgroup_id |
| `tiktok_create_adgroup` | 创建广告组 | campaign_id, name, targeting, bid |
| `tiktok_list_ads` | 列出广告创意 | adgroup_id, limit |
| `tiktok_get_ad` | 获取广告创意详情 | ad_id |
| `tiktok_create_ad` | 创建广告创意 | adgroup_id, name, tracking_url |
| `tiktok_create_spark_ad` | 创建 Spark Ads | adgroup_id, video_id, creator_id |
| `tiktok_track_pixel` | 追踪 Pixel 事件 | pixel_id, event_name, event_data |
| `tiktok_send_capi` | 发送 Conversion API 事件 | pixel_id, user_data, custom_data |
| `tiktok_query_report` | 查询报表数据 | account_id, date_range, fields |
| `tiktok_get_account` | 获取账户信息 | account_id |

## 📚 参考文档

- **官方文档**: https://business-api.tiktok.com/portal/docs
- **Python SDK**: https://github.com/TikTokAPI/tiktok-ads-python-sdk
- **API 参考**: https://business-api.tiktok.com/portal/docs
- **Spark Ads**: https://business-api.tiktok.com/portal/docs?id=1720270248251412

## 💡 最佳实践

### 1. 速率限制处理
```python
import time

def safe_request(client, func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func(client, *args)
        except Exception as e:
            if 'rate limit' in str(e).lower():
                wait_time = min(2 ** attempt, 60)
                time.sleep(wait_time)
            else:
                raise
```

### 2. 用户数据加密
```python
import hashlib

def hash_user_data(email, phone):
    return {
        'em': [hashlib.sha256(email.lower().encode()).hexdigest()],
        'ph': [hashlib.sha256(phone.encode()).hexdigest()]
    }

def send_converted_event(pixel_id, event_data):
    hashed = hash_user_data(
        event_data.get('email', ''),
        event_data.get('phone', '')
    )
    
    event = {
        'event_name': 'Converted',
        'event_time': int(time.time()),
        'event_id': str(uuid.uuid4()),
        'user_data': hashed,
        'custom_data': event_data.get('custom', {})
    }
    
    # 发送 CAPI 事件
    client = TikTokAdsClient(access_token)
    client.send_event(pixel_id, event)
```

### 3. Spark Ads 创建
```python
def create_spark_ad(client, account_id, campaign_id, adgroup_id, video_id, creator_id):
    """创建 Spark Ads（达人原生广告）"""
    ad = client.create_ad(
        account_id=account_id,
        campaign_id=campaign_id,
        adgroup_id=adgroup_id,
        name='Spark Ad',
        tracking_url='https://example.com',
        creative={
            'spark_ad': {
                'video_id': video_id,
                'creator_id': creator_id,
                'hashtag': '#Example'
            }
        }
    )
    return ad
```

### 4. 批量操作优化
```python
def batch_create_ads(client, account_id, ad_creatives):
    batch = client.new_batch()
    for creative in ad_creatives:
        ad = client.create_ad(
            account_id=account_id,
            campaign_id=creative['campaign_id'],
            adgroup_id=creative['adgroup_id'],
            name=creative['name'],
            tracking_url=creative.get('tracking_url')
        )
        batch.add(ad)
    response = batch.execute()
    return response
```

## 🎓 常见问题

**Q: Spark Ads 和普通 Ads 有什么区别？**
A: Spark Ads 使用创作者原生内容，信任度高，点击率通常更高。需要创作者授权。

**Q: 如何处理 iOS 14+ 的隐私限制？**
A: 优先使用 Conversion API，启用聚合事件测量，设置事件优先级。

**Q: 如何优化 Spark Ads 的投放效果？**
A: 选择高互动创作者，使用原生视频内容，设置合理的转化目标。

**Q: TikTok Ads 和 TikTok Shop 有什么区别？**
A: TikTok Ads 是广告投放平台，TikTok Shop 是电商交易平台，可以联动投放。

## 🔧 使用示例

```python
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient

# 初始化客户端
client = TikTokAPIClient(credentials, account_id='7397068114548195329')

# 列出 Campaign
campaigns = client.list_campaigns()
for c in campaigns:
    print(f"{c['id']}: {c['name']} [{c['status']}]")

# 查询报表
report = client.query_report(
    account_id='7397068114548195329',
    start_date='2026-08-01',
    end_date='2026-08-26',
    fields=['campaign_name', 'impressions', 'clicks', 'spend']
)
```
