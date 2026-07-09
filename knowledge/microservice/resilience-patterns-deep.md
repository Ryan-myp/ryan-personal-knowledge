# 微服务弹性模式深度实战：Circuit Breaker / Bulkhead / Rate Limiter / Retry

> **来源**：知识补全 + 生产实践  
> **创建日期**：2026-07-09  
> **深度等级**：🟢深（源码级 + 生产排障）  
> **对应技能**：ad-architecture-high-concurrency、ad-distributed-arch

---

## 一、为什么微服务需要弹性模式？

### 1.1 类比：交通系统 vs 微服务

想象城市交通系统：

```
传统单体架构 = 一条主干道
├── 堵车 → 整条路瘫痪
└── 修路 → 全城交通停止

微服务架构 = 城市路网
├── 某条路堵车 → 其他路正常
├── 但如果没有交通管制 → 堵车会蔓延到整个城市
└── 弹性模式 = 红绿灯 + 收费站 + 应急车道
```

**微服务的"连锁故障"场景：**

```
用户请求 ──→ API Gateway ──→ 订单服务 ──→ 库存服务
                                        └──→ 支付服务
                                                   └──→ 银行网关

如果银行网关响应慢（5秒）：
├── 支付服务线程池耗尽
├── 订单服务等待支付超时，线程也耗尽
└── API Gateway 所有连接都被占用 → 全站不可用

这就是"级联故障"——一个服务的延迟拖垮整个系统。
```

### 1.2 弹性模式的四大支柱

| 模式 | 解决的问题 | 核心思想 | 类比 |
|------|-----------|---------|------|
| **Circuit Breaker** | 防止对故障服务的无限重试 | 快速失败，给故障服务恢复时间 | 保险丝：电流过大时自动断开 |
| **Bulkhead** | 防止资源耗尽蔓延 | 隔离不同业务的资源 | 船舱分隔：一个舱进水不沉船 |
| **Rate Limiter** | 防止流量洪峰打垮服务 | 限制请求速率 | 收费站：限制车辆通过速度 |
| **Retry with Backoff** | 处理瞬态故障 | 指数退避重试 | 打电话：忙线后隔一会儿再打 |

---

## 二、Circuit Breaker（熔断器）

### 2.1 三种状态转换

```
                    失败率 > 阈值
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│  CLOSED   │───→│ OPEN         │───→│ HALF-OPEN     │
│ (正常)    │    │ (熔断打开)   │    │ (半开探测)    │
│           │    │              │    │              │
│ 请求正常  │    │ 快速失败     │    │ 少量试探请求  │
│ 通过      │    │ 不转发到下游 │    │ 成功则关闭    │
└──────────┘    └──────────────┘    └──────────────┘
       ↑                                      │
       └────────── 成功数恢复 ─────────────────┘
```

**关键参数：**

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| failureThreshold | 50% | 失败率超过此值触发熔断 |
| minimumCalls | 20 | 最小调用次数（避免样本太少误判） |
| sleepWindow | 30s | 熔断后等待多久尝试恢复 |
| successThreshold | 5 | 半开状态下连续成功多少次才关闭 |

### 2.2 Go 源码级实现

