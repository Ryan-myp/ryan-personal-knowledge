# 广告系统分布式架构深度：Kafka/缓存/分布式事务/服务网格/配置中心

> 广告系统的中间件选型与深度实践

---

## 第一部分：广告系统技术架构全景

### 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                    接入层                                   │
│  API Gateway (Kong/APISIX) → 限流/鉴权/路由/协议转换         │
└─────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                    业务层                                   │
│  竞价服务 / 召回服务 / 排序服务 / 计费服务 / 实验服务        │
│  Go Microservices → gRPC/HTTP                              │
└─────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                    中间件层                                 │
│  Kafka (消息队列) / Redis (缓存) / Etcd (注册中心)          │
│  Prometheus (监控) / Jaeger (链路追踪) / ELK (日志)         │
└─────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                    存储层                                   │
│  MySQL (关系数据) / ClickHouse (分析) / ES (检索)           │
│  OSS (素材存储) / CDN (分发)                                │
└─────────────────────────────────────────────────────────────┘
```

### 核心挑战

```
1. 高并发：1000+ QPS，50ms 响应
2. 高可用：99.99% SLA
3. 一致性：预算扣减不能超扣
4. 可扩展：随时加机器不中断
5. 可观测：出了问题能快速定位
```

---

## 第二部分：Kafka 深度实践

### 2.1 Kafka 在广告系统中的应用

```
Topic 设计：
├── ad.impression   (展示事件)     → 100 分区
├── ad.click        (点击事件)     → 50 分区
├── ad.conversion   (转化事件)     → 50 分区
├── ad.budget       (预算变更)     → 10 分区
├── ad.freq         (频次变更)     → 10 分区
└── ad.audit        (审核事件)     → 5 分区

消费组设计：
├── consumer-group-billing    → 计费服务（预算扣减）
├── consumer-group-analytics  → 数据分析（实时报表）
├── consumer-group-fraud      → 反作弊（实时检测）
├── consumer-group-index      → 索引同步（内存索引更新）
└── consumer-group-notify     → 通知服务（状态变更通知）
```

### 2.2 分区策略

```go
package kafka

import (
    "hash/fnv"
)

// Partitioner 分区器
type Partitioner struct {
    numPartitions int
}

// NewPartitioner 创建分区器
func NewPartitioner(numPartitions int) *Partitioner {
    return &Partitioner{numPartitions: numPartitions}
}

// Partition 计算分区号
func (p *Partitioner) Partition(key string) int {
    h := fnv.New32a()
    h.Write([]byte(key))
    return int(h.Sum32()) % p.numPartitions
}

// 分区键选择：
// → 展示事件：user_id（同一用户的事件在同一分区，保证顺序）
// → 点击事件：user_id
// → 转化事件：user_id
// → 预算变更：account_id（同一广告主的预算变更在同一分区）
// → 频次变更：user_id
```

### 2.3 Exactly-Once 语义

```
广告系统对消息一致性的要求：
→ 预算扣减：绝对不能多扣或少扣
→ 频次计数：绝对不能重复计数
→ 数据上报：允许少量丢失，但不能重复

实现方案：
1. 幂等写入：
   → 每条消息带唯一 ID
   → 消费者用 ID 去重
   → Redis SETNX 保证幂等

2. 事务消息：
   → Kafka 2.4+ 支持事务
   → 生产者事务：发送多条消息原子提交
   → 消费者事务：读取+写入原子操作

3. Offset 管理：
   → 先处理消息，再提交 Offset
   → 失败不提交 Offset，重试
   → 死信队列处理无法恢复的消息
```

```go
// IdempotentConsumer 幂等消费者
type IdempotentConsumer struct {
    kafkaConsumer *sarama.ConsumerGroup
    redis         *RedisClient
    handler       MessageHandler
}

// Consume 消费消息
func (c *IdempotentConsumer) Consume(ctx context.Context, msgs []*sarama.ConsumerMessage) error {
    for _, msg := range msgs {
        // 1. 检查是否已处理
        idempotencyKey := fmt.Sprintf("%s:%d:%d", msg.Topic, msg.Partition, msg.Offset)
        if c.redis.Exists(idempotencyKey) {
            continue // 已处理，跳过
        }
        
        // 2. 处理消息
        err := c.handler.Handle(msg)
        if err != nil {
            // 3. 处理失败，放入死信队列
            c.deadLetterQueue.Put(msg)
            return err
        }
        
        // 4. 标记为已处理
        c.redis.SetEX(idempotencyKey, "1", 86400) // 24 小时过期
    }
    
    return nil
}
```

### 2.4 性能调优

```
Producer 调优：
→ batch.size: 16KB（批量发送）
→ linger.ms: 5ms（等待时间）
→ compression.type: lz4（压缩）
→ acks: 1（平衡性能和可靠性）
→ retries: 3（重试次数）

