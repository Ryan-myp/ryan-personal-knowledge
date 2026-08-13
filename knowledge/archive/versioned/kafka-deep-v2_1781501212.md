# Kafka 核心深度：从 Controller 到 Consumer Group

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解 Kafka

想象一个报社系统：

```
报社 = Kafka Broker
编辑部 = Topic
版面 = Partition
订阅者 = Consumer
文章 = Message
```

**核心优势**：
- **顺序写磁盘**：利用文件系统缓存，顺序写比随机写快 100 倍
- **零拷贝**：sendfile 系统调用，不经过用户态
- **分区并行**：每个 Partition 独立，可以并行处理

---

## 第二部分：Broker 架构深度

### 2.1 目录结构

```
kafka-logs/
├── advertising-events-0/        # Topic: advertising-events, Partition: 0
│   ├── 00000000000000000000.log  # 日志文件（追加写）
│   ├── 00000000000000000000.index # 偏移量索引
│   └── 00000000000000000000.timeindex # 时间索引
├── advertising-events-1/        # Partition: 1
│   ├── 00000000000000000000.log
│   └── ...
└── advertising-events-2/        # Partition: 2
    ├── 00000000000000000000.log
    └── ...
```

### 2.2 日志追加写机制

```go
package kafka

import (
    "os"
    "sync"
    "syscall"
)

// LogSegment 一个日志段
type LogSegment struct {
    baseOffset  int64         // 起始偏移量
    file        *os.File      // 日志文件
    indexFile   *IndexFile    // 偏移量索引
    timeIndex   *IndexFile    // 时间索引
    mu          sync.Mutex
    isCompacted bool          // 是否正在合并
}

// Append 追加消息到日志
// 关键：这是顺序写，非常快
func (ls *LogSegment) Append(messages ...Message) error {
    ls.mu.Lock()
    defer ls.mu.Unlock()
    
    for _, msg := range messages {
        // 1. 写入消息
        data := ls.encodeMessage(msg)
        _, err := ls.file.Write(data)
        if err != nil {
            return err
        }
        
        // 2. 更新索引
        ls.indexFile.Append(msg.Offset, ls.file.Size())
        ls.timeIndex.Append(msg.Timestamp, ls.file.Size())
    }
    
    return nil
}

// 关键参数：log.retention.hours
// 默认 168 小时（7天），日志超过这个时间被删除
// 设置更短可以节省磁盘空间

// 关键参数：log.segment.bytes
// 默认 1GB，每个日志段最大 1GB
// 满了自动创建新段
```

### 2.3 零拷贝（Zero Copy）

```
传统拷贝：
Disk → Kernel Buffer → User Buffer → Socket Buffer → Kernel → Network
         (1)          (2)           (3)           (4)

零拷贝：
Disk → Kernel Buffer → Socket Buffer → Network
         (1)              (2)              (3)

sendfile() 系统调用：
- 数据直接从磁盘到网卡，不经过用户态
- 减少了 3 次用户态到内核态的切换
- 减少了 3 次内存拷贝
```

```go
// 传统拷贝方式
func copyData(file *os.File, conn net.Conn) error {
    buf := make([]byte, 4096)
    for {
        // 1. 磁盘 → 内核缓冲区 → 用户缓冲区（read）
        n, err := file.Read(buf)
        if err != nil {
            return err
        }
        // 2. 用户缓冲区 → 内核缓冲区（write）
        _, err = conn.Write(buf[:n])
        if err != nil {
            return err
        }
    }
}

// 零拷贝方式（sendfile）
import "syscall"

func zeroCopyData(file *os.File, conn net.Conn) error {
    // 数据直接从磁盘到网卡
    _, err := syscall.Sendfile(
        conn.(*net.TCPConn).SyscallConn(),
        file,
        nil,
        4096,
    )
    return err
}
```

---

## 第三部分：Producer 深度

### 3.1 Producer 工作流程

```
1. 创建 Producer
2. 发送消息 → 拦截器 → 序列化器 → Partitioner → Batch → Broker
3. Broker 返回 Ack
4. Producer 处理响应（成功/失败）
```

### 3.2 Partitioner 分区策略

