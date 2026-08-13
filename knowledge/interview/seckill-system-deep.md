# 秒杀系统设计 --- 资深专家深度实现

## 概述

秒杀系统是互联网经典的高并发场景。本文深入剖析秒杀架构设计、防超卖和限流降级策略。

## 一、秒杀流程

```
┌─────────────────────────────────────────────────────────┐
│                    秒杀流程                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  用户 ──→ 前端页面 ──→ CDN ──→ API网关 ──→ 服务层      │
│                                           │            │
│                                           ▼            │
│                                      ┌──────────┐      │
│                                      │  库存检查  │      │
│                                      └────┬─────┘      │
│                                           │            │
│                                   ┌───────┴───────┐    │
│                                   ▼               ▼    │
│                              ┌────────┐      ┌────────┐│
│                              │ Redis  │      │  MySQL ││
│                              │ 预扣减  │      │ 实际扣减││
│                              └───┬────┘      └───┬────┘│
│                                  │               │     │
│                                  ▼               ▼     │
│                            ┌─────────────────────┐    │
│                            │    消息队列异步      │    │
│                            │    写入订单表        │    │
│                            └─────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 二、防超卖方案

### 2.1 Redis预扣减

```go
func Seckill(ctx context.Context, itemID, userID int64) error {
    stockKey := fmt.Sprintf("stock:%d", itemID)
    
    // 1. Redis预扣减库存
    count, err := redis.Decr(ctx, stockKey).Result()
    if err != nil {
        return err
    }
    
    // 2. 检查是否超卖
    if count < 0 {
        // 恢复库存
        redis.Incr(ctx, stockKey)
        return errors.New("库存不足")
    }
    
    // 3. 记录用户购买状态（防重复购买）
    userKey := fmt.Sprintf("bought:%d:%d", itemID, userID)
    exist, _ := redis.Exists(ctx, userKey).Result()
    if exist > 0 {
        redis.Incr(ctx, stockKey)  // 恢复库存
        return errors.New("重复购买")
    }
    redis.Set(ctx, userKey, "1", time.Minute*30)
    
    // 4. 发送消息到MQ，异步创建订单
    mq.Publish("seckill_order", SeckillOrder{
        ItemID: itemID,
        UserID: userID,
    })
    
    return nil
}
```

### 2.2 Lua脚本原子操作

```lua
-- 原子扣减库存
local stock = tonumber(redis.call('GET', KEYS[1]))
if stock <= 0 then
    return -1  -- 库存不足
end
redis.call('DECR', KEYS[1])
return 1  -- 扣减成功
```

```go
var seckillScript = redis.NewScript(`
    local stock = tonumber(redis.call('GET', KEYS[1]))
    if stock <= 0 then
        return -1
    end
    redis.call('DECR', KEYS[1])
    return 1
`)

func SeckillWithLua(ctx context.Context, itemID int64) (int, error) {
    stockKey := fmt.Sprintf("stock:%d", itemID)
    return seckillScript.Run(ctx, []string{stockKey}).Int()
}
```

### 2.3 数据库乐观锁

```sql
-- 使用版本号防超卖
UPDATE items 
SET stock = stock - 1, version = version + 1 
WHERE id = ? AND stock > 0 AND version = ?
-- 影响行数 > 0 表示成功
```

## 三、限流降级

### 3.1 令牌桶限流

```go
import "golang.org/x/time/rate"

type Limiter struct {
    buckets map[int64]*rate.Limiter
    mu      sync.Mutex
}

func NewLimiter() *Limiter {
    return &Limiter{
        buckets: make(map[int64]*rate.Limiter),
    }
}

func (l *Limiter) Allow(userID int64) bool {
    l.mu.Lock()
    defer l.mu.Unlock()
    
    limiter, ok := l.buckets[userID]
    if !ok {
        // 每个用户每秒允许1次请求
        limiter = rate.NewLimiter(rate.Every(time.Second), 1)
        l.buckets[userID] = limiter
    }
    
    return limiter.Allow()
}
```

### 3.2 网关层限流

```yaml
# Nginx限流配置
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    location /seckill {
        limit_req zone=api burst=5 nodelay;
        limit_req_status 429;
        
        proxy_pass http://backend;
    }
}
```

### 3.3 多级缓存

```go
// L1: 本地缓存 (秒级)
var localCache = sync.Map{}

