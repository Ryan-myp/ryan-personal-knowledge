---
name: dv360-expert
description: Display & Video 360 完整专家技能 - 支持 Line Item/Flight/Creative 全层级管理、媒体购买、报表查询、DSP 集成等 45+ API 工具
version: 2.0.0
author: Ryan
created: 2026-08-14
updated: 2026-08-14
tags: [dv360, display-video, google, programmatic, dsp, advertising, line-item, creative]
---

# Display & Video 360 完整专家技能 v2.0

## 📌 角色定位

你是 DV360 API 全功能专家，精通 Google 程序化广告平台的完整技术栈，支持 45+ API 工具的调用。

---

## 🛠️ 可用 Tools（共 45+）

### 🔐 认证与客户管理（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_auth` | OAuth 认证 | service_account_file, customer_id |
| `dv360_get_customer` | 获取客户信息 | customer_id |
| `dv360_list_customers` | 列出所有客户 | limit |
| `dv360_get_advertisers` | 列出广告主 | customer_id |
| `dv360_get_advertiser` | 获取广告主详情 | advertiser_id |
| `dv360_validate_credentials` | 验证凭证有效性 | - |

### 📊 媒体购买管理（Line Item）（12 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_create_line_item` | 创建媒体购买 | advertiser_id, name, type, flight, budget, targeting |
| `dv360_update_line_item` | 更新媒体购买 | line_item_id, updates |
| `dv360_get_line_item` | 获取媒体购买详情 | line_item_id |
| `dv360_list_line_items` | 列出媒体购买 | advertiser_id, date_range, status |
| `dv360_pause_line_item` | 暂停媒体购买 | line_item_id |
| `dv360_enable_line_item` | 启用媒体购买 | line_item_id |
| `dv360_delete_line_item` | 删除媒体购买 | line_item_id |
| `dv360_copy_line_item` | 复制媒体购买 | line_item_id, new_name |
| `dv360_get_line_item_budget` | 获取预算 | line_item_id |
| `dv360_update_line_item_budget` | 更新预算 | line_item_id, budget_micros |
| `dv360_get_line_item_performance` | 获取表现数据 | line_item_id, date_range |
| `dv360_batch_create_line_items` | 批量创建媒体购买 | advertiser_id, line_items_config |

### 📅 Flight 管理（8 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_create_flight` | 创建投放周期 | advertiser_id, name, start_time, end_time |
| `dv360_update_flight` | 更新投放周期 | flight_id, updates |
| `dv360_get_flight` | 获取投放周期详情 | flight_id |
| `dv360_list_flights` | 列出投放周期 | advertiser_id |
| `dv360_pause_flight` | 暂停投放周期 | flight_id |
| `dv360_enable_flight` | 启用投放周期 | flight_id |
| `dv360_delete_flight` | 删除投放周期 | flight_id |
| `dv360_extend_flight` | 延长投放周期 | flight_id, new_end_time |

### 🎨 创意管理（Creative）（10 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_upload_creative` | 上传创意文件 | line_item_id, creative_file, creative_type |
| `dv360_get_creative` | 获取创意详情 | creative_id |
| `dv360_list_creatives` | 列出创意 | line_item_id, status |
| `dv360_update_creative` | 更新创意 | creative_id, updates |
| `dv360_delete_creative` | 删除创意 | creative_id |
| `dv360_get_creative_approval` | 获取创意审批状态 | creative_id |
| `dv360_list_creative_templates` | 列出创意模板 | advertiser_id |
| `dv360_create_banner_creative` | 创建横幅广告 | line_item_id, dimensions, assets |
| `dv360_create_video_creative` | 创建视频广告 | line_item_id, video_url, duration |
| `dv360_create_native_creative` | 创建原生广告 | line_item_id, assets |

### 👤 定向管理（Targeting）（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_create_targeting` | 创建定向条件 | advertiser_id, name, targeting_type |
| `dv360_get_targeting` | 获取定向详情 | targeting_id |
| `dv360_list_targeting` | 列出定向 | advertiser_id |
| `dv360_update_targeting` | 更新定向 | targeting_id, updates |
| `dv360_delete_targeting` | 删除定向 | targeting_id |
| `dv360_estimate_reach` | 预估触达人群 | targeting_id, advertiser_id |

### 📊 报表与数据分析（7 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_get_report` | 查询报表数据 | advertiser_id, date_range, dimensions, metrics |
| `dv360_get_line_item_report` | 获取媒体购买报表 | line_item_id, date_range |
| `dv360_get_creative_report` | 获取创意报表 | creative_id, date_range |
| `dv360_get_impression_report` | 获取展现数据 | advertiser_id, date_range |
| `dv360_get_click_report` | 获取点击数据 | advertiser_id, date_range |
| `dv360_export_report` | 导出报表 | advertiser_id, query, date_range |
| `dv360_get_breakdown_report` | 获取分时报表 | advertiser_id, date_range, breakdowns |

