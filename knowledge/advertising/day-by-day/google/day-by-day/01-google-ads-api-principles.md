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
└─ App Ads (应用广告)
```

### 1.2 为什么需要 API？

```
没有 API:
- 手动操作：打开浏览器 → 登录 → 创建广告
- 效率低：改一个出价要半天
- 无法自动化：不能根据数据自动调整

有 API:
- 批量操作：一次更新 1000 个广告
- 自动优化：根据转化数据自动调出价
- 数据获取：拉取所有广告数据做分析
- 实时监控：发现问题立即调整
```

### 1.3 API 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                  Google Ads API 架构                         │
│                                                             │
│  ┌──────────────┐                                          │
│  │  你的系统     │                                          │
│  │  (Client)    │                                          │
│  └──────┬───────┘                                          │
│         │ HTTPS/gRPC                                        │
│         ▼                                                   │
│  ┌────────────────────────────────────────────────────────┐│
│  │               Google Ads API Server                     ││
│  │                                                        ││
│  │  ┌────────────────────────────────────────────────────┐││
│  │  │              API Gateway                           │││
│  │  └────────────┬───────────────────────────────────────┘││
│  │               │                                        ││
│  │  ┌────────────▼───────────────────────────────────────┐││
│  │  │           Rate Limiter                             │││
│  │  │           (每秒请求限制)                             │││
│  │  └────────────┬───────────────────────────────────────┘││
│  │               │                                        ││
│  │  ┌────────────▼───────────────────────────────────────┐││
│  │  │           Authentication                           │││
│  │  │           (OAuth2 + 刷新令牌)                        │││
│  │  └────────────┬───────────────────────────────────────┘││
│  │               │                                        ││
│  │  ┌────────────▼───────────────────────────────────────┐││
│  │  │           业务逻辑层                                 │││
│  │  │           (CampaignService, AdGroupService...)      │││
│  │  └────────────────────────────────────────────────────┘││
│  └────────────────────────────────────────────────────────┘│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 快速体验

```bash
# 1. 安装 Google Ads API SDK
pip install google-ads

# 2. 配置
# 创建 google-ads.yaml
# developer_token: YOUR_DEVELOPER_TOKEN
# refresh_token: YOUR_REFRESH_TOKEN
# client_id: YOUR_CLIENT_ID
# client_secret: YOUR_CLIENT_SECRET
# login_customer_id: YOUR_CUSTOMER_ID

# 3. Python 示例
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.enums import MetricEnum

# 获取客户端
client = GoogleAdsClient.load_from_storage('google-ads.yaml')

# 查询广告数据
query = """
SELECT
    campaign.name,
    campaign.status,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
"""

# 执行查询
customer = client.get_service("Customer")
row_iterator = client.get_service("GoogleAdsService").search(
    customer_id="1234567890",
    query=query
)

for row in row_iterator:
    campaign = row.campaign
    metrics = row.metrics
    print(f"广告系列: {campaign.name}")
    print(f"展示: {metrics.impressions}")
    print(f"点击: {metrics.clicks}")
    print(f"花费: {metrics.cost_micros / 1000000} 元")
```

### 1.5 关键概念总结

| 概念 | 说明 |
|------|------|
| **Customer ID** | Google Ads 账户的唯一标识 |
| **Campaign** | 广告系列，包含多个广告组 |
| **AdGroup** | 广告组，包含多个广告 |
| **Keyword** | 关键词，匹配用户搜索 |
| **Metrics** | 指标，展示、点击、转化等 |
| **Developer Token** | API 开发者令牌，需要申请 |

---

## 第二部分：源码级深度剖析

### 2.1 认证流程源码

```python
# google/ads/googleads/client.py
# Google Ads 认证流程

