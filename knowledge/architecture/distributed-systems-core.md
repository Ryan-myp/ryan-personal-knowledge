# 分布式系统核心原理

> CAP 定理 / Paxos / Raft / Gossip / 一致性哈希 — 广告平台分布式架构基石

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要分布式系统理论？

广告平台是一个典型的分布式系统：
- **DSP（需求方平台）**：处理海量实时竞价请求，QPS 百万级
- **SSP（供应方平台）**：管理数百万广告位的库存和变现
- **Ad Exchange（广告交易平台）**：撮合供需双方
- **Ads Manager（广告管理平台）**：管理广告主账户、创意、投放计划

这些系统分布在全球多个数据中心，需要解决：
1. **数据一致性**：广告预算不能超花、竞价结果不能冲突
2. **高可用性**：广告系统 99.99% 可用性，宕机意味着收入损失
3. **低延迟**：实时竞价 RTT < 100ms，RTA（Real-Time API）< 50ms
4. **水平扩展**：QPS 从 1 万到 100 万，系统要能线性扩展

### 分布式系统三大问题

| 问题 | 说明 | 广告平台案例 |
|------|------|-------------|
| **一致性** | 多副本数据是否一致 | 广告主预算扣减不能超扣 |
| **可用性** | 系统是否持续服务 | 竞价接口不能因部分节点故障而不可用 |
| **分区容错** | 网络分区时系统是否可用 | 数据中心间网络断开时，各中心独立服务 |

---

## 第二部分：CAP 定理

### 2.1 CAP 三要素

**CAP 定理**（Brewer's Theorem，2000）：分布式系统不可能同时满足以下三点：

1. **Consistency（一致性）**：所有节点在同一时刻看到的数据是一致的
2. **Availability（可用性）**：每个请求都能收到响应，不保证数据是最新的
3. **Partition Tolerance（分区容错）**：网络分区时系统仍能工作

**核心结论**：在分布式系统中，P 是必须的，所以只能在 C 和 A 之间做权衡。

### 2.2 CA 系统（放弃 P）

传统关系型数据库，单数据中心内：
```
MySQL Master-Slave:
- C: Master 写，Slave 读，强一致
- A: 读请求都有响应
- P: 不满足 — 网络分区时，Slave 不可用，整个集群不可用

适用场景：广告主账户余额查询、预算扣减（强一致性场景）
```

### 2.3 CP 系统（放弃 A）

保证一致性，牺牲可用性：
```
ZooKeeper/Etcd:
- C: 强一致性（基于 Raft 协议）
- A: 分区时部分节点不可用
- P: 满足

适用场景：分布式锁、配置中心、Service Discovery
```

**Go 实现分布式锁示例**：
```go
type DistributedLock struct {
    key   string
    value string
    ttl   time.Duration
}

func (dl *DistributedLock) Lock() bool {
    // SET key value NX EX ttl
    // 原子操作：如果 key 不存在则设置，并设置过期时间
    return redisSetNX(dl.key, dl.value, dl.ttl)
}

func (dl *DistributedLock) Unlock() bool {
    // 只有持有锁的客户端才能释放
    // Lua 脚本：如果 value 匹配则删除
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    result := redisEval(script, []string{dl.key}, dl.value)
    return result == int64(1)
}
```

### 2.4 AP 系统（放弃 C）

保证可用性，牺牲一致性：
```
Cassandra/DynamoDB:
- C: 最终一致性
- A: 总是可用
- P: 满足

适用场景：广告曝光日志、用户行为日志（可接受短暂不一致）
```

### 2.5 广告平台中的 CAP 选择

| 场景 | 选择 | 原因 |
|------|------|------|
| 广告主余额扣减 | CP | 不能超扣，宁可报错 |
| 竞价结果计算 | AP | 延迟敏感，可接受短暂不一致 |
| 广告曝光日志 | AP | 日志可丢失，但最终要统计 |
| 创意审核状态 | CP | 审核状态必须一致 |
| 预算分配 | AP | 实时计算，可容忍误差 |
| 广告投放计划 | CP | 计划必须一致执行 |

