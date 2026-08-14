# Google Ads API 专家级指南 2025

> 基于 Google Ads API v25 官方文档蒸馏 | 生产环境最佳实践

---

## 一、API 架构核心认知

### 1.1 关键服务与客户端

```python
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

# ✅ 生产环境推荐：每次请求创建新鲜 client
def get_fresh_client(developer_token, refresh_token, client_id, client_secret, login_customer_id):
    """创建新鲜客户端，避免 token 缓存过期问题"""
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )
    return GoogleAdsClient(
        credentials=credentials,
        developer_token=developer_token,
        login_customer_id=login_customer_id,
        use_proto_plus=True  # 必须启用 proto_plus 获取 enum 访问
    )

# ❌ 避免：单例缓存导致 token 过期
# _clients = {}  # 全局缓存会有问题
```

### 1.2 核心服务一览

| 服务 | 用途 | 关键方法 |
|------|------|----------|
| `GoogleAdsService` | GAQL 查询 | `search()`, `search_stream()` |
| `CampaignService` | Campaign CRUD | `mutate_campaigns()`, `get_campaign()` |
| `CampaignBudgetService` | 预算管理 | `mutate_campaign_budgets()` |
| `AdGroupService` | 广告组管理 | `mutate_ad_groups()` |
| `AdGroupCriterionService` | 关键词管理 | `mutate_ad_group_criteria()` |
| `AdService` | 创意管理 | `mutate_ads()` |
| `CustomerClientService` | MCC 子账户 | `mutate_customer_clients()` |

### 1.3 生产环境错误处理

```python
from google.ads.googleads.errors import GoogleAdsException
import time

def safe_mutate_with_retry(client, service_method, customer_id, operations, max_retries=3):
    """带限流重试的批量操作"""
    for attempt in range(max_retries):
        try:
            response = service_method(
                customer_id=customer_id,
                operations=operations
            )
            return response
        except GoogleAdsException as e:
            error_code = e.error.code().code
            
            if error_code == 8:  # RESOURCE_EXHAUSTED (限流)
                wait_time = min(2 ** attempt, 60)
                print(f"⚠️ 限流，等待 {wait_time}s...")
                time.sleep(wait_time)
            elif error_code == 12:  # PERMISSION_DENIED
                print(f"❌ 权限不足: {e.error.message}")
                raise
            else:
                # 其他错误直接抛出
                raise
    
    raise Exception(f"重试 {max_retries} 次后仍失败")


def safe_search_stream(client, gaia, customer_id, query, batch_size=1000):
    """安全的流式查询，自动处理分页"""
    results = []
    try:
        response = gaia.search_stream(customer_id=customer_id, query=query)
        for batch in response:
            for row in batch.results:
                results.append(row)
                if len(results) % batch_size == 0:
                    print(f"  已获取 {len(results)} 条记录...")
            # batch 内部迭代完毕
    except GoogleAdsException as e:
        print(f"❌ 查询错误: {e.error.message}")
        raise
    return results
```

---

## 二、GAQL 查询语言专家指南

### 2.1 GAQL 核心语法

```
FROM <resource_type>
WHERE <condition>
SELECT <fields>
[DURING <date_range>]
[ORDER BY <field> [ASC|DESC]]
[LIMIT <count>]
[PAGE_SIZE <size>]
```

### 2.2 高级查询模式

#### 多资源 JOIN 查询

```python
# ❌ 错误：不支持 JOIN 语法
query = """
    SELECT ad.id, ad_group.name 
    FROM ad JOIN ad_group ON ad.ad_group = ad_group.id
"""

# ✅ 正确：通过 ad_group_ad 表关联
query = """
    SELECT 
        ad_group_ad.ad.id,
        ad_group_ad.ad.name,
        ad_group_ad.ad.status,
        ad_group.name AS ad_group_name
    FROM ad_group_ad
    WHERE ad_group_ad.ad_group = "customers/{cid}/adGroups/{ag_id}"
"""
```

#### 嵌套字段访问

```python
# ✅ 正确访问嵌套字段
query = """
    SELECT 
        campaign.id,
        campaign.name,
        campaign.status,
        campaign.bidding_strategy.type,
        campaign.campaign_budget.amount_micros,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.roas
    FROM campaign
    WHERE campaign.status = PAUSED
    DURING LAST_30_DAYS
    ORDER BY metrics.cost_micros DESC
    LIMIT 100
"""
```

#### IN 查询 (多值匹配)

