# TikTok Ads API — 从入门到源码级

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 TikTok Ads 是什么？

```
TikTok Ads 是 TikTok 的广告投放平台
用户可以在 TikTok 应用内投放广告

核心广告形式:
├─ In-Feed Ads (信息流广告 - 类似抖音)
├─ TopView Ads (置顶广告)
├─ Brand Takeover Ads (品牌接管广告)
├─ Spark Ads (原生广告 - 使用有机视频)
├─ Collection Ads (合集广告)
└─ Branded Effects (品牌特效)
```

### 1.2 为什么需要 API？

```
没有 API:
- 手动操作 TikTok Ads Manager
- 无法批量创建广告
- 无法自动优化

有 API:
- 批量管理广告账户
- 自动创建和调整广告
- 拉取数据进行分析
```

### 1.3 API 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│               TikTok Ads API 架构                            │
│                                                              │
│  ┌──────────────┐                                          │
│  │  你的系统     │                                          │
│  │  (Client)    │                                          │
│  └──────┬───────┘                                          │
│         │ HTTPS REST API                                    │
│         ▼                                                   │
│  ┌────────────────────────────────────────────────────────┐│
│  │              TikTok Ads API Server                      ││
│  │                                                        ││
│  │  ┌────────────────────────────────────────────────────┐││
│  │  │           Authentication                           │││
│  │  │           (OAuth2)                                 │││
│  │  └────────────┬───────────────────────────────────────┘││
│  │               │                                        ││
│  │  ┌────────────▼───────────────────────────────────────┐││
│  │  │           业务逻辑层                                 │││
│  │  │           Ad Account, Campaign, Ad, Creative...    │││
│  │  └────────────────────────────────────────────────────┘││
│  └────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 快速体验

```python
# 1. 安装 TikTok Ads API SDK
pip install tiktok-api

# 2. Python 示例
from tiktok_ads.tiktok_client import TiktokClient

client = TiktokClient(
    access_token='YOUR_ACCESS_TOKEN',
    advertiser_id='YOUR_ADVERTISER_ID',
)

# 查询广告账户
response = client.get(
    path='/ad-accounts',
    params={'page': 1, 'page_size': 10}
)

for account in response.get('data', {}).get('list', []):
    print(f"账户: {account['name']}")
    print(f"ID: {account['id']}")
    print(f"状态: {account['status']}")
```

### 1.5 关键概念速记

| 概念 | 说明 |
|------|------|
| **Access Token** | API 访问令牌，有效期 24 小时 |
| **Advertiser ID** | 广告账户 ID |
| **Campaign** | 广告系列 |
| **Ad Group** | 广告组 |
| **Ad** | 广告素材 |
| **Creative** | 创意素材 |

---

## 第二部分：源码级深度剖析

### 2.1 认证流程源码

```python
# tiktok_ads/auth/oauth.py
# TikTok OAuth 认证

class TikTokOAuthClient:
    """
    TikTok OAuth 认证客户端
    
    认证流程:
    1. 用户授权
    2. 获取 code
    3. 用 code 换 access_token 和 refresh_token
    4. 使用 refresh_token 刷新 access_token
    
    关键数据:
    ├── access_token: 有效期 24 小时
    ├── refresh_token: 有效期 30 天
    ├── token_type: Bearer
    └── scope: 权限范围
    """
    
    TOKEN_URL='https://business-api.tiktok.com/portal/login'
    AUTH_URL='https://business-api.tiktok.com/portal/'
    
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
    
    def generate_auth_url(self, redirect_uri, state=None):
        """生成授权 URL"""
        params = {
            'client_key': self.app_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'user.info.basic,advertiser.read',
            'state': state or 'random_state',
        }
        
        return f"{self.AUTH_URL}?{urlencode(params)}"
    
    def exchange_code_for_token(self, code, redirect_uri):
        """用 code 换取 access_token"""
        data = {
            'client_key': self.app_id,
            'client_secret': self.app_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }
        
        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        self.access_token = token_data['access_token']
        self.refresh_token = token_data['refresh_token']
        self.token_expiry = time.time() + token_data['expires_in']
        
        return token_data
    
    def refresh_token(self):
        """刷新 access_token"""
        data = {
            'client_key': self.app_id,
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
        }
        
        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        self.access_token = token_data['access_token']
        self.refresh_token = token_data.get('refresh_token', self.refresh_token)
        self.token_expiry = time.time() + token_data['expires_in']
        
        return token_data
```

