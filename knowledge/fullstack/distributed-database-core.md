# 分布式数据库核心原理

> MVCC / WAL / BloomFilter / 两阶段提交 — 广告平台数据存储基石

---

## 第一部分：入门引导（5 分钟速览）

### 为什么广告平台需要理解数据库内核？

广告平台的核心数据：
- **用户行为日志**：PV/Click/Conversion，每日 TB 级
- **广告库存**：实时可投放的广告位
- **竞价结果**：百万 QPS 的竞价记录
- **预算数据**：广告主预算扣减，强一致性要求

理解数据库内核能帮助：
1. **性能调优**：索引设计、查询优化、事务隔离
2. **问题排查**：死锁、慢查询、锁等待
3. **架构设计**：分库分表、读写分离、多活

### 数据库内核关键概念

| 概念 | 说明 | 广告平台场景 |
|------|------|-------------|
| **MVCC** | 多版本并发控制 | 预算扣减与查询并发 |
| **WAL** | 预写日志 | 数据持久化、崩溃恢复 |
| **B+ 树** | 索引结构 | 快速查询广告位 |
| **BloomFilter** | 布隆过滤器 | 快速判断 key 不存在 |
| **两阶段提交** | 分布式事务 | 跨库预算扣减 |

---

## 第二部分：MVCC（多版本并发控制）

### 2.1 MVCC 简介

**MVCC** 允许多个事务同时读/写，提高并发性能，无需加锁。

### 2.2 MVCC 核心机制

```
每行数据有多个版本：
row_id | data | version | tx_id | delete_flag
-----------------------------------------
1      | 100  | 1       | T1    | 0
1      | 150  | 2       | T2    | 0
1      | 200  | 3       | T3    | 0

每个事务有 read_view（快照）：
T1 read_view: 能看到 version ≤ 1 的版本
T2 read_view: 能看到 version ≤ 2 的版本
T3 read_view: 能看到 version ≤ 3 的版本
```

### 2.3 InnoDB MVCC 实现

```
InnoDB 每个行记录隐藏列：
- DB_TRX_ID: 最近修改该行的事务 ID
- DB_ROLL_PTR: 回滚指针（指向 undo log）
- DB_ROW_ID: 隐藏主键

事务读：
1. 读当前版本
2. 如果 tx_id > 当前事务 ID → 看不到
3. 通过回滚指针遍历 undo log，找到可见版本
```

### 2.4 Go 中模拟 MVCC

```go
type VersionedRow struct {
    Version int
    Data    string
    TXID    int64
    Deleted bool
}

type MVCCStore struct {
    rows   map[int][]VersionedRow
    maxTx  int64
}

func (m *MVCCStore) Put(key int, data string, txid int64) {
    row := VersionedRow{
        Version: len(m.rows[key]) + 1,
        Data:    data,
        TXID:    txid,
    }
    m.rows[key] = append(m.rows[key], row)
}

func (m *MVCCStore) Get(key int, txid int64) (string, bool) {
    versions, ok := m.rows[key]
    if !ok {
        return "", false
    }
    // 找到 txid 可见的最新版本
    for i := len(versions) - 1; i >= 0; i-- {
        v := versions[i]
        if v.TXID <= txid && !v.Deleted {
            return v.Data, true
        }
    }
    return "", false
}
```

---

## 第三部分：WAL（预写日志）

### 3.1 WAL 简介

**WAL（Write-Ahead Logging）**：在修改数据页之前，先写日志。

### 3.2 WAL 流程

```
事务修改数据：
1. 修改redo log（磁盘顺序写）
2. 修改内存 buffer pool
3. 提交事务 → 刷新 redo log
4. 后台线程异步刷脏页到磁盘

崩溃恢复：
1. 读 redo log
2. 重做（redo）未提交事务
3. 回滚（undo）未提交事务
```

### 3.3 WAL Go 实现

```go
type WAL struct {
    file    *os.File
    mu      sync.Mutex
    entries []WALEntry
}

type WALEntry struct {
    TXID    int64
    Key     string
    Value   string
    Op      string // PUT/DELETE
}

func (w *WAL) Write(entry WALEntry) error {
    w.mu.Lock()
    defer w.mu.Unlock()
    
    // 序列化到日志
    data := fmt.Sprintf("%d|%s|%s|%s\n", entry.TXID, entry.Key, entry.Value, entry.Op)
    _, err := w.file.WriteString(data)
    if err != nil {
        return err
    }
    
    // 强制刷盘
    return w.file.Sync()
}

func (w *WAL) Replay() map[string]string {
    result := make(map[string]string)
    // 从日志中恢复数据
    scanner := bufio.NewScanner(w.file)
    for scanner.Scan() {
        parts := strings.Split(scanner.Text(), "|")
        if len(parts) == 4 {
            key, value, op := parts[1], parts[2], parts[3]
            if op == "PUT" {
                result[key] = value
            } else if op == "DELETE" {
                delete(result, key)
            }
        }
    }
    return result
}
```

---

## 第四部分：BloomFilter（布隆过滤器）

### 4.1 BloomFilter 简介

