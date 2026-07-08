# 微信读书精华：从程序员到架构师深度蒸馏

> 基于微信读书「从程序员到架构师：大数据量、缓存、高并发、微服务、多团队协同等核心场景实战」蒸馏
> 作者: Ryan | 来源: 王伟杰 | 定位: 广告平台架构设计深度参考
> 蒸馏日期: 2026-07-08 | 状态: 🟢 深度（场景实战 + Trade-off + 广告平台映射）
> 阅读状态: ✅ 已读完

---

## 第一部分：入门引导（5 分钟速览）

### 1.1 为什么程序员到架构师是一道鸿沟？

从程序员到架构师，不是"写更多代码"，而是**决策维度的跃迁**：

```
程序员思维 → 架构师思维

┌─────────────────────┐    ┌─────────────────────┐
│ 关注点              │    │ 关注点              │
├─────────────────────┤    ├─────────────────────┤
│ 如何实现这个功能     │ →  │ 是否需要这个功能     │
│ 这段代码有没有 bug   │ →  │ 这个模块会不会成为瓶颈 │
│ 这个框架怎么用       │ →  │ 这个技术选型值不值得  │
│ 性能能不能优化       │ →  │ 成本和收益是否匹配    │
│ 单个服务的正确性     │ →  │ 多个系统的协调性      │
│ 技术深度             │ →  │ 技术广度 + 权衡能力   │
└─────────────────────┘    └─────────────────────┘
```

**在广告平台场景中的体现**：
- 程序员关注：竞价接口如何在 5ms 内返回广告
- 架构师关注：当 QPS 从 1万 增长到 100万 时，整个链路如何演进

### 1.2 全书五大部分总览

```
从程序员到架构师：五大场景实战
┌─────────────────────────────────────────────────────────────────────┐
│ 第1部分 数据持久化层场景实战                                          │
│   第2章 查询分离 — 读写分离/主从复制/跨机房                            │
│   第3章 分表分库 — 水平拆分/垂直拆分/全局ID                           │
├─────────────────────────────────────────────────────────────────────┤
│ 第2部分 缓存层场景实战                                                │
│   第5章 写缓存 — Cache-Aside/Read-Through/Write-Behind               │
│   第6章 数据收集 — 数据采集/ETL/实时统计                              │
│   第7章 秒杀架构 — 库存预热/防超卖/限流降级                           │
├─────────────────────────────────────────────────────────────────────┤
│ 第3部分 基于常见组件的微服务场景实战                                    │
│   第9章 全链路日志 — TraceID/采样策略/日志聚合                        │
│   第10章 熔断 — 熔断器模式/半开状态/降级策略                          │
│   第11章 限流 — 令牌桶/漏桶/滑动窗口/GuavaRateLimiter                 │
├─────────────────────────────────────────────────────────────────────┤
│ 第4部分 微服务进阶场景实战                                              │
│   第13章 数据一致性 — 最终一致性/ Saga/TCC/本地消息表                  │
│   第14章 数据同步 — Canal/Debezium/自定义同步                         │
│   第15章 BFF — Backend For Frontend/聚合服务/GraphQL                  │
├─────────────────────────────────────────────────────────────────────┤
│ 第5部分 开发运维场景实战                                                │
│   第17章 一人一套测试环境 — Docker/K8s/环境隔离                        │
│   第18章 结束语 — 如何成为不可或缺的人                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 架构设计的核心方法论

```
架构决策框架（TRIFORCE）：

T — Trade-off（权衡）：没有银弹，只有取舍
R — Requirements（需求）：架构服务于业务需求
I — Iteration（迭代）：架构是演进的，不是一次性的
F — Failure（容错）：假设一切都会失败
O — Optimization（优化）：测量驱动优化
C — Cost（成本）：技术成本 + 人力成本 + 时间成本
E — Evolution（演进）：架构需要随业务演进
```

---

## 第二部分：数据持久化层场景实战

### 2.1 查询分离（读写分离）

#### 2.1.1 为什么需要查询分离？

广告平台的典型数据访问模式：

```
写入：竞价事件、计费记录、曝光日志 → 高吞吐写入
读取：报表查询、用户画像查询、广告创意查询 → 复杂 JOIN + 聚合

问题：写入和读取争夺同一份资源
- 写入锁表 → 读取阻塞
- 读取大事务 → 写入超时
- 慢查询 → 连接池耗尽