---

## 第三部分：Paxos 协议

### 3.1 Paxos 简介

Paxos 是 Leslie Lamport 在 1990 年提出的分布式一致性算法，是 Raft 的前身。

### 3.2 Paxos 角色

| 角色 | 职责 |
|------|------|
| **Proposer**：提议者 | 提出值，发起共识 |
| **Acceptor**：接受者 | 接受或拒绝提议 |
| **Learner**：学习者 | 学习最终的共识值 |

### 3.3 Paxos 两阶段协议

**Phase 1: Prepare（准备阶段）**
1. Proposer 生成唯一的提案号 `n`
2. Proposer 向所有 Acceptor 发送 Prepare(n)
3. Acceptor 如果 n > 已处理的最高提案号，则：
   - 承诺不再接受更低的提案号
   - 返回已接受的最高值（如果有）

**Phase 2: Accept（接受阶段）**
1. Proposer 收到多数 Acceptor 的响应后
2. 如果有 Acceptor 已接受值，则使用该值；否则选择自己的值
3. Proposer 向所有 Acceptor 发送 Accept(n, value)
4. Acceptor 如果 n >= 承诺的最高提案号，则接受该值

### 3.4 Paxos Go 实现（简化版）

```go
type Acceptor struct {
    promisedProposalNumber int
    acceptedProposalNumber int
    acceptedValue          interface{}
}

func (a *Acceptor) Prepare(n int) (int, interface{}, bool) {
    if n > a.promisedProposalNumber {
        a.promisedProposalNumber = n
        return a.acceptedProposalNumber, a.acceptedValue, true
    }
    return 0, nil, false
}

func (a *Acceptor) Accept(n int, value interface{}) bool {
    if n >= a.promisedProposalNumber {
        a.acceptedProposalNumber = n
        a.acceptedValue = value
        return true
    }
    return false
}

type Proposer struct {
    id       string
    proposal int
    acceptors []*Acceptor
}

func (p *Proposer) Propose(value interface{}) interface{} {
    p.proposal++
    n := p.proposal
    
    // Phase 1: Prepare
    responses := make(chan PrepareResponse, len(p.acceptors))
    for _, acc := range p.acceptors {
        go func(acc *Acceptor) {
            num, val, ok := acc.Prepare(n)
            responses <- PrepareResponse{Number: num, Value: val, OK: ok}
        }(acc)
    }
    
    // 收集多数响应
    var maxNum int
    var maxValue interface{}
    
    for i := 0; i < len(p.acceptors); i++ {
        resp := <-responses
        if resp.OK {
            if resp.Number > maxNum {
                maxNum = resp.Number
                maxValue = resp.Value
            }
        }
    }
    
    // Phase 2: Accept
    if maxValue == nil {
        maxValue = value
    }
    
    for _, acc := range p.acceptors {
        go func(acc *Acceptor) {
            acc.Accept(n, maxValue)
        }(acc)
    }
    
    return maxValue
}

type PrepareResponse struct {
    Number int
    Value  interface{}
    OK     bool
}
```

### 3.5 Paxos 变体

| 变体 | 说明 | 应用 |
|------|------|------|
| **Multi-Paxos** | 优化：Leader 确定后，只需 Phase 2 | Raft 的基础 |
| **Viewstamp Replication** | Paxos + 视图切换 | Vbase |
| **Zab** | ZooKeeper 的协议 | ZooKeeper |

---

## 第四部分：Raft 协议

### 4.1 Raft 简介

Raft 是 2014 年斯坦福大学提出的分布式一致性算法，比 Paxos 更易理解。

### 4.2 Raft 角色

| 角色 | 职责 |
|------|------|
| **Leader**：领导者 | 接受客户端请求，复制日志到 Follower |
| **Follower**：跟随者 | 响应 Leader 和 Candidate 的 RPC |
| **Candidate**：候选人 | 竞选 Leader |

