# Raft共识算法 - 资深专家深度实现

## 一、核心概念

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Raft共识算法                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Role: Leader / Follower / Candidate                                   │
│                                                                         │
│   Leader:                                                                 │
│   • 处理所有客户端请求                                                   │
│   • 复制日志到所有节点                                                   │
│   • 心跳维持权威                                                         │
│                                                                         │
│   Follower:                                                              │
│   • 响应Leader/Candidate请求                                             │
│   • 不主动发起请求                                                         │
│                                                                         │
│   Candidate:                                                             │
│   • 竞选Leader                                                            │
│   • 获取多数票                                                             │
│                                                                         │
│   特点:                                                                   │
│   • 强一致性                                                             │
│   • 容错N/2节点                                                          │
│   • 自动故障转移                                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、选举实现

```go
type State int
const (
    Follower State = iota
    Candidate
    Leader
)

type Node struct {
    state      State
    term       int
    votedFor   int
    log        []Entry
    
    commitIndex int
    lastApplied int
}

func (n *Node) electionTimeout() {
    timeout := time.Duration(rand.Intn(300)) + 150 * time.Millisecond
    
    timer := time.NewTimer(timeout)
    <-timer.C
    
    // 开始竞选
    n.state = Candidate
    n.term++
    n.votedFor = n.id
    
    // 请求投票
    for _, peer := range peers {
        go n.requestVote(peer)
    }
}
```

## 三、日志复制

```go
func (l *Leader) appendEntry(entry Entry) {
    l.log = append(l.log, entry)
    
    // 发送给所有follower
    for _, follower := range l.followers {
        go l.sendAppendEntries(follower, entry)
    }
}

func (l *Leader) commitEntry(index int) {
    // 超过半数节点确认
    ackCount := 0
    for _, follower := range l.followers {
        if follower.matchIndex >= index {
            ackCount++
        }
    }
    
    if ackCount > len(l.followers)/2 {
        l.commitIndex = index
        l.applyToState(l.log[:index])
    }
}
```

## 四、面试高频题

### Q1: Raft如何保证一致性？

```
A:
1. Leader全权处理
2. 多数派确认
3. 日志幂等
```

### Q2: 如何实现故障转移？

```
A:
1. 超时选举
2. Term递增
3. 多数派胜出
```

## 五、自测题

1. 解释Raft三步选举
2. 如何实现日志复制？
3. 如何保证安全性？

---

## 参考文档

- [Raft论文](https://raft.github.io/raft.pdf)
- [etcd实现](https://github.com/etcd-io/etcd)
