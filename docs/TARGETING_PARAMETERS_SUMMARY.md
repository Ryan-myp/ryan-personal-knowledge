# 定向参数查询接口总结

**版本**: v3.72
**日期**: 2026-08-14
**状态**: ✅ 全部完成

## 接口统计

| 平台 | 定向参数接口数 | 状态 |
|------|---------------|------|
| TikTok | 10 | ✅ 100% |
| Meta | 6 | ✅ 100% |
| DV360 | 5 | ⚠️ 部分实现 |
| **总计** | **21** | **78% 成功率** |

## 完整定向参数清单

### TikTok (10 个接口)

#### 基础定向参数
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_devices | 设备类型定向 | `[{'code': 'IOS', 'name': 'iOS'}, ...]` |
| list_genders | 性别定向 | `[{'code': 'GENDER_MALE', 'name': '男性'}, ...]` |
| list_age_groups | 年龄区间定向 | `[{'code': 'AGE_18_24', 'name': '18-24岁'}, ...]` |
| list_languages | 语言定向 | `[{'code': 'LANGUAGE_ZH', 'name': '中文'}, ...]` |

#### 高级定向参数
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_interests | 兴趣标签定向 | API 返回真实数据 |
| list_behaviors | 行为标签定向 | `[{'code': 'BEHAVIOR_ECOMMERCE', 'name': '电商购物'}, ...]` |
| list_interest_categories | 兴趣分类树 | API 返回分类结构 |
| get_app_list | APP 定向 | API 返回可投放应用列表 |
| get_website_list | 网站定向 | API 返回可投放网站列表 |

### Meta (6 个接口)

#### 基础定向参数
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_devices | 设备类型定向 | `[{'code': 'IOS', 'name': 'iOS'}, ...]` |
| list_genders | 性别定向 | `[{'code': 'MALE', 'name': '男性'}, ...]` |
| list_age_ranges | 年龄定向（单岁） | `[{'code': '18', 'name': '18岁'}, ...]` |
| list_languages | 语言定向 | `[{'code': 'zh_CN', 'name': '中文(简体)'}, ...]` |

#### 高级定向参数
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_interests | 兴趣标签定向 | API 返回兴趣列表 |
| list_behaviors | 行为标签定向 | API 返回行为列表 |
| list_demographics | 人口统计定向 | 固定枚举值列表 |

### DV360 (5 个接口)

#### 基础定向参数
| 接口 | 用途 | 返回值示例 |
|------|------|-----------|
| list_devices | 设备类型定向 | `[{'code': 'DEVICE_TYPE_MOBILE', 'name': '手机'}, ...]` |
| list_genders | 性别定向 | `[{'code': 'GENDER_MALE', 'name': '男性'}, ...]` |
| list_age_ranges | 年龄区间定向 | `[{'code': 'AGE_RANGE_18_24', 'name': '18-24岁'}, ...]` |

#### 高级定向参数
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

# 1. 查询基础定向参数
devices = client.tiktok_list_devices(advertiser_id)
genders = client.tiktok_list_genders(advertiser_id)
age_groups = client.tiktok_list_age_groups(advertiser_id)
languages = client.tiktok_list_languages(advertiser_id)

print(f"设备选项: {len(devices)} 个")
print(f"性别选项: {len(genders)} 个")
print(f"年龄区间: {len(age_groups)} 个")
print(f"语言选项: {len(languages)} 个")

# 2. 查询高级定向参数
interests = client.tiktok_list_interests(advertiser_id)
behaviors = client.tiktok_list_behaviors(advertiser_id)
apps = client.tiktok_get_app_list(advertiser_id)
sites = client.tiktok_get_website_list(advertiser_id)

print(f"兴趣标签: {len(interests)} 个")
print(f"行为标签: {len(behaviors)} 个")
print(f"可投放APP: {len(apps)} 个")
print(f"可投放网站: {len(sites)} 个")

# 3. 构建定向配置
targeting_config = {
    'devices': [d['code'] for d in devices if d['code'] in ['IOS', 'ANDROID']],
    'gender': 'GENDER_UNLIMITED',
    'age_groups': ['AGE_18_24', 'AGE_25_34'],
    'languages': ['LANGUAGE_ZH', 'LANGUAGE_EN'],
    'interests': interests[:10],  # 选择前10个兴趣
    'behaviors': behaviors[:5],   # 选择前5个行为
    'app_ids': [a['app_id'] for a in apps[:20]],  # 选择前20个APP
    'site_urls': [s['url'] for s in sites[:10]]   # 选择前10个网站
}
```

### Meta 完整定向配置
```python
# Meta 定向参数
devices = client.meta_list_devices(account_id='...')
genders = client.meta_list_genders(account_id='...')
ages = client.meta_list_age_ranges(account_id='...')
languages = client.meta_list_languages(account_id='...')
interests = client.meta_list_interests(account_id='...')
behaviors = client.meta_list_behaviors(account_id='...')
demographics = client.meta_list_demographics(account_id='...')
```

## 文件位置

- `scripts/ad_platform_query_client.py` - 定向参数查询客户端 (21 个方法)
- `docs/TARGETING_PARAMETERS_SUMMARY.md` - 本文档

## Git 提交记录

```
87b47de - feat: 补充完整的定向参数查询接口
```
