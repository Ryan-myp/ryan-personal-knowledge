# 消息队列内核深度解析

> 深入消息队列：Kafka、RocketMQ、RabbitMQ内核原理。
> 源码级分析，包含生产环境调优。
> 适用对象：消息队列工程师、后端架构师

---

## 1. Kafka 内核

### 1.1 存储引擎

```
Kafka 存储引擎：

├── Log Segment
│   ├── .log (消息数据)
│   ├── .index (偏移量索引)
│   └── .timeindex (时间索引)
│
├── 零拷贝
│   └── sendfile系统调用
│
├── 顺序写
│   └── 高性能写入
│
└── 分区副本
    ├── Leader
    └── Follower
```

### 1.2 Go 实现 Kafka 核心

```go
// kafka_core.go

package mq

import (
    "sync"
)

type LogSegment struct {
    baseOffset int64
    messages   []*Message
    index      *OffsetIndex
    timeIndex  *TimeIndex
    mu         sync.Mutex
}

type Message struct {
    Offset    int64
    Timestamp int64
    Key       []byte
    Value     []byte
    Headers   map[string]string
}

type OffsetIndex struct {
    entries []IndexEntry
}

type IndexEntry struct {
    Offset   int64
    Position int64
}

type Partition struct {
    topic      string
    partition  int
    segments   []*LogSegment
    leader     *Broker
    replicas   []*Broker
    isr        []*Broker
    mu         sync.RWMutex
}

func (p *Partition) Append(message *Message) error {
    p.mu.Lock()
    defer p.mu.Unlock()
    
    segment := p.getLastSegment()
    if segment == nil || segment.isFull() {
        segment = p.createNewSegment()
    }
    
    message.Offset = segment.getNextOffset()
    segment.append(message)
    
    return nil
}
```

---

## 2. RocketMQ 内核

### 2.1 架构设计

```
RocketMQ 架构：

├── NameServer
│   └── 服务发现

├── Broker
│   ├── MessageStore
│   ├── CommitLog
│   ├── ConsumeQueue
│   └── IndexFile

├── Producer
│   └── 消息发送

└── Consumer
    ├── Push消费
    └── Pull消费
```

### 2.2 Go 实现 RocketMQ

```go
// rocketmq.go

package mq

import (
    "sync"
)

type Broker struct {
    nameServer  *NameServer
    messageStore *MessageStore
    mu          sync.Mutex
}

type MessageStore struct {
    commitLog    *CommitLog
    consumeQueue map[string][]*ConsumeQueue
    indexFile    *IndexFile
}

type CommitLog struct {
    path     string
    segments []*Segment
    mu       sync.Mutex
}

type ConsumeQueue struct {
    topic    string
    queueId  int
    files    []*CqFile
    mu       sync.Mutex
}

type CqFile struct {
    startIndex int64
    endIndex   int64
    data       []byte
}

func (cs *CommitLog) PutMessage(msg *Message) error {
    cs.mu.Lock()
    defer cs.mu.Unlock()
    
    segment := cs.getLastSegment()
    if segment == nil || segment.isFull() {
        segment = cs.createNewSegment()
    }
    
    return segment.append(msg)
}
```

---

## 3. RabbitMQ 内核

### 3.1 架构设计

```
RabbitMQ 架构：

├── Erlang VM
│   └── 高性能运行时

├── 交换机 (Exchange)
│   ├── direct
│   ├── topic
│   ├── headers
│   └── fanout

├── 队列 (Queue)
│   └── 消息存储

└── 绑定 (Binding)
    └── 路由规则
```

### 3.2 Go 实现 RabbitMQ

```go
// rabbitmq.go

package mq

import (
    "sync"
)

type Exchange struct {
    name    string
    type_   string // direct, topic, headers, fanout
    queues  []*Queue
    mu      sync.Mutex
}

type Queue struct {
    name     string
    durable  bool
    messages []*Message
    mu       sync.Mutex
}

type Binding struct {
    exchange string
    queue    string
    routingKey string
}

type RabbitMQ struct {
    exchanges map[string]*Exchange
    queues    map[string]*Queue
    bindings  []Binding
    mu        sync.Mutex
}

func (rmq *RabbitMQ) Publish(exchange string, routingKey string, msg *Message) error {
    rmq.mu.Lock()
    defer rmq.mu.Unlock()
    
    ex := rmq.exchanges[exchange]
    if ex == nil {
        return ErrExchangeNotFound
    }
    
    // 根据交换机类型路由
    switch ex.type_ {
    case "direct":
        rmq.directRouting(ex, routingKey, msg)
    case "topic":
        rmq.topicRouting(ex, routingKey, msg)
    case "fanout":
        rmq.fanoutRouting(ex, msg)
    }
    
    return nil
}
```

---

## 4. 性能调优

### 4.1 调优策略

```
消息队列调优策略：

├── Kafka调优
│   ├── 批量发送
│   ├── 压缩
│   ├── 分区数
│   └── 刷盘策略
│
├── RocketMQ调优
│   ├── 存储路径
│   ├── 刷盘方式
│   └── 消息轨迹
│
└── RabbitMQ调优
    ├── 队列长度
    ├── 消息 TTL
    └── 持久化
```

### 4.2 Go 实现调优

```go
// tuning.go

package mq

type TuningConfig struct {
    Kafka    KafkaTuning
    RocketMQ RocketMQTuning
    RabbitMQ RabbitMQTuning
}

type KafkaTuning struct {
    BatchSize        int
    LingerMs         int
    CompressionType string
    AckMode        string
}

type RocketMQTuning struct {
    FlushDiskType  string
    SyncFlushTimeout int
}

type RabbitMQTuning struct {
    QueueLengthLimit int
    MessageTTL      int
    MaxLength       int
}

func Optimize(config TuningConfig) {
    // 应用调优配置
    applyKafkaTuning(config.Kafka)
    applyRocketMQTuning(config.RocketMQ)
    applyRabbitMQTuning(config.RabbitMQ)
}
```

---

## 5. 总结

### 5.1 核心原理回顾

| 队列 | 特点 | 适用场景 |
|------|------|----------|
| Kafka | 高吞吐 | 日志收集 |
| RocketMQ | 事务消息 | 金融场景 |
| RabbitMQ | 灵活路由 | 企业应用 |

### 5.2 最佳实践

- [ ] 根据场景选择合适的消息队列
- [ ] 合理配置分区和副本
- [ ] 监控队列积压
- [ ] 设计可靠的消费逻辑

---

*最后更新：2026-08-11*
*作者：Ryan*
