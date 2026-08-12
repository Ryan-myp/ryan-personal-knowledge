# 广告系统面试题库

> **文档级别**: Level 4  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已创建

---

## 一、竞价系统

### Q1: RTB 竞价流程是什么样的？

```
应答流程:
1. DSP 接收 SSP 的 bid request
2. 提取用户/设备/上下文信息
3. 查询特征存储 (Redis/FastKV)
4. 预估 pCTR/pCVR (模型推理)
5. 计算 bid price = eCPA * pCTR * freq_cap
6. 返回 bid response

关键指标:
- 延迟要求: < 100ms
- 成功率: > 99%
- QPS: 万级
```

### Q2: 如何实现 RTA 过滤？

```go
// RTA 核心逻辑
func RTAFilter(ctx context.Context, userID string, adSlot string) (bool, error) {
    // 1. 本地缓存快速判断
    if cached, ok := localCache.Get(userID); ok {
        return cached.Blocked, nil
    }
    
    // 2. Redis 一致性检查
    blocked, err := redis.ZIsMember(ctx, "rta:blacklist", userID)
    if err != nil {
        return false, err
    }
    
    // 3. 异步刷新缓存
    if !blocked {
        go refreshRTACache(userID)
    }
    
    return blocked, nil
}
```

### Q3: 竞价超时如何控制？

```go
// 竞价超时控制
type BiddingTimeout struct {
    totalBudget    float64
    dailyBudget    float64
    frequencyCap   int
    pacer          *BudgetPacer
}

func (bt *BiddingTimeout) ShouldBid(bidPrice float64, userID string) bool {
    // 1. 预算检查
    if !bt.pacer.CheckDailyBudget() {
        return false
    }
    
    // 2. 频控检查
    if bt.checkFrequency(userID) {
        return false
    }
    
    return true
}
```

---

## 二、参考资料

```
核心文档:
├── RTB 协议: https://iabtechlab.com/rtb/
├── OpenRTB: https://www.iab.com/wp-content/uploads/2016/03/OpenRTB-v2-5-FINAL.pdf
└── AdRank: 内部排序算法文档
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