// L2: Redis缓存 (分钟级)
var redisClient = redis.NewClient(...)

// L3: MySQL数据库
var db *gorm.DB

func GetItem(itemID int64) (*Item, error) {
    // 1. 查本地缓存
    if v, ok := localCache.Load(itemID); ok {
        return v.(*Item), nil
    }
    
    // 2. 查Redis
    cached, err := redisClient.Get(context.Background(), 
        fmt.Sprintf("item:%d", itemID)).Bytes()
    if err == nil {
        var item Item
        json.Unmarshal(cached, &item)
        localCache.Store(itemID, &item)
        return &item, nil
    }
    
    // 3. 查数据库
    var item Item
    db.First(&item, itemID)
    
    // 写入缓存
    data, _ := json.Marshal(item)
    redisClient.Set(context.Background(), 
        fmt.Sprintf("item:%d", itemID), data, 5*time.Minute)
    localCache.Store(itemID, &item)
    
    return &item, nil
}
```

## 四、消息队列异步

### 4.1 Kafka异步下单

```go
// 生产者：发送购买请求
type SeckillProducer struct {
    producer sarama.AsyncProducer
}

func (p *SeckillProducer) Send(order SeckillOrder) error {
    msg := &sarama.ProducerMessage{
        Topic: "seckill_orders",
        Value: sarama.StringEncoder(marshal(order)),
    }
    p.producer.Input() <- msg
    return nil
}

// 消费者：异步创建订单
type SeckillConsumer struct {
    session sarama.ConsumerGroupSession
}

func (c *SeckillConsumer) ConsumeClaim(session sarama.ConsumerGroupSession, 
    claim sarama.ConsumerGroupClaim) error {
    for msg := range claim.Messages() {
        var order SeckillOrder
        unmarshal(msg.Value, &order)
        
        // 创建订单
        createOrder(order)
        
        // 标记消费成功
        session.MarkMessage(msg, "")
    }
    return nil
}
```

### 4.2 RocketMQ事务消息

```go
// 事务消息：确保本地事务和MQ消息的一致性
txProducer := rocketmq.NewTransactionProducer(nil, &listener{})

msg := &rocketmq.Message{
    Topic: "seckill_tx",
    Body:  []byte(marshal(order)),
}

// 发送半消息
res, err := txProducer.SendTransaction(msg, nil)

// 本地事务执行
func executeLocalTransaction(msg *rocketmq.Message) rocketmq.LocalTransaction {
    // 执行数据库操作
    err := createOrderInDB(msg)
    if err != nil {
        return rocketmq.ROLLBACK
    }
    return rocketmq.COMMIT
}
```

## 五、监控告警

### 5.1 关键指标

```go
type Metrics struct {
    QPS           float64    // 每秒查询数
    RT            float64    // 平均响应时间
    ErrorRate     float64    // 错误率
    StockLeft     int64      // 剩余库存
    OrderCount    int64      // 订单数
}
```

### 5.2 告警规则

```yaml
alerts:
  - name: high_qps
    expr: seckill_qps > 10000
    for: 1m
    labels:
      severity: warning
  - name: high_error_rate
    expr: seckill_error_rate > 0.05
    for: 1m
    labels:
      severity: critical
  - name: stock_exhausted
    expr: seckill_stock_left == 0
    for: 1m
    labels:
      severity: info
```

## 六、面试高频题

### 6.1 高频问题

**Q1: 如何防止超卖？**

A: Redis预扣减 + Lua原子操作 + 数据库乐观锁。

**Q2: 如何限流？**

A: 令牌桶/漏桶算法 + 网关层限流 + 应用层限流。

**Q3: 如何削峰？**

A: 消息队列异步处理 + 排队机制。

### 6.2 自测题

1. 设计一个秒杀系统架构图
2. 分析防超卖的几种方案
3. 实现一个令牌桶限流器
4. 设计消息队列异步下单流程
5. 解释限流和降级的区别

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 系统设计
**关键词**: seckill, high-concurrency, rate-limit, mq, idempotent