```go
package resilience

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// State represents the circuit breaker state
type State int

const (
	StateClosed   State = iota // 正常，请求通过
	StateOpen                  // 熔断，快速失败
	StateHalfOpen              // 半开，试探性放行
)

func (s State) String() string {
	switch s {
	case StateClosed:
		return "CLOSED"
	case StateOpen:
		return "OPEN"
	case StateHalfOpen:
		return "HALF-OPEN"
	default:
		return "UNKNOWN"
	}
}

// Config holds circuit breaker configuration
type Config struct {
	FailureThreshold float64       // 失败率阈值 (0.0 ~ 1.0)
	MinimumCalls     int           // 最小调用次数
	SleepWindow      time.Duration // 熔断持续时间
	SuccessThreshold int           // 半开成功阈值
}

// CircuitBreaker implements the circuit breaker pattern
type CircuitBreaker struct {
	config Config
	
	// 状态
	state        atomic.Value // 存储 State
	stateMu      sync.RWMutex // 状态切换锁
	
	// 计数器
	totalCalls   atomic.Int64
	failureCalls atomic.Int64
	successCalls atomic.Int64
	
	// 时间控制
	lastFailureTime atomic.Int64 // Unix nanoseconds
	openedAt        atomic.Int64 // 熔断开启时间
	
	// 回调
	onStateChange func(State, State)
}

// NewCircuitBreaker creates a new circuit breaker with default config
func NewCircuitBreaker(name string) *CircuitBreaker {
	cb := &CircuitBreaker{
		config: Config{
			FailureThreshold: 0.5,
			MinimumCalls:     20,
			SleepWindow:      30 * time.Second,
			SuccessThreshold: 5,
		},
	}
	cb.state.Store(StateClosed)
	return cb
}

// AllowRequest checks if request should be allowed
func (cb *CircuitBreaker) AllowRequest(ctx context.Context) error {
	state := cb.getState()
	
	switch state {
	case StateClosed:
		return cb.allowInClosed(ctx)
	case StateOpen:
		return cb.allowInOpen(ctx)
	case StateHalfOpen:
		return cb.allowInHalfOpen(ctx)
	default:
		return fmt.Errorf("unknown state: %v", state)
	}
}

// allowInClosed handles requests when circuit is closed
func (cb *CircuitBreaker) allowInClosed(ctx context.Context) error {
	cb.totalCalls.Add(1)
	return nil
}

// allowInOpen handles requests when circuit is open
func (cb *CircuitBreaker) allowInOpen(ctx context.Context) error {
	if cb.isSleepWindowElapsed() {
		// 切换到半开状态
		cb.setState(StateHalfOpen)
		cb.successCalls.Store(0)
		return nil
	}
	return fmt.Errorf("circuit breaker is OPEN, request rejected")
}

// allowInHalfOpen handles requests when circuit is half-open
func (cb *CircuitBreaker) allowInHalfOpen(ctx context.Context) error {
	cb.totalCalls.Add(1)
	return nil
}

// RecordSuccess records a successful call
func (cb *CircuitBreaker) RecordSuccess() {
	cb.successCalls.Add(1)
	
	state := cb.getState()
	if state == StateHalfOpen && cb.successCalls.Load() >= int64(cb.config.SuccessThreshold) {
		cb.setState(StateClosed)
		cb.resetCounters()
	}
}

// RecordFailure records a failed call
func (cb *CircuitBreaker) RecordFailure() {
	cb.failureCalls.Add(1)
	cb.lastFailureTime.Store(time.Now().UnixNano())
	
	state := cb.getState()
	if state == StateHalfOpen {
		// 半开状态下失败，立即重新熔断
		cb.setState(StateOpen)
		cb.openedAt.Store(time.Now().UnixNano())
		return
	}
	
	// 关闭状态下检查是否达到熔断条件
	if cb.shouldTrip() {
		cb.setState(StateOpen)
		cb.openedAt.Store(time.Now().UnixNano())
	}
}

// shouldTrip determines if circuit should trip
func (cb *CircuitBreaker) shouldTrip() bool {
	total := cb.totalCalls.Load()
	if total < int64(cb.config.MinimumCalls) {
		return false
	}
	
	failures := cb.failureCalls.Load()
	failureRate := float64(failures) / float64(total)
	
	return failureRate >= cb.config.FailureThreshold
}

// isSleepWindowElapsed checks if sleep window has passed
func (cb *CircuitBreaker) isSleepWindowElapsed() bool {
	openedAt := cb.openedAt.Load()
	if openedAt == 0 {
		return false
	}
	return time.Since(time.Unix(0, openedAt)) > cb.config.SleepWindow
}

// getState returns current state
func (cb *CircuitBreaker) getState() State {
	s, _ := cb.state.Load().(State)
	return s
}

// setState changes state
func (cb *CircuitBreaker) setState(newState State) {
	oldState := cb.getState()
	if oldState != newState {
		cb.state.Store(newState)
		if cb.onStateChange != nil {
			cb.onStateChange(oldState, newState)
		}
	}
}

// resetCounters resets all counters
func (cb *CircuitBreaker) resetCounters() {
	cb.totalCalls.Store(0)
	cb.failureCalls.Store(0)
	cb.successCalls.Store(0)
}

// Stats returns current breaker statistics
func (cb *CircuitBreaker) Stats() map[string]interface{} {
	return map[string]interface{}{
		"state":         cb.getState(),
		"total_calls":   cb.totalCalls.Load(),
		"failure_calls": cb.failureCalls.Load(),
		"success_calls": cb.successCalls.Load(),
		"failure_rate":  cb.getFailureRate(),
	}
}

func (cb *CircuitBreaker) getFailureRate() float64 {
	total := cb.totalCalls.Load()
	if total == 0 {
		return 0
	}
	return float64(cb.failureCalls.Load()) / float64(total)
}
```

