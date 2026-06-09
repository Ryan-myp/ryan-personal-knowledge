# Meta Ads API — 从入门到源码级

> 创建日期: 2026-06-09
> 作者: Ryan

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 Meta Ads 是什么？

```
Meta Ads 是 Meta（Facebook + Instagram）的广告投放平台
用户可以在 Facebook、Instagram、Messenger、Audience Network 上投放广告

核心产品:
├─ Facebook Ads (Facebook 广告)
├─ Instagram Ads (Instagram 广告)
├─ Messenger Ads (Messenger 广告)
├─ Audience Network (广告网络)
└─ Advantage+ (AI 优化广告)
```

### 1.2 为什么需要 API？

```
没有 API:
- 手动操作 Facebook Ads Manager
- 无法批量管理多个广告账户
- 无法自动优化广告

有 API:
- 批量管理广告账户
- 自动优化广告（根据数据调出价）
- 数据拉取和分析
- 集成内部系统
```

### 1.3 API 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                  Meta Ads API 架构                           │
│                                                             │
│  ┌──────────────┐                                          │
│  │  你的系统     │                                          │
│  │  (Client)    │                                          │
│  └──────┬───────┘                                          │
│         │ HTTPS REST API                                    │
│         ▼                                                   │
│  ┌────────────────────────────────────────────────────────┐│
│  │               Meta Ads API Server                       ││
│  │                                                        ││
│  │  ┌────────────────────────────────────────────────────┐││
│  │  │              GraphQL Layer                         │││
│  │  └────────────┬───────────────────────────────────────┘││
│  │               │                                        ││
│  │  ┌────────────▼───────────────────────────────────────┐││
│  │  │           业务逻辑层                                 │││
│  │  │           (AdAccount, Campaign, Ad, Image...)      │││
│  │  └────────────────────────────────────────────────────┘││
│  └────────────────────────────────────────────────────────┘│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 快速体验

```bash
# 1. 安装 Meta Ads API SDK
pip install facebook-business

# 2. Python 示例
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign

# 配置
ACCESS_TOKEN = 'YOUR_ACCESS_TOKEN'
APP_SECRET = 'YOUR_APP_SECRET'
APP_ID = 'YOUR_APP_ID'

FacebookAdsApi.init(ACCESS_TOKEN, APP_SECRET, APP_ID)

# 查询广告数据
my_account = AdAccount('act_YOUR_AD_ACCOUNT_ID')
params = {
    'level': 'ad',
    'date_preset': 'last_7_days',
}
stats = my_account.get_insights(params=params)

for insight in stats:
    print(f"广告: {insight['name']}")
    print(f"展示: {insight['actions'][0]['value']}")
```

### 1.5 关键概念总结

| 概念 | 说明 |
|------|------|
| **Access Token** | API 访问令牌，有有效期 |
| **Ad Account** | 广告账户 |
| **Campaign** | 广告系列 |
| **Ad Set** | 广告组（定向、预算、出价） |
| **Ad** | 广告素材 |
| **Insights** | 广告数据指标 |

---

## 第二部分：源码级深度剖析

### 2.1 认证流程源码

```python
# facebook_business/api.py
# Meta Ads API 认证

class FacebookAdsApi:
    """
    Meta Ads API 客户端
    
    认证方式:
    ├── User Token: 用户授权令牌
    │   ├── 需要用户登录
    │   ├── 权限: ads_management, read_insights
    │   └── 有效期: 60 天
    │
    ├── App Token: 应用令牌
    │   ├── 用于系统级操作
    │   ├── 有效期: 无限（除非撤销）
    │   └── 需要 App Secret
    │
    └── Customer Access Token: 客户令牌
        ├── 代理商专用
        ├── 管理多个广告账户
        └── 权限继承自父账户
    """
    
    _API_VERSION = 'v18.0'
    _APP_SECRET = None
    
    @classmethod
    def init(cls, access_token, app_secret=None, app_id=None):
        """
        初始化 API 客户端
        
        流程:
        1. 验证 access_token 格式
        2. 设置全局配置
        3. 建立会话
        """
        if not cls._validate_token(access_token):
            raise ValueError("Invalid access token")
        
        cls._APP_SECRET = app_secret or cls._APP_SECRET
        cls._access_token = access_token
        cls._session = requests.Session()
        cls._session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        })
    
    @classmethod
    def _validate_token(cls, token: str) -> bool:
        """验证 token"""
        # token 格式: 有 28-50 个字符
        return 28 <= len(token) <= 50
    
    @classmethod
    def get_api_version(cls) -> str:
        """获取当前 API 版本"""
        return cls._API_VERSION
```

### 2.2 请求执行源码

