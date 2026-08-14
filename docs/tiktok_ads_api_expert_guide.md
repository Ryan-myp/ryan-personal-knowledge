# TikTok Ads API 专家级指南 2025

> 基于 TikTok Business API v1.3 官方文档蒸馏 | Python 最佳实践

---

## 一、API 架构核心认知

### 1.1 账户层级结构

```
Business Center
└── Ad Account (ad_id)
    ├── Campaign
    │   └── Ad Group
    │       └── Ad (Creative)
    └── Conversion Tracking (Pixel/SDK)
```

### 1.2 认证与权限

```python
# TikTok Ads API 使用 OAuth 2.0 + Access Token
# 必需的权限范围:
REQUIRED_SCOPES = [
    'user_info.basic',           # 用户基本信息
    'ad_read',                   # 读取广告数据
    'ad_write',                  # 创建/管理广告
    'creative_read',             # 读取创意素材
    'creative_write',            # 上传创意素材
    'pixel_api'                  # Pixel 追踪
]

# Token 端点
TOKEN_URL = 'https://business-api.tiktok.com/open_api/v1.3/oauth/access_token/'
```

### 1.3 API 限流规则

| 限制类型 | 限制值 | 说明 |
|----------|--------|------|
| 每 Ad Account | 1000 请求/小时 | 基础限制 |
| 写操作 | 更严格 | Create/Update 受限 |
| 并发连接 | 5 | 同时连接限制 |
| 批量操作 | 最多 100 条 | 单次请求上限 |

---

## 二、Campaign 创建与管理

### 2.1 完整 Campaign 创建流程

```python
import requests
import time
import hashlib

class TikTokAdsExpertClient:
    """TikTok Ads API 专家级客户端"""
    
    def __init__(self, access_token: str, account_id: str):
        self.token = access_token
        self.account_id = account_id
        self.api_base = "https://business-api.tiktok.com/open_api/v1.3"
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
    
    def create_campaign(self, name: str, daily_budget: int,
                        objective: str = 'LEAD_GENERATION',
                        status: str = 'PAUSED') -> dict:
        """
        创建 Campaign
        objective: LEAD_GENERATION, PRODUCT_SALES, BRAND_AWARENESS, APP_INSTALLS
        daily_budget: 单位: cents (分)
        """
        url = f"{self.api_base}/campaign/adgroup/create/"
        
        payload = {
            'access_token': self.token,
            'ad_account_id': self.account_id,
            'campaign': {
                'name': name,
                'status': status,
                'daily_budget': daily_budget,
                'objective': objective
            }
        }
        
        r = requests.post(url, json=payload, headers=self.headers)
        result = r.json()
        
        if result.get('data', {}).get('campaign_id'):
            print(f"✅ Campaign created: {result['data']['campaign_id']}")
            return result['data']
        else:
            raise Exception(f"创建失败: {result}")
    
    def update_campaign(self, campaign_id: str, updates: dict) -> dict:
        """更新 Campaign 属性"""
        url = f"{self.api_base}/campaign/adgroup/update/"
        
        payload = {
            'access_token': self.token,
            'ad_account_id': self.account_id,
            'campaign': {
                'campaign_id': campaign_id,
                **updates
            }
        }
        
        r = requests.post(url, json=payload, headers=self.headers)
        return r.json()
    
    def list_campaigns(self, limit: int = 10, cursor: int = 0) -> dict:
        """列出 Campaigns"""
        url = f"{self.api_base}/campaign/adgroup/list/"
        
        payload = {
            'access_token': self.token,
            'ad_account_id': self.account_id,
            'limit': limit,
            'cursor': cursor
        }
        
        r = requests.post(url, json=payload, headers=self.headers)
        return r.json()
```

### 2.2 Ad Group 创建与受众定位