Consumer 调优：
→ max.poll.records: 500（单次拉取）
→ fetch.min.bytes: 1MB（最小拉取）
→ session.timeout.ms: 10s（会话超时）
→ heartbeat.interval.ms: 3s（心跳间隔）

Broker 调优：
→ num.partitions: 100（分区数）
→ replication.factor: 3（副本数）
→ log.retention.hours: 168（保留 7 天）
→ num.io.threads: 8（IO 线程）
→ num.network.threads: 3（网络线程）
```

---

## 第三部分：多级缓存架构

### 3.1 缓存分层

```
L1: 进程内缓存（Go map）
→ 速度：纳秒级
→ 容量：受限于内存
→ 适用：热点数据（用户画像/广告配置）
→ 失效：手动刷新/定时刷新

L2: Redis 缓存
→ 速度：毫秒级
→ 容量：GB 级别
→ 适用：共享数据（预算/频次/索引）
→ 失效：TTL/主动删除

L3: 磁盘缓存（本地 SSD）
→ 速度：微秒级
→ 容量：TB 级别
→ 适用：静态数据（模板/字典）
→ 失效：版本更新时刷新
```

### 3.2 缓存架构

```
                    ┌─────────────────────────────────────┐
                    │         Client (Go Service)         │
                    │  L1: Sync.Map / singleflight        │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       Redis Cluster                 │
                    │  - 预算/频次/用户画像               │
                    │  - TTL: 5min - 1hour                │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       MySQL / ClickHouse            │
                    │  - 持久化存储                        │
                    └─────────────────────────────────────┘
```

### 3.3 缓存一致性

```go
package cache

import (
    "sync"
    "time"
)

// CacheWithConsistency 带一致性的缓存
type CacheWithConsistency struct {
    l1       *L1Cache      // 进程内缓存
    l2       *L2Cache      // Redis 缓存
    db       *Database     // 数据库
    mu       sync.RWMutex  // 写锁
}

// Get 获取数据
func (c *CacheWithConsistency) Get(key string) (interface{}, error) {
    // 1. 查 L1
    if val, ok := c.l1.Get(key); ok {
        return val, nil
    }
    
    // 2. 查 L2
    if val, ok := c.l2.Get(key); ok {
        // 回填 L1
        c.l1.Set(key, val, 30*time.Second)
        return val, nil
    }
    
    // 3. 查 DB
    val, err := c.db.Get(key)
    if err != nil {
        return nil, err
    }
    
    // 4. 写入缓存
    c.l2.Set(key, val, 5*time.Minute)
    c.l1.Set(key, val, 30*time.Second)
    
    return val, nil
}

// Set 设置数据（Cache-Aside 模式）
func (c *CacheWithConsistency) Set(key string, val interface{}) error {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    // 1. 写 DB
    err := c.db.Set(key, val)
    if err != nil {
        return err
    }
    
    // 2. 删 L2（延迟双删）
    c.l2.Delete(key)
    
    // 3. 删 L1
    c.l1.Delete(key)
    
    // 4. 等待 100ms 后再次删除 L2（防止并发读）
    time.AfterFunc(100*time.Millisecond, func() {
        c.l2.Delete(key)
    })
    
    return nil
}
```

### 3.4 缓存问题处理

```
1. 缓存穿透：
   → 问题：查询不存在的数据，绕过缓存直接打 DB
   → 解决：布隆过滤器 + 空值缓存
   
2. 缓存击穿：
   → 问题：热点 Key 过期，大量请求打到 DB
   → 解决：互斥锁 + 永不过期（逻辑过期）
   
3. 缓存雪崩：
   → 问题：大量 Key 同时过期
   → 解决：TTL 加随机值 + 多级缓存
   
4. 缓存一致性：
   → 问题：DB 和缓存数据不一致
   → 解决：Cache-Aside + 延迟双删 + Canal 同步
```

```go
// BloomFilter 布隆过滤器（防穿透）
type BloomFilter struct {
    bits    []bool
    hashes  []func(string) int
    size    int
}

func (bf *BloomFilter) Add(item string) {
    for _, hash := range bf.hashes {
        idx := hash(item) % bf.size
        bf.bits[idx] = true
    }
}

func (bf *BloomFilter) MightContain(item string) bool {
    for _, hash := range bf.hashes {
        idx := hash(item) % bf.size
        if !bf.bits[idx] {
            return false
        }
    }
    return true
}

