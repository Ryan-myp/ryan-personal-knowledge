# Google Ads API 生产环境完整指南

> **领域**: 广告投放 / Google Ads
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: google-ads, api, campaigns, ad-groups, keywords, bidding, reporting
> **更新时间**: 2026-08-14
> **类型**: api-guide/production

---

## 📌 Google Ads API 概览

### 1. API 架构

```
┌─────────────────────────────────────────────────────┐
│              Google Ads API Architecture             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Client Application                                 │
│  ├── OAuth2 Authentication                          │
│  ├── Client Library (Python/Java/Go)               │
│  └── gRPC/REST Interface                            │
│         │                                            │
│         ▼                                            │
│  Google Ads API Server                              │
│  ├── MutateService (读写)                           │
│  ├── QueryService (只读)                            │
│  ├── ReportDefinitionService (报表)                │
│  └── CustomerService (账户管理)                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 2. 核心端点

```python
# 官方客户端库安装
pip install google-ads

# 配置凭证
from google.ads.googleads.client import GoogleAdsClient

# 加载配置（google-ads.yaml）
client = GoogleAdsClient.load_from_storage('google-ads.yaml')

# 获取服务
customer_service = client.get_service('CustomerService')
campaign_service = client.get_service('CampaignService')
ad_group_service = client.get_service('AdGroupService')
```

---

## 🔥 核心功能实现

### 1. 创建广告系列

```python
def create_campaign(client, customer_id, budget_resource_name):
    """创建标准广告系列"""
    campaign_service = client.get_service("CampaignService")
    
    campaign_operation = client.get_type("CampaignOperation")
    campaign = campaign_operation.create
    campaign.resource_name = f"customers/{customer_id}/campaigns/-"
    campaign.name = "Summer Sale 2026"
    campaign.advertising_channel_type = client.enums.AdvertisingChannelType.SEARCH
    
    # 出价策略
    campaign.standard_campaign_budget = budget_resource_name
    campaign.manual_cpc = client.get_type("ManualCpc")
    
    # 网络目标
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = True
    
    # 投放状态
    campaign.status = client.enums.CampaignStatus.PAUSED
    
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation]
    )
    
    return response.results[0].resource_name
```

### 2. 批量创建广告组

```python
def batch_create_ad_groups(client, customer_id, campaign_resource_name, keywords):
    """批量创建广告组并添加关键词"""
    ad_group_service = client.get_service("AdGroupService")
    keyword_service = client.get_service("KeywordService")
    
    operations = []
    
    for keyword_text in keywords[:10]:  # 每 10 个关键词一组
        # 创建广告组
        ad_group_op = client.get_type("AdGroupOperation")
        ad_group = ad_group_op.create
        ad_group.campaign = campaign_resource_name
        ad_group.name = f"AdGroup_{keyword_text[:20]}"
        ad_group.status = client.enums.AdGroupStatus.ENABLED
        
        # 设置 CPC 出价
        ad_group.cpc_bid_micros = 500000  # $0.50
        
        operations.append(ad_group_op)
        
        # 添加关键词
        keyword_op = client.get_type("AdGroupCriterionOperation")
        keyword = keyword_op.create
        keyword.ad_group = ad_group.resource_name
        keyword.keyword.text = keyword_text
        keyword.keyword.match_type = client.enums.KeywordMatchType.PHRASE
        keyword.negative = False
        
        operations.append(keyword_op)
    
    # 分批执行（每批 10 个）
    batch_size = 10
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i+batch_size]
        response = ad_group_service.mutate_ad_groups(
            customer_id=customer_id,
            operations=batch[:len(batch)//2]  # 只处理 ad_group operations
        )
        
        # 单独处理 keyword operations
        keyword_ops = [op for op in batch if 'AdGroupCriterionOperation' in str(type(op))]
        if keyword_ops:
            keyword_service.mutate_ad_group_criteria(
                customer_id=customer_id,
                operations=keyword_ops
            )
```

### 3. 智能出价策略

```python
def create_smart_bidding(client, customer_id, campaign_resource_name):
    """创建智能出价策略"""
    campaign_service = client.get_service("CampaignService")
    
    campaign_operation = client.get_type("CampaignOperation")
    campaign = campaign_operation.update
    campaign.resource_name = campaign_resource_name
    
    # Target CPA 出价
    campaign.bidding_strategy = client.get_service("BiddingStrategyService").bidding_strategy_path(
        customer_id, "smart-bidding-strategy-id"
    )
    
    # 或者使用 Target ROAS
    target_roas_setting = client.get_type("TargetRoasSetting")
    target_roas_setting.target_roas = 4.0  # 目标 ROAS 400%
    
    campaign.maximum_roas = target_roas_setting
    
    # 更新广告系列
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation]
    )
    
    return response.results[0].resource_name
