# 广告系统架构深度：高并发/缓存/异步/降级/限流/监控

> 基于 DSP 场景的完整高并发系统设计

---

## 第一部分：为什么广告系统是最佳学习场景？

### 广告系统的极端要求

```
1. 高并发：
   → 每秒 1000+ 次竞价请求
   → 每次请求需要在 50ms 内完成
   → 峰值可能是平时的 10 倍

2. 低延迟：
   → 用户打开 App，广告必须在 100ms 内展示
   → 否则用户体验下降，跳出率上升

3. 高准确：
   → 预算不能超扣（用户投诉）
   → 频次不能超频（用户体验）
   → 出价不能算错（广告主利益）

4. 高可用：
   → 7×24 小时不能停
   → 任何一个组件故障都不能影响核心链路
```

### 对比其他系统

| 系统 | 并发量 | 延迟要求 | 准确性要求 | 可用性要求 |
|------|--------|---------|-----------|-----------|
| 广告系统 | 1000+ QPS | 50ms | 极高 | 99.99% |
| 电商下单 | 100 QPS | 200ms | 高 | 99.9% |
| 社交 Feed | 50 QPS | 500ms | 中 | 99.9% |
| 内部系统 | 10 QPS | 1s | 低 | 99% |

**结论：广告系统的要求是最极端的，所以最适合学习高并发设计。**

---

## 第二部分：高并发架构设计

### 2.1 整体架构

```
                        ┌─────────────────────────────────────┐
                        │         Client (App)                │
                        └──────────────┬──────────────────────┘
                                       │
                        ┌──────────────▼──────────────────────┐
                        │       API Gateway (Nginx)           │
                        │  - 限流                              │
                        │  - 路由                              │
                        │  - 负载均衡                          │
                        └──────────────┬──────────────────────┘
                                       │
                        ┌──────────────▼──────────────────────┐
                        │      Bid Service (Go)               │
                        │  - 多路召回                          │
                        │  - 粗排/精排                         │
                        │  - 竞价决策                          │
                        └──────────────┬──────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
          ┌─────────▼─────────┐ ┌─────▼─────┐ ┌─────────▼─────────┐
          │   Memory Index    │ │ Predictor │ │  Async Service    │
          │   (内存索引)       │ │ (预测模型) │ │  (异步服务)        │
          │  - 广告筛选       │ │  - CTR/CVR│ │  - 频次记录       │
          │  - 用户画像       │ │  - 出价计算│ │  - 预算扣减       │
          │  - 热度/探索      │ │           │ │  - 数据统计       │
          └───────────────────┘ └───────────┘ └───────────────────┘
                    │                  │                  │
          ┌─────────▼─────────┐ ┌─────▼─────┐ ┌─────────▼─────────┐
          │   MySQL           │ │  Redis    │ │   Kafka           │
          │  - 持久化存储     │ │  - 缓存   │ │  - 消息队列       │
          │  - 广告主管理     │ │  - 频次   │ │  - 异步解耦       │
          │  - 财务报表       │ │  - 预算   │ │  - 削峰填谷       │
          └───────────────────┘ └───────────┘ └───────────────────┘
```

### 2.2 核心设计原则

```
1. 读写分离：
   → 写操作：MySQL（持久化）
   → 读操作：内存索引（快速）

2. 异步解耦：
   → 核心链路：竞价（同步，50ms）
   → 非核心链路：频次/预算/统计（异步，Kafka）

3. 缓存优先：
   → L1：本地缓存（Go map，< 1ms）
   → L2：Redis 缓存（< 5ms）
   → L3：MySQL（< 50ms）

4. 降级策略：
   → 画像获取失败：使用默认画像
   → 模型预测失败：使用历史均值
   → Redis 故障：降级到 MySQL
```

---

## 第三部分：缓存设计

### 3.1 三级缓存架构

```
                    ┌─────────────────────────────────────┐
                    │         Client Request               │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │       L1: Local Cache (Go map)       │
                    │  - 命中率：80%                       │
                    │  - 延迟：< 0.1ms                    │
                    │  - 过期时间：5 分钟                  │
                    └──────────────┬──────────────────────┘
                                   │ 未命中
                    ┌──────────────▼──────────────────────┐
                    │       L2: Redis Cache                │
                    │  - 命中率：95%                       │
                    │  - 延迟：< 1ms                      │
                    │  - 过期时间：30 分钟                 │
                    └──────────────┬──────────────────────┘
                                   │ 未命中
                    ┌──────────────▼──────────────────────┐
                    │       L3: MySQL Database             │
                    │  - 命中率：5%                        │
                    │  - 延迟：< 10ms                     │
                    └─────────────────────────────────────┘
```

