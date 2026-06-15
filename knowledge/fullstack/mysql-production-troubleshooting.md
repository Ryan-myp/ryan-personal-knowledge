# MySQL 生产排障实战

> 慢查询优化/锁冲突/主从延迟/连接池耗尽/死锁排查

---

## 第一部分：入门引导（5 分钟速览）

### 广告平台 MySQL 常见问题

| 问题 | 现象 | 根因 |
|------|------|------|
| 慢查询 | RT > 1s | 缺索引/全表扫描 |
| 锁冲突 | 连接等待 | 行锁/表锁竞争 |
| 主从延迟 | 读不到数据 | binlog 积压 |
| 连接池耗尽 | 502 错误 | 连接泄漏 |
| 死锁 | 事务回滚 | 多表更新顺序不一致 |

---

## 第二部分：慢查询排查

### 2.1 慢查询日志分析

```sql
-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.1;  -- 100ms 以上记录
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';

-- 分析慢查询
mysqldumpslow -s t -t 20 /var/log/mysql/slow.log

-- 查看当前慢查询
SHOW PROCESSLIST;

-- 查看最近执行的慢查询
SELECT * FROM sys.statements_with_runtimes_in_95th_percentile
ORDER BY avg_timer_wait DESC LIMIT 10;
```

### 2.2 EXPLAIN 深度解读

```sql
-- 基础 EXPLAIN
EXPLAIN SELECT * FROM ads WHERE campaign_id = 123 AND status = 'active';

-- 关键字段解读
-- type: ALL(全表) < range < ref < eq_ref < const
-- key: 使用的索引
-- rows: 预估扫描行数
-- Extra: Using filesort(需要排序), Using temporary(临时表), Using index(覆盖索引)

-- 优化前
EXPLAIN SELECT * FROM ads WHERE campaign_id = 123;
-- type: ALL, rows: 1000000, Extra: Using where

-- 优化后（添加索引）
ALTER TABLE ads ADD INDEX idx_campaign_status (campaign_id, status);
EXPLAIN SELECT * FROM ads WHERE campaign_id = 123 AND status = 'active';
-- type: ref, key: idx_campaign_status, rows: 1000
```

### 2.3 慢查询优化实战

```sql
-- 问题1: 分页深翻页
-- ❌ 慢查询
SELECT * FROM ads WHERE campaign_id = 123 ORDER BY created_at DESC LIMIT 100000, 10;

-- ✅ 优化：子查询先定位主键
SELECT a.* FROM ads a
INNER JOIN (
    SELECT id FROM ads WHERE campaign_id = 123 ORDER BY created_at DESC LIMIT 100000, 10
) b ON a.id = b.id;

-- 问题2: 函数导致索引失效
-- ❌ 慢查询
SELECT * FROM users WHERE YEAR(create_time) = 2024;

-- ✅ 优化：范围查询
SELECT * FROM users WHERE create_time >= '2024-01-01' AND create_time < '2025-01-01';

-- 问题3: OR 条件导致索引失效
-- ❌ 慢查询
SELECT * FROM ads WHERE campaign_id = 123 OR advertiser_id = 456;

-- ✅ 优化：UNION ALL
SELECT * FROM ads WHERE campaign_id = 123
UNION ALL
SELECT * FROM ads WHERE advertiser_id = 456;
```

---

## 第三部分：锁冲突排查

### 3.1 锁监控

```sql
-- 查看当前锁等待
SELECT * FROM information_schema.innodb_locks;
SELECT * FROM information_schema.innodb_lock_waits;

-- 查看活跃事务
SELECT * FROM information_schema.innodb_trx;

-- 查看最近死锁
SHOW ENGINE INNODB STATUS\G

-- 查看锁等待拓扑
SELECT * FROM performance_schema.data_lock_waits;
```

### 3.2 死锁排查

```sql
-- 死锁日志示例
*** (1) TRANSACTION:
TRANSACTION 12345, ACTIVE 0 sec inserting
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)
*** (2) TRANSACTION:
TRANSACTION 12346, ACTIVE 0 sec inserting
mysql tables in use 1, locked 1
*** DEADLOCK

-- 常见死锁场景
-- 场景1: 多表更新顺序不一致
-- 事务A: UPDATE orders SET status=1 WHERE id=1; UPDATE inventory SET stock=stock-1 WHERE order_id=1;
-- 事务B: UPDATE inventory SET stock=stock-1 WHERE order_id=2; UPDATE orders SET status=1 WHERE id=2;

-- 修复: 统一更新顺序
-- 事务A: UPDATE orders SET status=1 WHERE id=1; UPDATE inventory SET stock=stock-1 WHERE order_id=1;
-- 事务B: UPDATE orders SET status=1 WHERE id=2; UPDATE inventory SET stock=stock-1 WHERE order_id=2;

-- 场景2: 间隙锁导致的死锁
-- 修复: 使用唯一索引，避免间隙锁
```

### 3.3 锁优化策略

