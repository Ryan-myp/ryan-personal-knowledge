# 完整定向参数查询指南

**版本**: v3.73
**日期**: 2026-08-14
**状态**: ✅ 全部完成

## 接口总览

| 平台 | 定向参数接口数 | 状态 |
|------|---------------|------|
| TikTok | 6 | ✅ 100% |
| Meta | 7 | ✅ 100% |
| DV360 | 5 | ✅ 100% |
| **总计** | **18** | **100%** |

## 完整定向参数清单

### TikTok 定向参数 (6 个)

#### 基础定向
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_genders | 性别定向 | `[{'code': 'GENDER_MALE', 'name': '男性'}, ...]` |
| list_age_groups | 年龄区间定向 | `[{'code': 'AGE_18_24', 'name': '18-24岁'}, ...]` |
| list_languages | 语言定向 | `[{'code': 'LANGUAGE_ZH', 'name': '中文'}, ...]` |
| list_devices | 设备类型定向 | API 返回真实数据 |

#### 高级定向
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_interests | 兴趣标签定向 | API 返回兴趣列表 |
| list_behaviors | 行为标签定向 | `[{'code': 'BEHAVIOR_ECOMMERCE', 'name': '电商购物'}, ...]` |

### Meta 定向参数 (7 个)

#### 基础定向
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_genders | 性别定向 | `[{'code': 'MALE', 'name': '男性'}, ...]` |
| list_age_ranges | 年龄定向（单岁） | `[{'code': '18', 'name': '18岁'}, ...]` |
| list_languages | 语言定向 | `[{'code': 'zh_CN', 'name': '中文(简体)'}, ...]` |
| list_devices | 设备类型定向 | `[{'code': 'IOS', 'name': 'iOS'}, ...]` |

#### 高级定向
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_interests | 兴趣标签定向 | API 返回兴趣列表 |
| list_behaviors | 行为标签定向 | API 返回行为列表 |
| list_demographics | 人口统计定向 | 固定枚举值列表 |

### DV360 定向参数 (5 个)

#### 基础定向
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_genders | 性别定向 | `[{'code': 'GENDER_MALE', 'name': '男性'}, ...]` |
| list_age_ranges | 年龄区间定向 | `[{'code': 'AGE_RANGE_18_24', 'name': '18-24岁'}, ...]` |
| list_devices | 设备类型定向 | `[{'code': 'DEVICE_TYPE_MOBILE', 'name': '手机'}, ...]` |

#### 高级定向
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_interests | 兴趣定向 | API 返回兴趣列表 |
| list_location_targets | 地域定向 | API 返回地域列表 |

## 使用示例

### TikTok 完整定向配置
```python
from ad_platform_query_client import AdPlatformQueryClient
import json

with open('config/ad_platform_credentials.json') as f:
    creds = json.load(f)

client = AdPlatformQueryClient(creds)
advertiser_id = '7397068114548195329'

# 查询所有定向参数
genders = client.tiktok_list_genders(advertiser_id)
ages = client.tiktok_list_age_groups(advertiser_id)
languages = client.tiktok_list_languages(advertiser_id)
devices = client.tiktok_list_devices(advertiser_id)
interests = client.tiktok_list_interests(advertiser_id)
behaviors = client.tiktok_list_behaviors(advertiser_id)

# 构建定向配置
targeting = {
    'genders': ['GENDER_UNLIMITED'],
    'age_groups': ['AGE_18_24', 'AGE_25_34'],
    'languages': ['LANGUAGE_ZH', 'LANGUAGE_EN'],
    'devices': ['IOS', 'ANDROID'],
    'interests': interests[:10],
    'behaviors': behaviors[:5]
}
```

### Meta 完整定向配置
```python
# Meta 定向参数查询
genders = client.meta_list_genders(account_id='...')
ages = client.meta_list_age_ranges(account_id='...')
languages = client.meta_list_languages(account_id='...')
devices = client.meta_list_devices(account_id='...')
interests = client.meta_list_interests(account_id='...')
behaviors = client.meta_list_behaviors(account_id='...')
demographics = client.meta_list_demographics(account_id='...')

# 构建定向配置
targeting = {
    'genders': ['MALE', 'FEMALE'],
    'ages': {'min': 18, 'max': 35},
    'languages': ['zh_CN', 'en_US'],
    'devices': ['MOBILE', 'DESKTOP'],
    'interests': interests[:10],
    'behaviors': behaviors[:5],
    'demographics': demographics
}
```

## 文件位置

- `scripts/ad_platform_query_client.py` - 定向参数查询客户端 (26 个方法)
- `docs/COMPLETE_TARGETING_GUIDE.md` - 本文档

## Git 提交记录

```
c43c7f3 - feat: 补充完整的定向参数查询接口
```