```python
# 查询多个 Campaign
campaign_ids = [123456, 789012, 345678]
id_list = ", ".join(str(i) for i in campaign_ids)
query = f"""
    SELECT campaign.id, campaign.name, metrics.roas
    FROM campaign
    WHERE campaign.id IN ({id_list})
    DURING LAST_7_DAYS
"""
```

### 2.3 报表查询最佳实践

```python
def get_campaign_report(client, customer_id, date_range_days=30):
    """获取 Campaign 性能报表"""
    gaia = client.get_service('GoogleAdsService')
    
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.bidding_strategy.type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.all_conversions,
            metrics.ctr,
            metrics.average_cpc,
            metrics.roas
        FROM campaign
        DURING LAST_{date_range_days}_DAYS
        ORDER BY metrics.all_conversions DESC
        LIMIT 500
    """
    
    results = []
    for batch in gaia.search_stream(customer_id=customer_id, query=query):
        for row in batch.results:
            results.append({
                'campaign_id': row.campaign.id,
                'name': row.campaign.name,
                'status': row.campaign.status.name,
                'channel': row.campaign.advertising_channel_type.name,
                'impressions': row.metrics.impressions,
                'clicks': row.metrics.clicks,
                'cost': row.metrics.cost_micros / 1_000_000,
                'conversions': row.metrics.all_conversions,
                'ctr': row.metrics.ctr,
                'cpc': row.metrics.average_cpc / 1_000_000,
                'roas': row.metrics.roas
            })
    return results


def get_search_term_report(client, customer_id, campaign_id=None, days=30):
    """获取搜索词报告 - 用于否定关键词发现"""
    gaia = client.get_service('GoogleAdsService')
    
    where_clause = f"campaign.id = {campaign_id}" if campaign_id else "1=1"
    
    query = f"""
        SELECT
            search_term_view.search_term,
            search_term_view.match_type,
            ad_group.name AS ad_group_name,
            campaign.name AS campaign_name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.all_conversions,
            metrics.conversion_rate
        FROM search_term_view
        WHERE {where_clause}
        DURING LAST_{days}_DAYS
        ORDER BY metrics.cost_micros DESC
        LIMIT 1000
    """
    
    results = []
    for batch in gaia.search_stream(customer_id=customer_id, query=query):
        for row in batch.results:
            results.append({
                'search_term': row.search_term_view.search_term,
                'match_type': row.search_term_view.match_type.name,
                'ad_group': row.ad_group.name,
                'campaign': row.campaign.name,
                'impressions': row.metrics.impressions,
                'clicks': row.metrics.clicks,
                'cost': row.metrics.cost_micros / 1_000_000,
                'conversions': row.metrics.all_conversions,
                'ctr': row.metrics.ctr
            })
    return results
```

---

## 三、Campaign 创建与管理专家级实践

### 3.1 完整的 Campaign 创建流程