```

---

## 💡 生产实践要点

### 1. 限流处理

```python
import time
from google.ads.googleads.errors import GoogleAdsException

def safe_mutate(client, customer_id, operation, max_retries=3):
    """带重试的 mutate 操作"""
    for attempt in range(max_retries):
        try:
            response = operation.execute()
            return response
        except GoogleAdsException as e:
            if e.error.code().code == 8:  # RESOURCE_EXHAUSTED
                wait_time = min(2 ** attempt, 60)  # 指数退避，最多 60 秒
                print(f"限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception(f"重试 {max_retries} 次后仍失败")
```

### 2. 批量查询优化

```python
def query_performance(client, customer_id, date_range):
    """高效查询广告表现数据"""
    google_ads_service = client.get_service("GoogleAdsService")
    
    query = f"""
        SELECT 
            campaign.name,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            segments.date
        FROM campaign
        WHERE segments.date BETWEEN '{date_range.start}' AND '{date_range.end}'
        ORDER BY metrics.impressions DESC
        LIMIT 1000
    """
    
    # 使用分页查询
    results = []
    page_token = None
    
    while True:
        response = google_ads_service.search(
            customer_id=customer_id,
            query=query,
            page_size=1000,
            page_token=page_token
        )
        
        results.extend(response.results)
        
        if not response.next_page_token:
            break
        page_token = response.next_page_token
    
    return results
```

### 3. 数据同步策略

```python
from datetime import datetime, timedelta

def sync_daily_data(client, customer_id):
    """每日数据同步"""
    google_ads_service = client.get_service("GoogleAdsService")
    
    # 计算日期范围（昨天到今天）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    date_range = f"'{start_date.strftime('%Y-%m-%d')}' TO '{end_date.strftime('%Y-%m-%d')}'"
    
    query = f"""
        SELECT 
            campaign.name,
            ad_group.name,
            ad_group_ad.resource_name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.cost_per_conversion,
            segments.device.as_string()
        FROM ad_group_ad
        WHERE segments.date BETWEEN {date_range}
        ORDER BY metrics.impressions DESC
    """
    
    # 保存到数据库
    save_to_database(customer_id, query)
```

---

## 📊 API 配额与限制

| 操作类型 | 每日配额 | 每租户限制 |
|---------|---------|-----------|
| Get 请求 | 100,000 | 200/min |
| Mutate 请求 | 10,000 | 10/min |
| 报表下载 | 1,000 | 10/min |
| Streaming mutate | 无限制 | 根据负载 |

**最佳实践：**
1. 使用 streaming mutate 批量写入
2. 实现指数退避重试机制
3. 缓存查询结果，减少重复请求
4. 使用批量操作代替循环

---

## 🎓 面试高频问题

**Q: Google Ads API 和 Ads Script 有什么区别？**
A: 四级区别：
1. **语言**: API (Python/Java/Go) vs Script (JavaScript)
2. **功能**: API 更强大，支持复杂逻辑
3. **限制**: Script 有执行时间限制（5 分钟）
4. **部署**: API 可部署到任意服务器

**Q: 如何处理 API 限流？**
A: 三级处理：
1. **检测**: 捕获 `RESOURCE_EXHAUSTED` 错误
2. **退避**: 指数退避（2s, 4s, 8s...）
3. **队列**: 使用消息队列异步处理

---

## 📚 参考资源

- **官方文档**: https://developers.google.com/google-ads/api/docs/start
- **客户端库**: https://github.com/googleapis/google-ads-python
- **示例代码**: https://github.com/googleapis/google-ads-python/tree/master/examples

---

*本指南从生产实践出发，结合官方文档和实战经验，提供独家洞察。*