解决方案：读写分离
┌──────────┐     ┌──────────┐
│  Master  │────▶│  Slave 1 │  ← 读取
│  (写)    │     │  Slave 2 │  ← 读取
└──────────┘     └──────────┘
```

#### 2.1.2 广告平台读写分离方案

```go
// 广告平台读写分离路由
type DBRouter struct {
    writer *sql.DB  // Master - 只写
    readers []*sql.DB // Slaves - 只读
}

func (r *DBRouter) Write(query string, args ...interface{}) (*sql.Result, error) {
    return r.writer.Exec(query, args...)
}

func (r *DBRouter) Read(query string, args ...interface{}) (*sql.Rows, error) {
    // 负载均衡：轮询选择 slave
    reader := r.readers[time.Now().UnixNano()%int64(len(r.readers))]
    return reader.Query(query, args...)
}
```

**关键参数配置**：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `maxOpenConns` (writer) | 50 | Master 连接数，写入密集型 |
| `maxOpenConns` (reader) | 200 | Slave 连接数，读取密集型 |
| `connMaxLifetime` | 30m | 连接最大生命周期 |
| `replication lag threshold` | 5s | 超过 5s 延迟的 slave 不参与读取 |

#### 2.1.3 复制延迟问题与解决方案

```
主从复制延迟场景：
Master: INSERT INTO ad_impression VALUES (...)  →  t=0ms
Slave1: 同步中...  →  t=200ms  ← 此时读取可能看不到最新数据

广告平台中的影响：
1. 计费对账：刚产生的曝光记录，报表查不到 → 对账差异
2. 用户画像更新：刚点击的广告，画像没更新 → 定向不准
3. 频控：刚展示的广告，再次展示时频控没生效 → 用户体验差

解决方案：
┌─────────────────────────────────────────────────────────────┐
│ 方案1：强制走 Master（强一致）                                │
│   - 计费写入后立即读取 → 标记 readFromMaster=true             │
│   - 优点：数据绝对一致                                        │
│   - 缺点：Master 压力大，失去读写分离意义                       │
├─────────────────────────────────────────────────────────────┤
│ 方案2：容忍延迟（最终一致）                                    │
│   - 报表查询容忍 5s 延迟                                     │
│   - 频控查询走 Master（关键路径）                              │
│   - 优点：读写分离效果最大化                                   │
│   - 缺点：需要业务层感知延迟                                   │
├─────────────────────────────────────────────────────────────┤
│ 方案3：半同步复制（折中）                                      │
│   - Master 等待至少 1 个 Slave 写入 binlog 后才返回           │
│   - 延迟：RTT（通常 < 10ms）                                 │
│   - 优点：兼顾一致性和性能                                     │
│   - 缺点：Master 写入 RT 增加                                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 分表分库

#### 2.2.1 为什么要分表？

```
单表容量极限：
- InnoDB 单表建议不超过 2000 万行
- 超过后：索引膨胀、全表扫描变慢、DDL 操作锁表时间过长

广告平台数据量估算：
- 日曝光量：10 亿次
- 单条曝光记录：~200 bytes
- 日增量：~200 GB
- 年增量：~73 TB
- 单表 2000 万行 × 200 bytes = 4 GB

结论：必须分表！
```

#### 2.2.2 分表策略

```go
// 广告曝光表分表策略
type ShardStrategy int

const (
    HashShard ShardStrategy = iota  // 哈希分表
    RangeShard                       // 范围分表
    TimeShard                        // 时间分表
)

// 哈希分表：按 campaign_id 哈希
func hashShard(campaignID uint64, shardCount int) int {
    return int(campaignID % uint64(shardCount))
}

// 时间分表：按月分表
func timeShard(tablePrefix string, year int, month int) string {
    return fmt.Sprintf("%s_%d_%02d", tablePrefix, year, month)
}

// 复合分表：campaign_id 哈希 + 时间
// 先按时间分库，再按 campaign_id 分表
func compositeShard(campaignID uint64, year int, month int, 
                     dbCount int, tableCount int) (string, string) {
    dbIndex := int(campaignID % uint64(dbCount))
    tableIndex := int(campaignID % uint64(tableCount))
    return fmt.Sprintf("db_%d", dbIndex), 
           fmt.Sprintf("ad_impression_%d_%02d_t%d", year, month, tableIndex)
}
```

**分表方案对比**：

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 哈希分表 | 分布均匀，查询路由简单 | 扩容困难，跨分片查询难 | 均匀访问模式 |
| 范围分表 | 范围查询高效 | 数据倾斜，热点 key | 时间序列数据 |
| 时间分表 | 过期数据易清理 | 近期数据热点 | 日志/埋点数据 |
| 复合分表 | 灵活，兼顾查询和扩容 | 路由复杂 | 大规模广告平台 |

