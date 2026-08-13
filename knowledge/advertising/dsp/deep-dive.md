# DSP 深度解析

> 深入了解 DSP 架构、实时竞价、用户画像系统。

---

## 1. 核心架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Advertiser │────▶│    DSP      │────▶│    Ad Exchange│
│  (广告主)    │     │  (需求方平台) │     │   (广告交换)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                         ┌─────▼─────┐
                                         │ Publisher │
                                         │  (发布商)  │
                                         └───────────┘
```

---

## 2. 实时竞价流程

```go
func BidRequestHandler(req *BidRequest) *BidResponse {
    // 1. 用户画像查询
    user := UserProfileCache.Get(req.User.ID)
    
    // 2. 上下文分析
    context := AnalyzeContext(req.Impression)
    
    // 3. 价值预估
    pctr := Model.Predict(user, context)
    
    // 4. 出价计算
    bid := CalculateBid(pctr, budget, competition)
    
    return &BidResponse{
        Bid: bid,
        Targeting: user.Interests,
    }
}
```

---

## 3. 关键指标

| 指标 | 公式 | 目标值 |
|------|------|--------|
| CTR | 点击 / 展示 | > 1% |
| CVR | 转化 / 点击 | > 5% |
| ROAS | 收入 / 投放 | > 200% |
| Fill Rate | 出价次数 / 请求次数 | > 80% |

---

**参考**: 实时竞价系统设计、广告技术原理
