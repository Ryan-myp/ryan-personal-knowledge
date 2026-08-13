# MySQL分库分表 - 资深专家深度实现

## 一、分片策略

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    分库分表策略                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   水平分片 (Sharding)                                                    │
│   ├── Range分片: user_id 1-1000 -> DB1, 1001-2000 -> DB2               │
│   ├── Hash分片: user_id % 8 -> 分片0-7                                  │
│   └── 一致性Hash: 减少扩容影响                                           │
│                                                                         →
│   垂直分片 (Vertical Sharding)                                           │
│   ├── 核心表: 用户、订单 (高频)                                          │
│   ├── 详情表: 用户资料、订单详情 (低频)                                   │
│   └── 历史表: 日志、审计 (归档)                                          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```go
package sharding

import (
    "context"
    "database/sql"
)

// ShardingRouter 分片路由器
type ShardingRouter struct {
    dbs map[int]*sql.DB
}

func NewShardingRouter(shards int) *ShardingRouter {
    dbs := make(map[int]*sql.DB, shards)
    for i := 0; i < shards; i++ {
        dbs[i] = openDB(i)
    }
    return &ShardingRouter{dbs: dbs}
}

// GetUserDB 获取用户所属分片
func (r *ShardingRouter) GetUserDB(userID int) *sql.DB {
    return r.dbs[userID % len(r.dbs)]
}

// QueryUser 查询用户
func (r *ShardingRouter) QueryUser(ctx context.Context, userID int) (*User, error) {
    db := r.GetUserDB(userID)
    var user User
    err := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = ?", userID).Scan(
        &user.ID, &user.Name,
    )
    return &user, err
}
```

## 三、面试高频题

### Q1: 如何设计分片键？

```
A:
1. 高频查询字段
2. 均匀分布
3. 避免跨分片查询
```

### Q2: 如何解决跨分片查询？

```
A:
1. 冗余表设计
2. 搜索引擎辅助
3. 批量查询聚合
```

## 四、自测题

1. 解释分片策略
2. 如何设计分片键？
3. 如何解决跨分片查询？

---

## 参考文档

- [ShardingSphere](https://shardingsphere.apache.org/)
- [Vitess](https://vitess.io/)
