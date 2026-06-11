# Meta Ads API — 从入门到源码级

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 Meta Ads 是什么？

```
Meta Ads 是 Meta（Facebook + Instagram）的广告投放平台
用户可以在 Facebook、Instagram、Messenger、Audience Network 上投放广告

核心广告形式:
├─ Facebook Feed Ads (信息流广告)
├─ Instagram Feed Ads (Instagram 信息流)
├─ Stories Ads (Stories 广告)
├─ Reels Ads (Reels 短视频广告)
├─ Messenger Ads (消息广告)
├─ Audience Network Ads (受众网络)
└─ Marketplace Ads (市场广告)
```

### 1.2 为什么需要 Meta Ads API？

```
没有 API:
- 手动操作 Ads Manager
- 无法批量创建广告
- 无法自动优化广告
- 无法拉取数据做分析

有 API:
- 批量管理成千上万广告账户
- 自动创建和调整广告系列
- 拉取数据做归因分析
- 与内部系统打通
```

### 1.3 API 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│               Meta Ads API 架构                               │
│                                                              │
│  ┌──────────────┐                                          │
│  │  你的系统     │                                          │
│  │  (Client)    │                                          │
│  └──────┬───────┘                                          │
│         │ HTTPS REST API                                    │
│         ▼                                                   │
│  ┌────────────────────────────────────────────────────────┐│
│  │              Meta Graph API Server                      ││
│  │                                                        ││
│  │  ┌────────────────────────────────────────────────────┐││
│  │  │           Authentication                           │││
│  │  │           (OAuth2 + User Token / App Token)        │││
│  │  └────────────┬───────────────────────────────────────┘││
│  │               │                                        ││
│  │  ┌────────────▼───────────────────────────────────────┐││
│  │  │           GraphQL 查询层                             │││
│  │  │           (支持复杂查询和字段选择)                   │││
│  │  └────────────────────────────────────────────────────┘││
│  └────────────────────────────────────────────────────────┘│
│                                                              │
│  重要概念:                                                   │
│  ├── User Token: 代表广告账户管理员                        ││
│  ├── App Access Token: 代表应用                            ││
│  ├── Ad Account: 广告账户                                  ││
│  ├── Campaign: 广告系列                                    ││
│  ├── Ad Set: 广告组                                        ││
│  └── Ad: 广告                                              ││
└──────────────────────────────────────────────────────────────┘
```

### 1.4 快速体验

```python
# 1. 安装 Facebook SDK
# pip install facebook-sdk

import facebook

# 2. 获取 User Token
# 流程: 用户授权 → 获取 code → 交换 token
# 参考: https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/

ACCESS_TOKEN = "EAABwzLix1YBO...YOUR_TOKEN"
AD_ACCOUNT_ID = "act_your_ad_account_id"  # 以 act_ 开头

# 3. 获取广告数据
api = facebook.GraphAPI(ACCESS_TOKEN)

# 查询广告账户信息
account = api.get_object(
    f"{AD_ACCOUNT_ID}",
    fields="name,account_status,spend_cap"
)
print(f"账户: {account['name']}")
print(f"状态: {account['account_status']}")

# 查询广告系列
campaigns = api.get_connections(
    parent_id=AD_ACCOUNT_ID,
    connection_name="campaigns",
    fields="name,status,objective,budget_remaining"
)

for campaign in campaigns["data"]:
    print(f"系列: {campaign['name']}")
    print(f"  状态: {campaign['status']}")
    print(f"  目标: {campaign['objective']}")
```

### 1.5 关键概念速记

| 概念 | 说明 |
|------|------|
| **Access Token** | User Token（用户授权）或 App Access Token（应用级） |
| **User Token** | 代表广告账户管理员的访问令牌，需要用户授权 |
| **Ad Account ID** | 广告账户 ID（以 `act_` 开头） |
| **Campaign** | 广告系列（顶层） |
| **Ad Set** | 广告组（中间层） |
| **Ad** | 广告（最底层） |
| **Objective** | 广告目标（转化、流量、品牌认知等） |
| **Bid Amount** | 出价金额（单位：最小额货币） |
| **Graph API** | Meta 的 RESTful API 接口 |
| **App ID** | 应用 ID，用于创建 App Token |

---

## 第二部分：源码级深度剖析

### 2.1 认证流程源码

```python
# meta_ads/auth/oauth.py
# Meta OAuth2 认证流程

