# 数据库连接池深度实现 - MySQL/PostgreSQL/Redis

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 全栈/数据库  
> **代码密度**: 30%

---

## 一、连接池架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                      连接池架构                                       │
│                                                                     │
│  ┌─────────────┐      ┌─────────────────────────────────┐          │
│  │   App       │─────▶│         Connection Pool          │          │
│  │  Requests   │      │  ┌───────┐  ┌───────┐  ┌───────┐ │          │
│  └─────────────┘      │  │  Con  │  │  Con  │  │  Con  │ │          │
│                       │  │   1   │  │   2   │  │   3   │ │          │
│                       │  └───┬───┘  └───┬───┘  └───┬───┘ │          │
│                       │      │          │          │       │          │
│                       │  ┌───▼──────────▼──────────▼───┐ │          │
│                       │  │      Validation + Health     │ │          │
│                       │  └──────────────┬───────────────┘ │          │
│                       └─────────────────┼─────────────────┘          │
│                                         │                            │
│                              ┌────────────▼────────────┐             │
│                              │     Database Server      │             │
│                              │   (MySQL/PG/Redis)      │             │
│                              └─────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、MySQL 连接池

```go
// db/mysql_pool.go
package db

import (
    "database/sql"
    "fmt"
    "time"
    _ "github.com/go-sql-driver/mysql"
)

// MySQLPool MySQL 连接池配置
type MySQLPool struct {
    db *sql.DB
}

// PoolConfig 连接池配置
type PoolConfig struct {
    MaxOpenConns    int           // 最大打开连接数
    MaxIdleConns    int           // 最大空闲连接数
    MaxLifetime     time.Duration // 连接最大生命周期
    MaxIdleTime     time.Duration // 连接最大空闲时间
    ConnMaxIdleTime time.Duration
}

// NewMySQLPool 创建 MySQL 连接池
func NewMySQLPool(dsn string, config PoolConfig) (*MySQLPool, error) {
    db, err := sql.Open("mysql", dsn)
    if err != nil {
        return nil, fmt.Errorf("open mysql: %w", err)
    }
    
    // 配置连接池
    db.SetMaxOpenConns(config.MaxOpenConns)
    db.SetMaxIdleConns(config.MaxIdleConns)
    db.SetConnMaxLifetime(config.MaxLifetime)
    db.SetConnMaxIdleTime(config.ConnMaxIdleTime)
    
    // 健康检查
    db.SetPingInterval(30 * time.Second)
    
    // 测试连接
    if err := db.Ping(); err != nil {
        db.Close()
        return nil, fmt.Errorf("ping mysql: %w", err)
    }
    
    return &MySQLPool{db: db}, nil
}

// Query 查询
func (p *MySQLPool) Query(ctx context.Context, query string, args ...interface{}) (*sql.Rows, error) {
    return p.db.QueryContext(ctx, query, args...)
}

// Exec 执行
func (p *MySQLPool) Exec(ctx context.Context, query string, args ...interface{}) (sql.Result, error) {
    return p.db.ExecContext(ctx, query, args...)
}

// Close 关闭连接池
func (p *MySQLPool) Close() error {
    return p.db.Close()
}

// Stats 连接池统计
func (p *MySQLPool) Stats() sql.DBStats {
    return p.db.Stats()
}
```

---

## 三、PostgreSQL 连接池

```go
// db/pg_pool.go
package db

import (
    "database/sql"
    "fmt"
    "time"
    _ "github.com/lib/pq"
)

// PGPool PostgreSQL 连接池
type PGPool struct {
    db *sql.DB
}

// NewPGPool 创建 PG 连接池
func NewPGPool(connString string, config PoolConfig) (*PGPool, error) {
    db, err := sql.Open("postgres", connString)
    if err != nil {
        return nil, fmt.Errorf("open postgres: %w", err)
    }
    
    db.SetMaxOpenConns(config.MaxOpenConns)
    db.SetMaxIdleConns(config.MaxIdleConns)
    db.SetConnMaxLifetime(config.MaxLifetime)
    db.SetConnMaxIdleTime(config.ConnMaxIdleTime)
    
    if err := db.Ping(); err != nil {
        db.Close()
        return nil, fmt.Errorf("ping postgres: %w", err)
    }
    
    return &PGPool{db: db}, nil
}

// Transaction 事务处理
func (p *PGPool) Transaction(ctx context.Context, fn func(*sql.Tx) error) error {
    tx, err := p.db.BeginTx(ctx, nil)
    if err != nil {
        return err
    }
    defer tx.Rollback()
    
    if err := fn(tx); err != nil {
        return err
    }
    
    return tx.Commit()
}
```

