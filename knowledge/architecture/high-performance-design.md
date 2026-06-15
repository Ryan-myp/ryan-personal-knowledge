# 高性能架构设计：缓存/异步/并行/连接池

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解高性能

```
餐厅的高效运营：
1. 缓存 → 常卖菜品提前备好（预制菜）
2. 异步 → 客人点餐后先上饮料，后厨慢慢做菜
3. 并行 → 多个厨师同时做菜
4. 连接池 → 服务员固定分配，不临时找
```

### 性能优化的核心指标

```
1. 延迟（Latency）：请求从发起到响应的时间
2. 吞吐（Throughput）：单位时间内处理的请求数
3. 资源利用率（Resource Utilization）：CPU/内存/网络
4. P99/P95/P50：不同百分位的延迟
```

---

## 第二部分：缓存架构

### 2.1 缓存层级

```
L1 Cache（本地缓存）：
  → 进程内，最快（~100ns）
  → 容量小，数据不一致

L2 Cache（分布式缓存）：
  → Redis/Memcached，较快（~1ms）
  → 容量大，数据一致性好

L3 Cache（CDN）：
  → 边缘节点，适合静态资源
  → 全球加速

L4 Cache（数据库缓存）：
  → Buffer Pool
  → 最后防线
```

### 2.2 Go 实现多级缓存

```go
package cache

import (
    "context"
    "sync"
    "time"
    
    "github.com/eko/gocache/lib/v4/cache"
    "github.com/eko/gocache/lib/v4/store"
    redisstore "github.com/eko/gocache/store/redis/v4"
)

// MultiLevelCache 多级缓存
type MultiLevelCache struct {
    localCache  *LocalCache
    redisCache  *cache.Cache[string]
    redisStore  *redisstore.RedisStore
    mu          sync.RWMutex
}

// LocalCache 本地缓存
type LocalCache struct {
    data   map[string]*cacheItem
    maxItems int
    ttl    time.Duration
    mu     sync.RWMutex
}

type cacheItem struct {
    value     interface{}
    expiresAt time.Time
}

// NewMultiLevelCache 创建多级缓存
func NewMultiLevelCache(maxLocalItems int, redisAddr string) *MultiLevelCache {
    // 创建 Redis store
    redisStore := redisstore.NewRedis(redis.NewClient(&redis.Options{
        Addr: redisAddr,
    }))
    
    // 创建缓存层
    redisCache := cache.New[string](redisStore)
    
    // 创建本地缓存
    localCache := &LocalCache{
        data:       make(map[string]*cacheItem),
        maxItems:   maxLocalItems,
        ttl:        5 * time.Minute,
    }
    
    return &MultiLevelCache{
        localCache: localCache,
        redisCache: redisCache,
        redisStore: redisStore,
    }
}

// Get 获取缓存（多级）
func (mlc *MultiLevelCache) Get(ctx context.Context, key string) (interface{}, error) {
    // 1. 检查本地缓存
    if value, ok := mlc.localCache.get(key); ok {
        return value, nil
    }
    
    // 2. 检查 Redis 缓存
    value, err := mlc.redisCache.Get(ctx, key)
    if err != nil {
        return nil, err
    }
    
    // 3. 回填本地缓存
    mlc.localCache.set(key, value)
    
    return value, nil
}

// Set 设置缓存（多级）
func (mlc *MultiLevelCache) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
    // 1. 设置本地缓存
    mlc.localCache.set(key, value)
    
    // 2. 设置 Redis 缓存
    return mlc.redisCache.Set(ctx, key, value, &store.SetOptions{
        TTL: ttl,
    })
}

// Invalidate 失效缓存
func (mlc *MultiLevelCache) Invalidate(ctx context.Context, key string) error {
    // 1. 失效本地缓存
    mlc.localCache.invalidate(key)
    
    // 2. 失效 Redis 缓存
    return mlc.redisStore.Delete(ctx, key)
}
```

### 2.3 缓存穿透/击穿/雪崩

```
缓存穿透：查询不存在的数据
  → 解决方案：布隆过滤器、缓存空值

缓存击穿：热点 key 过期，大量请求打到数据库
  → 解决方案：互斥锁、永不过期

缓存雪崩：大量 key 同时过期
  → 解决方案：随机 TTL、集群部署
```

```go
// 布隆过滤器防穿透
type BloomFilter struct {
    bits    []bool
    hashes  []func([]byte) uint
    size    int
    k       int // 哈希函数数量
}

func (bf *BloomFilter) Add(item []byte) {
    for _, hash := range bf.hashes {
        idx := hash(item) % uint(len(bf.bits))
        bf.bits[idx] = true
    }
}

func (bf *BloomFilter) MightContain(item []byte) bool {
    for _, hash := range bf.hashes {
        idx := hash(item) % uint(len(bf.bits))
        if !bf.bits[idx] {
            return false
        }
    }
    return true
}

// 缓存击穿保护
type HotKeyProtection struct {
    mu       sync.Mutex
    locking  map[string]bool
}

func (hk *HotKeyProtection) Lock(key string) bool {
    hk.mu.Lock()
    defer hk.mu.Unlock()
    
    if hk.locking[key] {
        return false // 已经被锁定
    }
    
    hk.locking[key] = true
    return true
}

func (hk *HotKeyProtection) Unlock(key string) {
    hk.mu.Lock()
    defer hk.mu.Unlock()
    
    delete(hk.locking, key)
}
```

