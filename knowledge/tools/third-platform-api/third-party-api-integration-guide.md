# 第三方平台 API 集成指南

> Meta Ads、Google Ads、TikTok Ads API 集成。

---

## 1. Meta Ads API

```go
// 获取 Access Token
token, err := meta.GetAccessToken(clientID, clientSecret, code)

// 查询广告账户
accounts, err := meta.GetAccounts(token, fields)

// 创建广告系列
campaign, err := meta.CreateCampaign(token, accountID, params)
```

---

## 2. Google Ads API

```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage('google-ads.yaml')
service = client.get_service('GoogleAdsService')

query = """
    SELECT campaign.id, campaign.name, metrics.impressions
    FROM campaign
    WHERE segments.date >= '2024-01-01'
"""
response = service.search(request=customer_id, query=query)
```

---

## 3. TikTok Ads API

```javascript
const tiktok = require('tiktok-api');

const client = new tiktok.Client({
  access_token: process.env.TIKTOK_TOKEN,
});

const stats = await client.getStats({
  date_range: 'LAST_7_DAYS',
  level: 'AD_SET',
});
```

---

**参考**: 各平台官方 API 文档
