# 广告平台知识库

> Google / Meta / TikTok / Amazon — 从入门到源码级

## 文档索引

| 分类 | 文档 | 说明 |
|------|------|------|
| 基础知识 | [ad-system-architecture](../ad-ads/ad-system-architecture.md) | 广告系统架构概览 |
| 深度分析 | [ad-system-architecture-deep](../ad-ads/ad-system-architecture-deep.md) | 架构源码级深度 |
| 数据分析 | [ad-analytics](../ad-ads/ad-analytics.md) | 广告数据分析 |
| 深度分析 | [ad-analytics-deep](../ad-ads/ad-analytics-deep.md) | 数据分析深度 |

## 学习路线

```
广告系统基础 (CPC/CPM/OCPM 竞价机制)
    ↓
广告平台 API (Google/Meta/TikTok/Amazon)
    ↓
竞价优化 (RTA/RTB 实时竞价)
    ↓
创意生成 (DSP Creative Generation)
    ↓
数据分析 (归因模型/增量测量)
```

---

## 自测题

### 问题 1
广告竞价中 CPC、CPM、OCPM 各适用于什么场景？

<details>
<summary>查看答案</summary>

1. **CPC (按点击付费)**: 适合品牌曝光+流量获取，控制单次点击成本
2. **CPM (按展示付费)**: 适合品牌广告，按千次展示计费
3. **OCPM (优化千次展示)**: 平台根据转化概率自动出价，适合效果广告
4. **实际选择**: 初期用 CPC 收集数据，稳定后切换到 OCPM 优化 ROI

</details>

### 问题 2
为什么广告系统要用实时竞价（RTB）而不是固定价格？

<details>
<summary>查看答案</summary>

1. **效率**: 实时竞价让广告价值反映在价格上
2. **灵活性**: 不同用户、不同场景可以不同出价
3. **公平**: 价高者得，资源分配效率最高
4. **规模化**: RTB 平台可以处理百万级/秒的竞价请求
5. **Go 实现**: 用 goroutine 池处理高并发竞价请求

</details>