```python
def create_complete_search_campaign(
    client, 
    customer_id: str,
    campaign_name: str,
    daily_budget: float,
    target_cpa: float = None,
    target_roas: int = None,
    bidding_strategy_type: str = "TARGET_CPA"  # MANUAL_CPC, TARGET_CPA, MAXIMIZE_CONVERSIONS
) -> dict:
    """
    完整创建 Search Campaign，包含 Budget + Bidding Strategy + Campaign
    """
    # Step 1: 创建 Campaign Budget (独立 budget，不共享)
    budget_op = client.get_type("CampaignBudgetOperation")
    budget = budget_op.create
    budget.name = f"{campaign_name}_Budget"
    budget.amount_micros = int(daily_budget * 1_000_000)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    # 关键：shared=false 表示这是独立 budget
    budget.explicitly_shared = False
    
    budget_result = client.get_service('CampaignBudgetService').mutate_campaign_budgets(
        customer_id=customer_id,
        operations=[budget_op]
    )
    budget_resource = budget_result.results[0].resource_name
    budget_id = budget_resource.split('/')[-1]
    print(f"✅ Budget created: {budget_resource}")
    
    # Step 2: 创建 Bidding Strategy
    bs_op = client.get_type("BiddingStrategyOperation")
    bs = bs_op.create
    bs.name = f"{campaign_name}_Bidding"
    bs.type = getattr(client.enums.BiddingStrategyType, bidding_strategy_type)
    
    if bidding_strategy_type == "TARGET_CPA" and target_cpa:
        # 设置目标 CPA
        tpub_setting = client.get_type("TargetCpaSetting")
        tpub_setting.target_cpa_micros = int(target_cpa * 1_000_000)
        bs.target_cpa = tpub_setting
    elif bidding_strategy_type == "TARGET_ROAS" and target_roas:
        # 设置目标 ROAS (百分比转 micros)
        trvas_setting = client.get_type("TargetRoasSetting")
        trvas_setting.target_roas = target_roas
        bs.target_roas = trvas_setting
    elif bidding_strategy_type == "MAXIMIZE_CONVERSIONS":
        # Maximization 不需要额外设置
        pass
    
    bs_result = client.get_service('BiddingStrategyService').mutate_bidding_strategies(
        customer_id=customer_id,
        operations=[bs_op]
    )
    bs_resource = bs_result.results[0].resource_name
    print(f"✅ Bidding Strategy created: {bs_resource}")
    
    # Step 3: 创建 Campaign
    campaign_op = client.get_type("CampaignOperation")
    campaign = campaign_op.create
    campaign.name = campaign_name
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
    campaign.campaign_budget = budget_resource
    campaign.bidding_strategy = bs_resource
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )
    
    # 可选：设置 Geo Targeting
    # campaign.geo_target_constant = f"geoTargets/{country_code}"
    
    # 可选：设置 Network Targets
    # campaign.network_settings.target_google_search = True
    # campaign.network_settings.target_search_partners = False
    # campaign.network_settings.target_network = True
    # campaign.network_settings.target_content_network = False
    
    cs = client.get_service('CampaignService')
    result = cs.mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_op]
    )
    campaign_resource = result.results[0].resource_name
    campaign_id = campaign_resource.split('/')[-1]
    
    print(f"✅ Campaign created: {campaign_resource}")
    return {
        'campaign_id': campaign_id,
        'campaign_resource': campaign_resource,
        'budget_id': budget_id,
        'bidding_strategy': bs_resource,
        'status': 'PAUSED'
    }
```

### 3.2 PMax Campaign 创建 (完整示例)

```python
def create_pmax_campaign(
    client,
    customer_id: str,
    campaign_name: str,
    daily_budget: float,
    target_roas: int = 300,
    audience_signals: list = None
) -> dict:
    """
    创建 Performance Max Campaign
    audience_signals: 列表，每项包含 audience identifier
    """
    # Step 1: Budget
    budget_op = client.get_type("CampaignBudgetOperation")
    budget = budget_op.create
    budget.name = f"{campaign_name}_Budget"
    budget.amount_micros = int(daily_budget * 1_000_000)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget.explicitly_shared = False
    
    budget_result = client.get_service('CampaignBudgetService').mutate_campaign_budgets(
        customer_id=customer_id,
        operations=[budget_op]
    )
    budget_resource = budget_result.results[0].resource_name
    
    # Step 2: Bidding Strategy (Maximize Conversion Value with Target ROAS)
    bs_op = client.get_type("BiddingStrategyOperation")
    bs = bs_op.create
    bs.name = f"{campaign_name}_Bidding"
    bs.type = client.enums.BiddingStrategyType.MAXIMIZE_CONVERSION_VALUE
    
    if target_roas:
        trvas_setting = client.get_type('TargetRoasSetting')
        trvas_setting.target_roas = target_roas
        bs.target_roas = trvas_setting
    
    bs_result = client.get_service('BiddingStrategyService').mutate_bidding_strategies(
        customer_id=customer_id,
        operations=[bs_op]
    )
    bs_resource = bs_result.results[0].resource_name
    
    # Step 3: Campaign
    campaign_op = client.get_type("CampaignOperation")
    campaign = campaign_op.create
    campaign.name = campaign_name
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
    campaign.campaign_budget = budget_resource
    campaign.bidding_strategy = bs_resource
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )
    
    # Step 4: PMax 特有设置
    # 设置 Final URL Suffix (UTM 参数)
    campaign.final_url_suffix = "utm_source=google&utm_medium=pmax&utm_campaign={campaignid}"
    
    result = client.get_service('CampaignService').mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_op]
    )
    campaign_resource = result.results[0].resource_name
    
    return {
        'campaign_id': campaign_resource.split('/')[-1],
        'campaign_resource': campaign_resource,
        'budget_resource': budget_resource,
        'bidding_strategy': bs_resource
    }
```

---

## 四、Ad Group 与关键词管理

### 4.1 批量创建 Ad Group

