# etcd 源码级深度架构：Raft 共识、MVCC 存储与生产实践

## 一、etcd 概述：分布式系统的协调中枢

### 1.1 为什么需要 etcd？

etcd 是一个分布式键值存储系统，由 CNCF 孵化，是 Kubernetes 的默认存储后端。它的核心使命：**为分布式系统提供可靠的一致性状态**。

```
etcd 在云原生栈中的位置：

┌─────────────────────────────────────────────────────┐
│                    Application Layer                 │
│  K8s API Server  │  Prometheus  │  Consul  │  Custom  │
├─────────────────────────────────────────────────────┤
│                     etcd Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Raft     │  │ MVCC     │  │ Lease/Membership │   │
│  │ Consensus│  │ Storage  │  │ Watcher System   │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│         ↓              ↓                ↓            │
│  ┌──────────────────────────────────────────────┐   │
│  │           BoltDB (Persistent Storage)        │   │
│  └──────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│              Network Transport (gRPC)                │
└─────────────────────────────────────────────────────┘
```

**与 ZooKeeper/Consul 的核心差异**：

| 特性 | etcd | ZooKeeper | Consul |
|------|------|-----------|--------|
| 一致性协议 | Raft | Zab | Raft |
| API 风格 | Key-Value | Hierarchical ZNode | Key-Value + Service Discovery |
| 强一致性 | Linearizable read | Strong | Eventually (default) |
| 数据模型 | 扁平 KV + prefix | 树形 ZNode | 扁平 KV |
| 适用场景 | 配置存储/协调 | 分布式锁/队列 | 服务发现/健康检查 |
| 吞吐量 | ~10K-50K QPS | ~5K-10K QPS | ~10K-30K QPS |

> **类比**：如果把分布式系统比作一家公司，etcd 就是公司的"人事档案室"——所有员工（节点）的状态、公司的规章制度（配置）、谁是谁的上司（领导选举），全部存在这里。任何人想查"现在谁是 CEO？"，档案室保证给出的答案是唯一且最新的。

### 1.2 etcd 3.x 架构重构

etcd 3.x 相比 2.x 进行了彻底重写：

```
etcd 2.x → etcd 3.x 的关键变化：

2.x:
  Gossip Protocol (自定义) → 不可靠、难调试
  BoltDB (单文件) → 无并发读支持
  同步 KV store → 无历史版本

3.x:
  Raft (go-raft) → 工业级共识
  BBolt (分片+读写分离) → 高并发读
  MVCC → 支持历史版本和 Watch

核心设计理念：将"存储"和"共识"完全解耦
```

## 二、etcd 整体架构与数据流

### 2.1 请求处理完整链路

```
Client Request → API Server → Raft → Store → BoltDB

详细拆解：

1. Client (gRPC/HTTP)
   ↓ 序列化 protobuf
2. etcdserver.API
   ↓ 鉴权 + 配额检查
3. ApplierV3
   ↓ 转换为 InternalRaftRequest
4. Raft Node
   ↓ 提案 → 多数派确认 → 提交
5. Applied Entries
   ↓ 写入 MVCC Store
6. MVCC Store
   ↓ 写入 BatchTx → 刷盘
7. BoltDB
   ↓ mmap + WAL
8. OS Page Cache → fsync → Disk
```

### 2.2 核心组件关系图

```
┌─────────────────────────────────────────────────────────────┐
│                        etcd Server                           │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Raft    │  │  Store   │  │  Lease   │  │ Membership │  │
│  │  Node    │  │  (MVCC)  │  │  Lessor  │  │  Cluster   │  │
│  │          │  │          │  │          │  │            │  │
│  │ - Tick   │  │ - Put    │  │ - Grant  │  │ - Add      │  │
│  │ - Propose│  │ - Get    │  │ - Revoke │  │ - Remove   │  │
│  │ - Commit │  │ - Delete │  │ - Renew  │  │ - Member   │  │
│  │ - Apply  │  │ - Watch  │  │ - Expire │  │   Attr     │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │             │             │               │          │
│       └─────────────┴─────────────┴───────────────┘          │
│                            │                                 │
│                   ┌────────▼────────┐                         │
│                   │   Backend       │                         │
│                   │   (BBolt)       │                         │
│                   │                 │                         │
│                   │ - batchTx       │                         │
│                   │ - readTx        │                         │
│                   │ - concurrentTx  │                         │
│                   └────────┬────────┘                         │
│                            │                                 │
│                   ┌────────▼────────┐                         │
│                   │  WAL + Data File│                         │
│                   └─────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```


## 三、Raft 共识算法源码级实现

### 3.1 Raft 状态机

etcd 使用的 `go-raft` 库实现了经典 Raft 协议。核心状态：

```go
// raft/raft.go - 核心状态定义
type StateType uint

const (
    StateFollower StateType = iota
    StateCandidate
    StateLeader
)

// raft.go - raft 结构体核心字段
type raft struct {
    State           StateType
    Term            uint64
    Vote            uint64
    Lead            uint64
    
    // Log entries
    log             Storage       // 日志存储
    softState       *SoftState
    
    // Election
    electionElapsed int
    heartbeatElapsed int
    electionTimeout int
    heartbeatTimeout int
    
    // Proposal
    proposals       chan *pb.Message
    committed       uint64        // 已提交的最大 index
    applied         uint64        // 已应用的最大 index
    
    // Leader 特有
    replicas        map[uint64]bool
    nextMsgs        map[uint64][]pb.Message
}
```

**状态转换图**：

```
                    ┌─────────────┐
                    │   Follower  │
                    │             │
                    │ 等待 Leader  │
                    │ 心跳/日志    │
                    └──────┬──────┘
                           │ Receive RPC with higher term
                           │ 或 ElectionTimeout
                           ▼
                    ┌─────────────┐
                    │   Candidate │
                    │             │
                    │ 开始选举     │
                    │ 投票给自己   │
                    └──────┬──────┘
                    ┌──────┴──────┐
                    │             │
          获得多数票 │             │ 更高 term 的 Candidate 出现
                    ▼             │
            ┌─────────────┐       │
            │    Leader    │◀──────┘
            │             │
            │ 发送心跳    │
            │ 处理提案    │
            └─────────────┘
```

### 3.2 选举流程源码

```go
// server/etcdserver/raft.go - 选举触发
func (r *raftNode) tick() {
    r.tickMu.Lock()
    r.Tick()  // 调用 go-raft 的 Tick
    r.latestTickTs = time.Now()
    r.tickMu.Unlock()
}

// go-raft/raft.go - stepFollower 处理消息
func (rd *raft) step(m pb.Message) error {
    switch m.Type {
    case pb.MsgHup:
        if rd.state != StateFollower && rd.state != StateCandidate {
            break
        }
        if rd.progress == nil {
            pbutil.MustMarshall(m)
        }
        rd.becomeCandidate()
        
    case pb.MsgProp:
        // ... 提案处理
        
    case pb.MsgApp, pb.MsgAppResp, pb.MsgVote, pb.MsgVoteResp:
        // 日志同步和选举投票
    }
}
```

**选举超时与心跳超时的关系**：

```go
// 配置常量（etcd v3.5 默认值）
// server/config/config.go

// ElectionTick: Leader 在每个 Tick 周期内期望收到多少个心跳
// 通常 ElectionTick = 10, HeartbeatTick = 1
// 即: ElectionTimeout = 10 * HeartbeatInterval = 10 * 500ms = 5s
//     HeartbeatTimeout = 2 * ElectionTimeout = 10s

type Config struct {
    Name             string
    Dir              string
    WalDir           string
    SnapshotCount    uint64        // 默认 10000
    HeartbeatInterval  time.Duration // 默认 100ms
    ElectionTimeout  int           // 默认 10 ticks
    // ...
}
```

### 3.3 提案（Proposal）流程