```python
def create_ad_group(self, campaign_id: str, name: str,
                    budget: int, targeting: dict) -> dict:
    """
    创建 Ad Group (广告组)
    targeting: 详细的受众定位配置
    """
    url = f"{self.api_base}/campaign/adgroup/create/"
    
    # 构建完整 payload
    payload = {
        'access_token': self.token,
        'ad_account_id': self.account_id,
        'campaign_id': campaign_id,
        'adgroup': {
            'name': name,
            'status': 'PAUSED',
            'daily_budget': budget,
            
            # === 受众定位 ===
            'targeting': {
                # 地理位置
                'geo_locations': targeting.get('geo', {
                    'countries': ['US', 'GB', 'CA']
                }),
                
                # 年龄性别
                'age_range': targeting.get('age', {'min': 18, 'max': 65}),
                'genders': targeting.get('genders', ['MALE', 'FEMALE']),
                
                # 兴趣分类
                'interests': targeting.get('interests', []),
                
                # 行为标签
                'behaviors': targeting.get('behaviors', []),
                
                # 排除设置
                'exclusions': targeting.get('exclusions', {})
            },
            
            # === 投放设置 ===
            'placement_type': 'AUTOMATIC',  # AUTOMATIC / MANUAL
            'optimization_goal': 'LEAD',    # LEAD / PURCHASE / INSTALL
            
            # === 出价设置 ===
            'bid_amount': targeting.get('bid', 100),  # cents
            'bid_type': 'AUTO_BID'  # AUTO_BID / MANUAL_CPC
        }
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    result = r.json()
    
    if result.get('data', {}).get('adgroup_id'):
        print(f"✅ Ad Group created: {result['data']['adgroup_id']}")
    return result.get('data', {})


def build_targeting(
    countries: list = None,
    age_min: int = 18,
    age_max: int = 65,
    genders: list = None,
    interests: list = None,
    excluded_interests: list = None
) -> dict:
    """
    构建 TikTok 受众定位配置
    """
    targeting = {}
    
    if countries:
        targeting['geo'] = {'countries': countries}
    
    if age_min or age_max:
        targeting['age'] = {
            'min': age_min,
            'max': age_max
        }
    
    if genders:
        targeting['genders'] = [g.upper() for g in genders]
    
    if interests:
        targeting['interests'] = [
            {'interest_id': i} if isinstance(i, dict) else {'keyword': i}
            for i in interests
        ]
    
    if excluded_interests:
        targeting['exclusions'] = {
            'interests': [
                {'keyword': i} for i in excluded_interests
            ]
        }
    
    return targeting


# 使用示例
targeting = build_targeting(
    countries=['US', 'GB'],
    age_min=25,
    age_max=45,
    genders=['female'],
    interests=[
        'Beauty & Skincare',
        'Fashion',
        'Shopping'
    ],
    excluded_interests=['Competitor Brand A']
)
```

### 2.3 Ad 创意管理