### 4.3 Raft 选举流程

```
Follower → Candidate → Leader (如果赢得选举)

步骤:
1. Follower 超时（election timeout，150-300ms 随机）
2. 转变为 Candidate，增加 term，给自己投票
3. 向其他节点发送 RequestVote RPC
4. 如果获得多数投票，成为 Leader
5. 否则超时，重新开始选举

广告平台应用：Etcd 的 Leader 选举
```

### 4.4 Raft 日志复制

```
Leader 收到客户端请求：
1. 追加到本地日志
2. 并行向 Follower 发送 AppendEntries RPC
3. 收到多数 Follower 确认后，提交该日志条目
4. 应用到状态机

Follower 处理 AppendEntries:
- 如果日志不匹配：返回 conflict
- 如果匹配：追加日志，返回 success
- Leader 回退（back off）到第一个不匹配的位置，重新发送
```

### 4.5 Raft Go 实现（简化版）

```go
type Role int

const (
    Follower Role = iota
    Candidate
    Leader
)

type LogEntry struct {
    Term    int
    Index   int
    Command interface{}
}

type RaftNode struct {
    role           Role
    currentTerm    int
    votedFor       string
    logs           []LogEntry
    leaderID       string
    commitIndex    int
    lastApplied    int
    voteCount      int
    nextIndex      map[string]int
    matchIndex     map[string]int
}

func (r *RaftNode) Start(command interface{}) {
    if r.role != Leader {
        return
    }
    
    entry := LogEntry{
        Term:    r.currentTerm,
        Index:   len(r.logs) + 1,
        Command: command,
    }
    
    r.logs = append(r.logs, entry)
    r.commitIndex = len(r.logs)
    
    // 并行复制到 Follower
    for id := range r.nextIndex {
        if id != "self" {
            go r.appendEntries(id, entry)
        }
    }
}

func (r *RaftNode) handleRequestVote(req RequestVote) ResponseVote {
    if req.Term > r.currentTerm {
        r.currentTerm = req.Term
        r.votedFor = ""
        r.role = Follower
    }
    
    if req.Term < r.currentTerm || 
       (req.Term == r.currentTerm && r.votedFor != "" && r.votedFor != req.CandidateID) {
        return ResponseVote{Term: r.currentTerm, VoteGranted: false}
    }
    
    // 检查日志是否最新
    lastLogIndex := len(r.logs)
    lastLogTerm := 0
    if lastLogIndex > 0 {
        lastLogTerm = r.logs[lastLogIndex-1].Term
    }
    
    if req.LastLogTerm < lastLogTerm ||
       (req.LastLogTerm == lastLogTerm && req.LastLogIndex < lastLogIndex) {
        return ResponseVote{Term: r.currentTerm, VoteGranted: false}
    }
    
    r.votedFor = req.CandidateID
    return ResponseVote{Term: r.currentTerm, VoteGranted: true}
}

type RequestVote struct {
    Term         int
    CandidateID  string
    LastLogIndex int
    LastLogTerm  int
}

type ResponseVote struct {
    Term        int
    VoteGranted bool
}
```

### 4.6 Raft 相比 Paxos 的优势

| 特性 | Paxos | Raft |
|------|-------|------|
| 理解难度 | 高 | 低 |
| 实现复杂度 | 高 | 中 |
| Leader 管理 | 不显式 | 显式 |
| 日志复制 | 复杂 | 简单 |
| 生产应用 | ZooKeeper | Etcd、Consul、TiKV |

---

## 第五部分：Gossip 协议

### 5.1 Gossip 简介

Gossip 协议（又称 Epidemic 协议）是一种分布式成员管理协议，通过随机交换信息来传播状态。

### 5.2 Gossip 类型

| 类型 | 说明 | 应用 |
|------|------|------|
| **Push** | 节点将自己的状态推送给随机节点 | 广告曝光日志聚合 |
| **Pull** | 节点从随机节点拉取状态 | 配置同步 |
| **Push-Pull** | 双向交换 | Cassandra、DynamoDB |

