---
name: google-ads-api-expert
description: Google Ads API 专家技能，提供 OAuth 认证、广告管理、批量操作、智能出价、报表下载、限流处理等完整 API 操作能力
version: 1.0.0
author: Ryan
created: 2026-08-14
tags: [google, ads, api, google-ads, bidding, reporting, advertising]
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

### 2. 广告管理
- 创建/更新/暂停广告系列
- 批量操作（Streaming Mutate）
- 智能出价策略配置
- 关键词管理

### 3. 报表查询
- GAQL 查询语言
- 分页查询
- 报表下载

### 4. 限流处理
- 自动重试机制
- 指数退避
- 配额监控

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `google_auth` | OAuth 认证 | developer_token, refresh_token, customer_id |
| `google_create_campaign` | 创建广告系列 | customer_id, name, budget, bidding_strategy |
| `google_create_ad_group` | 创建广告组 | campaign_id, name, cpc_bid |
| `google_add_keywords` | 添加关键词 | ad_group_id, keywords, match_type |
| `google_create_ads` | 创建广告创意 | ad_group_id, ads_config |
| `google_set_bidding` | 设置出价策略 | campaign_id, strategy_type, target_cpa |
| `google_download_report` | 下载报表 | customer_id, query, date_range |
| `google_streaming_mutate` | 批量操作 | customer_id, operations |
| `google_get_metrics` | 查询指标 | customer_id, date_range, metrics |
| `google_pause_campaign` | 暂停广告系列 | campaign_resource_name |
| `google_enable_campaign` | 启用广告系列 | campaign_resource_name |

## 📚 参考文档

- **官方文档**: https://developers.google.com/google-ads/api/docs/start
- **Python SDK**: https://github.com/googleapis/google-ads-python
- **GAQL 参考**: https://developers.google.com/google-ads/api/docs/query/overview

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
    
    # 设置目标 CPA
    tpub bidding_strategy = campaign_service.bidding_strategy_path(
        customer_id, 'bidding-strategy-id'
    )
    campaign.bidding_strategy = bidding_strategy
    
    # 设置 Target CPA
    target_cpa_setting = client.get_type('TargetCpaSetting')
    target_cpa_setting.target_cpa_micros = int(target_cpa * 1000000)
    
    response = campaign_service.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_operation]
    )
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