#### 2.2.3 全局唯一 ID 生成

```go
// 广告平台 ID 生成器：Snowflake 变种
type SnowflakeID struct {
    mu         sync.Mutex
    timestamp  int64
    workerID   int64  // 机器 ID
    sequence   int64  // 序列号
}

func (s *SnowflakeID) NextID() int64 {
    s.mu.Lock()
    defer s.mu.Unlock()
    
    now := time.Now().UnixMilli()
    if now == s.timestamp {
        s.sequence++
    } else {
        s.timestamp = now
        s.sequence = 0
    }
    
    // ID 结构：timestamp(41bit) | workerID(10bit) | sequence(12bit)
    return (now << 22) | (s.workerID << 12) | s.sequence
}
```

**ID 生成方案对比**：

| 方案 | 延迟 | 吞吐量 | 有序性 | 可用性 | 适用场景 |
|------|------|--------|--------|--------|---------|
| 数据库自增 | 高 | 低 | 全局有序 | 依赖 DB | 小规模 |
| UUID | 低 | 高 | 无序 | 高 | 分布式场景 |
| Snowflake | 极低 | 极高 | 分段有序 | 高 | 广告平台首选 |
| Leaf（美团） | 低 | 高 | 分段有序 | 极高 | 超大规模 |

### 2.3 冷热分离

```
冷热数据分离架构：

热数据（最近 3 个月）：
├── MySQL 分表（SSD）
├── Redis 缓存（热点数据）
└── 查询 RT < 10ms

温数据（3 个月 - 1 年）：
├── MySQL 历史表（HDD）
├── 查询 RT < 100ms
└── 报表分析

冷数据（1 年以上）：
├── HDFS / S3 对象存储
├── ClickHouse / Elasticsearch
└── 查询 RT < 1s
```

---

## 第三部分：缓存层场景实战

### 3.1 写缓存策略

#### 3.1.1 三种缓存写入模式

```
Cache-Aside（旁路缓存）：
┌─────────┐    ┌─────────┐    ┌─────────┐
│  App    │───▶│  Cache  │───▶│  DB     │
│         │◀───│         │◀───│         │
└─────────┘    └─────────┘    └─────────┘

流程：
1. 读：先读 Cache，miss 则读 DB 并写入 Cache
2. 写：先写 DB，再删除 Cache（不是更新！）

优点：简单直观，Cache 和 DB 最终一致
缺点：写穿透时有短暂不一致

Read-Through（读取穿透）：
App → Cache → (miss) → Cache 自动读 DB → 返回
Cache 负责与 DB 的同步

优点：App 代码简洁
缺点：Cache 实现复杂

Write-Behind（写回缓存）：
App → Cache（立即返回）→ Cache 异步写 DB

优点：写入性能极高
缺点：数据可能丢失（Cache 宕机）
```

#### 3.1.2 广告平台缓存策略

```go
// 广告频控缓存：Cache-Aside + 延迟双删
type FrequencyControl struct {
    cache *redis.Client
    db    *sql.DB
}

// 写频控数据：先写 DB，再删 Cache
func (fc *FrequencyControl) UpdateFrequency(userID, adID string) error {
    // 1. 写 DB
    _, err := fc.db.Exec("INSERT INTO freq_control SET user_id=?, ad_id=?, count=count+1 ON DUPLICATE KEY UPDATE count=count+1", userID, adID)
    if err != nil {
        return err
    }
    
    // 2. 删 Cache
    fc.cache.Del(context.Background(), "freq:"+userID+":"+adID)
    
    // 3. 延迟删（防止并发读穿透）
    time.Sleep(500 * time.Millisecond)
    fc.cache.Del(context.Background(), "freq:"+userID+":"+adID)
    
    return nil
}

// 读频控数据：先读 Cache
func (fc *FrequencyControl) GetFrequency(userID, adID string) (int, error) {
    val, err := fc.cache.Get(context.Background(), "freq:"+userID+":"+adID).Int()
    if err == redis.Nil {
        // Cache miss，读 DB 并回填
        var count int
        err := fc.db.QueryRow("SELECT count FROM freq_control WHERE user_id=? AND ad_id=?", userID, adID).Scan(&count)
        if err != nil {
            return 0, err
        }
        fc.cache.Set(context.Background(), "freq:"+userID+":"+adID, count, 24*time.Hour)
        return count, nil
    }
    return val, nil
}
```

