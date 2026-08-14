# DV360 (Display & Video 360) API 专家级指南 2025

> 基于 Google Display & Video 360 REST API 官方文档蒸馏 | DSP 最佳实践

---

## 一、API 架构核心认知

### 1.1 账户层级结构

```
Partner (MCN/Agency)
└── Advertiser
    ├── Insertion Order (IO) - 类似 Campaign
    │   ├── Line Item - 广告投放单元
    │   │   ├── Flight - 时间段
    │   │   └── Creative - 创意素材
    │   └── Custom Channel (可选)
    └── Reported Custom Channel (RCCH)
```

### 1.2 核心概念

| 概念 | 说明 |
|------|------|
| **Partner** | 代理商/合作伙伴 (MCN) |
| **Advertiser** | 广告主 |
| **Insertion Order (IO)** | 预算单元，类似 Campaign |
| **Line Item** | 具体的投放单元 |
| **Flight** | 时间段控制 |
| **Creative** | 广告创意 |
| **Serving Summary** | 实际投放报告 |

### 1.3 API 端点与版本

```
Base URL: https://displayvideo.googleapis.com/v4
Version: v4 (当前稳定版本)
```

---

## 二、认证与授权

### 2.1 OAuth 2.0 认证

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def create_dv360_client(client_email: str, private_key: str, 
                        partner_id: int, advertiser_id: int):
    """
    创建 DV360 API Client
    使用 Service Account 认证
    """
    credentials = Credentials(
        token_uri="https://oauth2.googleapis.com/token",
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        refresh_token="YOUR_REFRESH_TOKEN"
    )
    
    # 构建 service
    service = build(
        'displayvideo',
        'v4',
        credentials=credentials
    )
    
    return {
        'service': service,
        'partner_id': partner_id,
        'advertiser_id': advertiser_id
    }


def list_advertisers(client) -> list:
    """列出 Advertisers"""
    service = client['service']
    partner_id = client['partner_id']
    
    request = service.partners().advertisers().list(
        parent=f'partners/{partner_id}'
    )
    response = request.execute()
    
    return response.get('advertisers', [])
```

### 2.2 权限范围

```python
DV360_SCOPES = [
    'https://www.googleapis.com/auth/display-video',
    'https://www.googleapis.com/auth/display-video-user-management',
]
```

---

## 三、Insertion Order (IO) 管理

### 3.1 创建 IO (Campaign 级别)

```python
def create_insertion_order(client, name: str, 
                            budget_micros: int,
                            start_date: str, end_date: str = None) -> dict:
    """
    创建 Insertion Order (类似 Campaign)
    budget_micros: 预算 (micros, 即 1e6 = $1)
    """
    service = client['service']
    advertiser_id = client['advertiser_id']
    
    body = {
        'name': name,
        'advertiser': f'advertisers/{advertiser_id}',
        'standard_ad_server_buying_type': 'DIRECT',
        'partner_id': client['partner_id'],
        
        # 预算设置
        'billing_setup': {
            'billing_type': 'CPM'  # CPM / CPA / CPC
        },
        
        # 时间设置
        'flight': {
            'start_time': f'{start_date}T00:00:00Z',
            'end_time': f'{end_date}T00:00:00Z' if end_date else None,
            'timezone_id': 'UTC'
        }
    }
    
    request = service.partners().insertionOrders().create(
        parent=f'partners/{client["partner_id"]}',
        body=body
    )
    response = request.execute()
    
    print(f"✅ IO created: {response.get('name')}")
    return response


def list_insertion_orders(client, limit: int = 10) -> list:
    """列出 IOs"""
    service = client['service']
    
    request = service.partners().insertionOrders().list(
        parent=f'partners/{client["partner_id"]}',
        pageSize=limit
    )
    response = request.execute()
    
    return response.get('insertionOrders', [])


def update_io_status(client, io_id: str, status: str) -> dict:
    """更新 IO 状态"""
    service = client['service']
    
    body = {
        'status': status  # DRAFT / APPROVED / REJECTED / REMOVED
    }
    
    request = service.partners().insertionOrders().patch(
        name=f'partners/{client["partner_id"]}/insertionOrders/{io_id}',
        body=body
    )
    return request.execute()
