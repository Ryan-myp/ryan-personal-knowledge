# Redis Pub/Sub与Streams - 资深专家深度实现

## 一、对比分析

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  Redis Pub/Sub vs Streams                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   特性                | Pub/Sub              | Streams                │
│   ────────────────────┼──────────────────────┼─────────────────────────│
│   消息持久化          | ❌ 不持久化           │ ✅ 持久化               │
│   消费组              | ❌ 不支持             │ ✅ 支持                 │
│   消息回溯            | ❌ 不支持             │ ✅ 支持                 │
│   发布延迟订阅        | ❌ 丢失消息           │ ✅ 可消费历史           │
│   适用场景            | 实时通知             │ 事件溯源、消息队列      │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Streams实现

```go
package redis

import (
    "context"
    "github.com/go-redis/redis/v8"
)

// StreamManager Stream管理器
type StreamManager struct {
    client *redis.Client
}

// XAdd 添加消息
func (m *StreamManager) XAdd(ctx context.Context, stream string, values map[string]string) (string, error) {
    id, err := m.client.XAdd(ctx, &redis.XAddArgs{
        Stream: stream,
        Values: values,
    }).Result()
    return id, err
}

// XReadGroup 消费组读取
func (m *StreamManager) XReadGroup(ctx context.Context, stream, group, consumer string, count int) ([]*redis.XStream, error) {
    return m.client.XReadGroup(ctx, &redis.XReadGroupArgs{
        Group:    group,
        Consumer: consumer,
        Streams:  []string{stream, ">"},
        Count:    count,
        Block:    0,
    }).Result()
}

// XAck 确认消息
func (m *StreamManager) XAck(ctx context.Context, stream, group string, ids ...string) (int64, error) {
    return m.client.XAck(ctx, stream, group, ids...).Result()
}
```

## 三、面试高频题

### Q1: Pub/Sub和Streams的区别？

```
A:
1. 持久化差异
2. 消费组支持
3. 消息回溯
```

### Q2: 如何实现消息队列？

```
A:
1. XAdd发布
2. XReadGroup消费
3. XAck确认
```

## 四、自测题

1. 解释Pub/Sub vs Streams
2. 如何实现消费组？
3. 如何确保消息不丢失？

---

## 参考文档

- [Redis Streams](https://redis.io/docs/data-types/streams/)
- [Redis PubSub](https://redis.io/docs/manual/pubsub/)