```python
def create_ad(self, adgroup_id: str, name: str,
              creative_config: dict) -> dict:
    """
    创建 Ad (创意)
    creative_config: {
        'video_url': str,        # 视频 URL 或本地路径
        'image_url': str,        # 图片 URL
        'title': str,            # 标题
        'description': str,      # 描述
        'link_url': str,         # 落地页 URL
        'cta_type': str          # CALL_NOW, LEARN_MORE, SHOP_NOW
    }
    """
    url = f"{self.api_base}/campaign/adgroup/creative/create/"
    
    # 上传媒体资源
    media_urls = []
    
    if creative_config.get('video_url'):
        media_urls.append({
            'media_type': 'VIDEO',
            'url': creative_config['video_url'],
            'video_url': creative_config['video_url']
        })
    
    if creative_config.get('image_url'):
        media_urls.append({
            'media_type': 'IMAGE',
            'url': creative_config['image_url']
        })
    
    # CTA 映射
    cta_map = {
        'CALL_NOW': 'CALL_NOW',
        'LEARN_MORE': 'LEARN_MORE',
        'SHOP_NOW': 'SHOP_NOW',
        'SIGN_UP': 'SIGN_UP'
    }
    
    payload = {
        'access_token': self.token,
        'ad_account_id': self.account_id,
        'adgroup_id': adgroup_id,
        'creative': {
            'name': name,
            'status': 'PAUSED',
            
            # 媒体资源
            'creative_type': 'VIDEO',  # VIDEO / IMAGE / CAROUSEL
            'media_files': media_urls,
            
            # 文本内容
            'title': creative_config.get('title', ''),
            'description': creative_config.get('description', ''),
            
            # 落地页
            'website_url': creative_config.get('link_url', ''),
            
            # CTA
            'call_to_action_type': cta_map.get(
                creative_config.get('cta_type', 'LEARN_MORE'),
                'LEARN_MORE'
            ),
            
            # 可选: 动态创意
            'dynamic_creative': {
                'enable_dynamic_creative': True,
                'headlines': [
                    creative_config.get('title', '')
                ],
                'descriptions': [
                    creative_config.get('description', '')
                ]
            }
        }
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    result = r.json()
    
    if result.get('data', {}).get('ad_id'):
        print(f"✅ Ad created: {result['data']['ad_id']}")
    
    return result.get('data', {})


def upload_video(self, file_path: str) -> str:
    """
    上传视频到 TikTok 素材库
    返回 video_id 用于创建 Ad
    """
    url = f"{self.api_base}/media/upload/"
    
    # TikTok 视频要求
    # - 格式: MP4, MOV
    # - 时长: 5-60 秒
    # - 分辨率: 至少 720p
    # - 比例: 9:16 (推荐), 1:1, 16:9
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        r = requests.post(url, headers=self.headers, files=files)
    
    result = r.json()
    return result.get('data', {}).get('media_id')


def upload_image(self, file_path: str) -> str:
    """上传图片到 TikTok 素材库"""
    url = f"{self.api_base}/media/upload/"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        r = requests.post(url, headers=self.headers, files=files)
    
    result = r.json()
    return result.get('data', {}).get('media_id')
```

---

## 三、Conversion Tracking 与归因

### 3.1 Pixel 事件追踪

```python
def setup_conversion_tracking(self, pixel_id: str, event_name: str,
                              custom_params: dict = None) -> dict:
    """
    设置转化追踪事件
    event_name: PURCHASE, LEAD, PAGE_VIEW, ADD_TO_CART
    """
    url = f"{self.api_base}/conversion/track/"
    
    payload = {
        'access_token': self.token,
        'ad_account_id': self.account_id,
        'pixel_id': pixel_id,
        'event_name': event_name,
        'event_time': int(time.time()),
        'event_source': 'WEBSITE',
        'event_value': custom_params.get('value', 0),
        'currency': custom_params.get('currency', 'USD'),
        'custom_data': custom_params or {},
        
        # 设备信息
        'user_agent': custom_params.get('user_agent', ''),
        'ip_address': custom_params.get('ip_address', ''),
        
        # 用户标识 (用于 Match Quality)
        'external_device_id': custom_params.get('external_id', ''),
        'hashed_email': self._hash_email(custom_params.get('email', '')),
        'hashed_phone': self._hash_phone(custom_params.get('phone', ''))
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    return r.json()


def _hash_email(self, email: str) -> str:
    """SHA-256 哈希邮箱"""
    if not email:
        return ''
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()


def _hash_phone(self, phone: str) -> str:
    """SHA-256 哈希电话"""
    if not phone:
        return ''
    # 移除所有非数字字符
    cleaned = ''.join(c for c in phone if c.isdigit())
    return hashlib.sha256(cleaned.encode()).hexdigest()
```

### 3.2 SDK 集成 (移动端)

