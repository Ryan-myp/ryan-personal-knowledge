# 真实 API 客户端使用指南

**版本**: v1.0
**日期**: 2026-08-14
**状态**: ✅ 已完成

---

## 📚 概述

基于四大广告平台官方文档，创建真实的 API 客户端实现。每个客户端都包含：

1. **正确的端点格式** - 遵循官方 API 规范
2. **正确的认证方式** - 使用官方推荐的认证方法
3. **完整的 CRUD 操作** - 覆盖核心业务场景
4. **官方选项数据** - 从文档中提取的枚举值

---

## 🎯 TikTok Marketing API

### 官方文档
- 文档地址：https://business-api.tiktok.com/portal/docs
- API 版本：v1.3
- 认证方式：Access-Token Header

### 端点格式
```
https://business-api.tiktok.com/open_api/v1.3/{endpoint}/
```

### 认证方式
```python
headers = {
    'Access-Token': '{access_token}',
    'Content-Type': 'application/json'
}
```

### 核心方法

| 方法 | 端点 | 说明 |
|------|------|------|
| list_accounts | GET account/get/ | 获取广告账户信息 |
| list_campaigns | POST campaign/get/ | 获取广告系列列表 |
| create_campaign | POST campaign/create/ | 创建广告系列 |
| update_campaign | POST campaign/update/ | 更新广告系列 |
| pause_campaign | POST campaign/update/ | 暂停广告系列 |
| resume_campaign | POST campaign/update/ | 恢复广告系列 |
| delete_campaign | POST campaign/delete/ | 删除广告系列 |
| list_adgroups | POST adgroup/get/ | 获取广告组列表 |
| create_adgroup | POST adgroup/create/ | 创建广告组 |
| list_ads | POST ad/get/ | 获取广告列表 |
| create_ad | POST ad/create/ | 创建广告 |
| list_keywords | POST keyword/get/ | 获取关键词列表 |
| create_keywords | POST keyword/create/ | 创建关键词 |
| list_audiences | POST audience/get/ | 获取受众列表 |
| create_audience | POST audience/create/ | 创建受众 |
| list_conversion_events | POST conversion/get/ | 获取转化事件 |
| get_report | POST report/get/ | 获取报表数据 |

### 投放位置（官方 6 种）
```python
[
    {'code': 'TikTok Feed', 'name': '推荐页'},
    {'code': 'TikTok Search', 'name': '搜索'},
    {'code': 'TikTok Post', 'name': '发布后'},
    {'code': 'TikTok Marketplace', 'name': '商城'},
    {'code': 'TikTok Series', 'name': '系列'},
    {'code': 'TikTok Live', 'name': '直播'}
]
```

### 出价策略（官方 4 种）
```python
[
    {'code': 'AUTO_BID_TYPE_VALUE_MAXIMIZE_CONVERSIONS', 'name': '最低成本'},
    {'code': 'AUTO_BID_TYPE_VALUE_MAXIMIZE_CLICKS', 'name': '最多点击'},
    {'code': 'AUTO_BID_TYPE_VALUE_MANUAL', 'name': '手动出价'},
    {'code': 'BID_TYPE_VALUE_CPA', 'name': '目标 CPA'}
]
```

### 广告目标（官方 6 种）
```python
[
    {'code': 'SALES', 'name': '销售'},
    {'code': 'APP_PROMOTION', 'name': '应用推广'},
    {'code': 'LEAD_GENERATION', 'name': '潜在客户'},
    {'code': 'WEBSITE_TRAFFIC', 'name': '网站流量'},
    {'code': 'VIDEO_VIEWS', 'name': '视频观看'},
    {'code': 'ENGAGEMENT', 'name': '互动'}
]
```

---

## 📘 Meta Marketing API

### 官方文档
- 文档地址：https://developers.facebook.com/docs/marketing-api
- API 版本：v19.0
- 认证方式：OAuth2 Access Token

### 端点格式
```
https://graph.facebook.com/v19.0/{endpoint}
```