```go
package producer

import (
    "hash/fnv"
    "strconv"
)

// Partitioner 分区器接口
type Partitioner interface {
    Partition(messages []Message, numPartitions int) int
}

// 默认分区器：Key Hash
type KeyHashPartitioner struct{}

func (p *KeyHashPartitioner) Partition(messages []Message, numPartitions int) int {
    key := messages[0].Key
    if key == "" {
        return roundRobin(numPartitions)
    }
    
    // FNV-1a 哈希
    h := fnv.New32a()
    h.Write([]byte(key))
    return int(h.Sum32()) % numPartitions
}

// RoundRobin 轮询分区器
type RoundRobinPartitioner struct {
    counter int
}

func (p *RoundRobinPartitioner) Partition(messages []Message, numPartitions int) int {
    partition := p.counter % numPartitions
    p.counter++
    return partition
}

// 自定义分区器
type CustomPartitioner struct{}

func (p *CustomPartitioner) Partition(messages []Message, numPartitions int) int {
    // 按用户 ID 哈希
    userID := messages[0].Headers["user_id"]
    h := fnv.New32a()
    h.Write([]byte(userID))
    return int(h.Sum32()) % numPartitions
}
```

### 3.3 Ack 机制

| Ack 级别 | 说明 | 性能 | 数据安全性 |
|---------|------|------|-----------|
| **acks=0** | 不等待 Broker 确认 | 最快 | 最低（可能丢消息） |
| **acks=1** | Leader 写入即确认 | 快 | 中（Leader 挂了可能丢） |
| **acks=all** | 所有 ISR 确认 | 最慢 | 最高（不丢） |

```go
// 推荐配置
config := &ProducerConfig{
    Brokers:        []string{"kafka1:9092", "kafka2:9092", "kafka3:9092"},
    AckMode:        kafka.ACK_ALL,       // 最安全
    ReplicationFactor: 3,                // 每个 Partition 3 副本
    MinInSyncReplicas: 2,               // 至少 2 个副本在同步
    BatchSize:      16384,              // 16KB
    LingerMs:       5,                  // 等待 5ms 攒批
    BufferMemory:   33554432,           // 32MB
    CompressionType: "lz4",             // 压缩
}
```

---

## 第四部分：Consumer 深度

### 4.1 Consumer Group

```
Consumer Group: 一组 Consumer 共同消费一个 Topic

Partition 0 → Consumer A (Group 1)
Partition 1 → Consumer B (Group 1)
Partition 2 → Consumer A (Group 1)

Partition 0 → Consumer C (Group 2)  // 另一个 Group 也能消费
Partition 1 → Consumer D (Group 2)
Partition 2 → Consumer C (Group 2)
```

### 4.2 Rebalance 策略

```go
package consumer

import (
    "sync"
)

// RebalanceStrategy 重平衡策略
type RebalanceStrategy int

const (
    RangeStrategy RebalanceStrategy = iota // Range 分配
    RoundRobinStrategy                     // 轮询分配
)

type ConsumerGroup struct {
    members      map[string]*Consumer
    assignments  map[string][]string // consumer → partitions
    mu           sync.Mutex
    strategy     RebalanceStrategy
}

// Range 分配
func (cg *ConsumerGroup) RangeRebalance(topic string, partitions []int) {
    members := cg.getMembers()
    if len(members) == 0 {
        return
    }
    
    consumers := len(members)
    nPartitions := len(partitions)
    
    // 每个消费者分配 partitions/consumers + 余数
    base := nPartitions / consumers
    remainder := nPartitions % consumers
    
    idx := 0
    for i := 0; i < consumers; i++ {
        count := base
        if i < remainder {
            count++
        }
        
        consumerID := getConsumerID(i)
        cg.assignments[consumerID] = partitions[idx : idx+count]
        idx += count
    }
}

// 关键参数：partition.assignment.strategy
// RangeAssignor: 默认，简单但可能不均
// RoundRobinAssignor: 轮询，更均匀
// StickyAssignor: 粘性分配，减少移动
```

### 4.3 提交偏移量

```go
// AutoCommit vs Manual Commit
config.AutoCommitEnabled = false  // 推荐手动提交
config.CommitInterval = 5 * time.Second

// 手动提交
func (c *Consumer) ProcessMessage(msg Message) error {
    // 1. 处理消息
    err := c.process(msg)
    if err != nil {
        return err
    }
    
    // 2. 手动提交偏移量
    c.Commit()
    
    return nil
}

// at-least-once 语义：先提交，后处理（可能重复）
// at-most-once 语义：先处理，后提交（可能丢消息）
// exactly-once 语义：幂等 Producer + 事务
```

