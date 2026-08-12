---
name: ad-bidding-expert
description: "广告竞价专家技能 — 覆盖 RTB/RTA 实时竞价、出价策略、质量分、反作弊、DSP/SSP 竞价引擎设计"
version: 1.0.0
author: ryan
tags: [advertising, bidding, rtb, dsp, ssp, expert]
---

# 广告竞价专家技能

> 从广告竞价系统的架构到实现，提供专家级知识支持

## 核心能力

### 1. 竞价系统设计
- RTB (Real-Time Bidding) 全流程
- RTA (Real-Time API) 实时决策
- 第一价格 vs 第二价格拍卖
- 质量分计算与调整

### 2. 出价策略
- CPC / CPM / OCPM / vCPM
- 智能出价（tCPA, tROAS）
- 预算约束下的动态出价
- 频控与频次优化

### 3. 算法与模型
- pCTR / pCVR 预估模型
- eCPM 排序公式
-  Bid Shading 出价调整
- 多臂老虎机 / Bandit 策略

### 4. 工程实现
- 高并发竞价引擎（Go）
- 低延迟优化（< 100ms）
- 分布式预算追踪
- 降级与容灾策略

## 知识库引用

| 主题 | 文档 |
|------|------|
| RTB 架构 | `knowledge/advertising/rtb-system-design-deep.md` |
| 竞价引擎 | `knowledge/advertising/ad-bidding-engine-deep.md` |
| DSP 竞价 | `knowledge/advertising/dsp-bidding-engine-deep.md` |
| 出价策略 | `knowledge/advertising/ad-bidding-strategy-deep.md` |
| 高频优化 | `knowledge/advertising/ad-rtb-performance-tuning.md` |
| 性能压测 | `knowledge/advertising/capacity-planning-stress-test.md` |
| 故障案例 | `knowledge/advertising/ad-bidding-system-failure.md` |

## 使用场景

### 场景 1: 设计竞价系统
1. 查看 `knowledge/advertising/ad-system-architecture-deep.md` 了解整体架构
2. 参考 `knowledge/advertising/dsp-high-concurrency-design-deep.md` 了解高并发设计
3. 查看 `knowledge/advertising/go-high-concurrency-bidding-system-deep.md` 学习 Go 实现

### 场景 2: 排查竞价延迟问题
1. 查看 `knowledge/advertising/ad-realtime-bidding-latency.md`
2. 查看 `knowledge/advertising/ad-bidding-timeout-case-deep.md`
3. 使用 `knowledge/advertising/ad-observability-deep.md` 的监控方案

### 场景 3: 优化出价策略
1. 查看 `knowledge/advertising/ad-bidding-algorithm-deep.md`
2. 查看 `knowledge/advertising/ad-rl-bidding-deep.md`（强化学习出价）
3. 查看 `knowledge/advertising/ad-ecpm-estimation-fix.md`

## 关键公式

```
eCPM = bid × pCTR × 1000
实际出价 = bid × BidShadingFactor
QualityScore = α × CTR + β × 相关度 + γ × 落地页体验
```

## 自测题

<details>
<summary>Q1: 为什么实时竞价要用第二价格拍卖而不是第一价格？</summary>

**答案**：
1. **激励真实出价**：第二价格下，最优策略是报出真实价值
2. **减少价格波动**：中标价由第二高价决定，避免恶性竞价
3. **保护广告主**：不会因竞争过度而支付过高价格
4. **但实践中**：许多平台采用第一价格+智能调价，平衡收入与用户体验
</details>

<details>
<summary>Q2: Bid Shading 的原理是什么？如何实现？</summary>

**答案**：
Bid Shading 通过历史中标数据学习价格分布，动态调整出价：
```go
func BidShading(originalBid, historicalWinRate float64) float64 {
    // 如果历史中标率 > 90%，降低出价
    if historicalWinRate > 0.9 {
        return originalBid * 0.95
    }
    // 如果历史中标率 < 10%，提高出价
    if historicalWinRate < 0.1 {
        return originalBid * 1.05
    }
    return originalBid
}
```
核心：在保持中标率的前提下最大化 ROI。
</details>

<details>
<summary>Q3: pCTR 模型冷启动如何解决？</summary>

**答案**：
1. **相似素材预热**：用同类素材的历史数据初始化
2. **元数据特征**：素材类型、广告主行业、落地页质量
3. **Cross-Domain Transfer**：从其他平台迁移模型
4. **探索-利用平衡**：ε-greedy 或 Thompson Sampling
</details>
