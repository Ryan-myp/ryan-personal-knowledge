# MySQL连接池 - 资深专家深度实现

## 一、连接池原理

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      连接池架构                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Client                                                                │
│   ├── getConnection()                                                    │
│   ├── use(connection)                                                    │
│   └── close(connection) → return to pool                                 │
│                                                                         →
│   Connection Pool                                                       │
│   ├── Idle Connections                                                   │
│   ├── Active Connections                                                 │
│   ├── Min/Max Connections                                                  │
│   └── Eviction Policy                                                    │
│                                                                         →
│   MySQL Server                                                          │
│   ├── Thread Pool                                                        │
│   └── Connection Limit                                                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Go实现

```go
import (
    "database/sql"
    "time"
)

func initDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("mysql", dsn)
    if err != nil {
        return nil, err
    }
    
    // 连接池配置
    db.SetMaxOpenConns(100)
    db.SetMaxIdleConns(10)
    db.SetConnMaxLifetime(time.Hour)
    db.SetConnMaxIdleTime(10 * time.Minute)
    
    return db, nil
}
```

## 三、面试高频题

### Q1: 连接池参数如何设置？

```
A:
1. MaxOpenConns: 根据QPS调整
2. MaxIdleConns: 20-50%
3. ConnMaxLifetime: 1小时
```

### Q2: 如何解决连接泄漏？

```
A:
1. 及时close连接
2. 设置超时
3. 监控活跃连接
```

## 四、自测题

1. 解释连接池原理
2. 如何配置参数？
3. 如何检测泄漏？

---

## 参考文档

- [Go database/sql](https://pkg.go.dev/database/sql)
- [MySQL连接池](https://dev.mysql.com/doc/refman/8.0/en/connection-pools.html)
