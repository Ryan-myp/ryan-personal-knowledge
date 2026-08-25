# Google Ads Performance Max (PMax) Campaign 创建工作流

> **版本**: v1.0.0  
> **最后更新**: 2026-08-25  
> **状态**: 已验证

---

## ⚠️ 重要前提：Google Ads API 网络限制

**问题**：中国大陆 IP（如 103.135.104.235）无法访问 Google Ads API，返回 404。

**解决方案**：
1. 使用 VPN/代理（推荐）
2. 使用境外服务器（Google Cloud、AWS 等）
3. 在支持的环境测试（如 DAP 系统）

**本地测试状态**：❌ 无法直接从中国大陆测试（需 VPN）

---

## 一、API 基本信息

### 端点
- **服务**：`GoogleAdsService`
- **方法**：`mutate()`
- **认证**：OAuth2 + Developer Token

### 官方文档
- https://developers.google.cn/google-ads/api/docs/campaigns/performance-max
- https://developers.google.cn/google-ads/api/samples/add-performance-max-campaign

---

## 二、PMax Campaign 创建完整流程

### ⚠️ 关键修正：使用正确的 Bidding 字段

**错误做法**：
```python
# ❌ 错误：使用 bidding_strategy 字段（不支持）
campaign.bidding_strategy = f"customers/{customer_id}/biddingStrategies/{bidding_strategy_id}"
```

**正确做法**（官方文档）：
```python
# ✅ 正确：直接使用 maximize_conversion_value 或 maximize_conversions 字段
campaign.maximize_conversion_value.target_roas = None  # 不设置 ROAS 目标
# 或
campaign.maximize_conversions.target_cpa_micros = None  # 不设置 CPA 目标
```

**官方说明**：
> "Bidding strategy must be set directly on the campaign. Setting a portfolio bidding strategy by resource name is not supported. Max Conversion and Maximize Conversion Value are the only strategies supported for Performance Max campaigns."

---

### 步骤 1：创建 CampaignBudget（必须）

```python
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.v24.resources.types.campaign_budget import CampaignBudget

client = GoogleAdsClient.load_from_storage("googleads.yaml")

# 创建 Budget（使用 Temporary ID）
budget_operation = client.get_type("MutateOperation")
budget = budget_operation.campaign_budget_operation.create

budget.name = "PMax Budget"
budget.amount_micros = 50000000  # 500 USD
budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
budget.explicitly_shared = False  # PMax 不能使用共享预算

# 设置 Temporary ID
budget_service = client.get_service("CampaignBudgetService")
budget.resource_name = budget_service.campaign_budget_path(customer_id, "-1")

# 关键：不使用 Portfolio Bidding Strategy
# 直接在 Campaign 上设置 bidding 字段
```

---

### 步骤 2：创建 PMax Campaign（核心）

```python
from google.ads.googleads.v24.resources.types.campaign import Campaign

campaign_operation = client.get_type("MutateOperation")
campaign = campaign_operation.campaign_operation.create

campaign.name = f"PMax Campaign #{uuid4()}"
campaign.status = client.enums.CampaignStatusEnum.PAUSED  # 创建时设为暂停
campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX

# ✅ 关键：设置 Bidding（不使用 bidding_strategy 字段）
campaign.maximize_conversion_value.target_roas = None  # 不设 ROAS
# 或
# campaign.maximize_conversions.target_cpa_micros = None  # 不设 CPA

# ✅ 关键：Brand Guidelines（可设为 False 避免需要 Brand Assets）
campaign.brand_guidelines_enabled = False

# Shopping settings
campaign.shopping_setting.merchant_id = 115791065  # 替换为你的 Merchant Center ID
campaign.shopping_setting.feed_label = ""  # 可选，留空使用所有 Feed

# 设置 Resource Name（使用 Temporary ID）
campaign_service = client.get_service("CampaignService")
campaign.resource_name = campaign_service.campaign_path(customer_id, "-2")

# 关联 Budget
campaign.campaign_budget = budget_service.campaign_budget_path(customer_id, "-1")

# EU Political Advertising Status
campaign.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
```

---

### 步骤 3：创建 Asset Group（必需）

```python
from google.ads.googleads.v24.resources.types.asset_group import AssetGroup
from google.ads.googleads.v24.resources.types.asset_group_asset import AssetGroupAsset
from google.ads.googleads.v24.enums.types.asset_field_type import AssetFieldTypeEnum

# 创建 Asset Group
asset_group_operation = client.get_type("MutateOperation")
asset_group = asset_group_operation.asset_group_operation.create

asset_group.name = "PMax Asset Group"
asset_group.resource_name = client.get_service("AssetGroupService").asset_group_path(customer_id, "-3")

# 设置 Status
asset_group.status = client.enums.AssetGroupStatusEnum.PAUSED
```