```python
def batch_create_ad_groups(client, customer_id: str, campaign_id: str, ad_groups: list) -> list:
    """
    批量创建 Ad Group
    ad_groups: [{'name': '...', 'cpc_bid': 100000}, ...] 单位: micros
    """
    service = client.get_service('AdGroupService')
    operations = []
    
    for i, ag_data in enumerate(ad_groups):
        op = client.get_type("AdGroupOperation")
        ag = op.create
        ag.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
        ag.name = f"{ag_data.get('name', 'AdGroup_{i}')}"
        ag.status = client.enums.AdGroupStatusEnum.PAUSED
        ag.type = client.enums.AdGroupTypeEnum.SEARCH_DYNAMIC_ADS
        
        if ag_data.get('cpc_bid'):
            ag.manual_cpc.bid_micros = ag_data['cpc_bid']
        
        operations.append(op)
    
    # 分批执行 (每批最多 10 个)
    batch_size = 10
    results = []
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i+batch_size]
        response = service.mutate_ad_groups(
            customer_id=customer_id,
            operations=batch
        )
        for r in response.results:
            results.append({
                'ad_group_id': r.resource_name.split('/')[-1],
                'resource_name': r.resource_name
            })
    
    return results
```

### 4.2 关键词管理最佳实践

```python
def create_keywords_batch(client, customer_id: str, ad_group_id: str, keywords: list, match_type: str = 'PHRASE') -> list:
    """
    批量创建关键词
    keywords: ['keyword1', 'keyword2', ...]
    match_type: PHRASE, EXACT, BROAD
    """
    service = client.get_service('AdGroupCriterionService')
    operations = []
    
    match_enum = getattr(client.enums.KeywordMatchType, match_type.upper())
    
    for kw in keywords:
        op = client.get_type("AdGroupCriterionOperation")
        keyword = op.create
        keyword.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
        keyword.keyword.text = kw
        keyword.keyword.match_type = match_enum
        # 可选：设置 Bid
        # keyword.cpc_bid_micros = 500000  # $5.00
        
        operations.append(op)
    
    # 分批执行 (每批最多 100 个)
    batch_size = 100
    results = []
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i+batch_size]
        response = service.mutate_ad_group_criteria(
            customer_id=customer_id,
            operations=batch
        )
        for r in response.results:
            results.append(r.resource_name)
    
    return results


def add_negative_keywords(client, customer_id: str, ad_group_id: str, negative_keywords: list) -> list:
    """添加否定关键词"""
    service = client.get_service('AdGroupCriterionService')
    operations = []
    
    for kw in negative_keywords:
        op = client.get_type("AdGroupCriterionOperation")
        neg_kw = op.create
        neg_kw.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
        neg_kw.keyword.text = kw
        neg_kw.keyword.match_type = client.enums.KeywordMatchType.PHRASE
        neg_kw.negative_keyword.is_negative = True
        
        operations.append(op)
    
    response = service.mutate_ad_group_criteria(
        customer_id=customer_id,
        operations=operations
    )
    return [r.resource_name for r in response.results]
```

---

## 五、Ad 创意管理

### 5.1 Responsive Search Ad 创建

```python
def create_rsa(client, customer_id: str, ad_group_id: str, 
               headlines: list, descriptions: list, 
               path1: str = None, path2: str = None) -> dict:
    """
    创建 Responsive Search Ad
    headlines: 最多 15 条，每条 30 字符
    descriptions: 最多 4 条，每条 90 字符
    """
    service = client.get_service('AdService')
    op = client.get_type("AdOperation")
    ad = op.create
    ad.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
    ad.type = client.enums.AdTypeEnum.RESPONSIVE_SEARCH_AD
    
    # Headlines (至少 3 条，最多 15 条)
    for i, headline in enumerate(headlines[:15]):
        h = ad.responsive_search_ad.info
        h.headline_part.text = headline[:30]  # 最多 30 字符
        h.headline_part.priority = 0  # 0 = optional, 1 = mandatory
    
    # Descriptions (最多 4 条)
    for desc in descriptions[:4]:
        d = ad.responsive_search_ad.info.add()
        d.description.text = desc[:90]  # 最多 90 字符
    
    # Path fields (可选)
    if path1:
        ad.responsive_search_ad.info.path1 = path1[:30]
    if path2:
        ad.responsive_search_ad.info.path2 = path2[:30]
    
    result = service.mutate_ads(customer_id=customer_id, operations=[op])
    return {
        'ad_id': result.results[0].resource_name.split('/')[-1],
        'resource_name': result.results[0].resource_name
    }
```

