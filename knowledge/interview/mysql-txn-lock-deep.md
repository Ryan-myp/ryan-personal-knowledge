# MySQL事务与锁 - 资深专家深度实现

## 一、ACID实现

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MySQL InnoDB ACID实现                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Atomicity (原子性)       Undo Log                                   │
│   Consistency (一致性)     约束 + 事务                                │
│   Isolation (隔离性)       Lock + MVCC                                │
│   Durability (持久性)      Redo Log                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、锁机制

### 2.1 锁类型

```go
package lock

// 锁粒度
type LockLevel int

const (
    TableLock LockLevel = iota
    RowLock
    GapLock    // 间隙锁
    NextKeyLock // 临键锁
)

// 锁模式
type LockMode int

const (
    ShareLock LockMode = iota  // S锁
    ExclusiveLock              // X锁
)

// InnoDB行锁
type RecordLock struct {
    lockType  LockLevel
    lockMode  LockMode
    recOffset int
    trxID     uint64
}

type GapLock struct {
    lowBound  int
    highBound int
    trxID     uint64
}
```

### 2.2 锁等待

```go
func (t *Transaction) lockRecord(rec *Record, mode LockMode, timeout time.Duration) error {
    lock := &RecordLock{
        lockType: RowLock,
        lockMode: mode,
        recOffset: rec.offset,
        trxID: t.id,
    }
    
    // 尝试加锁
    if t.tryLock(lock) {
        return nil
    }
    
    // 加入等待队列
    waitQueue := t.getWaitQueue(rec)
    waiter := &Waiter{Lock: lock, TrxID: t.id}
    waitQueue.push(waiter)
    
    // 等待锁释放
    select {
    case <-waiter.signal:
        return nil
    case <-time.After(timeout):
        return ErrLockWaitTimeout
    }
}
```

## 三、MVCC实现

```go
package mvcc

import (
    "sync"
)

// MVCC版本控制
type MVCC struct {
    versions map[string][]Version
    mu       sync.RWMutex
}

type Version struct {
    data      []byte
    trxID     uint64
    rollBack  uint64
    next      *Version
}

// Read View
type ReadView struct {
    trxIDs      []uint64
    minTrxID    uint64
    maxTrxID    uint64
    creatorTrxID uint64
}

func (mvcc *MVCC) Get(key string, view *ReadView) ([]byte, error) {
    mvcc.mu.RLock()
    defer mvcc.mu.RUnlock()
    
    versions := mvcc.versions[key]
    for v := versions; v != nil; v = v.next {
        if mvcc.isVisible(v, view) {
            return v.data, nil
        }
    }
    return nil, ErrNotFound
}

func (mvcc *MVCC) isVisible(version *Version, view *ReadView) bool {
    // 事务未启动
    if version.trxID < view.minTrxID {
        return true
    }
    // 事务已提交
    if version.trxID >= view.maxTrxID {
        return false
    }
    // 事务在视图中
    for _, id := range view.trxIDs {
        if id == version.trxID {
            return version.trxID == view.creatorTrxID
        }
    }
    return false
}
```

## 四、事务隔离级别

```sql
-- 隔离级别对比
-- READ UNCOMMITTED: 最低隔离，可能脏读
-- READ COMMITTED:   防止脏读，可能不可重复读
-- REPEATABLE READ:  防止不可重复读，可能幻读 (InnoDB默认)
-- SERIALIZABLE:     最高隔离，串行执行

-- InnoDB的REPEATABLE READ实现
-- • 快照读: 使用MVCC
-- • 当前读: 使用锁

BEGIN;
SELECT * FROM users WHERE id = 1;  -- 快照读，MVCC
SELECT * FROM users WHERE id = 1 FOR UPDATE;  -- 当前读，加锁
COMMIT;
```

## 五、面试高频题

### Q1: 什么是幻读？InnoDB如何避免？

```
A:
• 幻读: 同一事务内多次查询结果不同
• InnoDB通过Next-Key Lock解决
• Gap Lock + Record Lock
```

### Q2: 如何实现读写分离？

```
A:
1. 主库写，从库读
2. 延迟监控
3. 故障切换
```

## 六、自测题

1. 解释Undo Log的作用
2. 什么是当前读和快照读？
3. 如何实现乐观锁？

---

## 参考文档

- [InnoDB源码](https://github.com/mysql/mysql-server)
- [MySQL官方文档](https://dev.mysql.com/doc/)
