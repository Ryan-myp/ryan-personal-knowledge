# 前端性能优化深度实战

## 一、性能优化全景

### 1.1 核心指标

| 指标 | 说明 | 优秀标准 |
|------|------|----------|
| LCP | 最大内容绘制 | <2.5s |
| FID | 首次输入延迟 | <100ms |
| CLS | 累积布局偏移 | <0.1 |
| TTFB | 首字节时间 | <800ms |
| FCP | 首次内容绘制 | <1.8s |

### 1.2 优化策略分层

```
资源层:
├── 代码分割 (Code Splitting)
├── Tree Shaking
├── 压缩 (Gzip/Brotli)
└── CDN 加速

渲染层:
├── SSR/SSG/ISR
├── 虚拟列表
├── 懒加载
└── 防抖节流

缓存层:
├── Service Worker
├── HTTP Cache
├── LocalStorage
└── IndexedDB
```

## 二、代码分割实战

### 2.1 Webpack 配置

```javascript
module.exports = {
  optimization: {
    splitChunks: {
      chunks: 'all',
      cacheGroups: {
        vendors: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          priority: 10,
        },
        common: {
          minChunks: 2,
          name: 'common',
          priority: 5,
          reuseExistingChunk: true,
        },
      },
    },
  },
};
```

### 2.2 React 懒加载

```jsx
import { lazy, Suspense } from 'react';

const Dashboard = lazy(() => import('./Dashboard'));
const Settings = lazy(() => import('./Settings'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Suspense>
  );
}
```

## 三、自测题

1. Web Vitals 包含哪些指标？
2. 代码分割有什么好处？

## 四、动手验证

```bash
# 1. 配置代码分割
# 2. 实现懒加载
# 3. 添加 Service Worker
# 4. 使用 Lighthouse 测试
```

---

## Go 代码实战：性能优化核心模块

### 1. 多级缓存架构（L1/L2/L3）

```go
package cache

import (
	"context"
	"sync"
	"time"
)

// CacheLevel 缓存层级
type CacheLevel int

const (
	L1 In-Memory Cache Level CacheLevel = iota
	L2 Redis Cache
	L3 Database
)

// MultiLevelCache 多级缓存
type MultiLevelCache struct {
	l1  *InMemoryCache  // LRU, <1ms
	l2  *RedisCache     // Redis, <5ms
	l3  *DBCache        // MySQL, <50ms
	mu  sync.RWMutex
}

func (c *MultiLevelCache) Get(ctx context.Context, key string) ([]byte, error) {
	// L1: 内存缓存
	if data, ok := c.l1.Get(key); ok {
		return data, nil
	}
	
	// L2: Redis
	if data, err := c.l2.Get(ctx, key); err == nil {
		c.l1.Set(key, data) // 回写 L1
		return data, nil
	}
	
	// L3: 数据库
	data, err := c.l3.Query(ctx, key)
	if err != nil {
		return nil, err
	}
	
	c.l1.Set(key, data)
	c.l2.Set(ctx, key, data) // 回写 L2
	
	return data, nil
}

func (c *MultiLevelCache) Set(ctx context.Context, key string, data []byte, ttl time.Duration) {
	c.l1.Set(key, data)
	c.l2.Set(ctx, key, data)
	c.l3.Update(ctx, key, data)
}

// InMemoryCache 内存缓存（带过期）
type InMemoryCache struct {
	items map[string]*cacheEntry
	mu    sync.RWMutex
	ticker *time.Ticker
}

type cacheEntry struct {
	data      []byte
	expiresAt time.Time
}

func NewInMemoryCache() *InMemoryCache {
	c := &InMemoryCache{
		items: make(map[string]*cacheEntry),
		ticker: time.NewTicker(1 * time.Second),
	}
	go c.cleanupLoop()
	return c
}

func (c *InMemoryCache) cleanupLoop() {
	for range c.ticker.C {
		c.mu.Lock()
		now := time.Now()
		for key, entry := range c.items {
			if now.After(entry.expiresAt) {
				delete(c.items, key)
			}
		}
		c.mu.Unlock()
	}
}

func (c *InMemoryCache) Get(key string) ([]byte, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	entry, ok := c.items[key]
	if !ok || time.Now().After(entry.expiresAt) {
		return nil, false
	}
	return entry.data, true
}

func (c *InMemoryCache) Set(key string, data []byte) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items[key] = &cacheEntry{
		data:      data,
		expiresAt: time.Now().Add(5 * time.Minute), // 默认5分钟TTL
	}
}

// CircuitBreaker 熔断器（Hystrix模式）
type CircuitBreaker struct {
	mu           sync.Mutex
	state        CircuitState // closed, open, half-open
	failureCount int
	successCount int
	lastFailTime time.Time
	timeout      time.Duration
}

type CircuitState int

const (
	StateClosed CircuitState = iota
	StateOpen
	StateHalfOpen
)

func (cb *CircuitBreaker) AllowRequest() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	switch cb.state {
	case StateClosed:
		return true
	case StateOpen:
		// 超时后进入 half-open
		if time.Since(cb.lastFailTime) > cb.timeout {
			cb.state = StateHalfOpen
			cb.successCount = 0
			return true
		}
		return false
	case StateHalfOpen:
		return true
	}
	return false
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	if cb.state == StateHalfOpen {
		cb.successCount++
		if cb.successCount >= 3 {
			cb.state = StateClosed
			cb.failureCount = 0
		}
	} else {
		cb.failureCount = 0
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	
	cb.failureCount++
	cb.lastFailTime = time.Now()
	
	if cb.state == StateHalfOpen || cb.failureCount >= 5 {
		cb.state = StateOpen
	}
}
```

