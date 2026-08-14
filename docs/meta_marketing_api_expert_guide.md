# Meta Marketing API 专家级指南 2025

> 基于 Meta Marketing API v20+ 官方文档蒸馏 | Python SDK 最佳实践

---

## 一、API 架构核心认知

### 1.1 Meta 广告账户层级结构

```
Business Manager (BM)
└── Ad Account (act_{account_id})
    ├── Campaign
    │   ├── Ad Set (AdGroup)
    │   │   └── Ad
    │   │       └── Creative
    │   └── Insight (报表)
    └── Custom Audience / Lookalike
```

### 1.2 关键认证概念

```python
# Meta 使用 Access Token 而非 OAuth 流程
# 推荐权限范围:
# - ads_management (必需)
# - ads_read (必需)
# - public_profile (可选)
# - email (可选)

VALID_PERMISSIONS = [
    'ads_management',      # 创建/管理广告
    'ads_read',            # 读取广告数据
    'business_management', # 管理 BM
    'pages_manage_ads',    # 页面广告管理
    'pages_read_engagement', # 页面互动读取
]
```

### 1.3 API 版本管理

```python
# Meta API 版本规则:
# - 当前稳定版本: v20.0 (2024)
# - 支持最近 2-3 个版本
# - 迁移时需检查 Breaking Changes

# 推荐做法: 始终显式指定版本
API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
```

---

## 二、Campaign 创建与管理的专家实践

### 2.1 完整 Campaign 创建流程

```python
import requests
import time

class MetaAdsExpertClient:
    """Meta Marketing API 专家级客户端"""
    
    def __init__(self, access_token: str, account_id: str):
        self.token = access_token
        self.account_id = account_id  # 格式: act_123456789
        self.api_version = "v20.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
        # 请求头
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def create_campaign(self, name: str, objective: str, 
                        daily_budget: int = 1000,
                        status: str = 'PAUSED') -> dict:
        """
        创建 Campaign
        objective: OUTCOME_LEADS, OUTCOME_CONVERSIONS, OUTCOME_SALES, OUTCOME_AWARENESS
        daily_budget: cents (分)
        """
        url = f"{self.base_url}/{self.account_id}/campaigns"
        
        payload = {
            'name': name,
            'objective': objective,
            'status': status,
            'daily_budget': daily_budget,
            'special_ad_categories': []  # 必需，无特殊分类设为空数组
        }
        
        r = requests.post(url, json=payload, headers=self.headers)
        if r.status_code != 200:
            raise Exception(f"创建 Campaign 失败: {r.text}")
        
        result = r.json()
        campaign_id = result.get('id')
        print(f"✅ Campaign created: {campaign_id}")
        return {'id': campaign_id, 'name': name}
    
    def create_adset(self, campaign_id: str, name: str, 
                     daily_budget: int, targeting: dict) -> dict:
        """
        创建 Ad Set (广告组)
        targeting: 详细的受众定位配置
        """
        url = f"{self.base_url}/{campaign_id}/adsets"
        
        # 构建 targeting JSON
        targeting_json = {
            'location_ids': targeting.get('location_ids', []),
            'age_min': targeting.get('age_min', 18),
            'age_max': targeting.get('age_max', 65),
            'genders': targeting.get('genders', [1]),  # 1=female, 2=male
            'interests': targeting.get('interests', [])
        }
        
        # 可选: 排除受众
        if targeting.get('exclusions'):
            targeting_json['exclusions'] = targeting['exclusions']
        
        payload = {
            'name': name,
            'status': 'PAUSED',
            'daily_budget': daily_budget,
            'optimization_gate': 'OFF',  # 关闭优化门控，快速学习
            'billing_event': 'IMPRESSIONS',
            'bid_amount': targeting.get('bid_amount', 100),
            'targeting': targeting_json,
            'special_ad_categories': []  # 美国必需，其他国家可选
        }
        
        # 投放平台选择
        if targeting.get('platforms'):
            payload['promoted_object'] = {
                'placement': targeting['platforms']
            }
        
        r = requests.post(url, json=payload, headers=self.headers)
        if r.status_code != 200:
            raise Exception(f"创建 AdSet 失败: {r.text}")
        
        result = r.json()
        adset_id = result.get('id')
        print(f"✅ AdSet created: {adset_id}")
        return {'id': adset_id, 'name': name}
    
    def create_ad(self, adset_id: str, name: str, 
                  creative_config: dict) -> dict:
        """
        创建 Ad (创意)
        creative_config: {
            'body': str,           # 文案
            'title': str,          # 标题
            'link': str,           # 落地页 URL
            'image_hash': str,     # 图片 hash (先上传图片)
            'object_story_spec': dict
        }
        """
        url = f"{self.base_url}/{adset_id}/ads"
        
        # 构建 creative spec
        object_story_spec = {
            'page_id': creative_config.get('page_id'),
            'link_data': {
                'link': creative_config['link'],
                'message': creative_config.get('body', ''),
                'call_to_action': {
                    'type': creative_config.get('cta_type', 'LEARN_MORE'),
                    'value': {
                        'link': creative_config['link']
                    }
                }
            }
        }
        
        # 添加图片 (如果有)
        if creative_config.get('image_hash'):
            object_story_spec['link_data']['image_hash'] = creative_config['image_hash']
        
        payload = {
            'name': name,
            'status': 'PAUSED',
            'creative': {
                'body': creative_config.get('body', ''),
                'title': creative_config.get('title', ''),
                'object_story_spec': object_story_spec
            },
            'special_ad_categories': []
        }
        
        r = requests.post(url, json=payload, headers=self.headers)
        if r.status_code != 200:
            raise Exception(f"创建 Ad 失败: {r.text}")
        
        result = r.json()
        ad_id = result.get('id')
        print(f"✅ Ad created: {ad_id}")
        return {'id': ad_id, 'name': name}
```