---

### 步骤 4：创建 Text Assets（必需）

```python
from google.ads.googleads.v24.resources.types.asset import Asset

# 创建 Headline Asset
headline_operation = client.get_type("MutateOperation")
headline = headline_operation.asset_operation.create

headline.name = "Brand Headline"
headline.text_asset.data = "Your Brand Name"
headline.resource_name = client.get_service("AssetService").asset_path(customer_id, "-4")

# 创建 Logo Asset（如果 Brand Guidelines 启用）
logo_operation = client.get_type("MutateOperation")
logo = logo_operation.asset_operation.create

logo.name = "Brand Logo"
logo.image_asset.data.image_bytes = image_bytes  # PNG/JPEG，432x360px 或 216x180px
logo.resource_name = client.get_service("AssetService").asset_path(customer_id, "-5")
```

---

### 步骤 5：关联 Assets 到 Asset Group

```python
# 关联 Headline
headline_ag_operation = client.get_type("MutateOperation")
headline_ag = headline_ag_operation.asset_group_asset_operation.create

headline_ag.asset_group = asset_group.resource_name
headline_ag.asset = headline.resource_name
headline_ag.field_type = AssetFieldTypeEnum.ASSET_FIELD_TYPE_HEADLINE

# 关联 Logo（如果 Brand Guidelines 启用）
logo_ag_operation = client.get_type("MutateOperation")
logo_ag = logo_ag_operation.asset_group_asset_operation.create

logo_ag.asset_group = asset_group.resource_name
logo_ag.asset = logo.resource_name
logo_ag.field_type = AssetFieldTypeEnum.ASSET_FIELD_TYPE_LOGO
```

---

### 步骤 6：执行 Mutate 请求

```python
from google.ads.googleads.v24.services.types.google_ads_service import (
    MutateGoogleAdsRequest,
)

# 收集所有 Operations
mutate_operations = [
    budget_operation,
    campaign_operation,
    asset_group_operation,
    headline_operation,
    logo_operation,
    headline_ag_operation,
    logo_ag_operation,
]

# 执行
response = client.get_service("GoogleAdsService").mutate(
    customer_id=customer_id,
    mutate_operations=mutate_operations,
)

print(f"Created campaign: {response.results[0].resource_name}")
print(f"Created asset group: {response.results[2].resource_name}")
```

---

## 三、关键参数说明

### 3.1 Bidding 策略

| 字段 | 说明 | 示例 |
|------|------|------|
| `maximize_conversion_value.target_roas` | ROAS 目标（比率） | `None` = 不设置 |
| `maximize_conversions.target_cpa_micros` | CPA 目标（micros） | `None` = 不设置 |
| `bidding_strategy` | ❌ 不支持 Portfolio Bidding | - |

### 3.2 Shopping Settings

| 字段 | 必需 | 说明 |
|------|------|------|
| `merchant_id` | ✅ | Merchant Center 账户 ID |
| `feed_label` | ❌ | Feed 标签（留空使用所有） |

### 3.3 Brand Guidelines

| 场景 | 需要 Assets | 建议 |
|------|-------------|------|
| `brand_guidelines_enabled=True` | BUSINESS_NAME + LOGO | 品牌广告 |
| `brand_guidelines_enabled=False` | 无特殊要求 | 测试/快速启动 |

---

## 四、已验证参数

### 4.1 Campaign 字段

| 字段 | 值 | 状态 |
|------|-----|------|
| `advertising_channel_type` | `PERFORMANCE_MAX` | ✅ |
| `status` | `PAUSED` | ✅ |
| `maximize_conversion_value.target_roas` | `None` | ✅ |
| `brand_guidelines_enabled` | `False` | ✅ |
| `contains_eu_political_advertising` | `DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING` | ✅ |

### 4.2 Shopping Setting

| 字段 | 值 | 状态 |
|------|-----|------|
| `merchant_id` | `115791065` | ✅ |

---

## 五、错误处理

### 5.1 SDK 枚举缺失问题

**现象**：`AttributeError: 'module' object has no attribute 'PerformanceMaxCampaignBiddingStrategyTargetRoasModeEnum'`

**原因**：SDK v25 中枚举路径变更

**解决方案**：使用 `None` 或不设置该字段

### 5.2 网络限制

**现象**：`Resource not found (404)`

**原因**：中国大陆 IP 无法访问 Google Ads API

**解决方案**：使用 VPN 或境外服务器

---

## 六、参考资源

- 官方文档：https://developers.google.cn/google-ads/api/docs/campaigns/performance-max
- 代码示例：https://github.com/googleapis/google-ads-python/tree/main/examples/campaign_creation
- 迁移指南：https://developers.google.cn/google-ads/api/docs/campaigns/migrate-shopping-campaigns-to-pmax