### 3.2 秒杀架构（广告爆量场景）

```
广告爆量场景 = 秒杀场景

场景：某个热门 APP 投放信息流广告，瞬间获得大量曝光
问题：QPS 从 100 飙升至 100,000

秒杀架构五层防线：
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: CDN 静态资源缓存（提前预热）                         │
│   - 广告创意图片/视频 CDN 缓存                               │
│   - 命中 CDN → 不经过后端                                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: 网关限流（Token Bucket）                            │
│   - 每秒最多 50,000 请求                                    │
│   - 超出请求直接返回 429                                     │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: 缓存层（库存/频控预加载）                            │
│   - 频控数据预加载到 Redis                                   │
│   - 本地缓存（Caffeine/Guava）                               │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: 异步处理（消息队列削峰）                              │
│   - 曝光事件写入 Kafka                                       │
│   - 消费者按能力消费                                         │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: 数据库保护（连接池限制 + 慢查询熔断）                 │
│   - 最大连接数限制                                           │
│   - 慢查询自动熔断                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 第四部分：微服务场景实战

### 4.1 全链路日志

```
广告平台全链路追踪：

用户点击广告 → 广告服务器 → 竞价服务 → 计费服务 → 日志服务
    │              │            │            │            │
    └──────────────┴────────────┴────────────┴────────────┘
                    TraceID: abc-123-def-456

每个服务记录：
- TraceID（贯穿全链路）
- SpanID（当前调用）
- ParentSpanID（父调用）
- ServiceName
- Timestamp
- Duration
- Tags（user_id, ad_id, campaign_id）
```

```go
// Go 全链路日志实现
type TraceContext struct {
    TraceID string
    SpanID  string
    Parent  string
}

func NewTraceContext() *TraceContext {
    return &TraceContext{
        TraceID: generateUUID(),
        SpanID:  generateShortUUID(),
        Parent:  "",
    }
}

// 从 HTTP Header 中提取 TraceID
func ExtractTraceContext(r *http.Request) *TraceContext {
    traceID := r.Header.Get("X-Trace-ID")
    spanID := r.Header.Get("X-Span-ID")
    parent := r.Header.Get("X-Parent-Span-ID")
    
    if traceID == "" {
        traceID = generateUUID()
    }
    
    return &TraceContext{
        TraceID: traceID,
        SpanID:  generateShortUUID(),
        Parent:  parent,
    }
}
```

### 4.2 熔断模式

```
熔断器状态机：

CLOSED ─────▶ OPEN ─────▶ HALF-OPEN
  │            │            │
  │ 失败率>50% │ 等待5s     │ 测试请求
  │            │            │
  ▼            ▼            ▼
正常执行    快速失败    成功→CLOSED
                        失败→OPEN
```

```go
// 广告竞价服务熔断器
type CircuitBreaker struct {
    mu             sync.Mutex
    state          State  // CLOSED/OPEN/HALF-OPEN
    failureCount   int
    successCount   int
    failureThreshold int = 5
    successThreshold   int = 3
    timeout          time.Duration = 5 * time.Second
    lastFailTime     time.Time
}

func (cb *CircuitBreaker) AllowRequest() bool {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case CLOSED:
        return true
    case OPEN:
        if time.Since(cb.lastFailTime) > cb.timeout {
            cb.state = HALF-OPEN
            cb.successCount = 0
            return true
        }
        return false
    case HALF-OPEN:
        return true
    }
    return false
}

func (cb *CircuitBreaker) RecordSuccess() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.successCount++
    if cb.state == HALF-OPEN && cb.successCount >= cb.successThreshold {
        cb.state = CLOSED
        cb.failureCount = 0
    }
}

func (cb *CircuitBreaker) RecordFailure() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.failureCount++
    cb.lastFailTime = time.Now()
    
    if cb.state == CLOSED && cb.failureCount >= cb.failureThreshold {
        cb.state = OPEN
    }
}
```

### 4.3 限流

```go
// 广告 API 限流器：令牌桶 + 滑动窗口
type RateLimiter struct {
    tokens     chan struct{}
    windowSize time.Duration
    maxRequests int
}