```

---

## 四、Line Item 管理

### 4.1 创建 Line Item

```python
def create_line_item(client, io_id: str, name: str,
                     bidding_strategy: str = 'OPTIMIZED_CPM',
                     bid_amount_micros: int = None) -> dict:
    """
    创建 Line Item
    bidding_strategy: 
      - OPTIMIZED_CPM (推荐)
      - FLIGHT_CPM
      - FLIGHT_CPC
      - FIXED_RATE
    """
    service = client['service']
    
    body = {
        'name': name,
        'insertion_order': f'partners/{client["partner_id"]}/insertionOrders/{io_id}',
        
        # 出价策略
        'bidding_strategy': bidding_strategy,
        
        # 预算 (如不设置则使用 IO 预算)
        # 'line_item_budget_micros': bid_amount_micros,
        
        # 目标设置
        'targeting_setting': {
            'targeting_restriction': 'NONE'  # NONE / RESTRICT
        },
        
        # 创意大小要求
        'creative_viewability_match_type': 'VIEWABLE',
        
        # 可见性目标 (0-100)
        # 'viewability_target_percentage': 70
    }
    
    if bid_amount_micros:
        body['cpc_bid_micros'] = bid_amount_micros
        body['cpm_bid_micros'] = bid_amount_micros * 1000  # CPM 需要换算
    
    request = service.partners().insertionOrders().lineItems().create(
        parent=f'partners/{client["partner_id"]}/insertionOrders/{io_id}',
        body=body
    )
    response = request.execute()
    
    print(f"✅ Line Item created: {response.get('name')}")
    return response


def list_line_items(client, io_id: str, limit: int = 10) -> list:
    """列出 Line Items"""
    service = client['service']
    
    request = service.partners().insertionOrders().lineItems().list(
        parent=f'partners/{client["partner_id"]}/insertionOrders/{io_id}',
        pageSize=limit
    )
    response = request.execute()
    
    return response.get('lineItems', [])
```

### 4.2 Audience Targeting (受众定向)

```python
def set_audience_targeting(client, line_item_id: str,
                           audience_configs: list) -> dict:
    """
    设置受众定向
    audience_configs: [
        {
            'type': 'DEMOGRAPHIC',
            'gender': 'MALE',
            'age_range': '18-34'
        },
        {
            'type': 'INTEREST',
            'interest_id': '12345'
        }
    ]
    """
    service = client['service']
    partner_id = client['partner_id']
    
    body = {
        'targeting_setting': {
            'targeting_restriction': 'TARGETING',
            'audience_targeting': {
                'positive_targeting': {
                    'demographic_targetings': [],
                    'interest_targetings': [],
                    'keyword_targetings': []
                },
                'negative_targeting': {
                    'demographic_targetings': [],
                    'interest_targetings': [],
                    'keyword_targetings': []
                }
            }
        }
    }
    
    for config in audience_configs:
        if config['type'] == 'DEMOGRAPHIC':
            body['targeting_setting']['audience_targeting']['positive_targeting']['demographic_targetings'].append({
                'gender': config.get('gender'),
                'age_range': config.get('age_range')
            })
        elif config['type'] == 'INTEREST':
            body['targeting_setting']['audience_targeting']['positive_targeting']['interest_targetings'].append({
                'interest_segment_id': config.get('interest_id')
            })
        elif config['type'] == 'KEYWORD':
            body['targeting_setting']['audience_targeting']['positive_targeting']['keyword_targetings'].append({
                'keyword': config.get('keyword')
            })
    
    request = service.partners().insertionOrders().lineItems().patch(
        name=f'partners/{partner_id}/insertionOrders/{client["io_id"]}/lineItems/{line_item_id}',
        body={'targetingSetting': body['targeting_setting']}
    )
    return request.execute()
```

---

## 五、Creative 管理

### 5.1 创建视频创意

```python
def create_video_creative(client, line_item_id: str,
                          name: str, 
                          video_url: str,
                          duration_seconds: int = 30) -> dict:
    """
    创建视频创意
    video_url: Google Cloud Storage 路径或上传后的 URL
    """
    service = client['service']
    
    body = {
        'name': name,
        'line_item': f'partners/{client["partner_id"]}/insertionOrders/{client["io_id"]}/lineItems/{line_item_id}',
        
        # 视频信息
        'video': {
            'video_id': video_url.split('/')[-1],
            'duration_millis': duration_seconds * 1000,
            
            # 缩略图 (可选)
            # 'thumbnail': {
            #     'image_id': 'thumbnail_url'
            # }
        },
        
        # 品牌安全设置
        'brand_safety_settings': {
            'brand_safety_vendor_id': 1,  # 标准级别
            'brand_safety_visibility': {
                'min_viewable_percent': 70  # 最小可见度 70%
            }
        },
        
        # 广告格式
        'ad_format': 'VIDEO_SKIPPABLE'  # SKIPPABLE / NON_SKIPPABLE / BANNER
    }
    
    request = service.partners().insertionOrders().lineItems().creatives().create(
        parent=f'partners/{client["partner_id"]}/insertionOrders/{client["io_id"]}/lineItems/{line_item_id}',
        body=body
    )
    response = request.execute()
    
    print(f"✅ Video Creative created: {response.get('name')}")
    return response


