---
schema_version: "1"
id: ad-best-practices
title: 广告最佳实践
layer: experience
knowledge_type: best_practice
platform: all
source: 专家经验 + 实测数据
source_ref: "internal://ad-agent/playbook/ad-best-practices"
version: "1.0.0"
confidence: 0.75
updated_at: "2026-08-26"
tags: [best-practice, budget, naming]
status: published
source_kind: "internal"
authority: "operator"
evidence_level: "provisional"
last_verified_at: "2026-08-26"
---

# 广告最佳实践

> **来源**: 专家经验 + 实测数据
> **更新时间**: 2026-08-26

## 账户结构最佳实践

### 命名规范
- 格式：`{业务}-{产品}-{定向}-{格式}`
- 示例：`ecommerce-shoes-us-search`

### 层级优化
- 每个 Campaign 只放一个目标
- AdGroup 数量控制在 5-15 个
- 使用标签 (Labels) 进行分类管理

### 预期效果
- 提升管理效率 50%+
- 降低操作错误率

## 预算分配最佳实践

### 测试阶段
- 小预算多组合（$50-100/天）
- 测试不同定向和创意
- 保持至少 3-5 个活跃 AdGroup

### 放量阶段
- 集中预算到表现最好的 AdGroup
- 使用 CBO 自动预算分配
- 逐步扩大定向范围

### 预期效果
- 提升 ROAS 20-30%

## 关键词策略

### 搜索广告
- 使用短语匹配（Phrase Match）为主
- 添加否定关键词排除不相关流量
- 定期清理低效关键词

### 购物广告
- 优化商品标题和描述
- 使用商品分类细化定向
- 定期同步商品数据

## 出价策略

### Target CPA
- 适合有历史转化数据的账户
- 建议目标 CPA 不超过实际 CPA 的 120%
- 不存在脱离平台、目标、事件延迟、预算和账户规模的通用最低转化数；样本不足时降低结论置信度并延长观察窗口

### Maximize Conversions
- 适合新账户或数据不足
- 不设 CPA 上限，可能花费较多
- 配合预算控制使用

## 参考

- [Google Ads 最佳实践](https://support.google.com/google-ads/answer/2474563)
- [Meta 广告投放指南](https://www.facebook.com/business/learn)
- [TikTok Ads 最佳实践](https://business-api.tiktok.com/portal/docs)

## 质量护栏

最佳实践只有在适用条件明确时才可复用。每条建议补充平台、目标、对象层级、数据窗口、前提、主/保护指标、失效条件和回退动作；固定 benchmark 只能作为待验证假设，不能写成保证。涉及平台动态字段、政策或策略枚举时，必须回查当前官方文档和 Tool schema。