### 2.2 高级受众定位配置

```python
def build_advanced_targeting(
    countries: list,
    age_min: int = 18,
    age_max: int = 65,
    genders: list = None,
    interests: list = None,
    behaviors: list = None,
    custom_audiences: list = None,
    lookalike_audiences: list = None,
    exclude_audiences: list = None
) -> dict:
    """
    构建高级受众定位配置
    返回格式符合 Meta API 要求
    """
    targeting = {
        'countries': countries,
        'age_min': age_min,
        'age_max': age_max
    }
    
    if genders:
        targeting['genders'] = genders
    
    if interests:
        targeting['interests'] = [
            {'name': name} for name in interests
        ]
    
    if behaviors:
        targeting['behaviors'] = [
            {'name': name} for name in behaviors
        ]
    
    if custom_audiences:
        targeting['custom_audiences'] = custom_audiences
    
    if lookalike_audiences:
        targeting['lookalike_audiences'] = lookalike_audiences
    
    if exclude_audiences:
        targeting['exclusions'] = {
            'custom_audiences': exclude_audiences
        }
    
    return targeting


# 使用示例
targeting = build_advanced_targeting(
    countries=['840'],  # US FIPS 代码
    age_min=25,
    age_max=45,
    genders=[1, 2],  # 男女都投
    interests=[
        'Shopping and browsing',
        'E-commerce',
        'Online shopping'
    ],
    custom_audiences=['ca_123456'],  # 再营销列表
    lookalike_audiences=['la_789012'],  # 类似受众
    exclude_audiences=['ca_existing_customers']  # 排除已购买用户
)
```

---

## 三、Creative 管理与批量操作

### 3.1 图片上传与创意管理

```python
def upload_image(self, image_path: str, image_url: str = None) -> dict:
    """
    上传图片并获取 hash
    支持本地文件或 URL
    """
    url = f"{self.base_url}/{self.account_id}/photos"
    
    if image_url:
        payload = {'url': image_url}
    else:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            r = requests.post(url, headers=self.headers, files=files)
            return r.json()
    
    r = requests.post(url, json=payload, headers=self.headers)
    return r.json()


def batch_create_ads(self, adset_id: str, ads_config: list) -> list:
    """
    批量创建 Ad
    ads_config: [{
        'name': str,
        'body': str,
        'title': str,
        'link': str,
        'image_hash': str,
        'cta_type': str
    }, ...]
    """
    results = []
    for i, config in enumerate(ads_config):
        try:
            result = self.create_ad(adset_id, config['name'], config)
            results.append(result)
            time.sleep(0.5)  # 避免限流
        except Exception as e:
            print(f"⚠️ Ad {config['name']} failed: {e}")
            results.append({'name': config['name'], 'error': str(e)})
    
    return results
```

### 3.2 A/B 测试配置

