# Kafka 生产排障实战

> 消息积压/Rebalance/数据丢失/性能调优/消费者故障

---

## 第一部分：入门引导（5 分钟速览）

### 广告平台 Kafka 常见问题

| 问题 | 现象 | 根因 |
|------|------|------|
| 消息积压 | Lag 持续增长 | 消费者慢 |
| Rebalance | 消费中断 | 消费者上下线 |
| 数据丢失 | 消息缺失 | 配置不当 |
| 性能下降 | 延迟升高 | 磁盘 IO/CPU |
| 消费者故障 | 处理失败 | 代码 Bug |

---

## 第二部分：消息积压排查

### 2.1 积压监控

```bash
# 查看消费者组 lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group

# 关键字段
# TOPIC  PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG  CONSUMER-ID  HOST  CLIENT-ID
# ads    0          1000000         1050000         50000  -            -     -

# 实时监控 lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group --members

# 查看 topic 分区数
kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic ads-log

# 查看 broker 状态
kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

### 2.2 积压原因与解决

```
积压原因:
1. 消费者处理慢 → 优化代码/增加消费者
2. 分区数不足 → 增加分区
3. 网络瓶颈 → 优化网络/就近部署
4. 磁盘 IO → 使用 SSD/调整刷盘策略
5. 生产者速度快 → 调整批次大小

解决方案:
1. 增加消费者实例（不能超过分区数）
2. 优化消费者处理逻辑
3. 调整消费者配置
4. 临时扩容 broker
```

### 2.3 Go 消费者优化

```go
package kafka

import (
    "context"
    "github.com/IBM/sarama"
)

// 优化消费者配置
func NewOptimizedConsumer(config *sarama.Config) sarama.ConsumerGroup {
    // 批量处理
    config.Consumer.Fetch.Default = 1024 * 1024  // 1MB
    config.Consumer.MaxWaitTime = 250 * time.Millisecond
    config.Consumer.MaxMessageSize = 1024 * 1024  // 1MB
    
    // 自动提交偏移量
    config.Consumer.Offsets.AutoCommit.Enable = true
    config.Consumer.Offsets.AutoCommit.Interval = 1 * time.Second
    
    // 重试配置
    config.Net.MaxRetry = 3
    config.Net RetryBackoff = 1 * time.Second
    
    consumer, err := sarama.NewConsumerGroup([]string{"localhost:9092"}, "my-group", config)
    if err != nil {
        panic(err)
    }
    
    return consumer
}

// 批量处理消息
type BatchHandler struct {
    batchSize int
    buffer    []sarama.ConsumerMessage
}

func (h *BatchHandler) Setup(sarama.Session) error {
    h.buffer = make([]sarama.ConsumerMessage, 0, h.batchSize)
    return nil
}

func (h *BatchHandler) Cleanup(sarama.Session) error {
    return nil
}

func (h *BatchHandler) ConsumeClaim(sess sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
    for msg := range claim.Messages() {
        h.buffer = append(h.buffer, *msg)
        
        if len(h.buffer) >= h.batchSize {
            // 批量处理
            h.processBatch(sess, h.buffer)
            h.buffer = h.buffer[:0]
        }
    }
    
    // 处理剩余消息
    if len(h.buffer) > 0 {
        h.processBatch(sess, h.buffer)
    }
    
    return nil
}

func (h *BatchHandler) processBatch(sess sarama.ConsumerGroupSession, msgs []sarama.ConsumerMessage) {
    // 批量处理逻辑
    for _, msg := range msgs {
        // 处理消息
        sess.MarkMessage(msg, nil)
    }
}
```

---

## 第三部分：Rebalance 排查

### 3.1 Rebalance 监控

```bash
# 查看消费者组成员
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group --members

# 监控 Rebalance 事件
# 日志中搜索: "Rebalance started" 或 "Member joined group"

# 查看 Rebalance 原因
kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group my-group --state
```

### 3.2 Rebalance 优化

```
Rebalance 原因:
1. 消费者上下线
2. 心跳超时
3. 处理时间过长
4. Session 过期

优化策略:
1. 增加 session.timeout.ms = 30000
2. 增加 heartbeat.interval.ms = 10000
3. 使用 cooperative sticky 分配策略
4. 避免在消费者中做耗时操作

Go 实现:
config.Consumer.Group.Rebalance.Strategy = sarama.NewCooperativeStickyBalancer()
config.Consumer.Group.Session.Timeout = 60 * time.Second
config.Consumer.Group.Heartbeat.Interval = 10 * time.Second
```

---

## 第四部分：数据丢失排查

### 4.1 生产者配置

```go
// 确保数据不丢失的生产者配置
config := sarama.NewConfig()
config.Producer.RequiredAcks = sarama.WaitForAll  // 等待所有 ISR
config.Producer.Return.Errors = true
config.Producer.Return.Successes = true
config.Producer.MaxMessageBytes = 1024 * 1024  // 1MB
config.Producer.Compression = sarama.CompressionSnappy

// 重试配置
config.Producer.Retry.Max = 3
config.Producer.Retry.Backoff = 1 * time.Second
```

### 4.2 消费者配置

```go
// 确保数据不丢失的消费者配置
config := sarama.NewConfig()
config.Consumer.Offsets.AutoCommit.Enable = false  // 手动提交
config.Consumer.Offsets.Initial = sarama.OffsetNewest

// 手动提交偏移量
handler := &MessageHandler{
    session: sess,
}

func (h *MessageHandler) ConsumeClaim(sess sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
    for msg := range claim.Messages() {
        // 处理消息
        err := h.process(msg)
        if err != nil {
            // 处理失败，不提交偏移量
            log.Printf("message processing failed: %v", err)
            continue
        }
        
        // 处理成功，提交偏移量
        sess.MarkMessage(msg, nil)
    }
    return nil
}
```

### 4.3 Broker 配置

```
# 确保数据不丢失的 broker 配置
min.insync.replicas = 2  # 最少 2 个 ISR
unclean.leader.election.enable = false  # 不允许非 ISR 成为 leader
log.retention.hours = 168  # 保留 7 天
```

---

## 第五部分：自测题

### 问题 1
Kafka 消息积压怎么解决？

<details>
<summary>查看答案</summary>

1. 增加消费者实例（不超过分区数）
2. 优化消费者处理逻辑
3. 调整批量大小
4. 临时扩容 broker
5. 监控 lag 趋势

</details>

### 问题 2
如何避免 Kafka 数据丢失？

<details>
<summary>查看答案</summary>

1. 生产者: RequiredAcks = WaitForAll
2. 消费者: 手动提交偏移量
3. Broker: min.insync.replicas = 2
4. 重试机制: Retry.Max = 3
5. 监控: 定期检查 lag

</details>

### 问题 3
Rebalance 频繁发生怎么办？

<details>
<summary>查看答案</summary>

1. 增加 session.timeout.ms
2. 使用 cooperative sticky 策略
3. 避免在消费中做耗时操作
4. 监控消费者健康状态
5. Go 实现: NewCooperativeStickyBalancer()

</details>

---

*本文档基于 Kafka 生产排障经验整理。*