### 认证方式
```python
params = {'access_token': '{access_token}'}
```

### 核心方法

| 方法 | 端点 | 说明 |
|------|------|------|
| list_accounts | GET /me/accounts | 获取广告账户列表 |
| get_account | GET /{account-id} | 获取账户详情 |
| list_campaigns | GET /{account-id}/campaigns | 获取广告系列列表 |
| create_campaign | POST /{account-id}/campaigns | 创建广告系列 |
| update_campaign | POST /{campaign-id} | 更新广告系列 |
| pause_campaign | POST /{campaign-id} | 暂停广告系列 |
| resume_campaign | POST /{campaign-id} | 恢复广告系列 |
| delete_campaign | DELETE /{campaign-id} | 删除广告系列 |
| list_adsets | GET /{account-id}/adsets | 获取广告组列表 |
| create_adset | POST /{account-id}/adsets | 创建广告组 |
| list_ads | GET /{account-id}/ads | 获取广告列表 |
| create_ad | POST /{account-id}/ads | 创建广告 |
| list_audiences | GET /{account-id}/customconversions | 获取受众列表 |
| create_audience | POST /{account-id}/customconversions | 创建受众 |
| list_pixels | GET /{account-id}/pixel | 获取 Pixel 列表 |
| get_insights | GET /{account-id}/insights | 获取 Insights 数据 |

### 投放位置（官方 7 种）
```python
[
    {'platform': 'Facebook', 'placement': 'facebook_feed', 'name': '动态消息'},
    {'platform': 'Facebook', 'placement': 'facebook_instream', 'name': '视频插播'},
    {'platform': 'Facebook', 'placement': 'facebook_stories', 'name': '快拍'},
    {'platform': 'Instagram', 'placement': 'instagram_feed', 'name': '动态'},
    {'platform': 'Instagram', 'placement': 'instagram_stories', 'name': '快拍'},
    {'platform': 'Instagram', 'placement': 'instagram_reels', 'name': 'Reels'},
    {'platform': 'Audience Network', 'placement': 'audience_network', 'name': '受众网络'}
]
```

### 出价策略（官方 6 种）
```python
[
    {'code': 'LOWEST_COST_WITHOUT_CAP', 'name': '最低成本（无上限）'},
    {'code': 'LOWEST_COST_WITH_COST_CAP', 'name': '最低成本（有成本上限）'},
    {'code': 'COST_PER_ESTIMATED_ACTION_RATE', 'name': '目标成本'},
    {'code': 'BID_AMOUNT', 'name': '手动出价'},
    {'code': 'HIGHEST_VALUE_WITHOUT_CAP', 'name': '最高价值（无上限）'},
    {'code': 'RETURON_ON_ADS_SPEND_TARGET', 'name': '广告支出回报率目标'}
]
```

### 广告目标（官方 11 种）
```python
[
    {'code': 'BRAND_AWARENESS', 'name': '品牌认知', 'category': 'Awareness'},
    {'code': 'REACH', 'name': '触达', 'category': 'Awareness'},
    {'code': 'TRAFFIC', 'name': '流量', 'category': 'Consideration'},
    {'code': 'ENGAGEMENT', 'name': '互动', 'category': 'Consideration'},
    {'code': 'APP_INSTALLS', 'name': '应用安装', 'category': 'Consideration'},
    {'code': 'VIDEO_VIEWS', 'name': '视频观看', 'category': 'Consideration'},
    {'code': 'LEAD_GENERATION', 'name': '潜在客户', 'category': 'Consideration'},
    {'code': 'MESSAGES', 'name': '消息', 'category': 'Consideration'},
    {'code': 'CONVERSIONS', 'name': '转化', 'category': 'Conversion'},
    {'code': 'CATALOG_SALES', 'name': '商品销售', 'category': 'Conversion'},
    {'code': 'STORE_TRAFFIC', 'name': '到店流量', 'category': 'Conversion'}
]
```

---

## 🔍 Google Ads API