```python
def create_ab_test(self, campaign_id: str, test_name: str,
                   variants: list, budget_per_variant: int) -> dict:
    """
    创建 A/B 测试 (Split Test)
    variants: [{'name': 'A', 'adset_id': '...'}, ...]
    """
    url = f"{self.base_url}/{campaign_id}/abtest"
    
    payload = {
        'name': test_name,
        'prediction_window_hours': 72,  # 预测窗口
        'secondary_metrics': [
            {'event_type': 'ctr', 'metric_names': ['ctr']},
            {'event_type': 'cpr', 'metric_names': ['cpm']}
        ],
        'variants': variants,
        'termination_condition': {
            'confidence_level': 0.95,
            'winning_candidate_selection': 'TOTAL_ESTIMATED_ROAS'
        }
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    return r.json()


def get_ab_test_results(self, test_id: str) -> dict:
    """获取 A/B 测试结果"""
    url = f"{self.base_url}/{test_id}"
    params = {
        'fields': 'name,variants,statistical_significance',
        'access_token': self.token
    }
    r = requests.get(url, params=params, headers=self.headers)
    return r.json()
```

---

## 四、报表查询与数据分析

### 4.1 多维度报表查询

```python
def get_campaign_insights(self, campaign_ids: list, 
                          time_range: dict = None,
                          level: str = 'campaign') -> list:
    """
    获取 Campaign 级报表
    level: campaign, adset, ad
    time_range: {'since': '2025-01-01', 'until': '2025-01-31'}
    """
    url = f"{self.base_url}/{self.account_id}/insights"
    
    # 构建 fields
    fields = [
        'campaign_id', 'campaign_name', 'campaign_id',
        'spend', 'impressions', 'clicks', 'ctr', 'cpc',
        'purchases', 'purchase_roas', 'cost_per_purchase',
        'cpm', 'frequency', 'reach',
        'actions', 'action_values',
        'attacted_offsite_conversion_actions'
    ]
    
    params = {
        'fields': ','.join(fields),
        'level': level,
        'time_range': time_range or {'since': '30_days_ago', 'until': 'today'},
        'access_token': self.token
    }
    
    if campaign_ids:
        params['filtering'] = f'[{{"field":"campaign_id","operator":"in","value":{campaign_ids}}}]'
    
    all_data = []
    while url:
        r = requests.get(url, params=params, headers=self.headers)
        data = r.json()
        
        if 'data' in data:
            all_data.extend(data['data'])
        
        # 分页
        url = data.get('paging', {}).get('next')
        params = {}
        
        time.sleep(0.3)  # 限流保护
    
    return all_data


def get_detailed_insights(self, account_id: str, 
                          date_params: dict = None) -> list:
    """
    详细报表 - 包含所有渠道表现
    """
    url = f"{self.base_url}/{account_id}/insights"
    
    fields = [
        # 基础指标
        'spend', 'impressions', 'clicks', 'ctr', 'cpc',
        'frequency', 'reach',
        
        # 转化指标
        'purchases', 'purchase_roas', 'cost_per_purchase',
        'qualifying_call_starts', 'qualifying_message_conversations',
        
        # 渠道表现
        'actions', 'action_values',
        'attacked_offsite_conversion_actions',
        
        # 细分维度
        'placement', 'publisher_platform', 'platform_position',
        'age', 'gender', 'country', 'region'
    ]
    
    params = {
        'fields': ','.join(fields),
        'date_preset': date_params.get('preset', 'last_30d'),
        'breakdowns': date_params.get('breakdowns', ['placement', 'publisher_platform']),
        'access_token': self.token
    }
    
    all_data = []
    while url:
        r = requests.get(url, params=params, headers=self.headers)
        data = r.json()
        
        if 'data' in data:
            all_data.extend(data['data'])
        
        url = data.get('paging', {}).get('next')
        params = {}
        time.sleep(0.3)
    
    return all_data
```

### 4.2 归因窗口分析

```python
def analyze_attribution(self, account_id: str, 
                        conversion_window: dict = None) -> dict:
    """
    分析不同归因窗口的表现
    conversion_window: {'click': 7, 'view': 1}
    """
    url = f"{self.base_url}/{account_id}/insights"
    
    params = {
        'fields': ','.join([
            'spend', 'impressions', 'clicks',
            'purchases', 'purchase_roas', 'cost_per_purchase'
        ]),
        'time_range': '{"since":"30_days_ago","until":"today"}',
        'conversion_window': conversion_window or {'click': 7, 'view': 1},
        'breakdowns': ['placement', 'age', 'gender'],
        'access_token': self.token
    }
    
    r = requests.get(url, params=params, headers=self.headers)
    return r.json()
```

---

## 五、自定义受众管理