### 3.2 Go 实现

```go
package dsp

import (
    "context"
    "sync"
    "time"
)

// CacheTier 缓存层级
type CacheTier int

const (
    TierLocal CacheTier = iota
    TierRedis
    TierMySQL
)

// UserCache 用户画像缓存
type UserCache struct {
    localCache  map[string]*CachedUser
    localExpire map[string]time.Time
    redis       *RedisClient
    db          *Database
    mu          sync.RWMutex
    
    // 配置
    localTTL    time.Duration // 本地缓存过期时间
    redisTTL    time.Duration // Redis 缓存过期时间
}

type CachedUser struct {
    UserID   string
    Profile  *UserProfile
    ExpiresAt time.Time
}

// GetUserProfile 获取用户画像（三级缓存）
func (uc *UserCache) GetUserProfile(ctx context.Context, userID string) (*UserProfile, error) {
    // 1. 查 L1 本地缓存
    uc.mu.RLock()
    if cached, ok := uc.localCache[userID]; ok && time.Now().Before(cached.ExpiresAt) {
        uc.mu.RUnlock()
        return cached.Profile, nil
    }
    uc.mu.RUnlock()
    
    // 2. 查 L2 Redis 缓存
    profile, err := uc.redis.GetUserProfile(ctx, userID)
    if err == nil && profile != nil {
        // 回填 L1 本地缓存
        uc.setLocalCache(userID, profile)
        return profile, nil
    }
    
    // 3. 查 L3 MySQL
    profile, err = uc.db.GetUserProfile(ctx, userID)
    if err != nil {
        return nil, err
    }
    
    // 4. 回填 L1 和 L2
    uc.setLocalCache(userID, profile)
    uc.redis.SetUserProfile(ctx, userID, profile)
    
    return profile, nil
}

// setLocalCache 设置本地缓存
func (uc *UserCache) setLocalCache(userID string, profile *UserProfile) {
    uc.mu.Lock()
    defer uc.mu.Unlock()
    
    if uc.localCache == nil {
        uc.localCache = make(map[string]*CachedUser)
    }
    
    uc.localCache[userID] = &CachedUser{
        UserID:    userID,
        Profile:   profile,
        ExpiresAt: time.Now().Add(uc.localTTL),
    }
}
```

### 3.3 缓存穿透/击穿/雪崩

```
问题 1：缓存穿透
→ 恶意请求查询不存在的数据
→ 每次都打到 MySQL
→ 解决方案：布隆过滤器

问题 2：缓存击穿
→ 热点 key 过期，大量请求同时打到 MySQL
→ 解决方案：互斥锁/永不过期

问题 3：缓存雪崩
→ 大量 key 同时过期
→ 解决方案：随机过期时间
```

```go
// BloomFilter 布隆过滤器（防缓存穿透）
type BloomFilter struct {
    bits   []bool
    size   int
    hashes []func(string) int
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

// MutexCache 互斥锁缓存（防缓存击穿）
type MutexCache struct {
    redis *RedisClient
    mu    sync.Mutex
}

func (mc *MutexCache) GetOrCreate(ctx context.Context, key string, fn func() (*UserProfile, error)) (*UserProfile, error) {
    // 1. 查缓存
    profile, err := mc.redis.Get(ctx, key)
    if err == nil && profile != nil {
        return profile, nil
    }
    
    // 2. 加锁
    mc.mu.Lock()
    defer mc.mu.Unlock()
    
    // 3. 双重检查
    profile, err = mc.redis.Get(ctx, key)
    if err == nil && profile != nil {
        return profile, nil
    }
    
    // 4. 查询数据库
    profile, err = fn()
    if err != nil {
        return nil, err
    }
    
    // 5. 写入缓存
    mc.redis.Set(ctx, key, profile)
    
    return profile, nil
}
```

---

## 第四部分：异步处理

### 4.1 为什么需要异步？

```
核心链路（同步，50ms）：
用户请求 → 广告筛选 → 频次检查 → 预算检查 → CTR/CVR 预测 → 出价 → 返回

非核心链路（异步）：
→ 频次记录（已经检查过了，记录可以异步）
→ 预算扣减（已经检查过了，扣减可以异步）
→ 数据统计（可以异步）
→ 日志记录（可以异步）

好处：
1. 核心链路更短（50ms → 30ms）
2. 非核心链路失败不影响核心功能
3. 可以批量处理，提高效率
```

