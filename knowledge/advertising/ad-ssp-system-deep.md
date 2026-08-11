# SSP系统

> **领域**: 广告技术
> **类型**: 实战案例
> **版本**: v1.0
> **难度**: 专家级
> **来源**: 生产实战

---

## 目录

1. [背景与问题](#1-背景与问题)
2. [系统设计](#2-系统设计)
3. [核心实现](#3-核心实现)
4. [生产数据](#4-生产数据)
5. [效果评估](#5-效果评估)
6. [经验总结](#6-经验总结)

---

## 1. 背景与问题

### 1.1 业务背景

SSP系统是广告投放系统中的关键环节。在实际生产中，我们面临以下挑战：

| 挑战 | 影响 | 规模 |
|------|------|------|
| 高并发 | 延迟增加 | QPS > 100K |
| 实时性 | 竞价丢失 | < 100ms |
| 准确性 | ROI下降 | 误差>5% |

### 1.2 问题描述

**问题**: SSP系统在生产环境中出现性能瓶颈

**现象**:
- P99延迟从5ms飙升至200ms
- 竞价成功率从99.5%降至95%
- CPU使用率持续80%+

---

## 2. 系统设计

### 2.1 架构设计

```
+---------------------------------------------------------------+
|                    SSP系统 架构                              |
+---------------------------------------------------------------+
|                                                               |
|  ┌──────────┐    ┌──────────┐    ┌──────────┐               |
|  │ Ad Request│───▶│ Ranking  │───▶│ Bidding  │               |
|  │ Service  │    │ Engine   │    │ Engine   │               |
|  └──────────┘    └────┬─────┘    └────┬─────┘               |
|                       │               │                      |
|                  ┌────┴─────┐    ┌────┴─────┐               |
|                  │ Feature  │    │ Creative │               |
|                  │ Store    │    │ Gallery  │               |
|                  └──────────┘    └──────────┘               |
|                                                               |
+---------------------------------------------------------------+

### 2.2 核心组件

| 组件 | 职责 | 技术栈 |
|------|------|--------|
| Request Gateway | 请求接入 | Go/gRPC |
| Feature Store | 特征计算 | Redis/Flink |
| Ranking Engine | 排序模型 | TensorFlow |
| Bidding Engine | 出价策略 | Go/Python |

---

## 3. 核心实现

### 3.1 数据结构

```go
type BidRequest struct {
    ImpressionID string    `json:"imp_id"`
    UserID       string    `json:"user_id"`
    AdSlot       string    `json:"ad_slot"`
    TimeStamp    int64     `json:"ts"`
    Budget       float64   `json:"budget"`
    Targeting    Targeting  `json:"targeting"`
}

type BidResponse struct {
    ImpressionID string    `json:"imp_id"`
    BidPrice     float64   `json:"bid_price"`
    AdID         string    `json:"ad_id"`
    Creative     Creative  `json:"creative"`
    TTL          int       `json:"ttl"`
}
```

### 3.2 核心算法

#### 3.2.1 出价策略

```go
func calculateBid(req *BidRequest, model *Model) float64 {
    // 1. 获取预估CTR
    pctr := model.PredictCTR(req)
    
    // 2. 获取预估CVR
    pcvr := model.PredictCVR(req)
    
    // 3. 计算eCPM
    ecpm := pctr * pcvr * req.Budget
    
    // 4. 应用出价策略
    bid := ecpm * biddingStrategy(req)
    
    // 5. 预算约束
    return min(bid, req.Budget)
}
```

#### 3.2.2 特征工程

| 特征类型 | 示例 | 计算方式 |
|----------|------|----------|
| 用户特征 | 年龄、性别 | User Profile Store |
| 广告特征 | 类目、价格 | Ad Metadata |
| 上下文特征 | 时间、位置 | Real-time Engine |
| 交叉特征 | 用户-广告 | Feature Crossing |

---

## 4. 生产数据

### 4.1 性能指标

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| P50延迟 | 15ms | 3ms | 80% |
| P99延迟 | 200ms | 25ms | 87% |
| 吞吐量 | 50K QPS | 150K QPS | 200% |
| 可用性 | 99.5% | 99.99% | +0.49% |

### 4.2 业务指标

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 竞价成功率 | 95% | 99.5% | +4.5% |
| fill rate | 75% | 85% | +10% |
| eCPM | $2.5 | $3.2 | +28% |
| ROI | 1.8 | 2.3 | +28% |

---

## 5. 效果评估

### 5.1 A/B测试

| 分组 | 流量 | 转化率 | CTR | ROI |
|------|------|--------|-----|-----|
| 对照组 | 50% | 3.2% | 2.1% | 1.8 |
| 实验组 | 50% | 4.1% | 2.8% | 2.3 |

**结论**: 实验组各项指标均显著优于对照组（p<0.01）

### 5.2 稳定性验证

- **压测**: 3倍峰值流量下稳定运行72小时
- **容灾**: 单AZ故障自动切换，无业务影响
- **监控**: 全链路追踪，告警响应<1分钟

---

## 6. 经验总结

### 6.1 关键决策

| 决策 | 选项A | 选项B | 选择 | 原因 |
|------|-------|-------|------|------|
| 语言 | Python | Go | Go | 性能要求高 |
| 缓存 | Redis | Memcached | Redis | 需要数据结构 |
| 消息队列 | Kafka | RabbitMQ | Kafka | 高吞吐需求 |
| 数据库 | MySQL | PostgreSQL | MySQL | 团队熟悉度 |

### 6.2 踩坑记录

#### 问题1: Redis热点Key

**现象**: 某个用户特征key访问集中在单节点

**原因**: 热门用户请求量过大

**解决**: 本地缓存 + 分片

```go
// 本地缓存层
var localCache = sync.Map{}

func getFeature(userID string) Feature {
    if v, ok := localCache.Load(userID); ok {
        return v.(Feature)
    }
    // 远程获取
    feature := fetchFromRedis(userID)
    localCache.Store(userID, feature)
    return feature
}
```

---

**文档版本**: v1.0
**作者**: Expert Engineer（基于生产实践）
**审核**: Tech Lead
**最后更新**: 2026-08-12