```go
package deadlock

import (
    "database/sql"
    "fmt"
)

// 统一更新顺序避免死锁
func UpdateOrderAndInventory(db *sql.DB, orderID, inventoryID int64) error {
    tx, err := db.BeginTx(nil, nil)
    if err != nil {
        return err
    }
    defer tx.Rollback()
    
    // 1. 先更新订单（统一顺序）
    _, err = tx.Exec("UPDATE orders SET status = ? WHERE id = ?", 1, orderID)
    if err != nil {
        return err
    }
    
    // 2. 再更新库存
    _, err = tx.Exec("UPDATE inventory SET stock = stock - 1 WHERE id = ?", inventoryID)
    if err != nil {
        return err
    }
    
    return tx.Commit()
}

// 使用 SELECT FOR UPDATE 控制锁粒度
func DeductBudget(db *sql.DB, campaignID int64, amount float64) error {
    tx, err := db.BeginTx(nil, nil)
    if err != nil {
        return err
    }
    defer tx.Rollback()
    
    // 行级锁，只锁住当前行
    var budget float64
    err = tx.QueryRow("SELECT budget FROM campaigns WHERE id = ? FOR UPDATE", campaignID).Scan(&budget)
    if err != nil {
        return err
    }
    
    if budget < amount {
        return fmt.Errorf("insufficient budget")
    }
    
    _, err = tx.Exec("UPDATE campaigns SET budget = budget - ? WHERE id = ?", amount, campaignID)
    if err != nil {
        return err
    }
    
    return tx.Commit()
}
```

---

## 第四部分：主从延迟排查

### 4.1 延迟监控

```sql
-- 查看主从状态
SHOW SLAVE STATUS\G

-- 关键字段
-- Seconds_Behind_Master: 延迟秒数
-- Relay_Log_Space: 中继日志大小

-- 监控延迟
SELECT TIMESTAMPDIFF(SECOND, MAX(Last_Executed_Event_Time), NOW()) AS slave_delay
FROM performance_schema.replication_applier_status_by_worker;
```

### 4.2 延迟原因与优化

```
延迟原因:
1. 从库 IO 线程慢 → 增加从库 IO 线程数
2. 从库 SQL 线程慢 → 并行复制
3. 大事务 → 拆分大事务
4. 锁竞争 → 优化 SQL

优化方案:
1. 启用并行复制
SET GLOBAL slave_parallel_workers = 8;
SET GLOBAL slave_parallel_type = 'LOGICAL_CLOCK';

2. 优化 binlog
SET GLOBAL binlog_format = 'ROW';
SET GLOBAL binlog_row_image = 'FULL';

3. 读写分离
应用层路由：写 → 主库，读 → 从库
```

---

## 第五部分：连接池耗尽排查

### 5.1 连接池监控

```sql
-- 查看当前连接
SHOW PROCESSLIST;

-- 查看连接统计
SHOW STATUS LIKE 'Threads_connected';
SHOW STATUS LIKE 'Threads_running';

-- 查看连接等待
SELECT * FROM performance_schema.events_waits_current
WHERE EVENT_NAME LIKE 'wait/io/socket/%';
```

### 5.2 连接池优化

```go
package connection

import (
    "database/sql"
    "time"
)

func NewDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("mysql", dsn)
    if err != nil {
        return nil, err
    }
    
    // 连接池配置
    db.SetMaxOpenConns(100)      // 最大连接数
    db.SetMaxIdleConns(20)       // 最大空闲连接
    db.SetConnMaxLifetime(30 * time.Minute)  // 连接最大生命周期
    db.SetConnMaxIdleTime(10 * time.Minute)  // 空闲连接最大时间
    
    // 健康检查
    db.SetPingPeriod(30 * time.Second)
    
    return db, nil
}

// 连接泄漏排查
// 症状: Threads_connected 持续增长
// 原因: 忘记关闭连接/事务未提交
// 解决: 使用 defer db.Close()
```

---

## 第六部分：自测题

### 问题 1
如何定位慢查询？

<details>
<summary>查看答案</summary>

1. 开启慢查询日志
2. 使用 mysqldumpslow 分析
3. EXPLAIN 查看执行计划
4. 关注 type、key、rows、Extra
5. 添加合适索引

</details>

### 问题 2
死锁的根本原因是什么？

<details>
<summary>查看答案</summary>

1. 多表更新顺序不一致
2. 间隙锁导致
3. 事务持有锁时间过长
4. 解决：统一更新顺序，使用唯一索引
5. 监控：SHOW ENGINE INNODB STATUS

</details>

### 问题 3
主从延迟怎么解决？

<details>
<summary>查看答案</summary>

1. 并行复制：slave_parallel_workers = 8
2. 优化 binlog：ROW 格式
3. 拆分大事务
4. 读写分离：写主读从
5. 监控：SHOW SLAVE STATUS

</details>

---

*本文档基于 MySQL 生产排障经验整理。*