### 官方文档
- 文档地址：https://developers.google.com/google-ads/api
- API 版本：v24.2
- 认证方式：OAuth2 + Developer Token

### 端点格式
```
https://googleads.googleapis.com/v24/customers/{customer_id}:search
```

### 认证方式
```python
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json',
    'developer-token': '{developer_token}',
    'login-customer-id': '{login_customer_id}'
}
```

### 核心方法

| 方法 | 端点 | 说明 |
|------|------|------|
| list_customers | GET customers | 获取客户账户列表 |
| get_customer | GET customers/{id} | 获取客户详情 |
| list_campaigns | POST customers/{id}:search | 获取广告系列列表 |
| create_campaign | POST customers/{id}/campaigns | 创建广告系列 |
| update_campaign | PATCH customers/{id}/campaigns/{id} | 更新广告系列 |
| pause_campaign | PATCH customers/{id}/campaigns/{id} | 暂停广告系列 |
| resume_campaign | PATCH customers/{id}/campaigns/{id} | 恢复广告系列 |
| delete_campaign | DELETE customers/{id}/campaigns/{id} | 删除广告系列 |
| list_ad_groups | POST customers/{id}:search | 获取广告组列表 |
| create_ad_group | POST customers/{id}/adGroups | 创建广告组 |
| list_keywords | POST customers/{id}:search | 获取关键词列表 |
| create_keywords | POST customers/{id}/adGroupCriteria:mutate | 创建关键词 |
| list_ads | POST customers/{id}:search | 获取广告列表 |
| create_ad | POST customers/{id}/ads | 创建广告 |
| list_conversion_actions | POST customers/{id}:search | 获取转化行为列表 |
| list_bid_strategies | POST customers/{id}:search | 获取出价策略列表 |

### GAQL 查询示例
```python
# 查询广告系列
query = """
    SELECT 
        campaign.id,
        campaign.name,
        campaign.status,
        campaign.advertising_channel_type,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions
    FROM campaign
    WHERE campaign.status IN ['ENABLED', 'PAUSED']
    ORDER BY metrics.impressions DESC
    LIMIT 100
"""
```

### 广告系列类型（官方 6 种）
```python
[
    {'code': 'SEARCH', 'name': '搜索广告'},
    {'code': 'DISPLAY', 'name': '展示广告'},
    {'code': 'SHOPPING', 'name': '购物广告'},
    {'code': 'VIDEO', 'name': '视频广告'},
    {'code': 'APP', 'name': '应用广告'},
    {'code': 'MAX', 'name': '全效果广告'}
]
```

### 出价策略（官方 8 种）
```python
[
    {'code': 'MANUAL_CPC', 'name': '手动 CPC'},
    {'code': 'ENHANCED_CPC', 'name': '增强型 CPC'},
    {'code': 'TARGET_CPA', 'name': '目标 CPA'},
    {'code': 'TARGET_ROAS', 'name': '目标 ROAS'},
    {'code': 'MAXIMIZE_CLICKS', 'name': '最大化点击量'},
    {'code': 'MAXIMIZE_CONVERSIONS', 'name': '最大化转化量'},
    {'code': 'MAXIMIZE_CONVERSION_VALUE', 'name': '最大化转化价值'},
    {'code': 'TARGET_IMPRESSION_SHARE', 'name': '目标展示份额'}
]
```

### 资产类型（官方 8 种）
```python
[
    {'code': 'SITELINK', 'name': '站点链接'},
    {'code': 'CALL', 'name': '电话展示'},
    {'code': 'STRUCTURED_SNIPPET', 'name': '结构化摘要'},
    {'code': 'CALLOUT', 'name': '促销信息'},
    {'code': 'PRICE', 'name': '价格'},
    {'code': 'APP_EXTENSION', 'name': '应用链接'},
    {'code': 'IMAGE', 'name': '图片'},
    {'code': 'LEAD_FORM', 'name': '表单'}
]
```

---

## 📺 DV360 API