### 5.1 自定义受众创建

```python
def create_custom_audience(self, name: str, subtype: str, 
                           description: str = '') -> dict:
    """
    创建自定义受众
    subtype: 
      - CUSTOMER_LIST (上传客户列表)
      - WEBSITE (网站访客)
      - APP_ACTIVITY (APP 活动)
      - ENGAGEMENT (互动受众)
    """
    url = f"{self.base_url}/{self.account_id}/customaudiences"
    
    payload = {
        'name': name,
        'subtype': subtype,
        'description': description,
        'retention_days': 180
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    result = r.json()
    
    if 'id' in result:
        print(f"✅ Custom Audience created: {result['id']}")
    return result


def upload_customer_list(self, audience_id: str, 
                         user_data: list) -> dict:
    """
    上传客户列表到 Custom Audience
    user_data: [{'email': 'hash'}, {'phone': 'hash'}, ...]
    """
    url = f"{self.base_url}/{audience_id}/users"
    
    # Meta 要求数据加密
    import hashlib
    encoded_data = []
    for user in user_data:
        item = {}
        for key, value in user.items():
            if value:
                item[key] = hashlib.sha256(value.lower().encode()).hexdigest()
        encoded_data.append(item)
    
    payload = {'data': encoded_data}
    r = requests.post(url, json=payload, headers=self.headers)
    return r.json()


def create_lookalike(self, source_audience_id: str, 
                     name: str, location_ids: list = ['840']) -> dict:
    """创建 Lookalike 受众"""
    url = f"{self.base_url}/{self.account_id}/lookalikes"
    
    payload = {
        'name': name,
        'origin_audience_id': source_audience_id,
        'location_ids': location_ids,
        'lookalike_percent': 1  # 1-10%，越小越精准
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    return r.json()
```

---

## 六、限流与错误处理

### 6.1 Meta API 限流规则

| 限制类型 | 限制值 | 说明 |
|----------|--------|------|
| 每 Ad Account | 1000 请求/小时 | 基础限制 |
| 每 App | 2000 请求/小时 | 应用级限制 |
| 每 User Token | 200 请求/小时 | 用户级别限制 |
| 写操作 | 更严格 | Create/Update 受限更多 |

### 6.2 智能限流实现

```python
import time
import asyncio
from collections import defaultdict

class MetaRateLimiter:
    """Meta API 限流器"""
    
    def __init__(self, max_requests_per_hour=800):
        self.max_rph = max_requests_per_hour
        self.requests = defaultdict(list)
        self.lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None
    
    async def wait(self, account_id: str):
        """异步等待限流"""
        now = time.time()
        timestamps = self.requests[account_id]
        
        # 清理 1 小时前的记录
        self.requests[account_id] = [
            t for t in timestamps if now - t < 3600
        ]
        timestamps = self.requests[account_id]
        
        if len(timestamps) >= self.max_rph:
            wait_time = 3600 - (now - timestamps[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self.requests[account_id].append(time.time())
    
    def sync_wait(self, account_id: str):
        """同步版本"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.wait(account_id))


# 使用示例
rate_limiter = MetaRateLimiter(max_requests_per_hour=800)

async def batch_process_ads(account_id: str, operations: list):
    """批量处理 Ad 操作"""
    for op in operations:
        await rate_limiter.wait(account_id)
        result = await process_operation(op)
        yield result
```

### 6.3 错误处理最佳实践

```python
ERROR_HANDLING = {
    4: ('Bad Request', '检查请求参数'),
    13: ('User Token Expired', '重新获取 Access Token'),
    19: ('Permission Error', '检查 App 权限范围'),
    200: ('Permission Denied', '检查用户授权'),
    22: ('Platform Error', '服务端错误，稍后重试'),
    32: ('Field Error', '字段不存在或格式错误'),
    36: ('Business Error', '账户状态问题'),
    800: ('Duplicate Post', '重复请求'),
    801: ('Rate Limit', '触发限流，等待重试'),
    900: ('Unsupported Get', '不支持的查询'),
}

def handle_api_error(response):
    """统一的错误处理"""
    if response.status_code == 429:
        # Rate limited
        retry_after = response.headers.get('X-Ad-Ideia-RateLimit-Remaining', '3600')
        wait_time = int(retry_after) if retry_after else 60
        print(f"⚠️ 限流，等待 {wait_time}s")
        time.sleep(wait_time)
        return None
    
    error = response.json().get('error', {})
    error_code = error.get('code')
    
    if error_code in ERROR_HANDLING:
        msg, action = ERROR_HANDLING[error_code]
        print(f"❌ {msg}: {error.get('message')}")
        print(f"   建议: {action}")
    
    return error
```

