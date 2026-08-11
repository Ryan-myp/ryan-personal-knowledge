# 数据库连接池深度解析

> 深入数据库连接池：连接管理、超时控制、泄漏检测、性能优化。
> 包含生产环境连接池调优实践。
> 适用对象：DBA、后端工程师

---

## 1. 连接池架构

### 1.1 核心组件

```
连接池架构：

┌─────────────────────────────────────────────────────────────┐
│                    连接池架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Pool Manager (连接池管理器)                                   │
│  ├── 连接创建                                                │
│  ├── 连接回收                                                │
│  └── 连接销毁                                                │
│                                                             │
│  Active Connections (活跃连接)                                 │
│  └── 正在被使用的连接                                         │
│                                                             │
│  Idle Connections (空闲连接)                                   │
│  └── 等待被使用的连接                                         │
│                                                             │
│  Connection Factory (连接工厂)                                 │
│  └── 创建新连接                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现连接池

```go
// connection_pool.go

package db

import (
    "context"
    "sync"
    "time"
)

type Connection struct {
    ID         int
    CreatedAt  time.Time
    LastUsed   time.Time
    InUse      bool
    db         *DB
}

type PoolConfig struct {
    MaxOpenConns  int
    MaxIdleConns  int
    MaxLifetime   time.Duration
    MaxIdleTime   time.Duration
    WaitTimeout   time.Duration
}

type ConnectionPool struct {
    config  PoolConfig
    conns   []*Connection
    mu      sync.Mutex
    cond    *sync.Cond
    closed  bool
    stats   PoolStats
}

type PoolStats struct {
    Opens        int
    Closes       int
    Idle         int
    InUse        int
    WaitCount    int64
    WaitDuration time.Duration
}

func NewConnectionPool(db *DB, config PoolConfig) *ConnectionPool {
    pool := &ConnectionPool{
        config: config,
        conns:  make([]*Connection, 0, config.MaxOpenConns),
        db:     db,
    }
    pool.cond = sync.NewCond(&pool.mu)
    go pool.monitor()
    return pool
}

func (p *ConnectionPool) Get(ctx context.Context) (*Connection, error) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    // 尝试获取空闲连接
    for _, conn := range p.conns {
        if !conn.InUse && p.isAlive(conn) {
            conn.InUse = true
            conn.LastUsed = time.Now()
            p.stats.InUse++
            return conn, nil
        }
    }
    
    // 检查是否可以创建新连接
    if len(p.conns) < p.config.MaxOpenConns {
        conn, err := p.createConnection()
        if err != nil {
            return nil, err
        }
        conn.InUse = true
        p.stats.InUse++
        return conn, nil
    }
    
    // 等待空闲连接
    start := time.Now()
    for {
        for _, conn := range p.conns {
            if !conn.InUse && p.isAlive(conn) {
                conn.InUse = true
                conn.LastUsed = time.Now()
                p.stats.InUse++
                p.stats.WaitCount++
                p.stats.WaitDuration += time.Since(start)
                return conn, nil
            }
        }
        
        if p.config.WaitTimeout > 0 && time.Since(start) > p.config.WaitTimeout {
            return nil, ErrTimeout
        }
        
        p.cond.Wait()
    }
}

func (p *ConnectionPool) Put(conn *Connection) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    conn.InUse = false
    conn.LastUsed = time.Now()
    p.stats.InUse--
    
    p.cond.Signal()
}

func (p *ConnectionPool) Close() {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    p.closed = true
    for _, conn := range p.conns {
        conn.db.Close()
        p.stats.Closes++
    }
    p.conns = make([]*Connection, 0)
    p.cond.Broadcast()
}
```

---

## 2. 连接管理

### 2.1 生命周期管理

```
连接生命周期：

1. 创建
   ├── 验证数据库连接
   ├── 设置超时
   └── 初始化连接状态

