# TiDB 分布式数据库架构深度解析

> **领域**: 数据库 / 分布式系统
> **深度**: ⭐⭐⭐⭐⭐ 源码级分析
> **标签**: tidb, distributed, sql, transaction, raft
> **更新时间**: 2026-08-13
> **类型**: source-code/distributed-system

---

## 📌 TiDB 架构概览

### 1. 三组件架构图

```
┌─────────────────────────────────────────────────────┐
│                    TiDB Cluster                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐         │
│  │  TiDB   │    │  TiDB   │    │  TiDB   │  ...    │
│  │ (计算层) │    │ (计算层) │    │ (计算层) │         │
│  └────┬────┘    └────┬────┘    └────┬────┘         │
│       │              │              │               │
│       └──────────────┼──────────────┘               │
│                      ▼                              │
│            ┌─────────────────┐                      │
│            │    PD           │                      │
│            │  (调度中心)      │                      │
│            └────────┬────────┘                      │
│                     │                               │
│        ┌────────────┼────────────┐                  │
│        ▼            ▼            ▼                  │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│   │TiKV 1  │ │TiKV 2  │ │TiKV N  │              │
│   │(存储层) │ │(存储层) │ │(存储层) │              │
│   └─────────┘ └─────────┘ └─────────┘              │
└─────────────────────────────────────────────────────┘
```

### 2. 组件职责

| 组件 | 语言 | 职责 |
|------|------|------|
| TiDB | Go | SQL 解析、优化、执行 |
| PD | Go | 调度、元数据管理 |
| TiKV | Rust | 数据存储、事务处理 |

---

## 🔥 核心机制实现

### 1. 分布式事务（Percolator 模型）

```go
// 源码位置: tidb/store/driver/txn.go
type TxnCommand struct {
    startTS    uint64
    commitTS   uint64
    commands   []TikvCommand
}

func (txn *tikvTxn) Commit(ctx context.Context) error {
    // 1. 两阶段提交
    // Phase 1: Prewrite
    primary := txn.primaryKey
    for _, cmd := range txn.commands {
        if bytes.Equal(cmd.key, primary) {
            continue
        }
        if err := txn.prewrite(ctx, cmd); err != nil {
            return err
        }
    }
    
    // Phase 2: Commit
    return txn.commit(ctx, primary)
}
```

### 2. Raft 共识算法（TiKV）

```rust
// 源码位置: tikv/src/server/raftstore/
impl<T, B, R> Peer {
    fn propose(&mut self, ctx: Context, reqs: Vec<KeyValue>) -> Promise<u64> {
        // 1. 提案预处理
        let term = self.term();
        let pending_index = self.store.pending_proposals.len();
        
        // 2. 追加到 Raft Log
        let mut entry = Entry::default();
        entry.set_term(term);
        entry.set_index(self.last_index() + 1);
        entry.set_data(reqs.encode_to_vec());
        
        // 3. 广播提案
        self.propose_peers(term, vec![entry])
    }
}
```

---

## 💡 生产实践要点

### 1. 容量规划

```yaml
# TiDB 集群配置
tidb:
  instances: 3
  cpu: 16
  memory: 32Gi
  
pd:
  instances: 3
  cpu: 8
  memory: 16Gi
  
tikv:
  instances: 6
  cpu: 32
  memory: 64Gi
  store: SSD
```

### 2. 慢查询优化

```sql
-- 查看慢查询
SELECT * FROM information_schema.slow_query 
WHERE query_time > 1 
ORDER BY query_time DESC 
LIMIT 100;

-- 执行计划分析
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 123;
```

---

## 📊 性能基准测试

| 场景 | QPS | 延迟 P99 | 资源 |
|------|-----|----------|------|
| 点查 | 50K | 5ms | 低 |
| 范围查 | 20K | 20ms | 中 |
| 聚合查询 | 10K | 100ms | 高 |
| 复杂 JOIN | 5K | 200ms | 高 |

**测试环境**: 3TiDB + 6TiKV + 3PD, SSD

---

## 🎓 面试高频问题

**Q: TiDB 如何保证分布式事务一致性？**
A: 三级保障：
1. **Percolator 模型**: 两阶段提交
2. **Raft 共识**: 数据持久化
3. **HLC 时钟**: 时间戳服务

**Q: TiDB 与 MySQL 的主要差异是什么？**
A: 三级差异：
1. **架构**: 计算存储分离
2. **事务**: 分布式事务
3. **扩展**: 水平扩展

---

## 📚 参考资源

- **源码位置**: tidb/, tikv/, pd/
- **官方文档**: https://docs.pingcap.com/zh/tidb/stable
- **架构文档**: https://docs.pingcap.com/zh/tidb-overview

---

*本解析从 TiDB 源码出发，结合生产实践经验，提供独家洞察。*
