# MySQL 事务与锁深度解析

> 深入 MySQL 事务机制：ACID、MVCC、锁类型、死锁处理。
> 源码级分析 InnoDB 引擎，包含生产环境调优。
> 适用对象：DBA、后端工程师、性能优化工程师

---

## 1. 事务基础

### 1.1 ACID 特性

```
┌─────────────────────────────────────────────────────────────┐
│                    ACID 特性                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  A - Atomicity（原子性）                                     │
│  ─────────────────────────                                  │
│  事务中的所有操作要么全部成功，要么全部失败回滚               │
│  实现：Undo Log                                              │
│                                                             │
│  C - Consistency（一致性）                                   │
│  ─────────────────────────                                  │
│  事务执行前后，数据保持一致性约束                             │
│  实现：约束 + 事务隔离                                       │
│                                                             │
│  I - Isolation（隔离性）                                     │
│  ─────────────────────────                                  │
│  多个事务并发执行时，互不干扰                                 │
│  实现：锁 + MVCC                                             │
│                                                             │
│  D - Durability（持久性）                                    │
│  ─────────────────────────                                  │
│  事务提交后，数据永久保存                                     │
│  实现：Redo Log                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 事务隔离级别

```sql
-- 隔离级别对比

-- 1. 读未提交 (READ UNCOMMITTED)
SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
-- 问题：脏读

-- 2. 读已提交 (READ COMMITTED)
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
-- 问题：不可重复读

-- 3. 可重复读 (REPEATABLE READ) - MySQL 默认
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
-- 解决问题：不可重复读
-- 可能问题：幻读

-- 4. 串行化 (SERIALIZABLE)
SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- 解决问题：所有问题
-- 代价：性能下降
```

---

## 2. MVCC 实现

### 2.1 核心数据结构

```c
// ha_innobase.h (简化)

struct row_upd_t {
    undo_log_t    *undo_log;    // undo日志
    dtuple_t      *old_vals;    // 旧值
    dtuple_t      *new_vals;    // 新值
};

struct trx_t {
    ut_list_node  list;         // 事务列表
    trx_id_t      id;           // 事务ID
    trx_state_t   state;        // 状态
    mach_addr_t   wait_for;     // 等待的锁
    ulint         n_modifications; // 修改行数
    ulint         isolation_level; // 隔离级别
};

struct rec_t {
    ulint         next;         // 下一个记录
    ulint         prev;         // 上一个记录
    dtuple_t      *delete_mask; // 删除标记
    dtuple_t      *values;      // 数据值
    trx_id_t      trx_id;       // 创建事务ID
    roll_ptr_t    roll_ptr;     // 回滚指针
};
```

### 2.2 Hidden Columns

```sql
-- InnoDB 隐藏列

-- DB_TRX_ID: 创建或修改该行的事务ID (6字节)
-- DB_ROLL_PTR: 指向undo log的回滚指针 (7字节)
-- DB_ROW_ID: 隐藏的主键 (6字节)

-- 查看表结构
SHOW CREATE TABLE your_table;

-- InnoDB 内部结构
SELECT 
    TRX_ID,
    Roll_Ptr,
    ROW_ID
FROM your_table;
```

### 2.3 Read View

```go
// read_view.go

package transaction

import (
    "sync"
    "time"
)

type ReadView struct {
    lowLimitId    trxID      // 最小活跃事务ID
    upLimitId     trxID      // 最大活跃事务ID+1
    creator       trxID      // 创建者事务ID
    traders       []trxID    // 活跃事务列表
    createTime    time.Time  // 创建时间
}

func (rv *ReadView) IsVisible(trxID trxID) bool {
    // 可见性判断
    if trxID < rv.lowLimitId {
        return true  // 已提交
    }
    if trxID >= rv.upLimitId {
        return false // 未创建
    }
    
    // 在活跃列表中
    for _, id := range rv.traders {
        if id == trxID {
            return false
        }
    }
    return true
}
```

---

## 3. 锁机制

### 3.1 锁类型

```
┌─────────────────────────────────────────────────────────────┐
│                    MySQL 锁类型                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  全局锁                                                      │
│  ├── LOCK TABLES ... WRITE                                  │
│  └── 用途：全库备份                                         │
│                                                             │
│  表级锁                                                      │
│  ├── TABLE LOCK                                             │
│  ├── READ LOCK (共享锁)                                      │
│  └── WRITE LOCK (排他锁)                                     │
│                                                             │
│  行级锁                                                      │
│  ├── Record Lock (记录锁)                                   │
│  ├── Gap Lock (间隙锁)                                      │
│  └── Next-Key Lock (临键锁) = Record + Gap                  │
│                                                             │
│  意向锁                                                      │
│  ├── INTENTION READ LOCK (IS)                               │
│  └── INTENTION WRITE LOCK (IW)                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 锁等待处理

```go
// lock_wait.go

package transaction

import (
    "context"
    "time"
)

type LockWaitConfig struct {
    timeout      time.Duration
    retryCount   int
    retryDelay   time.Duration
}

func (c *LockWaitConfig) WaitForLock(ctx context.Context, lockID string) error {
    for i := 0; i < c.retryCount; i++ {
        select {
        case <-ctx.Done():
            return ctx.Err()
        default:
        }
        
        if c.tryAcquireLock(lockID) {
            return nil
        }
        
        time.Sleep(c.retryDelay)
    }
    
    return ErrLockTimeout
}

func (c *LockWaitConfig) tryAcquireLock(lockID string) bool {
    // 尝试获取锁
    return true
}
```

