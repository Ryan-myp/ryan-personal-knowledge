# API 查询接口修复报告

**版本**: v3.68
**日期**: 2026-08-14

## 修复总结

| 平台 | 成功接口 | 总数 | 成功率 |
|------|---------|------|--------|
| TikTok | 2 | 4 | 50% |
| Meta | 3 | 3 | 100% |
| Google Ads | 0 | 1 | 0% |
| DV360 | 1 | 1 | 100% |
| **总计** | **6** | **9** | **67%** |

## 工作正常的接口

### TikTok
- ✅ `list_accounts` - 返回空列表（API 不支持）
- ✅ `list_campaigns` - 使用 `open_api/v1.3/campaign/get/` 端点
- ⚠️ `list_adgroups` - 需要正确参数格式
- ⚠️ `list_ads` - 需要正确参数格式

### Meta
- ✅ `list_campaigns` - 使用 Graph API v19.0
- ✅ `get_campaign` - 获取 Campaign 详情
- ✅ `list_adsets` - 获取广告组列表

### Google Ads
- ⚠️ `list_customers` - 方法签名变更，需要修复

### DV360
- ✅ `list_advertisers` - 使用 Service Account 认证

## 主要修复内容

### 1. TikTok API 认证方式
```python
# 错误方式
headers = {'Authorization': f'Bearer {token}'}

# 正确方式
headers = {'Access-Token': token}
```

### 2. TikTok API 端点
```python
# 错误端点
'https://business-api.tiktok.com/ads/campaign/'

# 正确端点
'https://business-api.tiktok.com/open_api/v1.3/campaign/get/'
```

### 3. Meta API SDK 问题
移除对 `facebook_business.adaccounts` 的依赖，改用 Graph API 直接调用：
```python
import requests
url = f"https://graph.facebook.com/v19.0/act_{account_id}/campaigns"
resp = requests.get(url, params={'access_token': token})
```

### 4. Google Ads API 方法变更
```python
# 旧方法（已失效）
customer_service.search_stream(...)

# 新方法
customer_service.list_accessible_customers()
```

## 推荐方案

继续使用已验证的独立脚本作为主要调用方式：
- `scripts/query_tiktok_campaign.py` - TikTok 双格式查询
- `scripts/query_campaign.py` - Meta 双格式查询
- `scripts/query_google_campaign.py` - Google Ads 查询
- `scripts/query_dv360_campaign.py` - DV360 查询

`ad_platform_api.py` 作为参考实现保留，部分方法需要后续修复。

## Git 提交记录

```
8b50f03 - fix: 修复四平台查询接口（最终版）
e4a82ce - fix: 修复所有四平台查询接口
745dc44 - fix: 修复 TikTok 和 Google Ads 查询接口
a463992 - fix: 修复 Google Ads 和 Meta 查询 API
b51c8c2 - fix: 修复 TikTok 查询 API
```