def create_banner_creative(client, line_item_id: str,
                           name: str, image_url: str,
                           width: int = 300, height: int = 250) -> dict:
    """创建 Banner 创意"""
    service = client['service']
    
    body = {
        'name': name,
        'line_item': f'partners/{client["partner_id"]}/insertionOrders/{client["io_id"]}/lineItems/{line_item_id}',
        
        # Banner 信息
        'banner': {
            'image': image_url,
            'width': width,
            'height': height
        },
        
        # 尺寸规格
        'size': {
            'width': width,
            'height': height
        }
    }
    
    request = service.partners().insertionOrders().lineItems().creatives().create(
        parent=f'partners/{client["partner_id"]}/insertionOrders/{client["io_id"]}/lineItems/{line_item_id}',
        body=body
    )
    return request.execute()
```

### 5.2 创意审核与发布

```python
def review_creative(client, creative_id: str, approve: bool = True) -> dict:
    """审核创意"""
    service = client['service']
    
    body = {
        'status': 'APPROVED' if approve else 'REJECTED',
        'review_comment': 'Approved for campaign' if approve else 'Needs revision'
    }
    
    request = service.partners().insertionOrders().lineItems().creativs().patch(
        name=f'partners/{client["partner_id"]}/insertionOrders/{client["io_id"]}/lineItems/{client["line_item_id"]}/creatives/{creative_id}',
        body=body
    )
    return request.execute()


def get_creative_status(client, creative_id: str) -> dict:
    """获取创意审核状态"""
    service = client['service']
    
    request = service.partners().insertionOrders().lineItems().creatives().get(
        name=f'partners/{client["partner_id"]}/insertionOrders/{client["io_id"]}/lineItems/{client["line_item_id"]}/creatives/{creative_id}'
    )
    return request.execute()
```

---

## 六、报表与数据分析

### 6.1 Serving Summary (投放报告)

```python
def get_serving_summary(client, start_date: str, end_date: str,
                        group_by: list = None) -> dict:
    """
    获取投放总结报告
    group_by: ['DATE', 'LINE_ITEM', 'CREATIVE', 'CHANNEL']
    """
    service = client['service']
    
    body = {
        'filter_date_range': {
            'start_date': {'day': int(start_date.split('-')[2]), 
                          'month': int(start_date.split('-')[1]), 
                          'year': int(start_date.split('-')[0])},
            'end_date': {'day': int(end_date.split('-')[2]), 
                        'month': int(end_date.split('-')[1]), 
                        'year': int(end_date.split('-')[0])}
        },
        'dimension_filters': [],
        'group_by': group_by or ['DATE']
    }
    
    request = service.partners().insertionOrders().servingSummary().query(
        parent=f'partners/{client["partner_id"]}/insertionOrders/{client["io_id"]}',
        body=body
    )
    response = request.execute()
    
    return response.get('servingSummary', {})


def get_line_item_report(client, io_id: str, 
                         start_date: str, end_date: str) -> dict:
    """获取 Line Item 级别报表"""
    service = client['service']
    
    body = {
        'filter_date_range': {
            'start_date': parse_date(start_date),
            'end_date': parse_date(end_date)
        },
        'line_item_filter': {
            'line_item_names': ['*']  # 匹配所有
        },
        'metrics': [
            'SERVED_IMPRESSIONS',
            'SPEND_MICROS',
            'CLICKS',
            'VIEWABLE_IMPRESSIONS',
            'CTR',
            'CPM',
            'COMPLETE_VIEWS'
        ]
    }
    
    request = service.partners().insertionOrders().servingSummary().query(
        parent=f'partners/{client["partner_id"]}/insertionOrders/{io_id}',
        body=body
    )
    return request.execute()