// MutexCache 互斥锁缓存（防击穿）
type MutexCache struct {
    redis *RedisClient
    mu    sync.Map // key → 锁
}

func (mc *MutexCache) Get(key string) (interface{}, error) {
    // 1. 查缓存
    val, err := mc.redis.Get(key)
    if err == nil {
        return val, nil
    }
    
    // 2. 加锁
    lock, _ := mc.mu.LoadOrStore(key, &sync.Mutex{})
    mutex := lock.(*sync.Mutex)
    mutex.Lock()
    defer mutex.Unlock()
    
    // 3. 双重检查
    val, err = mc.redis.Get(key)
    if err == nil {
        return val, nil
    }
    
    // 4. 查 DB 并写入缓存
    val, err = mc.queryDB(key)
    if err != nil {
        return nil, err
    }
    
    mc.redis.Set(key, val, 5*time.Minute)
    return val, nil
}
```

---

## 第四部分：分布式事务

### 4.1 广告系统的分布式事务场景

```
场景 1：广告扣费 + 预算扣减
→ 扣费服务：记录消费
→ 预算服务：扣减预算
→ 要求：要么都成功，要么都失败

场景 2：频次更新 + 统计上报
→ 频次服务：更新频次计数
→ 统计服务：上报统计数据
→ 要求：至少一次（允许重复，但要幂等）

场景 3：广告状态变更 + 索引更新
→ 广告服务：更新广告状态
→ 索引服务：更新内存索引
→ 要求：最终一致性
```

### 4.2 Saga 模式实现

```go
package saga

import (
    "context"
    "fmt"
)

// Saga Saga 编排器
type Saga struct {
    steps []SagaStep
}

// SagaStep Saga 步骤
type SagaStep struct {
    Name     string
    Execute  func(ctx context.Context) error
    Compensate func(ctx context.Context) error // 补偿操作
}

// Execute 执行 Saga
func (s *Saga) Execute(ctx context.Context) error {
    executed := make([]int, 0)
    
    // 正向执行
    for i, step := range s.steps {
        if err := step.Execute(ctx); err != nil {
            // 执行失败，反向补偿
            s.compensate(ctx, executed)
            return fmt.Errorf("saga step %d failed: %w", i, err)
        }
        executed = append(executed, i)
    }
    
    return nil
}

// compensate 补偿操作
func (s *Saga) compensate(ctx context.Context, executed []int) {
    // 从后往前补偿
    for i := len(executed) - 1; i >= 0; i-- {
        step := s.steps[executed[i]]
        if err := step.Compensate(ctx); err != nil {
            // 补偿也失败了，记录日志，人工介入
            log.Error("compensation failed for step %s: %v", step.Name, err)
        }
    }
}
```

### 4.3 广告扣费的 Saga 实现

```go
// BillingSaga 扣费 Saga
type BillingSaga struct {
    billingSvc  *BillingService
    budgetSvc   *BudgetService
}

func (bs *BillingSaga) Create() *Saga {
    return &Saga{
        steps: []SagaStep{
            {
                Name: "record_consumption",
                Execute: func(ctx context.Context) error {
                    return bs.billingSvc.RecordConsumption(ctx)
                },
                Compensate: func(ctx context.Context) error {
                    return bs.billingSvc.ReverseConsumption(ctx)
                },
            },
            {
                Name: "deduct_budget",
                Execute: func(ctx context.Context) error {
                    return bs.budgetSvc.DeductBudget(ctx)
                },
                Compensate: func(ctx context.Context) error {
                    return bs.budgetSvc.RefundBudget(ctx)
                },
            },
        },
    }
}
```

### 4.4 TCC 模式

```
Try-Confirm-Cancel 模式：

Try:
→ 冻结预算（预留资金）
→ 冻结频次（预留计数）

Confirm:
→ 确认扣费（实际扣减）
→ 确认频次（实际递增）

Cancel:
→ 解冻预算（释放预留）
→ 解冻频次（释放预留）

适用场景：强一致性要求，预算扣减
```

---

## 第五部分：服务网格（Istio）

### 5.1 Istio 在广告系统中的应用

```
流量治理：
→ 灰度发布：1% 流量到新版本
→ 金丝雀发布：逐步放量
→ A/B 测试：按 Header 分流

熔断降级：
→ 依赖服务超时：熔断
→ 依赖服务错误率 > 50%：熔断
→ 熔断后降级：返回缓存数据

可观测性：
→ 分布式追踪：TraceID 透传
→ 指标采集：Prometheus
→ 日志收集：Fluentd → ES
```

### 5.2 Istio 配置

```yaml
# VirtualService - 灰度发布
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bidding-service
spec:
  hosts:
  - bidding-service
  http:
  - route:
    - destination:
        host: bidding-service
        subset: v1
      weight: 90
    - destination:
        host: bidding-service
        subset: v2
      weight: 10
