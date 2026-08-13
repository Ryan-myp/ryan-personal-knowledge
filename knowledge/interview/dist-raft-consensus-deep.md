# Raft共识算法 - 资深专家深度实现

## 一、Raft状态机

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Raft状态机                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────┐    RequestVote    ┌─────────┐    AppendEntries  ┌──────┐ │
│   │ Follower │◄────────────────│Candidate │───────────────▶│Leader  │ │
│   └────┬────┘   (超时)         └────┬────┘   (获得多数)    └───┬───┘ │
│        │                            │                          │      │
│        │ 选举超时                    │ 获得票数                   │ 心跳  │
│        ▼                            ▼                          ▼      │
│   ┌─────────┐                   ┌─────────┐                 ┌──────┐ │
│   │ Follower │◄────────────────│ Candidate │◄──────────────│ Leader │ │
│   └─────────┘   (发现更高term)   └─────────┘   (失去多数)    └──────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、核心数据结构

```go
package raft

import (
    "sync"
    "time"
)

type StateRole int

const (
    Follower StateRole = iota
    Candidate
    Leader
)

type Raft struct {
    mu            sync.Mutex
    peers         []*Peer
    me            int
    
    state         StateRole
    term          int
    votedFor      int
    commitIndex   int
    lastApplied   int
    
    nextIndex  []int
    matchIndex []int
    
    electionTimeout  time.Duration
    heartbeatInterval time.Duration
}
```

## 三、领导者选举

```go
func (r *Raft) startElection() {
    r.mu.Lock()
    defer r.mu.Unlock()
    
    r.state = Candidate
    r.term++
    r.votedFor = r.me
    r.resetElectionTimeout()
    
    args := RequestVoteArgs{
        Term:         r.term,
        CandidateID:  r.me,
        LastLogIndex: r.lastLogIndex(),
        LastLogTerm:  r.lastLogTerm(),
    }
    
    for i := range r.peers {
        if i != r.me {
            go r.sendRequestVote(i, args)
        }
    }
}

func (r *Raft) becomeLeader() {
    r.state = Leader
    r.grantedVotes = 0
    
    lastIdx := r.lastLogIndex()
    for i := range r.peers {
        r.nextIndex[i] = lastIdx + 1
        r.matchIndex[i] = 0
    }
    
    r.sendHeartbeats()
}
```

## 四、日志复制

```go
func (r *Raft) appendEntries(peer int) {
    r.mu.Lock()
    nextIdx := r.nextIndex[peer]
    prevIdx := nextIdx - 1
    prevTerm := r.logTerm(prevIdx)
    
    entries := r.getLog(nextIdx)
    args := AppendEntriesArgs{
        Term:         r.term,
        LeaderID:     r.me,
        PrevLogIndex: prevIdx,
        PrevLogTerm:  prevTerm,
        Entries:      entries,
        CommitIndex:  r.commitIndex,
    }
    r.mu.Unlock()
    
    var reply AppendEntriesReply
    r.peers[peer].RPC(&args, &reply)
    
    r.mu.Lock()
    defer r.mu.Unlock()
    
    if reply.Success {
        r.nextIndex[peer] = reply.NextIndex
        r.matchIndex[peer] = reply.NextIndex - 1
        r.tryCommit()
    } else {
        r.nextIndex[peer]--
    }
}
```

## 五、面试高频题

### Q1: Raft相比Paxos有什么优势？

```
A:
• Raft强调可理解性，分成三个子问题
• Paxos难以理解和实现
• Raft有明确的领导者
```

### Q2: Raft如何解决脑裂问题？

```
A:
• 多数派机制
• 任期机制
• 心跳机制
```

## 六、自测题

1. 解释Raft的领导者选举流程
2. Raft的日志复制如何保证一致性？
3. 如何处理Raft中的日志压缩？

---

## 参考文档

- [Raft Paper](https://raft.github.io/raft.pdf)
- [etcd Raft实现](https://github.com/etcd-io/etcd)