### 2.3 与 HTTP Client 集成

```go
package httpresilience

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"yourproject/resilience"
)

// ResilientHTTPClient wraps http.Client with circuit breaker and retry
type ResilientHTTPClient struct {
	client       *http.Client
	breaker      *resilience.CircuitBreaker
	maxRetries   int
	retryDelay   time.Duration
}

func NewResilientHTTPClient(timeout time.Duration) *ResilientHTTPClient {
	return &ResilientHTTPClient{
		client: &http.Client{
			Timeout: timeout,
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 10,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		breaker:    resilience.NewCircuitBreaker("payment-service"),
		maxRetries: 3,
		retryDelay: 100 * time.Millisecond,
	}
}

// Do executes HTTP request with resilience
func (rc *ResilientHTTPClient) Do(ctx context.Context, req *http.Request) (*http.Response, error) {
	var lastErr error
	
	for attempt := 0; attempt <= rc.maxRetries; attempt++ {
		// 1. 检查熔断器
		if err := rc.breaker.AllowRequest(ctx); err != nil {
			return nil, fmt.Errorf("circuit breaker open: %w", err)
		}
		
		// 2. 执行请求
		resp, err := rc.client.Do(req.WithContext(ctx))
		if err != nil {
			rc.breaker.RecordFailure()
			lastErr = err
			
			// 指数退避
			if attempt < rc.maxRetries {
				delay := rc.retryDelay * time.Duration(1<<uint(attempt))
				select {
				case <-ctx.Done():
					return nil, ctx.Err()
				case <-time.After(delay):
				}
			}
			continue
		}
		
		// 3. 检查 HTTP 状态码
		if resp.StatusCode >= 500 {
			resp.Body.Close()
			rc.breaker.RecordFailure()
			lastErr = fmt.Errorf("server error: %d", resp.StatusCode)
			
			if attempt < rc.maxRetries {
				delay := rc.retryDelay * time.Duration(1<<uint(attempt))
				select {
				case <-ctx.Done():
					return nil, ctx.Err()
				case <-time.After(delay):
				}
			}
			continue
		}
		
		// 4. 成功
		rc.breaker.RecordSuccess()
		return resp, nil
	}
	
	return nil, fmt.Errorf("all retries exhausted: %w", lastErr)
}
```

### 2.4 生产排障案例

**故障现象：** 支付服务偶尔返回 503，但数据库正常

**排查步骤：**

```bash
# 1. 查看熔断器状态指标
curl http://localhost:9090/metrics | grep circuit_breaker

# 输出：
# circuit_breaker_state{name="payment-service"} 1  # 1=OPEN
# circuit_breaker_total_calls{name="payment-service"} 1500
# circuit_breaker_failure_rate{name="payment-service"} 0.62

# 2. 分析原因：62% 失败率 > 50% 阈值，触发熔断

# 3. 查看下游日志
kubectl logs -l app=payment-service --tail=100 | grep ERROR

# 发现：数据库连接池耗尽
# pool_size=50, active=50, waiting=120

# 4. 根因：支付高峰期并发请求过多，连接池不够
```

**修复方案：**

```go
// 调整连接池大小
poolSize := 200  // 从 50 提升到 200

// 同时优化熔断器参数
breaker := NewCircuitBreaker("payment-service")
breaker.SetConfig(Config{
	FailureThreshold: 0.6,    // 提高阈值到 60%
	MinimumCalls:     50,     // 增加最小调用数
	SleepWindow:      60 * time.Second,  // 延长熔断时间
	SuccessThreshold: 10,     // 需要更多成功才关闭
})
```

