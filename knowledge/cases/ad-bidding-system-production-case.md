# 广告竞价系统生产实战案例

> 深入广告实时竞价系统：架构设计、性能优化、故障排查。
> 适用对象：广告工程师、后端架构师

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     竞价系统架构                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  请求流:                                                         │
│  Publisher → ADX → DSP(我们) → 竞价引擎 → 响应                   │
│                                                                 │
│  核心组件:                                                       │
│  ├── BidRequest Handler (请求处理)                              │
│  ├── User Profiling (用户画像)                                   │
│  ├── Ad Selection (广告选择)                                     │
│  ├── Pricing Engine (定价引擎)                                   │
│  └── BidResponse Generator (响应生成)                            │
│                                                                 │
│  SLA:                                                            │
│  ├── P99 延迟 < 100ms                                           │
│  ├── 可用性 > 99.99%                                            │
│  └── QPS > 100,000                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 关键代码

```go
// 竞价处理器
type BidHandler struct {
    userProfiler  *UserProfiler
    adSelector    *AdSelector
    pricingEngine *PricingEngine
    metrics       *Metrics
}

func (h *BidHandler) Handle(ctx context.Context, req *bidproto.BidRequest) (*bidproto.BidResponse, error) {
    start := time.Now()
    
    // 1. 用户画像检索 (Redis)
    profile, err := h.userProfiler.GetProfile(ctx, req.UserId)
    if err != nil {
        h.metrics.Inc("user_profile_error")
        return h.fallbackBid(req), nil
    }
    
    // 2. 广告选择 (Elasticsearch)
    ads, err := h.adSelector.Select(ctx, req, profile)
    if err != nil {
        h.metrics.Inc("ad_select_error")
        return h.fallbackBid(req), nil
    }
    
    // 3. 定价计算 (实时)
    bids := make([]*Bid, len(ads))
    for i, ad := range ads {
        price, err := h.pricingEngine.Calculate(ctx, ad, profile, req)
        if err != nil {
            continue
        }
        bids[i] = &Bid{
            AdID:      ad.ID,
            Price:     price,
            CreativeID: ad.CreativeID,
        }
    }
    
    h.metrics.ObserveLatency("bid_latency", time.Since(start))
    h.metrics.Inc("bid_success")
    
    return &bidproto.BidResponse{Bids: bids}, nil
}

// 降级策略
func (h *BidHandler) fallbackBid(req *bidproto.BidRequest) *bidproto.BidResponse {
    return &bidproto.BidResponse{
        Bids: []*Bid{{Price: req.MaxBid * 0.8}},
    }
}
```

---

## 3. 性能优化

```go
// 批量预取用户画像
func (p *UserProfiler) BatchGet(ctx context.Context, userIDs []string) (map[string]*Profile, error) {
    // Redis Pipeline
    pipeline := p.redis.Pipeline()
    cmds := make([]*redis.StringCmd, len(userIDs))
    
    for i, id := range userIDs {
        key := fmt.Sprintf("user:profile:%s", id)
        cmds[i] = pipeline.Get(ctx, key)
    }
    
    _, err := pipeline.Exec(ctx)
    if err != nil {
        return nil, err
    }
    
    profiles := make(map[string]*Profile)
    for i, cmd := range cmds {
        if val, err := cmd.Result(); err == nil {
            var profile Profile
            json.Unmarshal([]byte(val), &profile)
            profiles[userIDs[i]] = &profile
        }
    }
    return profiles, nil
}

// 缓存优化
var profileCache = cache.New(5*time.Minute, 10*time.Minute)

func (p *UserProfiler) GetProfile(ctx context.Context, userID string) (*Profile, error) {
    if cached, ok := profileCache.Get(userID); ok {
        return cached.(*Profile), nil
    }
    
    profile, err := p.fetchFromRedis(ctx, userID)
    if err != nil {
        return nil, err
    }
    
    profileCache.Set(userID, profile)
    return profile, nil
}
```

---

## 4. 故障排查

```bash
# 监控指标
curl http://localhost:9090/metrics | grep bid_

# 常见故障
# 1. Redis 延迟飙升
redis-cli --latency-history

# 2. ES 查询慢
GET _nodes/hot_threads

# 3. GC 停顿
go tool pprof http://localhost:6060/debug/pprof/heap
```

---

## 5. 实践总结

| 问题 | 解决方案 | 效果 |
|------|----------|------|
| Redis 单点 | Cluster + Pipeline | P99 延迟降低 40% |
| ES 查询慢 | 预构建索引 | 查询延迟降低 60% |
| GC 停顿 | 对象池 + 零分配 | CPU 使用降低 30% |

**参考**: 广告系统架构设计、实时竞价最佳实践