### 2. 限流器（滑动窗口）

```go
package rate

import (
	"sync"
	"time"
)

// SlidingWindowLimiter 滑动窗口限流器
type SlidingWindowLimiter struct {
	mu         sync.Mutex
	windowSize time.Duration
	maxOps     int64
	operations []int64 // 操作时间戳列表
}

func NewSlidingWindowLimiter(window time.Duration, maxOps int64) *SlidingWindowLimiter {
	return &SlidingWindowLimiter{
		windowSize: window,
		maxOps:     maxOps,
	}
}

func (l *SlidingWindowLimiter) Allow() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	
	now := time.Now().UnixNano()
	windowStart := now - int64(l.windowSize)
	
	// 清理过期操作
	idx := 0
	for idx < len(l.operations) && l.operations[idx] < windowStart {
		idx++
	}
	if idx > 0 {
		l.operations = l.operations[idx:]
	}
	
	// 检查是否超限
	if int64(len(l.operations)) >= l.maxOps {
		return false
	}
	
	l.operations = append(l.operations, now)
	return true
}

// TokenBucket 令牌桶（另一种常见限流方案）
type TokenBucket struct {
	mu         sync.Mutex
	tokens     float64
	maxTokens  float64
	refillRate float64
	lastRefill time.Time
}

func NewTokenBucket(maxTokens, refillRate float64) *TokenBucket {
	return &TokenBucket{
		tokens:     maxTokens,
		maxTokens:  maxTokens,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()
	
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens = math.Min(tb.maxTokens, tb.tokens+elapsed*tb.refillRate)
	tb.lastRefill = now
	
	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}
```

### 自测题

<details>
<summary>Q1: 多级缓存的回写策略（Write-Through vs Write-Behind）各有什么优劣？</summary>

**答案**：

| 策略 | 写入延迟 | 一致性 | 适用场景 |
|------|---------|--------|---------|
| Write-Through | 高（等L2/L3写完） | 强一致 | 计费/预算等关键数据 |
| Write-Behind | 低（只写L1） | 最终一致 | 用户画像/推荐特征 |

广告竞价场景：**读多写少**，用 Write-Through 保证一致性；**用户画像更新**用 Write-Behind 批量异步落盘。

</details>

<details>
<summary>Q2: CircuitBreaker 的 half-open 状态为什么需要 successCount >= 3 才恢复 closed？</summary>

**答案**：

**单次成功不够可靠**——网络抖动可能只是瞬间恢复。连续3次成功才能确认服务真正恢复。

**Trade-off**：
- 3次太保守 → 恢复慢，用户体验差
- 1次太激进 → 服务未完全恢复就恢复流量，导致雪崩
- **生产推荐**：3-5次，配合监控告警人工介入

</details>

<details>
<summary>Q3: 滑动窗口 vs 令牌桶限流器，各适用于什么场景？</summary>

**答案**：

| 特性 | 滑动窗口 | 令牌桶 |
|------|---------|--------|
| 突发处理 | ❌ 不允许 | ✅ 允许（桶中有剩余token） |
| 精度 | 高（精确窗口计数） | 中（依赖 refill 频率） |
| 实现复杂度 | 中 | 低 |
| 适用场景 | API调用限制、防刷 | CDN带宽控制、消息队列 |

广告平台：API限流用滑动窗口（精确控制），CDN回源用令牌桶（允许突发）。

</details>
