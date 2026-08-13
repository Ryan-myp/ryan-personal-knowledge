# Redis高级特性 - 资深专家深度实现

## 一、高级数据结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Redis 高级数据结构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   数据结构            | 适用场景                    | 命令示例         │
│   ────────────────────┼───────────────────────────┼──────────────────│
│   HyperLogLog         | 基数统计                    | PFADD/PFCOUNT    │
│   Bitmap              | 位图统计                    | SETBIT/GETBIT    │
│   Geospatial          | 地理位置                    | GEOADD/GEOPOS    │
│   Streams             | 消息队列                    | XADD/XREAD       │
│   Publish/Subscribe   | 发布订阅                    | PUBLISH/SUBSCRIBE│
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、HyperLogLog实现

```go
package redis

import (
    "github.com/go-redis/redis/v8"
)

// HyperLogLog 基数统计
type HyperLogLog struct {
    client *redis.Client
    key    string
}

func NewHyperLogLog(client *redis.Client, key string) *HyperLogLog {
    return &HyperLogLog{client: client, key: key}
}

// Add 添加元素
func (h *HyperLogLog) Add(ctx context.Context, element interface{}) error {
    return h.client.PFAdd(ctx, h.key, element).Err()
}

// Count 统计基数
func (h *HyperLogLog) Count(ctx context.Context) (uint64, error) {
    count, err := h.client.PFCount(ctx, h.key).Uint64()
    return count, err
}

// Merge 合并多个HyperLogLog
func (h *HyperLogLog) Merge(ctx context.Context, keys ...string) error {
    allKeys := append([]string{h.key}, keys...)
    return h.client.PFMerge(ctx, h.key, allKeys...).Err()
}
```

## 三、面试高频题

### Q1: 如何使用HyperLogLog？

```
A:
1. 唯一用户统计
2. UV去重
3. 误差约0.81%
```

### Q2: 如何实现消息队列？

```
A:
1. Streams持久化
2. Consumer Group
3. 消息ACK确认
```

## 四、自测题

1. 解释Redis高级数据结构
2. 如何使用HyperLogLog？
3. 如何设计消息队列？

---

## 参考文档

- [Redis Docs](https://redis.io/docs/)
- [Redis Commands](https://redis.io/commands/)