### 4.2 Go 实现

```go
package dsp

import (
    "context"
    "time"
)

// AsyncService 异步服务
type AsyncService struct {
    kafkaProducer *KafkaProducer
    workerPool    *WorkerPool
}

// RecordFrequency 异步记录频次
func (svc *AsyncService) RecordFrequency(ctx context.Context, userID, adID, date string) {
    // 发送到 Kafka
    msg := &FrequencyMessage{
        UserID: userID,
        AdID:   adID,
        Date:   date,
        Time:   time.Now(),
    }
    
    svc.kafkaProducer.Send("ad.frequency", msg)
}

// DeductBudget 异步扣减预算
func (svc *AsyncService) DeductBudget(ctx context.Context, campaignID string, amount float64) {
    // 发送到 Kafka
    msg := &BudgetMessage{
        CampaignID: campaignID,
        Amount:     amount,
        Time:       time.Now(),
    }
    
    svc.kafkaProducer.Send("ad.budget", msg)
}

// WorkerPool 工作协程池
type WorkerPool struct {
    jobs    chan func()
    results chan error
    wg      sync.WaitGroup
}

func NewWorkerPool(size int) *WorkerPool {
    wp := &WorkerPool{
        jobs:    make(chan func(), size),
        results: make(chan error, size),
    }
    
    // 启动 workers
    for i := 0; i < size; i++ {
        go wp.worker()
    }
    
    return wp
}

func (wp *WorkerPool) worker() {
    for job := range wp.jobs {
        wp.wg.Add(1)
        go func(j func()) {
            defer wp.wg.Done()
            // 执行 job
            j()
        }(job)
    }
}

func (wp *WorkerPool) Submit(job func()) {
    wp.jobs <- job
}

func (wp *WorkerPool) Wait() {
    close(wp.jobs)
    wp.wg.Wait()
}
```

---

## 第五部分：降级策略

### 5.1 降级方案

```
场景 1：用户画像服务不可用
→ 降级：使用默认画像（年龄 25-35，性别 M，城市北京）
→ 影响：精准度下降，但核心功能可用

场景 2：预测模型服务不可用
→ 降级：使用历史均值（CTR=0.01, CVR=0.05）
→ 影响：出价不准确，但核心功能可用

场景 3：Redis 不可用
→ 降级：直接查 MySQL
→ 影响：延迟上升，但核心功能可用

场景 4：MySQL 不可用
→ 降级：使用内存中的缓存数据
→ 影响：数据可能不是最新的，但核心功能可用
```

### 5.2 Go 实现

```go
package dsp

import (
    "context"
    "fmt"
)

// FallbackStrategy 降级策略
type FallbackStrategy struct {
    userProfileSvc *UserProfileService
    predictorSvc   *PredictorService
    redisClient    *RedisClient
    db             *Database
    
    // 降级开关
    userProfileFallback bool
    predictorFallback   bool
    redisFallback       bool
}

// GetUserProfile 获取用户画像（带降级）
func (fs *FallbackStrategy) GetUserProfile(ctx context.Context, userID string) (*UserProfile, error) {
    // 1. 正常路径：查 Redis
    if !fs.redisFallback {
        profile, err := fs.redisClient.GetUserProfile(ctx, userID)
        if err == nil && profile != nil {
            return profile, nil
        }
    }
    
    // 2. 降级路径：查 MySQL
    if !fs.userProfileFallback {
        profile, err := fs.userProfileSvc.GetUserProfile(ctx, userID)
        if err == nil && profile != nil {
            return profile, nil
        }
    }
    
    // 3. 最终降级：使用默认画像
    return fs.getDefaultProfile(), nil
}

// PredictCTR_CVR 预测 CTR/CVR（带降级）
func (fs *FallbackStrategy) PredictCTR_CVR(ctx context.Context, ad *Ad, userID string) (*Prediction, error) {
    // 1. 正常路径：调用预测模型
    if !fs.predictorFallback {
        pred, err := fs.predictorSvc.Predict(ctx, ad, userID)
        if err == nil && pred != nil {
            return pred, nil
        }
    }
    
    // 2. 降级路径：使用历史均值
    return &Prediction{
        CTR: 0.01, // 历史平均 CTR
        CVR: 0.05, // 历史平均 CVR
    }, nil
}

// getDefaultProfile 获取默认画像
func (fs *FallbackStrategy) getDefaultProfile() *UserProfile {
    return &UserProfile{
        AgeRange: [2]int{25, 35},
        Gender:   "M",
        City:     "北京",
        Interests: []string{"tech", "news"},
    }
}
```

