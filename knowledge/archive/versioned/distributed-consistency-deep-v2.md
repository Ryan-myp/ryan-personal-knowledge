# 分布式系统一致性深度解析

> 深入分布式一致性：CAP、Paxos、Raft、分布式事务。
> 源码级分析，包含生产环境实现。
> 适用对象：分布式系统工程师、架构师

---

## 1. CAP 定理

### 1.1 定理证明

```
定理：分布式系统最多同时满足以下三个特性中的两个：

- C (Consistency)：所有节点同一时刻看到相同数据
- A (Availability)：每个请求都能获得非错误响应
- P (Partition Tolerance)：系统在网络分区时仍能继续工作

证明思路：
1. 假设系统同时满足 C、A、P
2. 发生网络分区，节点 P1 和 P2 无法通信
3. 客户端向 P1 写入数据
4. P1 需要保持 C，必须等 P2 同步才能响应
5. 但这违背 A（不能保证响应）
6. 矛盾，所以不能同时满足三者
```

### 1.2 选型决策

```
CAP 选型矩阵：

┌────────────┬────────────┬─────────────┐
│ 场景       │ 选择       │ 原因        │
├────────────┼────────────┼─────────────┤
│ 银行系统   │ CP         │ 一致性优先  │
│ 社交网络   │ AP         │ 可用性优先  │
│ 电商库存   │ CP         │ 不能超卖    │
│ 内容发布   │ AP         │ 允许延迟    │
│ 日志收集   │ AP         │ 允许丢失    │
└────────────┴────────────┴─────────────┘
```

---

## 2. Paxos 算法

### 2.1 核心概念

```
Paxos 参与角色：

- Proposer：发起提案
- Acceptor：投票接受
- Learner：学习结果

Paxos 两阶段：

Phase 1 (Prepare)：
1. Proposer 选择 proposal number n
2. 向多数派 Acceptor 发送 PREPARE(n)
3. Acceptor 若 n > 已承诺的 max, 承诺不再接受 < n 的提案
4. 返回 (max_n, accepted_value)

Phase 2 (Accept)：
1. Proposer 收到多数派响应
2. 若有人已接受值，使用该值；否则自选值 v
3. 向多数派 Acceptor 发送 ACCEPT(n, v)
4. Acceptor 若 n >= 已承诺的 max, 接受 (n, v)
```

### 2.2 Go 实现简化版

```go
// paxos.go

package consensus

import (
    "sync"
)

type Proposal struct {
    Number int
    Value  interface{}
}

type Acceptor struct {
    mu           sync.Mutex
    promisedTo   int
    accepted     map[int]interface{}
}

func (a *Acceptor) Prepare(number int) (int, interface{}, bool) {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    if number < a.promisedTo {
        return 0, nil, false
    }
    a.promisedTo = number
    return number, a.accepted[number], true
}

func (a *Acceptor) Accept(number int, value interface{}) bool {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    if number < a.promisedTo {
        return false
    }
    a.accepted[number] = value
    return true
}
```

---

## 3. Raft 算法

### 3.1 节点状态

```
Raft 节点状态机：

┌─────────────────────────────────────────────────────────────┐
│                   Raft 状态                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Follower ( follower)                                      │
│  ├── 响应 Leader 心跳                                       │
│  └── 可转化为 Candidate                                     │
│                                                             │
│  Candidate (候选人)                                         │
│  ├── 请求投票                                               │
│  └── 若获得多数票 → Leader                                   │
│      若收到大于自己的 term → Follower                        │
│                                                             │
│  Leader (领导者)                                            │
│  ├── 处理客户端请求                                          │
│  ├── 复制日志到 Follower                                     │
│  └── 定期发送心跳                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现简化版

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

type RaftNode struct {
    mu            sync.Mutex
    state         State
    currentTerm   int
    votedFor      int
    logs          []LogEntry
    commitIndex   int
    lastApplied  int
    
    // Leader 专用
    nextIndex  map[int]int
    matchIndex map[int]int
    
    peers      []*RaftNode
    heartbeat  chan struct{}
}

type LogEntry struct {
    Term    int
    Index   int
    Command interface{}
}

func (r *RaftNode) Start(cmd interface{}) int {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    if r.state != Leader {
        return -1
    }
    
    entry := LogEntry{
        Term:    r.currentTerm,
        Index:   len(r.logs) + 1,
        Command: cmd,
    }
    r.logs = append(r.logs, entry)
    return entry.Index
}

func (r *RaftNode) AppendEntries(peer *RaftNode, prevLogIndex int, prevLogTerm int, entries []LogEntry) bool {
    peer.mu.Lock()
    defer peer.mu.Unlock()
    
    if prevLogIndex > 0 {
        if prevLogIndex > len(peer.logs) {
            return false
        }
        if peer.logs[prevLogIndex-1].Term != prevLogTerm {
            return false
        }
    }
    
    // 覆盖不一致的日志
    for i, entry := range entries {
        idx := prevLogIndex + i
        if idx >= len(peer.logs) {
            peer.logs = append(peer.logs, entry)
        } else if entry.Term != peer.logs[idx].Term {
            peer.logs[idx] = entry
            peer.logs = peer.logs[:idx+1]
        }
    }
    
    return true
}
```

