# Google Ads API 工作流

> **来源**: 官方文档 + API 实测
> **更新时间**: 2026-08-26

## 创建搜索广告系列

```python
from google.ads.googleads.client import GoogleAdsClient

def create_search_campaign(client, customer_id, config):
    """创建搜索广告系列"""
    campaign_service = client.get_service('CampaignService')
    
    campaign = client.get_type('Campaign')
    campaign.customer_id = customer_id
    campaign.name = config['name']
    campaign.advertising_channel_type = client.enums.AdvertisingChannelType.SEARCH
    
    # 预算
    budget = client.get_type('CampaignBudget')
    budget.resource_name = f'customers/{customer_id}/campaignBudgets/{config.get("budget_id")}'
    campaign.campaign_budget = budget.resource_name
    
    # 出价策略
    bidding_strategy = client.get_type('ManualCpc')
    bidding_strategy.enhanced_cpc_enabled = True
    campaign.manual_cpc = bidding_strategy
    
    # 状态
    campaign.status = client.enums.CampaignStatus.ENABLED
    
    # 创建
    operation = client.get_type('CampaignOperation')
    operation.create = campaign
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[operation]
    )
    return response.results[0].resource_name
```

## 批量添加关键词

```python
def batch_add_keywords(client, customer_id, ad_group_id, keywords):
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
    return len(response.results)
```

## 查询报表

```python
def get_campaign_report(client, customer_id, date_range):
    """查询 Campaign 报表"""
    google_ads_service = client.get_service('GoogleAdsService')
    
    query = f"""
        SELECT 
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{date_range[0]}' AND '{date_range[1]}'
        ORDER BY metrics.impressions DESC
    """
    
    response = google_ads_service.search(
        customer_id=customer_id,
        query=query
    )
    
    results = []
    for row in response:
        results.append({
            'campaign_id': row.campaign.id,
            'campaign_name': row.campaign.name,
            'impressions': row.metrics.impressions,
            'clicks': row.metrics.clicks,
            'cost': row.metrics.cost_micros / 1000000,
            'conversions': row.metrics.conversions,
        })
    return results
```

## 限流处理

```python
import time
from google.ads.googleads.errors import GoogleAdsException

def safe_mutate(client, customer_id, operation, max_retries=3):
    """安全执行 mutate 操作，自动重试"""
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

## 参考

- [官方文档](https://developers.google.com/google-ads/api/docs/start)
- [Python SDK](https://github.com/googleapis/google-ads-python)
- [GAQL 查询语言](https://developers.google.com/google-ads/api/docs/query/overview)