### 2.2 请求执行源码

```python
# tiktok_ads/client.py
# TikTok API 客户端

class TiktokClient:
    """
    TikTok Ads API 客户端
    
    支持的操作:
    ├── GET: 查询数据
    ├── POST: 创建资源
    ├── PUT: 更新资源
    └── DELETE: 删除资源
    
    支持的资源:
    ├── /ad-accounts: 广告账户
    ├── /campaigns: 广告系列
    ├── /ad-groups: 广告组
    ├── /ads: 广告
    ├── /creatives: 创意素材
    └── /reports: 报表数据
    """
    
    BASE_URL = 'https://business-api.tiktok.com/portal/api/v2'
    
    def __init__(self, access_token, advertiser_id):
        self.access_token = access_token
        self.advertiser_id = advertiser_id
        self._last_request_time = 0
    
    def _get_headers(self):
        """获取请求头"""
        return {
            'Access-Token': self.access_token,
            'Content-Type': 'application/json',
            'X-Biz': 'tt-adm-api',
        }
    
    def get(self, path, params=None):
        """GET 请求"""
        url = f"{self.BASE_URL}{path}"
        response = requests.get(
            url,
            headers=self._get_headers(),
            params=params,
        )
        return self._handle_response(response)
    
    def post(self, path, data=None):
        """POST 请求"""
        url = f"{self.BASE_URL}{path}"
        response = requests.post(
            url,
            headers=self._get_headers(),
            json=data,
        )
        return self._handle_response(response)
    
    def _handle_response(self, response):
        """处理响应"""
        if response.status_code != 200:
            raise TikTokAPIError(f"HTTP {response.status_code}")
        
        data = response.json()
        
        # 检查业务错误
        if data.get('code') != 0:
            error_code = data.get('code')
            error_message = data.get('message', '')
            raise TikTokAPIError(f"Error {error_code}: {error_message}")
        
        return data.get('data', {})
```

### 2.3 广告账户查询源码

```python
# tiktok_ads/ad_account.py
# 广告账户操作

class AdAccount:
    """广告账户操作"""
    
    def __init__(self, client):
        self.client = client
    
    def list(self, status=None, page=1, page_size=10):
        """列出广告账户"""
        params = {'page': page, 'page_size': page_size}
        if status:
            params['status'] = status
        
        return self.client.get('/ad-accounts', params=params)
    
    def create(self, name, currency, time_zone):
        """创建广告账户"""
        data = {
            'advertiser_name': name,
            'currency': currency,
            'timezone_id': time_zone,
        }
        
        return self.client.post('/advertisers', data=data)
    
    def get_insights(self, advertiser_id, date_preset=None, date_start=None, date_end=None, breakdowns=None, stats_type='ALL'):
        """获取广告数据"""
        data = {
            'advertiser_ids': [advertiser_id],
            'report_type': 'CAMPAIGN_AD_GROUP_AD',
            'stats_type': stats_type,
        }
        
        if date_preset:
            data['date_preset'] = date_preset
        elif date_start and date_end:
            data['date_start'] = date_start
            data['date_end'] = date_end
        
        if breakdowns:
            data['breakdowns'] = breakdowns
        
        return self.client.post('/reports/insights', data=data)
```

### 2.4 数据查询源码

```python
# tiktok_ads/reports.py
# 报表数据查询

class ReportClient:
    """报表数据查询"""
    
    def get_campaign_insights(self, advertiser_id, start_date, end_date,
                              metrics=['impressions', 'clicks', 'cost'],
                              breakdowns=['day']):
        """获取广告系列数据"""
        data = {
            'advertiser_ids': [advertiser_id],
            'report_name': 'campaign_insights',
            'date_preset': 'CUSTOM',
            'date_start': start_date,
            'date_end': end_date,
            'metrics': metrics,
            'breakdowns': breakdowns,
            'page': 1,
            'page_size': 50,
        }
        
        response = self.client.post('/reports/insights', data=data)
        
        # 处理分页
        all_data = response.get('insights', [])
        page = 2
        while response.get('has_more', False):
            data['page'] = page
            response = self.client.post('/reports/insights', data=data)
            all_data.extend(response.get('insights', []))
            page += 1
        
        return all_data
```