```go
// server/etcdserver/raft.go - 提案入口
func (r *raftNode) propose(ctx context.Context, c pb.ConfChange) error {
    cc := pb.ConfChangeV2{Context: c.Marshal()}
    return r.proposeCtx(ctx, nil, pb.MsgProp, pb.ConfChangeV2ToEntry(cc))
}

func (r *raftNode) proposeCtx(
    ctx context.Context, 
    done chan<- int, 
    t pb.MessageType, 
    data []byte,
) error {
    select {
    case r.proposec <- pb.Message{Type: t, Data: data, Done: done}:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    case <-r.stopped:
        return ErrStopped
    }
}
```

**写入路径详解**：

```
Client Put("key", "value")
  │
  ├─→ 1. gRPC Handler (etcdserver/api/rpc)
  │     解析 InternalRaftRequest
  │
  ├─→ 2. EtcdServer.Propose()
  │     ├─ 写入 Raft log (MemoryStorage)
  │     └─ 发送给 Leader
  │
  ├─→ 3. Leader: Raft Node.Propose()
  │     ├─ 追加 Entry 到 log
  │     └─ 等待 committed
  │
  ├─→ 4. Raft: 多数派确认后 → committed
  │
  ├─→ 5. EtcdServer.applyEntries()
  │     ├─ 解码 InternalRaftRequest
  │     └─ 调用 applierV3.Apply()
  │
  ├─→ 6. MVCC Store.Write()
  │     ├─ 递增 currentRev
  │     ├─ 写入 treeIndex (BTree)
  │     └─ 写入 BatchTx
  │
  └─→ 7. Backend.BatchTx.Commit()
        ├─ 写入 WAL
        └─ 写入 BBolt DB
```

### 3.4 Raft Log 同步与刷盘

```go
// server/storage/backend/backend.go - WAL 写入
func (b *backend) ForceCommit() {
    b.batchTx.Commit()
}

// BatchTx 的提交流程：
// 1. 将 pending mutations 写入 WAL (Write-Ahead Log)
// 2. WAL fsync
// 3. 将 mutations 写入 BBolt DB
// 4. BBolt tx.Commit()

// server/storage/backend/batch_tx.go
func (tx *batchTxBuffered) commitLocked() {
    // Step 1: 写入 WAL
    tx.unsafeCommit(true)
    
    // Step 2: 写入 BBolt
    tx.db.Batch().Update(func(txn *bolt.Tx) error {
        for bucket, kvs := range tx.pending {
            b := txn.Bucket([]byte(bucket))
            for key, val := range kvs {
                if err := b.Put(key, val); err != nil {
                    return err
                }
            }
        }
        return nil
    })
}
```

> **关键设计**：etcd 的 WAL 和 BBolt 的 WAL 是两层 WAL。外层 WAL 保证 Raft entry 的持久化，内层 BBolt WAL 保证 KV 写入的原子性。


## 四、MVCC 存储引擎深度解析

### 4.1 MVCC 架构总览

MVCC（Multi-Version Concurrency Control）是 etcd 3.x 的核心创新。它让每个 key-value 对拥有多个历史版本，通过 revision 机制实现版本控制。

```
MVCC 三层架构：

┌─────────────────────────────────────────┐
│           MVCC Store                     │
│                                          │
│  ┌──────────┐  ┌──────────────────────┐  │
│  │ treeIndex │  │     BoltDB Backend   │  │
│  │ (内存)   │  │                      │  │
│  │          │  │ Key bucket:           │  │
│  │ BTree     │  │   key → [rev, ver]   │  │
│  │ (32-way)  │  │                      │  │
│  │          │  │ Rev bucket:           │  │
│  │ 快速查找  │  │   rev → key+value    │  │
│  └────┬─────┘  └──────────────────────┘  │
│       │                                  │
│  ┌────▼─────┐                             │
│  │  readTx   │ ← 读事务（无锁，快照隔离）  │
│  │  batchTx  │ ← 写事务（互斥锁）         │
│  └──────────┘                             │
└─────────────────────────────────────────┘
```

### 4.2 Revision 数据结构

```go
// server/storage/mvcc/revision.go
const (
    revBytesLen = 8 + 1 + 8    // 17 bytes: main(8) + '_'(1) + sub(8)
    markedRevBytesLen = revBytesLen + 1  // 18 bytes with tombstone mark
    markBytePosition = markedRevBytesLen - 1
    markTombstone byte = 't'
)

type Revision struct {
    Main int64  // 主版本号：每次事务递增
    Sub  int64  // 子版本号：同一事务内的多次操作递增
}

// Revision 的字节编码：
// Main(8 bytes BE) + '_' + Sub(8 bytes BE)
// 例如: Revision{Main:1, Sub:0} → [0000000000000001]_[0000000000000000]
func RevToBytes(rev Revision, bytes []byte) []byte {
    binary.BigEndian.PutUint64(bytes, uint64(rev.Main))
    bytes[8] = '_'
    binary.BigEndian.PutUint64(bytes[9:], uint64(rev.Sub))
    return bytes
}
```

**为什么需要 Main + Sub 双版本号？**

```
场景：一个事务中 Put 三个 key

Put("user:1", "Alice")    → Revision{Main:5, Sub:0}
Put("user:2", "Bob")      → Revision{Main:5, Sub:1}
Put("user:3", "Charlie")  → Revision{Main:5, Sub:2}

Main=5 表示这三个操作属于同一个事务（原子性）
Sub=0,1,2 表示事务内的操作顺序

好处：
1. 可以精确判断哪些 key 在同一事务中修改
2. Compaction 时可以批量清理
3. Watch 可以返回事务级别的变更通知
```

### 4.3 keyIndex：内存索引结构

```go
// server/storage/mvcc/index.go
type treeIndex struct {
    sync.RWMutex
    tree *btree.BTree[*keyIndex]  // 32路 B+ Tree
    lg   *zap.Logger
}

type keyIndex struct {
    key       []byte
    created   Revision    // 创建时的 revision
    modified  []Revision  // 每次修改的 revision 列表（按时间排序）
}

// BTree 操作：Put(key, rev)
func (ti *treeIndex) Put(key []byte, rev Revision) {
    keyi := &keyIndex{key: key}
    
    ti.Lock()
    defer ti.Unlock()
    
    okeyi, ok := ti.tree.Get(keyi)  // O(log N) 查找
    if !ok {
        // 新 key：创建 keyIndex
        keyi.put(ti.lg, rev.Main, rev.Sub)
        ti.tree.ReplaceOrInsert(keyi)
        return
    }
    // 已有 key：追加到 modified 列表
    okeyi.put(ti.lg, rev.Main, rev.Sub)
}
```

**BTree 32 路设计的权衡**：

```
B-Tree Fanout = 32

高度 = log_32(N)

N=100万 → 高度 ≈ 3
N=1亿 → 高度 ≈ 4
N=10亿 → 高度 ≈ 5

这意味着：
- 任意一次 Get/Put/Range 最多 3-5 次内存指针跳转
- 完全在 CPU L3 Cache 内（每个 keyIndex ~200 bytes）
- 无磁盘 IO，纯内存操作
```

### 4.4 Get 操作的完整流程

```go
// server/storage/mvcc/index.go
func (ti *treeIndex) Get(key []byte, atRev int64) (modified, created Revision, ver int64, err error) {
    ti.RLock()
    defer ti.RUnlock()
    
    keyi := &keyIndex{key: key}
    keyi = ti.keyIndex(keyi)  // BTree 查找 O(log N)
    if keyi == nil {
        return Revision{}, Revision{}, 0, ErrRevisionNotFound
    }
    
    // 二分查找找到 atRev 时刻的 revision
    return keyi.get(ti.lg, atRev)
}

// keyIndex.get(): 在 modified 列表中二分查找
func (ki *keyIndex) get(lg *zap.Logger, atRev int64) (modified, created Revision, ver int64, err error) {
    // 二分查找：找到最大的 rev <= atRev
    i := sort.Search(len(ki.modified), func(i int) bool {
        return ki.modified[i].Main > atRev
    })
    
    if i == 0 {
        return Revision{}, ki.created, 0, ErrRevisionNotFound
    }
    
    if i > 0 {
        m := ki.modified[i-1]
        if m.IsTombstone() {
            return m.Previous, ki.created, 0, nil  // 已被删除
        }
        return m.Revision, ki.created, m.Version, nil
    }
    
    return ki.modified[len(ki.modified)-1], ki.created, 0, nil
}
```