**Trade-off 分析：**

| 方案 | 优点 | 缺点 |
|------|------|------|
| 增大连接池 | 提高吞吐量 | 占用更多内存，可能触发 GC |
| 提高熔断阈值 | 减少误熔断 | 可能让更多失败请求通过 |
| 添加超时控制 | 快速失败 | 可能误杀慢查询 |

---

## 三、Bulkhead（舱壁隔离）

### 3.1 原理

```
传统架构（共享资源）：
┌─────────────────────────────────────┐
│          线程池 (50 线程)            │
│                                     │
│  订单服务 ████████████████ (40)      │
│  支付服务 ██████ (10)                │
│                                     │
│  订单服务卡住 → 支付服务也没线程可用  │
└─────────────────────────────────────┘

Bulkhead 隔离：
┌──────────┐  ┌──────────┐  ┌──────────┐
│ 订单服务  │  │ 支付服务  │  │ 用户服务  │
│ 线程池    │  │ 线程池    │  │ 线程池    │
│ (40 线程) │  │ (10 线程) │  │ (5 线程)  │
└──────────┘  └──────────┘  └──────────┘
```

### 3.2 Go 实现

```go
package bulkhead

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
)

var ErrBulkheadFull = errors.New("bulkhead full, no available resources")

// ResourcePool manages a fixed-size pool of resources
type ResourcePool struct {
	semaphore chan struct{}
	mu        sync.Mutex
	available int
	total     int
}

// NewResourcePool creates a new resource pool
func NewResourcePool(size int) *ResourcePool {
	return &ResourcePool{
		semaphore: make(chan struct{}, size),
		available: size,
		total:     size,
	}
}

// Acquire tries to acquire a resource
func (p *ResourcePool) Acquire(ctx context.Context) error {
	select {
	case p.semaphore <- struct{}{}:
		p.mu.Lock()
		p.available--
		p.mu.Unlock()
		return nil
	case <-ctx.Done():
		return ctx.Err()
	default:
		return ErrBulkheadFull
	}
}

// Release releases a resource back to the pool
func (p *ResourcePool) Release() {
	p.mu.Lock()
	p.available++
	p.mu.Unlock()
	<-p.semaphore
}

// Bulkhead isolates different services with separate resource pools
type Bulkhead struct {
	pools map[string]*ResourcePool
	mu    sync.RWMutex
}

// NewBulkhead creates a new bulkhead
func NewBulkhead() *Bulkhead {
	return &Bulkhead{
		pools: make(map[string]*ResourcePool),
	}
}

// RegisterPool registers a resource pool for a service
func (b *Bulkhead) RegisterPool(service string, size int) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.pools[service] = NewResourcePool(size)
}

// Execute executes a function with bulkhead isolation
func (b *Bulkhead) Execute(ctx context.Context, service string, fn func(context.Context) error) error {
	b.mu.RLock()
	pool, exists := b.pools[service]
	b.mu.RUnlock()
	
	if !exists {
		// 默认使用共享池
		pool = b.getDefaultPool()
	}
	
	if err := pool.Acquire(ctx); err != nil {
		return err
	}
	defer pool.Release()
	
	return fn(ctx)
}

// getDefaultPool returns or creates a default shared pool
func (b *Bulkhead) getDefaultPool() *ResourcePool {
	b.mu.Lock()
	defer b.mu.Unlock()
	
	pool, exists := b.pools["default"]
	if !exists {
		pool = NewResourcePool(50)
		b.pools["default"] = pool
	}
	return pool
}

// Metrics tracks bulkhead usage
type Metrics struct {
	activeRequests atomic.Int64
	rejectedCount  atomic.Int64
	totalRequests  atomic.Int64
}

func (m *Metrics) RecordRequest() {
	m.totalRequests.Add(1)
	m.activeRequests.Add(1)
}

func (m *Metrics) RecordCompletion() {
	m.activeRequests.Add(-1)
}

func (m *Metrics) RecordRejection() {
	m.rejectedCount.Add(1)
}
```

### 3.3 实际应用场景

