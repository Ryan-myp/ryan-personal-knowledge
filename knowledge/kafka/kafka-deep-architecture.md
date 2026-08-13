# Apache Kafka 深度架构解析

> 深入 Kafka 内核：Broker 架构、Producer 原理、Consumer 机制、Partition 策略。
> 适用对象：消息队列工程师、大数据开发工程师

---

## 1. Kafka 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Kafka 集群架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Producer                                                        │
│     │                                                           │
│     │  Topic: orders                                             │
│     ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Broker 1    │  Broker 2    │  Broker 3    │  Broker 4  │   │
│  │              │              │              │            │   │
│  │  [Partition] │  [Partition] │  [Partition] │            │   │
│  │  [Partition] │  [Partition] │  [Partition] │            │   │
│  │  [Partition] │  [Partition] │              │            │   │
│  │   Replicas   │   Replicas   │   Replicas   │            │   │
│  └─────────────────────────────────────────────────────────┘   │
│            │                  │                 │               │
│            └──────────────────┴────────┬────────┘               │
│                                   │                                 │
│                              ZooKeeper                        Kafka  │
│                         (Controller选举)                     (KRaft) │
│                                                                 │
│  Consumer Groups:                                                │
│  Group A: C1, C2 (各消费一个 Partition)                          │
│  Group B: C3, C4, C5 (各消费一个 Partition)                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Producer 原理

### 2.1 发送流程

```go
// Producer 发送流程
1. 序列化: Key/Value → bytes
2. Partitioner: 计算目标 Partition
3. Batch: 累积到 Buffer
4. Sender: 批量发送请求
5. Ack: 等待 Broker 响应
```

### 2.2 分区策略

```java
// Kafka 内置分区器
public int partition(String topic, Object key, byte[] keyBytes, 
                     Object value, byte[] valueBytes, Cluster cluster) {
    List<PartitionInfo> partitions = cluster.partitionsForTopic(topic);
    int numPartitions = partitions.size();
    
    if (keyBytes == null) {
        // 轮询分配
        return stickyCounter.incrementAndGet() % numPartitions;
    }
    
    // MurmurHash2 哈希
    int hash = Utils.toPositive(murmur2(keyBytes));
    return hash % numPartitions;
}
```

---

## 3. Consumer 机制

### 3.1 Consumer Group

```
Topic: orders (6 Partitions)

Consumer Group A:
  C1 → Partition 0, 1, 2
  C2 → Partition 3, 4, 5
  
Consumer Group B:
  C3 → Partition 0, 1, 2
  C4 → Partition 3, 4, 5
```

### 3.2 Rebalance 策略

```go
type RebalanceListener interface {
    OnPartitionsRevoked Lost
    OnPartitionsAssigned Assigned
}

// Rebalance 触发条件:
// 1. Consumer 加入/退出 Group
// 2. Topic 创建/删除
// 3. Partition 增加/减少
// 4. Consumer 心跳超时
```

---

## 4. 消息语义

```
┌─────────────────────────────────────────────────────────────────┐
│                     消息投递语义                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  At Most Once (最多一次)                                        │
│  ├── 发送后不等待 ACK                                           │
│  ├── 可能丢消息                                                 │
│  └── 适用于: 日志收集、监控数据                                 │
│                                                                 │
│  At Least Once (至少一次)                                       │
│  ├── 发送等待 ACK (acks=all)                                    │
│  ├── 可能重复，但不丢                                           │
│  ├── 消费者需实现幂等                                           │
│  └── 适用于: 订单处理、支付                                     │
│                                                                 │
│  Exactly Once (精确一次)                                        │
│  ├── 事务支持 (isolation.level=read_committed)                  │
│  ├── 幂等 Producer + 事务 Consumer                              │
│  ├── 成本高                                                     │
│  └── 适用于: 金融、计费                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. 性能优化

### 5.1 Producer 配置

```properties
# 批量发送
linger.ms=5
batch.size=16384
buffer.memory=33554432

# 压缩
compression.type=lz4

# ACK 策略
acks=all  # 最安全
acks=1    # 折中
acks=0    # 最快
```

### 5.2 Consumer 配置

```properties
# 拉取策略
max.poll.records=500
fetch.min.bytes=1
fetch.max.wait.ms=500

# 偏移量提交
enable.auto.commit=false
auto.offset.reset=latest
```

---

## 6. 运维实践

```bash
# 查看 Topic 信息
kafka-topics.sh --describe --topic orders --bootstrap-server broker:9092

# 查看 Consumer Group
kafka-consumer-groups.sh --describe --group order-group --bootstrap-server broker:9092

# 查看 Lag
kafka-consumer-groups.sh --describe --group order-group --bootstrap-server broker:9092 --all-topics
```

---

**参考**: Kafka 官方文档、KIP 提案、LinkedIn Kafka 实践经验
