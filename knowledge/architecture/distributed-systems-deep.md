# 分布式系统核心原理深度解析

> 深入分布式系统核心：一致性协议、CAP 定理、分布式事务、共识算法。
> 源码级分析 Raft、Paxos，包含实际案例和调优经验。
> 适用对象：分布式系统工程师、架构师、后端高级开发者

---

## 1. CAP 定理深度解析

### 1.1 定理证明

```
定理：分布式系统最多同时满足以下三个特性中的两个：
- C (Consistency)：一致性
- A (Availability)：可用性
- P (Partition Tolerance)：分区容错性

证明：
假设系统同时满足 C、A、P

1. 由于 P，系统可能存在网络分区
2. 分区后，节点 A 和节点 B 无法通信
3. 由于 C，节点 A 和 B 必须看到相同的数据
4. 但无法通信，无法同步数据
5. 矛盾！

因此，系统最多只能满足 C、A、P 中的两个。
```

### 1.2 实际选择

| 系统 | 选择 | 说明 |
|------|------|------|
| ZooKeeper | CP | 保证一致性，分区时不可用 |
| Cassandra | AP | 保证可用性，分区时可能不一致 |
| Redis Cluster | AP | 最终一致性，高可用 |
| TiDB | CP | 强一致性，分布式事务 |

### 1.3 PACELC 定理

```
PACELC = CAP + Latency/Consistency

当没有分区时（E: Else）：
- 选择 Latency（低延迟）：AP 系统
- 选择 Consistency（一致性）：CP 系统
```

---

## 2. Raft 共识算法源码解析

### 2.1 状态机设计

```go
// raft.go

type State int

const (
    Follower State = iota
    Candidate
    Leader
)

type Raft struct {
    peers      []*RPCCli
    persist    Persist
    me         int
    dead       int32 // for testing

    // 持久化状态
    currentTerm int
    votedFor    int
    log         []Entry

    // 易失状态
    commitIndex int
    lastApplied int

    // Leader 状态
    nextIndex  []int
    matchIndex []int

    // 应用层状态
    applyCh chan ApplyMsg
    applyCond *sync.Cond
}
```

### 2.2 选举实现

```go
// raft.go

func (rf *Raft) run() {
    for rf.killed() == false {
        switch rf.state {
        case Follower:
            rf.stepFollower()
        case Candidate:
            rf.stepCandidate()
        case Leader:
            rf.stepLeader()
        }
    }
}

func (rf *Raft) stepCandidate() {
    select {
    case <-rf.ticker.C:
        rf.startElection()
    case msg := <-rf.applyCh:
        rf.apply(msg)
    }
}

func (rf *Raft) startElection() {
    rf.currentTerm++
    rf.votedFor = rf.me
    rf.saveState()
    
    rf.state = Candidate
    
    // 请求投票
    args := RequestVoteArgs{
        Term:        rf.currentTerm,
        CandidateId: rf.me,
        LastLogIndex: len(rf.log) - 1,
        LastLogTerm:  rf.log[len(rf.log)-1].Term,
    }
    
    for peer := range rf.peers {
        if peer == rf.me {
            continue
        }
        go rf.sendRequestVote(peer, args)
    }
}

func (rf *Raft) sendRequestVote(peer int, args RequestVoteArgs) {
    var reply RequestVoteReply
    rf.peers[peer].Call("Raft.RequestVote", &args, &reply)
    
    if reply.Term > rf.currentTerm {
        rf.becomeFollower(reply.Term)
        return
    }
    
    if reply.VoteGranted {
        rf.mu.Lock()
        rf.votesReceived++
        rf.mu.Unlock()
        
        if rf.votesReceived > len(rf.peers)/2 {
            rf.becomeLeader()
        }
    }
}
```

### 2.3 日志复制

```go
// raft.go

func (rf *Raft) becomeLeader() {
    rf.state = Leader
    rf.mu.Lock()
    rf.lastApplied = rf.commitIndex
    rf.mu.Unlock()
    
    // 初始化 nextIndex 和 matchIndex
    rf.nextIndex = make([]int, len(rf.peers))
    rf.matchIndex = make([]int, len(rf.peers))
    
    for i := range rf.peers {
        rf.nextIndex[i] = len(rf.log)
        rf.matchIndex[i] = 0
    }
    
    rf.sendHeartbeats()
}

func (rf *Raft) sendHeartbeats() {
    for peer := range rf.peers {
        if peer == rf.me {
            continue
        }
        go rf.sendAppendEntries(peer)
    }
}

func (rf *Raft) sendAppendEntries(peer int) {
    rf.mu.Lock()
    next := rf.nextIndex[peer]
    prevLogIndex := next - 1
    prevLogTerm := 0
    if prevLogIndex >= 0 {
        prevLogTerm = rf.log[prevLogIndex].Term
    }
    
    entries := make([]Entry, 0)
    if next < len(rf.log) {
        entries = append(entries, rf.log[next:]...)
    }
    
    args := AppendEntriesArgs{
        Term:         rf.currentTerm,
        LeaderId:     rf.me,
        PrevLogIndex: prevLogIndex,
        PrevLogTerm:  prevLogTerm,
        Entries:      entries,
        LeaderCommit: rf.commitIndex,
    }
    rf.mu.Unlock()
    
    var reply AppendEntriesReply
    rf.peers[peer].Call("Raft.AppendEntries", &args, &reply)
    
    if reply.Term > rf.currentTerm {
        rf.becomeFollower(reply.Term)
        return
    }
    
    if reply.Success {
        rf.mu.Lock()
        rf.nextIndex[peer] = next + len(entries)
        rf.matchIndex[peer] = rf.nextIndex[peer] - 1
        rf.mu.Unlock()
    } else {
        rf.mu.Lock()
        rf.nextIndex[peer]--
        rf.mu.Unlock()
    }
}
```