```go
// 广告竞价服务中的 Bulkhead 配置
func setupBulkheads() *Bulkhead {
	bh := NewBulkhead()
	
	// 核心竞价路径 - 大池子
	bh.RegisterPool("bid-auction", 200)
	
	// 用户画像查询 - 中等池子
	bh.RegisterPool("user-profile", 50)
	
	// 创意素材加载 - 小池子
	bh.RegisterPool("creative-load", 30)
	
	// 日志写入 - 最小池子
	bh.RegisterPool("log-write", 10)
	
	return bh
}

// 竞价请求处理
func (h *Handler) HandleBidRequest(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	var result *BidResponse
	var err error
	
	err = h.bulkhead.Execute(ctx, "bid-auction", func(ctx context.Context) error {
		// 1. 用户画像（独立 Bulkhead）
		userProfile, err := h.bulkhead.Execute(ctx, "user-profile", func(ctx context.Context) error {
			userProfile, err = h.profileService.Get(ctx, req.UserID)
			return err
		})
		if err != nil {
			return err
		}
		
		// 2. 创意加载（独立 Bulkhead）
		creatives, err := h.bulkhead.Execute(ctx, "creative-load", func(ctx context.Context) error {
			creatives, err = h.creativeService.Match(ctx, userProfile)
			return err
		})
		if err != nil {
			return err
		}
		
		// 3. 核心竞价逻辑
		result = h.auctionEngine.Run(ctx, req, userProfile, creatives)
		
		// 4. 日志（独立 Bulkhead，不影响核心流程）
		h.bulkhead.Execute(context.Background(), "log-write", func(ctx context.Context) error {
			h.logger.Info("bid processed", "request_id", req.ID)
			return nil
		})
		
		return nil
	})
	
	return result, err
}
```

---

## 四、Rate Limiter（限流器）

### 4.1 三种算法对比

| 算法 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **固定窗口** | 按时间窗口计数 | 实现简单 | 边界突刺问题 | 简单 API 限流 |
| **滑动窗口** | 多个固定窗口加权 | 平滑限流 | 内存占用多 | 高精度场景 |
| **令牌桶** | 匀速产生令牌 | 允许突发流量 | 需要维护桶 | CDN/消息队列 |
| **漏桶** | 匀速处理请求 | 平滑输出 | 不允许突发 | 防刷/防攻击 |

### 4.2 令牌桶算法实现（Go）

```go
package ratelimiter

import (
	"sync"
	"sync/atomic"
	"time"
)

// TokenBucket implements the token bucket rate limiting algorithm
type TokenBucket struct {
	mu         sync.Mutex
	tokens     float64
	maxTokens  float64
	refillRate float64 // tokens per second
	lastRefill time.Time
}

// NewTokenBucket creates a new token bucket
func NewTokenBucket(maxTokens float64, refillRate float64) *TokenBucket {
	return &TokenBucket{
		tokens:     maxTokens,
		maxTokens:  maxTokens,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

// Allow checks if a request is allowed and consumes a token
func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()
	
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	
	// 补充令牌
	tb.tokens += elapsed * tb.refillRate
	if tb.tokens > tb.maxTokens {
		tb.tokens = tb.maxTokens
	}
	tb.lastRefill = now
	
	// 消耗令牌
	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	
	return false
}

// AllowN checks if N tokens are available
func (tb *TokenBucket) AllowN(n int) bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()
	
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens += elapsed * tb.refillRate
	if tb.tokens > tb.maxTokens {
		tb.tokens = tb.maxTokens
	}
	tb.lastRefill = now
	
	if tb.tokens >= float64(n) {
		tb.tokens -= float64(n)
		return true
	}
	return false
}

// Wait blocks until a token is available
func (tb *TokenBucket) Wait(ctx context.Context) error {
	for {
		if tb.Allow() {
			return nil
		}
		
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(10 * time.Millisecond):
			// 短暂等待后重试
		}
	}
}

// Remaining returns the current number of tokens
func (tb *TokenBucket) Remaining() float64 {
	tb.mu.Lock()
	defer tb.mu.Unlock()
	return tb.tokens
}
```

### 4.3 分布式限流（Redis + Lua）

