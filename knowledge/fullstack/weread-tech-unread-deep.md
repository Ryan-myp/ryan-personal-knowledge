
---

## Go 代码实战：技术架构通用模式

### 1. 策略模式 + 工厂模式（广告出价策略）

```go
package bidding

import (
	"context"
	"fmt"
)

// BidStrategy 出价策略接口
type BidStrategy interface {
	Name() string
	CalculateBid(ctx context.Context, req *BidRequest) (float64, error)
}

// CPCStrategy CPC出价策略
type CPCStrategy struct {
	maxBid float64
}

func (s *CPCStrategy) Name() string { return "cpc" }

func (s *CPCStrategy) CalculateBid(ctx context.Context, req *BidRequest) (float64, error) {
	bid := req.PCTR * s.maxBid
	return max(bid, req.MinCPM), nil
}

// oCPXStrategy oCPX出价策略
type oCPXStrategy struct {
	targetCost float64 // 目标转化成本
	estimatedCVR float64
}

func (s *oCPXStrategy) Name() string { return "ocpx" }

func (s *oCPXStrategy) CalculateBid(ctx context.Context, req *BidRequest) (float64, error) {
	bid := s.targetCost * req.PCTR * s.estimatedCVR
	return max(bid, req.MinCPM), nil
}

// StrategyFactory 策略工厂
type StrategyFactory struct {
	strategies map[string]BidStrategy
}

func NewStrategyFactory() *StrategyFactory {
	return &StrategyFactory{
		strategies: map[string]BidStrategy{
			"cpc":  &CPCStrategy{maxBid: 5.0},
			"ocpa": &oCPXStrategy{targetCost: 50.0, estimatedCVR: 0.02},
			"cpm":  &CPMStrategy{},
		},
	}
}

func (f *StrategyFactory) Get(name string) (BidStrategy, error) {
	strategy, ok := f.strategies[name]
	if !ok {
		return nil, fmt.Errorf("unknown strategy: %s", name)
	}
	return strategy, nil
}

// CPMStrategy CPM出价策略
type CPMStrategy struct{}

func (s *CPMStrategy) Name() string { return "cpm" }

func (s *CPMStrategy) CalculateBid(ctx context.Context, req *BidRequest) (float64, error) {
	return req.TargetCPM, nil
}
```

### 2. 中间件链（HTTP Handler）

```go
package middleware

import (
	"context"
	"net/http"
	"time"
)

// HandlerFunc HTTP handler
type HandlerFunc func(http.ResponseWriter, *http.Request)

// Middleware 中间件
type Middleware func(HandlerFunc) HandlerFunc

// Chain 中间件链
type Chain struct {
	middlewares []Middleware
	handler     HandlerFunc
}

func NewChain(handler HandlerFunc) *Chain {
	return &Chain{
		handler: handler,
	}
}

func (c *Chain) Use(mw Middleware) *Chain {
	c.middlewares = append(c.middlewares, mw)
	return c
}

func (c *Chain) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	h := c.handler
	// 从后往前包装
	for i := len(c.middlewares) - 1; i >= 0; i-- {
		h = c.middlewares[i](h)
	}
	h(w, r)
}

// 内置中间件
func Logging(next HandlerFunc) HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next(w, r)
		fmt.Printf("[%s] %s %s %v\n", r.Method, r.URL.Path, r.RemoteAddr, time.Since(start))
	}
}

func Recovery(next HandlerFunc) HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				fmt.Printf("PANIC: %v\n", err)
				http.Error(w, "Internal Server Error", 500)
			}
		}()
		next(w, r)
	}
}

func RateLimit(maxRPS int) HandlerFunc {
	limit := make(chan struct{}, maxRPS)
	for i := 0; i < maxRPS; i++ {
		limit <- struct{}{}
	}
	
	go func() {
		ticker := time.NewTicker(time.Second)
		for range ticker.C {
			<-limit
			limit <- struct{}{}
		}
	}()
	
	return func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-limit:
			next(w, r)
		default:
			http.Error(w, "Too Many Requests", 429)
		}
	}
}
```

### 自测题

<details>
<summary>Q1: 策略模式在广告出价中为什么比 if-else 好？</summary>

**答案**：

| 对比项 | if-else | 策略模式 |
|--------|---------|---------|
| 扩展性 | 改源码 | 新增策略类 |
| 测试 | 复杂 | 独立测试 |
| 开闭原则 | ❌ | ✅ |
| 运行时切换 | 困难 | 容易 |

广告平台经常需要新增出价策略——策略模式让新增策略不影响已有代码。

</details>

<details>
<summary>Q2: 中间件链的包装顺序为什么是从后往前？</summary>

**答案**：

**执行顺序**：
```
请求 → Logging → Recovery → RateLimit → Handler
响应 ← Logging ← Recovery ← RateLimit ← Handler
```

从后往前包装确保 **Logging 最先执行、最后结束**（包裹最外层）。这是标准的洋葱模型。

</details>

<details>
<summary>Q3: RateLimit 的实现有什么性能问题？生产环境如何改进？</summary>

**答案**：

**当前实现的问题**：
1. channel 操作有锁开销
2. 每秒 refill 固定数量，不能处理突发

**改进方案**：
```go
// 方案1: 令牌桶（允许突发）
// 方案2: 滑动窗口计数器（更精确）
// 方案3: 使用 Redis + Lua（分布式限流）
```

广告 API 限流推荐 Redis + Lua 脚本，保证分布式一致性。

</details>