### 5.3 Gossip 流程

```
节点 A:
1. 随机选择 n 个节点（fanout）
2. 将自己的状态发送给它们
3. 收到响应后合并状态
4. 重复

节点 B:
1. 收到 A 的状态更新
2. 更新本地状态
3. 随机选择 m 个节点转发
4. ...
```

### 5.4 Gossip Go 实现

```go
type Node struct {
    id      string
    data    map[string]interface{}
    peers   []string
    stopped chan struct{}
}

func (n *Node) gossip() {
    // 随机选择 1-2 个 peer
    fanout := 2
    if len(n.peers) < fanout {
        fanout = len(n.peers)
    }
    
    selected := make([]string, 0, fanout)
    indices := make(map[int]bool)
    for len(selected) < fanout {
        idx := rand.Intn(len(n.peers))
        if !indices[idx] {
            indices[idx] = true
            selected = append(selected, n.peers[idx])
        }
    }
    
    // Push-Pull
    n.mu.RLock()
    data := make(map[string]interface{})
    for k, v := range n.data {
        data[k] = v
    }
    n.mu.RUnlock()
    
    for _, peer := range selected {
        n.push(peer, data)
        pulled := n.pull(peer)
        n.merge(pulled)
    }
}

func (n *Node) merge(remote map[string]interface{}) {
    n.mu.Lock()
    defer n.mu.Unlock()
    
    for k, v := range remote {
        if existing, ok := n.data[k]; ok {
            // 冲突解决：取最新版本
            existingTime := extractTimestamp(existing)
            remoteTime := extractTimestamp(v)
            if remoteTime > existingTime {
                n.data[k] = v
            }
        } else {
            n.data[k] = v
        }
    }
}
```

### 5.5 Gossip 在广告平台的应用

| 场景 | Gossip 优势 |
|------|------------|
| **广告预算同步** | 最终一致即可，不要求强一致 |
| **配置分发** | 分布式配置中心 |
| **故障检测** | 节点健康状态传播 |
| **分布式计数** | 广告曝光计数聚合 |

---

## 第六部分：一致性哈希

### 6.1 传统哈希的问题

```
传统哈希：hash(key) % N

问题：节点增减时，大量 key 需要重新映射
- N 个节点 → N+1 个节点：约 N/(N+1) * 100% 的数据需要迁移
- N=100：约 99% 的数据需要迁移
```

### 6.2 一致性哈希原理

```
1. 将 0 ~ 2^32-1 的整数空间组织成一个环
2. 每个节点哈希到环上的一个点：hash(node_id)
3. 每个 key 也哈希到环上的一个点：hash(key)
4. key 映射到顺时针第一个节点

节点增加：
- 新节点插入环上
- 只影响新节点和顺时针前一个节点之间的 key
- 其他 key 不受影响

节点减少：
- 被移除节点的 key 映射到顺时针下一个节点
```

### 6.3 虚拟节点解决数据倾斜

```
实际中，节点数量远少于环上的点，导致数据倾斜。
解决方案：每个节点对应多个虚拟节点（vnode）

例如：3 个物理节点，每个 150 个虚拟节点 = 450 个环上点
```

### 6.4 一致性哈希 Go 实现

```go
type Map struct {
    hash     Hash
    replicas int
    keys     []int
    hashMap  map[int]string
}

func (m *Map) Add(keys ...string) {
    for _, key := range keys {
        for i := 0; i < m.replicas; i++ {
            hash := int(m.hash([]byte(strconv.Itoa(i) + key)))
            m.keys = append(m.keys, hash)
            m.hashMap[hash] = key
        }
    }
    sort.Ints(m.keys)
}

func (m *Map) Get(key string) string {
    if len(m.keys) == 0 {
        return ""
    }
    
    hash := int(m.hash([]byte(key)))
    idx := sort.Search(len(m.keys), func(i int) bool {
        return m.keys[i] >= hash
    })
    
    if idx == len(m.keys) {
        idx = 0
    }
    
    return m.hashMap[m.keys[idx]]
}
```