### 2.5 错误处理源码

```python
# tiktok_ads/exceptions.py
# 错误处理

class TikTokAPIError(Exception):
    """TikTok API 错误
    
    常见错误码:
    ├── 62201: 权限不足
    ├── 62202: Token 无效或过期
    ├── 62203: 签名错误
    ├── 62204: 参数错误
    ├── 62205: 余额不足
    └── 62206: 频率限制
    """
    
    ERROR_MESSAGES = {
        62201: "权限不足",
        62202: "Token 无效或过期",
        62203: "签名错误",
        62204: "参数错误",
        62205: "余额不足",
        62206: "频率限制",
    }
    
    def __init__(self, message, error_code=None):
        self.error_code = error_code
        self.message = message
        super().__init__(message)
    
    def handle_error(self):
        """错误处理"""
        if self.error_code == 62202:  # Token 过期
            return 'refresh_token'
        elif self.error_code == 62206:  # 频率限制
            return 'retry'
        elif self.error_code == 62201:  # 权限不足
            return 'permission_error'
        elif self.error_code == 62204:  # 参数错误
            return 'parameter_error'
        
        return False
```

### 2.6 速率限制源码

```python
# tiktok_ads/ratelimit.py
# 速率限制

class TikTokRateLimiter:
    """
    TikTok 速率限制器
    
    限制规则:
    ├── 每个 advertiser 每分钟 30 次请求
    ├── 超过限制返回 62206 错误
    └── 需要指数退避
    """
    
    def __init__(self, max_requests_per_minute=30):
        self.max_requests = max_requests_per_minute
        self.request_count = 0
        self.window_start = time.time()
    
    def check(self):
        """检查速率限制"""
        elapsed = time.time() - self.window_start
        
        if elapsed > 60:
            self.request_count = 0
            self.window_start = time.time()
        
        if self.request_count >= self.max_requests:
            wait_time = 60 - elapsed
            time.sleep(wait_time)
            self.request_count = 0
            self.window_start = time.time()
        
        self.request_count += 1
    
    def handle_rate_limit(self, error_code):
        """处理速率限制错误"""
        if error_code == 62206:
            wait_time = 2 ** (self.request_count % 4)  # 指数退避
            time.sleep(wait_time)
            return True
        return False
```

---

## 第三部分：自测

### 问题 1
TikTok Ads API 的 access_token 有效期多久？
<details>
<summary>查看答案</summary>

- access_token: 24 小时
- refresh_token: 30 天
</details>

### 问题 2
常见错误码 62206 是什么意思？
<details>
<summary>查看答案</summary>

- 错误码 62206: 频率限制
- 处理: 指数退避，等待后重试
</details>

### 问题 3
TikTok Ads 支持的广告形式有哪些？
<details>
<summary>查看答案</summary>

- In-Feed Ads (信息流广告)
- TopView Ads (置顶广告)
- Spark Ads (原生广告)
- Collection Ads (合集广告)
- Branded Effects (品牌特效)
</details>

---

## 第四部分：动手验证

### 4.1 查询广告账户

```python
from tiktok_ads.tiktok_client import TiktokClient

client = TiktokClient(
    access_token='YOUR_ACCESS_TOKEN',
    advertiser_id='YOUR_ADVERTISER_ID',
)

# 查询广告账户
accounts = client.get(
    path='/ad-accounts',
    params={'page': 1, 'page_size': 10}
)

for account in accounts.get('list', []):
    print(f"账户: {account['name']}")
    print(f"ID: {account['id']}")
    print(f"状态: {account['status']}")
```

### 4.2 获取广告数据

```python
# 获取广告数据
insights = client.get_insights(
    advertiser_id='YOUR_ADVERTISER_ID',
    date_preset='last_7_days',
    breakdowns=['day'],
)

for data in insights:
    print(f"日期: {data['report_date']}")
    print(f"展示: {data['impressions']}")
    print(f"点击: {data['clicks']}")
    print(f"花费: {data['cost']}")
```

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