---

## 3. Paxos 算法解析

### 3.1 基本 Paxos

```
Phase 1: Prepare
  Proposer -> Acceptor: PREPARE(n)
  Acceptor -> Proposer: ACCEPTED(n, lastProposal)

Phase 2: Accept
  Proposer -> Acceptor: ACCEPT(n, value)
  Acceptor -> Proposer: ACCEPTED
```

### 3.2 Go 实现

```go
type Proposer struct {
    term   int
    id     string
    acceptors []string
}

func (p *Proposer) propose(value string) (string, error) {
    p.term++
    promise := make(chan acceptResponse, len(p.acceptors))
    
    // Phase 1: Prepare
    for _, a := range p.acceptors {
        go p.prepare(a, p.term, promise)
    }
    
    // 等待多数派
    accepted := 0
    var lastValue string
    for resp := range promise {
        if resp.term > p.term {
            return "", fmt.Errorf("higher term")
        }
        if resp.accepted {
            accepted++
            if resp.lastValue != "" {
                lastValue = resp.lastValue
            }
        }
        if accepted > len(p.acceptors)/2 {
            break
        }
    }
    
    // Phase 2: Accept
    acceptPromise := make(chan acceptResponse, len(p.acceptors))
    for _, a := range p.acceptors {
        go p.accept(a, p.term, lastValue, acceptPromise)
    }
    
    accepted = 0
    for resp := range acceptPromise {
        if resp.accepted {
            accepted++
        }
        if accepted > len(p.acceptors)/2 {
            return lastValue, nil
        }
    }
    
    return "", fmt.Errorf("failed to accept")
}
```

---

## 4. 分布式事务

### 4.1 两阶段提交 (2PC)

```go
type Coordinator struct {
    participants []string
    txID string
}

func (c *Coordinator) commit(tx *Transaction) error {
    // Phase 1: Prepare
    votes := make(chan bool, len(c.participants))
    for _, p := range c.participants {
        go c.prepare(p, tx, votes)
    }
    
    prepareOK := true
    for range c.participants {
        vote := <-votes
        if !vote {
            prepareOK = false
            break
        }
    }
    
    // Phase 2: Commit/Abort
    if prepareOK {
        for _, p := range c.participants {
            c.doCommit(p, tx)
        }
        return nil
    }
    
    for _, p := range c.participants {
        c.doAbort(p, tx)
    }
    return fmt.Errorf("prepare failed")
}

func (c *Coordinator) prepare(participant string, tx *Transaction, votes chan<- bool) {
    // 调用参与者 prepare
    ok := callPrepare(participant, tx)
    votes <- ok
}
```

### 4.2 三阶段提交 (3PC)

```
Phase 1: CanCommit
  Coordinator -> Participants: CAN_COMMIT?
  Participants -> Coordinator: YES/NO

Phase 2: PreCommit
  Coordinator -> Participants: PRE_COMMIT
  Participants -> Coordinator: ACK

Phase 3: DoCommit
  Coordinator -> Participants: DO_COMMIT / DO_ABORT
```

### 4.3 TCC 事务

```go
type TCCParticipant struct {
    id string
}

func (p *TCCParticipant) Try(ctx context.Context, data interface{}) error {
    // Try: 预留资源
    return p.reserve(data)
}

func (p *TCCParticipant) Confirm(ctx context.Context, data interface{}) error {
    // Confirm: 确认提交
    return p.commit(data)
}

func (p *TCCParticipant) Cancel(ctx context.Context, data interface{}) error {
    // Cancel: 取消预留
    return p.rollback(data)
}
```

---

## 5. 实战案例

### 5.1 Raft 选主失败排查

**问题**：集群频繁选主，无法稳定

**排查**：
```bash
# 查看日志
grep "StartElection" raft.log | tail -20
```

**根因**：网络分区导致多数派无法达成

**解决**：
1. 检查网络稳定性
2. 调整选举超时时间
3. 增加节点数到奇数

### 5.2 分布式锁性能优化

**问题**：Redis 分布式锁在高并发下性能瓶颈

**优化**：
```go
// 优化前：每次请求都加锁解锁
func processOrder(id string) {
    lock, _ := redis.GetLock(ctx, id)
    defer lock.Unlock()
    // 处理订单
}

// 优化后：本地缓存 + 分布式锁
var localCache sync.Map

func processOrder(id string) {
    if val, ok := localCache.Load(id); ok {
        return val  // 本地缓存命中
    }
    
    lock, _ := redis.GetLock(ctx, id)
    defer lock.Unlock()
    
    // 双重检查
    if val, ok := localCache.Load(id); ok {
        return val
    }
    
    // 处理订单
    result := handleOrder(id)
    localCache.Store(id, result)
    return result
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 主题 | 核心算法 | 关键优化点 |
|------|----------|-----------|
| 共识 | Raft、Paxos | 选主超时、日志复制 |
| 事务 | 2PC、3PC、TCC | 超时设置、回滚机制 |
| 锁 | Redis 分布式锁 | 本地缓存、看门狗 |
| 一致性 | 最终一致性 | 补偿机制、对账 |

### 6.2 设计原则

1. **多数派原则**：所有决策需多数派同意
2. **幂等性**：所有操作必须幂等
3. **超时处理**：设置合理超时，避免死锁
4. **日志持久化**：关键状态必须持久化

---

*最后更新：2026-08-11*
*作者：Ryan*