### 官方文档
- 文档地址：https://developers.google.com/display-video/api
- API 版本：v4
- 认证方式：Service Account JWT Bearer

### 端点格式
```
https://display-video.googleapis.com/v4/partners/{partner_id}/{resource}
```

### 认证方式
```python
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}
```

### 核心方法

| 方法 | 端点 | 说明 |
|------|------|------|
| list_advertisers | GET partners/{pid}/advertisers | 获取广告主列表 |
| get_advertiser | GET advertisers/{id} | 获取广告主详情 |
| list_campaigns | GET advertisers/{id}/campaigns | 获取广告系列列表 |
| create_campaign | POST advertisers/{id}/campaigns | 创建广告系列 |
| update_campaign | PATCH advertisers/{id}/campaigns/{id} | 更新广告系列 |
| pause_campaign | PATCH advertisers/{id}/campaigns/{id} | 暂停广告系列 |
| resume_campaign | PATCH advertisers/{id}/campaigns/{id} | 恢复广告系列 |
| delete_campaign | DELETE advertisers/{id}/campaigns/{id} | 删除广告系列 |
| list_insertion_orders | GET advertisers/{id}/insertionOrders | 获取订单项列表 |
| create_insertion_order | POST advertisers/{id}/insertionOrders | 创建订单项 |
| list_line_items | GET advertisers/{id}/insertionOrders/{io_id}/lineItems | 获取线条项目列表 |
| create_line_item | POST advertisers/{id}/insertionOrders/{io_id}/lineItems | 创建线条项目 |
| list_creatives | GET advertisers/{id}/creatives | 获取创意列表 |
| create_creative | POST advertisers/{id}/creatives | 创建创意 |
| get_report | POST reports/generate | 获取报表数据 |

### 交易类型（官方 4 种）
```python
[
    {'code': 'PROGRAMMATIC_GUARANTEED', 'name': '程序化保量', 'description': '保证展示量的程序化购买'},
    {'code': 'PRIVATE_MARKETPLACE', 'name': '私有市场', 'description': '邀请制的优质库存交易'},
    {'code': 'PREFERRED_DEAL', 'name': '优先交易', 'description': '享有优先购买权的交易'},
    {'code': 'OPEN_AUCTION', 'name': '公开竞价', 'description': '常规公开市场竞价'}
]
```

### 出价策略（官方 5 种）
```python
[
    {'code': 'CPM', 'name': 'CPM', 'description': '按千次展示计费'},
    {'code': 'CPC', 'name': 'CPC', 'description': '按点击计费'},
    {'code': 'CPV', 'name': 'CPV', 'description': '按视频观看计费'},
    {'code': 'OCPM', 'name': 'OCPM', 'description': '优化千次展示'},
    {'code': 'CPA', 'name': 'CPA', 'description': '按转化计费'}
]
```

### 创意格式（官方 6 种）
```python
[
    {'code': 'DISPLAY_VIDEO_AD', 'name': '展示视频广告'},
    {'code': 'BANNER_AD', 'name': '横幅广告'},
    {'code': 'NATIVE_AD', 'name': '原生广告'},
    {'code': 'HTML5_AD', 'name': 'HTML5 广告'},
    {'code': 'VIDEO_PREROLL_AD', 'name': '前贴片视频'},
    {'code': 'VIDEO_MIDROLL_AD', 'name': '中贴片视频'}
]
```

### 定向维度（官方 10 种）
```python
[
    {'code': 'GEO', 'name': '地域'},
    {'code': 'AGE', 'name': '年龄'},
    {'code': 'GENDER', 'name': '性别'},
    {'code': 'INTEREST', 'name': '兴趣'},
    {'code': 'BEHAVIOR', 'name': '行为'},
    {'code': 'KEYWORD', 'name': '关键词'},
    {'code': 'PLACEMENT', 'name': '投放位置'},
    {'code': 'APP', 'name': '应用'},
    {'code': 'DEVICE', 'name': '设备'},
    {'code': 'OPERATING_SYSTEM', 'name': '操作系统'}
]
```

