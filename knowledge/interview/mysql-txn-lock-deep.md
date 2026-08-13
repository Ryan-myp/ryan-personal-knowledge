# MySQL事务与锁 - 资深专家深度实现

## 一、事务隔离级别

```sql
-- 四种隔离级别
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;  -- 读未提交
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;    -- 读已提交
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;   -- 可重复读 (MySQL默认)
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;      -- 串行化
```

```
┌─────────────┬──────────┬──────────┬──────────┬──────────┐
│  隔离级别    │ 脏读     │ 不可重复读│ 幻读     │ 串行化   │
├─────────────┼──────────┼──────────┼──────────┼──────────┤
│ READ UNCOMMITTED│ ✗     │   ✗      │   ✗     │   ✓     │
│ READ COMMITTED │ ✓      │   ✗      │   ✗     │   ✓     │
│ REPEATABLE READ│ ✓      │   ✓      │   ✗*    │   ✓     │
│ SERIALIZABLE   │ ✓      │   ✓      │   ✓     │   ✓     │
└─────────────┴──────────┴──────────┴──────────┴──────────┘
* InnoDB通过MVCC和Next-Key Lock解决幻读
```

## 二、锁机制

```go
package lock

type LockType int

const (
    RecordLock LockType = iota  // 记录锁
    GapLock                     // 间隙锁
    NextKeyLock                 // 临键锁 (记录锁 + 间隙锁)
)

// InnoDB锁等待处理
type LockWait struct {
    Thd *Thd
    Table *Table
    Index *Index
    Rec *Record
    Mode LockMode
}

func (l *LockWait) TryLock() bool {
    // 尝试获取锁
    if l.Table.Lock.TryLock(l.Mode) {
        return true
    }
    
    // 加入等待队列
    l.Thd.SetState(ThdWaiting)
    l.Table.Lock.AddWaiter(l)
    
    // 等待锁释放
    for !l.Table.Lock.IsLocked(l.Mode) {
        // 超时检查
        if l.Thd.IsTimeout() {
            return false
        }
        // 死锁检测
        if l.Table.Lock.HasDeadlock() {
            return false
        }
    }
    
    return true
}
```

## 三、MVCC实现

```c
// 事务版本链结构
typedef struct version_node {
    void *prev;                   /* 前一个版本 */
    void *data;                   /* 数据记录 */
    roll_ptr_t roll_ptr;          /* 回滚指针 */
    db_horowitz_id_t db_trx_id;   /* 事务ID */
} version_node_t;

// 当前读 vs 快照读
// 当前读: SELECT ... FOR UPDATE / LOCK IN SHARE MODE
// 快照读: SELECT ... (普通查询)
```

## 四、面试高频题

### Q1: MySQL事务隔离级别如何选择？

```
A:
• 开发环境: REPEATABLE READ
• 高性能: READ COMMITTED
• 金融: SERIALIZABLE
```

### Q2: 如何解决死锁？

```
A:
1. 统一访问顺序
2. 设置锁超时
3. 合理设计索引
4. 减少事务粒度
```

## 五、自测题

1. 解释MVCC原理
2. 如何实现间隙锁？
3. 如何优化锁性能？

---

## 参考文档

- [MySQL官方文档](https://dev.mysql.com/doc/)
- [InnoDB源码](https://github.com/mysql/mysql-server)
