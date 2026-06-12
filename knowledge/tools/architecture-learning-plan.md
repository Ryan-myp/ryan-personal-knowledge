# 架构学习规划

> 从入门到源码级：分布式系统/性能优化/网络协议/安全

---

## 学习路径

| 阶段 | 主题 | 目标 | 时间 |
|------|------|------|------|
| 1 | 分布式系统 | CAP/Paxos/Raft/Gossip | 1 周 |
| 2 | 性能优化 | profiler/trace/eBPF | 1 周 |
| 3 | 网络协议 | TCP/UDP/HTTP2/gRPC | 1 周 |
| 4 | Linux 内核 | 进程/内存/网络/I/O | 1 周 |
| 5 | 安全 | OAuth2/JWT/RBAC/WAF | 1 周 |
| 6 | DevOps | Docker/K8s/ServiceMesh | 1 周 |
| 7 | 系统设计 | 广告/搜索/推荐/IM | 1 周 |
| 8 | 数据库内核 | MVCC/WAL/BloomFilter | 1 周 |

## 推荐资源

- **书籍**：《DDIA》《架构整洁之道》《Go 语言程序设计》
- **论文**：Raft、CFS、BBR
- **工具**：pprof、trace、eBPF、Wireshark

---

## 实战项目

### 用 Go 实现 Raft 共识算法

```go
package main

type RaftNode struct {
    role      string
    term      int
    log       []LogEntry
}

type LogEntry struct {
    Term  int
    Command string
}

func (r *RaftNode) StartCommand(cmd string) {
    if r.role != "leader" {
        return
    }
    
    entry := LogEntry{
        Term:    r.term,
        Command: cmd,
    }
    
    r.log = append(r.log, entry)
    // 复制给 followers
    for _, follower := range r.followers {
        go r.replicate(follower, entry)
    }
}
```

---

## 自测题

### 问题 1
学习分布式系统时，为什么建议先学 Raft 再学 Paxos？

<details>
<summary>查看答案</summary>

1. **Raft 更易理解**：显式的 Leader 选举，日志复制简单
2. **Paxos 复杂**：多阶段协议，实现难度大
3. **实际项目**：Etcd、Consul 都基于 Raft
4. **学习顺序**：Raft → 实现 → Paxos → Multi-Paxos

</details>

---

*本文档基于架构学习规划整理。*
