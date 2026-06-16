# 分布式系统深度：一致性协议/分布式事务/一致性哈希

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解分布式系统

```
分布式系统 = 多人合作完成一个项目

挑战：
1. 通信延迟：发邮件比说话慢
2. 节点故障：有人请假
3. 数据一致：大家看到的版本要一样
4. 时钟同步：大家的表要对齐
```

### 分布式系统核心问题

```
1. 一致性（Consistency）：所有节点数据相同
2. 可用性（Availability）：系统始终可用
3. 分区容忍性（Partition Tolerance）：网络分区仍能工作

CAP 定理：只能选两个
→ CP：强一致性，可能不可用
→ AP：高可用，可能不一致
→ CA：理论存在，实际不可能（网络总会分区）
```

---

## 第二部分：Raft 共识算法

### 2.1 Raft 原理

```
Raft 节点状态：
- Follower：被动接收命令
- Candidate：竞选 Leader
- Leader：处理所有请求

选举流程：
1. Follower 超时 → 转为 Candidate
2. Candidate 投票给自己
3. 请求其他节点投票
4. 获得多数票 → 成为 Leader

日志复制：
1. Leader 接收客户端请求
2. Leader 追加到自己的日志
3. Leader 复制给 Follower
4. Follower 确认后，Leader 提交
```

### 2.2 Go 实现 Raft

```go
package raft

import (
    "context"
    "fmt"
    "sync"
    "time"
)

type State int

const (
    Follower State = iota
    Candidate
    Leader
)

// Node Raft 节点
type Node struct {
    id            string
    state         State
    currentTerm   int
    votedFor      string
    log           []Entry
    commitIndex   int
    lastApplied   int
    
    leaders     map[string]bool
    votes       map[string]bool
    nextIndex   map[string]int
    matchIndex  map[string]int
    
    mu          sync.RWMutex
    applyCh     chan Entry
    leaderCh    chan string
}

type Entry struct {
    Term    int
    Command interface{}
}

// Start 启动节点
func (n *Node) Start(ctx context.Context, command interface{}) error {
    n.mu.Lock()
    defer n.mu.Unlock()
    
    if n.state != Leader {
        return fmt.Errorf("not leader")
    }
    
    entry := Entry{
        Term:    n.currentTerm,
        Command: command,
    }
    
    n.log = append(n.log, entry)
    
    // 复制给 Follower
    for peer := range n.leaders {
        go n.replicate(peer, entry)
    }
    
    return nil
}

// replicate 复制日志
func (n *Node) replicate(peer string, entry Entry) {
    // 发送 AppendEntries RPC
    // 等待确认
    // 更新 matchIndex
}

// elect 选举
func (n *Node) elect(ctx context.Context) {
    n.mu.Lock()
    n.state = Candidate
    n.currentTerm++
    n.votedFor = n.id
    n.votes = map[string]bool{n.id: true}
    n.mu.Unlock()
    
    // 请求投票
    for peer := range n.leaders {
        go n.requestVote(peer)
    }
    
    // 等待选举结果
    select {
    case <-ctx.Done():
        return
    case votes := <-n.votesCh:
        if len(votes) > len(n.leaders)/2 {
            n.mu.Lock()
            n.state = Leader
            n.mu.Unlock()
            n.leaderCh <- n.id
        }
    }
}
```

---

## 第三部分：分布式事务

### 3.1 分布式事务模式

```
1. 两阶段提交（2PC）
   → 协调者询问所有参与者
   → 所有同意才提交
   
2. 三阶段提交（3PC）
   → 增加预提交阶段
   → 减少阻塞时间
   
3. Saga 模式
   → 长事务拆分为短事务
   → 每个步骤有补偿操作
   
4. TCC 模式
   → Try/Confirm/Cancel
   → 应用层控制的分布式事务
```

### 3.2 Go 实现 Saga 模式

```go
package saga

import (
    "context"
    "fmt"
)

// Step Saga 步骤
type Step struct {
    Name        string
    Action      func(context.Context) error
    Compensation func(context.Context) error
}

// Saga Saga 编排器
type Saga struct {
    steps []Step
}

// NewSaga 创建 Saga
func NewSaga(steps []Step) *Saga {
    return &Saga{steps: steps}
}

// Execute 执行 Saga
func (s *Saga) Execute(ctx context.Context) error {
    executed := 0
    
    // 正向执行
    for i, step := range s.steps {
        if err := step.Action(ctx); err != nil {
            executed = i
            // 回滚已执行的步骤
            for j := executed - 1; j >= 0; j-- {
                if compErr := s.steps[j].Compensation(ctx); compErr != nil {
                    fmt.Printf("compensation failed: %v\n", compErr)
                }
            }
            return err
        }
    }
    
    return nil
}

// 使用示例
saga := NewSaga([]Step{
    {
        Name: "create_order",
        Action: func(ctx context.Context) error {
            // 创建订单
            return nil
        },
        Compensation: func(ctx context.Context) error {
            // 取消订单
            return nil
        },
    },
    {
        Name: "deduct_inventory",
        Action: func(ctx context.Context) error {
            // 扣减库存
            return nil
        },
        Compensation: func(ctx context.Context) error {
            // 恢复库存
            return nil
        },
    },
    {
        Name: "charge_payment",
        Action: func(ctx context.Context) error {
            // 扣款
            return nil
        },
        Compensation: func(ctx context.Context) error {
            // 退款
            return nil
        },
    },
})

err := saga.Execute(ctx)
if err != nil {
    // 自动回滚
}
```

