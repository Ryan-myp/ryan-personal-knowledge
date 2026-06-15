# 数据库深度：Memcached/TiDB

> Memcached 缓存淘汰/TiDB HTAP/MVCC 实现

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要缓存？

广告平台缓存策略：
- **用户画像**：Redis 缓存，命中率 95%+
- **广告库存**：Memcached 缓存，减少 DB 压力
- **热点数据**：本地缓存 + 分布式缓存

---

## 第二部分：Memcached 深度

### 2.1 缓存淘汰策略

```go
package memcached

import (
    "container/list"
    "sync"
)

type LRUCache struct {
    capacity int
    items    map[string]*list.Element
    list     *list.List
    mu       sync.RWMutex
}

type entry struct {
    key   string
    value interface{}
}

func NewLRUCache(capacity int) *LRUCache {
    return &LRUCache{
        capacity: capacity,
        items:    make(map[string]*list.Element),
        list:     list.New(),
    }
}

func (c *LRUCache) Get(key string) (interface{}, bool) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    if elem, ok := c.items[key]; ok {
        c.list.MoveToFront(elem)
        return elem.Value.(*entry).value, true
    }
    
    return nil, false
}

func (c *LRUCache) Set(key string, value interface{}) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    if elem, ok := c.items[key]; ok {
        c.list.MoveToFront(elem)
        elem.Value.(*entry).value = value
        return
    }
    
    if c.list.Len() >= c.capacity {
        oldest := c.list.Back()
        c.list.Remove(oldest)
        delete(c.items, oldest.Value.(*entry).key)
    }
    
    newEntry := &entry{key: key, value: value}
    elem := c.list.PushFront(newEntry)
    c.items[key] = elem
}
```

### 2.2 一致性哈希

```go
type ConsistentHash struct {
    hashFunc  func(string) uint32
    replicas  int
    ring      []uint32
    ringMap   map[uint32]string
}

func NewConsistentHash(replicas int, hashFunc func(string) uint32) *ConsistentHash {
    return &ConsistentHash{
        hashFunc: hashFunc,
        replicas: replicas,
        ring:     make([]uint32, 0),
        ringMap:  make(map[uint32]string),
    }
}

func (ch *ConsistentHash) Add(nodes ...string) {
    for _, node := range nodes {
        for i := 0; i < ch.replicas; i++ {
            hash := ch.hashFunc(node + fmt.Sprintf("%d", i))
            ch.ring = append(ch.ring, hash)
            ch.ringMap[hash] = node
        }
    }
    sort.Slice(ch.ring, func(i, j int) bool {
        return ch.ring[i] < ch.ring[j]
    })
}

func (ch *ConsistentHash) Get(key string) string {
    if len(ch.ring) == 0 {
        return ""
    }
    
    hash := ch.hashFunc(key)
    
    // 二分查找
    idx := sort.Search(len(ch.ring), func(i int) bool {
        return ch.ring[i] >= hash
    })
    
    if idx == len(ch.ring) {
        idx = 0
    }
    
    return ch.ringMap[ch.ring[idx]]
}
```

---

## 第三部分：TiDB

### 3.1 TiDB 架构

```
TiDB Layer (SQL Layer)
    ↓
PD (Placement Driver) — 元数据管理
    ↓
TiKV Layer (Storage Layer) — Raft 一致性
```

### 3.2 Go 客户端

```go
package tidb

import (
    "database/sql"
    _ "github.com/go-sql-driver/mysql"
)

func ConnectTiDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("mysql", dsn)
    if err != nil {
        return nil, err
    }
    
    // TiDB 兼容 MySQL 协议
    db.SetMaxOpenConns(100)
    db.SetMaxIdleConns(10)
    
    return db, nil
}

// HTAP 查询
func (db *DB) AnalyticalQuery(ctx context.Context, query string) ([]Row, error) {
    // TiDB 自动路由到 TiFlash
    rows, err := db.QueryContext(ctx, query)
    if err != nil {
        return nil, err
    }
    
    var result []Row
    for rows.Next() {
        var row Row
        err := rows.Scan(&row)
        if err != nil {
            return nil, err
        }
        result = append(result, row)
    }
    
    return result, nil
}
```

### 3.3 MVCC 实现

```go
// TiDB MVCC 原理
// 每个事务有 StartTS 和 CommitTS
// 读操作看 StartTS 之前的数据
// 写操作带 CommitTS 标记

type MVCCRecord struct {
    Key       []byte
    Value     []byte
    StartTS   int64
    CommitTS  int64
    Rollback  bool
}

type MVCCReader struct {
    startTS int64
}

func (r *MVCCReader) Get(key []byte) (*MVCCRecord, error) {
    // 从最新记录开始查找
    record := r.findLatest(key)
    
    if record == nil {
        return nil, nil
    }
    
    if record.CommitTS > r.startTS {
        return nil, nil
    }
    
    if record.Rollback {
        return nil, nil
    }
    
    return record, nil
}
```

---

## 第四部分：自测题

### 问题 1
Memcached 为什么比 Redis 快？

<details>
<summary>查看答案</summary>

1. **单线程**：无多线程竞争
2. **简单协议**：文本协议开销小
3. **内存分配**：Slab Allocator 优化
4. **无持久化**：纯内存操作
5. **适用场景**：纯缓存，不需要持久化

</details>

### 问题 2
TiDB 相比 MySQL 有什么优势？

<details>
<summary>查看答案</summary>

1. **水平扩展**：自动分片
2. **HTAP**：OLTP + OLAP 一体
3. **MySQL 兼容**：无缝迁移
4. **强一致**：Raft 保证
5. **广告场景**：海量日志分析

</details>

### 问题 3
一致性哈希相比普通哈希有什么优势？

<details>
<summary>查看答案</summary>

1. **最小变动**：增减节点只影响相邻节点
2. **负载均衡**：虚拟节点均匀分布
3. **分布式**：天然适合分布式缓存
4. **Go 实现**：ring + 二分查找
5. **广告场景**：用户分片

</details>

---

*本文档基于数据库原理整理。*