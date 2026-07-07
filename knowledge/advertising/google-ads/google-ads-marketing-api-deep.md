# Google Ads API 官方文档精读与实战

## 一、Google Ads API 官方架构

### 1.1 官方定义与定位

**Google 官方定义：**
> Google Ads API 是 Google Ads 的程序化接口，用于管理大型或复杂的 Google Ads 账号和广告系列。您可以构建软件，全方位管理从客户一级到关键字一级的账号。

**典型用例：**
- 自动账号管理
- 自定义报告
- 基于产品目录的广告管理
- 智能出价策略管理

**API 版本：** 当前最新版本 v24.2（2026 年 6 月）

### 1.2 账户层级结构

**官方层级：**

```
Customer (客户账户)
├── Campaigns (广告系列)
│   ├── AdGroups (广告组)
│   │   ├── Keywords (关键词)
│   │   ├── Ads (广告)
│   │   ├── Assets (资产/附加信息)
│   │   └── BiddableAdGroupCriterion (可竞价广告组限定词)
│   ├── Budget (预算)
│   ├── BiddingStrategy (出价策略)
│   └── TargetingSetting (定向设置)
├── SharedSets (共享设置)
│   ├── NegativeKeywordSets (否定关键词集)
│   └── AudienceViews (受众视图)
└── Labels (标签)
```

**关键对象：**

| 对象 | 说明 | 必填字段 |
|------|------|----------|
| Customer | 客户账户 | customer_id |
| Campaign | 广告系列 | name, status, advertising_channel_type |
| AdGroup | 广告组 | name, campaign, status |
| Keyword | 关键词 | ad_group, text, match_type |
| Ad | 广告 | ad_group, final_urls |
| Asset | 资产/附加信息 | name, type |

### 1.3 广告系列类型

**官方广告系列类型：**

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| SEARCH | 搜索广告 | 搜索意图捕获 |
| DISPLAY | 展示广告 | 品牌曝光、再营销 |
| SHOPPING | 购物广告 | 电商产品推广 |
| VIDEO | 视频广告 | YouTube 广告 |
| APP | 应用广告 | 应用安装、应用内事件 |
| MAX | 全效果广告 | 跨渠道自动化投放 |

**广告系列网络选择：**

| 网络 | 说明 | 适用场景 |
|------|------|----------|
| SEARCH_NETWORK | Google 搜索 | 搜索广告 |
| SEARCH_NETWORK_WITH_GOOGLE_PARTNERS | Google 搜索伙伴 | 搜索广告扩展 |
| DISPLAY_NETWORK | Google 展示网络 | 展示广告 |
| PARTNER_SEARCH_NETWORK | 合作伙伴搜索网络 | 搜索广告扩展 |

### 1.4 出价策略

**官方出价策略类型：**

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| MANUAL_CPC | 手动 CPC | 手动控制每次点击费用 |
| ENHANCED_CPC | 增强型 CPC | 在手动 CPC 基础上优化 |
| TARGET_CPA | 目标每次转化费用 | 转化优化 |
| TARGET_ROAS | 目标广告支出回报率 | 收入优化 |
| MAXIMIZE_CLICKS | 最大化点击量 | 流量获取 |
| MAXIMIZE_CONVERSIONS | 最大化转化量 | 转化优化 |
| MAXIMIZE_CONVERSION_VALUE | 最大化转化价值 | 收入优化 |
| TARGET_IMPRESSION_SHARE | 目标展示份额 | 品牌曝光 |
| TARGET_OUTRANK_SHARE | 目标超越份额 | 竞争定位 |

### 1.5 资产 (Assets)

**官方资产类型：**

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| SITELINK | 站点链接 | 引导到多个页面 |
| CALL | 电话展示 | 电话转化 |
| STRUCTURED_SNIPPET | 结构化摘要 | 展示产品特性 |
| CALLOUT | 促销信息 | 突出卖点 |
| PRICE | 价格 | 电商产品 |
| APP_EXTENSION | 应用链接 | 应用推广 |
| IMAGE | 图片 | 视觉展示 |
| PRODUCT_SALE | 产品销售 | 促销活动 |
| LEAD_FORM | 表单 | 潜在客户收集 |

## 二、核心 API 端点实战

### 2.1 认证与授权