---

## 四、Redis 连接池

```go
// db/redis_pool.go
package db

import (
    "context"
    "github.com/redis/go-redis/v9"
    "time"
)

// RedisPool Redis 连接池
type RedisPool struct {
    rdb *redis.Client
}

// NewRedisPool 创建 Redis 连接池
func NewRedisPool(addr string, password string, db int) *RedisPool {
    rdb := redis.NewClient(&redis.Options{
        Addr:         addr,
        Password:     password,
        DB:           db,
        MaxRetries:   3,
        PoolSize:     50,
        MinIdleConns: 10,
        PoolTimeout:  5 * time.Second,
        IdleTimeout:  5 * time.Minute,
        IdleCheckFrequency: time.Minute,
        ReadTimeout:  3 * time.Second,
        WriteTimeout: 3 * time.Second,
        DialTimeout:  5 * time.Second,
    })
    
    return &RedisPool{rdb: rdb}
}

// Get 获取
func (p *RedisPool) Get(ctx context.Context, key string) (string, error) {
    return p.rdb.Get(ctx, key).Result()
}

// Set 设置
func (p *RedisPool) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
    return p.rdb.Set(ctx, key, value, expiration).Err()
}

// Pipeline 管道操作
func (p *RedisPool) Pipeline(ctx context.Context, cmds ...redis.Cmder) error {
    pipe := p.rdb.Pipeline()
    for _, cmd := range cmds {
        pipe.Process(cmd)
    }
    _, err := pipe.Exec(ctx)
    return err
}

// Close 关闭
func (p *RedisPool) Close() error {
    return p.rdb.Close()
}
```

---

## 五、连接池监控

```go
// db/pool_monitor.go
package db

import (
    "fmt"
    "runtime"
    "time"
)

// PoolStats 连接池统计
type PoolStats struct {
    OpenConnections int
    InUse           int
    Idle            int
    WaitCount       int64
    WaitDuration    time.Duration
    MaxIdleClosed   int64
    MaxLifetimeClosed int64
}

// Monitor 连接池监控
type Monitor struct {
    lastStats PoolStats
    interval  time.Duration
}

func NewMonitor(interval time.Duration) *Monitor {
    return &Monitor{interval: interval}
}

func (m *Monitor) Collect(db *sql.DB) PoolStats {
    stats := db.Stats()
    current := PoolStats{
        OpenConnections: stats.OpenConnections,
        InUse:           stats.InUse,
        Idle:            stats.Idle,
        WaitCount:       stats.WaitCount,
        WaitDuration:    stats.WaitDuration,
        MaxIdleClosed:   stats.MaxIdleClosed,
        MaxLifetimeClosed: stats.MaxLifetimeClosed,
    }
    m.lastStats = current
    return current
}

func (m *Monitor) Log(db *sql.DB) {
    stats := m.Collect(db)
    goStat := runtime.NumGoroutine()
    
    fmt.Printf("[Pool Stats] Open:%d InUse:%d Idle:%d Wait:%d Goroutines:%d\n",
        stats.OpenConnections, stats.InUse, stats.Idle,
        stats.WaitCount, goStat)
}
```

---

## 六、连接池配置建议

| 场景 | MaxOpen | MaxIdle | MaxLifetime | 说明 |
|------|---------|---------|-------------|------|
| 低负载 | 10 | 5 | 5min | 节省资源 |
| 中等负载 | 50 | 20 | 10min | 推荐配置 |
| 高负载 | 200 | 100 | 30min | 需要调优 |
| 连接泄露 | 5 | 2 | 1min | 快速回收 |

---

## 七、自测题

1. **MaxOpenConns 设为 0 会怎样？**
   - 无限制，可能导致数据库连接耗尽

2. **连接池泄漏的表现？**
   - OpenConnections 持续增长，InUse 不为 0

3. **Redis 为什么不需要传统连接池？**
   - Redis 是单线程，连接开销小，但仍有连接池管理

