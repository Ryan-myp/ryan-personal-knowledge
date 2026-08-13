# Raft共识算法 - 资深专家深度实现

## 一、状态机模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Raft状态机                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Follower                                                             │
│   ├── 接收AppendEntries RPC                                              │
│   ├── 投票给先到达的Candidate                                             │
│   └── 心跳超时 → 成为Candidate                                            │
│                                                                         →
│   Candidate                                                            │
│   ├── 发起选举                                                          │
│   ├── 发送RequestVote RPC                                                │
│   └── 获得多数票 → 成为Leader                                            │
│                                                                         →
│   Leader                                                                 │
│   ├── 发送心跳                                                              │
│   ├── 复制日志                                                              │
│   └── 确定Committed Entry                                                │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、日志复制

```go
type LogEntry struct {
    Term     int
    Index    int
    Command  interface{}
}

// Leader复制日志
func (l *Leader) appendEntry(entry LogEntry) {
    l.mu.Lock()
    defer l.mu.Unlock()
    
    l.logs = append(l.logs, entry)
    l.nextIndex[l.peers] = len(l.logs) + 1
    
    // 向所有Follower复制
    for peer := range l.peers {
        l.sendAppendEntries(peer, entry)
    }
}

// Follower处理
func (f *Follower) applyEntry(index int) {
    if index > f.commitIndex {
        entry := f.log[index]
        f.stateMachine.Apply(entry.Command)
        f.commitIndex = index
    }
}
```

## 三、面试高频题

### Q1: 如何保证安全性？

```
A:
1. 多数派原则
2. Term单调递增
3. Leader完整性
```

### Q2: 如何选择Leader？

```
A:
1. 投票机制
2. 先至原则
3. 随机超时
```

## 四、自测题

1. 解释Raft三状态
2. 如何实现日志复制？
3. 如何处理脑裂？

---

## 参考文档

- [Raft论文](https://raft.github.io/raft.pdf)
- [etcd实现](https://github.com/etcd-io/etcd)
