---
name: ad-platform-tools
description: 广告平台通用工具集，提供统一认证管理、多平台 API 调用、数据同步、报表聚合等跨平台工具能力
version: 1.0.0
author: Ryan
created: 2026-08-14
tags: [ads, tools, api, multi-platform, authentication, reporting]
---

# 广告平台通用工具集

## 📌 工具集定位

为 TikTok、Meta、Google Ads、DV360 四大广告平台提供统一的 API 调用工具，简化开发流程，提升效率。

## 🎯 核心功能

### 1. 统一认证管理
```python
from ad_platform_tools import AdPlatformManager

manager = AdPlatformManager()

# 配置各平台凭证
manager.configure('tiktok', app_key='...', app_secret='...')
manager.configure('meta', app_id='...', app_secret='...')
manager.configure('google', developer_token='...', customer_id='...')
manager.configure('dv360', service_account_file='...')
```

### 2. 跨平台数据同步
```python
# 同步账户信息
accounts = manager.sync_accounts()

# 同步广告系列
campaigns = manager.sync_campaigns(account_ids)
```

### 3. 统一报表聚合
```python
# 获取多平台报表
reports = manager.get_reports(
    platform='all',
    date_range={'start': '2026-01-01', 'end': '2026-08-14'},
    metrics=['impressions', 'clicks', 'conversions', 'spend']
)
```

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `auth_configure` | 配置平台凭证 | platform, credentials |
| `auth_test` | 测试连接 | platform |
| `sync_accounts` | 同步账户信息 | platforms |
| `sync_campaigns` | 同步广告系列 | account_ids, platforms |
| `sync_ad_groups` | 同步广告组 | campaign_ids, platforms |
| `sync_ads` | 同步广告创意 | ad_group_ids, platforms |
| `get_report` | 查询报表 | platform, account_id, date_range, metrics |
| `aggregate_report` | 聚合多平台报表 | account_ids, date_range, metrics |
| `track_event` | 追踪转化事件 | platform, pixel_id, event_data |
| `list_creatives` | 列出创意资产 | platform, account_id |
| `upload_creative` | 上传创意文件 | platform, account_id, file_path |
| `manage_budget` | 管理预算 | platform, account_id, budget |

## 📚 支持的插件

| 插件 | 描述 | 状态 |
|------|------|------|
| `tiktok-ads-expert` | TikTok Ads API 专家技能 | ✅ 已配置 |
| `meta-marketing-api-expert` | Meta Marketing API 专家技能 | ✅ 已配置 |
| `google-ads-api-expert` | Google Ads API 专家技能 | ✅ 已配置 |
| `dv360-expert` | Display & Video 360 专家技能 | ✅ 已配置 |

## 💡 使用示例

### 1. 配置平台凭证
```python
from ad_platform_tools import AdPlatformManager

manager = AdPlatformManager()

# TikTok
manager.configure('tiktok', {
    'app_key': 'your_app_key',
    'app_secret': 'your_app_secret',
    'access_token': 'your_access_token'
})

# Meta
manager.configure('meta', {
    'app_id': 'your_app_id',
    'app_secret': 'your_app_secret',
    'access_token': 'your_access_token'
})

# Google Ads
manager.configure('google', {
    'developer_token': 'your_developer_token',
    'client_id': 'your_client_id',
    'client_secret': 'your_client_secret',
    'refresh_token': 'your_refresh_token',
    'customer_id': 'your_customer_id'
})

# DV360
manager.configure('dv360', {
    'service_account_file': 'path/to/service-account.json',
    'customer_id': 'your_customer_id'
})
```

### 2. 测试连接
```python
# 测试所有平台连接
results = manager.test_connections()
for platform, status in results.items():
    print(f"{platform}: {status}")
```

### 3. 同步数据
```python
# 同步所有账户
accounts = manager.sync_accounts(platforms=['tiktok', 'meta', 'google', 'dv360'])
print(f"同步了 {len(accounts)} 个账户")

# 同步广告系列
campaigns = manager.sync_campaigns(
    account_ids=[acc['id'] for acc in accounts],
    platforms=['tiktok', 'meta', 'google']
)
print(f"同步了 {len(campaigns)} 个广告系列")
```

### 4. 查询报表
```python
# 获取单个平台报表
report = manager.get_report(
    platform='google',
    account_id='123456789',
    date_range={'start': '2026-08-01', 'end': '2026-08-14'},
    metrics=['impressions', 'clicks', 'conversions', 'cost']
)

# 聚合多平台报表
aggregate = manager.aggregate_report(
    account_ids=['tiktok-123', 'meta-456', 'google-789'],
    date_range={'start': '2026-08-01', 'end': '2026-08-14'},
    metrics=['impressions', 'clicks', 'conversions', 'spend', 'roas']
)
```

### 5. 追踪转化事件
```python
# TikTok Pixel
manager.track_event(
    platform='tiktok',
    pixel_id='pixel_123',
    event_data={
        'event_name': 'Purchase',
        'value': 99.99,
        'currency': 'USD',
        'user_email': 'user@example.com'
    }
)

# Meta CAPI
manager.track_event(
    platform='meta',
    pixel_id='pixel_456',
    event_data={
        'event_name': 'CompleteRegistration',
        'value': 0,
        'currency': 'USD',
        'user_data': {
            'email': 'user@example.com',
            'phone': '1234567890'
        }
    }
)
```

## 🔐 凭证管理

### 1. 环境变量配置
```bash
# .env 文件
TIKTOK_APP_KEY=your_app_key
TIKTOK_APP_SECRET=your_app_secret
TIKTOK_ACCESS_TOKEN=your_access_token

META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
META_ACCESS_TOKEN=your_access_token

GOOGLE_DEVELOPER_TOKEN=your_developer_token
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REFRESH_TOKEN=your_refresh_token
GOOGLE_CUSTOMER_ID=your_customer_id

DV360_SERVICE_ACCOUNT_FILE=path/to/service-account.json
DV360_CUSTOMER_ID=your_customer_id
```

### 2. 安全存储建议
- 使用密钥管理服务（AWS Secrets Manager、Azure Key Vault）
- 不要在代码中硬编码凭证
- 定期轮换 Access Token
- 限制 API 权限范围

## ⚠️ 注意事项

1. **速率限制**: 各平台都有 API 调用限制，请合理控制请求频率
2. **凭证安全**: 妥善保管凭证信息，不要提交到版本控制系统
3. **错误处理**: 实现完善的错误处理和重试机制
4. **数据合规**: 遵守各平台的数据使用政策
5. **版权合规**: 仅获取公开的技术文档和 API 数据