func NewSlidingWindowLimiter(maxReq int, window time.Duration) *RateLimiter {
    rl := &RateLimiter{
        tokens:      make(chan struct{}, maxReq),
        windowSize:  window,
        maxRequests: maxReq,
    }
    
    // 预填充令牌
    for i := 0; i < maxReq; i++ {
        rl.tokens <- struct{}{}
    }
    
    // 定期补充令牌
    go func() {
        ticker := time.NewTicker(window / time.Duration(maxReq))
        for range ticker.C {
            select {
            case rl.tokens <- struct{}{}:
            default:
                // 令牌桶已满，丢弃
            }
        }
    }()
    
    return rl
}

func (rl *RateLimiter) Allow() bool {
    select {
    case <-rl.tokens:
        return true
    default:
        return false
    }
}
```

**限流算法对比**：

| 算法 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| 固定窗口 | 时间桶计数 | 简单 | 临界突刺 | 简单 API |
| 滑动窗口 | 固定窗口改进 | 平滑 | 内存占用 | 广告 API |
| 令牌桶 | 匀速放令牌 | 允许突发 | 需要维护 | 信息发布 |
| 漏桶 | 匀速处理 | 严格限速 | 不允许突发 | 消息队列 |

### 4.4 数据一致性

```
微服务间数据一致性方案：

Saga 模式（适合广告平台）：
┌────────┐    ┌────────┐    ┌────────┐
│ 下单   │───▶│ 竞价   │───▶│ 计费   │
│(补偿)  │◀───│(补偿)  │◀───│(补偿)  │
└────────┘    └────────┘    └────────┘

步骤：
1. 创建竞价任务 → 成功
2. 扣减预算 → 成功
3. 记录曝光 → 失败！

补偿：
3. 回滚曝光（无操作）
2. 恢复预算 → 成功
1. 取消竞价任务 → 成功
```

```go
// Saga 事务实现
type SagaStep struct {
    Name       string
    Execute    func() error
    Compensate func() error
}

type Saga struct {
    steps []SagaStep
}

func (s *Saga) AddStep(name string, exec, comp func() error) {
    s.steps = append(s.steps, SagaStep{Name: name, Execute: exec, Compensate: comp})
}

func (s *Saga) Execute() error {
    var executed []int
    
    for i, step := range s.steps {
        if err := step.Execute(); err != nil {
            // 执行失败，反向补偿
            for j := len(executed) - 1; j >= 0; j-- {
                s.steps[executed[j]].Compensate()
            }
            return fmt.Errorf("saga step %s failed: %w", step.Name, err)
        }
        executed = append(executed, i)
    }
    return nil
}
```

### 4.5 数据同步

```
广告平台数据同步方案：

CDC（Change Data Capture）：
┌────────┐  binlog  ┌──────────┐  Kafka  ┌──────────┐
│ MySQL  │─────────▶│  Canal   │────────▶│ ClickHouse│
└────────┘          └──────────┘         └──────────┘

Canal 工作原理：
1. Canal 伪装成 MySQL Slave
2. Master 推送 binlog 给 Canal
3. Canal 解析 binlog 为结构化数据
4. 推送到 Kafka / ElasticSearch / ClickHouse
```

### 4.6 BFF（Backend For Frontend）

```
广告平台 BFF 架构：

┌─────────────────────────────────────────────────────────────┐
│                         前端层                               │
│   Web Dashboard  │  Mobile App  │  第三方 API  │  内部系统    │
└────────┬─────────┴────────┬─────┴────────┬─────┴────────┬───┘
         │                  │              │              │
         └──────────────────┼──────────────┼──────────────┘
                            │              │
                    ┌───────▼──────────────▼───────┐
                    │        BFF 聚合层             │
                    │  ┌─────────┐ ┌─────────┐    │
                    │  │Campaign │ │ AdGroup │    │
                    │  │ Service │ │ Service │    │
                    │  └─────────┘ └─────────┘    │
                    │  ┌─────────┐ ┌─────────┐    │
                    │  │Creative │ │ Report  │    │
                    │  │ Service │ │ Service │    │
                    │  └─────────┘ └─────────┘    │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │       核心微服务层            │
                    │  竞价 · 计费 · 定向 · 频控    │
                    └──────────────────────────────┘
```

---

## 第五部分：开发运维场景实战

### 5.1 一人一套测试环境

```
广告平台测试环境架构：

物理隔离：
┌─────────────────────────────────────────────────────────────┐
│ K8s Namespace 隔离                                           │
│                                                              │
│  dev-ryan    → 完整生产配置（缩容 10%）                       │
│  dev-zhang   → 完整生产配置（缩容 10%）                       │
│  staging     → 生产等价配置（1:1）                           │
│  production  → 生产环境                                      │
└─────────────────────────────────────────────────────────────┘