class MetaOAuthClient:
    """
    Meta OAuth2 认证客户端
    
    认证方式:
    ├── User Token: 代表用户（广告账户管理员）
    │   └─ 需要用户授权，有效期短（通常 60 天）
    └── App Access Token: 代表应用
        └─ 基于 App ID + App Secret，不会过期
    
    授权流程:
    1. 用户授权 → 获取 code
    2. 用 code 交换 access_token
    3. 使用 access_token 调用 API
    """
    
    AUTH_URL = "https://www.facebook.com/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    GRAPH_API_URL = "https://graph.facebook.com/v18.0"
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.refresh_token = None
    
    def generate_auth_url(self, redirect_uri: str, scope: str = "ads_management") -> str:
        """
        生成授权 URL
        
        参数:
        ├── redirect_uri: 回调 URL
        └── scope: 权限范围
        
        常用 scope:
        ├── ads_management: 广告管理
        ├── ads_read: 广告读取
        ├── pages_read_engagement: 页面互动读取
        └── instagram_basic: Instagram 基础访问
        """
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "response_type": "code",
        }
        
        return f"{self.AUTH_URL}?{self._urlencode(params)}"
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict:
        """
        用 code 换取 access_token
        
        流程:
        1. 用户点击授权 URL → 跳转到 redirect_uri
        2. redirect_uri 中包含 code 参数
        3. 用 code 交换 access_token
        """
        params = {
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        
        response = self._request("POST", self.TOKEN_URL, params=params)
        
        token_data = self._parse_response(response)
        
        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", "")
        
        return token_data
    
    def _long_lived_token(self, short_lived_token: str) -> dict:
        """
        将短期 token（60 天）转换为长期 token（2 年）
        
        流程:
        1. 使用短 token 请求长 token
        2. Meta 返回有效期 2 年的 token
        """
        params = {
            "grant_type": "fb_exchange_token",
            "fb_exchange_token": short_lived_token,
        }
        
        response = self._request("GET", self.TOKEN_URL, params=params)
        return self._parse_response(response)
    
    def refresh_token(self, refresh_token: str) -> dict:
        """
        刷新 access_token
        
        流程:
        1. 发送 POST 请求
        2. 传入 refresh_token
        3. 获取新的 access_token
        """
        params = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        response = self._request("POST", self.TOKEN_URL, params=params)
        return self._parse_response(response)
    
    def _request(self, method: str, url: str, params: dict = None) -> dict:
        """发送 HTTP 请求"""
        import requests
        
        response = requests.request(
            method, url, params=params,
            timeout=30
        )
        return response
    
    def _parse_response(self, response) -> dict:
        """解析响应"""
        import requests
        
        if not isinstance(response, dict):
            response = response.json()
        
        # 检查错误
        if "error" in response:
            raise MetaAdsAPIError(
                error_code=response["error"]["code"],
                message=response["error"]["message"],
            )
        
        return response


class MetaAdsAPIError(Exception):
    """Meta Ads API 错误"""
    
    ERROR_MESSAGES = {
        200: "权限被拒绝",
        201: "请求被拒绝（参数错误）",
        368: "用户取消了授权",
        400: "请求格式错误",
        401: "Token 无效",
        403: "权限不足",
        404: "资源不存在",
        405: "请求方法不允许",
        407: "IP 被禁用",
        408: "应用被禁用",
        409: "资源冲突",
        410: "资源已删除",
        411: "字段不存在",
        412: "参数无效",
        413: "应用未配置",
        414: "速率限制",
        415: "不支持的格式",
        416: "应用超过限制",
        417: "业务账户被禁用",
        418: "页面权限不足",
        419: "Instagram 账户权限不足",
        420: "用户被禁用",
        421: "广告账户被禁用",
        422: "字段类型错误",
        423: "广告组已存在",
        424: "广告已存在",
        425: "预算冲突",
        426: "频率限制",
        427: "广告系列状态错误",
        428: "广告组状态错误",
        429: "广告状态错误",
    }
    
    def __init__(self, error_code: int, message: str):
        self.error_code = error_code
        self.message = message
        self.display_message = self.ERROR_MESSAGES.get(error_code, message)
        super().__init__(f"[{error_code}] {self.display_message}")
```

### 2.2 Graph API 查询源码

```python
# meta_ads/client.py
# Meta Graph API 客户端

class MetaAdsClient:
    """
    Meta Ads API 客户端
    
    Graph API 基础 URL: https://graph.facebook.com/v18.0
    
    支持的版本:
    ├── v18.0: 当前推荐版本（2024）
    └── v17.0: 旧版本
    
    API 端点:
    ├── GET /{ad_account_id}: 获取广告账户信息
    ├── GET /{ad_account_id}/campaigns: 获取广告系列
    ├── GET /{ad_account_id}/adsets: 获取广告组
    ├── GET /{ad_account_id}/ads: 获取广告
    ├── POST /{ad_account_id}/campaigns: 创建广告系列
    ├── POST /{ad_account_id}/adsets: 创建广告组
    ├── POST /{ad_account_id}/ads: 创建广告
    └── GET /{ad_account_id}/insights: 获取洞察数据
    """
    
    GRAPH_API_URL = "https://graph.facebook.com/v18.0"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self._last_request_time = 0
        self._request_count = 0
        self._max_requests_per_minute = 10000
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        return {
            "Authorization": f"OAuth {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def get(self, path: str, fields: list = None, params: dict = None) -> dict:
        """
        GET 请求
        
        参数:
        ├── path: API 路径（如 "/act_123456/campaigns"）
        ├── fields: 要获取的字段列表
        └── params: 查询参数
        """
        import requests
        
        url = f"{self.GRAPH_API_URL}{path}"
        
        request_params = params or {}
        if fields:
            request_params["fields"] = ",".join(fields)
        
        response = requests.get(
            url,
            headers=self._get_headers(),
            params=request_params,
        )
        
        return self._handle_response(response)
    
    def post(self, path: str, data: dict = None) -> dict:
        """
        POST 请求（创建/更新）
        
        参数:
        └── data: 请求体
        """
        import requests
        
        url = f"{self.GRAPH_API_URL}{path}"
        
        response = requests.post(
            url,
            headers=self._get_headers(),
            json=data,
        )
        
        return self._handle_response(response)
    
    def get_insights(self, account_id: str, level: str = "ad",
                     time_range: dict = None, fields: list = None) -> dict:
        """
        获取洞察数据
        
        参数:
        ├── account_id: 广告账户 ID（act_123456）
        ├── level: 聚合级别（account/campaign/adset/ad）
        ├── time_range: 时间范围
        │   ├── since: 开始日期（YYYY-MM-DD）
        │   └── until: 结束日期（YYYY-MM-DD）
        └── fields: 要获取的指标字段
        
        常用字段:
        ├── impressions: 展示
        ├── clicks: 点击
        ├── spend: 花费
        ├── cpc: 平均 CPC
        ├── ctr: 点击率
        ├── conversions: 转化
        ├── cost_per_action_type: 每次行动费用
        ├── purchase_roas: 购买 ROAS
        └── value_per_ad_set: 每广告组价值
        """
        path = f"/act_{account_id}/insights"
        
        params = {"level": level}
        if time_range:
            if "since" in time_range:
                params["since"] = time_range["since"]
            if "until" in time_range:
                params["until"] = time_range["until"]
        if fields:
            params["access_token"] = self.access_token
        
        return self.get(path, fields=fields, params=params)
```

### 2.3 创建广告系列源码

```python
# meta_ads/campaign.py
# 广告系列 CRUD 操作

class CampaignBuilder:
    """
    广告系列构建器
    
    广告系列层级:
    ┌─────────────────────────────────────────────────────┐
    │                  Ad Account                          │
    │  ┌───────────────────────────────────────────────┐  │
    │  │  Campaign (广告系列)                           │  │
    │  │  - 广告目标 (objective)                       │  │
    │  │  - 预算                                        │  │
    │  │  ┌──────────────────────────────────────────┐ │  │
    │  │  │  Ad Set (广告组)                         │ │  │
    │  │  │  - 定向 (targeting)                      │ │  │
    │  │  │  - 预算 (budget)                         │ │  │
    │  │  │  - 排期 (schedule)                       │ │  │
    │  │  │  ┌─────────────────────────────────────┐│ │  │
    │  │  │  │  Ad (广告)                          ││ │  │
    │  │  │  │  - 创意 (creative)                  ││ │  │
    │  │  │  │  - 文案 (copy)                      ││ │  │
    │  │  │  │  - 链接 (url)                       ││ │  │
    │  │  │  └─────────────────────────────────────┘│ │  │
    │  │  └──────────────────────────────────────────┘ │  │
    │  └───────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────┘
    """
    
    OBJECTIVES = {
        "CONVERSIONS": "转化（最常见）",
        "TRAFFIC": "流量",
        "BRAND_AWARENESS": "品牌认知",
        "REACH": "触达",
        "VIDEO_VIEWS": "视频观看",
        "LEAD_GENERATION": "销售线索",
        "MESSAGES": "消息",
        "CATALOG_SALES": "商品目录销售",
        "APP_INSTALLS": "应用安装",
    }
    
    BUDGET_OPTIONS = {
        "DAILY": "日预算",
        "LIFETIME": "总预算（全周期）",
    }
    
    @classmethod
    def create_conversion_campaign(cls, client: MetaAdsClient, 
                                    account_id: str, 
                                    name: str,
                                    daily_budget_usd: float,
                                    objective: str = "CONVERSIONS") -> str:
        """
        创建转化目标广告系列
        
        流程:
        1. 设置广告目标
        2. 设置预算
        3. 设置优化目标
        4. 设置事件集
        5. 发送 POST 请求
        6. 返回广告系列 ID
        
        参数:
        ├── client: Meta Ads 客户端
        ├── account_id: 广告账户 ID（act_123456）
        ├── name: 广告系列名称
        ├── daily_budget_usd: 日预算
        └── objective: 广告目标
        """
        path = f"/act_{account_id}/campaigns"
        
        # 预算转换（Meta 使用最小额货币单位）
        budget_amount = int(daily_budget_usd * 100)  # 转换为分
        
        data = {
            "name": name,
            "objective": objective,
            "status": "PAUSED",  # 创建后先暂停
            "special_ad_categories": [],
            "daily_budget": budget_amount,
            "optimization_goal": "LINK_CLICKS",
            "billing_event": "IMPRESSIONS",
        }
        
        response = client.post(path, data=data)
        
        campaign_id = response["id"]
        return str(campaign_id)
    
    @classmethod
    def create_ad_set(cls, client: MetaAdsClient,
                      account_id: str,
                      campaign_id: str,
                      name: str,
                      daily_budget_usd: float,
                      targeting: dict = None,
                      start_date: str = None,
                      end_date: str = None) -> str:
        """
        创建广告组
        
        参数:
        ├── targeting: 定向条件
        │   ├── geo_locations: 地理位置
        │   │   ├── countries: 国家代码（如 "US", "CN"）
        │   │   └── regions: 地区
        │   ├── age_min, age_max: 年龄范围
        │   ├── genders: 性别（1=女性，2=男性）
        │   ├── interests: 兴趣标签
        │   └── behaviors: 行为标签
        └── 其他: 预算、排期等
        """
        path = f"/act_{account_id}/adsets"
        
        budget_amount = int(daily_budget_usd * 100)
        
        # 构建定向
        if targeting is None:
            targeting = {
                "geo_locations": {"countries": ["US"]},
                "age_min": 18,
                "age_max": 65,
                "genders": [1, 2],
            }
        
        data = {
            "name": name,
            "campaign_id": campaign_id,
            "status": "PAUSED",
            "daily_budget": budget_amount,
            "targeting": targeting,
            "bid_amount": 100,  # 1.00 USD（以分为单位）
        }
        
        if start_date:
            data["start_time"] = start_date
        if end_date:
            data["end_time"] = end_date
        
        response = client.post(path, data=data)
        
        return str(response["id"])
```

### 2.4 批量操作源码

```python
# meta_ads/batch.py
# 批量操作

class BatchRequest:
    """
    批量请求
    
    Meta API 支持批量操作，最多 50 个请求一组
    
    使用方式:
    1. 创建 BatchRequest 对象
    2. 添加多个请求
    3. 执行批量
    4. 处理响应
    
    优势:
    ├── 减少 HTTP 连接次数
    ├── 提高吞吐量
    └── 减少网络开销
    """
    
    def __init__(self, client: MetaAdsClient):
        self.client = client
        self._requests = []
        self._request_id = 0
    
    def add_get(self, path: str, fields: list = None, 
                params: dict = None, name: str = None) -> str:
        """
        添加 GET 请求
        
        参数:
        └── name: 请求的引用名称（用于获取响应）
        """
        request_id = name or f"req_{self._request_id}"
        self._request_id += 1
        
        self._requests.append({
            "method": "GET",
            "path": path,
            "fields": fields,
            "params": params,
            "name": request_id,
        })
        
        return request_id
    
    def add_post(self, path: str, data: dict = None, 
                 name: str = None) -> str:
        """添加 POST 请求"""
        request_id = name or f"req_{self._request_id}"
        self._request_id += 1
        
        self._requests.append({
            "method": "POST",
            "path": path,
            "data": data,
            "name": request_id,
        })
        
        return request_id
    
    def execute(self) -> dict:
        """
        执行批量请求
        
        返回:
        └── 以 name 为键的响应字典
        """
        import requests
        
        path = f"/?batch={self._requests}"
        
        # 构建 batch 数据
        batch_data = []
        for req in self._requests:
            batch_data.append(req)
        
        response = requests.post(
            f"{self.client.GRAPH_API_URL}{path}",
            headers=self.client._get_headers(),
            json=batch_data,
        )
        
        # 解析批量响应
        raw_response = response.json()
        results = {}
        
        for i, resp in enumerate(raw_response):
            request_id = self._requests[i].get("name")
            if "error" in resp:
                results[request_id] = {
                    "error": resp["error"]["message"],
                    "code": resp["error"].get("code"),
                }
            else:
                results[request_id] = resp
        
        return results


# 使用示例
client = MetaAdsClient("YOUR_ACCESS_TOKEN")
batch = BatchRequest(client)

# 添加多个请求
batch.add_get("/act_123456/campaigns", fields=["name", "status"], name="campaigns")
batch.add_get("/act_123456/adsets", fields=["name", "status"], name="adsets")
batch.add_get("/act_123456/ads", fields=["name", "status"], name="ads")

# 执行批量
results = batch.execute()

print(f"广告系列: {len(results['campaigns'])}")
print(f"广告组: {len(results['adsets'])}")
print(f"广告: {len(results['ads'])}")
```

---

## 第三部分：自测

### 问题 1
Meta Ads API 中，广告账户 ID 的格式是什么？
<details>
<summary>查看答案</summary>

- 格式：`act_` + 数字
- 示例：`act_1234567890`
</details>

### 问题 2
Graph API 的常用版本有哪些？
<details>
<summary>查看答案</summary>

- v18.0: 当前推荐版本（2024）
- v17.0: 旧版本
- 版本号格式：v{year}.{version}
</details>

### 问题 3
Meta Ads API 支持批量操作吗？最多多少个请求？
<details>
<summary>查看答案</summary>

- 支持批量操作
- 最多 50 个请求一组
</details>

---

## 第四部分：动手验证

### 4.1 获取广告数据

```python
from meta_ads.client import MetaAdsClient

client = MetaAdsClient("YOUR_ACCESS_TOKEN")

# 获取广告系列
campaigns = client.get(
    path="/act_123456/campaigns",
    fields=["name", "status", "objective"],
)

for campaign in campaigns.get("data", []):
    print(f"系列: {campaign['name']}")
    print(f"  状态: {campaign['status']}")
    print(f"  目标: {campaign['objective']}")
```

### 4.2 创建广告

```python
from meta_ads.campaign import CampaignBuilder

# 创建广告系列
campaign_id = CampaignBuilder.create_conversion_campaign(
    client=client,
    account_id="1234567890",
    name="测试广告系列",
    daily_budget_usd=50.0,
    objective="CONVERSIONS",
)

# 创建广告组
ad_set_id = CampaignBuilder.create_ad_set(
    client=client,
    account_id="1234567890",
    campaign_id=campaign_id,
    name="测试广告组",
    daily_budget_usd=50.0,
    targeting={
        "geo_locations": {"countries": ["US"]},
        "age_min": 18,
        "age_max": 35,
    }
)

print(f"创建的广告组 ID: {ad_set_id}")
```

### 5. Go 实现：Meta Ads Campaign 管理客户端

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// MetaAdsClient 封装 Meta Graph API 的认证、限流、批量请求
type MetaAdsClient struct {
	accessToken string
	baseURL     string
	httpClient  *http.Client
	mu          sync.Mutex
	lastCallAt  time.Time
	rateLimit   int // 每分钟最大请求数
}

// Campaign 广告系列资源模型
type Campaign struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Status    string    `json:"status"` // ACTIVE, PAUSED, DELETED
	Objective string    `json:"objective"`
	StartDate *time.Time `json:"start_time,omitempty"`
	EndDate   *time.Time `json:"end_time,omitempty"`
	DailyBudget int64   `json:"daily_budget,omitempty"` // 单位为分
	CreatedAt time.Time `json:"created_time"`
	UpdatedAt time.Time `json:"updated_time"`
}

// AdSet 广告组资源模型
type AdSet struct {
	ID           string    `json:"id"`
	Name         string    `json:"name"`
	Status       string    `json:"status"`
	CampaignID   string    `json:"campaign_id"`
	DailyBudget  int64     `json:"daily_budget"`
	StartDate    *time.Time `json:"start_time,omitempty"`
	EndDate      *time.Time `json:"end_time,omitempty"`
	Targeting    json.RawMessage `json:"targeting"` // 灵活 targeting 结构
	BidAmount    *int64    `json:"bid_info,omitempty"`
	CreatedAt    time.Time `json:"created_time"`
}

// Ad 广告资源模型
type Ad struct {
	ID         string    `json:"id"`
	Name       string    `json:"name"`
	Status     string    `json:"status"`
	AdSetID    string    `json:"ad_group_id"`
	CreativeID string    `json:"creative_id"`
	CreatedAt  time.Time `json:"created_time"`
}

// NewMetaAdsClient 创建客户端，默认 600 次/分钟限流
func NewMetaAdsClient(accessToken string) *MetaAdsClient {
	return &MetaAdsClient{
		accessToken: accessToken,
		baseURL:     "https://graph.facebook.com/v20.0",
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		rateLimit: 600,
	}
}

// getHeaders 返回带认证头的 HTTP 请求头
func (c *MetaAdsClient) getHeaders() http.Header {
	return http.Header{
		"Authorization":     {fmt.Sprintf("Bearer %s", c.accessToken)},
		"Content-Type":      {"application/json"},
		"User-Agent":        {"MetaAds-Go-SDK/1.0"},
	}
}

// RateLimitWait 限流等待：确保距上次请求至少间隔 rateLimit 毫秒
func (c *MetaAdsClient) RateLimitWait() {
	c.mu.Lock()
	defer c.mu.Unlock()
	minInterval := time.Minute / time.Duration(c.rateLimit)
	elapsed := time.Since(c.lastCallAt)
	if elapsed < minInterval {
		time.Sleep(minInterval - elapsed)
	}
	c.lastCallAt = time.Now()
}

// Get 执行 GET 请求，支持分页自动拉取
func (c *MetaAdsClient) Get(ctx context.Context, path string, fields []string) ([]json.RawMessage, error) {
	c.RateLimitWait()
	v := url.Values{}
	v.Set("fields", strings.Join(fields, ","))
	v.Set("access_token", c.accessToken)
	uri := fmt.Sprintf("%s%s?%s", c.baseURL, path, v.Encode())

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, uri, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header = c.getHeaders()

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("GET %s: %w", uri, err)
	}
	defer resp.Body.Close()

	var result map[string]json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	data, ok := result["data"]
	if !ok {
		return nil, fmt.Errorf("no data field in response")
	}

	// 递归拉取下一页
	nextURL, hasNext := result["paging"], false
	if nextMap, ok := result["paging"].(map[string]json.RawMessage); ok {
		if next, ok := nextMap["next"]; ok {
			var nextStr string
			json.Unmarshal(next, &nextStr)
			if nextStr != "" {
				hasNext = true
				nextURL = []byte(nextStr)
			}
		}
	}

	var records []json.RawMessage
	if err := json.Unmarshal(data, &records); err != nil {
		return nil, fmt.Errorf("unmarshal data: %w", err)
	}

	if hasNext {
		var nextStr string
		json.Unmarshal(nextURL, &nextStr)
		nextStr = strings.Trim(nextStr, `"`)
		// 解析下一页 URL
		parsed, _ := url.Parse(nextStr)
		nextPath := parsed.Path
		if nextQuery := parsed.RawQuery; nextQuery != "" {
			nextPath += "?" + nextQuery
		}
		// 分页只拉一次，避免递归过深
		if len(fields) > 0 {
			paged, err := c.Get(ctx, nextPath, fields)
			if err == nil {
				records = append(records, paged...)
			}
		}
	}

	return records, nil
}

