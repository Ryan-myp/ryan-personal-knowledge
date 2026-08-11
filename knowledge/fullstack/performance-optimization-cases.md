# 性能优化实战案例库

> 本文档收录真实广告系统性能优化案例，涵盖数据库优化、缓存策略、并发控制等。
> 适用对象：后端工程师、性能优化工程师、技术负责人

---

## 案例 1：MySQL 慢查询优化 — 从 2s 到 50ms

### 1.1 问题现象

```sql
-- 某竞价查询，执行时间 2.1s
EXPLAIN SELECT * FROM bid_record 
WHERE user_id = 12345 
  AND campaign_id IN (SELECT id FROM campaign WHERE status = 1)
  AND create_time > '2024-01-01'
ORDER BY create_time DESC
LIMIT 20;
```

**执行计划分析**：
| id | select_type | table | type | key | rows | Extra |
|----|-------------|-------|------|-----|------|-------|
| 1 | PRIMARY | bid_record | ALL | NULL | 5000000 | Using where; Using filesort |
| 2 | SUBQUERY | campaign | ALL | NULL | 10000 | Using where |

**问题识别**：
1. `bid_record` 全表扫描 500 万行
2. 没有 `user_id` 索引
3. `campaign_id` IN 子查询导致 nested loop
4. `create_time` 范围查询后还要 filesort

### 1.2 优化方案

**第一步：添加联合索引**
```sql
-- 原始表结构
CREATE TABLE bid_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    campaign_id INT NOT NULL,
    bid_price DECIMAL(10,4),
    create_time DATETIME NOT NULL,
    INDEX idx_user (user_id)
);

-- 优化后：复合索引 (user_id, create_time)
ALTER TABLE bid_record 
ADD INDEX idx_user_time (user_id, create_time);

-- 覆盖索引避免回表
ALTER TABLE bid_record
ADD INDEX idx_user_campaign_time (user_id, campaign_id, create_time, bid_price);
```

**第二步：改写 SQL**
```sql
-- 优化前
SELECT * FROM bid_record 
WHERE user_id = 12345 
  AND campaign_id IN (SELECT id FROM campaign WHERE status = 1)
  AND create_time > '2024-01-01'
ORDER BY create_time DESC
LIMIT 20;

-- 优化后：JOIN 替代 IN
SELECT b.* FROM bid_record b
INNER JOIN campaign c ON b.campaign_id = c.id
WHERE b.user_id = 12345
  AND c.status = 1
  AND b.create_time > '2024-01-01'
ORDER BY b.create_time DESC
LIMIT 20;
```

**第三步：结果验证**
```sql
EXPLAIN SELECT b.* FROM bid_record b
INNER JOIN campaign c ON b.campaign_id = c.id
WHERE b.user_id = 12345
  AND c.status = 1
  AND b.create_time > '2024-01-01'
ORDER BY b.create_time DESC
LIMIT 20;
```

| id | select_type | table | type | key | rows | Extra |
|----|-------------|-------|------|-----|------|-------|
| 1 | PRIMARY | b | ref | idx_user_time | 1 | Using index condition |
| 1 | PRIMARY | c | eq_ref | PRIMARY | 1 | Using where |
| 2 | DERIVED | c | ALL | NULL | 10000 | Using where |

### 1.3 效果对比

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 执行时间 | 2100ms | 45ms | **46x** |
| 扫描行数 | 5,000,000 | 20 | **250,000x** |
| I/O | 全表扫描 | 索引扫描 | 大幅减少 |

### 1.4 关键经验

1. **索引选择顺序**：等值条件在前，范围条件在后
2. **覆盖索引**：SELECT 字段全在索引中，避免回表
3. **JOIN vs IN**：大数据量用 JOIN，小数据量 IN 也可
4. **执行计划验证**：优化前后必须对比 EXPLAIN

---

## 案例 2：Redis 缓存穿透优化

### 2.1 问题现象

```
日志：每秒 10 万次缓存 miss，打到 MySQL
现象：MySQL QPS 飙升到 8 万，CPU 100%
```

**攻击特征**：
- 特定 user_id 不存在（如 -1, 0, 99999999）
- 恶意请求持续打穿缓存

### 2.2 解决方案

**方案一：布隆过滤器**
```go
type BloomFilter struct {
    bf      *bloom.BloomFilter
    redis   *redis.Client
}

func (b *BloomFilter) IsExist(userID int64) bool {
    return b.bf.Test([]byte(strconv.FormatInt(userID, 10)))
}

func (b *BloomFilter) Add(userID int64) {
    b.bf.Add([]byte(strconv.FormatInt(userID, 10)))
}
```

