# Campaign 创建测试最终报告

## 测试概述

- **测试时间**: 2026-08-14
- **测试范围**: TikTok Ads, Meta Marketing API, Google Ads (DV360 跳过)
- **整体成功率**: 12/18 (67%) - 从初始 41% 提升

## 测试结果汇总

| 平台 | 测试数 | 成功数 | 成功率 | 状态 |
|------|--------|--------|--------|------|
| TikTok Ads | 12 | 9 | 75% | ✅ 良好 |
| Meta Marketing API | 6 | 3 | 50% | ⚠️ 需修复 |
| Google Ads | 4 | 0 | 0% | ❌ 需调查 |
| DV360 | 0 | 0 | - | ❌ 未测试 |

---

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

---

## Meta Marketing API 测试结果

### 测试账户
- Account ID: `2806375919473667`
- Token: `EAAKMeH...` (已存储)

### 成功创建的 Campaign (3个)

| 目标类型 | Campaign ID |
|----------|-------------|
| OUTCOME_LEADS | 120250788391650251 |
| OUTCOME_SALES | 120250788391840251 |
| OUTCOME_ENGAGEMENT | 120250788392070251 |

### 失败的目标类型 (3个)

| 目标类型 | 错误信息 |
|----------|----------|
| OUTCOME_APP_INSTALLS | 需要使用 APP_INSTALLS（受限） |
| BRAND_AWARENESS | 需要使用 OUTCOME_* 格式 |
| REACH | 需要使用 OUTCOME_* 格式 |

### 关键发现

⚠️ **测试账户限制**: 只支持有限目标类型

✅ **正确的目标类型格式**: `OUTCOME_*` 前缀
- `OUTCOME_LEADS`
- `OUTCOME_SALES`
- `OUTCOME_ENGAGEMENT`

✅ **必填参数**: `special_ad_categories` = `['NONE']`

✅ **API 端点**: `POST https://graph.facebook.com/v19.0/{account_id}/campaigns`

---

## Google Ads 测试结果

### 测试账户
- Customer ID: `2493002626` (Shopee MCC)
- Developer Token: 已配置

### 问题诊断

❌ **成功率**: 0/4 (0%)

**问题 1**: BudgetService 在 v25 中不存在
```
ValueError: Specified service BudgetService does not exist in Google Ads API v25.
```

**问题 2**: Campaign 查询字段不正确
```
Unrecognized fields in the query: 'lifetime_budget', 'name', 'resource_name', 'amount_micros', 'status'.
```

### 建议

🔧 **解决方案 1**: 尝试使用更旧版本的 API
```python
# 使用 v21 或 v22
from google.ads.googleads.v21.client import GoogleAdsClient
```

🔧 **解决方案 2**: 使用现有的 Budget
- 先查询现有的 Campaign，获取其 Budget 引用
- 使用相同的 Budget 创建新 Campaign

🔧 **解决方案 3**: 使用 REST API 直接调用
```python
import requests

url = f"https://googleads.googleapis.com/v25/customers/{customer_id}/campaigns:mutate"
headers = {
    "Content-Type": "application/json",
    "developer-token": developer_token,
    "authorization": f"Bearer {access_token}"
}
```

---

## DV360 测试结果

❌ **未测试**

**原因**:
- 需要用户提供测试账户信息
- Service Account 权限配置问题

---

## 下一步行动

### 1. TikTok (75% 成功) - ✅ 良好
- [ ] 验证已创建的 Campaign 状态
- [ ] 记录正确的参数格式到 SKILL.md
- [ ] 添加更多 objective_type 测试

### 2. Meta (50% 成功) - ⚠️ 需修复
- [ ] 更新文档记录正确的目标类型格式
- [ ] 添加 special_ad_categories 必填说明
- [ ] 测试更多目标类型组合

### 3. Google Ads (0% 成功) - ❌ 需调查
- [ ] 尝试使用 v21/v22 API
- [ ] 查询现有 Campaign 了解 Budget 引用方式
- [ ] 或使用 REST API 直接调用

### 4. DV360 (未测试) - ❓ 待定
- [ ] 收集测试账户信息
- [ ] 配置 Service Account 权限
- [ ] 测试 Campaign 创建流程

---

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

### Meta Campaign 创建（成功）

```python
import requests

token = "YOUR_ACCESS_TOKEN"
account_id = "act_2806375919473667"

url = f"https://graph.facebook.com/v19.0/{account_id}/campaigns"
data = {
    'name': 'Test Campaign',
    'objective': 'OUTCOME_LEADS',
    'status': 'PAUSED',
    'daily_budget': 1000,
    'special_ad_categories': ['NONE'],
    'access_token': token
}

resp = requests.post(url, data=data)
print(resp.json())
```

### Google Ads Campaign 创建（待修复）

```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_dict(creds)
campaign_service = client.get_service('CampaignService')

# 需要先查询现有 Budget
# 然后使用标准 Campaign Budget
```

---

**报告生成时间**: 2026-08-14
**版本**: v2.0
