# MySQL分库分表 - 资深专家深度实现

## 一、分片策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        分库分表策略                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   水平分表:                                                               │
│   • Hash分片: user_id % 16 → 16个分片                                    │
│   • 范围分片: user_id 0-1000万 → 分片1, 1000-2000万 → 分片2             │
│   • 时间分片: 按月分片                                                  │
│                                                                         │
│   垂直分库:                                                               │
│   • 用户库: user, profile, settings                                     │
│   • 订单库: order, payment, logistics                                   │
│   • 商品库: product, category, inventory                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Go实现

```go
package sharding

import (
    "fmt"
)

type ShardingStrategy interface {
    GetShardKey(data interface{}) string
    GetShardIndex(key string, totalShards int) int
}

// Hash分片策略
type HashShardingStrategy struct{}

func (h *HashShardingStrategy) GetShardIndex(key string, totalShards int) int {
    hash := fnv32(key)
    return int(hash % uint32(totalShards))
}

func fnv32(key string) uint32 {
    hash := uint32(2166136261)
    for i := 0; i < len(key); i++ {
        hash ^= uint32(key[i])
        hash *= 16777619
    }
    return hash
}

// 路由到正确的数据库和表
func (s *ShardingService) Route(tableName string, shardKey string) (dbIndex, tableIndex int) {
    strategy := s.getStrategy(tableName)
    index := strategy.GetShardIndex(shardKey, s.totalShards)
    
    dbIndex = index / s.tablesPerDB
    tableIndex = index % s.tablesPerDB
    
    return
}
```

## 三、分布式事务

```go
package distributed_txn

import (
    "context"
)

// TCC事务
type TCCTransaction struct {
    ctx context.Context
}

func (t *TCCTransaction) Try() error {
    // 尝试阶段: 执行业务逻辑，预留资源
    return nil
}

func (t *TCCTransaction) Confirm() error {
    // 确认阶段: 提交事务
    return nil
}

func (t *TCCTransaction) Cancel() error {
    // 取消阶段: 回滚事务
    return nil
}

// 本地消息表
type LocalMessageTable struct {
    db *DB
}

func (m *LocalMessageTable) Send(msg *Message) error {
    // 1. 写入本地消息表
    err := m.db.Insert("messages", msg)
    if err != nil {
        return err
    }
    
    // 2. 执行业务
    err = m.executeBusiness(msg)
    if err != nil {
        // 业务失败，消息标记为失败
        m.db.UpdateStatus(msg.ID, "failed")
        return err
    }
    
    // 3. 标记消息为已发送
    m.db.UpdateStatus(msg.ID, "sent")
    return nil
}
```

## 四、面试高频题

### Q1: 分库分表后如何解决跨分片查询？

```
A:
1. 避免跨分片查询
2. 使用ES同步数据
3. 分布式查询引擎（ShardingSphere）
```

### Q2: 如何选择分片键？

```
A:
1. 高基数（唯一值多）
2. 查询频繁
3. 均匀分布
```

## 五、自测题

1. 解释分库分表策略
2. 如何实现分布式事务？
3. 如何处理数据迁移？

---

## 参考文档

- [ShardingSphere](https://github.com/apache/shardingsphere)
- [MySQL官方文档](https://dev.mysql.com/doc/)