### 4.5 Put/Delete 操作流程

```go
// server/storage/mvcc/store.go - Write 事务
func (s *store) Write(trace *traceutil.Trace) TxnWrite {
    s.mu.Lock()
    tx := s.b.BatchTx()
    tx.LockOutsideApply()
    return &txnWrite{
        trace: trace,
        s:     s,
        tx:    tx,
        buf:   make([]*mvccpb.KeyValue, 0, 256),
    }
}

// txnWrite.Put()
func (tw *txnWrite) Put(key, value []byte) {
    rev := tw.s.newRev()  // 获取新 revision
    
    // 1. 检查 key 是否存在
    oldRev, created, ver, err := tw.s.kvindex.Get(key, rev.Main-1)
    
    // 2. 更新 treeIndex
    if err == nil {
        // Key 已存在：追加到 modified 列表
        tw.s.kvindex.Put(key, rev)
    } else {
        // Key 不存在：创建新的 keyIndex
        tw.s.kvindex.Put(key, rev)
    }
    
    // 3. 写入 BBolt Key bucket
    // key_bucket: key → [rev_bytes, ver_bytes]
    tw.unsafePut(key, value)
    
    // 4. 写入 Rev bucket (用于 compaction 后的历史查询)
    // rev_bucket: rev_bytes → [key_len, key, value_len, value]
    tw.writeRevBytes()
    
    // 5. 加入 buf 用于批量写入 Rev bucket
    tw.buf = append(tw.buf, kv)
}

// txnWrite.Commit()
func (tw *txnWrite) Commit(isRetry bool) {
    // 批量写入 Rev bucket
    tw.flush()
    
    // 递增 currentRev
    tw.s.updateCurrentRev()
    
    // 解锁
    tw.tx.Unlock()
}
```

### 4.6 Range 查询：前缀扫描

```go
// server/storage/mvcc/index.go
func (ti *treeIndex) Range(key, end []byte, atRev int64, limit int, withTotalCount bool) (
    keys [][]byte, modifies, creates []Revision, versions []int64, totalCount int,
) {
    ti.RLock()
    defer ti.RUnlock()
    
    keyi, endi := &keyIndex{key: key}, &keyIndex{key: end}
    
    // BTree 区间扫描：AscendGreaterOrEqual
    ti.tree.AscendGreaterOrEqual(keyi, func(item *keyIndex) bool {
        if len(endi.key) > 0 && !item.Less(endi) {
            return false  // 超出范围，停止遍历
        }
        
        // 对每个 key，获取 atRev 时刻的值
        if rev, _, _, err := item.get(ti.lg, atRev); err == nil {
            keys = append(keys, item.key)
            modifies = append(modifies, rev)
        }
        
        // 检查是否达到 limit
        if limit > 0 && len(keys) >= limit {
            return false
        }
        return true
    })
    
    return keys, modifies, creates, versions, totalCount
}
```


## 五、Watch 机制深度解析

### 5.1 Watch 架构设计

```
Watch 系统的核心挑战：
1. 如何高效通知成千上万的 watcher？
2. 慢 watcher 如何不影响快 watcher？
3. Watch 风暴如何防止？

解决方案：三级分层架构

┌─────────────────────────────────────────────────┐
│  Client Watch Requests                           │
│  (gRPC streaming)                                │
├─────────────────────────────────────────────────┤
│  WatchStream (per connection)                    │
│  ├─ watchers map[WatchID]*watcher               │
│  └─ ch chan<- WatchResponse (buffered=128)      │
├─────────────────────────────────────────────────┤
│  watchableStore                                  │
│  ├─ synced watcherGroup    (追上了的)           │
│  ├─ unsynced watcherGroup  (落后的)             │
│  ├─ victims []watcherBatch   (被阻塞的)         │
│  └─ victimc chan struct{}   (受害者唤醒信号)    │
├─────────────────────────────────────────────────┤
│  syncWatchersLoop()  (每 100ms 执行)             │
│  syncVictimsLoop()   (当 victimc 有信号时)       │
└─────────────────────────────────────────────────┘
```

### 5.2 Watch 创建流程

```go
// server/storage/mvcc/watchable_store.go
func (s *watchableStore) watch(key, end []byte, startRev int64, id WatchID, 
    ch chan<- WatchResponse, fcs ...FilterFunc) (*watcher, cancelFunc) {
    
    wa := &watcher{
        key:      key,
        end:      end,
        startRev: startRev,
        minRev:   startRev,
        id:       id,
        ch:       ch,
        fcs:      fcs,
    }
    
    s.mu.Lock()
    s.revMu.RLock()
    
    // 关键判断：这个 watcher 是否已经同步
    synced := startRev > s.store.currentRev || startRev == 0
    
    if synced {
        // 新 watcher 或从头开始 → 放入 synced 组
        wa.minRev = s.store.currentRev + 1
        if startRev > wa.minRev {
            wa.minRev = startRev
        }
        s.synced.add(wa)
    } else {
        // 回放历史 → 放入 unsynced 组（慢 watcher）
        slowWatcherGauge.Inc()
        s.unsynced.add(wa)
    }
    
    s.revMu.RUnlock()
    s.mu.Unlock()
    
    watcherGauge.Inc()
    return wa, func() { s.cancelWatcher(wa) }
}
```

### 5.3 Watcher 同步循环

```go
// server/storage/mvcc/watchable_store.go
func (s *watchableStore) syncWatchersLoop() {
    defer s.wg.Done()
    t := time.NewTicker(watchResyncPeriod) // 100ms
    defer t.Stop()
    
    for {
        select {
        case <-t.C:
            s.syncWatchers()
        case <-s.stopc:
            return
        }
    }
}

func (s *watchableStore) syncWatchers() {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    // 1. 从 synced 组取出最多 512 个 watcher
    watchers := s.synced.batch(len(s.synced))
    if len(watchers) == 0 {
        return
    }
    
    // 2. 对每个 watcher，从 store 中获取已发生的 events
    s.revMu.RLock()
    curRev := s.store.currentRev
    s.revMu.RUnlock()
    
    for _, wa := range watchers {
        // 从 key 到 end 范围查询 atRev 时刻的变化
        revs := s.store.kvindex.Revisions(wa.key, wa.end, curRev, 0, false)
        
        // 3. 发送到 watcher 的 channel
        resp := WatchResponse{
            WatchID:  wa.id,
            Revision: curRev,
            Events:   convertToEvents(revs),
        }
        
        // 关键：如果 channel 满了，这个 watcher 变成 victim
        select {
        case wa.ch <- resp:
            // 成功发送
        default:
            // Channel 满了！标记为 victim
            wa.victim = true
            s.victims = append(s.victims, watcherBatch{wa: struct{}{}})
            s.victimc <- struct{}{}
        }
    }
}
```

### 5.4 Victim 机制：防止 Watch 风暴

```
Watch 风暴场景：
- 10000 个 watcher 同时 watch "/" 前缀
- 一条 Put 产生 10000 个事件
- 如果逐个发送，第一个 watcher 的 channel 很快填满
- 后面的 watcher 全部被阻塞 → 内存暴涨

etcd 的解决方案：

1. 批量发送：每次最多同步 512 个 watcher
2. Victim 标记：channel 满的 watcher 被标记为 victim
3. 延迟处理：victim 在下一个 syncVictimsLoop 中被处理
4. 逐步追赶：每次只给 victim 发送少量事件，避免再次阻塞

victim 处理流程：
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  syncVictims  │────▶│  从 victim   │────▶│  发送事件    │
│  Loop 执行    │     │  batch 中取  │     │  (有限数量)  │
│              │     │  最多 512 个  │     │              │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                          channel 仍满？
                                                 │
                                        ┌────────▼────────┐
                                        │  重新放回 victims │
                                        │  等待下次循环     │
                                        └─────────────────┘
```

