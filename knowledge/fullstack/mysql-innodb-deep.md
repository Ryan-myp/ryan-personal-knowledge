# MySQL InnoDB 事务深度：从 ACID 到 MVCC 源码级解析

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 InnoDB 事务

想象你去银行取钱：

```
A = 原子性：取钱要么成功，要么失败，不能"扣了钱但没给现金"
C = 一致性：取钱前后，账户总额不变
I = 隔离性：你和别人的取款操作互不影响
D = 持久性：取钱成功后，即使银行断电，记录也不会丢
```

### ACID 在 InnoDB 中怎么实现？

| 特性 | 实现机制 | 关键文件 |
|------|---------|---------|
| **A** | Undo Log + 事务回滚 | undo/undo0zip.cc |
| **C** | 业务逻辑 + 约束 | 应用层 |
| **I** | MVCC + Lock | lock/lock0lock.cc |
| **D** | Redo Log + fsync | log/log0log.cc |

---

## 第二部分：Redo Log 深度解析

### 2.1 Redo Log 为什么能保证持久性？

**核心问题**：数据在内存里，断电不就丢了？

**答案**：Redo Log（WAL 写前日志）

```
写入流程：
1. 修改内存中的 Buffer Pool（快！）
2. 同时写 Redo Log 到磁盘（顺序写，快！）
3. 返回成功

后台线程：
4. 定期将 Redo Log 中的修改刷入 ibdata（慢！）

好处：
- 写内存很快
- Redo Log 是顺序写，比随机写快 100 倍
- 断电后从 Redo Log 恢复
```

### 2.2 Redo Log 源码级解析

```go
package innodb

import (
    "fmt"
    "os"
    "sync"
    "unsafe"
)

// RedoLog 模拟 InnoDB 的 Redo Log 结构
type RedoLog struct {
    mu         sync.Mutex
    file       *os.File
    lsn        uint64  // Log Sequence Number
    buffer     []byte
    bufferSize int     // 默认 16MB
}

// 初始化 Redo Log
func NewRedoLog(path string) (*RedoLog, error) {
    f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
    if err != nil {
        return nil, err
    }
    
    return &RedoLog{
        file:       f,
        bufferSize: 16 * 1024 * 1024, // 16MB
    }, nil
}

// WriteRedo 写入 Redo Log
// 关键：这是顺序写，非常快
func (rl *RedoLog) WriteRedo(record *RedoRecord) error {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    // 1. 序列化 Redo Record
    data := rl.serialize(record)
    
    // 2. 追加到 Redo Log 文件
    _, err := rl.file.Write(data)
    if err != nil {
        return err
    }
    
    // 3. 更新 LSN
    rl.lsn += uint64(len(data))
    
    return nil
}

// Flush 强制刷盘
// fsync 是关键：确保数据真正写到磁盘
func (rl *RedoLog) Flush() error {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    return rl.file.Sync() // fsync
}

// RedoRecord 一条 Redo 记录的格式
type RedoRecord struct {
    LSN       uint64  // 日志序列号
    PageID    uint32  // 页 ID
    Offset    uint16  // 页内偏移
    Length    uint16  // 修改长度
    Data      []byte  // 修改的数据
}

func (rl *RedoLog) serialize(r *RedoRecord) []byte {
    // 格式：[LSN(8)][PageID(4)][Offset(2)][Length(2)][Data(N)]
    // 总共 16 + N 字节
    data := make([]byte, 16+int(r.Length))
    
    // LSN
    copy(data[0:8], rl.uint64ToBytes(r.LSN))
    // PageID
    copy(data[8:12], rl.uint32ToBytes(r.PageID))
    // Offset
    copy(data[12:14], rl.uint16ToBytes(r.Offset))
    // Length
    copy(data[14:16], rl.uint16ToBytes(r.Length))
    // Data
    copy(data[16:], r.Data)
    
    return data
}

// 关键参数：innodb_flush_log_at_trx_commit
// 1: 每次事务提交都 fsync（最安全，性能最差）
// 2: 每次事务提交写 OS 缓存，每秒 fsync（性能好，可能丢 1 秒数据）
// 0: 不 fsync，由操作系统决定（性能最好，可能丢数据）
// 推荐：金融业务用 1，普通业务用 2
```

### 2.3 Redo Log 循环写