关键实践：
1. 基础设施即代码（Terraform/Helm）
2. 配置外部化（Apollo/Nacos）
3. 数据脱敏（生产数据 → 测试数据）
4. 自动化部署（CI/CD Pipeline）
```

### 5.2 成为不可或缺的人

```
架构师成长路径：

技术深度：
├── 精通 1-2 个核心技术领域（MySQL/Redis/Go）
├── 理解 3-5 个周边领域（Kafka/Elasticsearch/K8s）
└── 知道 10+ 个技术的优缺点和适用场景

业务理解：
├── 理解广告平台的商业模式（CPM/CPC/oCPM）
├── 理解核心指标（CTR/CVR/ROI/eCPM）
└── 能从业务角度做技术决策

软技能：
├── 沟通能力：向非技术人员解释技术方案
├── 领导力：带领团队完成复杂项目
├── 判断力：在信息不全时做出正确决策
└── 影响力：推动技术标准和最佳实践
```

---

## 第六部分：与知识库的对照

### 6.1 已有知识覆盖

| 主题 | 知识库文件 | 覆盖程度 |
|------|-----------|---------|
| 读写分离 | `fullstack/weread-distributed-architecture-deep.md` | ✅ 已覆盖 |
| 分表分库 | `middleware/weread-tech-fundamentals-deep.md` | ✅ 已覆盖 |
| 缓存策略 | `middleware/weread-redis-go-kafka-deep.md` | ✅ 已覆盖 |
| 熔断限流 | `architecture/ad-architecture-high-concurrency-deep.md` | ✅ 已覆盖 |
| 全链路日志 | `infrastructure/observability-architecture-deep.md` | ✅ 已覆盖 |
| Saga 事务 | `architecture/weread-distributed-architecture-deep.md` | ✅ 已覆盖 |
| CDC 同步 | `bigdata/weread-ad-data-pipeline-deep.md` | ✅ 已覆盖 |

### 6.2 本书独特贡献

1. **场景化视角**：不是讲理论，而是讲"大数据量/缓存/高并发/微服务/多团队协同"五个具体场景
2. **查询分离的延迟处理**：专门讨论了主从复制延迟在广告平台中的影响和解决方案
3. **冷热分离策略**：针对广告数据的生命周期管理提供了清晰的分层方案
4. **秒杀架构五层防线**：将电商秒杀架构迁移到广告爆量场景，非常实用
5. **一人一套测试环境**：K8s namespace 隔离的实践方案，对中小团队很有参考价值
6. **BFF 聚合层**：广告平台管理后台的 BFF 设计模式

### 6.3 待补充知识

1. ~~微服务治理（Service Mesh/Istio）~~ → 已有 `architecture/cloud-native-architecture.md`
2. ~~分布式事务（TCC/Saga）~~ → 已在 saga 部分覆盖
3. ~~数据一致性模型~~ → 需要补充 CAP/BASE 理论的广告场景映射

---

## 第七部分：自测题

### Q1：广告曝光表日增 10 亿条，如何设计分表策略？

**答案**：
- 采用时间分表 + 哈希分表的复合策略
- 先按月份分库（`ad_impression_202607`），再按 campaign_id 哈希分表（128 表/库）
- 全局 ID 使用 Snowflake 算法
- 冷热数据分离：3 个月内走 MySQL，3 个月后同步到 ClickHouse
- 扩容方案：新增月份分库不影响已有数据

### Q2：读写分离场景下，计费系统如何保证数据一致性？

**答案**：
- 计费写入走 Master
- 计费后的即时查询（如预算扣除验证）强制走 Master（readFromMaster=true）
- 报表查询容忍 5s 延迟，走 Slave
- 关键路径（频控检查）走 Master
- 使用半同步复制降低延迟到 < 10ms

### Q3：秒杀架构中，如何防止广告频控超卖？

**答案**：
- 第一层：Redis 预扣减（Lua 原子操作）
- 第二层：本地缓存 + 分布式锁
- 第三层：异步消息队列削峰
- 第四层：数据库最终校验（乐观锁）
- 第五层：兜底策略（用户投诉后补偿）

---

> **蒸馏总结**：本书核心价值在于"场景化实战"——不是泛泛而谈架构理论，而是针对大数据量、缓存、高并发、微服务、多团队协同五个具体场景，给出了可落地的技术方案。对于广告平台从业者，特别有价值的是秒杀架构五层防线和读写分离延迟处理方案。