### 5.2 扩展信息 (Asset) 管理

```python
def add_feed_items_to_campaign(client, customer_id: str, campaign_id: str, feed_items: list):
    """为 PMax Campaign 添加素材"""
    # 注意：PMax Asset 通过 AssetGroup 管理，不是直接关联 Campaign
    # 这里展示如何创建和关联 Asset
    
    asset_service = client.get_service('AssetService')
    
    for item in feed_items:
        op = client.get_type("AssetOperation")
        asset = op.create
        asset.name = item['name']
        
        if item['type'] == 'IMAGE':
            asset.type = client.enums.AssetType.IMAGE
            # 上传图像数据...
        elif item['type'] == 'VIDEO':
            asset.type = client.enums.AssetType.VIDEO
            asset.youtube_video_id = item.get('youtube_id', '')
        elif item['type'] == 'BUSINESS_NAME':
            asset.type = client.enums.AssetType.BUSINESS_NAME
            asset.business_name.name = item.get('business_name', '')
        elif item['type'] == 'CALL_TO_ACTION':
            asset.type = client.enums.AssetType.CALL_TO_ACTION
            cta = asset.call_to_action_asset
            cta.text = item['text'][:30]
            cta.style = getattr(client.enums.CallToActionType, item.get('style', 'LEARN_MORE'))
        
        result = asset_service.mutate_assets(customer_id=customer_id, operations=[op])
        print(f"✅ Created asset: {result.results[0].resource_name}")
```

---

## 六、报表与数据分析

### 6.1 多维度报表查询

```python
def get_performance_report(client, customer_id: str, date_from: str, date_to: str):
    """
    获取多维度性能报表
    date_from/to: 'YYYYMMDD' 格式
    """
    gaia = client.get_service('GoogleAdsService')
    
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            ad_group.id,
            ad_group.name,
            ad_group_ad.ad.id AS ad_id,
            ad_group_ad.ad.name AS ad_name,
            ad_group_ad.status AS ad_status,
            
            -- 基础指标
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.all_conversions,
            metrics.ctr,
            metrics.average_cpc,
            
            -- 转化价值
            metrics.all_conversions_value,
            metrics.roas,
            metrics.cost_per_all_conversions,
            
            -- 搜索特定指标
            search_term_view.search_term,
            search_term_view.match_type,
            
            -- 地理分布
            geo_target_constant.campaign_geo_target_constant_match_type,
            
            -- 设备
            device.name AS device_type,
            
            -- 时间段
            segments.date
        FROM campaign
        LEFT JOIN ad_group ON ad_group.campaign = campaign.resource_name
        LEFT JOIN ad_group_ad ON ad_group_ad.ad_group = ad_group.resource_name
        LEFT JOIN search_term_view ON search_term_view.ad_group_criterion = ad_group_ad.resource_name
        WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY metrics.cost_micros DESC
        LIMIT 5000
    """
    
    results = []
    for batch in gaia.search_stream(customer_id=customer_id, query=query):
        for row in batch.results:
            results.append({
                'campaign_id': row.campaign.id,
                'campaign_name': row.campaign.name,
                'ad_group_id': row.ad_group.id if row.ad_group else None,
                'ad_id': row.ad_group_ad.ad.id if row.ad_group_ad and row.ad_group_ad.ad else None,
                'search_term': row.search_term_view.search_term if row.search_term_view else None,
                'impressions': row.metrics.impressions,
                'clicks': row.metrics.clicks,
                'cost': row.metrics.cost_micros / 1_000_000,
                'conversions': row.metrics.all_conversions,
                'ctr': row.metrics.ctr,
                'cpc': row.metrics.average_cpc / 1_000_000,
                'roas': row.metrics.roas,
                'conversion_value': row.metrics.all_conversions_value,
                'cpa': row.metrics.cost_per_all_conversions / 1_000_000 if row.metrics.cost_per_all_conversions else None,
                'device': row.device.name if row.device else None,
                'date': row.segments.date
            })
    return results
```

### 6.2 竞品分析查询

