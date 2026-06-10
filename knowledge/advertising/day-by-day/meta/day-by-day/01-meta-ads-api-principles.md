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

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