// CampaignService 广告系列管理服务
type CampaignService struct {
	client *MetaAdsClient
}

func NewCampaignService(client *MetaAdsClient) *CampaignService {
	return &CampaignService{client: client}
}

// List 列出指定广告账户下所有广告系列
func (s *CampaignService) List(ctx context.Context, accountID string) ([]Campaign, error) {
	path := fmt.Sprintf("/act_%s/campaigns", accountID)
	records, err := s.client.Get(ctx, path, []string{
		"id", "name", "status", "objective",
		"start_time", "end_time", "daily_budget",
		"created_time", "updated_time",
	})
	if err != nil {
		return nil, err
	}
	var campaigns []Campaign
	for _, r := range records {
		var c Campaign
		if err := json.Unmarshal(r, &c); err != nil {
			return nil, fmt.Errorf("unmarshal campaign %s: %w", string(r[:min(20, len(r))]), err)
		}
		campaigns = append(campaigns, c)
	}
	return campaigns, nil
}

// Create 创建广告系列
func (s *CampaignService) Create(ctx context.Context, accountID string, params map[string]interface{}) (*Campaign, error) {
	s.client.RateLimitWait()
	data, _ := json.Marshal(params)
	params["access_token"] = s.client.accessToken

	uri := fmt.Sprintf("%s/act_%s/campaigns", s.client.baseURL, accountID)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, uri, strings.NewReader(string(data)))
	if err != nil {
		return nil, err
	}
	req.Header = s.client.getHeaders()

	resp, err := s.client.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result struct {
		ID string `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return &Campaign{ID: result.ID}, nil
}

// AdSetService 广告组管理服务
type AdSetService struct {
	client *MetaAdsClient
}

func NewAdSetService(client *MetaAdsClient) *AdSetService {
	return &AdSetService{client: client}
}

// Create 创建广告组
func (s *AdSetService) Create(ctx context.Context, accountID, campaignID string, params map[string]interface{}) (*AdSet, error) {
	s.client.RateLimitWait()
	params["campaign_id"] = campaignID
	data, _ := json.Marshal(params)
	params["access_token"] = s.client.accessToken

	uri := fmt.Sprintf("%s/act_%s/adsets", s.client.baseURL, accountID)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, uri, strings.NewReader(string(data)))
	if err != nil {
		return nil, err
	}
	req.Header = s.client.getHeaders()

	resp, err := s.client.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result struct {
		ID string `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return &AdSet{ID: result.ID}, nil
}