---

## 第三部分：异步架构

### 3.1 异步处理模式

```
1. 消息队列
   → Kafka/RabbitMQ
   → 解耦、削峰、异步

2. 事件驱动
   → 事件总线
   → 实时响应

3. 工作队列
   → Worker 池
   → 批量处理
```

### 3.2 Go 实现异步处理

```go
package async

import (
    "context"
    "sync"
    "time"
)

// WorkerPool 工作池
type WorkerPool struct {
    jobs    chan func()
    wg      sync.WaitGroup
    running int64
    stopped int32
}

func NewWorkerPool(workerCount, queueSize int) *WorkerPool {
    wp := &WorkerPool{
        jobs: make(chan func(), queueSize),
    }
    
    // 启动 worker
    for i := 0; i < workerCount; i++ {
        wp.wg.Add(1)
        go wp.worker()
    }
    
    return wp
}

func (wp *WorkerPool) worker() {
    defer wp.wg.Done()
    
    for job := range wp.jobs {
        atomic.AddInt64(&wp.running, 1)
        
        func() {
            defer func() {
                atomic.AddInt64(&wp.running, -1)
                if r := recover(); r != nil {
                    fmt.Printf("worker panic: %v\n", r)
                }
            }()
            job()
        }()
    }
}

func (wp *WorkerPool) Submit(job func()) error {
    if atomic.LoadInt32(&wp.stopped) == 1 {
        return fmt.Errorf("pool is stopped")
    }
    
    select {
    case wp.jobs <- job:
        return nil
    default:
        return fmt.Errorf("queue is full")
    }
}

func (wp *WorkerPool) Stop() {
    atomic.StoreInt32(&wp.stopped, 1)
    close(wp.jobs)
    wp.wg.Wait()
}
```

---

## 第四部分：并行架构

### 4.1 并行处理模式

```
1. Fan-out/Fan-in
   → 分发任务到多个 worker
   → 收集结果

2. Pipeline
   → 多阶段处理
   → 每个阶段并行处理

3. MapReduce
   → Map：分散处理
   → Reduce：聚合结果
```

### 4.2 Go 实现并行处理

```go
package parallel

import (
    "context"
    "sync"
)

// FanOutFanIn Fan-out/Fan-in 模式
func FanOutFanIn(ctx context.Context, items []string, processor func(context.Context, string) (string, error)) ([]string, error) {
    var wg sync.WaitGroup
    results := make([]string, len(items))
    errs := make([]error, len(items))
    
    for i, item := range items {
        wg.Add(1)
        go func(idx int, item string) {
            defer wg.Done()
            
            result, err := processor(ctx, item)
            if err != nil {
                errs[idx] = err
                return
            }
            
            results[idx] = result
        }(i, item)
    }
    
    wg.Wait()
    
    // 检查错误
    for _, err := range errs {
        if err != nil {
            return nil, err
        }
    }
    
    return results, nil
}

// Pipeline 管道模式
type Stage struct {
    name     string
    process  func(interface{}) (interface{}, error)
}

type Pipeline struct {
    stages []Stage
}

func (p *Pipeline) AddStage(name string, process func(interface{}) (interface{}, error)) {
    p.stages = append(p.stages, Stage{
        name:    name,
        process: process,
    })
}

func (p *Pipeline) Run(ctx context.Context, input interface{}) (interface{}, error) {
    result := input
    
    for _, stage := range p.stages {
        var err error
        result, err = stage.process(result)
        if err != nil {
            return nil, err
        }
    }
    
    return result, nil
}

// MapReduce MapReduce 模式
func MapReduce(ctx context.Context, items []string, mapper func(context.Context, string) ([]interface{}, error), reducer func([]interface{}) interface{}) interface{} {
    // Map 阶段
    type result struct {
        values []interface{}
        err    error
    }
    
    ch := make(chan result, len(items))
    
    for _, item := range items {
        go func(i string) {
            values, err := mapper(ctx, i)
            ch <- result{values: values, err: err}
        }(item)
    }
    
    // 收集 Map 结果
    var allValues []interface{}
    for i := 0; i < len(items); i++ {
        r := <-ch
        if r.err != nil {
            return nil
        }
        allValues = append(allValues, r.values...)
    }
    
    // Reduce 阶段
    return reducer(allValues)
}
```

---

## 第五部分：连接池

### 5.1 连接池原理