---

## 4. 分布式事务

### 4.1 2PC 两阶段提交

```
2PC 协议流程：

Phase 1: Prepare
1. Coordinator 向所有 Participant 发送 PREPARE 消息
2. Participant 执行事务，但不提交
3. Participant 回复 VOTE_COMMIT 或 VOTE_ABORT

Phase 2: Commit/Abort
1. 所有 Participant 都投票 COMMIT → Coordinator 发送 COMMIT
2. 任一 Participant 投票 ABORT → Coordinator 发送 ABORT
```

### 4.2 Go 实现 2PC

```go
// two_phase_commit.go

package transaction

import (
    "sync"
    "time"
)

type Participant struct {
    id        int
    vote      string
    committed bool
}

type TwoPhaseCommit struct {
    mu          sync.Mutex
    participants []*Participant
    voteCount   map[string]int
}

func (tpc *TwoPhaseCommit) Prepare() (bool, error) {
    tpc.mu.Lock()
    defer tpc.mu.Unlock()
    
    tpc.voteCount = map[string]int{"COMMIT": 0, "ABORT": 0}
    
    for _, p := range tpc.participants {
        // 模拟 prepare
        vote := "COMMIT"
        if p.id%3 == 0 {
            vote = "ABORT"
        }
        p.vote = vote
        tpc.voteCount[vote]++
    }
    
    return tpc.voteCount["ABORT"] == 0, nil
}

func (tpc *TwoPhaseCommit) Commit() {
    tpc.mu.Lock()
    defer tpc.mu.Unlock()
    
    for _, p := range tpc.participants {
        p.committed = true
    }
}

func (tpc *TwoPhaseCommit) Abort() {
    tpc.mu.Lock()
    defer tpc.mu.Unlock()
    
    for _, p := range tpc.participants {
        p.committed = false
    }
}
```

---

## 5. Saga 模式

### 5.1 流程

```
Saga 模式：

[Step 1] ──► [Step 2] ──► [Step 3] ──► [Step 4]
   │            │            │            │
   ▼            ▼            ▼            ▼
Comp1        Comp2        Comp3        Comp4

正向执行：Step1 → Step2 → Step3 → Step4
失败回滚：Step4 → Comp4 → Comp3 → Comp2 → Comp1
```

### 5.2 Go 实现

```go
// saga.go

package transaction

type Step struct {
    Name       string
    Action     func() error
    Compensation func() error
}

type Saga struct {
    steps []*Step
}

func (s *Saga) Execute() error {
    executed := 0
    defer s.rollback(executed)
    
    for i, step := range s.steps {
        if err := step.Action(); err != nil {
            executed = i
            return err
        }
        executed = i + 1
    }
    return nil
}

func (s *Saga) rollback(upTo int) {
    for i := upTo - 1; i >= 0; i-- {
        if err := s.steps[i].Compensation(); err != nil {
            // 记录错误，继续回滚
        }
    }
}
```

---

## 6. 总结

### 6.1 核心原理回顾

| 算法 | 特点 | 适用场景 |
|------|------|----------|
| Paxos | 理论严谨 | ZooKeeper |
| Raft | 易理解实现 | etcd、Consul |
| 2PC | 强一致 | 传统数据库 |
| Saga | 最终一致 | 微服务事务 |

### 6.2 最佳实践

- [ ] 根据场景选择一致性模型
- [ ] Raft 优于 Paxos 工程实现
- [ ] 长事务考虑 Saga
- [ ] 设置合理的超时重试

---

*最后更新：2026-08-11*
*作者：Ryan*