```python
def get_auction_insights(client, customer_id: str, campaign_id: str):
    """获取竞对份额报告"""
    gaia = client.get_service('GoogleAdsService')
    
    query = f"""
        SELECT
            auction_insight_view.search_query,
            auction_insight_view.position_in_auction,
            auction_insight_view.impression_share,
            auction_insight_view.top_of_page_rate,
            auction_insight_view.absolute_top_of_page_rate,
            auction_insight_view.overlap_rate,
            auction_insight_view.outranking_share,
            auction_insight_view.click_loss_rate,
            auction_insight_view.impression_loss_rate
        FROM auction_insight_view
        WHERE campaign.id = {campaign_id}
        DURING LAST_30_DAYS
        ORDER BY auction_insight_view.impression_share DESC
        LIMIT 100
    """
    
    results = []
    for batch in gaia.search_stream(customer_id=customer_id, query=query):
        for row in batch.results:
            results.append({
                'query': row.auction_insight_view.search_query,
                'position': row.auction_insight_view.position_in_auction,
                'impression_share': row.auction_insight_view.impression_share,
                'overlap_rate': row.auction_insight_view.overlap_rate,
                'outranking_share': row.auction_insight_view.outranking_share,
                'click_loss_rate': row.auction_insight_view.click_loss_rate
            })
    return results
```

---

## 七、限流与配额管理

### 7.1 Google Ads API 配额限制

| 限制类型 | 限制值 | 说明 |
|----------|--------|------|
| 每客户每秒 | 100 请求 | 单客户并发限制 |
| 每客户每分钟 | 5000 请求 | 短期突发限制 |
| 每开发者令牌每秒 | 500 请求 | 全局限制 |
| Mutate 批量大小 | 1000 操作/请求 | 单次 mutate 上限 |
| Search 结果 | 10,000 行 | 单次搜索上限 |

### 7.2 智能限流实现

```python
import time
import random
from collections import defaultdict

class RateLimiter:
    """Google Ads API 智能限流器"""
    
    def __init__(self, requests_per_second=10, burst_size=50):
        self.max_rps = requests_per_second
        self.burst_size = burst_size
        self.requests = defaultdict(list)  # per customer_id 记录时间戳
        self.last_request = {}
    
    def wait(self, customer_id: str):
        """等待合适的请求间隔"""
        now = time.time()
        timestamps = self.requests[customer_id]
        
        # 清理过期记录 (超过 1 秒)
        self.requests[customer_id] = [t for t in timestamps if now - t < 1.0]
        timestamps = self.requests[customer_id]
        
        # 计算等待时间
        if len(timestamps) >= self.max_rps:
            wait_time = 1.0 - (now - timestamps[0])
            if wait_time > 0:
                time.sleep(wait_time)
        
        # 记录本次请求
        self.requests[customer_id].append(time.time())
    
    def execute_with_retry(self, func, customer_id, *args, max_retries=3):
        """带重试的执行方法"""
        for attempt in range(max_retries):
            try:
                self.wait(customer_id)
                result = func(*args)
                return result
            except GoogleAdsException as e:
                if e.error.code().code == 8:  # RESOURCE_EXHAUSTED
                    wait = min(2 ** attempt + random.uniform(0, 1), 30)
                    print(f"⚠️ 限流，等待 {wait:.1f}s (attempt {attempt+1})")
                    time.sleep(wait)
                else:
                    raise
        raise Exception(f"重试 {max_retries} 次后失败")


# 使用示例
rate_limiter = RateLimiter(requests_per_second=10)

def safe_search(client, customer_id, query):
    gaia = client.get_service('GoogleAdsService')
    return rate_limiter.execute_with_retry(
        gaia.search_stream,
        customer_id,
        customer_id=customer_id,
        query=query
    )
```

---

## 八、生产环境最佳实践清单

### 8.1 代码质量

- [ ] 使用 `use_proto_plus=True` 获取 Enum 访问
- [ ] 每次请求创建 fresh client，避免 token 过期
- [ ] 所有 mutate 操作包裹在 try-except 中
- [ ] 实现指数退避重试机制
- [ ] 限制单次批量操作 ≤1000 条
- [ ] 使用 `search_stream` 而非 `search` 处理大数据集

### 8.2 性能优化

- [ ] 选择最小必要字段，避免过度查询
- [ ] 使用 `LIMIT` 和 `PAGE_SIZE` 控制结果集
- [ ] 批量操作合并为单次请求
- [ ] 异步并发查询不同资源
- [ ] 缓存只读数据 (Campaign 列表等)

### 8.3 错误处理

