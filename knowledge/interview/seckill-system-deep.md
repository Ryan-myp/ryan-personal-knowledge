# 秒杀系统设计 - 资深专家深度实现

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      秒杀系统架构                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│   │  CDN     │───►│  WAF     │───►│  Nginx   │───►│  Gateway │        │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│                                                                          │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│   │ Redis    │◄───│  MQ      │◄───│  Service │◄───│  DB      │        │
│   │ (库存)    │    │ (异步)    │    │ (限流)    │    │ (持久化)  │        │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、核心实现

```go
package seckill

import (
    "context"
    "github.com/go-redis/redis/v8"
    "time"
)

type SeckillService struct {
    redis client *redis.Client
    mq    *amqp.Channel
}

// 预扣库存
func (s *SeckillService) PreDeductStock(ctx context.Context, itemId string, userId string) (bool, error) {
    // 1. 检查用户是否已购买
    purchasedKey := fmt.Sprintf("seckill:bought:%s:%s", itemId, userId)
    exists, err := s.redis.Exists(ctx, purchasedKey).Result()
    if err != nil || exists > 0 {
        return false, errors.New("已购买")
    }
    
    // 2. 原子扣减库存
    stockKey := fmt.Sprintf("seckill:stock:%s", itemId)
    count := s.redis.Decr(ctx, stockKey)
    
    if count < 0 {
        s.redis.Incr(ctx, stockKey) // 恢复库存
        return false, errors.New("库存不足")
    }
    
    // 3. 标记已购买
    s.redis.Set(ctx, purchasedKey, "1", 24*time.Hour)
    
    // 4. 发送MQ消息
    s.mq.Publish("seckill.order", []byte(fmt.Sprintf(`{"itemId":"%s","userId":"%s"}`, itemId, userId)))
    
    return true, nil
}

// 库存预热
func (s *SeckillService) WarmupStock(itemId string, total int) error {
    stockKey := fmt.Sprintf("seckill:stock:%s", itemId)
    return s.redis.Set(context.Background(), stockKey, total, 0).Err()
}
```

## 三、面试高频题

### Q1: 如何防止超卖？

```
A:
1. Redis原子操作
2. 数据库乐观锁
3. 分布式锁
```

### Q2: 如何处理热点key？

```
A:
1. 本地缓存
2. 分片存储
3. 预热数据
```

## 四、自测题

1. 解释秒杀系统架构
2. 如何实现库存扣减？
3. 如何处理高并发？

---

## 参考文档

- [秒杀系统设计](https://zhuanlan.zhihu.com/p/111781593)
- [Redis原子操作](https://redis.io/commands/decr)