```python
# Android/iOS SDK 配置
TIKTOK_SDK_CONFIG = {
    'app_id': 'YOUR_APP_ID',
    'app_version': '1.0.0',
    'sdk_version': '3.3.0',
    
    # 事件类型
    'events': {
        'PURCHASE': {
            'event_name': 'PURCHASE',
            'event_params': ['value', 'currency', 'content_id']
        },
        'ADD_TO_CART': {
            'event_name': 'ADD_TO_CART',
            'event_params': ['value', 'currency']
        },
        'INITIATE_CHECKOUT': {
            'event_name': 'INITIATE_CHECKOUT'
        }
    }
}


# 示例: Flutter 集成
def log_purchase_event(value: float, currency: str = 'USD',
                       contents: list = None):
    """记录购买事件"""
    import analytics  # TikTok Analytics SDK
    
    event_params = {
        'value': value,
        'currency': currency,
        'content_type': 'product',
        'contents': contents or []
    }
    
    analytics.track('Purchase', event_params)
```

---

## 四、报表查询与数据分析

### 4.1 Campaign 级报表

```python
def get_campaign_report(self, campaign_id: str,
                        date_from: str, date_to: str) -> list:
    """
    获取 Campaign 性能报表
    date_from/to: 'YYYY-MM-DD' 格式
    """
    url = f"{self.api_base}/report/campaign/"
    
    payload = {
        'access_token': self.token,
        'ad_account_id': self.account_id,
        'date_from': date_from,
        'date_to': date_to,
        'campaign_id': campaign_id,
        'fields': [
            'campaign_id', 'campaign_name', 'campaign_status',
            'spend', 'impressions', 'clicks', 'ctr', 'cpc',
            'conversions', 'conversion_rate', 'cost_per_conversion',
            'roas'
        ]
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    return r.json().get('data', {}).get('report', [])


def get_adgroup_report(self, adgroup_id: str,
                       date_from: str, date_to: str) -> list:
    """获取 Ad Group 级报表"""
    url = f"{self.api_base}/report/adgroup/"
    
    payload = {
        'access_token': self.token,
        'ad_account_id': self.account_id,
        'date_from': date_from,
        'date_to': date_to,
        'adgroup_id': adgroup_id,
        'fields': [
            'adgroup_id', 'adgroup_name', 'adgroup_status',
            'spend', 'impressions', 'clicks', 'ctr',
            'conversions', 'conversion_rate'
        ]
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    return r.json().get('data', {}).get('report', [])
```

### 4.2 创意表现分析

```python
def analyze_creative_performance(self, adgroup_id: str,
                                 days: int = 30) -> dict:
    """
    分析创意素材表现
    识别 Top/Bottom 创意
    """
    url = f"{self.api_base}/report/creative/"
    
    date_from = _days_ago(days)
    date_to = today()
    
    payload = {
        'access_token': self.token,
        'ad_account_id': self.account_id,
        'date_from': date_from,
        'date_to': date_to,
        'adgroup_id': adgroup_id,
        'fields': [
            'ad_id', 'ad_name', 'creative_type',
            'spend', 'impressions', 'clicks', 'ctr',
            'conversions', 'cost_per_conversion',
            'video_completion_rate', 'play_rate'
        ]
    }
    
    r = requests.post(url, json=payload, headers=self.headers)
    data = r.json().get('data', {}).get('report', [])
    
    # 分析 Top/Bottom 创意
    top_ads = sorted(data, key=lambda x: x.get('conversions', 0), reverse=True)[:5]
    bottom_ads = sorted(data, key=lambda x: x.get('ctr', 0))[:5]
    
    return {
        'total_creatives': len(data),
        'top_performers': top_ads,
        'underperformers': bottom_ads,
        'avg_ctr': sum(a.get('ctr', 0) for a in data) / max(len(data), 1),
        'avg_cpc': sum(a.get('cpc', 0) for a in data) / max(len(data), 1)
    }
```

---

## 五、批量操作与限流处理

### 5.1 智能限流器

