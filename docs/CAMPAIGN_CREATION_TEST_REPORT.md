# Campaign 创建测试报告

## 测试概述

- **测试时间**: 2025-08-14
- **测试范围**: TikTok Ads, Meta Marketing API, Google Ads (DV360 跳过)
- **测试账户**: 使用 config/ad_platform_credentials.json 中的测试账户

## 测试结果汇总

| 平台 | 测试数 | 成功数 | 成功率 | 状态 |
|------|--------|--------|--------|------|
| TikTok Ads | 12 | 9 | 75% | ✅ 部分成功 |
| Meta Marketing API | 6 | 0 | 0% | ⚠️ 权限限制 |
| Google Ads | 4 | 0 | 0% | ⚠️ 配置问题 |
| DV360 | - | - | - | ❌ 未测试 |

## TikTok Ads 测试结果

### 测试账户
- advertiser_id: `7397068114548195329`

### 成功创建的 Campaign (9个)

| 目标类型 | Campaign ID | 状态 |
|----------|-------------|------|
| PRODUCT_SALES | 1873502452886529 | PAUSED |
| TRAFFIC | 1873502685898754 | PAUSED |
| APP_INSTALL | 1873502595050897 | PAUSED |
| VIDEO_VIEWS | 1873502443450786 | PAUSED |
| CONVERSIONS | 1873502664221057 | PAUSED |
| REACH | 1873502642996530 | PAUSED |
| LEAD_GENERATION | 1873502590600481 | PAUSED |
| ENGAGEMENT | 1873502567319026 | PAUSED |
| WEB_CONVERSIONS | 1873502628048001 | PAUSED |

### 失败的目标类型 (3个)

| 目标类型 | 错误信息 |
|----------|----------|
| CATALOG_SALES | Catalog sales ads is no longer available |
| SHOP_PURCHASES | Shopping ads is not available to this advertiser account |
| APP_PROMOTION | Enter a valid Campaign Type |

### 关键发现

✅ **正确的 API 端点**: `POST https://business-api.tiktok.com/open_api/v1.3/campaign/create`

✅ **正确的认证方式**: `Access-Token` 请求头

✅ **正确的参数格式**:
```json
{
  "advertiser_id": "7397068114548195329",
  "campaign_name": "Test_Campaign_NAME",
  "objective_type": "TRAFFIC",
  "budget": 50.0,
  "campaign_group_status": 0,
  "budget_mode": "BUDGET_MODE_DAY"
}
```

✅ **预算单位**: 美元（$50 = 50.0）

✅ **状态码**: `campaign_group_status: 0` = PAUSED

## Meta Marketing API 测试结果

### 测试账户
- Account ID: `2806375919473667`
- Token: `EAAKMeH...` (已存储)

### 问题诊断

⚠️ **Token 权限**: 有 `pages_manage_ads` 权限

⚠️ **账户限制**:
- 只支持 `APP_INSTALLS` 和 `BRAND_AWARENESS` 目标类型
- 需要 `special_ad_categories` 参数

### 错误信息

```
(#100) Objective APP_INSTALLS is invalid. Use one of: APP_INSTALLS, BRAND
(#100) The parameter special_ad_categories is required.
```

### 建议

🔧 使用专门的 Campaign 创建测试账户
🔧 或请求更高权限的 Marketing API 访问

## Google Ads 测试结果

### 测试账户
- Customer ID: `2493002626` (Shopee MCC)
- Developer Token: 已配置

### 问题诊断

⚠️ **API 客户端创建**: 成功
⚠️ **Token 刷新**: 成功
⚠️ **创建失败**: "The required field was not present"

### 可能原因

1. 需要使用 `sub_operation` 而不是 `operation`
2. 需要额外的必填字段（如 `tracking_url_template`）
3. MCC 账户权限限制

### 建议

🔧 检查 Google Ads API 官方文档的必填字段
🔧 或使用现有 Campaign 进行查询测试

## DV360 测试结果

❌ **未测试** - 需要用户提供具体的测试账户信息

## 下一步行动

1. **TikTok**: 验证已创建的 Campaign 是否正常（状态、预算等）
2. **Meta**: 获取专门的测试账户或请求更高权限
3. **Google Ads**: 检查必填字段并使用正确的 API 调用方式
4. **文档更新**: 将成功的 API 调用模式更新到 SKILL.md

## 附录：API 调用示例

### TikTok Campaign 创建（成功）

```python
import requests
import time

token = "YOUR_ACCESS_TOKEN"
advertiser_id = "7397068114548195329"

headers = {'Access-Token': token, 'Content-Type': 'application/json'}

data = {
    'advertiser_id': advertiser_id,
    'campaign_name': f'Test_Campaign_{int(time.time())}',
    'objective_type': 'TRAFFIC',
    'budget': 50.0,
    'campaign_group_status': 0,
    'budget_mode': 'BUDGET_MODE_DAY'
}

url = "https://business-api.tiktok.com/open_api/v1.3/campaign/create"
resp = requests.post(url, headers=headers, json=data)
print(resp.json())
```

### Meta Campaign 创建（需要权限）

```python
import requests

token = "YOUR_ACCESS_TOKEN"
account_id = "act_2806375919473667"

url = f"https://graph.facebook.com/v19.0/{account_id}/campaigns"
data = {
    'name': 'Test Campaign',
    'objective': 'APP_INSTALLS',
    'status': 'PAUSED',
    'daily_budget': 1000,
    'special_ad_categories': ['NONE'],
    'access_token': token
}

resp = requests.post(url, data=data)
print(resp.json())
```

### Google Ads Campaign 创建（需要修复）

```python
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

# 需要检查必填字段
client = GoogleAdsClient.load_from_dict(creds)
campaign_service = client.get_service('CampaignService')

# 需要添加必填字段
campaign = client.get_type('Campaign')
campaign.name = 'Test Campaign'
campaign.advertising_channel_type = 1  # SEARCH
campaign.status = 3  # PAUSED

# 需要添加 tracking_url_template 等必填字段
```

---

**报告生成时间**: 2025-08-14
**版本**: v1.0