```

### 6.2 渠道表现分析

```python
def analyze_channel_performance(client, io_id: str, 
                                start_date: str, end_date: str) -> dict:
    """分析各渠道表现"""
    service = client['service']
    
    body = {
        'filter_date_range': {
            'start_date': parse_date(start_date),
            'end_date': parse_date(end_date)
        },
        'dimension_filters': [{
            'dimension': 'CHANNEL',
            'values': ['YOUTUBE', 'DISPLAY', 'TV']
        }],
        'group_by': ['CHANNEL'],
        'metrics': [
            'SERVED_IMPRESSIONS',
            'SPEND_MICROS',
            'CTR',
            'CPM',
            'VIEW_THROUGH_RATE'
        ]
    }
    
    request = service.partners().insertionOrders().servingSummary().query(
        parent=f'partners/{client["partner_id"]}/insertionOrders/{io_id}',
        body=body
    )
    return request.execute()
```

---

## 七、Creative Media API (素材上传)

### 7.1 上传视频素材

```python
def upload_video_to_gcs(client, file_path: str, 
                        folder: str = 'creatives') -> str:
    """
    上传视频到 Google Cloud Storage
    这是 DV360 创建视频创意的必要步骤
    """
    from google.cloud import storage
    
    # 初始化 GCS client
    storage_client = storage.Client()
    bucket_name = f'dv360-{client["partner_id"]}'
    bucket = storage_client.bucket(bucket_name)
    
    # 生成文件名
    filename = f'{folder}/{int(time.time())}_{os.path.basename(file_path)}'
    blob = bucket.blob(filename)
    
    # 上传
    blob.upload_from_filename(file_path)
    
    # 获取公开 URL
    blob.make_public()
    return blob.public_url


def upload_image_to_gcs(client, file_path: str) -> str:
    """上传图片到 GCS"""
    from google.cloud import storage
    
    storage_client = storage.Client()
    bucket_name = f'dv360-{client["partner_id"]}'
    bucket = storage_client.bucket(bucket_name)
    
    filename = f'images/{int(time.time())}_{os.path.basename(file_path)}'
    blob = bucket.blob(filename)
    
    blob.upload_from_filename(file_path)
    blob.make_public()
    
    return blob.public_url
```

---

## 八、生产环境最佳实践

### 8.1 性能优化

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class DV360BatchProcessor:
    """DV360 批量处理工具"""
    
    def __init__(self, client, batch_size=10):
        self.client = client
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    async def batch_create_line_items(self, io_id: str, 
                                       line_items: list) -> list:
        """批量创建 Line Items"""
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(
                self.executor,
                self._create_single_line_item,
                io_id, item
            )
            for item in line_items
        ]
        return await asyncio.gather(*futures)
    
    def _create_single_line_item(self, io_id: str, config: dict) -> dict:
        """创建单个 Line Item"""
        service = self.client['service']
        
        body = {
            'name': config['name'],
            'insertion_order': f'partners/{self.client["partner_id"]}/insertionOrders/{io_id}',
            'bidding_strategy': config.get('bidding_strategy', 'OPTIMIZED_CPM')
        }
        
        request = service.partners().insertionOrders().lineItems().create(
            parent=f'partners/{self.client["partner_id"]}/insertionOrders/{io_id}',
            body=body
        )
        return request.execute()
```

### 8.2 错误处理

```python
DV360_ERROR_CODES = {
    400: ('INVALID_ARGUMENT', '参数错误，检查请求格式'),
    401: ('UNAUTHENTICATED', '认证失败，检查 Token'),
    403: ('PERMISSION_DENIED', '权限不足，检查 Service Account'),
    404: ('NOT_FOUND', '资源不存在，检查 ID'),
    429: ('RATE_LIMITED', '限流，等待重试'),
    500: ('INTERNAL_ERROR', '服务端错误'),
    503: ('SERVICE_UNAVAILABLE', '服务不可用'),
}
```

---

## 参考资源

- [DV360 API 官方文档](https://developers.google.com/display-video/api/guides)
- [REST API Reference](https://developers.google.com/display-video/api/reference/rest)
- [Python Client Library](https://googleapis.dev/python/displayvideo/latest/)

---

## 总结

DV360 API 使用的关键点：

1. **Service Account 认证** - 需要 Google Cloud 项目配置
2. **GCS 素材管理** - 视频/图片需先上传到 GCS
3. **Creative Review 流程** - 创意需要审核才能投放
4. **Serving Summary 报表** - 详细的投放表现数据
