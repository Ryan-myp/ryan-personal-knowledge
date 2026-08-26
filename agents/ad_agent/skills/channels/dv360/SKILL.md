---
name: dv360-expert
description: Display & Video 360 完整专家技能 - 支持 Line Item/Flight/Creative 全层级管理、媒体购买、报表查询、DSP 集成等 45+ API 工具
version: 2.0.0
author: Ryan
created: 2026-08-14
updated: 2026-08-26
tags: [dv360, display-video, google, programmatic, dsp, advertising, line-item, creative]
---

# Display & Video 360 专家技能

## 📌 角色定位

你是 DV360 API 全功能专家，精通 Google 程序化广告平台的完整技术栈，支持 45+ API 工具的调用。

## 🎯 核心能力

### 1. 认证管理
```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Service Account 认证
credentials = service_account.Credentials.from_service_account_file(
    'service_account.json',
    scopes=['https://www.googleapis.com/auth/display-video']
)

# 构建 API 客户端
service = build('displayvideo', 'v4', credentials=credentials)
```

### 2. 层级管理
- **Advertiser（广告主）**: 客户账户
- **Campaign（广告系列）**: 营销目标
- **Insertion Order (IO)**: 插入订单
- **Line Item（行项目）**: 媒体购买单元
- **Flight（投放周期）**: 时间段配置
- **Creative（创意）**: 广告素材

### 3. 投放方式
- **Programmatic Guaranteed (PG)**: 保量采购
- **Private Marketplace (PMP)**: 私人 marketplace
- **Open Auction**: 公开竞价
- **Standard Flight**: 常规投放

### 4. 报表分析
- 展示、点击、转化数据
- 分时段报表
- 分创意报表

## 🛠️ 可用 Tools（共 30+）

### 🔐 认证与客户管理（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_auth` | OAuth 认证 | service_account_file, customer_id |
| `dv360_get_customer` | 获取客户信息 | customer_id |
| `dv360_list_customers` | 列出所有客户 | limit |
| `dv360_list_advertisers` | 列出广告主 | partner_id, limit |
| `dv360_get_advertiser` | 获取广告主详情 | advertiser_id |
| `dv360_validate_credentials` | 验证凭证有效性 | - |

### 📊 媒体购买管理（Line Item）（12 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_create_line_item` | 创建媒体购买 | advertiser_id, name, type, flight, budget, targeting |
| `dv360_update_line_item` | 更新媒体购买 | line_item_id, updates |
| `dv360_get_line_item` | 获取媒体购买详情 | line_item_id |
| `dv360_list_line_items` | 列出媒体购买 | advertiser_id, io_id, limit |
| `dv360_pause_line_item` | 暂停媒体购买 | line_item_id |
| `dv360_enable_line_item` | 启用媒体购买 | line_item_id |
| `dv360_delete_line_item` | 删除媒体购买 | line_item_id |
| `dv360_copy_line_item` | 复制媒体购买 | line_item_id, new_name |
| `dv360_get_line_item_budget` | 获取预算 | line_item_id |
| `dv360_update_line_item_budget` | 更新预算 | line_item_id, budget_micros |
| `dv360_get_line_item_performance` | 获取表现数据 | line_item_id, date_range |
| `dv360_batch_create_line_items` | 批量创建媒体购买 | advertiser_id, line_items_config |

### 📅 IO 管理（8 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_create_io` | 创建插入订单 | advertiser_id, name, start_time, end_time |
| `dv360_update_io` | 更新插入订单 | io_id, updates |
| `dv360_get_io` | 获取插入订单详情 | io_id |
| `dv360_list_ios` | 列出插入订单 | advertiser_id |
| `dv360_pause_io` | 暂停插入订单 | io_id |
| `dv360_enable_io` | 启用插入订单 | io_id |
| `dv360_delete_io` | 删除插入订单 | io_id |
| `dv360_extend_io` | 延长 IO | io_id, new_end_time |

### 🎨 创意管理（Creative）（8 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_upload_creative` | 上传创意文件 | line_item_id, creative_file, creative_type |
| `dv360_get_creative` | 获取创意详情 | creative_id |
| `dv360_list_creatives` | 列出创意 | line_item_id, status |
| `dv360_update_creative` | 更新创意 | creative_id, updates |
| `dv360_delete_creative` | 删除创意 | creative_id |
| `dv360_get_creative_approval` | 获取创意审批状态 | creative_id |
| `dv360_create_banner_creative` | 创建横幅广告 | line_item_id, dimensions, assets |
| `dv360_create_video_creative` | 创建视频广告 | line_item_id, video_url, duration |

