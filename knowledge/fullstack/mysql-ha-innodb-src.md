# MySQL 高可用/InnoDB 事务源码深度

> MHA/Orchestrator/PXC / InnoDB 事务 ACID / MVCC 源码 / WAL redo log / 死锁检测

---

## 第一部分：入门引导（5 分钟速览）

### MySQL 为什么需要高可用？

广告平台要求 99.99% 可用性：
- **预算扣减**：不能丢失数据
- **竞价结果**：不能重复计算
- **用户数据**：不能丢失

### MySQL 高可用方案对比

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **MHA** | 自动故障切换 | 主从复制延迟 | 中小规模 |
| **Orchestrator** | 可视化拓扑 | 需要额外部署 | 大规模集群 |
| **PXC** | 强一致性 | 写性能较低 | 强一致需求 |
| **Group Replication** | 原生支持 | 配置复杂 | 大型集群 |

---

## 第二部分：InnoDB 事务 ACID 实现

### 2.1 ACID 四个特性

```
A - Atomicity（原子性）：undo log 回滚
C - Consistency（一致性）：事务前后数据一致
I - Isolation（隔离性）：MVCC + 锁
D - Durability（持久性）：redo log 落盘
```

### 2.2 redo log 实现

```go
package innodb

import (
    "os"
    "sync"
)

// RedoLog 实现 WAL（Write-Ahead Logging）
type RedoLog struct {
    files  []*os.File
    mu     sync.Mutex
    pos    int64
}

// LogRecord 日志记录
type LogRecord struct {
    lsn     int64   // Log Sequence Number
    pageId  int32
    offset  int32
    data    []byte
    checksum uint32
}

func (rl *RedoLog) Write(record *LogRecord) error {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    // 1. 序列化日志记录
    data := rl.serialize(record)
    
    // 2. 追加到文件
    _, err := rl.files[0].WriteAt(data, rl.pos)
    if err != nil {
        return err
    }
    
    rl.pos += int64(len(data))
    
    // 3. fsync 确保落盘
    return rl.files[0].Sync()
}

func (rl *RedoLog) Replay() error {
    // 1. 读取 redo log 文件
    scanner := bufio.NewScanner(rl.files[0])
    
    // 2. 重做所有事务
    for scanner.Scan() {
        record := rl.deserialize(scanner.Bytes())
        rl.apply(record)
    }
    
    return nil
}

func (rl *RedoLog) apply(record *LogRecord) {
    // 将日志应用到 buffer pool
    page := rl.getBufferPoolPage(record.pageId)
    copy(page[record.offset:], record.data)
}
```

### 2.3 undo log 实现

```go
type UndoLog struct {
    segments map[string]*UndoSegment
}

type UndoSegment struct {
    rollPtr  int64
    records  []*UndoRecord
}

type UndoRecord struct {
    transactionId int64
    action        string // INSERT, DELETE, UPDATE
    beforeImage   []byte
    afterImage    []byte
    nextRollPtr   int64
}

func (ul *UndoLog) Rollback(txnId int64) error {
    // 1. 查找该事务的所有 undo 记录
    records := ul.findRecordsByTxn(txnId)
    
    // 2. 按逆序执行回滚
    for i := len(records) - 1; i >= 0; i-- {
        record := records[i]
        
        switch record.action {
        case "INSERT":
            // 删除数据
            ul.delete(record.afterImage)
        case "DELETE":
            // 恢复数据
            ul.insert(record.beforeImage)
        case "UPDATE":
            // 恢复到修改前
            ul.update(record.beforeImage)
        }
    }
    
    return nil
}
```

---

## 第三部分：MVCC 源码解析

### 3.1 行版本控制

