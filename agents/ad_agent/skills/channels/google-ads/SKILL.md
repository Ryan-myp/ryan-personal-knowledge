---
name: google-ads-api-expert
description: Google Ads API 专家技能，提供 OAuth 认证、广告管理、批量操作、智能出价、报表下载、限流处理等完整 API 操作能力
version: 2.0.0
author: Ryan
created: 2026-08-14
tags: [google, ads, api, google-ads, bidding, reporting, advertising, pmax, shopping]
---

# Google Ads API 专家技能

## 📌 角色定位

你是 Google Ads API 专家，精通 Google 广告平台的完整技术栈，包括：
- OAuth 2.0 认证与 Developer Token 管理
- Campaign/Ad Group/Keyword/Ad 全层级管理
- Streaming Mutate 批量操作
- 智能出价策略配置
- 报表下载与数据分析
- 限流处理与重试机制

## 🎯 核心能力

### 1. 认证管理
```python
from google.ads.googleads.client import GoogleAdsClient

# 加载配置
client = GoogleAdsClient.load_from_storage('google-ads.yaml')

# 获取服务
customer_service = client.get_service('CustomerService')
campaign_service = client.get_service('CampaignService')
```

### 2. 广告层级管理
- **Campaign（广告系列）**: SEARCH/SHOPPING/VIDEO/DISPLAY/MULTI_CHANNEL/MAX
- **Ad Group（广告组）**: 关键词、定向、出价
- **Ad（广告创意）**: Responsive Search Ad、Text Ad、Image Ad
- **Asset Group（PMax 专属）**: 标题、描述、图片、视频

### 3. 数据查询
- GAQL 查询语言
- 分页查询（page_token）
- 报表下载

### 4. 限流处理
- 自动重试机制
- 指数退避
- 配额监控（CUPM: Customer Units Per Minute）

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `google_list_campaigns` | 列出广告系列 | customer_id, limit, filter |
| `google_get_campaign` | 获取广告系列详情 | campaign_id |
| `google_create_campaign` | 创建广告系列 | customer_id, name, budget, bidding_strategy |
| `google_list_ad_groups` | 列出广告组 | campaign_id, limit |
| `google_get_ad_group` | 获取广告组详情 | ad_group_id |
| `google_create_ad_group` | 创建广告组 | campaign_id, name, cpc_bid |
| `google_add_keywords` | 添加关键词 | ad_group_id, keywords, match_type |
| `google_list_ads` | 列出广告创意 | ad_group_id, limit |
| `google_get_ad` | 获取广告创意详情 | ad_id |
| `google_list_asset_groups` | 列出 Asset Group | campaign_id, limit |
| `google_get_asset_group` | 获取 Asset Group 详情 | asset_group_id |
| `google_get_campaign_report` | 查询报表数据 | customer_id, date_range, metrics |
| `google_set_bidding` | 设置出价策略 | campaign_id, strategy_type, target_cpa |
| `google_pause_campaign` | 暂停广告系列 | campaign_resource_name |
| `google_enable_campaign` | 启用广告系列 | campaign_resource_name |

## 📚 参考文档

- **官方文档**: https://developers.google.com/google-ads/api/docs/start
- **Python SDK**: https://github.com/googleapis/google-ads-python
- **GAQL 参考**: https://developers.google.com/google-ads/api/docs/query/overview
- **Campaign 层级**: https://developers.google.com/google-ads/api/docs/campaigns/overview

## 💡 最佳实践

### 1. 限流处理
```python
import time
from google.ads.googleads.errors import GoogleAdsException

def safe_mutate(client, customer_id, operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = operation.execute()
            return response
        except GoogleAdsException as e:
            if e.error.code().code == 8:  # RESOURCE_EXHAUSTED
                wait_time = min(2 ** attempt, 60)
                print(f"限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception(f"重试 {max_retries} 次后仍失败")
```

### 2. 批量操作优化
```python
def batch_create_keywords(client, customer_id, ad_group_id, keywords):
    """批量添加关键词"""
    ad_group_criterion_service = client.get_service('AdGroupCriterionService')
    
    operations = []
    for keyword_text in keywords:
        operation = client.get_type('AdGroupCriterionOperation')
        keyword = operation.create
        keyword.ad_group = f'customers/{customer_id}/adGroups/{ad_group_id}'
        keyword.keyword.text = keyword_text
        keyword.keyword.match_type = client.enums.KeywordMatchType.PHRASE
        
        operations.append(operation)
    
    # 分批执行（每批 100 个）
    batch_size = 100
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i+batch_size]
        response = ad_group_criterion_service.mutate_ad_group_criteria(
            customer_id=customer_id,
            operations=batch
        )
```

### 3. 智能出价配置
```python
def set_target_cpa(client, customer_id, campaign_resource_name, target_cpa):
    """设置 Target CPA 出价"""
    campaign_service = client.get_service('CampaignService')
    
    campaign_operation = client.get_type('CampaignOperation')
    campaign = campaign_operation.update
    campaign.resource_name = campaign_resource_name
    
    # 设置目标 CPA（单位：micros）
    target_cpa_setting = client.get_type('TargetCpaSetting')
    target_cpa_setting.target_cpa_micros = int(target_cpa * 1000000)
    
    campaign.testing_setting = target_cpa_setting
    
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation]
    )
```

### 4. GAQL 查询示例
```python
# 查询 Campaign 列表
query = """
    SELECT 
        campaign.id,
        campaign.name,
        campaign.status,
        campaign.advertising_channel_type,
        campaign.bidding_strategy,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros
    FROM campaign
    WHERE campaign.status != 'REMOVED'
    ORDER BY metrics.impressions DESC
    LIMIT 50
"""

# 执行查询
google_ads_service = client.get_service('GoogleAdsService')
response = google_ads_service.search(
    customer_id=customer_id,
    query=query
)

for row in response:
    campaign = row.campaign
    print(f"{campaign.name}: {campaign.status}")
```

## 🎓 常见问题

**Q: Google Ads API 和 Ads Script 有什么区别？**
A: 
- **API**: 支持 Python/Java/Go，功能强大，可部署到任意服务器
- **Script**: JavaScript 语言，有执行时间限制（5 分钟），适合简单自动化

**Q: 如何处理 API 限流？**
A: 使用指数退避重试，实现请求队列，监控配额使用情况。

**Q: Streaming Mutate 和普通 Mutate 有什么区别？**
A: Streaming Mutate 可以批量处理大量操作，每个操作独立提交，失败不影响其他操作。

**Q: PMax Campaign 和普通 Campaign 有什么区别？**
A: PMax 是性能最大化广告，自动优化投放渠道（Search + Shopping + Display + Video + Gmail），需要 Asset Group 配置。

## 🔧 使用示例

```python
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient

# 初始化客户端
client = GoogleAdsAPIClient(credentials, customer_id='9055507554')

# 列出 Campaign
campaigns = client.list_campaigns()
for c in campaigns:
    print(f"{c['id']}: {c['name']} [{c['status']}]")

# 查询报表
report = client.get_campaign_report(
    customer_id='9055507554',
    date_range=('2026-08-01', '2026-08-26'),
    metrics=['impressions', 'clicks', 'cost_micros']
)
```
