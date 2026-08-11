# 分布式系统一致性深度解析

> 深入分布式一致性：CAP定理、Paxos、Raft、2PC、Saga、TCC。
> 包含源码级分析和生产环境实现。
> 适用对象：分布式系统工程师、架构师

---

## 1. CAP 定理

### 1.1 定理证明

```
定理：分布式系统最多同时满足以下三个特性中的两个：
- C (Consistency)：所有节点同一时刻看到相同数据
- A (Availablity)：每个请求都能得到响应
- P (Partition Tolerance)：系统继续运行 despite网络分区

证明思路：
1. 假设系统同时满足 CAP
2. 发生网络分区，节点 P1, P2 无法通信
3. P1 写入数据，P2 读取数据
4. 为了 C，P2 必须等待 P1 的更新
5. 为了 A，P2 必须返回数据
6. 矛盾：P2 不能同时满足 C 和 A
7. 结论：系统最多满足 CAP 中的两个
```

### 1.2 实际应用

```
场景选择：

CA (Consistency + Availability)
├── 单节点数据库
├── 不考虑分区容忍
└── 适用：小型应用

CP (Consistency + Partition Tolerance)
├── ZooKeeper
├── HBase
├── Redis Cluster
└── 适用：需要强一致性的场景

AP (Availability + Partition Tolerance)
├── Cassandra
├── DynamoDB
├── DNS
└── 适用：高可用场景
```

---

## 2. Paxos 算法

### 2.1 算法流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Paxos 算法流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1: Prepare                                           │
│  ├── Proposer 发送 Prepare(n) 给所有 Acceptor                │
│  ├── Acceptor 如果 n > 已承诺的n，承诺不再接受更小的n        │
│  └── Acceptor 返回 Promise(n, accepted_value)               │
│                                                             │
│  Phase 2: Accept                                            │
│  ├── Proposer 收到过半 Acceptor 的 Promise                   │
│  ├── 选择 value = 最高编号的 accepted_value（如果有）        │
│  ├── 发送 Accept(n, value) 给所有 Acceptor                   │
│  └── Acceptor 如果 n >= 已承诺的n，接受该提议               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现

```go
// paxos.go

package paxos

import (
    "sync"
    "sync/atomic"
)

type Proposer struct {
    id      int
    proposals chan proposal
}

type Acceptor struct {
    mu          sync.Mutex
    promiseNum  int
    acceptedNum int
    acceptedVal interface{}
}

type Learner struct {
    decisions chan interface{}
}

type proposal struct {
    num int
    val interface{}
}

func (a *Acceptor) Accept(p proposal) bool {
    a.mu.Lock()
    defer a.mu.Unlock()
    
    if p.num < a.promiseNum {
        return false
    }
    
    a.promiseNum = p.num
    if a.acceptedNum < p.num {
        a.acceptedNum = p.num
        a.acceptedVal = p.val
    }
    return true
}
```

---

## 3. Raft 算法

### 3.1 状态机

```
┌─────────────────────────────────────────────────────────────┐
│                    Raft 状态机                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌─────────┐                              │
│                    │ Follower │◄─────────────────────┐      │
│                    └────┬────┘                      │      │
│                         │                           │      │
│            ┌────────────┼────────────┐              │      │
│            │            │            │              │      │
│            ▼            ▼            ▼              │      │
│       ┌─────────┐  ┌─────────┐  ┌─────────┐        │      │
│       │Candidate│──►│ Leader  │  │ timeout │        │      │
│       └────┬────┘  └────┬────┘  └─────────┘        │      │
│            │            │                           │      │
│            └────────────┼───────────────────────────┘      │
│                         │                                  │
│                    timeout / election loss                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Go 实现

```go
// raft.go

package raft

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

type Node struct {
    mu         sync.Mutex
    state      State
    term       int
    votes      map[int]bool
    log        []Entry
    commitIndex int
    lastApplied int
}

type Entry struct {
    Term    int
    Index   int
    Command interface{}
}

func (n *Node) Start(command interface{}) int {
    n.mu.Lock()
    defer n.mu.Unlock()
    
    entry := Entry{
        Term:    n.term,
        Command: command,
        Index:   len(n.log),
    }
    n.log = append(n.log, entry)
    
    return entry.Index
}
```

---

## 4. 分布式事务

### 4.1 2PC 两阶段提交

```
┌─────────────────────────────────────────────────────────────┐
│                  2PC 两阶段提交                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1: Prepare                                           │
│  ├── Coordinator 发送 Prepare 消息给所有 Participant         │
│  ├── Participant 执行事务，但不提交                          │
│  └── Participant 回复 Vote Commit / Vote Abort              │
│                                                             │
│  Phase 2: Commit / Abort                                    │
│  ├── 所有 Participant 投票 Commit → Coordinator 发送 Commit  │
│  ├── 有 Participant 投票 Abort → Coordinator 发送 Abort     │
│  └── Participant 执行 Commit 或 Rollback                     │
│                                                             │
│  问题：                                                      │
│  ├── 阻塞性问题：Coordinator 宕机                           │
│  ├── 单点故障：Coordinator                                 │
│  └── 同步阻塞：等待所有节点响应                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 3PC 三阶段提交

