# 广告中间件深度：消息队列/网络编程/CDN

> 广告系统的消息队列选型、网络编程、CDN 加速

---

## 第一部分：消息队列选型

### 广告系统 MQ 需求分析

```
广告系统消息队列需求：
┌─────────────────────────────────────────────────────────────────────┐
│ 场景                │ 吞吐量  │ 延迟    │ 可靠性  │ 推荐方案       │
├─────────────────────┼─────────┼─────────┼─────────┼───────────────┤
│ 曝光/点击追踪        │ 500K/s  │ < 10ms  │ 至少一次│ Kafka         │
│ 竞价事件            │ 100K/s  │ < 5ms   │ 精确一次│ Kafka         │
│ 计费事件            │ 50K/s   │ < 100ms │ 至少一次│ Kafka         │
│ 告警通知            │ 1K/s    │ < 1s    │ 至少一次│ RabbitMQ      │
│ 异步任务            │ 10K/s   │ < 1s    │ 至少一次│ NATS          │
│ 实时推送            │ 5K/s    │ < 100ms │ 至少一次│ NATS          │
└─────────────────────────────────────────────────────────────────────┘
```

### Kafka 在广告系统中的深度实践

```go
package kafka

import (
    "context"
    "github.com/IBM/sarama"
    "time"
)

// AdKafkaProducer 广告 Kafka 生产者
type AdKafkaProducer struct {
    producer sarama.AsyncProducer
    topics   map[string]string // event_type -> topic
}

// NewAdKafkaProducer 创建生产者
func NewAdKafkaProducer(brokers []string) (*AdKafkaProducer, error) {
    config := sarama.NewConfig()
    config.Producer.RequiredAcks = sarama.WaitForAll // 确保数据不丢
    config.Producer.Return.Successes = true
    config.Producer.Compression = sarama.CompressionLZ4
    config.Producer.MaxMessageBytes = 1024 * 1024 // 1MB
    
    producer, err := sarama.NewAsyncProducer(brokers, config)
    if err != nil {
        return nil, err
    }
    
    return &AdKafkaProducer{
        producer: producer,
        topics: map[string]string{
            "impression": "ad.impressions",
            "click":      "ad.clicks",
            "conversion": "ad.conversions",
            "bid":        "ad.bids",
        },
    }, nil
}

// Publish 发布广告事件
func (p *AdKafkaProducer) Publish(ctx context.Context, eventType string, key string, value []byte) error {
    topic, ok := p.topics[eventType]
    if !ok {
        return fmt.Errorf("unknown event type: %s", eventType)
    }
    
    msg := &sarama.ProducerMessage{
        Topic: topic,
        Key:   sarama.StringEncoder(key), // 按 key 分区
        Value: sarama.ByteEncoder(value),
    }
    
    select {
    case p.producer.Input() <- msg:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    }
}

// AdKafkaConsumer 广告 Kafka 消费者
type AdKafkaConsumer struct {
    consumer sarama.ConsumerGroup
    handlers map[string]EventHandler
}

type EventHandler func(ctx context.Context, event *AdEvent) error

// Consume 消费事件
func (c *AdKafkaConsumer) Consume(ctx context.Context, topics []string) error {
    for {
        err := c.consumer.Consume(ctx, topics, c)
        if err != nil {
            return err
        }
        
        // 检查是否需要退出
        if ctx.Err() != nil {
            break
        }
    }
    return nil
}

func (c *AdKafkaConsumer) Setup(session sarama.ConsumerGroupSession) error {
    // 标记消费者已就绪
    return nil
}

func (c *AdKafkaConsumer) Cleanup(session sarama.ConsumerGroupSession) error {
    // 清理资源
    return nil
}

func (c *AdKafkaConsumer) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
    for message := range claim.Messages() {
        // 处理消息
        event := &AdEvent{}
        json.Unmarshal(message.Value, event)
        
        if handler, ok := c.handlers[event.Type]; ok {
            if err := handler(session.Context(), event); err != nil {
                // 记录错误，不阻塞消费
                log.Error("event handler error", "type", event.Type, "error", err)
                session.MarkMessage(message, nil) // 标记处理成功（即使失败也要 advance）
                continue
            }
        }
        session.MarkMessage(message, nil)
    }
    return nil
}
```

