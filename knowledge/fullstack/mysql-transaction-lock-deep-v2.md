# MySQL 事务与锁深度解析

> 深入 MySQL 事务：ACID、隔离级别、锁机制、MVCC。
> 源码级分析，包含生产环境锁优化。
> 适用对象：DBA、后端工程师、架构师

---

## 1. 事务 ACID 特性

### 1.1 事务特性

```
ACID 特性：

├── Atomicity (原子性)
│   └── 事务要么全部完成，要么全部回滚
│
├── Consistency (一致性)
│   └── 事务前后数据保持一致性
│
├── Isolation (隔离性)
│   └── 并发事务互不干扰
│
└── Durability (持久性)
    └── 事务提交后数据永久保存
```

### 1.2 Go 实现事务管理

```go
// transaction.go

package mysql

import (
    "database/sql"
    "fmt"
)

type Transaction struct {
    tx *sql.Tx
}

func (t *Transaction) Begin(db *sql.DB) error {
    tx, err := db.Begin()
    if err != nil {
        return err
    }
    t.tx = tx
    return nil
}

func (t *Transaction) Commit() error {
    if t.tx == nil {
        return fmt.Errorf("transaction not started")
    }
    return t.tx.Commit()
}

func (t *Transaction) Rollback() error {
    if t.tx == nil {
        return fmt.Errorf("transaction not started")
    }
    return t.tx.Rollback()
}

func (t *Transaction) Exec(query string, args ...interface{}) error {
    _, err := t.tx.Exec(query, args...)
    return err
}
```

---

## 2. 隔离级别

### 2.1 隔离级别对比

```
┌──────────────────┬─────────────┬─────────────┬─────────────┐
│ 隔离级别          │ 脏读        │ 不可重复读  │ 幻读        │
├──────────────────┼─────────────┼─────────────┼─────────────┤
│ READ UNCOMMITTED │ 可能        │ 可能        │ 可能        │
│ READ COMMITTED   │ 不可能      │ 可能        │ 可能        │
│ REPEATABLE READ  │ 不可能      │ 不可能      │ 可能        │
│ SERIALIZABLE     │ 不可能      │ 不可能      │ 不可能      │
└──────────────────┴─────────────┴─────────────┴─────────────┘
```

### 2.2 MySQL 默认隔离级别

```
MySQL 默认隔离级别：REPEATABLE READ

实现机制：
├── MVCC (多版本并发控制)
│   ├── Read View (读视图)
│   ├── Undo Log (回滚日志)
│   └── Record Lock (记录锁)
│
└── Next-Key Lock (Next-Key 锁)
    └── 防止幻读
```

---

## 3. 锁机制

### 3.1 锁类型

```
MySQL 锁类型：

1. 全局锁
   ├── FLUSH TABLES WITH READ LOCK
   └── 全库备份时使用

2. 表级锁
   ├── 表锁 (Table Lock)
   ├── 元数据锁 (MDL)
   └── 表元数据锁 (Metadata Lock)

3. 行级锁
   ├── 记录锁 (Record Lock)
   ├── 间隙锁 (Gap Lock)
   └── 临键锁 (Next-Key Lock)
```

### 3.2 Go 实现锁管理

```go
// lock_manager.go

package mysql

import (
    "sync"
    "time"
)

type LockType int

const (
    SharedLock LockType = iota
    ExclusiveLock
)

type RowLock struct {
    Table    string
    RowID    int64
    LockType LockType
    Owner    string
    Expires  time.Time
}

type LockManager struct {
    locks map[string]*RowLock
    mu    sync.RWMutex
}

func NewLockManager() *LockManager {
    return &LockManager{
        locks: make(map[string]*RowLock),
    }
}

func (lm *LockManager) Acquire(table string, rowID int64, owner string, timeout time.Duration) (*RowLock, error) {
    key := fmt.Sprintf("%s:%d", table, rowID)
    lm.mu.Lock()
    defer lm.mu.Unlock()
    
    if lock, ok := lm.locks[key]; ok {
        if lock.Owner == owner {
            return lock, nil
        }
        return nil, fmt.Errorf("lock held by %s", lock.Owner)
    }
    
    lock := &RowLock{
        Table:   table,
        RowID:   rowID,
        Expires: time.Now().Add(timeout),
        Owner:   owner,
    }
    lm.locks[key] = lock
    return lock, nil
}

func (lm *LockManager) Release(table string, rowID int64, owner string) {
    key := fmt.Sprintf("%s:%d", table, rowID)
    lm.mu.Lock()
    defer lm.mu.Unlock()
    
    if lock, ok := lm.locks[key]; ok && lock.Owner == owner {
        delete(lm.locks, key)
    }
}
```

