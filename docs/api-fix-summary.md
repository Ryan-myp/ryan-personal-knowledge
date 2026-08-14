# API 查询接口修复总结

**日期**: 2026-08-14
**版本**: v3.68

## 修复结果

| 平台 | 接口 | 状态 | 说明 |
|------|------|------|------|
| TikTok | list_accounts | ✅ | 返回空列表（API 不支持） |
| TikTok | list_campaigns | ✅ | 使用 open_api/v1.3 端点 |
| TikTok | list_adgroups | ✅ | 使用 campaign_id 参数 |
| TikTok | list_ads | ✅ | 使用 campaign_id 参数 |
| Meta | list_campaigns | ✅ | 使用 Graph API v19.0 |
| Meta | get_campaign | ✅ | 获取单条 Campaign 详情 |
| Meta | list_adsets | ✅ | 获取广告组列表 |
| Meta | list_ads | ✅ | 获取广告创意列表 |
| Meta | list_audiences | ⚠️ | 需要修复 SDK 导入问题 |
| Google Ads | list_customers | ⚠️ | 部分成功（方法签名变更） |
| DV360 | list_advertisers | ✅ | 使用 Service Account |

**成功率**: 8/11 = 73%

## 主要修复

### 1. TikTok API
- 使用正确的认证头：`Access-Token` 而非 `Authorization: Bearer`
- 使用正确的端点：`open_api/v1.3/campaign/get/` 而非 `/ads/campaign/`
- 使用 `campaign_id` 参数而非 JSON 格式的 `filtering`

### 2. Meta API
- 使用 Graph API v19.0 直接调用
- 修复返回数据解析（dict vs list）
- 移除对 `facebook_business.adaccounts` 的依赖

### 3. Google Ads API
- 使用 `GoogleAdsClient(credentials=..., use_proto_plus=True)`
- 修复 OAuth2 凭据配置

### 4. DV360 API
- 使用 Service Account JWT Bearer 认证
- 正确使用 partner_id 参数

## 已验证的测试账户

```json
{
  "tiktok": {
    "advertiser_id": "7397068114548195329",
    "campaign_id": "1836521788460274"
  },
  "meta": {
    "business_id": "2806375919473667",
    "campaign_id": "120250706434530251"
  },
  "google": {
    "customer_id": "2493002626",
    "account_name": "Shopee MCC"
  },
  "dv360": {
    "partner_id": "4659631",
    "advertiser_id": "5110831"
  }
}
```

## 后续建议

1. **Meta list_audiences**: 需要修复 SDK 导入路径
2. **Google Ads list_customers**: 可能需要使用 proto-plus 的正确方法名
3. **写操作接口**: 保持现状，需要二次确认机制保护线上数据

## Git 提交

- `b51c8c2` - 修复 TikTok 查询 API
- `a463992` - 修复 Google Ads 和 Meta 查询 API
- 最新提交 - 修复 TikTok 和 Google Ads 查询接口
