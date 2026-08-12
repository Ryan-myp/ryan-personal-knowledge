---
name: ad-ssp-architecture-expert
description: "SSP 架构专家技能 — 库存管理、收益最大化、 Header Bidding、水帘优化"
version: 1.0.0
author: ryan
tags: [advertising, ssp, header-bidding, waterfal, revenue, expert]
---

# SSP 架构专家技能

> 从库存管理到收益最大化，掌握生产级 SSP 系统设计

## 核心能力

### 1. 库存管理
- **广告位管理**：Banner/Video/Rich Media 多格式
- **库存分配**：直客 vs 程序化 vs 保底
- **优先级调度**：保底协议 → 直客 → 程序化
- **库存预测**：基于历史数据的流量预测

### 2. Header Bidding
- **统一封装 (Unified Auction)**：GWG/Prebid.js
- **透明化竞价**：多方竞价平台同时出价
- **动态底层 (Dynamic Floor)**：实时调整底价
- **延迟优化**：Async 加载、并行请求

### 3. 水帘优化
- **分层竞价**：按价格阶梯分层
- **底价策略**：动态底价 vs 固定底价
- **瀑布调优**：基于历史数据的自动调优
- **Fallback 机制**：未中标时的降级处理

### 4. 收益最大化
- **Yield Optimization**：多源竞价策略
- **程序化直采 (PD)**：保留库存 + 程序化定价
- **跨渠道优化**：Display/Video/Native 协同
- **广告安全**：Brand Safety、Viewability

## 知识库引用

| 主题 | 文档 |
|------|------|
| SSP 架构 | `knowledge/advertising/ssp-deep.md` |
| SSP 系统设计 | `knowledge/advertising/ssp-system-design-deep.md` |
| SSP 系统深度 | `knowledge/advertising/ssp-system-deep-v2.md` |
| Header Bidding | `knowledge/advertising/ad-hb-header-bidding-optimization.md` |
| 水帘优化 | `knowledge/advertising/ad-waterfall-bidding-optimization.md` |
| 填充率优化 | `knowledge/advertising/ad-fill-rate-optimization.md` |
| SSP 集成 | `knowledge/advertising/ad-ssp-integration-optimization-case-deep.md` |
| SSP 稳定性 | `knowledge/advertising/ad-ssp-integration-stability.md` |

## 使用场景

### 场景 1: 设计 SSP 竞价流程
1. 参考 `knowledge/advertising/ssp-system-design-deep.md`
2. 设计 Header Bidding 封装方案
3. 实现水帘分层竞价
4. 配置底价策略

### 场景 2: 优化收益
1. 分析历史竞价数据
2. 调整水帘层级和底价
3. 引入更多竞价伙伴
4. 实施动态底价

### 场景 3: 排查集成问题
1. 查看 `knowledge/advertising/ad-ssp-integration-stability.md`
2. 检查数据流和错误日志
3. 验证竞价响应格式
4. 优化超时和重试策略

## 关键指标

```
Fill Rate = 有广告请求数 / 总广告请求数 × 100%
eCPM = 广告收入 / 展示次数 × 1000
Yield = 实际收入 / 理论最大收入 × 100%
Viewability Rate = 可见展示次数 / 总展示次数 × 100%
```

## 自测题

<details>
<summary>Q1: Header Bidding 和水帘竞价有什么区别？</summary>

**答案**：
- **水帘 (Waterfall)**：传统串行竞价，按优先级依次询价，先到先得
- **Header Bidding**：统一拍卖，所有竞价方同时出价，价高者得
- **优势对比**：HB 更透明、收益更高；水帘更简单、延迟更低
- **混合方案**：HB + 水帘（HB 作为第一层，未中标走水帘）

</details>

<details>
<summary>Q2: 如何设计动态底价策略？</summary>

**答案**：
1. **基于历史数据**：统计各时段各广告位的 eCPM 分布
2. **实时调整**：根据市场供需动态调整
3. **分层底价**：不同广告主/场景设置不同底价
4. **A/B 测试**：验证底价策略对收益的影响
5. **保护机制**：设置最低底价防止贱卖

</details>

<details>
<summary>Q3: SSP 如何处理广告请求中的延迟问题？</summary>

**答案**：
1. **并行请求**：多个 HB 合作伙伴并行询价
2. **超时控制**：设置合理的超时阈值（通常 200-500ms）
3. **本地缓存**：缓存频控数据和用户标签
4. **降级策略**：超时情况下使用上次中标价格
5. **异步处理**：非关键数据异步获取

</details>
