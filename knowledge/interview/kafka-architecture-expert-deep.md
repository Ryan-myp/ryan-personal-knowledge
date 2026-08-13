# Kafka架构深度 - 资深专家深度实现

## 一、核心概念

### 1.1 基本术语

```
Producer: 消息生产者
Consumer: 消息消费者
Topic: 消息主题 (分类)
Partition: 分区 (并发单元)
Offset: 消费位点
Broker: 服务器节点
Replica: 副本
Leader: 主副本
Follower: 从副本
ZooKeeper: 协调服务
```

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Kafka Cluster                               │
│                                                                     │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                         │
│  │ Broker 1│    │ Broker 2│    │ Broker 3│                         │
│  │         │    │         │    │         │                         │
│  │ Part 0  │    │ Part 1  │    │ Part 2  │                         │
│  │ Part 1  │    │ Part 2  │    │ Part 0  │                         │
│  │ Part 2  │    │ Part 0  │    │ Part 1  │                         │
│  └─────────┘    └─────────┘    └─────────┘                         │
│                                                                     │
│  ZooKeeper: 元数据管理、Leader选举                                   │
└─────────────────────────────────────────────────────────────────────┘

Producer → Topic → Partition 0, 1, 2
Consumer Group → 每个Partition由一个Consumer处理
```

## 二、数据存储

### 2.1 Log Segment

```
topic-partition目录结构:
┌─────────────────────────────────────────────────────────────┐
│  00000000000000000000.log    # 消息日志                      │
│  00000000000000000000.index  # 偏移量索引                    │
│  00000000000000000000.timeindex # 时间索引                   │
│  00000000000000000030.log    # 新segment (30MB)              │
│  ...                                                          │
└─────────────────────────────────────────────────────────────┘

每个Segment包含:
- 固定大小的消息
- 稀疏索引 (每16KB一个索引条目)
```

### 2.2 Go Producer实现

```go
package kafka

import (
	"context"
	"fmt"
	"github.com/segmentio/kafka-go"
)

type Producer struct {
	writer *kafka.Writer
}

func NewProducer(brokers []string) *Producer {
	return &Producer{
		writer: &kafka.Writer{
			Addr:     kafka.TCP(brokers...),
			Topic:    "orders",
			Balancer: &kafka.LeastBytes{},
		},
	}
}

func (p *Producer) Send(ctx context.Context, key, value []byte) error {
	msg := kafka.Message{
		Key:   key,
		Value: value,
	}
	return p.writer.WriteMessages(ctx, msg)
}

func (p *Producer) Close() error {
	return p.writer.Close()
}
```

## 三、消费模式

### 3.1 Consumer Group

```
Topic: orders (3 partitions)

Consumer Group: order-processors
┌─────────────────────────────────────────────────────────────┐
│  Consumer 1: Partition 0, 1                                  │
│  Consumer 2: Partition 2                                     │
└─────────────────────────────────────────────────────────────┘

扩容:
- 增加Consumer → 重平衡 (Rebalance)
- 减少Consumer → 分区分配
```

### 3.2 Go Consumer实现

```go
package kafka

import (
	"context"
	"fmt"
	"github.com/segmentio/kafka-go"
)

type Consumer struct {
	reader *kafka.Reader
	handler func(context.Context, kafka.Message) error
}

func NewConsumer(brokers []string, groupID, topic string) *Consumer {
	return &Consumer{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers:     brokers,
			GroupID:     groupID,
			Topic:       topic,
			MinBytes:    10e3,  // 10KB
			MaxBytes:    10e6,  // 10MB
			MaxWait:     250 * time.Millisecond,
		}),
	}
}

func (c *Consumer) Start(ctx context.Context) error {
	for {
		msg, err := c.reader.ReadMessage(ctx)
		if err != nil {
			return err
		}
		
		if err := c.handler(ctx, msg); err != nil {
			// 失败处理: 重试或写入死信队列
			fmt.Printf("message handler error: %v\n", err)
		}
	}
}
```

## 四、可靠性保证

### 4.1 ACK机制

```go
// Producer配置
producer := kafka.NewProducer(kafka.ProducerConfig{
	Brokers: []string{"broker1:9092"},
	Topic:   "orders",
	
	// ACK级别:
	// 0: 不等待ACK (最快，可能丢数据)
	// 1: 等待Leader ACK
	// -1: 等待所有ISR副本ACK (最安全)
	Ack: kafka.RequireAll,
})
```

### 4.2 精确一次语义

```
At-Least-Once (至少一次):
- Producer重试 + Consumer幂等

At-Most-Once (至多一次):
- Producer不重试 + Consumer不保存offset

Exactly-Once (精确一次):
- 幂等Producer + 事务Consumer

实现方式:
1. 幂等Producer: producer.id + sequence.number
2. 事务: beginTransaction → sendMessage → commitTransaction
```

## 五、性能调优

### 5.1 Producer优化

```go
config := kafka.ProducerConfig{
	BatchSize:      16384,    // 16KB批量发送
	LingerMs:       10,       // 等待10ms攒批
	MaxInFlightReq: 5,        // 最大并发请求
	Compression:    snappy,   // Snappy压缩
}
```

### 5.2 Consumer优化

```go
config := kafka.ConsumerConfig{
	MaxPollRecords: 500,      // 每次最多拉取500条
	MaxPollInterval: 300000,  // 最大处理时间5分钟
	SessionTimeout:  10000,   // 会话超时10秒
	HeartbeatInterval: 3000,  // 心跳间隔3秒
}
```

## 六、面试高频题

### Q1: Kafka为什么这么快？

```
A:
1. 顺序写磁盘
2. Zero-copy技术
3. 分区并行
4. 页面缓存
```

### Q2: 如何保证消息不丢失？

```
A:
1. Producer: ACK=all + retries
2. Broker: min.insync.replicas=2
3. Consumer: 手动提交offset
```

### Q3: 什么是Rebalance？

```
A: Consumer Group内消费者数量变化时，重新分配分区的过程。
触发条件:
- 消费者增加/减少
- Topic分区变化
- 消费者故障
```

## 七、自测题

1. 解释Kafka的Log Segment结构
2. 如何实现Kafka精确一次语义？
3. Kafka与RabbitMQ的区别？

---

## 参考文档

- [Kafka官方文档](https://kafka.apache.org/documentation/)
- [Kafka: The Definitive Guide](https://www.oreilly.com/library/view/kafka-the-definitive/9781491936153/)
