# 秒杀系统设计 - 资深专家深度实现

## 一、架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      秒杀系统架构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   用户层                                                                  │
│   ├── CDN缓存                                                            │
│   ├── 前端限流                                                            │
│   └── 静态资源                                                              │
│                                                                         │
│   网关层                                                                  │
│   ├── API网关                                                              │
│   ├── 限流: Token Bucket                                                 │
│   └── 熔断: Circuit Breaker                                              │
│                                                                         │
│   业务层                                                                  │
│   ├── 活动判断                                                            │
│   ├── 库存预热                                                            │
│   └── 下单处理                                                            │
│                                                                         │
│   数据层                                                                  │
│   ├── Redis预扣库存                                                        │
│   ├── MQ异步下单                                                          │
│   └── MySQL最终落库                                                        │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、库存扣减

```java
// Redis预扣库存
public boolean stockDecr(String itemId) {
    String key = "stock:" + itemId;
    Long count = redisTemplate.opsForValue().decrement(key);
    
    if (count < 0) {
        // 库存不足
        redisTemplate.opsForValue().increment(key);
        return false;
    }
    return true;
}

// 原子性保证
@DistributedLock(key = "stock:{itemId}")
public boolean stockDecr(String itemId) {
    Long stock = redisTemplate.opsForValue().decrement("stock:" + itemId);
    return stock >= 0;
}
```

## 三、MQ削峰

```java
// 下单消息
public class OrderMessage {
    private String userId;
    private String itemId;
    private Long amount;
}

// 生产者
public void createOrder(OrderMessage msg) {
    mqTemplate.send("order_queue", msg);
}

// 消费者
@RabbitListener(queues = "order_queue")
public void consumeOrder(OrderMessage msg) {
    orderService.createOrder(msg);
}
```

## 四、面试高频题

### Q1: 秒杀系统如何防超卖？

```
A:
1. Redis原子扣减
2. 数据库乐观锁
3. 分布式锁
```

### Q2: 如何处理高并发？

```
A:
1. 限流熔断
2. 缓存预热
3. MQ削峰
```

## 五、自测题

1. 解释秒杀架构
2. 如何实现库存扣减？
3. 如何防止黄牛？

---

## 参考文档

- [秒杀系统设计](https://github.com/aaron24/high-concurrency-design)
- [高并发架构模式](https://github.com/alibaba/Sentinel)
