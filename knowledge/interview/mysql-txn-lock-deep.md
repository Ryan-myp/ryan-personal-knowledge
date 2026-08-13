# MySQL事务与锁机制 --- 资深专家深度实现

## 概述

MySQL的事务隔离和锁机制是保证数据一致性的核心。本文深入剖析InnoDB事务实现、锁类型和死锁处理。

## 一、事务隔离级别

### 1.1 四个隔离级别

```sql
-- 查看当前隔离级别
SELECT @@transaction_isolation;

-- 设置隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET GLOBAL TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- 四种隔离级别
-- READ UNCOMMITTED: 读未提交 (允许脏读)
-- READ COMMITTED: 读已提交 (防止脏读)
-- REPEATABLE READ: 可重复读 (防止脏读+不可重复读) - InnoDB默认
-- SERIALIZABLE: 串行化 (防止所有并发问题)
```

### 1.2 并发问题类型

```
┌─────────────────────────────────────────────────────────┐
│                  并发问题类型                            │
├──────────────┬──────────┬──────────┬────────────────────┤
│   问题类型   │ RU       │ RC       │ RR / Serializable  │
├──────────────┼──────────┼──────────┼────────────────────┤
│ 脏读         │ ❌      │ ✅      │ ✅                 │
│ 不可重复读   │ ❌      │ ❌      │ ✅                 │
│ 幻读         │ ❌      │ ❌      │ ⚠️*               │
└──────────────┴──────────┴──────────┴────────────────────┘
* RR通过MVCC和Next-Key Lock解决大部分幻读
```

## 二、InnoDB锁机制

### 2.1 锁类型

```sql
-- 行锁
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;  -- 共享锁
SELECT * FROM users WHERE id = 1 FOR UPDATE;           -- 排他锁

-- 表锁
LOCK TABLES users READ;
LOCK TABLES users WRITE;

-- 元数据锁 (MDL)
-- 自动管理，DML操作时获取
```

### 2.2 间隙锁 (Gap Lock)

```sql
-- Next-Key Lock = Record Lock + Gap Lock
-- 锁住记录本身和记录之间的间隙

-- 示例：防止幻读
BEGIN;
SELECT * FROM orders WHERE status = 'pending' FOR UPDATE;
-- 锁住 status='pending' 的记录及其间隙
-- 其他事务不能插入 status='pending' 的记录

COMMIT;
```

### 2.3 死锁检测

```sql
-- 死锁自动检测
-- InnoDB会在等待超时后回滚事务

-- 查看死锁信息
SHOW ENGINE INNODB STATUS;

-- 死锁日志 (MySQL 5.7+)
SET GLOBAL innodb_deadlock_detect = ON;
SELECT * FROM information_schema.innodb_deadlocks;
```

```go
// Go处理死锁重试
func transferWithRetry(from, to int64, amount int64) error {
    maxRetries := 3
    for i := 0; i < maxRetries; i++ {
        err := db.Transaction(func(tx *gorm.DB) error {
            // 固定顺序获取锁，避免死锁
            if from < to {
                tx.Exec("SELECT * FROM accounts WHERE id=? FOR UPDATE", from)
                tx.Exec("SELECT * FROM accounts WHERE id=? FOR UPDATE", to)
            } else {
                tx.Exec("SELECT * FROM accounts WHERE id=? FOR UPDATE", to)
                tx.Exec("SELECT * FROM accounts WHERE id=? FOR UPDATE", from)
            }
            // 执行转账...
            return nil
        })
        if err == nil {
            return nil
        }
        if !isDeadlock(err) {
            return err
        }
    }
    return errors.New("死锁重试失败")
}
```

## 三、MVCC实现

### 3.1 隐藏列

```sql
-- InnoDB每行有两个隐藏列
-- DB_TRX_ID: 最近修改该行的事务ID
-- DB_ROLL_PTR: 回滚指针，指向undo log

-- 查看事务ID
SELECT DB_TRX_ID, DB_ROLL_PTR, * FROM users;
```

