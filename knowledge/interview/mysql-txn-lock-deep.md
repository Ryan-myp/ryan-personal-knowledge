# MySQL事务与锁 - 资深专家深度实现

## 一、事务隔离级别

### 1.1 四种隔离级别

```
┌──────────────┬──────────┬──────────┬──────────┬──────────┐
│              │ 读已提交  │ 可重复读  │ 串行化   │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┤
│ 脏读         │ ✗        │ ✗        │ ✗        │          │
│ 不可重复读   │ ✗        │ ✗        │ ✗        │          │
│ 幻影读       │ ✓        │ ✗        │ ✗        │          │
└──────────────┴──────────┴──────────┴──────────┴──────────┘
```

### 1.2 InnoDB实现机制

```go
// 事务隔离级别配置
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;  // 默认

// 查看当前隔离级别
SELECT @@transaction_isolation;
```

## 二、锁机制详解

### 2.1 锁类型

```
锁层级:
├── 全局锁 (FLUSH TABLES WITH READ LOCK)
├── 表级锁
│   ├── 表锁 (LOCK TABLES)
│   ├── MDL锁 (元数据锁)
│   └── 自增锁 (AUTO_INC)
└── 行级锁
    ├── 记录锁 (Record Lock)
    ├── 间隙锁 (Gap Lock)
    └── 临键锁 (Next-Key Lock)
```

### 2.2 记录锁

```sql
-- 示例: 记录锁作用范围
SELECT * FROM orders WHERE id = 100 FOR UPDATE;
-- 只锁定 id=100 这一行

-- 演示: 事务A持有记录锁
START TRANSACTION;
SELECT * FROM orders WHERE id = 100 FOR UPDATE;
-- 此时其他事务无法修改 id=100

-- 事务B尝试修改 (会被阻塞)
UPDATE orders SET status = 'paid' WHERE id = 100;
```

### 2.3 间隙锁

```sql
-- 间隙锁防止幻影读
-- 索引范围: (100, 200)
SELECT * FROM orders WHERE id > 100 AND id < 200 FOR UPDATE;
-- 锁定范围: (100, 200)
-- 其他事务无法在此范围插入新记录

-- 演示间隙锁
-- 表数据: id=100, id=200, id=300
START TRANSACTION;
SELECT * FROM orders WHERE id BETWEEN 100 AND 300 FOR UPDATE;
-- 锁定间隙: (100, 200), (200, 300)

-- 事务B尝试插入 (被阻塞)
INSERT INTO orders (id, status) VALUES (150, 'new');
```

### 2.4 Next-Key Lock

```
Next-Key Lock = 记录锁 + 间隙锁

索引值: 100, 200, 300, 400

查询: SELECT * FROM t WHERE id = 200 FOR UPDATE;

锁定范围:
┌────┬────┬────┬────┬────┐
│ <100│ 100│(100,200)│ 200 │(200,300)│ 300 │...
└────┴────┴───────┴─────┴───────┴─────┴────┘
     ↑ Gap Lock    ↑ Record Lock    ↑ Gap Lock
```

## 三、死锁检测与处理

### 3.1 死锁产生条件

```
产生死锁的四个必要条件:
1. 互斥条件: 资源不能共享
2. 占有且等待: 持有资源并等待其他资源
3. 不可抢占: 资源不能被强制剥夺
4. 循环等待: 存在循环等待链
```

### 3.2 Go实现死锁检测

```go
package deadlock

import (
	"context"
	"fmt"
	"time"
)

// Transaction 事务
type Transaction struct {
	ID         int
	Resources  []string
	WaitFor    map[string]int // resource -> txID
	Timeout    time.Duration
}

// DeadlockDetector 死锁检测器
type DeadlockDetector struct {
	waitForGraph map[int]map[string]int
}

// Detect 检测死锁
func (d *DeadlockDetector) Detect(tx *Transaction) error {
	visited := make(map[int]bool)
	return d.dfs(tx.ID, visited)
}

func (d *DeadlockDetector) dfs(txID int, visited map[int]bool) error {
	if visited[txID] {
		return fmt.Errorf("deadlock detected: cycle involving tx %d", txID)
	}
	visited[txID] = true

	for _, waitTxID := range d.waitForGraph[txID] {
		if err := d.dfs(waitTxID, visited); err != nil {
			return err
		}
	}
	return nil
}
```