---

## 七、生产环境最佳实践

### 7.1 代码质量检查清单

- [ ] 所有请求使用 session 复用连接
- [ ] 实现指数退避重试 (1s, 2s, 4s, 8s)
- [ ] 批量操作控制并发数 (建议 ≤10)
- [ ] 敏感信息不硬编码 (使用环境变量)
- [ ] 所有 API 调用记录日志
- [ ] 定期轮换 Access Token

### 7.2 性能优化技巧

```python
# ✅ 推荐: 使用并行请求提高效率
import aiohttp
import asyncio

async def batch_get_insights(session: aiohttp.ClientSession, 
                             account_ids: list) -> dict:
    """并行获取多个账户的报表"""
    async def fetch(session, aid):
        async with session.get(
            f"https://graph.facebook.com/v20.0/{aid}/insights",
            params={'access_token': TOKEN, 'fields': 'spend,impressions'}
        ) as resp:
            return await resp.json()
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, aid) for aid in account_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return dict(zip(account_ids, results))
```

### 7.3 安全最佳实践

```python
# 使用环境变量存储敏感信息
import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN')
APP_SECRET = os.environ.get('META_APP_SECRET')
BUSINESS_MANAGER_ID = os.environ.get('BM_ID')

# Token 刷新机制
def refresh_access_token():
    """使用 App Secret 签名验证刷新 Token"""
    import requests
    token_url = "https://graph.facebook.com/oauth/access_token"
    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': os.environ['APP_ID'],
        'client_secret': APP_SECRET,
        'fb_exchange_token': ACCESS_TOKEN
    }
    r = requests.get(token_url, params=params)
    return r.json().get('access_token')
```

---

## 参考资源

