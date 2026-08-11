# 数据库分库分表深度解析

> 深入数据库分库分表：ShardingSphere、分布式ID、路由策略、数据迁移。
> 源码级分析，包含生产环境最佳实践。
> 适用对象：DBA、后端工程师

---

## 1. 分库分表策略

### 1.1 水平分表

```
水平分表策略：

┌─────────────────────────────────────────────────────────────┐
│                        分表策略                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  按时间分表：                                                │
│  ├── user_202401, user_202402, user_202403...               │
│  └── 适用：日志、订单等时间敏感数据                          │
│                                                             │
│  按ID取模分表：                                              │
│  ├── user_0, user_1, user_2... user_15                      │
│  └── 适用：用户表、订单表等均匀分布数据                       │
│                                                             │
│  按范围分表：                                                │
│  ├── user_0_1000000, user_1000000_2000000...                │
│  └── 适用：需要范围查询的数据                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Go 实现分表路由

```go
// sharding.go

package database

import (
    "fmt"
    "sync"
)

type ShardingStrategy int

const (
    Modulo ShardingStrategy = iota
    Range
    Time
)

type ShardingRule struct {
    TableName  string
    Strategy   ShardingStrategy
    NumTables  int
    TimeFormat string
}

type ShardingEngine struct {
    rules map[string]*ShardingRule
    mu    sync.RWMutex
}

func NewShardingEngine() *ShardingEngine {
    return &ShardingEngine{
        rules: make(map[string]*ShardingRule),
    }
}

func (se *ShardingEngine) AddRule(rule *ShardingRule) {
    se.mu.Lock()
    defer se.mu.Unlock()
    se.rules[rule.TableName] = rule
}

func (se *ShardingEngine) GetTableName(ruleName string, shardKey interface{}) string {
    se.mu.RLock()
    rule, ok := se.rules[ruleName]
    se.mu.RUnlock()
    
    if !ok {
        return ruleName
    }
    
    switch rule.Strategy {
    case Modulo:
        return fmt.Sprintf("%s_%d", ruleName, shardKey.(int64)%int64(rule.NumTables))
    case Range:
        return se.rangeShard(ruleName, shardKey)
    case Time:
        return se.timeShard(ruleName, shardKey)
    }
    return ruleName
}

func (se *ShardingEngine) rangeShard(tableName string, shardKey interface{}) string {
    id := shardKey.(int64)
    rangeSize := int64(1000000)
    index := id / rangeSize
    return fmt.Sprintf("%s_%d", tableName, index)
}

func (se *ShardingEngine) timeShard(tableName string, shardKey interface{}) string {
    t := shardKey.(string)
    return fmt.Sprintf("%s_%s", tableName, t)
}
```

---

## 2. 分布式 ID

### 2.1 雪花算法优化

```
雪花算法优化：

├── 时钟回拨问题
│   ├── 等待时钟同步
│   └── 抛出异常
│
├── 机器ID分配
│   ├── 手动配置
│   ├── ZooKeeper分配
│   └── 数据库分配
│
└── 序列号优化
    ├── 位运算优化
    └── 批量生成
```

### 2.2 Go 实现雪花算法

```go
// snowflake.go

package database

import (
    "sync"
    "time"
)

type Snowflake struct {
    mu              sync.Mutex
    workerID        int64
    datacenterID    int64
    sequence        int64
    lastTimestamp   int64
}

const (
    workerIDBits      = int64(5)
    datacenterIDBits  = int64(5)
    sequenceBits      = int64(12)
    
    maxWorkerID       = -1 ^ (-1 << workerIDBits)
    maxDatacenterID   = -1 ^ (-1 << datacenterIDBits)
    
    workerIDShift     = sequenceBits
    datacenterIDShift = sequenceBits + workerIDBits
    timestampLeftShift = sequenceBits + workerIDBits + datacenterIDBits
    
    sequenceMask = -1 ^ (-1 << sequenceBits)
)

func NewSnowflake(workerID, datacenterID int64) (*Snowflake, error) {
    if workerID > maxWorkerID || workerID < 0 {
        return nil, fmt.Errorf("worker ID can't be greater than %d or less than 0", maxWorkerID)
    }
    if datacenterID > maxDatacenterID || datacenterID < 0 {
        return nil, fmt.Errorf("datacenter ID can't be greater than %d or less than 0", maxDatacenterID)
    }
    
    return &Snowflake{
        workerID:    workerID,
        datacenterID: datacenterID,
        sequence:    0,
    }, nil
}

func (sf *Snowflake) NextID() (int64, error) {
    sf.mu.Lock()
    defer sf.mu.Unlock()
    
    timestamp := time.Now().UnixMilli()
    
    if timestamp < sf.lastTimestamp {
        return 0, fmt.Errorf("clock moved backwards")
    }
    
    if timestamp == sf.lastTimestamp {
        sf.sequence = (sf.sequence + 1) & sequenceMask
        if sf.sequence == 0 {
            for timestamp <= sf.lastTimestamp {
                timestamp = time.Now().UnixMilli()
            }
        }
    } else {
        sf.sequence = 0
    }
    
    sf.lastTimestamp = timestamp
    
    id := ((timestamp) << timestampLeftShift) |
           (sf.datacenterID << datacenterIDShift) |
           (sf.workerID << workerIDShift) |
           sf.sequence
    
    return id, nil
}
```

---

## 3. 数据迁移

### 3.1 在线迁移流程

```
在线迁移流程：

1. 双写阶段
   ├── 新表写入
   └── 旧表写入
   
2. 数据同步阶段
   ├── 历史数据迁移
   └── 增量数据同步
   
3. 切换阶段
   ├── 停写旧表
   ├── 数据校验
   └── 切换读流量
   
4. 清理阶段
   └── 删除旧表
```

### 3.2 Go 实现数据迁移

```go
// data_migration.go

package database

import (
    "context"
    "database/sql"
)

type MigrationStrategy int

const (
    DualWrite MigrationStrategy = iota
    CDC
    BatchCopy
)

type DataMigration struct {
    sourceDB *sql.DB
    targetDB *sql.DB
    strategy MigrationStrategy
}

func NewDataMigration(source, target *sql.DB) *DataMigration {
    return &DataMigration{
        sourceDB: source,
        targetDB: target,
        strategy: DualWrite,
    }
}

func (dm *DataMigration) Migrate(ctx context.Context, table string) error {
    switch dm.strategy {
    case DualWrite:
        return dm.dualWriteMigration(ctx, table)
    case CDC:
        return dm.cdcMigration(ctx, table)
    case BatchCopy:
        return dm.batchCopyMigration(ctx, table)
    }
    return nil
}

func (dm *DataMigration) dualWriteMigration(ctx context.Context, table string) error {
    // 1. 双写配置
    // 2. 历史数据迁移
    // 3. 增量数据同步
    // 4. 切换流量
    return nil
}

func (dm *DataMigration) cdcMigration(ctx context.Context, table string) error {
    // CDC 同步
    return nil
}

func (dm *DataMigration) batchCopyMigration(ctx context.Context, table string) error {
    // 批量复制
    return nil
}
```

---

## 4. 总结

### 4.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| 分表策略 | 数据分散 |
| 分布式ID | 全局唯一 |
| 数据迁移 | 平滑升级 |

### 4.2 最佳实践

- [ ] 合理选择分表策略
- [ ] 解决时钟回拨问题
- [ ] 在线迁移保证一致性
- [ ] 定期数据归档

---

*最后更新：2026-08-12*
*作者：Ryan*