```go
func (s *watchableStore) syncVictimsLoop() {
    defer s.wg.Done()
    
    for {
        select {
        case <-s.victimc:
            s.syncVictims()
        case <-s.stopc:
            return
        }
    }
}

func (s *watchableStore) syncVictims() {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    victims := s.victims
    s.victims = nil
    
    for _, victimBatch := range victims {
        for wa := range victimBatch {
            // 只发送有限的 events，防止再次阻塞
            events := s.fetchLimitedEvents(wa)
            
            select {
            case wa.ch <- WatchResponse{Events: events}:
                wa.victim = false
                s.synced.add(wa)  // 重新放回 synced
            default:
                // 仍然满了，放回 victims
                victimBatch[wa] = struct{}{}
            }
        }
    }
}
```

### 5.5 Watch 事件类型

```go
// api/mvccpb/kv.proto
message Event {
    enum EventType {
        PUT = 0;        // 创建或更新
        DELETE = 1;     // 删除
    }
    
    EventType type;
    KeyValue kvs;
    KeyValue prev_kvs;  // PUT 时有旧值，DELETE 时有被删值
}

message KeyValue {
    bytes key = 1;
    bytes value = 2;
    int64 create_revision = 3;
    int64 mod_revision = 4;
    int64 version = 5;
    int64 lease = 6;
}
```


## 六、Lease 租约机制

### 6.1 Lease 数据结构

```go
// server/lease/lease.go
type Lease struct {
    ID           LeaseID      // 租约 ID
    ttl          int64        // 总 TTL（秒）
    remainingTTL int64        // 剩余 TTL（续期时更新）
    
    expiryMu     sync.RWMutex
    expiry       time.Time    // 过期时间点
    
    mu           sync.RWMutex
    itemSet      map[LeaseItem]struct{}  // 绑定的 key 集合
    revokec      chan struct{}           // 撤销通知通道
}

type LeaseItem struct {
    Key string
}
```

### 6.2 Lease 生命周期

```
Grant Lease(TTL=300)
  │
  ├─→ 创建 Lease 对象
  ├─→ 设置 expiry = now + 300s
  ├─→ 持久化到 BBolt (lease bucket)
  └─→ 返回 LeaseID
  │
  ├─→ Renew Lease(ID)  (每 60s 调用一次)
  │   ├─→ 更新 expiry = now + remainingTTL
  │   └─→ 不写磁盘（内存操作）
  │
  ├─→ Attach Key → Lease
  │   ├─→ lease.itemSet[key] = {}
  │   └─→ 反向索引：key → leaseID
  │
  ├─→ 正常续期 → Lease 保持有效
  │
  └─→ Revoke / Expire
      ├─→ 从 itemSet 中获取所有 key
      ├─→ 批量 DeleteRange(keys)
      └─→ 清理 Lease 对象
```

### 6.3 Lease Manager 源码

```go
// server/lease/lessor.go
type lessor struct {
    mu sync.RWMutex
    
    leaseMap    map[LeaseID]*Lease     // LeaseID → Lease
    itemMap     map[LeaseItem]LeaseID  // LeaseItem → LeaseID (反向索引)
    
    demotec     chan struct{}          // demoted 信号
    
    rd          RangeDeleter           // 用于删除过期 lease 绑定的 key
    cp          Checkpointer           // 用于 checkpoint 剩余 TTL
    
    b           backend.Backend        // 持久化
    expiredC    chan []*Lease          // 过期 lease 通道
    
    // 速率控制
    leaseRevokeRate   int  // 每秒最多撤销 1000 个 lease
    checkpointInterval time.Duration  // 默认 5 分钟
}

func (l *lessor) Grant(id LeaseID, ttl int64) (*Lease, error) {
    l.mu.Lock()
    defer l.mu.Unlock()
    
    lease := NewLease(id, ttl)
    lease.refresh(time.Duration(ttl) * time.Second)
    
    l.leaseMap[id] = lease
    l.persistTo(lease)  // 写入 BBolt
    
    return lease, nil
}

func (l *lessor) Renew(id LeaseID) (int64, error) {
    l.mu.Lock()
    defer l.mu.Unlock()
    
    lease, ok := l.leaseMap[id]
    if !ok {
        return 0, ErrLeaseNotFound
    }
    
    if l.isDemoted() {
        return 0, ErrLeaseNotPrimary
    }
    
    // 续期：延长 expiry
    lease.refresh(time.Duration(lease.getRemainingTTL()) * time.Second)
    
    return lease.ttl, nil
}
```

### 6.4 Lease 过期检测

```go
// server/lease/lessor.go
func (l *lessor) start() {
    // 启动过期检测协程
    go l.loop()
}

func (l *lessor) loop() {
    for {
        select {
        case <-l.stopC:
            return
        case <-time.After(1 * time.Second):
            // 每秒检查一次过期 lease
            l.mu.RLock()
            var expired []*Lease
            
            // 按 expiry 排序的 heap，检查头部
            for {
                if len(l.leaseHeap) == 0 {
                    break
                }
                top := l.leaseHeap[0]
                if top.Remaining() > 0 {
                    break  // 没有更多过期的
                }
                
                expired = append(expired, top)
                heap.Pop(l.leaseHeap)  // 弹出
            }
            l.mu.RUnlock()
            
            if len(expired) > 0 {
                l.expiredC <- expired
            }
        }
    }
}

// 当 lease 过期时：
// 1. ExpiredLeasesC() 收到 []*Lease
// 2. 调用 rd (RangeDeleter) 删除所有绑定的 key
// 3. 从 leaseMap 中移除
```

### 6.5 Lease Checkpoint：跨 Leader 选举保持 TTL

```
问题：
- Leader 选举期间，新 Leader 不知道旧 Leader 上各 lease 的 remainingTTL
- 如果直接用 full TTL，可能导致 lease 意外提前过期

解决方案：Lease Checkpoint
- 定期（默认 5 分钟）将 remainingTTL 写入共识日志
- Leader 选举后，新 Leader 从 checkpoint 恢复
- 使用 checkpoint 中的 remainingTTL 而非 full TTL

流程：
┌─────────────────────────────────────────────┐
│ 每 5 分钟：                                  │
│ 1. Leader 收集所有 lease 的 remainingTTL    │
│ 2. 批量写入 LeaseCheckpointRequest           │
│ 3. 通过 Raft 共识持久化                      │
│ 4. 新 Leader 选举后从 meta bucket 恢复       │
└─────────────────────────────────────────────┘

// checkpoint 的批量优化
const (
    maxLeaseCheckpointBatchSize = 1000   // 每次最多 1000 个 lease
    leaseCheckpointRate         = 1000   // 每秒最多 1000 个 checkpoint
)
```


## 七、Compaction 与 Defrag 机制

### 7.1 Compaction：清理历史版本

```
为什么需要 Compaction？

MVCC 会为每个 key 保留所有历史版本。如果不清理：
- 存储无限增长
- Range 查询变慢（需要遍历所有版本）
- Watch 回放历史数据过多

Compaction 流程：

Step 1: 客户端请求 compaction at revision R
Step 2: etcd 将 scheduledCompact 写入 meta bucket
Step 3: 后台 goroutine 检测到 scheduledCompact
Step 4: treeIndex.Compact(R) → 删除 R 之前的所有 revision
Step 5: 批量从 Key bucket 和 Rev bucket 删除旧数据
Step 6: 标记 finishedCompact = R
```