```
连接池解决的问题：
1. 频繁创建/销毁连接的开销
2. 连接泄漏（未关闭连接）
3. 连接数失控

连接池的关键参数：
1. MaxOpen：最大打开连接数
2. MaxIdle：最大空闲连接数
3. IdleTimeout：空闲超时时间
4. MaxLifetime：最大生命周期
```

### 5.2 Go 实现连接池

```go
package pool

import (
    "context"
    "fmt"
    "sync"
    "time"
)

// Connection 连接接口
type Connection interface {
    Close() error
    IsValid() bool
}

// Pool 连接池
type Pool struct {
    conns        chan Connection
    factory      func() (Connection, error)
    maxOpen      int
    maxIdle      int
    idleTimeout  time.Duration
    maxLifetime  time.Duration
    mu           sync.Mutex
    openCount    int
    closed       bool
}

// NewPool 创建连接池
func NewPool(factory func() (Connection, error), maxOpen, maxIdle int, idleTimeout, maxLifetime time.Duration) *Pool {
    p := &Pool{
        conns:       make(chan Connection, maxOpen),
        factory:     factory,
        maxOpen:     maxOpen,
        maxIdle:     maxIdle,
        idleTimeout: idleTimeout,
        maxLifetime: maxLifetime,
    }
    
    // 启动空闲连接清理
    go p.cleanup()
    
    return p
}

// Get 获取连接
func (p *Pool) Get(ctx context.Context) (Connection, error) {
    select {
    case conn := <-p.conns:
        if conn.IsValid() {
            return conn, nil
        }
        // 连接无效，创建新连接
    case <-ctx.Done():
        return nil, ctx.Err()
    }
    
    // 创建新连接
    p.mu.Lock()
    if p.openCount < p.maxOpen {
        p.openCount++
        p.mu.Unlock()
    } else {
        p.mu.Unlock()
        // 等待有空闲连接
        select {
        case conn := <-p.conns:
            if conn.IsValid() {
                return conn, nil
            }
        case <-ctx.Done():
            return nil, ctx.Err()
        }
    }
    
    // 创建新连接
    conn, err := p.factory()
    if err != nil {
        p.mu.Lock()
        p.openCount--
        p.mu.Unlock()
        return nil, err
    }
    
    return conn, nil
}

// Put 归还连接
func (p *Pool) Put(conn Connection) {
    if conn == nil || !conn.IsValid() {
        p.mu.Lock()
        p.openCount--
        p.mu.Unlock()
        return
    }
    
    select {
    case p.conns <- conn:
    default:
        // 池已满，关闭连接
        conn.Close()
        p.mu.Lock()
        p.openCount--
        p.mu.Unlock()
    }
}

// cleanup 清理空闲连接
func (p *Pool) cleanup() {
    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()
    
    for range ticker.C {
        p.mu.Lock()
        if p.closed {
            p.mu.Unlock()
            return
        }
        p.mu.Unlock()
        
        // 清理超时连接
        // ...
    }
}

// Close 关闭连接池
func (p *Pool) Close() error {
    p.mu.Lock()
    p.closed = true
    p.mu.Unlock()
    
    close(p.conns)
    return nil
}
```

---

## 第六部分：生产排障案例

### 6.1 缓存问题

```
现象：缓存命中率低，数据库压力大

排查：
1. 检查缓存 TTL 设置
2. 检查缓存 key 设计
3. 检查缓存预热

根因：TTL 太短，热点数据频繁过期

解决方案：
1. 延长热点数据的 TTL
2. 添加缓存预热
3. 使用缓存击穿保护
```

### 6.2 连接池问题

```
现象：数据库连接数耗尽，请求超时

排查：
1. 检查连接池配置
2. 检查是否有连接泄漏
3. 检查慢查询

根因：连接池 MaxOpen 设置过小

解决方案：
1. 增大 MaxOpen
2. 添加连接泄漏检测
3. 优化慢查询
```

---

## 第七部分：自测题

### 问题 1
多级缓存的优势是什么？

<details>
<summary>查看答案</summary>

1. **性能**：L1 最快，L2 容量大
2. **一致性**：L2 保证数据一致性
3. **容错**：L1 故障不影响 L2
4. **回填**：L2 命中后回填 L1
5. **Go 实现**：MultiLevelCache

</details>

### 问题 2
缓存穿透/击穿/雪崩的区别？

<details>
<summary>查看答案</summary>

1. **穿透**：查询不存在的数据
2. **击穿**：热点 key 过期
3. **雪崩**：大量 key 同时过期
4. **解决**：布隆过滤器、互斥锁、随机 TTL
5. **Go 实现**：BloomFilter/HotKeyProtection

</details>

### 问题 3
连接池的关键参数？

<details>
<summary>查看答案</summary>

1. **MaxOpen**：最大打开连接数
2. **MaxIdle**：最大空闲连接数
3. **IdleTimeout**：空闲超时
4. **MaxLifetime**：最大生命周期
5. **Go 实现**：Pool 结构体

</details>

---

*本文档基于高性能架构原理整理。*