**方案二：空值缓存**
```go
func (s *UserService) GetUser(userID int64) (*User, error) {
    // 1. 检查缓存
    cacheKey := fmt.Sprintf("user:%d", userID)
    data, err := s.redis.Get(ctx, cacheKey).Bytes()
    if err == nil {
        var user User
        json.Unmarshal(data, &user)
        return &user, nil
    }
    
    // 2. 检查是否是空值标记
    if s.redis.Exists(ctx, cacheKey).Val() {
        return nil, ErrUserNotFound
    }
    
    // 3. 查询数据库
    user, err := s.db.GetUser(ctx, userID)
    if err != nil {
        // 4. 缓存空值，防止穿透
        s.redis.Set(ctx, cacheKey, "", 5*time.Minute)
        return nil, err
    }
    
    // 5. 缓存真实数据
    s.redis.Set(ctx, cacheKey, user, 30*time.Minute)
    return user, nil
}
```

**方案三：参数校验**
```go
func (s *UserService) ValidateUserID(userID int64) error {
    // 负数、0、超大值直接拒绝
    if userID <= 0 || userID > 1000000000 {
        return errors.New("invalid user_id")
    }
    return nil
}
```

### 2.3 效果对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 缓存命中率 | 15% | 95% |
| MySQL QPS | 80,000 | 8,000 |
| 响应时间 | 500ms | 5ms |

---

## 案例 3：高并发竞价限流

### 3.1 问题

```
场景：大促期间，QPS 从 1 万飙升至 50 万
问题：下游 DSP 服务被打挂，整体超时
```

### 3.2 解决方案：多级限流

```go
type RateLimiter struct {
    local    *Limiter      // 本地令牌桶
    remote   *redis.Client // Redis 分布式限流
    quota    int           // 每分钟配额
}

func (r *RateLimiter) Allow(ctx context.Context, userID string) bool {
    // 第一层：本地限流（快速拒绝）
    if !r.local.Allow() {
        return false
    }
    
    // 第二层：Redis 分布式限流
    key := fmt.Sprintf("rate:%s:%d", userID, time.Now().Minute())
    count := r.remote.Incr(ctx, key).Val()
    if count == 1 {
        r.redis.Expire(ctx, key, 60)
    }
    return count <= int64(r.quota)
}
```

### 3.3 令牌桶实现

```go
type TokenBucket struct {
    tokens     float64
    maxTokens  float64
    refillRate float64 // tokens/second
    lastRefill time.Time
    mu         sync.Mutex
}

func (b *TokenBucket) Allow() bool {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    now := time.Now()
    elapsed := now.Sub(b.lastRefill).Seconds()
    b.tokens += elapsed * b.refillRate
    if b.tokens > b.maxTokens {
        b.tokens = b.maxTokens
    }
    b.lastRefill = now
    
    if b.tokens >= 1 {
        b.tokens--
        return true
    }
    return false
}
```

---

## 案例 4：Redis 缓存击穿

### 4.1 问题

```
现象：热点 key 过期瞬间，大量请求打到 MySQL
影响：MySQL CPU 飙升，响应超时
```

### 4.2 解决方案：互斥锁

```go
func (s *CacheService) GetWithMutex(ctx context.Context, key string, builder func() (interface{}, error)) (interface{}, error) {
    // 1. 从缓存获取
    data, err := s.redis.Get(ctx, key).Result()
    if err == nil {
        return s.deserialize(data), nil
    }
    
    // 2. 缓存 miss，尝试获取分布式锁
    lockKey := fmt.Sprintf("lock:%s", key)
    locked, err := s.redis.SetNX(ctx, lockKey, "1", 10*time.Second).Result()
    if err != nil || !locked {
        // 3. 获取锁失败，短暂等待后重试
        time.Sleep(50 * time.Millisecond)
        return s.GetWithMutex(ctx, key, builder)
    }
    
    defer s.redis.Del(ctx, lockKey)
    
    // 4. 双重检查
    data, err = s.redis.Get(ctx, key).Result()
    if err == nil {
        return s.deserialize(data), nil
    }
    
    // 5. 构建数据
    result, err := builder()
    if err != nil {
        return nil, err
    }
    
    // 6. 写入缓存
    serialized, _ := s.serialize(result)
    s.redis.Set(ctx, key, serialized, 30*time.Minute)
    
    return result, nil
}
```

---

## 案例 5：消息队列堆积

### 5.1 问题

```
现象：Kafka 消息堆积 500 万条
原因：消费者处理速度跟不上生产速度
```

### 5.2 解决方案