```python
ERROR_HANDLING_MAP = {
    8:    ("RESOURCE_EXHAUSTED", "限流，等待重试"),
    9:    ("INTERNAL_ERROR", "内部错误，稍后重试"),
    10:   ("UNAUTHENTICATED", "认证失败，检查 Token"),
    12:   ("PERMISSION_DENIED", "权限不足，检查账号"),
    13:   ("FAILED_PRECONDITION", "前置条件不满足"),
    14:   ("INVALID_ARGUMENT", "参数错误，检查请求"),
    16:   ("UNIMPLEMENTED", "方法未实现"),
    23:   ("SERVING_DISABLED", "账户服务已禁用"),
}
```

---

## 九、Batch Job 批量处理（官方示例）

### 9.1 为什么使用 Batch Job

对于大规模操作（如批量创建成百上千个 Campaign），推荐使用 **BatchJobService**：
- 异步执行，不阻塞主线程
- 支持大量操作（单次最多 10,000 条）
- 失败不影响其他操作
- 可查询执行结果和错误详情

### 9.2 Batch Job 完整流程

```python
import asyncio
from uuid import uuid4
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# ==================== 临时 ID 管理 ====================
_temporary_id = -1

def get_next_temporary_id():
    """返回下一个临时 ID，用于 Batch Job 引用"""
    global _temporary_id
    _temporary_id -= 1
    return _temporary_id


# ==================== Step 1: 创建 Batch Job ====================
def create_batch_job(client, customer_id: str) -> str:
    """创建 Batch Job 并返回 Resource Name"""
    batch_job_service = client.get_service('BatchJobService')
    
    batch_job_op = client.get_type('BatchJobOperation')
    batch_job = batch_job_op.create
    # 不需要设置任何属性，只需创建空对象
    
    response = batch_job_service.mutate_batch_job(
        customer_id=customer_id,
        operation=batch_job_op
    )
    resource_name = response.result.resource_name
    print(f"✅ Batch Job created: {resource_name}")
    return resource_name


# ==================== Step 2: 构建操作列表 ====================
def build_campaign_operations(client, customer_id: str, campaigns_config: list):
    """构建完整的 Campaign 操作列表"""
    operations = []
    
    for config in campaigns_config:
        # 2.1 Campaign Budget Operation
        budget_op = client.get_type('CampaignBudgetOperation')
        budget = budget_op.create
        budget.name = f"{config['name']}_Budget"
        budget.amount_micros = int(config['budget'] * 1_000_000)
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget.explicitly_shared = False
        
        operations.append(budget_op)
        
        # 2.2 Campaign Operation
        campaign_op = client.get_type('CampaignOperation')
        campaign = campaign_op.create
        campaign.name = config['name']
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
        campaign.contains_eu_political_advertising = (
            client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
        )
        
        operations.append(campaign_op)
        
        # 2.3 Ad Group Operations
        for i in range(config.get('ad_groups', 2)):
            ad_group_op = client.get_type('AdGroupOperation')
            ad_group = ad_group_op.create
            ad_group.name = f"{config['name']}_AG_{i}"
            ad_group.status = client.enums.AdGroupStatusEnum.PAUSED
            ad_group.type = client.enums.AdGroupTypeEnum.SEARCH_DYNAMIC_ADS
            
            if config.get('cpc_bid'):
                ad_group.manual_cpc.bid_micros = int(config['cpc_bid'] * 1_000_000)
            
            operations.append(ad_group_op)
        
        # 2.4 Keyword Operations
        keywords = config.get('keywords', ['shoes', 'sneakers'])
        for kw in keywords:
            kw_op = client.get_type('AdGroupCriterionOperation')
            keyword = kw_op.create
            keyword.keyword.text = kw
            keyword.keyword.match_type = client.enums.KeywordMatchType.PHRASE
            operations.append(kw_op)
    
    return operations


# ==================== Step 3: 添加操作到 Batch Job ====================
def add_batch_job_operations(batch_job_service, operations, resource_name: str):
    """将操作添加到 Batch Job"""
    for i, op in enumerate(operations):
        batch_job_op = client.get_type('BatchJobOperation')
        batch_job_op.add_mutate_operation.operation_index = i
        batch_job_op.add_mutate_operations.mutate_operation = op
        
        batch_job_service.add_batch_job_operations(
            resource_name=resource_name,
            operation=batch_job_op
        )
    print(f"✅ Added {len(operations)} operations to Batch Job")


# ==================== Step 4: 运行 Batch Job ====================
def run_batch_job(batch_job_service, resource_name: str):
    """运行 Batch Job（异步）"""
    operation = batch_job_service.run_batch_job(resource_name=resource_name)
    print(f"🚀 Batch Job executed: {resource_name}")
    return operation


# ==================== Step 5: 轮询并获取结果 ====================
def fetch_and_print_results(batch_job_service, resource_name: str, page_size: int = 1000):
    """获取 Batch Job 执行结果"""
    request = client.get_type('ListBatchJobResultsRequest')
    request.resource_name = resource_name
    request.page_size = page_size
    
    results = batch_job_service.list_batch_job_results(request=request)
    
    for result in results:
        status = result.status.message or "N/A"
        op_index = result.operation_index
        print(f"  Operation #{op_index}: status={status}")


# ==================== 完整异步流程 ====================
async def main(client: GoogleAdsClient, customer_id: str, campaigns_config: list):
    """完整的 Batch Job 执行流程"""
    batch_job_service = client.get_service('BatchJobService')
    
    # Step 1: 创建 Batch Job
    resource_name = create_batch_job(client, customer_id)
    
    # Step 2: 构建操作
    operations = build_campaign_operations(client, customer_id, campaigns_config)
    
    # Step 3: 添加操作
    add_batch_job_operations(batch_job_service, operations, resource_name)
    
    # Step 4: 运行
    operation = run_batch_job(batch_job_service, resource_name)
    
    # Step 5: 轮询并等待完成
    print("⏳ Waiting for batch job to complete...")
    operation.result()  # 阻塞直到完成
    
    # Step 6: 获取结果
    fetch_and_print_results(batch_job_service, resource_name)


# 使用示例
if __name__ == "__main__":
    client = GoogleAdsClient.load_from_storage('google-ads.yaml')
    
    campaigns = [
        {'name': 'Campaign_001', 'budget': 100, 'cpc_bid': 2.0, 
         'keywords': ['running shoes', 'sports shoes']},
        {'name': 'Campaign_002', 'budget': 150, 'cpc_bid': 2.5,
         'keywords': ['formal shoes', 'leather shoes']}
    ]
    
    asyncio.run(main(client, 'YOUR_CUSTOMER_ID', campaigns))
```