```python
import asyncio
from collections import defaultdict

class TikTokRateLimiter:
    """TikTok API 限流器"""
    
    def __init__(self, max_requests_per_minute=30):
        self.max_rpm = max_requests_per_minute
        self.requests = defaultdict(list)
    
    def wait(self, account_id: str):
        """等待合适的请求间隔"""
        now = time.time()
        timestamps = self.requests[account_id]
        
        # 清理 1 分钟前的记录
        self.requests[account_id] = [
            t for t in timestamps if now - t < 60
        ]
        timestamps = self.requests[account_id]
        
        if len(timestamps) >= self.max_rpm:
            wait_time = 60 - (now - timestamps[0])
            if wait_time > 0:
                time.sleep(wait_time)
        
        self.requests[account_id].append(time.time())
    
    def execute_with_retry(self, func, account_id, *args, max_retries=3):
        """带重试的执行方法"""
        for attempt in range(max_retries):
            try:
                self.wait(account_id)
                return func(*args)
            except Exception as e:
                if '429' in str(e) or 'rate_limit' in str(e).lower():
                    wait = min(2 ** attempt * 10, 60)
                    print(f"⚠️ 限流，等待 {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                else:
                    raise
        raise Exception(f"重试 {max_retries} 次后失败")
```

### 5.2 批量创建示例

```python
def batch_create_campaigns(self, campaigns_config: list) -> list:
    """
    批量创建 Campaigns
    campaigns_config: [{name, budget, objective}, ...]
    """
    results = []
    limiter = TikTokRateLimiter(max_requests_per_minute=20)
    
    for i, config in enumerate(campaigns_config):
        try:
            limiter.execute_with_retry(
                self.create_campaign,
                self.account_id,
                name=config['name'],
                daily_budget=config['budget'],
                objective=config.get('objective', 'LEAD_GENERATION')
            )
            results.append({'index': i, 'status': 'success'})
            time.sleep(0.5)  # 额外缓冲
        except Exception as e:
            results.append({'index': i, 'status': 'error', 'error': str(e)})
    
    return results
```

---

## 六、生产环境最佳实践

### 6.1 代码质量检查清单

- [ ] 所有请求设置超时 (建议 30s)
- [ ] 实现指数退避重试
- [ ] 批量操作控制并发数 (建议 ≤5)
- [ ] 敏感信息使用环境变量存储
- [ ] 记录所有 API 调用日志
- [ ] Token 自动刷新机制

### 6.2 安全最佳实践

```python
import os
from dotenv import load_dotenv

load_dotenv()

# 从环境变量获取敏感信息
ACCESS_TOKEN = os.environ.get('TIKTOK_ACCESS_TOKEN')
ACCOUNT_ID = os.environ.get('TIKTOK_ACCOUNT_ID')
CLIENT_SECRET = os.environ.get('TIKTOK_CLIENT_SECRET')

# 不要硬编码
# ❌ ACCESS_TOKEN = 'your_token_here'
```

### 6.3 错误处理

```python
ERROR_HANDLING_MAP = {
    1001: ('认证失败', '检查 Access Token 是否有效'),
    1002: ('权限不足', '检查权限范围'),
    1101: ('账户不存在', '检查 Ad Account ID'),
    1201: ('参数错误', '检查请求参数'),
    1301: ('限流', '等待后重试'),
    1401: ('服务不可用', '稍后重试'),
}
```

---

## 参考资源

- [TikTok Business API 官方文档](https://business-api.tiktok.com/developer/docs)
- [Python SDK GitHub](https://github.com/TikTokAPI/TikTok-Business-API)
- [转换追踪指南](https://business-api.tiktok.com/developer/docs/en/business-growth/conversion-tracking)
- [受众定位指南](https://business-api.tiktok.com/developer/docs/en/business-growth/targeting)

---

## 总结

TikTok Ads API 成功的关键：

1. **快速测试素材** - 多创意组合找到胜者
2. **精准受众定位** - 兴趣/行为/排除都重要
3. **重视归因** - Pixel + SDK 双端追踪
4. **遵守限流** - 批量操作要控制节奏
