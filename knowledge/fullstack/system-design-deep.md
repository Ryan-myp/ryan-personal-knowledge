# 系统设计面试深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、系统设计方法论

```
┌─────────────────────────────────────────────────────────────────────┐
│                    系统设计六步法                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1️⃣  澄清需求 (Clarify)     2️⃣  容量估算 (Estimate)              │
│     ├─ 功能范围              ├─ QPS/吞吐                            │
│     ├─ 约束条件              ├─ 存储规模                            │
│     └─ 成功标准              └─ 带宽需求                            │
│                                                                     │
│  3️⃣  高层设计 (High-Level)  4️⃣  详细设计 (Deep Dive)              │
│     ├─ 核心组件              ├─ API 设计                            │
│     ├─ 数据流                ├─ 数据模型                            │
│     └─ 关键决策              └─ 一致性策略                          │
│                                                                     │
│  5️⃣  瓶颈分析 (Bottleneck)  6️⃣  扩展优化 (Scale)                  │
│     ├─ 性能热点              ├─ 水平扩展                            │
│     ├─ 单点故障              ├─ 缓存策略                            │
│     └─ 容量限制              └─ 灾备方案                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心组件设计

### 2.1 API Gateway 设计

```go
// 文件: design/gateway/gateway.go
package gateway

import (
    "context"
    "net/http"
    "sync"
)

// ─── 网关核心结构 ───
type Gateway struct {
    routes      map[string]*Route
    middlewares []Middleware
    rateLimiter RateLimiter
    circuit     CircuitBreaker
    
    // 路由表 (支持热更新)
    mu          sync.RWMutex
}

type Route struct {
    Path       string
    Methods    []string
    Handler    http.HandlerFunc
    RateLimit  int  // QPS 限制
    Timeout    int  // 超时毫秒
    Upstream   string
}

// ─── 中间件链 ───
type Middleware func(http.Handler) http.Handler

func (g *Gateway) Use(mw Middleware) {
    g.middlewares = append(g.middlewares, mw)
}

// ─── 请求处理 ───
func (g *Gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    route := g.lookupRoute(r.Method, r.URL.Path)
    if route == nil {
        http.Error(w, "404 Not Found", http.StatusNotFound)
        return
    }
    
    ctx, cancel := context.WithTimeout(r.Context(), time.Duration(route.Timeout)*time.Millisecond)
    defer cancel()
    
    // 限流检查
    if !g.rateLimiter.Allow(route.Path) {
        http.Error(w, "429 Too Many Requests", http.StatusTooManyRequests)
        return
    }
    
    // 熔断器检查
    if g.circuit.IsOpen(route.Upstream) {
        http.Error(w, "503 Service Unavailable", http.StatusServiceUnavailable)
        return
    }
    
    // 执行中间件链
    handler := g.buildHandlerChain(route.Handler)
    handler.ServeHTTP(w, r.WithContext(ctx))
}

// ─── 路由查找 ───
func (g *Gateway) lookupRoute(method, path string) *Route {
    g.mu.RLock()
    defer g.mu.RUnlock()
    
    for _, route := range g.routes {
        if route.Path == path && contains(route.Methods, method) {
            return route
        }
    }
    return nil
}
```

### 2.2 分布式缓存设计

```go
// 文件: design/cache/distributed_cache.go
package cache

import (
    "context"
    "sync"
    "time"
)

// ─── 缓存层级 ───
type CacheLayer int

const (
    L1_Local CacheLayer = iota
    L2_Reddis
    L3_Database
)

// ─── 多级缓存 ───
type MultiLevelCache struct {
    local  *LocalCache
    redis  *RedisClient
    db     Database
    config CacheConfig
}

type CacheConfig struct {
    LocalSize   int           // L1 容量
    TTL         time.Duration // 全局 TTL
    Eviction    string        // 淘汰策略
}

// ─── 三级缓存查询 ───
func (c *MultiLevelCache) Get(ctx context.Context, key string) (*Item, error) {
    // L1: 本地缓存
    if item, ok := c.local.Get(key); ok {
        return item, nil
    }
    
    // L2: Redis
    if item, err := c.redis.Get(ctx, key); err == nil && item != nil {
        c.local.Set(key, item) // 回源 L1
        return item, nil
    }
    
    // L3: 数据库
    item, err := c.db.Query(ctx, key)
    if err != nil {
        return nil, err
    }
    
    c.redis.Set(ctx, key, item, c.config.TTL)
    c.local.Set(key, item)
    
    return item, nil
}

// ─── 缓存预热 ───
func (c *MultiLevelCache) WarmUp(ctx context.Context, keys []string) error {
    // 批量从 DB 加载
    items, err := c.db.BatchQuery(ctx, keys)
    if err != nil {
        return err
    }
    
    // 并行写入缓存
    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        go func(i *Item) {
            defer wg.Done()
            c.redis.Set(ctx, i.Key, i, c.config.TTL)
            c.local.Set(i.Key, i)
        }(item)
    }
    wg.Wait()
    
    return nil
}
```

---

## 三、经典系统设计题

### 3.1 短链接系统

```
设计要素:
├─ 唯一 ID 生成 (Snowflake/Bitly)
├─ 存储设计 (MySQL + Redis)
├─ 重定向策略 (301 vs 302)
└─ 访问统计 (流式处理)

架构:
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Client  │───▶│  Gateway │───▶│ Redirect │
└──────────┘    └──────────┘    └────┬─────┘
                                     │
                              ┌──────▼──────┐
                              │  Redis Cache │
                              │  (短链接->长)│
                              └──────┬──────┘
                                     │
                              ┌──────▼──────┐
                              │  MySQL      │
                              │  (持久化)    │
                              └─────────────┘
```

### 3.2 实时竞价系统 (RTB)

```
延迟要求: < 100ms (P99)

架构:
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│  AdReq  │──▶│ Filter  │──▶│ Bidding │──▶│  Response│
│  (<1ms) │   │ (<5ms)  │   │ (<50ms) │   │  (<20ms) │
└─────────┘   └─────────┘   └─────────┘   └─────────┘
                                      │
                              ┌───────▼───────┐
                              │  Redis ZSet   │
                              │  (频率控制)    │
                              └───────────────┘
```

---

## 四、可扩展性策略

```
┌─────────────────────────────────────────────────────────────────┐
│                    扩展策略矩阵                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  瓶颈类型         解决方案                    复杂度            │
│  ───────────────────────────────────────────────────────────  │
│  CPU 密集型       水平扩展 + 负载均衡         低                │
│  IO 密集型        异步化 + 连接池             中                │
│  数据库瓶颈       读写分离 + 分库分表         高                │
│  缓存瓶颈         多级缓存 + 热点Key          中                │
│  网络瓶颈         CDN + 边缘计算              中                │
│  一致性瓶颈       最终一致 + 补偿机制         高                │
│                                                                 │
│  扩展原则:                                                     │
│  ├─ 优先水平扩展，避免垂直扩展                                  │
│  ├─ 无状态设计便于扩展                                          │
│  ├─ 异步解耦提升吞吐                                            │
│  └─ 容量规划预留 3x 余量                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、参考资料

```
核心书籍:
├── "Designing Data-Intensive Applications" (Martin Kleppmann)
├── "System Design Interview" (Alex Xu)
└── "The Art of Scalability"

在线资源:
├── HighScalability.com
├── LinkedIn Engineering Blog
└── Netflix Tech Blog
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