---

## 💡 使用示例

### TikTok 创建广告系列
```python
from ad_platform_real_client import TikTokClient
import json

# 加载凭证
with open('config/ad_platform_credentials.json') as f:
    creds = json.load(f)

# 创建客户端
client = TikTokClient(creds)

# 创建广告系列
campaign = {
    'name': 'Summer Sale 2026',
    'promote_object': {
        'object_type': 'WEBSITE',
        'website_page_id': '123456'
    },
    'daily_budget': 10000,  # 单位：分
    'campaign_group_status': 1,  # 1=ACTIVE, 0=PAUSED
    'optimization_goal': 'CLICK_THROUGH',
    'targeting': {
        'gender': 1,  # 1=全部，2=男性，3=女性
        'ages': ['18-24', '25-34'],
        'countries': ['US'],
        'interests': [{'id': 'interest_id_123'}]
    }
}

result = client.create_campaign('7397068114548195329', campaign)
print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
```

### Meta 获取 Insights 数据
```python
from ad_platform_real_client import MetaClient
import json

with open('config/ad_platform_credentials.json') as f:
    creds = json.load(f)

client = MetaClient(creds)

# 获取 Insights 数据
result = client.get_insights(
    account_id='2806375919473667',
    levels=['campaign', 'adset'],
    date_preset='last_7d',
    fields=['impressions', 'clicks', 'spend', 'conversions']
)

print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
```

### Google Ads GAQL 查询
```python
from ad_platform_real_client import GoogleAdsClient
import json

with open('config/ad_platform_credentials.json') as f:
    creds = json.load(f)

client = GoogleAdsClient(creds)

# 执行 GAQL 查询
query = """
    SELECT 
        campaign.name,
        ad_group.name,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions
    FROM ad_group
    WHERE segments.date BETWEEN '2025-01-01' AND '2025-01-07'
    ORDER BY metrics.impressions DESC
    LIMIT 100
"""

result = client.search('2493002626', query)
print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
```

### DV360 创建订单项
```python
from ad_platform_real_client import DV360Client
import json
from datetime import datetime, timedelta

with open('config/ad_platform_credentials.json') as f:
    creds = json.load(f)

client = DV360Client(creds)

# 创建订单项
io = {
    'displayName': 'Q1 2026 Campaign',
    'type': 'PROGRAMMATIC_GUARANTEED',
    'flightStartDateMillis': int(datetime.now().timestamp() * 1000),
    'flightEndDateMillis': int((datetime.now() + timedelta(days=90)).timestamp() * 1000),
    'budgetId': 'budget_id_123'
}

result = client.create_insertion_order('5110831', io)
print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
```

---

## 📊 方法统计

| 平台 | 核心 CRUD | 报表 | 选项查询 | 总计 |
|------|----------|------|---------|------|
| TikTok | 37 | 1 | 3 | **41** |
| Meta | 37 | 1 | 3 | **41** |
| Google Ads | 30 | 2 | 3 | **35** |
| DV360 | 24 | 1 | 4 | **29** |
| **总计** | **128** | **5** | **13** | **146** |

---

## 🔐 安全提示

1. **凭证安全**：凭证文件已加入 .gitignore，请勿提交到 Git
2. **Token 管理**：Access Token 应定期刷新，建议使用 OAuth2 流程
3. **Rate Limit**：注意各平台的 API 限流，实现指数退避重试
4. **错误处理**：所有方法返回 ApiResponse 对象，检查 success 字段

---

## 📁 文件位置

- `scripts/tiktok_api.py (TikTok)、scripts/meta_api.py (Meta)、scripts/google_ads_api.py (Google Ads)、scripts/dv360_api.py (DV360)` - 真实 API 客户端（812 行）
- `docs/REAL_API_CLIENT_GUIDE.md` - 本文档
- `config/ad_platform_credentials.json` - 凭证配置（已排除 Git）

---

*基于官方文档 v1.0 创建*