```go
package ratelimiter

import (
	"context"
	"fmt"
	"time"
	
	"github.com/redis/go-redis/v9"
)

// DistributedRateLimiter uses Redis for distributed rate limiting
type DistributedRateLimiter struct {
	rdb *redis.Client
}

// NewDistributedRateLimiter creates a new distributed rate limiter
func NewDistributedRateLimiter(rdb *redis.Client) *DistributedRateLimiter {
	return &DistributedRateLimiter{rdb: rdb}
}

// LimitByUser limits requests per user with sliding window
func (rl *DistributedRateLimiter) LimitByUser(ctx context.Context, userID string, maxRequests int, window time.Duration) error {
	key := fmt.Sprintf("rate_limit:user:%s", userID)
	now := time.Now().UnixMilli()
	windowStart := now - window.Milliseconds()
	
	// Lua script for atomic operations
	luaScript := `
		local key = KEYS[1]
		local window_start = tonumber(ARGV[1])
		local max_requests = tonumber(ARGV[2])
		local now = tonumber(ARGV[3])
		
		-- 移除过期记录
		redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
		
		-- 当前窗口内的请求数
		local count = redis.call('ZCARD', key)
		
		if count < max_requests then
			-- 添加新请求
			redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
			redis.call('EXPIRE', key, math.ceil(window.Seconds()))
			return 1
		else
			return 0
		end
	`
	
	result, err := rl.rdb.Eval(ctx, luaScript, []string{key}, windowStart, maxRequests, now).Int()
	if err != nil {
		return fmt.Errorf("rate limit check failed: %w", err)
	}
	
	if result == 0 {
		return fmt.Errorf("rate limit exceeded for user %s", userID)
	}
	
	return nil
}
```

### 4.4 广告场景限流策略

```go
// 广告竞价系统的多级限流
func setupAdRateLimiting() {
	// L1: 全局限流 - 保护整个竞价引擎
	globalLimiter := NewTokenBucket(10000, 10000) // 10k RPS
	
	// L2: 广告主限流 - 防止单个广告主占满资源
	advertiserLimiters := make(map[string]*TokenBucket)
	
	// L3: IP 限流 - 防止恶意请求
	ipLimiters := make(map[string]*TokenBucket)
	
	// L4: 用户限流 - 个性化配额
	userLimiters := make(map[string]*TokenBucket)
}

func (h *Handler) RateLimitCheck(ctx context.Context, req *BidRequest) error {
	// L1: 全局限流
	if !h.globalLimiter.Allow() {
		return h.Error(429, "global rate limit exceeded")
	}
	
	// L2: 广告主限流
	limiter := h.getAdvertiserLimiter(req.AdvertiserID)
	if !limiter.Allow() {
		return h.Error(429, "advertiser rate limit exceeded")
	}
	
	// L3: IP 限流
	ipLimiter := h.getIPLimiter(req.Device.IP)
	if !ipLimiter.Allow() {
		return h.Error(429, "IP rate limit exceeded")
	}
	
	return nil
}
```

---

## 五、Retry with Exponential Backoff（指数退避重试）

### 5.1 重试策略矩阵

| 场景 | 重试策略 | 最大重试 | 初始延迟 | 最大延迟 |
|------|---------|---------|---------|---------|
| 网络超时 | 指数退避 | 5 | 100ms | 30s |
| 503 Service Unavailable | 指数退避 | 3 | 50ms | 10s |
| 429 Too Many Requests | 读取 Retry-After | 1 | Retry-After | - |
| 数据库死锁 | 固定延迟 | 3 | 50ms | 150ms |
| 幂等写操作 | 指数退避+Jitter | 5 | 100ms | 30s |

### 5.2 Go 实现

