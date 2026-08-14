# Google Ads Campaign 创建 - 完整问题诊断

## 问题总结

**状态**: ❌ 无法通过 API 创建 Campaign  
**原因**: 缺少多个必填字段，且账户可能存在权限限制

---

## 🔴 发现的所有必填字段

### 1. campaign_budget（关键缺失）
```
error_code: REQUIRED
message: "The required field was not present."
location: operations[0].create.campaign_budget
```

**说明**: Campaign 必须关联一个 Budget，不能只传 Bidding Strategy

### 2. contains_eu_political_advertising（另一个缺失）
```
error_code: REQUIRED
message: "The required field was not present."
location: operations[0].create.contains_eu_political_advertising
```

**说明**: 需要明确声明是否包含欧盟政治广告

### 3. 操作权限限制
```
error_code: OPERATION_NOT_PERMITTED_FOR_CONTEXT
message: "The operation is not allowed for the given context."
```

**说明**: 当前账户可能不允许通过 API 创建 Campaign

---

## ✅ 已确认的可用资源

### Bidding Strategy（5个）
| ID | Name | Type |
|---|------|------|
| 7494425156 | PBPD ELHA | (6) |
| 7807377600 | tROAs Portfolio Bidding Average | (8) |
| 8032941125 | tROAs Portfolio Bidding High | (8) |
| 8058852853 | TH - Shopping Small Categories | (8) |
| 9463566509 | tROAs Portfolio Bidding (MC/WC) Low | (8) |

### Account 信息
- Customer ID: 2493002626
- Account Name: Shopee MCC
- Account Type: MCC (Manager Account)
- Currency: USD
- Timezone: Asia/Singapore
- Sub-accounts: 46

---

## 📋 创建 Campaign 所需完整参数

### 最小必填字段
```python
campaign = {
    "name": "Test_Campaign_XXX",
    "advertising_channel_type": "SEARCH",
    "status": "PAUSED",
    "bidding_strategy": "customers/2493002626/biddingStrategies/7494425156",
    "campaign_budget": "customers/2493002626/campaignBudgets/XXX",  # ⚠️ 必须
    "contains_eu_political_advertising": False  # ⚠️ 必须
}
```

### 完整推荐字段
```python
campaign = {
    # 必填
    "name": "Test_Campaign_XXX",
    "advertising_channel_type": "SEARCH",  # SEARCH/DISPLAY/SHOPPING/VIDEO/MAXIMIZE_CLICKS/PERFORMANCE_MAX
    "status": "PAUSED",
    "bidding_strategy": "...",
    "campaign_budget": "...",
    "contains_eu_political_advertising": False,
    
    # 可选但推荐
    "shopping_setting": {
        "merchant_id": 123456789,  # Shopping 广告必需
        "sales_country": "SG",
        "campaign_priority": 0,
        "normalize_localinventories": True
    },
    "maximize_clicks_setting": {
        "target_cpa_micros": 0
    },
    "campaign_schedule": {
        "start_date": "20260814",
        "end_date": "20261231"
    }
}
```

---

## 🚫 当前问题

### 问题 1: 缺少 Campaign Budget
- BudgetService 在 v25 已被移除
- 需要先查询现有 Budget 或手动创建
- 或者使用标准 Campaign Budget

### 问题 2: 操作权限限制
- 错误信息: "The operation is not allowed for the given context."
- 可能原因:
  1. MCC 账户不能直接创建 Campaign（需要子账户）
  2. 测试账户权限不足
  3. 账户需要特定设置才能通过 API 创建

---

## 🔧 解决方案

### 方案 1: 查询子账户创建（推荐）
```python
# 从之前的查询结果中获取子账户 ID
sub_accounts = [
    "7830479674",  # H19 MCC
    "1045828457",  # SeaMoney Credit - ID MCC
    "1165788658",  # Monee Credit - MY MCC
    "4837298071",  # 7-Eleven-TH
    "5472010084",  # SeaMoney - TH MCC
    "8844208336",  # SPay- VN
    "9389300632",  # Shopee- PH
    "16996295161", # Shopee-ID
]

# 选择一个子账户测试
customer_id = "8844208336"  # 例如：SPay- VN
```

### 方案 2: 手动创建 Budget
```python
# 如果 BudgetService 不可用，需要先手动创建 Budget
# 在 Google Ads 界面创建一个 Budget
# 然后查询 Budget ID 并在 API 中使用
```

### 方案 3: 使用现有 Campaign 结构
```python
# 查询一个现有 Campaign，复制其所有字段
# 然后修改 name 和 resource_name 创建新的
```

---

## 📊 四平台 Campaign 创建最终统计

| 平台 | 测试数 | 成功数 | 成功率 | 状态 |
|------|--------|--------|--------|------|
| TikTok Ads | 12 | 9 | 75% | ✅ 良好 |
| Meta API | 6 | 3 | 50% | ⚠️ 需修复 |
| Google Ads | 4 | 0 | 0% | ❌ 需调查 |
| DV360 | 0 | 0 | - | ❌ 未测试 |

**整体成功率**: 12/22 = 55%（从初始 41% 提升）

---

## 🎯 下一步行动

1. **Google Ads**
   - [ ] 尝试使用子账户创建 Campaign
   - [ ] 或者在 Google Ads 界面手动创建一个 Budget
   - [ ] 然后查询 Budget ID 再创建 Campaign

2. **DV360**
   - [ ] 需要用户提供测试账户信息
   - [ ] 或者先手动创建一个 Campaign 了解结构

3. **文档更新**
   - [ ] 记录 Google Ads Campaign 创建的完整参数要求
   - [ ] 添加 Budget 创建流程说明

---

## 📝 技术备注

### Google Ads API 版本
- 当前使用: v25
- 注意: BudgetService 在 v25 已被移除
- 推荐使用: standardCampaignBudget 字段

### Python SDK
```python
from google.ads.googleads.v25.enums.types.advertising_channel_type import AdvertisingChannelTypeEnum
from google.ads.googleads.v25.enums.types.campaign_status import CampaignStatusEnum
from google.ads.googleads.v25.resources.types.campaign import Campaign
```

### 完整错误信息
```
status = StatusCode.INVALID_ARGUMENT
details = "Request contains an invalid argument."

errors:
1. REQUIRED: campaign_budget
2. REQUIRED: contains_eu_political_advertising
3. OPERATION_NOT_PERMITTED_FOR_CONTEXT: 操作不被允许
```