```python
# facebook_business/adobjects/ad.py
# Ad 对象操作

class Ad(BaseAdObject):
    """
    广告对象
    
    常用方法:
    ├── get(): 获取广告详情
    ├── update(): 更新广告
    ├── delete(): 删除广告
    ├── get_insights(): 获取广告数据
    └── create(): 创建广告
    """
    
    def get_insights(
        self,
        fields: list = None,
        params: dict = None,
        date_preset: str = 'last_7_days',
    ):
        """
        获取广告数据
        
        参数:
        ├── fields: 要获取的字段
        ├── params: 查询参数
        └── date_preset: 日期预设
        
        支持的 date_preset:
        ├── today: 今天
        ├── yesterday: 昨天
        ├── last_7_days: 过去 7 天
        ├── last_30_days: 过去 30 天
        ├── this_month: 本月
        ├── last_month: 上月
        ├── lifetime: 全部
        └── custom: 自定义日期
        """
        api_version = FacebookAdsApi.get_api_version()
        url = f'/{api_version}/{self.get_id()}/insights'
        
        default_params = {
            'date_preset': date_preset,
            'level': 'ad',
        }
        
        if fields:
            default_params['fields'] = ','.join(fields)
        
        if params:
            default_params.update(params)
        
        response = requests.get(url, params=default_params)
        response.raise_for_status()
        
        return response.json()['data']
```

### 2.3 批量操作源码

```python
# facebook_business/adobjects/adaccount.py
# 批量操作

class AdAccount(BaseAdObject):
    """
    广告账户操作
    
    批量操作支持:
    ├── 创建多个广告
    ├── 更新多个广告
    ├── 删除多个广告
    └── 批量获取数据
    """
    
    def create_campaign(
        self,
        name: str,
        advertising_channel_type: str,
        optimization_goal: str,
        status: str = 'PAUSED',
    ) -> 'Campaign':
        """
        创建广告系列
        
        流程:
        1. 构建 POST 请求
        2. 设置广告系列参数
        3. 执行请求
        4. 返回创建结果
        """
        params = {
            'name': name,
            'advertising_channel_type': advertising_channel_type,
            'optimization_goal': optimization_goal,
            'status': status,
        }
        
        return self.create_campaign(params)
    
    def bulk_create_ads(
        self,
        ad_data_list: list,
        sync_mode: bool = False,
    ) -> list:
        """
        批量创建广告
        
        参数:
        ├── ad_data_list: 广告数据列表
        │   ├── {name, creative, ...}
        │   ├── {name, creative, ...}
        │   └── ...
        └── sync_mode: 是否同步执行
        
        流程:
        1. 验证每个广告数据
        2. 分批发送请求（每批 20 个）
        3. 等待执行完成
        4. 返回结果列表
        """
        results = []
        batch_size = 20
        
        for i in range(0, len(ad_data_list), batch_size):
            batch = ad_data_list[i:i+batch_size]
            
            # 构建批量请求
            operations = []
            for ad_data in batch:
                operation = {
                    'node_id': self.get_id(),
                    'operation': 'POST',
                    'path': '/ads',
                    'body': ad_data,
                }
                operations.append(operation)
            
            # 执行批量请求
            response = self.api.execute_bulk(operations)
            results.extend(response)
        
        return results
```

### 2.4 数据查询源码

```python
# facebook_business/adobjects/adaccount.py
# 数据查询

class AdAccount(BaseAdObject):
    """
    广告账户数据查询
    
    支持的查询级别:
    ├── account: 广告账户级别
    ├── campaign: 广告系列级别
    ├── adset: 广告组级别
    ├── ad: 广告级别
    └── day: 按天
    
    支持的指标:
    ├── impressions: 展示
    ├── reach: 触达人数
    ├── clicks: 点击
    ├── ctr: 点击率
    ├── cpc: 每次点击费用
    ├── conversions: 转化
    ├── cost_per_conversion: 每次转化费用
    └── roas: 广告回报率
    """
    
    def get_insights(
        self,
        fields: list = None,
        params: dict = None,
        date_preset: str = 'last_7_days',
        level: str = 'ad',
        breakdowns: list = None,
    ):
        """
        获取广告数据
        
        参数:
        ├── fields: 要获取的字段
        ├── params: 查询参数
        ├── date_preset: 日期预设
        ├── level: 查询级别
        └── breakdowns: 拆分维度
        
        支持的 breakdowns:
        ├── time: 按时间拆分
        ├── age: 按年龄拆分
        ├── gender: 按性别拆分
        ├── country: 按国家拆分
        ├── platform: 按平台拆分
        └── device: 按设备拆分
        """
        api_version = FacebookAdsApi.get_api_version()
        url = f'/{api_version}/{self.get_id()}/insights'
        
        default_params = {
            'date_preset': date_preset,
            'level': level,
        }
        
        if fields:
            default_params['fields'] = ','.join(fields)
        
        if breakdowns:
            default_params['breakdowns'] = ','.join(breakdowns)
        
        if params:
            default_params.update(params)
        
        response = requests.get(url, params=default_params)
        response.raise_for_status()
        
        return response.json()['data']
```

### 2.5 错误处理源码