### 3.3 MySQL死锁日志分析

```sql
-- 查看死锁信息
SHOW ENGINE INNODB STATUS\G

-- 死锁日志关键信息:
------------------------
LATEST DETECTED DEADLOCK
------------------------
*** (1) TRANSACTION:
TRANSACTION 12345, ACTIVE 0 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)

*** (1) HOLDS THE LOCK(S):
 RECORD LOCKS space id 1234 page no 5 n bits 72

*** (2) TRANSACTION:
TRANSACTION 12346, ACTIVE 0 sec starting index read
2 lock struct(s), heap size 1136, 1 row lock(s)

*** (2) HOLDS THE LOCK(S):
 RECORD LOCKS space id 1234 page no 5 n bits 72

*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
 RECORD LOCKS space id 1234 page no 5 n bits 72
```

## 四、锁优化策略

### 4.1 减少锁持有时间

```go
// ❌ 错误: 事务内执行耗时操作
func BadExample() {
	tx, _ := db.Begin()
	// 1. 查询
	row := tx.QueryRow("SELECT * FROM orders WHERE id = ?", id)
	// 2. 处理业务逻辑 (耗时)
	processOrder(row)
	// 3. 更新
	tx.Exec("UPDATE orders SET status = ?", status)
	tx.Commit()
}

// ✅ 正确: 缩短事务范围
func GoodExample() {
	// 1. 查询 (不在事务中)
	var order Order
	db.QueryRow("SELECT * FROM orders WHERE id = ?", id).Scan(&order)
	
	// 2. 处理业务逻辑
	processOrder(order)
	
	// 3. 短事务更新
	tx, _ := db.Begin()
	tx.Exec("UPDATE orders SET status = ?", order.Status)
	tx.Commit()
}
```

### 4.2 统一锁顺序

```go
// 避免死锁: 始终按相同顺序加锁
func TransferMoney(from, to int, amount float64) error {
	// 统一先锁小ID，再锁大ID
	first, second := from, to
	if first > second {
		first, second = second, first
	}
	
	tx1, _ := db.Begin()
	tx1.Exec("UPDATE accounts SET balance = balance - ? WHERE id = ?", amount, first)
	
	tx2, _ := db.Begin()
	tx2.Exec("UPDATE accounts SET balance = balance + ? WHERE id = ?", amount, second)
	
	tx1.Commit()
	tx2.Commit()
	return nil
}
```

## 五、面试高频题

### Q1: 什么是MVCC？

```
A: MVCC (多版本并发控制) 通过undo log实现:
1. Read View: 事务开始时生成
2. Version Chain: 每行记录有多个历史版本
3. 可见性判断: 根据Read View判断版本可见性
```

### Q2: RC和RR有什么区别？

```
A:
1. RC: 每次SELECT生成新Read View
2. RR: 事务第一次SELECT生成Read View，后续复用
3. RR防止不可重复读和幻影读
```

### Q3: 如何避免死锁？

```
A:
1. 统一锁顺序
2. 一次性申请所有锁
3. 缩短持锁时间
4. 使用乐观锁
```

## 六、自测题

1. 解释Next-Key Lock的工作原理
2. 如何实现乐观锁？
3. 分析死锁产生的原因和解决方案

---

## 参考文档

- [MySQL官方文档](https://dev.mysql.com/doc/refman/8.0/en/)
- [InnoDB锁机制详解](https://dev.mysql.com/doc/refman/8.0/en/innodb-locks.html)
