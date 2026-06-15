# 消息队列进阶：RocketMQ/Pulsar/消息幂等/顺序消息

> 消息队列对比/事务消息/延迟消息/死信队列/消息堆积

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要消息队列？

广告平台使用消息队列：
- **异步处理**：日志收集、数据分析
- **流量削峰**：竞价高峰平滑
- **系统解耦**：服务间通信
- **可靠传输**：保证消息不丢失

### 消息队列对比

| 特性 | Kafka | RocketMQ | Pulsar |
|------|-------|----------|--------|
| 吞吐量 | 最高 | 高 | 高 |
| 延迟 | 低 | 最低 | 低 |
| 事务消息 | 不支持 | 支持 | 支持 |
| 顺序消息 | 分区级 | 全局/分区 | 分区级 |
| 积压能力 | 最强 | 强 | 强 |

---

## 第二部分：消息幂等

### 2.1 幂等性设计

```go
package middleware

import (
    "context"
    "sync"
)

// IdempotencyChecker 幂等检查器
type IdempotencyChecker struct {
    processed map[string]bool
    mu        sync.RWMutex
}

func NewIdempotencyChecker() *IdempotencyChecker {
    return &IdempotencyChecker{
        processed: make(map[string]bool),
    }
}

func (ic *IdempotencyChecker) Check(messageID string) bool {
    ic.mu.Lock()
    defer ic.mu.Unlock()
    
    if ic.processed[messageID] {
        return false // 已处理
    }
    
    ic.processed[messageID] = true
    return true // 未处理
}

// 带过期时间的幂等检查
type IdempotencyCheckerWithTTL struct {
    processed map[string]*entry
    mu        sync.RWMutex
    ttl       time.Duration
}

type entry struct {
    timestamp time.Time
}

func (ic *IdempotencyCheckerWithTTL) Check(messageID string) bool {
    ic.mu.Lock()
    defer ic.mu.Unlock()
    
    // 清理过期记录
    ic.cleanup()
    
    if entry, ok := ic.processed[messageID]; ok {
        return false
    }
    
    ic.processed[messageID] = &entry{
        timestamp: time.Now(),
    }
    return true
}

func (ic *IdempotencyCheckerWithTTL) cleanup() {
    now := time.Now()
    for id, entry := range ic.processed {
        if now.Sub(entry.timestamp) > ic.ttl {
            delete(ic.processed, id)
        }
    }
}
```

### 2.2 数据库幂等

```go
func (s *Service) ProcessMessage(msg Message) error {
    // 使用唯一约束保证幂等
    _, err := s.db.Exec(`
        INSERT INTO message_processing (message_id, status, created_at)
        VALUES (?, 'processing', NOW())
        ON DUPLICATE KEY UPDATE status = 'processing'
    `, msg.ID)
    
    if err != nil {
        return err
    }
    
    // 处理消息
    result, err := s.process(msg)
    if err != nil {
        s.db.Exec(`UPDATE message_processing SET status = 'failed' WHERE message_id = ?`, msg.ID)
        return err
    }
    
    // 标记成功
    s.db.Exec(`UPDATE message_processing SET status = 'success' WHERE message_id = ?`, msg.ID)
    return result
}
```

---

## 第三部分：顺序消息

### 3.1 分区顺序

```go
type OrderedProducer struct {
    broker *Broker
}

func (op *OrderedProducer) SendOrdered(topic string, message Message, hashKey string) error {
    // 1. 计算分区
    partition := op.calculatePartition(hashKey)
    
    // 2. 发送消息到指定分区
    err := op.broker.Send(topic, partition, message)
    if err != nil {
        return err
    }
    
    return nil
}

func (op *OrderedProducer) calculatePartition(hashKey string) int {
    hash := crc32.ChecksumIEEE([]byte(hashKey))
    return int(hash % uint32(op.broker.PartitionCount))
}
```

### 3.2 消费者顺序消费

```go
type OrderedConsumer struct {
    broker     *Broker
    handlers   map[int]MessageHandler
    mu         sync.Mutex
}

func (oc *OrderedConsumer) Consume(topic string, handler MessageHandler) error {
    partitionCount := oc.broker.PartitionCount
    
    oc.mu.Lock()
    oc.handlers = make(map[int]MessageHandler)
    oc.mu.Unlock()
    
    // 每个分区一个 goroutine
    for i := 0; i < partitionCount; i++ {
        go func(partition int) {
            for {
                messages, err := oc.broker.Consume(topic, partition)
                if err != nil {
                    continue
                }
                
                // 顺序处理分区内消息
                for _, msg := range messages {
                    handler(msg)
                }
            }
        }(i)
    }
    
    return nil
}
```

---

## 第四部分：延迟消息和死信队列

### 4.1 延迟消息

```go
type DelayMessageQueue struct {
    broker   *Broker
    schedule *time.Ticker
}

func (dmq *DelayMessageQueue) SendDelay(topic string, message Message, delay time.Duration) error {
    // 1. 计算投递时间
    deliverAt := time.Now().Add(delay)
    
    // 2. 存储延迟消息
    err := dmq.broker.StoreDelayedMessage(topic, message, deliverAt)
    if err != nil {
        return err
    }
    
    return nil
}

func (dmq *DelayMessageQueue) startScheduler() {
    go func() {
        ticker := time.NewTicker(1 * time.Second)
        defer ticker.Stop()
        
        for range ticker.C {
            // 查找到达投递时间的消息
            messages, err := dmq.broker.GetDueMessages(time.Now())
            if err != nil {
                continue
            }
            
            // 投递到实际主题
            for _, msg := range messages {
                dmq.broker.Publish(msg.Topic, msg.Message)
            }
        }
    }()
}
```

### 4.2 死信队列

```go
type DeadLetterQueue struct {
    broker   *Broker
    maxRetry int
}

func (dlq *DeadLetterQueue) Process(message Message, handler MessageHandler) error {
    retryCount := 0
    
    for retryCount < dlq.maxRetry {
        err := handler(message)
        if err == nil {
            return nil
        }
        
        retryCount++
        if retryCount < dlq.maxRetry {
            // 等待后重试
            time.Sleep(time.Duration(retryCount) * time.Second)
        }
    }
    
    // 超过最大重试次数，发送到死信队列
    return dlq.broker.SendToDLQ(message.Topic+"_dlq", message)
}
```

---

## 第五部分：自测题

### 问题 1
为什么需要消息幂等？

<details>
<summary>查看答案</summary>

1. **网络重试**：消息可能重复投递
2. **消费者重试**：处理失败后重新消费
3. **解决方案**：唯一 ID + 去重表
4. **性能优化**：内存去重 + 数据库兜底
5. **Go 实现**：IdempotencyChecker

</details>

### 问题 2
Kafka 如何保证消息顺序？

<details>
<summary>查看答案</summary>

1. **分区级顺序**：同一分区内消息有序
2. **哈希分配**：相同 key 的消息到同一分区
3. **单分区消费**：避免并行消费打乱顺序
4. **缺点**：吞吐量受限
5. **适用场景**：订单状态更新、资金流水

</details>

### 问题 3
死信队列的作用是什么？

<details>
<summary>查看答案</summary>

1. **隔离异常**：失败消息不阻塞正常消息
2. **重试机制**：可以重新处理
3. **人工干预**：开发可以查看和修复
4. **监控告警**：死信数量异常时告警
5. **Go 实现**：DeadLetterQueue

</details>

---

*本文档基于消息队列原理整理。*