### 3.2 Undo Log版本链

```
┌─────────────────────────────────────────────────────────┐
│                    Undo Log版本链                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  记录: id=1, name='ryan', version=3                      │
│                                                          │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐          │
│  │ Version3│────→│ Version2│────→│ Version1│          │
│  │ trx=100 │     │ trx=90  │     │ trx=80  │          │
│  │ name=A  │     │ name=B  │     │ name=C  │          │
│  └─────────┘     └─────────┘     └─────────┘          │
│       ↑                                                  │
│       │ TRX_ID=95                                        │
│    当前事务可见的版本                                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Read View

```go
// Read View结构
type ReadView struct {
    trxIdSet    map[int64]bool  // 活跃事务ID集合
    minTrxId    int64           // 最小活跃事务ID
    maxTrxId    int64           // 最大活跃事务ID (创建时的最大ID+1)
    creatorTrxId int64          // 创建Read View的事务ID
}

// 可见性判断
func (rv *ReadView) isVisible(trxId int64) bool {
    if trxId <= rv.minTrxId {
        return true  // 事务已提交
    }
    if trxId >= rv.maxTrxId {
        return false // 事务未启动
    }
    if rv.trxIdSet[trxId] {
        return false // 活跃事务，未提交
    }
    return true  // 已提交事务
}
```

## 四、锁算法

### 4.1 Record Lock

```sql
-- 记录锁：锁住索引记录
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 只锁住id=1这一条记录
```

### 4.2 Next-Key Lock

```sql
-- 记录锁 + 间隙锁
-- 锁住 (idx, idx] 区间
SELECT * FROM orders WHERE status = 'pending' FOR UPDATE;
-- 锁住 status='pending' 的记录和间隙
```

### 4.3 Hint Lock

```sql
-- 仅锁住记录，不锁间隙
SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE;
-- 使用唯一索引等值查询时，退化为Record Lock
```

## 五、性能优化

### 5.1 避免锁竞争

```sql
-- 短事务原则
BEGIN;
-- 快速查询并更新
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- 避免在事务中进行长操作
-- 不要：事务中调用HTTP请求
-- 不要：事务中处理大量数据
```

### 5.2 索引优化

```sql
-- 确保WHERE条件使用索引
-- 否则可能升级为表锁

-- 查看锁等待
SELECT * FROM information_schema.innodb_locks;
SELECT * FROM information_schema.innodb_lock_waits;
```

### 5.3 批量操作

```sql
-- 批量更新减少锁持有时间
UPDATE orders SET status = 'shipped' 
WHERE id IN (1,2,3,4,5);

-- 避免大事务
-- 分批提交
BEGIN;
UPDATE orders SET status = 'shipped' WHERE id BETWEEN 1 AND 100;
COMMIT;
BEGIN;
UPDATE orders SET status = 'shipped' WHERE id BETWEEN 101 AND 200;
COMMIT;
```

## 六、面试高频题

### 6.1 高频问题

**Q1: MVCC是如何实现可重复读的？**

A: 通过Undo Log版本链和Read View实现：
- 每次事务读取时创建Read View
- 通过版本号链找到可见的版本
- 写入时创建新版本，原版本保留

**Q2: Gap Lock的作用是什么？**

A: 防止幻读：
- 锁住索引记录之间的间隙
- 阻止其他事务在间隙中插入记录
- Next-Key Lock = Record Lock + Gap Lock

**Q3: 如何避免死锁？**

A:
- 固定锁获取顺序
- 缩短事务持续时间
- 使用合适的隔离级别
- 添加重试机制

### 6.2 自测题

1. 画出MVCC版本链示意图
2. 解释Next-Key Lock的工作原理
3. 设计一个防超卖的库存扣减方案
4. 分析以下场景的死锁原因
5. 解释RR和RC隔离级别的区别

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 数据库
**关键词**: mysql, transaction, lock, mvcc, deadlock