**方案一：水平扩展消费者**
```go
// 启动多个 consumer group
func StartConsumers(topics []string, batchSize int) {
    for i := 0; i < 10; i++ { // 10 个消费者实例
        go func(instanceID int) {
            consumer, _ := kafka.NewConsumer(...)
            consumer.Subscribe(topics...)
            
            for msg := range consumer.Messages() {
                processBatch(msg, batchSize)
            }
        }(i)
    }
}
```

**方案二：批量处理**
```go
func processBatch(messages []*kafka.Message) {
    // 批量插入 MySQL
    tx, _ := db.Begin()
    for _, msg := range messages {
        insertIntoDB(tx, msg)
    }
    tx.Commit()
}
```

**方案三：背压机制**
```go
type BackpressureController struct {
    queueSize int
    maxQueue  int
}

func (c *BackpressureController) ShouldAccept() bool {
    return c.queueSize < c.maxQueue
}

func (c *BackpressureController) OnMessageReceived() {
    c.queueSize++
}

func (c *BackpressureController) OnMessageProcessed() {
    c.queueSize--
}
```

---

## 案例 6：数据库连接池泄漏

### 6.1 问题

```
日志：connection pool exhausted
原因：长时间查询占用连接不释放
```

### 6.2 解决方案

```go
func initDB() *sql.DB {
    db, _ := sql.Open("mysql", dsn)
    
    // 设置连接池参数
    db.SetMaxOpenConns(50)      // 最大连接数
    db.SetMaxIdleConns(20)      // 最大空闲连接
    db.SetConnMaxLifetime(5 * time.Minute)  // 连接最大生命周期
    db.SetConnMaxIdleTime(2 * time.Minute)  // 空闲连接回收时间
    
    return db
}

// 使用连接超时
func queryWithTimeout(ctx context.Context, db *sql.DB, query string) (*sql.Rows, error) {
    ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
    defer cancel()
    
    return db.QueryContext(ctx, query)
}
```

---

## 案例 7：Go 协程泄漏

### 7.1 问题

```
现象：Goroutine 数量持续增长
原因：channel 未正确关闭
```

### 7.2 排查

```go
// pprof 查看 goroutine 详情
import _ "net/http/pprof"

// 访问 http://localhost:6060/debug/pprof/goroutine?debug=2
```

### 7.3 修复

```go
// ❌ 错误：忘记关闭 channel
func producer(ch chan int) {
    for i := 0; i < 10; i++ {
        ch <- i
    }
    // 忘记 close(ch)
}

// ✅ 正确：确保关闭 channel
func producer(ch chan int) {
    defer close(ch)
    for i := 0; i < 10; i++ {
        ch <- i
    }
}

// 使用 done channel 控制退出
func worker(ctx context.Context, wg *sync.WaitGroup) {
    defer wg.Done()
    for {
        select {
        case <-ctx.Done():
            return
        case data := <-ch:
            process(data)
        }
    }
}
```

---

## 案例 8：gRPC 服务降级

### 8.1 问题

```
场景：竞价高峰期，下游 DSP 服务响应超时
影响：主流程阻塞，用户体验差
```

### 8.2 解决方案

```go
func (s *AuctionService) Bid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
    // 设置超时
    ctx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
    defer cancel()
    
    // 并行调用多个 DSP
    type result struct {
        resp *BidResponse
        err  error
    }
    
    ch := make(chan result, len(s.dspClients))
    var wg sync.WaitGroup
    
    for _, dsp := range s.dspClients {
        wg.Add(1)
        go func(dsp DSPClient) {
            defer wg.Done()
            resp, err := dsp.Bid(ctx, req)
            ch <- result{resp, err}
        }(dsp)
    }
    
    wg.Wait()
    close(ch)
    
    // 收集结果，选择最优
    var wins []*BidResponse
    for r := range ch {
        if r.err == nil && r.resp.Price >= req.FloorPrice {
            wins = append(wins, r.resp)
        }
    }
    
    if len(wins) == 0 {
        // 降级：返回空响应，不阻塞主流程
        return &BidResponse{}, nil
    }
    
    return selectBestBid(wins), nil
}
```

---

## 总结

### 优化原则 Checklist

- [ ] 慢查询必须加索引，避免全表扫描
- [ ] 热点数据必须缓存，设置合理 TTL
- [ ] 空查询结果也要缓存，防止穿透
- [ ] 大流量必须限流，保护下游服务
- [ ] 消息堆积必须扩容或降级
- [ ] 连接池必须设置超时，防止泄漏
- [ ] Goroutine 必须正确退出，防止泄漏
- [ ] 服务必须实现降级，保证可用性

---

*最后更新：2026-08-11*
*作者：Ryan*
