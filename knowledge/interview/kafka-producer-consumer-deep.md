# Kafka生产者消费者 - 资深专家深度实现

## 一、架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Kafka 生产者消费者架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Producer              Topic               Consumer                    │
│   ┌─────────┐       ┌─────────┐         ┌─────────┐                   │
│   │ App     │──────►│ Partition│◄────────│ App     │                   │
│   │  producer│       │   0     │         │ Consumer│                   │
│   └─────────┘       ├─────────┤         └────┬────┘                   │
│                      │   ...   │              │                          │
│   ┌─────────┐       ├─────────┤              ▼                          │
│   │ App     │──────►│ Partition│         ┌─────────┐                   │
│   │ producer│       │   N     │         │ Group   │                   │
│   └─────────┘       └─────────┘         └─────────┘                   │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、生产者实现

```go
package kafka

import (
    "context"
    "github.com/segmentio/kafka-go"
)

// ProducerConfig 生产者配置
type ProducerConfig struct {
    Brokers      []string
    Topic        string
    BatchSize    int
    BatchTimeout time.Duration
}

// Producer 生产者
type Producer struct {
    writer *kafka.Writer
}

func NewProducer(config ProducerConfig) *Producer {
    return &Producer{
        writer: &kafka.Writer{
            Addr:         kafka.TCP(config.Brokers...),
            Topic:        config.Topic,
            BatchSize:    config.BatchSize,
            BatchTimeout: config.BatchTimeout,
        },
    }
}

// Send 发送消息
func (p *Producer) Send(ctx context.Context, key, value []byte) error {
    msg := kafka.Message{
        Key:   key,
        Value: value,
    }
    return p.writer.WriteMessages(ctx, msg)
}

// SendBatch 批量发送
func (p *Producer) SendBatch(ctx context.Context, msgs []kafka.Message) error {
    return p.writer.WriteMessages(ctx, msgs...)
}
```

## 三、消费者实现

```go
package kafka

import (
    "context"
)

// ConsumerConfig 消费者配置
type ConsumerConfig struct {
    Brokers      []string
    Topic        string
    GroupID      string
    MinBytes     int
    MaxBytes     int
    MaxPollInterval time.Duration
}

// Consumer 消费者
type Consumer struct {
    reader *kafka.Reader
    handler func(context.Context, kafka.Message) error
}

func NewConsumer(config ConsumerConfig, handler func(context.Context, kafka.Message) error) *Consumer {
    return &Consumer{
        reader: kafka.NewReader(kafka.ReaderConfig{
            Brokers:           config.Brokers,
            Topic:             config.Topic,
            GroupID:           config.GroupID,
            MinBytes:          config.MinBytes,
            MaxBytes:          config.MaxBytes,
            MaxPollInterval:   config.MaxPollInterval,
        }),
        handler: handler,
    }
}

// Consume 消费消息
func (c *Consumer) Consume(ctx context.Context) error {
    for {
        msg, err := c.reader.ReadMessage(ctx)
        if err != nil {
            return err
        }
        
        if err := c.handler(ctx, msg); err != nil {
            // 失败处理
            return err
        }
    }
}
```

## 四、面试高频题

### Q1: 如何保证消息不丢失？

```
A:
1. 生产者ack=all
2. 副本同步
3. 消费者手动提交
```

### Q2: 如何保证消息顺序？

```
A:
1. 单partition
2. 单consumer
3. 幂等生产
```

## 五、自测题

1. 解释生产消费架构
2. 如何实现生产者？
3. 如何保证可靠性？

---

## 参考文档

- [Kafka Docs](https://kafka.apache.org/documentation/)
- [segmentio/kafka-go](https://github.com/segmentio/kafka-go)