**OAuth2 流程：**

```
1. 创建 Google Cloud 项目
2. 启用 Google Ads API
3. 创建 OAuth2 凭据
4. 获取 refresh_token
5. 使用 refresh_token 获取 access_token
6. 使用 access_token 调用 API
```

**认证代码示例：**

```python
from google.ads.googleads.client import GoogleAdsClient

# 从配置文件加载凭据
client = GoogleAdsClient.load_from_storage('google-ads.yaml')

# 获取服务
customer_service = client.get_service('CustomerService')
campaign_service = client.get_service('CampaignService')
ad_group_service = client.get_service('AdGroupService')
keyword_service = client.get_service('KeywordService')
ad_service = client.get_service('AdService')
```

### 2.2 广告系列管理

**创建广告系列：**

```python
# 创建搜索广告系列
campaign = client.get_type("Campaign")
campaign.resource_name = f"customers/{customer_id}/campaigns/{campaign_id}"
campaign.name = "My Search Campaign"
campaign.advertising_channel_type = client.enums.AdvertisingChannelType.SEARCH
campaign.status = client.enums.CampaignStatus.PAUSED
campaign.manual_cpc_bid_ceiling_micros = 5000000  # $0.50
campaign.optimization_score_monitoring_duration.days = 7
campaign.network_settings.target_google_searchs = True
campaign.network_settings.target_search_network = True
campaign.network_settings.target_display_network = False

# 创建购物广告系列
shopping_campaign = client.get_type("Campaign")
shopping_campaign.resource_name = f"customers/{customer_id}/campaigns/{shopping_campaign_id}"
shopping_campaign.name = "My Shopping Campaign"
shopping_campaign.advertising_channel_type = client.enums.AdvertisingChannelType.SHOPPING
shopping_campaign.shopping_setting.product_promotion_link = f"customers/{customer_id}/productPromotions/{promotion_id}"
shopping_campaign.status = client.enums.CampaignStatus.PAUSED
```

**查询广告系列：**

```python
# 使用 GAQL 查询
query = """
    SELECT 
        campaign.id,
        campaign.name,
        campaign.status,
        campaign.advertising_channel_type,
        campaign.bidding_strategy_name,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions
    FROM campaign
    WHERE campaign.status IN ['ENABLED', 'PAUSED']
    ORDER BY metrics.impressions DESC
    LIMIT 100
"""

response = client.search(customer_id, query)
for row in response:
    print(f"Campaign: {row.campaign.name}, Impressions: {row.metrics.impressions}")
```

### 2.3 广告组管理

**创建广告组：**

```python
ad_group = client.get_type("AdGroup")
ad_group.customer_id = customer_id
ad_group.campaign = campaign_resource_name
ad_group.name = "Running Shoes"
ad_group.status = client.enums.AdGroupStatus.ENABLED
ad_group.cpc_bid_micros = 200000  # $0.20
ad_group.target_cpa_micros = 1000000  # $1.00 (可选)
```

### 2.4 关键词管理

**添加关键词：**

```python
ad_group_keyword = client.get_type("AdGroupKeyword")
ad_group_keyword.ad_group = ad_group_resource_name
ad_group_keyword.keyword.text = "running shoes"
ad_group_keyword.keyword.match_type = client.enums.KeywordMatchType.PHRASE
ad_group_keyword.cpc_bid_micros = 150000  # $0.15
```

**搜索词报告：**

```python
query = """
    SELECT 
        search_term_view.search_term,
        search_term_view.match_type,
        metrics.clicks,
        metrics.impressions,
        metrics.cost_micros,
        metrics.conversions
    FROM search_term_view
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.clicks DESC
    LIMIT 1000
"""
```

### 2.5 广告创意管理

**创建响应式搜索广告 (RSA)：**

```python
responsive_search_ad = client.get_type("ResponsiveSearchAd")
responsive_search_ad.path1 = "your-path-part1"
responsive_search_ad.path2 = "your-path-part2"
responsive_search_ad.business_name = "Your Business Name"

# 添加标题
for i in range(1, 16):
    headline = responsive_search_ad.headline_parts.add()
    headline.part1 = f"Headline {i}"

# 添加描述
for i in range(1, 5):
    description = responsive_search_ad.descriptions.add()
    description.part1 = f"Description {i}"

# 设置最终 URL
responsive_search_ad.final_urls.append("https://www.example.com")
```

