# Google Ads 最佳实践

## 1. 限流处理

Google Ads API 有严格的速率限制（10,000 CUPM）。实现指数退避重试：

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

## 2. 批量操作优化

使用 Streaming Mutate 批量处理大量操作：

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

## 3. 智能出价配置

### Target CPA
```python
def set_target_cpa(client, customer_id, campaign_resource_name, target_cpa):
    campaign_service = client.get_service('CampaignService')
    
    campaign_operation = client.get_type('CampaignOperation')
    campaign = campaign_operation.update
    campaign.resource_name = campaign_resource_name
    
    target_cpa_setting = client.get_type('TargetCpaSetting')
    target_cpa_setting.target_cpa_micros = int(target_cpa * 1000000)
    campaign.testing_setting = target_cpa_setting
    
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation]
    )
```

### Maximize Conversions
```python
def set_max_conversions(client, customer_id, campaign_resource_name):
    campaign_service = client.get_service('CampaignService')
    
    campaign_operation = client.get_type('CampaignOperation')
    campaign = campaign_operation.update
    campaign.resource_name = campaign_resource_name
    
    # 设置最大化转化出价策略
    bidding_strategy = campaign_service.bidding_strategy_path(
        customer_id, 'bidding-strategy-id'
    )
    campaign.bidding_strategy = bidding_strategy
    
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation]
    )
```

## 4. GAQL 查询示例

```python
# 查询 Campaign 表现
query = """
    SELECT 
        campaign.id,
        campaign.name,
        campaign.status,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions
    FROM campaign
    WHERE campaign.status != 'REMOVED'
    ORDER BY metrics.impressions DESC
    LIMIT 50
"""

google_ads_service = client.get_service('GoogleAdsService')
response = google_ads_service.search(
    customer_id=customer_id,
    query=query
)

for row in response:
    campaign = row.campaign
    print(f"{campaign.name}: {campaign.status}")
```

## 5. 常见问题

**Q: 如何处理 API 限流？**
A: 使用指数退避重试，实现请求队列，监控配额使用情况。

**Q: Streaming Mutate 和普通 Mutate 有什么区别？**
A: Streaming Mutate 可以批量处理大量操作，每个操作独立提交，失败不影响其他操作。

**Q: PMax Campaign 和普通 Campaign 有什么区别？**
A: PMax 是性能最大化广告，自动优化投放渠道，需要 Asset Group 配置。