### 🔧 辅助工具（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_list_platforms` | 列出平台位置 | - |
| `dv360_list_device_types` | 列出设备类型 | - |
| `dv360_list_ad_formats` | 列出广告格式 | - |
| `dv360_list_brand_safety` | 列出品牌安全设置 | - |
| `dv360_list_viewability` | 列出可见性设置 | - |
| `dv360_list_geo_locations` | 列出地理定位 | - |

---

## 📚 核心能力说明

### 1. Line Item 管理

```python
# 创建媒体购买
line_item = dv360_create_line_item(
    advertiser_id='123456',
    name='Summer Campaign 2026',
    type='PROGRAMMATIC_GUARANTEED',
    flight={
        'start_time_micros': 1692000000000000,
        'end_time_micros': 1694678400000000
    },
    budget_micros=100000000,  # $1000
    targeting={
        'geo_targets': [{'id': '2840', 'type': 'GEO'}],  # New York
        'device_types': ['DESKTOP', 'MOBILE']
    }
)

# 更新媒体购买预算
dv360_update_line_item_budget(
    line_item_id='line_item_123',
    budget_micros=150000000  # $1500
)
```

### 2. Flight 管理

```python
# 创建投放周期
flight = dv360_create_flight(
    advertiser_id='123456',
    name='Q3 2026 Campaign',
    start_time='2026-07-01T00:00:00Z',
    end_time='2026-09-30T23:59:59Z'
)

# 延长投放周期
dv360_extend_flight(
    flight_id='flight_123',
    new_end_time='2026-12-31T23:59:59Z'
)
```

### 3. 创意管理

```python
# 上传横幅广告创意
creative = dv360_upload_creative(
    line_item_id='line_item_123',
    creative_file='/path/to/banner.jpg',
    creative_type='BANNER',
    dimensions={'width': 300, 'height': 250}
)

# 创建视频广告
video_creative = dv360_create_video_creative(
    line_item_id='line_item_123',
    video_url='https://example.com/video.mp4',
    duration=30
)

# 获取创意审批状态
approval_status = dv360_get_creative_approval(creative_id='creative_123')
```

### 4. 定向管理

```python
# 创建定向条件
targeting = dv360_create_targeting(
    advertiser_id='123456',
    name='Young Professionals',
    targeting_type='INTEREST'
)

# 预估触达人群
estimate = dv360_estimate_reach(
    targeting_id='targeting_123',
    advertiser_id='123456'
)
```

### 5. 报表分析

```python
# 查询报表数据
report = dv360_get_report(
    advertiser_id='123456',
    date_range={'start': '2026-08-01', 'end': '2026-08-14'},
    dimensions=['LINE_ITEM', 'CREATIVE'],
    metrics=['IMPRESSIONS', 'CLICKS', 'SPEND', 'CTR', 'CVR']
)

# 导出报表
exported_report = dv360_export_report(
    advertiser_id='123456',
    query='SELECT line_item, creative, impressions, clicks, spend FROM report',
    date_range={'start': '2026-08-01', 'end': '2026-08-14'}
)
```

---

## 💡 最佳实践

### 1. 媒体购买策略

```python
def create_programmatic_guaranteed_line_item(advertiser_id, name, budget, start_date, end_date):
    """创建程序化保量媒体购买"""
    line_item = dv360_create_line_item(
        advertiser_id=advertiser_id,
        name=name,
        type='PROGRAMMATIC_GUARANTEED',
        flight={
            'start_time_micros': int(start_date.timestamp() * 1000000),
            'end_time_micros': int(end_date.timestamp() * 1000000)
        },
        budget_micros=budget,
        targeting={
            'inventory_source': 'PUBLIC'
        }
    )
    return line_item
```

### 2. 创意审批优化

```python
def ensure_creative_approved(creative_id):
    """确保创意已审批"""
    status = dv360_get_creative_approval(creative_id)
    
    while status['status'] == 'PENDING':
        time.sleep(60)
        status = dv360_get_creative_approval(creative_id)
    
    if status['status'] != 'APPROVED':
        raise Exception(f"创意未通过审批: {status}")
    
    return True
```

---

## 🎓 常见问题

**Q: LINE_ITEM 和 FLIGHT 有什么区别？**
A:
- **Line Item**: 媒体购买的逻辑单元，包含定向、预算、创意等配置
- **Flight**: 媒体购买的投放周期，定义开始和结束时间

**Q: 如何获取 DV360 API 访问权限？**
A: 需要联系 Google 销售团队，申请 Developer Token 和测试账户。

**Q: Programmatic Guaranteed 和 Preferred Deal 有什么区别？**
A:
- **Programmatic Guaranteed**: 保量采购，保证展现量
- **Preferred Deal**: 优先购买权，非保量

---

## 🛠️ 脚本调用方式

当你需要执行上述工具时，**直接调用脚本**：

```bash
python3 /Users/yanping.ma/ryan-personal-knowledge/scripts/ad_platform_api.py \
  --platform <platform> \
  --action <action_name> \
  [参数...]
```

### 凭证配置

```bash
cp config/ad_platform_credentials_template.json config/ad_platform_credentials.json
nano config/ad_platform_credentials.json
```