```
Redo Log 不是无限增长的！它是循环使用的。

┌─────────────────────────────────────────────────────┐
│ redo_log_001 (1GB)                                  │
│ ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐ │
│ │  LSN │  LSN │  LSN │  LSN │  LSN │  LSN │  LSN │ │
│ │ 0001 │ 0002 │ 0003 │ 0004 │ 0005 │ 0006 │ 0007 │ │
│ └──────┴──────┴──────┴──────┴──────┴──────┴──────┘ │
│ ▲                                                  │
│ │                                                  │
│ └──────────────── checkpoint ──────────────────────┘
│ (checkpoint 之前的可以复用)
│
│ write_pos: 当前写入位置
│ checkpoint: 检查点位置
│
│ 当 write_pos 追上 checkpoint 时，需要等待 checkpoint 推进
```

```go
// 关键参数：innodb_log_file_size
// 默认 48MB，建议设置为内存的 25%
// 越大越好：减少 checkpoint 频率，提高性能
// 但恢复时间更长

// 关键参数：innodb_log_files_in_group
// 默认 2，表示有两个 redo log 文件循环使用
// 增大可以减少 checkpoint 频率
```

---

## 第三部分：Undo Log 深度解析

### 3.1 Undo Log 的作用

```
Undo Log 有两个主要用途：
1. 事务回滚（Rollback）
2. MVCC（多版本并发控制）
```

### 3.2 Undo Log 结构

```
Undo Log 记录的是"反向操作"：

INSERT → 删除记录
UPDATE → 恢复到旧值
DELETE → 重新插入记录
```

```go
package undo

import (
    "fmt"
)

// UndoRecord 一条 Undo 记录
type UndoRecord struct {
    RollPointer uint64 // 回滚指针，指向上一条 Undo 记录
    TransactionID uint64 // 事务 ID
    RollOperation RollOp // 操作类型
    OldValue    []byte // 旧值
    NewValue    []byte // 新值
}

type RollOp int

const (
    RollInsert RollOp = iota // 撤销 INSERT = 删除
    RollUpdate               // 撤销 UPDATE = 恢复旧值
    RollDelete               // 撤销 DELETE = 重新插入
)

// UndoLog 管理 Undo 记录
type UndoLog struct {
    records []UndoRecord
    mu      sync.Mutex
}

func (ul *UndoLog) AddRecord(rec UndoRecord) {
    ul.mu.Lock()
    defer ul.mu.Unlock()
    ul.records = append(ul.records, rec)
}

// Rollback 回滚事务
func (ul *UndoLog) Rollback(txnID uint64) error {
    ul.mu.Lock()
    defer ul.mu.Unlock()
    
    // 从后往前找该事务的 Undo 记录
    for i := len(ul.records) - 1; i >= 0; i-- {
        rec := ul.records[i]
        if rec.TransactionID != txnID {
            continue
        }
        
        // 执行反向操作
        switch rec.RollOperation {
        case RollInsert:
            // 撤销 INSERT = 删除该行
            ul.deleteRow(rec.NewValue)
        case RollUpdate:
            // 撤销 UPDATE = 恢复旧值
            ul.restoreRow(rec.OldValue, rec.NewValue)
        case RollDelete:
            // 撤销 DELETE = 重新插入
            ul.insertRow(rec.NewValue)
        }
    }
    
    return nil
}
```

---

## 第四部分：MVCC 深度解析

### 4.1 MVCC 是什么？

**类比**：维基百科的版本历史

```
版本 1: 页面标题 = "Go 语言"
版本 2: 页面标题 = "Go 编程语言"  ← 有人修改了
版本 3: 页面标题 = "Go 编程语言" + 内容更新

不同时间点的人看到的是不同版本：
- 你在版本 1 开始编辑
- 别人在版本 2 编辑
- 你不会互相干扰
```

**MVCC 在数据库中的体现**：

```
事务 A 在 T1 读到 row.version = 1
事务 B 在 T2 修改 row.version = 2
事务 A 在 T3 再读 → 仍然看到 version = 1（不可重复读 avoided）
```

### 4.2 Hidden Columns（隐藏列）

```
每行数据实际上有这些隐藏列：

┌─────────────────────────────────────────────────────┐
│ 用户可见列                                            │
│ id | name | age | ...                                │
├─────────────────────────────────────────────────────┤
│ InnoDB 隐藏列                                         │
│ DB_TRX_ID (8 bytes) | DB_ROLL_PTR (7 bytes) | ...   │
└─────────────────────────────────────────────────────┘

DB_TRX_ID: 创建或修改这行的事务 ID
DB_ROLL_PTR: 回滚指针，指向 Undo Log 中的上一版本
DB_ROW_ID: 隐藏的行 ID（如果表没有主键，InnoDB 自动生成）
```

