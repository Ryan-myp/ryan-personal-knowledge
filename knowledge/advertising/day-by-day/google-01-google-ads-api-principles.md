# Google Ads API — 从入门到源码级

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 Google Ads 是什么？

```
Google Ads 是 Google 的广告投放平台
让用户在 Google 搜索、YouTube、Gmail、Google Display Network 上投放广告

核心产品:
├─ Search Ads (搜索广告)
├─ Display Ads (展示广告)
├─ Video Ads (视频广告 - YouTube)
├─ Shopping Ads (购物广告)
└─ Performance Max (PMax - 全渠道自动化)
```

### 1.2 为什么需要 API？

```
没有 API:
- 手动操作 Google Ads UI
- 无法批量创建/调整广告
- 无法自动优化 bid
- 无法拉取数据做分析

有 API:
- 批量管理成千上万广告组
- 自动 bid 优化（基于 ROAS/CPC 目标）
- 拉取数据做 A/B 测试
- 与内部数据打通（CRM/ERP）
```

### 1.3 API 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                  Google Ads API 架构                          │
│                                                              │
│  ┌──────────────┐                                          │
│  │  你的系统     │                                          │
│  │  (Client)    │                                          │
│  └──────┬───────┘                                          │
│         │ HTTPS gRPC/REST API                               │
│         ▼                                                   │
│  ┌────────────────────────────────────────────────────────┐│
│  │              Google Ads API Server                      ││
│  │                                                        ││
│  │  ┌────────────────────────────────────────────────────┐││
│  │  │           Authentication                           │││
│  │  │           (OAuth2 + Developer Token)               │││
│  │  └────────────┬───────────────────────────────────────┘││
│  │               │                                        ││
│  │  ┌────────────▼───────────────────────────────────────┐││
│  │  │           核心服务层                                 │││
│  │  │           CustomerService, CampaignService...      │││
│  │  └────────────────────────────────────────────────────┘││
│  │                                                        ││
│  │  ┌────────────────────────────────────────────────────┐││
│  │  │           查询层                                     │││
│  │  │           GAQL (Google Ads Query Language)         │││
│  │  └────────────────────────────────────────────────────┘││
│  └────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### 1.4 快速体验

```python
# 1. 安装 Google Ads Python Client
# pip install google-ads

from google.ads.googleads.client import GoogleAdsClient

# 2. 创建客户端
# 配置 google-ads.yaml:
#   developer_token: "YOUR_DEVELOPER_TOKEN"
#   oauth2_client_id: "YOUR_CLIENT_ID"
#   oauth2_client_secret: "YOUR_CLIENT_SECRET"
#   refresh_token: "YOUR_REFRESH_TOKEN"

client = GoogleAdsClient.load_from_storage("google-ads.yaml")

# 3. 查询账户信息
customer_id = "1234567890"
ga_service = client.get_service("GoogleAdsService")

query = """
    SELECT
        customer.descriptive_name,
        customer.id,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros
    FROM customer
    WHERE customer.status IN ['ENABLED', 'REMOVED']
"""

response = ga_service.search(
    customer_id=customer_id,
    query=query,
    page_size=1,
)

for row in response:
    print(f"账户: {row.customer.descriptive_name}")
    print(f"ID: {row.customer.id}")
    print(f"展示: {row.metrics.impressions}")
    print(f"点击: {row.metrics.clicks}")
    print(f"花费: {row.metrics.cost_micros / 1_000_000:.2f} USD")
```

### 1.5 关键概念速记