```go
// server/storage/mvcc/kvstore.go
func (s *store) compact(rev int64) error {
    // 1. 获取需要保留的 revision
    keep := s.kvindex.Compact(rev)  // 返回 rev >= compactRev 的 keyIndex
    
    // 2. 写入 meta bucket: scheduledCompact = rev
    // 3. 后台 goroutine 执行实际删除
    s.fifoSched.Schedule(func(ctx context.Context) {
        s.compactBarrier(ctx, ch)
        
        s.mu.Lock()
        defer s.mu.Unlock()
        
        // 4. 从 Key bucket 删除旧版本
        tx := s.b.BatchTx()
        tx.LockOutsideApply()
        unsafeCompact(tx, s.compactMainRev, rev, keep)
        tx.Unlock()
        
        // 5. 更新 compactMainRev
        s.updateCompactRev(rev)
    })
    
    return nil
}

// 实际删除的 SQL 等价操作：
// DELETE FROM key_bucket WHERE rev < compactRev AND rev NOT IN (keep)
// DELETE FROM rev_bucket WHERE rev < compactRev AND rev NOT IN (keep)
```

### 7.2 Compaction 的防死锁机制

```go
// server/storage/mvcc/kvstore.go - compactBarrier
func (s *store) compactBarrier(ctx context.Context, ch chan struct{}) {
    if ctx == nil || ctx.Err() != nil {
        // 修复 mvcc 中的死锁问题 (PR #11817)
        // compaction 和 apply snapshot 由 raft 序列化，不会同时发生
        s.mu.Lock()
        f := schedule.NewJob("kvstore_compactBarrier", func(ctx context.Context) {
            s.compactBarrier(ctx, ch)
        })
        s.fifoSched.Schedule(f)
        s.mu.Unlock()
        return
    }
    close(ch)  //  barrier 完成，通知等待者
}
```

### 7.3 Defrag：碎片整理

```
Compaction 之后发生了什么？

Compaction 只是逻辑删除（标记为无效），物理空间并未释放。
BBolt 的页面变为 free 状态，但文件体积不变。

Defrag 的作用：
1. 创建一个全新的 BBolt DB
2. 只拷贝活跃数据到新 DB
3. 原子替换文件

Defrag 流程：

┌─────────────────────────────────────────────────┐
│ 1. 创建临时文件 (etcd.defrag.*)                  │
│ 2. 从原 DB 读取所有活跃数据                       │
│ 3. 写入临时文件（紧凑布局，无碎片）               │
│ 4. 关闭原 DB                                     │
│ 5. 原子 mv 临时文件 → 原文件名                   │
│ 6. 重新打开 BBolt DB                             │
│ 7. 通知 Raft 节点完成 defrag                      │
└─────────────────────────────────────────────────┘
```

```go
// 伪代码：defrag 核心逻辑
func (b *backend) Defrag() error {
    // 1. 确保自己是 leader
    if !b.isLeader() {
        return ErrDefragOnNonLeader
    }
    
    // 2. 创建临时文件
    tmpPath := b.path + ".defrag"
    tmpDB, err := bolt.Open(tmpPath, 0600, &bolt.Options{
        NoSync:  true,   // defrag 期间不 sync，更快
        NoFreelistSync: true,
    })
    
    // 3. 从原 DB 读取所有活跃数据
    b.db.View(func(tx *bolt.Tx) error {
        return tx.ForEach(func(bucketName []byte, bucket *bolt.Bucket) error {
            cursor := bucket.Cursor()
            for k, v := cursor.First(); k != nil; k, v = cursor.Next() {
                // 只拷贝活跃数据
                if !b.isCompacted(bucketName, k) {
                    tmpBucket.Put(k, v)
                }
            }
            return nil
        })
    })
    
    // 4. 关闭原 DB，原子替换
    b.Close()
    os.Rename(tmpPath, b.path)
    
    // 5. 重新打开
    b.db, _ = bolt.Open(b.path, 0600, &bolt.Options{
        InitialMmapSize: b.cfg.MmapSize,
    })
    
    return nil
}
```

### 7.4 Compaction vs Defrag 的运维策略

```bash
# etcd 推荐的 compaction 间隔
# 根据 QPS 和数据增长率计算

# 公式：
# compaction_interval = min_retention_period
# 其中 min_retention_period = max(watch_history, hash_check_interval)

# 典型配置：
# --auto-compaction-mode=periodic
# --auto-compaction-retention=1h    # 每小时 compaction
# 
# 或：
# --auto-compaction-mode=revision
# --auto-compaction-retention=10000 # 保留最近 10000 个 revision

# defrag 频率：
# 建议在低峰期执行，因为 defrag 期间 leader 不可用
# 一般每周 1-2 次，或在磁盘使用率 > 80% 时执行

# 生产环境脚本示例：
# 1. 先 compaction
# 2. 等待 compaction 完成
# 3. 在低峰期 defrag
# 4. 验证数据完整性
```


## 八、BoltDB 持久化层深度

### 8.1 BBolt 存储布局

```
etcd 使用 BBolt（BoltDB 的 fork）作为持久化引擎。

BBolt 文件布局：

┌───────────────────────────────────────────────────────┐
│ Page 0: Meta0 (备份)                                   │
│ Page 1: Meta1 (主)                                     │
│ Page 2-N: Free pages (空闲)                             │
│ N+1-M: Allocated pages (数据页)                        │
└───────────────────────────────────────────────────────┘

Meta page 结构：
┌─────────────────────────┐
│ magic: 0xED0CDA2ED      │
│ version: 3              │
│ page_size: 4096         │
│ flags: 2                │
│ root: RootBucket        │ ← 指向根 bucket 的 page ID
│ pgid: 2                 │ ← 根 bucket 所在页
│ txid: 12345             │ ← 最后一次提交的 tx id
│ checksum: xxx           │
└─────────────────────────┘
```

### 8.2 etcd 的 Bucket 设计

```go
// server/storage/schema/schema.go

// etcd 使用两个主要 bucket：
// 1. Key bucket: 存储 key → [revision, version] 的映射
// 2. Rev bucket: 存储 revision → key+value 的完整数据

// 此外还有 meta bucket 存储系统元数据：
// - meta: compactRevision, finishedCompact, scheduledCompact
// - lease: 所有 lease 的持久化状态
// - membership: 集群成员信息
// - auth: 认证授权信息

// Key bucket 布局：
// ┌──────────────────────────────────────────┐
// │ Bucket: "key"                             │
// │                                          │
// │ key: "user:1"                             │
// │ value: [17 bytes revision][4 bytes ver]  │
// │         ↑ rev_bytes (Main_Sub)           │
// │         ↑ version (int32 BE)             │
// └──────────────────────────────────────────┘

// Rev bucket 布局：
// ┌──────────────────────────────────────────┐
// │ Bucket: "rev"                             │
// │                                          │
// │ key: [17 bytes revision]                  │
// │ value: [4 bytes key_len][key][4 bytes    │
// │        val_len][value]                    │
// └──────────────────────────────────────────┘
```

### 8.3 事务模型：读写分离

```go
// backend 提供三种事务类型：

// 1. BatchTx (写事务) - 互斥锁
//    所有写操作通过 batchTxBuffered 缓冲
//    默认配置：batchLimit=10000, batchInterval=100ms
type batchTxBuffered struct {
    tx      *bolt.Tx        // 底层的 bolt transaction
    buf     map[string]map[string][]byte  // 缓冲
    locks   []RLocker       // 需要的锁
}

// 2. ReadTx (读事务) - 阻塞式
//    等待 batchTx 刷新后才可读
type readTx struct {
    tx      *bolt.Tx
    buf     *txReadBuffer   // 读取 batchTx 的缓冲区
}

// 3. ConcurrentReadTx (并发读) - 非阻塞 ★核心优化★
//    读取 batchTx 缓冲区中已 commit 的数据
//    不需要等待写事务释放锁
type concurrentReadTx struct {
    readTx         readTx
    metaReadTx     readTx
    bufVersion     uint64  // 缓冲区版本号
}
```

**ConcurrentReadTx 的设计精髓**：

