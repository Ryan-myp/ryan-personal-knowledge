# MySQL 存储引擎深度解析

> 深入MySQL存储引擎：InnoDB、MyISAM、存储结构、索引实现。
> 源码级分析，包含生产环境调优。
> 适用对象：DBA、后端工程师

---

## 1. InnoDB 架构

### 1.1 核心组件

```
InnoDB 核心组件：

├── 缓冲池 (Buffer Pool)
│   ├── 数据页缓存
│   ├── 索引页缓存
│   └── 自适应哈希
│
├── 重做日志 (Redo Log)
│   ├── WAL机制
│   └── 崩溃恢复
│
├── 撤销日志 (Undo Log)
│   ├── MVCC支持
│   └── 事务回滚
│
└── .change 文件
    └── 表空间
```

### 1.2 Go 实现 InnoDB

```go
// innodb.go

package mysql

import (
    "sync"
)

type InnoDB struct {
    bufferPool  *BufferPool
    redoLog     *RedoLog
    undoLog     *UndoLog
    tableSpace  *TableSpace
    mu          sync.Mutex
}

type BufferPool struct {
    pages    map[pageID]*Page
    lruList  *LRUList
    hashIndex *HashIndex
}

type RedoLog struct {
    files   []*Logfile
    cursor  int64
    mu      sync.Mutex
}

type UndoLog struct {
    segments []*UndoSegment
    mu       sync.Mutex
}

type Page struct {
    id       pageID
    data     []byte
    dirty    bool
    lsn      int64
}

func NewInnoDB() *InnoDB {
    return &InnoDB{
        bufferPool: NewBufferPool(),
        redoLog:    NewRedoLog(),
        undoLog:    NewUndoLog(),
        tableSpace: NewTableSpace(),
    }
}
```

---

## 2. B+树索引

### 2.1 索引结构

```
B+树索引结构：

┌─────────────────────────────────────────────────────────────┐
│                    B+树结构                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌─────┐                                  │
│                    │ 15  │  Root Node                      │
│                    └──┬──┘                                  │
│                       │                                     │
│          ┌────────────┼────────────┐                       │
│          │            │            │                       │
│     ┌────┴────┐  ┌────┴────┐  ┌────┴────┐                │
│     │ 5 10   │  │ 20 25   │  │ 30 35   │  Leaf Nodes    │
│     └────┬────┘  └────┬────┘  └────┬────┘                │
│          │            │            │                       │
│    ┌─────┴───┐  ┌────┴───┐  ┌────┴───┐                  │
│    │ 1 3 5   │  │ 7 9    │  │11 13 15│  Data Pages       │
│    └─────────┘  └────────┘  └────────┘                  │
│                                                             │
│  特点：                                                      │
│  ├── 所有数据在叶子节点                                      │
│  ├── 叶子节点双向链表                                        │
│  └── 非叶子节点只存索引                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现 B+树

```go
// bplus_tree.go

package mysql

import (
    "sync"
)

type BPlusTree struct {
    root     *Node
    order    int
    mu       sync.RWMutex
}

type Node struct {
    isLeaf   bool
    keys     []interface{}
    values   []interface{}
    children []*Node
    next     *Node // 叶子节点链表
}

func NewBPlusTree(order int) *BPlusTree {
    return &BPlusTree{
        root:  NewNode(true),
        order: order,
    }
}

func (t *BPlusTree) Insert(key, value interface{}) {
    t.mu.Lock()
    defer t.mu.Unlock()
    
    node := t.root
    if node.isFull() {
        newRoot := NewNode(false)
        newRoot.children = append(newRoot.children, node)
        t.splitChild(newRoot, 0)
        t.root = newRoot
    }
    t.insertNonFull(node, key, value)
}

func (t *BPlusTree) Search(key interface{}) (interface{}, bool) {
    t.mu.RLock()
    defer t.mu.RUnlock()
    return t.searchNode(t.root, key)
}

