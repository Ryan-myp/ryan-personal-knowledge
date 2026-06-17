# 分布式数据库深度：TiDB 事务 + 分布式索引/序列号

> TiDB 2PC 事务机制、MVCC 实现、全局序列号、分布式索引

---

## 第一部分：TiDB 事务模型

### TiDB 的乐观锁（Optimistic Lock）

```
TiDB 默认事务模型：乐观锁（Optimistic）

优点：
1. 读操作不加锁，高并发读场景性能好
2. 写冲突时才检测，大部分事务成功提交
3. 适合广告平台场景（读多写少）

缺点：
1. 写冲突率高时，重试次数多，性能下降
2. 长事务容易冲突

实现：
1. 开始事务：获取 TSO（start_ts）
2. 读操作：读取 start_ts 之前的数据
3. 写操作：写入 Lock CF + Write CF
4. 提交：预写（prewrite）→ 提交（commit）
```

### 源码逐行解析：2PC 提交流程

```rust
// TiKV 源码：src/storage/txn/actions/commit.rs
// 2PC 提交流程

pub async fn commit(&self, keys: Vec<Key>, start_ts: Timestamp, 
                    commit_ts: Timestamp) -> Result<()> {
    // 1. 遍历所有 key 进行 commit
    for key in keys {
        // 2. 检查 Key 是否已提交（避免重复提交）
        let existing = self.get_write(&key, start_ts).await?;
        if let Some(write) = existing {
            if write.commit_ts == Some(commit_ts) {
                continue; // 已提交，跳过
            }
        }
        
        // 3. 更新 Write CF 中的 commit_ts
        let write = Write {
            op: Op::Put,
            start_ts: start_ts,
            commit_ts: Some(commit_ts),  // 标记已提交
            short_value: None,
        };
        
        // 4. 写入 RocksDB Write CF
        self.put_write(key, &write).await?;
        
        // 5. 清理 Lock CF（如果存在）
        self.delete_lock(key).await?;
    }
    
    // 6. 异步清理旧版本数据
    self.schedule_purge(commit_ts).await;
    
    Ok(())
}
```

**关键点**：
- **Write CF commit_ts**：标记事务提交，读者可以根据 commit_ts 读取
- **Lock CF 清理**：事务提交后删除锁
- **异步清理**：旧版本数据由 GC 线程定期清理

### TiDB MVCC 存储结构

```
TiDB/MVCC 存储结构（RocksDB）：

Write CF（写列族）：
┌─────────────────────────────────────────────────┐
│ Key: user:1001                                  │
│ │ commit_ts=100 │ start_ts=90 │ Put │           │
│ │ commit_ts=90  │ start_ts=80 │ Put │           │
│ │ commit_ts=80  │ start_ts=70 │ Put │           │
└─────────────────────────────────────────────────┘
说明：Write CF 按 Key 排序，commit_ts 递增

Lock CF（锁列族）：
┌─────────────────────────────────────────────────┐
│ Key: user:1001                                  │
│ │ start_ts=100 │ TxnId=100 │ Put │             │
└─────────────────────────────────────────────────┘
说明：Lock CF 只有活跃事务的锁

Default CF（默认列族，业务数据）：
┌─────────────────────────────────────────────────┐
│ Key: user:1001:version=90                       │
│ Value: {"name":"Alice","age":25}                │
│ Key: user:1001:version=80                       │
│ Value: {"name":"Alice","age":24}                │
└─────────────────────────────────────────────────┘
说明：Default CF 按 version 排序，保存历史值
```

---

## 第二部分：分布式索引

### TiDB 索引类型

```
TiDB 支持的索引：
1. 主键索引：Row ID 自动创建
2. 唯一索引：UNIQUE KEY
3. 普通索引：INDEX
4. 联合索引：INDEX(a, b, c)
5. 覆盖索引：SELECT 的列都在索引中
6. 前缀索引：INDEX(col(10))

TiDB 索引存储：
┌─────────────────────────────────────────────────┐
│ 主键索引：                                      │
│   Key: [table_id][index_id][encoded_primary_key] │
│   Value: Row ID                                 │
│                                                 │
│ 二级索引：                                      │
│   Key: [table_id][index_id][encoded_index_key]  │
│   Value: Row ID + 隐藏列（如果需要）             │
│                                                 │
│ 回表：                                          │
│   1. 用二级索引找到 Row ID                      │
│   2. 用 Row ID 到主键索引取数据                   │
└─────────────────────────────────────────────────┘
```

### 覆盖索引优化

```sql
-- 覆盖索引：不需要回表
-- 索引：INDEX(user_id, status, created_at)

-- 好：所有列都在索引中
SELECT user_id, status FROM orders WHERE user_id = 123;

-- 差：需要回表（created_at 不在索引中）
SELECT user_id, status, created_at FROM orders WHERE user_id = 123;

-- TiDB 优化器自动选择：
-- 1. 检查索引是否覆盖所有需要的列
-- 2. 如果覆盖，直接用索引扫描
-- 3. 如果不覆盖，回表取数据
```

---

## 第三部分：全局序列号

### 为什么需要全局序列号？

```
MySQL 自增 ID 的问题：
1. 分库分表后，ID 不全局唯一
2. 主从切换，ID 可能重复
3. 步长不可控

TiDB 解决方案：
1. AUTO_INCREMENT_ID → TSO
2. Row ID → TSO 作为高 42 位
3. 全局唯一，自动递增
```

### TiDB 全局序列号实现