**布隆过滤器**：用极小空间判断元素是否存在，可能有误判（假阳性），但不会漏判（假阴性）。

### 4.2 BloomFilter 原理

```
1. 初始化 m 位比特数组，全部为 0
2. 有 k 个哈希函数
3. 插入元素：通过 k 个哈希函数计算 k 个位置，设为 1
4. 查询元素：通过 k 个哈希函数，如果全部为 1 → 可能存在

误判率：p ≈ (1 - e^(-kn/m))^k
```

### 4.3 BloomFilter Go 实现

```go
package bloomfilter

import (
    "hash/fnv"
    "math"
)

type BloomFilter struct {
    bits      []bool
    bitSize   int
    hashCount int
}

func NewBF(n int, p float64) *BloomFilter {
    bitSize := int(-float64(n) * math.Log(p) / (math.Ln2 * math.Ln2))
    hashCount := int(float64(bitSize) / float64(n) * math.Ln2)
    return &BloomFilter{
        bits:      make([]bool, bitSize),
        bitSize:   bitSize,
        hashCount: hashCount,
    }
}

func (bf *BloomFilter) Add(key string) {
    for i := 0; i < bf.hashCount; i++ {
        h := fnv64a(key + string(rune(i)))
        idx := int(h % uint64(bf.bitSize))
        bf.bits[idx] = true
    }
}

func (bf *BloomFilter) MightContain(key string) bool {
    for i := 0; i < bf.hashCount; i++ {
        h := fnv64a(key + string(rune(i)))
        idx := int(h % uint64(bf.bitSize))
        if !bf.bits[idx] {
            return false
        }
    }
    return true
}

func fnv64a(s string) uint64 {
    h := fnv.New64a()
    h.Write([]byte(s))
    return h.Sum64()
}
```

### 4.4 广告平台中的 BloomFilter 应用

| 场景 | 作用 | 误判率 |
|------|------|--------|
| **广告去重** | 判断曝光是否重复 | 0.01% |
| **缓存穿透** | 判断 key 不存在 | 0.1% |
| **DDoS 检测** | 判断 IP 是否恶意 | 1% |
| **数据同步** | 判断数据变更 | 0.001% |

---

## 第五部分：两阶段提交（2PC）

### 5.1 2PC 流程

```
Prepare 阶段：
- Coordinator 向所有 Participant 发送 Prepare 消息
- Participant 执行事务，不提交
- 回复 OK 或 ABORT

Commit 阶段：
- Coordinator 收到所有 OK → 发送 Commit
- 任一 ABORT → 发送 Abort
- Participant 执行 Commit/Abort
```

### 5.2 2PC Go 实现

```go
type Participant struct {
    id    string
    db    *Database
    ready chan bool
}

func (p *Participant) Prepare() bool {
    // 执行事务但不提交
    p.db.Begin()
    if p.db.Commit() {
        p.ready <- true
        return true
    }
    p.ready <- false
    return false
}

type Coordinator struct {
    participants []*Participant
    ch           chan bool
}

func (c *Coordinator) Execute() error {
    // Phase 1: Prepare
    for _, p := range c.participants {
        go p.Prepare()
    }
    
    for i := 0; i < len(c.participants); i++ {
        ok := <-c.ch
        if !ok {
            // Phase 2: Abort
            for _, p := range c.participants {
                p.db.Rollback()
            }
            return fmt.Errorf("prepare failed")
        }
    }
    
    // Phase 2: Commit
    for _, p := range c.participants {
        p.db.Commit()
    }
    return nil
}
```

---

## 第六部分：自测题

### 问题 1
MVCC 如何解决读写冲突？

<details>
<summary>查看答案</summary>

1. **读不会阻塞写**：读事务看快照，写事务不阻塞读
2. **写不会阻塞读**：写事务只修改新版本，读事务看旧版本
3. **写-写冲突**：需要乐观锁（版本号）或悲观锁（SELECT FOR UPDATE）
4. **快照隔离**：InnoDB 的 Repeatable Read 级别
5. **实际场景**：广告主查询预算与扣减事务并发

</details>

### 问题 2
BloomFilter 的误判率如何计算和优化？

<details>
<summary>查看答案</summary>

1. **误判率公式**：p ≈ (1 - e^(-kn/m))^k
   - n: 元素数，k: 哈希函数数，m: 比特数组大小
2. **优化方向**：
   - 增加 m：空间换精度
   - 优化 k：k = ln(2) * m/n ≈ 0.693 * m/n
3. **广告平台**：m=8M bits, n=1M elements, k=6 → p≈0.001%

</details>

### 问题 3
WAL 如何保证崩溃恢复？

<details>
<summary>查看答案</summary>

1. **顺序写优势**：redo log 顺序写，性能远高于随机写
2. **崩溃恢复流程**：
   - 读 redo log，找到最后检查点
   - 重做（redo）所有事务
   - 回滚（undo）未提交事务
3. **fsync 保证**：commit 后必须 fsync redo log
4. **广告平台**：预算扣减必须 WAL + fsync

</details>

---

*本文档基于数据库内核原理整理，结合广告平台实战场景。*