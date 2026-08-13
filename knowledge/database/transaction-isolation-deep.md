# 数据库事务隔离级别深度解析

> 深入理解 MySQL InnoDB 事务隔离机制：读未提交、读已提交、可重复读、串行化。
> 包含 MVCC 实现、锁机制、间隙锁、next-key lock 详解。

---

## 1. 事务隔离级别概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    事务隔离级别矩阵                             │
├──────────────────────┬─────────┬─────────┬─────────┬───────────┤
│                      │  读未提交 │ 读已提交│ 可重复读│  串行化   │
├──────────────────────┼─────────┼─────────┼─────────┼───────────┤
│ 脏读(Dirty Read)      │    ✗    │    ✓    │    ✓    │     ✓     │
│ 不可重复读(NonRepeat) │    ✗    │    ✗    │    ✓    │     ✓     │
│ 幻读(Phantom Read)    │    ✗    │    ✗    │    ✗    │     ✓     │
└──────────────────────┴─────────┴─────────┴─────────┴───────────┘
```

### 1.1 三种并发问题

```
场景1: 脏读 (Dirty Read)
┌─────────────┐         ┌─────────────┐
│  Transaction│         │  Transaction│
│     A       │         │     B       │
├─────────────┤         ├─────────────┤
│ UPDATE SET  │         │             │
│  balance=100│         │             │
│             │────────▶│ SELECT      │
│             │  读取    │  balance    │
│             │  未提交  │  = 100 ❌   │
│ ROLLBACK    │         │             │
└─────────────┘         └─────────────┘
     回滚后余额应为0，但B读到了100
```

---

## 2. InnoDB MVCC 实现原理

### 2.1 隐藏列

```sql
-- InnoDB 为每行记录添加的隐藏列
DB_TRX_ID    - 事务ID (6字节)
DB_ROLL_PTR  - 回滚指针 (7字节)
DB_ROW_ID    - 行ID (6字节，自增)
```

### 2.2 Undo Log 版本链

```
┌─────────────────────────────────────────────────────────────────┐
│                    MVCC 版本链结构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  当前版本: [data] ──┐                                           │
│                      │ rollback_ptr                            │
│                      ▼                                           │
│  历史版本1: [data] ──┐                                           │
│                      │ rollback_ptr                            │
│                      ▼                                           │
│  历史版本2: [data] ──┐                                           │
│                      │ rollback_ptr = NULL                      │
│                      ▼                                           │
│  最早版本:  [data]                                              │
│                                                                 │
│  每个版本关联:                                                   │
│  - DB_TRX_ID: 创建该版本的事务ID                                │
│  - DB_ROLL_PTR: 指向上一个版本                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Read View 机制

```go
// ReadView 读视图
type ReadView struct {
    trxIds      []int64    // 活跃事务ID列表
    minTrxId    int64      // 最小活跃事务ID
    maxTrxId    int64      // 下一个将要分配的事务ID
    creatorTrxId int64     // 创建 ReadView 的事务ID
}

// 可见性判断规则
func (rv *ReadView) IsVisible(trxId int64, rollPtr uintptr) bool {
    if trxId < rv.minTrxId || trxId >= rv.maxTrxId {
        return true
    }
    if trxId == rv.creatorTrxId {
        return true
    }
    for _, id := range rv.trxIds {
        if id == trxId {
            return false
        }
    }
    return true
}
```

---

## 3. 锁机制详解

### 3.1 锁类型

```
┌─────────────────────────────────────────────────────────────────┐
│                     InnoDB 锁体系                               │
├─────────────────────────────────────────────────────────────────┤
│  全局锁                                                          │
│  ├── LOCK TABLES ... WRITE                                     │
│  └── FLUSH TABLES WITH READ LOCK                               │
│                                                                 │
│  表级锁                                                         │
│  ├── MDL (Metadata Lock) - 元数据锁                            │
│  ├── 意向共享锁 (IS)                                             │
│  └── 意向排他锁 (IX)                                             │
│                                                                 │
│  行级锁                                                         │
│  ├── Record Lock - 锁定索引记录                                 │
│  ├── Gap Lock - 间隙锁，锁定范围                                │
│  └── Next-Key Lock - Record + Gap                              │
│                                                                 │
│  行锁模式                                                        │
│  ├── Shared Lock (S锁) - 共享锁/读锁                           │
│  └── Exclusive Lock (X锁) - 排他锁/写锁                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Next-Key Lock 算法

```
// NextKeyLock = record lock + gap lock
// 锁定范围: (prev, current]
// 例如: 索引值 10, 20, 30
// next-key lock on 20 锁定 (10, 20]
```

---

## 4. 生产环境配置

```ini
# my.cnf 推荐配置
[mysqld]
transaction_isolation = REPEATABLE-READ
innodb_deadlock_detect = ON
innodb_lock_wait_timeout = 50
innodb_buffer_pool_size = 8G
innodb_buffer_pool_instances = 8
```

---

## 5. 实践 Checklist

- [ ] 生产环境使用 REPEATABLE-READ 隔离级别
- [ ] 启用死锁检测，设置合理超时
- [ ] 避免大事务，控制事务粒度
- [ ] 使用 EXPLAIN 分析锁竞争
- [ ] 监控 InnoDB 锁等待情况

---

**参考**: MySQL 官方文档、InnoDB 存储引擎源码、Percona 性能调优指南
