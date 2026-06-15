# 广告系统容灾与降级策略

> 故障切换/降级方案/熔断策略/灰度发布/混沌工程

---

## 第一部分：入门引导（5 分钟速览）

### 广告平台故障场景

| 故障 | 影响 | 应对策略 |
|------|------|---------|
| 数据库宕机 | 无法扣减预算 | 降级到本地缓存 |
| Redis 集群故障 | 用户画像丢失 | 降级到 MySQL |
| Kafka 分区故障 | 日志丢失 | 降级到本地文件 |
| 机房断电 | 服务不可用 | 多机房容灾 |
| 代码 Bug | 竞价失败 | 快速回滚 |

---

## 第二部分：降级策略

### 2.1 分级降级

```go
package downgrade

import (
    "context"
)

type DowngradeManager struct {
    level int  // 0: 正常, 1: 部分降级, 2: 完全降级
}

func (dm *DowngradeManager) GetLevel() int {
    return dm.level
}

func (dm *DowngradeManager) SetLevel(level int) {
    dm.level = level
}

// 竞价降级
func (dm *DowngradeManager) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    switch dm.level {
    case 0: // 正常
        return dm.fullBid(ctx, req)
    case 1: // 部分降级
        return dm.partialBid(ctx, req)
    case 2: // 完全降级
        return dm.fallbackBid(ctx, req)
    default:
        return nil, fmt.Errorf("unknown downgrade level")
    }
}

func (dm *DowngradeManager) fullBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 完整竞价流程
    profile := dm.getUserProfile(req.UserID)
    ctr := dm.predictCTR(profile)
    cvr := dm.predictCVR(profile)
    price := ctr * cvr * req.TargetCPA
    return &BidResponse{Price: price}, nil
}

func (dm *DowngradeManager) partialBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 降级：不使用用户画像
    price := req.BaseBid * 0.8  // 降低 20%
    return &BidResponse{Price: price}, nil
}

func (dm *DowngradeManager) fallbackBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 完全降级：固定出价
    return &BidResponse{Price: req.FloorPrice}, nil
}
```

### 2.2 服务降级

```go
// 用户画像降级
type UserProfileFallback struct {
    localCache map[string]*UserProfile
}

func (f *UserProfileFallback) Get(userID string) (*UserProfile, bool) {
    // 1. 尝试本地缓存
    if profile, ok := f.localCache[userID]; ok {
        return profile, true
    }
    
    // 2. 降级到默认画像
    return &UserProfile{
        Age: 25,
        Gender: 0.5,
        Interests: []string{"tech"},
    }, false
}
```

---

## 第三部分：熔断与限流

### 3.1 熔断器

```go
type CircuitBreaker struct {
    state        CircuitState
    failureCount int
    successCount int
    lastFailTime time.Time
    timeout      time.Duration
    threshold    int
    halfOpenMax  int
}

type CircuitState int

const (
    Closed CircuitState = iota
    Open
    HalfOpen
)

func (cb *CircuitBreaker) AllowRequest() bool {
    switch cb.state {
    case Closed:
        return true
    case Open:
        if time.Since(cb.lastFailTime) > cb.timeout {
            cb.state = HalfOpen
            cb.successCount = 0
            return true
        }
        return false
    case HalfOpen:
        return cb.successCount < cb.halfOpenMax
    }
    return false
}

func (cb *CircuitBreaker) RecordSuccess() {
    if cb.state == HalfOpen {
        cb.successCount++
        if cb.successCount >= cb.halfOpenMax {
            cb.state = Closed
            cb.failureCount = 0
        }
    } else {
        cb.failureCount = 0
    }
}

func (cb *CircuitBreaker) RecordFailure() {
    cb.failureCount++
    cb.lastFailTime = time.Now()
    if cb.failureCount >= cb.threshold {
        cb.state = Open
    }
}
```

### 3.2 限流器

```go
type RateLimiter struct {
    tokens     chan struct{}
    refillRate int
    maxTokens  int
}

func NewRateLimiter(rate, burst int) *RateLimiter {
    rl := &RateLimiter{
        tokens:     make(chan struct{}, burst),
        refillRate: rate,
        maxTokens:  burst,
    }
    
    for i := 0; i < burst; i++ {
        rl.tokens <- struct{}{}
    }
    
    go rl.refill()
    return rl
}

func (rl *RateLimiter) Wait(ctx context.Context) error {
    select {
    case <-rl.tokens:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    }
}

func (rl *RateLimiter) refill() {
    ticker := time.NewTicker(time.Second / time.Duration(rl.refillRate))
    defer ticker.Stop()
    
    for range ticker.C {
        select {
        case rl.tokens <- struct{}{}:
        default:
        }
    }
}
```

---

## 第四部分：灰度发布

### 4.1 蓝绿部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bidding-service-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bidding-service
      version: blue
  template:
    metadata:
      labels:
        app: bidding-service
        version: blue
    spec:
      containers:
      - name: server
        image: registry.example.com/bidding-service:v1.2.3
---
apiVersion: v1
kind: Service
metadata:
  name: bidding-service
spec:
  selector:
    app: bidding-service
    version: blue  # 指向蓝环境
  ports:
  - port: 80
    targetPort: 8080
```

### 4.2 金丝雀发布

```go
type CanaryRelease struct {
    canaryRatio float64  // 金丝雀流量比例
}

func (cr *CanaryRelease) ShouldUseCanary() bool {
    rand := rand.Float64()
    return rand < cr.canaryRatio
}

func (cr *CanaryRelease) RouteRequest(req *Request) string {
    if cr.ShouldUseCanary() {
        return "canary"
    }
    return "stable"
}
```

---

## 第五部分：自测题

### 问题 1
广告系统降级策略有哪些？

<details>
<summary>查看答案</summary>

1. 分级降级：正常 → 部分 → 完全
2. 用户画像降级：使用默认画像
3. 竞价降级：固定出价
4. 日志降级：本地文件
5. 数据库降级：缓存兜底

</details>

### 问题 2
熔断器为什么需要 HalfOpen 状态？

<details>
<summary>查看答案</summary>

1. Closed: 正常，允许请求
2. Open: 故障，拒绝请求
3. HalfOpen: 试探性允许
4. 避免误判：故障恢复后自动切换
5. Go 实现：CircuitBreaker 状态机

</details>

### 问题 3
灰度发布为什么重要？

<details>
<summary>查看答案</summary>

1. 降低发布风险
2. 快速回滚
3. A/B 测试验证效果
4. 逐步放量
5. 蓝绿/金丝雀两种策略

</details>

---

*本文档基于广告系统容灾与降级经验整理。*