class GoogleAdsClient:
    """
    Google Ads API 客户端
    
    认证流程:
    1. 从配置文件加载凭据
    2. 构建 OAuth2 客户端
    3. 获取 access_token 和 refresh_token
    4. 维护令牌刷新机制
    
    关键文件:
    - google-ads.yaml: 配置文件
    - oauth2.json: OAuth2 凭据
    - refresh_token: 刷新令牌
    """
    
    def __init__(
        self,
        config: dict = None,
        oauth2: dict = None,
        login_customer_id: str = None,
        developer_token: str = None,
    ):
        self._oauth2_config = oauth2 or self._load_oauth2_config()
        self._login_customer_id = login_customer_id
        self._developer_token = developer_token
        
        # 令牌管理器
        self._token_manager = TokenManager(
            client_id=self._oauth2_config['client_id'],
            client_secret=self._oauth2_config['client_secret'],
            refresh_token=self._get_refresh_token()
        )
    
    def _load_oauth2_config(self) -> dict:
        """从配置文件加载 OAuth2 配置"""
        config_path = Path.home() / '.google' / 'api_config' / 'google-ads.yaml'
        if not config_path.exists():
            raise FileNotFoundError("google-ads.yaml not found")
        
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def get_access_token(self) -> str:
        """
        获取 access token
        
        流程:
        1. 检查是否有有效的 access token
        2. 如果有且未过期，直接返回
        3. 如果过期，使用 refresh token 刷新
        4. 返回新的 access token
        """
        token = self._token_manager.get_token()
        
        # 检查是否过期
        if token.expired:
            # 刷新 token
            token = self._token_manager.refresh_token()
        
        return token.token
    
    def get_access_token_for_customer(self, customer_id: str) -> str:
        """
        为特定客户获取 access token
        
        需要:
        - 用户已授权该 customer_id
        - 有 developer token
        - 是 customer 的 manager 或 admin
        """
        return self.get_access_token()
```

### 2.2 Token 管理器源码

```python
# google/ads/googleads/auth/token_manager.py
# Token 管理器

import requests
from datetime import datetime, timedelta
from typing import Optional