---

## 4. 死锁处理

### 4.1 死锁检测

```go
// deadlock_detector.go

package transaction

import (
    "sync"
)

type DeadlockDetector struct {
    waitForGraph *WaitForGraph
    mu           sync.Mutex
}

type WaitForGraph struct {
    nodes map[string]*WaitNode
}

type WaitNode struct {
    txID      string
    waitingFor string
}

func (d *DeadlockDetector) Detect() ([]string, error) {
    d.mu.Lock()
    defer d.mu.Unlock()
    
    // 使用 DFS 检测环
    visited := make(map[string]bool)
    cycle := make([]string, 0)
    
    for nodeID := range d.waitForGraph.nodes {
        if !visited[nodeID] {
            if path := d.dfs(nodeID, visited, make([]string, 0)); len(path) > 0 {
                cycle = append(cycle, path...)
            }
        }
    }
    
    return cycle, nil
}

func (d *DeadlockDetector) dfs(nodeID string, visited map[string]bool, path []string) []string {
    if visited[nodeID] {
        return path
    }
    
    visited[nodeID] = true
    path = append(path, nodeID)
    
    node := d.waitForGraph.nodes[nodeID]
    if next, ok := d.waitForGraph.nodes[node.waitingFor]; ok {
        return d.dfs(next.txID, visited, path)
    }
    
    return nil
}
```

### 4.2 死锁预防

```sql
-- 死锁预防策略

-- 1. 统一访问顺序
-- 所有事务按相同顺序访问表

-- 2. 缩短事务长度
BEGIN;
-- 快速操作
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- 3. 使用低隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 4. 添加索引
-- 减少锁范围
CREATE INDEX idx_account_id ON accounts(id);

-- 5. 合理设置 innodb_lock_wait_timeout
SET innodb_lock_wait_timeout = 50;
```

---

## 5. 性能调优

### 5.1 事务参数

```ini
# my.cnf

# 事务相关
innodb_support_xa = ON
innodb_autoinc_lock_mode = 2
innodb_locks_unsafe_for_binlog = OFF

# 锁等待
innodb_lock_wait_timeout = 50
wait_timeout = 28800
interactive_timeout = 28800

# 死锁检测
innodb_deadlock_detect = ON
innodb_print_all_deadlocks = ON

# Undo Log
innodb_undo_tablespaces = 3
innodb_undo_log_truncate = ON
max_undo_logs = 128
```

### 5.2 监控 SQL

```sql
-- 查看当前事务
SELECT 
    t.trx_id,
    t.trx_state,
    t.trx_started,
    t.trx_wait_started,
    t.trx_weight,
    t.trx_mysql_thread_id,
    t.trx_query
FROM information_schema.innodb_trx t;

-- 查看锁等待
SELECT 
    r.trx_id waiting_trx_id,
    r.trx_mysql_thread_id waiting_thread,
    r.trx_query waiting_query,
    b.trx_id blocking_trx_id,
    b.trx_mysql_thread_id blocking_thread,
    b.trx_query blocking_query
FROM information_schema.innodb_lock_waits w
JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id;

-- 查看死锁
SHOW ENGINE INNODB STATUS;
```

---

## 6. 实战案例

### 6.1 高并发UPDATE

```go
// high_concurrency_update.go

package transaction

import (
    "database/sql"
    "sync"
)

type ConcurrentUpdater struct {
    db *sql.DB
    mu sync.Mutex
}

func (u *ConcurrentUpdater) Update(id int, amount int) error {
    // 使用行锁
    tx, err := u.db.BeginTx(nil, &sql.TxOptions{
        Isolation: sql.LevelRepeatableRead,
    })
    if err != nil {
        return err
    }
    
    defer tx.Rollback()
    
    // 悲观锁
    var balance int
    err = tx.QueryRow("SELECT balance FROM accounts WHERE id = ? FOR UPDATE", id).Scan(&balance)
    if err != nil {
        return err
    }
    
    newBalance := balance - amount
    _, err = tx.Exec("UPDATE accounts SET balance = ? WHERE id = ?", newBalance, id)
    if err != nil {
        return err
    }
    
    return tx.Commit()
}

// 乐观锁方案
func (u *ConcurrentUpdater) UpdateOptimistic(id, amount, version int) error {
    tx, err := u.db.BeginTx(nil, nil)
    if err != nil {
        return err
    }
    
    defer tx.Rollback()
    
    var currentVersion int
    err = tx.QueryRow("SELECT version FROM accounts WHERE id = ?", id).Scan(&currentVersion)
    if err != nil {
        return err
    }
    
    if currentVersion != version {
        return ErrVersionMismatch
    }
    
    _, err = tx.Exec("UPDATE accounts SET balance = balance - ?, version = version + 1 WHERE id = ? AND version = ?", amount, id, version)
    if err != nil {
        return err
    }
    
    return tx.Commit()
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 事务 | Undo Log + Redo Log |
| 隔离 | MVCC + 锁 |
| 锁 | Record/Gap/Next-Key |
| 死锁 | 等待图检测 |

### 7.2 最佳实践

- [ ] 选择合适的隔离级别
- [ ] 添加合适索引
- [ ] 缩短事务长度
- [ ] 统一访问顺序
- [ ] 监控锁等待

---

*最后更新：2026-08-11*
*作者：Ryan*