2. 使用
   ├── 标记为使用中
   ├── 记录最后使用时间
   └── 执行SQL

3. 回收
   ├── 标记为空闲
   ├── 检查是否过期
   └── 归还到池中

4. 销毁
   ├── 超过最大空闲时间
   ├── 超过最大生命周期
   └── 关闭连接
```

### 2.2 Go 实现连接管理

```go
// connection_lifecycle.go

package db

import (
    "time"
)

func (p *ConnectionPool) isAlive(conn *Connection) bool {
    // 检查连接是否过期
    if p.config.MaxLifetime > 0 {
        if time.Since(conn.CreatedAt) > p.config.MaxLifetime {
            return false
        }
    }
    
    // 检查最大空闲时间
    if p.config.MaxIdleTime > 0 {
        if time.Since(conn.LastUsed) > p.config.MaxIdleTime {
            return false
        }
    }
    
    return true
}

func (p *ConnectionPool) createConnection() (*Connection, error) {
    conn, err := p.db.Connect()
    if err != nil {
        return nil, err
    }
    
    connection := &Connection{
        ID:        len(p.conns),
        CreatedAt: time.Now(),
        LastUsed:  time.Now(),
        db:        p.db,
    }
    
    p.conns = append(p.conns, connection)
    p.stats.Opens++
    
    return connection, nil
}

func (p *ConnectionPool) removeDeadConnections() {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    alive := make([]*Connection, 0)
    for _, conn := range p.conns {
        if p.isAlive(conn) {
            alive = append(alive, conn)
        } else {
            conn.db.Close()
            p.stats.Closes++
        }
    }
    p.conns = alive
}

func (p *ConnectionPool) monitor() {
    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()
    
    for range ticker.C {
        if p.closed {
            return
        }
        p.removeDeadConnections()
        p.enforceLimits()
    }
}

func (p *ConnectionPool) enforceLimits() {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    // 确保至少有MaxIdleConns个空闲连接
    idleCount := 0
    for _, conn := range p.conns {
        if !conn.InUse {
            idleCount++
        }
    }
    
    for idleCount < p.config.MaxIdleConns && 
        len(p.conns) < p.config.MaxOpenConns {
        conn, err := p.createConnection()
        if err != nil {
            break
        }
        idleCount++
    }
}
```

---

## 3. 性能优化

### 3.1 优化策略

```
连接池优化策略：

├── 连接数优化
│   ├── 根据QPS计算所需连接数
│   ├── 设置合理的最大连接数
│   └── 监控连接使用情况
│
├── 超时优化
│   ├── 连接超时
│   ├── 查询超时
│   └── 事务超时
│
├── 泄漏检测
│   ├── 长时间占用检测
│   ├── 未关闭连接告警
│   └── 自动回收
│
└── 监控指标
    ├── 连接数
    ├── 等待时间
    └── 错误率
```

### 3.2 Go 实现性能监控

```go
// pool_monitor.go

package db

import (
    "sync/atomic"
    "time"
)

type PoolMonitor struct {
    pool        *ConnectionPool
    metrics     sync.Map
}

type Metrics struct {
    ActiveConns    int32
    IdleConns      int32
    TotalCreated   int32
    TotalClosed    int32
    WaitCount      int64
    WaitTime       int64 // 纳秒
    LastWaitTime   int64 // 纳秒
}

func NewPoolMonitor(pool *ConnectionPool) *PoolMonitor {
    return &PoolMonitor{pool: pool}
}

func (m *PoolMonitor) RecordAcquire(duration time.Duration) {
    m.metrics.Store("wait_count", atomic.AddInt64(&m.getMetrics().WaitCount, 1))
    m.metrics.Store("wait_time", atomic.AddInt64(&m.getMetrics().WaitTime, duration.Nanoseconds()))
    atomic.StoreInt64(&m.getMetrics().LastWaitTime, duration.Nanoseconds())
}

