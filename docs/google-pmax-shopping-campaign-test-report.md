# Google Ads PMax & Shopping Campaign 测试报告

**测试时间**: 2026-08-25 09:46:37
**测试账户**: 2493002626 (Shopee MCC)
**测试状态**: ❌ 失败

---

## 测试结果汇总

| 广告类型 | 状态 | 错误代码 | 原因 |
|---------|------|---------|------|
| Performance Max | ❌ 失败 | CANNOT_ATTACH_TO_BIDDING_STRATEGY | 需要 MAXIMIZE_CONVERSIONS 类型 Bidding Strategy |
| Shopping | ❌ 失败 | RESOURCE_NOT_FOUND | 需要有效的 Merchant Center ID |

---

## 详细错误分析

### 1. PMax Campaign 创建失败

**错误信息**:
```
CANNOT_ATTACH_TO_BIDDING_STRATEGY: Cannot attach the campaign to this bidding strategy.
OPERATION_NOT_PERMITTED_FOR_CONTEXT: The operation is not allowed for the given context.
```

**根本原因**:
- PMax Campaign 必须使用 `MAXIMIZE_CONVERSIONS` 类型的 Bidding Strategy
- 现有账户中只有 `TARGET_CPA` 和 `TARGET_ROAS` 类型的 Bidding Strategy
- MCC 主账户可能限制 API 创建 Campaign

**现有 Bidding Strategy**:
| 名称 | 类型 | 可用 |
|-----|------|-----|
| PBPD ELHA | TARGET_CPA | ❌ 不适用于 PMax |
| tROAs Portfolio Bidding Average | TARGET_ROAS | ❌ 不适用于 PMax |
| tROAs Portfolio Bidding High | TARGET_ROAS | ❌ 不适用于 PMax |
| TH - Shopping Small Categories | TARGET_ROAS | ❌ 不适用于 PMax |
| tROAs Portfolio Bidding (MC/WC) Low | TARGET_ROAS | ❌ 不适用于 PMax |

### 2. Shopping Campaign 创建失败

**错误信息**:
```
RESOURCE_NOT_FOUND: Resource was not found. (Merchant ID = 0)
REQUIRED: The required field was not present. (shopping_setting.campaign_priority)
OPERATION_NOT_PERMITTED_FOR_CONTEXT: The operation is not allowed for the given context.
```

**根本原因**:
- Merchant ID 设置为 0，需要有效的 Merchant Center ID
- 缺少必需的 `shopping_setting.campaign_priority` 字段
- MCC 主账户可能限制 API 创建 Campaign

---

## 解决方案

### 方案 1: 使用子账户创建（推荐）

```python
# 从 MCC 账户列表中选择一个子账户
sub_accounts = [
    "7830479674",   # H19 MCC
    "1045828457",  # SeaMoney Credit - ID MCC
    "1165788658",  # Monee Credit - MY MCC
    "4837298071",  # 7-Eleven-TH
    "5472010084",  # SeaMoney - TH MCC
    "8844208336",  # SPay- VN
    "9389300632",  # Shopee- PH
    "16996295161", # Shopee-ID
]

# 使用子账户创建 Campaign
customer_id = "8844208336"  # 例如：SPay- VN
```

### 方案 2: 在界面创建所需资源

**PMax Campaign**:
1. 在 Google Ads 界面创建一个 `MAXIMIZE_CONVERSIONS` 类型的 Bidding Strategy
2. 或者在界面手动创建一个 PMax Campaign，然后复制其配置

**Shopping Campaign**:
1. 在 Google Merchants Center 创建商品 feed
2. 在 Google Ads 界面链接 Merchant Center
3. 记录 Merchant ID，用于 API 创建

### 方案 3: 使用官方 Python 示例

参考官方文档：
- https://developers.google.com/google-ads/api/docs/campaigns/performance-max
- https://developers.google.com/google-ads/api/docs/campaigns/shopping

---

## 知识库更新

已更新 `agents/ad_agent/knowledge_base/google/workflows.json`:

- ✅ `google_pmax_campaign_workflow` - 添加错误分析和解决方案
- ✅ `google_shopping_campaign_workflow` - 添加必需字段说明
- ✅ `google_network_restriction` - 更新为"已解决"（使用 Python SDK）

---

## 服务状态

```
✅ ad-agent 服务健康运行
✅ 4 平台 (meta, google, tiktok, dv360), 19 工具
✅ http://127.0.0.1:8765/
```

---

## 下一步行动

1. **选择子账户测试**: 使用子账户 ID 重新测试 PMax 和 Shopping Campaign 创建
2. **创建 Bidding Strategy**: 在界面创建 MAXIMIZE_CONVERSIONS 类型的 Bidding Strategy
3. **链接 Merchant Center**: 在界面链接 Merchant Center 获取有效 Merchant ID
4. **更新知识库**: 根据测试结果进一步完善工作流文档

---

*报告生成时间: 2026-08-25 09:46:37*