```
传统方案：
  Writer Lock → Write → Unlock
  Reader Lock → Read → Unlock
  读写互斥 → 高 QPS 下严重瓶颈

etcd 方案：
  Writer: 写入 batchTxBuffered.buf (内存)
  Reader: 从 concurrentReadTx 读取
          ├─ 先读 buf (已 commit 的写操作)
          └─ 再读 bolt.Tx (持久化的数据)
  读写完全并行！

时序图：
  T0: Writer 开始 batchTx
  T1: Writer buf["key"] = "value"  (内存操作)
  T2: Reader 开始 concurrentReadTx
  T3: Reader 读 buf → 找到 "value" ✓
  T4: Writer Commit → 刷盘
  T5: Reader 读到持久化数据 ✓

关键：Reader 在 T3 就能读到 T1 的写入，
      无需等待 T4 的磁盘刷盘！
```

### 8.4 Backend 配置参数

```go
type BackendConfig struct {
    Path               string           // 数据文件路径
    BatchInterval      time.Duration    // 默认 100ms
    BatchLimit         int              // 默认 10000
    BackendFreelistType  bolt.FreelistType  // hashmap (默认)
    MmapSize           uint64           // 默认 10GB
    UnsafeNoFsync      bool             // 危险！仅测试用
    Mlock              bool             // 锁定内存防 swap
    Timeout            time.Duration    // 文件锁超时
}

// 关键参数调优：
// BatchInterval: 越小延迟越低，但 fsync 越频繁
//   推荐: 100ms (默认)
// BatchLimit: 越大吞吐越高，但延迟也越大
//   推荐: 10000 (默认)
// MmapSize: 初始 mmap 大小，设大可减少写者阻塞读者
//   推荐: 10GB (默认)，数据量大时增大
```


## 九、Kubernetes 中的 etcd 深度集成

### 9.1 K8s API Server 与 etcd 的交互

```
K8s API Server → etcd 的数据流：

Pod 创建流程：
1. kubectl create -f pod.yaml
2. API Server 接收请求 → 鉴权 → 准入控制
3. API Server 序列化 Pod 为 JSON → 写入 etcd
   PUT /registry pods/default/my-pod
   Value: {"apiVersion":"v1","kind":"Pod",...}
4. etcd Raft 共识 → 持久化
5. API Server 收到 etcd 响应 → 返回 kubectl
6. kubelet 通过 Watch /registry/pods 感知新 Pod
7. kubelet 调度容器

etcd 中的数据模型映射：
┌─────────────────────────────────────────────────┐
│ etcd Prefix          │ K8s Resource              │
├──────────────────────┼───────────────────────────┤
│ /registry/pods/      │ Pod                       │
│ /registry/services/  │ Service                   │
│ /registry/deployments/│ Deployment               │
│ /registry/configmaps/ │ ConfigMap                 │
│ /registry/secrets/   │ Secret                    │
│ /registry/nodes/     │ Node                      │
│ /registry/events/    │ Event                     │
│ /registry/leases/    │ EndpointSlice Lease       │
│ /registry/endpoints/ │ Endpoint                  │
│ /registry/namespaces/│ Namespace                 │
└─────────────────────────────────────────────────┘
```

### 9.2 etcd 在 K8s 中的关键用途

```go
// 1. 配置存储（最主要用途）
// 所有 K8s 资源对象存储在 etcd 中
// 数据量估算：1000 Node 集群 ≈ 10万 objects ≈ 500MB

// 2. Lease 用于 Leader Election
// K8s 的 LeaderElection 基于 etcd Lease 实现
type LeasedResourceLock struct {
    leaseClient clientset.Interface
    namespace   string
    lockName    string
    identity    string
    leaseDuration time.Duration
    renewDeadline   time.Duration
    retryPeriod     time.Duration
}

// Leader 每 leaseDuration 时间内必须 renew 一次
// 如果超过 renewDeadline 还没 renew，新 Leader 竞选

// 3. Watch 驱动 Controller Reconciliation
// 每个 Controller (Deployment Controller, ReplicaSet Controller...)
// 通过 Watch 监听相关资源变化，触发 reconcile 循环

// 4. Distributed Lock
// +k8s.io/client-go/util/flowcontrol 使用 etcd lease 实现 rate limiter
```

### 9.3 etcd 性能与 K8s 规模的关系

```
K8s 集群规模 vs etcd 要求：

┌──────────────┬───────────┬───────────┬───────────────┐
│ Node 数量    │ etcd 大小 │ 推荐 SSD  │ 预期 QPS      │
├──────────────┼───────────┼───────────┼───────────────┤
│ < 500        │ < 200MB   │ 任何 SSD  │ < 50          │
│ 500-2500     │ 200-500MB │ NVMe SSD  │ < 100         │
│ 2500-5000    │ 500MB-1GB │ NVMe SSD  │ < 150         │
│ > 5000       │ > 1GB     │ NVMe SSD  │ < 200         │
└──────────────┴───────────┴───────────┴───────────────┘

关键性能指标：
- etcd 延迟 P99 < 50ms（含网络 RTT）
- 磁盘 IOPS > 5000（SSD）
- 网络 RTT < 10ms（同机房）
- 磁盘使用率 < 80%（触发 compaction）

etcd 慢查询告警：
--warning-applied-duration=500ms  (默认)
--alert-during-duration=1s
```

### 9.4 etcd 快照与备份

```bash
# etcdctl snapshot save
etcdctl snapshot save /backup/etcd-snapshot-$(date +%Y%m%d).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/ssl/etcd/ca.crt \
  --cert=/etc/ssl/etcd/healthcheck-client.crt \
  --key=/etc/ssl/etcd/healthcheck-client.key

# 快照恢复
etcdctl snapshot restore /backup/etcd-snapshot.db \
  --name=etcd-node-1 \
  --initial-cluster=etcd-node-1=http://10.0.0.1:2380 \
  --data-dir=/var/lib/etcd-from-snapshot

# 快照内部结构验证
etcdutl snapshot status /backup/etcd-snapshot.db \
  --endpoints=https://127.0.0.1:2379
  
# 输出示例：
# Cluster ID: 1234567890
# Commit: 12345678
# Total key-value pairs: 45678
# Database size: 156 MB
# Hash: 3216549876
```


## 十、广告系统中的 etcd 应用场景

### 10.1 DSP 系统中的 etcd 应用

```
在广告 DSP 平台中，etcd 承担以下核心角色：

┌─────────────────────────────────────────────────────────────┐
│                    DSP Architecture                          │
│                                                              │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐            │
│  │ Bid       │    │ Ad        │    │ User      │            │
│  │ Engine    │    │ Serving   │    │ Profile   │            │
│  │ (Go)      │    │ (Go)      │    │ (Go)      │            │
│  └─────┬─────┘    └─────┬─────┘    └─────┬─────┘            │
│        │                │                │                   │
│        └────────┬───────┴────────────────┘                   │
│                 │                                             │
│        ┌────────▼────────┐                                    │
│        │    etcd Cluster  │                                    │
│        │                 │                                    │
│        │ • 动态配置       │ ← campaign budget, targeting       │
│        │ • 服务发现       │ ← bid engine 实例注册              │
│        │ • 分布式锁       │ ← 频控锁 (frequency cap)           │
│        │ • 会话状态       │ ← 用户 session, device fingerprint │
│        │ • 开关控制       │ ← feature flag (灰度发布)          │
│        └─────────────────┘                                    │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 具体使用模式

```go
// 1. 动态配置下发
// 场景：运营调整出价策略，无需重启服务

type BidConfig struct {
    BaseBid       float64   `json:"base_bid"`
    FloorPrice    float64   `json:"floor_price"`
    CapFrequency  int       `json:"cap_frequency"`  // 每用户每日最大展示次数
    Targeting     string    `json:"targeting"`      // jsonpath 条件
}

// 启动时 watch 配置 key
func LoadBidConfig(ctx context.Context, client *clientv3.Client) (*BidConfig, context.CancelFunc) {
    resp, err := client.Get(ctx, "/dsp/config/bid_strategy")
    if err != nil {
        panic(err)
    }
    
    var config BidConfig
    json.Unmarshal(resp.Kvs[0].Value, &config)
    
    // 启动 watcher 监听变化
    ctx, cancel := context.WithCancel(ctx)
    go func() {
        for {
            watchResp := client.Watch(ctx, "/dsp/config/bid_strategy", 
                clientv3.WithPrevKV())
            for wresp := range watchResp {
                for _, ev := range wresp.Events {
                    if ev.Type == mvccpb.PUT {
                        json.Unmarshal(ev.Kv.Value, &config)
                        log.Info("bid config updated", zap.Any("config", config))
                    }
                }
            }
        }
    }()
    
    return &config, cancel
}

