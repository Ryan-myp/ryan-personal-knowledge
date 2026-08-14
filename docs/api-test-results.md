# 四平台 API 测试报告

## 测试时间
2026-08-14

## 测试结果汇总

| 平台 | 测试账户 | list_campaigns | get_campaign | 状态 |
|------|---------|----------------|--------------|------|
| Meta | 2806375919473667 | ✅ 5 campaigns | ✅ 成功 | 正常 |
| TikTok | 7397068114548195329 | ⚠️ 连接不稳定 | ✅ 可用 | 需关注 |
| Google Ads | 2493002626 (MCC) | ⚠️ 方法名问题 | ✅ 可用 | 需修复 |
| DV360 | 5110831 | ✅ 成功 | ✅ 成功 | 正常 |

## 已修复问题

### 1. Meta API
- **问题**: SDK 导入路径错误 `facebook_business.adaccounts`
- **修复**: 改用 Graph API 直接调用，使用 `requests` 库
- **状态**: ✅ 完全可用

### 2. TikTok API
- **问题**: 
  - 认证头错误 (用了 `Authorization: Bearer`)
  - 端点错误 (用了 `/portal/api/v20230728`)
  - 响应格式解析错误 (应该是 `data.list`)
- **修复**: 
  - 改用 `Access-Token` header
  - 改用 `open_api/v1.3` 端点
  - 修正响应解析逻辑
- **状态**: ✅ 基本可用 (偶发连接问题)

### 3. DV360 API
- **问题**: advertisers 查询需要 partner_id 参数
- **修复**: 添加 partner_id 参数支持
- **状态**: ✅ 可用

### 4. Google Ads API
- **问题**: `google_list_accounts` 方法不存在
- **状态**: ⚠️ 需要补充方法或改用脚本

## 测试命令

```bash
# Meta
python3 scripts/query_campaign.py meta <CAMPAIGN_ID>

# TikTok
python3 scripts/query_tiktok_campaign.py <campaign_id> <advertiser_id>

# Google Ads
python3 scripts/query_google_campaign.py <CAMPAIGN_RESOURCE_NAME>

# DV360
python3 scripts/query_dv360_campaign.py <CAMPAIGN_ID>
```

## 后续优化建议

1. **TikTok**: 添加重试机制处理连接不稳定问题
2. **Google Ads**: 统一方法命名或添加 `google_list_accounts` 别名
3. **DV360**: 确认 advertisers 查询是否需要特定权限
4. **通用**: 添加更详细的错误日志和超时处理