```go
// TiDB 源码：util/autoid/autoid.go
// AutoID 分配

type AutoIDAllocator struct {
    allocator AutoAllocator
    tableID   int64
}

func (a *AutoIDAllocator) NextID() (int64, error) {
    // 1. 获取 TSO
    tso, err := a.allocator.GetTSO()
    if err != nil {
        return 0, err
    }
    
    // 2. 构建全局唯一 ID
    // 高 42 位：TSO 物理时间
    // 中间 22 位：全局自增序列号
    // 低 0 位：无（TiDB 默认不使用）
    id := (tso << 22) | (a.tableID & 0x3FFFF)
    
    return id, nil
}

func (a *AutoIDAllocator) BatchAllocIDs(count int) ([]int64, error) {
    // 批量分配：减少 TSO 调用次数
    tso, err := a.allocator.GetTSO()
    if err != nil {
        return nil, err
    }
    
    var ids []int64
    for i := 0; i < count; i++ {
        id := (tso << 22) | (int64(i) & 0x3FFFF)
        ids = append(ids, id)
    }
    
    return ids, nil
}
```

---

## 第四部分：CockroachDB 架构

### CockroachDB 架构

```
CockroachDB vs TiDB：

CockroachDB:
├── Go 语言实现
├── 基于 Raft 共识（RocksDB 存储）
├── ACID 事务（跨行/跨表）
├── 自动分片（Range 160MB）
├── 自动 rebalance（Leader/Replica）
└── PostgreSQL 协议

TiDB:
├── Go 语言实现
├── 基于 Raft（TiKV 存储）
├── ACID 事务（2PC）
├── 自动分片（Region 96MB）
├── 自动 split/merge
└── MySQL 协议
```

### CockroachDB Range 机制

```
CockroachDB Range 架构：
┌─────────────────────────────────────────────────┐
│  Table: orders                                  │
│                                                 │
│  Range 1: [min, "a")                            │
│  Range 2: ["a", "b")                            │
│  ...                                            │
│  Range N: ["z", max)                            │
│                                                 │
│  每个 Range 有：                                │
│  - Leader：处理读写请求                         │
│  - Replicas：3 副本（默认）                      │
│  - Raft Group：保证一致性                        │
│                                                 │
│  Range 分裂：                                   │
│  - 160MB 自动 Split                             │
│  - 热点 Key 手动 Split                          │
│  - Split 后生成新 Range                          │
└─────────────────────────────────────────────────┘
```

### CockroachDB 分布式事务

```go
// CockroachDB 分布式事务
// 所有事务都是分布式 2PC

func (txn *Txn) Commit() error {
    // 1. 收集事务写的所有 Key
    keys := txn.localCommitSource.Keys()
    
    // 2. 计算所有 Key 的哈希
    var ranges []roachpb.RangeID
    for _, key := range keys {
        rangeID := txn.store.LookupRange(key)
        ranges = append(ranges, rangeID)
    }
    
    // 3. 收集涉及的 Leader
    leaders := make(map[roachpb.RangeID]*grpc.Connection)
    for _, rangeID := range ranges {
        leaders[rangeID] = txn.store.GetLeader(rangeID)
    }
    
    // 4. 两阶段提交
    // Phase 1: PrePrepare（发送 Prepare 到所有 Leader）
    for _, leader := range leaders {
        leader.PrePrepare(txn.Proto)
    }
    
    // 5. 等待所有 Leader 确认
    acks := make(chan bool, len(leaders))
    for _, leader := range leaders {
        go func(l *grpc.Connection) {
            acks <- l.WaitPrepare()
        }(leader)
    }
    
    // 6. 收集确认
    for range len(leaders) {
        if <-acks {
            // 全部确认
        } else {
            // 回滚
            txn.Rollback()
            return errors.New("2PC failed")
        }
    }
    
    // 7. Commit
    for _, leader := range leaders {
        leader.Commit(txn.Proto)
    }
    
    return nil
}
```

---

## 第五部分：自测题

### Q1: TiDB 和 CockroachDB 的区别？

**A**:
| 维度 | TiDB | CockroachDB |
|------|------|-------------|
| **协议** | MySQL | PostgreSQL |
| **分片** | Region 96MB | Range 160MB |
| **事务** | 乐观锁（默认） | 乐观锁（Pebble） |
| **扩展性** | 水平扩展强 | 水平扩展好 |
| **生态** | 国内生态好 | 国际生态好 |
| **适合** | 广告平台（MySQL 生态） | 新系统（PostgreSQL 生态） |

### Q2: 为什么广告平台适合 TiDB？

**A**:
1. MySQL 协议兼容：迁移成本低
2. 自动分片：无需手动分库分表
3. 强一致性：广告计费不能丢数据
4. 高吞吐：广告写入量大
5. 在线扩缩容：无需停机

### Q3: Region Split 影响读写吗？

**A**: 不影响。Split 是异步的，Split 过程中旧 Region 仍然处理读写。Split 完成后，旧 Region 被分成两个新 Region，读写自动路由到新 Region。

---

## 第六部分：生产实践

### 1. 容量规划

```
TiDB 集群规划：
- 10 节点 3x3 部署（3 PD + 6 TiKV + 3 TiDB）
- 每个 TiKV 节点：32 核 / 128GB / 2TB SSD
- 总容量：~6TB（原始数据）
- 实际使用：~3TB（考虑副本和写放大）
```

### 2. 监控指标

```
关键监控指标：
1. TiKV Region 数 → 监控 Split 频率
2. TiDB QPS/P99 延迟 → 监控查询性能
3. PD TSO 延迟 → 监控时间戳分配
4. RocksDB 磁盘使用 → 监控写放大
5. GC Life Time → 监控旧版本清理
```

### 3. 常见问题

```
1. 热点 Key：使用随机前缀打散
2. 慢查询：使用 EXPLAIN，覆盖索引
3. Region 不平衡：手动 Split/Merge
4. GC 慢：调整 gc_life_time
```
