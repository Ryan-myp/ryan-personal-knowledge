# 分布式一致性协议深度解析

> 深入分布式一致性：Paxos、Raft、ZAB、2PC。
> 源码级分析，包含生产环境实现。
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

├── Learner (学习者)
│   └── 学习决策

└── 角色
    ├── Proposer (提议者)
    ├── Acceptor (接受者)
    └── Learner (学习者)
```

### 1.2 Go 实现 Paxos

```go
// paxos.go

package consensus

import (
    "sync"
)

type Proposer struct {
    id      int
    mu      sync.Mutex
    proposals []Proposal
}

type Acceptor struct {
    id              int
    promisedNum     int
    acceptedNum     int
    acceptedValue   interface{}
    mu              sync.Mutex
}

type Learner struct {
    id         int
    decisions  []Decision
    mu         sync.Mutex
}

type Proposal struct {
    Num     int
    Value   interface{}
}

type Decision struct {
    Value interface{}
}

func (p *Proposer) Propose(value interface{}) (interface{}, error) {
    p.mu.Lock()
    proposalNum := p.generateProposalNum()
    p.mu.Unlock()
    
    // Phase 1: Prepare
    promises, err := p.prepare(proposalNum)
    if err != nil {
        return nil, err
    }
    
    // Phase 2: Accept
    acceptedValue := p.selectValue(proposalNum, promises)
    acceptResults, err := p.accept(proposalNum, acceptedValue)
    if err != nil {
        return nil, err
    }
    
    // 检查是否多数派接受
    if countAccepted(acceptResults) >= quorumSize() {
        return acceptedValue, nil
    }
    
    return nil, ErrNoConsensus
}

func (a *Acceptor) Prepare(proposalNum int) (int, interface{}, bool) {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    if proposalNum > a.promisedNum {
        a.promisedNum = proposalNum
        return a.promisedNum, a.acceptedValue, true
    }
    return a.promisedNum, a.acceptedValue, false
}

func (a *Acceptor) Accept(proposalNum int, value interface{}) bool {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    if proposalNum >= a.promisedNum {
        a.acceptedNum = proposalNum
        a.acceptedValue = value
        return true
    }
    return false
}
```

---

## 2. Raft 协议

### 2.1 状态机

```
Raft 状态机：

┌─────────┐    Election Timeout    ┌─────────┐
│  Follower │──────────────────────>│ Candidate │
└─────────┘                        └─────────┘
    ↑                                   │
    │              Election Timeout     │
    └───────────────────────────────────┘
          (重新选举)
```

### 2.2 Go 实现 Raft

```go
// raft.go

package consensus

import (
    "sync"
    "time"
)

type State int

const (
    Follower State = iota
    Candidate
    Leader
)

type Raft struct {
    mu          sync.Mutex
    state       State
    currentTerm int
    votedFor    *int
    log         []Entry
    commitIndex int
    lastApplied int
    peers       []string
    nextIndex   map[int]int
    matchIndex  map[int]int
}

type Entry struct {
    Term    int
    Command interface{}
    Index   int
}

func NewRaft(peers []string) *Raft {
    r := &Raft{
        state:  Follower,
        peers:  peers,
        nextIndex: make(map[int]int),
        matchIndex: make(map[int]int),
    }
    r.startElectionTimer()
    return r
}

func (r *Raft) Apply(command interface{}) int {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    if r.state != Leader {
        return -1
    }
    
    entry := Entry{
        Term:    r.currentTerm,
        Command: command,
        Index:   len(r.log),
    }
    r.log = append(r.log, entry)
    
    // 复制到所有节点
    r.replicate(entry)
    
    return entry.Index
}

func (r *Raft) startElectionTimer() {
    go func() {
        for {
            timeout := r.randomElectionTimeout()
            time.Sleep(timeout)
            r.startElection()
        }
    }()
}
```

---

## 3. 两阶段提交

### 3.1 流程

```
2PC 流程：

Phase 1: 准备阶段
├── Coordinator 发送 PREPARE 到所有 Participant
└── Participant 准备事务并投票

Phase 2: 提交阶段
├── 所有 Participant 投票 YES → COMMIT
└── 存在 Participant 投票 NO → ROLLBACK
```

### 3.2 Go 实现 2PC

```go
// two_phase_commit.go

package consensus

import (
    "context"
    "sync"
)

type Coordinator struct {
    participants []string
    state        string
    mu           sync.Mutex
}

type Participant struct {
    id      string
    state   string
    voted   bool
    mu      sync.Mutex
}

func (c *Coordinator) Prepare(ctx context.Context) (bool, error) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    c.state = "preparing"
    
    var wg sync.WaitGroup
    votes := make(chan bool, len(c.participants))
    
    for _, p := range c.participants {
        wg.Add(1)
        go func(pid string) {
            defer wg.Done()
            voted := c.prepareParticipant(ctx, pid)
            votes <- voted
        }(p)
    }
    
    go func() {
        wg.Wait()
        close(votes)
    }()
    
    allYes := true
    for vote := range votes {
        if !vote {
            allYes = false
        }
    }
    
    c.state = "committed"
    return allYes, nil
}

func (c *Coordinator) prepareParticipant(ctx context.Context, participantID string) bool {
    // 发送 PREPARE 请求
    // 等待响应
    return true
}
```

---

## 4. 总结

### 4.1 协议对比

| 协议 | 一致性级别 | 容错能力 | 性能 |
|------|-----------|----------|------|
| Paxos | 强一致 | 1个故障 | 中 |
| Raft | 强一致 | 1个故障 | 高 |
| 2PC | 强一致 | 无 | 低 |

### 4.2 最佳实践

- [ ] 根据场景选择协议
- [ ] 监控一致性状态
- [ ] 设计故障恢复机制
- [ ] 性能调优

---

*最后更新：2026-08-11*
*作者：Ryan*