class TokenManager:
    """
    Token 管理器
    
    功能:
    ├── 管理 refresh_token
    ├── 获取/刷新 access_token
    ├── 缓存 token
    └── 处理 token 过期
    
    关键数据:
    - access_token: 有效期 1 小时
    - refresh_token: 长期有效
    - token_expiry: 过期时间
    """
    
    def __init__(self, client_id, client_secret, refresh_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.token_expiry = None
    
    def get_token(self) -> Token:
        """获取有效 token"""
        if self.access_token and self.token_expiry > datetime.now():
            return Token(self.access_token, self.token_expiry)
        
        # 需要刷新
        return self.refresh_token()
    
    def refresh_token(self) -> Token:
        """
        刷新 access token
        
        流程:
        1. 发送 POST 请求到 Google OAuth2 端点
        2. 提供 refresh_token 和 client 凭据
        3. Google 返回新的 access_token
        4. 缓存新 token
        """
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        
        data = response.json()
        
        self.access_token = data['access_token']
        # access_token 有效期 3600 秒（1 小时）
        self.token_expiry = datetime.now() + timedelta(seconds=data['expires_in'])
        
        return Token(self.access_token, self.token_expiry)
```

### 2.3 搜索查询执行源码

```python
# google/ads/googleads/services/google_ads_service.py
# Google Ads 搜索服务

class GoogleAdsService:
    """
    Google Ads 搜索服务
    
    核心方法:
    ├── search(): 同步查询
    ├── search_page(): 分页查询
    ├── search_paged(): 分页生成器
    └── stream_google_ads(): 流式查询
    
    支持查询:
    ├── SELECT 字段
    ├── FROM 表
    ├── WHERE 条件
    └── ORDER BY / LIMIT
    """
    
    def __init__(self, client, customer_id):
        self.client = client
        self.customer_id = customer_id
    
    def search(self, query: str):
        """
        执行搜索查询
        
        流程:
        1. 验证 query 语法
        2. 设置请求头（授权、customer_id）
        3. 发送 gRPC 请求
        4. 解析响应
        5. 返回行迭代器
        
        gRPC 请求:
        ├── search_request: {
        │   ├── customer_id: string
        │   ├── query: string (GAQL 语法)
        │   └── pagesize: int (可选)
        │}
        └── search_response: {
            ├── resource_name: string
            ├── campaign: Campaign
            ├── metrics: Metrics
            └── ...
        }
        """
        # 构建请求
        request = SearchGoogleAdsRequest(
            customer_id=str(self.customer_id),
            query=query,
            pagesize=1000
        )
        
        # 调用 gRPC
        response = self._stub.search(request=request)
        
        # 解析响应
        return self._parse_response(response)
    
    def _parse_response(self, response) -> Iterator[Row]:
        """解析 gRPC 响应"""
        for row in response.results:
            yield Row(row, response.column_spec)
    
    def search_paged(self, query: str, page_size: int = 1000) -> Iterator[Row]:
        """
        分页查询（推荐）
        
        优势:
        - 每次只拉一页
        - 自动处理分页
        - 内存友好
        
        注意:
        - Google Ads API 最大 page_size = 10000
        - 需要处理分页 token
        """
        request = SearchGoogleAdsRequest(
            customer_id=str(self.customer_id),
            query=query,
            pagesize=page_size
        )
        
        # gRPC streaming response
        for page in self._stub.search_paged(request=request):
            for row in page.results:
                yield Row(row, page.column_spec)
```

### 2.4 GAQL 查询语法源码

```python
# google/ads/googleads/gaql/query_builder.py
# GAQL 查询构建器

# GAQL = Google Ads Query Language

# 查询结构:
# SELECT fields FROM table WHERE conditions ORDER BY ... LIMIT ...

# 示例查询:
"""
SELECT
    campaign.name,
    campaign.status,
    campaign.bidding_strategy_type,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros,
    metrics.conversions
FROM campaign
WHERE
    segments.date >= '2026-01-01'
    AND segments.date <= '2026-01-31'
    AND campaign.status = ENABLED
    AND metrics.impressions > 1000
ORDER BY
    metrics.cost_micros DESC
LIMIT
    1000
"""

class QueryBuilder:
    """
    GAQL 查询构建器
    
    常用字段:
    ├── Campaign
    │   ├── name: 广告系列名称
    │   ├── status: 状态 (ENABLED/PAUSED/REMOVED)
    │   ├── bidding_strategy_type: 出价策略
    │   ├── advertising_channel_type: 广告类型
    │   └── customer_id: 客户 ID
    │
    ├── AdGroup
    │   ├── name: 广告组名称
    │   ├── status: 状态
    │   ├── cpc_bid_micros: CPC 出价
    │   └── campaign_id: 广告系列 ID
    │
    ├── Keyword
    │   ├── text: 关键词文本
    │   ├── match_type: 匹配类型 (EXACT/PHRASE/BROAD)
    │   └── ad_group_id: 广告组 ID
    │
    └── Metrics (常用指标)
        ├── impressions: 展示次数
        ├── clicks: 点击次数
        ├── cost_micros: 花费（微货币单位）
        ├── conversions: 转化次数
        ├── ctr: 点击率
        └── cpm: 千次展示成本
    """
    
    @staticmethod
    def build_campaign_report(
        customer_id: str,
        start_date: str,
        end_date: str,
        min_impressions: int = 0,
        limit: int = 10000,
    ) -> str:
        """
        构建广告系列报告查询
        
        参数:
        - customer_id: 客户 ID
        - start_date: 开始日期
        - end_date: 结束日期
        - min_impressions: 最小展示数
        - limit: 限制条数
        """
        query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.bidding_strategy_type,
            campaign.cpc_bid_ceiling_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversion_rate,
            metrics.average_cpc,
            metrics.cpm
        FROM campaign
        WHERE
            segments.date >= '{start_date}'
            AND segments.date <= '{end_date}'
            AND metrics.impressions >= {min_impressions}
        ORDER BY
            metrics.cost_micros DESC
        LIMIT {limit}
        """
        return query
```

### 2.5 速率限制源码

```python
# google/ads/googleads/helpers/rate_limiter.py
# 速率限制

from google.ads.googleads.enums import RateLimitSeverity

class GoogleAdsRateLimiter:
    """
    Google Ads API 速率限制
    
    限制规则:
    ├── 每秒请求限制: 取决于账号等级
    │   ├── 入门级: 60 请求/分钟
    │   ├── 标准级: 1000 请求/分钟
    │   └── 高级级: 无限
    │
    ├── 每日请求限制: 取决于 daily_budget
    │   └── daily_budget * 1000
    │
    └── 响应头:
        ├── google.ads.googleads.responses.per_minute_quota_remaining
        ├── google.ads.googleads.responses.per_minute_usage
        └── google.ads.googleads.responses.daily_quota_remaining
    
    处理策略:
    ├── 自动退避
    ├── 排队
    └── 重试
    """
    
    def __init__(self):
        self.request_count = 0
        self.time_window_start = time.time()
        self.requests_per_minute = 1000
    
    def check_and_wait(self):
        """
        检查速率限制并等待
        
        流程:
        1. 计算当前窗口内的请求数
        2. 如果超过限制，等待
        3. 重置窗口
        """
        elapsed = time.time() - self.time_window_start
        
        # 窗口过期（60 秒）
        if elapsed > 60:
            self.request_count = 0
            self.time_window_start = time.time()
        
        # 超过限制
        if self.request_count >= self.requests_per_minute:
            wait_time = 60 - elapsed
            time.sleep(wait_time)
            self.request_count = 0
            self.time_window_start = time.time()
        
        self.request_count += 1
    
    def handle_rate_limit_error(self, error):
        """
        处理速率限制错误
        
        状态码:
        ├── NOT_ENOUGH_PERMISSIONS: 权限不足
        └── DAILY_QUOTA_EXCEEDED: 日配额超限
        """
        if error.code == GoogleAdsError.RateLimitExceeded:
            # 等待后重试
            retry_after = int(error.details.retry_after)
            time.sleep(retry_after)
            return True
        
        return False
```

### 2.6 微货币单位转换源码

```python
# google/ads/googleads/utils/units.py
# 货币单位转换

# Google Ads 使用 micros（微单位）
# 1 micros = 0.000001 货币单位

# 转换:
# cost_micros = 12345678
# cost = cost_micros / 1000000 = 12.345678 元

class UnitConverter:
    """
    单位转换器
    
    Google Ads API 使用微单位:
    ├── 金额: micros (1 micros = 10^-6)
    ├── 数量: micros for percentages (1% = 10000 micros)
    └── 时间: micros for timestamps
    
    转换函数:
    ├── micro_to_float(): micros → float
    ├── float_to_micro(): float → micros
    └── format_currency(): 格式化金额
    """
    
    @staticmethod
    def micro_to_float(micros: int) -> float:
        """转换为浮点数"""
        return micros / 1000000.0
    
    @staticmethod
    def float_to_micro(value: float) -> int:
        """转换为 micros"""
        return int(value * 1000000)
    
    @staticmethod
    def format_currency(micros: int, currency: str = "CNY") -> str:
        """
        格式化货币
        
        示例:
        >>> UnitConverter.format_currency(12345678)
        '¥ 12.35'
        """
        value = UnitConverter.micro_to_float(micros)
        
        # 根据货币格式化
        if currency == "USD":
            return f"${value:.2f}"
        elif currency == "CNY":
            return f"¥ {value:.2f}"
        elif currency == "EUR":
            return f"€ {value:.2f}"
        else:
            return f"{value:.2f} {currency}"
```

---

## 第三部分：自测

### 问题 1
Google Ads API 的认证流程是什么？
<details>
<summary>查看答案</summary>

1. 从 google-ads.yaml 加载配置
2. 使用 refresh_token 获取 access_token
3. access_token 有效期 1 小时
4. 过期后使用 refresh_token 刷新
</details>

### 问题 2
GAQL 查询的基本结构是什么？
<details>
<summary>查看答案</summary>

SELECT fields FROM table WHERE conditions ORDER BY ... LIMIT ...
</details>

### 问题 3
micros 是什么？为什么使用它？
<details>
<summary>查看答案</summary>

micros = 微单位，1 micros = 10^-6
- 高精度表示金额
- 避免浮点数精度问题
- cost_micros / 1000000 = 实际金额
</details>

---

## 第四部分：动手验证

### 4.1 运行查询

```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage('google-ads.yaml')

query = """
SELECT
    campaign.name,
    metrics.impressions,
    metrics.clicks,
    metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
"""

customer_id = "YOUR_CUSTOMER_ID"
customer = client.get_service("Customer", customer_id)

for row in client.get_service("GoogleAdsService").search_paged(
    customer_id=customer_id,
    query=query
):
    print(f"广告系列: {row.campaign.name}")
    print(f"展示: {row.metrics.impressions}")
    print(f"点击: {row.metrics.clicks}")
    print(f"花费: {row.metrics.cost_micros / 1000000:.2f} 元")
```

### 4.2 创建广告系列

```python
from google.ads.googleads.resources.campaign import CampaignOperation

# 创建 CampaignOperation
campaign_operation = CampaignOperation()
campaign = campaign_operation.create

campaign.name = "测试广告系列"
campaign.advertising_channel_type = "SEARCH"
campaign.status = "PAUSED"

# 设置预算
budget = client.get_type("Budget").budget
budget.delivery_method = "STANDARD"
budget.amount_micros = 100000000  # 100 元

campaign.standard_upgrade_config = (
    client.get_type("StandardUpgradeConfig")
)
campaign.standard_upgrade_config.default_bid_amount_micros = 500000  # 0.5 元
campaign.standard_upgrade_config.budget = budget

# 执行创建
campaign_service = client.get_service("CampaignService")
result = campaign_service.mutate_campaigns(
    customer_id=customer_id,
    operations=[campaign_operation]
)
print(f"创建成功: {result.results[0].resource_name}")
```

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