```python
# facebook_business/exceptions.py
# 错误处理

import facebook_business
from facebook_business import FacebookRequestError

class FacebookRequestError(FacebookRequestError):
    """
    Meta API 请求错误
    
    常见错误:
    ├── 100: Invalid parameter
    ├── 200: Permissions error
    ├── 368: Duplicate request
    ├── 800: Rate limit
    ├── 803: Policy violation
    └── 908: App disabled
    
    处理策略:
    ├── 自动重试: 500 系列错误
    ├── 用户提示: 3xx 系列错误
    └── 记录日志: 所有错误
    """
    
    ERROR_CODES = {
        100: "Invalid parameter",
        200: "Permissions error",
        368: "Duplicate request",
        800: "Rate limit",
        803: "Policy violation",
        908: "App disabled",
        909: "App not active",
        910: "App suspended",
    }
    
    def __init__(self, error_code, error_message, error_subcode=None):
        self.error_code = error_code
        self.error_message = error_message
        self.error_subcode = error_subcode
        super().__init__(error_message)
    
    def handle_error(self):
        """
        错误处理
        
        返回:
        ├── True: 已处理
        └── False: 需要重试
        """
        # 可重试的错误
        if self.error_code == 800:  # 速率限制
            return self._handle_rate_limit()
        elif self.error_code == 368:  # 重复请求
            return True
        elif self.error_code in (200, 803, 908):  # 权限/策略/应用
            return False
        
        return False
```

### 2.6 速率限制源码

```python
# facebook_business/ratelimit.py
# 速率限制

import time
from functools import wraps

class RateLimitExceeded(Exception):
    """速率限制异常"""
    pass

def handle_rate_limit(func):
    """
    速率限制处理装饰器
    
    流程:
    1. 执行函数
    2. 捕获 RateLimitExceeded 异常
    3. 等待后重试
    4. 最多重试 3 次
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except RateLimitExceeded as e:
                if attempt == max_retries - 1:
                    raise
                # 指数退避
                wait_time = 2 ** (attempt + 1)
                time.sleep(wait_time)
        return None
    return wrapper

class MetaRateLimiter:
    """
    Meta 速率限制器
    
    限制规则:
    ├── 每个 ad account 的速率限制
    ├── 根据 access_token 类型不同
    ├── User Token: 每分钟 200 次
    ├── App Token: 每分钟 1000 次
    └── Customer Token: 每分钟 500 次
    
    检测:
    ├── 响应头: X-App-Usage
    ├── 响应头: X-Page-Usage
    └── 响应体: error subcode 800
    """
    
    def __init__(self, max_requests_per_minute=200):
        self.max_requests = max_requests_per_minute
        self.request_count = 0
        self.window_start = time.time()
    
    def check(self):
        """检查速率限制"""
        elapsed = time.time() - self.window_start
        
        # 窗口过期
        if elapsed > 60:
            self.request_count = 0
            self.window_start = time.time()
        
        # 超过限制
        if self.request_count >= self.max_requests:
            wait_time = 60 - elapsed
            time.sleep(wait_time)
            self.request_count = 0
            self.window_start = time.time()
        
        self.request_count += 1
```

---

## 第三部分：自测

### 问题 1
Meta Ads API 支持的认证方式有哪些？
<details>
<summary>查看答案</summary>

- User Token: 用户授权，有效期 60 天
- App Token: 应用令牌，长期有效
- Customer Access Token: 代理商专用
</details>

### 问题 2
date_preset 支持哪些值？
<details>
<summary>查看答案</summary>

- today, yesterday
- last_7_days, last_30_days
- this_month, last_month
- lifetime, custom
</details>

### 问题 3
错误码 800 是什么意思？如何处理？
<details>
<summary>查看答案</summary>

- 错误码 800: 速率限制
- 处理: 等待后重试（指数退避）
</details>

---

## 第四部分：动手验证

### 4.1 查询广告数据

```python
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

FacebookAdsApi.init(ACCESS_TOKEN, APP_SECRET, APP_ID)

my_account = AdAccount('act_YOUR_AD_ACCOUNT_ID')
stats = my_account.get_insights(
    params={
        'level': 'ad',
        'date_preset': 'last_7_days',
    }
)

for insight in stats:
    print(f"广告: {insight['name']}")
    print(f"展示: {insight['impressions']}")
    print(f"点击: {insight['clicks']}")
```

### 4.2 创建广告

```python
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adaccount import AdAccount

my_account = AdAccount('act_YOUR_AD_ACCOUNT_ID')

ad = my_account.create_ad({
    Ad.Field.name: '测试广告',
    Ad.Field.campaign_id: 'YOUR_CAMPAIGN_ID',
    Ad.Field.adset_id: 'YOUR_ADSET_ID',
    Ad.Field.status: Ad.Status.paused,
    Ad.Field.ad Creatives: [
        {
            AdCreative.Field.title: '测试',
            AdCreative.Field.body: '测试广告',
            AdCreative.Field.image_hash: image_hash,
        }
    ],
})

print(f"创建成功: {ad[Ad.Field.id]}")
```

---

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
