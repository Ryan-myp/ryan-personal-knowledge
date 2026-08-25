# Google Ads PMax & Shopping Campaign 最终测试报告

**测试时间**: 2026-08-25 09:53:18
**测试账户**: 9055507554 (子账户)
**Merchant Center ID**: 115791065

---

## 测试结果汇总

| 广告类型 | 状态 | Campaign ID | 说明 |
|---------|------|-------------|------|
| **Performance Max** | ❌ 失败 | - | 缺少 MAXIMIZE_CONVERSIONS 类型 Bidding Strategy |
| **Shopping** | ✅ 成功 | 24170606373 | 使用 Merchant ID 115791065 |

---

## Shopping Campaign 创建详情

```
Campaign ID: 24170606373
Campaign Name: Test Shopping Campaign - 6a43bd84-986c-432d-a7b3-e22df9748b87
Status: PAUSED (3)
Type: SHOPPING (4)
Merchant ID: 115791065
Campaign Priority: 0
Budget ID: 15816050555
```

---

## PMax Campaign 失败原因

**错误**: `CANNOT_ATTACH_TO_BIDDING_STRATEGY`

**根本原因**:
- 子账户中只有 2 个 Bidding Strategy，类型都是 `UNKNOWN`
- PMax Campaign 需要 `MAXIMIZE_CONVERSIONS` 类型的 Bidding Strategy
- 需要在 Google Ads 界面创建新的 Bidding Strategy

**现有 Bidding Strategy**:
| 名称 | ID | Type |
|-----|-----|------|
| 1 | 12085500030 | UNKNOWN |
| portfolio-s1 | 12089370311 | UNKNOWN |

---

## 关键参数

### Shopping Campaign 必需参数
```python
campaign.shopping_setting.merchant_id = 115791065  # 有效 Merchant Center ID
campaign.shopping_setting.campaign_priority = 0     # 优先级 (0-100)
campaign.bidding_strategy = resource_name           # TARGET_ROAS 类型
```

### PMax Campaign 必需参数
```python
campaign.advertising_channel_type = PERFORMANCE_MAX
campaign.bidding_strategy = resource_name           # 必须是 MAXIMIZE_CONVERSIONS 类型
campaign.campaign_budget = resource_name
```

---

## 下一步

1. **PMax Campaign**: 在 Google Ads 界面创建 MAXIMIZE_CONVERSIONS 类型的 Bidding Strategy
2. **Shopping Campaign**: 可以继续创建 Ad Group 和 Product Scopes

---

*报告生成时间: 2026-08-25 09:53:18*
