# MySQL事务与锁 - 资深专家深度实现

## 一、事务隔离级别

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     事务隔离级别                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Isolation Level      | Dirty Read | Non-Repeatable | Phantom          │
│   ---------------------|------------|----------------|------------------│
│   READ UNCOMMITTED     |     Y      |       Y        |       Y          │
│   READ COMMITTED       |     N      |       Y        |       Y          │
│   REPEATABLE READ      |     N      |       N        |       Y          │
│   SERIALIZABLE         |     N      |       N        |       N          │
│                                                                         │
│   MySQL默认: REPEATABLE READ                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、锁机制

```sql
-- 表锁
LOCK TABLES orders WRITE;
UNLOCK TABLES;

-- 行锁
START TRANSACTION;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
UPDATE orders SET status = 'paid' WHERE id = 1;
COMMIT;

-- 间隙锁
SELECT * FROM orders WHERE status = 'pending' FOR UPDATE;
-- 锁住(status='pending')的间隙
```

## 三、MVCC实现

```c
// InnoDB MVCC实现
struct trx {
    uint64_t trx_id;
    int64_t  roll_ptr;
    trx_state_t state;
};

struct undo_log {
    byte   type_hint;
    byte   info_bits;
    ut_ad  undo_log_no;
    // 事务回滚指针
};
```

## 四、面试高频题

### Q1: 什么是幻读？

```
A:
• 同一事务内，多次查询返回不同结果集
• 通过间隙锁解决
```

### Q2: 死锁如何产生？

```
A:
1. 事务A持有锁1，等待锁2
2. 事务B持有锁2，等待锁1
3. 形成循环等待
```

## 五、自测题

1. 解释MVCC原理
2. 如何实现乐观锁？
3. 如何优化锁性能？

---

## 参考文档

- [MySQL InnoDB源码](https://github.com/mysql/mysql-server)
- [ACID特性](https://en.wikipedia.org/wiki/ACID)