```go
type RowVersion struct {
    data        []byte
    version     int64      // 版本号
    trxId       int64      // 创建事务 ID
    rollPtr     int64      // 回滚指针
    deleted     bool       // 是否删除
}

type MVCCStore struct {
    tables map[string]map[int64][]*RowVersion
}

func (m *MVCCStore) Get(key string, trxId int64) (*RowVersion, error) {
    table := m.tables[key]
    if table == nil {
        return nil, fmt.Errorf("table not found")
    }
    
    // 找到 trxId 可见的最新版本
    for i := len(table) - 1; i >= 0; i-- {
        row := table[i]
        if row.trxId <= trxId && !row.deleted {
            return row, nil
        }
    }
    
    return nil, fmt.Errorf("no visible version")
}

func (m *MVCCStore) Put(key string, data []byte, trxId int64) error {
    row := &RowVersion{
        data:    data,
        version: time.Now().UnixNano(),
        trxId:   trxId,
    }
    
    m.tables[key] = append(m.tables[key], row)
    return nil
}
```

### 3.2 Read View

```go
type ReadView struct {
    trxIds     []int64    // 活跃事务 ID 列表
    minTrxId   int64      // 最小事务 ID
    maxTrxId   int64      // 最大事务 ID（下一个要分配的事务 ID）
    creatorTrx int64      // 创建者事务 ID
}

func (rv *ReadView) IsVisible(row *RowVersion) bool {
    // 1. 如果行的 trxId 等于 creatorTrx，可见
    if row.trxId == rv.creatorTrx {
        return true
    }
    
    // 2. 如果行的 trxId < minTrxId，可见（事务已完成）
    if row.trxId < rv.minTrxId {
        return true
    }
    
    // 3. 如果行的 trxId >= maxTrxId，不可见（事务未开始）
    if row.trxId >= rv.maxTrxId {
        return false
    }
    
    // 4. 检查 trxId 是否在活跃列表中
    for _, id := range rv.trxIds {
        if row.trxId == id {
            return false // 事务还在活跃，不可见
        }
    }
    
    return true // 事务已完成，可见
}
```

---

## 第四部分：死锁检测

### 4.1 死锁图

```go
type DeadlockDetector struct {
    waitGraph map[string][]string // 等待图：节点 → 等待的节点
}

func (dd *DeadlockDetector) DetectDeadlock() ([]string, error) {
    // 1. 构建等待图
    graph := dd.buildWaitGraph()
    
    // 2. DFS 检测环
    visited := make(map[string]bool)
    path := []string{}
    
    var detectCycle func(node string) bool
    detectCycle = func(node string) bool {
        if visited[node] {
            return true
        }
        
        visited[node] = true
        path = append(path, node)
        
        for _, neighbor := range graph[node] {
            if detectCycle(neighbor) {
                return true
            }
        }
        
        path = path[:len(path)-1]
        return false
    }
    
    // 3. 检测所有节点
    for node := range graph {
        if detectCycle(node) {
            return path, nil
        }
    }
    
    return nil, nil
}
```

---

## 第五部分：自测题

### 问题 1
InnoDB 如何用 redo log 保证事务持久性？

<details>
<summary>查看答案</summary>

1. **WAL 原则**：先写日志，再写数据页
2. **redo log 顺序写**：顺序写比随机写快 10 倍
3. **fsync 保证**：commit 时 fsync redo log
4. **崩溃恢复**：重启时重做 redo log
5. **两阶段提交**：prepare + commit 保证一致性

</details>

### 问题 2
MVCC 如何解决读写冲突？

<details>
<summary>查看答案</summary>

1. **读不阻塞写**：读事务看快照
2. **写不阻塞读**：写事务只修改新版本
3. **Read View**：每个事务有独立的可见性视图
4. **回滚指针**：通过 undo log 找到可见版本
5. **写-写冲突**：需要乐观锁或悲观锁

</details>

### 问题 3
MySQL 死锁如何处理？

<details>
<summary>查看答案</summary>

1. **死锁检测**：构建等待图，检测环
2. **死锁预防**：按顺序加锁
3. **死锁避免**：超时检测
4. **死锁处理**：选择代价小的事务回滚
5. **Go 实现**：使用检测器算法

</details>

---

*本文档基于 MySQL 高可用原理整理，结合广告平台实战场景。*