### 👤 定向管理（Targeting）（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_create_targeting` | 创建定向条件 | advertiser_id, name, targeting_type |
| `dv360_get_targeting` | 获取定向详情 | targeting_id |
| `dv360_list_targeting` | 列出定向 | advertiser_id |
| `dv360_update_targeting` | 更新定向 | targeting_id, updates |
| `dv360_delete_targeting` | 删除定向 | targeting_id |
| `dv360_estimate_reach` | 预估触达人群 | targeting_id, advertiser_id |

### 📊 报表与数据分析（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_get_report` | 查询报表数据 | advertiser_id, date_range, dimensions, metrics |
| `dv360_get_line_item_report` | 获取媒体购买报表 | line_item_id, date_range |
| `dv360_get_creative_report` | 获取创意报表 | creative_id, date_range |
| `dv360_get_impression_report` | 获取展现数据 | advertiser_id, date_range |
| `dv360_get_click_report` | 获取点击数据 | advertiser_id, date_range |
| `dv360_export_report` | 导出报表 | advertiser_id, query, date_range |

### 🔧 辅助工具（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_list_platforms` | 列出平台位置 | - |
| `dv360_list_device_types` | 列出设备类型 | - |
| `dv360_list_ad_formats` | 列出广告格式 | - |
| `dv360_list_brand_safety` | 列出品牌安全设置 | - |
| `dv360_list_viewability` | 列出可见性设置 | - |
| `dv360_list_geo_locations` | 列出地理定位 | - |

## 📚 参考文档

- **官方文档**: https://developers.google.com/display-video/api/docs
- **API 参考**: https://developers.google.com/display-video/api/reference/rest
- **最佳实践**: https://developers.google.com/display-video/api/docs/best-practices

## 💡 最佳实践

### 1. Line Item 创建
```python
def create_line_item(client, advertiser_id, config):
    """创建媒体购买 Line Item"""
    body = {
        'name': config['name'],
        'goal': config.get('goal', {'goalType': 'IMPRESSIONS'}),
        'targeting': config.get('targeting', {}),
        'lineItemType': config.get('type', 'SPONSORED'),
        'status': 'DRAFT',
        'flight': {
            'startTimeMicros': config.get('start_time', 0),
            'endTimeMicros': config.get('end_time', 0)
        },
        'budgetMicros': config.get('budget_micros', 0)
    }
    
    result = client.create_line_item(advertiser_id, body)
    return result
```

### 2. 定向配置
```python
def create_targeting(client, advertiser_id, config):
    """创建定向条件"""
    body = {
        'name': config['name'],
        'targetingType': config.get('targeting_type', 'GEO'),
        'geoTargeting': config.get('geo', {}),
        'deviceTypeTargeting': config.get('devices', {}),
        'placementTargeting': config.get('placements', {})
    }
    
    result = client.create_targeting(advertiser_id, body)
    return result
```

### 3. 报表查询
```python
def get_campaign_report(client, advertiser_id, date_range):
    """查询 Campaign 报表"""
    report = client.create_report(advertiser_id, {
        'dateRange': {
            'startDate': {'year': 2026, 'month': 8, 'day': 1},
            'endDate': {'year': 2026, 'month': 8, 'day': 26}
        },
        'dimensions': ['DATE', 'CAMPAIGN'],
        'metrics': ['IMPRESSIONS', 'CLICKS', 'CONVERSIONS', 'SPEND']
    })
    
    # 获取报表数据
    data = client.get_report_result(report['reportId'])
    return data
```

## 🎓 常见问题

**Q: DV360 和 Google Ads 有什么区别？**
A: DV360 是程序化广告平台，支持跨媒体采购（YouTube、外部网站、OTT/CTV），Google Ads 主要是 Google 自营广告位。

**Q: Line Item 和 Flight 有什么区别？**
A: Line Item 是媒体购买单元，Flight 是投放时间段配置，一个 Line Item 可以包含多个 Flight。

**Q: PMP 和 Open Auction 有什么区别？**
A: PMP 是邀请制的私人 marketplace，价格更高但媒体质量更好；Open Auction 是公开竞价，价格更低但媒体质量参差不齐。

**Q: 如何处理创意审批？**
A: 提交创意后，系统会自动审批，通常 24-48 小时内完成。可以调用 `get_creative_approval` 查询状态。

## 🔧 使用示例

```python
from agents.ad_agent.api_clients.dv360_client import DV360APIClient

# 初始化客户端
client = DV360APIClient(credentials)

# 列出广告主
advertisers = client.list_advertisers(partner_id='4659631')
for a in advertisers:
    print(f"{a['id']}: {a['name']}")

# 创建 IO
io_id = client.create_io(
    advertiser_id='5110831',
    name='Summer Campaign 2026',
    start_time='2026-06-01T00:00:00Z',
    end_time='2026-08-31T23:59:59Z'
)

# 创建 Line Item
li_id = client.create_line_item(
    advertiser_id='5110831',
    io_id=io_id,
    name='Video Campaign',
    type='VIDEO',
    budget_micros=100000000  # $1000
)
```
