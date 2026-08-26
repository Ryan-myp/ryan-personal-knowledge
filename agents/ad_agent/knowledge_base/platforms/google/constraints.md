# Google Ads 参数约束规则

> **来源**: 官方文档 + API 实测
> **更新时间**: 2026-08-26

## Campaign → AdGroup 约束

| Campaign Type | 支持的 AdGroup 类型 |
|---------------|---------------------|
| SEARCH | TEXT_AD, RESPONSIVE_SEARCH_AD |
| SHOPPING | PRODUCT_AD |
| VIDEO | VIDEO_AD |
| MAX | 需要 Asset Group |

## 参数约束规则

### 1. 名称长度限制
- Campaign: 最大 60 字符
- AdGroup: 最大 60 字符
- Keyword: 最大 80 字符

### 2. 预算约束
- 一个 CampaignBudget 可关联多个 Campaign
- 但一个 Campaign 只能关联一个 Budget
- Budget 不能与 AdGroup 关联

### 3. 出价策略约束
- 每个 Campaign 只能有一个 BiddingStrategy
- 支持的策略：
  - MANUAL_CPC
  - TARGET_CPA
  - TARGET_ROAS
  - MAXIMIZE_CONVERSIONS
  - TARGET_OUTCOME_ROAS

### 4. 关键词约束
- 同一 AdGroup 内不能有重复关键词
- 相同关键词不能有相同 MatchType
- 关键词数量限制：AdGroup 最多 20000 个

## 错误处理

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 8 | RESOURCE_EXHAUSTED | 限流，指数退避重试 |
| 37 | DUPLICATE_ELEMENT | 重复元素 |
| 102 | VALIDATION_ERROR | 参数验证失败 |
| 104 | HEADER_ERROR | 请求头错误 |
| 116 | mutually_exclusive | 互斥参数 |

## 参考

- [错误码参考](https://developers.google.com/google-ads/api/docs/errors/error-codes)
- [约束规则文档](https://developers.google.com/google-ads/api/docs/campaigns/constraints)