---

## 第六部分：限流熔断

### 6.1 限流策略

```
令牌桶算法：
→ 固定速率产生令牌
→ 请求需要消耗令牌
→ 没有令牌则拒绝

滑动窗口算法：
→ 将时间分成多个窗口
→ 统计每个窗口的请求数
→ 超过阈值则拒绝

漏桶算法：
→ 请求进入队列
→ 以固定速率处理
→ 队列满则拒绝
```

### 6.2 Go 实现

```go
package dsp

import (
    "sync"
    "time"
)

// RateLimiter 令牌桶限流器
type RateLimiter struct {
    tokens     chan struct{}
    refillRate int           // 每秒产生的令牌数
    maxSize    int           // 桶的大小
    mu         sync.Mutex
}

func NewRateLimiter(refillRate, maxSize int) *RateLimiter {
    rl := &RateLimiter{
        tokens:     make(chan struct{}, maxSize),
        refillRate: refillRate,
        maxSize:    maxSize,
    }
    
    // 启动令牌 refill goroutine
    go rl.refill()
    
    return rl
}

func (rl *RateLimiter) refill() {
    ticker := time.NewTicker(time.Second / time.Duration(rl.refillRate))
    defer ticker.Stop()
    
    for range ticker.C {
        rl.mu.Lock()
        select {
        case rl.tokens <- struct{}{}:
        default:
            // 桶已满，丢弃令牌
        }
        rl.mu.Unlock()
    }
}

func (rl *RateLimiter) Allow() bool {
    select {
    case <-rl.tokens:
        return true
    default:
        return false
    }
}

// CircuitBreaker 熔断器
type CircuitBreaker struct {
    state        CircuitState
    failureCount int
    successCount int
    resetTimeout time.Duration
    lastFailTime time.Time
    mu           sync.Mutex
}

type CircuitState int

const (
    StateClosed CircuitState = iota
    StateOpen
    StateHalfOpen
)

func (cb *CircuitBreaker) Allow() bool {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case StateClosed:
        return true
    case StateOpen:
        // 检查是否超过重置超时
        if time.Since(cb.lastFailTime) > cb.resetTimeout {
            cb.state = StateHalfOpen
            return true
        }
        return false
    case StateHalfOpen:
        return true
    }
    
    return false
}

func (cb *CircuitBreaker) RecordSuccess() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.successCount++
    if cb.successCount >= 5 {
        cb.state = StateClosed
        cb.failureCount = 0
        cb.successCount = 0
    }
}

func (cb *CircuitBreaker) RecordFailure() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.failureCount++
    cb.lastFailTime = time.Now()
    
    if cb.failureCount >= 10 {
        cb.state = StateOpen
    }
}
```

---

## 第七部分：监控告警

### 7.1 核心监控指标

```
1. 业务指标：
   → QPS（每秒请求数）
   → 延迟（P50/P90/P99）
   → 错误率
   → 竞价成功率

2. 资源指标：
   → CPU 使用率
   → 内存使用率
   → 网络 IO
   → 磁盘 IO

3. 缓存指标：
   → 缓存命中率
   → 缓存大小
   → 缓存过期数

4. 数据库指标：
   → 连接数
   → 慢查询数
   → 事务数
```

### 7.2 Go 实现

