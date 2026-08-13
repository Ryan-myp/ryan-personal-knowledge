# SSP 深度解析

> 深入了解 SSP 架构、流量管理、价格优化。

---

## 1. 核心架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Publisher  │────▶│    SSP      │────▶│  Ad Exchange │
│  (发布商)    │     │  (供给方平台) │     │  (广告交换)   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                         ┌─────▼─────┐
                                         │   DSP     │
                                         │ (需求方)   │
                                         └───────────┘
```

---

## 2. 流量管理

```go
func FlowManager(site *Site) *BidRequest {
    // 1. 流量清洗
    cleanTraffic := Clean(site.Traffic)
    
    // 2. 标签化
    labeled := Label(cleanTraffic)
    
    // 3. 预筛选
    filtered := PreFilter(labeled, site.Policy)
    
    // 4. 出价策略
    bidPrice := OptimizePrice(filtered, marketCondition)
    
    return &BidRequest{
        Impression: filtered,
        Reserve:    bidPrice,
    }
}
```

---

## 3. 收入优化

| 策略 | 说明 | 效果 |
|------|------|------|
| Floor Price | 设置底价 | 保证最低收益 |
| Header Bidding | 多源竞价 | 提高竞争度 |
| Yield Optimization | 动态优化 | 最大化收益 |
| Direct Deals | 直销合作 | 稳定收入来源 |

---

**参考**: SSP 架构设计、广告变现最佳实践