---

## 第四部分：一致性哈希

### 4.1 一致性哈希原理

```
传统哈希：
hash(key) % N
→ 节点变化时，大部分数据需要迁移

一致性哈希：
1. 将哈希空间组织成环
2. 数据和节点都映射到环上
3. 顺时针找到最近的节点

优势：
→ 节点增减时，只影响相邻节点
→ 数据迁移量最小
```

### 4.2 Go 实现一致性哈希

```go
package consistenthash

import (
    "hash/crc32"
    "sort"
    "sync"
)

// Hash 哈希函数
type Hash func([]byte) uint32

// Map 一致性哈希环
type Map struct {
    hashFunc   Hash
    replicas   int
    keys       []uint32
    hashMap    map[uint32]string
    mu         sync.RWMutex
}

// New 创建一致性哈希
func New(replicas int, fn Hash) *Map {
    m := &Map{
        hashFunc: fn,
        replicas: replicas,
        hashMap:  make(map[uint32]string),
    }
    
    if m.hashFunc == nil {
        m.hashFunc = crc32.ChecksumIEEE
    }
    
    return m
}

// Add 添加节点
func (m *Map) Add(nodes ...string) {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    for _, node := range nodes {
        for i := 0; i < m.replicas; i++ {
            hash := m.hashFunc([]byte(fmt.Sprintf("%s-%d", node, i)))
            m.keys = append(m.keys, hash)
            m.hashMap[hash] = node
        }
    }
    
    sort.Slice(m.keys, func(i, j int) bool {
        return m.keys[i] < m.keys[j]
    })
}

// Get 获取节点
func (m *Map) Get(key string) string {
    m.mu.RLock()
    defer m.mu.RUnlock()
    
    if len(m.keys) == 0 {
        return ""
    }
    
    hash := m.hashFunc([]byte(key))
    
    // 二分查找
    idx := sort.Search(len(m.keys), func(i int) bool {
        return m.keys[i] >= hash
    })
    
    // 环回
    if idx == len(m.keys) {
        idx = 0
    }
    
    return m.hashMap[m.keys[idx]]
}
```

---

## 第五部分：生产排障案例

### 5.1 Raft 选举风暴

```
现象：Leader 频繁更换

排查：
1. 检查网络延迟
2. 检查心跳间隔
3. 检查选举超时

根因：网络抖动导致心跳丢失

解决方案：
1. 调整选举超时时间
2. 增加心跳频率
3. 优化网络
```

### 5.2 分布式事务超时

```
现象：Saga 执行超时

排查：
1. 检查每个步骤的执行时间
2. 检查补偿操作的可靠性
3. 检查重试机制

根因：库存扣减步骤慢

解决方案：
1. 异步化处理
2. 增加超时时间
3. 优化数据库查询
```

---

## 第六部分：自测题

### 问题 1
Raft 相比 Paxos 有什么优势？

<details>
<summary>查看答案</summary>

1. **可理解性**：更容易理解和实现
2. **强 Leader**：所有请求通过 Leader
3. **日志复制**：清晰的日志复制机制
4. **节点加入**：支持动态加入
5. **Go 实现**：etcd 使用 Raft

</details>

### 问题 2
Saga 模式相比 2PC 有什么优势？

<details>
<summary>查看答案</summary>

1. **无锁**：不需要分布式锁
2. **高性能**：异步执行
3. **容错性**：部分失败可补偿
4. **适用场景**：长事务
5. **Go 实现**：Saga 编排器

</details>

### 问题 3
一致性哈希相比普通哈希有什么优势？

<details>
<summary>查看答案</summary>

1. **最小迁移**：节点增减影响小
2. **负载均衡**：虚拟节点均匀分布
3. **适用场景**：分布式缓存
4. **Go 实现**：consistenthash
5. **虚拟节点**：解决数据倾斜

</details>

---

*本文档基于分布式系统原理整理。*