```
Phase 1: CanCommit
Phase 2: PreCommit
Phase 3: DoCommit

改进：
- 减少阻塞时间
- 增加超时处理
- 但仍存在同步阻塞问题
```

---

## 5. Saga 模式

### 5.1 原理

```
Saga 模式：

事务1 → 事务2 → 事务3 → 事务4
  ↓       ↓       ↓       ↓
  C1      C2      C3      C4
  │       │       │       │
  R1      R2      R3      R4 (补偿操作)

特点：
- 长事务，无锁
- 最终一致性
- 每个步骤有对应的补偿操作
```

### 5.2 Go 实现

```go
// saga.go

package saga

import (
    "context"
)

type Step struct {
    Name        string
    Execute     func(context.Context) error
    Compensation func(context.Context) error
}

type Saga struct {
    steps []*Step
}

func (s *Saga) Execute(ctx context.Context) error {
    executed := make([]*Step, 0)
    
    for _, step := range s.steps {
        if err := step.Execute(ctx); err != nil {
            // 执行补偿
            for i := len(executed) - 1; i >= 0; i-- {
                executed[i].Compensation(ctx)
            }
            return err
        }
        executed = append(executed, step)
    }
    
    return nil
}
```

---

## 6. TCC 模式

### 6.1 三阶段

```
Try: 预留资源
Confirm: 确认提交
Cancel: 取消补偿
```

### 6.2 Go 实现

```go
// tcc.go

package tcc

import (
    "context"
)

type TCC interface {
    Try(ctx context.Context, params map[string]interface{}) error
    Confirm(ctx context.Context, params map[string]interface{}) error
    Cancel(ctx context.Context, params map[string]interface{}) error
}

type Transaction struct {
    tcc      TCC
    params   map[string]interface{}
}

func (t *Transaction) Execute(ctx context.Context) error {
    // Try
    if err := t.tcc.Try(ctx, t.params); err != nil {
        return err
    }
    
    // Confirm
    if err := t.tcc.Confirm(ctx, t.params); err != nil {
        // Cancel
        t.tcc.Cancel(ctx, t.params)
        return err
    }
    
    return nil
}
```

---

## 7. 一致性模型

### 7.1 一致性级别

```
┌─────────────────────────────────────────────────────────────┐
│                  一致性模型对比                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  强一致性 (Strong Consistency)                              │
│  ├── 写入后立即可读                                         │
│  ├── 适用于：金融交易                                       │
│  └── 代价：性能低                                           │
│                                                             │
│  最终一致性 (Eventual Consistency)                          │
│  ├── 最终会达到一致                                         │
│  ├── 适用于：社交网络                                       │
│  └── 代价：可能存在短暂不一致                                │
│                                                             │
│  弱一致性 (Weak Consistency)                                │
│  ├── 不保证何时可见                                         │
│  ├── 适用于：日志系统                                       │
│  └── 代价：可能读到旧数据                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 实战案例

### 8.1 分布式锁

```go
// distributed_lock.go

package lock

import (
    "context"
    "time"
)

type DistributedLock struct {
    key   string
    ttl   time.Duration
    value string
}

func (l *DistributedLock) Lock(ctx context.Context) bool {
    // 使用 Redis SET NX PX
    // ...
    return true
}

func (l *DistributedLock) Unlock(ctx context.Context) error {
    // 使用 Lua 脚本原子删除
    // ...
    return nil
}
```

---

## 9. 总结

### 9.1 核心原理回顾

| 算法 | 核心思想 |
|------|----------|
| Paxos | 多数派协议 |
| Raft | 领导选举+日志复制 |
| 2PC | 两阶段提交 |
| Saga | 长事务+补偿 |
| TCC | 预留-确认-取消 |

### 9.2 最佳实践

- [ ] 根据场景选择一致性模型
- [ ] 合理使用分布式锁
- [ ] 实现幂等性
- [ ] 设计补偿机制
- [ ] 监控一致性状态

---

*最后更新：2026-08-11*
*作者：Ryan*