```go
package retry

import (
	"context"
	"math"
	"math/rand"
	"time"
)

// Config holds retry strategy configuration
type Config struct {
	MaxRetries    int           // 最大重试次数
	InitialDelay  time.Duration // 初始延迟
	MaxDelay      time.Duration // 最大延迟
	Multiplier    float64       // 退避倍数
	Jitter        bool          // 是否启用随机抖动
}

// DefaultConfig returns default retry configuration
func DefaultConfig() Config {
	return Config{
		MaxRetries:   3,
		InitialDelay: 100 * time.Millisecond,
		MaxDelay:     10 * time.Second,
		Multiplier:   2.0,
		Jitter:       true,
	}
}

// Executor executes a function with retry logic
type Executor struct {
	config Config
}

// NewExecutor creates a new retry executor
func NewExecutor(config Config) *Executor {
	return &Executor{config: config}
}

// Execute runs fn with retry on transient errors
func (e *Executor) Execute(ctx context.Context, fn func(ctx context.Context) error) error {
	var lastErr error
	delay := e.config.InitialDelay
	
	for attempt := 0; attempt <= e.config.MaxRetries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(e.calculateDelay(delay)):
			}
			delay = e.nextDelay(delay)
		}
		
		lastErr = fn(ctx)
		if lastErr == nil {
			return nil
		}
		
		// 检查是否应该重试（非瞬态错误不重试）
		if !e.isTransientError(lastErr) {
			return lastErr
		}
	}
	
	return lastErr
}

// calculateDelay applies jitter if enabled
func (e *Executor) calculateDelay(baseDelay time.Duration) time.Duration {
	if !e.config.Jitter {
		return baseDelay
	}
	
	// Full jitter: random(0, baseDelay)
	maxDelay := math.Min(float64(baseDelay), float64(e.config.MaxDelay))
	jittered := time.Duration(rand.Float64() * maxDelay)
	return jittered
}

// nextDelay calculates the next delay with exponential backoff
func (e *Executor) nextDelay(current time.Duration) time.Duration {
	next := time.Duration(float64(current) * e.config.Multiplier)
	if next > e.config.MaxDelay {
		next = e.config.MaxDelay
	}
	return next
}

// isTransientError checks if error is retryable
func (e *Executor) isTransientError(err error) bool {
	// 网络相关错误可重试
	if netErr, ok := err.(interface{ Temporary() bool }); ok {
		return netErr.Temporary()
	}
	
	// 超时错误可重试
	if timeoutErr, ok := err.(interface{ Timeout() bool }); ok {
		return timeoutErr.Timeout()
	}
	
	return false
}
```

### 5.3 广告场景重试

```go
// 广告出价接口重试配置
func adBidRetryConfig() retry.Config {
	return retry.Config{
		MaxRetries:   3,
		InitialDelay: 50 * time.Millisecond,
		MaxDelay:     5 * time.Second,
		Multiplier:   2.0,
		Jitter:       true,
	}
}

// 调用外部 DSP 时带重试
func (h *Handler) CallExternalDSP(ctx context.Context, dspID string, bid *BidRequest) (*BidResponse, error) {
	executor := retry.NewExecutor(adBidRetryConfig())
	
	var response *BidResponse
	err := executor.Execute(ctx, func(ctx context.Context) error {
		resp, err := h.dspClient.Bid(ctx, dspID, bid)
		if err != nil {
			return err
		}
		response = resp
		return nil
	})
	
	if err != nil {
		// 所有重试失败，使用降级策略
		return h.fallbackBid(bid), nil
	}
	
	return response, nil
}
```

---

## 六、组合使用：完整的弹性链路

```go
package resilient

import (
	"context"
	"net/http"
	"time"

	"yourproject/bulkhead"
	"yourproject/ratelimiter"
	"yourproject/retry"
)

// ResilienceChain chains multiple resilience patterns
type ResilienceChain struct {
	rateLimiter *ratelimiter.TokenBucket
	bulkhead    *bulkhead.Bulkhead
	retry       *retry.Executor
	breaker     *resilience.CircuitBreaker
}

// NewResilienceChain creates a complete resilience chain
func NewResilienceChain() *ResilienceChain {
	return &ResilienceChain{
		rateLimiter: ratelimiter.NewTokenBucket(1000, 100), // 100 RPS
		bulkhead:    bulkhead.NewBulkhead(),
		retry:       retry.NewExecutor(retry.DefaultConfig()),
		breaker:     resilience.NewCircuitBreaker("default"),
	}
}

// Execute runs a function through the entire resilience chain
func (rc *ResilienceChain) Execute(ctx context.Context, service string, fn func(context.Context) error) error {
	// 1. 限流
	if !rc.rateLimiter.Allow() {
		return fmt.Errorf("rate limited")
	}
	
	// 2. 熔断
	if err := rc.breaker.AllowRequest(ctx); err != nil {
		return err
	}
	
	// 3. 舱壁隔离
	var result error
	err := rc.bulkhead.Execute(ctx, service, func(ctx context.Context) error {
		// 4. 重试
		result = rc.retry.Execute(ctx, fn)
		return result
	})
	
	if err != nil {
		rc.breaker.RecordFailure()
		return err
	}
	
	rc.breaker.RecordSuccess()
	return nil
}
```

