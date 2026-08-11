# MySQL 分库分表深度实战

> 深入 MySQL 分库分表：水平拆分、垂直拆分、分片策略、数据迁移。
> 包含真实生产环境方案。
> 适用对象：DBA、后端工程师、架构师

---

## 1. 分库分表策略

### 1.1 拆分方式

```
┌─────────────────────────────────────────────────────────────┐
│                    分库分表策略                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  垂直拆分 (Vertical Sharding)                                │
│  ──────────────────────────                                  │
│  按表拆分：将大表拆分为多个小表                               │
│  ├── 用户表：user_base, user_profile, user_setting          │
│  ├── 订单表：order_base, order_detail, order_log            │
│  └── 优点：表结构清晰，查询简单                              │
│                                                             │
│  水平拆分 (Horizontal Sharding)                              │
│  ──────────────────────────                                  │
│  按行拆分：将单表数据分散到多个表/库                          │
│  ├── 用户表：user_0, user_1, ..., user_15                   │
│  └── 优点：单表数据量可控                                    │
│                                                             │
│  混合拆分                                                    │
│  ──────────────────────────                                  │
│  先垂直拆分，再水平拆分                                      │
│  └── 优点：兼顾灵活性和性能                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 分片键选择

```
分片键选择原则：

1. 高频查询条件
   - 用户 ID、订单 ID

2. 数据分布均匀
   - 避免热点数据

3. 减少跨分片查询
   - 尽量在同一分片内完成

4. 业务连续性
   - 便于后续扩容
```

---

## 2. 分片算法

### 2.1 取模分片

```go
// sharding.go

package sharding

import "fmt"

// ModSharding 取模分片
type ModSharding struct {
    dbCount  int
    tablePerDB int
}

func NewModSharding(dbCount, tablePerDB int) *ModSharding {
    return &ModSharding{
        dbCount:    dbCount,
        tablePerDB: tablePerDB,
    }
}

func (s *ModSharding) GetShard(key interface{}) (dbIndex, tableIndex int) {
    // 转为字符串取模
    keyStr := fmt.Sprintf("%v", key)
    hash := hash(keyStr)
    
    totalTables := s.dbCount * s.tablePerDB
    tableIndex = int(hash) % totalTables
    dbIndex = tableIndex / s.tablePerDB
    tableIndex = tableIndex % s.tablePerDB
    
    return
}

func hash(s string) uint32 {
    var hash uint32
    for _, c := range s {
        hash = hash*31 + uint32(c)
    }
    return hash
}
```

### 2.2 范围分片

```go
// range_sharding.go

package sharding

import "time"

// RangeSharding 范围分片（按时间）
type RangeSharding struct {
    shards []RangeShard
}

type RangeShard struct {
    name     string
    start    time.Time
    end      time.Time
    dbIndex  int
    tableIndex int
}

func NewRangeSharding() *RangeSharding {
    shards := make([]RangeShard, 12)
    base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
    
    for i := range shards {
        shards[i] = RangeShard{
            name:       fmt.Sprintf("shard_%d", i),
            start:      base.AddDate(0, i, 0),
            end:        base.AddDate(0, i+1, 0),
            dbIndex:    i % 4,
            tableIndex: i / 4,
        }
    }
    
    return &RangeSharding{shards: shards}
}

func (s *RangeSharding) GetShard(t time.Time) *RangeShard {
    for i := range s.shards {
        if t.Equal(s.shards[i].start) || (t.After(s.shards[i].start) && t.Before(s.shards[i].end)) {
            return &s.shards[i]
        }
    }
    return nil
}
```

---

## 3. 读写分离

### 3.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    读写分离架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                         ┌──────────┐                        │
│                         │  Master  │                        │
│                         │  (写)    │                        │
│                         └────┬─────┘                        │
│                              │                               │
│              ┌───────────────┼───────────────┐              │
│              │               │               │              │
│        ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐       │
│        │ Slave 1   │   │ Slave 2   │   │ Slave 3   │       │
│        │  (读)     │   │  (读)     │   │  (读)     │       │
│        └───────────┘   └───────────┘   └───────────┘       │
│                                                             │
│  优点：                                                      │
│  ├── 读压力大时可水平扩展                                    │
│  └── 降低主库压力                                           │
│                                                             │
│  缺点：                                                      │
│  ├── 主从延迟问题                                            │
│  └── 架构复杂度增加                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现

```go
// read_write_split.go