// 2. 服务发现
// 场景：bid engine 水平扩展，ad serving 需要动态发现实例

func RegisterInstance(client *clientv3.Client, instanceID string, addr string, ttl int64) *lease.LeaseKeepAlive {
    // 注册到 etcd
    _, err := client.Put(context.Background(), 
        fmt.Sprintf("/dsp/instances/%s", instanceID),
        addr,
        clientv3.WithLease(leaseID),
    )
    
    // 保持租约
    keepAlive, err := client.KeepAlive(context.Background(), leaseID)
    return keepAlive
}

func DiscoverInstances(client *clientv3.Client) ([]string, error) {
    resp, err := client.Get(context.Background(), 
        "/dsp/instances/", clientv3.WithPrefix())
    
    addrs := make([]string, 0, len(resp.Kvs))
    for _, kv := range resp.Kvs {
        addrs = append(addrs, string(kv.Value))
    }
    return addrs, nil
}

// 3. 分布式锁（频控）
// 场景：同一用户对同一广告主的展示频率限制

func AcquireFrequencyLock(client *clientv3.Client, userID string, advertiserID string, ttl int64) (bool, error) {
    key := fmt.Sprintf("/dsp/freq/%s/%s", userID, advertiserID)
    
    // 尝试获取锁，设置 TTL
    resp, err := client.Put(context.Background(), key, "locked", 
        clientv3.WithLease(leaseID))
    
    if resp.Header.Revision > 0 {
        return true, nil  // 获取成功
    }
    return false, nil  // 已有锁，被限制
}

// 4. Feature Flag（灰度发布）
// 场景：新竞价策略只对 10% 流量生效

func IsFeatureEnabled(client *clientv3.Client, feature string, ratio int) bool {
    resp, err := client.Get(context.Background(), 
        fmt.Sprintf("/dsp/features/%s", feature))
    
    if err != nil || len(resp.Kvs) == 0 {
        return false
    }
    
    // ratio 是 0-100 的比例
    // 用 userID hash 决定是否在范围内
    hash := hash(userID) % 100
    return hash < ratio
}
```

### 10.3 etcd 在广告系统中的容量规划

```
广告 DSP 平台的 etcd 容量规划：

预估数据量：
- 广告活动配置：10K campaigns × 2KB = 20MB
- 创意素材元数据：100K creatives × 1KB = 100MB
- 用户频控 key：1M users × 10 advertisers × 50 bytes = 500MB
- 服务注册实例：100 instances × 100 bytes = 10KB
- 临时会话数据：50K sessions × 500 bytes = 25MB

总计：≈ 700MB（含历史版本膨胀 3x）≈ 2.1GB

容量规划建议：
- etcd 配额：--quota-backend-bytes=2GB (默认)
- 预留 20% 余量 → 实际可用 1.6GB
- 需要调整配额或增加 compaction 频率
- 考虑将频控数据迁移到 Redis（更适合高频读写）
```


## 十一、生产排障指南

### 11.1 常见问题与排查

#### 问题 1：etcd 磁盘使用率持续上涨

```
症状：
- etcd 数据文件持续增长
- compaction 后磁盘空间不释放
- P99 延迟升高

根因分析：
1. Compaction 未执行或频率太低
2. Defrag 未执行（compaction 只逻辑删除，物理空间需 defrag 释放）
3. Watch 历史 retention 过长

排查命令：
$ etcdctl endpoint status --write-out=table
+----------------+------------------+---------+---------+-----------+------------+
|    ENDPOINT    |        ID        | VERSION | DB SIZE | IS LEADER | RAFT TERM  |
+----------------+------------------+---------+---------+-----------+------------+
| 127.0.0.1:2379 | 8e9e05c52164694d |  3.5.17 |  2.1 GB |    true   |   12345678 |
+----------------+------------------+---------+---------+-----------+------------+

$ etcdctl alarm list
# 检查是否有 db size 告警

$ etcdctl member list --write-out=table
# 检查各成员状态

解决方案：
# 1. 手动触发 compaction
$ etcdctl compact <revision>

# 2. 在低峰期执行 defrag
$ etcdctl defrag

# 3. 调整自动 compaction 策略
# --auto-compaction-mode=periodic
# --auto-compaction-retention=1h

# 4. 如果数据量过大，考虑增加 quota
# --quota-backend-bytes=4294967296  # 4GB
```

#### 问题 2：Leader 频繁切换

```
症状：
- etcdctl endpoint status 看到 leader 频繁变化
- 客户端收到 NotLeader 错误
- 提案延迟飙升

根因分析：
1. 磁盘 IO 不稳定（SSD 退化/磁盘满载）
2. 网络分区/高延迟
3. GC 停顿（Go runtime）
4. 请求超时导致 leader 选举

排查：
$ journalctl -u etcd --since "1 hour ago" | grep -i "took"
# 查看 slow request 日志

$ etcdctl endpoint health --write-out=table
# 检查各节点健康状态

解决方案：
# 1. 使用 NVMe SSD，避免 SATA SSD
# 2. 调整 election-timeout：
#    网络稳定：100ms * 10 = 1s
#    网络不稳定：500ms * 10 = 5s
# 3. 启用 mlock 防止 swap：
#    --enable-mlock=true
# 4. 调整 GC 目标：
#    GOGC=100 (默认)
```

#### 问题 3：Watch 延迟高

```
症状：
- 客户端 watch 收到事件延迟 > 1s
- 大量 slow watcher

根因：
1. 慢 watcher channel 满 → victim 堆积
2. Watch 范围太大（如 watch "/"）
3. 事件爆发（如大批量 put）

排查：
$ etcdctl watch / --prefix --watch-only
# 观察事件频率

$ etcdctl endpoint status --write-out=json | jq '.[].Stats.WatchCount'
# 查看各节点 watch 数量

解决方案：
# 1. 缩小 watch 范围（用 prefix 而非 watch /）
# 2. 客户端实现 backpressure（channel 满时暂停消费）
# 3. 批量操作使用 Txn 而非多次 Put
# 4. 监控 slow watcher 数量
```

#### 问题 4：客户端连接被拒绝

```
症状：
- "too many open files"
- "connection refused"
- "context deadline exceeded"

排查：
$ ss -s  # 查看 socket 统计
$ ulimit -n  # 查看文件描述符限制

解决方案：
# 1. 增加文件描述符限制
$ ulimit -n 65536

# 2. 调整 etcd 连接池
# clientv3.Config:
#   DialTimeout: 5 * time.Second
#   DialKeepAliveTime: 10 * time.Second
#   DialKeepAliveTimeout: 5 * time.Second
#   MaxCallSendMsgSize: 2 * 1024 * 1024  # 2MB

# 3. 使用连接复用
```

### 11.2 性能调优 Checklist

```
etcd 性能调优清单：

磁盘：
  □ 使用 NVMe SSD（最低 SATA SSD）
  □ 独立磁盘，不与 K8s 共享 IO 路径
  □ 磁盘使用率 < 80%

网络：
  □ etcd 节点间 RTT < 1ms（同机房）
  □ 千兆以太网（最低），推荐万兆
  □ 关闭 TCP Nagle（etcd 默认已优化）

内存：
  □ 每节点 ≥ 4GB（推荐 8GB+）
  □ 启用 mlock 防止 swap
  □ GOGC=100

配置：
  □ --quota-backend-bytes=2GB（根据数据量调整）
  □ --auto-compaction-mode=periodic
  □ --auto-compaction-retention=1h
  □ --snapshot-count=10000
  □ --heartbeat-interval=100
  □ --election-timeout=1000
  □ --max-request-bytes=1572864（1.5MB）
  □ --enable-v2=false（v2 API 已废弃）
  □ --logger=zap
  □ --log-level=info