---

## 第五部分：Controller 深度

### 5.1 Controller 选举

```
Controller 是 Kafka 集群的"大脑"，负责：
1. Partition Leader 选举
2. ISR（In-Sync Replicas）管理
3. Topic 创建/删除
4. Partition 重分配
5. Broker 下线检测
```

```go
package controller

import (
    "time"
)

// Controller 选举流程
// 1. 所有 Broker 启动时尝试创建 /controller ZNode
// 2. 成功创建的成为 Controller
// 3. Controller 过期时（90秒）重新选举
// 4. 使用 ephemeral node 保证只有一个 Controller

type ZKController struct {
    sessionTimeout  time.Duration
    zkClient        *ZKClient
    isController    bool
}

func (zk *ZKController) ElectController(brokerID int) error {
    // 创建 ephemeral ZNode
    path := fmt.Sprintf("/controller/brokers/%d", brokerID)
    err := zk.zkClient.CreateEphemeral(path, []byte(fmt.Sprintf(`{"version":1,"broker":%d,"timestamp":"%d"}`, brokerID, time.Now().Unix())))
    if err != nil {
        return err
    }
    
    zk.isController = true
    go zk.monitor()
    return nil
}

func (zk *ZKController) monitor() {
    ticker := time.NewTicker(90 * time.Second) // 90 秒过期
    defer ticker.Stop()
    
    for range ticker.C {
        // 检查自己是否还是 Controller
        if !zk.zkClient.Exists("/controller") {
            zk.isController = false
            // 尝试重新选举
            zk.ElectController(myBrokerID)
        }
    }
}
```

### 5.2 ISR（In-Sync Replicas）

```
ISR: 跟 Leader 保持同步的副本集合

Leader: Partition 0
ISR: [Leader, Replica1, Replica2]

如果 Replica3 延迟超过 replica.lag.time.max.ms (默认 10s)：
→ Replica3 被移出 ISR

如果 ISR 只剩 1 个（Leader 自己）：
→ min.insync.replicas=2 的生产者会报错！
```

---

## 第六部分：生产排障案例

### 6.1 消费延迟高

```
现象：Consumer Group 消费延迟持续增长

排查步骤：
1. kafka-consumer-groups.sh --describe --group mygroup
2. 检查 Consumer 处理逻辑是否太慢
3. 检查 Broker 负载
4. 增加 Consumer 数量或分区数
```

### 6.2 Leader 频繁切换

```
现象：Partition Leader 频繁切换

排查：
1. kafka-topics.sh --describe --topic mytopic
2. 检查 Broker 是否经常重启
3. 检查 replica.lag.time.max.ms 是否太短
4. 检查网络是否稳定
```

---

## 第七部分：自测题

### 问题 1
Kafka 为什么比 RabbitMQ 吞吐量大？

<details>
<summary>查看答案</summary>

1. **顺序写磁盘**：利用文件系统缓存
2. **零拷贝**：sendfile 减少拷贝
3. **分区并行**：每个 Partition 独立
4. **批量处理**：Producer/Consumer 都支持批量
5. **简单协议**：二进制协议，无复杂路由

</details>

### 问题 2
Consumer Rebalance 会阻塞消费吗？

<details>
<summary>查看答案</summary>

1. **Range 策略**：会短暂阻塞
2. **Sticky 策略**：增量 Rebalance，阻塞时间短
3. **Cooperative 策略**：增量 Rebalance，几乎不阻塞
4. **优化**：增加 session.timeout.ms
5. **注意**：Rebalance 期间消费暂停

</details>

### 问题 3
Kafka 怎么保证消息不丢失？

<details>
<summary>查看答案</summary>

1. **Producer**：acks=all + retries>0
2. **Broker**：replication.factor=3 + min.insync.replicas=2
3. **Consumer**：手动提交偏移量
4. **Topic**：cleanup.policy=compact
5. **监控**：监控 ISR 数量和消费延迟

</details>

---

*本文档基于 Kafka 源码和生产实战整理。*