func (m *PoolMonitor) getMetrics() *Metrics {
    if v, ok := m.metrics.Load("metrics"); ok {
        return v.(*Metrics)
    }
    metrics := &Metrics{}
    m.metrics.Store("metrics", metrics)
    return metrics
}

func (m *PoolMonitor) GetStats() map[string]interface{} {
    metrics := m.getMetrics()
    
    active := atomic.LoadInt32(&metrics.ActiveConns)
    idle := atomic.LoadInt32(&metrics.IdleConns)
    
    waitTime := atomic.LoadInt64(&metrics.WaitTime)
    waitCount := atomic.LoadInt64(&metrics.WaitCount)
    avgWait := int64(0)
    if waitCount > 0 {
        avgWait = waitTime / waitCount
    }
    
    return map[string]interface{}{
        "active_conns":  active,
        "idle_conns":    idle,
        "total_created": atomic.LoadInt32(&metrics.TotalCreated),
        "total_closed":  atomic.LoadInt32(&metrics.TotalClosed),
        "wait_count":    waitCount,
        "avg_wait_ms":   avgWait / 1e6,
        "last_wait_ms":  atomic.LoadInt64(&metrics.LastWaitTime) / 1e6,
    }
}
```

---

## 4. 泄漏检测

### 4.1 检测原理

```
连接泄漏检测：

1. 追踪连接获取
   ├── 记录获取时间
   ├── 记录调用栈
   └── 关联Connection对象

2. 定期扫描
   ├── 检查长时间占用连接
   ├── 生成泄漏报告
   └── 发送告警
```

### 4.2 Go 实现泄漏检测

```go
// leak_detector.go

package db

import (
    "runtime"
    "sync"
    "time"
)

type LeakDetector struct {
    pool           *ConnectionPool
    trackedConns   map[int]*TrackedConnection
    leakThreshold  time.Duration
    mu             sync.Mutex
}

type TrackedConnection struct {
    Conn       *Connection
    AcquiredAt time.Time
    Stack      []byte
}

func NewLeakDetector(pool *ConnectionPool, threshold time.Duration) *LeakDetector {
    return &LeakDetector{
        pool:          pool,
        trackedConns:  make(map[int]*TrackedConnection),
        leakThreshold: threshold,
    }
}

func (ld *LeakDetector) Track(conn *Connection) {
    ld.mu.Lock()
    defer ld.mu.Unlock()
    
    stack := make([]byte, 1024)
    runtime.Callers(3, stack)
    
    ld.trackedConns[conn.ID] = &TrackedConnection{
        Conn:       conn,
        AcquiredAt: time.Now(),
        Stack:      stack,
    }
}

func (ld *LeakDetector) Untrack(connID int) {
    ld.mu.Lock()
    defer ld.mu.Unlock()
    
    delete(ld.trackedConns, connID)
}

func (ld *LeakDetector) CheckLeaks() []*LeakReport {
    ld.mu.Lock()
    defer ld.mu.Unlock()
    
    var leaks []*LeakReport
    
    for id, tracked := range ld.trackedConns {
        duration := time.Since(tracked.AcquiredAt)
        if duration > ld.leakThreshold {
            leaks = append(leaks, &LeakReport{
                ConnID:     id,
                Duration:   duration,
                StackTrace: string(tracked.Stack),
            })
        }
    }
    
    return leaks
}

type LeakReport struct {
    ConnID     int
    Duration   time.Duration
    StackTrace string
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| 连接池 | 管理数据库连接 |
| 生命周期 | 控制连接创建/销毁 |
| 性能监控 | 追踪连接使用 |
| 泄漏检测 | 发现连接泄漏 |

### 5.2 最佳实践

- [ ] 合理设置连接数
- [ ] 配置合理的超时
- [ ] 启用泄漏检测
- [ ] 监控连接指标

---

*最后更新：2026-08-11*
*作者：Ryan*
