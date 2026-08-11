# Kafka 消息队列深度解析

> 深入 Kafka 核心：日志存储、分区策略、副本机制、流处理。
> 源码级分析，包含生产环境调优。
> 适用对象：消息队列工程师、数据工程师、后端架构师

---

## 1. Kafka 架构

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Kafka 架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Producer (生产者)                                           │
│  ├── 发送消息到 Broker                                      │
│  ├── 分区策略                                                │
│  └── 批量发送                                                │
│                                                             │
│  Broker (服务器)                                             │
│  ├── 存储消息                                               │
│  ├── 处理请求                                               │
│  └── 副本同步                                                │
│                                                             │
│  Consumer (消费者)                                           │
│  ├── 拉取消息                                                │
│  ├── 偏移量管理                                             │
│  └── 消费组                                                 │
│                                                             │
│  ZooKeeper (协调服务)                                        │
│  ├── 集群管理                                               │
│  ├── 选举 Leader                                           │
│  └── 配置管理                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Topic 和 Partition

```
Topic: my-topic

Partition 0          Partition 1          Partition 2
┌─────────┐         ┌─────────┐         ┌─────────┐
│ Log 0   │         │ Log 1   │         │ Log 2   │
├─────────┤         ├─────────┤         ├─────────┤
│ msg 1   │         │ msg A   │         │ msg X   │
│ msg 2   │         │ msg B   │         │ msg Y   │
│ msg 3   │         │ msg C   │         │ msg Z   │
│ ...     │         │ ...     │         │ ...     │
└─────────┘         └─────────┘         └─────────┘
     ▲                    ▲                    ▲
     │                    │                    │
   Offset 0            Offset 0            Offset 0
```

---

## 2. 日志存储

### 2.1 Segment 结构

```
Log Directory: /var/kafka-logs/my-topic-0/

├── 00000000000000000000.index    # 偏移量索引
├── 00000000000000000000.log      # 消息数据
├── 00000000000000000000.timeindex # 时间索引
├── 00000000000000000100.index    # 下一个 segment
├── 00000000000000000100.log
└── log.retention.hours=168       # 保留时间
```

### 2.2 消息格式

```protobuf
// Kafka Record 格式

message Record {
    int64  offset        = 1;  // 消息偏移量
    int64  timestamp     = 2;  // 时间戳
    int32  magic         = 3;  // 格式版本
    int32  attributes    = 4;  // 压缩/编码属性
    bytes  key           = 5;  // 消息键
    bytes  value         = 6;  // 消息值
    map<string, string> headers = 7; // 头信息
}

// 压缩方式
// 0: None
// 1: GZIP
// 2: Snappy
// 3: LZ4
// 4: ZSTD
```

---

## 3. 分区策略

### 3.1 默认策略

```go
// partitioner.go

package kafka

import (
    "hash/crc32"
)

type Partitioner interface {
    Partition(message *Message, numPartitions int) int
}

// 默认分区器：按 key 哈希
type DefaultPartitioner struct{}

func (p *DefaultPartitioner) Partition(message *Message, numPartitions int) int {
    if message.Key == nil {
        // 无 key：轮询
        return p.roundRobin(numPartitions)
    }
    
    // 有 key：哈希
    hash := crc32.ChecksumIEEE(message.Key)
    return int(hash) % numPartitions
}

// 轮询分区器
type RoundRobinPartitioner struct {
    counter uint64
}

func (p *RoundRobinPartitioner) Partition(message *Message, numPartitions int) int {
    idx := atomic.AddUint64(&p.counter, 1) % uint64(numPartitions)
    return int(idx)
}
```

### 3.2 自定义分区

```go
// custom_partitioner.go

package kafka

type CustomPartitioner struct{}

func (p *CustomPartitioner) Partition(message *Message, numPartitions int) int {
    // 按业务逻辑分区
    switch message.Topic {
    case "orders":
        return 0
    case "users":
        return 1
    case "payments":
        return 2
    default:
        return int(crc32.ChecksumIEEE(message.Key)) % numPartitions
    }
}
```

---

## 4. 副本机制

### 4.1 Leader/Follower

```
Topic: orders, Partitions: 3, Replication: 3

Partition 0:
  Leader: Broker 1
  Replicas: [1, 2, 3]
  ISR: [1, 2]  # In-Sync Replicas

Partition 1:
  Leader: Broker 2
  Replicas: [2, 3, 1]
  ISR: [2, 3]

Partition 2:
  Leader: Broker 3
  Replicas: [3, 1, 2]
  ISR: [3, 1, 2]
```