---
# DestinationRule - 服务版本定义
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: bidding-service
spec:
  host: bidding-service
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
---
# CircuitBreaker - 熔断配置
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: redis-service
spec:
  host: redis-service
  trafficPolicy:
    outlierDetection:
      consecutiveErrors: 5
      interval: 30s
      baseEjectionTime: 60s
      maxEjectionPercent: 50
```

---

## 第六部分：配置中心（Apollo）

### 6.1 配置管理

```
配置分级：
→ 全局配置：所有环境共享
→ 环境配置：dev/staging/prod 不同
→ 集群配置：不同广告位不同
→ 实例配置：不同服务实例不同

配置热更新：
→ 修改配置 → 推送 → 服务自动生效
→ 无需重启
→ 版本回滚
```

### 6.2 Go 实现

```go
package config

import (
    "sync"
    "time"
)

// ConfigManager 配置管理器
type ConfigManager struct {
    configs map[string]string
    listeners map[string][]func(string)
    mu sync.RWMutex
    apolloClient *ApolloClient
}

// Get 获取配置
func (cm *ConfigManager) Get(key string) string {
    cm.mu.RLock()
    defer cm.mu.RUnlock()
    return cm.configs[key]
}

// Watch 监听配置变更
func (cm *ConfigManager) Watch(key string, callback func(string)) {
    cm.mu.Lock()
    defer cm.mu.Unlock()
    
    if cm.listeners[key] == nil {
        cm.listeners[key] = make([]func(string), 0)
    }
    cm.listeners[key] = append(cm.listeners[key], callback)
}

// notifyListeners 通知监听者
func (cm *ConfigManager) notifyListeners(key, newValue string) {
    cm.mu.RLock()
    listeners := cm.listeners[key]
    cm.mu.RUnlock()
    
    for _, listener := range listeners {
        listener(newValue)
    }
}
```

---

## 第七部分：全链路追踪（Jaeger）

### 7.1 TraceID 透传

```
请求链路：
API Gateway → 竞价服务 → 召回服务 → 排序服务 → 计费服务
    │              │              │              │
    └──────────────┴──────────────┴──────────────┘
                    TraceID（全局唯一）
                    SpanID（每个服务的子span）
                    ParentSpanID（父子关系）
```

### 7.2 Go 实现

```go
package trace

import (
    "context"
    "github.com/uber/jaeger-client-go"
)

// Tracer 链路追踪
type Tracer struct {
    jaeger *jaeger.Tracer
}

// StartSpan 开始新的 Span
func (t *Tracer) StartSpan(ctx context.Context, operationName string) (context.Context, jaeger.Span) {
    span := t.jaeger.StartSpan(operationName)
    ctx = jaeger.ContextWithSpan(ctx, span)
    return ctx, span
}

// Inject 注入 TraceID 到 Header
func (t *Tracer) Inject(ctx context.Context, headers map[string]string) error {
    span := jaeger.SpanFromContext(ctx)
    return t.jaeger.Inject(span.Context(), jaeger.HTTPHeaders, jaeger.HTTPHeadersCarrier(headers))
}

// Extract 从 Header 提取 TraceID
func (t *Tracer) Extract(headers map[string]string) (context.Context, jaeger.Span, error) {
    spanContext, err := t.jaeger.Extractor(jaeger.HTTPHeadersCarrier(headers))
    if err != nil {
        return nil, nil, err
    }
    span := t.jaeger.StartSpan("operation", jaeger.ChildOf(spanContext))
    return jaeger.ContextWithSpan(context.Background(), span), span, nil
}
```

---

## 第八部分：自测题

### 问题 1
Kafka 分区策略怎么选？

<details>
<summary>查看答案</summary>

1. **展示事件**：user_id（保证顺序）
2. **预算变更**：account_id（同一广告主同一分区）
3. **频次变更**：user_id
4. **分区数**：根据 QPS 预估（1000 QPS → 100 分区）
5. **Exactly-Once**：幂等写入 + Offset 管理
</details>

### 问题 2
缓存穿透/击穿/雪崩怎么解决？

<details>
<summary>查看答案</summary>

1. **穿透**：布隆过滤器 + 空值缓存
2. **击穿**：互斥锁 + 永不过期
3. **雪崩**：TTL 加随机值 + 多级缓存
4. **一致性**：Cache-Aside + 延迟双删
</details>

---

*本文档基于广告系统分布式架构生产实战整理。*