### 9.3 Batch Job vs 直接 Mutate 对比

| 特性 | 直接 Mutate | Batch Job |
|------|-------------|-----------|
| 单次操作数 | ≤1000 | ≤10,000 |
| 执行方式 | 同步 | 异步 |
| 错误隔离 | 失败即停止 | 失败不影响其他 |
| 结果查询 | 即时返回 | 需轮询 |
| 适用场景 | 少量操作 | 批量操作 |

---

## 十、Field Mask 更新技巧

### 10.1 部分字段更新

```python
def update_campaign_field_mask(client, campaign_id: str, updates: dict):
    """
    使用 Field Mask 只更新指定字段
    避免覆盖其他字段
    """
    campaign_op = client.get_type('CampaignOperation')
    campaign = campaign_op.update
    campaign.resource_name = f"customers/{customer_id}/campaigns/{campaign_id}"
    
    # 设置要更新的字段
    for key, value in updates.items():
        if hasattr(campaign, key):
            setattr(campaign, key, value)
    
    # 关键：设置 update_mask 指定要更新的字段
    campaign_op.update_mask = ','.join(updates.keys())
    
    response = client.get_service('CampaignService').mutate_campaigns(
        customer_id=customer_id,
        operations=[campaign_op]
    )
    return response


# 使用示例：只更新预算，不影响其他字段
update_campaign_field_mask(
    client, 
    campaign_id='123456',
    updates={
        'campaign_budget': 'customers/123/campaignBudgets/789',
        'status': client.enums.CampaignStatusEnum.ENABLED
    }
)
```

---

## 参考资源

- [Google Ads API 官方文档](https://developers.google.com/google-ads/api/docs/start)
- [Google Ads Python SDK 示例](https://github.com/googleads/google-ads-python)
- [GAQL Query Cookbook](https://developers.google.com/google-ads/api/docs/query/cookbook)
- [API 配额与限流指南](https://developers.google.com/google-ads/api/docs/rate-limits)
- [v25 版本变更说明](https://ads-developers.googleblog.com/2026/07/announcing-v25-of-google-ads-api.html)
- [Batch Job 官方示例](https://developers.google.com/google-ads/api/samples/add-complete-campaigns-using-batch-job)

---

## 总结

Google Ads API 成功的三个支柱：

1. **正确的认证与限流** - 新鲜 client + 指数退避
2. **高效的 GAQL 查询** - 最小字段 + 分页 + 流式
3. **可靠的批量处理** - Batch Job + Field Mask

记住：**API 是工具，理解广告架构才是核心**。