### 4.2 ISR 机制

```c
// isr_manager.c (简化)

typedef struct {
    int leader;           // Leader Broker ID
    int *replicas;        // 所有副本
    int replica_count;
    int *isr;            // 同步副本
    int isr_count;
    int high_watermark;   // 高水位
} PartitionState;

// ISR 收缩：副本落后超过阈值
void shrink_isr(PartitionState *state, int replica_id) {
    // 检查副本延迟
    if (state->replicas[replica_id].lag > max_lag) {
        // 从 ISR 移除
        remove_from_isr(state, replica_id);
    }
}

// ISR 扩展：副本追上 Leader
void expand_isr(PartitionState *state, int replica_id) {
    if (state->replicas[replica_id].lag <= min_lag) {
        add_to_isr(state, replica_id);
    }
}
```

---

## 5. 生产环境调优

### 5.1 Producer 配置

```properties
# producer.properties

# 批量发送
batch.size=16384              # 16KB
linger.ms=5                   # 等待 5ms
buffer.memory=33554432        # 32MB

# 压缩
compression.type=lz4          # LZ4 压缩

# 可靠性
acks=all                      # 所有副本确认
retries=3                     # 重试 3 次
max.in.flight.requests.per.connection=5

# 超时
request.timeout.ms=30000
delivery.timeout.ms=120000
```

### 5.2 Consumer 配置

```properties
# consumer.properties

# 会话超时
session.timeout.ms=30000
heartbeat.interval.ms=10000

# 提交策略
auto.commit.interval.ms=1000
enable.auto.commit=true

# 最大poll记录数
max.poll.records=500

# 消费者组
group.id=my-consumer-group
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 症状 | 排查命令 | 解决方案 |
|------|------|----------|----------|
| 消费滞后 | lag 增长 | `kafka-consumer-groups.sh` | 增加消费者 |
| 消息丢失 | 数据不一致 | 检查 acks | 设置 acks=all |
| 重复消费 | 数据重复 | 检查幂等性 | 实现幂等处理 |
| 磁盘满 | 无法写入 | `du -sh` | 清理旧日志 |

### 6.2 监控指标

```go
// metrics.go

package kafka

import "github.com/prometheus/client_golang/prometheus"

type KafkaMetrics struct {
    messagesIn       prometheus.Counter
    messagesOut      prometheus.Counter
    bytesIn          prometheus.Counter
    bytesOut         prometheus.Counter
    recordFailures   prometheus.Counter
    recordsDelayed   prometheus.Counter
    producerLatency  prometheus.Histogram
    consumerLag      prometheus.Gauge
}

func NewKafkaMetrics() *KafkaMetrics {
    return &KafkaMetrics{
        messagesIn: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "kafka_messages_in_total",
            Help: "Messages received",
        }),
        messagesOut: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "kafka_messages_out_total",
            Help: "Messages sent",
        }),
        bytesIn: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "kafka_bytes_in_total",
            Help: "Bytes received",
        }),
        bytesOut: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "kafka_bytes_out_total",
            Help: "Bytes sent",
        }),
        recordFailures: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "kafka_record_failures_total",
            Help: "Record send failures",
        }),
        recordsDelayed: prometheus.NewCounter(prometheus.CounterOpts{
            Name: "kafka_records_delayed_total",
            Help: "Records delayed",
        }),
        producerLatency: prometheus.NewHistogram(prometheus.HistogramOpts{
            Name:    "kafka_producer_latency_seconds",
            Help:    "Producer latency",
            Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0},
        }),
        consumerLag: prometheus.NewGauge(prometheus.GaugeOpts{
            Name: "kafka_consumer_lag",
            Help: "Consumer lag",
        }),
    }
}
```

---

## 7. 总结

### 7.1 核心原理回顾

| 模块 | 核心机制 |
|------|----------|
| 存储 | Segment + 索引 |
| 分区 | 哈希/轮询策略 |
| 副本 | Leader/Follower + ISR |
| 可靠性 | Ack + 重试 + 幂等 |

### 7.2 最佳实践

- [ ] 合理设置分区数
- [ ] 配置副本同步策略
- [ ] 监控消费滞后
- [ ] 实现幂等处理
- [ ] 定期清理日志

---

*最后更新：2026-08-11*
*作者：Ryan*