- [Meta Marketing API 官方文档](https://developers.facebook.com/docs/marketing-ads-api/)
- [Python SDK GitHub](https://github.com/facebook/facebook-python-business-sdk)
- [API 版本说明](https://developers.facebook.com/docs/graph-api/changelog/version-history)
- [限流指南](https://developers.facebook.com/docs/graph-api/overview/rate-limiting)
- [Ads Management API 文档](https://developers.facebook.com/docs/ads-apis)

---

## 附录：v25 API 新特性

### A.0 Meta GQL API (GraphQL)

Meta 正在逐步推出基于 GraphQL 的 API，支持更灵活的查询：

```python
import requests

class MetaGQLClient:
    """Meta GQL API 客户端 - 使用 GraphQL 查询"""
    
    def __init__(self, access_token: str):
        self.token = access_token
        self.base_url = "https://graph.facebook.com/v25.0"
    
    def query_with_gql(self, account_id: str, query: str) -> dict:
        """
        使用 GQL 查询（替代传统 REST）
        query: GraphQL 查询语句
        """
        url = f"{self.base_url}/{account_id}"
        
        # GraphQL 查询示例
        gql_query = """
        {
            campaign {
                id
                name
                status
                objective
                daily_budget {
                    amount
                    currency
                }
                adsets(limit: 10) {
                    data {
                        id
                        name
                        status
                        targeting {
                            geo_locations {
                                countries
                            }
                        }
                    }
                }
            }
        }
        """
        
        params = {
            'access_token': self.token,
            'fields': gql_query
        }
        
        r = requests.get(url, params=params, headers=self.headers)
        return r.json()
    
    def batch_gql_query(self, queries: list) -> dict:
        """
        批量 GQL 查询（推荐方式）
        减少 API 调用次数
        """
        url = f"{self.base_url}/{account_id}"
        
        # 批量查询
        batch_queries = {str(i): q for i, q in enumerate(queries)}
        
        params = {
            'access_token': self.token,
            'batch': json.dumps(list(batch_queries.values()))
        }
        
        r = requests.post(url, data=params, headers=self.headers)
        return r.json()


# 使用示例
gql_client = MetaGQLClient(access_token='YOUR_TOKEN')

# 复杂的多层级查询
result = gql_client.query_with_gql(
    account_id='act_123456',
    query="""
    {
        campaigns {
            data {
                id
                name
                insight {
                    actions
                    spend
                    ctr
                }
            }
        }
    }
    """
)
```

**GQL vs REST 对比**:

| 特性 | REST API | GQL API |
|------|----------|---------|
| 查询灵活性 | 固定字段 | 自定义查询 |
| 嵌套数据 | 多次请求 | 单次请求 |
| 性能 | 较慢 | 更快 |
| 适用场景 | 简单 CRUD | 复杂报表分析 |

### A.1 2025 年关键变更

| 特性 | 说明 | 影响 |
|------|------|------|
| Campaign 字段扩展 | 新增 `campaign_type`、`dynamic_audience_id` | 支持更精细的投放控制 |
| Ad Set 优化门控 | `optimization_gate` 支持多目标 | 提升转化效率 |
| Creative 批量操作 | 支持 100+ Creative 批量上传 | 提高素材管理效率 |
| 报表精度提升 | 归因窗口扩展到 90 天 | 更准确的 ROI 分析 |
| 动态创意增强 | `dynamic_creative` 支持 20+ 变量 | 自动化 A/B 测试 |

### A.2 版本迁移检查清单

```python
# v25 迁移注意事项
V25_CHANGES = {
    # 已弃用的端点
    'deprecated_endpoints': [
        '/v24/adaccounts/{aid}/insights',  # 改用 /v25/adaccounts/{aid}/insights
    ],
    
    # 必填字段变更
    'required_fields_v25': {
        'campaign': ['name', 'objective', 'status', 'daily_budget'],
        'adset': ['name', 'campaign_id', 'optimization_gate'],
        'ad': ['name', 'creative', 'status']
    },
    
    # 新增的筛选条件
    'new_filters': [
        'adset.effective_status',
        'adset.optimization_goal',
        'campaign.spend_cap'
    ]
}


def migrate_from_v24_to_v25(client):
    """从 v24 迁移到 v25 的辅助函数"""
    # 1. 更新所有端点版本
    client.api_version = 'v25'
    
    # 2. 添加必填字段
    def ensure_required_fields(campaign_data):
        required = ['name', 'objective', 'status', 'daily_budget']
        missing = [f for f in required if f not in campaign_data]
        if missing:
            print(f"⚠️ Campaign 缺少必填字段: {missing}")
        return campaign_data
    
    # 3. 检查废弃功能
    def check_deprecated_usage(data):
        deprecated_fields = ['date_preset', 'time_increment']
        for field in deprecated_fields:
            if field in data:
                print(f"⚠️ 字段 '{field}' 在 v25 中已废弃")
        return data
    
    return client
```

### A.3 v25 新增报表字段

```python
# v25 Insights API 新增字段
V25_NEW_FIELDS = {
    # 转化相关
    'purchase_roas_7d_click': '7天点击归因购买 ROAS',
    'purchase_roas_1d_view': '1天浏览归因购买 ROAS',
    'qualifying_message_conversations': '高质量消息对话数',
    'qualifying_call_starts': '高质量通话开始数',
    
    # 创意表现
    'creative_ctr': '创意 CTR',
    'creative_video_play_30s': '30秒视频播放数',
    'creative_video_view_complete': '完整视频观看数',
    
    # 受众
    'audience_size_estimate': '受众规模估算',
    'reach_by_age_gender': '分年龄性别的触达'
}
```

### A.4 Batch Upload Creative (批量上传)

```python
def batch_upload_creatives(self, account_id: str, creatives: list) -> dict:
    """
    批量上传创意 (v25 新功能)
    最多支持 100 个创意同时上传
    """
    url = f"https://graph.facebook.com/v25.0/{account_id}/creatives"
    
    # 构建 multipart form data
    files = {}
    data = {'input': json.dumps([{
        'name': c['name'],
        'object_story_spec': c.get('object_story_spec')
    } for c in creatives])}
    
    for i, c in enumerate(creatives):
        if 'image' in c:
            files[f'creative_{i}'] = ('image.jpg', c['image'], 'image/jpeg')
    
    r = requests.post(url, data=data, files=files, headers=self.headers)
    return r.json()


def get_batch_upload_status(self, batch_id: str) -> dict:
    """查询批量上传状态"""
    url = f"https://graph.facebook.com/v25.0/{batch_id}"
    params = {'fields': 'status,created_creative_ids'}
    r = requests.get(url, params=params, headers=self.headers)
    return r.json()
```

---

## 总结

Meta Marketing API 的核心要点：

1. **版本管理** - 始终指定 API 版本，关注 Breaking Changes
2. **权限最小化** - 只申请必要的权限范围
3. **批量操作** - 使用 Batch API 提高效率
4. **归因分析** - 利用多窗口归因优化预算分配