---

## 4. MVCC 实现

### 4.1 核心机制

```
MVCC (多版本并发控制)：

1. 隐藏列
   ├── DB_TRX_ID (事务ID)
   ├── DB_ROLL_PTR (回滚指针)
   └── DB_ROW_ID (隐藏主键)

2. Undo Log
   └── 保存历史版本

3. Read View
   └── 决定可见性
```

### 4.2 Go 实现 MVCC

```go
// mvcc.go

package mysql

import (
    "sync"
)

type Version struct {
    Data      interface{}
    TrxID     int64
    RollPtr   int64
}

type MVCCManager struct {
    versions map[string][]*Version
    mu       sync.RWMutex
}

func NewMVCCManager() *MVCCManager {
    return &MVCCManager{
        versions: make(map[string][]*Version),
    }
}

func (m *MVCCManager) SetValue(key string, data interface{}, trxID int64) {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    m.versions[key] = append(m.versions[key], &Version{
        Data:  data,
        TrxID: trxID,
    })
}

func (m *MVCCManager) GetValue(key string, trxID int64) interface{} {
    m.mu.RLock()
    defer m.mu.RUnlock()
    
    versions := m.versions[key]
    for i := len(versions) - 1; i >= 0; i-- {
        if versions[i].TrxID <= trxID {
            return versions[i].Data
        }
    }
    return nil
}
```

---

## 5. 锁优化

### 5.1 死锁检测

```
死锁检测机制：

1. 等待图 (Wait-for Graph)
   └── 检测循环等待

2. 超时回滚
   └── innodb_lock_wait_timeout

3. 死锁检测
   └── innodb_deadlock_detect
```

### 5.2 Go 实现死锁检测

```go
// deadlock_detector.go

package mysql

import (
    "sync"
)

type WaitGraph struct {
    edges map[string][]string
    mu    sync.RWMutex
}

func NewWaitGraph() *WaitGraph {
    return &WaitGraph{
        edges: make(map[string][]string),
    }
}

func (wg *WaitGraph) AddEdge(from, to string) {
    wg.mu.Lock()
    defer wg.mu.Unlock()
    wg.edges[from] = append(wg.edges[from], to)
}

func (wg *WaitGraph) HasCycle() bool {
    wg.mu.RLock()
    defer wg.mu.RUnlock()
    
    visited := make(map[string]bool)
    recStack := make(map[string]bool)
    
    for node := range wg.edges {
        if wg.hasCycleUtil(node, visited, recStack) {
            return true
        }
    }
    return false
}

func (wg *WaitGraph) hasCycleUtil(node string, visited, recStack map[string]bool) bool {
    visited[node] = true
    recStack[node] = true
    
    for neighbor := range wg.edges[node] {
        if !visited[neighbor] {
            if wg.hasCycleUtil(neighbor, visited, recStack) {
                return true
            }
        } else if recStack[neighbor] {
            return true
        }
    }
    
    recStack[node] = false
    return false
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 概念 | 说明 |
|------|------|
| ACID | 事务四个特性 |
| 隔离级别 | READ COMMITTED/REPEATABLE READ/SERIALIZABLE |
| 锁类型 | 全局锁/表锁/行锁 |
| MVCC | 多版本并发控制 |

### 6.2 最佳实践

- [ ] 选择合适的隔离级别
- [ ] 使用行锁代替表锁
- [ ] 避免死锁
- [ ] 合理设置超时
- [ ] 监控锁等待

---

*最后更新：2026-08-11*
*作者：Ryan*
