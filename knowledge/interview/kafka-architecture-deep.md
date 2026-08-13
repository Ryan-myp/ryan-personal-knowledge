# Kafka内核深度 - 资深专家深度实现

## 一、Broker架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Kafka Broker架构                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                        Broker                                   │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │   │
│   │  │ ZooKeeper│  │ Log Dir │  │ Network │  │ Controller│      │   │
│   │  │ Client   │  │ Manager │  │ Server  │  │          │      │   │
│   │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │   │
│   │       │             │             │             │             │   │
│   │  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐      │   │
│   │  │ Topic    │  │ Partition│  │ Producer │  │ Consumer │      │   │
│   │  │ Metadata │  │  Storage │  │  Handler │  │  Handler │      │   │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Partition存储

```java
// kafka.log.Log
public class Log {
    private final String topic;
    private final int partition;
    private final File logDir;
    private final int maxSegmentBytes;
    
    // 索引文件: Offset -> Position
    private final Index index;
    // 位置文件: Offset -> Position  
    private final PositionLog positionLog;
    
    // 当前segment
    private LogSegment activeSegment;
    
    public AppendResult append(MessageSet messages) {
        long baseOffset = activeSegment.sizeInBytes();
        activeSegment.append(baseOffset, messages);
        return new AppendResult(baseOffset, messages.sizeInBytes());
    }
    
    public Message read(long offset, int maxSize) {
        return findSegment(offset).read(offset, maxSize);
    }
}
```

## 三、生产者在流程

```go
package producer

import (
    "sync"
    "time"
)

type Producer struct {
    brokers     []*Broker
    partitioner Partitioner
    batch       *Batch
    acks        AckMode
    
    done chan struct{}
}

func (p *Producer) Send(topic string, key, value []byte) error {
    // 1. 选择partition
    partition := p.partitioner.Partition(topic, key)
    
    // 2. 创建或复用batch
    batch := p.getBatch(topic, partition)
    
    // 3. 追加到batch
    msg := &Message{
        Key:       key,
        Value:     value,
        Timestamp: time.Now(),
    }
    batch.append(msg)
    
    // 4. batch满或超时，发送
    if batch.full() || batch.timeout() {
        return p.sendBatch(topic, partition, batch)
    }
    
    return nil
}

func (p *Producer) sendBatch(topic string, partition int, batch *Batch) error {
    broker := p.brokers[partition % len(p.brokers)]
    
    // 异步发送
    respCh := make(chan *FetchResponse, 1)
    go broker.Send(batch, respCh)
    
    select {
    case resp := <-respCh:
        return resp.Error
    case <-time.After(30 * time.Second):
        return ErrTimeout
    }
}
```

## 四、消费者Group

```go
package consumer

import (
    "sync"
)

type ConsumerGroup struct {
    groupId    string
    members    map[string]*Member
    rebalance  RebalanceStrategy
}

type Member struct {
    id         string
    broker     *Broker
    assignments []TopicPartition
}

// Rebalance策略
type RebalanceStrategy interface {
    Assign(members []*Member, topics []string) map[string][]TopicPartition
}

// Range策略
type RangeStrategy struct{}

func (r *RangeStrategy) Assign(members []*Member, topics []string) map[string][]TopicPartition {
    result := make(map[string][]TopicPartition)
    
    for _, topic := range topics {
        partitions := getPartitions(topic)
        n := len(members)
        
        for i, part := range partitions {
            memberIdx := i % n
            result[members[memberIdx].id] = append(result[members[memberIdx].id], part)
        }
    }
    
    return result
}
```

## 五、面试高频题

### Q1: Kafka为什么快？

```
A:
1. 顺序读写（磁盘顺序读写接近内存随机读写）
2. Zero Copy技术
3. Page Cache
4. 分区并行处理
5. 批量发送和压缩
```

### Q2: 如何保证消息不丢失？

```
A:
• 生产者: acks=all
• Broker: replica-factor ≥ 3
• 消费者: 手动提交offset，处理成功后再提交
```

## 六、自测题

1. Kafka的Leader/Follower机制是什么？
2. 如何设计Kafka的分区策略？
3. Kafka如何保证消息的顺序性？

---

## 参考文档

- [Kafka源码](https://github.com/apache/kafka)
- [Kafka官方文档](https://kafka.apache.org/documentation/)