### 6.5 一致性哈希在广告平台的应用

| 场景 | 说明 |
|------|------|
| **分片存储** | 用户行为日志分片到多台服务器 |
| **负载均衡** | 请求路由到不同后端 |
| **缓存集群** | Redis Cluster 使用一致性哈希 |
| **微服务实例** | 服务实例的动态增删 |

---

## 第七部分：分布式系统中的其他关键概念

### 7.1 分布式锁

```go
type DistributedLock struct {
    key   string
    value string
    ttl   time.Duration
}

func (dl *DistributedLock) Lock() bool {
    // SET key value NX EX ttl
    return redisSetNX(dl.key, dl.value, dl.ttl)
}

func (dl *DistributedLock) Unlock() bool {
    // Lua 脚本：如果 value 匹配则删除
    script := `
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    `
    result := redisEval(script, []string{dl.key}, dl.value)
    return result == int64(1)
}
```

### 7.2 分布式事务

| 方案 | 说明 | 适用场景 |
|------|------|---------|
| **2PC（两阶段提交）** | 准备 → 提交/回滚 | 强一致场景，性能差 |
| **TCC（Try-Confirm-Cancel）** | 业务层面的补偿事务 | 金融、支付 |
| **Saga** | 长事务分解为多个本地事务 | 微服务 |
| **本地消息表** | 通过消息表实现最终一致 | 订单系统 |

### 7.3 分布式 ID

```go
type Snowflake struct {
    machineID     int64
    sequence      int64
    lastTimestamp int64
}

func (sf *Snowflake) NextID() int64 {
    timestamp := time.Now().UnixMilli()
    
    if timestamp == sf.lastTimestamp {
        sf.sequence++
        if sf.sequence > 4095 {
            for timestamp <= sf.lastTimestamp {
                timestamp = time.Now().UnixMilli()
            }
            sf.sequence = 0
        }
    } else {
        sf.sequence = 0
    }
    
    sf.lastTimestamp = timestamp
    
    // 64 位 ID 分配：
    // 1 位符号 | 41 位时间戳 | 10 位机器 ID | 12 位序列号
    id := (timestamp << 22) | (sf.machineID << 12) | sf.sequence
    return id
}
```

---

## 第八部分：自测题

### 问题 1
广告平台中，哪个场景适合选择 AP 而不是 CP？

<details>
<summary>查看答案</summary>

1. **竞价结果计算**：延迟敏感，RTT < 100ms，可接受短暂不一致
2. **广告曝光日志**：可丢失但需最终统计
3. **用户行为分析**：数据可重建，强一致意义不大
4. **CP 场景**：余额扣减、预算分配（强一致）
5. **关键区别**：延迟 vs 一致性，哪个更重要

</details>

### 问题 2
Raft 选举超时时间为什么是随机的？

<details>
<summary>查看答案</summary>

1. **避免冲突**：如果多个节点同时超时，同时发起选举，选票分散
2. **随机范围**：150-300ms（常见配置），减少选举冲突
3. **选举过程**：
   - 节点 A 超时 → 成为 Candidate，先发 RPC
   - 节点 B 超时 → 可能还没发 RPC，收到 A 的 RequestVote
   - B 投票给 A，A 赢得选举
4. **实际效果**：大多数情况下只有一个节点先发起选举

</details>

### 问题 3
一致性哈希中，为什么需要虚拟节点？

<details>
<summary>查看答案</summary>

1. **数据倾斜**：物理节点少时，环上的分布不均匀
2. **虚拟节点解决**：每个物理节点对应多个虚拟节点
3. **示例**：3 个物理节点 × 150 虚拟节点 = 450 个点
4. **效果**：key 均匀分布在环上，数据均匀分配到物理节点
5. **虚拟节点数选择**：根据节点数量和预期数据量，通常 100-500

</details>

---

*本文档基于分布式系统核心理论整理，结合广告平台实战场景。*