---

## 第二部分：网络编程

### gRPC 在广告系统中的应用

```go
// bidding.proto
syntax = "proto3";
package bidding;

service BidderService {
  rpc PlaceBid (BidRequest) returns (BidResponse);
  rpc GetBidHistory (BidHistoryRequest) returns (BidHistoryResponse);
}

message BidRequest {
  string request_id = 1;
  string campaign_id = 2;
  string user_id = 3;
  string device_id = 4;
  double budget_remaining = 5;
  repeated string interests = 6;
}

message BidResponse {
  string bid_id = 1;
  double bid_price = 2;
  bool win = 3;
  string ad_id = 4;
}
```

### HTTP/2 连接池优化

```go
package http2

import (
    "crypto/tls"
    "net/http"
    "time"
)

// NewAdHTTPClient 创建优化的 HTTP/2 客户端
func NewAdHTTPClient() *http.Client {
    transport := &http.Transport{
        MaxIdleConns:        200,
        MaxIdleConnsPerHost: 50,
        IdleConnTimeout:     90 * time.Second,
        TLSHandshakeTimeout: 5 * time.Second,
        ResponseHeaderTimeout: 10 * time.Second,
        TLSClientConfig: &tls.Config{
            MinVersion: tls.VersionTLS12,
            NextProtos: []string{"h2", "http/1.1"}, // HTTP/2 优先
        },
    }
    
    return &http.Client{
        Transport: transport,
        Timeout:   30 * time.Second,
    }
}
```

---

## 第三部分：CDN 加速

```
CDN 在广告系统中的应用：
1. 广告素材分发：图片/视频通过 CDN 加速
2. 追踪像素：曝光/点击追踪通过 CDN 边缘节点
3. 静态资源：JS/CSS 通过 CDN 分发
4. API 加速：DNS 解析优化 + HTTP/2

CDN 配置：
• 缓存策略：广告素材缓存 24h，追踪像素不缓存
• 边缘计算：在 CDN 边缘节点做简单逻辑判断
• SSL 终止：CDN 处理 TLS，减轻后端压力
```

---

## 第四部分：自测题

### Q1: Kafka 为什么适合广告事件流？

**A**: 高吞吐（百万级消息/秒）、持久化（数据不丢）、分区并行（水平扩展）、支持回溯消费。

### Q2: gRPC 和 HTTP/REST 的区别？

**A**: gRPC 基于 HTTP/2 + Protobuf，二进制协议，性能更好；REST 基于 HTTP/1.1 + JSON，人类可读，生态更成熟。

### Q3: CDN 在广告系统中的关键作用？

**A**: 广告素材分发（图片/视频）、追踪像素低延迟、边缘计算、SSL 终止。

---

## 第五部分：生产实践

### 1. Kafka 运维

```
Kafka 运维要点：
• 监控：broker lag、producer throughput、consumer lag
• 扩容：增加 partition 提升吞吐
• 备份：定期备份 topic 元数据
• 清理：设置合理的 retention 策略
```

### 2. gRPC 优化

```
gRPC 优化要点：
• 连接复用：HTTP/2 多路复用
• 流式传输：Server Streaming / Client Streaming
• 超时控制：设置合理的超时
• 压缩：启用 gzip 压缩
```

### 3. CDN 优化

```
CDN 优化要点：
• 缓存策略：合理设置 TTL
• 边缘计算：在边缘做简单逻辑
• SSL 终止：减轻后端压力
• 监控：命中率、延迟、带宽
```