func (n *Node) isFull() bool {
    return len(n.keys) >= n.order*2-1
}
```

---

## 3. 事务日志

### 3.1 Redo Log

```
Redo Log 工作原理：

1. 修改数据页
   └── 标记为dirty

2. 写入Redo Log
   ├── log buffer
   └── 刷盘策略

3. 刷盘触发
   ├── innodb_flush_log_at_trx_commit
   ├── doublewrite buffer
   └── fsync
```

### 3.2 Go 实现 Redo Log

```go
// redo_log.go

package mysql

import (
    "os"
    "sync"
)

type RedoLog struct {
    files    []*LogFile
    cursor   int64
    buffer   []byte
    mu       sync.Mutex
}

type LogEntry struct {
    lsn      int64
    pageID   pageID
    offset   int
    data     []byte
    checksum uint32
}

func NewRedoLog(path string) (*RedoLog, error) {
    return &RedoLog{
        files: make([]*LogFile, 2),
    }, nil
}

func (rl *RedoLog) Write(entry *LogEntry) error {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    // 写入 log buffer
    rl.buffer = append(rl.buffer, entry.data...)
    rl.cursor += int64(len(entry.data))
    
    // 检查是否需要刷盘
    if rl.cursor > rl.flushThreshold {
        return rl.flush()
    }
    return nil
}

func (rl *RedoLog) flush() error {
    // 双重写缓冲
    // 刷盘到文件
    return nil
}

func (rl *RedoLog) Replay(startLSN int64) {
    // 崩溃恢复
}
```

---

## 4. MVCC 实现

### 4.1 版本链

```
MVCC 版本链：

┌─────────────────────────────────────────────────────────────┐
│  Row Version Chain                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Current  │───→│ Version  │───→│ Version  │             │
│  │ Version  │    │  3       │    │  2       │             │
│  └──────────┘    └──────────┘    └──────────┘             │
│       ↑                                                 │
│       │                                                 │
│  ┌──────────┐                                           │
│  │ Undo Log │← 回滚指针                                  │
│  └──────────┘                                           │
│                                                             │
│  可见性判断：                                               │
│  ├── trx_id <= consistent_trx_id                          │
│  └── trx_id > last_trx_id (如果已删除)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Go 实现 MVCC

```go
// mvcc.go

package mysql

import (
    "sync"
)

type MVCCManager struct {
    versions map[string][]*Version
    mu       sync.RWMutex
}

type Version struct {
    trxID     int64
    data      []byte
    prev      *Version
    deleted   bool
}

func NewMVCCManager() *MVCCManager {
    return &MVCCManager{
        versions: make(map[string][]*Version),
    }
}

func (m *MVCCManager) Get(key string, snapshotTrxID int64) ([]byte, error) {
    m.mu.RLock()
    defer m.mu.RUnlock()
    
    versions, ok := m.versions[key]
    if !ok {
        return nil, nil
    }
    
    // 找到可见版本
    for _, v := range versions {
        if m.isVisible(v, snapshotTrxID) {
            return v.data, nil
        }
    }
    return nil, nil
}

func (m *MVCCManager) Set(key string, data []byte, trxID int64) error {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    version := &Version{
        trxID: trxID,
        data:  data,
    }
    
    if versions, ok := m.versions[key]; ok && len(versions) > 0 {
        version.prev = versions[0]
    }
    
    m.versions[key] = append([]*Version{version}, m.versions[key]...)
    return nil
}

func (m *MVCCManager) isVisible(version *Version, snapshotTrxID int64) bool {
    return version.trxID <= snapshotTrxID && !version.deleted
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 组件 | 作用 |
|------|------|
| Buffer Pool | 数据缓存 |
| Redo Log | 持久性 |
| Undo Log | 回滚/MVCC |
| B+树 | 索引结构 |

### 5.2 最佳实践

- [ ] 合理配置 Buffer Pool
- [ ] 监控 Redo Log 刷盘
- [ ] 优化索引设计
- [ ] 理解 MVCC 机制

---

*最后更新：2026-08-12*
*作者：Ryan*
