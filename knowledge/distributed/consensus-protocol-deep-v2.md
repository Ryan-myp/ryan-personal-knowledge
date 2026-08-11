# 分布式一致性协议深度解析

> 深入分布式一致性：Paxos、Raft、ZAB、2PC、TCC。
> 源码级分析，包含生产环境实践。
> 适用对象：分布式系统工程师、架构师

---

## 1. Paxos 协议

### 1.1 核心概念

```
Paxos 核心概念：

├── Proposal (提案)
│   └── 提议的值

├── Accept (接受)
│   └── 接受提案

├── Promise (承诺)
│   └── 承诺不接受其他提案

└── 多数派 (Majority)
    └── 超过半数的节点
```

### 1.2 Go 实现 Paxos

```go
// paxos.go

package distributed

import (
    "sync"
)

type PaxosNode struct {
    id           int
    ballots      map[int]*Ballot
    accepted     map[int]acceptedValue
    mu           sync.Mutex
}

type Ballot struct {
    number   int
    value    interface{}
    promise  bool
}

type acceptedValue struct {
    ballot int
    value  interface{}
}

func (p *PaxosNode) Prepare(number int) (*Ballot, error) {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    if p.ballots[number] == nil {
        p.ballots[number] = &Ballot{number: number}
    }
    
    return p.ballots[number], nil
}

func (p *PaxosNode) Accept(number int, value interface{}) error {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    ballot := p.ballots[number]
    if ballot == nil {
        ballot = &Ballot{number: number}
        p.ballots[number] = ballot
    }
    
    ballot.value = value
    p.accepted[number] = acceptedValue{ballot: number, value: value}
    return nil
}
```

---

## 2. Raft 协议

### 2.1 状态机

```
Raft 状态机：

┌──────────┐    Timeout    ┌──────────┐    Append     ┌──────────┐
│  Follower │────────────→│  Candidate │───────────→│  Leader   │
│          │←─────────────│          │←────────────│          │
│  接收RPC  │   选举超时    │  发起选举  │   成功     │  发送心跳 │
└──────────┘               └──────────┘            └──────────┘
                              ↓                       ↓
                        选举失败                  领导者任期
                        回到 Follower           持久化日志
```

### 2.2 Go 实现 Raft

```go
// raft.go

package distributed

import (
    "sync"
    "time"
)

type RaftState int

const (
    Follower RaftState = iota
    Candidate
    Leader
)

type Raft struct {
    id          int
    state       RaftState
    term        int
    votedFor    int
    log         []Entry
    commitIndex int
    lastApplied int
    
    leaders     map[int]bool
    nextIndex   map[int]int
    matchIndex  map[int]int
    
    mu          sync.Mutex
    applyCh     chan ApplyMessage
}

type Entry struct {
    Term    int
    Index   int
    Command interface{}
}

func NewRaft(id int, applyCh chan ApplyMessage) *Raft {
    return &Raft{
        id:      id,
        state:   Follower,
        term:    0,
        log:     make([]Entry, 0),
        applyCh: applyCh,
        leaders: make(map[int]bool),
        nextIndex: make(map[int]int),
        matchIndex: make(map[int]int),
    }
}

func (r *Raft) Start(command interface{}) (int, int, bool) {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    if r.state != Leader {
        return 0, 0, false
    }
    
    entry := Entry{
        Term:    r.term,
        Index:   len(r.log) + 1,
        Command: command,
    }
    r.log = append(r.log, entry)
    
    // 复制给所有 follower
    for peer := range r.leaders {
        r.nextIndex[peer] = entry.Index
        r.matchIndex[peer] = 0
    }
    
    return entry.Index, entry.Term, true
}
```

---

## 3. 两阶段提交

### 3.1 2PC 流程

```
两阶段提交流程：

Phase 1: 准备阶段
├── Coordinator → Participants: PREPARE?
└── Participants → Coordinator: YES/NO

Phase 2: 提交阶段
├── Coordinator → Participants: COMMIT
└── Participants → Coordinator: ACK
```

### 3.2 Go 实现 2PC

```go
// two_phase_commit.go

package distributed

import (
    "sync"
)

type TXState int

const (
    Prepared TXState = iota
    Committed
    Aborted
)

type TwoPhaseCommit struct {
    participants []string
    state        TXState
    mu           sync.Mutex
}

func NewTwoPhaseCommit(participants []string) *TwoPhaseCommit {
    return &TwoPhaseCommit{
        participants: participants,
        state:        Prepared,
    }
}

func (tx *TwoPhaseCommit) Prepare() bool {
    tx.mu.Lock()
    defer tx.mu.Unlock()
    
    allPrepared := true
    for _, participant := range tx.participants {
        if !tx.prepareParticipant(participant) {
            allPrepared = false
            break
        }
    }
    
    if allPrepared {
        tx.state = Committed
    } else {
        tx.state = Aborted
        tx.abort()
    }
    
    return allPrepared
}

func (tx *TwoPhaseCommit) prepareParticipant(participant string) bool {
    // 模拟准备
    return true
}

func (tx *TwoPhaseCommit) abort() {
    for _, participant := range tx.participants {
        tx.abortParticipant(participant)
    }
}

func (tx *TwoPhaseCommit) abortParticipant(participant string) {
    // 模拟回滚
}
```

---

## 4. 总结

### 4.1 协议对比

| 协议 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| Paxos | 理论完备 | 实现复杂 | 通用分布式 |
| Raft | 易于理解 | 单领导者 | 日志复制 |
| 2PC | 强一致 | 性能差 | 事务处理 |
| TCC | 高性能 | 业务侵入 | 金融场景 |

### 4.2 最佳实践

- [ ] 根据场景选择一致性协议
- [ ] Raft 优先于 Paxos
- [ ] 避免 2PC 长事务
- [ ] 监控集群状态

---

*最后更新：2026-08-12*
*作者：Ryan*