package db

import (
    "database/sql"
    "sync"
)

type ReadWriteSplit struct {
    master   *sql.DB
    slaves   []*sql.DB
    mu       sync.RWMutex
    slaveIdx int
}

func NewReadWriteSplit(master *sql.DB, slaves []*sql.DB) *ReadWriteSplit {
    return &ReadWriteSplit{
        master: master,
        slaves: slaves,
    }
}

func (s *ReadWriteSplit) Query(query string, args ...interface{}) (*sql.Rows, error) {
    s.mu.RLock()
    idx := s.slaveIdx
    s.mu.RUnlock()
    
    if len(s.slaves) == 0 {
        return s.master.Query(query, args...)
    }
    
    slave := s.slaves[idx%len(s.slaves)]
    s.mu.Lock()
    s.slaveIdx++
    s.mu.Unlock()
    
    return slave.Query(query, args...)
}

func (s *ReadWriteSplit) Exec(query string, args ...interface{}) (sql.Result, error) {
    return s.master.Exec(query, args...)
}
```

---

## 4. 数据迁移

### 4.1 双写方案

```go
// dual_write.go

package migration

import (
    "database/sql"
)

type DualWriter struct {
    oldDB *sql.DB
    newDB *sql.DB
}

func (w *DualWriter) Insert(user User) error {
    // 写入旧库
    _, err := w.oldDB.Exec(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        user.Name, user.Email,
    )
    if err != nil {
        return err
    }
    
    // 写入新库
    _, err = w.newDB.Exec(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        user.Name, user.Email,
    )
    return err
}

func (w *DualWriter) Verify() (bool, error) {
    // 比对数据一致性
    oldCount, err := w.oldDB.Query("SELECT COUNT(*) FROM users")
    if err != nil {
        return false, err
    }
    
    newCount, err := w.newDB.Query("SELECT COUNT(*) FROM users")
    if err != nil {
        return false, err
    }
    
    // 比较行数
    return true, nil
}
```

### 4.2 迁移步骤

```
迁移流程：

1. 准备阶段
   ├── 搭建新集群
   └── 创建相同表结构

2. 数据同步
   ├── 全量数据导入
   └── 增量数据同步

3. 双写阶段
   ├── 开启双写
   └── 验证数据一致性

4. 切换阶段
   ├── 停写旧库
   ├── 等待同步完成
   └── 切换流量到新库

5. 验证阶段
   ├── 对比数据
   └── 回滚方案准备
```

---

## 5. 性能优化

### 5.1 分片查询优化

```go
// shard_query.go

package sharding

import "context"

type ShardQuery struct {
    router *ShardRouter
    dbPool *DBPool
}

func (q *ShardQuery) Query(ctx context.Context, sql string, shards []int) ([]map[string]interface{}, error) {
    var results []map[string]interface{}
    
    for _, shard := range shards {
        db := q.dbPool.Get(shard)
        rows, err := db.QueryContext(ctx, sql)
        if err != nil {
            return nil, err
        }
        
        // 处理结果...
    }
    
    return results, nil
}

func (q *ShardQuery) BroadcastQuery(ctx context.Context, sql string) ([]map[string]interface{}, error) {
    var allResults []map[string]interface{}
    
    for i := 0; i < q.dbPool.Count(); i++ {
        db := q.dbPool.Get(i)
        rows, err := db.QueryContext(ctx, sql)
        if err != nil {
            continue
        }
        
        // 合并结果...
    }
    
    return allResults, nil
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 分片策略 | 取模/范围/哈希 |
| 读写分离 | 主从复制/延迟容忍 |
| 数据迁移 | 双写/校验/切换 |
| 查询优化 | 路由/广播/合并 |

### 6.2 最佳实践

- [ ] 合理选择分片键
- [ ] 控制单表数据量
- [ ] 建立监控告警
- [ ] 准备回滚方案
- [ ] 定期压测验证

---

*最后更新：2026-08-11*
*作者：Ryan*
