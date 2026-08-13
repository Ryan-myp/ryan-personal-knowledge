# MySQL连接池实现 - 资深专家深度实现

## 一、连接池架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MySQL连接池架构                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐             │
│   │  Application │────►│ Connection  │────►│   MySQL     │             │
│   │   Client    │     │    Pool     │     │  Server     │             │
│   └─────────────┘     └─────────────┘     └─────────────┘             │
│                            │                                              │
│                    ┌───────┴───────┐                                     │
│                    ▼               ▼                                     │
│               ┌─────────┐    ┌─────────┐                                │
│               │ Active  │    │ Idle    │                                │
│               │  Conns  │    │  Conns  │                                │
│               └─────────┘    └─────────┘                                │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package connpool

import (
    "database/sql"
    "sync"
    "time"
)

type Config struct {
    MaxOpen     int
    MaxIdle     int
    IdleTimeout time.Duration
}

type Pool struct {
    mu      sync.Mutex
    conns   []*sql.Conn
    config  Config
    db      *sql.DB
}

func New(config Config) *Pool {
    db, _ := sql.Open("mysql", "user:pass@tcp(127.0.0.1:3306)/db")
    
    db.SetMaxOpenConns(config.MaxOpen)
    db.SetMaxIdleConns(config.MaxIdle)
    db.SetConnMaxIdleTime(config.IdleTimeout)
    
    return &Pool{
        config: config,
        db:     db,
    }
}

// Acquire 获取连接
func (p *Pool) Acquire(ctx context.Context) (*sql.Conn, error) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    // 从池中获取空闲连接
    for _, conn := range p.conns {
        if !conn.IsClosed() {
            // 移除并返回
            p.conns = append(p.conns[:i], p.conns[i+1:]...)
            return conn, nil
        }
    }
    
    // 创建新连接
    return p.db.Conn(ctx)
}

// Release 归还连接
func (p *Pool) Release(conn *sql.Conn) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    if !conn.IsClosed() && len(p.conns) < p.config.MaxIdle {
        p.conns = append(p.conns, conn)
    }
}

// Stats 获取连接池统计
func (p *Pool) Stats() PoolStats {
    return PoolStats{
        Open:  p.db.Stats().OpenConnections,
        Idle:  p.db.Stats().InUse,
        Wait:  p.db.Stats().WaitCount,
        Miss:  p.db.Stats().WaitDuration,
    }
}
```

## 三、面试高频题

### Q1: 连接池如何配置？

```
A:
1. MaxOpen: 最大连接数
2. MaxIdle: 最大空闲连接
3. IdleTimeout: 空闲超时时间
```

### Q2: 如何监控连接池？

```
A:
1. Open Connections
2. In Use
3. Wait Count
```

## 四、自测题

1. 解释连接池架构
2. 如何配置连接池？
3. 如何监控连接池？

---

## 参考文档

- [Go Database/sql](https://pkg.go.dev/database/sql)
- [MySQL Connector](https://dev.mysql.com/doc/connector-go/en/)