---

## 七、自测题

### Q1: 熔断器的 HALF-OPEN 状态为什么需要 SuccessThreshold 而不是立即关闭？

**答案：**

HALF-OPEN 是熔断恢复的试探阶段。如果只允许一个成功请求就关闭熔断器，可能出现：

1. **假恢复**：下游服务只是短暂可用，马上又故障
2. **雪崩风险**：一旦关闭，大量请求瞬间涌入，可能再次打垮下游

SuccessThreshold（如连续 5 次成功）确保下游确实恢复了稳定，而不是偶发成功。

### Q2: Bulkhead 和 Circuit Breaker 有什么区别？什么时候用哪个？

**答案：**

| 维度 | Bulkhead | Circuit Breaker |
|------|----------|-----------------|
| 防护目标 | 资源耗尽 | 故障传播 |
| 机制 | 隔离资源池 | 快速失败 |
| 何时触发 | 资源用尽时拒绝 | 失败率达到阈值时熔断 |
| 适用场景 | 多服务共享资源 | 调用不稳定下游 |

**最佳实践：两者配合使用**
- Bulkhead 防止资源争抢
- Circuit Breaker 防止对故障服务的无效调用

### Q3: 令牌桶和漏桶的区别是什么？广告系统应该用哪个？

**答案：**

| 特性 | 令牌桶 | 漏桶 |
|------|--------|------|
| 流量特征 | 允许突发 | 匀速输出 |
| 实现复杂度 | 简单 | 简单 |
| 适用场景 | API 限流、CDN | 消息队列、防刷 |

**广告系统选择令牌桶的原因：**
1. 竞价请求有天然突发特性（广告主预算耗尽时请求骤减）
2. 令牌桶允许短期突发，提高资源利用率
3. 可以设置不同的桶大小适配不同业务

---

## 八、动手验证

### 8.1 单元测试

```go
func TestCircuitBreaker(t *testing.T) {
	cb := NewCircuitBreaker("test")
	
	// 模拟失败
	for i := 0; i < 20; i++ {
		cb.RecordFailure()
	}
	
	assert.Equal(t, StateOpen, cb.getState())
	
	// 熔断期间请求被拒绝
	err := cb.AllowRequest(context.Background())
	assert.Error(t, err)
	
	// 等待睡眠窗口
	time.Sleep(35 * time.Second)
	
	// 进入半开状态
	assert.Equal(t, StateHalfOpen, cb.getState())
	
	// 连续成功恢复
	for i := 0; i < 5; i++ {
		cb.RecordSuccess()
	}
	
	assert.Equal(t, StateClosed, cb.getState())
}
```

### 8.2 压测脚本

```bash
# 测试限流效果
wrk -t4 -c100 -d30s http://localhost:8080/api/bid \
    --script=test.lua

# test.lua
request = function()
    return wrk.format("POST", "/api/bid", nil, nil)
end

# 观察限流指标
watch 'curl -s localhost:9090/metrics | grep rate_limiter'
```

---

## 九、与知识库的对照

### 已有内容
- `advertising/ad-architecture-high-concurrency.md` — 高并发架构，包含部分限流内容
- `architecture/high-availability-design.md` — 容灾/熔断/限流/降级概述
- `microservice/distributed-transactions-deep.md` — 分布式事务模式

### 本文件补充
- ✅ Circuit Breaker 完整状态机实现（含代码）
- ✅ Bulkhead 资源池隔离模式（含代码）
- ✅ Rate Limiter 令牌桶算法（含 Redis 分布式实现）
- ✅ Retry 指数退避 + Jitter（含广告场景配置）
- ✅ 四级限流策略（全局→广告主→IP→用户）

### 缺失内容（待补充）
- ❌ 自适应限流（基于 P99 延迟动态调整阈值）
- ❌ 弹性伸缩与限流的联动策略