# Google Ads PMax Campaign 测试最终报告

**测试时间**: 2026-08-25 10:11:36
**测试账户**: 9055507554 (子账户)
**测试状态**: ❌ PMax 创建失败

---

## 测试结果汇总

| 广告类型 | 状态 | Campaign ID | 说明 |
|---------|------|-------------|------|
| **Shopping** | ✅ 成功 | 24170606373 | 使用子账户 9055507554 + Merchant ID 115791065 |
| **PMax** | ❌ 失败 | - | 现有 Bidding Strategy 类型不匹配 |

---

## PMax 失败原因分析

### 问题 1: Bidding Strategy 类型不匹配

**现有 Bidding Strategy**:
| 名称 | ID | Type | 值 |
|-----|-----|------|-----|
| 1 | 12085500030 | TARGET_SPEND | 9 |
| portfolio-s1 | 12089370311 | TARGET_SPEND | 9 |

**PMax 要求**: MAXIMIZE_CONVERSIONS (type=10)

### 问题 2: SDK v25 缺少枚举

```python
# 尝试访问 BiddingStrategySchemeEnum
client.enums.BiddingStrategySchemeEnum
# AttributeError: '_EnumGetter' object has no attribute 'BiddingStrategySchemeEnum'
```

### 问题 3: HTTP API 矛盾错误

- 不设置 scheme: "The required field was not present"
- 设置 scheme: "Unknown name scheme"

---

## 解决方案

### 方案 1: 手动创建 Bidding Strategy（推荐）

在 Google Ads 界面手动创建:
1. 登录 Google Ads 账户 9055507554
2. 进入「工具和管理员」→「出价策略」
3. 点击「+ 出价策略」
4. 选择「最大化转化次数」
5. 记录创建的 Bidding Strategy Resource Name

### 方案 2: 使用 DAP 系统

DAP 系统已经支持 PMax Campaign 创建:
- 参考: `mkt-admin.test.shopee.sg/mkt/dap/ad-account/google-om/edit`
- 选择 `Maximize conversions` 作为 Bidding Strategy

### 方案 3: 升级 SDK

升级到 google-ads v26+ 可能解决枚举缺失问题。

---

## Shopping Campaign 成功详情

```
Campaign ID:  24170606373
Campaign Name: Test Shopping Campaign - 6a43bd84-...
Status:       PAUSED
Type:         SHOPPING
Merchant ID:  115791065
Priority:     0
Budget ID:    15816050555
```

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

## 服务状态

```
✅ ad-agent 服务健康运行
✅ http://127.0.0.1:8765/
✅ 4 平台 (meta, google, tiktok, dv360), 19 工具
```

---

*报告生成时间: 2026-08-25 10:11:36*
