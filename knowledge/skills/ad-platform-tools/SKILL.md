---
name: ad-platform-tools
description: 广告平台统一工具集 - 跨平台认证管理、数据同步、报表聚合、事件追踪等 30+ 通用工具
version: 2.0.0
author: Ryan
created: 2026-08-14
updated: 2026-08-14
tags: [ads, tools, api, multi-platform, authentication, reporting, sync, unified]
---

# 广告平台统一工具集 v2.0

## 📌 工具集定位

为 TikTok、Meta、Google Ads、DV360 四大广告平台提供统一的 API 调用工具，简化开发流程，提升效率。

---

## 🛠️ 可用 Tools（共 30+）

### 🔐 统一认证管理（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `auth_configure` | 配置平台凭证 | platform, credentials |
| `auth_test` | 测试连接 | platform |
| `auth_refresh` | 刷新所有 Token | platform |
| `auth_list_configured` | 列出已配置平台 | - |
| `auth_get_token` | 获取指定平台 Token | platform |
| `auth_clear_credentials` | 清除凭证 | platform |

### 📊 跨平台数据同步（8 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `sync_accounts` | 同步所有账户 | platforms, force_refresh |
| `sync_campaigns` | 同步广告系列 | account_ids, platforms, date_range |
| `sync_ad_groups` | 同步广告组 | campaign_ids, platforms |
| `sync_ads` | 同步广告创意 | ad_group_ids, platforms |
| `sync_audiences` | 同步受众 | account_ids, platforms |
| `sync_creatives` | 同步创意资产 | platforms |
| `sync_products` | 同步产品目录 | account_ids, platforms |
| `sync_all` | 全量同步 | platforms, include_history |

### 📈 统一报表查询（6 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `get_report` | 查询单平台报表 | platform, account_id, date_range, metrics |
| `aggregate_report` | 聚合多平台报表 | account_ids, date_range, metrics |
| `compare_platforms` | 对比多平台表现 | account_ids, date_range, metrics |
| `export_report` | 导出报表到 CSV/JSON | platform, query, format |
| `get_metrics_summary` | 获取指标摘要 | account_ids, date_range |
| `get_daily_trends` | 获取日趋势数据 | account_ids, days |

### 🎯 跨平台事件追踪（5 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `track_event` | 追踪跨平台事件 | platform, pixel_id, event_data |
| `track_multi_platform` | 跨平台追踪同一事件 | platforms, event_name, event_data |
| `get_conversion_summary` | 获取转化汇总 | platforms, date_range |
| `validate_pixel` | 验证 Pixel 有效性 | platform, pixel_id |
| `test_conversion` | 测试转化追踪 | platform, pixel_id, event_name |

### 🔧 通用广告操作（5 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `create_campaign` | 创建跨平台广告系列 | platform, config |
| `update_campaign` | 更新广告系列 | platform, campaign_id, updates |
| `pause_campaign` | 暂停广告系列 | platform, campaign_id |
| `enable_campaign` | 启用广告系列 | platform, campaign_id |
| `duplicate_campaign` | 复制广告系列 | platform, source_id, target_config |

### 📋 辅助工具（5 个）

| Tool | 功能 | 参数 |
|------|------|------|
| `list_platforms` | 列出所有平台 | - |
| `get_platform_status` | 获取平台状态 | platform |
| `check_rate_limits` | 检查 API 限流 | platform |
| `get_quota_usage` | 获取配额使用情况 | platform |
| `sync_config_to_env` | 同步配置到环境变量 | - |

---

## 📚 核心能力说明

### 1. 统一认证管理

```python
from ad_platform_tools import AdPlatformManager

manager = AdPlatformManager()

# 配置各平台凭证
manager.configure('tiktok', {
    'app_key': 'your_app_key',
    'app_secret': 'your_app_secret',
    'access_token': 'your_access_token'
})

manager.configure('meta', {
    'app_id': 'your_app_id',
    'app_secret': 'your_app_secret',
    'access_token': 'your_access_token'
})

manager.configure('google', {
    'developer_token': 'your_developer_token',
    'client_id': 'your_client_id',
    'client_secret': 'your_client_secret',
    'refresh_token': 'your_refresh_token',
    'customer_id': 'your_customer_id'
})

# 测试连接
results = manager.test_connections()
for platform, status in results.items():
    print(f"{platform}: {'✅ 成功' if status else '❌ 失败'}")
```

### 2. 跨平台数据同步

```python
# 同步所有账户
accounts = manager.sync_accounts(platforms=['tiktok', 'meta', 'google'])
print(f"同步了 {len(accounts)} 个账户")

# 同步广告系列
campaigns = manager.sync_campaigns(
    account_ids=[acc['id'] for acc in accounts],
    platforms=['tiktok', 'meta', 'google'],
    date_range={'start': '2026-08-01', 'end': '2026-08-14'}
)

# 同步受众
audiences = manager.sync_audiences(
    account_ids=[acc['id'] for acc in accounts],
    platforms=['meta', 'google']
)
```

### 3. 统一报表聚合

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

# 对比多平台表现
comparison = manager.compare_platforms(
    account_ids=['tiktok-123', 'meta-456', 'google-789'],
    date_range={'start': '2026-08-01', 'end': '2026-08-14'},
    metrics=['spend', 'conversions', 'ctr', 'cpc']
)
```

### 4. 跨平台事件追踪

```python
# 追踪跨平台转化事件
manager.track_multi_platform(
    platforms=['tiktok', 'meta', 'google'],
    event_name='Purchase',
    event_data={
        'value': 99.99,
        'currency': 'USD',
        'transaction_id': 'txn_123'
    }
)

# 获取转化汇总
conversion_summary = manager.get_conversion_summary(
    platforms=['tiktok', 'meta', 'google'],
    date_range={'start': '2026-08-01', 'end': '2026-08-14'}
)
```

---

## 💡 最佳实践

### 1. 批量操作优化

```python
def batch_update_campaigns(manager, campaigns, updates):
    """批量更新广告系列"""
    results = []
    for campaign in campaigns:
        try:
            result = manager.update_campaign(
                platform=campaign['platform'],
                campaign_id=campaign['id'],
                updates=updates
            )
            results.append(result)
        except Exception as e:
            print(f"更新失败 {campaign['id']}: {e}")
    return results
```

### 2. 错误处理与重试

```python
import time

def safe_operation(manager, func, *args, max_retries=3):
    """安全操作（含重试）"""
    for attempt in range(max_retries):
        try:
            return func(*args)
        except Exception as e:
            if 'rate limit' in str(e).lower() or 'quota' in str(e).lower():
                wait_time = min(2 ** attempt * 60, 600)
                print(f"限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception(f"重试 {max_retries} 次后仍失败")
```

---

## 🎓 支持的 Skill 插件

| 插件 | 描述 | 状态 |
|------|------|------|
| `tiktok-ads-expert` | TikTok Ads API 专家技能 | ✅ 已配置 |
| `meta-marketing-api-expert` | Meta Marketing API 专家技能 | ✅ 已配置 |
| `google-ads-api-expert` | Google Ads API 专家技能 | ✅ 已配置 |
| `dv360-expert` | Display & Video 360 专家技能 | ✅ 已配置 |

---

*本工具集为跨平台广告管理的核心基础设施，可与各平台专家 Skills 配合使用。*