### 4.3 Read View（读视图）

```
Read View 是 MVCC 的核心！

Read View 包含：
1. m_ids: 当前活跃的事务 ID 列表
2. min_trx_id: 最小活跃事务 ID
3. max_trx_id: 下一个要分配的事务 ID
4. creator_trx_id: 创建这个 Read View 的事务 ID

可见性规则：
- 如果 row.trx_id < min_trx_id → 可见（事务已提交）
- 如果 row.trx_id >= max_trx_id → 不可见（事务还没开始）
- 如果 row.trx_id 在 m_ids 中 → 不可见（事务活跃）
- 如果 row.trx_id == creator_trx_id → 可见（自己改的）
- 其他情况 → 通过 Undo Log 找更早的版本
```

```go
package mvcc

import (
    "fmt"
    "sort"
)

// ReadView 读视图
type ReadView struct {
    mIds        []uint64 // 活跃事务 ID 列表
    minTrxId    uint64   // 最小活跃事务 ID
    maxTrxId    uint64   // 下一个要分配的事务 ID
    creatorTrxId uint64  // 创建者事务 ID
}

// IsVisible 判断某行数据对当前 ReadView 是否可见
func (rv *ReadView) IsVisible(rowTrxId uint64) bool {
    // 1. 如果行数据的事务 ID < min_trx_id，说明事务已提交 → 可见
    if rowTrxId < rv.minTrxId {
        return true
    }
    
    // 2. 如果行数据的事务 ID >= max_trx_id，说明事务还没开始 → 不可见
    if rowTrxId >= rv.maxTrxId {
        return false
    }
    
    // 3. 在 mIds 范围内，检查是否是自己创建的
    if rowTrxId == rv.creatorTrxId {
        return true
    }
    
    // 4. 在 mIds 列表中，说明事务活跃 → 不可见
    for _, id := range rv.mIds {
        if id == rowTrxId {
            return false
        }
    }
    
    // 5. 不在 mIds 中但 >= min_trx_id → 已提交 → 可见
    return true
}

// 创建 Read View 的时机
// REPEATABLE READ（默认隔离级别）：第一次 SELECT 时创建
// READ COMMITTED：每次 SELECT 时都创建新的 Read View
```

### 4.4 Undo Log Chain（回滚链表）

```
当数据不可见时，通过 Undo Log Chain 找到可见的版本：

原始数据:
  Row: id=1, name=Alice, trx_id=100
  Undo: trx_id=90, name=Bob
  
ReadView: min=95, max=110, mIds=[100, 105]

检查 Row (trx_id=100):
  100 < 95? No
  100 >= 110? No
  100 == creator? No
  100 in mIds? Yes → 不可见
  
→ 跟随 Undo Log Chain 找上一个版本
→ Undo (trx_id=90):
  90 < 95? Yes → 可见！返回 name=Bob
```

---

## 第五部分：死锁检测

### 5.1 死锁是什么？

```
事务 A 持有锁 L1，等待 L2
事务 B 持有锁 L2，等待 L1
→ 死锁！谁也动不了
```

### 5.2 Go 实现死锁检测

```go
package deadlock

import (
    "sync"
)

// LockGraph 锁等待图
type LockGraph struct {
    mu       sync.Mutex
    waitsFor map[uint64]uint64 // txID → 等待的 txID
}

// AddWait 添加等待关系
func (lg *LockGraph) AddWait(waiter, holder uint64) {
    lg.mu.Lock()
    defer lg.mu.Unlock()
    lg.waitsFor[waiter] = holder
}

// RemoveWait 移除等待关系
func (lg *LockGraph) RemoveWait(txID uint64) {
    lg.mu.Lock()
    defer lg.mu.Unlock()
    delete(lg.waitsFor, txID)
}

// DetectCycle 检测死锁（环）
func (lg *LockGraph) DetectCycle() ([]uint64, bool) {
    lg.mu.Lock()
    defer lg.mu.Unlock()
    
    visited := make(map[uint64]bool)
    path := make([]uint64, 0)
    
    for txID := range lg.waitsFor {
        if !visited[txID] {
            cycle, found := lg.dfs(txID, visited, path)
            if found {
                return cycle, true
            }
        }
    }
    
    return nil, false
}

func (lg *LockGraph) dfs(current uint64, visited map[uint64]bool, path []uint64) ([]uint64, bool) {
    if visited[current] {
        // 找到环
        return path, true
    }
    
    visited[current] = true
    path = append(path, current)
    
    if next, ok := lg.waitsFor[current]; ok {
        cycle, found := lg.dfs(next, visited, path)
        if found {
            return cycle, true
        }
    }
    
    return nil, false
}
```