监控：
  □ prometheus-etcd-exporter
  □ 监控指标：
     - etcd_disk_wal_fsync_duration_seconds
     - etcd_disk_backend_commit_duration_seconds
     - etcd_server_leader_changes_seen_total
     - etcd_mvcc_db_total_size_in_bytes
     - etcd_network_peer_sent_fail_total
```


## 十二、etcd vs 其他分布式存储对比

### 12.1 核心能力矩阵

```
┌──────────────────┬──────────────┬──────────────┬──────────────┐
│     特性         │   etcd       │  ZooKeeper   │    Consul    │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ 一致性协议       │ Raft         │ Zab          │ Raft         │
│ API 模型         │ Key-Value    │ ZNode Tree   │ Key-Value    │
│ 线性化读         │ ✓ (--linearizable) │ ✗    │ ✓            │
│ Watch 支持       │ ✓ (全量历史) │ ✓            │ ✓ (Session)  │
│ Lease/TTL        │ ✓            │ ✗ (Ephemeral)│ ✓            │
│ 事务支持         │ ✓ (CompareAndSwap) │ ✗  │ ✓            │
│ 多数据中心       │ ✗            │ ✗            │ ✓ (WAN)      │
│ 服务发现         │ ✗ (需自建)   │ ✗ (需自建)   │ ✓ (内置)     │
│ KV 值大小上限     │ 1.5MB        │ 1MB          │ 512KB        │
│ 推荐集群大小      │ 3-7          │ 3-5          │ 3-5          │
│ 写吞吐 (QPS)     │ 10K-50K      │ 5K-10K       │ 10K-30K      │
│ 读吞吐 (QPS)     │ 10K-100K     │ 5K-50K       │ 10K-100K     │
│ Go 语言实现       │ ✓            │ ✗ (Java)     │ ✓            │
│ CNCF 项目        │ ✓            │ ✗            │ ✓            │
└──────────────────┴──────────────┴──────────────┴──────────────┘
```

### 12.2 何时选择 etcd？

```
选择 etcd 的场景：
✅ 需要强一致性（线性化读）
✅ 需要 Watch 机制监听数据变化
✅ 需要 Lease/TTL 管理短期数据
✅ 需要 CompareAndSwap 实现分布式锁
✅ 作为 K8s 等云原生系统的后端
✅ 需要事务性多 key 操作
✅ Go 生态集成

不选择 etcd 的场景：
❌ 需要多数据中心部署（用 Consul DC 或 Spanner）
❌ 需要丰富的 ACL 权限控制（用 Consul）
❌ 数据量极大（> 10GB，用 Cassandra/DynamoDB）
❌ 需要高写入吞吐（> 100K QPS，用 Kafka/RocksDB）
❌ 需要层级数据结构（用 ZooKeeper）
```

## 十三、自测题

### 题目 1：MVCC 与 Compaction 的交互

**问题**：假设 etcd 中有以下操作序列：
```
Put("key1", "v1") at rev=1
Put("key1", "v2") at rev=2
Compaction at rev=2
Put("key1", "v3") at rev=3
Get("key1", atRev=2)  // 返回什么？
Get("key1", atRev=3)  // 返回什么？
Get("key1", atRev=1)  // 返回什么？
```

**答案**：
```
1. Get("key1", atRev=2) → 返回 "v2"
   - Compaction at rev=2 意味着 rev<=2 的历史被清理
   - 但 atRev=2 的请求仍在 compaction 边界上，取决于 compact 是否包含 rev=2
   - 实际：compaction at rev=R 后，rev<R 的数据被清理，rev>=R 的保留
   - 所以 atRev=2 返回 "v2"

2. Get("key1", atRev=3) → 返回 "v3"
   - rev=3 > compaction rev=2，数据完整保留

3. Get("key1", atRev=1) → 返回 ErrCompacted
   - rev=1 < compaction rev=2，数据已被清理
   - 客户端需要重新 watch 从当前 revision 开始

关键：compaction 是不可逆的操作！一旦 compact，历史版本永久丢失。
```

### 题目 2：Watch 风暴防护

**问题**：10000 个 watcher 同时 watch key prefix "/ads/"，此时发生一次 Put("/ads/campaign/1", "updated")。etcd 如何防止这次单个写操作导致 10000 个 channel 写入阻塞？

**答案**：
```
etcd 的三级防护机制：

1. 批量同步：syncWatchersLoop 每 100ms 执行一次，
   每次最多处理 512 个 watcher（maxWatchersPerSync）

2. Victim 机制：如果某个 watcher 的 channel 已满，
   该 watcher 被标记为 victim，不再在 syncWatchersLoop 中处理

3. 延迟追赶：syncVictimsLoop 在 victimc 信号触发时执行，
   每次只给 victim 发送有限数量的事件，避免再次阻塞

在这个场景中：
- 第一个 512 个 watcher 在 syncWatchersLoop 中立即收到事件
- 第 513-1024 个 watcher 如果 channel 满，成为 victim
- syncVictimsLoop 逐步处理 victim batch
- 整个过程被限制在可控的内存和 CPU 消耗内

对比：如果没有 victim 机制，10000 个 channel 同时写入
会导致内存暴增和 GC 压力，最终 OOM。
```

### 题目 3：Raft 提案延迟

**问题**：etcd 集群 3 节点，网络 RTT=5ms。一个 Put 请求从客户端发出到确认写入，最短和最长时间分别是多少？

**答案**：
```
最短时间（理想情况，已经是 Leader）：
1. Client → Leader: 5ms (RTT)
2. Leader 写入本地 WAL: ~0.1ms
3. Leader → Followers 复制日志: 5ms
4. 多数派确认 (Leader + 1 Follower): ~0.1ms
5. Leader → Client 确认: 5ms
总计: ≈ 15ms

最长时间（非 Leader，需要转发）：
1. Client → Non-Leader: 5ms
2. Non-Leader → Leader (内部转发): 5ms
3. Leader 写入 WAL: ~0.1ms
4. Leader → Followers 复制: 5ms
5. 多数派确认: ~0.1ms
6. Leader → Non-Leader: 5ms
7. Non-Leader → Client: 5ms
总计: ≈ 25ms

如果考虑磁盘 fsync：
- SSD fsync ≈ 0.1-1ms
-  SATA SSD fsync ≈ 1-5ms
-  HDD fsync ≈ 10-20ms（绝对不能用！）

生产建议：etcd 必须跑在 NVMe SSD 上，fsync 延迟 < 0.5ms。
```


## 十四、与知识库的对照

### 已有知识
- `architecture/high-availability-design.md` — 提到了 etcd 作为 K8s 存储后端，但没有源码级深度
- `fullstack/kubernetes-deep-dive.md` — 有 etcd 章节但只有概念层面
- `middleware/ad-cicd-gitops-argocd-deep.md` — 涉及 etcd 作为 ArgoCD 后端
- `network/tls-ssl-deep.md` — 有 TLS 配置与 etcd 集群通信相关

### 本文件补充的独特价值
1. **MVCC 源码级实现** — treeIndex 的 BTree 结构、Revision 的字节编码、Get/Put/Range 的完整代码路径
2. **Watch 系统深度** — synced/unsynced/victim 三级架构、防风暴机制的源码实现
3. **Lease Manager** — 完整的租约生命周期、checkpoint 机制、过期检测
4. **Compaction/Defrag** — 逻辑删除 vs 物理删除的区别、防死锁机制
5. **BBolt 事务模型** — BatchTx/ReadTx/ConcurrentReadTx 的读写分离设计
6. **广告系统实战** — DSP 场景下的具体 Go 代码示例

### 缺失内容（待补充）
- [ ] etcd 与 TiKV 的对比（TiKV 也是 Go 实现的分布式 KV，但基于 Raft + PD）
- [ ] etcd 3.6 的 v3.6 多租户特性（Multi-Tenancy）
- [ ] etcd 与 NATS JetStream 的选型对比（轻量级替代方案）