// BatchService 批量请求服务：合并多个 API 调用到一个 HTTP 请求
type BatchService struct {
	client *MetaAdsClient
	batches []batchEntry
}

type batchEntry struct {
	method       string
	path         string
	body         string
	params       url.Values
	resultName   string // e.g. "create_campaign"
}

func NewBatchService(client *MetaAdsClient) *BatchService {
	return &BatchService{client: client}
}

// Add 添加一个批量请求
func (b *BatchService) Add(method, path, resultName string, params url.Values, body string) {
	b.batches = append(b.batches, batchEntry{
		method:     method,
		path:       path,
		body:       body,
		params:     params,
		resultName: resultName,
	})
}

// Execute 执行批量请求
func (b *BatchService) Execute(ctx context.Context) ([]map[string]any, error) {
	if len(b.batches) == 0 {
		return nil, nil
	}
	b.client.RateLimitWait()

	var requests []map[string]any
	for _, entry := range b.batches {
		req := map[string]any{
			"method": entry.method,
			"relative_url": entry.path,
		}
		if entry.body != "" {
			req["body"] = entry.body
		} else if entry.params != nil {
			req["body"] = entry.params.Encode()
		}
		if entry.resultName != "" {
			req["name"] = entry.resultName
		}
		requests = append(requests, req)
	}

	data, _ := json.Marshal(requests)
	uri := fmt.Sprintf("%s", b.client.baseURL)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, uri, strings.NewReader(string(data)))
	if err != nil {
		return nil, err
	}
	req.Header = b.client.getHeaders()
	req.URL.Path += "/batch"
	req.URL.RawQuery = url.Values{"access_token": {b.client.accessToken}}.Encode()

	resp, err := b.client.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var results []map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&results); err != nil {
		return nil, err
	}
	return results, nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func main() {
	client := NewMetaAdsClient("YOUR_ACCESS_TOKEN")
	campaignSvc := NewCampaignService(client)
	adSetSvc := NewAdSetService(client)

	ctx := context.Background()

	// 列出广告系列
	campaigns, err := campaignSvc.List(ctx, "YOUR_AD_ACCOUNT_ID")
	if err != nil {
		fmt.Printf("error: %v\n", err)
		return
	}
	for _, c := range campaigns {
		fmt.Printf("Campaign: %s [%s] budget=%d\n", c.Name, c.Status, c.DailyBudget)
	}

	// 创建广告系列
	newCampaign, err := campaignSvc.Create(ctx, "YOUR_AD_ACCOUNT_ID", map[string]interface{}{
		"name":         "My Campaign",
		"objective":    "CONVERSIONS",
		"status":       "ACTIVE",
		"daily_budget": 5000, // 50 USD in cents
	})
	if err != nil {
		fmt.Printf("create campaign error: %v\n", err)
		return
	}
	fmt.Printf("Created campaign: %s\n", newCampaign.ID)

	// 使用批量 API
	batchSvc := NewBatchService(client)
	batchSvc.Add(
		"GET", "act_YOUR_AD_ACCOUNT_ID/campaigns?fields=name,status,daily_budget",
		"list_campaigns", nil, "",
	)
	batchSvc.Add(
		"GET", "act_YOUR_AD_ACCOUNT_ID/adsets?fields=name,status",
		"list_adsets", nil, "",
	)
	results, err := batchSvc.Execute(ctx)
	if err != nil {
		fmt.Printf("batch error: %v\n", err)
	} else {
		for _, r := range results {
			for _, r := range results {
				fmt.Printf("batch result: %v\n", r)
			}
			}
			```

			### Meta Ads API 的 Go 实现（生产级）

			```go
			// Meta Ads API: Go 语言生产级 SDK 实现
			// 覆盖 OAuth 认证、端点调用、批量操作、速率限制
			package metaads

			import (
			"encoding/json"
			"fmt"
			"net/http"
			"strings"
			"sync"
			"time"
			)

			// ==================== OAuth 认证 ====================

			// MetaAdsClient 完整的 Meta Ads API 客户端
			type MetaAdsClient struct {
			AppID         string
			AppSecret     string
			AccessToken   string
			APIVersion    string // 如 "v21.0"
			BaseURL       string
			httpClient    *http.Client
			tokenMux      sync.Mutex // token 并发保护
			lastTokenTime time.Time
			}

			// NewMetaAdsClient 创建客户端
			func NewMetaAdsClient(appID, appSecret, accessToken string) *MetaAdsClient {
			return &MetaAdsClient{
				AppID:       appID,
				AppSecret:   appSecret,
				AccessToken: accessToken,
				APIVersion:  "v21.0",
				BaseURL:     "https://graph.facebook.com",
				httpClient: &http.Client{
					Timeout: 30 * time.Second,
				},
			}
			}

			// ExchangeCode 用 authorization code 换 access_token
			func (c *MetaAdsClient) ExchangeCode(code, redirectURI string) (tokenResp, error) {
			params := url.Values{}
			params.Set("client_id", c.AppID)
			params.Set("client_secret", c.AppSecret)
			params.Set("code", code)
			params.Set("redirect_uri", redirectURI)
			params.Set("grant_type", "authorization_code")

			resp, err := c.post("/oauth/access_token", params)
			if err != nil {
				return tokenResp{}, err
			}
			return parseTokenResponse(resp)
			}

			// ShortToLongToken 短期 token → 长期 token（60 天 → 2 年）
			func (c *MetaAdsClient) ShortToLongToken(shortToken string) (tokenResp, error) {
			params := url.Values{}
			params.Set("grant_type", "fb_exchange_token")
			params.Set("fb_exchange_token", shortToken)

			resp, err := c.get("/oauth/access_token", params)
			if err != nil {
				return tokenResp{}, err
			}
			return parseTokenResponse(resp)
			}

			// RefreshToken 刷新 access_token
			func (c *MetaAdsClient) RefreshToken(refreshToken string) (tokenResp, error) {
			params := url.Values{}
			params.Set("grant_type", "refresh_token")
			params.Set("refresh_token", refreshToken)

			resp, err := c.post("/oauth/access_token", params)
			if err != nil {
				return tokenResp{}, err
			}
			return parseTokenResponse(resp)
			}

			// ==================== 核心端点 ====================

			// Campaign 广告系列
			type Campaign struct {
			ID            string  `json:"id"`
			Name          string  `json:"name"`
			Status        string  `json:"status"` // ACTIVE, PAUSED, ARCHIVED
			BudgetAmount   *int64  `json:"daily_budget,omitempty"`
			BidAmount      *int64  `json:"promoted_object,omitempty"`
			AdvertisingType string `json:"advertising_type,omitempty"`
			}

			// AdSet 广告组
			type AdSet struct {
			ID            string  `json:"id"`
			Name          string  `json:"name"`
			Status        string  `json:"status"`
			DayParts       []int   `json:"dayparts,omitempty"`
			BidAmount      *int64  `json:"bid_amount,omitempty"`
			Targeting      *Target `json:"targeting,omitempty"`
			}

			// Target 定向条件
			type Target struct {
			GEOLocations *GEO `json:"geo_locations,omitempty"`
			Ages         []int `json:"ages,omitempty"`
			Genders      []int `json:"genders,omitempty"`
			}

			// GEO 地理位置
			type GEO struct {
			Countries    []string `json:"countries,omitempty"`
			Cities       []string `json:"cities,omitempty"`
			Radius       int      `json:"radius,omitempty"`
			}

			// Ad 广告
			type Ad struct {
			ID        string   `json:"id"`
			Name      string   `json:"name"`
			Status    string   `json:"status"`
			Body      string   `json:"body,omitempty"`
			Title     string   `json:"title,omitempty"`
			ImageURLs []string `json:"attachment,omitempty"`
			}

			// CampaignResp 广告系列列表响应
			type CampaignResp struct {
			Data  []Campaign       `json:"data"`
			Paging *Paging         `json:"paging,omitempty"`
			}

			// Paging 分页信息
			type Paging struct {
			Cursor string `json:"cursors,omitempty"`
			Next   string `json:"next,omitempty"`
			}

			// GetCampaigns 获取广告系列列表
			func (c *MetaAdsClient) GetCampaigns(adAccountId string, fields []string) ([]Campaign, error) {
			path := fmt.Sprintf("/%s/%s/campaigns", c.APIVersion, adAccountId)
			params := url.Values{}
			params.Set("fields", strings.Join(fields, ","))
			params.Set("access_token", c.AccessToken)

			resp, err := c.get(path, params)
			if err != nil {
				return nil, err
			}

			var result CampaignResp
			if err := json.Unmarshal(resp, &result); err != nil {
				return nil, fmt.Errorf("parse campaigns: %w", err)
			}
			return result.Data, nil
			}

			// GetCampaignInsights 获取广告系列洞察数据
			func (c *MetaAdsClient) GetCampaignInsights(
			adAccountId string,
			ids []string,
			metrics []string,
			timeRange map[string]string,
			) ([]map[string]interface{}, error) {
			path := fmt.Sprintf("/%s/%s/insights", c.APIVersion, adAccountId)
			params := url.Values{}
			params.Set("ids", strings.Join(ids, ","))
			params.Set("metrics", strings.Join(metrics, ","))
			if start, ok := timeRange["start_date"]; ok {
				params.Set("time_range[start_date]", start)
			}
			if end, ok := timeRange["end_date"]; ok {
				params.Set("time_range[end_date]", end)
			}
			params.Set("access_token", c.AccessToken)

			resp, err := c.get(path, params)
			if err != nil {
				return nil, err
			}

			var result struct {
				Data []map[string]interface{} `json:"data"`
			}
			if err := json.Unmarshal(resp, &result); err != nil {
				return nil, fmt.Errorf("parse insights: %w", err)
			}
			return result.Data, nil
			}

			// ==================== 批量操作 ====================

			// BatchRequest 批量请求
			type BatchRequest struct {
			Method   string            `json:"method"`
			Path     string            `json:"path"`
			Body     map[string]string `json:"body,omitempty"`
			Headers  map[string]string `json:"headers,omitempty"`
			}

			// BatchResponse 批量响应
			type BatchResponse struct {
			Status  int               `json:"status"`
			Body    json.RawMessage   `json:"body"`
			Headers map[string]string `json:"headers"`
			}

			// ExecuteBatch 执行批量操作（一次 HTTP 完成多个 API 调用）
			func (c *MetaAdsClient) ExecuteBatch(
			adAccountId string,
			reqs []BatchRequest,
			) ([]BatchResponse, error) {
			if len(reqs) == 0 {
				return nil, nil
			}
			if len(reqs) > 50 {
				reqs = reqs[:50] // Meta 限制每批最多 50 个
			}

			path := fmt.Sprintf("/%s/%s/batch", c.APIVersion, adAccountId)
			params := url.Values{}
			bodyJSON, _ := json.Marshal(reqs)
			params.Set("requests", string(bodyJSON))
			params.Set("access_token", c.AccessToken)

			resp, err := c.post(path, params)
			if err != nil {
				return nil, err
			}

			var result []BatchResponse
			if err := json.Unmarshal(resp, &result); err != nil {
				return nil, fmt.Errorf("parse batch response: %w", err)
			}
			return result, nil
			}

			// ==================== 速率限制 ====================

			// RateLimiter 基于 Graph API Rate Limit 的实现
			type RateLimiter struct {
			maxCallsPerHour int
			callCount       int
			windowStart     time.Time
			mu              sync.Mutex
			}

			// NewRateLimiter 创建限流器（默认 200 calls/hour）
			func NewRateLimiter(maxCallsPerHour int) *RateLimiter {
			if maxCallsPerHour == 0 {
				maxCallsPerHour = 200 // Graph API 默认限制
			}
			return &RateLimiter{
				maxCallsPerHour: maxCallsPerHour,
				windowStart:     time.Now(),
			}
			}

			// Wait 等待直到可以发送请求
			func (rl *RateLimiter) Wait() {
			rl.mu.Lock()
			defer rl.mu.Unlock()

			now := time.Now()
			if now.Sub(rl.windowStart) > time.Hour {
				rl.windowStart = now
				rl.callCount = 0
			}

			if rl.callCount >= rl.maxCallsPerHour {
				// 等待窗口结束
				deadline := rl.windowStart.Add(time.Hour)
				time.Sleep(time.Until(deadline))
				rl.windowStart = time.Now()
				rl.callCount = 0
			}
			rl.callCount++
			}

			// ==================== 错误处理 ====================

			// MetaAdsAPIError API 错误
			type MetaAdsAPIError struct {
			Code      int    `json:"code"`
			Message   string `json:"message"`
			Type      string `json:"type"`
			FBTraceID string `json:"fbtrace_id,omitempty"`
			}

			func (e *MetaAdsAPIError) Error() string {
			return fmt.Sprintf("Meta Ads API error [%d]: %s (type: %s, trace: %s)",
				e.Code, e.Message, e.Type, e.FBTraceID)
			}

			// ==================== 内部方法 ====================

			type tokenResp struct {
			AccessToken  string `json:"access_token"`
			ExpiresIn    int    `json:"expires_in"`
			RefreshToken string `json:"refresh_token"`
			}

			func parseTokenResponse(data json.RawMessage) (tokenResp, error) {
			var resp tokenResp
			err := json.Unmarshal(data, &resp)
			return resp, err
			}

			func (c *MetaAdsClient) get(path string, params url.Values) (json.RawMessage, error) {
			url := c.BaseURL + path + "?" + params.Encode()
			resp, err := c.httpClient.Get(url)
			if err != nil {
				return nil, err
			}
			defer resp.Body.Close()

			var result json.RawMessage
			if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
				return nil, err
			}

			var errorCheck struct {
				Error struct {
					Code    int    `json:"code"`
					Message string `json:"message"`
				} `json:"error"`
			}
			if err := json.Unmarshal(result, &errorCheck); err == nil {
				if errorCheck.Error.Code != 0 {
					return nil, &MetaAdsAPIError{
						Code:    errorCheck.Error.Code,
						Message: errorCheck.Error.Message,
						Type:    "OAuthException",
					}
				}
			}
			return result, nil
			}

			func (c *MetaAdsClient) post(path string, params url.Values) (json.RawMessage, error) {
			url := c.BaseURL + path
			resp, err := c.httpClient.PostForm(url, params)
			if err != nil {
				return nil, err
			}
			defer resp.Body.Close()

			var result json.RawMessage
			if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
				return nil, err
			}
			return result, nil
			}

			// ==================== 使用示例 ====================

			func main() {
			// 1. 创建客户端
			client := NewMetaAdsClient(
				"your_app_id",
				"your_app_secret",
				"EAABwzLixnjYBO7...",
			)

			// 2. 限流器
			limiter := NewRateLimiter(200)

			// 3. 获取广告系列
			limiter.Wait()
			campaigns, err := client.GetCampaigns(
				"act_123456789",
				[]string{"id", "name", "status", "daily_budget", "created_time"},
			)
			if err != nil {
				fmt.Printf("error: %v\n", err)
				return
			}
			for _, c := range campaigns {
				fmt.Printf("Campaign: %s - %s (%s)\n", c.ID, c.Name, c.Status)
			}

			// 4. 批量操作：创建 Campaign + AdSet + Ad
			batchReqs := []BatchRequest{
				{
					Method: "POST",
					Path:   "/act_123456789/campaigns",
					Body: map[string]string{
						"name":               "Summer Sale Campaign",
						"objective":          "OUTCOME_RESULTS",
						"status":             "PAUSED",
						"daily_budget":       "5000",
					},
				},
				{
					Method: "POST",
					Path:   "/act_123456789/adset",
					Body: map[string]string{
						"name":       "Prospecting AdSet",
						"campaign_id":  "[response:0.id]", // 引用上一步结果
						"status":     "PAUSED",
						"daily_budget": "2000",
					},
				},
			}
			results, err := client.ExecuteBatch("act_123456789", batchReqs)
			for _, r := range results {
				fmt.Printf("Batch result: status=%d\n", r.Status)
			}
			}
			```

			---

			*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
			*答不出自测题？回去重读对应章节。*