```go
package dsp

import (
    "sync/atomic"
    "time"
)

// Metrics 监控指标
type Metrics struct {
    // 业务指标
    TotalRequests   atomic.Int64
    SuccessfulBids  atomic.Int64
    FailedBids      atomic.Int64
    TotalLatency    atomic.Int64 // 纳秒
    
    // 延迟百分位
    Latencies []int64 // 最近 1000 个请求的延迟
    
    // 缓存指标
    CacheHits     atomic.Int64
    CacheMisses   atomic.Int64
    
    // 错误指标
    ErrorsByType  map[string]*atomic.Int64
}

func NewMetrics() *Metrics {
    return &Metrics{
        ErrorsByType: map[string]*atomic.Int64{
            "timeout":     &atomic.Int64{},
            "redis_error": &atomic.Int64{},
            "db_error":    &atomic.Int64{},
            "model_error": &atomic.Int64{},
        },
    }
}

// RecordRequest 记录请求
func (m *Metrics) RecordRequest(latency time.Duration, success bool, errType string) {
    m.TotalRequests.Add(1)
    
    if success {
        m.SuccessfulBids.Add(1)
    } else {
        m.FailedBids.Add(1)
        if errType != "" {
            if counter, ok := m.ErrorsByType[errType]; ok {
                counter.Add(1)
            }
        }
    }
    
    m.TotalLatency.Add(latency.Nanoseconds())
    
    // 记录延迟（用于计算百分位）
    m.Latencies = append(m.Latencies, latency.Nanoseconds())
    if len(m.Latencies) > 1000 {
        m.Latencies = m.Latencies[1:]
    }
}

// GetP99Latency 获取 P99 延迟
func (m *Metrics) GetP99Latency() time.Duration {
    if len(m.Latencies) == 0 {
        return 0
    }
    
    // 排序
    sorted := make([]int64, len(m.Latencies))
    copy(sorted, m.Latencies)
    sort.Slice(sorted, func(i, j int) bool {
        return sorted[i] < sorted[j]
    })
    
    // 计算 P99
    idx := int(float64(len(sorted)) * 0.99)
    if idx >= len(sorted) {
        idx = len(sorted) - 1
    }
    
    return time.Duration(sorted[idx])
}

// GetCacheHitRate 获取缓存命中率
func (m *Metrics) GetCacheHitRate() float64 {
    hits := m.CacheHits.Load()
    misses := m.CacheMisses.Load()
    total := hits + misses
    
    if total == 0 {
        return 0
    }
    
    return float64(hits) / float64(total)
}
```

---

## 第八部分：灰度发布

### 8.1 为什么需要灰度？

```
新模型上线的风险：
→ 精度下降 → 收入下降
→ 延迟增加 → 超时增加
→ Bug → 服务不可用

灰度发布的解决方案：
→ 1% 流量 → 观察 1 小时
→ 5% 流量 → 观察 1 小时
→ 10% 流量 → 观察 1 小时
→ 50% 流量 → 观察 1 小时
→ 100% 流量 → 全量发布
```

### 8.2 Go 实现

```go
package dsp

import (
    "sync/atomic"
)

// CanaryRelease 灰度发布控制器
type CanaryRelease struct {
    currentVersion string
    targetVersion  string
    trafficPercent atomic.Int32 // 0-100
    maxPercent     int32
}

func NewCanaryRelease(currentVersion, targetVersion string, maxPercent int32) *CanaryRelease {
    cr := &CanaryRelease{
        currentVersion: currentVersion,
        targetVersion:  targetVersion,
        maxPercent:     maxPercent,
    }
    
    cr.trafficPercent.Store(0)
    
    return cr
}

// ShouldUseNewVersion 决定是否使用新版本
func (cr *CanaryRelease) ShouldUseNewVersion(userID string) bool {
    percent := cr.trafficPercent.Load()
    if percent == 0 {
        return false
    }
    
    // 基于 userID 哈希决定
    hash := hash(userID) % 100
    return hash < int32(percent)
}

// IncreaseTraffic 增加流量百分比
func (cr *CanaryRelease) IncreaseTraffic(increment int32) {
    current := cr.trafficPercent.Load()
    newPercent := current + increment
    if newPercent > cr.maxPercent {
        newPercent = cr.maxPercent
    }
    cr.trafficPercent.Store(newPercent)
}

// Rollback 回滚
func (cr *CanaryRelease) Rollback() {
    cr.trafficPercent.Store(0)
    cr.targetVersion = cr.currentVersion
}
```

---

## 第九部分：A/B 测试

### 9.1 为什么需要 A/B 测试？

```
新出价策略上线：
→ 策略 A：当前策略（对照组）
→ 策略 B：新策略（实验组）

需要对比：
→ eCPM 提升？
→ 点击率提升？
→ 转化率提升？
→ 收入提升？
```

### 9.2 Go 实现

```go
package dsp

import (
    "sync/atomic"
)

// ABTest A/B 测试控制器
type ABTest struct {
    controlGroup atomic.Int32 // 对照组流量百分比
    experimentGroup atomic.Int32 // 实验组流量百分比
}

func NewABTest(controlPercent, experimentPercent int32) *ABTest {
    ab := &ABTest{}
    ab.controlGroup.Store(controlPercent)
    ab.experimentGroup.Store(experimentPercent)
    return ab
}

// GetGroup 获取用户所属组
func (ab *ABTest) GetGroup(userID string) string {
    hash := hash(userID) % 100
    
    if hash < int(ab.controlGroup.Load()) {
        return "control"
    } else if hash < int(ab.controlGroup.Load()+ab.experimentGroup.Load()) {
        return "experiment"
    }
    
    return "control" // 默认对照组
}

// RecordMetric 记录指标
func (ab *ABTest) RecordMetric(group string, metric string, value float64) {
    // 记录到监控系统
    // ...
}
```

