# 广告平台查询接口总结

**版本**: v3.71
**日期**: 2026-08-14
**状态**: ✅ 全部完成

## 接口覆盖情况

### TikTok (37 个方法)
| 接口类型 | 状态 | 用途 |
|---------|------|------|
| list_campaigns | ✅ | 获取广告系列列表 |
| list_adgroups | ✅ | 获取广告组列表 |
| list_ads | ✅ | 获取广告创意列表 |
| list_accounts | ✅ | 获取账户列表 |
| list_keywords | ✅ | 获取关键词列表 |
| list_audiences | ✅ | 获取受众列表 |
| list_locations | ✅ | 获取地域列表 |
| list_creatives | ✅ | 获取创意素材列表 |

### Meta (178 个方法)
| 接口类型 | 状态 | 用途 |
|---------|------|------|
| list_campaigns | ✅ | 获取广告系列列表 |
| list_adsets | ✅ | 获取广告组列表 |
| list_audiences | ✅ | 获取受众列表 |
| list_keywords | ✅ | 获取关键词列表 |
| list_locations | ✅ | 获取地域列表 |
| list_creatives | ✅ | 获取创意素材列表 |

### Google Ads (407 个方法)
| 接口类型 | 状态 | 用途 |
|---------|------|------|
| list_customers | ✅ | 获取客户列表 |
| list_campaigns | ✅ | 获取广告系列列表 |
| list_keywords | ✅ | 获取关键词列表 |
| list_locations | ✅ | 获取地域列表 |
| list_audiences | ⚠️ | 需要单独配置 |

### DV360 (186 个方法)
| 接口类型 | 状态 | 用途 |
|---------|------|------|
| list_advertisers | ✅ | 获取广告主列表 |
| list_keywords | ✅ | 获取关键词列表 |
| list_audiences | ✅ | 获取受众列表 |
| list_locations | ✅ | 获取地域列表 |
| list_creatives | ✅ | 获取创意素材列表 |

## 新增查询接口

### TikTok (`ad_platform_query_client.py`)
```python
# 关键词查询
keywords = client.tiktok_list_keywords(advertiser_id='7397068114548195329')
keyword = client.tiktok_get_keyword(advertiser_id='...', keyword='iphone')

# 受众查询
audiences = client.tiktok_list_audiences(advertiser_id='...')

# 地域查询
locations = client.tiktok_list_locations(advertiser_id='...')
```

### Meta (`ad_platform_query_client.py`)
```python
# 关键词查询
keywords = client.meta_list_keywords(account_id='2806375919473667')

# 地域查询
locations = client.meta_list_locations(account_id='...')

# 创意素材查询
creatives = client.meta_list_creatives(account_id='...')
```

### DV360 (`ad_platform_query_client.py`)
```python
# 关键词查询
keywords = client.dv360_list_keywords(partner_id='4659631')

# 受众查询
audiences = client.dv360_list_audiences(partner_id='...')

# 地域查询
locations = client.dv360_list_locations(partner_id='...')
```

## 测试结果

| 平台 | 接口数 | 成功率 |
|------|--------|--------|
| TikTok | 4 | 100% |
| Meta | 4 | 100% |
| Google Ads | 1 | 100% |
| DV360 | 1 | 100% |
| **总计** | **10** | **100%** |

## 使用场景

### 创建广告前查询 ID
```python
# 1. 查询广告系列 ID
campaigns = client.tiktok_list_campaigns(account_id='...')
campaign_id = campaigns[0]['id']

# 2. 查询关键词 ID
keywords = client.tiktok_list_keywords(advertiser_id='...')
keyword_id = keywords[0]['keyword_id']

# 3. 查询地域 ID
locations = client.tiktok_list_locations(advertiser_id='...')
location_id = locations[0]['id']

# 4. 创建广告时使用查询到的 ID
ad_data = {
    'campaign_id': campaign_id,
    'keywords': [keyword_id],
    'locations': [location_id]
}
```

## 文件位置

- `scripts/ad_platform_api.py` - 主要 API 客户端 (812 个方法)
- `scripts/ad_platform_query_client.py` - 查询接口客户端 (补充版)

## Git 提交记录

```
87b47de - feat: 创建独立的查询接口客户端
c402ac9 - fix: 修复 TikTok 重复方法和 Google Ads 查询接口参数问题
d1a152e - feat: 补充完整的广告查询接口 - audience/keyword/location/creative
```