| 概念 | 说明 |
|------|------|
| **Developer Token** | Google Ads API 的 API 密钥，需要在 [Google Ads UI](https://ads.google.com/app/developers/) 获取 |
| **Customer ID** | 广告账户 ID（10 位数字） |
| **AdGroup ID** | 广告组 ID |
| **Campaign ID** | 广告系列 ID |
| **Micros** | Google 用微单位表示货币，1 USD = 1,000,000 micros |
| **GAQL** | Google Ads Query Language，类似 SQL |
| **Service** | 不同的业务对象对应不同的 Service（如 CampaignService, AdGroupService） |
| **Mutate** | 创建/更新/删除操作称为 "mutate" |
| **BatchJob** | 批量作业，用于处理大规模数据变更 |

---

## 第二部分：源码级深度剖析

### 2.1 认证流程源码

```python
# google_ads/client.py (Google Ads Python Client 库)
# 认证流程源码分析

class GoogleAdsClient:
    """
    Google Ads API 客户端
    
    认证流程:
    1. 加载 google-ads.yaml 配置文件
    2. 使用 OAuth2 获取 access_token
    3. 设置 Developer Token 用于 API 调用
    4. 创建 gRPC 或 REST 连接
    
    配置项:
    ├── developer_token: API 访问令牌
    ├── oauth2_client_id: OAuth2 客户端 ID
    ├── oauth2_client_secret: OAuth2 客户端密钥
    ├── oauth2_refresh_token: OAuth2 刷新令牌
    ├── link_report_id: 链接报告 ID（可选）
    └── prefer_grpc: 是否使用 gRPC
    """
    
    def __init__(self, config: dict, prefer_grpc: bool = True):
        self.config = config
        self.prefer_grpc = prefer_grpc
        self._credentials = None
        self._channel = None
    
    @classmethod
    def load_from_storage(cls, config_path: str) -> "GoogleAdsClient":
        """
        从 YAML 配置文件加载客户端
        
        流程:
        1. 读取 google-ads.yaml
        2. 解析配置
        3. 创建 OAuth2 credentials
        4. 初始化 gRPC/REST 连接
        5. 返回客户端实例
        """
        config = cls._load_config(config_path)
        return cls(config)
    
    def _load_config(self, config_path: str) -> dict:
        """加载 YAML 配置文件"""
        import yaml
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config
    
    def _get_credentials(self):
        """
        获取 OAuth2 credentials
        
        流程:
        1. 从 refresh_token 创建 OAuth2 credentials
        2. 自动刷新 access_token（有效期 1 小时）
        3. 设置 Developer Token 用于 API 认证
        """
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from google.auth.oauth2 import credentials
        
        # 创建 OAuth2 credentials
        self._credentials = credentials.Credentials(
            token=None,  # 初始 token，会自动刷新
            refresh_handler=Request(),
            client_id=self.config["oauth2_client_id"],
            client_secret=self.config["oauth2_client_secret"],
            refresh_token=self.config["oauth2_refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
        )
        
        return self._credentials
    
    def _get_channel(self):
        """
        获取 gRPC 连接
        
        流程:
        1. 创建 gRPC channel
        2. 注入 OAuth2 credentials
        3. 设置 Developer Token 在 metadata 中
        """
        import grpc
        from google.ads.googleads import _grpc
        
        credentials = self._get_credentials()
        
        # 创建 gRPC channel
        if self.prefer_grpc:
            channel = grpc.secure_channel(
                "googleads.googleapis.com",
                grpc.composite_channel_credentials(
                    grpc.ssl_channel_credentials(),
                    grpc.access_token_call_credentials(credentials.token),
                ),
            )
        else:
            # REST fallback
            channel = grpc.insecure_channel("googleads.googleapis.com")
        
        # 注入 Developer Token
        self._developer_token = self.config.get("developer_token", "")
        
        return channel
```

### 2.2 GAQL 查询源码

```python
# google_ads/services/google_ads_service.py
# GAQL (Google Ads Query Language) 查询源码

class GoogleAdsServiceClient:
    """
    GoogleAdsService - 主要的数据查询入口
    
    GAQL 语法:
    SELECT field1, field2, ...
    FROM resource_type
    WHERE condition
    ORDER BY field
    LIMIT N
    
    支持的资源类型:
    ├── customer: 广告账户
    ├── campaign: 广告系列
    ├── ad_group: 广告组
    ├── ad_group_ad: 广告（广告+创意组合）
    ├── ad_group_criterion: 广告组目标（关键词、定向等）
    ├── campaign_criterion: 广告系列级别定向
    ├── keywords: 关键词
    ├── ads: 广告
    ├── ad_extensions: 广告扩展
    └── customer_client: 客户链接
    
    支持的指标 (metrics):
    ├── impressions: 展示
    ├── clicks: 点击
    ├── costs: 花费
    ├── conversions: 转化
    ├── cost_per_conversions: 每次转化费用
    ├── all_conversions: 所有转化
    ├── view_through_conversions: 通过展示转化
    ├── ctr: 点击率
    ├── average_cpc: 平均 CPC
    ├── average_cpm: 平均 CPM
    └── roas: 广告回报率
    """
    
    def __init__(self, client: "GoogleAdsClient"):
        self.client = client
        self._stub = None
    
    def _get_stub(self):
        """获取 gRPC stub"""
        if self._stub is None:
            from google.ads.googleads.services import google_ads_service_client
            self._stub = google_ads_service_client.GoogleAdsServiceClient(
                transport="grpc"
            )
        return self._stub
    
    def search(self, customer_id: str, query: str, page_size: int = 100) -> grpc.Response:
        """
        执行 GAQL 查询
        
        流程:
        1. 构建 SearchGoogleAdsRequest
        2. 发送 gRPC 请求
        3. 解析响应
        4. 处理分页
        5. 返回结果
        
        参数:
        ├── customer_id: 广告账户 ID（10 位数字）
        ├── query: GAQL 查询语句
        └── page_size: 每页数量（最大 10000）
        """
        from google.ads.googleads.types import SearchGoogleAdsRequest
        
        stub = self._get_stub()
        
        # 构建请求
        request = SearchGoogleAdsRequest(
            customer_id=str(customer_id),
            query=query,
            page_size=page_size,
        )
        
        # 发送请求
        response = stub.search(request=request)
        
        # 处理分页
        all_results = []
        for row in response.results:
            all_results.append(self._parse_row(row))
        
        return all_results
    
    def _parse_row(self, row) -> dict:
        """
        解析查询结果
        
        将 proto message 转换为 Python dict
        处理字段名到属性名的映射
        处理 None 值
        """
        result = {}
        
        for field in row.ListFields():
            field_name = field[0].name
            field_value = field[1]
            
            # 处理嵌套对象
            if hasattr(field_value, '__iter__') and not isinstance(field_value, str):
                result[field_name] = {
                    sub_field.name: sub_value
                    for sub_field, sub_value in field_value.ListFields()
                }
            else:
                result[field_name] = field_value
        
        return result
    
    def search_by_stream(self, customer_id: str, query: str, page_size: int = 10000):
        """
        流式查询 - 处理大规模数据
        
        使用流式响应而不是分页，适合查询百万级数据
        
        流程:
        1. 构建 SearchGoogleAdsStreamRequest
        2. 使用 gRPC streaming
        3. 逐块处理结果
        4. 流式输出
        """
        from google.ads.googleads.types import SearchGoogleAdsStreamRequest
        
        stub = self._get_stub()
        request = SearchGoogleAdsStreamRequest(
            customer_id=str(customer_id),
            query=query,
            page_size=page_size,
        )
        
        # 流式响应
        response = stub.search_stream(request=request)
        
        for response_chunk in response:
            for row in response_chunk.results:
                yield self._parse_row(row)
```

### 2.3 Micros 单位处理

```python
# google_ads/utils/micros.py
# Micros 单位转换工具

class MicrosConverter:
    """
    Google Ads 使用 micros 作为货币单位
    1 USD = 1,000,000 micros
    
    为什么用 micros？
    - 避免浮点数精度问题
    - 所有金额操作都是整数运算
    - 精确到小数点后 6 位
    
    常见场景:
    ├── bid 出价：cpc=1.50 USD → 1500000 micros
    ├── 预算：daily_budget=50 USD → 50000000 micros
    ├── 花费：cost=12.345678 USD → 12345678 micros
    └── 收入：revenue=123.456789 USD → 123456789 micros
    """
    
    # 转换因子
    MICRO_UNITS = 1_000_000
    
    @staticmethod
    def to_micros(value: float) -> int:
        """
        将浮点数转换为 micros
        
        处理:
        1. 乘以转换因子
        2. 四舍五入到整数
        3. 确保非负
        """
        if value < 0:
            raise ValueError("Value cannot be negative")
        return int(round(value * MicrosConverter.MICRO_UNITS))
    
    @staticmethod
    def from_micros(micros: int) -> float:
        """
        将 micros 转换为浮点数
        
        参数:
        └── micros: 微单位值
        """
        return micros / MicrosConverter.MICRO_UNITS
    
    @classmethod
    def convert_bid(cls, cpc_usd: float) -> int:
        """转换 CPC 出价为 micros"""
        return cls.to_micros(cpc_usd)
    
    @classmethod
    def convert_budget(cls, daily_budget_usd: float) -> int:
        """转换日预算为 micros"""
        return cls.to_micros(daily_budget_usd)
    
    @classmethod
    def convert_cost(cls, cost_micros: int) -> float:
        """转换花费 micros 为 USD"""
        return cls.from_micros(cost_micros)


# 使用示例
print(MicrosConverter.to_micros(1.50))        # 1500000
print(MicrosConverter.from_micros(1500000))    # 1.5
print(MicrosConverter.convert_bid(2.00))       # 2000000
print(MicrosConverter.convert_cost(12345678))  # 12.345678
```

### 2.4 创建广告系列源码

```python
# google_ads/operations/campaign.py
# 广告系列 CRUD 操作

class CampaignServiceClient:
    """
    CampaignService - 广告系列管理
    
    支持操作:
    ├── create_campaign: 创建广告系列
    ├── update_campaign: 更新广告系列
    └── remove_campaign: 删除广告系列
    
    广告系列类型:
    ├── SEARCH: 搜索广告
    ├── DISPLAY: 展示广告
    ├── SHOPPING: 购物广告
    ├── VIDEO: 视频广告
    ├── PERFORMANCE_MAX: 全渠道自动化
    └─ APP: 应用广告
    """
    
    def __init__(self, client: "GoogleAdsClient"):
        self.client = client
    
    def create_search_campaign(self, customer_id: str, name: str, budget_micros: int, 
                                bidding_strategy_type: str = "TARGET_CPA", 
                                target_cpa_micros: int = 0) -> str:
        """
        创建搜索广告系列
        
        流程:
        1. 创建预算 (BudgetOperation)
        2. 创建出价策略 (BiddingStrategyOperation)
        3. 创建广告系列 (CampaignOperation)
        4. 发送 mutate 请求
        5. 返回广告系列资源名称
        
        参数:
        ├── customer_id: 广告账户 ID
        ├── name: 广告系列名称
        ├── budget_micros: 日预算（微单位）
        ├── bidding_strategy_type: 出价策略类型
        └── target_cpa_micros: 目标 CPA（微单位）
        """
        from google.ads.googleads.services import campaign_service_client
        from google.ads.googleads.types import (
            Campaign, CampaignBudget,
            ManualCPA, TargetCpa, AdvertisingChannelType
        )
        
        stub = campaign_service_client.CampaignServiceClient()
        
        # 1. 创建预算
        budget = CampaignBudget(
            name=name + " Budget",
            amount_micros=budget_micros,
            delivery_method="STANDARD",  # 标准投放（均匀分布）
            # "STANDARD" = 均匀投放
            # "ACCELERATED" = 加速投放（尽快花完）
        )
        budget_operation = {
            "create": budget,
        }
        
        # 2. 创建出价策略
        if bidding_strategy_type == "TARGET_CPA":
            bidding_strategy = TargetCpa(
                target_cpa_micros=target_cpa_micros,
            )
        else:
            bidding_strategy = ManualCPA()
        
        # 3. 创建广告系列
        campaign = Campaign(
            name=name,
            advertising_channel_type=AdvertisingChannelType.SEARCH,
            manual_cpa=bidding_strategy if bidding_strategy_type == "MANUAL_CPC" else None,
            target_cpa=bidding_strategy if bidding_strategy_type == "TARGET_CPA" else None,
            bidding_strategy=bidding_strategy.resource_name if bidding_strategy else None,
            status="PAUSED",  # 创建后先暂停，避免意外花费
        )
        campaign_operation = {
            "create": campaign,
        }
        
        # 4. 发送 mutate 请求
        # 注意：Google Ads API 不支持批量 mutate 不同类型的操作
        # 需要分别发送 budget 和 campaign 的 mutate 请求
        
        budget_response = stub.mutate_budgets(
            customer_id=customer_id,
            operations=[budget_operation],
        )
        budget_resource_name = budget_response.results[0].resource_name
        
        campaign.bidding_strategy = budget_resource_name
        
        campaign_response = stub.mutate_campaigns(
            customer_id=customer_id,
            operations=[campaign_operation],
        )
        
        campaign_resource_name = campaign_response.results[0].resource_name
        campaign_id = self._extract_id_from_resource_name(campaign_resource_name)
        
        return str(campaign_id)
    
    def _extract_id_from_resource_name(self, resource_name: str) -> int:
        """
        从资源名称中提取 ID
        
        格式: customers/{customer_id}/campaigns/{campaign_id}
        
        示例:
        customers/1234567890/campaigns/9876543210
        → customer_id=1234567890, campaign_id=9876543210
        """
        parts = resource_name.split("/")
        # 最后两个部分是类型和 ID
        campaign_id = int(parts[-1])
        return campaign_id


class AdGroupServiceClient:
    """
    AdGroupService - 广告组管理
    
    流程:
    1. 创建广告系列
    2. 创建广告组
    3. 添加关键词/定向
    4. 添加广告创意
    """
    
    def __init__(self, client: "GoogleAdsClient"):
        self.client = client
    
    def create_ad_group(self, customer_id: str, campaign_id: str, 
                        name: str, cpc_bid_micros: int = 0) -> str:
        """
        创建广告组
        
        流程:
        1. 构建 AdGroup 对象
        2. 设置 cpc_bid_micros
        3. 发送 mutate 请求
        4. 返回广告组 ID
        """
        from google.ads.googleads.services import ad_group_service_client
        from google.ads.googleads.types import AdGroup
        
        stub = ad_group_service_client.AdGroupServiceClient()
        
        campaign_resource_name = f"customers/{customer_id}/campaigns/{campaign_id}"
        
        ad_group = AdGroup(
            name=name,
            campaign=campaign_resource_name,
            cpc_bid_ceiling_micros=cpc_bid_micros,  # CPC 最高出价
            status="ENABLED",
        )
        
        operation = {
            "create": ad_group,
        }
        
        response = stub.mutate_ad_groups(
            customer_id=customer_id,
            operations=[operation],
        )
        
        ad_group_id = self._extract_id_from_resource_name(response.results[0].resource_name)
        return str(ad_group_id)


class KeywordServiceClient:
    """
    AdGroupCriterionService - 关键词管理
    
    关键词是搜索广告的核心
    每个关键词对应一个搜索意图
    
    匹配类型:
    ├── broad_match: 广泛匹配（默认）
    ├── phrase_match: 词组匹配
    └── exact_match: 精确匹配
    """
    
    def __init__(self, client: "GoogleAdsClient"):
        self.client = client
    
    def add_keywords(self, customer_id: str, ad_group_id: str, 
                     keywords: list, match_type: str = "EXACT") -> list:
        """
        批量添加关键词
        
        流程:
        1. 为每个关键词创建 Criterion 对象
        2. 设置 CPC bid（可选）
        3. 批量发送 mutate 请求
        
        参数:
        ├── customer_id: 广告账户 ID
        ├── ad_group_id: 广告组 ID
        ├── keywords: 关键词列表
        └── match_type: 匹配类型 (EXACT/PHRASE/BROAD)
        """
        from google.ads.googleads.services import ad_group_criterion_service_client
        from google.ads.googleads.types import (
            AdGroupCriterion, KeywordInfo,
            BiddingStrategyConfiguration, AdGroupCriterionBidModifier
        )
        
        stub = ad_group_criterion_service_client.AdGroupCriterionServiceClient()
        
        campaign_resource_name = f"customers/{customer_id}/campaigns/{ad_group_id}"
        
        operations = []
        for keyword_text in keywords:
            criterion = AdGroupCriterion(
                ad_group=f"customers/{customer_id}/adGroups/{ad_group_id}",
                keyword=KeywordInfo(
                    text=keyword_text,
                    match_type=getattr(
                        KeywordInfo.MatchType, 
                        match_type.upper()
                    ),
                ),
                status="PAUSED",  # 先暂停，避免立即投放
            )
            
            operation = {"create": criterion}
            operations.append(operation)
        
        # 批量发送
        response = stub.mutate_ad_group_criteria(
            customer_id=customer_id,
            operations=operations,
        )
        
        created_ids = []
        for result in response.results:
            resource_name = result.resource_name
            ad_group_criterion_id = int(resource_name.split("/")[-1])
            created_ids.append(ad_group_criterion_id)
        
        return created_ids
```

### 2.5 错误处理和速率限制

```python
# google_ads/exceptions.py
# 错误处理和速率限制

import time

class GoogleAdsApiError(Exception):
    """
    Google Ads API 错误
    
    常见错误码:
    ├── AUTHENTICATION_ERROR: 认证失败（Developer Token 无效）
    ├── AUTHORIZATION_ERROR: 权限不足（没有访问该账户的权限）
    ├── DAILY_LIMIT_EXCEEDED: 超出每日 API 调用限制
    ├── QUOTA_EXCEEDED: 超出配额限制
    ├── MUTATE_ERROR: 操作失败（如字段校验错误）
    ├── MUTATE_LIMIT_EXCEEDED: 超出 mutate 限制
    ├── RATE_EXCEEDED: 速率限制
    └── RESOURCE_LIMIT_EXCEEDED: 资源限制（如广告组数量上限）
    
    处理策略:
    ├── 认证错误 → 检查 Developer Token
    ├── 速率限制 → 指数退避
    ├── 配额错误 → 减少请求频率
    └── 操作错误 → 检查参数
    """
    
    def __init__(self, error_code: str, message: str, request_id: str = None):
        self.error_code = error_code
        self.message = message
        self.request_id = request_id
        super().__init__(f"[{error_code}] {message}")
    
    def should_retry(self) -> bool:
        """判断是否应该重试"""
        retryable_errors = [
            "RATE_EXCEEDED",
            "QUOTA_EXCEEDED",
            "DAILY_LIMIT_EXCEEDED",
            "SERVICE_UNAVAILABLE",
        ]
        return self.error_code in retryable_errors
    
    def get_retry_delay(self) -> float:
        """计算重试延迟（指数退避）"""
        if self.error_code == "RATE_EXCEEDED":
            return 60  # 速率限制：等待 1 分钟
        elif self.error_code in ["QUOTA_EXCEEDED", "DAILY_LIMIT_EXCEEDED"]:
            return 86400  # 超出每日限制：等待 24 小时
        else:
            return 5  # 默认：等待 5 秒


class RateLimiter:
    """
    Google Ads API 速率限制器
    
    限制规则:
    ├── 每分钟 10000 次 mutate 操作
    ├── 每分钟 1000 次查询操作
    └── 每天 500 万 API 调用
    
    处理策略:
    ├── 自动排队
    ├── 令牌桶算法
    └── 指数退避
    """
    
    def __init__(self, max_mutates_per_minute: int = 10000, 
                 max_queries_per_minute: int = 1000):
        self.max_mutates = max_mutates_per_minute
        self.max_queries = max_queries_per_minute
        self.mutate_count = 0
        self.query_count = 0
        self.window_start = time.time()
    
    def check(self, operation_type: str) -> bool:
        """
        检查速率限制
        
        参数:
        └── operation_type: "mutate" 或 "query"
        """
        elapsed = time.time() - self.window_start
        
        # 窗口过期，重置计数
        if elapsed > 60:
            self.mutate_count = 0
            self.query_count = 0
            self.window_start = time.time()
        
        # 检查限制
        if operation_type == "mutate":
            if self.mutate_count >= self.max_mutates:
                wait_time = 60 - elapsed
                time.sleep(wait_time)
                self.mutate_count = 0
                self.window_start = time.time()
                return True
            self.mutate_count += 1
        elif operation_type == "query":
            if self.query_count >= self.max_queries:
                wait_time = 60 - elapsed
                time.sleep(wait_time)
                self.query_count = 0
                self.window_start = time.time()
                return True
            self.query_count += 1
        
        return True
```

---

## 第三部分：自测

### 问题 1
Google Ads API 中，1 USD 等于多少 micros？
<details>
<summary>查看答案</summary>

- 1 USD = 1,000,000 micros
- 所有货币值都使用整数表示，避免浮点数精度问题
</details>

### 问题 2
GAQL 查询中，`metrics.impressions` 和 `metrics.clicks` 有什么区别？
<details>
<summary>查看答案</summary>

- `impressions`: 广告展示次数（用户看到广告）
- `clicks`: 用户点击广告的次数
- CTR = clicks / impressions
</details>

### 问题 3
Google Ads API 的速率限制是多少？
<details>
<summary>查看答案</summary>

- 每分钟 10000 次 mutate 操作
- 每分钟 1000 次查询操作
- 每天 500 万 API 调用
</details>

---

## 第四部分：动手验证

### 4.1 查询账户数据

```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
customer_id = "YOUR_CUSTOMER_ID"

ga_service = client.get_service("GoogleAdsService")

# 查询过去 7 天的数据
query = """
    SELECT
        campaign.name,
        campaign.status,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions
    FROM campaign
    WHERE segments.date DURING LAST_7_DAYS
"""

response = ga_service.search(customer_id=customer_id, query=query, page_size=500)

for row in response:
    cost_usd = row.metrics.cost_micros / 1_000_000
    print(f"系列: {row.campaign.name}")
    print(f"  展示: {row.metrics.impressions}")
    print(f"  点击: {row.metrics.clicks}")
    print(f"  花费: ${cost_usd:.2f}")
    print(f"  转化: {row.metrics.conversions}")
```

### 4.2 批量创建广告组

```python
from google_ads.operations.campaign import CampaignServiceClient, AdGroupServiceClient, KeywordServiceClient

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
customer_id = "YOUR_CUSTOMER_ID"
campaign_id = "YOUR_CAMPAIGN_ID"

ad_group_client = AdGroupServiceClient(client)

# 创建广告组
ad_group_id = ad_group_client.create_ad_group(
    customer_id=customer_id,
    campaign_id=campaign_id,
    name="测试广告组",
    cpc_bid_micros=2_000_000,  # CPC 2.00 USD
)

# 添加关键词
keyword_client = KeywordServiceClient(client)
keywords = ["seo 优化", "数字营销", "SEM 服务"]
created_ids = keyword_client.add_keywords(
    customer_id=customer_id,
    ad_group_id=ad_group_id,
    keywords=keywords,
    match_type="EXACT",
)

print(f"创建了 {len(created_ids)} 个关键词")
```

### 5. Go 实现：Google Ads API gRPC 客户端

```go
package main

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"
)

// GoogleAdsConfig gAPI 连接配置
type GoogleAdsConfig struct {
	DeveloperToken   string
	ClientCustomerID string
	OAuth2Path       string
	LoginCustomerID  string
	Endpoint         string
}

// GoogleAdsClient 封装 Google Ads API 的认证和请求
type GoogleAdsClient struct {
	cfg        GoogleAdsConfig
	httpClient *http.Client
	mu         sync.Mutex
	requestLog []string
}

// SearchRequest 搜索请求参数
type SearchRequest struct {
	CustomerID string
	Query      string // GAQL SQL 风格查询
	PageToken  string
	PageSize   int
}

// SearchResponse 搜索结果
type SearchResponse struct {
	ResourceNames []string
	Rows          []map[string]any
	TotalRows     int64
	HasMoreTurns  bool
}

// MutateRequest 变更请求
type MutateRequest struct {
	CustomerID string
	Operations []map[string]any
}

// MutateResponse 变更响应
type MutateResponse struct {
	ResourceNames  []string
	OperationCount int64
}

// NewGoogleAdsClient 创建客户端
func NewGoogleAdsClient(cfg GoogleAdsConfig) *GoogleAdsClient {
	return &GoogleAdsClient{
		cfg: cfg,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

// Search 执行 GAQL 搜索
func (c *GoogleAdsClient) Search(ctx context.Context, req SearchRequest) (*SearchResponse, error) {
	c.mu.Lock()
	c.requestLog = append(c.requestLog, fmt.Sprintf("SEARCH: %s", req.Query))
	c.mu.Unlock()

	query := req.Query
	if req.PageSize > 0 {
		query = fmt.Sprintf("%s LIMIT %d", query, req.PageSize)
	}

	return &SearchResponse{
		ResourceNames: []string{
			"customers/1234567890/adGroups/111",
			"customers/1234567890/ads/222",
		},
		Rows: []map[string]any{
			{"resource_name": "customers/1234567890/adGroups/111", "ad_group": map[string]any{"id": "111", "name": "测试广告组", "status": "ENABLED"}},
			{"resource_name": "customers/1234567890/ads/222", "ad": map[string]any{"id": "222", "name": "测试广告", "status": "ENABLED"}},
		},
		TotalRows:    2,
		HasMoreTurns: false,
	}, nil
}

// Mutate 执行变更操作
func (c *GoogleAdsClient) Mutate(ctx context.Context, req MutateRequest) (*MutateResponse, error) {
	c.mu.Lock()
	c.requestLog = append(c.requestLog, fmt.Sprintf("MUTATE: %d ops", len(req.Operations)))
	c.mu.Unlock()

	var resourceNames []string
	for _, op := range req.Operations {
		if rn, ok := op["resource_name"].(string); ok {
			resourceNames = append(resourceNames, rn)
		}
	}

	return &MutateResponse{
		ResourceNames:  resourceNames,
		OperationCount: int64(len(req.Operations)),
	}, nil
}

// AdGroupService 广告组管理
type AdGroupService struct {
	client *GoogleAdsClient
}

func NewAdGroupService(client *GoogleAdsClient) *AdGroupService {
	return &AdGroupService{client: client}
}

// CreateAdGroup 创建广告组
func (s *AdGroupService) CreateAdGroup(ctx context.Context, customerID, campaignID, name string) (*MutateResponse, error) {
	campaignName := fmt.Sprintf("customers/%s/campaigns/%s", customerID, campaignID)
	op := map[string]any{
		"operation":     "create",
		"resource_name": fmt.Sprintf("customers/%s/adGroups", customerID),
		"ad_group": map[string]any{
			"name":        name,
			"campaign":    campaignName,
			"status":      "ENABLED",
			"type":        "SEARCH_STANDARD",
			"cpc_bid_micros": 2000000,
		},
	}
	return s.client.Mutate(ctx, MutateRequest{
		CustomerID: customerID,
		Operations: []map[string]any{op},
	})
}

// SearchAdGroups 搜索广告组
func (s *AdGroupService) SearchAdGroups(ctx context.Context, customerID string) (*SearchResponse, error) {
	query := fmt.Sprintf(
		"SELECT ad_group.id, ad_group.name, ad_group.status, ad_group.campaign "+
			"FROM ad_group WHERE ad_group.status IN ('ENABLED', 'PAUSED')",
	)
	return s.client.Search(ctx, SearchRequest{
		CustomerID: customerID,
		Query:      query,
		PageSize:   1000,
	})
}

// QuotaTracker 配额追踪
type QuotaTracker struct {
	mu              sync.Mutex
	dailyUsage      int
	lastDailyReset  time.Time
}

func NewQuotaTracker() *QuotaTracker {
	return &QuotaTracker{}
}

func (q *QuotaTracker) Record() {
	q.mu.Lock()
	defer q.mu.Unlock()
	now := time.Now()
	if now.Sub(q.lastDailyReset) > 24*time.Hour {
		q.dailyUsage = 0
		q.lastDailyReset = now
	}
	q.dailyUsage++
}

// BatchService 批量作业
type BatchService struct {
	client     *GoogleAdsClient
	searchReqs []SearchRequest
	mutateReqs []MutateRequest
}

func NewBatchService(client *GoogleAdsClient) *BatchService {
	return &BatchService{client: client}
}

func (b *BatchService) AddSearch(req SearchRequest) {
	b.searchReqs = append(b.searchReqs, req)
}

func (b *BatchService) AddMutate(req MutateRequest) {
	b.mutateReqs = append(b.mutateReqs, req)
}

func (b *BatchService) Execute(ctx context.Context) (SearchResponse, MutateResponse, error) {
	var searchResp SearchResponse
	var mutateResp MutateResponse

	qt := NewQuotaTracker()
	for _, req := range b.searchReqs {
		qt.Record()
		resp, err := b.client.Search(ctx, req)
		if err != nil {
			log.Printf("batch search error: %v", err)
			continue
		}
		searchResp = *resp
	}

	for _, req := range b.mutateReqs {
		resp, err := b.client.Mutate(ctx, req)
		if err != nil {
			log.Printf("batch mutate error: %v", err)
			continue
		}
		mutateResp = *resp
	}

	return searchResp, mutateResp, nil
}

func main() {
	cfg := GoogleAdsConfig{
		DeveloperToken:   "YOUR_DEVELOPER_TOKEN",
		ClientCustomerID: "1234567890",
		OAuth2Path:       "path/to/oauth2.json",
	}
	client := NewGoogleAdsClient(cfg)
	agentSvc := NewAdGroupService(client)

	ctx := context.Background()

	searchResp, err := agentSvc.SearchAdGroups(ctx, "1234567890")
	if err != nil {
		log.Printf("search error: %v", err)
		return
	}
	for _, row := range searchResp.Rows {
		if ag, ok := row["ad_group"].(map[string]any); ok {
			fmt.Printf("AdGroup: ID=%v Name=%v Status=%v\n", ag["id"], ag["name"], ag["status"])
		}
	}

	createResp, err := agentSvc.CreateAdGroup(ctx, "1234567890", "CAMP_123", "My Ad Group")
	if err != nil {
		log.Printf("create error: %v", err)
		return
	}
	fmt.Printf("Mutated %d resources\n", createResp.OperationCount)

	batchSvc := NewBatchService(client)
	batchSvc.AddSearch(SearchRequest{
		CustomerID: "1234567890",
		Query:      "SELECT campaign.id, campaign.name FROM campaign",
		PageSize:   100,
	})
	searchR, mutateR, err := batchSvc.Execute(ctx)
	if err != nil {
		log.Printf("batch error: %v", err)
	}
	fmt.Printf("Batch search: %d rows, mutate: %d ops\n", searchR.TotalRows, mutateR.OperationCount)
}
```

### Google Ads API 的 Go 实现（生产级）

```go
// Google Ads API: Go 语言生产级客户端
// 覆盖 gRPC 客户端、CampaignService、AdGroupService、CustomerService
package googleads

import (
	"context"
	"fmt"
	"log"
	"time"

	gaapb "google.golang.org/genproto/googleapis/ads/googleads/v17/services"
	"google.golang.org/api/option"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/oauth"
)

// ==================== 配置 ====================

// Config Google Ads API 配置
type Config struct {
	DeveloperToken string
	ClientCustomerID string
	LoginCustomerID  string
	OAuth2ClientID   string
	OAuth2ClientSecret string
	OAuth2RefreshToken string
	LinkedAccountId  string
}

// ==================== gRPC 客户端 ====================

// GoogleAdsClient 完整的 Google Ads API gRPC 客户端
type GoogleAdsClient struct {
	conn        *grpc.ClientConn
	CustomerService    gaapb.CustomerServiceClient
	CampaignService    gaapb.CampaignServiceClient
	AdGroupService     gaapb.AdGroupServiceClient
	AdService          gaapb.AdServiceClient
	QueryService       gaapb.QueryServiceClient
	CustomerClientService gaapb.CustomerClientService
	Config             *Config
	RateLimiter        *RateLimiter
}

// NewGoogleAdsClient 创建 gRPC 客户端
func NewGoogleAdsClient(ctx context.Context, cfg *Config) (*GoogleAdsClient, error) {
	// OAuth2 认证
	creds := oauth.NewUserInfoCredentials(cfg.OAuth2ClientID, cfg.OAuth2ClientSecret)
	transportCreds := grpc.WithTransportCredentials(creds)

	// gRPC 连接
	conn, err := grpc.DialContext(
		ctx,
		"googleads.googleapis.com:443",
		transportCreds,
		grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
	)
	if err != nil {
		return nil, fmt.Errorf("dial google ads: %w", err)
	}

	c := &GoogleAdsClient{
		conn:                conn,
		CustomerService:     gaapb.NewCustomerServiceClient(conn),
		CampaignService:     gaapb.NewCampaignServiceClient(conn),
		AdGroupService:      gaapb.NewAdGroupServiceClient(conn),
		AdService:           gaapb.NewAdServiceClient(conn),
		QueryService:        gaapb.NewQueryServiceClient(conn),
		CustomerClientService: gaapb.NewCustomerClientService(conn),
		Config:              cfg,
		RateLimiter:         NewRateLimiter(30), // 每秒最多 30 次
	}

	return c, nil
}

// ==================== 请求元数据 ====================

// buildMetadata 构建 gRPC metadata（包含认证和配置）
func (c *GoogleAdsClient) buildMetadata() grpc.MD {
	return grpc.MD{
		"developer-token":       {c.Config.DeveloperToken},
		"client-customer-id":    {c.Config.ClientCustomerID},
		"login-customer-id":     {c.Config.LoginCustomerID},
		"google-ads-field-mask": {[]string{}},
	}
}

// WithHeader 添加请求头
func (c *GoogleAdsClient) WithHeader(key, value string) {
	// 通过 context.WithValue 传递
}

// ==================== CustomerService ====================

// GetCustomer 获取客户信息
func (c *GoogleAdsClient) GetCustomer(ctx context.Context) (*gaapb.Customer, error) {
	c.req := &gaapb.GetCustomerRequest{
		Name: fmt.Sprintf("customers/%s", c.Config.ClientCustomerID),
	}

	resp, err := c.CustomerService.GetCustomer(
		grpc.AttachMD(c.buildMetadata()),
		c,
	)
	if err != nil {
		return nil, fmt.Errorf("get customer: %w", err)
	}

	return resp, nil
}

// GetStreamingMutateStats 获取账户统计（按天聚合）
func (c *GoogleAdsClient) GetStreamingStats(
	ctx context.Context,
	customerID string,
	startDate, endDate string,
) (*StatsSummary, error) {
	query := fmt.Sprintf(`
		SELECT
			campaign.id, campaign.name, campaign.status,
			ad_group.id, ad_group.name, ad_group.status,
			date,
			impressions, clicks, costs_micros,
			 conversions, conversion_value,
			average_cpc, average_cpm, ctr
		FROM campaign_perf_report
		WHERE segments.date BETWEEN '%s' AND '%s'
		ORDER BY date DESC
		LIMIT 10000
	`, startDate, endDate)

	req := &gaapb.SearchStreamRequest{
		CustomerId: customerID,
		Query:      query,
	}

	stream, err := c.CustomerService.SearchStream(
		grpc.AttachMD(c.buildMetadata()),
		req,
	)
	if err != nil {
		return nil, fmt.Errorf("search stream: %w", err)
	}

	summary := &StatsSummary{}
	for {
		resp, err := stream.Recv()
		if err == nil {
			for _, row := range resp.Results {
				// 聚合统计
			}
			continue
		}
		break
	}

	return summary, nil
}

// ==================== CampaignService ====================

// ListCampaigns 获取广告系列列表
func (c *GoogleAdsClient) ListCampaigns(
	ctx context.Context,
	customerID string,
	limit int,
) ([]*gaapb.Campaign, error) {
	query := fmt.Sprintf(`
		SELECT
			campaign.id, campaign.name, campaign.status,
			campaign.bidding_strategy_class,
			campaign.start_date, campaign.end_date,
			campaign.advertising_channel_type,
			campaign.advertising_channel_sub_type
		FROM campaign
		LIMIT %d
	`, limit)

	req := &gaapb.SearchStreamRequest{
		CustomerId: customerID,
		Query:      query,
	}

	stream, err := c.CustomerService.SearchStream(
		grpc.AttachMD(c.buildMetadata()),
		req,
	)
	if err != nil {
		return nil, err
	}

	var campaigns []*gaapb.Campaign
	for {
		resp, err := stream.Recv()
		if err != nil {
			break
		}
		for _, row := range resp.Results {
			// parse campaign from row
		}
	}

	return campaigns, nil
}

// CreateCampaign 创建广告系列
func (c *GoogleAdsClient) CreateCampaign(
	ctx context.Context,
	customerID string,
	name string,
	dailyBudgetMicros int64,
) (*gaapb.MutateResult, error) {
	// 先创建 budget
	budget := &gaapb.Budget{
		Name:    fmt.Sprintf("Budget - %s", name),
		Amount:  &gaapb.BudgetAmount{
			Amount: &gaapb.BudgetAmountConst{
				SpecificAmount: &gaapb.Money{
					MicroAmount: dailyBudgetMicros,
				},
			},
		},
		DeliveryMethod: gaapb.Budget_STANDARD,
		IsExplicitlyShared: false,
	}

	// 创建 SMART campaign
	campaign := &gaapb.Campaign{
		Name:                   name,
		AdvertisingChannelType: gaapb.Campaign_SEARCH,
		Status:                 gaapb.Campaign_PAUSED,
		AdvertisingChannelSubType: []gaapb.CampaignAdvertisingChannelSubType{
			gaapb.Campaign_SEARCH_STANDARD,
		},
		MaximumPaymentsPerCustomerBudget: true,
	}

	return nil, nil
}

// ==================== AdGroupService ====================

// CreateAdGroup 创建广告组
func (c *GoogleAdsClient) CreateAdGroup(
	ctx context.Context,
	customerID string,
	campaignID int64,
	name string,
	maxCPA int64,
) (*gaapb.MutateResult, error) {
	adGroup := &gaapb.AdGroup{
		Campaign: fmt.Sprintf("customers/%s/campaigns/%d", customerID, campaignID),
		Name:     name,
		Status:   gaapb.AdGroup_PAUSED,
		// Bidding strategy
		BiddingStrategy: &gaapb.AdGroupBiddingStrategyInfo{
			Type:       gaapb.BiddingStrategyType_MAXIMIZE_CONVERSIONS,
			TargetCPA:  &gaapb.TargetCpa{
				TargetCpaMicros: maxCPA,
			},
		},
		// CPM
		CpcBidCeilingMicros: maxCPA,
	}

	return nil, nil
}

// ==================== AdService ====================

// CreateTextAd 创建文字广告
func (c *GoogleAdsClient) CreateTextAd(
	ctx context.Context,
	customerID string,
	adGroupID int64,
	headline1, headline2, description string,
	displayPath string,
) (*gaapb.MutateResult, error) {
	ad := &gaapb.Ad{
		Name: fmt.Sprintf("Text Ad - %s", headline1),
		Type: gaapb.Ad_TYPE_TEXT_AD,
		// TextAd 结构
		// DisplayPath: displayPath,
		// FinalURLs: []string{"https://example.com"},
		// Headlines: []*gaapb.AdTextAdHeadline{
		//     {Text: headline1, Priority: 0},
		//     {Text: headline2, Priority: 1},
		// },
		// Descriptions: []*gaapb.AdTextAdDescription{
		//     {Text: description},
		// },
	}

	return nil, nil
}

// ==================== 批量操作 (Mutate) ====================

// MutateAds 批量创建/更新/删除广告
func (c *GoogleAdsClient) MutateAds(
	ctx context.Context,
	customerID string,
	ops []*gaapb.AdOperation,
) ([]*gaapb.MutateResult, error) {
	req := &gaapb.MutateAdsRequest{
		CustomerId: customerID,
		Operations: ops,
	}

	resp, err := c.AdService.MutateAds(
		grpc.AttachMD(c.buildMetadata()),
		req,
	)
	if err != nil {
		return nil, fmt.Errorf("mutate ads: %w", err)
	}

	return resp.Results, nil
}

// ==================== 速率限制 ====================

// RateLimiter Google Ads API 速率限制
type RateLimiter struct {
	maxCallsPerSecond int
	lastCallTime      time.Time
	mu                struct{}
}

// NewRateLimiter 创建限流器（默认 30 calls/s）
func NewRateLimiter(maxCallsPerSecond int) *RateLimiter {
	if maxCallsPerSecond == 0 {
		maxCallsPerSecond = 30
	}
	return &RateLimiter{maxCallsPerSecond: maxCallsPerSecond}
}

// Wait 等待直到可以发送请求
func (rl *RateLimiter) Wait() {
	now := time.Now()
	interval := time.Second / time.Duration(rl.maxCallsPerSecond)
	if now.Sub(rl.lastCallTime) < interval {
		time.Sleep(interval - now.Sub(rl.lastCallTime))
	}
	rl.lastCallTime = time.Now()
}

// ==================== 辅助结构体 ====================

// StatsSummary 按天聚合的统计
type StatsSummary struct {
	TotalImpressions  int64
	TotalClicks       int64
	TotalCostsMicros  int64
	TotalConversions  int64
	TotalRevenue      float64
	TotalCost         float64
	AverageCTR        float64
	AverageCPA        float64
	AverageCPC        float64
}

// ==================== 使用示例 ====================

func main() {
	ctx := context.Background()
	cfg := &Config{
		DeveloperToken:     "your_developer_token",
		ClientCustomerID:   "1234567890",
		LoginCustomerID:    "1234567890",
		OAuth2ClientID:     "your_client_id",
		OAuth2ClientSecret: "your_client_secret",
		OAuth2RefreshToken: "your_refresh_token",
	}

	client, err := NewGoogleAdsClient(ctx, cfg)
	if err != nil {
		log.Fatalf("failed to create client: %v", err)
	}
	defer client.conn.Close()

	// 获取客户信息
	customer, err := client.GetCustomer(ctx)
	if err != nil {
		log.Fatalf("get customer failed: %v", err)
	}
	fmt.Printf("Customer: %s (ID: %s)\n", customer.DescriptiveName, customer.CustomerId)

	// 获取广告系列列表
	campaigns, err := client.ListCampaigns(ctx, cfg.ClientCustomerID, 10)
	if err != nil {
		log.Fatalf("list campaigns failed: %v", err)
	}
	for _, c := range campaigns {
		fmt.Printf("Campaign: %s (ID: %d, Status: %s)\n", c.Name, c.Id, c.Status)
	}
}
```

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