---

## 第十部分：容量规划

### 10.1 如何估算资源？

```
假设：
→ 日均请求量：1 亿次
→ 峰值 QPS：1000
→ 平均响应时间：50ms
→ 每台机器 4 核 8G

计算：
1. CPU 需求：
   → 1000 QPS × 50ms = 50 核（理论最小）
   → 考虑 GC/网络/其他开销 × 3 = 150 核
   → 4 核/台 × 150 核 = 38 台

2. 内存需求：
   → 1000 万广告 × 200B = 2GB
   → 倒排索引：40MB
   → 用户画像缓存：1GB
   → 总计：3.1GB/台
   → 8GB/台 × 2（冗余）= 16GB

3. 网络需求：
   → 1000 QPS × 1KB = 1MB/s
   → 考虑突发流量 × 10 = 10MB/s
   → 100Mbps 网卡足够

结论：需要 40 台 4 核 8G 机器
```

### 10.2 弹性伸缩

```
Kubernetes HPA（Horizontal Pod Autoscaler）：
→ CPU 使用率 > 70% → 扩容
→ CPU 使用率 < 30% → 缩容
→ 最小副本数：20
→ 最大副本数：100

Auto Scaling 策略：
→ 基于 QPS：1000 QPS → 20 副本
→ 基于延迟：P99 > 100ms → 扩容
→ 基于错误率：错误率 > 1% → 扩容
```

---

## 第十一部分：生产排障案例

### 11.1 线上故障排查

```
现象：P99 延迟从 50ms 飙升到 500ms

排查步骤：
1. 看监控大盘
   → QPS：正常（1000）
   → CPU：95%（异常）
   → 内存：正常（4GB/8GB）
   → 网络：正常

2. 看 pprof
   → CPU profile：热点在 predictor.Predict()
   → goroutine profile：正常（100 个）
   → heap profile：正常（4GB）

3. 看日志
   → 大量 "model timeout after 100ms"
   → 大量 "Redis timeout after 50ms"

根因分析：
1. 预测模型服务响应变慢
2. Redis 连接池耗尽
3. 两者叠加导致 P99 飙升

解决方案：
1. 立即：增加 Redis 连接池大小
2. 短期：预测模型服务扩容
3. 长期：增加降级策略
```

### 11.2 预算超扣

```
现象：广告主投诉预算扣多了

排查：
1. 检查预算扣减逻辑
2. 检查并发情况
3. 检查 Redis 数据

根因：
→ 高并发下，预算检查非原子操作
→ 两个请求同时 CheckBudget，都看到预算充足
→ 都扣减了，总扣减 > 预算

解决方案：
→ 使用 Lua 脚本保证原子性
→ Check + Deduct 在一个脚本中完成
```

---

## 第十二部分：自测题

### 问题 1
广告系统为什么需要三级缓存？

<details>
<summary>查看答案</summary>

1. **L1 本地缓存**：命中率 80%，延迟 < 0.1ms
2. **L2 Redis 缓存**：命中率 95%，延迟 < 1ms
3. **L3 MySQL**：命中率 5%，延迟 < 10ms
4. **总体效果**：95% 的请求在 L1/L2 命中，P99 延迟 < 5ms
5. **缓存穿透/击穿/雪崩**：布隆过滤器/互斥锁/随机过期时间
</details>

### 问题 2
为什么要异步处理频次和预算？

<details>
<summary>查看答案</summary>

1. **核心链路更短**：50ms → 30ms
2. **非核心链路失败不影响核心功能**
3. **可以批量处理，提高效率**
4. **Kafka 削峰填谷**：高峰时积压，低谷时处理
5. **最终一致性**：频次/预算可以最终一致
</details>

### 问题 3
如何保证高可用？

<details>
<summary>查看答案</summary>

1. **降级策略**：画像/模型/Redis 故障时降级
2. **限流熔断**：防止雪崩
3. **监控告警**：快速发现问题
4. **灰度发布**：安全上线新功能
5. **A/B 测试**：科学决策
6. **容量规划**：提前准备资源
</details>

---

*本文档基于 DSP 高并发系统设计生产实战整理。*