### 2.6 资产管理

**添加站点链接资产：**

```python
asset = client.get_type("Asset")
asset.name = "My Sitelink Asset"
asset.type_ = client.enums.AssetType.SITELINK

sitelink_asset = asset.sitelink_asset
sitelink_asset.line1 = "Shop Now"
sitelink_asset.line2 = "Best Prices"
sitelink_asset.url = "https://www.example.com/shop"
```

## 三、转化追踪

### 3.1 转化操作

**创建转化操作：**

```python
conversion_action = client.get_type("ConversionAction")
conversion_action.type_ = client.enums.ConversionActionType.PURCHASE
conversion_action.name = "Purchase Conversion"
conversion_action.category = client.enums.ConversionActionCategory.DEFAULT
conversion_action.default_currency_code = "USD"
conversion_action.value_source = client.enums.ConversionActionValueSource.DEFAULT_VALUE
conversion_action.is_mergeable = True
conversion_action.view_through_lookback_window_days = 30
conversion_action.click_lookback_window_days = 30
```

**标准转化事件：**

| 事件 | 说明 | 适用场景 |
|------|------|----------|
| PURCHASE | 购买 | 电商 |
| LEAD | 潜在客户 | B2B、教育 |
| SIGNUP | 注册 | 用户注册 |
| PAGE_VIEW | 页面浏览 | 内容营销 |
| PHONE_CALL | 电话 | 本地服务 |
| APP_INSTALL | 应用安装 | 应用推广 |
| APP_REENGAGEMENT | 应用重激活 | 应用留存 |

### 3.2 转化值设置

```python
conversion_action.value_source = client.enums.ConversionActionValueSource.MANUAL_VALUES
conversion_action.manual_value = 100.0  # 固定值 $100

# 或使用动态值
conversion_action.value_source = client.enums.ConversionActionValueSource.REVENUE
```

## 四、报告与监控

### 4.1 GAQL 查询

**GAQL (Google Ads Query Language) 语法：**

```sql
SELECT 
    campaign.name,
    campaign.status,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions,
    metrics.ctr,
    metrics.average_cpc,
    metrics.cost_per_conversion
FROM campaign
WHERE segments.date BETWEEN '2024-01-01' AND '2024-01-31'
  AND campaign.status IN ('ENABLED', 'PAUSED')
ORDER BY metrics.conversions DESC
LIMIT 100
```

**常用指标：**

| 指标 | 说明 |
|------|------|
| impressions | 展示量 |
| clicks | 点击量 |
| cost_micros | 花费 (微单位) |
| conversions | 转化量 |
| ctr | 点击率 |
| average_cpc | 平均 CPC |
| cost_per_conversion | 单次转化费用 |
| conversion_rate | 转化率 |
| roas | 广告支出回报率 |

### 4.2 报告生成

```python
# 生成性能报告
report = client.get_type("GenerateReportRequest")
report.customer_id = customer_id
report.query = """
    SELECT 
        campaign.name,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros
    FROM campaign
    WHERE segments.date DURING LAST_7_DAYS
"""

response = client.services.report_service.generate_report(report)
for row in response:
    print(row)
```

## 五、自测题

1. Google Ads API 的典型用例有哪些？
2. 广告系列的层级结构是怎样的？
3. 如何创建响应式搜索广告？
4. GAQL 查询的基本语法是什么？
5. 转化追踪的配置步骤是什么？

## 六、动手验证

```bash
# 1. 配置 OAuth2 认证
# - 创建 Google Cloud 项目
# - 启用 Google Ads API
# - 获取 refresh_token

# 2. 创建广告系列
# - 选择广告系列类型
# - 设置预算和出价
# - 配置定向

# 3. 添加关键词
# - 选择匹配类型
# - 设置出价
# - 添加否定关键词

# 4. 创建广告创意
# - 编写标题和描述
# - 设置最终 URL
# - 添加资产

# 5. 配置转化追踪
# - 创建转化操作
# - 安装跟踪代码
# - 验证数据回传

# 6. 生成报告
# - 编写 GAQL 查询
# - 分析性能数据
# - 优化投放策略
```