### 5.3 死锁预防策略

| 策略 | 说明 | 优缺点 |
|------|------|--------|
| **死锁检测** | 建等待图，检测环 | 优点：只杀一个事务<br>缺点：有检测开销 |
| **死锁预防** | 按固定顺序加锁 | 优点：无检测开销<br>缺点：可能死锁 |
| **超时回滚** | 等待超过 N ms 就回滚 | 优点：简单<br>缺点：可能误杀 |

```go
// InnoDB 默认使用死锁检测 + 超时
// innodb_deadlock_detect = on (默认)
// innodb_lock_wait_timeout = 50s (默认)

// 最佳实践：
// 1. 按相同顺序访问表
// 2. 尽量用小事务
// 3. 使用 SELECT ... FOR SHARE 代替 UPDATE
// 4. 设置合理的 lock_wait_timeout
```

---

## 第六部分：生产排障案例

### 6.1 慢查询排查

```
现象：某接口响应时间从 10ms 飙升到 5s

排查步骤：
1. SHOW PROCESSLIST → 找到慢查询
2. EXPLAIN → 分析执行计划
3. 检查索引是否命中
4. 检查锁等待
```

```sql
-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1; -- 超过 1s 的记录

-- 查看慢查询日志
mysqldumpslow /var/log/mysql/slow.log

-- EXPLAIN 分析
EXPLAIN SELECT * FROM ads WHERE campaign_id = 123 AND status = 'active';

-- 关键看：
-- type: ref = 使用索引等值查询，range = 索引范围查询，ALL = 全表扫描
-- key: 实际使用的索引
-- rows: 预估扫描行数
-- Extra: Using where = 需要额外过滤，Using index = 覆盖索引
```

### 6.2 锁等待排查

```sql
-- 查看锁等待
SELECT * FROM information_schema.INNODB_LOCK_WAITS;

-- 查看活跃事务
SELECT * FROM information_schema.INNODB_TRX;

-- 查看锁信息
SELECT * FROM information_schema.INNODB_LOCKS;

-- 杀死锁等待的事务
KILL <thread_id>;
```

### 6.3 Buffer Pool 调优

```
现象：MySQL 内存使用率高，但查询慢

原因：Buffer Pool 太小，频繁从磁盘读取

解决：
1. 增大 innodb_buffer_pool_size
2. 生产环境建议设为物理内存的 60-80%
3. 监控 Buffer Pool 命中率

SHOW ENGINE INNODB STATUS\G

-- 关键指标：
-- Page read rate: 每秒读的页数
-- Page write rate: 每秒写的页数
-- Buffer pool hit rate: 命中率（应该 > 99%）
```

---

## 第七部分：自测题

### 问题 1
为什么 Redo Log 是顺序写，而数据页是随机写？

<details>
<summary>查看答案</summary>

1. **Redo Log**：追加到文件末尾，顺序写
2. **数据页**：修改任意位置的页，随机写
3. **顺序写比随机写快 100 倍**
4. **Redo Log 循环使用**：不会无限增长
5. **fsync 保证持久性**：数据真正写到磁盘

</details>

### 问题 2
MVCC 如何解决不可重复读？

<details>
<summary>查看答案</summary>

1. **Read View**：每个事务有自己的读视图
2. **Undo Log Chain**：通过回滚链找到可见版本
3. **REPEATABLE READ**：第一次 SELECT 创建 Read View
4. **READ COMMITTED**：每次 SELECT 创建新 Read View
5. **RR 级别**：同一个事务内看到的数据是一致的

</details>

### 问题 3
Buffer Pool 命中率低于 99% 怎么优化？

<details>
<summary>查看答案</summary>

1. **增大 innodb_buffer_pool_size**
2. **分片**：多 CPU 核心时分成多个 Buffer Pool
3. **预热**：启动时加载热点数据
4. **监控**：Page read/write rate
5. **索引优化**：减少全表扫描

</details>

---

*本文档基于 MySQL InnoDB 源码和生产实战整理，包含逐行解析、排障案例、对比分析。*